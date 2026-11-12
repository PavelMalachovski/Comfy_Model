"""Copy the trained persona LoRAs from the running pod to out/dev/loras/ (git-ignored backup).

    .venv/bin/python scripts/fetch_loras.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from comfy_model import remote
from comfy_model.runpod_pod import current_pod

REMOTE = "/workspace/ComfyUI/models/loras/"
DEST = Path("out/dev/loras")


def main() -> int:
    pod = current_pod()
    if pod is None:
        print("no running pod", file=sys.stderr)
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    ssh = " ".join(["ssh", *remote._ssh_opts(), "-p", str(pod.ssh_port)])
    argv = ["rsync", "-rltz", "--include=*.safetensors", "--exclude=*", "-e", ssh,
            f"root@{pod.ssh_host}:{REMOTE}", str(DEST) + "/"]
    rc = subprocess.run(argv).returncode
    for f in sorted(DEST.glob("*.safetensors")):
        print(f"{f}  {f.stat().st_size / 1e6:.0f} MB")
    return rc


if __name__ == "__main__":
    sys.exit(main())
