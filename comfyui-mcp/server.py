# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""
ComfyUI MCP server for HyperFlow H3 Flash (or any ComfyUI video workflow).

Lets Claude Desktop, Claude Code, or Codex generate videos on your remote
ComfyUI (e.g. a Vast.ai instance) by queuing your exported API-format workflow.

Config (environment variables):
  COMFY_URL      Base URL of ComfyUI, e.g. https://xxxx.trycloudflare.com
  COMFY_TOKEN    Vast.ai OPEN_BUTTON_TOKEN (leave empty if ComfyUI has no auth)
                 Both can instead live in connection.json next to this file:
                 {"url": "https://....trycloudflare.com", "token": "..."}  (re-read on every call)
  WORKFLOW_DIR   Folder with API-format workflow JSONs (default: ./workflows next to this file)
  OUTPUT_DIR     Where finished videos are downloaded (default: ~/Movies/comfyui-mcp)

Workflows (export from ComfyUI via Workflow > Export (API)):
  t2v.json   text-to-video        (required)
  i2v.json   first-frame-to-video (optional, used when first_image_path is given)
  flf2v.json first+last frame     (optional, used when last_image_path is given)
  ref2v.json reference-to-video   (optional, used when reference_image_paths is given)
"""

from __future__ import annotations

import copy
import json
import logging
import os
import random
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

COMFY_URL = os.environ.get("COMFY_URL", "").rstrip("/")
COMFY_TOKEN = os.environ.get("COMFY_TOKEN", "")
HERE = Path(__file__).resolve().parent
WORKFLOW_DIR = Path(os.environ.get("WORKFLOW_DIR", HERE / "workflows")).expanduser()
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "~/Movies/comfyui-mcp")).expanduser()

FPS = 24
MIN_FRAMES, MAX_FRAMES = 124, 360  # HyperFlow H3 Flash supports ~5.2 s to 15 s at 24 fps
CLIENT_ID = str(uuid.uuid4())

logging.getLogger("httpx").setLevel(logging.WARNING)  # keep logs quiet (stdout is the MCP channel)

mcp = FastMCP("comfyui")


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #

CONNECTION_FILE = HERE / "connection.json"


def _connection() -> tuple[str, str]:
    """URL/token from connection.json next to this file (re-read on every call, so it can be
    updated without restarting Claude), falling back to the COMFY_URL / COMFY_TOKEN env vars."""
    url, token = COMFY_URL, COMFY_TOKEN
    if CONNECTION_FILE.exists():
        data = json.loads(CONNECTION_FILE.read_text())
        url = (data.get("url") or url).rstrip("/")
        token = data.get("token") or token
    return url, token


def _client() -> httpx.Client:
    url, token = _connection()
    if not url:
        raise RuntimeError("No ComfyUI URL. Put it in connection.json or the COMFY_URL env var.")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"token": token} if token else {}
    return httpx.Client(
        base_url=url,
        headers=headers,
        params=params,
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, read=300.0),
    )


def _check(r: httpx.Response) -> httpx.Response:
    if r.status_code in (401, 403):
        raise RuntimeError(
            f"ComfyUI refused the request ({r.status_code}). Check COMFY_TOKEN; "
            "on Vast.ai it is the OPEN_BUTTON_TOKEN."
        )
    if r.status_code >= 400:
        raise RuntimeError(f"ComfyUI error {r.status_code}: {r.text[:800]}")
    ctype = r.headers.get("content-type", "")
    if "text/html" in ctype and r.request.url.path.startswith(("/prompt", "/history", "/queue", "/system_stats")):
        raise RuntimeError(
            "Got an HTML page instead of JSON - probably a login page. "
            "Check COMFY_TOKEN and that COMFY_URL points at the ComfyUI (port 8188) tunnel."
        )
    return r


# --------------------------------------------------------------------------- #
# Workflow patching
# --------------------------------------------------------------------------- #

def _load_workflow(name: str) -> dict[str, Any]:
    path = WORKFLOW_DIR / f"{name}.json"
    if not path.exists():
        raise RuntimeError(
            f"Workflow '{path}' not found. In ComfyUI open the hyperflow_{name} workflow, "
            f"then Workflow > Export (API), and save it as {path}."
        )
    data = json.loads(path.read_text())
    if "nodes" in data and "links" in data:
        raise RuntimeError(
            f"{path.name} is a UI-format workflow. Re-export it with Workflow > Export (API)."
        )
    return data


def _is_literal(v: Any) -> bool:
    # Linked inputs look like ["node_id", output_index]; literals are plain values.
    return not (isinstance(v, list) and len(v) == 2 and isinstance(v[1], int))


def _title(node: dict[str, Any]) -> str:
    return (node.get("_meta", {}) or {}).get("title", "") or ""


def _set_prompt(wf: dict[str, Any], prompt: str) -> int:
    candidates = []
    for nid, node in wf.items():
        for key in ("text", "prompt"):
            if key in node.get("inputs", {}) and isinstance(node["inputs"][key], str):
                score = 0
                t = _title(node).lower()
                if "prompt" in t:
                    score += 2
                if "negative" in t:
                    score -= 5
                candidates.append((score, nid, key))
    if not candidates:
        raise RuntimeError("Couldn't find a prompt text box in the workflow.")
    candidates.sort(key=lambda c: -c[0])
    _, nid, key = candidates[0]
    wf[nid]["inputs"][key] = prompt
    return 1


def _set_inputs(wf: dict[str, Any], names: tuple[str, ...], value: Any) -> int:
    n = 0
    for node in wf.values():
        inputs = node.get("inputs", {})
        for name in names:
            if name in inputs and _is_literal(inputs[name]):
                inputs[name] = value
                n += 1
    return n


def _set_images(wf: dict[str, Any], first: str | None, last: str | None) -> None:
    loaders = [
        (nid, node) for nid, node in sorted(wf.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)
        if node.get("class_type", "").startswith("LoadImage") and "image" in node.get("inputs", {})
    ]
    if (first or last) and not loaders:
        raise RuntimeError("This workflow has no Load Image node to put your image into.")
    last_nodes = [x for x in loaders if "last" in _title(x[1]).lower()]
    first_nodes = [x for x in loaders if x not in last_nodes]
    if first:
        target = first_nodes[0] if first_nodes else loaders[0]
        target[1]["inputs"]["image"] = first
    if last:
        if last_nodes:
            target = last_nodes[0]
        elif len(loaders) >= 2:
            target = loaders[1]
        else:
            raise RuntimeError("This workflow has only one Load Image node; can't set a last frame.")
        target[1]["inputs"]["image"] = last


def _set_refs(wf: dict[str, Any], names: list[str]) -> None:
    """Rewire the reference-to-video node to use exactly these uploaded images, in order."""
    ref_nid = next((nid for nid, n in wf.items()
                    if any(k.startswith("ref_images.") for k in n.get("inputs", {}))), None)
    if ref_nid is None:
        raise RuntimeError("This workflow has no reference-image inputs (expected the ref2v workflow).")
    node = wf[ref_nid]["inputs"]
    for k in [k for k in node if k.startswith("ref_images.")]:
        src = node.pop(k)
        if isinstance(src, list) and src and src[0] in wf and wf[src[0]].get("class_type") == "LoadImage":
            del wf[src[0]]
    for i, name in enumerate(names):
        nid = str(900 + i)
        wf[nid] = {"class_type": "LoadImage", "inputs": {"image": name},
                   "_meta": {"title": f"<Picture {i + 1}>"}}
        node[f"ref_images.ref_image_{i}"] = [nid, 0]


def _seconds_to_frames(seconds: float) -> int:
    frames = int(round(seconds * FPS / 4.0)) * 4
    return max(MIN_FRAMES, min(MAX_FRAMES, frames))


# --------------------------------------------------------------------------- #
# ComfyUI operations
# --------------------------------------------------------------------------- #

def _upload_image(c: httpx.Client, path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        raise RuntimeError(f"Image not found: {p}")
    with p.open("rb") as f:
        r = _check(c.post("/upload/image", files={"image": (p.name, f)}, data={"overwrite": "true"}))
    info = r.json()
    name = info["name"]
    return f"{info['subfolder']}/{name}" if info.get("subfolder") else name


def _outputs(entry: dict[str, Any]) -> list[dict[str, str]]:
    files = []
    for node_out in entry.get("outputs", {}).values():
        for items in node_out.values():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and "filename" in it and it.get("type", "output") == "output":
                    files.append(it)
    return files


def _download(c: httpx.Client, files: list[dict[str, str]], prompt_id: str) -> list[str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for it in files:
        params = {"filename": it["filename"], "subfolder": it.get("subfolder", ""), "type": it.get("type", "output")}
        dest = OUTPUT_DIR / f"{prompt_id[:8]}_{it['filename']}"
        with c.stream("GET", "/view", params=params) as r:
            _check(r)
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        saved.append(str(dest))
    return saved


def _status(c: httpx.Client, prompt_id: str, download: bool) -> dict[str, Any]:
    hist = _check(c.get(f"/history/{prompt_id}")).json()
    if prompt_id in hist:
        entry = hist[prompt_id]
        st = entry.get("status", {}) or {}
        if st.get("status_str") == "error":
            msgs = [m for m in st.get("messages", []) if m and m[0] == "execution_error"]
            detail = msgs[-1][1].get("exception_message", "") if msgs else ""
            return {"prompt_id": prompt_id, "state": "error", "error": detail or "Execution failed (see ComfyUI log)."}
        files = _outputs(entry)
        result: dict[str, Any] = {"prompt_id": prompt_id, "state": "done", "remote_files": [
            f"{f.get('subfolder', '')}/{f['filename']}".lstrip("/") for f in files]}
        if download and files:
            result["local_files"] = _download(c, files, prompt_id)
        return result

    q = _check(c.get("/queue")).json()
    running = [j[1] for j in q.get("queue_running", [])]
    pending = [j[1] for j in sorted(q.get("queue_pending", []), key=lambda j: j[0])]
    if prompt_id in running:
        return {"prompt_id": prompt_id, "state": "running"}
    if prompt_id in pending:
        return {"prompt_id": prompt_id, "state": "queued", "position": pending.index(prompt_id) + 1,
                "jobs_ahead": len(running) + pending.index(prompt_id)}
    return {"prompt_id": prompt_id, "state": "unknown",
            "note": "Not in queue or history. ComfyUI may have restarted."}


def _wait(c: httpx.Client, prompt_id: str, wait_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + max(0, wait_seconds)
    while True:
        st = _status(c, prompt_id, download=True)
        if st["state"] in ("done", "error", "unknown") or time.monotonic() >= deadline:
            if st["state"] in ("queued", "running"):
                st["next"] = "Still working. Call get_video_status with this prompt_id to keep waiting."
            return st
        time.sleep(3)


def _submit(c: httpx.Client, prompt: str, seconds: float, steps: int, seed: int | None, width: int,
            height: int, first_image_path: str | None, last_image_path: str | None,
            reference_image_paths: list[str] | None, uploaded: dict[str, str] | None = None,
            front: bool = False):
    """Build and queue one job. Returns (prompt_id, workflow, seed, frames)."""
    uploaded = uploaded if uploaded is not None else {}

    def up(path: str) -> str:
        if path not in uploaded:
            uploaded[path] = _upload_image(c, path)
        return uploaded[path]

    name = ("ref2v" if reference_image_paths else
            "flf2v" if last_image_path else "i2v" if first_image_path else "t2v")
    wf = copy.deepcopy(_load_workflow(name))
    seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    frames = _seconds_to_frames(seconds)
    first = up(first_image_path) if first_image_path else None
    last = up(last_image_path) if last_image_path else None
    refs = [up(p) for p in (reference_image_paths or [])]
    _set_prompt(wf, prompt)
    _set_inputs(wf, ("width",), width)
    _set_inputs(wf, ("height",), height)
    if not _set_inputs(wf, ("length", "num_frames", "frames"), frames):
        raise RuntimeError("Couldn't find a length/frames input in the workflow.")
    _set_inputs(wf, ("noise_seed", "seed"), seed)
    _set_inputs(wf, ("steps",), steps)
    if first or last:
        _set_images(wf, first, last)
    if refs:
        _set_refs(wf, refs)
    r = _check(c.post("/prompt", json={"prompt": wf, "client_id": CLIENT_ID, **({"front": True} if front else {})}))
    body = r.json()
    if body.get("node_errors"):
        raise RuntimeError(f"ComfyUI rejected the workflow: {json.dumps(body['node_errors'])[:1500]}")
    return body["prompt_id"], name, seed, frames


# --------------------------------------------------------------------------- #
# MCP tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def generate_video(
    prompt: str,
    seconds: float = 5,
    steps: int = 6,
    seed: int | None = None,
    width: int = 1344,
    height: int = 768,
    first_image_path: str | None = None,
    last_image_path: str | None = None,
    reference_image_paths: list[str] | None = None,
    wait_seconds: int = 240,
) -> dict[str, Any]:
    """Generate a video (with audio) on the remote ComfyUI using HyperFlow H3 Flash.

    Args:
        prompt: Describe the scene, camera movement, and sound. No negative prompt is used.
        seconds: Clip length, about 5 to 15 seconds (24 fps). 5 s takes ~2 min, 15 s ~10 min on an RTX 5090.
        steps: 4 (fastest), 6 (default), or 8 (best quality).
        seed: Same prompt + seed reproduces the same video. Omit for a random seed.
        width, height: Output size, multiples of 32. 1344x768 is what the model was trained on.
        first_image_path: Optional local image to start the video from (uses i2v workflow).
        last_image_path: Optional local image to end on (uses flf2v workflow; needs first_image_path).
        reference_image_paths: Optional list of up to 9 local images (characters, props, settings)
            for reference-to-video (ref2v workflow). Refer to them in the prompt as
            <Picture 1>, <Picture 2>, ... in list order. Can't be combined with first/last image.
        wait_seconds: How long to wait for the result before returning a prompt_id to poll.
            The finished MP4 is downloaded to the local OUTPUT_DIR.
    """
    if steps not in (4, 6, 8):
        raise ValueError("steps must be 4, 6, or 8")
    if width % 32 or height % 32:
        raise ValueError("width and height must be multiples of 32")
    if last_image_path and not first_image_path:
        raise ValueError("last_image_path requires first_image_path")
    if reference_image_paths and (first_image_path or last_image_path):
        raise ValueError("Use either reference_image_paths or first/last image, not both")
    if reference_image_paths and len(reference_image_paths) > 9:
        raise ValueError("At most 9 reference images")

    with _client() as c:
        prompt_id, name, seed, frames = _submit(c, prompt, seconds, steps, seed, width, height,
                                                first_image_path, last_image_path, reference_image_paths)
        result = _wait(c, prompt_id, wait_seconds)

    result.update({"workflow": name, "seed": seed, "frames": frames,
                   "seconds": round(frames / FPS, 2), "steps": steps})
    return result


@mcp.tool()
def get_video_status(prompt_id: str, wait_seconds: int = 240) -> dict[str, Any]:
    """Check on (and optionally wait for) a video job. Downloads the MP4 locally when done."""
    with _client() as c:
        return _wait(c, prompt_id, wait_seconds)


@mcp.tool()
def list_queue() -> dict[str, Any]:
    """Show what ComfyUI is running now and what's waiting in the queue."""
    with _client() as c:
        q = _check(c.get("/queue")).json()
    return {
        "running": [j[1] for j in q.get("queue_running", [])],
        "pending": [j[1] for j in sorted(q.get("queue_pending", []), key=lambda j: j[0])],
    }


