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

## Parked
- 4b: manual recording via clickable numbered overlays (different front-end, same
  step format — a human click is intentional by definition, so it sidesteps the
  commit-gate problem entirely). Build after 4a proves the format.
- Filename: recording.json overwrites each run (fine for testing). Real use keys
  the filename to the test name when InstructionSets exist (Phase 0 / 9).
- Refactor: command-dispatch elifs -> per-action functions (maybe per-action files
  click/type/press/fill). Housekeeping at next checkpoint, not mid-feature.
- Phase 11: import Testmodus Selenium recordings -> map into this Step format.