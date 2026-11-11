#!/usr/bin/env python3
"""Work out what one TikTok Shop video is about.

    understand.py <base64 of the video's JSON item>      # how the n8n workflow calls it
    understand.py --json '{"video_id": "...", "tiktok_url": "..."}'

Steps, each cached under media/<video_id>/ so a repeat run is instant:
  1. download the MP4 from TikTok (yt-dlp)            -> video.mp4
  2. transcribe the speech (Whisper on this Mac)      -> transcript.json
  3. pull 6 still frames (ffmpeg)                     -> frame_1.jpg ...
  4. Claude reads transcript + frames + caption       -> understanding.json

Prints one JSON object: {"video_id", "ok", "understanding" | "error", "transcript", "video_file"}.
Always exits 0 so one bad video doesn't stop the n8n run; look at "ok".
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
TRANSCRIBE = Path.home() / "comfyui-mcp" / "transcribe.py"
FRAMES = 6
MODEL = os.environ.get("UNDERSTAND_MODEL", "sonnet")
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")

PROMPT = """You are analysing one TikTok Shop video so a content team can make their own video that sells as well.

Read these {n} still frames with the Read tool, in order (they are spread evenly through the video; the first is the opening shot):
{frames}

Video length: {duration}s
Caption: {caption}
Creator: @{creator}
Product: {product}
Speech transcript with timestamps (may be empty if nobody talks):
{transcript}

Answer with ONLY one JSON object, no markdown fence, no other words, in plain normal English, with exactly these keys:
{{
 "summary": "2 sentences: what happens in the video",
 "hook": {{"spoken": "first words said, verbatim, or null", "on_screen_text": "text overlay in the opening shot, verbatim, or null", "type": "e.g. problem, shock, demo, question, deal, story"}},
 "format": "e.g. talking head, hands-only demo, before/after, unboxing, voiceover over b-roll, skit",
 "beats": [{{"at": "0-3s", "what": "what is shown or said"}}],
 "product_shown_how": "how the product appears and is demonstrated",
 "selling_angle": "the main reason given to buy",
 "proof": "evidence used: results, reviews, numbers, demo; or null",
 "call_to_action": "what the viewer is told to do, or null",
 "why_it_works": "1-2 sentences",
 "how_to_remake": "3 short concrete tips for making our own version"
}}
Only state what the frames, transcript or caption show. Use null when you can't tell."""


def fail(video_id, message):
    print(json.dumps({"video_id": video_id, "ok": False, "error": message}))
    sys.exit(0)


def run(cmd, timeout, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, **kw)


def download(url, dest):
    if dest.exists():
        return
    r = run(["yt-dlp", "-q", "--no-warnings", "-f", "b[acodec!=none][ext=mp4]/b[acodec!=none]/bv*+ba/b",
             "--merge-output-format", "mp4", "-o", str(dest), url], 300)
    if r.returncode or not dest.exists():
        raise RuntimeError(f"download failed: {(r.stderr or '').strip()[:200]}")


def duration(video):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], 60)
    return float(r.stdout.strip() or 0)


def transcribe(video, dest):
    if dest.exists():
        return json.loads(dest.read_text())
    r = run(["uv", "run", str(TRANSCRIBE), str(video), str(dest)], 900)
    if r.returncode or not dest.exists():
        if "No audio track" in (r.stderr + r.stdout):
            data = {"text": "", "segments": []}
            dest.write_text(json.dumps(data))
            return data
        raise RuntimeError(f"transcribe failed: {(r.stderr or '').strip()[-200:]}")
    return json.loads(dest.read_text())


def frames(video, folder, seconds):
    paths = [folder / f"frame_{i + 1}.jpg" for i in range(FRAMES)]
    if all(p.exists() for p in paths):
        return paths
    last = max(seconds - 0.5, 0.5)
    for i, p in enumerate(paths):
        at = 0.4 if i == 0 else last * i / (FRAMES - 1)
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", "scale=480:-2", "-q:v", "4", str(p)], 120)
    return [p for p in paths if p.exists()]


def ask_claude(prompt, folder, model=MODEL):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_"))}
    r = run(["claude", "-p", prompt, "--model", model, "--output-format", "json", "--allowedTools", "Read",
             "--setting-sources", "", "--strict-mcp-config"], 600, cwd=folder, env=env)
    try:
        reply = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError(f"claude failed: {(r.stderr or r.stdout).strip()[-300:]}")
    text = reply.get("result", "")
    if "authenticate" in text or "login" in text.lower():
        raise RuntimeError("Claude is not signed in on this Mac. In a terminal run: claude auth login")
    if r.returncode or reply.get("is_error"):
        raise RuntimeError(f"claude failed: {text[:300]}")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError(f"claude gave no JSON: {text[:200]}")
    return json.loads(m.group(0))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--json":
        item = json.loads(sys.argv[2])
    elif len(sys.argv) == 2:
        item = json.loads(base64.b64decode(sys.argv[1]))
    else:
        sys.exit(__doc__)
    vid = str(item.get("video_id") or "")
    if not re.fullmatch(r"\d{5,25}", vid):
        fail(vid, "bad video_id")
    url = item.get("tiktok_url") or ""
    if not url.startswith("https://www.tiktok.com/"):
        fail(vid, "no TikTok link")
    for tool in ("yt-dlp", "ffmpeg", "ffprobe", "uv", "claude"):
        if not shutil.which(tool):
            fail(vid, f"{tool} not found")
    folder = MEDIA / vid
    folder.mkdir(parents=True, exist_ok=True)
    video, out = folder / "video.mp4", folder / "understanding.json"
    try:
        download(url, video)
        transcript = transcribe(video, folder / "transcript.json")
        if out.exists():
            understanding = json.loads(out.read_text())
        else:
            seconds = duration(video)
            shots = frames(video, folder, seconds)
            lines = "\n".join(f"[{s['start']:.0f}s] {s['text'].strip()}" for s in transcript.get("segments", []))
            product = item.get("product_title") or "unknown"
            if item.get("product_price"):
                product += f" (${item['product_price']})"
            understanding = ask_claude(PROMPT.format(
                n=len(shots), frames="\n".join(str(p) for p in shots), duration=round(seconds),
                caption=item.get("title") or "", creator=item.get("creator") or "?", product=product,
                transcript=lines[:6000] or "(no speech)"), folder)
            out.write_text(json.dumps(understanding, indent=2))
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as e:
        fail(vid, str(e)[:400])
    print(json.dumps({"video_id": vid, "ok": True, "understanding": understanding,
                      "transcript": transcript.get("text", ""), "video_file": str(video)}))


if __name__ == "__main__":
    main()