@mcp.tool()
def cancel(prompt_id: str | None = None) -> str:
    """Cancel a job. With a prompt_id, removes it from the queue (or stops it if running).
    Without one, stops the running job and clears the whole queue."""
    with _client() as c:
        q = _check(c.get("/queue")).json()
        running = [j[1] for j in q.get("queue_running", [])]
        if prompt_id is None:
            _check(c.post("/queue", json={"clear": True}))
            _check(c.post("/interrupt", json={}))
            return "Stopped the running job and cleared the queue."
        if prompt_id in running:
            _check(c.post("/interrupt", json={"prompt_id": prompt_id}))
            return f"Stopped running job {prompt_id}."
        _check(c.post("/queue", json={"delete": [prompt_id]}))
        return f"Removed {prompt_id} from the queue."


@mcp.tool()
def list_recent_videos(limit: int = 10) -> list[dict[str, Any]]:
    """List recent finished jobs on the server with their output files."""
    with _client() as c:
        hist = _check(c.get("/history", params={"max_items": limit})).json()
    out = []
    for pid, entry in list(hist.items())[-limit:][::-1]:
        st = (entry.get("status") or {}).get("status_str", "")
        out.append({"prompt_id": pid, "status": st,
                    "files": [f"{f.get('subfolder', '')}/{f['filename']}".lstrip("/") for f in _outputs(entry)]})
    return out


