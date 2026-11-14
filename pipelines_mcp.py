# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""ONE MCP server for every pipeline in this repository.

    {"mcpServers": {"video-pipelines": {"command": "uv", "args": ["run", "/path/to/n8n-video-pipelines/pipelines_mcp.py"]}}}

An assistant (or a UI such as a workflow builder) that connects can:
  - list_pipelines()         what each pipeline makes and whether it can be run from here
  - start_pipeline(name)     that pipeline's skill (skills/<name>/SKILL.md) and the questions to ask the person first
  - then the pipeline's own tools: cartoon_*, commercial_*, educational_*, swap_*

Every pipeline's "what to ask and in what order" lives in skills/<name>/SKILL.md and skills/<name>/intake.json, not in
this file. A new pipeline is added by adding that folder and its tools here.
Slow steps run in the background: the tool returns at once and a *_status tool reports the result.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
ADS = Path(os.environ.get("ADS_HOME") or ROOT / "cinematic-commercial" / "ads")      # ADS_HOME / CARTOON_SHOWS: a UI gives each user their own folders
EPISODES = ROOT / "episodes"
SWAPS = Path(os.environ.get("SWAP_HOME") or ROOT / "swap" / "jobs")                       # SWAP_HOME: the same, for single swaps
sys.path.insert(0, str(ROOT / "cartoon"))
sys.path.insert(0, str(ROOT / "cinematic-commercial"))
import mcp_server as cartoon  # noqa: E402  (the cartoon pipeline's own server; its tools are re-used here)
import write_ad  # noqa: E402

UV = cartoon.UV
start_job, job_state, stop_job = cartoon._start, cartoon._state, cartoon._stop

INSTRUCTIONS = """This server runs several video pipelines. Each makes a different kind of video and needs different
things from the person.

ALWAYS work like this:
1. If it is not obvious which pipeline fits, call list_pipelines and choose with the person. "A cartoon", "an animated
   character" -> cartoon. "An ad", "a commercial", "a product film" -> cinematic-commercial. "An explainer",
   "a presenter video about ..." -> educational-presenter. "Put our presenter into this creator's video" -> person-swap.
   "Make this photo say this recording" -> talking-avatar.
2. Call start_pipeline(<name>) BEFORE any other tool of that pipeline. It returns the pipeline's skill and its
   "ask_first" questions.
3. ASK the person those questions, in plain words, in one short message. Skip the ones they already answered and the
   optional ones they clearly do not care about. Do not start making anything until the required ones are answered.
   For the cartoon pipeline that means: what is the character (describe it), its name, and whether they have a
   reference picture of it.
4. Follow the steps in the skill, with the tools it names, in its order. Show the person what was made at each
   checkpoint the skill names (the character sheet and its rules, the script, the pictures) before spending GPU time.
5. Slow tools return at once. Poll the pipeline's status tool, and tell the person roughly how long a step takes.
6. Report failures plainly, quoting the error. Never invent a result or a file."""

mcp = FastMCP("video-pipelines", instructions=INSTRUCTIONS)


def _pipelines() -> list[str]:
    return sorted(p.parent.name for p in SKILLS.glob("*/intake.json"))


def _intake(name: str) -> dict[str, Any]:
    if name not in _pipelines():
        raise ValueError(f"unknown pipeline \"{name}\"; the pipelines are: {', '.join(_pipelines())}")
    return json.loads((SKILLS / name / "intake.json").read_text())


@mcp.tool()
def list_pipelines() -> list[dict[str, Any]]:
    """Every pipeline: what it makes, and whether it can be run through this server ("full"), only partly
    ("partial") or only by hand for now ("by hand")."""
    out = []
    for name in _pipelines():
        d = _intake(name)
        text = (SKILLS / name / "SKILL.md").read_text()
        m = re.search(r'^description:\s*"?(.*?)"?\s*$', text, re.M)
        out.append({"pipeline": name, "title": d["title"], "makes": d["makes"], "use_when": m.group(1) if m else "",
                    "ready": d["ready"], "needs": d["needs"]})
    return out


