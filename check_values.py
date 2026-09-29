"""Throwaway: does perceive() now report field values and checkbox state?

Manual test for the perceive change. Deliberately NOT main.py manual mode -
that would make you name and save a recording just to read some output.

    py check_values.py

Log into Oracle, navigate to any page with a form, then press Enter here to
perceive. Type into a field, press Enter here again, and the value should
change. Ctrl+C to stop. Nothing is saved.
"""
import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from perceive import perceive

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "")
if not BASE_URL:
    raise SystemExit("BASE_URL not set - add it to .env")


def show(elements):
    """Only the elements carrying state. An Oracle page perceives well over a
    hundred elements and the interesting ones would be lost in the list."""
    stateful = [e for e in elements
                if "value" in e or "checked" in e or "col_date" in e]
    print(f"\n{len(elements)} elements perceived, {len(stateful)} carry state:")
    for e in stateful:
        bits = []
        if "value" in e:
            bits.append(f"value={e['value']!r}")
        if "checked" in e:
            bits.append(f"checked={e['checked']}")
        if "col_date" in e:
            bits.append(f"col_date={e['col_date']!r}")
        print(f"   {e['index']:>3} <{e['tag']}> {e['name'][:30]!r:<32} "
              f"{'  '.join(bits)}")
    if not stateful:
        print("   (none - are you on a page with form fields?)")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    page = browser.new_page(no_viewport=True)
    page.goto(BASE_URL)
    input("Log in, navigate to a page with a form, then press Enter...")

    while True:
        try:
            show(perceive(page))
        except Exception as e:
            print(f"perceive failed: {e}")
        if input("\nEnter to re-perceive, or 'q' to quit: ").strip().lower() == "q":
            break

    browser.close()
