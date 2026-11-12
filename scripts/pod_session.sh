#!/usr/bin/env bash
# One pod session: wait for GPU capacity, run each argument as a shell command in order,
# then ALWAYS power the pod off (retried; verified with `cm pod status`).
#
#   scripts/pod_session.sh "cm batch photo ..." "cm lora refine ..."
#
# Env: CM_MODELS (default pod/qwen_models.yaml), CM_CAPACITY_TRIES (default 150, 1/min).
# A failing command does not stop the session; later commands still run (they resume).
set -u
cd "$(dirname "$0")/.."
CM=".venv/bin/cm"
MODELS="${CM_MODELS:-pod/qwen_models.yaml}"
TRIES="${CM_CAPACITY_TRIES:-150}"

power_off() {
    for t in 1 2 3 4 5 6; do
        "$CM" pod down 2>&1 | tail -1
        if "$CM" pod status 2>&1 | grep -q "no running pod"; then
            echo "[session] pod is off"
            return 0
        fi
        echo "[session] pod still listed, retry $t"
        sleep 30
    done
    echo "[session] WARNING: could not confirm the pod is off; check the RunPod console" >&2
}
trap power_off EXIT

up=0
for i in $(seq 1 "$TRIES"); do
    out=$("$CM" pod up --models "$MODELS" 2>&1)
    if echo "$out" | grep -q "no longer any instances"; then
        echo "[session] try $i: no capacity"
        sleep 60
        continue
    fi
    echo "$out" | grep -v "HTTP Request" | tail -4
    if "$CM" pod status 2>&1 | grep -q "ComfyUI: .*(up)"; then up=1; fi
    break
done
if [ "$up" != 1 ]; then
    echo "[session] no pod with a live ComfyUI; nothing run" >&2
    exit 1
fi

for cmd in "$@"; do
    echo "[session] >>> $cmd"
    bash -c "$cmd" 2>&1 | grep -v "HTTP Request"
done