@mcp.tool()
def download_video(prompt_id: str) -> dict[str, Any]:
    """Download the output files of a finished job to the local OUTPUT_DIR."""
    with _client() as c:
        return _status(c, prompt_id, download=True)


@mcp.tool()
def free_gpu_memory() -> str:
    """Unload models from GPU/RAM on the server (they reload on the next run)."""
    with _client() as c:
        _check(c.post("/free", json={"unload_models": True, "free_memory": True}))
    return "Asked ComfyUI to unload models and free memory."


@mcp.tool()
def server_info() -> dict[str, Any]:
    """Show ComfyUI version, GPU, and free VRAM. Use this to test the connection."""
    with _client() as c:
        s = _check(c.get("/system_stats")).json()
    dev = (s.get("devices") or [{}])[0]
    gb = 1024 ** 3
    return {
        "comfyui_version": s.get("system", {}).get("comfyui_version"),
        "gpu": dev.get("name"),
        "vram_total_gb": round(dev.get("vram_total", 0) / gb, 1),
        "vram_free_gb": round(dev.get("vram_free", 0) / gb, 1),
        "workflows_found": sorted(p.stem for p in WORKFLOW_DIR.glob("*.json")) if WORKFLOW_DIR.exists() else [],
        "output_dir": str(OUTPUT_DIR),
    }


