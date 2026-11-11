---
name: episode-director
description: "Plans one short educational episode for our AI presenter: script, sets, camera shots, her physical direction, cutaways. Use whenever an episode spec is written or reviewed."
---

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
- **Write for the ear.** She is heard once, never re-read. One idea per sentence, everyday words, no colon or dash, no clause hanging off a clause. If a line needs an exception to be true, drop the claim instead of adding the exception.
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
- **Gestures stay small and close to her chest.** Never a hand pushed toward the camera, never arms spread wide: a hand near the lens comes out huge and stops looking like hers.
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
