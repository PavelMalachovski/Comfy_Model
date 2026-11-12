#!/usr/bin/env bash
# Fanvue days 8-15 re-renders: 8 frames x 2 variants on a separate vast.ai RTX 5090. The operator runs it.
# Rents -> installs -> renders scenes/fanvue_fix815.yaml -> instance DESTROYED (also on error/Ctrl+C, 3-hour guard)
# -> repacks out/prod/day8..day15 (variant _01 goes in; Claude reviews and may switch to _02).
# About 35 min, about $0.4.
#   scripts/fanvue_fix815.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8193} scripts/vast_batch.sh scenes/fanvue_fix815.yaml out/dev/fanvue-fix815
.venv/bin/python scripts/prod_pack.py day8 day10 day11 day12 day13 day14 day15
echo "done: re-renders in out/dev/fanvue-fix815, packed into out/prod"
