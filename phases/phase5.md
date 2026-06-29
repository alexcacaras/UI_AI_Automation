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