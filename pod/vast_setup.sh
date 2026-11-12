#!/usr/bin/env bash
# Runs ON a vast.ai instance (as root): the same ComfyUI as the Mac (~/ComfyUI): v0.40.0,
# ComfyUI-GGUF, Impact Pack/Subpack, controlnet_aux at the Mac's commits, and the same model files
# from Hugging Face. LoRAs come from the Mac by scp (scripts/vast_session.sh).
# Idempotent: rerun only fetches what is missing. No secrets are needed or stored here.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
W=/workspace; C=$W/ComfyUI; M=$C/models
log() { printf '[vast-setup %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
mkdir -p $W && cd $W
# vastai/pytorch images keep python in /venv/main and ship git; only apt-install what is missing
[ -x /venv/main/bin/python ] && export PATH=/venv/main/bin:$PATH
log "system packages"
for i in 1 2 3; do  # apt mirrors on some hosts flake: retry, then give up loudly (aria2 is optional)
    command -v git >/dev/null && command -v aria2c >/dev/null && break
    timeout 300 apt-get update -qq || true
    timeout 300 apt-get install -y -qq git aria2 >/dev/null || true
    sleep 5
done
command -v git >/dev/null || { log "apt failed: no git"; exit 100; }
command -v aria2c >/dev/null || log "no aria2c: downloads go through curl"

clone() {  # url dir commit
    [ -d "$2/.git" ] || git clone -q "$1" "$2"
    git -C "$2" fetch -q --depth 200 origin 2>/dev/null || true
    git -C "$2" checkout -q "$3"
}
log "ComfyUI + nodes"
[ -d $C/.git ] || git clone -q https://github.com/comfyanonymous/ComfyUI.git $C
git -C $C fetch -q --tags && git -C $C checkout -q v0.40.0
clone https://github.com/city96/ComfyUI-GGUF.git $C/custom_nodes/ComfyUI-GGUF 6ea2651
clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git $C/custom_nodes/ComfyUI-Impact-Pack 429d0159ad429e64d2b3916e6e7be9c22d025c3c
clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git $C/custom_nodes/ComfyUI-Impact-Subpack 50c7b71a6a224734cc9b21963c6d1926816a97f1
clone https://github.com/Fannovel16/comfyui_controlnet_aux $C/custom_nodes/comfyui_controlnet_aux b9abafa

log "python deps"
python -m pip install -q -r $C/requirements.txt
for n in ComfyUI-GGUF ComfyUI-Impact-Pack ComfyUI-Impact-Subpack comfyui_controlnet_aux; do
    [ -f $C/custom_nodes/$n/requirements.txt ] && python -m pip install -q -r $C/custom_nodes/$n/requirements.txt || true
done
python -m pip install -q gguf
# the slim CUDA image has no X/GL libs (libxcb) and its apt mirror can hang: use headless OpenCV
python -m pip uninstall -y -q opencv-python opencv-contrib-python 2>/dev/null || true
python -m pip install -q opencv-python-headless opencv-contrib-python-headless
python -c "import cv2" || { log "cv2 import failed"; exit 1; }

log "models"
dl() {  # repo path dest_dir [name]
    local name="${4:-$(basename "$2")}"; mkdir -p "$M/$3"
    [ -s "$M/$3/$name" ] && [ ! -f "$M/$3/$name.aria2" ] && return 0
    local url="https://huggingface.co/$1/resolve/main/$2"
    if command -v aria2c >/dev/null; then aria2c -q -x 16 -s 16 -c -d "$M/$3" -o "$name" "$url"
    else curl -fsSL --retry 5 -C - -o "$M/$3/$name" "$url"; fi
}
dl unsloth/Qwen-Image-2512-GGUF qwen-image-2512-Q5_K_M.gguf diffusion_models &
dl unsloth/Qwen2.5-VL-7B-Instruct-GGUF Qwen2.5-VL-7B-Instruct-Q6_K.gguf text_encoders &
dl unsloth/Qwen2.5-VL-7B-Instruct-GGUF mmproj-F16.gguf text_encoders Qwen2.5-VL-7B-Instruct-mmproj-F16.gguf &
dl Comfy-Org/Qwen-Image_ComfyUI split_files/vae/qwen_image_vae.safetensors vae &
dl Bingsu/adetailer face_yolov8m.pt ultralytics/bbox &
dl Bingsu/adetailer hand_yolov8s.pt ultralytics/bbox &
wait
log "core models ready (photo graphs)"
dl unsloth/Qwen-Image-Edit-2511-GGUF qwen-image-edit-2511-Q5_K_M.gguf diffusion_models &
dl Comfy-Org/Qwen-Image-InstantX-ControlNets split_files/controlnet/Qwen-Image-InstantX-ControlNet-Union.safetensors controlnet &
dl lightx2v/Qwen-Image-2512-Lightning Qwen-Image-2512-Lightning-8steps-V1.0-bf16.safetensors loras &
dl lightx2v/Qwen-Image-Edit-2511-Lightning Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors loras &
wait
log "all models ready"
du -sh $M

# start ComfyUI (localhost only; reached through an SSH tunnel from the Mac)
pkill -f "main.py --listen" 2>/dev/null || true; sleep 2
cd $C && setsid nohup python main.py --listen 127.0.0.1 --port 8188 > $W/comfy.log 2>&1 < /dev/null &
for i in $(seq 60); do curl -s 127.0.0.1:8188/system_stats >/dev/null && break; sleep 2; done
grep -q "IMPORT FAILED" $W/comfy.log && { grep -B2 "IMPORT FAILED" $W/comfy.log; exit 1; }
log "ComfyUI up, all custom nodes imported"
