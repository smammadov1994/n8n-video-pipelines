#!/usr/bin/env python3
"""Plan one episode: script + shot list (Claude, following skills/episode-director), a fact check,
then the set pictures of her (Codex image generation), each checked against her master picture.

    plan_episode.py <episode folder> "<topic>" ["<where it should be filmed>"]

Writes <folder>/spec.json and <folder>/sets/<name>_1344x768.png. Safe to run again: finished
parts are kept. Prints one JSON line {"ok": ...}.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from understand import ask_claude  # noqa: E402

SKILL = (ROOT / "skills" / "episode-director" / "SKILL.md").read_text().split("---", 2)[-1].strip()   # drop the front matter
LONG = len(sys.argv) > 4 and sys.argv[4] == "long"   # richer cut: nine takes, 4-5 places, no walking shots
if LONG:
    SKILL += "\n\n" + (ROOT / "skills" / "episode-director" / "LONGFORM.md").read_text().strip()
TAKES, SETS = ((8, 10), (4, 5)) if LONG else ((5, 6), (2, 3))
MASTER = ROOT / "her" / "her_couch_b_1080x1920.png"
STOCK = ROOT / "her" / "sets"                         # desk_front / desk_side pictures (studio, no table in frame)
CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
UV = str(Path.home() / ".local/bin/uv")
W, H = 1344, 768
MOOD = re.compile(r"\b(energetic|excited|confident|charismatic|playful|curious|enthusiastic|passionate|cheerful)\b", re.I)
HYPE = re.compile(r"\b(amazing|incredible|mind-?blowing|insane|crazy|did you know|hey guys)\b", re.I)

WRITE = """You are the director of a short educational video series. Your rulebook:

{skill}

---

Plan one episode following every rule above.

TOPIC: {topic}
WHERE TO FILM (a suggestion; choose real, specific scenery that shows the topic): {where}

Answer with ONLY the JSON object described in section 6, no markdown fence."""

CHECK = """You are a careful science fact-checker for a short educational video for a general audience.

Topic: {topic}
Lines spoken, in order:
{lines}

For each line decide whether it states anything false, misleading, or more certain than the science is. Simplification is fine; being wrong is not.
Only flag a line that is actually wrong or misleading. A simplification a teacher would use with a twelve-year-old is fine; do not add qualifiers ("though some...", "less strongly...") to a line that is true as a simplification.
A corrected line must still sound like a person talking: short plain sentences a twelve-year-old follows on first hearing, no colons or dashes, no stacked clauses. Prefer cutting the wrong claim to adding exceptions. If the original line ended with "Follow for more." the corrected one does too.
Answer with ONLY one JSON object: {{"problems": [{{"n": <line number>, "issue": "what is wrong", "fixed_says": "a corrected line, 14 to 20 words, plain words, same job in the script"}}]}}
Use an empty list when every line is fine."""

POLISH = """These are the lines a presenter speaks, in order, in a short educational video for a general audience. Viewers HEAR each line once, at about three words a second; they cannot re-read it.

Topic: {topic}
{lines}

Find every line that is hard to follow by ear: a sentence that packs in two ideas, an awkward or unnatural phrase nobody would say out loud, a clause hanging off a clause, a missing little word, a colon or dash, a line that does not connect to the one before it. Tides (the owner): "It's a difference in pull: the Moon tugs nearer water harder than it tugs the whole Earth" sounded like gibberish.
Rewrite each such line so a twelve-year-old gets it on first hearing: one idea, short everyday sentences, the way a friendly teacher talks. Keep every fact true (never make a line less accurate), keep the line's job in the script, 14 to 20 words, American spelling, no place names, no hype words. The LAST line must end with "Follow for more." Leave good lines alone.
Answer with ONLY one JSON object: {{"lines": [{{"n": <line number>, "says": "the clearer line", "why": "what was hard to follow"}}]}}
Use an empty list when every line already sounds natural."""

PICTURE = """Use your image generation tool to make ONE new landscape 16:9 image of the AI-generated character in the attached reference image (a synthetic character, not a real person). Keep her face as identical to the reference as possible: same face shape, same eyebrows at the same resting height, same eyes, nose, lips and jaw. Same long straight dark hair with a middle part, same beige ribbed tank top, same small gold heart necklace, blue jeans, and a small black clip-on lavalier mic on her neckline with a thin cable. Bare wrists, no watch, no bracelets. Save it in the current folder as {name}.png.

