# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""MCP server for the cartoon pipeline: make a cartoon of ANY character from a chat.

Add it to an MCP client (Claude Desktop, Claude Code, Codex ...):

    {"mcpServers": {"cartoon": {"command": "uv", "args": ["run", "/path/to/n8n-video-pipelines/cartoon/mcp_server.py"]}}}

The assistant that connects is told (see INSTRUCTIONS) to begin by asking what character the person wants, then to
call create_show, show the person the character sheet and the rules, and only then write and film an episode.
Slow steps run in the background: a tool that starts one returns at once, and job_status says when it is done.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import show as S  # noqa: E402

UV = os.environ.get("UV_BIN", str(Path.home() / ".local/bin/uv"))
PATH = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

INSTRUCTIONS = """This server makes short cartoons starring any character, a few seconds per scene, with the character
speaking each line. One character is a "show"; a show has episodes.

When someone wants a cartoon, do this in order.

1. ASK FIRST, before calling anything, unless they already told you:
   - What is the character? Ask them to describe it: what kind of creature or thing, shape, colours, face, what it
     wears, anything that makes it special.
   - Its name.
   - Do they have a picture of it? If so, the full path of the image file on this computer. (Optional. Without
     one, the character is drawn from their description.)
   - What kind of cartoon is it, and where does it happen? (Optional. Sensible ones are chosen if they do not say.)
   - Who is it for? (Small children by default; that turns on the safety rules.)
   Call list_shows first if they might mean a character that already exists.
2. Call create_show. It draws or takes the character sheet, then a model looks at that picture and writes the
   show's rules: the exact look, the art style, the place, and the keep-in-line rules that stop the video model
   from adding limbs, tails or copies, moving marks, changing clothes or adding text. It takes two to four minutes:
   poll job_status.
3. Show the person the character sheet (get_show returns its path) and read them the character description and the
   rules in plain words. Ask if anything is wrong. Fix it with update_show (for example: "three buttons, not four").
   Do not go on until they are happy: every picture and clip of this show will follow these rules.
4. Ask what the episode is about, then call write_episode (about a minute). Read the lines back with get_episode.
   Change scenes with save_episode if they want something different.
5. Film it with run_step, one step at a time, in this order: "pictures", "voice", "shoot", "finish". Check
   job_status between steps. "shoot" needs the GPU and takes several minutes per scene; say so before starting.
   After "pictures", offer to show the start pictures before spending GPU time.
6. When "finish" is done, give them the path of final.mp4 (wide) and short.mp4 (vertical).

Say plainly when something failed, and quote the error the tool returned. Never invent a result."""

mcp = FastMCP("cartoon", instructions=INSTRUCTIONS)
PROCS: dict[int, subprocess.Popen] = {}                 # steps this server started, so a finished one is seen as finished


def _jobs(folder: Path) -> Path:
    d = folder / "_jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _alive(pid: int) -> bool:
    if pid in PROCS:
        return PROCS[pid].poll() is None
    try:
        os.kill(pid, 0)                                      # a step started by an earlier run of the server
        return True
    except OSError:
        return False


