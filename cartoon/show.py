"""What a cartoon show is, and the two prompts built from it. Every other script in this folder reads the show
through this file, so nothing else names a character.

A show is a folder in shows/:

    shows/<show>/show.json              who the character is, the look, the place, the rules that keep it in line, the voice
    shows/<show>/character_sheet.png    one picture of the character; every start picture descends from it
    shows/<show>/<episode>/script.json  one entry per scene: says, picture, does

An episode is addressed as "<show>/<episode>", for example "mango/omelet".

show.json:
    name           the character's name, as written in the scripts
    what           the kind of cartoon in a few words ("children's cooking cartoon")
    character      what the character looks like, exactly
    style          the art style
    place          where every scene happens, in one sentence
    place_word     one word for that place ("kitchen")
    keep_same      what must stay identical from picture to picture
    picture_rules  what a start picture must and must not show (counts of limbs, nothing dangerous, no text)
    clip_rules     the same for the moving clip (the character keeps its shape, no extra limbs, same place and light)
    picture_extra  optional extra sentence for start pictures
    voice          {"id": Fish Audio voice id, "speed": 0.9, "tone": "(cheerful, warm, friendly) "}

new_show.py writes show.json from a description and a picture; edit it by hand afterwards if a rule is wrong.
"""
import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOWS = HERE / "shows"
CODEX = os.environ.get("CODEX_BIN", "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")
DEFAULT_VOICE = {"id": "44a7a443f7404ef6b8565022b150d2ed", "name": "Kids (Fish library): young, cheerful, clear",
                 "speed": 0.9, "tone": "(cheerful, warm, friendly) "}
NEEDED = ("name", "what", "character", "style", "place", "keep_same", "picture_rules", "clip_rules")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def episode_dir(episode: str) -> Path:
    """shows/<show>/<episode> for "show/episode". Refuses anything that would leave shows/."""
    parts = episode.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[a-z0-9][a-z0-9_-]*", p) for p in parts):
        raise ValueError(f'an episode is written "<show>/<episode>" in lower-case letters, digits, - and _ (got "{episode}")')
    return SHOWS / parts[0] / parts[1]


def load_show(folder: Path) -> dict:
    """The show a folder belongs to: `folder` is the show folder itself or one of its episodes."""
    for f in (folder, folder.parent):
        if (f / "show.json").exists():
            show = json.loads((f / "show.json").read_text())
            missing = [k for k in NEEDED if not str(show.get(k) or "").strip()]
            if missing:
                raise ValueError(f"{f / 'show.json'} is missing: {', '.join(missing)}")
            show["folder"] = f
            show["sheet"] = f / "character_sheet.png"
            show["voice"] = {**DEFAULT_VOICE, **(show.get("voice") or {})}
            show.setdefault("place_word", "place")
            return show
    raise FileNotFoundError(f"no show.json in {folder} or {folder.parent}")


def picture_prompt(show: dict, scene: dict) -> str:
    """What Codex is told when it draws a scene's start picture from the previous picture."""
    n, name = scene["n"], show["name"]
    return f"""Use your image generation tool to make ONE new landscape 16:9 image that is another shot of the same {show['what']} as the attached image. Keep EVERYTHING identical to the attached image except what is described as changed: {show['keep_same']}, the same camera position, the same art style and rendering. {show.get('picture_extra', '')}

The character: {show['character']}

What this shot shows: {scene['picture']} {name} faces the camera, eyes on the camera, mouth slightly open as if about to speak. {show['picture_rules']}

Art style: {show['style']}

Save the image as scene{n}.png in the current directory. Reply with just the file path."""


def clip_rules(show: dict) -> str:
    return (f"One continuous take, camera locked off, no cuts, no zoom. {show['clip_rules']} "
            f"{show['name']} says the line exactly once and adds no word after the last one. No text on screen, no captions, no music.")


def clip_prompt(show: dict, scene: dict) -> str:
    """What the video model is told for one scene."""
    name = show["name"]
    return (f"SCENE: A {show['what']}. {scene['picture']} {show['place']}, exactly as in the first frame. "
            f"{name}'s eyes are on the camera. {scene['does']} "
            f"LINE: {name} speaks these exact words, the mouth matching the voice on the soundtrack: \"{scene['says']}\" "
            f"STYLE: {show['style']} RULES: {clip_rules(show)} Same character and {show['place_word']} as the first frame.")


def ask_claude(prompt: str, folder: Path, model: str = "sonnet", timeout: int = 600) -> dict:
    """One question to the `claude` command-line tool, answered as a JSON object. It may read files in `folder`
    (that is how it looks at a picture)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_"))}
    env["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    r = subprocess.run(["claude", "-p", prompt, "--model", model, "--output-format", "json", "--allowedTools", "Read",
                        "--setting-sources", "", "--strict-mcp-config"], capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL, cwd=folder, env=env)
    try:
        reply = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError(f"claude failed: {(r.stderr or r.stdout).strip()[-300:]}")
    text = reply.get("result", "")
    if r.returncode or reply.get("is_error"):
        raise RuntimeError(f"claude failed: {text[:300]}")
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    if not m:
        raise RuntimeError(f"claude gave no JSON: {text[:200]}")
    return json.loads(m.group(0))