# --------------------------------------------------------------------------- #
# Fish Audio text-to-speech (runs on this machine, uses its internet)
# --------------------------------------------------------------------------- #

FISH_API = "https://api.fish.audio"


def _fish_key() -> str:
    key = os.environ.get("FISH_API_KEY", "")
    if CONNECTION_FILE.exists():
        key = json.loads(CONNECTION_FILE.read_text()).get("fish_api_key") or key
    if not key:
        raise RuntimeError("No Fish Audio key. Add \"fish_api_key\" to connection.json.")
    return key


@mcp.tool()
def fish_voices(query: str = "", limit: int = 10, language: str = "en") -> list[dict[str, Any]]:
    """Search the Fish Audio voice library (e.g. "storyteller", "young boy", "grandma").
    Returns voice ids to pass to fish_tts as reference_id, with a sample audio URL to preview."""
    params: dict[str, Any] = {"page_size": max(1, min(limit, 30)), "sort_by": "score"}
    if query:
        params["title"] = query
    if language:
        params["language"] = language
    with httpx.Client(timeout=60, headers={"Authorization": f"Bearer {_fish_key()}"}) as c:
        r = c.get(f"{FISH_API}/model", params=params)
    if r.status_code >= 400:
        raise RuntimeError(f"Fish Audio error {r.status_code}: {r.text[:500]}")
    out = []
    for it in r.json().get("items", []):
        samples = it.get("samples") or []
        out.append({
            "reference_id": it.get("_id"),
            "title": it.get("title"),
            "description": (it.get("description") or "")[:200],
            "tags": it.get("tags"),
            "languages": it.get("languages"),
            "sample_url": (samples[0].get("audio") if samples and isinstance(samples[0], dict) else None),
            "likes": it.get("like_count"),
        })
    return out


