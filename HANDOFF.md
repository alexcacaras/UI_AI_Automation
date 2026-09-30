# HANDOFF — where this project stands, 2026-09-30

Written on the last day of the original author's time on it, for whoever picks
it up next (possibly the same person, later, on their own time).

**Read `CLAUDE.md` first** for what the project is and the hard invariants.
Then the phase doc for whatever area you are touching — those docs are the real
asset here. They record not just what was built but what was TRIED AND WRONG,
which is the expensive knowledge.

---

## The one-paragraph version

Record a UI path once, replay it deterministically forever, and when Oracle
changes the page underneath it, an LLM repairs the broken step instead of a
human re-recording the test. Agency at authoring time and repair time;
determinism in the hot path. That boundary is the feature — do not let an LLM
into the replay loop.

---

## What works today

| area | state |
|---|---|
| Perception (`perceive.py`) | Redwood, classic ADF, JET data grids, element **state** (value/checked), grid column dates |
| Recording | three modes — overlay (badges + live keystrokes), manual, AI-assisted |
| Replay (`replay.py`) | deterministic, ranked locators, retry, screenshot `.docx` reports |
| Healer Tier 1 | LLM re-finds a lost element. Proven through a whole Oracle shell migration |
| Healer Tier 2 | write-back — a repaired recording matches at rank 1 next run and pays nothing |
| Verification L0–L3 | all four levels built. See below |
| Variables | `${name}` placeholders, resolved per run |
| Web frontend | Flask + React, staged launch → manual login → record |

## The verification ladder — all four levels exist

    0. every step found an element      what "run passed" used to mean
    1. each action DID something        warns
    2. ended on the right page          warns
    3. the value asked for landed       warns

**Everything warns; nothing fails a run.** That is deliberate and should stay
that way until a guard has been near-silent across many trusted runs. A check
that fails good runs gets switched off rather than fixed.

---

## What is NOT done — in the order I would do it

### 1. Test the variables feature end to end  *(30 minutes)*
Built and committed, offline-tested, **the UI path is unproven.** Substitution,
name parsing, unknown-name handling and the non-interactive path all pass
offline; the tkinter button and the record-then-replay round trip were never
run on a live page.

    py main.py -> o -> record -> type a value -> CapsLock to seal
                 -> name it in the command centre -> { } MAKE VARIABLE
    py main.py -> p -> same recording -> it should ask for the value

Order matters: **seal first, then the button.** The button rewrites the value of
a step that already exists.

### 2. Step 5 — read-only page text  *(half a day)*
`perceive_readable()` is built and measured but wired to nothing. See phase6.md
"STEP 5 — MEASURED, NOT INTEGRATED". Two known defects to fix before
integrating:
  - an infolet CONTAINER that happens to be `aria-live` is not a status
  - the same message arrives twice, because a live region wraps the element it
    announces and the dedupe key includes the id

Then fold it into the fingerprint (FORMAT 4) so level 1 can tell "the click did
nothing" from "the click worked and found nothing". That distinction is the
single biggest remaining blind spot.

### 3. Tier 3 — the vision healer  *(1–2 days)*
Escalate to a screenshot when the text healer returns `-1`.

The prerequisite is **settled**: `qwen2.5vl:7b` reads dense Oracle screenshots
correctly (proven — `vision_probe.py`). `gemma4:e4b` advertises vision and
silently drops images; do not waste a day on that, phase6.md explains why.

Give it its own `HEALER_VISION_MODEL` setting — it is ~170s per call, which is
fine for a tier that only fires after text healing gave up and unacceptable
anywhere near the hot path.

**Design it from what Tier 1 actually gets wrong.** Level 3 now produces that
evidence automatically; it did not exist before, which is why Tier 3 was
deliberately sequenced after it.

### 4. Make this a library  *(1–2 days, needs care)*
So other projects consume it instead of copying it. `bcpc_run.py` (gitignored)
is the first intended consumer and becomes its own project. Blocker:
`replay()` needs to be path-aware rather than assuming it runs from the repo
root.

