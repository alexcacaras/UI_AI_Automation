# main.pyS
from playwright.sync_api import sync_playwright
from loop import run_loop
from replay import replay

def on_badge_click(index):
         print(f"badge {index} clicked")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    page = browser.new_page(no_viewport=True)
    page.expose_function("badgeClicked", on_badge_click)
    page.goto("https://fa-euum-test-saasfaprod1.fa.ocs.oraclecloud.com")
    input("Log in manually in the browser, then press Enter here and choose the mode...")
    
    mode = input("(a)i drive / (m)anual record / (o)verlay / (p)layback: ").strip().lower()
    if mode == "p":
        replay(page)
    elif mode == "m":
        run_loop(page, mode="manual")
    elif mode == "o":
        from command_center import start_command_center
        start_command_center()
        run_loop(page, mode="overlay")
    else:
        run_loop(page, mode ="ai")

    input("press enter to close")
    browser.close()
