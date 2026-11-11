#!/usr/bin/env python3
"""The steps of the n8n "Episode machine" workflow. Each prints ONE JSON line and always exits 0,
so the workflow decides what happens next instead of dying on an error.

    episode_job.py next <base64 JSON list of {topic, where, style}>   pick the next topic that has no finished episode
    episode_job.py plan <folder name>                                  script, fact check, set pictures
    episode_job.py shoot <folder name>                                 Fish-voice version on the 5090 (waits if the 5090 is away)
    episode_job.py finish <folder name>                                release the lock, refresh the gallery, sort into ready / needs a look
    episode_job.py post                                                publish ONE waiting episode to YouTube (Short + full video), spaced 30 min apart
    episode_job.py approve <folder name>                               put a flagged episode on the ready list by hand

Only one episode is made at a time: `next` answers go=false while another one is in flight.
Pause the machine:  touch episodes/PAUSE      Resume:  delete that file.
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EP = ROOT / "episodes"
LOCK = EP / ".busy"
OUT = ROOT / "output"
UV = str(Path.home() / ".local/bin/uv")
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")
sys.path.insert(0, str(HERE))
import run_night  # noqa: E402  (slug, wait_for_server, build_index)


def say(**out):
    print(json.dumps(out))


def run(cmd, timeout):
    return run_night.run(cmd, timeout)


def finished(folder):
    rf = folder / "result.json"
    return rf.exists() and bool((json.loads(rf.read_text()).get("fish") or {}).get("wide"))


def folder_for(topic):
    """The episode folder for a topic: the existing one with the same slug, else a new one with the next number."""
    slug = run_night.slug(topic)
    folders = sorted(p for p in EP.iterdir() if p.is_dir() and re.match(r"\d\d+-", p.name))
    for p in folders:
        if p.name.split("-", 1)[1] == slug:
            return p, False
    number = max([int(p.name.split("-")[0]) for p in folders] or [0]) + 1
    return EP / f"{number:02d}-{slug}", True


def next_topic(encoded):
    topics = json.loads(base64.b64decode(encoded))
    EP.mkdir(exist_ok=True)
    if (EP / "PAUSE").exists():
        return say(go=False, why="paused (episodes/PAUSE exists)")
    busy = subprocess.run(["pgrep", "-f", "plan_episode.py|make_episode.py"], capture_output=True, text=True).stdout.split()
    if busy:
        return say(go=False, why="an episode is being made right now")
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 3 * 3600:
        return say(go=False, why="an episode is in flight: " + LOCK.read_text()[:80])
    done = 0
    for t in topics:
        folder, new = folder_for(t["topic"])
        if not new and finished(folder):
            done += 1
            continue
        tried = folder / "failed.json"                    # failed twice: left alone for 3 hours, then tried again
        if tried.exists() and json.loads(tried.read_text()).get("count", 0) >= 2 and time.time() - tried.stat().st_mtime < 3 * 3600:
            continue
        folder.mkdir(exist_ok=True)
        style = t.get("style") or "long"
        if (folder / "spec.json").exists():               # already planned earlier: keep that plan and its style
            style = "long" if len(json.loads((folder / "spec.json").read_text()).get("takes", [])) > 6 else "short"
        (folder / "job.json").write_text(json.dumps({"topic": t["topic"], "where": t.get("where", ""), "style": style}, indent=2))
        LOCK.write_text(f"{folder.name} since {time.strftime('%H:%M')}")
        return say(go=True, folder=folder.name, topic=t["topic"], style=style, done=done, total=len(topics))
    say(go=False, why="every topic on the list has a finished episode (or failed twice)", done=done, total=len(topics))


def plan(name):
    folder = EP / name
    job = json.loads((folder / "job.json").read_text())
    cmd = ["python3", str(HERE / "plan_episode.py"), str(folder), job["topic"], job.get("where", "")] + (["long"] if job["style"] == "long" else [])
    out = {"ok": False}
    for _ in range(2):
        out = run(cmd, 50 * 60)
        if out.get("ok"):
            break
    say(ok=bool(out.get("ok")), folder=name, title=out.get("title"), takes=out.get("takes"),
        fact_fixes=len(out.get("fact_fixes") or []), error=out.get("error"))


def shoot(name):
    folder = EP / name
    deadline = time.time() + 3 * 3600
    out = {"ok": False, "error": "the 5090 did not answer for 3 hours"}
    for attempt in range(3):
        LOCK.write_text(f"{name} since {time.strftime('%H:%M')}")           # keep the lock fresh on long waits
        if not run_night.wait_for_server(deadline):
            break
        out = run([UV, "run", str(HERE / "make_episode.py"), str(folder), "fish"], 90 * 60)
        if out.get("ok"):
            break
        time.sleep(120)
    fish = out.get("fish") or {}
    say(ok=bool(out.get("ok")), folder=name, title=out.get("title"), seconds=fish.get("seconds"), minutes=fish.get("minutes"),
        flags=fish.get("flags") or [], error=out.get("error") or out.get("errors") or None)


def finish(name):
    folder = EP / name
    LOCK.unlink(missing_ok=True)
    result = json.loads((folder / "result.json").read_text()) if (folder / "result.json").exists() else {}
    fish = result.get("fish") or {}
    status = "failed" if not fish.get("wide") else ("needs_look" if fish.get("flags") else "ready")
    tried = folder / "failed.json"
    if status == "failed":
        count = (json.loads(tried.read_text()).get("count", 0) if tried.exists() else 0) + 1
        tried.write_text(json.dumps({"count": count, "last": time.strftime("%Y-%m-%d %H:%M")}))
    else:
        tried.unlink(missing_ok=True)
    try:
        run_night.build_index()
    except Exception:
        pass
    OUT.mkdir(exist_ok=True)
    entry = {"folder": name, "title": result.get("title"), "status": status, "when": time.strftime("%Y-%m-%d %H:%M"),
             "wide": fish.get("wide"), "vertical": fish.get("vertical"), "seconds": fish.get("seconds"), "flags": fish.get("flags") or [],
             "post": (folder / "post.txt").read_text() if (folder / "post.txt").exists() else ""}
    if status != "failed":                                 # two lists the upload step (and the owner) read
        for listed, keep in (("ready_to_post.json", status == "ready"), ("needs_look.json", status == "needs_look")):
            path = OUT / listed
            items = [e for e in (json.loads(path.read_text()) if path.exists() else []) if e["folder"] != name]
            path.write_text(json.dumps(items + ([entry] if keep else []), indent=2))
    say(**entry)


def listed(name):
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else []


def approve(name):
    """the owner said this episode is good: put it on the ready list even though a take was flagged."""
    folder = EP / name
    result = json.loads((folder / "result.json").read_text())
    fish = result["fish"]
    entry = {"folder": name, "title": result.get("title"), "status": "ready", "when": time.strftime("%Y-%m-%d %H:%M"),
             "wide": fish.get("wide"), "vertical": fish.get("vertical"), "seconds": fish.get("seconds"), "flags": fish.get("flags") or [],
             "post": (folder / "post.txt").read_text() if (folder / "post.txt").exists() else "", "approved_by_hand": True}
    OUT.mkdir(exist_ok=True)
    (OUT / "ready_to_post.json").write_text(json.dumps([e for e in listed("ready_to_post.json") if e["folder"] != name] + [entry], indent=2))
    (OUT / "needs_look.json").write_text(json.dumps([e for e in listed("needs_look.json") if e["folder"] != name], indent=2))
    say(ok=True, folder=name, status="ready")


POSTER = ROOT.parent / "poster"
GAP = 3 * 3600           # one episode every 3 hours (the owner agreed 2026-11-11): each Short gets a clean test, channel is not flooded
BACKOFF = 2 * 3600       # after a failed upload (sign-in lost, daily upload limit...), leave YouTube alone this long


def post(_=None):
    """Publish ONE waiting episode (Short + full video, public). Called every time the workflow runs, so an
    upload that failed is tried again later and nothing on the ready list is forgotten."""
    state_file = OUT / "posting.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    now = time.time()
    waiting = [e for e in listed("ready_to_post.json")
               if not ((EP / e["folder"] / "youtube_vertical.json").exists() and (EP / e["folder"] / "youtube_wide.json").exists())]
    if not waiting:
        return say(ok=True, posted=None, why="nothing waiting to be posted")
    if now < state.get("busy_until", 0):
        return say(ok=True, posted=None, why="another upload is running", waiting=len(waiting))
    if now < state.get("retry_after", 0):
        return say(ok=True, posted=None, why="last upload failed: " + str(state.get("error"))[:150] + "; trying again at "
                   + time.strftime("%H:%M", time.localtime(state["retry_after"])), waiting=len(waiting))
    if now - state.get("last_post", 0) < GAP:
        return say(ok=True, posted=None, why="spacing uploads; next one at " + time.strftime("%H:%M", time.localtime(state["last_post"] + GAP)),
                   waiting=len(waiting))
    name = waiting[0]["folder"]
    state_file.write_text(json.dumps({**state, "busy_until": now + 20 * 60}))
    r = subprocess.run([str(POSTER / ".venv/bin/python"), str(POSTER / "yt.py"), "upload", str(EP / name), "public", "both"],
                       capture_output=True, text=True, timeout=30 * 60, stdin=subprocess.DEVNULL)
    lines = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
    ok = len(lines) == 2 and all(x.get("ok") for x in lines)
    state = {"last_post": time.time()} if ok else {"last_post": state.get("last_post", 0), "retry_after": time.time() + BACKOFF,
                                                   "error": next((x.get("error") for x in lines if not x.get("ok")), None) or (r.stderr or "no answer")[-200:]}
    state_file.write_text(json.dumps(state))
    say(ok=ok, posted=name if ok else None, title=waiting[0].get("title"), waiting=len(waiting) - (1 if ok else 0),
        links=[x.get("url") for x in lines if x.get("url")], error=state.get("error"))


if __name__ == "__main__":
    step, arg = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    try:
        {"next": next_topic, "plan": plan, "shoot": shoot, "finish": finish, "approve": approve, "post": post}[step](arg)
    except Exception as e:
        if step != "next":
            LOCK.unlink(missing_ok=True) if step == "finish" else None
        say(ok=False, go=False, folder=arg if step != "next" else None, why=f"{type(e).__name__}: {e}"[:300], error=f"{type(e).__name__}: {e}"[:300])
