"""`cm` entry point: batch, export, pod (up|status|down|ssh). Later tasks add lora."""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Optional

import typer

from comfy_model import remote, runpod_pod
from comfy_model.batch import run_batch
from comfy_model.comfy_client import ComfyClient, ComfyError
from comfy_model.config import ConfigError, Secrets, load_secrets, load_settings
from comfy_model.export import export_image
from comfy_model.profile import load_profile
from comfy_model.runpod_pod import PodError, PodInfo
from comfy_model.scenes import SceneError

app = typer.Typer(help="cm: ComfyUI generation on rented RunPod GPUs.", no_args_is_help=True)

NO_POD = "no running pod — run `cm pod up`"


@app.callback()
def main() -> None:
    """Root command group."""


def _make_client(url: str) -> ComfyClient:
    return ComfyClient(url)


def _configure() -> Secrets:
    """Load secrets and hand the RunPod API key (if any) to the SDK wrapper."""
    secrets = load_secrets()
    runpod_pod.configure(secrets)
    return secrets


def _redact(text: str, secrets: Secrets) -> str:
    for value in secrets.values():
        if value and len(value) >= 4:
            text = text.replace(value, "***")
    return text


def _current_pod() -> PodInfo | None:
    """``runpod_pod.current_pod()`` with every failure turned into a clean exit 1."""
    secrets: Secrets = Secrets()
    try:
        secrets = _configure()
        return runpod_pod.current_pod()
    except (ConfigError, PodError) as e:
        raise _fail(str(e)) from None
    except Exception as e:  # RunPod API / network
        raise _fail(_redact(f"cannot check the pod via the RunPod API: {type(e).__name__}: {e}", secrets)) from None


def _resolve_url(url: str | None) -> str | None:
    if url:
        return url
    pod = _current_pod()  # stale state (pod already gone) is cleared -> None
    return pod.comfy_url if pod else None


def _fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(1)


