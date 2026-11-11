#!/bin/bash
# Set up a fresh Vast ComfyUI machine (RTX 5090, 200 GB disk) for the person swap. Paste into its Jupyter terminal. ~5 minutes, ~56 GB.
set -e
cd /workspace/ComfyUI/custom_nodes
for r in ethanfel/ComfyUI-MiniMaxH3-Context-Loop Adudeguyman/ComfyUI-Fantastic-MiniMaxH3-PromptBuilder kijai/ComfyUI-KJNodes Kosinkadink/ComfyUI-VideoHelperSuite D3voz/comfyui-h3-oneclick-swap; do
  d=$(basename $r); [ -d $d ] || git clone --depth 1 https://github.com/$r
  [ -f $d/requirements.txt ] && pip install -q -r $d/requirements.txt
done
cd /workspace && { [ -d openjutsu ] || git clone --depth 1 https://github.com/D3voz/openjutsu; }
cd /workspace/ComfyUI
hf download Comfy-Org/MiniMax-H3 diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors vae/minimax_h3_video_vae_int8_convrot.safetensors vae/minimax_h3_audio_vae_fp32.safetensors text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors --local-dir models
hf download Comfy-Org/Qwen3-VL text_encoders/qwen3vl_8b_int8_convrot.safetensors --local-dir models
hf download Comfy-Org/sam3.1 checkpoints/sam3.1_multiplex_fp16.safetensors --local-dir models
supervisorctl restart comfyui
mkdir -p /workspace/results
echo "Done. Copy run_swap.py and queue.sh to /workspace, put character.png in ComfyUI/input, then: nohup /workspace/queue.sh &"
