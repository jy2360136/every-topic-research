"""用 Playwright 截图 candidates.html 演示页"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "topics" / "agent-development" / "candidates.html"
SHOTS = ROOT / "topics" / "agent-development" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(HTML.as_uri())
    page.wait_for_load_state("networkidle")
    # 截全页
    page.screenshot(path=str(SHOTS / "01_initial.png"), full_page=True)
    print("01_initial.png saved")

    # 点击 "全选高分项"
    page.evaluate("selectTop()")
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / "02_top_selected.png"), full_page=True)
    print("02_top_selected.png saved")

    # 点击 "仅选官方字幕"
    page.evaluate("selectOfficial()")
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / "03_official_only.png"), full_page=True)
    print("03_official_only.png saved")

    browser.close()
print("Done.")