def _start(folder: Path, job: str, cmd: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    """Run a step in the background. Its output goes to _jobs/<job>.log; its last line is the step's JSON result."""
    jobs = _jobs(folder)
    pid_file, log = jobs / f"{job}.pid", jobs / f"{job}.log"
    if pid_file.exists():
        try:
            if _alive(int(pid_file.read_text())):
                return {"started": False, "job": job, "why": "this step is already running; check its status"}
        except ValueError:
            pass
    p = subprocess.Popen(cmd, cwd=HERE, stdin=subprocess.DEVNULL, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                         env={**os.environ, "PATH": PATH, **(env or {})}, start_new_session=True)
    PROCS[p.pid] = p
    pid_file.write_text(str(p.pid))
    (jobs / f"{job}.started").write_text(str(time.time()))
    return {"started": True, "job": job, "next": "check this step with the pipeline's status tool, giving this job name"}


def _state(folder: Path, job: str) -> dict[str, Any]:
    jobs = _jobs(folder)
    pid_file, log = jobs / f"{job}.pid", jobs / f"{job}.log"
    if not pid_file.exists():
        return {"job": job, "state": "never started"}
    try:
        running = _alive(int(pid_file.read_text()))
    except ValueError:
        running = False
    started = float((jobs / f"{job}.started").read_text()) if (jobs / f"{job}.started").exists() else time.time()
    lines = [l for l in (log.read_text(errors="replace").splitlines() if log.exists() else []) if l.strip()]
    out: dict[str, Any] = {"job": job, "state": "running" if running else "finished", "minutes": round((time.time() - started) / 60, 1)}
    if not running:
        for line in reversed(lines):
            if line.lstrip().startswith("{"):
                try:
                    out["result"] = json.loads(line)
                    break
                except ValueError:
                    continue
        if "result" not in out:
            out["result"] = {"ok": False, "error": "the step ended without a result", "last_lines": lines[-5:]}
    else:
        out["last_line"] = lines[-1][:200] if lines else ""
    return out


def _show_folder(show: str) -> Path:
    if S.slug(show) != show or not show:
        raise ValueError('a show name is lower-case letters, digits and dashes, for example "pip"')
    return S.SHOWS / show


@mcp.tool()
def list_shows() -> list[dict[str, Any]]:
    """Every cartoon show that exists: its folder name, the character's name, what kind of cartoon it is, and its episodes."""
    out = []
    for f in sorted(S.SHOWS.glob("*/show.json")):
        d = json.loads(f.read_text())
        eps = sorted(e.parent.name for e in f.parent.glob("*/script.json"))
        out.append({"show": f.parent.name, "name": d.get("name"), "what": d.get("what"), "episodes": eps})
    return out


@mcp.tool()
def create_show(show: str, name: str, description: str, kind_of_cartoon: str = "", place: str = "",
                reference_image_path: str = "", audience: str = "small children", redo: bool = False) -> dict[str, Any]:
    """Start a new cartoon show for one character. ASK the person for the character's description and name first.

    Draws the character sheet (or uses the person's picture), then a model looks at it and writes the show's rules:
    the exact look, the art style, the place, what must stay the same, and the keep-in-line rules for pictures and
    clips. Runs in the background for two to four minutes: call job_status(show, job="create_show").

    Args:
        show: Folder name for the show, lower-case with dashes, for example "pip" or "captain-carrot".
        name: The character's name as it should be spoken and written.
        description: The person's own description of the character, as complete as they gave it.
        kind_of_cartoon: For example "children's counting cartoon". Leave empty to have one chosen.
        place: Where every scene happens. Leave empty to have a simple one invented.
        reference_image_path: Full path of a picture of the character on this computer, if the person has one.
        audience: Who watches. "small children" turns on the no-knives, no-flame rules.
        redo: Write the rules again for a show that already exists (the character sheet is kept unless a new picture is given).
    """
    folder = _show_folder(show)
    cmd = [UV, "run", "new_show.py", show, "--name", name, "--describe", description, "--audience", audience]
    for flag, value in (("--what", kind_of_cartoon), ("--place", place), ("--picture", reference_image_path)):
        if value:
            cmd += [flag, value]
    if redo:
        cmd.append("--redo")
    return _start(folder, "create_show", cmd)


@mcp.tool()
def get_show(show: str) -> dict[str, Any]:
    """A show's character description, style, place, rules and voice, plus the path of its character sheet picture."""
    folder = _show_folder(show)
    d = json.loads((folder / "show.json").read_text())
    return {**d, "character_sheet": str(folder / "character_sheet.png"),
            "episodes": sorted(e.parent.name for e in folder.glob("*/script.json"))}


@mcp.tool()
def update_show(show: str, field: str, value: str) -> dict[str, Any]:
    """Correct one part of a show after the person has read it.

    Args:
        show: The show's folder name.
        field: One of: name, what, character, style, place, place_word, keep_same, picture_rules, clip_rules,
               voice_id (a Fish Audio voice id), voice_tone (three adjectives), voice_speed (0.7 to 1.2).
        value: The complete new text for that field (not just the changed words).
    """
    folder = _show_folder(show)
    path = folder / "show.json"
    d = json.loads(path.read_text())
    if field in ("name", "what", "character", "style", "place", "place_word", "keep_same", "picture_rules", "clip_rules"):
        if not value.strip():
            raise ValueError(f"{field} cannot be empty")
        d[field] = value.strip()
    elif field == "voice_id":
        d.setdefault("voice", {})["id"] = value.strip()
    elif field == "voice_tone":
        d.setdefault("voice", {})["tone"] = f"({value.strip().strip('()')}) "
    elif field == "voice_speed":
        d.setdefault("voice", {})["speed"] = max(0.7, min(float(value), 1.2))
    else:
        raise ValueError(f"unknown field {field}")
    path.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return {"saved": True, "field": field, "note": "pictures and clips made from now on use the new text; ones already made are not changed"}


@mcp.tool()
def write_episode(show: str, episode: str, idea: str, scenes: int = 5, redo: bool = False) -> dict[str, Any]:
    """Have a model write an episode's script (what the character says, the start picture and the action of every scene).
    Runs in the background for about a minute: call job_status(show, job="write_episode", episode=episode).

    Args:
        show: The show's folder name.
        episode: Folder name for the episode, lower-case with underscores or dashes, for example "five_apples".
        idea: One or two sentences: what happens in this episode.
        scenes: How many scenes, 2 to 10. Each is a few seconds.
        redo: Write the script again, replacing the one that is there.
    """
    ep = S.episode_dir(f"{show}/{episode}")
    cmd = ["python3", "write_episode.py", f"{show}/{episode}", idea, "--scenes", str(scenes)] + (["--redo"] if redo else [])
    ep.mkdir(parents=True, exist_ok=True)
    return _start(ep, "write_episode", cmd)


@mcp.tool()
def get_episode(show: str, episode: str) -> dict[str, Any]:
    """An episode's script and what has been made of it so far (pictures, voice, clips, final video)."""
    ep = S.episode_dir(f"{show}/{episode}")
    script = json.loads((ep / "script.json").read_text())
    ns = [s["n"] for s in script]
    return {"script": script,
            "pictures": {n: str(ep / "pictures" / f"scene{n}_1344x768.png") for n in ns if (ep / "pictures" / f"scene{n}_1344x768.png").exists()},
            "voice": [n for n in ns if (ep / "voice" / f"scene{n}.wav").exists()],
            "clips": json.loads((ep / "best.json").read_text()) if (ep / "best.json").exists() else {},
            "final": str(ep / "final.mp4") if (ep / "final.mp4").exists() else None,
            "short": str(ep / "short.mp4") if (ep / "short.mp4").exists() else None}


@mcp.tool()
def save_episode(show: str, episode: str, script: list[dict[str, Any]]) -> dict[str, Any]:
    """Replace an episode's script with an edited one. Each scene needs "says", "picture" and "does".
    Start pictures of scenes whose "picture" text changed are thrown away here; run the pictures step again to redraw them."""
    ep = S.episode_dir(f"{show}/{episode}")
    S.load_show(ep.parent)
    clean = []
    for i, s in enumerate(script, 1):
        if not all(str(s.get(k) or "").strip() for k in ("says", "picture", "does")):
            raise ValueError(f"scene {i} needs says, picture and does")
        clean.append({"n": i, "says": str(s["says"]).strip(), "picture": str(s["picture"]).strip(), "does": str(s["does"]).strip()})
    ep.mkdir(parents=True, exist_ok=True)
    old = json.loads((ep / "script.json").read_text()) if (ep / "script.json").exists() else []
    changed = [s["n"] for s in clean if s["n"] > len(old) or old[s["n"] - 1].get("picture") != s["picture"]]
    for n in changed:                                        # a picture that no longer matches its text is drawn again
        (ep / "pictures" / f"scene{n}_1344x768.png").unlink(missing_ok=True)
    (ep / "script.json").write_text(json.dumps(clean, indent=1, ensure_ascii=False) + "\n")
    return {"saved": True, "scenes": len(clean), "pictures_to_redraw": changed}


@mcp.tool()
def run_step(show: str, episode: str, step: str) -> dict[str, Any]:
    """Run one step of filming an episode in the background. Order: pictures, voice, shoot, finish.

    pictures: a start picture per scene, drawn from the character sheet (a few minutes, no GPU).
    voice:    the character speaks every line (about a minute, needs the Fish Audio key).
    shoot:    one clip per scene on the GPU, up to four tries each until the words match (several minutes per scene).
    finish:   joins the best takes into final.mp4 and a vertical short.mp4.
    Then call job_status(show, job=step, episode=episode).
    """
    if step not in ("pictures", "voice", "shoot", "finish"):
        raise ValueError("step is one of: pictures, voice, shoot, finish")
    ep = S.episode_dir(f"{show}/{episode}")
    if not (ep / "script.json").exists():
        raise ValueError("this episode has no script yet: call write_episode or save_episode first")
    return _start(ep, step, ["python3", "cartoon_job.py", step, f"{show}/{episode}"])


@mcp.tool()
def job_status(show: str, job: str, episode: str = "") -> dict[str, Any]:
    """Whether a background step is still running, and its result when it has finished.

    Args:
        show: The show's folder name.
        job: "create_show", "write_episode", "pictures", "voice", "shoot" or "finish".
        episode: The episode's folder name, for every job except create_show.
    """
    folder = S.episode_dir(f"{show}/{episode}") if episode else _show_folder(show)
    return _state(folder, job)


if __name__ == "__main__":
    mcp.run()
