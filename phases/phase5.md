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
id-less <a></a> buttons resolved by name+tag on replay.

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
- run_loop(page, mode, name): saves to recordings/<name></name>.json
  (os.makedirs("recordings", exist_ok=True) creates the folder once).
- replay(page, name): loads recordings/<name></name>.json. If missing, lists available
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
- Runs are ephemeral; saving as runs/<name></name>.json is the next increment.
- Login is still manual (pre-run). Automated session_setup reading ${creds} from .env
  is Phase 0's design, deferred.
- Results are terminal print only. A pytest-style dashboard (requested by a stakeholder)
  is a reporting layer for later.
  ## 5d — Perceive/naming fixes (partial)

Classic Oracle pages (setup + maintenance) had buttons/fields no mode could click —
they got no badge because getName() returned "".

Causes + fixes:

- Icon buttons (+ Create, Export) are <a></a> wrapping only an ; the name lives in
  the img's `alt`. Added img-alt fallback to perceive.getName AND overlay.elementInfo.
  (Two naming functions — a fix must go in both or record/replay disagree.)
- Some inputs (setup search box) are genuinely nameless but have ids. Stamping loop now
  rescues nameless input/textbox/combobox as "text field" instead of dropping them.

New bug: setup search magnifier has id:"" and shares name "Search" with the top-nav
one, so find_by_name clicks the wrong one. Workaround: press Enter to search (confirmed).
Real fix: ranked locators — promoted from Phase 0 parked to active.

## 5e — Native <select></select> support

Native <select></select> dropdowns (Country, State, Purpose — common on classic pages, rare on
Redwood) couldn't replay: recording captured a click, but a synthetic click doesn't open
the OS-native dropdown, so the option was never picked. Fix: drive selects with
select_option, not click.

- New "select" action: {id, name, tag, value}. value = the option's VISIBLE TEXT
  ("Sold to") — the internal value is just a reorderable index.
- select_option_forgiving: exact match, then case-insensitive fallback (fixes "Sold To"
  vs "Sold to"; also turns a 30s timeout into an instant error).
- Manual: `select N value` (maxsplit=2 keeps spaces).
- Overlay: a 'change' listener auto-records the pick; click handler SKIPS <select></select> so
  it's one clean step, not doubled click+select.
- Recorded on "didn't error" (like type/fill), not gated on "changed".

Not searchselect — that's oj-select-single, a different widget; its patterns don't apply.
Grid-row note: select ids contain the row index. Multi-row works if the "Add Row" clicks
are recorded (replay rebuilds rows in order). Pre-existing rows would break — deferred.
PROVEN: manual + overlay, single/two-row, case-tolerant replay.

## 5f — Screenshot report (Word doc on replay)

Replay can output a .docx: heading = test name, then one screenshot per step in order.
Simple by design — no step labels.

- .env SCREENSHOTS=on/off (default off, so bug-hunting stays fast).
- Shot AFTER each step, viewport only, 500ms settle.
- Output: recordings/docs/<testname></testname>/<testname></testname>.docx.
- Folder wiped each run, so re-replay overwrites cleanly.
- build_doc in report.py. Dep: python-docx (add to setup.bat verify).
- Only builds on success; a failed replay makes no doc.



## 5g — Bug-hunt batch (perceive gaps + robustness)

Tested across ERP/EPM/SCM pages, fixed several:

- Icon-button naming already done (5d). Confirmed holding on more pages.
- Search suggestions: global-search dropdown items are 
- 
,
not in ACTIONABLE, so never badged. Added li.FndSearchSuggestLIItem to the selector.
Records/replays IF the dropdown is open when perceive fires. NOTE: replay is inherently
fragile — suggestions share one id and are LIVE data (a recorded "Purchase Order YYC003493"
only replays while that result still appears). Prefer navigating via menu for regression.- Navigator scroll: the Nav side-panel scroller (id …_UISnvr…nv_pgl3) isn't under viewport
  center, so scroll-table's walk-from-center missed it. Added a "navigator" scroll target
  that finds it by id pattern directly. Command: scroll navigator N. Command-center button added.
- Crash wrap: draw_overlays/install_listener run page.evaluate; if the page is mid-navigation
  (e.g. arrow-Enter on a search suggestion) the context is destroyed and the WHOLE session
  crashed. Wrapped both in try/except → continue (re-settle at loop top). Navigation-during-draw
  is now a skipped iteration, not a fatal crash. Protects EVERY navigation, not just search.

Dates — recording convention, NOT code:

- Classic calendar day cells are id-less  (class x12k). Adding  to ACTIONABLE would
  badge EVERY table cell on every page (flood), and a "click day 14" recording is fragile
  anyway (wrong date next month, can't parameterize). So: TYPE the date into the field
  (dd/mm/yy is typeable), don't click the calendar. Deterministic + parameterizable (${date},
  Phase 8 later). Same spirit as Enter-to-search.

Known limitations documented (defer): Time Card grid, new-tab popups, global-search replay.
