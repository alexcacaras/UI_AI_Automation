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

Record by using the page directly: numbered badges on live elements, live keystroke
capture (type into real fields, sealed to record), and a threaded command center for
nav/wait/done/scroll. All actions produce the standard identity-based step format, so
overlay recordings replay via Phase 5 identically to AI/manual.

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
Seal captures document.activeElement as the type target + value + mode. The target
passes through elementInfo(), which STRIPS the `oj-searchselect-filter-` prefix off
the id (see 4d).

### Browser->Python channels (rewritten in 4d)
- CLICKS: pushed. Badges are pointerEvents:none LABELS; a capture-phase click listener
  on document reads e.target.closest('[data-ai-index]') and calls
  window.badgeClicked(elementInfo(el)) — a page.expose_function bound in main.py that
  drops the identity straight into a Python queue.Queue (overlay.click_queue).
- KEYS: still polled. install_listener sets window._lastAction; the loop reads it via
  wait_for_function(timeout=300).
- COMMAND CENTER: Python queue (command_queue).
- Loop poll order: click_queue (nowait) -> command_queue (nowait) -> _lastAction
  (blocking 300ms, which is what makes the loop breathe rather than spin).

### Command center (threaded)
command_center.py: tkinter window (dark themed, always-on-top) in a daemon thread,
started once for overlay mode. Buttons put commands in a queue: Done / Wait / Nav(+url)
/ Scroll page / Scroll table. The loop reads the queue in its poll. Threading +
queue.Queue is the safe cross-thread mailbox; the GUI thread and the Playwright loop
run independently.

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
nav, wait, scroll. Overlay-authored recording replays deterministically via Phase 5.

## 4c — Scroll (page + table)  DONE

Below-the-fold elements are unreachable, not just unseen: perceive stamps only
what's in the viewport, so an off-screen field has NO data-ai-index and cannot be
clicked by any mode. Scroll makes elements ADDRESSABLE.

Two mechanisms, both position-free (no mouse, no focus), in actions.scroll():
- target=page  -> window.scrollBy(0, amount)
- target=table -> walk UP from elementFromPoint(viewport center) to the nearest
                  real scroller (scrollHeight > clientHeight+5 AND overflowY
                  auto|scroll), then element.scrollBy(0, amount). Guarded with
                  if(el) — walking off <html> yields null.
Negative amount scrolls up. Default 600. Unknown target prints and no-ops.

ELIMINATED (empirically, in DevTools/scratch — do not revisit):
- page.mouse.wheel: scrolls whatever is under the CURSOR. Needed a click first for
  the table, never moved the window. Position-dependence is fatal for autonomous
  driving and for replay (nothing to record but a mouse position).
- Blind querySelectorAll(...).find(scroller): returns the FIRST scroller in DOM
  order, not the visible one. Set scrollTop to a number while the rows never moved.
  Walk-up-from-center picks the one you're looking at.
- CSS overflow property as a detector: the property filter returns [] on pages that
  demonstrably scroll. The proxy is leaky. (The scroll EVENT, captured with
  {capture:true}, names the true scroller — useful for diagnosis, useless for replay.)

Recording: immediate-commit, alongside nav/wait — NOT via pending_step/did_change.
Scroll ALWAYS changes the perceived element set (that is its entire purpose), so the
verdict carries zero information, and parking it in that slot would steal the verdict
belonging to the previous action.
Record shape: {action: scroll, target: page|table, amount: N}
The `target` field is what lets replay pick the right mechanism without guessing.

Command center: one entry + one button per target (raw tk.Button, not styled(),
because the command string is built at click-time from the entry via .get()).
All three modes reach the SAME dispatch branch in loop.py — only the command SOURCE
differs. Scroll was written once.

PROVEN: overlay-authored run (page scrolls to reach "Show more quick actions" and an
id-less "Positions" link, plus a table scroll on the results grid) replayed
deterministically end to end.

PARKED (edge case, never hit): walk-up-from-center assumes the scroller you want is
under the viewport middle. A page with two STACKED inner scrollers could resolve the
wrong one. First suspect if a future grid scrolls the wrong region.

