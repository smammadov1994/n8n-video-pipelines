# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""TEST: one take of her driven by a ready-made voice track (e.g. Fish Audio).

    uv run fish_take.py <voice.wav> <start picture> <out.mp4> "<what she does>" "<the words in the audio>"

The 5090 model builds the clip around the given audio (anchored at frame 0), so the words are
exactly the audio's words; the model only has to move her mouth and body to it.
"""
import copy, json, shutil, subprocess, sys, time
from pathlib import Path

COMFY = Path.home() / "comfyui-mcp"
sys.path.insert(0, str(COMFY))
import server  # noqa: E402

voice, picture, out, does, words = sys.argv[1:6]
seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", voice],
                               capture_output=True, text=True).stdout.strip())
frames = next(17 * k + 5 for k in range(1, 60) if (17 * k + 5) / 24 >= seconds + 0.4)   # model's 17k+5 grid
prompt = (f"SCENE: YouTube educational video, mirrorless camera locked off on a tripod, eye level, medium shot. She sits at "
          f"the wooden desk exactly as in the first frame, eyes on the lens. {does} "
          f"LINE: She speaks these exact words, her lips matching the voice on the soundtrack: \"{words}\" "
          f"RULES: One continuous take, no jump cuts, no zoom. Her face keeps exactly the proportions of the first frame. "
          f"Hands empty with five natural fingers, bare wrists. She keeps the same beige ribbed tank top, gold heart necklace "
          f"and black clip-on mic with its cable. The room stays exactly as in the first frame. No text on screen, no music.")
with server._client() as c:
    img = server._upload_image(c, picture)
    aud = server._upload_image(c, voice)                      # same upload endpoint stores any input file
    wf = copy.deepcopy(server._load_workflow("i2v"))
    wf["5"]["inputs"].update({"prompt": prompt, "width": 1344, "height": 768, "length": frames})
    wf["20"]["inputs"]["image"] = img
    wf["22"] = {"class_type": "LoadAudio", "inputs": {"audio": aud}, "_meta": {"title": "Voice track"}}
    wf["23"] = {"class_type": "MiniMaxH3AddGuide", "_meta": {"title": "Anchor voice at frame 0"},
                "inputs": {"positive": ["5", 0], "latent": ["5", 1], "frame_idx": 0, "audio_vae": ["4", 0], "audio": ["22", 0]}}
    wf["9"]["inputs"]["conditioning"] = ["23", 0]
    wf["8"]["inputs"]["noise_seed"] = 4321
    wf["14"]["inputs"]["filename_prefix"] = "hyperflow/voice2v"
    r = c.post("/prompt", json={"prompt": wf, "client_id": server.CLIENT_ID, "front": True})
    body = r.json()
    if r.status_code >= 400 or body.get("node_errors"):
        print(json.dumps({"ok": False, "error": json.dumps(body)[:1500]})); sys.exit(0)
    pid, t0, lost = body["prompt_id"], time.monotonic(), 0
    while True:
        st = server._status(c, pid, download=True)
        if st["state"] == "done":
            shutil.move([f for f in st["local_files"] if f.endswith(".mp4")][0], out); break
        if st["state"] == "error":
            print(json.dumps({"ok": False, "error": st.get("error")})); sys.exit(0)
        lost = lost + 1 if st["state"] == "unknown" else 0
        if lost >= 8 or time.monotonic() - t0 > 1500:
            print(json.dumps({"ok": False, "error": "lost or timed out"})); sys.exit(0)
        time.sleep(4)
print(json.dumps({"ok": True, "file": out, "audio_seconds": round(seconds, 2), "frames": frames,
                  "clip_seconds": round(frames / 24, 2), "took_s": round(time.monotonic() - t0)}))
