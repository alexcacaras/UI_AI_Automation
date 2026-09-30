# HANDOFF — where this project stands, 2026-09-30

Written on the last day of the original author's time on it, for whoever picks
it up next (possibly the same person, later, on their own time).


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
root. Don't necessarily need this.

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

---

## Where this is going — the longer arc

Sources: `roadmap.md` (the master phase list), the Direction / vision section of
`CLAUDE.md`, and Phase 0's layer stack. Everything below is **plan, not
capability** — do not read it as something that exists.

### First, a numbering warning

`roadmap.md`'s phase numbers and the `phases/phase*.md` files have **drifted
apart**. Roadmap Phase 7 is "cross-client validation"; `phase7.md` is the web
frontend, which the roadmap never anticipated. Roadmap Phase 8 is "document +
vision intelligence" and includes variables — which shipped early, today, as
`variables.py`.

Trust the `phase*.md` files for what was BUILT and `roadmap.md` for where it was
HEADED. Reconciling them is a half-hour job someone should do before adding a
"Phase 13".

### The layer stack — the shape the whole thing is growing into

Phase 0 defined four layers, and only the bottom one is really built:

    Primitives       click, type, press, nav, wait, scroll, select     BUILT
    Blocks           named reusable sequences (login, go_home)         not built
    InstructionSets  the missions / tests                              partly - a
                                                                       recording IS
                                                                       a primitive
                                                                       InstructionSet
    Run              session_setup + ordered tests                     partly - runs.py
                                                                       does the ordering

**Blocks are the biggest missing piece**, and the most useful next structural
step. Today every recording re-records its own navigation from Home, so a
Navigator change breaks all of them and each is repaired separately. With
Blocks, `go_home` and `login` are authored once and every test inherits the fix.
It also makes login deterministic and credential-driven instead of recorded,
which is what `phase0.md` says it must be and what the plaintext-password issue
is really about.

### The near-term product line, from the roadmap

- **Cross-client / cross-instance validation.** Prove one authored flow runs
  against a different pod by swapping `ClientConfig` — URL, `${variables}`,
  credentials. This is the "works anywhere" claim, and `variables.py` was the
  missing half. The other half is ClientConfig itself, still unbuilt: today
  `BASE_URL` lives in `.env` and there is no per-client file.
- **Guardrails hardening.** `risk_level` (safe / write / destructive) is in the
  Phase 0 Step schema and is enforced nowhere. The engine should refuse a
  destructive action unless config allows it. Relevant sooner than it sounds:
  the BCPC job wrote to real user accounts, and nothing in the tool knew that
  was different from clicking a menu.
- **Testmodus integration.** Consume the existing instruction sets — named step
  lists, sets calling other sets, variable definitions — as authored paths.
  Note the shape already matches: Blocks and `${variables}` are exactly what
  those sets assume.
- **Product UX.** Pick an instance and credentials, pick a test, watch it run.
  `server.py` is the first third of this.
- **RAG (Phase 9).** `chromadb` is already a dependency and
  `chunk_master_doc.py` already builds chunks. Feed the AI the relevant
  instruction-set chunk at runtime so authoring stops wandering. The Phase 3
  finding points straight here: models won on instruction-following, not Oracle
  knowledge, so supply the knowledge at runtime rather than training it in.
  **RAG, not fine-tuning** — lighter, updatable, and correct for a system whose
  domain changes every Oracle release.

### The long horizon — beyond the browser

From `CLAUDE.md`, stated there as direction and not a commitment: the same
perceive → decide → act loop generalises to the whole laptop. A local, private
assistant where the data never leaves the machine.

**The hard part is PERCEIVE, and this project is the evidence for why.** Off the
web there is no DOM, so perception moves to OS accessibility APIs, OCR
(`pytesseract`, already a dependency) and vision. Everything painful in these
phase docs — naming elements that have no label, identity that survives a
re-render, telling structure from data, knowing when the screen has settled —
recurs there without a DOM to lean on. Action generalises far more easily
(`pyautogui`, also already a dependency); input was never the bottleneck.

Two things learned here transfer directly and are worth carrying:

- **Identity, never position.** `ui-id-138` renumbers every session; a grid cell
  IS its `{row, column}`. On a desktop the same rule decides whether automation
  survives a window move.
