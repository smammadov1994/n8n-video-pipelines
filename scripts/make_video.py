# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Turn one script into a finished TikTok: her talking (generated on the 5090) under the product video.

    uv run make_video.py <base64 of the video's JSON item> [--max N]   # how the n8n workflow calls it
    uv run make_video.py --json '{"video_id": "...", "script": {...}}'

For each take in the script (a short line she says):
  1. the 5090 generates a ~5 s clip of her saying it (voice baked in)   -> media/<id>/takes/
  2. the clip is transcribed and compared to the line, word by word
  3. wrong words -> generate again with a new seed, up to TRIES times; the best try is kept
Then the takes are trimmed, joined (her.mp4) and stacked under the product video (final.mp4).
A final video is only made when every take passed the word check.

Changing one part: edit that take's "says" in media/<id>/script_v2.json and run again. Takes are
cached by their exact words, so only the edited take is generated again.

Prints one JSON object: {"video_id", "ok", "final", "takes": [...]} or {"ok": false, "error"}.
"""
import base64
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEDIA = HERE.parent / "media"
COMFY = Path.home() / "comfyui-mcp"
HER = Path(os.environ.get("HER_IMAGE", str(HERE.parent / "her" / "her_couch_b_768x1344.png"))).expanduser()
COMPOSE = Path.home() / "Movies/comfyui-mcp/overnight/ugc/compose.py"
TRANSCRIBE = COMFY / "transcribe.py"
TRIES = int(os.environ.get("TAKE_TRIES", "4"))
PASS = float(os.environ.get("TAKE_PASS", "0.97"))   # share of her scripted words heard, in order. 0.97 = every word
                                                    # right for lines up to ~30 words; one wrong word fails the take
WAIT = 15 * 60                                        # longest wait for one clip
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")

STYLE = "couch-v3-verbs"   # part of each take's cache key: change it and every take is generated again
RULES_FILE = HERE.parent / "her" / "rules.txt"   # one rule per line; every bad take earns a new line here

# Prompt = SCENE + what she does + LINE + RULES. Direction style (performance-bible method, adopted
# 2026-11-10): verbs, not feelings. Each take carries its own "does": 2-3 small physical actions tied to
# words of her line. No mood adjectives; they make the model stretch her brows and mouth.
SCENE = ("SCENE: UGC iPhone front-camera footage, vertical, eye level, handheld with only tiny natural sway. "
         "The young woman sits on the arm of her couch exactly as in the first frame: long straight dark hair, "
         "beige ribbed tank top, small gold heart necklace, black clip-on lav mic on her neckline, soft daylight "
         "from the left, pink lamp glow and wooden dining chairs behind her. Her eyes are on the lens. {action}")
ACTIONS = {   # fallback when a take has no "does" of its own
    "hook": "She leans in a few centimeters as she starts. Halfway through the line her eyebrows lift once and settle. After her last word she closes her lips and holds the lens.",
    "reason": "On her first words she points straight up above her head with one finger at the video playing above her and glances up at it, then her eyes come straight back to the lens. After her last word she closes her lips and holds the lens.",
    "buy": "Halfway through the line her head tilts slightly to one side. On her last words she gives one small point upward, then one slow nod, lips closed."}
VOICE = "Quick and warm, in a clear young American woman's voice, about three words per second, she says:"


def build_prompt(line, job, does=None):
    rules = " ".join(r.strip() for r in RULES_FILE.read_text().splitlines() if r.strip()) if RULES_FILE.exists() else ""
    return (SCENE.format(action=(does or "").strip() or ACTIONS.get(job, ACTIONS["hook"]))
            + f' LINE: {VOICE} "{line}"' + f" RULES: {rules} Quiet room tone.")


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
FILLER = {"a", "an", "and", "the", "dollars", "dollar", "bucks"}


def fail(video_id, message, **extra):
    print(json.dumps({"video_id": video_id, "ok": False, "error": message, **extra}))
    sys.exit(0)


def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def words(text):
    """Lower-case words with numbers as digits, so 'twenty-three dollars' and '$23' compare equal."""
    text = text.lower().replace("-", " ").replace(",", "")
    out, num, seen = [], 0, False
    for w in re.findall(r"[a-z']+|\d+", text):
        w = w.replace("'", "")                          # "dune's" and "dunes" sound the same: not a wrong word
        w = re.sub(r"our(s?)$", r"or\1", w)             # neighbours / neighbors
        if w in ONES or w in TENS:
            num += ONES.index(w) if w in ONES else TENS[w]
            seen = True
        elif w == "hundred" and seen:
            num *= 100
        elif w == "thousand" and seen:
            num *= 1000
        else:
            if seen:
                out.append(str(num))
                num, seen = 0, False
            if w and w not in FILLER:
                out.append(w)
    if seen:
        out.append(str(num))
    return out


def score(line, heard):
    """How much of the scripted line was heard, in order, and nothing much extra."""
    a, b = words(line), words(heard)
    if not a or not b:
        return 0.0
    matched = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(min(matched / len(a), matched / len(b)), 3)


def seconds_for(line):
    return min(8.0, max(5.2, len(line.split()) / 3.2 + 0.6))   # 5.2 s is the model's shortest clip


def generate(server, client, line, job, seed, dest, does=None):
    prompt = build_prompt(line.replace('"', "'"), job, does)
    prompt_id, _, _, _ = server._submit(client, prompt, seconds_for(line), 6, seed, 768, 1344, str(HER),
                                        None, None, front=True)
    deadline, lost = time.monotonic() + WAIT, 0
    while True:
        st = server._status(client, prompt_id, download=True)
        if st["state"] == "done":
            files = [f for f in st.get("local_files", []) if f.endswith(".mp4")]
            if not files:
                raise RuntimeError("5090 finished but returned no video")
            shutil.move(files[0], dest)
            return
        if st["state"] == "error":
            raise RuntimeError(f"5090 job failed: {st.get('error') or ''}"[:300])
        # "unknown" also shows for a moment while a job moves between queue and history: only give
        # up when it stays unknown for a while.
        lost = lost + 1 if st["state"] == "unknown" else 0
        if lost >= 8:
            raise RuntimeError("5090 lost the job (not in its queue or history). ComfyUI may have restarted.")
        if time.monotonic() > deadline:
            raise RuntimeError("5090 took longer than 15 minutes for one clip")
        time.sleep(4)


def heard_in(clip):
    out = clip.with_suffix(".transcript.json")
    if not out.exists():
        r = run(["uv", "run", str(TRANSCRIBE), str(clip), str(out)], 900)
        if not out.exists():
            raise RuntimeError(f"transcribe failed: {(r.stderr or '').strip()[-200:]}")
    data = json.loads(out.read_text())
    end = max((s["end"] for s in data.get("segments", [])), default=0)
    return data.get("text", "").strip(), end


FACE_CHECK = HERE / "face_check.py"
FACE_MASTER = Path(os.environ.get("HER_MASTER", str(HERE.parent / "her" / "her_couch_b_1080x1920.png"))).expanduser()
# Face match against the master picture, 0 = stranger, 1 = identical. Marks set from the owner's own
# calls on 2026-11-09: takes he accepted scored 0.68-0.83 (typical frame), the trail-walk take he
# said looked like someone else scored 0.42. Move them as he judges more clips.
FACE_PASS = float(os.environ.get("FACE_PASS", "0.60"))     # typical frame at or above this: her
FACE_FLAG = float(os.environ.get("FACE_FLAG", "0.66"))     # passes but below this: flagged for a look
FACE_FLOOR = float(os.environ.get("FACE_FLOOR", "0.42"))   # any single frame below this: not her


def face_of(clip):
    """{"median", "lowest", "face_height", "verdict": her | look | not_her | no_face} for one clip."""
    out = Path(str(clip)[:-4] + ".face.json")
    if out.exists():
        d = json.loads(out.read_text())
    else:
        r = run(["uv", "run", str(FACE_CHECK), str(FACE_MASTER), str(clip)], 600)
        lines = [x for x in r.stdout.splitlines() if x.startswith("{")]
        if not lines:
            raise RuntimeError(f"face check failed: {(r.stderr or '').strip()[-200:]}")
        d = json.loads(lines[-1])
        out.write_text(json.dumps(d))
    if d["median"] is None:
        verdict = "no_face"
    elif d["median"] < FACE_PASS or d["lowest"] < FACE_FLOOR:
        verdict = "not_her"
    else:
        verdict = "look" if d["median"] < FACE_FLAG else "her"
    return {"median": d["median"], "lowest": d["lowest"], "face_height": d["face_height"],
            "face_x": d.get("face_x"), "verdict": verdict}


def make_take(server, client, folder, n, line, job, does=None):
    """Best clip of her saying `line`. Cached by the exact words."""
    key = hashlib.sha1(f"{STYLE}|{line}|{does or ''}".encode()).hexdigest()[:8]
    record = folder / f"take{n}_{key}.json"
    if record.exists():
        return json.loads(record.read_text())
    tries, started = [], time.monotonic()
    for attempt in range(1, TRIES + 1):
        clip = folder / f"take{n}_{key}_try{attempt}.mp4"
        if not clip.exists():
            generate(server, client, line, job, 1000 * n + attempt * 7919 + int(key, 16) % 100000, clip, does)
        heard, end = heard_in(clip)
        tries.append({"try": attempt, "file": str(clip), "heard": heard, "match": score(line, heard), "speech_end": end})
        tries[-1]["face"] = face_of(clip) if tries[-1]["match"] >= PASS else None
        tries[-1]["good"] = tries[-1]["match"] >= PASS and tries[-1]["face"]["verdict"] in ("her", "look")
        if tries[-1]["good"]:
            break
    best = max(tries, key=lambda t: (t["good"], t["match"], (t["face"] or {}).get("median") or 0))
    result = {"n": n, "says": line, "job": job, "passed": best["good"], "match": best["match"], "face": best["face"],
              "heard": best["heard"], "file": best["file"], "speech_end": best["speech_end"],
              "tries": len(tries), "all_tries": tries, "seconds_spent": round(time.monotonic() - started)}
    if result["passed"]:          # a failed take is not cached, so the next run tries again
        record.write_text(json.dumps(result, indent=2))
    return result


def join(takes, dest):
    """Trim each take just after her last word and join them into one clip."""
    args, parts = [], []
    for i, t in enumerate(takes):
        length = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            t["file"]]).stdout.strip())
        cut = min(length, t["speech_end"] + 0.35) if t["speech_end"] > 1 else length
        args += ["-i", t["file"]]
        parts.append(f"[{i}:v]trim=0:{cut:.2f},setpts=PTS-STARTPTS,fps=24[v{i}];"
                     f"[{i}:a]atrim=0:{cut:.2f},asetpts=PTS-STARTPTS,afade=t=out:st={max(cut - 0.08, 0):.2f}:d=0.08[a{i}];")
    chain = "".join(parts) + "".join(f"[v{i}][a{i}]" for i in range(len(takes))) + f"concat=n={len(takes)}:v=1:a=1[v][a]"
    r = run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", chain, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", str(dest)])
    if r.returncode:
        raise RuntimeError(f"joining takes failed: {r.stderr.strip()[-300:]}")


def main():
    args = sys.argv[1:]
    limit = None
    if "--max" in args:
        i = args.index("--max")
        limit = int(args[i + 1])
        del args[i:i + 2]
    if len(args) == 2 and args[0] == "--json":
        item = json.loads(args[1])
    elif len(args) == 1:
        item = json.loads(base64.b64decode(args[0]))
    else:
        sys.exit(__doc__)
    vid = str(item.get("video_id") or "")
    if not re.fullmatch(r"\d{5,25}", vid):
        fail(vid, "bad video_id")
    if limit is not None and int(item.get("rank") or 1) > limit:
        fail(vid, f"skipped: only the first {limit} video(s) per run get a video (Settings: videos)", skipped=True)
    folder = MEDIA / vid
    saved = folder / "script_v2.json"      # the saved copy wins, so hand edits to a take are used
    script = json.loads(saved.read_text()) if saved.exists() else item.get("script")
    takes_in = (script or {}).get("takes") or []
    if not takes_in:
        fail(vid, "no script takes for this video")
    top = folder / "video.mp4"
    if not top.exists():
        fail(vid, "product video was not downloaded")
    if not HER.exists():
        fail(vid, f"her picture is missing: {HER}")
    takes_dir = folder / "takes"
    takes_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(COMFY))
    started = time.monotonic()
    try:
        import server
        with server._client() as client:
            takes = [make_take(server, client, takes_dir, int(t.get("n") or i + 1), t["says"].strip(), t.get("job") or "", t.get("does"))
                     for i, t in enumerate(takes_in)]
    except Exception as e:  # network, 5090 down, transcribe: report it, don't crash the n8n run
        fail(vid, f"{type(e).__name__}: {e}"[:400])
    slim = [{k: t.get(k) for k in ("n", "says", "heard", "match", "face", "passed", "tries", "file")} for t in takes]
    bad = [t["n"] for t in takes if not t["passed"]]
    if bad:
        fail(vid, f"take {', '.join(map(str, bad))} still had wrong words or the wrong face after {TRIES} tries; no final video made. "
                  "Run again to retry, or reword that take in script_v2.json.", takes=slim)
    try:
        her = folder / "her.mp4"
        join(takes, her)
        final = folder / "final.mp4"
        r = run(["uv", "run", str(COMPOSE), "--top", str(top), "--her", str(her), "--out", str(final),
                 "--caption", (script.get("overlay_caption") or "")[:32]])
        if r.returncode or not final.exists():
            raise RuntimeError(f"compose failed: {(r.stderr or r.stdout).strip()[-300:]}")
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as e:
        fail(vid, str(e)[:400], takes=slim)
    print(json.dumps({"video_id": vid, "ok": True, "final": str(final), "her": str(her), "takes": slim,
                      "seconds_spent": round(time.monotonic() - started)}))


if __name__ == "__main__":
    main()
