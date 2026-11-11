#!/usr/bin/env python3
"""Post finished episodes to YouTube through social-auto-upload's browser uploader (YouTube Studio, signed-in Chrome).

    .venv/bin/python yt.py login                       # opens Chrome; sign in to YouTube once (up to 10 minutes)
    .venv/bin/python yt.py check                       # is the saved sign-in still good?
    .venv/bin/python yt.py upload <episode folder> [private|unlisted|public] [both|vertical|wide] [--declare-ai]

Only the YouTube part of the repo is loaded. The saved sign-in lives in social-auto-upload/cookies/youtube_main.json:
whoever has that file is signed in as the channel, so it never leaves this Mac.
Every upload is marked "not made for kids". The "AI use" question is left untouched unless --declare-ai is added.
Prints one JSON line. An episode is never uploaded twice: the result is kept in <episode>/youtube_vertical.json and youtube_wide.json.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / "social-auto-upload"
sys.path.insert(0, str(REPO))
COOKIE = REPO / "cookies" / "youtube_main.json"
COOKIE.parent.mkdir(exist_ok=True)

from patchright.async_api import async_playwright  # noqa: E402
from uploader.youtube_uploader.main import YouTubeVideo, youtube_cookie_gen  # noqa: E402
from utils.base_social_media import set_init_script  # noqa: E402


async def cookie_auth(account_file):
    """Is the saved sign-in still good? The repo's own check runs Chrome hidden, and hidden Chrome never
    reaches the channel page, so it always says no. This one opens a visible window for a few seconds."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        try:
            context = await set_init_script(await browser.new_context(storage_state=account_file))
            page = await context.new_page()
            await page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
            for _ in range(10):
                await page.wait_for_timeout(1000)
                if "/channel/" in page.url:
                    return True
                if "accounts.google.com" in page.url:
                    return False
            return False
        except Exception:
            return False
        finally:
            await browser.close()


def say(**out):
    print(json.dumps(out))


def post_text(folder):
    """post.txt is: title, blank line, description, blank line, hashtags."""
    parts = [p.strip() for p in (folder / "post.txt").read_text().split("\n\n") if p.strip()]
    title = parts[0][:95]
    tags = [w.lstrip("#") for w in (parts[2].split() if len(parts) > 2 else [])]
    description = (parts[1] if len(parts) > 1 else "") + ("\n\n" + parts[2] if len(parts) > 2 else "")
    return title, description, tags


async def upload(folder, visibility, shape):
    if shape == "both":                                   # the Short first, then the full wide video
        for one in ("vertical", "wide"):
            await upload(folder, visibility, one)
        return
    record = folder / f"youtube_{shape}.json"
    if record.exists():
        return say(ok=True, already=True, **json.loads(record.read_text()))
    video = folder / ("final_fish_vertical.mp4" if shape == "vertical" else "final_fish.mp4")
    if not video.exists():
        return say(ok=False, error=f"no video at {video}")
    if not COOKIE.exists() or not await cookie_auth(str(COOKIE)):
        return say(ok=False, error="not signed in to YouTube: run  .venv/bin/python yt.py login")
    title, description, tags = post_text(folder)
    if shape == "vertical" and "#Shorts" not in description:
        description += " #Shorts"
    if shape == "wide":
        description = description.replace(" #Shorts", "")
    app = YouTubeVideo(title, str(video), tags, str(COOKIE), description=description, visibility=visibility, headless=False)
    app.altered_content = "--declare-ai" in sys.argv     # off by default (the owner, 2026-11-11); add --declare-ai to tick "AI use: Yes"
    app.shot_dir = str(folder)
    app.published, app.video_url = False, ""
    await app.main()
    out = {"folder": folder.name, "title": title, "visibility": visibility, "shape": shape, "url": app.video_url,
           "altered_content_declared": getattr(app, "altered_declared", False), "when": time.strftime("%Y-%m-%d %H:%M")}
    if app.published:
        record.write_text(json.dumps(out, indent=2))
    say(ok=app.published, **out)


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "login":
        r = asyncio.run(youtube_cookie_gen(str(COOKIE)))
        if r["success"]:
            COOKIE.chmod(0o600)
        return say(ok=r["success"], status=r["status"])
    if step == "check":
        return say(ok=COOKIE.exists() and asyncio.run(cookie_auth(str(COOKIE))))
    if step == "upload":
        folder = Path(sys.argv[2]).resolve()
        visibility = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "public"   # public every time (the owner, 2026-11-11)
        shape = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else "both"   # Short + full video (the owner, 2026-11-11)
        try:
            return asyncio.run(upload(folder, visibility, shape))
        except Exception as e:
            return say(ok=False, folder=folder.name, error=f"{type(e).__name__}: {e}"[:300])
    print(__doc__)


if __name__ == "__main__":
    main()