@mcp.tool()
def fish_tts(
    text: str,
    filename: str,
    reference_id: str | None = None,
    speed: float = 1.0,
    model: str = "s2.1-pro-free",
) -> dict[str, Any]:
    """Generate speech with Fish Audio and save it as a WAV in OUTPUT_DIR/audio/.
    Use the same reference_id for a character every time so their voice stays identical.
    Emotion/tone cues can be written inline, e.g. "(whispering) I don't know."

    Args:
        text: The line to speak.
        filename: Output file name, e.g. "ep1p1_s1_narrator.wav".
        reference_id: Voice id from fish_voices (or a cloned voice id). Omit for the default voice.
        speed: 0.5-2.0 speaking rate.
        model: Fish Audio model name.
    """
    import wave
    body: dict[str, Any] = {"text": text, "format": "wav", "prosody": {"speed": speed}}
    if reference_id:
        body["reference_id"] = reference_id
    headers = {"Authorization": f"Bearer {_fish_key()}", "model": model}
    with httpx.Client(timeout=httpx.Timeout(120.0)) as c:
        r = c.post(f"{FISH_API}/v1/tts", json=body, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"Fish Audio error {r.status_code}: {r.text[:500]}")
    out_dir = OUTPUT_DIR / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = filename if filename.lower().endswith(".wav") else filename + ".wav"
    dest = out_dir / Path(name).name
    dest.write_bytes(r.content)
    seconds = None
    try:
        with wave.open(str(dest), "rb") as w:
            seconds = round(w.getnframes() / float(w.getframerate()), 2)
    except Exception:
        pass
    return {"path": str(dest), "seconds": seconds, "bytes": len(r.content)}

