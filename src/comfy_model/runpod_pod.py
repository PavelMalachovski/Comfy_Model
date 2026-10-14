"""RunPod pod lifecycle (create / wait / terminate) and the local pod state file.

All SDK calls go through the module attribute ``runpod`` so tests can replace it.
Secret values are passed to the SDK only; nothing here prints or logs them.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from comfy_model.config import ConfigError, Secrets, Settings, load_secrets

STATE_PATH = Path(".cm/pod.json")
PUBKEY_PATH = Path("~/.ssh/id_ed25519.pub")
POD_NAME = "cm-comfyui"
CONTAINER_DISK_GB = 20

# The runpod SDK module, imported on first use (`import runpod` costs ~2 s, which
# every `cm` command would otherwise pay). Tests replace this attribute.
runpod: Any = None


class PodError(RuntimeError):
    """RunPod pod could not be created, reached or tracked."""


@dataclass(frozen=True)
class PodInfo:
    id: str
    ssh_host: str
    ssh_port: int
    comfy_url: str


def comfy_url(pod_id: str, port: int = 8188) -> str:
    return f"https://{pod_id}-{port}.proxy.runpod.net"


def _sdk() -> Any:
    global runpod
    if runpod is None:
        import runpod as sdk

        runpod = sdk
    return runpod


def _api() -> Any:
    """The SDK module, with ``api_key`` set (from .env/environment if not yet)."""
    sdk = _sdk()
    if not getattr(sdk, "api_key", None):
        sdk.api_key = load_secrets().require("RUNPOD_API_KEY")
    return sdk


def configure(secrets: Secrets) -> None:
    """Use ``secrets``' RUNPOD_API_KEY for SDK calls (no-op if it has none; the
    first API call then raises a ConfigError naming the key)."""
    key = secrets.get("RUNPOD_API_KEY")
    if key:
        _sdk().api_key = key


def _read_pubkey(path: Path) -> str:
    try:
        key = Path(path).expanduser().read_text(encoding="utf-8").strip()
    except OSError:
        key = ""
    if not key:
        raise ConfigError(
            f"no SSH public key at {path}: create one with `ssh-keygen -t ed25519`"
        )
    return key


def create(settings: Settings, secrets: Secrets, *, pubkey_path: Path | None = None) -> str:
    """Create the GPU pod with the network volume mounted at /workspace; returns its id."""
    api_key = secrets.require("RUNPOD_API_KEY")
    volume_id = secrets.require("RUNPOD_VOLUME_ID")
    pubkey = _read_pubkey(pubkey_path or PUBKEY_PATH)
    env = {
        "PUBLIC_KEY": pubkey,
        "RUNPOD_API_KEY": api_key,
        "IDLE_TIMEOUT_MIN": f"{settings.idle_timeout_min:g}",
        "MAX_RUNTIME_H": f"{settings.max_runtime_h:g}",
        "COMFY_PORT": str(settings.comfy_port),
    }
    hf_token = secrets.get("HF_TOKEN")
    if hf_token:
        env["HF_TOKEN"] = hf_token
    sdk = _sdk()
    sdk.api_key = api_key
    pod = sdk.create_pod(
        name=POD_NAME,
        image_name=settings.image,
        gpu_type_id=settings.gpu_type,
        cloud_type="SECURE",
        gpu_count=1,
        network_volume_id=volume_id,
        volume_mount_path="/workspace",
        container_disk_in_gb=CONTAINER_DISK_GB,
        ports=f"{settings.comfy_port}/http,22/tcp",
        support_public_ip=True,
        env=env,
        data_center_id=settings.datacenter,
    )
    pod_id = pod.get("id") if isinstance(pod, dict) else None
    if not pod_id:
        raise PodError("RunPod did not return a pod id; check the RunPod console for a stray pod")
    return str(pod_id)


def _public_ssh(pod: dict) -> tuple[str, int] | None:
    runtime = pod.get("runtime") or {}
    for p in runtime.get("ports") or []:
        if (
            isinstance(p, dict)
            and p.get("privatePort") == 22
            and p.get("type") == "tcp"
            and p.get("isIpPublic")
            and p.get("ip")
            and p.get("publicPort")
        ):
            return str(p["ip"]), int(p["publicPort"])
    return None


def wait_ready(
    pod_id: str,
    timeout_s: float = 600,
    *,
    comfy_port: int = 8188,
    poll_s: float = 5,
    sleep: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
) -> PodInfo:
    """Poll ``get_pod`` until the public SSH port mapping appears."""
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    api = _api()
    deadline = clock() + timeout_s
    last_error = ""
    while True:
        try:
            pod = api.get_pod(pod_id)
        except Exception as e:  # transient API/network errors: keep polling until deadline
            last_error = f" (last API error: {type(e).__name__}: {e})"
        else:
            if pod is None:
                raise PodError(f"pod {pod_id} disappeared while starting")
            ssh = _public_ssh(pod) if isinstance(pod, dict) else None
            if ssh:
                return PodInfo(id=pod_id, ssh_host=ssh[0], ssh_port=ssh[1],
                               comfy_url=comfy_url(pod_id, comfy_port))
        remaining = deadline - clock()
        if remaining <= 0:
            raise PodError(f"pod {pod_id} not ready after {timeout_s:g}s (no public SSH port){last_error}")
        sleep(min(poll_s, remaining))


def terminate(pod_id: str) -> None:
    _api().terminate_pod(pod_id)


def exists(pod_id: str) -> bool:
    """True while RunPod still knows the pod (API errors propagate)."""
    pod = _api().get_pod(pod_id)
    return isinstance(pod, dict) and pod.get("desiredStatus") != "TERMINATED"


# -- local state ----------------------------------------------------------------
def save_state(pod: PodInfo, state: Path = STATE_PATH) -> None:
    state = Path(state)
    state.parent.mkdir(parents=True, exist_ok=True)
    data = {**asdict(pod), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    tmp = state.with_name(f".{state.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, state)


def clear_state(state: Path = STATE_PATH) -> None:
    Path(state).unlink(missing_ok=True)


def load_state(state: Path = STATE_PATH) -> dict | None:
    """The state file as a dict, ``None`` if absent; ``PodError`` if unreadable
    (left in place: it may point at a pod that is still billing)."""
    state = Path(state)
    try:
        raw = state.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as e:
        raise PodError(f"cannot read {state}: {e}") from None
    try:
        data = json.loads(raw)
        PodInfo(id=str(data["id"]), ssh_host=str(data["ssh_host"]),
                ssh_port=int(data["ssh_port"]), comfy_url=str(data["comfy_url"]))
    except (ValueError, KeyError, TypeError):
        raise PodError(
            f"{state} is corrupt; check the RunPod console for a running pod, then delete the file"
        ) from None
    return data


def current_pod(state: Path = STATE_PATH) -> PodInfo | None:
    """The tracked pod if it still exists. A stale state file (pod already
    removed, e.g. by the watchdog) is deleted and ``None`` returned."""
    data = load_state(state)
    if data is None:
        return None
    info = PodInfo(id=str(data["id"]), ssh_host=str(data["ssh_host"]),
                   ssh_port=int(data["ssh_port"]), comfy_url=str(data["comfy_url"]))
    if not exists(info.id):
        clear_state(state)
        return None
    return info
