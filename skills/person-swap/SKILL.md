---
name: person-swap
description: "Re-films an existing video with another person or character in place of the original one: same room, same product, same movements. Use when someone has a video and wants themselves, their avatar or their character in it instead."
---

# Person swap pipeline

The room, the product and the movements stay. The person becomes whoever is in the picture supplied. The voice can stay, or a new voice can say the same words.

## Ask first

1. **Which video?** The file.
2. **Who goes into it?** A picture of the person or character: face clearly visible, chest up or more.
3. **Is it your own video, or has its creator agreed to this?** This must be answered. A swap copies someone's video and puts someone else in it. If the answer is neither, do not make it, and say why. Do not guess and do not accept "it was public".
4. **And the picture:** is it you, someone who agreed, or a made-up character? Do not put a real person who has not agreed into a video.
5. **The voice:** keep the original, or a new voice saying the same words. Keep by default.

## Steps

1. `swap_prepare`: six frames are looked at to see whether the video suits a swap, it is cut to at most 20 seconds, the voice is set. A minute or two; poll `swap_job_status(name, "prepare")`.
2. Tell them what the check said and how long the swap will take (about 40 seconds of work per second of video, so about 13 minutes for 20 seconds). If the check says it is unlikely to work, say why in plain words and ask whether to try anyway (`force`).
3. `swap_run(name, "send")`: uploads the clip and the picture. The GPU swaps it.
4. `swap_run(name, "collect")` every few minutes until `swap_get` shows it finished. Give them `swapped.mp4`.

## What works and what does not

- Works: one person, face to camera, talking, product in hand, close framing.
- Does not work: outfit videos (the swapped person keeps their own clothes), word-by-word captions burned into the picture (they come out garbled), full-body turns, more than one person, a person far from the camera.

## Notes

- The result has the shape of the video that went in. Phone videos stay tall.
- Only the first 20 seconds are used.
- The swap GPU has to be connected (the owner runs `python3 set_5090.py --swap`) and has to run `swap/box/queue.sh` and `swap/box/run_swap.py` from this repository. Without a connection, `send` says so.
- Captions and an end card are a separate step (`swap/caption_job.py`), not offered through these tools yet.
- `swap_batch_step` is the owner's batch version for Kaiyros lists with our own presenter. Do not use it for a person's own request.
