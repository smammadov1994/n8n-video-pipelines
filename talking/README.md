# Talking avatar (LongCat-Video-Avatar 1.5)

One picture of someone + one voice recording goes in. A video of that someone saying those words comes out: lips, face, head and hands move with the voice.

It is kept apart from the three pipelines because it works differently from everything else here. It is a tool that is run by hand for now; no n8n workflow drives it yet.

<img src="../docs/media/talking_frames.jpg" width="640" alt="Four frames from the first test: the presenter talking, made from one photo and a voice file">

Example: [`examples/talking/first_test.mp4`](../examples/talking/first_test.mp4) (first test, 3.7 seconds, one segment).

## What it is for

- A real person talking to camera from their own photo and their own (or a cloned) voice.
- Any speaker the picture shows: a person, a cartoon, an animal, a mascot.
- Long takes: clips are built from segments that continue each other, so a minute or more stays one shot.

It is not for shots without a speaker (scenery, product close-ups, action), for big movement such as walking, or for scene changes inside one clip. Those stay with the general models.

## How it differs from the other models in this repository

| | MiniMax H3 / HyperFlow Flash (episodes, cartoon) | OpenJutsu one-click swap (person swap) | LongCat Avatar 1.5 (this folder) |
|---|---|---|---|
| Starts from | Text, plus a start picture | An existing video of someone else | One picture and a voice file |
| What drives the mouth | The model makes picture around the audio; words can still come out wrong, so every take is transcribed and checked | The original performer's movements | The voice file itself; the model is built for lip sync |
| Best at | Any kind of shot: places, actions, cutaways | Re-filming a real clip with our presenter | A person talking, for as long as needed |
| Clip length | Short takes joined in editing | Length of the source clip | Any length, 3.2 s added per segment, but slow past the first (see timing) |
| Runs in | ComfyUI | ComfyUI | Its own program and Python environment, beside ComfyUI |
| Card memory | Fits a 32 GB card | Fits a 32 GB card | Needs the three fixes below to fit 32 GB |

In short: the others decide what the picture shows and hope the mouth matches. This one takes the voice as the fixed thing and makes the face follow it.

## Files

| File | What it does |
|---|---|
| `setup_longcat.sh` | Installs everything on the rented machine: the program, its own Python 3.10, the packages, about 70 GB of model files. Run once. |
| `fit_32gb.py` | Three small edits to the program so it fits a 32 GB card, plus the calm dial (called by the setup script). |
| `flash_attn_shim.py` | Stand-in for a speed package that does not build on the RTX 5090 (used by the setup script only when the real one fails). |
| `run_talk.sh` | Makes one clip: picture, voice file, description, name, number of segments, size, strength. |
| `example-script.md` | A 45-second spoken script with notes for on-screen pieces. |

## Setup

On a Vast.ai machine with 1x RTX 5090, at least 60 GB of memory and 120 GB of disk (the ComfyUI template is fine; this installs beside it):

```bash
scp -r talking <machine>:/workspace/talking
ssh <machine> 'bash /workspace/talking/setup_longcat.sh'
```

Allow 30 to 45 minutes, most of it downloading.

## Making a clip

```bash
bash /workspace/run_talk.sh <picture> <voice.wav> "<description>" <name> <segments> 480p [strength]
```

- **picture**: the speaker, as they should look in the video. A portrait picture gives a 480x832 video.
- **voice.wav**: the full spoken track (Fish Audio in this project).
- **description**: who is in the picture, what they wear, the room, and that they are speaking to the camera. Longer and more concrete works better.
- **segments**: one segment is 3.7 seconds; each further one adds 3.2 seconds. For a voice track of `d` seconds use `ceil((d - 3.72) / 3.2) + 1`.

- **strength** (optional, default 0.45): how hard the face reacts to the voice. See the next section.

The result is `/workspace/LongCat-Video/outputs/<name>/ai2v_demo_1.mp4` for one segment, and `video_continue_<n>.mp4` (the whole clip so far) after each further segment.

Measured on an RTX 5090 at 480p: the first segment takes about 2.5 minutes. Every further segment takes 6 to 8 minutes, because the data carried between segments has to live in main memory on a 32 GB card. One minute of video is 19 segments, so about two hours. For that reason short takes of 4 to 10 seconds, cut together in editing, are the practical way to use it on one card. A machine with more card memory would not need that fix and would be much faster on long takes.

## Keeping the speaker calm

Out of the box the speaker looked angry: wide mouth, raised eyebrows, hands pushing out, as if shouting. In the fast 8-step mode the program locks its own guidance settings (text and audio guidance are both forced to 1.0), so those cannot be turned down. Three things were tested on the same shot on 2026-11-14, and the combination of all three was chosen as the standard:

1. **A calm voice.** This was the biggest single change. The face follows the mood of the voice file, so a punchy read gives a shouting face. For Fish Audio: start the line with `(calm)(soft tone)` and set speed to 0.92.
2. **A calm description.** Say how the face and hands behave, not only that the person is "speaking calmly". The wording that worked, after the part that describes the person and room:
   > ...sits relaxed and talks quietly to the camera like a friend explaining something over coffee. Her face is soft and relaxed with a gentle closed-mouth smile between phrases, eyebrows resting, mouth opening only a little as she speaks. Her hands rest in her lap with an occasional small slow gesture. Calm, warm, unhurried. Steady camera.

   On its own, with the old punchy voice, this was not enough.
3. **Strength 0.45.** The dial added by `fit_32gb.py` (`AUDIO_STRENGTH`, the last argument of `run_talk.sh`). 1.0 is the program as shipped; 0.7 was also tried; 0.45 is the default. Lower values make the mouth move less, so if lips start to look lazy on a new voice, raise it toward 0.7.

## What had to be fixed to run it on an RTX 5090

These are all handled by `setup_longcat.sh`; they are listed so the next person does not rediscover them.

1. **Python version.** The package list is written for Python 3.10 and fails on the machine's 3.12. The script builds a separate 3.10 environment.
2. **Package list.** Two entries (`libsndfile1`, `tritonserverclient`) are not Python packages, and the pinned torch does not know the 5090. They are dropped and a CUDA 12.8 torch is installed.
3. **flash_attn does not build.** `flash_attn_shim.py` supplies the two functions the program calls, using the attention built into torch.
4. **Out of memory at load.** The text encoder (about 11 GB) is kept in main memory; set by `TEXT_ENCODER_ON_CPU=1` in `run_talk.sh`.
5. **Out of memory while sampling.** The Whisper voice encoder and the vocal separator are moved off the card once the voice has been read. After this the card holds about 16 GB before sampling starts.
6. **Out of memory on the second segment.** The data carried over between segments is kept in main memory (`offload_kv_cache=True`). With it the card peaks at about 30.7 GB of 32.
7. **Launch.** The demo program must be started with `torchrun`, even on one card.

## Not done yet

- No automatic check of the result (words heard back, face, big mistakes) like the episode pipeline has.
- 720p and the two-speaker mode have not been tried.
- No n8n workflow.
