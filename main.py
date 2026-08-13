# main.py
from playwright.sync_api import sync_playwright
from loop import run_loop
from replay import replay
from overlay import click_queue
from runs import build_order, run_suite

def on_badge_click(info):
    click_queue.put(info)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    page = browser.new_page(no_viewport=True)
    page.expose_function("badgeClicked", on_badge_click)
    page.goto("")
    input("Log in manually in the browser, then press Enter here and choose the mode...")

    mode = input("(a)i / (m)anual / (o)verlay / (p)layback / (r)un: ").strip().lower()

    if mode == "r":
        order = build_order()
        run_suite(page, order)
    elif mode == "p":
        name = input("recording name: ").strip()
        replay(page, name)
    else:
        name = input("recording name: ").strip()
        goal = input("goal for this recording (one line): ").strip()
        if mode == "m":
            run_loop(page, "manual", name, goal)
        elif mode == "o":
            from command_center import start_command_center
            start_command_center()
            run_loop(page, "overlay", name, goal)
        else:
            run_loop(page, "ai", name, goal)

    input("press enter to close")
    browser.close()