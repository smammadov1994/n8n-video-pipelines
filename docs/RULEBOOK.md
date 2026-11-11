# Episode rulebook (everything the machine follows)

Put together 2026-11-10 23:40 from the live files. Sources are named in each part; edit those files, not this copy.

Contents: A. Director rulebook · B. Long-form style · C. Rules inside every video prompt · D. Picture maker instructions · E. Picture check · F. Clip checks · G. Limits enforced by code

---

# A. Director rulebook
Source: `skills/episode-director/SKILL.md`. The script-writing AI reads this for every episode.

# Episode Director

Turns a topic into a spec the episode maker can shoot: a 35-45 second YouTuber-style explainer with one presenter, several locations and camera angles, and documentary cutaways. Every rule here was learned from a take that went wrong; follow them even when they feel fussy.

The presenter is always the same woman: long straight dark hair with a middle part, beige ribbed tank top, small gold heart necklace, blue jeans, black clip-on mic on her neckline. Never describe her differently and never change her clothes.

## 1. Shape of an episode

Six takes, hard cuts between them, about 6-7 seconds each.

| Take | Job | Where |
|---|---|---|
| 1 | Hook: one surprising, concrete fact or question | `desk_front` |
| 2 | Set up the idea in plain words | `desk_side` (the "turn to second camera" cut) |
| 3 | First part of the explanation | location set A |
| 4 | Second part | location set B (a different angle or spot) |
| 5 | The part that makes it click | location set A or B, whichever take 4 did not use |
| 6 | Payoff: why it matters, then "Follow for more." | `desk_front` |

- Never use the same set in two takes in a row.
- Exactly two cutaways, on two of takes 3, 4, 5.

## 2. Script (what she says)

