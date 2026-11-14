"""Write a commercial's script file (ads/<name>/spec.json) from a product, an art style and an idea.

    python3 write_ad.py <name> --product "a tall slim mint-green can of sparkling water" --style "handmade paper craft"
                        [--idea "a dry paper desert comes alive when the can opens"] [--tagline "Open something."]
                        [--picture /path/to/product.png] [--redo]

A model writes the look, the pictures to draw and three clips of three shots, following the rules in README.md.
The result is checked (clip lengths, camera names, every named picture attached in its clip) before it is saved.
Prints ONE JSON line and always exits 0. Read the script before drawing or rendering.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ["static", "dolly_in", "dolly_out", "zoom_in", "zoom_out", "pan_left", "pan_right", "truck_left", "truck_right",
           "tilt_up", "tilt_down", "pedestal_up", "pedestal_down", "orbit", "tracking", "handheld"]

ASK = """You write a 30-second commercial for an automatic pipeline. An image model draws two or three reference pictures,
then a video model films three 10-second clips of three shots each, copying those pictures. Nine shots in all.

The product: {product}
The art style: {style}
The idea, if the person gave one: {idea}
The closing line, if the person gave one: {tagline}
{own_picture}

Write a small story that makes sense and ends by showing the product in a clever way: the product is the answer to the
story, revealed with a twist (the whole world turns out to be inside it, its shape appears in something else, the story
was about it all along). The art style holds from the first shot to the last.

Rules. Each one comes from a render that went wrong.
1. Never show a small object being picked up, opened by hand or handled. Show it still, then cut to it already in place.
2. Draw the product ONCE (picture key "product") and use that picture in every shot the product appears in.
3. A character that appears in a clip must be the "pic" of at least one shot in THAT clip, and be named with its
   {{key}} in every shot that shows it. A clip without the picture invents a different character.
4. People, characters and the product are drawn on PLAIN backgrounds. The place is described in the shot, never in
   the character's or product's picture.