- **Verification is a ladder, not a boolean.** "It ran" is not "it worked" is
  not "it did the right thing to the right record". That distinction cost most
  of Phase 6 to learn and is not specific to browsers at all.

---

## If you want to use Claude Code on this

This project was built with Claude Code, and most of what made that work was the
`CLAUDE.md` file. Below is a version you can drop into a new project and adapt —
it is the one from here, trimmed to the parts that generalise.

The important part is not the file format. It is these four instructions, which
are what stopped the tool from autopiloting through a codebase its author was
still learning:

- **Explain before editing** — propose, justify, show the diff.
- **One small, independently testable change at a time.**
- **DevTools first** — validate on the live page before touching Python.
- **Honest pushback over agreement.**

Three habits mattered as much as the file:

1. **Write the lessons down as you go, including the wrong turns.** The
   `phases/*.md` docs in this repo record what was tried and was WRONG —
   `num_ctx` versus temperature, the two write-back gates that both failed, the
   console test that can prove a click works but never that one fails. That is
   the expensive knowledge, and it is what lets a fresh session pick up where
   the last one stopped instead of re-deriving it.
2. **Build a throwaway harness before debugging anything slow.** Every probe in
   this repo paid for itself the day it was written.
3. **Make it prove things, and say when something is unproven.** "Tested
   offline only, the UI path is unproven" is in a commit message in this repo,
   and that sentence is worth more than a confident claim.

````markdown
# CLAUDE.md — <project name>

## What this project is
<Two or three sentences. What it does, who it is for, and the ONE architectural
commitment that must not be broken. Ours was: determinism in the hot path, the
LLM only at authoring and repair time.>

---

## How I want you to work with me — read this first
This is a learning project. I want to learn the code, not just receive it.

- **Explain before editing.** Propose the change and tell me *why*, then show me
  the diff. Ideally I understand it well enough to have written it myself.
  Do not autopilot through multiple files.
- **One small, independently testable change at a time.** I test each change by
  hand before we move on. This needs my manual testing between steps — it is
  not a batch job.
- **Validate in the real environment first.** Check the browser console / the
  live system / the actual data before touching code. Never assume the code is
  the right place to start.
- **Teach the code.** Explain the mechanism, not just the result.
- **Honest pushback over agreement.** If my idea is wrong or fragile, say so and
  say why. Correctness before speed.

---

## Environment
- <OS and shell. Ours: Windows / PowerShell only, no `&&` chaining.>
- <Local path, repo, branch.>
- <How I share screenshots with you — for us, pasting into the terminal does not
  work, so: read the NEWEST file in <folder>, sorted by modified time.>

## Stack
<Languages, frameworks, local services, models. Note anything non-obvious about
why a particular choice was made.>

---

## File map
- `foo.py` — one line on what it owns
- `bar.py` — one line on what it owns
- `phases/phaseN.md` — **design + hard-won lessons per area. Read the relevant
  phase doc before working in that area.**

---

## Hard invariants — violate these and working code breaks silently
<The rules that are not obvious from reading the code, each with the CONSEQUENCE
of breaking it. Ours included:>

1. Two naming functions must stay in sync; a fix goes in BOTH.
2. Indices are valid only for the current snapshot. Never reuse one.
3. Record identity, never position.
4. <...>

Keep these to things that break SILENTLY. A rule whose violation throws an
error does not need to be here — the error will say so.

---

## Where we are
**Built and working:** <the honest list>

**In progress:** <what is half-done, and what "done" means for it>

**Known bugs, not yet fixed:** <state them plainly, including the ones you have
decided to live with and why>

**Deferred, not blocking:** <things deliberately parked, with the reason —
"wait until X actually shows up in a log rather than predicting where it will">

---

## Direction / vision — NOT built (aspiration; do not treat as current capability)
<Where it is going. Label it clearly so a future session does not mistake a plan
for a feature.>
````

### Two more things worth doing

- **Keep a per-area doc, not one giant file.** `CLAUDE.md` says what the project
  is and how to work; `phases/phaseN.md` holds the detail and the history for
  one area. Then "read phase6.md before touching the healer" is a one-line
  instruction that loads exactly the right context.
- **Ask it to write the commit messages, and make them explain WHY.** The git
  log in this repo is genuinely useful documentation — it records the reasoning
  and the rejected alternatives, not just the diff. That costs nothing extra at
  the time and is worth a great deal six months later.