@app.command()
def batch(
    kind: str = typer.Argument(..., help="face | dataset | photo | video"),
    scenes: Path = typer.Argument(..., help="Scene YAML file."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output dir (default out/<date>-<kind>)."),
    ref: Optional[Path] = typer.Option(None, "--ref", help="Reference image (dataset)."),
    lora: Optional[str] = typer.Option(None, "--lora", help="LoRA file name on the pod (photo)."),
    strength: float = typer.Option(0.9, "--strength", help="LoRA strength (photo)."),
    url: Optional[str] = typer.Option(None, "--url", help="ComfyUI URL (default: running pod)."),
) -> None:
    """Generate every scene of SCENES; re-running skips outputs that already exist."""
    if kind not in ("face", "dataset", "photo", "video"):
        raise _fail(f"unknown kind {kind!r}; expected face, dataset, photo or video")
    base = _resolve_url(url)
    if base is None:
        raise _fail(NO_POD)
    out_dir = out or Path("out") / f"{date.today().isoformat()}-{kind}"

    def progress(scene_id: str, done: int, skipped: int, failed: int) -> None:
        typer.echo(f"{scene_id}: {done} done, {skipped} skipped, {failed} failed")

    try:
        profile = load_profile()
        client = _make_client(base)
        try:
            report = run_batch(
                kind, scenes, client, profile, out_dir,
                ref_image=ref, lora=lora, lora_strength=strength, on_scene=progress,
            )
        finally:
            close = getattr(client, "close", None)
            if close:
                close()
    except SceneError as e:
        raise _fail(str(e)) from None
    except ValueError as e:
        raise _fail(str(e)) from None
    except ComfyError as e:
        raise _fail(f"aborted: {e}") from None

    typer.echo(
        f"total: {len(report.done)} done, {len(report.skipped)} skipped, "
        f"{len(report.failed)} failed -> {out_dir}"
    )
    for name, msg in report.failed:
        typer.echo(f"  failed {name}: {msg}", err=True)
    if report.failed:
        raise typer.Exit(1)


@app.command()
def export(
    files: list[Path] = typer.Argument(..., help="Images (.png/.jpg/.webp) or videos (.mp4)."),
    to: Path = typer.Option(Path("export"), "--to", help="Destination directory."),
    grain: float = typer.Option(0.03, "--grain", help="Film grain strength (0 = none)."),
) -> None:
    """Strip metadata, add the AI label and grain; write posting-ready files."""
    missing = [f for f in files if not f.is_file()]
    if missing:
        raise _fail("file not found: " + ", ".join(str(f) for f in missing))
    for f in files:
        try:
            out = export_image(f, to, grain=grain)
        except (ValueError, OSError) as e:
            raise _fail(str(e)) from None
        typer.echo(str(out))


# -- cm pod ---------------------------------------------------------------------
pod_app = typer.Typer(help="Rent, inspect and release the RunPod GPU pod.", no_args_is_help=True)
app.add_typer(pod_app, name="pod")

SYNC_PATHS = [Path("pod"), Path("workflows"), Path("src/comfy_model/watchdog.py")]
REMOTE_DIR = "/workspace/cm/"
PREP_CMD = (
    "mkdir -p /workspace/cm && (command -v rsync >/dev/null || "
    "(export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq rsync >/dev/null))"
)
BOOTSTRAP_CMD = "bash /workspace/cm/pod/bootstrap.sh"
# kill -0 alone could match an unrelated process reusing a pid from an old pidfile
# (the pidfile lives on the persistent network volume).
WATCHDOG_CHECK = (
    'pid=$(cat /workspace/.cm/watchdog.pid) && kill -0 "$pid" && grep -qa watchdog.py "/proc/$pid/cmdline"'
)
SSH_TIMEOUT_S = 180
COMFY_TIMEOUT_S = 600

# Indirection so tests can run the polling loops instantly.
_sleep = time.sleep
_clock = time.monotonic


class _UpError(RuntimeError):
    pass


def _clear_known_hosts() -> None:
    Path(remote.KNOWN_HOSTS).unlink(missing_ok=True)


def _remote_ok(argv: list[str], what: str) -> None:
    rc = remote.run(argv)
    if rc != 0:
        raise _UpError(f"{what} failed (exit {rc})")


def _wait_ssh(pod: PodInfo) -> None:
    deadline = _clock() + SSH_TIMEOUT_S
    while remote.run(remote.ssh_argv(pod, "true")) != 0:
        if _clock() >= deadline:
            raise _UpError(f"SSH to root@{pod.ssh_host}:{pod.ssh_port} not available after {SSH_TIMEOUT_S}s")
        _sleep(5)


def _wait_comfy(url: str) -> None:
    client = _make_client(url)
    try:
        deadline = _clock() + COMFY_TIMEOUT_S
        while not client.ping():
            if _clock() >= deadline:
                raise _UpError(
                    f"ComfyUI did not answer at {url} within {COMFY_TIMEOUT_S // 60} min "
                    "(log: /workspace/.cm/comfyui.out on the pod)"
                )
            _sleep(10)
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


def _provision(pod_id: str, comfy_port: int) -> PodInfo:
    info = runpod_pod.wait_ready(pod_id, comfy_port=comfy_port)
    _clear_known_hosts()
    runpod_pod.save_state(info)  # lets `cm pod down` find the pod if this process dies
    typer.echo(f"pod {pod_id} started (ssh root@{info.ssh_host} -p {info.ssh_port}); bootstrapping ...")
    _wait_ssh(info)
    _remote_ok(remote.ssh_argv(info, PREP_CMD), "preparing /workspace/cm on the pod")
    _remote_ok(remote.rsync_argv(info, SYNC_PATHS, REMOTE_DIR), "rsync to the pod")
    _remote_ok(remote.ssh_argv(info, BOOTSTRAP_CMD), "pod bootstrap")
    if remote.run(remote.ssh_argv(info, WATCHDOG_CHECK)) != 0:
        raise _UpError("watchdog is not running on the pod (see /workspace/.cm/watchdog.out); "
                       "refusing to leave an unsupervised pod")
    typer.echo("watchdog running; waiting for ComfyUI ...")
    _wait_comfy(info.comfy_url)
    return info


def _teardown(pod_id: str, secrets: Secrets) -> None:
    try:
        runpod_pod.terminate(pod_id)
    except Exception as e:
        typer.echo(_redact(
            f"FAILED to terminate pod {pod_id} ({type(e).__name__}: {e}); it may still be billing — "
            "run `cm pod down` or terminate it in the RunPod console", secrets), err=True)
        return
    runpod_pod.clear_state()
    _clear_known_hosts()
    typer.echo(f"terminated pod {pod_id}", err=True)


@pod_app.command("up")
def pod_up() -> None:
    """Create the pod, sync files, bootstrap ComfyUI + watchdog, wait until ComfyUI answers."""
    try:
        settings = load_settings()
        secrets = _configure()
    except ConfigError as e:
        raise _fail(str(e)) from None
    missing = [str(p) for p in SYNC_PATHS if not p.exists()]
    if missing:
        raise _fail("run `cm pod up` from the repository root; missing: " + ", ".join(missing))
    existing = _current_pod()
    if existing:
        raise _fail(f"pod {existing.id} already running: {existing.comfy_url} (use it, or `cm pod down`)")

    try:
        pod_id = runpod_pod.create(settings, secrets)
    except ConfigError as e:
        raise _fail(str(e)) from None
    except Exception as e:
        raise _fail(_redact(f"pod creation failed: {type(e).__name__}: {e}", secrets)) from None
    typer.echo(f"created pod {pod_id}; waiting for it to start ...")

    try:
        info = _provision(pod_id, settings.comfy_port)
    except (Exception, KeyboardInterrupt) as e:
        msg = str(e) if isinstance(e, _UpError) else f"{type(e).__name__}: {e}"
        typer.echo(_redact(f"error: {msg}", secrets), err=True)
        _teardown(pod_id, secrets)
        raise typer.Exit(1)

    runpod_pod.save_state(info)
    typer.echo(f"ComfyUI: {info.comfy_url}")
    typer.echo(f"ssh: cm pod ssh  (root@{info.ssh_host} -p {info.ssh_port})")
    typer.echo(f"auto-off after {settings.idle_timeout_min:g} min idle / {settings.max_runtime_h:g} h max")


@pod_app.command("status")
def pod_status() -> None:
    """Show the running pod (clears stale state if the pod is gone)."""
    pod = _current_pod()
    if pod is None:
        typer.echo(NO_POD)
        return
    data = runpod_pod.load_state() or {}
    typer.echo(f"pod {pod.id} running (since {data.get('created_at', '?')})")
    client = _make_client(pod.comfy_url)
    try:
        up = client.ping()
    finally:
        close = getattr(client, "close", None)
        if close:
            close()
    typer.echo(f"ComfyUI: {pod.comfy_url} ({'up' if up else 'not responding'})")
    typer.echo(f"ssh: root@{pod.ssh_host} -p {pod.ssh_port}")


@pod_app.command("down")
def pod_down() -> None:
    """Terminate the pod and delete the local state."""
    pod = _current_pod()
    if pod is None:
        typer.echo("no running pod")
        return
    try:
        runpod_pod.terminate(pod.id)
    except Exception as e:
        raise _fail(_redact(
            f"terminate failed for pod {pod.id}: {type(e).__name__}: {e}; state kept — retry `cm pod down`",
            load_secrets())) from None
    runpod_pod.clear_state()
    _clear_known_hosts()
    typer.echo(f"terminated pod {pod.id}")


@pod_app.command("ssh")
def pod_ssh() -> None:
    """Open an interactive shell on the pod."""
    pod = _current_pod()
    if pod is None:
        raise _fail(NO_POD)
    raise typer.Exit(remote.run(remote.ssh_argv(pod)))
