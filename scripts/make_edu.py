# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Make a YouTuber-style explainer of her from a spec: several sets, camera angles, cutaways.

    uv run make_edu.py <folder with spec.json and sets/>

spec.json: title, width, height, voice, takes[]. Each take: n, set (a picture in sets/<set>_<w>x<h>.png
that the clip starts from), says (her line), scene (camera + what she does), optional cutaway
{name, from, prompt}: footage with no people that covers her picture from `from` seconds to the end
of the take while her voice carries on.

Each take is generated on the 5090, transcribed, compared to the line word for word and retried
(new seed) up to TRIES times; takes are cached by set + scene + words, so editing one take only
remakes that take. A final video is only assembled when every take passed.

Prints one JSON object with the result.
"""
import hashlib
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec_ = importlib.util.spec_from_file_location("make_video", HERE / "make_video.py")
mv = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(mv)

# Direction style (from the performance-bible method, adopted 2026-11-10): the camera sees verbs, not
# feelings. A take's "scene" says where the camera is and then what she physically does, as 2-3 small
# actions each tied to specific words of her line (a tap, a glance, one eyebrow lift that settles, a
# half-beat pause). No adjectives like energetic, charismatic, playful: the model answers those with
# stretched brows and wide grins, which is where her face drifted.
RULES = ("One continuous take, no jump cuts, no zoom. She says the line exactly once, word for word, adds "
         "nothing and repeats nothing. Her face keeps exactly the proportions of the first frame. Hands empty "
         "with five natural fingers. She keeps the same beige ribbed tank top, gold heart necklace and black "
         "clip-on mic with its cable. The same place and scenery stay behind her from the first frame to the last. "
         "No text on screen, no captions, no music.")
VOICE = "Quick and warm, in a clear young American woman's voice, about three words per second, she says:"


def render(server, client, prompt, seconds, seed, w, h, first_image, dest, last_image=None, steps=6):
    """Queue one clip on the 5090 and wait for the file. With last_image the clip must also END on
    that picture (first+last frame workflow), which pins her face at both ends of the take."""
    prompt_id, _, _, _ = server._submit(client, prompt, seconds, steps, seed, w, h, first_image, last_image, None, front=True)
    deadline, lost = time.monotonic() + mv.WAIT, 0
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
        lost = lost + 1 if st["state"] == "unknown" else 0
        if lost >= 8:
            raise RuntimeError("5090 lost the job. ComfyUI may have restarted.")
        if time.monotonic() > deadline:
            raise RuntimeError("5090 took longer than 15 minutes for one clip")
        time.sleep(4)


def make_take(server, client, folder, spec, t):
    line, w, h = t["says"].strip(), spec["width"], spec["height"]
    image = folder / "sets" / f"{t['set']}_{w}x{h}.png"
    if not image.exists():
        raise RuntimeError(f"set picture missing: {image.name}")
    anchor = bool(t.get("anchor_end", spec.get("anchor_end")))   # end the take on the same picture it starts from
    steps = int(t.get("steps", spec.get("steps", 6)))
    mode = f"|end-anchored|{steps}" if anchor or steps != 6 else ""
    key = hashlib.sha1(f"{t['set']}|{t['scene']}|{line}{mode}".encode()).hexdigest()[:8]
    takes = folder / "takes"
    takes.mkdir(exist_ok=True)
    record = takes / f"take{t['n']}_{key}.json"
    if record.exists() and "face" in json.loads(record.read_text()):   # records from before the face check are re-checked
        return json.loads(record.read_text())
    ending = (" After her last word she returns to exactly the pose and calm expression of the first frame and holds it."
              if anchor else "")
    prompt = f"SCENE: {t['scene']}{ending} LINE: {spec.get('voice', VOICE)} \"{line}\" RULES: {spec.get('rules', RULES)} Quiet natural ambience."
    tries, started = [], time.monotonic()
    for attempt in range(1, mv.TRIES + 1):
        clip = takes / f"take{t['n']}_{key}_try{attempt}.mp4"
        if not clip.exists():
            render(server, client, prompt, mv.seconds_for(line) + (0.9 if anchor else 0), 500 * t["n"] + attempt * 7919 + int(key, 16) % 100000,
                   w, h, str(image), clip, last_image=str(image) if anchor else None, steps=steps)
        heard, end = mv.heard_in(clip)
        tries.append({"try": attempt, "file": str(clip), "heard": heard, "match": mv.score(line, heard), "speech_end": end})
        words_ok = tries[-1]["match"] >= mv.PASS
        tries[-1]["face"] = mv.face_of(clip) if words_ok else None
        tries[-1]["good"] = words_ok and tries[-1]["face"]["verdict"] in ("her", "look")
        if tries[-1]["good"]:
            break
        if not words_ok and len(tries) >= 2 and tries[-1]["heard"] == tries[-2]["heard"]:
            break   # same wrong word twice: she can't say this line, it needs rewording, not more tries
    best = max(tries, key=lambda x: (x["good"], x["match"], (x["face"] or {}).get("median") or 0))
    result = {"n": t["n"], "set": t["set"], "says": line, "passed": best["good"], "match": best["match"], "face": best["face"],
              "heard": best["heard"], "file": best["file"], "speech_end": best["speech_end"], "tries": len(tries),
              "seconds_spent": round(time.monotonic() - started)}
    if result["passed"] or spec.get("keep_failed"):   # unattended runs keep the best try so a retry doesn't redo it
        record.write_text(json.dumps(result, indent=2))
    return result


def make_cutaway(server, client, folder, spec, c):
    key = hashlib.sha1(c["prompt"].encode()).hexdigest()[:8]
    clip = folder / "takes" / f"cutaway_{c['name']}_{key}.mp4"
    if not clip.exists():
        render(server, client, c["prompt"], 5.2, int(key, 16) % 100000, spec["width"], spec["height"], None, clip)
    return clip


def length(path):
    return float(mv.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout.strip())


def assemble(folder, spec, takes, cutaways):
    """Trim each take after her last word, lay cutaways over the picture, join, scale to 1080p."""
    parts = []
    for t in takes:
        cut = min(length(t["file"]), t["speech_end"] + 0.3) if t["speech_end"] > 1 else length(t["file"])
        part = folder / "takes" / f"part{t['n']}.mp4"
        cover = cutaways.get(t["n"])
        if cover and cover["from"] < cut - 0.8:
            start = cover["from"]
            fc = (f"[0:v]trim=0:{start:.2f},setpts=PTS-STARTPTS,fps=24[a];"
                  f"[1:v]trim=0.3:{0.3 + cut - start:.2f},setpts=PTS-STARTPTS,fps=24,scale={spec['width']}:{spec['height']}[b];"
                  f"[a][b]concat=n=2:v=1:a=0[v];[0:a]atrim=0:{cut:.2f},asetpts=PTS-STARTPTS[au]")
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", t["file"], "-i", str(cover["file"]), "-filter_complex", fc]
        else:
            fc = (f"[0:v]trim=0:{cut:.2f},setpts=PTS-STARTPTS,fps=24[v];[0:a]atrim=0:{cut:.2f},asetpts=PTS-STARTPTS[au]")
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", t["file"], "-filter_complex", fc]
        r = mv.run(cmd + ["-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(part)])
        if r.returncode:
            raise RuntimeError(f"take {t['n']} edit failed: {r.stderr.strip()[-300:]}")
        parts.append(part)
    args = [x for p in parts for x in ("-i", str(p))]
    n = len(parts)
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v0][a0];[v0]scale=1920:-2,format=yuv420p[v];[a0]loudnorm=I=-14:TP=-1.5[a]"
    final = folder / "final.mp4"
    r = mv.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
                "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    if r.returncode:
        raise RuntimeError(f"joining failed: {r.stderr.strip()[-300:]}")
    return final


def main():
    folder = Path(sys.argv[1]).resolve()
    spec = json.loads((folder / "spec.json").read_text())
    sys.path.insert(0, str(mv.COMFY))
    started = time.monotonic()
    try:
        import server
        with server._client() as client:
            takes = [make_take(server, client, folder, spec, t) for t in spec["takes"]]
            cutaways = {t["n"]: {"file": make_cutaway(server, client, folder, spec, t["cutaway"]), "from": t["cutaway"]["from"]}
                        for t in spec["takes"] if t.get("cutaway")}
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:400]}))
        return
    slim = [{k: t.get(k) for k in ("n", "set", "says", "heard", "match", "face", "passed", "tries", "seconds_spent")} for t in takes]
    bad = [t["n"] for t in takes if not t["passed"]]
    if bad:
        print(json.dumps({"ok": False, "error": f"take {bad} still had wrong words or the wrong face after {mv.TRIES} tries", "takes": slim}))
        return
    try:
        final = assemble(folder, spec, takes, cutaways)
    except RuntimeError as e:
        print(json.dumps({"ok": False, "error": str(e), "takes": slim}))
        return
    print(json.dumps({"ok": True, "final": str(final), "seconds": round(length(final), 1), "takes": slim,
                      "seconds_spent": round(time.monotonic() - started)}))


if __name__ == "__main__":
    main()
