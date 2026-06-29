from perceive import perceive
from actions import click, fill_by_name, did_change
from llm import ask_llm
from actions import search_element
import json
from overlay import draw_overlays

#loop file


def run_loop(page, mode):
     done = False
     history = []
     previous_elements = None
     recording = []
     pending_step = None
     while not done:
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=13000)
        except:
            pass    # some Oracle pages never fully idle — don't hang, just proceed
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
        print("\n--- PAGE NOW ---")
        for el in elements:
            print(el)
        if previous_elements is not None and history:
            verdict = did_change(previous_elements, elements)
            if history[-1]["result"] == "pending":
                history[-1]["result"] = verdict
            if pending_step is not None:
                if pending_step["action"] == "click":
                    if verdict == "changed":
                        recording.append(pending_step)
                elif pending_step["action"] == "press":
                    recording.append(pending_step)
                elif pending_step["action"] == "type":
                    recording.append(pending_step)
                elif pending_step["action"] == "fill":
                    recording.append(pending_step)
                pending_step = None

        previous_elements = elements
        #cmd = input("\naction? (click N / type N text / nav URL / press N / wait / fill / done):").strip()
        goal = "Open the Navigator and go to My Client Groups and then go to Workforce Structures. You are done when the page shows Workforce Structures items like 'Positions', 'Jobs', and 'Request a New Position' — when you see those, respond with: done"
        if mode == "manual":
            #page.wait_for_timeout(500)
            draw_overlays(page)
            cmd = input("\naction? (click N / type N text / nav URL / press N / wait / fill / done):").strip()
        elif mode == "overlay":
            draw_overlays(page)
            page.evaluate("window.lastClickedBadge = null")
            page.wait_for_function("window.lastClickedBadge !== null", timeout=0)
            index = page.evaluate("window.lastClickedBadge")
            page.evaluate("document.querySelectorAll('.ai-overlay-badge').forEach(b => b.remove())")
            cmd = f"click {index}"
        else:
            ai_cmd = ask_llm(elements, goal, history[-5:]).strip()
            if ai_cmd.startswith("nav"):
                ai_cmd = "nav https://fa-euum-test-saasfaprod1.fa.ocs.oraclecloud.com"
            print(f"\n AI wants to:{ai_cmd}")
            cmd = input("Press Enter to run it, or type your own command to override: ").strip()
            if cmd == "":
                cmd = ai_cmd
        try:
            if cmd == "done":
                done = True
            elif cmd.startswith("click "):
                index = int(cmd.split()[1])
                click(page, index)
                el = search_element(elements, index)
                pending_step = {"action": "click", "id": el["id"], "name": el["name"], "role": el["role"], "tag": el["tag"]}

            elif cmd.startswith("type "):
                parts = cmd.split(maxsplit=2)
                index = int(parts[1])
                text = parts[2]
                press_enter = text.endswith(" Enter")
                if press_enter:
                    text = text[:-6]
                page.locator(f'[data-ai-index="{index}"]').focus()
                page.keyboard.type(text)
                if press_enter:
                    page.keyboard.press("Enter")
                el = search_element(elements, index)
                pending_step = {"action": "type", "id": el["id"], "name": el["name"], "role": el["role"], "tag": el["tag"], "value": text, "enter": press_enter}

            elif cmd.startswith("fill "):
                rest = cmd.split(maxsplit=1)[1]                       
                if "|" not in rest:
                    print("usage: fill <field name> | <value>")
                else:
                    name, value = rest.split("|", 1)
                    name = name.strip().strip('\'"')
                    value = value.strip().strip('\'"')
                    fill_by_name(page, name, value)
                    #fill_by_name(page, name.strip().strip('\'"'), value.strip().strip('\'"'))
                    pending_step = {"action": "fill", "name": name, "value": value}

            elif cmd.startswith("nav "):
                url = cmd.split(maxsplit=1)[1]
                page.goto(url)

            elif cmd.startswith("press "):
                parts = cmd.split()
                key = parts[1]
                count = int(parts[2]) if len(parts) > 2 else 1   
                for _ in range(count):
                    page.keyboard.press(key)
                pending_step = {"action": "press", "value": key}

            elif cmd == "wait":
                page.wait_for_timeout(3000)
            else:
                print("didnt understand that - try: click 9 / type 9 hello / nav http://... / press Enter / wait / fill / done")
            history.append({"cmd": cmd, "result": "pending"})
            print("recent:", history[-5:])
        except Exception as e:
            print(f"action failed {e}")
            history.append({"cmd": cmd, "result": f"error: {str(e).splitlines()[0]}"})
            print("recent:", history[-5:])

     with open("recording.json", "w") as f:
         json.dump(recording, f, indent=2)
     print(f"saved {len(recording)} steps to recording.json")