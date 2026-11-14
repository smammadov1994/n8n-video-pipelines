#!/usr/bin/env python3
"""Swap ONE video the person supplies, with ANY person or character they supply. (swap_job.py is the batch
version for Kaiyros lists and our own presenter.)

    swap_one.py prepare <job> --video clip.mp4 --person avatar.png --rights own|agreed
                              [--voice keep|new] [--voice-id FISH_ID] [--seconds 20] [--force]
    swap_one.py send <job>       upload the prepared clip and the person's picture to the swap GPU
    swap_one.py collect <job>    bring the finished swap back as jobs/<job>/swapped.mp4
    swap_one.py status <job>

prepare  looks at six frames to see whether the video suits a swap (one person, face to camera and talking,
         no word-by-word captions, not an outfit video), cuts it to at most 20 seconds at 720 px wide, and
         sets the soundtrack: --voice keep leaves the original voice, --voice new has a library voice
         (--voice-id, default the presenter's) say the same words at the same moments.
--rights is required: "own" (the video is the person's own) or "agreed" (its creator agreed to this).
         Anything else is refused. The picture must be of someone who agreed too, or of a made-up character.

A job is a folder in swap/jobs/ (or in SWAP_HOME, one per user of a UI). The swap GPU is reached through
~/comfyui-mcp/swap_connection.json (the owner runs `python3 set_5090.py --swap`); it must run box/queue.sh
and box/run_swap.py from this repository, which use the picture sent with the job instead of the
presenter's when there is one. Each step prints ONE JSON line and always exits 0.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JOBS = Path(os.environ.get("SWAP_HOME") or HERE / "jobs")
CONN = Path.home() / "comfyui-mcp" / "swap_connection.json"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

WHY = {"one_person": "there is not exactly one person on camera",
       "face_talking": "the person's face is not clearly visible and facing the camera most of the time",
       "word_captions": "captions that follow the speech are burned into the picture; they come out garbled",
       "outfit_video": "it is an outfit video; the swapped person keeps their own clothes",
       "lying_or_far": "the person is lying down or far from the camera"}


def say(**out):
    print(json.dumps(out, ensure_ascii=False))


def folder_of(job):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", job or ""):
        raise ValueError('a job name is lower-case letters, digits, - and _, for example "bottle-remake"')
    return JOBS / job


def tag_of(folder):
    """The job's name on the GPU. The folder's path is mixed in, so two users with a job of the same name do not collide."""
    return f"{folder.name}_{hashlib.md5(str(folder.resolve()).encode()).hexdigest()[:6]}"


def run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def prepare(o):
    import prep_swaps as ps          # the frame questions, the voice call and the shared helpers
    import understand as u
    if o.rights not in ("own", "agreed"):
        return say(ok=False, error='say whose video this is: --rights own (your own video) or --rights agreed (its creator agreed to the swap)')
    video, person = Path(o.video).expanduser(), Path(o.person).expanduser()
    for p in (video, person):
        if not p.exists():
            return say(ok=False, error=f"no file at {p}")
    folder = folder_of(o.job)
    folder.mkdir(parents=True, exist_ok=True)
    dur = u.duration(video)
    if dur < 4:
        return say(ok=False, error="the video is shorter than 4 seconds")
    span = min(dur, float(o.seconds))
    frames = folder / "frames"
    frames.mkdir(exist_ok=True)
    for i in range(6):
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{0.4 + (span - 1) * i / 5:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", "scale=480:-2", "-q:v", "4", str(frames / f"frame_{i + 1}.jpg")])
    v = u.ask_claude(ps.SCREEN, frames, "sonnet")
    (folder / "screen.json").write_text(json.dumps(v, indent=1))
    bad = [WHY[k] for k, want in (("one_person", True), ("face_talking", True), ("word_captions", False), ("outfit_video", False), ("lying_or_far", False))
           if v.get(k) is not want]
    if bad and not o.force:
        return say(ok=False, suits_a_swap=False, why=bad, note=v.get("note"),
                   error="this video is unlikely to swap well; add --force to try anyway")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(person), "-vf", "scale='min(1024,iw)':-2", str(folder / "person.png")], 120)
    if not (folder / "person.png").exists():
        return say(ok=False, error="the person's picture could not be read")
    out, words = folder / "source.mp4", ""
    base = ["ffmpeg", "-y", "-loglevel", "error", "-t", f"{span:.2f}", "-i", str(video)]
    video_out = ["-c:v", "libx264", "-crf", "23", "-preset", "veryfast", "-maxrate", "2800k", "-bufsize", "5600k"]
    if o.voice == "new":
        t = u.transcribe(video, folder / "transcript.json")
        segs = [s for s in t.get("segments", []) if s["text"].strip() and s["start"] < span]
        while segs and segs[-1]["end"] > span + 2.5:
            segs.pop()
        if len(" ".join(s["text"] for s in segs).split()) < 4:
            return say(ok=False, error="no clear speech was heard to say again; use --voice keep")
        if o.voice_id:
            ps.VOICE = o.voice_id
        parts, cursor = [], 0.0
        for i, s in enumerate(segs):                         # each sentence starts where it started; sped up a little only if it would run into the next
            wav = folder / f"voice_{i}.wav"
            if not wav.exists():
                ps.fish(s["text"].strip(), wav)
            length = ps.seconds(wav)
            start = max(s["start"], cursor)
            room = (segs[i + 1]["start"] if i + 1 < len(segs) else start + length) - start
            tempo = min(1.25, max(1.0, length / max(room, 0.5)))
            parts.append((wav, start, tempo))
            cursor = start + length / tempo + 0.08
        span = round(min(dur, cursor + 0.4), 2)
        fc = "".join(f"[{i + 1}:a]atempo={tempo:.3f},adelay={int(start * 1000)}|{int(start * 1000)}[a{i}];" for i, (_, start, tempo) in enumerate(parts))
        fc += "".join(f"[a{i}]" for i in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0,apad[a];[0:v]scale=720:-2,fps=24[v]"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-t", str(span), "-i", str(video)]
        for wav, _, _ in parts:
            cmd += ["-i", str(wav)]
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(span), *video_out, "-c:a", "aac", "-b:a", "128k", "-ar", "44100", str(out)]
        words = " ".join(s["text"].strip() for s in segs)
    else:
        cmd = base + ["-vf", "scale=720:-2,fps=24", *video_out, "-c:a", "aac", "-b:a", "128k", "-ar", "44100", str(out)]
    r = run(cmd, 900)
    if r.returncode or not out.exists():
        return say(ok=False, error="cutting the video failed: " + r.stderr.strip()[-200:])
    size = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)]).stdout.strip()
    (folder / "job.json").write_text(json.dumps({"job": o.job, "tag": tag_of(folder), "rights": o.rights, "voice": o.voice, "seconds": round(span, 2),
                                                  "size": size, "words": words, "screen": v, "prepared": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
    say(ok=True, job=o.job, seconds=round(span, 2), size=size, voice=o.voice, suits_a_swap=not bad, warnings=bad, note=v.get("note"),
        source=str(out), person=str(folder / "person.png"), minutes_to_swap=round(span * 0.65, 1))


def connection():
    if not CONN.exists():
        return None
    c = json.loads(CONN.read_text())
    return c["url"].rstrip("/"), c["token"]


def curl(args, timeout=900):
    return run(["curl", "-s", "-m", str(timeout), *args], timeout + 30)


def send(o):
    folder = folder_of(o.job)
    if not (folder / "source.mp4").exists():
        return say(ok=False, error="prepare this job first")
    c = connection()
    if not c:
        return say(ok=False, error=f"no swap GPU is connected ({CONN} does not exist). The owner copies the GPU's ComfyUI link and runs: python3 set_5090.py --swap")
    url, tok = c
    tag = tag_of(folder)
    for path, name in ((folder / "person.png", f"c_{tag}.png"), (folder / "source.mp4", f"q_{tag}.mp4")):   # the picture first: the queue starts on the clip
        r = curl(["-o", "/dev/null", "-w", "%{http_code}", "-H", f"Authorization: Bearer {tok}", "-F", f"image=@{path};filename={name}", "-F", "overwrite=true", f"{url}/upload/image"])
        if r.stdout.strip() != "200":
            return say(ok=False, error=f"the GPU refused {name} (answer {r.stdout.strip() or 'none'})")
    (folder / "sent").write_text(time.strftime("%Y-%m-%d %H:%M"))
    job = json.loads((folder / "job.json").read_text())
    say(ok=True, job=o.job, sent=True, minutes_to_swap=round(job["seconds"] * 0.65, 1))


def collect(o):
    folder = folder_of(o.job)
    out = folder / "swapped.mp4"
    if out.exists():
        return say(ok=True, job=o.job, finished=True, video=str(out))
    if not (folder / "sent").exists():
        return say(ok=False, error="this job has not been sent yet")
    c = connection()
    if not c:
        return say(ok=False, error=f"no swap GPU is connected ({CONN} does not exist)")
    url, tok = c
    tag = tag_of(folder)
    view = f"{url}/view?subfolder=swap_results&type=output&filename="
    r = curl(["-o", str(out), "-w", "%{http_code}", "-H", f"Authorization: Bearer {tok}", f"{view}{tag}.mp4"])
    if r.stdout.strip() == "200" and out.exists() and out.stat().st_size > 100000:
        return say(ok=True, job=o.job, finished=True, video=str(out))
    out.unlink(missing_ok=True)
    failed = curl(["-o", "/dev/null", "-w", "%{http_code}", "-H", f"Authorization: Bearer {tok}", f"{view}{tag}.failed"]).stdout.strip() == "200"
    if failed:
        log = curl(["-H", f"Authorization: Bearer {tok}", f"{view}{tag}.log"]).stdout.strip().splitlines()
        return say(ok=False, job=o.job, finished=False, error="the swap failed on the GPU", last_lines=log[-4:])
    say(ok=True, job=o.job, finished=False, sent_at=(folder / "sent").read_text(), note="still swapping, or waiting behind other clips")


def status(o):
    folder = folder_of(o.job)
    job = json.loads((folder / "job.json").read_text()) if (folder / "job.json").exists() else {}
    say(ok=True, job=o.job, prepared=bool(job), sent=(folder / "sent").exists(), finished=(folder / "swapped.mp4").exists(),
        gpu_connected=CONN.exists(), seconds=job.get("seconds"), voice=job.get("voice"),
        video=str(folder / "swapped.mp4") if (folder / "swapped.mp4").exists() else None)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("step", choices=["prepare", "send", "collect", "status"]); a.add_argument("job")
    a.add_argument("--video", default=""); a.add_argument("--person", default=""); a.add_argument("--rights", default="")
    a.add_argument("--voice", default="keep", choices=["keep", "new"]); a.add_argument("--voice-id", default="")
    a.add_argument("--seconds", default="20"); a.add_argument("--force", action="store_true")
    o = a.parse_args()
    try:
        {"prepare": prepare, "send": send, "collect": collect, "status": status}[o.step](o)
    except Exception as e:
        say(ok=False, error=f"{type(e).__name__}: {e}"[:400])
