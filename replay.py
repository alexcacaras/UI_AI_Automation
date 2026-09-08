import json
import os
from perceive import perceive
from actions import (click, fill_by_name, scroll, select_option_forgiving,
                     resolve, scroll_grid_h, wait_for_lov_options)
import shutil
from report import build_doc
from llm import heal_step
from writeback import plan_repair, describe_repair, apply_repairs
import baseline
from dotenv import load_dotenv
load_dotenv()
SCREENSHOTS = os.getenv("SCREENSHOTS", "off").lower() == "on"
HEALER = os.getenv("HEALER", "on").lower() == "on"
# PHASE 6 TIER 2. Repair a recording whose locators have drifted, so the next
# run matches on rank 1 and pays nothing. Off switch here because a write-back
# edits the user's recording, and recordings/ is gitignored.
WRITEBACK = os.getenv("WRITEBACK", "on").lower() == "on"
# PHASE 6 OUTCOME VERIFICATION, STEP 1 — capture only, compare nothing.
# `run passed` today means every step FOUND an element, which is not the same as
# the actions having done anything. This records what each page actually looked
# like, so a later run has something to be checked against. It cannot change
# whether a run passes or fails; that comes later, and only once the comparison
# has been quiet on runs that are already trusted.
BASELINE = os.getenv("BASELINE", "on").lower() == "on"
# CONSECUTIVE heals, not total. Two heals far apart in a run are two unrelated
# Oracle changes, both legitimately repaired. Heals BACK TO BACK are different:
# each one runs on a page the previous heal navigated to, so once one is wrong
# the rest are guaranteed garbage and the run walks further off course while
# still reporting progress. After this many in a row, stop trusting the healer.
MAX_CONSECUTIVE_HEALS = int(os.getenv("HEALER_MAX_CONSECUTIVE", "3"))

# LEVEL 1 — "did the action actually do anything?". Actions whose silence is
# already explained, so the warning stays worth reading:
#   type   — perceive reports no VALUES, so a field holding "Smith" looks
#            identical to an empty one. The sensor is blind, not the app quiet.
#   scroll — changes what is on screen, not what exists.
#   wait   — is not supposed to do anything.
# Everything else that changes nothing gets a line. Measured on two real
# recordings (26 steps) this fires once, so it is a signal and not noise.
QUIET_EXPECTED = {"type", "scroll", "wait"}


def _warn_if_no_change(before, after):
    """Say so when a step left the page exactly as it found it.

    WHAT THIS CATCHES, and why it is worth a line
        The BCPC bulk job clicked a User Category combobox that never opened —
        actions.click() sent it to focus(), which does not open a dropdown. No
        error, step reported success, run went green, nothing happened. The next
        step then asked the healer to find an option that was not in the DOM.
        This check fires on the FIRST step, where the cause is.

    WHAT IT CANNOT CATCH, proven in DevTools rather than assumed
        A step whose result is legitimately nothing. `test_broken` clicks Search
        on Manage Journals; the query runs and returns "No results found", so
        the page is unchanged. "The action did nothing" and "the action did
        something that produced nothing" have the identical fingerprint, and no
        amount of tuning separates them — telling them apart needs perceive to
        read what the page SAYS (result counts, messages, disabled buttons),
        which it does not do yet.

    So this WARNS and never fails a run.
    """
    if before["action"] in QUIET_EXPECTED:
        return False
    if not baseline.compare(before["elements"], after["elements"])["same"]:
        return False
    print(f"   step {before['step_index']} ({before['action']} "
          f"{before['step_name']}) changed nothing on the page - "
          f"confirm this step was meant to")
    return True


# LEVEL 2 — "is this the page the good run was on?". Two independent good runs
# of the same recording matched at 100% on every interior step, zero elements
# added or missing, so a strict threshold is affordable. It is a threshold and
# not equality because Oracle pages legitimately differ on data.
MIN_OVERLAP = float(os.getenv("BASELINE_MIN_OVERLAP", "95"))


