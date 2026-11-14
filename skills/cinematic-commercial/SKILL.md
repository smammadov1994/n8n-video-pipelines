---
name: cinematic-commercial
description: "Makes a 30-second, nine-shot commercial for one product in one art style, with the product shown in a clever way at the end. Use when someone wants an ad, a commercial, a product film, a concept spot or a product video in a particular look."
---

# Cinematic commercial pipeline

Nine shots in three clips, one look from start to finish, a small story, a clever last shot, one short spoken line at the end. About 50 minutes of GPU time.

## Ask first

1. **What is the product?** What it is and what it looks like: shape, colours, material. No brand names or logos unless the brand is theirs.
2. **Do you have a picture of the product?** Optional. If not, it is drawn from the description. A clean picture on a plain background works best.
3. **What art style?** Offer examples if they are unsure: live action, stop motion, 3D animated film, comic book, paper craft, black-and-white film noir, 1970s home movie, pixel game, ink painting, oil painting, travel poster, felted wool, 1980s neon, shadow puppets.
4. **Any idea for the story or the ending?** Optional. If they have none, propose one in two sentences and a clever way to show the product at the end, and ask if they like it.
5. **The closing line.** Two to five words, or let it be written.
6. **Sound.** By default: sound effects and the one spoken line, no music (they add music on top). Ask only if they bring it up.

## Steps

1. `commercial_write`: a model writes the script file (the look, the pictures to draw, three clips of three shots). About a minute; poll `commercial_status`.
2. Read the nine shots back in plain words (`commercial_get`). Change with `commercial_save`.
3. `commercial_step` in order: `draw` (Codex draws the character, the product and the end picture; show them `pictures.jpg`), `build`, `render` (about 16 minutes per clip on the GPU; say so first), `sheet`, `join`.
4. After `sheet`, look at the frame sheets yourself before joining: a character that changed, an object that appears too early, a stray first or last moment. Say what you saw.
5. Give them `final.mp4`.

## Rules for the script (each one cost a render)

- Never show a small object being picked up or handled. Show it still, then cut to it already in place.
- One picture of the product, used in every shot the product appears in, the end shot included.
- A character's picture in every clip the character is in, and named in every shot that shows it.
- People and products are drawn on plain backgrounds; the place is described in the shot.
- Do not call anyone "the presenter". Name the character.
- Say what must not be there: "no wire", "lips closed", "nobody speaks", "nothing is picked up".
- No lettering anywhere. Titles are added afterwards.
- The spoken line is two to five words, off screen, in the last shot.
- Ask for sounds, not music.
- Each clip is 243 frames: three shots of about 75 to 93 frames.

## Limits

No readable text in the picture. Not for long talking. Fine actions are sometimes skipped. Nothing checks the result automatically; someone has to look at the frame sheets. Full guide: `cinematic-commercial/README.md`.
