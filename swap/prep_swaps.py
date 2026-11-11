#!/usr/bin/env python3
"""Pick Kaiyros TikTok Shop videos that suit the person swap, and prepare each one for it.

    prep_swaps.py <top|trending|latest> <how many to look at> [how many NEW ones to keep] [how deep into the list]

Per video: download, look at 6 frames (Claude) to decide if it suits the swap, transcribe, have HER voice
(Fish, same voice as every episode) say the same words placed at the same moments, cut to the first ~20 s at a
sentence end, and write swap/ready/<id>.mp4 (720p, her voice as the soundtrack) + <id>.json.
Suits the swap = one person on camera, face clearly visible and talking, product held or shown close,
no word-by-word captions burned in, not an outfit/clothing video. the owner (2026-11-11): the creators are in the
Kaiyros program and have agreed to this.
"""
import json, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import understand as u
READY = HERE / "ready"; READY.mkdir(exist_ok=True)
DISCOVER = ROOT.parent / "discover-download" / "discover.py"
VOICE, SPEED, TONE = "b545c585f631496c914815291da4e893", 0.95, "(relaxed, friendly, smiling) "
MAX_SECONDS = 20.0

SCREEN = """Read frame_1.jpg to frame_6.jpg in the current folder: six frames, in time order, from one short product video.
Answer as plain facts:
- one_person: exactly one person appears on camera across the frames (hands-only shots count as no person)
- face_talking: that person's face is clearly visible, facing the camera, in at least five of the six frames
- product_in_hand: they hold or show a product near their face or chest in at least two frames
- word_captions: captions that follow the speech word by word are burned into the picture (a single static title does not count)
- outfit_video: the product being shown is the clothing the person is wearing
- lying_or_far: the person is lying down, or is small/far from the camera in most frames
Answer with ONLY one JSON object: {"one_person": true or false, "face_talking": true or false, "product_in_hand": true or false, "word_captions": true or false, "outfit_video": true or false, "lying_or_far": true or false, "note": "one short sentence"}"""


def fish(text, dest):
    key = json.loads((Path.home() / "comfyui-mcp/connection.json").read_text())["fish_api_key"]
    body = json.dumps({"text": TONE + text, "format": "wav", "prosody": {"speed": SPEED}, "reference_id": VOICE})
    for attempt in range(5):
        r = subprocess.run(["curl", "-s", "-m", "180", "-o", str(dest), "-w", "%{http_code}", "-X", "POST", "https://api.fish.audio/v1/tts",
                            "-H", f"Authorization: Bearer {key}", "-H", "Content-Type: application/json", "-H", "model: s2.1-pro-free", "-d", body],
                           capture_output=True, text=True)
        if r.stdout.strip() == "200" and dest.exists() and dest.stat().st_size > 2000:
            return
        time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"Fish refused: {r.stdout}")


def seconds(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)


