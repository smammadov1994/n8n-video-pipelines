#!/usr/bin/env bash
# On the rented machine: make one talking clip from a picture and a voice file.
#   bash /workspace/run_talk.sh <picture> <voice.wav> "<description of person, room, action>" [name] [segments] [480p|720p]
# One segment is a few seconds; more segments continue the same shot for longer voice files.
set -euo pipefail
PIC=$1; WAV=$2; PROMPT=$3; NAME=${4:-talk}; SEGS=${5:-1}; RES=${6:-480p}
cd /workspace/LongCat-Video
source .venv/bin/activate
mkdir -p jobs
python3 - "$PIC" "$WAV" "$PROMPT" "jobs/$NAME.json" <<'PY'
import json, sys
pic, wav, prompt, out = sys.argv[1:5]
json.dump({"prompt": prompt, "cond_image": pic, "cond_audio": {"person1": wav}}, open(out, "w"), indent=1)
PY
# The small (int8) model is used so it fits the 32 GB card; the fast-steps add-on is required by version 1.5.
TEXT_ENCODER_ON_CPU=1 torchrun --nproc_per_node=1 run_demo_avatar_single_audio_to_video.py --context_parallel_size=1 \
  --checkpoint_dir=./weights/LongCat-Video-Avatar-1.5 --model_type avatar-v1.5 --use_distill --use_int8 \
  --stage_1=ai2v --input_json="jobs/$NAME.json" --output_dir="outputs/$NAME" \
  --num_segments="$SEGS" --resolution="$RES" --ref_img_index=10 --mask_frame_range=3
ls -la "outputs/$NAME"
