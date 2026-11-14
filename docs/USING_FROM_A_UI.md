# Using the pipelines from a chat or a UI

One MCP server, [`pipelines_mcp.py`](../pipelines_mcp.py), covers every pipeline. A chat assistant
or a workflow UI connects to it once and can offer all of them.

```json
{"mcpServers": {"video-pipelines": {"command": "uv", "args": ["run", "/path/to/n8n-video-pipelines/pipelines_mcp.py"]}}}
```

## The idea

Each pipeline needs different things from the person. A cartoon needs a character; a commercial
needs a product and a look; an explainer needs a question. That knowledge does not live in the UI
and does not live in the server's code. It lives in one folder per pipeline:

```
skills/<pipeline>/SKILL.md      what the pipeline makes, what to ask first, the steps and their tools, the rules, the limits
skills/<pipeline>/intake.json   the same "ask first" questions as data, so a UI can draw a form
```

The server hands both out. Whoever is driving (a model in a chat, or a UI) asks the questions, then
calls the tools the skill names, in its order.

## Three calls every client makes

| Call | Returns |
|---|---|
| `list_pipelines()` | every pipeline: `pipeline`, `title`, `makes`, `use_when`, `ready` (`full`, `partial`, `by hand`), `needs` |
| `start_pipeline(pipeline)` | `skill` (the text of SKILL.md), `ask_first` (the questions), `tools_in_order`, and what already exists (shows, commercials) |
| the pipeline's status tool | whether a background step is running, and its result |

The server's own instructions tell a connecting model to call `start_pipeline` before any other
tool of a pipeline and to ask the `ask_first` questions before making anything. For the cartoon
pipeline that means: what is the character, its name, and is there a reference picture.

## A question, as data

```json
{"id": "reference_image_path",
 "ask": "Do you have a picture of it? (optional; one is drawn from your description if not)",
 "kind": "image",
 "required": false}
```

- `id` is the name of the tool argument the answer fills.
- `kind` is `text`, `image`, `choice`, `choice_or_text`, `number` or `audio_or_text`. A `choice` has `options` and may have a `default`.
- `when`, if present, says the question belongs to a later moment ("after the character is approved").
- An `image` answer is the full path of a file on the machine the server runs on.

A UI can show these as a form. A chat assistant asks them in words.

## The pipelines and their tools

| Pipeline | Ready | Tools |
|---|---|---|
| `cartoon` | full | `cartoon_create_show`, `cartoon_get_show`, `cartoon_update_show`, `cartoon_write_episode`, `cartoon_get_episode`, `cartoon_save_episode`, `cartoon_run_step`, `cartoon_job_status`, `cartoon_list_shows` |
| `cinematic-commercial` | full | `commercial_write`, `commercial_get`, `commercial_save`, `commercial_step` (`draw`, `build`, `render`, `sheet`, `join`), `commercial_status`, `commercial_list` |
| `educational-presenter` | partial: no publishing | `educational_plan`, `educational_shoot`, `educational_status` |
| `person-swap` | partial: needs the swap GPU connected | `swap_step` (`prep`, `send`, `collect`, `status`), `swap_status` |
| `talking-avatar` | by hand | none yet; the skill says how it is run |

## Steps, as data (for a node canvas)

`start_pipeline` also returns `steps` and `canvas`, so a workflow UI can draw a pipeline without
knowing it in advance.

```json
{"id": "film", "title": "Film it", "tool": "commercial_step", "args": {"step": "render"}, "job": "render",
 "minutes": 50, "gpu": true, "video_seconds": 30, "approve": false,
 "say": "Three clips of about ten seconds, around 16 minutes each."}
```

- `tool` and `args` are what to call; `job` is the name to give the status tool and `stop_step`.
- `minutes` is roughly how long it takes; `gpu` says whether it costs GPU time; `video_seconds` is what a price can be worked out from.
- `show` names the thing to put in front of the person when the step ends (`script`, `pictures_strip`, `frame_sheets`, `final`, `character_sheet`); the pipeline's `get` tool returns it.
- `approve: true` means: stop here and let the person look before going on.

`canvas` says which node of a "subject, on camera, what to make, script, film, final" workflow
supplies each answer and runs each step. For the cinematic commercial:

| Canvas node | Supplies | Runs |
|---|---|---|
| The subject | the product and its picture | |
| On camera (optional) | the person's own character or avatar, to star in it | |
| What to make: "Commercial" | the art style, wide or tall | |
| The script | story idea, closing line | write the script, draw the pictures |
| Film it | | prepare the shots, film, frame sheets to look over |
| Final video | | join |

Made for that use:

- **Tall videos.** `shape: "tall"` gives 9:16 (768x1344) for phones; `wide` is 16:9.
- **The person's own pictures.** A product picture and a character picture can both be handed in; only what is missing is drawn.
- **A folder per user.** Start the server with `ADS_HOME` and `CARTOON_SHOWS` set to that user's folders. Nothing is shared between users and the repository's own examples stay out of their list.
- **A stop button.** `stop_step(pipeline, job, name)` ends a running step and keeps what it finished.

<img src="media/commercial_own_pictures.jpg" width="420" alt="A user's own character, their own product photo, and the ending the pipeline drew from them">

*Tested this way: a character picture and a product photo handed in, tall shape. The pipeline wrote the script, kept both pictures, and drew only the ending (right): the character inside a world that is the product.*

## How slow steps work

Drawing, writing and filming take from a minute to an hour. A tool that starts one returns at once:

```json
{"started": true, "job": "render", "next": "check this step with the pipeline's status tool, giving this job name"}
```

and the status tool answers `{"state": "running", "minutes": 3.2, "last_line": "..."}` until it is
`{"state": "finished", "result": {"ok": true, ...}}`. A UI polls every few seconds and shows the
`last_line`; a chat assistant tells the person roughly how long the step takes and checks back.

Every step can be started again safely: it only does what is still missing.

## Checkpoints: show before spending

The skills name the moments to stop and show the person something, because GPU time is the
expensive part:

- cartoon: the character sheet and its rules, then the script, then the start pictures;
- commercial: the nine shots, then the drawn pictures, then the frame sheets before joining;
- educational: the lines after planning.

## What the machine needs

`uv`, `ffmpeg`, the Codex command-line program (pictures), the `claude` command-line tool signed in
(rules and scripts), a Fish Audio key and a connected GPU ([`RUNBOOK.md`](RUNBOOK.md)). Without a
GPU, everything up to and including pictures still works; the filming steps say that no GPU is
connected.

## Adding a pipeline

1. `skills/<name>/SKILL.md` with `name` and `description` at the top, and the sections: Ask first, Steps, rules, Limits.
2. `skills/<name>/intake.json`: `pipeline`, `title`, `makes`, `ready`, `needs`, `ask_first`, `tools_in_order`.
3. Its tools in `pipelines_mcp.py`, each prefixed with the pipeline's short name. Slow ones go through `start_job`.

`list_pipelines` and `start_pipeline` pick the new folder up by themselves.
