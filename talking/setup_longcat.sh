#!/usr/bin/env bash
# Sets up LongCat-Video-Avatar 1.5 (photo or short video of a person + a voice file -> talking video)
# on a rented RTX 5090 machine. Copy the whole talking/ folder to the machine and run this once.
# About 80 GB of downloads. Safe to run again: finished downloads are skipped.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)   # the folder holding this script, flash_attn_shim.py, fit_32gb.py and run_talk.sh
cd /workspace

[ -d LongCat-Video ] || git clone --single-branch --branch main https://github.com/meituan-longcat/LongCat-Video
cd LongCat-Video

# Own Python 3.10 environment (the version the model was written for), so the machine's ComfyUI install is left alone.
[ -x .venv/bin/python ] && .venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 10))' || { rm -rf .venv; uv python install 3.10 >/dev/null 2>&1; "$(uv python find 3.10)" -m venv .venv; }
source .venv/bin/activate
# The 5090 needs a CUDA 12.8 build of torch; the repo pins an older one that does not know this card.
pip install -q --upgrade pip setuptools wheel
pip install -q torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu128
pip install -q ninja psutil packaging wheel setuptools pip
# Pins dropped: torch (above), flash-attn (below), sympy (torch brings its own), and two names that are not Python packages.
grep -v -i '^torch\|^flash\|^sympy\|^libsndfile1\|^tritonserverclient' requirements.txt requirements_avatar.txt -h | sort -u > /tmp/req.txt
pip install -q -r /tmp/req.txt "huggingface_hub[cli]"
apt-get install -y -qq libsndfile1 >/dev/null 2>&1 || true
pip install -q flash_attn==2.7.4.post1 --no-build-isolation || { echo "flash_attn did not build; using the stand-in"; mkdir -p flash_attn; cp "$HERE/flash_attn_shim.py" flash_attn/__init__.py; }
python3 "$HERE/fit_32gb.py"
cp "$HERE/run_talk.sh" /workspace/run_talk.sh
command -v ffmpeg >/dev/null || (apt-get update -qq && apt-get install -y -qq ffmpeg)

# Weights. The base repo is only needed for its text encoder and picture decoder (not its 54 GB video model).
huggingface-cli download meituan-longcat/LongCat-Video --local-dir ./weights/LongCat-Video \
  --include "text_encoder/*" "tokenizer/*" "vae/*" "*.json"
# Avatar 1.5: full model, small (int8) model, fast-steps add-on, and one copy of the Whisper listener.
huggingface-cli download meituan-longcat/LongCat-Video-Avatar-1.5 --local-dir ./weights/LongCat-Video-Avatar-1.5 \
  --exclude "whisper-large-v3/flax_model.msgpack" "whisper-large-v3/*fp32*" "whisper-large-v3/pytorch_model.bin"

df -h /workspace | tail -1
echo "Setup finished. Test: bash /workspace/run_talk.sh <picture> <voice.wav> \"<description of the person and room>\""
