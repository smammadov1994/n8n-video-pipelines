#!/usr/bin/env python3
"""Run OpenJutsu's simple one-person swap straight against ComfyUI on this machine (no web app).
    python3 run_swap.py [--check]      --check only lists missing nodes / model files
Mirrors lib/simple.ts pruneSimple: hat fix off, lip-sync ON (the person talks), default sizes."""
import json, re, sys, time, urllib.request, urllib.error
API = "http://127.0.0.1:18188"
def get(p): return json.load(urllib.request.urlopen(API + p, timeout=120))
def post(p, body):
    req = urllib.request.Request(API + p, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try: return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e: return {"http_error": e.code, "body": json.loads(e.read().decode() or "{}")}
g = json.load(open("/workspace/openjutsu/workflows/simple.api.json"))
def is_link(v): return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)
# hat fix off
for k in ("47", "48", "49", "50", "51", "52"): g.pop(k, None)
g["42"]["inputs"]["mask"] = ["39", 0]
# lip-sync on: drop the "No lip-sync" nodes and let H3 hear the soundtrack
MUTE = re.compile(r"^Mute the (clip|reference) audio H3 hears$")
NOLS = re.compile(r"^(No lip-sync in the prompt|SAM: faces|SAM 3\.1 track faces|Faces \(shown on the mannequins?\))$")
through = {}
for k, n in g.items():
    t = (n.get("_meta") or {}).get("title", "")
    if MUTE.match(t): through[k] = n["inputs"]["audio"]
    elif NOLS.match(t): through[k] = None
for k in through: g.pop(k)
for k, n in g.items():
    for name, v in list(n["inputs"].items()):
        if is_link(v) and v[0] in through:
            if through[v[0]] is not None: n["inputs"][name] = through[v[0]]
            elif name in ("no_lip_sync", "faces", "face_size"): del n["inputs"][name]
            else: sys.exit(f"node {k}.{name} still links to removed node {v[0]}")
for k, n in g.items():
    for name, v in n["inputs"].items():
        if is_link(v) and v[0] not in g: sys.exit(f"node {k}.{name} links to missing node {v[0]}")
# our files
g["2"]["inputs"]["image"] = "character.png"
VIDEO = next((a for a in sys.argv[1:] if a.endswith(".mp4")), "source.mp4")
g["5"]["inputs"]["video"] = VIDEO
g["19"]["inputs"]["clip_name"] = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
g["16"]["inputs"]["lora_name"] = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
g["11"]["inputs"].update({"seed": 11, "clip_seconds": 6, "roles": ""})
info = get("/object_info")
missing = sorted({n["class_type"] for n in g.values()} - set(info))
print("missing node types:", missing or "none")
def options(cls, field):
    try: return info[cls]["input"]["required"][field][0]
    except Exception: return []
for k, cls, field in (("15", "UNETLoader", "unet_name"), ("16", "LoraLoaderModelOnly", "lora_name"), ("13", "CLIPLoader", "clip_name"), ("19", "CLIPLoader", "clip_name"),
                      ("20", "VAELoader", "vae_name"), ("21", "VAELoader", "vae_name"), ("23", "CheckpointLoaderSimple", "ckpt_name")):
    want, have = g[k]["inputs"][field], options(cls, field)
    hit = [h for h in have if isinstance(h, str) and h.split("/")[-1] == want.split("/")[-1]]
    if hit: g[k]["inputs"][field] = hit[0]
    print(f"  {field} {want}: {'ok as ' + hit[0] if hit else 'MISSING'}")
if "--check" in sys.argv or missing: sys.exit(0)
r = post("/prompt", {"prompt": g, "client_id": "swap-trial"})
if "prompt_id" not in r:
    print("REJECTED:", json.dumps(r)[:3000]); sys.exit(1)
pid = r["prompt_id"]; print("queued", pid, flush=True); t0 = time.time()
while True:
    time.sleep(15)
    h = get("/history/" + pid).get(pid)
    if h:
        st = h.get("status", {})
        print("finished in", round((time.time() - t0) / 60, 1), "min:", st.get("status_str"), flush=True)
        for m in st.get("messages", []):
            if m[0] in ("execution_error", "execution_interrupted"): print("ERROR:", json.dumps(m[1])[:2500])
        for nid, o in h.get("outputs", {}).items():
            for key, items in o.items():
                for it in items if isinstance(items, list) else []:
                    if isinstance(it, dict) and it.get("filename"): print("OUTPUT", nid, it.get("subfolder", ""), it["filename"], it.get("type"))
                    elif isinstance(it, str) and len(it) < 400: print("TEXT", nid, it)
        break
    q = get("/queue"); print(f"  {round((time.time() - t0) / 60, 1)} min, running {len(q['queue_running'])}, pending {len(q['queue_pending'])}", flush=True)
