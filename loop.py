from perceive import perceive
from actions import click, fill_by_name, did_change, do_click, do_type_python, do_type_live, scroll
from llm import ask_llm
from actions import search_element, select_option_forgiving
import json
from overlay import draw_overlays, install_listener, click_queue
from command_center import command_queue
import queue
import os

#loop file


def run_loop(page, mode, name, goal):
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
                elif pending_step["action"] == "select":
                    recording.append(pending_step)
                pending_step = None

        previous_elements = elements
        #cmd = input("\naction? (click N / type N text / nav URL / press N / wait / fill / done):").strip()
        #goal = "Open the Navigator and go to My Client Groups and then go to Workforce Structures. You are done when the page shows Workforce Structures items like 'Positions', 'Jobs', and 'Request a New Position' — when you see those, respond with: done"
        if mode == "manual":
            #page.wait_for_timeout(500)
            draw_overlays(page)
            cmd = input("\naction? (click N / type N text / nav URL / press N / wait / fill / select / done):").strip()
        elif mode == "overlay":
            draw_overlays(page)
            install_listener(page)

            cc_cmd = None
            click_info = None
            action = None
            while True:
                # 1. did a click arrive from the browser? (pushed, not polled)
                try:
                    click_info = click_queue.get_nowait()
                    break
                except queue.Empty:
                    pass

                # 2. did a command-center button fire?
                try:
                    cc_cmd = command_queue.get_nowait()
                    break
                except queue.Empty:
                    pass

                # 3. did a keystroke seal or a press happen?
                try:
                    handle = page.wait_for_function(
                        "window._lastAction !== null ? window._lastAction : null",
                        timeout=300
                    )
                    action = handle.json_value()
                    page.evaluate("window._lastAction = null;")
                    break
                except:
                    continue

            if cc_cmd is not None:
                cmd = cc_cmd
            elif click_info is not None:
                step = {"action": "click", "id": click_info.get("id",""), "name": click_info.get("name",""),
                        "role": click_info.get("role",""), "tag": click_info.get("tag","")}
                recording.append(step)
                cmd = "overlay_done"
            elif action is not None and action["kind"] == "seal":
                print(f">>> SEAL: value='{action['value']}' target={action['target']}")
                if action["value"] != "":
                    t = action["target"] or {}
                    step = {"action": "type", "id": t.get("id",""), "name": t.get("name",""),
                            "role": "", "tag": t.get("tag",""),
                            "value": action["value"], "mode": action["mode"], "enter": False}
                    recording.append(step)
                cmd = "overlay_done"
            elif action is not None and action["kind"] == "press":
                step = {"action": "press", "value": action["value"]}
                recording.append(step)
                cmd = "overlay_done"
            elif action is not None and action["kind"] == "select":
                t = action["target"]
                step = {"action": "select", "id": t.get("id",""), "name": t.get("name",""),
                        "role": t.get("role",""), "tag": t.get("tag",""), "value": t.get("value","")}
                recording.append(step)
                cmd = "overlay_done"
        else:
            ai_cmd = ask_llm(elements, goal, history[-5:]).strip()
            if ai_cmd.startswith("nav"):
                ai_cmd = "nav (insert url))"
            print(f"\n AI wants to:{ai_cmd}")
            cmd = input("Press Enter to run it, or type your own command to override: ").strip()
            if cmd == "":
                cmd = ai_cmd
        try:
            if cmd == "done":
                done = True
            elif cmd == "overlay_done":
                pass
            elif cmd.startswith("click "):
                index = int(cmd.split()[1])
                pending_step = do_click(page, index, elements)

            elif cmd.startswith("type "):
                parts = cmd.split(maxsplit=2)
                index = int(parts[1])
                text = parts[2]
                press_enter = text.endswith(" Enter")
                if press_enter:
                    text = text[:-6]
                pending_step = do_type_python(page, index, text, press_enter, elements)

            elif cmd.startswith("fill "):
                rest = cmd.split(maxsplit=1)[1]                       
                if "|" not in rest:
                    print("usage: fill <field name> | <value>")
                else:
                    field_name, value = rest.split("|", 1)
                    field_name = field_name.strip().strip('\'"')
                    value = value.strip().strip('\'"')
                    fill_by_name(page, field_name, value)
                    #fill_by_name(page, name.strip().strip('\'"'), value.strip().strip('\'"'))
                    pending_step = {"action": "fill", "name": field_name, "value": value}

            elif cmd.startswith("nav "):
                url = cmd.split(maxsplit=1)[1]
                if not url.startswith("http"):
                    url = "https://" + url
                page.goto(url)
                recording.append({"action": "nav", "value": url})

            elif cmd.startswith("press "):
                parts = cmd.split()
                key = parts[1]
                count = int(parts[2]) if len(parts) > 2 else 1   
                for _ in range(count):
                    page.keyboard.press(key)
                pending_step = {"action": "press", "value": key}

            elif cmd == "wait":
                page.wait_for_timeout(3000)
                recording.append({"action": "wait"})

            elif cmd.startswith("scroll "):
                parts = cmd.split()
                target = parts[1]
                amount = int(parts[2]) if len(parts) > 2 else 600
                scroll(page, target, amount)
                recording.append({"action": "scroll","target": target, "amount": amount})

            elif cmd.startswith("select "):
                parts = cmd.split(maxsplit=2)      # ["select", "N", "Sold to"]
                index = int(parts[1])
                value = parts[2]
                # act: set the select
                select_option_forgiving(page, index, value)
                # record: capture the element's identity
                el = search_element(elements, index)
                pending_step = {"action": "select", "id": el["id"], "name": el["name"],
                                "role": el["role"], "tag": el["tag"], "value": value}
            else:
                print("didnt understand that - try: click 9 / type 9 hello / nav http://... / press Enter / wait / fill / scroll / done")
            history.append({"cmd": cmd, "result": "pending"})
            print("recent:", history[-5:])
        except Exception as e:
            print(f"action failed {e}")
            history.append({"cmd": cmd, "result": f"error: {str(e).splitlines()[0]}"})
            print("recent:", history[-5:])

     os.makedirs("recordings", exist_ok=True)
     while True:
         path = f"recordings/{name}.json"
         if not os.path.exists(path):
             break                                    # name is free, done
         confirm = input(f"'{name}' exists — overwrite? (y/n): ").strip().lower()
         if confirm == "y":
             break                                    # user chose to overwrite, done
         name = input("enter a new name: ").strip()   # otherwise loop with the new name

     envelope = {"name": name, "goal": goal, "steps": recording}
     with open(path, "w") as f:
         json.dump(envelope, f, indent=2)
     print(f"saved {len(recording)} steps to recordings/{name}.json")