@mcp.tool()
def start_pipeline(pipeline: str) -> dict[str, Any]:
    """Call this FIRST for a pipeline. Returns its skill (how to run it, its rules, its limits) and "ask_first":
    the questions to put to the person before anything is made. Each question has an id (the argument it fills),
    the wording, a kind (text, image, choice, number) and whether it is required.

    Args:
        pipeline: cartoon, cinematic-commercial, educational-presenter, person-swap or talking-avatar.
    """
    d = _intake(pipeline)
    skill = (SKILLS / pipeline / "SKILL.md").read_text().split("---", 2)[-1].strip()
    out = {"pipeline": pipeline, "ask_first": d["ask_first"], "steps": d.get("steps", []), "canvas": d.get("canvas", {}),
           "tools_in_order": d["tools_in_order"], "ready": d["ready"], "needs": d["needs"], "skill": skill}
    if pipeline == "cartoon":
        out["existing_shows"] = cartoon.list_shows()
    if pipeline == "cinematic-commercial":
        out["existing_commercials"] = commercial_list()
    if pipeline == "person-swap":
        out["existing_swaps"] = sorted(p.parent.name for p in SWAPS.glob("*/job.json"))
        out["gpu_connected"] = (Path.home() / "comfyui-mcp" / "swap_connection.json").exists()
    return out


# ---------------------------------------------------------------- cartoon: the cartoon server's tools, prefixed
for _fn in (cartoon.list_shows, cartoon.create_show, cartoon.get_show, cartoon.update_show, cartoon.write_episode,
            cartoon.get_episode, cartoon.save_episode, cartoon.run_step, cartoon.job_status):
    mcp.tool(name=f"cartoon_{_fn.__name__}")(_fn)


# ---------------------------------------------------------------- cinematic commercial
def _ad(name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""):
        raise ValueError('a commercial\'s name is lower-case letters, digits and dashes, for example "paper-fizz"')
    return ADS / name


@mcp.tool()
def commercial_list() -> list[dict[str, Any]]:
    """Every commercial that has a script: its name, the look, and whether it has been rendered and joined."""
    out = []
    for f in sorted(ADS.glob("*/spec.json")):
        d = json.loads(f.read_text())
        out.append({"name": f.parent.name, "look": str(d.get("style", ""))[:110], "clips_rendered": len(list((f.parent / "clips").glob("*.mp4"))),
                    "final": str(f.parent / "final.mp4") if (f.parent / "final.mp4").exists() else None})
    return out


@mcp.tool()
def commercial_write(name: str, product: str, art_style: str, idea: str = "", tagline: str = "",
                     product_image_path: str = "", hero_image_path: str = "", shape: str = "wide",
                     redo: bool = False) -> dict[str, Any]:
    """Have a model write a commercial's script: the look, the pictures to draw, and nine shots in three clips,
    ending on a clever way of showing the product. ASK the person for the product and the art style first.
    Runs in the background for about a minute: call commercial_status(name, "write").

    Args:
        name: Folder name, lower-case with dashes, for example "clay-toothbrush".
        product: What the product is and what it looks like. No brand names or logos unless the brand is theirs.
        art_style: For example "stop motion", "comic book", "black-and-white film noir", "paper craft".
        idea: The person's idea for the story or the ending, if they have one.
        tagline: The closing spoken line, two to five words, if they have one.
        product_image_path: Full path of the person's own picture of the product, if they have one.
        hero_image_path: Full path of a picture of the person's own character or avatar, to star in the commercial.
        shape: "wide" (16:9) or "tall" (9:16, for phones).
        redo: Write the script again, replacing the one that is there.
    """
    if shape not in ("wide", "tall"):
        raise ValueError('shape is "wide" or "tall"')
    folder = _ad(name)
    folder.mkdir(parents=True, exist_ok=True)
    cmd = ["python3", str(ROOT / "cinematic-commercial" / "write_ad.py"), name, "--product", product, "--style", art_style, "--shape", shape]
    for flag, value in (("--idea", idea), ("--tagline", tagline), ("--picture", product_image_path), ("--hero-picture", hero_image_path)):
        if value:
            cmd += [flag, value]
    return start_job(folder, "write", cmd + (["--redo"] if redo else []))


@mcp.tool()
def commercial_get(name: str) -> dict[str, Any]:
    """A commercial's script (look, pictures, the nine shots) and what has been made: the drawn pictures, the rendered
    clips, the frame sheets to look at, and the finished video."""
    folder = _ad(name)
    spec = json.loads((folder / "spec.json").read_text())
    prefix = spec["name"]
    return {"script": spec,
            "pictures_drawn": {k: str(folder / f"{prefix}_{k}.png") for k in spec["pictures"] if (folder / f"{prefix}_{k}.png").exists()},
            "pictures_strip": str(folder / "pictures.jpg") if (folder / "pictures.jpg").exists() else None,
            "clips": sorted(str(p) for p in (folder / "clips").glob("*.mp4")),
            "frame_sheets": sorted(str(p) for p in (folder / "clips").glob("*.jpg")),
            "final": str(folder / "final.mp4") if (folder / "final.mp4").exists() else None}


