# main.pyS
from playwright.sync_api import sync_playwright
from loop import run_loop
from replay import replay
from overlay import click_queue

def on_badge_click(info):
    click_queue.put(info)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    page = browser.new_page(no_viewport=True)
    page.expose_function("badgeClicked", on_badge_click)
    page.goto("https://fa-euum-dev2-saasfaprod1.fa.ocs.oraclecloud.com")
    input("Log in manually in the browser, then press Enter here and choose the mode...")
    
    mode = input("(a)i drive / (m)anual record / (o)verlay / (p)layback: ").strip().lower()
    name = input("recording name: ").strip()
    if mode == "p":
        replay(page, name)
    elif mode == "m":
        run_loop(page, "manual", name)
    elif mode == "o":
        from command_center import start_command_center
        start_command_center()
        run_loop(page, "overlay", name)
    else:
        run_loop(page, "ai", name)

    input("press enter to close")
    browser.close()
