# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Render a commercial's three clips on the GPU straight from the Mac, with no browser in between.

    uv run render.py ads/<name> [seed]

Needs `adkit.py draw` and `adkit.py build` to have run, the ComfyUI driver in ~/comfyui-mcp, and a connection file
for a GPU that has ComfyUI-MiniMaxDirector and the model files in README.md: ~/comfyui-mcp/swap_connection.json
(made by `python3 set_5090.py --swap`), or the file named in COMFY_CONNECTION. Clips that already exist are kept.
Prints progress lines, then ONE JSON line. Always exits 0.

Not yet proven end to end: the seven example commercials were queued through the GPU's Jupyter page with
box/run_director.py, which builds this same graph.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.home() / "comfyui-mcp"))


def say(**out):
    print(json.dumps(out, ensure_ascii=False))


def graph(timeline, prefix, seed):
    return {
     "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
     "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
     "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"}},
     "5": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
     "6": {"class_type": "MiniMaxDirector", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "audio_vae": ["5", 0], "timeline": timeline, "width": 1344, "height": 768, "ref_image_size": "max"}},
     "7": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
     "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
     "9": {"class_type": "BasicScheduler", "inputs": {"model": ["2", 0], "scheduler": "simple", "steps": 20, "denoise": 1.0}},
     "10": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": ["6", 0]}},
     "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["7", 0], "guider": ["10", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 1]}},
     "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
     "13": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["11", 0], "vae": ["5", 0]}},
     "14": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "audio": ["13", 0], "fps": 24}},
     "15": {"class_type": "SaveVideo", "inputs": {"video": ["14", 0], "filename_prefix": "video/" + prefix, "format": "auto", "codec": "auto"}},
    }


def main():
    folder = Path(sys.argv[1]).resolve()
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 11
    spec = json.loads((folder / "spec.json").read_text())
    name = spec["name"]
    timelines = sorted(folder.glob(f"{name}_[0-9].json"))
    if len(timelines) != len(spec["clips"]):
        return say(ok=False, error="build the timelines first: python3 adkit.py build " + str(folder / "spec.json"))
    missing = [k for k in spec["pictures"] if not (folder / f"{name}_{k}.png").exists()]
    if missing:
        return say(ok=False, error="draw the pictures first; missing: " + ", ".join(missing))
    conn = Path(os.environ.get("COMFY_CONNECTION", Path.home() / "comfyui-mcp" / "swap_connection.json"))
    if not conn.exists():
        return say(ok=False, error=f"no GPU is connected: {conn} does not exist. The owner copies the GPU's ComfyUI link and runs: python3 set_5090.py --swap")
    import server
    server.CONNECTION_FILE = conn                            # the director node and its model files live on the swap GPU
    (folder / "clips").mkdir(exist_ok=True)
    os.environ.setdefault("OUTPUT_DIR", str(folder / "clips" / "_downloads"))
    done, failed = [], []
    with server._client() as c:
        if "MiniMaxDirector" not in c.get("/object_info/MiniMaxDirector").text:
            return say(ok=False, error="this GPU does not have ComfyUI-MiniMaxDirector installed (see README.md, Run it)")
        for k in spec["pictures"]:                           # ComfyUI's input folder, under the file name the timelines use
            server._upload_image(c, str(folder / f"{name}_{k}.png"))
        waiting = {}
        for t in timelines:
            dest = folder / "clips" / f"{t.stem}.mp4"
            if dest.exists():
                done.append(dest.name)
                continue
            r = c.post("/prompt", json={"prompt": graph(t.read_text(), t.stem, seed), "client_id": server.CLIENT_ID})
            body = r.json()
            if r.status_code >= 400 or body.get("node_errors"):
                failed.append(f"{t.stem}: refused: {json.dumps(body)[:300]}")
                continue
            waiting[body["prompt_id"]] = dest
            print("queued", t.stem, flush=True)
        deadline = time.monotonic() + 40 * 60 * max(1, len(waiting))
        while waiting and time.monotonic() < deadline:
            for pid, dest in list(waiting.items()):
                st = server._status(c, pid, download=True)
                if st["state"] == "done":
                    files = [f for f in st.get("local_files", []) if f.endswith(".mp4")]
                    if files:
                        Path(files[0]).replace(dest)
                        done.append(dest.name)
                        print("finished", dest.name, flush=True)
                    else:
                        failed.append(f"{dest.stem}: finished without a video")
                    del waiting[pid]
                elif st["state"] == "error":
                    failed.append(f"{dest.stem}: {str(st.get('error') or 'failed')[:200]}")
                    del waiting[pid]
            time.sleep(20)
        failed += [f"{d.stem}: still not finished after the wait" for d in waiting.values()]
    say(ok=not failed and len(done) == len(timelines), clips=sorted(done), problems=failed)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        say(ok=False, error=f"{type(e).__name__}: {e}"[:400])