5. The last shot's picture (key "end") shows the clever ending exactly as it should look, product included.
6. Never write "presenter". Name the character by what it is.
7. Say what must not be there when a model would add it: "no wire", "lips closed", "nobody speaks", "nothing is picked up".
8. No lettering, no brand names, no logos anywhere. Labels are blank or carry one simple shape.
9. Nobody speaks on screen. One voiceover line of two to five words, in the last shot only ("say").
10. "sound" lists sounds that are heard, never music.
11. Each clip has exactly three shots whose "len" values add up to exactly 243. Use lengths between 75 and 93.
12. "camera" is one of: {cameras}. "amp" is "small" or "large", "speed" is "slow" or "fast" (leave both out for static, tracking, handheld).
13. Two or three pictures in all. Keys are short lower-case words.
14. Each shot's "text" is one sentence of 25 to 50 words saying what is seen. The first shot of a clip starts with a
    capital letter. The second and third shots start in lower case with the thing shown ("a close-up of ...", "the
    tower standing ..."), because the words "the camera cuts to" are put in front of them automatically. Never write
    "the camera cuts to" yourself.

Answer with ONLY one JSON object, no markdown fence, in exactly this shape:
{{
 "name": "{prefix}",
 "style": "one or two sentences: the look, written so a video model keeps it in every shot",
 "picture_style": "Style: the same look, for still pictures.",
 "voice": "A woman or man with a ... voice",
 "pictures": {{
  "hero":    {{"draw": "what to draw, in full, on a plain background", "is": "the short phrase the shots call it"}},
  "product": {{"draw": "...", "is": "..."}},
  "end":     {{"draw": "the clever ending as one picture", "is": "..."}}
 }},
 "clips": [
  {{"sound": "sounds heard in this clip",
    "shots": [
     {{"len": 80, "pic": "hero", "camera": "dolly_in", "amp": "small", "speed": "slow", "text": "... {{hero}} ..."}},
     {{"len": 80, "camera": "static", "text": "..."}},
     {{"len": 83, "pic": "product", "camera": "dolly_in", "amp": "small", "speed": "slow", "text": "{{product}} ..."}}
    ]}},
  {{"sound": "...", "shots": [3 shots]}},
  {{"sound": "...", "shots": [2 shots, then the last: {{"len": 88, "pic": "end", "camera": "dolly_in", "amp": "small", "speed": "slow", "say": "the closing line", "text": "{{end}} ..."}}]}}
 ]
}}"""


def say(**out):
    print(json.dumps(out, ensure_ascii=False))


def ask_claude(prompt, folder):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_"))}
    env["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    r = subprocess.run(["claude", "-p", prompt, "--model", "opus", "--output-format", "json", "--allowedTools", "Read",
                        "--setting-sources", "", "--strict-mcp-config"], capture_output=True, text=True, timeout=900,
                       stdin=subprocess.DEVNULL, cwd=folder, env=env)
    try:
        reply = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError(f"claude failed: {(r.stderr or r.stdout).strip()[-300:]}")
    if r.returncode or reply.get("is_error"):
        raise RuntimeError(f"claude failed: {reply.get('result', '')[:300]}")
    m = re.search(r"\{.*\}", reply.get("result", ""), re.S)
    if not m:
        raise RuntimeError("claude gave no JSON")
    return json.loads(m.group(0))


def problems(spec):
    """What is wrong with a script, as sentences. Empty when it can be built."""
    bad = []
    pics = spec.get("pictures") or {}
    if not 1 <= len(pics) <= 4:
        bad.append("there must be one to four pictures")
    if len(spec.get("clips") or []) != 3:
        bad.append("there must be exactly three clips")
    for c, clip in enumerate(spec.get("clips") or [], 1):
        shots = clip.get("shots") or []
        total = sum(int(s.get("len") or 0) for s in shots)
        if total % 17 != 5 or not 124 <= total <= 243:
            bad.append(f"clip {c} is {total} frames; it must be 243 (or 124, 141, ... 226)")
        attached = {s.get("pic") for s in shots if s.get("pic")}
        for i, s in enumerate(shots, 1):
            if s.get("pic") and s["pic"] not in pics:
                bad.append(f"clip {c} shot {i} uses picture \"{s['pic']}\", which is not in pictures")
            if s.get("camera") and s["camera"] not in CAMERAS:
                bad.append(f"clip {c} shot {i} has camera \"{s['camera']}\"; use one of {', '.join(CAMERAS)}")
            for key in re.findall(r"\{(\w+)\}", s.get("text") or ""):
                if key not in attached:
                    bad.append(f"clip {c} shot {i} names {{{key}}}, but no shot in clip {c} has \"pic\": \"{key}\"")
            if not (s.get("text") or "").strip():
                bad.append(f"clip {c} shot {i} has no text")
    return bad


def main():
    a = argparse.ArgumentParser()
    a.add_argument("name"); a.add_argument("--product", required=True); a.add_argument("--style", required=True)
    a.add_argument("--idea", default=""); a.add_argument("--tagline", default=""); a.add_argument("--picture", default="")
    a.add_argument("--redo", action="store_true")
    o = a.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", o.name):
        return say(ok=False, error='the name is lower-case letters, digits and dashes, for example "paper-fizz"')
    folder = HERE / "ads" / o.name
    out = folder / "spec.json"
    if out.exists() and not o.redo:
        return say(ok=False, error=f"ads/{o.name} already has a script. Add --redo to write it again.")
    folder.mkdir(parents=True, exist_ok=True)
    prefix = re.sub(r"[^a-z0-9]", "", o.name)[:12] or "ad"       # file names on the GPU start with this
    own = ""
    if o.picture:
        src = Path(o.picture).expanduser()
        if not src.exists():
            return say(ok=False, error=f"no picture at {src}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=1344:768:force_original_aspect_ratio=decrease,pad=1344:768:(ow-iw)/2:(oh-ih)/2:color=white",
                        str(folder / f"{prefix}_product.png")], timeout=120)
        own = (f"The person supplied their own picture of the product: read the file {prefix}_product.png in the current "
               "folder with the Read tool and describe the product from it in \"is\". Still write a \"draw\" text for "
               "it; it will not be drawn again.")
    spec = ask_claude(ASK.format(product=o.product, style=o.style, idea=o.idea or "(none: invent one)", tagline=o.tagline or "(none: write one)",
                                 own_picture=own, cameras=", ".join(CAMERAS), prefix=prefix), folder)
    spec["name"] = prefix
    for clip in spec.get("clips") or []:                     # the director adds these words itself; twice reads as a stutter
        for shot in clip.get("shots") or []:
            shot["text"] = re.sub(r"^\s*the camera cuts to\s+", "", str(shot.get("text") or ""), flags=re.I)
    bad = problems(spec)
    if bad:
        (folder / "spec.rejected.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
        return say(ok=False, error="the script came back with mistakes; run again", problems=bad[:8])
    out.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
    say(ok=True, name=o.name, file=str(out), pictures=list(spec["pictures"]), line=next((s.get("say") for c in spec["clips"] for s in c["shots"] if s.get("say")), None),
        shots=[s["text"][:110] for c in spec["clips"] for s in c["shots"]])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        say(ok=False, error=f"{type(e).__name__}: {e}"[:400])