def _check_against_baseline(good, current):
    """Compare this run's page against the known-good capture of the SAME step.

    WHY THIS IS NOT PAGE-TO-PAGE WITHIN A RUN
        Consecutive pages in one run overlap by 0%, 12%, 38%, 87%, 100% — every
        value is legitimate, because navigating away from a page SHOULD replace
        everything on it. There is no threshold to be had there. Comparing the
        same step across two runs is the only version of the question with a
        stable answer.

    WHY STATE 0 IS EXEMPT
        The first capture of a recording is whatever the PREVIOUS test left
        behind, seen through a crude settle gate (invariant #10). Measured at 24
        elements on one run and 126 on another, both fine. It is the least
        reproducible state in any capture and must never fail a run.

    WARNS, never fails. On a Redwood-style upgrade EVERY page legitimately
    differs from its baseline, which is precisely when the healer is doing its
    most valuable work — a check that failed the run there would be worse than
    no check at all. It earns the right to fail only after being quiet on runs
    already trusted.
    """
    if current["step_index"] == 0:
        return False
    diff = baseline.compare(good["elements"], current["elements"])
    if diff["overlap"] >= MIN_OVERLAP:
        return False

    where = (f"step {current['step_index']} ({current['action']} "
             f"{current['step_name']})")
    print(f"   {where} does not match the known-good run: "
          f"{diff['overlap']:.0f}% of the page is the same "
          f"(+{len(diff['added'])} new, -{len(diff['removed'])} missing)")
    # Only claim "same page, different data" when the evidence supports it:
    # every difference is an element that HAS an id present on both sides, and
    # the disagreement is over its name. That is a row showing different data.
    #
    # `anonymous` must be zero. Two different Time Management pages once scored
    # 100% on id overlap because every element that DISTINGUISHED them was
    # id-less while the shared chrome carried all the ids — and the reassuring
    # line printed on a page that was genuinely wrong. A message that talks you
    # out of investigating a true positive is worse than no message.
    if (diff["anonymous"] == 0 and diff["renamed"]
            and diff["id_overlap"] is not None
            and diff["id_overlap"] >= MIN_OVERLAP):
        print(f"      but every difference is an element with a known id whose "
              f"text changed ({len(diff['renamed'])} of them) - same page, "
              f"different data")
    elif diff["anonymous"]:
        print(f"      {diff['anonymous']} of the differences are elements with "
              f"no id, so nothing identifies them - this could be a different "
              f"page, not just different data")
    return True

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
    # One captured page state per step, plus one after the last step. Dropped
    # without being written if the run dies — a half-run is not a known-good run.
    states = []
    quiet_steps = []             # steps that left the page exactly as they found it
    mismatches = []              # steps that did not match the known-good run

    # LEVEL 2. Load the blessed baseline, but only USE it if it still describes
    # this recording. A capture is tied to the step list it was taken from, so a
    # recording that has gained or lost a step since makes every index after
    # that point compare the wrong pages against each other — a check that is
    # confidently wrong is worse than one that admits it cannot run.
    good_states = None
    if BASELINE:
        good = baseline.load(name)
        if good is None:
            print("   no known-good baseline yet - this run will record one")
        elif good.get("format") != baseline.FORMAT:
            print(f"   baseline is format {good.get('format')}, expected "
                  f"{baseline.FORMAT} - not comparing; delete it to recapture")
        elif len(good["states"]) != len(recording) + 1:
            print(f"   baseline has {len(good['states'])} states but this "
                  f"recording has {len(recording)} steps - the recording "
                  f"changed; not comparing, delete the baseline to recapture")
        else:
            good_states = good["states"]
            print(f"   comparing against known-good run of "
                  f"{good.get('captured', '?')}")

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

        # Capture BEFORE acting. This perceive is the page the previous step
        # produced, so one capture per step answers both questions we care
        # about: state[N] matching state[N-1] means step N-1 silently did
        # nothing, and state[N] not matching the known-good run means the flow
        # is somewhere else. Nothing compares them yet — this only records.
        if BASELINE:
            current = baseline.observe(elements, step, step_index)
            # The effect of the PREVIOUS step is the difference between the page
            # it started on and the page this one starts on. Replay perceives
            # before acting and never after, so the warning necessarily arrives
            # one step late — it is labelled with the step it is about, which
            # costs nothing, where a second perceive per step would cost a
            # settle wait on every step of every run.
            if states and _warn_if_no_change(states[-1], current):
                quiet_steps.append(states[-1]["step_index"])
            if good_states and _check_against_baseline(good_states[step_index],
                                                       current):
                mismatches.append(step_index)
            states.append(current)

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

    if BASELINE:
        # THE LAST STEP IS THE ONE NOBODY WATCHES. Replay perceives before
        # acting and never after, so every step's result is seen at the top of
        # the NEXT step — and the final action has no next step. On a recording
        # that ends in Save, that is the single most important action in the run
        # going unobserved. One extra perceive closes it.
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=13000)
        except:
            pass
        # RETRY, for the same reason the top-of-loop perceive does. The first
        # version of this had the settle wait but no retry, and captured a page
        # of ZERO elements on test_broken — the one capture added specifically
        # because the last action goes unwatched was the least reliable one in
        # the file. A page still rendering is not a result.
        final = []
        for attempt in range(5):
            page.wait_for_timeout(2000)
            try:
                final = perceive(page)
            except Exception as e:
                print(f"   final perceive failed, retrying: {e}")
                continue
            if len(final) > 6:
                break
            print(f"   final page looks empty ({len(final)} elements), waiting...")
        if final:
            last = baseline.observe(final)
            # THE LAST STEP IS THE ONE WORTH CHECKING MOST. On a recording that
            # ends in Save, this is the only place the save can be seen to have
            # done anything at all.
            if states and _warn_if_no_change(states[-1], last):
                quiet_steps.append(states[-1]["step_index"])
            if good_states:
                # The final state is indexed by step count, not step_index -
                # it belongs to no step. Give it that index so the message
                # points at the last step, which is what produced it.
                last_check = dict(last, step_index=len(recording),
                                  action="(after last step)")
                if _check_against_baseline(good_states[-1], last_check):
                    mismatches.append(len(recording))
            states.append(last)
        else:
            print("   final page never settled — baseline not captured")
            states = []

    if SCREENSHOTS and shots:
        build_doc(name, shots)
    # The run finished, so every step downstream of a repair worked on the page
    # that repair produced. That is the evidence; commit the buffer now.
    if WRITEBACK and repairs:
        apply_repairs(name, data, repairs)
    if BASELINE and states:
        # THE NO-LAUNDERING RULE. A passing run is allowed to define "good" only
        # while there is nothing to check it against. Once a baseline exists, an
        # unverified pass must NEVER quietly overwrite it — a run that resolved
        # every locator and did nothing would rewrite the definition of a good
        # run in its own image, and the drift would be permanent and invisible.
        # Refreshing on a VERIFIED pass is what lets the baseline drift forward
        # with the app the way write-back drifts the recording. That comes with
        # the comparison; until then, first capture wins.
        #
        # Every run still leaves its capture in <name>.last-run.json, blessed or
        # not. A run that records nothing can never be compared to anything, and
        # two captures of the same recording are the only way to learn which
        # fields are genuinely stable across runs.
        baseline.save_last_run(name, states, goal)
        if baseline.exists(name):
            print(f"   baseline already recorded for '{name}' — kept; this run "
                  f"saved to {baseline.last_run_path(name)}")
        else:
            path = baseline.save(name, states, goal)
            print(f"   baseline captured: {len(states)} page states -> {path}")

    if mismatches:
        # Also not a failure, and for a sharper reason than level 1: on a
        # Redwood-style upgrade EVERY page differs from its baseline, which is
        # exactly the run the healer just rescued. Failing there would break the
        # tool on the day it works best. This earns the right to fail only after
        # it has been quiet across runs that are already trusted.
        print(f"run passed, but {len(mismatches)} step(s) did not match the "
              f"known-good run: {', '.join(str(i) for i in mismatches)} - the "
              f"locators resolved, but those pages are not the ones recorded")

    if quiet_steps:
        # Deliberately NOT a failure. Some steps legitimately change nothing —
        # a search returning no rows, proven in DevTools on test_broken step 7.
        # This is here so a run that silently did nothing stops looking exactly
        # like a run that worked.
        print(f"run passed, but {len(quiet_steps)} step(s) changed nothing: "
              f"{', '.join(str(i) for i in quiet_steps)} - if an action there "
              f"was supposed to have an effect, this run is green for nothing")

    if total_heals:
        # A green run that needed healing is not the same as a green run that
        # didn't. Say so, or the drift is invisible until it stops healing.
        print(f"run passed, but {total_heals} step(s) needed the healer — those "
              f"locators are stale (Tier 2 will write the repairs back)")
    return True