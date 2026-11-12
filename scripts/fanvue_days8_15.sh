#!/usr/bin/env bash
# Fanvue days 8-15 (32 frames) on a separate vast.ai RTX 5090. The operator runs it.
# Rents a fresh instance -> installs -> renders scenes/fanvue_days8_15.yaml -> instance DESTROYED (also on error/Ctrl+C,
# 3-hour guard) -> packs out/prod/day8..day15. About 1 h 30 min, about $1.
#   scripts/fanvue_days8_15.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8192} scripts/vast_batch.sh scenes/fanvue_days8_15.yaml out/dev/fanvue-days8-15
.venv/bin/python scripts/prod_pack.py day8 day9 day10 day11 day12 day13 day14 day15
echo "done: Fanvue frames in out/dev/fanvue-days8-15, packed into out/prod/day8..day15"
