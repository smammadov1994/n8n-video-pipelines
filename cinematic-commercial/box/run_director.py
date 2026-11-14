"""On the GPU box: queue director clips.   python3 run_director.py SEED timeline1.json [timeline2.json ...]   (FRONT=1 puts them at the head of the queue)
Each clip is saved as ComfyUI/output/video/<timeline name>_00001_.mp4. Plain 20-step path of the pack's workflow, 1344x768."""
import json, os, sys, urllib.request
from pathlib import Path
seed = int(sys.argv[1])
for path in sys.argv[2:]:
    tl = Path(path).read_text()
    g = {
     "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
     "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
     "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"}},
     "5": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
     "6": {"class_type": "MiniMaxDirector", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "audio_vae": ["5", 0], "timeline": tl, "width": 1344, "height": 768, "ref_image_size": "max"}},
     "7": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
     "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
     "9": {"class_type": "BasicScheduler", "inputs": {"model": ["2", 0], "scheduler": "simple", "steps": 20, "denoise": 1.0}},
     "10": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": ["6", 0]}},
     "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["7", 0], "guider": ["10", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 1]}},
     "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
     "13": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["11", 0], "vae": ["5", 0]}},
     "14": {"class_type": "CreateVideo", "inputs": {"images": ["12", 0], "audio": ["13", 0], "fps": 24}},
     "15": {"class_type": "SaveVideo", "inputs": {"video": ["14", 0], "filename_prefix": "video/" + Path(path).stem, "format": "auto", "codec": "auto"}},
    }
    req = urllib.request.Request("http://localhost:18188/prompt", json.dumps({"prompt": g, "front": bool(os.environ.get("FRONT"))}).encode(), {"Content-Type": "application/json"})
    try:
        print(Path(path).stem, urllib.request.urlopen(req).read().decode()[:200])
    except urllib.error.HTTPError as e:
        print(Path(path).stem, "REFUSED", e.read().decode()[:800])
