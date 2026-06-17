from playwright.sync_api import sync_playwright
import requests
import json
import time

INSTRUCTION_FILE = "instructions.txt"
MODEL = "qwen3:14b"

with open(INSTRUCTION_FILE, "r", encoding="utf-8") as f:
    instructions = f.read()

completed_actions = []


def ask_ai(current_url="", current_title="", visible_text=""):
    prompt = f"""
You are a browser automation agent.

You are executing this test:

{instructions}

Completed actions:
{completed_actions}

Current page state:
URL: {current_url}
TITLE: {current_title}
VISIBLE TEXT:
{visible_text[:3000]}

Choose the next action.

Rules:
- Return ONLY valid JSON.
- No markdown.
- No explanations.
- Follow the guardrails.
- Choose only ONE next action.
- Use generic browser actions only.

Allowed actions:
- goto
- click_text
- click_input
- type_text
- press_key
- wait
- read_title
- stop

JSON examples:
{{"action":"goto","url":"https://www.google.com"}}
{{"action":"click_input"}}
{{"action":"type_text","text":"Oracle Fusion"}}
{{"action":"press_key","key":"Enter"}}
{{"action":"click_text","text":"Images"}}
{{"action":"wait","seconds":2}}
{{"action":"read_title"}}
{{"action":"stop","reason":"Test complete"}}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False},
    )

    raw = response.json()["response"].strip()

    print("\nRAW AI RESPONSE:")
    print(raw)

    return json.loads(raw)


def execute_action(page, action):
    name = action.get("action")

    print("\nEXECUTING:")
    print(action)

    if name == "goto":
        page.goto(action["url"])
        page.wait_for_load_state("domcontentloaded")

    elif name == "click_input":
        try:
            page.get_by_role("combobox").first.click(timeout=5000)
        except Exception:
            page.locator(
                "input:not([type='hidden']):not([type='file']):visible, textarea:visible"
            ).first.click(timeout=5000)

    elif name == "type_text":
        page.keyboard.type(action["text"])

    elif name == "press_key":
        page.keyboard.press(action["key"])

    elif name == "click_text":
        page.get_by_text(action["text"], exact=False).first.click()

    elif name == "wait":
        time.sleep(int(action.get("seconds", 2)))

    elif name == "read_title":
        print("\nPAGE TITLE:")
        print(page.title())

    elif name == "stop":
        print("\nSTOP:")
        print(action.get("reason", "Test complete"))
        return False

    else:
        raise ValueError(f"Unknown action: {name}")

    completed_actions.append(action)
    return True


print("Loaded instructions:")
print(instructions)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    keep_running = True

    while keep_running:
        if page.url == "about:blank":
            current_url = ""
            current_title = ""
            visible_text = ""
        else:
            current_url = page.url
            current_title = page.title()

            try:
                visible_text = page.locator("body").inner_text(timeout=3000)
            except Exception:
                visible_text = ""

        try:
            action = ask_ai(current_url, current_title, visible_text)
            keep_running = execute_action(page, action)

        except Exception as e:
            print("\nERROR:")
            print(e)
            keep_running = False

    input("Press Enter to close browser...")
    browser.close()