It is a single unedited still frame from a YouTube educational video shot on a mirrorless camera on a tripod.

Where she is and what is behind her: {picture}

Fixed rules: the camera is exactly at her eye level and straight in front of her (not from below, above or the side). She is close to the camera, chest-up or waist-up, with her head about one third of the frame height; she is centred unless the description above puts her on the left or right third. Soft, even, neutral daylight on her face: no sunset glow, no orange tint, no backlight, no rim light. Nothing crosses in front of her body: no table, desk, counter, railing or any other object between her and the camera, and no surface along the bottom of the frame. If the place has a table or counter, it is behind her or off to one side, never in front. The bottom edge of the frame cuts her at the waist or lower ribs with only her clothes there. Objects that show the topic sit behind her or beside her at shoulder height. She is standing or sitting still. Calm friendly expression like the reference: eyebrows relaxed, mouth just slightly open mid-word, looking into the lens. Hands empty and down, small and slender in proportion to her body. No other people, no text, no signs, no watermark. Real skin texture with visible pores, no retouching, no beauty filter.

Reply with just the file path."""


def problems_in(spec):
    out, names = [], {s["name"] for s in spec.get("sets", [])} | {"desk_front", "desk_side"}
    takes = spec.get("takes", [])
    if not TAKES[0] <= len(takes) <= TAKES[1]:
        out.append(f"needs {TAKES[1] - 1 if LONG else 6} takes, has {len(takes)}")
    for i, t in enumerate(takes):
        n = len(t.get("says", "").split())
        if not 12 <= n <= 21:
            out.append(f"take {t.get('n')}: {n} words, must be 14-20")
        if t.get("set") not in names:
            out.append(f"take {t.get('n')}: unknown set {t.get('set')}")
        if i and takes[i - 1].get("set") == t.get("set"):
            out.append(f"takes {takes[i - 1].get('n')} and {t.get('n')} use the same set in a row")
        if MOOD.search(t.get("does", "")):
            out.append(f"take {t.get('n')}: mood word in 'does' ({MOOD.search(t['does']).group(0)})")
        if HYPE.search(t.get("says", "")):
            out.append(f"take {t.get('n')}: hype word in 'says' ({HYPE.search(t['says']).group(0)})")
        if not t.get("does"):
            out.append(f"take {t.get('n')}: no 'does'")
    for s in spec.get("sets", []):
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", s.get("name", "")) or not s.get("picture") or not s.get("camera"):
            out.append(f"set {s.get('name')}: needs name, picture and camera")
    if not SETS[0] <= len(spec.get("sets", [])) <= SETS[1]:
        out.append(f"needs {SETS[0]} to {SETS[1]} location sets")
    if LONG:
        used = [t.get("set") for t in takes]
        out += [f"set {n} is used {used.count(n)} times, at most 2" for n in set(used) if used.count(n) > 2]
        if used.count("desk_front") > 1 or "desk_side" in used:
            out.append("studio at most once, desk_side not used")
        covers = [t for t in takes if t.get("cutaway")]
        if not 2 <= len(covers) <= 4 or any(re.search(r"\b(woman|she|her)\b", t["cutaway"].get("prompt", ""), re.I) for t in covers):
            out.append(f"needs 3 nature cutaways with no people (has {len(covers)}); she is never shown walking")
    return out


def polish(folder, topic, spec):
    """Read the script as a listener would and rewrite lines that are hard to follow by ear. Returns the changes."""
    lines = "\n".join(f"{t['n']}. {t['says']}" for t in spec["takes"])
    try:
        out = ask_claude(POLISH.format(topic=topic, lines=lines), folder, "opus")
    except Exception:
        return []
    changes = []
    for p in out.get("lines", []):
        new = str(p.get("says", "")).strip()
        for t in spec["takes"]:
            if t["n"] == p.get("n") and 12 <= len(new.split()) <= 21 and not HYPE.search(new) and new != t["says"]:
                changes.append({"n": t["n"], "was": t["says"], "now": new, "why": "clearer to hear: " + str(p.get("why", ""))})
                t["says"] = new
    return changes


def redirect(folder, spec, changed_ns):
    """Rewrite 'does' for takes whose line changed, so every action is tied to words that are in the new line."""
    changed = [t for t in spec["takes"] if t["n"] in changed_ns]
    if not changed:
        return
    redo = ask_claude(
        "You are the director of a short educational video series. Your rulebook:\n\n" + SKILL
        + "\n\n---\n\nSome lines of this episode were reworded. Rewrite 'does' for each changed take so every action is tied "
          "to words that are actually in its new line (rulebook section 4).\n\nFull script:\n"
        + "\n".join(f"{t['n']}. {t['says']}" for t in spec["takes"])
        + "\n\nChanged takes (new line, old direction):\n" + json.dumps(
            [{"n": t["n"], "set": t["set"], "says": t["says"], "old_does": t["does"]} for t in changed])
        + "\n\nAnswer with ONLY one JSON object: {\"takes\": [{\"n\": 1, \"does\": \"...\"}]}", folder, "opus")
    for r in redo.get("takes", []):
        for t in spec["takes"]:
            if t["n"] == r.get("n") and r.get("does") and not MOOD.search(r["does"]):
                t["does"] = r["does"]


def write_spec(folder, topic, where):
    spec = ask_claude(WRITE.format(skill=SKILL, topic=topic, where=where or "your choice"), folder, "opus")
    for _ in range(2):                                   # let the writer fix its own rule breaks
        bad = problems_in(spec)
        if not bad:
            break
        spec = ask_claude(WRITE.format(skill=SKILL, topic=topic, where=where or "your choice")
                          + "\n\nYour previous answer broke these rules; fix them and answer again with the full JSON:\n- "
                          + "\n- ".join(bad) + "\n\nPrevious answer:\n" + json.dumps(spec), folder, "opus")
    bad = problems_in(spec)
    if bad:
        raise RuntimeError("script still breaks rules: " + "; ".join(bad)[:300])
    lines = "\n".join(f"{t['n']}. {t['says']}" for t in spec["takes"])
    try:
        verdict = ask_claude(CHECK.format(topic=topic, lines=lines), folder, "opus")
    except Exception as e:  # a failed check must not pass silently
        raise RuntimeError(f"fact check did not run: {e}")
    fixes = []
    for p in verdict.get("problems", []):
        for t in spec["takes"]:
            if t["n"] == p.get("n") and 12 <= len(str(p.get("fixed_says", "")).split()) <= 21:
                fixes.append({"n": t["n"], "was": t["says"], "now": p["fixed_says"], "why": p.get("issue")})
                t["says"] = p["fixed_says"]
    fixes += polish(folder, topic, spec)
    if fixes:      # the lines changed, so her actions (tied to words) and the post text must follow
        changed = [t for t in spec["takes"] if t["n"] in {f["n"] for f in fixes}]
        redo = ask_claude(
            "You are the director of a short educational video series. Your rulebook:\n\n" + SKILL
            + "\n\n---\n\nA fact check changed some lines of this episode. Rewrite 'does' for each changed take so every "
              "action is tied to words that are actually in its new line (rulebook section 4), and rewrite the post "
              "description so it agrees with the corrected script.\n\nFull script:\n"
            + "\n".join(f"{t['n']}. {t['says']}" for t in spec["takes"])
            + "\n\nChanged takes (new line, old direction):\n" + json.dumps(
                [{"n": t["n"], "set": t["set"], "says": t["says"], "old_does": t["does"]} for t in changed])
            + "\n\nAnswer with ONLY one JSON object: {\"takes\": [{\"n\": 1, \"does\": \"...\"}], "
              "\"description\": \"two sentences\"}", folder, "opus")
        for r in redo.get("takes", []):
            for t in spec["takes"]:
                if t["n"] == r.get("n") and r.get("does") and not MOOD.search(r["does"]):
                    t["does"] = r["does"]
        if redo.get("description"):
            spec.setdefault("post", {})["description"] = redo["description"]
    spec.update({"topic": topic, "width": W, "height": H, "fact_check": {"fixes": fixes}})
    return spec


def face_of_picture(path):
    r = subprocess.run([UV, "run", str(HERE / "face_check.py"), str(MASTER), str(path)], capture_output=True, text=True, timeout=600)
    lines = [x for x in r.stdout.splitlines() if x.startswith("{")]
    return json.loads(lines[-1]) if lines else {"median": None, "face_height": None}


BODY = """Read the image file {name} in the current folder. It is a start frame for an AI video of a woman talking to camera.
Answer these as plain facts about what is in the picture, not as a judgment of quality:
- surface_in_front: is there any table, desk, counter, bar, railing or other surface or object between her and the camera, or running along the bottom of the frame in front of her body? (true even if it looks natural, e.g. she sits at a table with her hands on it)
- hands_on_object: are her hands resting on or holding anything?
- limb_mistake: extra, missing or fused arms, hands or fingers
- jewelry_on_wrist: a watch or bracelet
Answer with ONLY one JSON object: {{"surface_in_front": true or false, "hands_on_object": true or false, "limb_mistake": true or false, "jewelry_on_wrist": true or false, "note": "one short sentence on what you saw"}}"""


def body_check(picture):
    """Does the still make physical sense (no body inside furniture, sane hands)? A failed check counts as not ok."""
    try:
        v = ask_claude(BODY.format(name=picture.name), picture.parent, "sonnet")
        bad = [k for k in ("surface_in_front", "hands_on_object", "limb_mistake", "jewelry_on_wrist") if v.get(k) is not False]
        return not bad, (", ".join(bad) + ": " + str(v.get("note") or "")) if bad else ""
    except Exception as e:
        return False, f"body check did not run: {e}"[:200]


def make_picture(folder, s):
    """One still of her in this set. Up to 3 Codex attempts; kept only if it is clearly her and close enough."""
    sets = folder / "sets"
    final = sets / f"{s['name']}_{W}x{H}.png"
    if final.exists():
        return json.loads((sets / f"{s['name']}.face.json").read_text()) if (sets / f"{s['name']}.face.json").exists() else {}
    work = sets / "_work"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(MASTER, work / "reference.png")
    best = None
    for attempt in range(1, 4):
        raw = work / f"{s['name']}.png"
        raw.unlink(missing_ok=True)
        try:
            # the prompt goes in on stdin: "-i" takes a list of files and would swallow a prompt argument
            subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(work),
                            "-i", str(work / "reference.png")],
                           input=PICTURE.format(name=s["name"], picture=s["picture"]),
                           capture_output=True, text=True, timeout=420)
        except subprocess.TimeoutExpired:
            continue
        if not raw.exists():
            continue
        sized = work / f"{s['name']}_try{attempt}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf",
                        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", str(sized)], timeout=120)
        face = face_of_picture(sized)
        face["try"] = attempt
        face["body_ok"], face["body_problem"] = body_check(sized)
        good = face["body_ok"] and (face.get("median") or 0) >= 0.85 and (face.get("face_height") or 0) >= 0.22
        rank = lambda f: (bool(f.get("body_ok")), f.get("median") or 0)      # a sane body first, then the closest face
        if best is None or rank(face) > rank(best[1]):
            best = (sized, face)
        if good:
            break
    if best is None:
        raise RuntimeError(f"no picture came back for set {s['name']}")
    if (best[1].get("median") or 0) < 0.75 or (best[1].get("face_height") or 0) < 0.18:
        raise RuntimeError(f"set {s['name']}: best picture is not close enough to her "
                           f"(match {best[1].get('median')}, face height {best[1].get('face_height')})")
    if not best[1].get("body_ok"):
        raise RuntimeError(f"set {s['name']}: every picture had a body mistake ({best[1].get('body_problem')})")
    shutil.copy(best[0], final)
    (sets / f"{s['name']}.face.json").write_text(json.dumps(best[1]))
    return best[1]


def main():
    folder, topic = Path(sys.argv[1]).resolve(), sys.argv[2]
    where = sys.argv[3] if len(sys.argv) > 3 else ""
    (folder / "sets").mkdir(parents=True, exist_ok=True)
    spec_file = folder / "spec.json"
    try:
        spec = json.loads(spec_file.read_text()) if spec_file.exists() else write_spec(folder, topic, where)
        spec_file.write_text(json.dumps(spec, indent=2) + "\n")
        for name in ("desk_front", "desk_side"):
            if not (folder / "sets" / f"{name}_{W}x{H}.png").exists():
                shutil.copy(STOCK / f"{name}_{W}x{H}.png", folder / "sets" / f"{name}_{W}x{H}.png")
        pictures = {s["name"]: make_picture(folder, s) for s in spec["sets"]}
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}))
        return
    print(json.dumps({"ok": True, "title": spec["title"], "takes": len(spec["takes"]), "pictures": pictures,
                      "fact_fixes": spec.get("fact_check", {}).get("fixes", [])}))


if __name__ == "__main__":
    main()
