#!/usr/bin/env python3
"""Steps of the n8n "Swap machine" workflow. Each prints ONE JSON line and exits 0.

    swap_job.py prep <top|trending|latest> <look at> <keep>   pick + prepare Kaiyros clips (her voice) -> swap/ready/
    swap_job.py send        upload prepared clips to the swap machine's queue
    swap_job.py collect     download finished swaps -> swap/finished/<id>.mp4 (+ <id>.json: creator, product, words)
    swap_job.py status

The swap machine is a second Vast box (see swap/box/install.sh, queue.sh, run_swap.py). The Mac reaches it through
~/comfyui-mcp/swap_connection.json {"url": "http://ip:port", "token": "..."}: the owner copies the ComfyUI IP link in that
machine's Instance Portal and runs  python3 set_5090.py --swap   (Claude cannot read the token).
Without that file, send/collect say so and do nothing; clips can still be moved by hand through the Jupyter page.
"""
import json, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
READY, DONE, SENT = HERE / "ready", HERE / "finished", HERE / "sent"
CONN = Path.home() / "comfyui-mcp" / "swap_connection.json"
for d in (READY, DONE, SENT): d.mkdir(exist_ok=True)

def say(**o): print(json.dumps(o))

def conn():
    if not CONN.exists():
        return None
    c = json.loads(CONN.read_text())
    return c["url"].rstrip("/"), c["token"]

def curl(args, timeout=600):
    return subprocess.run(["curl", "-s", "-m", str(timeout), *args], capture_output=True, text=True)

def prep(which="trending", look="60", keep="14"):
    r = subprocess.run([sys.executable, str(HERE / "prep_swaps.py"), which, look, keep], capture_output=True, text=True, timeout=3 * 3600)
    lines = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
    say(ok=True, looked_at=sum(1 for x in lines if "id" in x), kept_now=sum(1 for x in lines if x.get("kept")), ready=len(list(READY.glob("*.mp4"))))

def send():
    c = conn()
    if not c:
        return say(ok=False, why="swap machine not connected (no ~/comfyui-mcp/swap_connection.json)", waiting=len(list(READY.glob("*.mp4"))))
    url, tok = c; sent = []
    for clip in sorted(READY.glob("*.mp4")):
        mark = SENT / clip.stem
        if mark.exists() or (DONE / clip.name).exists():
            continue
        r = curl(["-o", "/dev/null", "-w", "%{http_code}", "-H", f"Authorization: Bearer {tok}", "-F", f"image=@{clip};filename=q_{clip.name}", "-F", "overwrite=true", f"{url}/upload/image"])
        if r.stdout.strip() == "200":
            mark.write_text(time.strftime("%Y-%m-%d %H:%M")); sent.append(clip.stem)
    say(ok=True, sent=sent, in_queue=len(list(SENT.glob("*"))))

def collect():
    c = conn()
    if not c:
        return say(ok=False, why="swap machine not connected (no ~/comfyui-mcp/swap_connection.json)", finished=len(list(DONE.glob("*.mp4"))))
    url, tok = c; got = []
    for mark in sorted(SENT.glob("*")):
        out = DONE / f"{mark.name}.mp4"
        if out.exists():
            continue
        r = curl(["-o", str(out), "-w", "%{http_code}", "-H", f"Authorization: Bearer {tok}", f"{url}/view?filename={mark.name}.mp4&subfolder=swap_results&type=output"])
        if r.stdout.strip() == "200" and out.stat().st_size > 100000:
            meta = READY / f"{mark.name}.json"
            if meta.exists(): (DONE / meta.name).write_text(meta.read_text())
            got.append(mark.name)
        else:
            out.unlink(missing_ok=True)
    say(ok=True, collected=got, finished=len(list(DONE.glob("*.mp4"))), still_swapping=len([m for m in SENT.glob("*") if not (DONE / f"{m.name}.mp4").exists()]))

def status():
    say(ok=True, connected=CONN.exists(), ready=len(list(READY.glob("*.mp4"))), sent=len(list(SENT.glob("*"))), finished=len(list(DONE.glob("*.mp4"))))

if __name__ == "__main__":
    step, args = (sys.argv[1] if len(sys.argv) > 1 else "status"), sys.argv[2:]
    try:
        {"prep": prep, "send": send, "collect": collect, "status": status}[step](*args)
    except Exception as e:
        say(ok=False, why=f"{type(e).__name__}: {e}"[:300])
