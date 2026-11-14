---
name: educational-presenter
description: "Makes a 35 to 45 second explainer in which our AI presenter answers one science or how-things-work question, as a wide video and a vertical Short. Use when someone wants an educational video, an explainer, or a talking presenter video on a topic."
---

# Educational presenter pipeline

One presenter (always the same woman), several places, a few documentary cutaways, every fact checked. The episode is written by the rulebook in `skills/episode-director/SKILL.md`; this file is only about what to ask and which steps to run.

## Ask first

1. **What question should the episode answer?** One clear question ("Why is the ocean salty?"). If they give a broad subject, offer three sharper questions and let them pick.
2. **Where should it be filmed?** Optional. Real, specific scenery that shows the topic. If they do not say, the writer chooses.
3. **Short or long?** The normal episode is 35 to 45 seconds. Ask only if they bring up length.

Do not ask about the presenter's look, clothes or voice: they are fixed.

## Steps

1. `educational_plan` with the topic: the script is written, fact-checked, polished for the ear, and the start pictures are drawn and checked. Several minutes; poll `educational_status`.
2. Read the lines back from the result. If a line is wrong, plan again with a sharper topic.
3. `educational_shoot`: the voice is recorded first, each take is filmed around it and checked for words, face and big mistakes, up to four tries. Thirty minutes or more on the GPU; say so first.
4. `educational_status` reports whether the episode is ready or needs a person to look at it, and where the files are.

Publishing to YouTube is not offered through these tools. It is done by the owner's scheduled workflow.

## Rules

- The presenter never walks, is never filmed from behind or far away, and never handles objects.
- Only big mistakes fail a take: swapped limbs, giant hands, a changed outfit or background, a second person, text on screen.
- A misread word is fixed by rewording the line, not by trying again.

## Limits

One presenter only. Topics that need diagrams or on-screen text do not suit it. A flagged episode needs a person to listen before it is used.
