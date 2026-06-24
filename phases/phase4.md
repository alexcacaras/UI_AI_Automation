# Phase 4 — Recording (auto-author)

GOAL: turn a successful AI run into a saved, replayable artifact. Pay the slow-LLM
cost ONCE to find a path; record the steps that worked; Phase 5 replays them fast
with no LLM.

## Core principle: record identity, never index
- index is position in TODAY's perceive — renumbers every run, useless to replay.
- Record the element's DURABLE fields: id (primary), name (backup), role/tag
  (disambiguate). This IS the Phase 0 Step schema (semantic_name + ranked locators).
- Replay (Phase 5) reads recorded id -> scans fresh perceive for that id -> finds
  its NEW index -> acts on that index. Index becomes a runtime lookup, never stored.

## What 4a captures (per successful step)
- the action (click / type / fill / etc.)
- the acted-on element's {id, name, role} — pulled from the elements list at act-time
- (value, for type/fill)
- only steps where result == "changed" are real path steps

## Parked
- 4b: manual recording via clickable numbered overlays (different front-end, same
  step format — build after 4a proves the format).
- Phase 11: import Testmodus Selenium recordings -> map into this Step format.