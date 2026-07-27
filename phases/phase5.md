# Phase 5 — Deterministic Replay (no LLM in the loop)

GOAL: replay a recording fast and deterministically. Read recording.json, re-find
each element by its durable locator in a FRESH perceive, do the action. No goal, no
ask_llm, no history. This is the production hot path.

## 5a — replay engine  DONE
Proven end-to-end on a real 3-page wizard (Request a New Position): navigate in,
open date picker + click a day, set searchselect reason, Continue, fill Business
Unit, type Name + Job. Zero LLM.

### The resolution chain (the core mechanic)
recorded id -> fresh perceive (today's indices) -> find element -> act on TODAY's index.
Index is never stored; it's re-derived every run. This is what survives Oracle's
constant renumbering.

### Finders (actions.py)
- find_by_id(elements, id): primary locator, matches el["id"].
- find_by_name(elements, name, tag): FALLBACK for id-less elements. Matches name AND
  tag (tag disambiguates name collisions, e.g. div item vs "Expand" caret link).
  Needed because Oracle buttons (Continue/Submit/Cancel) and calendar days have id="".
- Replay picks: if step["id"] is non-empty use find_by_id, else find_by_name.
  This is the Phase 0 ranked-locator idea (id first, name fallback) in its first form.

### Retry-on-miss (the slow-page fix)
A recorded element may not be loaded yet when replay reaches its step (wizard page
transitions are slow). So the find is wrapped in a retry loop: perceive -> find ->
if None, wait + re-perceive, up to 5 times. Only stop if still missing after retries.
This replaces the manual "wait to re-perceive" that was needed during recording.
NOTE: currently wraps click/type only. fill does NOT yet retry (known gap).

### Action replay shapes
- click: find element -> click(page, el["index"])
- type:  find element -> focus by index -> type value -> if enter: wait 1s, press Enter
         (the 1s settle mirrors fill_by_name's searchselect race fix)
- fill:  fill_by_name(page, name, value) — name-based, no find_by_id, has its own settle
- press: page.keyboard.press(value) — no element
- scroll: scroll(page, target, amount) — no element, no find, no retry. Re-runs the
          same mechanism with recorded args. Pixel amounts are absolute, so a page
          that renders differently on replay could land elsewhere; the retry-on-miss
          around the NEXT click absorbs this in practice (proven).

## KEY BUG FOUND & FIXED: did_change went blind to id-less elements
did_change compared SETS of ids. Oracle's date-picker (and other widgets) flood the
page with id="" elements (30+ calendar day buttons, all id=""). A set collapses all
"" to ONE entry, so adding 30 id-less buttons changed the id-set by ZERO -> verdict
"no change" -> the date-field click was dropped from the recording (click only records
on "changed"). This is why the date never recorded and replay stalled on the required
empty date field.
FIX: compare sets of (id, name) TUPLES, not bare ids. Now id-less elements are distinct
by name ('', 'Previous') vs ('', '14'), the set grows, "changed" fires correctly.
Side effect: did_change is now slightly more sensitive (tiny text changes register) —
acceptable; over-detection is the safe failure for recording.

## DATE FIELD (Oracle oj-input-date) — solved
Not typeable directly. Sequence that works: click the date field (opens calendar
picker) -> click the day number (e.g. "28") -> field populates, "Enter a value" error
clears. Both clicks now record correctly (after did_change fix). Calendar days are
id-less <a> buttons resolved by name+tag on replay.

## Parked / next
- fill retry-on-miss (fill should re-perceive like click/type before giving up).
- Recording cleanliness: replay faithfully reproduces authoring fumbles (Backspace,
  retries). Needs pruning, or manual recording (4b), or end-of-run confirm-clean-path.
- Multiple recordings: recording.json is one scratch file; key by test name later.
- Phase 6 (healer): when find_by_id AND find_by_name both fail (element truly gone after
  a UI change), call the LLM to re-perceive and repair that step. find returning None
  is already the exact hook.



# Phase 5b — Named recordings (multi-recording storage)

GOAL: stop the single-file clobber. Each recording gets a name; replay picks by name.

## What changed
- main.py: prompts for a recording name after the mode choice; passes `name`
  into run_loop (save) and replay (load).
- run_loop(page, mode, name): saves to recordings/<name>.json
  (os.makedirs("recordings", exist_ok=True) creates the folder once).
- replay(page, name): loads recordings/<name>.json. If missing, lists available
  recordings and re-prompts (blank = exit) rather than crashing on open().

## Format decision
Bare array, keyed by FILENAME — no envelope. Smallest change that doesn't corner
us: when Phase 0's InstructionSet shape is needed (name/goal/ranked-locators for
the healer), wrap the array in an object rather than converting one. Deferred until
a field beyond `steps` is actually required.

## Proven
Recorded test1 and test2 separately (both files persist), replayed each by name,
and a bad name lists options + re-prompts.

## Parked
- Overwrite on re-record is silent — recording the same name twice clobbers. Same
  list+confirm pattern could guard it later.
- Runs (ordered lists of recordings to replay in sequence — Phase 0 "Run" schema)
  not built. This is single-recording replay only.
- Recording cleanliness (fumbles replay verbatim) still open — carried from Phase 5.

## 5c — Runs (replay multiple recordings in sequence)  DONE

build_order() (runs.py): lists recordings/ numbered, user types order "2,3,1" at
runtime -> ["test2","test3","test1"]. No file editing; ephemeral (not saved).
run_suite(page, order): replays each in sequence with TWO layers of isolation:
  - replay() now returns True (all steps done) / False (a step's locator not found).
  - run_suite wraps each replay in try/except for UNEXPECTED crashes.
  Either way: mark FAIL, continue to next test, print PASS/FAIL summary at end.
main.py: new (r)un mode splits off before the name prompt (a Run has an order, not
a single name).

Purpose: dependency isolation. A recording that needs a prior recording's result
fails contained — skip it, keep running the rest.

Convention (not code): recording 2 should start with a click-home to reset to a
known page, since it inherits whatever page recording 1 left behind.

PARKED:
- build_order has no input guard: "9" (out of range) -> IndexError, "abc" -> ValueError.
- Runs are ephemeral; saving as runs/<name>.json is the next increment.
- Login is still manual (pre-run). Automated session_setup reading ${creds} from .env
  is Phase 0's design, deferred.
- Results are terminal print only. A pytest-style dashboard (requested by a stakeholder)
  is a reporting layer for later.