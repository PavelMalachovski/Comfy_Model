"""ssh / rsync command lines for the pod, and a streaming runner."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from comfy_model.runpod_pod import PodInfo

# Per-project known_hosts: RunPod reuses public ip:port pairs across pods, so a
# global known_hosts would eventually refuse a new pod's host key. `cm pod up`
# clears this file for every new pod; accept-new pins the key for the pod's life.
KNOWN_HOSTS = ".cm/known_hosts"


def _ssh_opts(connect_timeout: int = 15) -> list[str]:
    return [
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={KNOWN_HOSTS}",
        "-o", f"ConnectTimeout={connect_timeout}",
    ]


def ssh_argv(
    pod: PodInfo, command: str | None = None, *, connect_timeout: int = 15, batch_mode: bool = False
) -> list[str]:
    """``batch_mode``: never prompt (fail instead), for unattended best-effort checks."""
    opts = _ssh_opts(connect_timeout) + (["-o", "BatchMode=yes"] if batch_mode else [])
    argv = ["ssh", *opts, "-p", str(pod.ssh_port), f"root@{pod.ssh_host}"]
    if command:
        argv.append(command)
    return argv


def rsync_argv(pod: PodInfo, local: list[Path], remote_dir: str) -> list[str]:
    """Copy each local path (a directory is copied as itself, not its contents)
    into ``remote_dir`` on the pod."""
    ssh = " ".join(["ssh", *_ssh_opts(), "-p", str(pod.ssh_port)])
    return [
        "rsync", "-az", "--exclude=__pycache__", "-e", ssh,
        *(str(Path(p)) for p in local),
        f"root@{pod.ssh_host}:{remote_dir}",
    ]


def capture(argv: list[str], timeout_s: float) -> tuple[int, str]:
    """Run ``argv`` capturing stdout; ``(rc, stdout)``. A missing binary or a run
    longer than ``timeout_s`` gives a non-zero rc and empty output, never an exception."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, ""
    except OSError:
        return 127, ""
    return r.returncode, r.stdout


def run(argv: list[str]) -> int:
    """Run ``argv`` with output streamed to the terminal; returns the exit code."""
    try:
        return subprocess.run(argv).returncode
    except OSError as e:
        print(f"cannot run {argv[0]}: {e}", file=sys.stderr)
        return 127
