#!/usr/bin/env bash
# Fanvue bed set: 6 breast close-ups + 6 rear self-shots, 2 variants each (24 frames). The operator runs it.
# Fresh vast instance, destroyed on exit. ~50-60 min.
#   scripts/fanvue_bed_closeups.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8193} scripts/vast_batch.sh scenes/fanvue_bed_closeups.yaml out/dev/fanvue-bed-closeups
echo "done: out/dev/fanvue-bed-closeups. Tell Claude to review and pack."
