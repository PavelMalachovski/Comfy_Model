#!/usr/bin/env bash
# Idempotent pod bootstrap: run ON the pod by `cm pod up` as
#   bash /workspace/cm/pod/bootstrap.sh
# Everything lives on the network volume (/workspace): venv, ComfyUI, custom
# nodes, models. Re-running only does what is missing.
#
#   bash bootstrap.sh --print-downloads   print "url dest_path" per pod/models.yaml
#                                         entry and exit (no downloads, no side effects;
#                                         python with PyYAML taken from $CM_PY or python3)
#
# Never enable xtrace here: the environment holds RUNPOD_API_KEY and HF_TOKEN.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$HERE/models.yaml"
WS=/workspace
CM_DIR="$WS/cm"
STATE_DIR="$WS/.cm"
VENV="$WS/venv"
COMFY_DIR="$WS/ComfyUI"
MODELS_DIR="$COMFY_DIR/models"
WATCHDOG_PID="/workspace/.cm/watchdog.pid"
WATCHDOG_OUT="$STATE_DIR/watchdog.out"
COMFY_PID="$STATE_DIR/comfyui.pid"
COMFY_OUT="$STATE_DIR/comfyui.out"
# Own heartbeat file: "$STATE_DIR/busy" belongs to `cm lora train` (the watchdog honours both).
BOOTSTRAP_BUSY="$STATE_DIR/busy.bootstrap"

log() { printf '[bootstrap] %s\n' "$*"; }
die() { printf '[bootstrap] ERROR: %s\n' "$*" >&2; exit 1; }
usage() { printf 'usage: %s [--print-downloads]\n' "$0" >&2; }

# "url dest_path" for every manifest entry (same URL rule as comfy_model.workflow).
manifest_downloads() {
    "$1" - "$MANIFEST" "$MODELS_DIR" <<'PY'
import sys
import yaml

manifest, models_dir = sys.argv[1], sys.argv[2]
with open(manifest, encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
for m in data.get("models") or []:
    url = m.get("url") or "https://huggingface.co/{}/resolve/main/{}".format(m["repo"], m["path"])
    print(url, "{}/{}/{}".format(models_dir, m["dest"], m["file"]))
PY
}

case "${1:-}" in
    --print-downloads)
        manifest_downloads "${CM_PY:-python3}"
        exit 0
        ;;
    "") ;;
    *) usage; exit 2 ;;
esac

# --- environment ----------------------------------------------------------------
# RunPod injects pod env vars into PID 1 only; SSH sessions do not see them.
# (Unreadable /proc/1/environ -> nothing imported; RUNPOD_POD_ID check below fails.)
while IFS= read -r -d '' kv; do
    case "$kv" in
        RUNPOD_POD_ID=*|RUNPOD_API_KEY=*|HF_TOKEN=*|IDLE_TIMEOUT_MIN=*|MAX_RUNTIME_H=*|COMFY_PORT=*)
            export "${kv?}" ;;
    esac
done < <(cat /proc/1/environ 2>/dev/null || true)
COMFY_PORT="${COMFY_PORT:-8188}"
export NO_PROXY=127.0.0.1,localhost
export no_proxy="$NO_PROXY"
export COMFY_URL="http://127.0.0.1:${COMFY_PORT}"
[ -n "${RUNPOD_POD_ID:-}" ] || die "RUNPOD_POD_ID not set (not on a RunPod pod?); refusing to run without a watchdog"

# shellcheck source=/dev/null
. "$HERE/versions.env"
: "${COMFYUI_TAG:?}" "${IMPACT_PACK_COMMIT:?}" "${IMPACT_SUBPACK_COMMIT:?}"

# The watchdog terminates the pod with runpodctl: prove that works before relying on it
# (output discarded: it could echo credentials).
command -v runpodctl >/dev/null || die "runpodctl missing; the watchdog could not terminate this pod"
runpodctl get pod "$RUNPOD_POD_ID" >/dev/null 2>&1 \
    || die "runpodctl cannot reach the RunPod API (unauthorised?); the watchdog could not terminate this pod"

mkdir -p "$STATE_DIR"

# Is the process in pidfile $1 alive and running $2? (Pidfiles live on the
# persistent volume, so a pid from an earlier pod may now name another process.)
alive() {
    local pid
    pid="$(cat "$1" 2>/dev/null)" || return 1
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && grep -qa -- "$2" "/proc/$pid/cmdline" 2>/dev/null
}

# --- watchdog first: the pod is never unsupervised --------------------------------
start_watchdog() {
    if alive "$WATCHDOG_PID" watchdog.py; then
        log "watchdog already running (pid $(cat "$WATCHDOG_PID"))"
        return 0
    fi
    log "starting watchdog (idle ${IDLE_TIMEOUT_MIN:-15} min, max ${MAX_RUNTIME_H:-4} h)"
    setsid nohup python3 "$CM_DIR/watchdog.py" >>"$WATCHDOG_OUT" 2>&1 </dev/null &
    echo $! >"$WATCHDOG_PID"
    sleep 2
    if ! alive "$WATCHDOG_PID" watchdog.py; then
        tail -n 20 "$WATCHDOG_OUT" >&2 || true
        die "watchdog exited right after start"
    fi
}
start_watchdog

