"""Make a multi-shot commercial from one spec file, with Codex pictures and the MiniMax Director.

    python3 adkit.py draw  ads/<name>/spec.json     # Codex draws every picture in the spec (skips ones already drawn)
    python3 adkit.py build ads/<name>/spec.json     # writes one director timeline per clip and checks it
    python3 adkit.py sheet ads/<name>               # frame sheets of the rendered clips, to look at
    python3 adkit.py join  ads/<name>               # joins clips/<name>_1.mp4, _2.mp4, ... into final.mp4

The rendering itself happens on the GPU box (box/run_director.py there queues the timelines).
See README.md in this folder for the whole procedure and the rules that came out of real failures.

Spec (JSON):
{
  "name": "sneaker-city",                      # also the file prefix on the box
  "style": "...",                              # the look, first sentence of every clip's prompt
  "picture_style": "...",                      # appended to every Codex picture prompt
  "pictures": {"shoe": {"draw": "what Codex should draw", "is": "what the prompt calls it"}, ...},
  "voice": "A woman with a warm, low voice",   # only needed when a shot has "say"
  "clips": [
    {"sound": "what is heard (no music)",
     "shots": [{"len": 80, "pic": "shoe", "camera": "dolly_in", "amp": "small", "speed": "slow",
                "text": "... {shoe} ...", "say": "optional voiceover line", "enter": "cut"}]}
  ]
}
"{shoe}" in a shot's text becomes the <Picture n> token of that picture. A picture must be the
"pic" of some shot in the same clip to be named in it. Clip length is the sum of "len" and has
to be 124, 141, ... 243 (length % 17 == 5).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIRECTOR = Path(os.environ.get("MINIMAX_DIRECTOR", ROOT / "vendor" / "ComfyUI-MiniMaxDirector"))   # a clone of github.com/imbutus/ComfyUI-MiniMaxDirector
sys.path.insert(0, str(DIRECTOR / "src"))
CODEX = os.environ.get("CODEX_BIN", "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")   # the Codex command-line program that draws the pictures
SIZES = {"wide": (1344, 768), "tall": (768, 1344)}      # "shape" in the script file; wide when it is not said


def load(path: str):
    spec = json.loads(Path(path).read_text())
    return spec, Path(path).resolve().parent


def draw_one(folder: Path, spec: dict, key: str) -> str:
    out = folder / f"{spec['name']}_{key}.png"
    if out.exists():
        return f"{key}: already drawn"
    work = folder / "_draw" / key
    work.mkdir(parents=True, exist_ok=True)
    W, H = SIZES[spec.get("shape", "wide")]
    frame = "portrait 9:16, about 864x1536" if H > W else "landscape 16:9, about 1536x864"
    prompt = (f"Use your image generation tool to make one picture, then save it in the current folder as {key}.png "
              f"(PNG, {frame}). Do nothing else, and do not write any other files.\n\n"
              f"PICTURE: {spec['pictures'][key]['draw']}\n\n{spec['pictures'][key].get('style', spec['picture_style'])} No text, no letters, no logos, no brand marks, no watermark.")
    for _ in range(2):
        try:
            subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(work)],
                           input=prompt, capture_output=True, text=True, timeout=420)
        except subprocess.TimeoutExpired:
            continue
        raw = work / f"{key}.png"
        if raw.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf",
                            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", str(out)], timeout=120)
            return f"{key}: drawn"
    return f"{key}: FAILED"


def draw(path: str) -> None:
    spec, folder = load(path)
    with ThreadPoolExecutor(4) as pool:
        for line in pool.map(lambda k: draw_one(folder, spec, k), spec["pictures"]):
            print(line)
    pics = [folder / f"{spec['name']}_{k}.png" for k in spec["pictures"]]
    pics = [p for p in pics if p.exists()]
    if pics:                                                  # one strip to look at
        ins = sum((["-i", str(p)] for p in pics), [])
        chain = "".join(f"[{i}]scale=-2:270[s{i}];" for i in range(len(pics))) + "".join(f"[s{i}]" for i in range(len(pics))) + f"hstack={len(pics)}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", chain if len(pics) > 1 else "[0]scale=-2:270", str(folder / "pictures.jpg")])
        print("look at", folder / "pictures.jpg")


def director() -> None:
    """The MiniMax Director's code has to be on this machine to build and check timelines. Fetch it once."""
    if (DIRECTOR / "src" / "minimax_director").exists():
        return
    print("fetching ComfyUI-MiniMaxDirector into", DIRECTOR)
    DIRECTOR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "https://github.com/imbutus/ComfyUI-MiniMaxDirector", str(DIRECTOR)], check=True, timeout=300)
    subprocess.run(["git", "-C", str(DIRECTOR), "checkout", "-q", "dc38ef9"], timeout=60)      # the version the examples were made with


