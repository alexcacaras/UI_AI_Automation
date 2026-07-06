# Phase 4 — Recording (auto-author)

GOAL: turn a successful AI run into a saved, replayable artifact. Pay the slow-LLM
cost ONCE to find a path; record the steps that worked; Phase 5 replays them fast
with no LLM.

## Core principle: record identity, never index
- index is position in TODAY's perceive — renumbers every run, useless to replay.
- Record the element's DURABLE fields: id (primary), name (backup), role + tag
  (disambiguate — e.g. div "My Client Groups" vs the "Expand..." caret link).
  This IS the Phase 0 Step schema (semantic_name + ranked locators).
- Replay (Phase 5) reads recorded id -> scans fresh perceive for that id -> finds
  its NEW index -> acts on that index. Index becomes a runtime lookup, never stored.

## 4a — what's captured per action  DONE
search_element(elements, target) in actions.py pulls the acted-on element's dict
by index at act-time. Entry shapes:
- click: {action, id, name, role, tag}                  — locators only
- type:  {action, id, name, role, tag, value, enter}    — locators + typed text + enter flag
- fill:  {action, name, value}                          — name-based (no index/locators)
- press: {action, value}                                — key only, no element

## Commit gate (when a recorded step is kept)
- pending_step built at act-time, committed/dropped one loop later when the verdict lands.
- click: records ONLY if verdict == "changed" (a click that moves the page is a real step).
- press / type / fill: record if they didn't error (looser — these often DON'T change
  the id-set, so "changed" would wrongly drop a successful type). Over-recording is the
  SAFE failure: an extra harmless step replays fine; a missing step breaks replay.
- wait: NOT recorded (replay has its own settle gate; wait is a timing crutch, not a path step).

## Known open issue (type gate)
type may not change the id-set even when it worked, so the "didn't error" gate
over-records. Refine later (e.g. verify typed text actually landed) — only against
observed failures, not hypotheticals.
## 4b — Overlay recorder + live capture + command center  COMPLETE

Record by using the page directly: numbered badges on live elements (click to record
clicks), live keystroke capture (type into real fields, sealed to record), and a
threaded command center for nav/wait/done. All actions produce the standard identity-
based step format, so overlay recordings replay via Phase 5 identically to AI/manual.

### Modes
main.py: (a)i / (m)anual / (o)verlay / (p)layback. run_loop takes a `mode` param.
All modes share one perceive + dispatch + recording core; only the command SOURCE differs.

### Overlay input model (the design that works)
One always-on JS keydown listener (install_listener), installed ONCE per page
(guarded by `if (!window._overlayHandler)` so re-perceives don't wipe capturedText or
stack duplicate listeners — this guard was the fix for types not recording):
- character keys -> accumulate window.capturedText  (live capture, DOM-swap-proof)
- Backspace -> trims capturedText (edits, never recorded)
- CapsLock -> seal as type mode=replace ; Insert -> seal mode=append
    (only fires if capturedText != '' — empty-seal guard, avoids clobbering _lastAction)
- character while Ctrl/Cmd/Alt held -> IGNORED (Ctrl+A/Ctrl+C were leaking letters like
    "ca" into values — guarded by checking !e.ctrlKey etc.)
- bare Shift/Control/Alt/Meta -> ignored
- everything else (Enter/Tab/arrows/PageDown/F-keys...) -> press step
Seal captures document.activeElement as the type target + value + mode.

### Browser->Python channels
- badges set window.lastClickedBadge (sticky-note); listener sets window._lastAction.
- Loop polls: wait_for_function(badge OR _lastAction, timeout=500); on timeout, check
  the command-center queue (get_nowait). So it waits for badge-click OR keyboard OR
  command-center button, all at once. (Solves: input()/blocking wait can't also hear
  other sources.)

### Command center (threaded)
command_center.py: tkinter window (dark themed, always-on-top) in a daemon thread,
started once for overlay mode. Buttons put commands in a queue: Done / Wait / Nav(+url).
The loop reads the queue in its poll. Threading + queue.Queue is the safe cross-thread
mailbox; the GUI thread and the Playwright loop run independently.

### Recording: immediate-commit for overlay
Overlay actions are DELIBERATE (human clicked/typed on purpose), so they commit
immediately (recording.append right when done) — NOT through the did_change gate.
The gate's "only record clicks if changed" was DROPPING deliberate overlay clicks
(4-of-5 lost); immediate-commit fixed it. (AI/manual still use the deferred gate.)

### nav / wait now recorded (all modes)
nav dispatch: records {action:nav, value:url} + auto-prepends https:// if missing.
wait dispatch: records {action:wait}. done is NOT recorded (it just ends the run).
replay.py handles nav (page.goto) and wait (wait_for_timeout).

### Proven
Full action set records AND replays: click, type (live+seal, replace/append), press,
nav, wait. Overlay-authored recording replays deterministically via Phase 5.

## 4b — Parked / known limits (next work)
- SEARCHSELECT TIMING: type->Enter races Oracle's dropdown filter (Enter fires before
  the filtered option appears). A manual pause helps but is fragile. Real fix: for
  combobox fields (role=combobox), replay should type full value -> wait ~800ms ->
  Enter (reuse fill_by_name's proven pattern). Also: searchselect swaps to an ephemeral
  `oj-searchselect-filter-...` input on focus, so the seal's activeElement grabs that
  transient id — should attribute the type to the last-CLICKED stable field id instead.
- DATE PICKER: clicking calendar days crashes; workaround = type the date as text.
- SCROLLING / below-the-fold: perceive only sees the viewport; PageDown records but
  doesn't reliably scroll Oracle. Need scroll-and-re-perceive (mouse.wheel or container
  scroll) to reach/record lower elements. Likely the highest-value next fix for long forms.
- Single-slot _lastAction can drop an action if two happen within the 500ms poll (rare).
- Multiple recordings: still one recording.json scratch file; key by test name later.
- Remove the >>> SEAL debug print for a clean version.