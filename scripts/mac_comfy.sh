#!/usr/bin/env bash
# Local ComfyUI on the Mac (installed in ~/ComfyUI, see docs/guide/11-render.md).
#
#   scripts/mac_comfy.sh start    # start in the background and open http://127.0.0.1:8188
#   scripts/mac_comfy.sh stop     # stop it and free ~15-20 GB of memory
#   scripts/mac_comfy.sh status
#
# Env: COMFY_HOME (default ~/ComfyUI), COMFY_PORT (default 8188),
#      COMFY_ARGS (extra ComfyUI flags, e.g. "--cache-none --disable-smart-memory" to save memory).
set -u
HOME_DIR="${COMFY_HOME:-$HOME/ComfyUI}"
PORT="${COMFY_PORT:-8188}"
URL="http://127.0.0.1:$PORT"
LOG="$HOME_DIR/comfyui.log"

up() { curl -s -o /dev/null -w "%{http_code}" "$URL/system_stats" 2>/dev/null | grep -q 200; }
pids() { lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true; }  # the server listening on PORT

case "${1:-status}" in
  start)
    if up; then echo "already running: $URL"; exit 0; fi
    [ -x "$HOME_DIR/.venv/bin/python" ] || { echo "no ComfyUI in $HOME_DIR" >&2; exit 1; }
    cd "$HOME_DIR" || exit 1
    PYTORCH_ENABLE_MPS_FALLBACK=1 nohup .venv/bin/python main.py --listen 127.0.0.1 --port "$PORT" ${COMFY_ARGS:-} \
      > "$LOG" 2>&1 &
    for _ in $(seq 1 90); do up && break; sleep 2; done
    if up; then echo "running: $URL (log: $LOG)"; open "$URL" 2>/dev/null || true
    else echo "did not start, see $LOG" >&2; exit 1; fi
    ;;
  stop)
    p=$(pids)
    if [ -z "$p" ]; then echo "not running"; exit 0; fi
    kill $p
    for _ in $(seq 1 15); do [ -z "$(pids)" ] && break; sleep 1; done
    [ -z "$(pids)" ] && echo "stopped" || { echo "still running: $(pids)" >&2; exit 1; }
    ;;
  status)
    if up; then
      q=$(curl -s "$URL/queue" | python3 -c "import json,sys; q=json.load(sys.stdin); print(len(q.get('queue_running',[])), 'running,', len(q.get('queue_pending',[])), 'queued')" 2>/dev/null)
      echo "running: $URL ($q)"
    else
      echo "not running"
    fi
    ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
