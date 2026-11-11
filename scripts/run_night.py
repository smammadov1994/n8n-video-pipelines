#!/usr/bin/env python3
"""Make episodes one after another until the topic list or the time budget runs out.

    python3 run_night.py [hours]          # default 9

For each topic: plan (script, fact check, set pictures) -> shoot the Fish-voice version -> shoot
the model-voice version -> refresh episodes/index.html. Everything is cached per episode folder,
so stopping and starting again continues where it left off.

Stop it early:   touch episodes/STOP
Watch it:        episodes/status.json, episodes/night.log, episodes/index.html
"""
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EP = ROOT / "episodes"
UV = str(Path.home() / ".local/bin/uv")

# (topic, where to film). Chosen so the place can be the lesson.
TOPICS = [
    ("Why the ocean is salty when the rivers that feed it are fresh", "a rocky ocean beach; a river mouth or stream running over rocks"),
    ("How honey bees turn flower nectar into honey", "a flower garden beside wooden beehive boxes; a kitchen counter with a jar of honey and honeycomb"),
    ("How a volcano erupts", "a field of black hardened lava rock; the rim of an old volcanic crater"),
    ("Why leaves change color in autumn", "a forest path under red and yellow maple trees; beside a single bright tree with fallen leaves on the ground"),
    ("Why the sea has tides", "a rocky shore with tide pools at low tide; a harbor wall with a visible high-water line"),
    ("How glaciers carve valleys", "a wide U-shaped mountain valley; beside a huge smooth scratched boulder left by ice"),
    ("How trees share food and warnings through fungus in the soil", "an old mossy forest among big tree roots; beside a fallen log covered in mushrooms"),
    ("Why ice floats on water", "the edge of a frozen lake; a kitchen counter with a clear glass of ice water"),
    ("How sand dunes move", "among tall desert sand dunes with wind ripples; the sharp crest of a dune"),
    ("How caves grow stalactites", "the mouth of a limestone cave; inside a lit cave with stalactites behind her"),
    ("How a river carves a canyon", "the rim of a deep red-rock canyon; down by the river at the canyon floor"),
    ("Why the desert gets cold at night", "a rocky desert with cactus in daylight; the same desert under an overcast sky"),
    ("How coral reefs are built by tiny animals", "a tropical beach beside clear shallow water with reef visible; an aquarium wall with living coral behind her"),
    ("How mountains make their own weather", "a mountain meadow with clouds piling against peaks; a dry rocky slope on the far side of a range"),
    ("Why rivers bend and wind instead of running straight", "a grassy bank above a winding river; the inside of a river bend with a gravel bar"),
    ("How a seed knows which way is up", "a vegetable garden with seedlings in rows; a greenhouse bench with sprouting pots"),
]


def slug(text):
    words = re.sub(r"[^a-z0-9 ]", "", text.lower()).split()
    stop = {"why", "how", "the", "a", "an", "is", "are", "its", "their", "when", "that", "it", "of", "and", "in", "to", "by", "do", "does", "has", "have", "which"}
    return "-".join([w for w in words if w not in stop][:3])


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)


def run(cmd, timeout):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout // 60} minutes"}
    lines = [x for x in r.stdout.splitlines() if x.startswith("{")]
    if not lines:
        return {"ok": False, "error": (r.stderr or r.stdout).strip()[-300:] or "no output"}
    try:
        return json.loads(lines[-1])
    except ValueError:
        return {"ok": False, "error": lines[-1][:300]}


def server_up():
    """Is ComfyUI on the 5090 answering? (any reply that is not a gateway error counts)"""
    try:
        url = json.loads((Path.home() / "comfyui-mcp" / "connection.json").read_text())["url"].rstrip("/")
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-m", "10", "-w", "%{http_code}", url + "/system_stats"],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() in ("200", "401", "403")
    except Exception:
        return False


def wait_for_server(deadline):
    """Hold here while the 5090 is away, instead of burning shoot attempts. False = gave up (STOP or out of time)."""
    told = False
    def steady():                      # three good answers 20 s apart, so a one-off blip does not count
        for k in range(3):
            if not server_up():
                return False
            if k < 2:
                time.sleep(20)
        return True
    while not steady():
        if (EP / "STOP").exists() or time.time() > deadline:
            return False
        if not told:
            log("   5090 not answering, waiting for it to come back")
            told = True
        time.sleep(60)
    if told:
        log("   5090 is back")
    return True


