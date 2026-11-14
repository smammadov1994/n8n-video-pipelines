---
name: talking-avatar
description: "Turns one picture of someone and one voice recording into a video of them saying those words, for any length. Use when someone wants a person, character or mascot to speak a recording to camera."
---

# Talking avatar

The voice is fixed and the face follows it. Any speaker a picture shows: a person, a cartoon, an animal.

## Ask first

1. **The picture** of the speaker, face clearly visible, roughly from the chest up.
2. **The voice recording** (or the words, if a voice is to be generated first).
3. **Whose picture and voice are these?** Use only a person who has agreed, or yourself.
4. **One sentence about the scene:** who it is, where they are, how they speak (calm, excited).

## How it is run today

By hand, on its own rented machine, not through ComfyUI: `talking/run_talk.sh <picture> <voice.wav> "<description>"`. There is no tool for it in the MCP server yet. Tell the person this plainly and point them to `talking/README.md`.

## Limits

Speakers only: no scenery, no walking, no scene changes. Slow past the first few seconds. Strength 0.45 is the calm default; higher looks like shouting.