def prepare(vid, info, begin=0.0):
    """begin = seconds into the video where the clip starts (used to skip an opening caption)."""
    folder = u.MEDIA / vid; folder.mkdir(parents=True, exist_ok=True)
    out = READY / f"{vid}.mp4"
    verdict_file = folder / "swap_screen.json"
    if out.exists() and not begin:
        return {"id": vid, "kept": True, "why": "already prepared"}
    u.download(f"https://www.tiktok.com/@_/video/{vid}", folder / "video.mp4")
    dur = u.duration(folder / "video.mp4")
    if dur < 6:
        return {"id": vid, "kept": False, "why": "shorter than 6 s"}
    if verdict_file.exists():
        v = json.loads(verdict_file.read_text())
    else:
        work = folder / "swap_frames"; work.mkdir(exist_ok=True)
        span = min(dur, MAX_SECONDS)
        for i in range(6):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{0.4 + (span - 1) * i / 5:.2f}", "-i", str(folder / "video.mp4"), "-frames:v", "1",
                            "-vf", "scale=480:-2", "-q:v", "4", str(work / f"frame_{i + 1}.jpg")])
        v = u.ask_claude(SCREEN, work, "sonnet")
        verdict_file.write_text(json.dumps(v, indent=2))
    good = v.get("one_person") is True and v.get("face_talking") is True and v.get("word_captions") is False and v.get("outfit_video") is False and v.get("lying_or_far") is False
    if not good:
        return {"id": vid, "kept": False, "why": "does not suit the swap: " + str(v.get("note"))[:120]}
    t = u.transcribe(folder / "video.mp4", folder / "transcript.json")
    segs = [dict(s, start=s["start"] - begin, end=s["end"] - begin) for s in t.get("segments", [])
            if s["text"].strip() and begin - 0.05 <= s["start"] < begin + MAX_SECONDS]
    if (t.get("language") or "en") != "en" or len(" ".join(s["text"] for s in segs).split()) < 12:
        return {"id": vid, "kept": False, "why": "no clear English speech in the first 20 s"}
    while segs and segs[-1]["end"] > MAX_SECONDS + 2.5:
        segs.pop()
    if not segs:
        return {"id": vid, "kept": False, "why": "first sentence runs past 20 s"}
    # her voice says each sentence, starting where the creator started it; sped up a little only if it would run into the next one
    voice_dir = folder / "her_voice"; voice_dir.mkdir(exist_ok=True)
    parts, cursor = [], 0.0
    for i, s in enumerate(segs):
        wav = voice_dir / f"seg_{int((s['start'] + begin) * 100)}.wav"
        if not wav.exists():
            fish(s["text"].strip(), wav)
        length = seconds(wav)
        start = max(s["start"], cursor)
        room = (segs[i + 1]["start"] if i + 1 < len(segs) else start + length) - start
        tempo = min(1.25, max(1.0, length / max(room, 0.5)))
        parts.append((wav, start, tempo))
        cursor = start + length / tempo + 0.08
    total = round(min(dur - begin, cursor + 0.4), 2)
    if total < 7:
        return {"id": vid, "kept": False, "why": "less than 7 s left after the caption"}
    fc = "".join(f"[{i + 1}:a]atempo={tempo:.3f},adelay={int(start * 1000)}|{int(start * 1000)}[a{i}];" for i, (_, start, tempo) in enumerate(parts))
    fc += "".join(f"[a{i}]" for i in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0,apad[a];[0:v]scale=720:-2,fps=24[v]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{begin:.2f}", "-t", str(total), "-i", str(folder / "video.mp4")]
    for wav, _, _ in parts:
        cmd += ["-i", str(wav)]
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(total), "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
            "-maxrate", "2800k", "-bufsize", "5600k", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not out.exists():
        return {"id": vid, "kept": False, "why": "cut failed: " + r.stderr.strip()[-160:]}
    meta = {"id": vid, "seconds": total, "words": " ".join(s["text"].strip() for s in segs), "product": (info.get("product") or {}).get("title"),
            "creator": (info.get("creator") or {}).get("display_name"), "views": (info.get("metrics") or {}).get("views_total"), "screen": v, "starts_at": begin,
            "size_mb": round(out.stat().st_size / 1e6, 1)}
    (READY / f"{vid}.json").write_text(json.dumps(meta, indent=2))
    return {"id": vid, "kept": True, "why": f"{total} s, {meta['size_mb']} MB, {str(meta['product'])[:50]}"}


def main():
    which, look, keep = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 99
    pool = int(sys.argv[4]) if len(sys.argv) > 4 else max(look, 200)      # how deep into the Kaiyros list to reach
    r = subprocess.run([str(DISCOVER), which, "-n", str(look), "--pool", str(pool), "--stdout-json"], capture_output=True, text=True, timeout=900)
    videos = json.loads(r.stdout)
    kept = 0                                                               # NEW clips prepared in this run (not the ones already in ready/)
    for info in videos:
        if kept >= keep:
            break
        vid = str(info["id"])
        try:
            res = prepare(vid, info)
        except Exception as e:
            res = {"id": vid, "kept": False, "why": f"{type(e).__name__}: {e}"[:160]}
        if res["kept"] and res["why"] != "already prepared":
            kept += 1
        print(json.dumps(res), flush=True)
    print(json.dumps({"done": True, "ready": len(list(READY.glob('*.mp4')))}), flush=True)


if __name__ == "__main__":
    main()
