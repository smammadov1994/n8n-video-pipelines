#!/usr/bin/env python3
"""Add captions, a product tag and an end card to finished swaps, with raea (https://github.com/shinyobjectz/raea).
Runs on the Mac, no GPU rental. Replaces the by-hand CapCut step: the text is drawn by code, so it is always spelled right.

    caption_job.py            caption every swap/finished/<id>.mp4 that has no swap/captioned/<id>.mp4 yet
    caption_job.py <id>       caption (or re-caption) one

Per video: a small raea project in swap/caption_work/<id>/ (the clip, word timings heard from the clip itself,
edit.tsx from caption_template/), rendered to swap/captioned/<id>.mp4. Prints one JSON line and always exits 0.
The look lives in caption_template/edit.tsx: change it there and re-run with an id to redo a clip.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
FINISHED, DONE, WORK, TEMPLATE = HERE / "finished", HERE / "captioned", HERE / "caption_work", HERE / "caption_template" / "edit.tsx"
RAEA = str(Path.home() / ".local/bin/raea")
os.environ["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

NAME = """A TikTok Shop product listing is named:
{listing}
Give the short name a person would call this product out loud: the brand if there is a clear one, then what it is.
At most 4 words, at most 26 characters, title case, no emoji, no quotes. Answer with ONLY that name."""


def run(cmd, cwd=None, timeout=1800):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def short_name(listing):
    """A short product name for the tag and the end card (asked once, then kept in the clip's json)."""
    plain = re.sub(r"[\[\]【】|,(].*", "", listing or "").strip()
    fallback = " ".join(plain.split()[:4])[:26] or "This product"
    r = run(["claude", "-p", NAME.format(listing=listing), "--model", "sonnet", "--setting-sources", ""], timeout=180)
    name = (r.stdout or "").strip().splitlines()[-1].strip(" \"'.") if r.returncode == 0 and r.stdout.strip() else ""
    return name if 2 <= len(name) <= 30 else fallback


def caption(vid):
    src, meta_file = FINISHED / f"{vid}.mp4", FINISHED / f"{vid}.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    if not meta.get("short_name"):
        meta["short_name"] = short_name(meta.get("product", ""))
        if meta_file.exists():
            meta_file.write_text(json.dumps(meta, indent=2))
    proj = WORK / vid
    (proj / "media").mkdir(parents=True, exist_ok=True)
    take = proj / "media" / "take.mp4"
    if not take.exists():                                    # 1080x1920, 30 fps: the size the template is laid out for
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
             "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(take)], timeout=600)
    seconds = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(take)]).stdout.strip())
    if not (proj / "media" / "take.words.json").exists():    # cutting on a line makes raea listen to the clip first;
        run([RAEA, "cut", "media/take.mp4", "zzzz"], cwd=proj)   # the made-up line is never found, the word timings are kept
    r = run([RAEA, "cut", "media/take.mp4", "--at", f"0-{seconds - 0.05:.2f}"], cwd=proj)
    words = json.loads((proj / "words.json").read_text()) if (proj / "words.json").exists() else []
    if not words:
        raise RuntimeError("raea heard no words in the clip: " + (r.stderr or r.stdout)[-200:])
    (proj / "edit.tsx").write_text(TEMPLATE.read_text().replace("__PRODUCT__", meta["short_name"].replace('"', "'")))
    DONE.mkdir(exist_ok=True)
    out = DONE / f"{vid}.mp4"
    r = run([RAEA, "render", "edit.tsx", "-o", str(out), "--kbps", "9000", "--manifest", "render.json"], cwd=proj)
    if not out.exists():
        raise RuntimeError("raea render failed: " + (r.stderr or r.stdout)[-300:])
    check = run([RAEA, "check", str(out), "--manifest", "render.json", "--words", "words.json"], cwd=proj).stdout
    serious = [l for l in check.splitlines() if l.startswith("error") and l.split()[1] in ("clipped", "safe-area", "reading", "cues", "frozen", "flashing")]
    return {"id": vid, "ok": True, "name": meta["short_name"], "words": len(words), "seconds": round(seconds + 2.8, 1),
            "mb": round(out.stat().st_size / 1e6, 1), "problems": [l[:140] for l in serious]}


def main():
    ids = sys.argv[1:] or sorted(p.stem for p in FINISHED.glob("*.mp4") if not (DONE / p.name).exists())
    results = []
    for vid in ids:
        try:
            res = caption(vid)
        except Exception as e:
            res = {"id": vid, "ok": False, "why": f"{type(e).__name__}: {e}"[:300]}
        results.append(res)
        print(json.dumps(res), file=sys.stderr, flush=True)                 # progress, one line per clip
    print(json.dumps({"ok": all(r["ok"] for r in results), "captioned": [r["id"] for r in results if r["ok"]],
                      "failed": [r["id"] for r in results if not r["ok"]],
                      "with_problems": [r["id"] for r in results if r.get("problems")],
                      "total_captioned": len(list(DONE.glob("*.mp4"))) if DONE.exists() else 0}))


if __name__ == "__main__":
    main()
