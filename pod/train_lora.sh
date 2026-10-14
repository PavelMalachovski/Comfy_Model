#!/usr/bin/env bash
# LoRA training on the pod, launched by `cm lora train` over ssh as
#   bash /workspace/cm/pod/train_lora.sh <name> <trigger>      (name = <trigger>_v<N>)
# Validates, then detaches (setsid nohup) and returns; the detached supervisor
#   1. keeps /workspace/.cm/busy fresh (the watchdog must not kill a 2 h training),
#   2. installs ai-toolkit at $AI_TOOLKIT_COMMIT into /workspace/ai-toolkit if missing,
#   3. trains with /workspace/cm/training/<name>.yaml (log: /workspace/.cm/train.log),
#   4. copies <name>.safetensors into ComfyUI's loras dir and removes the busy file.
# Follow with `cm lora status`.
#
# Only HF_TOKEN is taken from the pod environment. Never enable xtrace here.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS=/workspace
STATE_DIR=/workspace/.cm
BUSY=/workspace/.cm/busy   # heartbeat file; busy.bootstrap belongs to bootstrap.sh
LOG=/workspace/.cm/train.log
PIDFILE=/workspace/.cm/train.pid
AIT_DIR="$WS/ai-toolkit"
AIT_VENV="$AIT_DIR/venv"
LORAS_DIR=/workspace/ComfyUI/models/loras
CONFIG_DIR="$WS/cm/training"

log() { printf '[train %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '[train] ERROR: %s\n' "$*" >&2; exit 1; }

# Is the process in $PIDFILE alive and one of ours? (pidfile lives on the persistent volume)
training_alive() {
    local pid
    pid="$(cat "$PIDFILE" 2>/dev/null)" || return 1
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && grep -qa train_lora.sh "/proc/$pid/cmdline" 2>/dev/null
}

# --- environment ------------------------------------------------------------------
# RunPod injects pod env vars into PID 1 only; SSH sessions do not see them.
# FLUX.1-dev is gated on Hugging Face, so HF_TOKEN is the one variable training needs.
while IFS= read -r -d '' kv; do
    case "$kv" in
        HF_TOKEN=*|COMFY_PORT=*) export "${kv?}" ;;
    esac
done < <(cat /proc/1/environ 2>/dev/null || true)
# FLUX.1-dev is ~24 GB: keep the Hugging Face cache on the network volume, not the container disk.
export HF_HOME="$WS/hf-cache"

HEARTBEAT_PID=""
cleanup() {
    if [ -n "$HEARTBEAT_PID" ]; then kill "$HEARTBEAT_PID" 2>/dev/null || true; fi
    rm -f "$BUSY" "$PIDFILE"
}

supervise() {
    local name="$1" sup_pid=$$ rc=0
    trap cleanup EXIT
    trap 'exit 143' TERM INT HUP
    (while kill -0 "$sup_pid" 2>/dev/null; do touch "$BUSY"; sleep 60; done) >/dev/null 2>&1 </dev/null &
    HEARTBEAT_PID=$!

    # shellcheck source=/dev/null
    . "$HERE/versions.env"
    : "${AI_TOOLKIT_COMMIT:?}"
    local stamp="$AIT_DIR/.git/cm-ref" venv_stamp="$AIT_VENV/.cm-installed"
    if [ ! -d "$AIT_DIR/.git" ] || [ "$(cat "$stamp" 2>/dev/null)" != "$AI_TOOLKIT_COMMIT" ]; then
        log "installing ai-toolkit @ $AI_TOOLKIT_COMMIT"
        if [ ! -d "$AIT_DIR/.git" ]; then
            git init -q "$AIT_DIR"
            git -C "$AIT_DIR" remote add origin https://github.com/ostris/ai-toolkit
        fi
        git -C "$AIT_DIR" fetch -q origin "$AI_TOOLKIT_COMMIT" \
            || git -C "$AIT_DIR" fetch -q origin
        git -C "$AIT_DIR" checkout -q -f "$AI_TOOLKIT_COMMIT"
        git -C "$AIT_DIR" submodule update --init --recursive -q
        echo "$AI_TOOLKIT_COMMIT" >"$stamp"
    fi
    if [ "$(cat "$venv_stamp" 2>/dev/null)" != "$AI_TOOLKIT_COMMIT" ]; then
        # Own venv (image torch reused): ai-toolkit's pins must not disturb ComfyUI's /workspace/venv.
        log "installing ai-toolkit requirements"
        [ -x "$AIT_VENV/bin/python" ] || python3 -m venv --system-site-packages "$AIT_VENV"
        "$AIT_VENV/bin/python" -m pip install -q --disable-pip-version-check -r "$AIT_DIR/requirements.txt"
        echo "$AI_TOOLKIT_COMMIT" >"$venv_stamp"
    fi

    log "training $name (config $CONFIG_DIR/$name.yaml)"
    (cd "$AIT_DIR" && "$AIT_VENV/bin/python" run.py "$CONFIG_DIR/$name.yaml") || rc=$?
    if [ "$rc" -ne 0 ]; then
        log "FAILED: training exited with code $rc"
        return "$rc"
    fi

    local out="$AIT_DIR/output/$name/$name.safetensors"
    if [ ! -f "$out" ]; then
        log "FAILED: training finished but $out does not exist"
        return 1
    fi
    mkdir -p "$LORAS_DIR"
    cp "$out" "$LORAS_DIR/$name.safetensors.part"
    mv "$LORAS_DIR/$name.safetensors.part" "$LORAS_DIR/$name.safetensors"
    log "DONE: $LORAS_DIR/$name.safetensors (use with: cm batch photo ... --lora $name.safetensors)"
}

