---
name: cartoon
description: "Makes a short cartoon starring any character the person describes: the character speaks each line and does one small thing per scene. Use when someone wants a cartoon, an animated character, a kids' show, a mascot video or an animated explainer with one character."
---

# Cartoon pipeline

A character is a **show**. A show has **episodes**. Each scene is a few seconds: the character says one line and does one small action, in one fixed place.

## Ask first

Do not call any tool until you know these. Ask in plain words, one short message.

1. **What is the character?** Have them describe it: what kind of creature or thing, body shape, colours, face, what it wears, anything that makes it special. More detail gives a steadier character.
2. **Its name.**
3. **Do you have a picture of it?** If yes, the image file. If no, one is drawn from the description. Tell them the picture wins over the words where they disagree.
4. **What kind of cartoon is it, and where does it happen?** Optional. If they do not say, a simple bright place is invented.
5. **Who is it for?** Small children by default, which turns on the safety rules (no knives, no flame).

If they might mean a character that already exists, call `cartoon_list_shows` first.

## Steps

1. `cartoon_create_show`: draws or takes the character sheet; a model looks at it and writes the show's rules. Two to four minutes; poll `cartoon_job_status`.
2. **Show them the character sheet and read them the rules** (`cartoon_get_show`). The rules say exactly what the character is: how many arms, legs, tails, ears, wheels or wings, which marks sit on which side, what it wears, and what must never appear. Ask whether anything is wrong and fix it with `cartoon_update_show`. Do not continue until they agree: every picture and clip follows these rules.
3. Ask **what the episode is about** (one or two sentences) and how many scenes (4 to 6 is normal). `cartoon_write_episode`, then read the lines back with `cartoon_get_episode`. Change scenes with `cartoon_save_episode`.
4. Film with `cartoon_run_step`, in order: `pictures` (a few minutes, no GPU), `voice` (about a minute), `shoot` (several minutes per scene on the GPU; say so first), `finish`.
5. After `pictures`, offer to show the start pictures before GPU time is spent.
6. Give them `final.mp4` (wide) and `short.mp4` (vertical).

## Why the rules matter

A video model left alone adds a third arm, a second tail or a second copy of the character, moves a mark to the other side, changes the clothes and writes nonsense letters. The rules written in step 1 are what stop that. They are made for this one character, from its picture, so a robot gets "one wheel, no legs" and a cat gets "two arms, two paws, one tail".

## How scenes must be written (when you edit a script)

- One scene is one camera position and one small action.
- The line is short: at most 16 words.
- `picture` describes the start of the scene in full, every time: where the character is, every object and where it is, what is held.
- Everything the scene uses is already visible in its start picture. Nothing arrives from outside the frame.
- `does` describes things that are seen happening, tied to the words. When something moves, say it is seen travelling the whole way.
- What one scene did is how things look at the start of the next.

## Limits

One character per show. The character speaks its own lines (no narrator-only mode). One fixed place per show. Full guide: `cartoon/README.md`.
