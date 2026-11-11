#!/usr/bin/env python3
"""Point the pipeline at a new 5090. Copy the machine's ComfyUI link (the one with ?token=...)
or just the token, then run:   python3 set_5090.py [http://ip:port] [--swap]
(--swap = the person-swap machine; without it, the episode machine)
The token is read from the clipboard and written to ~/comfyui-mcp/connection.json; it is never printed."""
import json
import re
import subprocess
import sys
from pathlib import Path

clip = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
m = re.search(r"token=([A-Za-z0-9]+)", clip)
token = m.group(1) if m else clip
if not re.fullmatch(r"[A-Za-z0-9]{32,128}", token):
    sys.exit("Clipboard does not hold a token or a link with ?token=... Copy it and run again.")
url = next((a for a in sys.argv[1:] if a.startswith("http")), None)
if not url:
    m = re.match(r"(http://\d+\.\d+\.\d+\.\d+:\d+)", clip)
    url = m.group(1) if m else sys.exit("Give the address: python3 set_5090.py http://ip:port")
SWAP = "--swap" in sys.argv        # the person-swap machine keeps its own file
p = Path.home() / "comfyui-mcp" / ("swap_connection.json" if SWAP else "connection.json")
d = json.loads(p.read_text()) if p.exists() else {}
d["url"], d["token"] = url.rstrip("/"), token
p.write_text(json.dumps(d, indent=2))
code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-m", "15", "-w", "%{http_code}", "-H", f"Authorization: Bearer {token}",
                       f"{d['url']}/system_stats?token={token}"], capture_output=True, text=True).stdout
print(f"saved {d['url']} (token {len(token)} characters). Machine answered: {code} " + ("- good" if code == "200" else "- NOT accepted"))
