#!/usr/bin/env python3
"""Audit set pictures for body mistakes (her body inside a table etc.) and remake the bad ones.

    fix_sets.py stock            # make her/sets/desk_front + desk_side (studio, no table in frame)
    fix_sets.py <episode folder> [...]   # body-check every location picture; remake failures; refresh desk pictures
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan_episode as pe  # noqa: E402

STUDIO = {
    "desk_front": "She sits upright in her home studio, shoulders square to the camera. Behind her a wooden bookshelf with books and trailing plants, an antique globe on a shelf at shoulder height to one side, a warm lamp, and a window with daylight on the other side.",
    "desk_side": "The same home studio from a second camera position that is still straight in front of her at eye level, slightly closer, with a different part of the room behind her: the window and curtain on one side and the end of the bookshelf with the globe and a small potted plant on the other.",
}


def stock():
    out = {}
    for name, picture in STUDIO.items():
        out[name] = pe.make_picture(pe.ROOT / "her", {"name": name, "picture": picture})
    return out


import re
TOUCH = re.compile(r"\b(desk|table|tabletop|counter|stool|railing|rests? on|resting on|leans? on|touch(es)?|picks? up|holds?)\b", re.I)

REWRITE = """You are the director of a short educational video series. A new rule was added to the rulebook:

"Nothing in front of her. Never put a table, desk, counter, railing or any object between her and the camera, and never a surface along the bottom of the frame: the video model makes her body pass through it. If a place has a table or counter, put it behind her or to one side. Objects that show the topic go behind or beside her at shoulder height. Her direction never has her touch, lean on or pick up anything. The home studio sets desk_front and desk_side now show her chest-up with a bookshelf, globe and lamp behind her and no desk in the frame."

Fix this episode so it obeys the rule. Keep every 'says' line exactly. Keep set names. Change only what breaks the rule: a set's 'picture' and 'camera' (camera must still end "exactly as in the first frame"), and a take's 'does' (keep the same timing style: small actions tied to words in the line, hands in the air at chest height, never on a surface).

Episode:
{spec}

Answer with ONLY one JSON object: {{"sets": [{{"name": "...", "picture": "...", "camera": "..."}}], "takes": [{{"n": 1, "does": "..."}}]}} listing only the sets and takes you changed (empty lists if nothing needs changing)."""


def rewrite(folder, spec):
    """Bring an already-written episode in line with the nothing-in-front rule. Returns names of sets whose picture text changed."""
    small = {"sets": spec["sets"], "takes": [{"n": t["n"], "set": t["set"], "says": t["says"], "does": t["does"]} for t in spec["takes"]]}
    r = pe.ask_claude(REWRITE.format(spec=json.dumps(small, indent=1)), folder, "opus")
    changed = []
    for n in r.get("sets", []):
        for s in spec["sets"]:
            if s["name"] == n.get("name") and n.get("picture") and n.get("camera"):
                if n["picture"] != s["picture"]:
                    changed.append(s["name"])
                s["picture"], s["camera"] = n["picture"], n["camera"]
    for n in r.get("takes", []):
        for t in spec["takes"]:
            if t["n"] == n.get("n") and n.get("does") and not pe.MOOD.search(n["does"]):
                t["does"] = n["does"]
    (folder / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
    return changed


def episode(folder):
    spec = json.loads((folder / "spec.json").read_text())
    report = {}
    retold = []
    text = " ".join(s["picture"] + " " + s["camera"] for s in spec["sets"]) + " ".join(t["does"] for t in spec["takes"])
    if TOUCH.search(text):
        try:
            retold = rewrite(folder, spec)
            report["script"] = f"direction rewritten, sets retold: {retold}"
        except Exception as e:
            report["script"] = f"REWRITE FAILED: {e}"[:200]
    for name in STUDIO:
        shutil.copy(pe.STOCK / f"{name}_{pe.W}x{pe.H}.png", folder / "sets" / f"{name}_{pe.W}x{pe.H}.png")
    for s in spec["sets"]:
        pic = folder / "sets" / f"{s['name']}_{pe.W}x{pe.H}.png"
        ok, why = pe.body_check(pic) if pic.exists() else (False, "missing")
        if ok and s["name"] not in retold:
            report[s["name"]] = "ok"
            continue
        pic.unlink(missing_ok=True)
        (folder / "sets" / f"{s['name']}.face.json").unlink(missing_ok=True)
        try:
            pe.make_picture(folder, s)
            report[s["name"]] = f"remade (was: {why})"
        except Exception as e:
            report[s["name"]] = f"STILL BAD: {e}"[:200]
    return report


if __name__ == "__main__":
    if sys.argv[1:] == ["stock"]:
        print(json.dumps(stock()), flush=True)
    else:
        for f in sys.argv[1:]:
            print(Path(f).name, json.dumps(episode(Path(f).resolve())), flush=True)
