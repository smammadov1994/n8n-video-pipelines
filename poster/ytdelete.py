#!/usr/bin/env python3
"""Permanently delete ONE video in YouTube Studio. Refuses unless the video's title matches exactly.
    .venv/bin/python ytdelete.py <video id> "<exact title>" [--look]      (--look = stop before deleting)"""
import asyncio, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "social-auto-upload"))
from patchright.async_api import async_playwright
from utils.base_social_media import set_init_script
COOKIE = str(HERE / "social-auto-upload/cookies/youtube_main.json")

async def main(vid, title, look):
    out = {"video": vid, "deleted": False}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, channel="chrome")
        c = await set_init_script(await b.new_context(storage_state=COOKIE, viewport={"width": 1400, "height": 1000}))
        page = await c.new_page()
        page.set_default_timeout(20000)
        await page.goto(f"https://studio.youtube.com/video/{vid}/edit", wait_until="domcontentloaded")
        box = page.locator("#title-textarea #textbox").first
        await box.wait_for(state="visible", timeout=60000)
        await page.wait_for_timeout(2500)
        found = (await box.inner_text()).strip()
        out["title_found"] = found
        if found != title:
            out["error"] = "title does not match, nothing deleted"
        else:
            await page.locator("#overflow-menu-button, ytcp-icon-button#overflow-menu-button").first.click()
            await page.wait_for_timeout(1200)
            out["menu"] = await page.evaluate("() => Array.from(document.querySelectorAll('tp-yt-paper-item, ytcp-text-menu tp-yt-paper-item')).filter(e => e.offsetParent).map(e => (e.innerText||'').trim())")
            await page.screenshot(path=str(HERE / f"delete_menu_{vid}.png"))
            if not look:
                await page.locator("tp-yt-paper-item:has-text('Delete')").first.click()
                await page.wait_for_timeout(1500)
                await page.locator("#confirm-checkbox, ytcp-checkbox-lit#confirm-checkbox, tp-yt-paper-checkbox#confirm-checkbox").first.click()
                await page.wait_for_timeout(600)
                await page.screenshot(path=str(HERE / f"delete_confirm_{vid}.png"))
                await page.locator("#confirm-button, ytcp-button#confirm-button").first.click()
                await page.wait_for_timeout(6000)
                out["deleted"] = True
                out["url_after"] = page.url.split("?")[0]
        await c.storage_state(path=COOKIE)
        await b.close()
    print(json.dumps(out))
a = sys.argv[1:]
asyncio.run(main(a[0], a[1], "--look" in a))