# --------------------------------------------------------------------------- #
# Kaiyros Discover (pull real TikTok videos) + local transcription
# --------------------------------------------------------------------------- #

import subprocess
import sys

DISCOVER_SCRIPT = Path(os.environ.get(
    "KAIYROS_DISCOVER", "~/Desktop/Projects/Web-Apps/kaiyros/discover-download/discover.py")).expanduser()
TRANSCRIBE_SCRIPT = HERE / "transcribe.py"
_JOBS: dict[str, dict[str, Any]] = {}


def _env() -> dict[str, str]:
    env = dict(os.environ)
    extra = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", str(Path.home() / ".homebrew/bin"), "/usr/local/bin"]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "/usr/bin:/bin")])
    return env


def _uv() -> str:
    for c in (Path.home() / ".local/bin/uv", Path("/opt/homebrew/bin/uv"), Path("/usr/local/bin/uv")):
        if c.exists():
            return str(c)
    return "uv"


def _start(kind: str, cmd: list[str], meta: dict[str, Any]) -> str:
    job_id = f"{kind}-{uuid.uuid4().hex[:8]}"
    log_dir = OUTPUT_DIR / ".jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{job_id}.log"
    proc = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            env=_env(), start_new_session=True)
    _JOBS[job_id] = {"kind": kind, "proc": proc, "log": log, **meta}
    return job_id


def _discover_result(job: dict[str, Any], out: str) -> dict[str, Any]:
    m = re.search(r"Full details: (.+videos\.json)", out)
    if not m:
        return {"state": "failed", "output": out[-1500:]}
    vj = Path(m.group(1).strip())
    videos = json.loads(vj.read_text())
    files = sorted(vj.parent.glob("*.mp4"))
    rows = []
    for i, v in enumerate(videos, 1):
        media, met, cr = v.get("media") or {}, v.get("metrics") or {}, v.get("creator") or {}
        local = next((str(f) for f in files if f.name.startswith(f"{i:03d}_")), None)
        extra = {k: v[k] for k in v if any(s in k.lower() for s in ("transcript", "hook", "caption", "script"))}
        rows.append({"rank": i, "id": v.get("id"), "title": v.get("title"), "creator": cr.get("handle"),
                     "views": met.get("views_total"), "likes": met.get("likes_total"),
                     "posted_at": v.get("posted_at"), "tiktok_url": media.get("canonical_url"),
                     "local_file": local, **extra})
    return {"state": "done", "folder": str(vj.parent), "videos_json": str(vj), "videos": rows,
            "fields_available": sorted(videos[0].keys()) if videos else []}