- 14 to 20 words per take. One idea per take. Short sentences.
- American spelling (neighbors, defenses, color). Plain words a twelve-year-old knows. If a technical word is needed, say it once and explain it in the same breath.
- Take 1 never starts with "Did you know", "Hey guys" or "Today". Open on the fact itself.
- Numbers: at most one per take, spelled out in words, and only if you are certain of it. Prefer comparisons ("about as fast as your fingernails grow") to figures.
- Only well-established, school-level facts. No disputed claims, no statistics you would have to look up, no health advice.
- No place names, people's names or foreign words in her lines ("Hawaii" came out wrong, and the word check cannot hear a mispronounced name). Say what it is instead: "whole islands", "the biggest desert on Earth". Names can go in the post text.
- First person is fine ("I love this part"). No hype words: amazing, incredible, mind-blowing, insane, crazy.
- **One human moment per episode.** In one of the last three takes she reacts to the fact in a few of her own words, inside the line: "I love that.", "That still gets me.", "Honestly, that surprised me." Its `does` gives the reaction a face: right after those words a closed-lip smile and a small shake of the head, or one eyebrow lift that melts into a smile. This is the moment viewers remember (the owner's favourite: "I love that" with the little face at the end of the trees episode). Exactly one; more feels fake.
- Read all six lines in a row: they must make sense as one continuous explanation with no line depending on something only the picture shows.

## 3. Sets (where she is)

`desk_front` and `desk_side` always exist (her home studio: bookshelf, globe on the shelf, lamp; she sits chest-up with no desk or table in the frame).

**Nothing in front of her.** Never put a table, desk, counter, railing or any object between her and the camera, and never a surface along the bottom of the frame: the video model makes her body pass through it. If a place has a table or counter, put it behind her or to one side. Objects that show the topic go behind or beside her at shoulder height. Her direction never has her touch, lean on or pick up anything. You design two or three location sets per episode.

**Never a plain background.** Every second of the video has scenery about the topic behind her or on screen: no blank wall, no plain coloured backdrop, no empty sky filling the frame.

**The scenery must teach.** The location has to be the thing she is talking about, visible behind her: lava rock for volcanoes, a tide pool for tides, a beehive and flowers for bees. A viewer with the sound off should guess the topic from the background.

Each location set is one still picture she starts every take from. Rules that keep her face her own:

- **Straight on, eye level.** Camera directly in front of her at her eye height. Never from below, above or the side.
- **Chest-up or waist-up, close.** Her head is about one third of the frame height. Never a wide shot of a small figure, never walking toward the camera.
- **Soft, even daylight on her face.** Open shade or overcast. No sunset glow, no backlight, no rim light, no coloured light.
- **She is still.** Standing or sitting in one spot. Movement belongs to the cutaways.
- Two location sets should differ clearly (other side of the place, a different object behind her, standing vs sitting on a rock) so the cut reads as a new shot.
- No other people, no animals touching her, no text or signs.
- Hands empty and down, bare wrists.

For each set write `picture` (what the still shows: where she is, what is behind her, framing) and `camera` (one sentence used in every video prompt for that set, ending "exactly as in the first frame").

## 4. Her direction (what she does)

From the performance-bible method. **The camera sees verbs, not feelings.**

- Never write a mood word: energetic, excited, confident, charismatic, playful, curious, warm. Write the physical action.
- Two or three small actions per take, each tied to specific words of her line: "On the words *pull apart* her hands move apart a few centimeters."
- **Prepare before the word.** If a gesture has a setup, the setup happens before she says the word, so the meaningful part lands on it: "Before the words *pull apart* her two fists are already together at chest height; on the words they move apart." Never "she brings her fists together and then moves them apart" on the word.
- Channels to use: a small lean in as she starts, one glance away and straight back to the lens, a slight head tilt, one corner of her mouth lifting, a closed-lip smile, a slow nod, a half-beat pause after a word, one small hand gesture at chest height.
- **At most one eyebrow lift per take**, and it settles straight after.
- **No mouth action on a spoken word** (no lip press, no bite): it swallows the word.
- Hands stay below her chin and never cross her face. She never touches, holds or leans on anything.
- Her eyes are on the lens unless a glance is written.
- Every take ends: "After her last word she closes her lips and holds the lens."

## 5. Cutaways

Documentary footage with no people that covers the picture while her voice carries on. It should show the thing she just named, moving: lava rising, a bee on a flower, a river running to the sea.

- `after_words`: how many words of her line are spoken before the cutaway starts (usually about half the line, so we see her say the start).
- `prompt`: one or two sentences. Name the camera move (slow push-in, aerial drift, macro, time-lapse feel), the subject, the light. End with: "realistic documentary footage, no people, no text. <ambient sound> only, no speech, no music."

## 6. Output

One JSON object, nothing else:

```json
{
  "title": "short episode title, no clickbait",
  "sets": [
    {"name": "lava_field", "picture": "...", "camera": "... exactly as in the first frame."}
  ],
  "takes": [
    {"n": 1, "set": "desk_front", "says": "...", "does": "...", "cutaway": null},
    {"n": 3, "set": "lava_field", "says": "...", "does": "...",
     "cutaway": {"after_words": 8, "prompt": "..."}}
  ],
  "post": {"title": "...", "description": "two sentences", "hashtags": ["#science", "..."]},
  "facts": ["each factual claim the script makes, one per item, in plain words"]
}
```

Set names are lowercase letters and underscores. `desk_front` and `desk_side` are used by name and are not listed under `sets`.

---

# B. Long-form style (added on top of A for episodes marked "long")
Source: `skills/episode-director/LONGFORM.md`

## 7. Long-form style (this episode uses it; it overrides sections 1, 3 and 5 wherever they differ)

A richer YouTube cut: about 65-75 seconds, shot almost entirely on location, with a new place or framing on almost every cut.

**Shape.** Nine takes.

- Take 1 is the hook and is shot at the most striking location, not in the studio.
- Takes 2-8 walk through the explanation, one idea each, moving from place to place.
- Take 9 is the payoff and ends with "Follow for more."
- The studio (`desk_front`) may appear at most once, somewhere in the middle, as a "here is the trick" beat. `desk_side` is not used.

**Places.** Design four or five location sets.

- No set is used more than twice, and never in two takes in a row.
- Every set must look clearly different from the others. Vary all of these across the sets:
  - the place itself (shoreline, forest edge, high viewpoint, rocks, reeds, a path);
  - what is behind her and how far away it is (open water to the horizon, trees close behind, a rock wall, a valley far below);
  - framing: chest-up in some sets, waist-up in others;
  - her position in the frame: centred, on the left third, or on the right third, with the scenery filling the other side;
  - standing in some sets, sitting on the ground in another.
- Her face is still straight on to the lens at her eye level in every set, in soft even daylight. That rule does not bend; the variety comes from everything else.
- The "nothing in front of her" rule still holds in every set.

**Camera feel.** In each set's `camera` sentence choose one and say it: locked off on a tripod; a very slow push-in toward her; a slight handheld sway. Use at least two different ones across the episode.

**Cutaways.** Three, on any takes except take 1 and take 9. Nature footage with no people, as in section 5, each with a different camera move (aerial drift, macro, slow push-in, underwater, time-lapse feel).

**She never walks and is never filmed from behind or far away.** Walking shots of her were tried and looked wrong (the owner, 2026-11-10). She is only ever seen still, talking to the lens, in a new place each time. The feeling of travel comes from the change of place and framing alone.

Everything else (script rules, her direction, output format) is unchanged. The JSON has nine takes and four or five sets.

---

# C. Rules written into every video prompt
Source: `scripts/make_edu.py` (RULES), adjusted in `scripts/make_episode.py`

> One continuous take, no jump cuts, no zoom. She says the line exactly once, word for word, adds nothing and repeats nothing. Her face keeps exactly the proportions of the first frame. Hands empty with five natural fingers. Her forearms and wrists are bare skin with nothing worn on them. She keeps the same beige ribbed tank top, gold heart necklace and black clip-on mic with its cable. The same place and scenery stay behind her from the first frame to the last. No text on screen, no captions, no music.

Every talking clip's prompt is: SCENE (camera sentence of the set + her direction) + LINE (her exact words) + these RULES.

---

# D. Instructions to the picture maker (each location picture)
Source: `scripts/plan_episode.py` (PICTURE)

Use your image generation tool to make ONE new landscape 16:9 image of the AI-generated character in the attached reference image (a synthetic character, not a real person). Keep her face as identical to the reference as possible: same face shape, same eyebrows at the same resting height, same eyes, nose, lips and jaw. Same long straight dark hair with a middle part, same beige ribbed tank top, same small gold heart necklace, blue jeans, and a small black clip-on lavalier mic on her neckline with a thin cable. Bare wrists, no watch, no bracelets. Save it in the current folder as {name}.png.

It is a single unedited still frame from a YouTube educational video shot on a mirrorless camera on a tripod.

Where she is and what is behind her: {picture}

Fixed rules: the camera is exactly at her eye level and straight in front of her (not from below, above or the side). She is close to the camera, chest-up or waist-up, with her head about one third of the frame height; she is centred unless the description above puts her on the left or right third. Soft, even, neutral daylight on her face: no sunset glow, no orange tint, no backlight, no rim light. Nothing crosses in front of her body: no table, desk, counter, railing or any other object between her and the camera, and no surface along the bottom of the frame. If the place has a table or counter, it is behind her or off to one side, never in front. The bottom edge of the frame cuts her at the waist or lower ribs with only her clothes there. Objects that show the topic sit behind her or beside her at shoulder height. She is standing or sitting still. Calm friendly expression like the reference: eyebrows relaxed, mouth just slightly open mid-word, looking into the lens. Hands empty and down. No other people, no text, no signs, no watermark. Real skin texture with visible pores, no retouching, no beauty filter.

Reply with just the file path.

---

# E. Picture check (every location picture, before any video is made)
Source: `scripts/plan_episode.py` (BODY). Any "true" = picture is thrown away and remade. Also measured: face match against her master picture.

Read the image file {name} in the current folder. It is a start frame for an AI video of a woman talking to camera.
Answer these as plain facts about what is in the picture, not as a judgment of quality:
- surface_in_front: is there any table, desk, counter, bar, railing or other surface or object between her and the camera, or running along the bottom of the frame in front of her body? (true even if it looks natural, e.g. she sits at a table with her hands on it)
- hands_on_object: are her hands resting on or holding anything?
- limb_mistake: extra, missing or fused arms, hands or fingers
- jewelry_on_wrist: a watch or bracelet
Answer with ONLY one JSON object: {{"surface_in_front": true or false, "hands_on_object": true or false, "limb_mistake": true or false, "jewelry_on_wrist": true or false, "note": "one short sentence on what you saw"}}

---

# F. Clip checks (every talking clip, after it is shot)
A clip that fails any of the three is reshot with a new seed, up to 4 tries. The best try is kept and flagged if none passes.

1. **Words** (`scripts/make_video.py`): the clip is transcribed; at least 97% of the scripted words must be heard, in order. Apostrophes and -our/-or spellings are ignored.
2. **Face** (`scripts/face_check.py`): her face is measured against the master picture across the clip; typical frame at least 0.60, no frame under 0.42.
3. **Big mistakes** (`scripts/clip_check.py`): six frames on a sheet, these questions, any "true" fails the clip. Small things (watch, bracelet, tiny differences) are deliberately not asked.

   - **limb_mistake**: an extra arm or hand, a missing arm, an arm that swaps sides or bends the wrong way, or a hand that is obviously mangled (clearly six or more fingers, or fingers melted into a lump). Ordinary motion blur, fingers held together, and one hand resting on, over or against the other do not count
   - **body_through_object**: a part of her body clearly sunk into or passing through a solid object or surface (for example her torso inside a table)
   - **different_person**: her face in a later frame is obviously a different woman from frame 1, or is badly warped. Normal talking mouth shapes, blinks, smiles and raised eyebrows do not count
   - **outfit_swapped**: her top is a clearly different garment or colour than in frame 1
   - **place_swapped**: a later frame is clearly in a different place than frame 1, or a large object pops into or out of the scene. Small changes from the camera moving or her shifting do not count
   - **turned_away**: her back is to the camera, or her face is turned away from the lens in most frames
   - **text_or_extra_person**: readable text, a caption, a logo or watermark on screen, or a second person

---

# G. Limits enforced by code (a script that breaks these is sent back to the writer)
Source: `scripts/plan_episode.py` (problems_in)

- Takes: 5-6 (short) or 8-10 (long). Words per take: 12-21.
- Every take names a set that exists; never the same set twice in a row; every take has direction.
- No mood words in direction: energetic, excited, confident, charismatic, playful, curious, enthusiastic, passionate, cheerful.
- No hype words in lines: amazing, incredible, mind-blowing, insane, crazy, "did you know", "hey guys".
- Location sets: 2-3 (short) or 4-5 (long). Long: no set more than twice, studio at most once, 2-4 nature cutaways, none showing a woman.
- Fact check: a second AI reads every line; any false or overconfident line is rewritten before anything is shot.
- One episode at a time; a topic that fails twice is skipped.
