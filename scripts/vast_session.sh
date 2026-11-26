#!/usr/bin/env bash
# Long-lived vast.ai session (photo + Wan 2.2 I2V 14B video): rent -> install -> upload LoRA -> keep an SSH
# tunnel on 127.0.0.1:$PORT. The instance is NOT destroyed automatically: when done run
#   python3 scripts/vast.py destroy $(cat $SESSION)   (SESSION defaults to .vast_session; set it to run two sessions)
# Never prints the API key.
set -euo pipefail
cd "$(dirname "$0")/.."
SESSION=${SESSION:-.vast_session}; PORT=${PORT:-8190}; LORA=${LORA:-ohwxroxana_v5.safetensors}
export VAST_IMAGE=${VAST_IMAGE:-vastai/pytorch:cuda-12.8.1-auto}
KEY=~/.ssh/vast_roxana; KH=~/.ssh/vast_known_hosts
log() { printf '[vast %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
if [ -s "$SESSION" ]; then ID=$(cat "$SESSION"); log "reusing instance $ID"
else
    # Offers vanish between search and rent: try the 5 cheapest in turn.
    ID=""
    for OFFER in ${OFFER:-$(python3 scripts/vast.py search -n 5 | awk '{print $1}')}; do
        ID=$(python3 scripts/vast.py create "$OFFER" --label roxana-session --disk 200) && break
        log "offer $OFFER is gone, trying the next one"; ID=""
    done
    [ -n "$ID" ] || { log "no offer could be rented, run up again in a minute"; exit 1; }
    echo "$ID" > "$SESSION"; log "rented instance $ID (offer $OFFER) - destroy by hand when done"
fi
read -r HOST SSHPORT < <(python3 scripts/vast.py wait "$ID")
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KH" -o ConnectTimeout=15 -o ServerAliveInterval=30 -p "$SSHPORT" "root@$HOST")
SCP=(scp -q -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KH" -P "$SSHPORT")
for i in $(seq 40); do "${SSH[@]}" true 2>/dev/null && break; sleep 15; done
"${SSH[@]}" true 2>/dev/null || { log "ssh never came up (instance $ID still exists)"; exit 1; }
log "ssh ok: $HOST:$SSHPORT"
"${SCP[@]}" pod/vast_setup.sh pod/vast_video_setup.sh "root@$HOST:/root/"
log "installing ComfyUI, photo models, Wan 2.2 14B (~20-30 min)"
"${SSH[@]}" "VIDEO=${VIDEO:-1};" 'bash /root/vast_setup.sh > /root/setup.log 2>&1 < /dev/null; s=$?; grep "vast-setup" /root/setup.log; [ $s -eq 0 ] || { tail -25 /root/setup.log; exit $s; }
             [ "${VIDEO:-1}" = 0 ] && exit 0
             bash /root/vast_video_setup.sh > /root/video_setup.log 2>&1 < /dev/null; s=$?; grep "vast-video" /root/video_setup.log; [ $s -eq 0 ] || tail -25 /root/video_setup.log; exit $s' 2>/dev/null
"${SCP[@]}" ~/ComfyUI/models/loras/"$LORA" "root@$HOST:/workspace/ComfyUI/models/loras/"
log "LoRA $LORA uploaded"
log "tunnel on 127.0.0.1:$PORT (Ctrl+C closes the tunnel only; the instance keeps running and billing)"
exec ssh -N -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KH" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
    -L "$PORT:127.0.0.1:8188" -p "$SSHPORT" "root@$HOST"
