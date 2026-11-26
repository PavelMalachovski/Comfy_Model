#!/usr/bin/env bash
# Runs ON a vast.ai instance after pod/vast_setup.sh: adds Wan 2.2 I2V 14B (fp8) + Lightning 4-step LoRAs
# for workflows/wan22-i2v-14b/video.json (~38 GB) + FILM interpolation. Idempotent. No secrets.
set -euo pipefail
M=/workspace/ComfyUI/models; R=Comfy-Org/Wan_2.2_ComfyUI_Repackaged
log() { printf '[vast-video %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
dl() {  # repo path dest_dir
    local name; name=$(basename "$2"); mkdir -p "$M/$3"
    [ -s "$M/$3/$name" ] && [ ! -f "$M/$3/$name.aria2" ] && return 0
    local url="https://huggingface.co/$1/resolve/main/$2"
    if command -v aria2c >/dev/null; then aria2c -q -x 16 -s 16 -c -d "$M/$3" -o "$name" "$url"
    else curl -fsSL --retry 5 -C - -o "$M/$3/$name" "$url"; fi
}
log "Wan 2.2 I2V 14B models"
dl $R split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors diffusion_models &
dl $R split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors diffusion_models &
dl $R split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors loras &
dl $R split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors loras &
dl Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors text_encoders &
dl $R split_files/vae/wan_2.1_vae.safetensors vae &
# FILM frame interpolation for ComfyUI's built-in FrameInterpolate node (16 -> 32 fps)
dl Comfy-Org/frame_interpolation frame_interpolation/film_net_fp16.safetensors frame_interpolation &
wait
ls -la $M/diffusion_models $M/loras | grep -i wan
log "video models ready"
