# main.pyS
from playwright.sync_api import sync_playwright
from loop import run_loop
from replay import replay

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    page = browser.new_page(no_viewport=True)
    page.goto("https://fa-euum-test-saasfaprod1.fa.ocs.oraclecloud.com")
    input("Log in manually in the browser, then press Enter here and choose the mode...")
    
    mode = input("(a)i drive / (m)anual record / (p)layback: ").strip().lower()
    if mode == "p":
        replay(page)
    elif mode == "m":
        run_loop(page, mode="manual")
    else:
        run_loop(page, mode ="ai")

    input("press enter to close")
    browser.close()
