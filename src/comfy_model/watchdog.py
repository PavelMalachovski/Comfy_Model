"""Idle/max-runtime watchdog. Runs ON the pod (rsynced, run with system python).

Stdlib only, no imports from comfy_model: `python3 /workspace/cm/watchdog.py`.
Terminates the pod after IDLE_TIMEOUT_MIN idle or MAX_RUNTIME_H total.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BUSY_FILE = Path("/workspace/.cm/busy")
LOG_FILE = Path("/workspace/.cm/watchdog.log")
POLL_S = 30.0


def decide(
    now: float,
    started_at: float,
    last_busy_at: float,
    busy: bool,
    idle_timeout_s: float,
    max_runtime_s: float,
) -> str | None:
    if now - started_at >= max_runtime_s:
        return "max_runtime"
    if not busy and now - last_busy_at >= idle_timeout_s:
        return "idle"
    return None


def comfy_busy(base_url: str) -> bool:
    """True if ComfyUI has running/pending jobs. Unreachable or garbled -> False."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/queue", timeout=5) as r:
            q = json.load(r)
        return bool(q.get("queue_running")) or bool(q.get("queue_pending"))
    except Exception:
        return False


def ssh_busy(
    path: Path = BUSY_FILE, now: float | None = None, max_age_s: float = 600
) -> bool:
    """True if the heartbeat file (written by `cm lora train`) is fresh."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return (time.time() if now is None else now) - mtime < max_age_s


def run_loop(now, sleep, busy, terminate, idle_timeout_s, max_runtime_s, poll_s=POLL_S):
    """Poll until a shutdown decision is made; call terminate(reason) and return it."""
    started_at = last_busy_at = now()
    while True:
        t = now()
        is_busy = busy()
        if is_busy:
            last_busy_at = t
        reason = decide(t, started_at, last_busy_at, is_busy, idle_timeout_s, max_runtime_s)
        if reason:
            terminate(reason)
            return reason
        sleep(poll_s)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_FILE.open("a") as f:
        f.write(f"{stamp} {msg}\n")


def main() -> int:
    idle_s = float(os.environ.get("IDLE_TIMEOUT_MIN", "15")) * 60
    max_s = float(os.environ.get("MAX_RUNTIME_H", "4")) * 3600
    url = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
    pod_id = os.environ.get("RUNPOD_POD_ID")
    if not pod_id:
        _log("RUNPOD_POD_ID not set; watchdog cannot terminate the pod, exiting")
        print("RUNPOD_POD_ID not set", file=sys.stderr)
        return 1

    def terminate(reason: str) -> None:
        _log(f"terminating pod {pod_id}: reason={reason}")
        subprocess.run(["runpodctl", "remove", "pod", pod_id], check=False)

    _log(f"watchdog started: idle={idle_s:.0f}s max_runtime={max_s:.0f}s comfy={url}")
    run_loop(
        now=time.time,
        sleep=time.sleep,
        busy=lambda: comfy_busy(url) or ssh_busy(),
        terminate=terminate,
        idle_timeout_s=idle_s,
        max_runtime_s=max_s,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
