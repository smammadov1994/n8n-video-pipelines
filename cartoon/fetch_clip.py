# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Pick up a clip whose wait ran out while it was still in the 5090 queue (does not queue anything new).
    EPISODE=pbj uv run fetch_clip.py <scene n> <try> <prompt id>"""
import sys
import make_clips as m
import server
n, attempt, pid = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
dest = m.EP / "clips" / f"scene{n}_try{attempt}.mp4"
with server._client() as c:
    st = server._status(c, pid, download=False)
    print("state:", st["state"], flush=True)
    if st["state"] in ("done", "running", "pending", "queued"):
        m.wait_for(server, c, pid, dest)
        m.check(dest, m.SCRIPT[n - 1]["says"])