def build(path: str) -> None:
    director()
    from minimax_director import Timeline, compile_timeline
    from minimax_director.lint import lint
    spec, folder = load(path)
    for number, clip in enumerate(spec["clips"], 1):
        order = []                                            # pictures in the order the compiler numbers them
        for shot in clip["shots"]:
            if shot.get("pic") and shot["pic"] not in order:
                order.append(shot["pic"])
        token = {k: f"<Picture {i}>" for i, k in enumerate(order, 1)}
        shots, moves, at = [], [], 0
        for shot in clip["shots"]:
            text = shot["text"]
            for key in re.findall(r"\{(\w+)\}", text):
                if key not in token:
                    sys.exit(f"clip {number}: {{{key}}} is named but is not the pic of any shot in this clip")
                text = text.replace("{" + key + "}", token[key])
            record = {"start": at, "length": shot["len"], "prompt": text}
            if shot.get("enter") and shot["enter"] != "cut":
                record["transition"] = shot["enter"]
            if shot.get("pic"):
                p = spec["pictures"][shot["pic"]]
                record["media"] = {"kind": "image", "filename": f"{spec['name']}_{shot['pic']}.png", "subfolder": "",
                                   "description": p["is"], "retention": p.get("keep", "fully_preserved")}
            if shot.get("say"):
                record["lines"] = [{"text": shot["say"], "ids": "S1", "delivery": shot.get("how", "says"), "language": "English", "offscreen": True}]
            shots.append(record)
            if shot.get("camera"):
                move = {"start": at, "length": shot["len"], "camera": shot["camera"]}
                move.update({k2: shot[k] for k, k2 in (("amp", "amplitude"), ("speed", "speed")) if shot.get(k)})
                moves.append(move)
            at += shot["len"]
        if at % 17 != 5:
            sys.exit(f"clip {number}: {at} frames; the length has to be 124, 141, 158, ... 243 (length % 17 == 5)")
        spoken = any(s.get("say") for s in clip["shots"])
        doc = {"version": 1, "fps": 24, "duration": at, "global_prompt": spec["style"], "music": clip.get("music", ""),
               "speech": spoken, "shots": shots, "moves": moves, "references": [],
               "cues": [{"start": 0, "length": at, "prompt": clip.get("sound") or "Near silence. Nobody speaks."}]}
        if spoken:
            doc["speakers"] = [{"id": 1, "voice": spec.get("voice", "A woman with a warm, low voice")}]
        out = folder / f"{spec['name']}_{number}.json"
        out.write_text(json.dumps(doc, indent=1))
        t = Timeline.from_json(out.read_text())
        prompt = compile_timeline(t).prompt
        (folder / f"{spec['name']}_{number}.prompt.txt").write_text(prompt)
        issues = [str(i) for i in lint(t) if "words" not in str(i)]
        print(f"clip {number}: {at} frames ({at / 24:.1f} s), {len(order)} pictures, {len(prompt.split())} words", issues or "")


def clips_of(folder: Path) -> list[Path]:
    return sorted((folder / "clips").glob("*.mp4"), key=lambda p: int(re.findall(r"_(\d+)", p.stem)[-1]))


def sheet(folder_arg: str) -> None:
    folder = Path(folder_arg)
    for clip in clips_of(folder):
        out = folder / "clips" / f"{clip.stem}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf", "fps=1.2,scale=400:-1,tile=4x3", "-frames:v", "1", str(out)])
        print(out)


def join(folder_arg: str, sound: bool = True) -> None:
    folder = Path(folder_arg)
    clips = clips_of(folder)
    if not clips:
        sys.exit("no clips in " + str(folder / "clips"))
    dur = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(c)],
                                capture_output=True, text=True).stdout) for c in clips]
    fade, ins, v, a, total = 0.5, sum((["-i", str(c)] for c in clips), []), "[0:v]", "[0:a]", dur[0]
    parts = []
    for i in range(1, len(clips)):
        parts.append(f"{v}[{i}:v]xfade=transition=fade:duration={fade}:offset={total - fade:.3f}[v{i}]")
        parts.append(f"{a}[{i}:a]acrossfade=d={fade}[a{i}]")
        v, a, total = f"[v{i}]", f"[a{i}]", total + dur[i] - fade
    parts.append(f"{v}fade=t=out:st={total - 0.6:.3f}:d=0.6,format=yuv420p[v]")
    parts.append(f"{a}afade=t=out:st={total - 0.8:.3f}:d=0.8[a]")
    out = folder / "final.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(parts), "-map", "[v]"] + \
          (["-map", "[a]", "-c:a", "aac", "-b:a", "192k"] if sound else ["-an"]) + ["-c:v", "libx264", "-crf", "17", "-preset", "medium", str(out)]
    subprocess.run(cmd, check=True)
    print(out, f"{total:.1f} s")


if __name__ == "__main__":
    {"draw": draw, "build": build, "sheet": sheet, "join": join}[sys.argv[1]](sys.argv[2])