def _transcribe_result(job: dict[str, Any], out: str) -> dict[str, Any]:
    dest = Path(job["dest"])
    if not dest.exists():
        return {"state": "failed", "output": out[-1500:]}
    data = json.loads(dest.read_text())
    return {"state": "done", "transcript_file": str(dest), **data}


def _job_wait(job_id: str, wait_seconds: int) -> dict[str, Any]:
    job = _JOBS.get(job_id)
    if not job:
        return {"state": "unknown", "error": f"No job {job_id} (the server may have restarted)."}
    deadline = time.time() + max(0, min(wait_seconds, 50))
    while job["proc"].poll() is None and time.time() < deadline:
        time.sleep(1)
    if job["proc"].poll() is None:
        return {"job_id": job_id, "state": "running", "next": "Call job_status with this job_id to keep waiting."}
    out = job["log"].read_text(errors="replace")
    res = (_discover_result if job["kind"] == "discover" else _transcribe_result)(job, out)
    return {"job_id": job_id, **res}


@mcp.tool()
def kaiyros_discover(sort: str = "top", n: int = 1, query: str | None = None, all_videos: bool = False,
                     download: bool = True, wait_seconds: int = 45) -> dict[str, Any]:
    """Pull real TikTok videos from Kaiyros Discover (needs `discover.py setup` done once in a terminal).

    Args:
        sort: "top" (most viewed), "latest" (newest) or "trending" (fastest growing).
        n: How many videos.
        query: Optional search words, e.g. "cat" or "skincare".
        all_videos: Include videos with no linked product.
        download: Save the MP4s (into ~/Movies/comfyui-mcp/discover/<sort>-<date>/).
        wait_seconds: How long to wait before returning a job_id to poll with job_status.
    Returns the videos (title, creator, views, likes, TikTok link, local file) and the folder.
    """
    if sort not in ("top", "latest", "trending"):
        raise ValueError("sort must be top, latest or trending")
    if not DISCOVER_SCRIPT.exists():
        raise RuntimeError(f"discover.py not found at {DISCOVER_SCRIPT}")
    cmd = [sys.executable, str(DISCOVER_SCRIPT), sort, "-n", str(n), "--json",
           "--out", str(OUTPUT_DIR / "discover")]
    if download:
        cmd.append("--download")
    if all_videos:
        cmd.append("--all")
    if query:
        cmd += ["-q", query]
    return _job_wait(_start("discover", cmd, {}), wait_seconds)


@mcp.tool()
def transcribe(path: str, language: str | None = None, wait_seconds: int = 45) -> dict[str, Any]:
    """Transcribe a local video or audio file on this Mac with Whisper (mlx, large-v3-turbo).
    The first run downloads the model (~1.6 GB), so poll with job_status.
    Writes <file>.transcript.json next to the file. Returns text plus timed segments."""
    src = Path(path).expanduser()
    if not src.exists():
        raise FileNotFoundError(src)
    dest = src.with_suffix(".transcript.json")
    if dest.exists():
        return {"state": "done", "transcript_file": str(dest), **json.loads(dest.read_text())}
    cmd = [_uv(), "run", str(TRANSCRIBE_SCRIPT), str(src), str(dest)] + ([language] if language else [])
    return _job_wait(_start("transcribe", cmd, {"dest": str(dest)}), wait_seconds)


@mcp.tool()
def job_status(job_id: str, wait_seconds: int = 45) -> dict[str, Any]:
    """Check on (and wait for) a kaiyros_discover or transcribe job."""
    return _job_wait(job_id, wait_seconds)



# --------------------------------------------------------------------------- #
# Batches: queue many jobs at once, collect finished ones into named files
# --------------------------------------------------------------------------- #