@mcp.tool()
def commercial_save(name: str, script: dict[str, Any]) -> dict[str, Any]:
    """Replace a commercial's script with an edited one (the whole object, as commercial_get returned it under
    "script"). It is checked first: clip lengths, camera names, every named picture attached in its clip.
    Pictures whose "draw" text changed are thrown away so the draw step makes them again."""
    folder = _ad(name)
    bad = write_ad.problems(script)
    if bad:
        return {"saved": False, "problems": bad}
    old = json.loads((folder / "spec.json").read_text()) if (folder / "spec.json").exists() else {}
    script["name"] = old.get("name") or re.sub(r"[^a-z0-9]", "", name)[:12]
    redraw = [k for k, p in script["pictures"].items() if (old.get("pictures") or {}).get(k, {}).get("draw") != p.get("draw")]
    for k in redraw:
        (folder / f"{script['name']}_{k}.png").unlink(missing_ok=True)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "spec.json").write_text(json.dumps(script, indent=1, ensure_ascii=False) + "\n")
    return {"saved": True, "pictures_to_redraw": redraw, "note": "run the build step again; clips already rendered are not changed"}


@mcp.tool()
def commercial_step(name: str, step: str) -> dict[str, Any]:
    """Run one step of making a commercial in the background. Order: draw, build, render, sheet, join.

    draw:   Codex draws the script's pictures (a few minutes, no GPU). Show the person pictures.jpg afterwards.
    build:  writes and checks one timeline per clip (seconds).
    render: films the three clips on the GPU, about 16 minutes each. Needs a connected GPU that has the director node.
    sheet:  twelve frames per clip on one sheet, to look at before joining.
    join:   final.mp4.
    Then call commercial_status(name, step).
    """
    folder = _ad(name)
    spec = folder / "spec.json"
    if not spec.exists():
        raise ValueError("this commercial has no script yet: call commercial_write first")
    kit = str(ROOT / "cinematic-commercial" / "adkit.py")
    cmds = {"draw": ["python3", kit, "draw", str(spec)], "build": ["python3", kit, "build", str(spec)],
            "render": [UV, "run", str(ROOT / "cinematic-commercial" / "render.py"), str(folder)],
            "sheet": ["python3", kit, "sheet", str(folder)], "join": ["python3", kit, "join", str(folder)]}
    if step not in cmds:
        raise ValueError("step is one of: draw, build, render, sheet, join")
    return start_job(folder, step, cmds[step])


@mcp.tool()
def commercial_status(name: str, job: str) -> dict[str, Any]:
    """Whether a commercial's background step is still running, and what it printed when it finished.
    job is "write", "draw", "build", "render", "sheet" or "join"."""
    folder = _ad(name)
    state = job_state(folder, job)
    if state.get("state") == "finished" and not isinstance(state.get("result"), dict):
        state["result"] = {"ok": False}
    log = folder / "_jobs" / f"{job}.log"
    if state.get("state") == "finished" and log.exists() and job in ("draw", "build", "sheet", "join"):
        lines = [l for l in log.read_text(errors="replace").splitlines() if l.strip()]     # these steps print plain lines, not JSON
        state["result"] = {"ok": not any(w in " ".join(lines) for w in ("FAILED", "Traceback", "Error", "error:")), "printed": lines[-12:]}
    return state


@mcp.tool()
def stop_step(pipeline: str, job: str, name: str = "", episode: str = "") -> dict[str, Any]:
    """Stop a background step the person no longer wants. What it already finished is kept.

    Args:
        pipeline: cartoon, cinematic-commercial, educational-presenter or person-swap.
        job: The step's job name, as given when it was started ("render", "shoot", "pictures" ...).
        name: The commercial's name, the show's name, or the educational episode's folder name.
        episode: For a cartoon episode step, the episode's name.
    """
    if pipeline == "cinematic-commercial":
        folder = _ad(name)
    elif pipeline == "cartoon":
        folder = cartoon.S.episode_dir(f"{name}/{episode}") if episode else cartoon._show_folder(name)
    elif pipeline == "educational-presenter":
        folder = EPISODES / name
    elif pipeline == "person-swap":
        folder = _swap(name) if name else ROOT / "swap"
    else:
        raise ValueError("this pipeline has no background steps")
    return stop_job(folder, job)


