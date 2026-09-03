import json
import os
from perceive import perceive
from actions import (find_by_id, click, fill_by_name, find_by_name, scroll,
                     select_option_forgiving, find_by_grid, scroll_grid_h,
                     wait_for_lov_options)
import shutil
from report import build_doc
from dotenv import load_dotenv
load_dotenv()
SCREENSHOTS = os.getenv("SCREENSHOTS", "off").lower() == "on"

def replay(page, name):
    path = f"recordings/{name}.json"
    while not os.path.exists(path):
        print(f"no recording named '{name}' in recordings/")
        try:
            available = [f[:-5] for f in os.listdir("recordings") if f.endswith(".json")]
            print("available:", ", ".join(available) if available else "(none)")
        except FileNotFoundError:
            print("available: (no recordings folder yet)")
        name = input("recording name (or blank to exit): ").strip()
        if name == "":
            print("exiting replay")
            return
        path = f"recordings/{name}.json"

    with open(path) as f:
        data = json.load(f)
    # tolerate both shapes: new envelope {name, goal, steps} or old bare array
    if isinstance(data, dict):
        recording = data["steps"]
        goal = data.get("goal", "")
    else:
        recording = data          # old bare-array recording
        goal = ""

    shots = []                                        # just image paths, in order
    if SCREENSHOTS:
        shot_dir = f"recordings/docs/{name}"
        if os.path.exists(shot_dir):
            shutil.rmtree(shot_dir)                   # clear old shots (handles fewer-steps case)
        os.makedirs(shot_dir, exist_ok=True)
    for step in recording:
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=13000)
        except:
            pass

        elements = []
        for attempt in range(5):
            page.wait_for_timeout(2000)
            try:
                elements = perceive(page)
            except Exception as e:
                print(f"perceive failed, retrying {e}")
                page.wait_for_timeout(1000)
                continue
            if len(elements) > 6:
                break
            print(f"page looks empty ({len(elements)} elements), waiting...")

        action = step["action"]
        print(f"replaying: {action} {step.get('name', step.get('value', ''))}")

        if action in ("click", "type"):
            el = None
            is_grid = bool(step.get("grid"))
            for attempt in range(5):
                elements = perceive(page)
                if is_grid:
                    el = find_by_grid(elements, step["grid"], step["row"], step["column"])
                elif step["id"]:
                    el = find_by_id(elements, step["id"])
                else:
                    el = find_by_name(elements, step["name"], step["tag"])
                if el is not None:
                    break
                print(f"'{step['name']}' not found yet, re-perceiving...")
                if is_grid:
                    # The grid is virtualized — an off-screen column isn't in the
                    # DOM at all. Start from the far left, then walk right.
                    scroll_grid_h(page, step["grid"], "reset" if attempt == 0 else 600)
                page.wait_for_timeout(2000)

            if el is None:
                print(f"couldn't find {step['name']} after retries, stopping")
                return False

            if action == "click":
                click(page, el["index"])
            else:  # type
                loc = page.locator(f'[data-ai-index="{el["index"]}"]')
                if is_grid:
                    # A grid cell needs a trusted CLICK to reach edit mode; focus()
                    # leaves it in 'navigation' and the keystrokes go nowhere.
                    # And search-select cells query per keystroke — full-speed
                    # typing strands them on a stale "No matches found".
                    loc.click()
                    page.wait_for_timeout(500)
                    if step.get("mode") == "replace":
                        loc.press("Control+A")
                    page.keyboard.type(step["value"], delay=120)
                else:
                    loc.focus()
                    if step.get("mode") == "replace":
                        loc.press("Control+A")     # select-all so type() overwrites
                    page.keyboard.type(step["value"])
                if step["enter"]:
                    if is_grid:
                        wait_for_lov_options(page)   # never Enter into an empty list
                    else:
                        page.wait_for_timeout(1000)
                    page.keyboard.press("Enter")

        elif action == "fill":
            fill_by_name(page, step["name"], step["value"])

        elif action == "press":
            page.keyboard.press(step["value"])

        elif step["action"] == "nav":
            page.goto(step["value"])

        elif step["action"] == "wait":
            page.wait_for_timeout(3000)
        
        elif step["action"] == "scroll":
            scroll(page, step["target"], step["amount"])

        elif action == "select":
            el = find_by_id(elements, step["id"])
            if el is None:
                print(f"couldn't find select {step['name']}, stopping")
                return False
            select_option_forgiving(page, el["index"], step["value"])

        if SCREENSHOTS:                                           
                page.wait_for_timeout(500)
                img_path = f"{shot_dir}/step_{len(shots)+1}.png"
                page.screenshot(path=img_path)
                shots.append(img_path)

        page.wait_for_timeout(3000)

    if SCREENSHOTS and shots:                                   
        build_doc(name, shots)
    return True