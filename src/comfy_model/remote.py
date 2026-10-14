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


def _ssh_opts() -> list[str]:
    return [
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={KNOWN_HOSTS}",
        "-o", "ConnectTimeout=15",
    ]


def ssh_argv(pod: PodInfo, command: str | None = None) -> list[str]:
    argv = ["ssh", *_ssh_opts(), "-p", str(pod.ssh_port), f"root@{pod.ssh_host}"]
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


def run(argv: list[str]) -> int:
    """Run ``argv`` with output streamed to the terminal; returns the exit code."""
    try:
        return subprocess.run(argv).returncode
    except OSError as e:
        print(f"cannot run {argv[0]}: {e}", file=sys.stderr)
        return 127
