"""Start pictures for an episode, each made by Codex from a reference picture so cat, kitchen and props stay the same.
    python3 make_pictures.py <episode folder> <reference picture> <scene numbers...>"""
import json, shutil, subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parent; CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
ep, ref, wanted = R / sys.argv[1], Path(sys.argv[2]).resolve(), [int(x) for x in sys.argv[3:]]
style, char = (R / "style.txt").read_text().strip(), (R / "character.txt").read_text().strip()
procs = []
for s in json.loads((ep / "script.json").read_text()):
    if s["n"] not in wanted: continue
    w = ep / "work" / f"s{s['n']}"; w.mkdir(parents=True, exist_ok=True); shutil.copy(ref, w / "previous_scene.png")
    (w / f"scene{s['n']}.png").unlink(missing_ok=True)
    (w / "prompt.txt").write_text(f"""Use your image generation tool to make ONE new landscape 16:9 image that is another shot of the same children's cooking cartoon as the attached image. Keep EVERYTHING identical to the attached image except what is described as changed: the same cat character (same body shape, fur colour, face, eyes, folded left ear, teal apron with yellow round pocket, floppy teal chef hat with yellow band), the same kitchen with pale yellow wall and light wooden cupboards, the same round window on the left, the same shelf with the same pink, yellow and purple jars on the right, the same camera position, the same art style and rendering. Remove every prop from the counter that is not listed below.

The character: {char}

What this shot shows: {s['picture']} Mango faces the camera, eyes on the camera, mouth slightly open as if about to speak. Exactly one cat, two arms, two paws. Every listed object and the paw doing the action are fully visible and not hidden by anything. No knives, no flame, no fire, no smoke, no text.

Art style: {style}

Save the image as scene{s['n']}.png in the current directory. Reply with just the file path.""")
    procs.append(subprocess.Popen([CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(w), "-i", str(w / "previous_scene.png")],
                                  stdin=open(w / "prompt.txt"), stdout=open(w / "log.txt", "w"), stderr=subprocess.STDOUT))
for p in procs: p.wait(timeout=500)
for n in wanted:
    raw = ep / "work" / f"s{n}" / f"scene{n}.png"; print(n, raw.exists())
    if raw.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", "scale=1344:768:force_original_aspect_ratio=increase,crop=1344:768", str(ep / "pictures" / f"scene{n}_1344x768.png")])
