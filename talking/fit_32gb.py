#!/usr/bin/env python3
"""Make LongCat-Video-Avatar 1.5 fit a 32 GB card (RTX 5090), and add a calm dial. Run inside the LongCat-Video folder.

Out of the box the program puts every part on the card at once and runs out of memory.
Three small edits fix it, and with them the card sits at about 16 GB before sampling:

1. The text encoder stays in main memory when TEXT_ENCODER_ON_CPU=1 is set; only its result goes to the card.
2. The voice encoder (Whisper) and the vocal separator are taken off the card once the voice has been read.
3. For clips longer than one segment, the data carried over from the previous segment (the "kv cache") is kept
   in main memory instead of on the card. Without this the second segment runs out of memory.

A fourth edit is not about memory. It adds an expression dial, read from AUDIO_STRENGTH (1.0 = unchanged).
In the fast 8-step mode the program locks its own guidance settings, so there is no shipped way to make the
speaker less intense. The dial pulls the voice signal toward its average over the clip, so the face reacts
less to each loud syllable. run_talk.sh sets it to 0.45.

Safe to run twice: an edit that is already there is skipped. A changed upstream file stops with a clear message.
"""
import sys
from pathlib import Path

def edit(path, old, new, mark, first=False):
    """Replace `old` with `new`. `old` must appear exactly once, or at least once when first=True (then only the first is changed)."""
    p = Path(path); s = p.read_text()
    if mark in s:
        print(f"already done: {path}"); return
    n = s.count(old)
    if n == 0 or (n > 1 and not first):
        sys.exit(f"{path}: the expected lines were found {n} times; upstream changed, edit by hand")
    p.write_text(s.replace(old, new, 1)); print(f"edited: {path}")

PIPE = "longcat_video/pipeline_longcat_video_avatar.py"
edit(PIPE,
     "        prompt_embeds = self.text_encoder(text_input_ids.to(device), mask.to(device)).last_hidden_state\n",
     "        _te = self.text_encoder.device  # 32 GB card: the text encoder may live in main memory\n"
     "        prompt_embeds = self.text_encoder(text_input_ids.to(_te), mask.to(_te)).last_hidden_state.to(device)\n",
     "_te = self.text_encoder.device")
edit(PIPE,
     "        if self.text_encoder is not None:\n            self.text_encoder = self.text_encoder.to(device, non_blocking=True)\n",
     "        if self.text_encoder is not None and not __import__('os').environ.get('TEXT_ENCODER_ON_CPU'):\n"
     "            self.text_encoder = self.text_encoder.to(device, non_blocking=True)\n",
     "TEXT_ENCODER_ON_CPU")
edit("run_demo_avatar_single_audio_to_video.py",
     "    audio_emb = full_audio_emb[center_indices][None,...].to(local_rank)\n",
     "    audio_emb = full_audio_emb[center_indices][None,...].to(local_rank)\n"
     "    # 32 GB card: the voice encoder and the vocal separator have done their job; take them off the card.\n"
     "    pipe.audio_encoder.to('cpu'); audio_encoder.to('cpu')\n"
     "    try:\n        del vocal_separator\n    except Exception:\n        pass\n"
     "    import gc; gc.collect(); torch.cuda.empty_cache()\n"
     "    print(f'[INFO] card memory before sampling: {torch.cuda.memory_allocated()/2**30:.1f} GB', flush=True)\n",
     "card memory before", first=True)  # the same line appears again inside the segment loop; only the first is wanted
edit("run_demo_avatar_single_audio_to_video.py", "offload_kv_cache=False", "offload_kv_cache=True", "offload_kv_cache=True")
edit("run_demo_avatar_single_audio_to_video.py",
     "        if torch.isnan(full_audio_emb).any():\n",
     "        # Expression strength: 1.0 = as heard. Lower pulls every moment toward the clip average,\n"
     "        # so the face reacts less to each loud syllable.\n"
     "        _s = float(os.environ.get('AUDIO_STRENGTH', '1.0'))\n"
     "        if _s != 1.0:\n"
     "            _m = full_audio_emb.mean(dim=0, keepdim=True)\n"
     "            full_audio_emb = _m + _s * (full_audio_emb - _m)\n"
     "            print(f'[INFO] audio strength {_s}', flush=True)\n"
     "        if torch.isnan(full_audio_emb).any():\n",
     "AUDIO_STRENGTH")
