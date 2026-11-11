#!/usr/bin/env python3
"""Make every prepared clip free of text over the picture (the swap garbles text; the owner adds text in CapCut).

    text_screen.py     for each swap/ready/<id>.mp4 not checked yet: look at one frame per second of the original video.
No overlay text -> keep. Text only at the start -> rebuild the clip to begin at the first sentence after the text is gone.
Text later on or all the way through -> move to swap/rejected_text/."""
import json, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts")); sys.path.insert(0, str(HERE))
import understand as u
import prep_swaps as ps
READY, OUT = HERE / "ready", HERE / "rejected_text"; OUT.mkdir(exist_ok=True)
N = 12
ASK = """Read s01.jpg to s%02d.jpg in the current folder: one frame per second from a short video, in order (s01 = second 0.5, s02 = second 1.5, and so on).
For each frame decide whether any text is drawn OVER the picture: a title, caption, subtitle, sticker text, emoji caption, disclaimer or watermark. Text printed on a real object in the scene (a product label, a shirt, a sign) does not count.
Answer with ONLY one JSON object: {"frames_with_text": [numbers of the frames that have overlay text, e.g. 1, 2], "note": "what the text says"}""" % N
def check(clip):
    vid = clip.stem; meta_file = READY / f"{vid}.json"; meta = json.loads(meta_file.read_text())
    if meta.get("text_checked"): return vid, "kept", "(checked before)"
    video = u.MEDIA / vid / "video.mp4"; work = u.MEDIA / vid / "text_frames2"; work.mkdir(parents=True, exist_ok=True)
    for i in range(N):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{i + 0.5:.1f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", str(work / f"s{i + 1:02d}.jpg")])
    have = sorted(int(p.stem[1:]) for p in work.glob("s*.jpg"))
    v = u.ask_claude(ASK, work, "sonnet")
    bad = sorted(int(x) for x in v.get("frames_with_text", []) if str(x).isdigit() and int(x) in have)
    note = str(v.get("note"))[:120]
    if not bad:
        meta["text_checked"] = True; meta_file.write_text(json.dumps(meta, indent=2)); return vid, "kept", "no text on screen"
    last = bad[-1]
    if last > 6 or last >= len(have):
        for f in READY.glob(f"{vid}.*"): shutil.move(str(f), OUT / f.name)
        return vid, "dropped", f"text until second {last}: {note}"
    t = json.loads((u.MEDIA / vid / "transcript.json").read_text())
    starts = [s["start"] for s in t.get("segments", []) if s["text"].strip() and s["start"] >= last + 0.3]
    if not starts:
        for f in READY.glob(f"{vid}.*"): shutil.move(str(f), OUT / f.name)
        return vid, "dropped", "no sentence starts after the caption"
    for f in READY.glob(f"{vid}.*"): f.unlink()
    r = ps.prepare(vid, {"product": {"title": meta.get("product")}, "creator": {"display_name": meta.get("creator")}, "metrics": {"views_total": meta.get("views")}}, begin=round(starts[0] - 0.15, 2))
    if r["kept"]:
        m = json.loads(meta_file.read_text()); m["text_checked"] = True; m["skipped_caption"] = note; meta_file.write_text(json.dumps(m, indent=2))
        return vid, "kept", f"starts at {starts[0]:.1f} s, after the caption; {r['why']}"
    return vid, "dropped", r["why"]
if __name__ == "__main__":
    for f in list(OUT.glob("*")):                      # give earlier rejects another chance under the new rule
        if f.suffix in (".mp4", ".json") and "--retry" in sys.argv: shutil.move(str(f), READY / f.name)
    with ThreadPoolExecutor(4) as pool:
        for vid, verdict, why in pool.map(check, sorted(READY.glob("*.mp4"))):
            print(json.dumps({"id": vid, "result": verdict, "why": why}), flush=True)
