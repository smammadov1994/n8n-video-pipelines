#!/bin/zsh
# Is the episode machine alive? Run:  ~/Desktop/Projects/Web-Apps/kaiyros/n8n-pipeline/status.sh
cd "$(dirname "$0")"
/opt/homebrew/bin/python3 - <<'PY'
import json, os, subprocess, time, glob, sqlite3
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
print(time.strftime("Status at %H:%M, %a %b %d"))
n8n = sh("lsof -tiTCP:5678 -sTCP:LISTEN | head -1")
print("n8n (the engine):      ", "RUNNING" if n8n else "DOWN  <-- nothing will be made or posted")
try:
    row = sqlite3.connect(".n8n/database.sqlite").execute("select startedAt from execution_entity where workflowId='kaiyrosEpisodeMachine1' order by id desc limit 1").fetchone()
    ago = (time.time() - time.mktime(time.strptime(row[0][:19], "%Y-%m-%d %H:%M:%S")) + time.timezone) / 60
    print("last wake-up:          ", f"{ago:.0f} min ago", "(should be under 11)" if ago > 11 else "")
except Exception as e:
    print("last wake-up:           unknown", e)
print("paused:                ", "YES (delete episodes/PAUSE to resume)" if os.path.exists("episodes/PAUSE") else "no")
busy = open("episodes/.busy").read() if os.path.exists("episodes/.busy") else ""
print("making right now:      ", busy or "nothing (between episodes, or list finished)")
code = sh("curl -s -o /dev/null -m 10 -w '%{http_code}' $(/opt/homebrew/bin/python3 -c \"import json,pathlib;print(json.loads((pathlib.Path.home()/'comfyui-mcp/connection.json').read_text())['url'])\")/system_stats")
print("5090 video machine:    ", "answering" if code in ("200", "401", "403") else f"NOT answering ({code or 'no reply'})")
print("Mac power:             ", sh("pmset -g batt | tail -1 | cut -f2 | cut -d';' -f1,2"))
made = sorted(glob.glob("episodes/*/final_fish.mp4"), key=os.path.getmtime)
today = [f for f in made if time.time() - os.path.getmtime(f) < 12 * 3600]
print(f"episodes finished:      {len(made)} total, {len(today)} in the last 12 hours")
for f in today[-4:]:
    print("    ", time.strftime("%H:%M", time.localtime(os.path.getmtime(f))), f.split("/")[1])
posted = sorted(glob.glob("episodes/*/youtube_wide.json"), key=os.path.getmtime)
print(f"published to YouTube:   {len(posted)} episodes (Short + full video each)")
for f in posted[-3:]:
    print("    ", time.strftime("%H:%M", time.localtime(os.path.getmtime(f))), f.split("/")[1])
ready = json.load(open("output/ready_to_post.json")) if os.path.exists("output/ready_to_post.json") else []
waiting = [e["folder"] for e in ready if not os.path.exists(f"episodes/{e['folder']}/youtube_wide.json")]
st = json.load(open("output/posting.json")) if os.path.exists("output/posting.json") else {}
nxt = max(st.get("last_post", 0) + 3 * 3600, st.get("retry_after", 0))
print(f"waiting to publish:     {len(waiting)}" + (f", next at {time.strftime('%H:%M', time.localtime(nxt))}" if waiting else ""))
if st.get("error"): print("last upload problem:   ", str(st["error"])[:120])
look = json.load(open("output/needs_look.json")) if os.path.exists("output/needs_look.json") else []
print(f"flagged, not published: {len(look)}", [e["folder"] for e in look][:4] if look else "")
PY
