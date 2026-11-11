# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Cartoon cat feasibility test. Technique copied from kaiyros n8n-pipeline/scripts/make_episode.py
(voice_clip: Fish voice anchored at frame 0 of an image-to-video job on the 5090).

    uv run make_clips.py voice            speak the three lines (cached)
    uv run make_clips.py clip <n> <try>   one clip of scene n, try number picks the seed
    uv run make_clips.py check <file>     transcript score + 6-frame sheet for one clip

Differences from production: jobs are queued at the BACK of the queue (no "front"), and downloads
land in this folder, so the live production run is not disturbed.
"""
import copy
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
os.environ.setdefault("OUTPUT_DIR", str(HERE / "work" / "downloads"))
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")
COMFY = Path.home() / "comfyui-mcp"
sys.path.insert(0, str(COMFY))

VOICE_ID = "44a7a443f7404ef6b8565022b150d2ed"      # "Kids" from the Fish library: young, cheerful, clear
SPEED = 0.9
TONE = "(cheerful, warm, friendly) "
W, H = 1344, 768
TAIL = float(os.environ.get("TAIL", "0.6"))   # silent seconds after the last word
STYLE = (HERE / "style.txt").read_text().strip()
EP = HERE / os.environ.get("EPISODE", "")            # EPISODE=omelet uses the omelet/ subfolder
SCRIPT = json.loads((EP / "script.json").read_text())
RULES = ("One continuous take, camera locked off, no cuts, no zoom. Exactly one cat. Mango keeps exactly the shape, "
         "colours, face, teal apron with yellow pocket and teal chef hat of the first frame. Two arms, two paws, "
         "no extra limbs. Bright sunny daytime kitchen with the same even lighting and the same pale yellow wall in every frame. Mango says the line exactly once and adds no word after the last one. No text on screen, no captions, no music.")


def run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def seconds_of(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout.strip())


def words(text):
    text = text.lower().replace("-", " ").replace("yogurt", "yoghurt").replace("omelette", "omelet").replace("its", "it is").replace("it's", "it is").replace("grownup", "grown up").replace("byebye", "bye bye")
    return re.findall(r"[a-z]+", text.replace("'", ""))


def score(line, heard):
    a, b = words(line), words(heard)
    if not a or not b:
        return 0.0
    matched = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(min(matched / len(a), matched / len(b)), 3)


def heard_in(clip):
    out = clip.with_suffix(".transcript.json")
    if not out.exists():
        r = run(["uv", "run", str(COMFY / "transcribe.py"), str(clip), str(out), "en"])
        if not out.exists():
            raise RuntimeError(f"transcribe failed: {(r.stderr or '').strip()[-200:]}")
    return json.loads(out.read_text()).get("text", "").strip()


def fish_voice(server, line, dest):
    if dest.exists():
        return
    body = {"text": TONE + line, "format": "wav", "prosody": {"speed": SPEED}, "reference_id": VOICE_ID}
    headers = {"Authorization": f"Bearer {server._fish_key()}", "model": "s2.1-pro-free"}
    for attempt in range(6):
        r = httpx.post(f"{server.FISH_API}/v1/tts", json=body, headers=headers, timeout=180)
        if r.status_code < 400:
            raw = dest.with_suffix(".raw.wav")
            raw.write_bytes(r.content)
            run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "44100", "-ac", "2", str(dest)])
            raw.unlink(missing_ok=True)
            if dest.exists():
                return
        if r.status_code in (429, 500, 502, 503):
            time.sleep(30 * (attempt + 1))
            continue
        raise RuntimeError(f"Fish Audio error {r.status_code}: {r.text[:200]}")
    raise RuntimeError("Fish Audio kept refusing")


def wait_for(server, client, prompt_id, dest):
    deadline, lost, errors = time.monotonic() + 90 * 60, 0, 0     # longer than production: we wait behind its jobs
    while True:
        try:
            st = server._status(client, prompt_id, download=True)
            errors = 0
        except Exception:
            errors += 1
            if errors > 20:
                raise RuntimeError("lost contact with the 5090")
            time.sleep(15)
            continue
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
            raise RuntimeError("5090 lost the job")
        if time.monotonic() > deadline:
            raise RuntimeError("waited 90 minutes for one clip")
        time.sleep(5)


def voice_clip(server, client, voice, picture, prompt, seed, dest):
    frames = next(17 * k + 5 for k in range(7, 60) if (17 * k + 5) / 24 >= seconds_of(voice) + TAIL)
    wf = copy.deepcopy(server._load_workflow("i2v"))
    wf["5"]["inputs"].update({"prompt": prompt, "width": W, "height": H, "length": frames})
    wf["20"]["inputs"]["image"] = server._upload_image(client, str(picture))
    wf["22"] = {"class_type": "LoadAudio", "inputs": {"audio": server._upload_image(client, str(voice))},
                "_meta": {"title": "Voice track"}}
    wf["23"] = {"class_type": "MiniMaxH3AddGuide", "_meta": {"title": "Anchor voice at frame 0"},
                "inputs": {"positive": ["5", 0], "latent": ["5", 1], "frame_idx": 0, "audio_vae": ["4", 0], "audio": ["22", 0]}}
    wf["9"]["inputs"]["conditioning"] = ["23", 0]
    wf["8"]["inputs"]["noise_seed"] = seed
    wf["14"]["inputs"]["filename_prefix"] = "hyperflow/catcartoon"
    r = client.post("/prompt", json={"prompt": wf, "client_id": server.CLIENT_ID})      # back of the queue
    body = r.json()
    if r.status_code >= 400 or body.get("node_errors"):
        raise RuntimeError(f"5090 rejected the job: {json.dumps(body)[:400]}")
    print("queued", body["prompt_id"], "frames", frames, flush=True)
    wait_for(server, client, body["prompt_id"], dest)


def prompt_for(s):
    return (f"SCENE: A children's cooking cartoon. {s['picture']} Colourful cartoon kitchen with a round window, wooden "
            f"cupboards and a shelf of jars, exactly as in the first frame. Mango's eyes are on the camera. {s['does']} "
            f"LINE: Mango speaks these exact words, the mouth matching the voice on the soundtrack: \"{s['says']}\" "
            f"STYLE: {STYLE} RULES: {RULES} Same character and kitchen as the first frame.")


def check(clip, line):
    heard = heard_in(clip)
    d = seconds_of(clip)
    sheet = clip.with_suffix(".sheet.jpg")
    times = [d * (i + 0.5) / 6 for i in range(6)]
    parts = []
    for i, t in enumerate(times):
        p = clip.parent / f"_{clip.stem}_{i}.jpg"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1", "-vf", "scale=672:-1", str(p)])
        parts.append(p)
    args = ["ffmpeg", "-v", "error", "-y"]
    for p in parts:
        args += ["-i", str(p)]
    run(args + ["-filter_complex", "".join(f"[{i}]" for i in range(6)) + "xstack=inputs=6:layout=0_0|w0_0|0_h0|w0_h0|0_h0+h1|w0_h0+h1", str(sheet)])
    for p in parts:
        p.unlink(missing_ok=True)
    out = {"file": clip.name, "seconds": round(d, 2), "heard": heard, "match": score(line, heard), "sheet": str(sheet)}
    print(json.dumps(out, indent=1))
    return out


def main():
    what = sys.argv[1]
    if what == "check":
        clip = Path(sys.argv[2]).resolve()
        n = int(re.search(r"scene(\d)", clip.name).group(1))
        check(clip, SCRIPT[n - 1]["says"])
        return
    import server
    if what == "voice":
        for s in SCRIPT:
            dest = EP / "voice" / f"scene{s['n']}.wav"
            fish_voice(server, s["says"], dest)
            heard = heard_in(dest)
            print(s["n"], round(seconds_of(dest), 2), "s", score(s["says"], heard), heard)
        return
    n, attempt = int(sys.argv[2]), int(sys.argv[3])
    s = SCRIPT[n - 1]
    dest = EP / "clips" / f"scene{n}_try{attempt}.mp4"
    if not dest.exists():
        with server._client() as client:
            voice_clip(server, client, EP / "voice" / f"scene{n}.wav", EP / "pictures" / f"scene{n}_{W}x{H}.png",
                       prompt_for(s), 4100 * n + 7919 * attempt, dest)
    check(dest, s["says"])


if __name__ == "__main__":
    main()
