"""Start pictures for an episode, each made by Codex from a reference picture so the character, the place and the props stay the same.
    python3 make_pictures.py <show>/<episode> <reference picture> <scene numbers...>
The first scene is drawn from the show's character sheet, every later scene from scene 1."""
import json, shutil, subprocess, sys
import show as S
ep, ref, wanted = S.episode_dir(sys.argv[1]), S.Path(sys.argv[2]).resolve(), [int(x) for x in sys.argv[3:]]
show = S.load_show(ep)
procs = []
for s in json.loads((ep / "script.json").read_text()):
    if s["n"] not in wanted: continue
    w = ep / "work" / f"s{s['n']}"; w.mkdir(parents=True, exist_ok=True); shutil.copy(ref, w / "previous_scene.png")
    (w / f"scene{s['n']}.png").unlink(missing_ok=True)
    (w / "prompt.txt").write_text(S.picture_prompt(show, s))
    procs.append(subprocess.Popen([S.CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(w), "-i", str(w / "previous_scene.png")],
                                  stdin=open(w / "prompt.txt"), stdout=open(w / "log.txt", "w"), stderr=subprocess.STDOUT))
for p in procs: p.wait(timeout=500)
(ep / "pictures").mkdir(exist_ok=True)
for n in wanted:
    raw = ep / "work" / f"s{n}" / f"scene{n}.png"; print(n, raw.exists())
    if raw.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", "scale=1344:768:force_original_aspect_ratio=increase,crop=1344:768", str(ep / "pictures" / f"scene{n}_1344x768.png")])
