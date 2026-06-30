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

### Option 2 (live keystroke capture) — FOUNDATION PROVEN
Live capture works: keydown listener accumulates window.capturedText, Python reads it back.
Tested on the search field (a swapping searchselect-type input) — captured 'hello' correctly.
KEY: this captures the user's KEYSTROKES, not Oracle's DOM value — so it beats read-back,
which returned empty because Oracle swaps the input on focus. Capture is DOM-swap-proof.
Seal for the real build = CAPSLOCK (inert: no char, no submit, no close). Test used
terminal-Enter to isolate capture from seal-key wiring.

### Next session — build Option 2 properly (the plan)
1. Refactor: extract loop actions into functions in actions.py (do_click, do_type_python,
   do_type_live, do_press, ...). Each returns the same pending_step shape. Loop picks the
   variant by mode (overlay -> do_type_live; manual/ai -> do_type_python). typeo is an
   AUTHORING action only — it records as a normal `type` step (replay never sees typeo).
2. Real overlay-type: badge-click targets field -> capture keystrokes -> CAPSLOCK seals ->
   record as type N <captured>. The landing (Enter submit, or searchselect pick) is a
   SEPARATE recorded step.
3. Searchselect: type (captured) + press ArrowDown + press Enter (keyboard-pick the top
   match) — avoids the fragile dynamic-option click on replay.
4. Live press capture (the seal mechanic generalizes — capture special keys as press steps).
5. nav/wait/done via terminal (hybrid) or later a control panel.