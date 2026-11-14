#!/usr/bin/env python3
"""The steps of the n8n "Cartoon machine" workflow. Each prints ONE JSON line and always exits 0.

    cartoon_job.py pictures <show>/<episode>   start picture per scene (Codex, from the character sheet, then from scene 1)
    cartoon_job.py voice <show>/<episode>      the character's voice line per scene (Fish Audio)
    cartoon_job.py shoot <show>/<episode>      one clip per scene on the 5090, up to 4 tries until the words match
    cartoon_job.py finish <show>/<episode>     join the best take of every scene into final.mp4 + a vertical Short

<show>/<episode> is a folder in shows/ that holds script.json, for example mango/omelet. The show folder above it
holds show.json (the character, the look, the rules) and character_sheet.png. new_show.py makes a show,
write_episode.py writes an episode. The Mango examples were made by running these same scripts by hand.
"""
import json, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import show as S  # noqa: E402
UV = str(Path.home() / ".local/bin/uv")
PASS, TRIES = 0.97, 4
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")


def say(**out):
    print(json.dumps(out))


def run(cmd, episode, timeout):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=HERE, stdin=subprocess.DEVNULL,
                          env={**os.environ, "EPISODE": episode})


def scenes(episode):
    return json.loads((S.episode_dir(episode) / "script.json").read_text())


def pictures(episode):
    ep = S.episode_dir(episode)
    (ep / "pictures").mkdir(exist_ok=True)
    first = ep / "pictures" / "scene1_1344x768.png"
    if not first.exists():                                   # scene 1 from the character sheet
        run(["python3", "make_pictures.py", episode, str(S.load_show(ep)["sheet"]), "1"], episode, 600)
    todo = [str(s["n"]) for s in scenes(episode) if not (ep / "pictures" / f"scene{s['n']}_1344x768.png").exists()]
    if todo and first.exists():                              # every other scene from scene 1, so character and place stay the same
        run(["python3", "make_pictures.py", episode, str(first)] + todo, episode, 900)
    missing = [s["n"] for s in scenes(episode) if not (ep / "pictures" / f"scene{s['n']}_1344x768.png").exists()]
    say(ok=not missing, episode=episode, missing_pictures=missing)


def voice(episode):
    ep = S.episode_dir(episode)
    (ep / "voice").mkdir(exist_ok=True)
    r = run([UV, "run", "make_clips.py", "voice"], episode, 1800)
    missing = [s["n"] for s in scenes(episode) if not (ep / "voice" / f"scene{s['n']}.wav").exists()]
    say(ok=not missing, episode=episode, missing_voice=missing, error=(r.stderr or "")[-200:] if missing else None)


def shoot(episode):
    ep = S.episode_dir(episode)
    (ep / "clips").mkdir(exist_ok=True)
    best, flags = {}, []
    for s in scenes(episode):
        top = None
        for attempt in range(1, TRIES + 1):
            r = run([UV, "run", "make_clips.py", "clip", str(s["n"]), str(attempt)], episode, 100 * 60)
            try:
                out = json.loads(r.stdout[r.stdout.index("{\n"):])
            except ValueError:
                continue
            if top is None or out["match"] > top["match"]:
                top = out
            if out["match"] >= PASS:
                break
        if top is None:
            flags.append(f"scene {s['n']}: no clip")
            continue
        best[str(s["n"])] = top["file"]
        if top["match"] < PASS:
            flags.append(f"scene {s['n']}: heard \"{top['heard']}\"")
    (ep / "best.json").write_text(json.dumps(best, indent=1))
    say(ok=len(best) == len(scenes(episode)), episode=episode, flags=flags)


def finish(episode):
    ep = S.episode_dir(episode)
    best = json.loads((ep / "best.json").read_text())
    clips = [str(ep / "clips" / best[str(s["n"])]) for s in scenes(episode)]
    final, short = ep / "final.mp4", ep / "short.mp4"
    subprocess.run(["sh", str(HERE / "join.sh")] + clips, env={**os.environ, "OUT": str(final)}, timeout=1800)
    subprocess.run(["sh", str(HERE / "make_short.sh"), str(final), str(short)], timeout=1800)
    say(ok=final.exists(), episode=episode, final=str(final), short=str(short) if short.exists() else None)


if __name__ == "__main__":
    step, episode = sys.argv[1], sys.argv[2]
    try:
        {"pictures": pictures, "voice": voice, "shoot": shoot, "finish": finish}[step](episode)
    except Exception as e:
        say(ok=False, episode=episode, error=f"{type(e).__name__}: {e}"[:300])
