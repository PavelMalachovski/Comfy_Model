#!/usr/bin/env bash
# Fanvue long clips (scenes/video_fanvue_long.yaml), OPERATOR ONLY: own vast.ai instance on port 8192,
# separate from Claude's session. Never RunPod. Results stay on this Mac in out/dev/video-fanvue-long.
#
#   scripts/fanvue_video.sh up          # rent + install + tunnel (keep this terminal open, ~20 min)
#   scripts/fanvue_video.sh keys        # in a 2nd terminal: keyframes, 2 variants per clip -> review the PNGs
#   scripts/fanvue_video.sh facefix     # only if keys ran before 20 Nov 09:00: fix faces of the edited angles
#   scripts/fanvue_video.sh video 1     # animate keyframe set 1 (or "1,2"), ~15 min per clip
#   scripts/fanvue_video.sh video 2 fv02-lotus-orbit   # one clip only
#   scripts/fanvue_video.sh down        # DESTROY the instance (do not forget)
set -euo pipefail
cd "$(dirname "$0")/.."
export SESSION=.vast_session_fanvue PORT=8192
SPEC=scenes/video_fanvue_long.yaml; OUT=out/dev/video-fanvue-long; URL=http://127.0.0.1:$PORT
case "${1:-}" in
    up)    scripts/vast_session.sh ;;
    keys)  .venv/bin/python scripts/video_keys.py keys "$SPEC" --out "$OUT" --url "$URL" --face-fix 0.6 ;;
    facefix) .venv/bin/python scripts/video_keys.py facefix "$SPEC" --out "$OUT" --url "$URL" --face-fix 0.6 ${2:+--only "$2"} ;;
    video) .venv/bin/python scripts/video_keys.py video "$SPEC" --out "$OUT" --url "$URL" --set "${2:-1}" ${3:+--only "$3"} ;;
    down)  [ -s "$SESSION" ] || { echo "no $SESSION: nothing to destroy (check: python3 scripts/vast.py status)"; exit 0; }
           python3 scripts/vast.py destroy "$(cat "$SESSION")" && rm -f "$SESSION"
           pkill -f "L $PORT:127.0.0.1:8188" 2>/dev/null || true
           python3 scripts/vast.py status ;;
    *)     sed -n 2,9p "$0"; exit 1 ;;
esac
