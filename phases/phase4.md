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
## 4b — Manual recording (overlay-driven, no AI)  IN PROGRESS

GOAL: record by interacting with the page visually instead of reading the terminal
element-list and typing `click 7`. Removes the mental-mapping tax (cross-referencing
terminal indices to on-screen elements) and the mistype risk. Essentially a
domain-specific Playwright codegen, tuned to our Step format + Oracle widgets.

### Why a different INPUT model, same recorder
Recording logic (pending_step, commit gate, durable locators) is UNCHANGED. Only the
SOURCE of the command changes: AI (run_loop) vs human-via-overlay (manual_loop). Both
feed the same recording.json.

### Interaction model (the target design)
- Numbered badges drawn on every actionable element (the data-ai-index stamps).
- Click a badge -> dropdown: click / type / fill.
  - click: executes, records, auto-re-perceives (badges reset). No manual "continue".
  - type / fill: prompts for a value -> confirm (checkmark/Enter) -> executes, records,
    re-perceives.
- press: captured LIVE via a key-listener (you actually press the key on the page).
  press has no badge and no event-collapsing problem, so live capture is clean here.
- done: a control to end + name + SAVE the recording. Browser stays open to start a
  fresh recording without restarting.

### Key design decision: declare intent, don't infer it
We capture INTENT (you pick "type", give the value) rather than watching raw DOM events
(click + keystrokes) and trying to collapse them back into one `type` step. Inferring
intent from raw events is the hard problem codegen tools fight; declaring it via the
dropdown sidesteps it. (Exception: press, where one keystroke = one step, so live
capture is fine.)

### The two load-bearing hard parts (build the spine first)
1. Browser->Python bridge: badge clicks / dropdown picks / values happen in browser JS;
   recorder is Python. Playwright `expose_function` is the bridge. This is the spine —
   everything routes through it.
2. Re-injection: injected overlays + key-listener + control panel are destroyed on every
   navigation/re-perceive. Must re-inject EVERY perceive, or they vanish mid-recording.

### Build order (smallest-first; prove the spine before features)
1. Mode menu: main.py -> (a)i drive / (m)anual record / (p)layback.
2. overlay.py -> draw_overlays(page): always-on numbered badges at each stamped
   element's corner, pointer-events:none (so later clicks pass through to the real
   element). VISUAL ONLY first — still type commands in terminal, but read indices off
   the page. Tests: do badges land on the right elements? can we inject + re-inject?
3. Click-capture via expose_function (badge click -> index to Python).
4. Dropdown for action + value input.
5. press via live key-listener; done/name/save panel; fresh-recording-without-restart.

### Parked (later)
- Variables / carry-forward (capture an invoice number, reuse downstream) = Phase 8c.
- Hover-to-reveal badges (start always-on; add hover only if clutter is a problem).
- In-page panel vs second tab for controls — settle when we reach step 4.
- Testmodus Selenium recordings -> map to our Step format = Phase 11 (separate front-end,
  same recording.json target).

### Badge visibility FIXED — it was z-index, not timing
Diagnosed via DevTools (not assumed): badges WERE drawing (logged 63 stamped) but
rendered UNDER Oracle's Navigator flyout. zIndex 999999 lost to the flyout's own
stacking layer. Fix: zIndex = 2147483647 (max 32-bit int) — badges now render above
flyout, dialogs, calendar picker, everything. Confirmed on home, flyout, full wizard.
The earlier "settle-gate" theory was WRONG for this bug (page was settling fine; badges
were just hidden). Settle-gate stays parked — not needed for overlay visibility.
KNOWN (cosmetic, not fixing now): old badges linger ~1s after an action before the loop
re-perceives and redraws. Harmless (you read badges after settle). The eventual
settle-gate would smooth this; not worth blind waits (they make lingering worse).

### NEXT SESSION — top priority: the settle-gate (finally)
This is now blocking THREE things: clean perceive, replay timing, accurate overlays.
Build the real settle gate from the Phase 1 spec: wait until
  - networkidle, AND
  - no VISIBLE progress dialog (oj-sp-message-progress-dialog / oj-c-dialog progress)
  - no VISIBLE element with aria-busy="true"
  - main components carry oj-complete
...before perceive returns (and before draw_overlays). Replaces all the blind
wait_for_timeout crutches. Then resume 4b step 3 (click-capture via expose_function).