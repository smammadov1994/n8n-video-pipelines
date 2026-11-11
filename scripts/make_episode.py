# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Shoot one planned episode twice: once with a Fish Audio voice driving her, once with the video
model's own voice. Needs <folder>/spec.json and <folder>/sets/ (from plan_episode.py).

    uv run make_episode.py <episode folder> [fish|native|both]

FISH version   Each line is spoken by Fish first; the 5090 model then generates her around that
               voice track, so the words are exact. Checked: words heard, face match. Up to 3 tries.
NATIVE version The 5090 model makes her voice itself. Checked the same way, up to 4 tries per take.
Cutaway footage is generated once and shared. Every finished part is cached, so running again
continues where it stopped.

Out: final_fish.mp4, final_native.mp4 (16:9, 1080p), *_vertical.mp4 (9:16 crops that follow her
face), post.txt, result.json. A take that never passed is still used (best try) and FLAGGED in
result.json, so a video with a flag needs a human look before posting.
"""
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from clip_check import look_at

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


me = load("make_edu")
mv = me.mv
sys.path.insert(0, str(mv.COMFY))

FISH_VOICE = "b545c585f631496c914815291da4e893"     # "Friendly Women" from the Fish library
FISH_SPEED = 0.88
FISH_TONE = "(relaxed, friendly, smiling) "
FISH_TRIES = 4
CAMERAS = {
    "desk_front": "YouTube educational video, mirrorless camera locked off on a tripod, eye level, medium shot. She sits in her home studio, bookshelf, globe and lamp behind her, no desk or table in the frame, exactly as in the first frame.",
    "desk_side": "YouTube educational video, second camera position, chest-up shot, camera locked off on a tripod. Same home studio, window and bookshelf behind her, no desk or table in the frame, exactly as in the first frame.",
}
RULES = me.RULES.replace("Hands empty with five natural fingers.", "Hands empty with five natural fingers. Her forearms and wrists are bare skin with nothing worn on them. Her hands are small and slender, in proportion to her body, and stay close to her chest, never reaching toward the camera.")


def camera_of(spec, name):
    for s in spec.get("sets", []):
        if s["name"] == name:
            return "YouTube educational video, camera locked off on a tripod at her eye level, straight in front of her. " + s["camera"]
    return CAMERAS[name]


def seconds_of(path):
    return float(mv.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout.strip())


# ------------------------------------------------------------------ Fish voice

def fish_voice(server, line, dest):
    """Fish speaks the line. Cached by voice + speed + words."""
    if dest.exists():
        return
    body = {"text": FISH_TONE + line, "format": "wav", "prosody": {"speed": FISH_SPEED}, "reference_id": FISH_VOICE}
    headers = {"Authorization": f"Bearer {server._fish_key()}", "model": "s2.1-pro-free"}
    for attempt in range(6):
        r = httpx.post(f"{server.FISH_API}/v1/tts", json=body, headers=headers, timeout=180)
        if r.status_code < 400:
            raw = dest.with_suffix(".raw.wav")
            raw.write_bytes(r.content)
            mv.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "44100", "-ac", "2", str(dest)])
            raw.unlink(missing_ok=True)
            if dest.exists():
                return
        if r.status_code in (429, 500, 502, 503):
            time.sleep(30 * (attempt + 1))
            continue
        raise RuntimeError(f"Fish Audio error {r.status_code}: {r.text[:200]}")
    raise RuntimeError("Fish Audio kept refusing (rate limit or outage)")


def wait_for(server, client, prompt_id, dest):
    deadline, lost, errors = time.monotonic() + 25 * 60, 0, 0
    while True:
        try:
            st = server._status(client, prompt_id, download=True)
            errors = 0
        except Exception:                    # tunnel hiccup: keep waiting, the job is still on the GPU
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
            raise RuntimeError("5090 lost the job. ComfyUI may have restarted.")
        if time.monotonic() > deadline:
            raise RuntimeError("5090 took longer than 25 minutes for one clip")
        time.sleep(4)


def voice_clip(server, client, voice, picture, prompt, seed, w, h, dest):
    """One clip of her generated around a ready voice track (anchored at frame 0)."""
    frames = next(17 * k + 5 for k in range(7, 60) if (17 * k + 5) / 24 >= seconds_of(voice) + 0.45)
    wf = copy.deepcopy(server._load_workflow("i2v"))
    wf["5"]["inputs"].update({"prompt": prompt, "width": w, "height": h, "length": frames})
    wf["20"]["inputs"]["image"] = server._upload_image(client, str(picture))
    wf["22"] = {"class_type": "LoadAudio", "inputs": {"audio": server._upload_image(client, str(voice))},
                "_meta": {"title": "Voice track"}}
    wf["23"] = {"class_type": "MiniMaxH3AddGuide", "_meta": {"title": "Anchor voice at frame 0"},
                "inputs": {"positive": ["5", 0], "latent": ["5", 1], "frame_idx": 0, "audio_vae": ["4", 0], "audio": ["22", 0]}}
    wf["9"]["inputs"]["conditioning"] = ["23", 0]
    wf["8"]["inputs"]["noise_seed"] = seed
    wf["14"]["inputs"]["filename_prefix"] = "hyperflow/voice2v"
    r = client.post("/prompt", json={"prompt": wf, "client_id": server.CLIENT_ID, "front": True})
    body = r.json()
    if r.status_code >= 400 or body.get("node_errors"):
        raise RuntimeError(f"5090 rejected the job: {json.dumps(body)[:400]}")
    wait_for(server, client, body["prompt_id"], dest)


def fish_take(server, client, folder, spec, t):
    line = t["says"].strip()
    key = hashlib.sha1(f"{FISH_VOICE}|{FISH_SPEED}|{t['set']}|{t['does']}|{line}".encode()).hexdigest()[:8]
    out = folder / "fish"
    out.mkdir(exist_ok=True)
    record = out / f"take{t['n']}_{key}.json"
    if record.exists():
        return json.loads(record.read_text())
    voice = out / f"voice{t['n']}_{hashlib.sha1(line.encode()).hexdigest()[:8]}.wav"
    fish_voice(server, line, voice)
    picture = folder / "sets" / f"{t['set']}_{spec['width']}x{spec['height']}.png"
    prompt = (f"SCENE: {camera_of(spec, t['set'])} Her eyes are on the lens. {t['does']} "
              f"LINE: She speaks these exact words, her lips matching the voice on the soundtrack: \"{line}\" "
              f"RULES: {RULES} Quiet natural ambience.")
    tries, started = [], time.monotonic()
    for attempt in range(1, FISH_TRIES + 1):
        clip = out / f"take{t['n']}_{key}_try{attempt}.mp4"
        if not clip.exists():
            voice_clip(server, client, voice, picture, prompt, 900 * t["n"] + attempt * 7919 + int(key, 16) % 100000,
                       spec["width"], spec["height"], clip)
        heard, _ = mv.heard_in(clip)
        match = mv.score(line, heard)
        face = mv.face_of(clip)
        good = match >= mv.PASS and face["verdict"] in ("her", "look")
        look = look_at(clip, seconds_of(voice)) if good else None      # frames checked for watches, bad hands, changed scene...
        good = good and look["good"]
        tries.append({"try": attempt, "file": str(clip), "heard": heard, "match": match, "face": face, "look": look, "good": good})
        if good:
            break
    best = max(tries, key=lambda x: (x["good"], x["match"] >= mv.PASS, -len((x["look"] or {}).get("problems", [])), x["match"],
                                     x["face"].get("median") or 0))
    result = {"n": t["n"], "set": t["set"], "says": line, "passed": best["good"], "match": best["match"], "face": best["face"],
              "look": best["look"],
              "heard": best["heard"], "file": best["file"], "speech_end": round(seconds_of(voice), 2),
              "tries": len(tries), "seconds_spent": round(time.monotonic() - started)}
    record.write_text(json.dumps(result, indent=2))   # kept even when flagged: an unattended retry must not redo it
    return result


def native_take(server, client, folder, spec, t):
    """Her own (model-made) voice: the explainer maker's take, with this episode's camera + direction."""
    scene = f"{camera_of(spec, t['set'])} Her eyes are on the lens. {t['does']}"
    return me.make_take(server, client, folder, {**spec, "rules": RULES, "keep_failed": True}, {**t, "scene": scene})


def cutaway(server, client, folder, spec, t):
    c = t["cutaway"]
    key = hashlib.sha1(c["prompt"].encode()).hexdigest()[:8]
    clip = folder / "takes" / f"cutaway{t['n']}_{key}.mp4"
    clip.parent.mkdir(exist_ok=True)
    if not clip.exists():
        me.render(server, client, c["prompt"], 5.2, int(key, 16) % 100000, spec["width"], spec["height"], None, clip)
    return clip


# ------------------------------------------------------------------ editing

def make_part(take, cover, w, h, vertical, dest):
    """One take trimmed just after her last word, optional cutaway over the second half."""
    cut = min(seconds_of(take["file"]), take["speech_end"] + 0.35) if take["speech_end"] > 1 else seconds_of(take["file"])
    if vertical:
        cw = int(h * 9 / 16) // 2 * 2
        x = max(0, min(w - cw, int(((take.get("face") or {}).get("face_x") or 0.5) * w - cw / 2)))
        her, mid, size = f"crop={cw}:{h}:{x}:0,scale=1080:1920", f"crop={cw}:{h}:{(w - cw) // 2}:0,scale=1080:1920", ""
    else:
        her = mid = "scale=1920:-2,crop=1920:1080"
    args = ["-i", take["file"]]
    start = None
    if cover:
        words = len(take["says"].split())
        start = round(max(1.6, min(cut - 1.3, take["speech_end"] * cover["after_words"] / max(words, 1))), 2)
        if cut - start < 1.0 or cut - start > 4.6:
            start = max(1.6, cut - 4.4) if cut - start > 4.6 else None
    if cover and start:
        args += ["-i", str(cover["file"])]
        fc = (f"[0:v]trim=0:{start},setpts=PTS-STARTPTS,fps=24,{her}[a];"
              f"[1:v]trim=0.3:{0.3 + cut - start:.2f},setpts=PTS-STARTPTS,fps=24,scale={w}:{h},{mid}[b];"
              f"[a][b]concat=n=2:v=1:a=0[v];[0:a]atrim=0:{cut:.2f},asetpts=PTS-STARTPTS[au]")
    else:
        fc = f"[0:v]trim=0:{cut:.2f},setpts=PTS-STARTPTS,fps=24,{her}[v];[0:a]atrim=0:{cut:.2f},asetpts=PTS-STARTPTS[au]"
    r = mv.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", fc, "-map", "[v]", "-map", "[au]", "-c:v", "libx264",
                "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-ac", "2", str(dest)])
    if r.returncode:
        raise RuntimeError(f"take {take['n']} edit failed: {r.stderr.strip()[-300:]}")


def assemble(folder, spec, takes, covers, name):
    out = {}
    for vertical in (False, True):
        parts = []
        for t in takes:
            part = folder / "parts" / f"{name}_{'v' if vertical else 'h'}_{t['n']}.mp4"
            part.parent.mkdir(exist_ok=True)
            make_part(t, covers.get(t["n"]), spec["width"], spec["height"], vertical, part)
            parts.append(part)
        n = len(parts)
        fc = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5[a]"
        final = folder / f"final_{name}{'_vertical' if vertical else ''}.mp4"
        r = mv.run(["ffmpeg", "-v", "error", "-y", *[x for p in parts for x in ("-i", str(p))], "-filter_complex", fc,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
        if r.returncode:
            raise RuntimeError(f"joining failed: {r.stderr.strip()[-300:]}")
        out["vertical" if vertical else "wide"] = str(final)
    out["seconds"] = round(seconds_of(out["wide"]), 1)
    return out


def version(server, client, folder, spec, covers, name, take_fn):
    started = time.monotonic()
    takes = [take_fn(server, client, folder, spec, t) for t in spec["takes"]]
    for t in takes:                      # a take that failed on words never had its face measured
        if not t.get("face"):
            try:
                t["face"] = mv.face_of(t["file"])
            except Exception:
                t["face"] = {"median": None, "lowest": None, "face_x": 0.5, "verdict": "no_face"}
    files = assemble(folder, spec, takes, covers, name)
    flags = [f"take {t['n']}: " + ("heard \"" + t["heard"] + "\"" if t["match"] < mv.PASS else
                                   "picture: " + ", ".join(t["look"]["problems"]) + " (" + t["look"]["note"] + ")"
                                   if t.get("look") and not t["look"]["good"] else
                                   f"face match {(t.get('face') or {}).get('median')}") for t in takes if not t["passed"]]
    return {**files, "flags": flags, "minutes": round((time.monotonic() - started) / 60, 1),
            "takes": [{"n": t["n"], "set": t["set"], "says": t["says"], "heard": t["heard"], "match": t["match"],
                       "face": (t.get("face") or {}).get("median"), "face_low": (t.get("face") or {}).get("lowest"),
                       "tries": t["tries"], "passed": t["passed"]} for t in takes]}


def main():
    folder = Path(sys.argv[1]).resolve()
    which = sys.argv[2] if len(sys.argv) > 2 else "both"
    spec = json.loads((folder / "spec.json").read_text())
    result_file = folder / "result.json"
    result = json.loads(result_file.read_text()) if result_file.exists() else {}
    result.update({"title": spec["title"], "topic": spec.get("topic"), "folder": str(folder)})
    post = spec.get("post") or {}
    (folder / "post.txt").write_text(f"{post.get('title') or spec['title']}\n\n{post.get('description', '')}\n\n"
                                     f"{' '.join(post.get('hashtags', []))}\n")
    import server
    errors = {}
    with server._client() as client:
        try:
            covers = {t["n"]: {"file": cutaway(server, client, folder, spec, t), "after_words": int(t["cutaway"].get("after_words") or 8)}
                      for t in spec["takes"] if t.get("cutaway")}
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"cutaways: {type(e).__name__}: {e}"[:400]}))
            return
        for name, fn in (("fish", fish_take), ("native", native_take)):
            if which not in (name, "both") or (result.get(name) or {}).get("wide"):
                continue
            try:
                result[name] = version(server, client, folder, spec, covers, name, fn)
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"[:400]
            result_file.write_text(json.dumps(result, indent=2))
    print(json.dumps({"ok": not errors, "errors": errors, "title": spec["title"],
                      **{n: {k: result[n][k] for k in ("seconds", "flags", "minutes")} for n in ("fish", "native") if result.get(n)}}))


if __name__ == "__main__":
    main()