def build_index():
    cards = []
    for folder in sorted(p for p in EP.iterdir() if p.is_dir()):
        rf = folder / "result.json"
        if not rf.exists():
            continue
        r = json.loads(rf.read_text())
        post = (folder / "post.txt").read_text() if (folder / "post.txt").exists() else ""
        blocks = []
        for name, label in (("fish", "Fish voice"), ("native", "Model's own voice")):
            v = r.get(name)
            if not v or not v.get("wide"):
                continue
            flags = "".join(f"<li>{html.escape(f)}</li>" for f in v.get("flags", []))
            status = (f'<p class="bad">Needs a look before posting:</p><ul class="bad">{flags}</ul>' if flags
                      else '<p class="ok">Every take passed the word check and the face check.</p>')
            rows = "".join(f"<tr><td>{t['n']}</td><td>{html.escape(t['set'])}</td><td>{html.escape(t['says'])}</td>"
                           f"<td>{round((t['match'] or 0) * 100)}%</td><td>{t.get('face')}</td><td>{t['tries']}</td></tr>" for t in v["takes"])
            blocks.append(
                f'<section><h3>{label} · {v["seconds"]}s · {v.get("minutes", "?")} min to make</h3>'
                f'<div class="pair"><video controls preload="none" src="{folder.name}/final_{name}.mp4"></video>'
                f'<video class="tall" controls preload="none" src="{folder.name}/final_{name}_vertical.mp4"></video></div>{status}'
                f'<details><summary>Takes</summary><table><tr><th>#</th><th>set</th><th>line</th><th>words</th><th>face</th><th>tries</th></tr>{rows}</table></details></section>')
        if blocks:
            cards.append(f'<article><h2>{html.escape(r.get("title") or folder.name)}</h2><p class="dim">{html.escape(folder.name)}</p>'
                         f'{"".join(blocks)}<details><summary>Post text</summary><pre>{html.escape(post)}</pre></details></article>')
    page = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Episodes</title>
<style>
:root{{color-scheme:light dark;--bg:#f6f5f1;--card:#fff;--text:#1a1a18;--dim:#6b6a65;--line:#e3e1da;--ok:#1d7a46;--bad:#b3261e}}
@media(prefers-color-scheme:dark){{:root{{--bg:#151514;--card:#201f1e;--text:#eeede8;--dim:#a09f99;--line:#33322f;--ok:#5fc48a;--bad:#f2857d}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--text);font:14px/1.5 -apple-system,system-ui,sans-serif}}
main{{max-width:980px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:18px;margin:0}} h3{{font-size:14px;margin:16px 0 8px}}
article{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0}}
.pair{{display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}} video{{width:min(100%,640px);border-radius:8px;background:#000}} video.tall{{width:200px}}
.dim{{color:var(--dim);margin:2px 0 0}} .ok{{color:var(--ok)}} .bad{{color:var(--bad)}} ul{{margin:4px 0 8px;padding-left:18px}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px}} td,th{{border-top:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
summary{{cursor:pointer;color:var(--dim);margin-top:8px}} pre{{white-space:pre-wrap;font:inherit}}
</style><main><h1>Episodes</h1><p class="dim">{len(cards)} finished · updated {time.strftime('%Y-%m-%d %H:%M')}</p>{''.join(cards)}</main>"""
    (EP / "index.html").write_text(page)


def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 9
    deadline = time.time() + hours * 3600
    EP.mkdir(exist_ok=True)
    status = {"started": time.strftime("%Y-%m-%d %H:%M"), "episodes": {}}
    gpu_fails = 0
    for i, (topic, where) in [(i, t) for _ in range(2) for i, t in enumerate(TOPICS, 1)]:   # second pass picks up failures
        folder = EP / f"{i:02d}-{slug(topic)}"
        name = folder.name
        if (EP / "STOP").exists() or time.time() > deadline:
            log("stopping: " + ("STOP file" if (EP / "STOP").exists() else "time budget used"))
            break
        rf = folder / "result.json"
        done = json.loads(rf.read_text()) if rf.exists() else {}
        if done.get("fish", {}).get("wide"):                 # Fish voice only (the owner, 2026-11-10: more consistent than the model's voice)
            status["episodes"][name] = "done earlier"
            continue
        folder.mkdir(exist_ok=True)
        log(f"== {name}: planning")
        plan = {"ok": False}
        for attempt in range(2):
            plan = run(["python3", str(HERE / "plan_episode.py"), str(folder), topic, where], 50 * 60)
            if plan.get("ok"):
                break
            log(f"   plan failed: {plan.get('error')}")
        if not plan.get("ok"):
            status["episodes"][name] = f"skipped, planning failed: {plan.get('error')}"
            (EP / "status.json").write_text(json.dumps(status, indent=2))
            continue
        log(f"   planned: {plan.get('title')} | fact fixes: {len(plan.get('fact_fixes', []))}")
        made = {"ok": False}
        for attempt in range(3):
            if (EP / "STOP").exists() or not wait_for_server(deadline):
                break
            made = run([UV, "run", str(HERE / "make_episode.py"), str(folder), "fish"], 90 * 60)
            log(f"   shoot attempt {attempt + 1}: {json.dumps(made)[:400]}")
            if made.get("ok"):
                gpu_fails = 0
                break
            gpu_fails += 1
            time.sleep(120 if gpu_fails < 3 else 600)      # 5090 or tunnel trouble: give it time
        status["episodes"][name] = made
        (EP / "status.json").write_text(json.dumps(status, indent=2))
        try:
            build_index()
        except Exception as e:
            log(f"   index failed: {e}")
    status["finished"] = time.strftime("%Y-%m-%d %H:%M")
    (EP / "status.json").write_text(json.dumps(status, indent=2))
    build_index()
    log("night run finished")


if __name__ == "__main__":
    main()
