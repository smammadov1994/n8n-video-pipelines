#!/usr/bin/env python3
"""List the newest videos on the channel as YouTube Studio shows them (title, visibility). Read-only.
    .venv/bin/python ytlist.py [shorts|videos]"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "social-auto-upload"))
from patchright.async_api import async_playwright
from utils.base_social_media import set_init_script
COOKIE = str(Path(__file__).resolve().parent / "social-auto-upload/cookies/youtube_main.json")
async def main(tab):
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, channel="chrome")
        c = await set_init_script(await b.new_context(storage_state=COOKIE))
        page = await c.new_page()
        await page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
        for _ in range(15):
            await page.wait_for_timeout(1000)
            if "/channel/" in page.url: break
        await page.goto(page.url.split("?")[0].rstrip("/") + f"/videos/{'short' if tab == 'shorts' else 'upload'}", wait_until="domcontentloaded")
        await page.wait_for_timeout(7000)
        rows = await page.evaluate("""() => Array.from(document.querySelectorAll('ytcp-video-row')).slice(0, 8).map(r => ({
            title: (r.querySelector('#video-title')?.textContent || '').trim(),
            link: r.querySelector('#video-title')?.getAttribute('href') || '',
            visibility: (r.querySelector('.tablecell-visibility')?.innerText || '').trim().split('\\n')[0],
            restrictions: (r.querySelector('.tablecell-restrictions')?.innerText || '').trim().replace(/\\n/g, ' '),
            date: (r.querySelector('.tablecell-date')?.innerText || '').trim().replace(/\\n/g, ' '),
            views: (r.querySelector('.tablecell-views')?.innerText || '').trim(), comments: (r.querySelector('.tablecell-comments')?.innerText || '').trim()}))""")
        print(json.dumps({"tab": tab, "rows": rows}, indent=1))
        await b.close()
asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "shorts"))
