# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27", "numpy"]
# ///
"""Speak one line several times and measure each take, to pick one without a drawn-out or odd ending.
    EPISODE=pbj uv run voice_takes.py <scene n> <how many>
Prints for each take: length, words heard, and the sound bursts (start-end seconds) found by loudness."""
import subprocess, sys
import numpy as np
import make_clips as m
import server
n, count = int(sys.argv[1]), int(sys.argv[2])
line = m.SCRIPT[n - 1]["says"]
for i in range(1, count + 1):
    dest = m.EP / "work" / f"voice{n}_take{i}.wav"
    m.fish_voice(server, line, dest)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(dest), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(pcm, np.int16).astype(float); k = 800                       # 50 ms windows
    rms = np.sqrt((a[:len(a) // k * k].reshape(-1, k) ** 2).mean(axis=1)); on = rms > rms.max() * 0.06
    bursts, start = [], None
    for j, v in enumerate(list(on) + [False]):
        if v and start is None: start = j
        if not v and start is not None:
            if bursts and start - bursts[-1][1] <= 4: bursts[-1][1] = j           # gaps under 0.2 s are inside a word
            else: bursts.append([start, j])
            start = None
    heard = m.heard_in(dest)
    print(i, f"{m.seconds_of(dest):.2f}s", m.score(line, heard), "|", heard, "|", [(round(s * .05, 2), round(e * .05, 2)) for s, e in bursts], flush=True)
