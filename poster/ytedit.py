#!/usr/bin/env python3
"""Change an already-uploaded video in YouTube Studio: visibility, and optionally answer "AI use: No".
    .venv/bin/python ytedit.py <video id> <public|unlisted|private> [--ai-no] [--look]"""
import asyncio, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "social-auto-upload"))
from patchright.async_api import async_playwright
from utils.base_social_media import set_init_script
COOKIE = str(HERE / "social-auto-upload/cookies/youtube_main.json")
NAMES = {"public": "PUBLIC", "unlisted": "UNLISTED", "private": "PRIVATE"}

async def main(vid, visibility, ai_no, look):
    out = {"video": vid}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, channel="chrome")
        c = await set_init_script(await b.new_context(storage_state=COOKIE, viewport={"width": 1400, "height": 1000}))
        page = await c.new_page()
        page.set_default_timeout(20000)
        await page.goto(f"https://studio.youtube.com/video/{vid}/edit", wait_until="domcontentloaded")
        await page.locator("#title-textarea, ytcp-video-title").first.wait_for(state="visible", timeout=60000)
        await page.wait_for_timeout(3000)
        if look:
            out["radios"] = await page.evaluate("() => Array.from(document.querySelectorAll('tp-yt-paper-radio-button')).map(r => [r.getAttribute('name'), r.getAttribute('aria-checked'), (r.innerText||'').trim().slice(0,30)])")
            out["visibility_now"] = await page.evaluate("() => (document.querySelector('ytcp-video-metadata-visibility')?.innerText || '').trim().replace(/\\n/g,' ').slice(0,80)")
        if ai_no:
            try:
                await page.locator("#toggle-button").first.click(timeout=5000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            done = False
            for sel in ("tp-yt-paper-radio-button[name='VIDEO_HAS_ALTERED_CONTENT_NO']",
                        "ytcp-altered-content-select tp-yt-paper-radio-button:has-text('No')",
                        "ytkp-altered-content-select tp-yt-paper-radio-button:has-text('No')"):
                try:
                    el = page.locator(sel).first
                    await el.scroll_into_view_if_needed(timeout=4000)
                    await el.click(timeout=4000)
                    done = sel
                    break
                except Exception:
                    continue
            out["ai_no"] = done
        if visibility:
            await page.locator("ytcp-video-metadata-visibility").first.click()
            await page.wait_for_timeout(1500)
            await page.locator(f"tp-yt-paper-radio-button[name='{NAMES[visibility]}']").first.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(HERE / f"edit_popup_{vid}.png"))
            out["popup_buttons"] = await page.evaluate("() => Array.from(document.querySelectorAll('ytcp-video-visibility-select ytcp-button, tp-yt-paper-dialog ytcp-button, ytcp-video-visibility-edit-popup ytcp-button, ytcp-button')).filter(b => b.offsetParent).map(b => [b.id, (b.innerText||'').trim().slice(0,20)])")
            for sel in ("ytcp-video-visibility-edit-popup #save-button", "ytcp-video-visibility-edit-popup ytcp-button:has-text('Done')", "ytcp-button:has-text('Done'):visible", "#done-button:visible"):
                try:
                    await page.locator(sel).first.click(timeout=4000)
                    out["popup_done"] = sel
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(1500)
        if visibility or ai_no:
            try:
                await page.locator("ytcp-button#save").first.click(timeout=8000)                # page-level Save
                await page.wait_for_timeout(5000)
                out["saved"] = True
            except Exception as e:
                out["saved"] = f"no page save button: {str(e)[:80]}"
        await page.screenshot(path=str(HERE / f"edit_{vid}.png"))
        await c.storage_state(path=COOKIE)
        await b.close()
    print(json.dumps(out))

a = sys.argv[1:]
vis = next((x for x in a[1:] if x in NAMES), None)
asyncio.run(main(a[0], vis, "--ai-no" in a, "--look" in a))
