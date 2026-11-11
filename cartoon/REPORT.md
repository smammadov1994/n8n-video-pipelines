# Mango the cooking cat: feasibility test report

Date: 11 November 2026. One test video, `final.mp4`, 32.8 seconds, 1920x1080, four shots.

## Short answer

Yes, the same setup that makes the realistic presenter can make a kids cartoon. The cat stayed the
same cat, the cartoon look did not slip, every word was spoken correctly, and after the owner's feedback
the cooking step now shows a real cause and effect (the berry is seen leaving the bowl and landing in
the cup). It took 8 clip generations out of the 12 allowed. Nothing was uploaded or posted anywhere.

## What was made

| File | What it is |
|---|---|
| `final.mp4` | The test video (4 shots joined) |
| `character_sheet.png` | Reference picture of Mango, front view, plain kitchen |
| `pictures/scene1`, `scene2a`, `scene2b`, `scene3` `_1344x768.png` | The start picture of each shot |
| `final_frames_sheet.jpg` | 16 frames of the final video on one sheet, for a quick look |
| `character.txt`, `style.txt` | The character description and the one style paragraph, reused word for word |
| `script.json` | The lines, the picture descriptions and the actions for each shot |
| `make_clips.py`, `join.sh`, `sync_check.py` | The small scripts used (technique copied from the kaiyros pipeline, nothing there was edited) |

The character: Mango, a very round pear-shaped apricot-orange cat with no stripes, cream belly and
muzzle, pink heart-shaped nose, green eyes, one folded ear, teal apron with a round yellow pocket and a
floppy teal chef hat with a yellow band. Designed from a written description, not from any existing
cartoon. I did not run a formal similarity search against existing characters: **not verified** beyond my
own judgment that it does not look like a known cartoon cat.

The script (a no-heat, no-knife fruit and yoghurt cup):

1. "Hello, little chefs! I am Mango the cat. Today we make a yummy fruit and yoghurt cup!"
2. a) "First, spoon some creamy yoghurt into your cup." b) "Then drop soft berries on top. Plop, plop, plop!"
3. "Look, our fruit cup is ready! Always cook with a grown-up. Bye-bye, little chefs!"

## The five questions

### 1. Did the cat stay the same across scenes?

Yes. In every frame I looked at (6 frames per clip for all 8 clips, plus 16 frames of the final video)
it is the same cat: same round shape, same orange, same face, same folded ear, same apron, pocket and
hat. No extra limbs, no extra tails, no second cat, no text on screen.

Small slips I saw:
- Shot 3: when Mango puts the cup down, the yellow pocket is hidden for a moment and Mango stands up
  taller than before.
- A spare take of shot 3 (not used) grew two small buttons on the apron straps.
- Berry shot: a thin light-green strip shows beside Mango's body for about two seconds, and pink paw
  pads appear when the paw turns (they are not on the character sheet).

### 2. Did the style hold?

Yes. All clips kept the soft, rounded, clay-like 3D kids-show look from first frame to last. No drift
toward a realistic photo look in any clip. This was the biggest unknown and it turned out to be the
strongest result.

### 3. Did the mouth sync look acceptable?

Probably yes, but this is the least certain answer, because I cannot watch and listen at the same time
the way a person does. What I did check:
- Words: each clip was transcribed by a speech-to-text program. All four clips in the final video are
  word for word correct.
- Mouth movement: I looked at close-up face frames five times per second. The mouth opens and closes in
  varied shapes all the way through each line and closes into a smile when the voice stops.
- A rough measurement (how open the mouth is against how loud the voice is, frame by frame) shows the
  mouth opens when the voice is loud, with no delay, in the yoghurt and berry shots and in the first
  version of scene 2. It is weak or unreliable for shots 1 and 3, where the head and props move through
  the measured area. Treat this number as a hint, not proof.

**Not verified:** whether each mouth shape matches each sound closely enough to look right to a person
at normal speed. the owner watched the first cut and did not complain about the mouth, which is the best
evidence so far. Also **not verified by ear:** how pleasant the voice sounds. I chose it from its
description ("Kids": young, cheerful, clear); I cannot hear it.

### 4. How many tries did each scene need, and what failed?

| Shot | Clips made | Result |
|---|---|---|
| 1 Hello | 2 | First try was good. The second was made only to see if the result repeats: it did. |
| 2 first version (yoghurt and berries in one 10-second shot) | 1 | Words and cat fine, but rejected by the owner: berries appeared on the spoon from nowhere. |
| 2a Yoghurt | 1 | First try good: spoon lifts yoghurt out of the bowl, carries it over, tips it into the cup. |
| 2b Berries | 2 | Try 1: berry path was right, but the model added a fourth "plop" in the quiet second after the voice ended. Try 2 (new seed, plus a rule "adds no word after the last one"): correct. |
| 3 Result and goodbye | 2 | First try was good. Second made for comparison, also good but with the apron buttons slip. |

