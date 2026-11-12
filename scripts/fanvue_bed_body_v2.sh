#!/usr/bin/env bash
# Fanvue faceless body set, second pass: body-only profile + graph with face in the negative, LoRA 0.7.
# 9 scenes x 2 (18 frames). The operator runs it. Fresh vast instance, destroyed on exit. ~40-50 min.
#   scripts/fanvue_bed_body_v2.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8193} PROFILE=character/profile_body_40.yaml STRENGTH=${STRENGTH:-0.7} \
    WORKFLOWS=workflows/qwen-mac-hero-opt-v5-40-body \
    scripts/vast_batch.sh scenes/fanvue_bed_body_v2.yaml out/dev/fanvue-bed-body-v2
echo "done: out/dev/fanvue-bed-body-v2. Tell Claude to review and pack."