# While installing/downloading, ComfyUI is not up yet, so keep the watchdog's
# heartbeat fresh; the 4 h hard limit still applies. Stopped on exit.
# Detached from our stdout/stderr so a leftover `sleep 60` cannot hold the ssh session open.
heartbeat() { while true; do touch "$BOOTSTRAP_BUSY"; sleep 60; done; }
heartbeat >/dev/null 2>&1 </dev/null &
HEARTBEAT_PID=$!
stop_heartbeat() { kill "$HEARTBEAT_PID" 2>/dev/null || true; rm -f "$BOOTSTRAP_BUSY"; }
trap stop_heartbeat EXIT

# --- venv ------------------------------------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
    log "creating venv $VENV (reusing the image's torch)"
    python3 -m venv --system-site-packages "$VENV"
fi
PIP=("$VENV/bin/python" -m pip install -q --disable-pip-version-check)

# --- repositories at pinned refs -------------------------------------------------
# ensure_repo DIR URL REF: clone/fetch REF (tag or commit) if DIR is missing or
# was installed at another ref, then install its requirements.txt.
ensure_repo() {
    local dir="$1" url="$2" ref="$3" stamp="$1/.git/cm-ref"
    if [ -d "$dir/.git" ] && [ "$(cat "$stamp" 2>/dev/null)" = "$ref" ]; then
        return 0
    fi
    log "installing $(basename "$dir") @ $ref"
    if [ ! -d "$dir/.git" ]; then
        git init -q "$dir"
        git -C "$dir" remote add origin "$url"
    fi
    git -C "$dir" fetch -q --depth 1 origin "$ref"
    git -C "$dir" checkout -q -f FETCH_HEAD
    if [ -f "$dir/requirements.txt" ]; then
        "${PIP[@]}" -r "$dir/requirements.txt"
    fi
    echo "$ref" >"$stamp"
}

ensure_repo "$COMFY_DIR" https://github.com/comfyanonymous/ComfyUI "$COMFYUI_TAG"
ensure_repo "$COMFY_DIR/custom_nodes/ComfyUI-Impact-Pack" \
    https://github.com/ltdrdata/ComfyUI-Impact-Pack "$IMPACT_PACK_COMMIT"
ensure_repo "$COMFY_DIR/custom_nodes/ComfyUI-Impact-Subpack" \
    https://github.com/ltdrdata/ComfyUI-Impact-Subpack "$IMPACT_SUBPACK_COMMIT"

if ! "$VENV/bin/python" -c 'import yaml' 2>/dev/null; then
    "${PIP[@]}" pyyaml
fi

# --- models ----------------------------------------------------------------------
download() {
    local url="$1" dest="$2"
    if [ -f "$dest" ]; then
        return 0
    fi
    log "downloading $(basename "$dest")"
    mkdir -p "$(dirname "$dest")"
    local auth=()
    case "$url" in
        https://huggingface.co/*)
            if [ -n "${HF_TOKEN:-}" ]; then auth=(-H "Authorization: Bearer $HF_TOKEN"); fi ;;
    esac
    curl -fL -C - --retry 5 --retry-delay 5 --no-progress-meter "${auth[@]}" -o "$dest.part" "$url"
    mv "$dest.part" "$dest"
}

downloads="$(manifest_downloads "${CM_PY:-$VENV/bin/python}")"
while read -r url dest; do
    [ -n "$url" ] || continue
    download "$url" "$dest"
done <<<"$downloads"

# --- ComfyUI ---------------------------------------------------------------------
comfy_listening() { curl -sf -o /dev/null --max-time 5 "$COMFY_URL/system_stats"; }

if comfy_listening || alive "$COMFY_PID" main.py; then
    log "ComfyUI already running"
else
    log "starting ComfyUI on port $COMFY_PORT"
    (
        cd "$COMFY_DIR"
        # Keep the secrets out of ComfyUI's own environment. This is hygiene, not isolation:
        # ComfyUI (third-party nodes, unauthenticated public proxy URL) runs as root and can
        # still read them from /proc/1/environ, where RunPod puts every pod env var.
        # --disable-metadata: no prompt/workflow embedded in saved PNGs and mp4s.
        setsid nohup env -u RUNPOD_API_KEY -u HF_TOKEN "$VENV/bin/python" main.py --listen 0.0.0.0 --port "$COMFY_PORT" \
            --disable-metadata >>"$COMFY_OUT" 2>&1 </dev/null &
        echo $! >"$COMFY_PID"
    )
fi

log "done (ComfyUI log: $COMFY_OUT, watchdog log: $WATCHDOG_OUT)"
