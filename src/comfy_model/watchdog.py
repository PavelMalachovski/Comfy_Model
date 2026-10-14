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

BUSY_FILE = Path("/workspace/.cm/busy")  # `cm lora train` heartbeat
BOOTSTRAP_BUSY_FILE = Path("/workspace/.cm/busy.bootstrap")  # pod/bootstrap.sh heartbeat
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
    path: Path | None = None, now: float | None = None, max_age_s: float = 600
) -> bool:
    """True if a heartbeat file is fresh: ``path`` if given, else either the
    `cm lora train` file or the bootstrap file."""
    paths = [path] if path is not None else [BUSY_FILE, BOOTSTRAP_BUSY_FILE]
    t = time.time() if now is None else now
    for p in paths:
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if t - mtime < max_age_s:
            return True
    return False


def run_loop(now, sleep, busy, terminate, idle_timeout_s, max_runtime_s, poll_s=POLL_S):
    """Poll until a shutdown decision is made and terminate(reason) succeeds (returns
    truthy); a failed terminate is retried on every following poll."""
    started_at = last_busy_at = now()
    while True:
        t = now()
        is_busy = busy()
        if is_busy:
            last_busy_at = t
        reason = decide(t, started_at, last_busy_at, is_busy, idle_timeout_s, max_runtime_s)
        if reason and terminate(reason):
            return reason
        # No decision yet, or terminate failed: keep polling and retry next time.
        sleep(poll_s)


def _log(msg: str) -> None:
    """Best-effort log line; never raises (falls back to stderr)."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"{stamp} {msg}"
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"{line} (log file unavailable: {e})", file=sys.stderr)


def _env_positive(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        val = float(raw)
        if val > 0 and val == val and val != float("inf"):
            return val
    except ValueError:
        pass
    _log(f"invalid {name}={raw!r}; using default {default}")
    return default


def remove_pod(pod_id: str, timeout_s: float = 60) -> bool:
    """Run `runpodctl remove pod`; True only on exit code 0. Never raises."""
    try:
        r = subprocess.run(
            ["runpodctl", "remove", "pod", pod_id],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log(f"runpodctl remove pod {pod_id} failed: {type(e).__name__}: {e}")
        return False
    if r.returncode != 0:
        _log(
            f"runpodctl remove pod {pod_id} failed: rc={r.returncode} "
            f"stderr={(r.stderr or '').strip()[:500]}"
        )
        return False
    return True


def main() -> int:
    pod_id = os.environ.get("RUNPOD_POD_ID")
    if not pod_id:
        _log("RUNPOD_POD_ID not set; watchdog cannot terminate the pod, exiting")
        print("RUNPOD_POD_ID not set", file=sys.stderr)
        return 1
    idle_s = _env_positive("IDLE_TIMEOUT_MIN", 15) * 60
    max_s = _env_positive("MAX_RUNTIME_H", 4) * 3600
    url = os.environ.get("COMFY_URL") or "http://127.0.0.1:8188"

    def terminate(reason: str) -> bool:
        _log(f"terminating pod {pod_id}: reason={reason}")
        return remove_pod(pod_id)

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
