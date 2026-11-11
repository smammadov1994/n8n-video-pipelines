"""Rough lip-sync measure for a cartoon mouth: per video frame, how much mouth interior (dark red / pink
pixels in the face area) is showing, compared with how loud the voice is at that moment.
    uv run --with numpy sync_check.py <clip> <x> <y> <w> <h>      (face box in the 1344x768 frame)
Prints the correlation at several time shifts. High at shift 0 = mouth opens when the voice is loud."""
import subprocess, sys
import numpy as np
clip, x, y, w, h = sys.argv[1], *map(int, sys.argv[2:6])
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-vf", f"crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
f = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(int)
r, g, b = f[..., 0], f[..., 1], f[..., 2]
mouth = ((r > 70) & (b > g * 0.9) & (g < 150) & (r > g + 30)).sum(axis=(1, 2)).astype(float)   # pink/red, not orange fur
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-ac", "1", "-ar", "24000", "-f", "s16le", "-"], capture_output=True).stdout
a = np.frombuffer(pcm, np.int16).astype(float)
n = min(len(mouth), len(a) // 1000)
loud = np.sqrt((a[:n * 1000].reshape(n, 1000) ** 2).mean(axis=1)); mouth = mouth[:n]
k = np.ones(3) / 3; loud_s, mouth_s = np.convolve(loud, k, "same"), np.convolve(mouth, k, "same")
def corr(shift):
    if shift >= 0: u, v = mouth_s[shift:], loud_s[:n - shift]
    else: u, v = mouth_s[:n + shift], loud_s[-shift:]
    return float(np.corrcoef(u, v)[0, 1])
speaking = loud > loud.max() * 0.08
print(clip.split("/")[-1], "frames", n, "| mouth more open while voice is on: %.0f vs %.0f px when silent" % (mouth[speaking].mean(), mouth[~speaking].mean() if (~speaking).any() else float("nan")))
print("  correlation by shift (frames, + = mouth late):", {s: round(corr(s), 2) for s in (-6, -4, -2, -1, 0, 1, 2, 4, 6, 12, 24)})
