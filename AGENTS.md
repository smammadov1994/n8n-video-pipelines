# AGENTS.md

Guidance for AI coding agents (and people) working in this repository.

## What this is

Three unattended video pipelines orchestrated by n8n and rendered on rented RTX 5090s through ComfyUI:

- **Educational presenter**: `workflows/episode-machine.json` → `scripts/episode_job.py`
- **Person swap**: `workflows/swap-machine.json` → `swap/swap_job.py`
- **Kids cartoon**: `workflows/cartoon-machine.json` → `cartoon/cartoon_job.py`

One more pipeline is run by hand, with no workflow: **Cinematic commercial**, `cinematic-commercial/adkit.py` and `cinematic-commercial/box/run_director.py`. Its own `README.md` is the reference.

Read `README.md` for the picture, `docs/RULEBOOK.md` for every content rule, `docs/RUNBOOK.md` for machine setup.

## The one contract every step follows

A workflow node runs a script with `Execute Command`. The script:

1. prints **exactly one JSON object as its last stdout line**,
2. **always exits 0**, even on failure (`{"ok": false, "error": "..."}`),
3. is **safe to run again**: it does only what is still missing.

n8n's `Read ...` Code nodes parse that last line and branch on it. Do not print other lines that start with `{` after the result, do not raise out of `__main__`, and do not make a step depend on being run only once.

## Where things live

| Path | Purpose |
|---|---|
| `scripts/plan_episode.py` | WRITE → CHECK (facts) → POLISH (read by ear) → pictures → face and body check |
| `scripts/make_episode.py` | voice-first clips, word/face/big-mistake checks, up to 4 tries, final wide + vertical |
| `scripts/clip_check.py` | six-frame vision check; questions are the list at the top of the file |
| `scripts/make_video.py` | `words()` and the transcript score used everywhere |
| `scripts/episode_job.py` | n8n steps: `next`, `plan`, `shoot`, `finish`, `post`, `approve` |
| `skills/episode-director/` | the director rulebook the script writer follows (`SKILL.md`, `LONGFORM.md`) |
| `swap/prep_swaps.py`, `swap/text_screen.py` | pick and prepare clips for the swap |
| `swap/swap_job.py` | n8n steps: `prep`, `send`, `collect`, `status` (batches from Kaiyros lists, our presenter) |
| `swap/swap_one.py` | one supplied video, any supplied person: `prepare`, `send`, `collect`, `status`; needs `--rights own` or `agreed` |
| `swap/caption_job.py`, `swap/caption_template/edit.tsx` | captions, product tag and end card on finished swaps, rendered by raea on the Mac |
| `swap/box/` | runs on the swap GPU, not on the Mac |
| `cartoon/show.py` | what a show is; the picture prompt and the clip prompt are built here and nowhere else |
| `cartoon/shows/<show>/` | one character: `show.json` (look, style, place, rules, voice), `character_sheet.png`, `<episode>/script.json` |
| `cartoon/new_show.py`, `cartoon/write_episode.py` | a model writes a new show's rules from a description and a picture; a model writes an episode |
| `cartoon/cartoon_job.py` | n8n steps: `pictures`, `voice`, `shoot`, `finish`, each given `<show>/<episode>` |
| `cartoon/mcp_server.py` | MCP server for the cartoon pipeline; its instructions make the assistant ask for the character first |
| `poster/` | YouTube publishing helpers |
| `cinematic-commercial/adkit.py` | commercials: `draw` (Codex pictures), `build` (director timelines), `sheet` (frames to check), `join` |
| `cinematic-commercial/ads/<name>/spec.json` | one commercial: look, pictures, three clips of three shots |
| `cinematic-commercial/box/` | runs on the GPU: queue director clips, drop a queued clip |
| `comfyui-mcp/` | ComfyUI client (`server.py`), transcription, and the video workflow JSON files |
| `pipelines_mcp.py` | ONE MCP server over every pipeline: `list_pipelines`, `start_pipeline`, then each pipeline's tools |
| `skills/<pipeline>/SKILL.md`, `intake.json` | what to ask the person first, the steps and their tools, the rules; `intake.json` is the same questions as data for a UI |
| `cinematic-commercial/write_ad.py`, `render.py` | a model writes a commercial's script; render its clips straight from the Mac |

