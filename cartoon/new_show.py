# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Start a new cartoon show from a description of its character, and optionally a picture of it.

    uv run new_show.py <show> --name "Pip" --describe "a small round blue robot with one antenna who loves counting"
                              [--what "children's counting cartoon"] [--place "a sunny playroom with a low table"]
                              [--picture /path/to/reference.png] [--audience "small children"] [--redo]

What it does:
  1. character sheet   your picture if you gave one, otherwise Codex draws the character from the description
  2. the rules         a model LOOKS at that sheet, reads the description, and writes show.json: the exact look of
                       the character, the art style, the place, what must stay the same from picture to picture,
                       and the keep-in-line rules for pictures and clips (how many arms, legs, tails, ears, wheels
                       or wings it has, which marks sit on which side, what it wears, what must never appear)
  3. the voice         a matching voice is looked up in the Fish Audio library (the default kids' voice if that fails)

Prints ONE JSON line and always exits 0. Read shows/<show>/show.json afterwards and correct any rule by hand:
those rules go into every picture and every clip of the show.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import show as S  # noqa: E402

DESIGN = """You are setting up a cartoon show for an automatic pipeline. An image model will draw a start picture for every
scene and a video model will animate it. Both make the same mistakes again and again unless they are told exactly what
the character is: they add a third arm, a second tail, a second copy of the character, they move a mark to the other
side, change the clothes, add text. Your job is to look at the character and write the description and the rules that
stop this.

Read the picture character_sheet.png in the current folder with the Read tool. That picture is the character: where it
and the person's words disagree about looks, the picture wins.

The person's words about the character: {describe}
The character's name: {name}
The kind of cartoon they want: {what}
Where it happens: {place}
Who watches it: {audience}

Answer with ONLY one JSON object, no markdown fence, with exactly these keys:
{{
 "what": "the kind of cartoon in three to six words, lower case, for example: children's cooking cartoon",
 "character": "One paragraph of 80 to 130 words that would let an artist who has never seen the picture redraw this exact character: what kind of thing it is, body shape and proportions, every colour and where it is, face (eyes, nose, mouth, ears), limbs, tail or wheels or wings, any mark that makes it THIS character and which side it is on, and everything it wears. Use the name. State what is absent when a model would likely add it (NO stripes, no claws, no fingers).",
 "style": "One sentence of 30 to 50 words naming the art style of the picture (medium, shapes, surfaces, lighting, colours), ending with: fully animated cartoon, not a photograph, no text, no letters, no logos anywhere.",
 "place": "One sentence: the single fixed place every scene happens in, with three or four things that are always there and where they are. Use the person's place if they gave one; otherwise invent a simple bright one that suits the cartoon.",
 "place_word": "one word for that place",
 "keep_same": "One sentence in the form: the same <kind> character (same <five to eight features that identify it, in a comma list>), the same <place with its wall or ground colour>, the same <fixed thing and where>, the same <fixed thing and where>",
 "picture_rules": "Rules for one still picture, 25 to 50 words. Start with: Exactly one <kind>, then the exact count of each body part a model tends to multiply or drop for THIS character (arms, legs, hands or paws, tails, ears, eyes, wings, wheels, antennae, horns). Then: Every listed object and the <hand, paw, claw ...> doing the action are fully visible and not hidden by anything. Then what must never appear, ending with: no text.",
 "clip_rules": "Rules for the moving clip, 40 to 70 words. Start with: Exactly one <kind>. Then: {name} keeps exactly the <the features and clothes that must not change> of the first frame. Then the counts again with: no extra limbs. Then one sentence fixing the place, the time of day and the light: the same <...> in every frame.",
 "voice_search": "two to four words to search a voice library for this character's voice, for example: cheerful young child",
 "voice_tone": "three adjectives for how every line is spoken, for example: cheerful, warm, friendly",
 "note": "one sentence for the person: anything in the picture that is likely to be hard to keep the same"
}}

If the audience is children, the rules must also keep out anything unsafe to copy: no knives, no flame, no fire, no smoke.
Write plain English. Do not mention pictures, files or these instructions in the values."""


def say(**out):
    print(json.dumps(out, ensure_ascii=False))


def draw_sheet(folder: Path, name: str, describe: str, what: str) -> None:
    work = folder / "_sheet"
    work.mkdir(parents=True, exist_ok=True)
    prompt = (f"Use your image generation tool to make one picture, then save it in the current folder as character_sheet.png "
              f"(PNG, landscape 16:9, about 1536x864). Do nothing else, and do not write any other files.\n\n"
              f"PICTURE: A character sheet for a {what or 'cartoon'}. Exactly ONE character, drawn once, full body from head to "
              f"foot, standing, front view facing the viewer, friendly neutral pose with arms relaxed, on a plain flat pale "
              f"background with nothing else in the picture. The character, named {name}: {describe}\n\n"
              f"Fully animated cartoon style, clean simple shapes, not a photograph. No text, no letters, no labels, no logos.")
    subprocess.run([S.CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(work)],
                   input=prompt, capture_output=True, text=True, timeout=420)
    if not (work / "character_sheet.png").exists():
        raise RuntimeError("Codex did not draw the character sheet")
    shutil.move(work / "character_sheet.png", folder / "character_sheet.png")
    shutil.rmtree(work, ignore_errors=True)


def find_voice(words: str) -> dict | None:
    try:
        sys.path.insert(0, str(Path.home() / "comfyui-mcp"))
        import server
        found = server.fish_voices(query=words, limit=5, language="en")
        if found and found[0].get("reference_id"):
            return {"id": found[0]["reference_id"], "name": f"{found[0].get('title') or words} (Fish library, found with: {words})",
                    "sample": found[0].get("sample_url")}
    except Exception:
        pass
    return None


def main():
    a = argparse.ArgumentParser()
    a.add_argument("show"); a.add_argument("--name", required=True); a.add_argument("--describe", required=True)
    a.add_argument("--what", default=""); a.add_argument("--place", default=""); a.add_argument("--picture", default="")
    a.add_argument("--audience", default="small children"); a.add_argument("--redo", action="store_true")
    o = a.parse_args()
    if S.slug(o.show) != o.show:
        return say(ok=False, error=f'the show folder name must be lower-case letters, digits and dashes, for example "{S.slug(o.show) or "pip"}"')
    folder = S.SHOWS / o.show
    if (folder / "show.json").exists() and not o.redo:
        return say(ok=False, error=f"shows/{o.show} already exists. Add --redo to write its show.json again (the character sheet is kept).")
    folder.mkdir(parents=True, exist_ok=True)
    sheet = folder / "character_sheet.png"
    if o.picture:
        src = Path(o.picture).expanduser()
        if not src.exists():
            return say(ok=False, error=f"no picture at {src}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale='min(1536,iw)':-2", str(sheet)], timeout=120)
    elif not sheet.exists():
        draw_sheet(folder, o.name, o.describe, o.what)
    if not sheet.exists():
        return say(ok=False, error="there is no character sheet to look at")
    d = S.ask_claude(DESIGN.format(describe=o.describe, name=o.name, what=o.what or "(not said: choose what suits the character)",
                                   place=o.place or "(not said: invent one)", audience=o.audience), folder, "opus")
    voice = find_voice(str(d.get("voice_search") or "")) or dict(S.DEFAULT_VOICE)
    tone = ", ".join(w.strip() for w in str(d.get("voice_tone") or "cheerful, warm, friendly").split(",")[:3])
    show = {"name": o.name, **{k: str(d.get(k) or "").strip() for k in ("what", "character", "style", "place", "place_word", "keep_same", "picture_rules", "clip_rules")},
            "voice": {"id": voice["id"], "name": voice.get("name", ""), "speed": 0.9, "tone": f"({tone}) "},
            "audience": o.audience, "described_as": o.describe}
    missing = [k for k in S.NEEDED if not show.get(k)]
    if missing:
        return say(ok=False, error=f"the design came back without: {', '.join(missing)}")
    (folder / "show.json").write_text(json.dumps(show, indent=1, ensure_ascii=False) + "\n")
    say(ok=True, show=o.show, folder=str(folder), character_sheet=str(sheet), note=d.get("note"), voice_sample=voice.get("sample"),
        **{k: show[k] for k in ("what", "character", "style", "place", "keep_same", "picture_rules", "clip_rules")}, voice=show["voice"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        say(ok=False, error=f"{type(e).__name__}: {e}"[:400])