@mcp.tool()
def queue_batch(jobs_path: str) -> dict[str, Any]:
    """Queue every job in a JSON file on the GPU without waiting.

    The file is a list of jobs: {"id", "dest" (path under OUTPUT_DIR, e.g. "ollie/E1/shots/s1_v1.mp4"),
    "prompt", "seconds", "steps", "width", "height", "seed"?, "first_image_path"?,
    "reference_image_paths"?}. Writes <jobs>.manifest.json (used by collect_batch). Jobs already in
    the manifest are skipped, so it is safe to run again.
    """
    jp = Path(jobs_path).expanduser()
    jobs = json.loads(jp.read_text())
    mp = jp.with_suffix(".manifest.json")
    manifest = json.loads(mp.read_text()) if mp.exists() else {}
    queued, errors = 0, []
    uploaded: dict[str, str] = {}
    with _client() as c:
        for j in jobs:
            if j["id"] in manifest:
                continue
            try:
                pid, wf, seed, frames = _submit(
                    c, j["prompt"], j.get("seconds", 5), j.get("steps", 6), j.get("seed"),
                    j.get("width", 1344), j.get("height", 768), j.get("first_image_path"), None,
                    j.get("reference_image_paths"), uploaded, front=bool(j.get("front")))
                manifest[j["id"]] = {"prompt_id": pid, "dest": j["dest"], "workflow": wf, "seed": seed,
                                     "frames": frames, "queued_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                queued += 1
            except Exception as e:  # keep going; report at the end
                errors.append(f"{j['id']}: {e}"[:300])
            mp.write_text(json.dumps(manifest, indent=1))
        q = _check(c.get("/queue")).json()
    return {"queued": queued, "in_manifest": len(manifest), "errors": errors, "manifest": str(mp),
            "gpu_queue": len(q.get("queue_running", [])) + len(q.get("queue_pending", []))}


@mcp.tool()
def collect_batch(manifest_path: str, max_seconds: int = 40) -> dict[str, Any]:
    """Download finished jobs from a batch into their named files (OUTPUT_DIR/<dest>).
    Call repeatedly; each call works for at most max_seconds. Returns progress counts."""
    mp = Path(manifest_path).expanduser()
    manifest = json.loads(mp.read_text())
    deadline = time.monotonic() + min(max_seconds, 50)
    new, errors = [], []
    with _client() as c:
        q = _check(c.get("/queue")).json()
        active = {j[1] for j in q.get("queue_running", []) + q.get("queue_pending", [])}
        for jid, m in manifest.items():
            if m.get("done") or m.get("error") or m["prompt_id"] in active:
                continue
            if time.monotonic() > deadline:
                break
            hist = _check(c.get(f"/history/{m['prompt_id']}")).json()
            if m["prompt_id"] not in hist:
                m["error"] = "missing (not queued or in history)"
                errors.append(jid)
                continue
            entry = hist[m["prompt_id"]]
            if (entry.get("status") or {}).get("status_str") == "error":
                m["error"] = "generation failed"
                errors.append(jid)
                continue
            files = [f for f in _outputs(entry) if f["filename"].endswith(".mp4")]
            if not files:
                continue
            dest = OUTPUT_DIR / m["dest"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            it = files[0]
            params = {"filename": it["filename"], "subfolder": it.get("subfolder", ""), "type": "output"}
            with c.stream("GET", "/view", params=params) as r:
                _check(r)
                with dest.open("wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            m["done"] = True
            new.append(m["dest"])
            mp.write_text(json.dumps(manifest, indent=1))
    mp.write_text(json.dumps(manifest, indent=1))
    vals = list(manifest.values())
    return {"downloaded_now": new, "errors_now": errors,
            "done": sum(1 for v in vals if v.get("done")), "failed": sum(1 for v in vals if v.get("error")),
            "waiting": sum(1 for v in vals if not v.get("done") and not v.get("error")), "total": len(vals),
            "gpu_queue": len(active)}


if __name__ == "__main__":
    mcp.run()
