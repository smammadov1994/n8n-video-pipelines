#!/bin/bash
# Set up a fresh Vast.ai ComfyUI machine for the episode pipeline (HyperFlow H3 Flash).
# Paste into the machine's Jupyter terminal (or: bash setup_5090.sh). Safe to run twice.
# Source: https://github.com/Video-Rebirth/hyperflow-h3-flash/blob/main/integrations/README.md
set -e
COMFY=${COMFY:-/workspace/ComfyUI}
[ -f /venv/main/bin/activate ] && source /venv/main/bin/activate
cd "$COMFY"
echo "ComfyUI version: $(git describe --tags 2>/dev/null || echo unknown)  (needs 0.43.0 or newer)"

# 1. add-on nodes
cd custom_nodes
[ -d ComfyUI-GGUF ] || git clone https://github.com/city96/ComfyUI-GGUF
[ -d ComfyUI-HyperFlow-Flash ] || git clone https://github.com/Video-Rebirth/ComfyUI-HyperFlow-Flash
pip install -q -r ComfyUI-GGUF/requirements.txt -r ComfyUI-HyperFlow-Flash/requirements.txt
cd ..

# 2. model files (about 35 GB). Our workflows expect the two video models inside
#    models/diffusion_models/fl2va_gguf/ and .../ref2va_gguf/.
pip install -q -U "huggingface_hub[cli]"
hf download VideoRebirthAI/hyperflow-h3-flash \
  fl2va_gguf/minimax_h3_fl2va_hyperflow_flash_14b-Q4_K_M.gguf \
  ref2va_gguf/minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf \
  --local-dir models/diffusion_models
hf download Comfy-Org/MiniMax-H3 \
  text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors \
  vae/minimax_h3_video_vae_fp16.safetensors \
  vae/minimax_h3_audio_vae_fp32.safetensors \
  --local-dir models

# 3. restart ComfyUI so it sees the new nodes and files
supervisorctl restart comfyui 2>/dev/null || echo "Restart ComfyUI by hand (Instance Portal, or stop/start the instance)."

echo
echo "Done. Send Claude these two values:"
echo "  token:   $OPEN_BUTTON_TOKEN"
echo "  address: the localhost:8188 row in Instance Portal > Tunnels (or public IP:port mapped to 8188)"