Total: 8 clip generations. Other small failures: the voice maker once said "clop" instead of "plop"
(caught by the transcript, re-spoken once); the speech-to-text program invented "Thank you" at the end
of the first joined video, which I checked is silence, not real sound.

### 5. Can the model show a real cause and effect? (the question that decides a cooking show)

Yes, when the shot is set up for it. What made the difference:

- **One action per shot.** Yoghurt and berries in one shot failed. One shot for the spoon, one for the
  berries worked first time for the movement.
- **Start picture with the action already begun.** The yoghurt picture starts with the spoon already in
  the bowl with yoghurt on it; the berry picture starts with the paw already holding a strawberry just
  above the berry bowl. The model only has to move something it can already see.
- **The path spelled out in order** in the instructions ("lifts the strawberry out of the bowl, carries
  it over the cup, lets it fall") plus "nothing appears from nowhere".

Checked by looking at close-up frames in order, six per second: the strawberry leaves the bowl in the
paw, travels across, drops into the cup; the paw goes back into the bowl, comes out with a blueberry,
carries it over and drops it. Same result in both berry tries, so it was not luck.

Weak spots that remain:
- The blueberry floats a little beside the paw rather than sitting firmly in it.
- In the last frames of the berry shot there are two blueberries in the cup though only one was dropped.
- The cup has only one spoonful of yoghurt at the end of the yoghurt shot and is full at the start of
  the berry shot. A real show would say "keep spooning" or add a shot.
- I did not try the first-and-last-frame method; it was not needed.
- Only gentle actions were tested (lift, carry, drop). Pouring, stirring, spreading and mixing colours
  are **not tested**.

## Things kept the same between shots, and things that were not

Making the 2a and 2b start pictures from the scene 1 picture (instead of from the character sheet)
fixed the props: same clear glass bowls, same pink, yellow and purple jars. The first version of scene 2
had teal and yellow bowls and a different jar, because it was made from the character sheet alone.

Still different: the cup stands on the left in shot 1 and in the middle in the cooking shots, and the
bowls are gone from the counter in shot 3. These are choices in the start pictures, easy to fix next time.

## What a repeatable show would need, and is it worth it

Needed:
1. A fixed character pack: the character sheet, the character text and the style paragraph (all exist now).
2. One "kitchen master" picture, and every start picture made from the previous one, so props never change.
3. A shot rule: one visible action per shot, 5 to 7 seconds, start picture shows the action already begun.
   A recipe step becomes two or three shots, so a one-minute episode is about 10 to 12 shots.
4. An automatic look-check for cartoons. The production face-match check does not work on a cat. The
   word check works as it is. For looks, a picture-reading check per clip ("same cat? same outfit? did
   the berry leave the bowl?") would replace my looking by hand.
5. A person's ear on the voice once, and a person's eye on the mouth at normal speed.
6. Child-safety rules written into the script step (no heat, no knives, grown-up nearby), checked each episode.

Cost seen here: each clip waited and rendered in a few minutes behind the production jobs; pictures and
voice were free. About 1.3 tries per shot on average.

Is it worth it? The technical risk is lower than expected: character and style held on the first try,
which is the part that usually kills cartoon attempts. The remaining work is mostly planning shots
carefully. A fair next step is one full 60-second episode with the rules above before deciding. That would
show whether 10 to 12 shots still feel like one continuous kitchen. That has **not been tested**; this test
covers four shots only.

## Guardrails kept

- Worked only in this folder; nothing under `kaiyros/` was changed.
- Jobs were added to the back of the 5090 queue (the production script jumps the queue; this one does
  not). No restart, no memory freeing, no cancelling, `connection.json` untouched.
- No accounts created, nothing posted or uploaded. The Fish Audio key was never printed.

---

# Second video: Mango makes an omelet (`final_omelet.mp4`)

42.9 seconds, 1920x1080, five shots. Made with the rules learned from the first video: one action per
shot, start picture with the action already begun, every start picture made from the first one so the
kitchen and props match. Files are in `omelet/` (script, start pictures, voice, all clips).

The lines:
1. "Hello, little chefs! It is Mango. Today we make a fluffy yellow omelet!"
2. "First, crack two eggs into the bowl. Tap, tap, crack!"
3. "Now whisk, whisk, whisk, until it is all yellow."
4. "The hot pan is a job for a grown-up. Pour it in, and wait."
5. "Look, a fluffy yellow omelet! Always cook with a grown-up. Bye-bye, little chefs!"

Safety choice (mine, not asked): an omelet needs heat, so the earlier "no stove" rule could not hold.
Cracking and whisking are shown as the child's steps; the pan line says the hot pan is a grown-up's job;
the cooktop shows no flame, fire or smoke.

## What was checked and what came out

- Words: all five clips and the joined video transcribed word for word correct.
- Frames looked at in order, four per second, for the three action shots:
  - **Crack:** Mango taps the egg on the bowl rim, the shell splits, the yolk and white drop out of the
    shell into the bowl next to the first yolk, and Mango ends holding one half shell in each paw.
  - **Whisk:** the whisk circles in the bowl and the two yolks visibly break and blend into one even
    yellow liquid.
  - **Pour:** the egg runs in a stream from the bowl into the pan, the pan fills, the bowl empties and is
    put down on the counter.
  These three actions (cracking, mixing, pouring) were untested before. All three worked on the first try.
- Same cat, same outfit, same kitchen, same jars in all five shots of the final video. No extra limbs, no text.

## Tries

| Shot | Clips made | Result |
|---|---|---|
| 1 Hello | 1 | Good. Mango does not clearly point at the eggs as asked; small thing. |
| 2 Crack | 1 | Good. |
| 3 Whisk | 1 | Good. |
| 4 Pour | 1 | Good. |
| 5 Result | 4 | Try 1: kitchen faded to black with a spotlight, apron turned into dungarees with buttons, omelet became a stack. Try 2: kitchen fine, but apron grew yellow buttons and lost its pocket after the plate was put down. Try 3 (new start picture, plate already on the counter so the whole apron is visible): apron right, but the kitchen turned into a dark night scene. Try 4: good. |

Total 8 clips. The voice maker also got two lines wrong once ("Oh" for "Hello", "risk" for "whisk");
both were caught by the transcript and re-spoken.

## Two new lessons from shot 5

1. **Do not hide part of the outfit in the start picture.** When the plate covered the apron, the model
   had to invent the apron once the plate moved, and invented buttons. With the apron fully visible
   from the first frame it stayed correct.
2. **Do not name the thing you do not want.** Adding "the background never goes dark" was followed by a
   dark kitchen; replacing it with "bright sunny daytime kitchen, same even lighting in every frame"
   was followed by a correct one. One try each, so this is a likely cause, **not proven**.

The goodbye shot is the weakest kind of shot in both videos (the apron slip appeared in the first video
too). A fixed, reusable goodbye clip would remove that risk from every episode.

## Weak spots in this video

- No shot of the omelet cooking, being folded or going onto the plate: it cuts from liquid egg in the
  pan to the finished omelet. Flipping and folding are **not tested**.
- The script does not tell children to wash hands after touching raw egg. A real episode should.
- Shot 1 shows a yellow glow in the empty bowl (the apron pocket seen through the glass); it can look
  like the bowl already holds something.
- Mouth sync by a person at normal speed and the sound of the voice: **not verified**, same as before.

---

# Third video: Mango makes a peanut butter and jelly sandwich (`final_pbj.mp4`)

50.2 seconds, 1920x1080, six shots. Same Mango, same kitchen, same voice, same method as the omelet
video. Files are in `pbj/` (script, start pictures, voice, clips).

The lines:
1. "Hello, little chefs! It is Mango. Today we make a peanut butter and jelly sandwich!"
2. "First, put two slices of bread on your plate."
3. "Spread peanut butter on one slice. Smooth, smooth, smooth."
4. "Spread jelly on the other slice. Wiggle, wiggle, wiggle."
5. "Now press the two slices together. Pat, pat, pat." (first version ended in "Squish!", see below)
6. "Look, a peanut butter and jelly sandwich! Always cook with a grown-up. Bye-bye, little chefs!"

Kid-safe: the only tool is a small rounded wooden spreader with a blunt tip. No knife appears in any
picture or clip I looked at. The jars have no labels and there is no text on screen.

## What was checked and what came out

- Words: all six clips and the joined video transcribed word for word correct.
- Frames looked at in order, four per second, for the four action shots:
  - **Bread:** Mango carries the second slice in both paws from above the wooden board to the plate and
    lays it down.
  - **Peanut butter:** the spreader lifts out of the peanut butter jar with a blob on it, moves to the
    slice next to that jar and wipes back and forth; the slice ends up mostly covered.
  - **Jelly:** the spreader lifts out of the jelly jar with a blob on it, moves to the plain slice next to
    that jar and wipes back and forth; the slice ends up covered.
  - **Press:** Mango lowers the jelly slice, jelly side down, onto the peanut butter slice, presses with
    both paws, lifts the paws away; one closed sandwich stays on the plate.
  Every ingredient is seen coming from where it sits. Nothing appears from nowhere in these shots.
- Same cat, same outfit (apron and pocket correct in every shot, including the goodbye), same kitchen,
  jars and plate in the same places in all six shots. No extra limbs, no text.

## Tries

Seven clips: one per shot, plus one retake of the press shot after the owner heard an odd sound in it (see below). The goodbye shot, which needed four tries in the omelet
video, worked first time here with the two lessons applied (whole apron visible in the start picture,
"bright sunny daytime" wording).

Two of the six clips (bread, goodbye) sat in the 5090 queue behind production jobs for more than
40 minutes, longer than my script waits. I picked them up from the queue when they finished instead of
queueing them again, so no extra work was put on the machine.

## Weak spots in this video

- **Bread shot ends differently from the next shot.** The second slice lands partly on top of the first
  one; the peanut butter shot then starts with the two slices lying side by side. The cause is my start
  picture (first slice in the middle of the plate, no room beside it). Fix next time: first slice on
  the left half of the plate.
- Peanut butter covers most of the slice, not edge to edge.
- The jelly looks pinker on the bread than in the jar.
- In shot 1 the bread stack may read as three slices; the script says two.
- Mango's arms stretch rather long in the bread shot and in the last wave.
- The spreader lies in front of the jelly jar in some shots and is missing from the counter in the
  press shot's close frames. Small.
- Peanut allergy: the video does not mention it. A real episode for small children should (for example
  "ask your grown-up first"), or use a seed butter.
- Mouth sync by a person at normal speed and the sound of the voice: **not verified**, same as before.

## Where the method stands after three videos

| Video | Shots | Clips made | Shots right on first try |
|---|---|---|---|
| Fruit and yoghurt cup | 4 | 8 | 3 of 4 (one extra word), plus the rejected first version of scene 2 |
| Omelet | 5 | 8 | 4 of 5 |
| PB&J sandwich | 6 | 6 | 6 of 6 |

Each video used what the one before taught. The rules now are: one action per shot; start picture shows
the action already begun; every start picture made from the first one; whole outfit visible in every
start picture; say what you want, not what you do not want; spell out the path of each ingredient.

## Fix after the owner's feedback: odd sound in the press shot

the owner heard "some weird sound" after "now press the two slices together". Cause found by measuring the
sound: the voice maker stretched the word "Squish!" into 1.7 seconds of hiss. The clip's sound matched
the voice track exactly, so the video model did not add anything; the voice track itself was bad. My
word check could not catch it, because the speech-to-text program still heard "Squish" correctly.

Five more takes of the same line still dragged the word to about one second, so I changed the line to
"Now press the two slices together. Pat, pat, pat." and picked the take with three short, separate pats
(about half a second each). The press shot was remade with that voice (one new clip, good on first try:
slice lowered, both paws pat, closed sandwich left on the plate) and `final_pbj.mp4` was joined again
(51.2 s). Whether it now sounds right: **not verified**, I cannot hear it; the measurements say the long
hiss is gone.

New rule: avoid sound-effect words with long hissing sounds ("squish", "whoosh", "shhh") in the script;
use short, hard words ("pat", "tap", "plop"). And measure every voice line for a drawn-out ending, not
only its words (`voice_takes.py` does this).

---

# Published on YouTube (11 November 2026)

the owner asked for the three videos to be posted as Shorts on the channel **Yummy With Mango**
(@YummyWithMango) and marked as made for kids. Done through his Chrome, with his go-ahead on titles,
descriptions and Public visibility.

| Short | Link | Length |
|---|---|---|
| Mango Makes a Fruit and Yoghurt Cup \| Easy No-Cook Snack for Kids | https://youtube.com/shorts/Arykk9ItdAE | 0:33 |
| Mango Makes a Fluffy Omelet \| Cook With a Grown-Up | https://youtube.com/shorts/LXVR2w52QuM | 0:43 |
| Mango Makes a PB&J Sandwich \| Easy Kids Recipe | https://youtube.com/shorts/Xvgv6w9yg4o | 0:51 |

Settings on each: Public; "Yes, it's made for kids" (YouTube then switches off comments and
notifications, shown in Studio); no paid promotion; YouTube's AI question answered "No" because it
asks only about realistic-looking content or real people, and this is an obvious cartoon. Each
description still says "Animated with AI tools". YouTube's copyright check found no issues on all three.

Shorts must be tall, so each wide video was turned into a 1080x1920 file (`shorts/` folder,
`make_short.sh`): the middle three quarters of the picture at full width, on a soft blurred copy of
itself. Nothing from the counter is cut off; I checked one frame of each layout, not every frame.

Things the owner should know:
- The channel's profile picture is currently a photo of a person, not Mango. For a kids channel a Mango
  picture would fit better.
- The channel sits under a Google account whose address differs from the one in the hand-over note
  (the note named a yummywithmango address). The channel name and handle match.
- I did not watch the Shorts play on YouTube itself; I confirmed they are listed as Public in Studio.