State on disk, all outside git: `episodes/<nn-slug>/` (one folder per episode), `output/*.json` (ready list, needs-a-look list, posting state), `swap/ready|sent|finished/`, `cartoon/shows/<show>/<episode>/{pictures,voice,clips,work}`.

## Commands

```bash
./start.sh start                                          # run n8n (http://localhost:5678)
./status.sh                                               # health: engine, current episode, publish queue, flags
./start.sh import:workflow --input=workflows/<file>       # after editing a workflow file
./start.sh publish:workflow --id=<workflow id>            # then restart n8n, between episodes
python3 scripts/episode_job.py approve <episode folder>   # publish a flagged episode by hand
python3 scripts/audit_looks.py --requeue                  # re-check finished episodes
touch episodes/PAUSE                                      # pause; delete the file to resume
```

There is no test suite. To check a change, run the single step it touches against an existing episode folder and read its JSON line.

## Rules that came from real failures: keep them

- **Voice first.** Speech is generated before the clip and anchored at frame 0. Do not go back to generating speech inside the video model: voices drift between clips.
- **A misread word is fixed by rewording, not by retrying.** If a line fails the word check four times, change the words (`"a drop"` → `"one drop of water"`).
- **Only big mistakes fail a clip.** Swapped limbs, giant hands, a changed outfit or background, a second person, text on screen. Jewellery that comes and goes does not. Do not tighten `clip_check.py` without being asked.
- **The presenter never walks, is never filmed from behind or far away, never touches objects.** Still, talking, in varied places and framings.
- **The video models never draw text.** Text comes from raea after the fact (`swap/caption_job.py`): it is code, so it is always spelled right. Keep source clips free of burned-in captions.
- **Swap picker**: one person, face talking, product in hand; no outfit videos, no word-by-word captions. Count only *newly* prepared clips toward the keep limit.
- **Cartoon**: no script names a character. Everything about one lives in `shows/<show>/show.json`; a new character is a new show, never a code change. Everything a scene uses is already visible in its start picture; actions are written as things seen happening; no knives, no flame when the audience is children. Files sent to the GPU carry the show and episode in their name (two episodes once overwrote each other's `scene2.wav`).
- **Publishing**: public, Short plus full video, one episode every three hours, back off after a failed upload. A new YouTube channel has a daily upload limit until it is phone-verified.
- **Commercials**: never film a small object being picked up; one product picture used in every shot it appears in; a character's picture in every clip it is in; people and products drawn on plain backgrounds; no lettering; no brand names or logos. The full list is in `cinematic-commercial/README.md`.
- **The machine keeps its caches.** Takes are cached by line and direction. When a picture changes, move the old take files aside or the old clip is reused.

## When a pipeline changes

A pipeline's questions, steps and rules are in `skills/<pipeline>/SKILL.md` and `skills/<pipeline>/intake.json`. Change them there, not in the MCP server's text. If a tool's arguments change, change the matching `id` in `intake.json`. `docs/USING_FROM_A_UI.md` is the contract a UI relies on.

## Safety

- Never commit or print secrets. Tokens, the Fish Audio key and machine addresses live in `~/comfyui-mcp/connection.json` and `~/comfyui-mcp/swap_connection.json`; the YouTube session lives in `poster/social-auto-upload/cookies/`. `set_5090.py` reads the token from the clipboard and never echoes it. Keep it that way.
- Never commit `episodes/`, `media/`, `output/`, `swap/ready`, `swap/sent`, `swap/finished`, `node_modules/`, `.n8n/` (see `.gitignore`).
- Renting a GPU costs money and destroying one deletes its files. Ask the owner before either.
- Do not stop a running `make_episode.py` by pattern-killing; it takes the n8n step down with it. Use the pause file and let the episode finish.
- The swap pipeline may only be used on videos whose creators have agreed to it, or on the person's own video. `swap_one.py` and the `swap_prepare` tool refuse without that answer; do not add a default or a way round it. The picture swapped in must be of someone who agreed, or of a made-up character.

## Style

Small scripts, standard library first, one job per file, a docstring at the top that shows the command line. Comments say why. Messages meant for the owner are written in plain language without jargon.
