import json
from perceive import perceive
from actions import find_by_id, click



def replay(page):
    with open("recording.json") as f:
        recording = json.load(f)

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

        el = find_by_id(elements, step["id"])
        if el is None:
            print(f"couldn't find {step['name']}, stopping")
            break

        print(f"replaying: {step['action']} {step['name']}")
        click(page, el["index"])
        page.wait_for_timeout(3000)