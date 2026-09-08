import json
import os
from perceive import perceive
from actions import (click, fill_by_name, scroll, select_option_forgiving,
                     resolve, scroll_grid_h, wait_for_lov_options)
import shutil
from report import build_doc
from llm import heal_step
from writeback import plan_repair, describe_repair, apply_repairs
from dotenv import load_dotenv
load_dotenv()
SCREENSHOTS = os.getenv("SCREENSHOTS", "off").lower() == "on"
HEALER = os.getenv("HEALER", "on").lower() == "on"
# PHASE 6 TIER 2. Repair a recording whose locators have drifted, so the next
# run matches on rank 1 and pays nothing. Off switch here because a write-back
# edits the user's recording, and recordings/ is gitignored.
WRITEBACK = os.getenv("WRITEBACK", "on").lower() == "on"
# CONSECUTIVE heals, not total. Two heals far apart in a run are two unrelated
# Oracle changes, both legitimately repaired. Heals BACK TO BACK are different:
# each one runs on a page the previous heal navigated to, so once one is wrong
# the rest are guaranteed garbage and the run walks further off course while
# still reporting progress. After this many in a row, stop trusting the healer.
MAX_CONSECUTIVE_HEALS = int(os.getenv("HEALER_MAX_CONSECUTIVE", "3"))

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
    consecutive_heals = 0        # reset by any step that resolves on its own
    total_heals = 0              # reported at the end of the run
    # Repairs are BUFFERED, not written when they are found. A repair claims the
    # new locator points at the element the step meant, and the evidence for that
    # claim is the rest of the run working from the page this step landed on. If
    # the run dies later, these are dropped and the recording is untouched — the
    # next run simply degrades (or heals) again and offers the same repair.
    repairs = []                 # (step_index, {field: new_value})

    for step_index, step in enumerate(recording):
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
            rank = "no match"
            is_grid = bool(step.get("grid"))
            for attempt in range(5):
                elements = perceive(page)
                el, rank = resolve(elements, step)
                if el is not None:
                    break
                print(f"'{step['name']}' not found yet, re-perceiving...")
                if is_grid:
                    # The grid is virtualized — an off-screen column isn't in the
                    # DOM at all. Start from the far left, then walk right.
                    scroll_grid_h(page, step["grid"], "reset" if attempt == 0 else 600)
                page.wait_for_timeout(2000)

            healed = False
            heal_reason = ""
            if el is None and HEALER:
                # PHASE 6 TIER 1. The deterministic finder has exhausted its five
                # retries, so this run is already dead — the healer costs nothing
                # a passing step would have paid. It does NOT try harder to find
                # by id/name; it asks which element on screen NOW is the lost one.
                # `elements` is the last perceive from the retry loop above.
                if consecutive_heals >= MAX_CONSECUTIVE_HEALS:
                    print(f"   healer stood down: {consecutive_heals} heals in a row "
                          f"already — this run has probably lost its place")
                else:
                    print(f"couldn't find {step['name']} — asking the healer...")
                    el, reason = heal_step(step, elements, goal, rank,
                                           steps=recording, step_index=step_index)
                    if el is None:
                        print(f"   healer gave up: {reason}")
                    else:
                        healed = True
                        heal_reason = reason
                        # The rank was "no match" — that is what SENT us to the
                        # healer. Now that one has answered, say so, so write-back
                        # can tell a healed step from an unresolvable one.
                        rank = "healed"
                        consecutive_heals += 1
                        total_heals += 1
                        print(f'   HEALED -> {el["index"]}: <{el["tag"]}> "{el["name"]}" '
                              f'id={el.get("id") or "(none)"}')
                        print(f"   reason: {reason}")

            if not healed:
                # A step that resolved on its own means we are demonstrably still
                # on the right page, so the cascade worry is over.
                consecutive_heals = 0

            if el is None:
                print(f"couldn't find {step['name']} after retries, stopping")
                return False

            # is_grid was read off the STEP, before resolving. Trust the element
            # we actually landed on instead: a healed cell can be a grid cell
            # whose step no longer says so. It decides click-vs-focus, and a
            # grid cell reached by focus() stays in 'navigation' mode and eats
            # every keystroke without erroring (invariant #13) — a silent pass.
            is_grid = bool(el.get("grid"))

            # Only report when the tightest locator did NOT win. A step that
            # falls back still passes today, but it is drifting — this is the
            # warning you get before it breaks (and what the Phase 6 healer
            # will want to know about a step).
            # A healed step already printed its own HEALED line; calling that
            # "degraded" as well would be noise.
            if rank not in ("grid", "id", "healed"):
                print(f"   locator degraded -> matched on {rank} "
                      f"(recorded id: {step.get('id') or '(none)'})")

            if WRITEBACK:
                # plan_repair returns None for anything it should not touch: a
                # rank-1 match (nothing to fix) and a GUESS (no evidence which of
                # the candidates is right, and repairing it would delete the
                # warning that the step is ambiguous).
                changes = plan_repair(step, el, rank, heal_reason)
                if changes:
                    repairs.append((step_index, changes))
                    print(f"   repair queued for this step:")
                    print(describe_repair(changes, step))
                elif rank.startswith("GUESS"):
                    print(f"   NOT repaired: {rank} is a guess, not an "
                          f"identification — this step needs scoping or a re-record")

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
            # select used to resolve once against the warm-up perceive with no
            # retries, while click/type got five — a slow render failed here
            # where a click would have recovered. Now it matches, and goes
            # through resolve() so it gets the ranked fallback too.
            el = None
            rank = "no match"
            for attempt in range(5):
                elements = perceive(page)
                el, rank = resolve(elements, step)
                if el is not None:
                    break
                print(f"select '{step['name']}' not found yet, re-perceiving...")
                page.wait_for_timeout(2000)

            # PHASE 6. Same healer hook as the click/type branch above — a select
            # step that loses its locator is no different from a click that does,
            # and leaving it out meant one action type could not be repaired at
            # all. KEEP THE TWO IN SYNC: a change to the heal/write-back rules
            # here needs the same change up there (they are separate blocks only
            # because click/type also scrolls virtualized grids while retrying).
            healed = False
            heal_reason = ""
            if el is None and HEALER:
                if consecutive_heals >= MAX_CONSECUTIVE_HEALS:
                    print(f"   healer stood down: {consecutive_heals} heals in a row "
                          f"already — this run has probably lost its place")
                else:
                    print(f"couldn't find select {step['name']} — asking the healer...")
                    el, reason = heal_step(step, elements, goal, rank,
                                           steps=recording, step_index=step_index)
                    if el is None:
                        print(f"   healer gave up: {reason}")
                    else:
                        healed = True
                        heal_reason = reason
                        rank = "healed"
                        consecutive_heals += 1
                        total_heals += 1
                        print(f'   HEALED -> {el["index"]}: <{el["tag"]}> "{el["name"]}" '
                              f'id={el.get("id") or "(none)"}')
                        print(f"   reason: {reason}")

            if not healed:
                consecutive_heals = 0

            if el is None:
                print(f"couldn't find select {step['name']}, stopping")
                return False
            if rank not in ("grid", "id", "healed"):
                print(f"   locator degraded -> matched on {rank}")

            if WRITEBACK:
                changes = plan_repair(step, el, rank, heal_reason)
                if changes:
                    repairs.append((step_index, changes))
                    print(f"   repair queued for this step:")
                    print(describe_repair(changes, step))
                elif rank.startswith("GUESS"):
                    print(f"   NOT repaired: {rank} is a guess, not an "
                          f"identification — this step needs scoping or a re-record")

            select_option_forgiving(page, el["index"], step["value"])

        if SCREENSHOTS:                                           
                page.wait_for_timeout(500)
                img_path = f"{shot_dir}/step_{len(shots)+1}.png"
                page.screenshot(path=img_path)
                shots.append(img_path)

        page.wait_for_timeout(3000)

    if SCREENSHOTS and shots:
        build_doc(name, shots)
    # The run finished, so every step downstream of a repair worked on the page
    # that repair produced. That is the evidence; commit the buffer now.
    if WRITEBACK and repairs:
        apply_repairs(name, data, repairs)
    if total_heals:
        # A green run that needed healing is not the same as a green run that
        # didn't. Say so, or the drift is invisible until it stops healing.
        print(f"run passed, but {total_heals} step(s) needed the healer — those "
              f"locators are stale (Tier 2 will write the repairs back)")
    return True