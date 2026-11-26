#!/usr/bin/env bash
# Fanvue masked repair pass (SDXL inpaint over chosen boxes), OPERATOR ONLY: own vast.ai instance on port 8192,
# kept alive until "down". Never RunPod. Results stay on this Mac in out/dev/fanvue-inpaint.
#
#   scripts/fanvue_inpaint.sh up             # rent + install (no video models) + tunnel; keep this terminal open
#   scripts/fanvue_inpaint.sh model [URL]    # 2nd terminal: download the SDXL checkpoint onto the instance
#                                            #   default: RealVisXL V5.0 fp16 (Hugging Face, SG161222)
#                                            #   Civitai link: export CIVITAI_TOKEN=... first (never printed)
#   scripts/fanvue_inpaint.sh fix [stems]    # run scenes/fanvue_inpaint.yaml (optionally only some images)
#   scripts/fanvue_inpaint.sh base           # Qwen + v5 faceless body frames from scenes/fanvue_body_v3.yaml
#   scripts/fanvue_inpaint.sh refs [ids]     # X/Telegram set posed by 20 references (scenes/x_refs20.yaml)
#   scripts/fanvue_inpaint.sh refs2 [ids]    # X/Telegram set 2 posed by 19 references (scenes/x_refs19.yaml)
#   scripts/fanvue_inpaint.sh fvrefs [ids]   # Fanvue versions of 7 approved X frames (scenes/fanvue_refs7.yaml)
#   scripts/fanvue_inpaint.sh gen [ids]      # plain SDXL body frames from scenes/fanvue_sdxl_body.yaml
#   scripts/fanvue_inpaint.sh down           # DESTROY the instance (do not forget)
set -euo pipefail
cd "$(dirname "$0")/.."
export SESSION=.vast_session_fanvue PORT=8192 VIDEO=0
SPEC=scenes/fanvue_inpaint.yaml; OUT=out/dev/fanvue-inpaint; URL=http://127.0.0.1:$PORT
DEFAULT_URL=https://huggingface.co/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors
KEY=~/.ssh/vast_roxana; KH=~/.ssh/vast_known_hosts
case "${1:-}" in
    up)    scripts/vast_session.sh ;;
    model) [ -s "$SESSION" ] || { echo "no $SESSION: run up first"; exit 1; }
           SRC=${2:-$DEFAULT_URL}
           NAME=$(grep -o '^checkpoint: *[^ #]*' "$SPEC" | awk '{print $2}')
           read -r HOST SSHPORT < <(python3 scripts/vast.py wait "$(cat "$SESSION")")
           HDR=""; case "$SRC" in *civitai.com*) [ -n "${CIVITAI_TOKEN:-}" ] || { echo "export CIVITAI_TOKEN first"; exit 1; }
                                                 HDR="Authorization: Bearer $CIVITAI_TOKEN";; esac
           echo "downloading $SRC -> models/checkpoints/$NAME"
           ssh -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KH" -p "$SSHPORT" "root@$HOST" \
               "cd /workspace/ComfyUI/models/checkpoints && curl -fL --retry 3 -o '$NAME.part' ${HDR:+-H \"\$(cat)\"} '$SRC' && mv '$NAME.part' '$NAME' && ls -lh '$NAME'" <<<"$HDR" ;;
    base)  CM_WAIT_TIMEOUT_S=3600 .venv/bin/cm batch photo scenes/fanvue_body_v3.yaml \
               --profile character/profile_body_40.yaml --lora ohwxroxana_v5.safetensors --strength "${STRENGTH:-0.7}" \
               --workflows workflows/qwen-mac-hero-opt-v5-40-body --out out/dev/fanvue-body-v3 --url "$URL" ;;
    refs)  .venv/bin/python scripts/ref_poses.py scenes/x_refs20.yaml --out out/dev/x-refs20 --url "$URL" ${2:+--only "$2"} ;;
    refs2) .venv/bin/python scripts/ref_poses.py scenes/x_refs19.yaml --out out/dev/x-refs19 --url "$URL" ${2:+--only "$2"} ;;
    fvrefs) .venv/bin/python scripts/ref_poses.py scenes/fanvue_refs7.yaml --out out/dev/fanvue-refs7 --url "$URL" ${2:+--only "$2"} ;;
    gen)   .venv/bin/python scripts/sdxl_gen.py scenes/fanvue_sdxl_body.yaml --out out/dev/fanvue-sdxl-body --url "$URL" ${2:+--only "$2"} ;;
    fix)   .venv/bin/python scripts/inpaint_fix.py "$SPEC" --out "$OUT" --url "$URL" ${2:+--only "$2"} ;;
    down)  [ -s "$SESSION" ] || { echo "no $SESSION: nothing to destroy (check: python3 scripts/vast.py status)"; exit 0; }
           python3 scripts/vast.py destroy "$(cat "$SESSION")" && rm -f "$SESSION"
           pkill -f "L $PORT:127.0.0.1:8188" 2>/dev/null || true
           python3 scripts/vast.py status ;;
    *)     sed -n 2,15p "$0"; exit 1 ;;
esac
