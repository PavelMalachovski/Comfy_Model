#!/usr/bin/env bash
# One-shot render on a fresh vast.ai RTX 5090: rent -> install (pod/vast_setup.sh) -> upload LoRA ->
# render a scene file through an SSH tunnel -> results land on the Mac -> instance DESTROYED (with its disk).
#
#   scripts/vast_batch.sh scenes/fanvue_week1.yaml out/dev/fanvue-week1
#
# The instance is destroyed on any exit (done, error, Ctrl+C) and by a 3-hour guard.
# Needs VAST_API_KEY in .env and ~/.ssh/vast_roxana (registered on vast). Never prints the key.
set -euo pipefail
cd "$(dirname "$0")/.."
SCENES=${1:?scenes file}; OUT=${2:?output dir}; PORT=${PORT:-8190}; LORA=${LORA:-ohwxroxana_v5.safetensors}
# vast's own image ships sshd (pytorch/pytorch needed apt on start, which broke on flaky hosts, 19 Nov 2026)
export VAST_IMAGE=${VAST_IMAGE:-vastai/pytorch:cuda-12.8.1-auto}
KEY=~/.ssh/vast_roxana; KH=~/.ssh/vast_known_hosts
log() { printf '[vast %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

OFFER=${OFFER:-$(python3 scripts/vast.py search -n 1 | awk "NR==1{print \$1}")}
[ -n "$OFFER" ] || { log "no RTX 5090 offer found"; exit 1; }
ID=$(python3 scripts/vast.py create "$OFFER" --label roxana-batch)
log "rented instance $ID (offer $OFFER)"
TUNNEL=""
cleanup() {
    [ -n "$TUNNEL" ] && kill "$TUNNEL" 2>/dev/null || true
    log "destroying instance $ID"
    python3 scripts/vast.py destroy "$ID" || log "!!! destroy failed: check console.vast.ai and delete instance $ID by hand"
    [ -n "${GUARD:-}" ] && kill "$GUARD" 2>/dev/null || true
}
trap cleanup EXIT
(sleep 10800; python3 scripts/vast.py destroy "$ID") >/dev/null 2>&1 &
GUARD=$!

read -r HOST SSHPORT < <(python3 scripts/vast.py wait "$ID")
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KH" -o ConnectTimeout=15 -o ServerAliveInterval=30 -p "$SSHPORT" "root@$HOST")
SCP=(scp -q -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KH" -P "$SSHPORT")
for i in $(seq 40); do "${SSH[@]}" true 2>/dev/null && break; sleep 15; done
"${SSH[@]}" true 2>/dev/null || { log "ssh never came up"; exit 1; }
log "ssh ok: $HOST:$SSHPORT"

"${SCP[@]}" pod/vast_setup.sh "root@$HOST:/root/"
log "installing ComfyUI and models (~10-15 min)"
"${SSH[@]}" 'bash /root/vast_setup.sh > /root/setup.log 2>&1 < /dev/null; s=$?; grep "vast-setup" /root/setup.log; [ $s -eq 0 ] || tail -25 /root/setup.log; exit $s' 2>/dev/null
"${SCP[@]}" ~/ComfyUI/models/loras/"$LORA" "root@$HOST:/workspace/ComfyUI/models/loras/"
log "LoRA $LORA uploaded"

ssh -N -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KH" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
    -L "$PORT:127.0.0.1:8188" -p "$SSHPORT" "root@$HOST" &
TUNNEL=$!
for i in $(seq 30); do curl -s "http://127.0.0.1:$PORT/system_stats" >/dev/null && break; sleep 2; done
log "tunnel up on 127.0.0.1:$PORT, rendering $SCENES -> $OUT"

CM_WAIT_TIMEOUT_S=3600 .venv/bin/cm batch photo "$SCENES" \
    --profile "${PROFILE:-character/profile_phone_40.yaml}" --lora "$LORA" --strength "${STRENGTH:-0.8}" \
    --workflows "${WORKFLOWS:-workflows/qwen-mac-hero-opt-v5-40}" --out "$OUT" --url "http://127.0.0.1:$PORT"
log "render done: $(ls "$OUT"/*.png 2>/dev/null | wc -l | tr -d ' ') frames in $OUT"
