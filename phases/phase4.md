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
### 4b progress — click-capture WORKING (step 3 done)
- Step 1 (mode menu): DONE — (a)i / (m)anual / (o)verlay / (p)layback. run_loop takes mode.
- Step 2 (draw_overlays): DONE — numbered badges, max z-index (2147483647) so they sit
  above flyout/dialog layers.
- Step 3 (click-capture): DONE. Pattern (Option 2, sync-Playwright-friendly):
    * badge click sets window.lastClickedBadge = idx  (pure JS, no expose_function callback)
    * loop (overlay mode) resets it null, then page.wait_for_function("...!== null", timeout=0)
      — this BLOCKS but pumps browser events, so the click registers (plain input() froze
      the single thread and the click never arrived — that was the core bug)
    * read index, REMOVE all badges, then run as "click N"
  KEY FIX: badges must be removed BEFORE Playwright executes the click — the badge (max
  z-index, pointer-events:auto so it can catch your click) otherwise INTERCEPTS Playwright's
  click on the real element ("<div ai-overlay-badge> intercepts pointer events"). So:
  draw -> catch click -> remove badges -> execute -> re-perceive -> redraw.
  Recording is UNCHANGED: badge click just produces the same "click N" string the terminal
  would; existing dispatch + commit gate record it. Proven: clicked Me/My Team/Navigator
  badges, all executed and recorded.

### Option 2 live-type — WORKING (overlay click + type both work)
- Actions extracted to functions in actions.py: do_click, do_type_python (manual/AI
  Python-types), do_type_live (overlay captures keystrokes). All return the same
  pending_step shape -> recording/replay unchanged, don't care which authored it.
- Overlay branch routes by tag: input/textarea -> do_type_live; else -> click.
  do_type_live does its action inline (capture), sets cmd="overlay_done", dispatch
  skips it with `elif cmd == "overlay_done": pass`. (Overlay-type IS the action, like a
  click — Python records, doesn't re-type.)
- do_type_live: keydown listener accumulates window.capturedText (handles Backspace),
  CapsLock sets window._sealed, wait_for_function blocks on seal, read text, record as
  {action:type, value:<captured>, enter:False}. Landing (Enter/ArrowDown) is separate.
- GOTCHA fixed: badge index comes back as a STRING from page.evaluate; must int() it
  before search_element (which matches int index) or el is None.
- Proven: clicked Search badge (opens box), clicked input badge -> typed live ->
  CapsLock sealed -> recorded as type step; clicks before/after also recorded.

### Still to do (the control layer — nav/wait/done/press)
- DONE in overlay: no path yet (loop waits for badge click). Next: make the overlay
  wait watch for EITHER a badge click OR a key (Escape=done), via
  "window.lastClickedBadge !== null || window.overlayDone === true". This "wait for
  badge OR key" pattern is the foundation for nav/wait/done/press too.
- press live-capture, nav, wait: same control-layer pattern.
- Searchselect: type (live) + ArrowDown + Enter to pick top match (test on replay).
- Then: full overlay record -> save -> replay cycle test.