if [ "${1:-}" = "--supervise" ]; then
    [ -n "${2:-}" ] || die "usage: $0 --supervise <name>"
    supervise "$2"
    exit $?
fi

# --- launcher: validate synchronously so problems show up in the ssh session -------
[ $# -eq 2 ] || { printf 'usage: %s <name> <trigger>\n' "$0" >&2; exit 2; }
NAME="$1"
TRIGGER="$2"
[[ "$NAME" =~ ^[A-Za-z0-9_.-]+$ && "$TRIGGER" =~ ^[A-Za-z0-9_.-]+$ ]] || die "invalid name or trigger"

[ -n "${HF_TOKEN:-}" ] || die "HF_TOKEN is not set on the pod. FLUX.1-dev is gated: accept its license on Hugging Face, put HF_TOKEN in .env, and recreate the pod (cm pod down; cm pod up)"
[ -f "$CONFIG_DIR/$NAME.yaml" ] || die "training config $CONFIG_DIR/$NAME.yaml missing (run via cm lora train)"
[ -d "$WS/dataset/$TRIGGER" ] || die "dataset $WS/dataset/$TRIGGER missing (run via cm lora train)"
[ -d "$WS/ComfyUI/models" ] || die "ComfyUI not installed on the pod (run cm pod up first)"
mkdir -p "$STATE_DIR"
if training_alive; then
    die "a training is already running (pid $(cat "$PIDFILE")); follow it with cm lora status"
fi

# The resident ComfyUI may still hold Flux in VRAM (24 GB card): ask it to unload
# so quantized training fits. Best effort. --noproxy: this is a local call.
if ! curl -fsS --noproxy '*' -m 10 -X POST "http://127.0.0.1:${COMFY_PORT:-8188}/free" \
        -H 'Content-Type: application/json' -d '{"unload_models":true,"free_memory":true}' >/dev/null; then
    log "WARNING: could not ask ComfyUI to free VRAM; training may run out of GPU memory"
fi

touch "$BUSY"   # busy from the very first second, before the supervisor's own heartbeat starts
printf '\n=== %s: training %s ===\n' "$(date -u +%FT%TZ)" "$NAME" >>"$LOG"
setsid nohup bash "$HERE/train_lora.sh" --supervise "$NAME" >>"$LOG" 2>&1 </dev/null &
echo $! >"$PIDFILE"
sleep "${CM_TRAIN_GRACE_S:-3}"   # grace period to catch an immediate crash
if ! training_alive && ! tail -n 3 "$LOG" | grep -q 'DONE:'; then
    tail -n 20 "$LOG" >&2 || true
    rm -f "$BUSY"
    die "training exited right after start (log above)"
fi
log "started training $NAME (pid $(cat "$PIDFILE")), log: $LOG"
