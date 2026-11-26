#!/usr/bin/env bash
# Fanvue bed set: faceless body set, 9 scenes x 2 (18 frames). The operator runs it.
# Fresh vast instance, destroyed on exit. ~40-50 min.
#   scripts/fanvue_bed_body.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8193} scripts/vast_batch.sh scenes/fanvue_bed_body.yaml out/dev/fanvue-bed-body
echo "done: out/dev/fanvue-bed-body. Tell Claude to review and pack."