# ---------------------------------------------------------------- educational presenter
def _episode_folder(topic: str) -> Path:
    words = re.sub(r"[^a-z0-9 ]", "", topic.lower()).split()
    stop = {"why", "how", "the", "a", "an", "is", "are", "its", "their", "when", "that", "it", "of", "and", "in", "to", "by", "do", "does", "has", "have", "which"}
    slug = "-".join([w for w in words if w not in stop][:3]) or "episode"
    EPISODES.mkdir(exist_ok=True)
    folders = sorted(p for p in EPISODES.iterdir() if p.is_dir() and re.match(r"\d\d+-", p.name))
    for p in folders:
        if p.name.split("-", 1)[1] == slug:
            return p
    return EPISODES / f"{max([int(p.name.split('-')[0]) for p in folders] or [0]) + 1:02d}-{slug}"


@mcp.tool()
def educational_plan(topic: str, where: str = "") -> dict[str, Any]:
    """Plan one educational episode: the script is written from the director rulebook, every fact is checked, the lines
    are polished for the ear, and the presenter's start pictures are drawn and checked. ASK for the question first.
    Runs in the background for several minutes: call educational_status(episode).

    Args:
        topic: The one question the episode answers, for example "Why is the ocean salty?".
        where: Real, specific scenery to film in, if the person named some.
    """
    folder = _episode_folder(topic)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(json.dumps({"topic": topic, "where": where, "style": "short"}, indent=1))
    out = start_job(folder, "plan", ["python3", str(ROOT / "scripts" / "episode_job.py"), "plan", folder.name])
    return {**out, "episode": folder.name}


@mcp.tool()
def educational_shoot(episode: str) -> dict[str, Any]:
    """Film a planned episode on the GPU (voice first, each take checked for words, face and big mistakes), then sort
    it into ready or needs-a-look. Half an hour or more: call educational_status(episode)."""
    folder = EPISODES / episode
    if not (folder / "spec.json").exists():
        raise ValueError("this episode is not planned yet: call educational_plan and wait for it to finish")
    job = str(ROOT / "scripts" / "episode_job.py")
    return start_job(folder, "shoot", ["sh", "-c", f'python3 "{job}" shoot "{episode}"; python3 "{job}" finish "{episode}"'])


@mcp.tool()
def educational_status(episode: str = "") -> dict[str, Any]:
    """With an episode name: how its plan and shoot steps stand, its lines once planned, and its files once filmed.
    With no name: every episode folder and whether it is finished."""
    if not episode:
        EPISODES.mkdir(exist_ok=True)
        return {"episodes": [{"episode": p.name, "planned": (p / "spec.json").exists(), "filmed": (p / "result.json").exists()}
                             for p in sorted(EPISODES.iterdir()) if p.is_dir() and re.match(r"\d\d+-", p.name)]}
    folder = EPISODES / episode
    out: dict[str, Any] = {"episode": episode, "plan": job_state(folder, "plan"), "shoot": job_state(folder, "shoot")}
    if (folder / "spec.json").exists():
        spec = json.loads((folder / "spec.json").read_text())
        out["title"] = spec.get("title")
        out["lines"] = [t.get("line") for t in spec.get("takes", []) if t.get("line")]
    if (folder / "result.json").exists():
        fish = (json.loads((folder / "result.json").read_text()).get("fish") or {})
        out["video"] = {"wide": fish.get("wide"), "vertical": fish.get("vertical"), "flags": fish.get("flags") or [],
                        "status": "needs a person to look" if fish.get("flags") else "ready"}
    return out


# ---------------------------------------------------------------- person swap: one video, any person
def _swap(name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name or ""):
        raise ValueError('a swap\'s name is lower-case letters, digits, - and _, for example "bottle-remake"')
    return SWAPS / name