PARKED (recording noise): scroll records pixel amounts verbatim, so authoring fumbles
(1800, then 600, 600, 600) replay faithfully. Works, but noisy — same "recording
cleanliness" item already parked in phase5.md.

## 4d — Overlay click channel rebuilt: identity at click-time  DONE

Three bugs, one root cause: overlay INTERCEPTED clicks and resolved them LATER by index.

### DATE PICKER — solved (was: "clicking calendar days crashes")
Not a calendar bug. Badges had pointerEvents:auto and their own click listener, so the
badge ate the click. Oracle saw a click OUTSIDE the popup -> closed the calendar ->
Python then ran do_click() on a now-hidden element -> 30s Playwright timeout
("element is not visible"). Manual/AI never hit it because they don't draw clickable
badges.
FIX: badges become pointerEvents:none labels. A capture-phase document click listener
observes the REAL click. The human's click both DOES the thing and gets recorded.
Overlay must therefore NOT re-click: do_click was firing a SECOND click on a closed
calendar. Overlay's badge branch now records only.

### NAVIGATION CLICKS — solved (regression introduced by the above, then closed)
Once the human's click acts immediately, the page can navigate BEFORE Python reads the
sticky note. wait_for_function returns a JSHandle — a pointer into the page's JS heap —
and navigation destroys that heap: "Execution context was destroyed". Every navigating
click was silently DROPPED. Polling cannot fix a read-after-the-fact.
FIX: page.expose_function("badgeClicked", ...). The browser PUSHES the identity into
Python at click-time, before navigation begins. Nothing to read later, nothing to lose.

### SEARCHSELECT id — solved
Oracle swaps in an ephemeral `oj-searchselect-filter-<stableId>|input` on focus. The
seal's activeElement grabbed it; that id doesn't exist on replay -> find_by_id fails.
FAILED FIX (recorded so it isn't retried): attribute the type to _lastClickedElement
(the last stamped element clicked). The swap happens DURING the click, so closest()
finds nothing and the memory keeps the PREVIOUS element — it recorded a type into
"Continue". The last-clicked memory fails for exactly the widget it was meant to fix.
FIX: keep activeElement (it genuinely IS the field being typed into) and normalise the
id in elementInfo() by stripping the known prefix. Hardcodes an Oracle internal string;
empirical, and it corrects a right signal rather than replacing it with a guessy one.

- SEARCHSELECT TIMING (dormant, not open): was masked as a timing race but the real
  cause was the ephemeral id (fixed in 4d) — the type step never ran. Now it runs, and
  replay's per-step 3s settle covers the dropdown filter, so type->Enter (as SEPARATE
  steps) works. STILL LATENT: the enter:true path only waits 1s; and if the 3s
  per-step settle is ever tightened, the race returns. Reuse fill_by_name's
  type->800ms->Enter pattern if that happens.

### The principle that fell out
CAPTURE identity, not position. lastClickedBadge used to hold an INDEX that Python
resolved against a possibly-stale `elements` list (perceive renumbers on every
re-render). Now the browser captures {id, name, tag, role} at the instant of the click.
No lookup, nothing to go stale. This is "record identity, never index" applied to the
CAPTURE path, not just the storage format.

PROVEN: one overlay run recorded navigating clicks, a calendar day ("14"), a
searchselect (stable id), scroll page + table — and replayed end to end.

PARKED: elementInfo's name chain is weaker than perceive's getName() — no <label for>,
no |hint, no proximity. So date/reason fields record name:"". Harmless while id is
present; would bite an id-less element.

## Parked / known limits (next work)

- find_by_name(name, tag) is ambiguous for id-less elements (the calendar has several
  cells named T/S). "14" replayed today, but a recording replayed next month points at
  a different date. Phase 0's ranked locators are the real answer.
- Single-slot _lastAction can drop an action if two happen within the 300ms poll (rare).
- Multiple recordings: still one recording.json scratch file; key by test name later.
- Remove the >>> SEAL debug print for a clean version.