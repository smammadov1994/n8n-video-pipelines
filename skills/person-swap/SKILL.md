---
name: person-swap
description: "Re-films an existing product video with our presenter in place of the original person, in her voice, with captions and an end card. Use when someone has a creator's product video and wants our presenter's version of it."
---

# Person swap pipeline

The room, the product and the movements stay; the person becomes our presenter and the voice becomes hers.

## Ask first

1. **Which video?** The video file, or which list to pick from (top, trending or latest product videos).
2. **Has the person in the video agreed to this?** This pipeline may only be used on videos whose creators have agreed. If the answer is no or unknown, stop and say why.
3. **How many?** When picking from a list: how many to look at and how many to keep.

## What works and what does not

- Works: one person, face to camera, talking, product in hand, close framing.
- Does not work: outfit videos (she keeps her own clothes), videos with word-by-word captions burned in (they come out garbled), full-body turns, more than one person.

## Steps

1. `swap_step` `prep`: picks and prepares clips, records the lines in her voice.
2. `swap_step` `send`: uploads them to the swap GPU.
3. `swap_step` `collect`: brings finished swaps back.
4. `swap_step` `status` at any time.

The swap GPU has to be connected first (the owner runs `python3 set_5090.py --swap`). Without that, `send` and `collect` say so and do nothing.

## Limits

About five to seven minutes per ten seconds of video. Captions and the end card are added by a separate step (`swap/caption_job.py`).
