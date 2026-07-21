# PROJECT ROADMAP — AI-Driven Oracle UI Automation

The master phase list. Phases 0–2 are **complete** (see their READMEs).
Phase 3 is **in progress**. Everything below is the agreed plan; details of
later phases will sharpen as we reach them, but the shape is fixed here so it
isn't lost.

---

## The core architecture (unchanging)

A **perceive → decide → act → re-perceive** loop. Perception turns a live Oracle
page into a short numbered list of actionable elements. A decider picks one
action. The executor runs it. Repeat. In authoring mode the decider is the LLM;
the long-term production model is **record-then-replay**: use the slow LLM ONCE
to author a path, record the resolved steps, then replay them fast and
deterministically with no LLM in the hot path, and call the LLM healer only on
failure.

---

## Phases

### Phase 0 — Data model / schemas COMPLETE
Five schemas (Step, Block, InstructionSet, Run, ClientConfig). Three principles
(structure stable / data variable; locators semantic & ranked; the saved step is
the unit of truth). Credentials are env-var NAMES, not values. See PHASE_0_README.

### Phase 1 — Perception  COMPLETE
Turn a page into ~visible+actionable+named elements. 2,690 → ~42 on the worst
page. Handles `aria-labelledby` (added Phase 2). Known refinement deferred: a
proper settle gate (spinner/glass-pane/oj-complete) instead of a blind wait. See
PHASE_1_README.

### Phase 2 — Action layer  COMPLETE
Nine primitives (click, type, type+Enter, nav, press, wait, done) proven on real
Oracle by hand, incl. a full Change Assignment journey. Crash-proof. See
PHASE_2_README.

### Phase 3 — LLM in the decide slot 
Replace human `input()` with an LLM call that reads the element list + goal and
returns a command. (Detailed breakdown below.)

### Phase 4 — Step recording (auto-author)
When a run succeeds, record the resolved steps (the semantic locator bundle for
each chosen element, the action, the value) into the Step/Block schema. This is
how a slow AI authoring run becomes a reusable artifact.

### Phase 5 — Deterministic replay engine
Replay recorded steps fast, with NO LLM in the loop. Re-resolve each step by its
ranked locators. This is the production hot path — nightly regression runs here.

### Phase 6 — Healer on failure
When a replay step fails (UI changed), call the LLM to re-perceive and repair
just that step, then continue. The only place the LLM lives in production.

### Phase 7 — Cross-client / cross-instance validation
Prove the same authored flow runs on a different client/instance by swapping
ClientConfig (URL + ${variables} + creds). The "works anywhere" proof.

### Phase 8 — Document + vision intelligence
(a) Vision fallback: when perception is thin, hand the LLM a screenshot so it can
SEE what the DOM list missed. (b) Read screenshots embedded in instruction docs
to understand intent. (c) Variables: capture a value (e.g. an invoice number) and
reuse it in a later step.

### Phase 9 — Knowledge / memory (RAG)
Feed the AI the right instruction-set / master-doc chunk at runtime
(`chunk_master_doc.py` already builds these). Gives the AI the PATH so it stops
wandering. RAG, not fine-tuning, is the chosen approach (lighter, updatable).

### Phase 10 — Guardrails hardening
Enforce risk_level vs config (dry_run / allow_writes / allow_destructive) so the
agent never commits a destructive action it shouldn't.

### Phase 11 — Testmodus integration
Consume existing Testmodus instruction sets (named step lists, sets that call
other sets, variable definitions) as authored paths / Blocks.

### Phase 12 — Product UX
The person running it picks an instance + creds in a UI, picks a test, watches it
run. Deterministic config-driven login feeds the logged-in page to the engine.


### Future plan from this idea
The idea is to have system for browser and desktop automation that an LLM can drive.
Essentially creating a jarvis-esque systme on the laptop where all data belongs to you.
This allows AI to know more about you (making it work better) and help you with any task 
(this is future idea thtaa steps beyond just automating and record/replay with LLM)
---