@mcp.tool()
def swap_prepare(name: str, video_path: str, person_image_path: str, rights: str, voice: str = "keep",
                 voice_id: str = "", force: bool = False) -> dict[str, Any]:
    """Get one video ready to be re-filmed with another person or character in it. ASK first: which video, whose
    picture, and whether they may use both. Checks that the video suits a swap (one person, face to camera and
    talking, no word-by-word captions, not an outfit video), cuts it to at most 20 seconds, and sets the voice.
    Runs in the background for a minute or two: call swap_job_status(name, "prepare").

    Args:
        name: Folder name for this swap, lower-case with dashes, for example "bottle-remake".
        video_path: Full path of the video on this computer.
        person_image_path: Full path of a picture of the person or character to put in the video.
        rights: "own" if the video is the person's own, "agreed" if its creator agreed to this. Anything else is refused:
                do not guess, ask. The picture must also be of someone who agreed, or of a made-up character.
        voice: "keep" leaves the original voice; "new" has a library voice say the same words at the same moments.
        voice_id: A Fish Audio voice id for "new" (the presenter's voice when empty).
        force: Try even though the check says the video is unlikely to swap well.
    """
    if rights not in ("own", "agreed"):
        raise ValueError('rights must be "own" (their own video) or "agreed" (its creator agreed). Ask the person; do not assume.')
    if voice not in ("keep", "new"):
        raise ValueError('voice is "keep" or "new"')
    folder = _swap(name)
    folder.mkdir(parents=True, exist_ok=True)
    cmd = ["python3", str(ROOT / "swap" / "swap_one.py"), "prepare", name, "--video", video_path, "--person", person_image_path,
           "--rights", rights, "--voice", voice] + (["--voice-id", voice_id] if voice_id else []) + (["--force"] if force else [])
    return start_job(folder, "prepare", cmd)


@mcp.tool()
def swap_run(name: str, step: str) -> dict[str, Any]:
    """Send a prepared swap to the GPU, or bring the finished one back. In the background.

    send:    uploads the clip and the person's picture; the GPU swaps it (about 40 seconds of work per second of video).
    collect: fetches the result as swapped.mp4, or says it is still swapping, or why it failed.
    Then call swap_job_status(name, step). Run collect again later if it is still swapping.
    """
    if step not in ("send", "collect"):
        raise ValueError("step is send or collect")
    return start_job(_swap(name), step, ["python3", str(ROOT / "swap" / "swap_one.py"), step, name])


@mcp.tool()
def swap_get(name: str) -> dict[str, Any]:
    """One swap: whether it is prepared, sent and finished, what the check said about the video, and the files
    (the prepared clip, the person's picture, the finished swap)."""
    folder = _swap(name)
    job = json.loads((folder / "job.json").read_text()) if (folder / "job.json").exists() else {}
    files = {k: str(folder / f) for k, f in (("source", "source.mp4"), ("person", "person.png"), ("swapped", "swapped.mp4")) if (folder / f).exists()}
    return {"name": name, "prepared": bool(job), "sent": (folder / "sent").exists(), "finished": (folder / "swapped.mp4").exists(),
            "seconds": job.get("seconds"), "size": job.get("size"), "voice": job.get("voice"), "check": job.get("screen"), "files": files,
            "gpu_connected": (Path.home() / "comfyui-mcp" / "swap_connection.json").exists()}


@mcp.tool()
def swap_job_status(name: str, job: str) -> dict[str, Any]:
    """Whether a swap's background step is still running, and its result. job is "prepare", "send" or "collect"."""
    return job_state(_swap(name), job)


# ---------------------------------------------------------------- person swap: batches from Kaiyros lists, with our presenter
@mcp.tool()
def swap_batch_step(step: str, source: str = "top", look_at: int = 20, keep: int = 5) -> dict[str, Any]:
    """The owner's batch version: picks creator videos from the Kaiyros lists and swaps in our own presenter.
    Only for videos whose creators have agreed. For one video the person supplies, use swap_prepare instead.

    prep:    pick and prepare clips from a list ("top", "trending" or "latest"), looking at `look_at` and keeping `keep`.
    send:    upload the prepared clips to the swap GPU.
    collect: bring finished swaps back.
    status:  how many are waiting, sent and finished.
    Then call swap_batch_status(step).
    """
    job = str(ROOT / "swap" / "swap_job.py")
    cmds = {"prep": ["python3", job, "prep", source, str(look_at), str(keep)], "send": ["python3", job, "send"],
            "collect": ["python3", job, "collect"], "status": ["python3", job, "status"]}
    if step not in cmds:
        raise ValueError("step is one of: prep, send, collect, status")
    if step == "prep" and source not in ("top", "trending", "latest"):
        raise ValueError("source is one of: top, trending, latest")
    return start_job(ROOT / "swap", step, cmds[step])


@mcp.tool()
def swap_batch_status(step: str) -> dict[str, Any]:
    """Whether a batch person-swap step is still running, and its result. step is prep, send, collect or status."""
    return job_state(ROOT / "swap", step)


if __name__ == "__main__":
    mcp.run()