### 5. Longer-horizon, from the phase docs
- **Tier 2b** — auto re-run to VERIFY a repair. Blocked on side effects: a
  second pass of a flow that CREATES a record books it twice. Needs a
  `rerun_safe` flag set at record time, defaulting to NO.
- **Phase 9 / RAG** — `chromadb` is already a dependency. Runtime path
  knowledge so AI authoring stops wandering.
- **`scope_id` locator rank** — deliberately NOT built. Wait until
  `GUESS name+tag` actually shows up in a run log rather than predicting where
  duplicates will be.

---

## Known issues, honestly

- **Passwords are recorded in plaintext.** The overlay keystroke capture writes
  whatever you type, including into password fields, into the recording.
  `recordings/` is gitignored so nothing leaves the machine, and the decision
  was explicitly made to accept this. **Close it before anyone else records.**
- **Recordings and baselines contain real employee data** — names, person
  numbers, assignment ids, and on one journals page financial rows. That is why
  `recordings/` is gitignored. Reverse that only after a deliberate decision.
- **Typed dates fail level 3.** Invariant #9 types `dd/mm/yy`; Oracle renders
  `mm/dd/yyyy`; the substring check cannot match. `baseline._undate` could
  normalise both sides.
- **Recording cleanliness** — authoring fumbles (a stray scroll, two waits)
  replay verbatim. Noisy, harmless.
- **`select N` with no value** raises `list index out of range`.
  `loop.py`'s select branch has no argument guard. Same family as
  `runs.build_order`.
- **~25 early commits carry a work email**, recent ones a personal one. Private
  repo, so a decision rather than an emergency.

---

## How to work on this — the method, not the code

The phase docs are full of expensive lessons. Four that generalise:

1. **DevTools before Python.** Nearly every hard bug here was a wrong
   assumption about what the page contains. The grid was "an iframe problem",
   then "a shadow DOM problem", then neither — the selector simply never
   matched. But note the trap in phase2.md: `el.click()` in the console can
   prove a click WORKS and can never prove one FAILS.
2. **Change one thing and re-run.** The healer's "hallucinated index 230" was a
   prompt format bug; the truncation was `num_ctx`; the temperature was
   innocent. All three were only separable by changing one variable at a time,
   and all three were cheap only because `corrupt_step.py` made the failure
   repeatable.
3. **Build the harness first.** `corrupt_step.py`, `test_heal.py`,
   `perceive_probe.py`, `baseline_probe.py`, `baseline_diff.py`,
   `vision_probe.py` — each turns a "wait for Oracle to break" problem into a
   seconds-long loop. Every one of them paid for itself the day it was written.
4. **When a human disagrees with the tool, push on it.** Twice now, someone
   watched a run, said "but that passed fine", and the disagreement found a
   real bug — once a baseline blessed from a half-loaded page, once a warning
   that called grid cells unidentifiable. Explaining the disagreement away
   would have buried both.

And the rule that keeps the whole design honest: **before improving how the
healer answers a question, ask whether the question should reach it at all.**
Anything with an exact, machine-checkable answer belongs in `resolve()`. The
healer's real job is the fuzzy case — a renamed label.

---

## Running it

    py main.py          terminal: (a)i / (m)anual / (o)verlay / (p)layback / (r)un
    py server.py        web frontend -> /api/launch -> log in by hand -> /api/start

Login is manual by design, in both. `.env` holds `BASE_URL` and the model
settings; see `.env.example`.

Offline tools, no browser and no Oracle login needed:

    py perceive_probe.py             perceive against a fixture, ~2 seconds
    py baseline_probe.py             fingerprint + level 3 decisions
    py baseline_report.py <name> -v  which steps changed nothing
    py baseline_diff.py <name>       why level 2 warned
    py check_values.py               live page, values and readable text
    py vision_probe.py <image>       can a model read a screenshot
    py corrupt_step.py <name>        break a step on purpose, to test healing
    py bless.py <name>               accept the last run as the new baseline
