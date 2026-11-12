#!/usr/bin/env bash
# Second Fanvue re-render pass: f12d and f14c as rear shots, 2 variants each. The operator runs it. ~25 min, ~$0.3.
#   scripts/fanvue_fix815b.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8193} scripts/vast_batch.sh scenes/fanvue_fix815b.yaml out/dev/fanvue-fix815b
echo "done: out/dev/fanvue-fix815b. Tell Claude to review and pack."
