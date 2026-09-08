# Phase 6 — The Healer (LLM-assisted locator repair)

GOAL: when a replay step's locator no longer resolves, don't give up — ask the LLM
to find which current element the step MEANT, so the run survives UI changes.
This is the architectural payoff: deterministic hot path, LLM only on failure.

## The bet
- Replay is fast and deterministic (no LLM) as long as locators hold.
- When Oracle changes the UI and a locator breaks, the healer engages — LLM re-finds
  the element from the current page + the recording's goal/context.
- The LLM is NEVER in the hot path; it only runs when find_by_id / find_by_name fail.

## The hook (already in place)
replay.py, inside the click/type branch:
    if el is None:
        print("couldn't find ... after retries, stopping")
        return False        # <-- healer engages HERE instead of giving up

The deterministic finder has already exhausted its 5 retries by this point, so the
healer's job is NOT "try harder to find by id/name" — it's "figure out which element
the step meant, when the saved locator no longer matches."

## Prerequisite — DONE (envelope + goal)
Recordings are now {name, goal, steps} (was: bare array).
- loop.py: prompts for goal at record time (recording modes only), saves envelope.
- replay.py: reads .steps, extracts goal (isinstance check tolerates old bare arrays).
- The `goal` variable is in scope at the return-False point, ready to feed the healer.

## Act 1 — recover the run (DONE — see TIER 1 BUILT AND PROVEN, below)
A heal_step function that, given the failed step + current elements + the goal,
picks which current element is the lost one, so replay can act on it and continue.

Inputs to the healer:
  - failed step: {action, name, role, tag, id}  (the description of what we lost)
  - current perceived elements                    (the candidate set)
  - the recording's goal                          (intent / context)
Output:
  - the chosen element dict (replay does click/type on el["index"]), OR
  - None / give-up (the escape hatch — later this is what escalates to vision)

Design decisions (locked):
- NEW function (heal_step in llm.py), NOT a reuse of ask_llm. ask_llm answers
  "what's the next action?"; heal_step answers "which current element IS this lost one?"
  Different question, different prompt, different output.
- Constrained output: LLM returns JSON {"index": <n>, "reason": "<why>"}, with
  {"index": -1} meaning "no plausible match" (the give-up signal).
  Log the reason (for debugging), but only the index feeds the action.
- Send ALL current elements first (unfiltered). Add candidate filtering only if token
  size or wrong-picks demand it — prove the simple version first.
- TEXT-ONLY to start. Vision (screenshot) is a later escalation tier, triggered by the
  text healer returning -1. Design the give-up path in from the start so vision can slot
  in behind it, but don't build vision yet.
- Return the whole element dict on success (replay works in el["index"]; and Act 2
  write-back will need the full id/name/tag).

## TIER 1 — BUILT AND PROVEN (2026-09-03)

Healing works end to end on real Oracle pages, for both click and type steps.

What exists:
- `llm.py` — `heal_step(step, elements, goal, rank, steps, step_index)`. Returns
  `(element_dict_or_None, reason)`. Behind it: `_complete` (provider shim),
  `_complete_ollama`, `_extract_json`. `ask_llm` untouched.
- `replay.py` — hook at the `el is None` point in the click/type branch, AFTER the
  five deterministic retries. A step that resolves never touches the LLM.
- `corrupt_step.py` — the test harness. Breaks one step of a recording on purpose.
- `test_heal.py` — offline prompt harness, fake elements, no browser. Seconds per
  iteration. Note its limit: ~600 tokens of fake page, so it CANNOT reproduce any
  problem that only appears on a real, large page (see the num_ctx trap below).
- `.env` — `HEALER`, `HEALER_PROVIDER`, `HEALER_MODEL`, `HEALER_NUM_CTX`,
  `HEALER_TEMPERATURE`, `HEALER_MAX_CONSECUTIVE`. Documented in `.env.example`.

Proven on:
- `test` step 12 (`My Client Groups` -> corrupted to `Client Groups`, id blanked):
  healed, and steps 13-14 then resolved with NO healing — which is the real proof.
  A wrong pick would have put the run in a different Navigator module where
  `Time Management` does not exist.
- `typetest` step 7 (a `type` into `Name` -> corrupted to `Person Name`, id blanked,
  on a page that also has a `Person Number` field): healed to the right input, and
  the search returned the expected rows. Same self-validating shape.

### The harness is the important part
Breaking a step on demand makes healing testable in minutes instead of waiting for
Oracle to change. TWO THINGS MUST BE BROKEN, not one:
- Ranked locators (`actions.resolve`) walk grid -> id -> name+tag. Blanking ONLY the
  id now falls through to name+tag and PASSES. The healer never fires and the test
  proves nothing. So blank the id AND staleness the name (and grid/row/col for a cell).
- Reword the name plausibly ("Name" -> "Person Name"), never to gibberish. Gibberish
  gives the model nothing to match on, so -1 is the CORRECT answer and you learn
  nothing about healing.
- Break a step that LATER steps depend on. Then the recording validates the heal for
  you and you never have to trust the model's stated reason. Breaking the last step
  of a recording tests nothing: a wrong pick still reports PASS.

## CASE STUDY — a classic-Navigator recording surviving Oracle's Redwood shell
### (2026-09-04, unplanned. This is the proof the whole phase exists for.)

Not a manufactured break. `typetest_broken` was replayed expecting to test ONE
corrupted step, and instead the pod had been upgraded underneath it: the classic
Navigator was gone, replaced by the Redwood shell, and every navigation id had
been renamed from `pt1:_UISnvr:0:nvgpgl2_*` to `ojSpSimpleUIShellNavigator_*`.

A recording made against the old UI. A page that no longer has any of its ids.
**The run finished, on the right record, and reported PASS.**

What each step did:

| step | recorded | what happened |
|------|----------|---------------|
| 1 | click `Oracle Logo Home` (id `pt1:_UIScil1u`) — NOT corrupted | id gone → 5 retries → HEALED |
| 2 | click `Navigator` (id `pt1:_UISmmLink`) | id gone → resolved on **name+tag**, new id `ojSpSimpleUIShellNavigator_NAVa5` |
| 3 | click `My Client Groups` | id gone → resolved on **name+tag** |
| 5 | click `Person Management` | id gone → HEALED |
| 6 | click `Name` (the search input) | HEALED |
| 7 | type into `Person Name` (the deliberately corrupted step) | HEALED → `<input> "Name"` id `_FOpt1:…SP3:q1:value00::content` |
| 9-11 | More Information, Actions, Assignment Status | **resolved on their recorded ids, no healing** |

TWO layers did the work, and telling them apart matters:

- **Ranked locators (no LLM, no cost) carried steps 2 and 3.** The ids were gone;
  the names were not. This is Phase 5i paying for itself — before ranked locators
  these two steps would have been heal requests, and the healer would have had
  four extra chances to be wrong.
- **The healer carried steps 1, 5, 6 and 7** — the ones where the label itself had
  moved, which is the fuzzy case it is actually good at.

### Why the "wrong-looking" heals were not wrong

Read in isolation the heals look bad: `Oracle Logo Home` healed to an `Actions`
button, `Person Management` healed to a link named `My Client Groups`, `Name`
healed to a link named `Person Management`. Reviewed live, that looked like a
four-heal cascade and was nearly written up as one.

It was not. Redwood restructured the navigation, so the recording's steps no
longer map one-to-one onto the new UI — and each heal picked the element the
FLOW needed at that point rather than the one the step's label named. The
sequence re-aligned itself to the new shell.

**The evidence, and the only part of this that is not interpretation:**

1. Step 7 healed onto `_FOpt1:…SP3:q1:value00::content` — the exact id recorded in
   the uncorrupted `typetest.json`. It arrived precisely where the recording meant
   to be.
2. Steps 9, 10 and 11 then resolved **deterministically on their recorded ids**.
   Those ids only exist on the Person Management results page. No model was
   involved in that; either they are on the page or they are not.

A recording is its own oracle. Later steps resolving on their original ids is
proof of position that no stated reason from a model can give you, and it is why
phase6.md tells you to break a step that LATER steps depend on.

### Why MAX_CONSECUTIVE correctly did not fire

Four heals in one run, and the cap (3) never tripped — because heals were
separated by steps that resolved on their own. That is the invariant working as
designed, not a near miss: a step resolving deterministically PROVES the page is
the expected one, which retires the cascade worry the counter exists for.

### What this case study is evidence FOR

That the product thesis holds: **agency at authoring and repair time,
determinism in the hot path.** Oracle ships UI changes continuously. A
traditional recorded regression suite breaks on an upgrade and a human re-records
it. This one absorbed a shell replacement — a rename of every navigation id in
the flow — and kept running, on a local 8B model, without a human.

### What it is NOT evidence for

- **That heals are self-checking.** Nothing in the run verified the heals. They
  were validated afterwards, by a human reading which ids resolved later. A run
  where the heals were wrong would have looked identical up to the moment it
  didn't.
- **That the write-back from this run is trustworthy.** Step 3 wrote back id
  `ojSpSimpleUIShellNavigator_groupNode_benefits` for an element named
  `My Client Groups`. Unique name+tag match, so `resolve()` believed it — but the
  id says *benefits*. Unresolved; the next replay answers it. Backup:
  `recordings/backups/typetest_broken.20260904-122459.json`.
- **That it generalises to parameterised runs.** Heals are chosen against one
  page state. The same heal on a different user's page may not apply.

## HARD-WON LESSONS (cost most of a session — read before blaming a model)

**1. Ollama's `num_ctx` silently truncates. This is the big one.**
`ollama show gemma4:e4b` advertises 131072 context. That is what the MODEL can do.
Ollama allocates only `num_ctx` per request and its own default is small (2048 on
this setup). A Navigator page perceives to ~2800 prompt tokens, so the prompt was
being CUT with no error and no warning. The model then answered confidently from a
page it had only half received — it picked "Sales" for "Client Groups" and reasoned
about the SHAPE of divs, because shape was all that survived truncation.

The failure looks exactly like a weak model. It is not. Set `num_ctx` explicitly,
and print `prompt_eval_count` from the response — that number is the ground truth
for what the model actually ingested, and `_complete_ollama` now warns when it hits
the ceiling. Before swapping models, always check that line first.

**2. Temperature was NOT the cause — and the wrong conclusion was nearly recorded.**
gemma's default `temperature` is 1, which looked like an obvious culprit for erratic
picks. It was tested directly (set back to 1, everything else unchanged): it healed
correctly twice. Keep temperature 0 anyway — healing is a lookup, not composition,
and a regression tool must give the same answer twice — but it is NOT the fix.

Both of these were only distinguishable by changing ONE thing and re-running. The
first diagnosis, the correction to it, and the correction to THAT were all cheap only
because `corrupt_step.py` made the failure repeatable.

**3. An 8B local model is enough for this task.** gemma4:e4b heals correctly once it
can see the whole element list. The instinct to reach for `qwen3:14b` / `phi4:14b`
was premature and would have "fixed" it for the wrong reason, leaving a slower model
in place forever. Order to reach for things: prompt rules -> few-shot examples ->
bigger model -> more perceive detail. The last one is the real ceiling: if two
elements perceive identically, NO model can tell them apart — that is an information
problem, not an intelligence problem.

**4. "Hallucinated index 230" was NOT hallucination — it was my prompt format.**
The healer kept answering index 230, identically every run. The element lines read:

    76: <div> "row 5, Quantity (col 10)" id=ui-id-230

A bare number at the front, another at the back, nothing saying which was which.
It was reading the digits out of the id. Fixed by labelling the field (`index=76`)
and by NEVER sending a grid cell's id at all — `ui-id-N` is a jQuery counter that
renumbers every session (invariant #12), so it was meaningless noise shaped exactly
like an answer. A stable, repeatable wrong answer is evidence of a systematic cause;
random wrongness is the model. 230 every single time was the tell, and it was missed
for two runs by calling it hallucination.

**4b. Retry-with-feedback is worth having, and -1 must never be retried.**
`heal_step` now re-asks on an invalid or unparseable answer, carrying the element
list (so the correction stays grounded in the real page), what it previously
answered, and why that was rejected. `HEALER_MAX_ATTEMPTS`, default 2. A `-1` is
never retried: it is a legitimate answer, and re-asking after a correct give-up is
pressure to fabricate a match that does not exist.

**4c. EXACT NUMERIC LOOKUP IS NOT A LANGUAGE-MODEL TASK. Read this one twice.**
A time-card cell was corrupted realistically (grid element renamed, `row=0 col=9`
intact and IN the prompt). The correct answer was an exact match on two integers.
gemma answered `row 2, Quantity (col 22)` — wrong row, column thirteen positions off
— and wrote a fluent justification: "row 1 (which corresponds to the second data row
in the grid structure)". It never looked anything up. It chose a cell and then
explained it. Three runs, three different wrong cells, three confident reasons.

The fix was NOT a better prompt or a bigger model. It was realising the healer should
never have been asked: `actions.resolve()` gained a `grid-position` rank (match
`{row, column}` when the grid's own id no longer matches, falling through if more
than one grid shares the position). The step now resolves deterministically, instantly,
for zero tokens — and `find_by_grid` requiring all three fields was a real gap in
Phase 5i, not something Phase 6 introduced.

Generalise it: before improving how the healer answers a question, ask whether the
question should reach the healer at all. Anything with an exact, machine-checkable
answer belongs in `resolve()`. The healer's real job is the FUZZY case — a renamed
label — which it handled correctly on both the Navigator and Person Management tests.

**5. Cascading heals are the dangerous failure, not a single wrong heal.**
Observed: step 12 healed wrong -> step 13 healed wrong ON TOP of it -> the run walked
deeper into the wrong module, each heal individually plausible, the sequence nonsense.
`replay.py` now caps CONSECUTIVE heals (`HEALER_MAX_CONSECUTIVE`, default 3) and
stands the healer down past that. Consecutive, not total: two heals far apart are two
unrelated Oracle changes, both legitimately repaired; two back to back mean the second
is judging a page the first one navigated to.

**6. A green run that needed healing is not a green run.** replay now says so at the
end. Without it, drift is invisible until the day it stops healing.

**7. Recording goals matter now.** `test.json` has `goal: "test"`, which is worth
nothing to the healer. `typetest.json` has a real one, and that is the difference
between the model knowing it is searching for a person and guessing from labels.
Tell teammates: the goal is not a label, it is context the repair path reads.

**8. A heal request can be a symptom of a broken ACTION, not a broken locator.**
The BCPC bulk job asked the healer "which element is `BCPC_TRUSTEES`?" on a page
where the User Category dropdown had never opened — because `actions.click()`
sent the combobox to `.focus()`, which does not open it (see phase2.md, "focus()
is not a click"). The option was not in the DOM. There was no correct answer, and
the healer was about to invent a plausible one.

This is 4c's rule with a second class added. Questions that should never reach
the healer:
  - **exactly answerable** — belongs in `resolve()` (4c: grid row/column);
  - **unanswerable because the PREVIOUS step silently did nothing** — belongs in
    a bug fix.
Only the genuinely fuzzy case is the healer's job.

Practical tell: when a heal request appears for an element that should obviously
be on screen, suspect the step BEFORE it before suspecting the locator. Replay
verifies an element was FOUND, never that the action DID anything, so a no-op
step is invisible until the next step cannot find what it produced.

### Unproven, kept anyway
The recorded-path context (all steps, with the failing one marked, plus "the steps
after this must stay reachable") is built and costs ~270 tokens. It has NOT been shown
to change an outcome — both proven heals were winnable on the label alone, so every
prompt variant passes them. Keep it (rare call, cheap, can only help on hard cases)
but do not claim it works until a heal with several equally-plausible candidates
turns on it.

### Not done in Tier 1 — BOTH CLOSED 2026-09-08
- ~~`select` steps cannot heal~~ — DONE. The `select` branch now has the same healer
  hook and write-back as click/type. Worth knowing what `select` means here: a NATIVE
  `<select>` element driven by `select_option`. Oracle's Redwood/ADF dropdowns are
  divs, inputs and `<li role="option">`, so they were always recorded as CLICKS and
  always healed. Only 4 `select` steps exist across every recording — a small hole,
  but "this action type cannot be repaired" is the kind of gap that confuses for an
  hour when it finally bites.
  The two branches are separate blocks (click/type also scrolls virtualized grids
  while retrying) and carry comments saying they must be changed together.
- ~~No write-back~~ — DONE. See TIER 2 below.

The `is_grid` recompute is DONE AND CONFIRMED. replay reads `is_grid` off the RESOLVED
element, not the step: a healed grid cell whose step lost its grid identity would
otherwise take the `focus()` path, stay in 'navigation' mode and swallow every
keystroke silently while still reporting PASS. Verified on a `test1` heal — the cell
entered edit mode and the value landed.

### Grid cells and the healer — the rule that came out of this
Do NOT send a grid cell to the healer when its position survives. `resolve()` handles
the renamed-grid case now (`grid-position` rank). The healer only sees a cell if BOTH
the grid id and the row/column are gone — and that step is probably UNHEALABLE in
principle, because a cell's identity IS its position and no model recovers deleted
information. `corrupt_step.py --blank-position` produces that worst case deliberately;
the right outcome there is the healer giving up, and Tier 2 should be able to say
"re-record this step" rather than pretending a repair happened.

### New known issue found while testing
Replay verifies that an element was FOUND, never that the action DID anything. A
`typetest` run ended inside an open Oracle cascading menu, having navigated nowhere,
and printed `run passed`. Same family as the checkbox no-op bug. Locator resolution
is not interaction success.

## STATUS UPDATE — the Act 2 blocker is gone

Ranked locators are BUILT (phase5.md 5i). `actions.resolve(elements, step)` walks
grid → id → name+tag(unique) → name+tag(guess) and returns WHICH rank matched, which
changes two things for this phase.

First, the healer fires less often and for better reasons: a step whose id went stale now
recovers on name+tag instead of failing, so a heal request means the locator genuinely
lost the element rather than "the id renumbered." Second, Act 2 write-back is now possible
for id-less elements — the thing that was blocking it. Replay already prints
`locator degraded -> matched on <rank>`, so a step that has been falling back for weeks is
a repair candidate BEFORE it ever fails. Feeding that rank to the healer is likely more
valuable than the goal string.

## TIER 2 — WRITE-BACK. DONE AND PROVEN (2026-09-08)

After a step resolves on anything looser than the tightest locator — including a heal —
the recording is repaired, so the next run matches at rank 1 and pays nothing. This is
what makes a recording LEARN instead of decay.

`writeback.py`: `plan_repair(step, el, rank, reason)` decides what to change,
`apply_repairs(name, data, repairs)` backs up and writes. `replay.py` buffers repairs
and commits them at the end of a passing run.

### Proof (the numbers, not an opinion)
| recording | before | after |
|---|---|---|
| `test1_broken` | step 7 `grid-position` | silent, rank 1 |
| `test_broken` | 1 heal | 0 heals |
| `typetest_broken` | 4 heals + 2 degraded | 0 heals, 0 degraded |

Five model calls across two recordings, then zero, permanently. `typetest_broken` is
the strong case: it re-aligned a classic-Navigator recording onto the Redwood shell
(see the case study above) and then FROZE that alignment into the file.

### WHEN it writes — end of a passing run, from a buffer. Never at resolve time.
A repair claims the new locator points at the element the step meant, and the evidence
is the rest of the run working from the page that step landed on. The asymmetry decides
it: buffering and losing a repair to a later failure costs ONE RUN (the next run
re-degrades and offers it again); writing early and being wrong costs the RECORDING,
and `recordings/` is gitignored so there is no `git checkout` to undo it.

### What it writes, per rank
| rank | repair |
|---|---|
| `grid` / `id` | nothing — already tightest |
| `grid-position` | refresh `grid`; keep `row`/`column`; force `id` blank (invariant #12) |
| `name+tag` unique | write today's `id` (or blank if the element has none); refresh `name`/`tag` |
| `healed` | same, plus `healed_from` provenance |
| `GUESS name+tag` | **NOTHING. Reported only.** |

A GUESS means several elements matched and `resolve()` took the first, with no evidence
it is the right one. Writing that id back would freeze an arbitrary pick as rank-1 truth
AND delete the loud GUESS warning that is the only signal the step is ambiguous — the
drift would go invisible at the same moment it went permanent.

### Provenance — the recording has to explain itself
A heal rewrites the locator, so without provenance a step silently stops describing what
a human meant: `"Oracle Logo Home"` becomes `"Actions"` and nobody can tell what the step
was ever for. Each repaired step keeps:

```json
"healed_from": {"name": "...", "id": "...", "tag": "...",
                "when": "2026-09-08", "reason": "<the model's own words>",
                "originally": "<the label a HUMAN recorded>"}
```

`originally` survives repeated heals — every later repair overwrites the immediate
previous locator, but the human's label is the one never to lose. Backups
(`recordings/backups/`, newest 5) restore the whole file; provenance lets you revert one
step. Together they are version control where the machine is one of the authors.

### TWO GATES WERE TRIED AND BOTH WERE WRONG. Do not re-invent them.
1. **"a heal followed by another heal is suspect."** No. In a whole-UI migration
   consecutive heals are what a legitimate repair LOOKS like.
2. **"only write back if a later step resolves at rank 1."** No. In a total id change
   NOTHING resolves at rank 1 anywhere, so this refuses to repair exactly the case the
   healer exists for.

Both failed identically: they infer "did this work?" from HOW LOCATORS RESOLVED, which
is a property of the locators, not of the task. In a total UI change every
locator-derived signal goes to zero while the task may have completed perfectly.

**So the evidence write-back actually runs on is "the run completed", which is weaker
than it sounds** — replay verifies an element was FOUND, never that the action DID
anything. That is knowingly accepted, and the backup plus provenance are the mitigation:
not provably right, but recoverable and auditable. The real fix is outcome verification
(below), and until that exists no gate will do its job.

## THE NEXT THING — outcome verification (blocks Tier 3, unblocks everything)
There is still no machine definition of "the test worked". `run passed` means every step
found an element. It does not mean the timecard saved, the category changed, or the
person was found. A `typetest` run once ended inside an open cascading menu, having
navigated nowhere, and printed `run passed`.

Design agreed, not built — compare STRUCTURE, not pixels:
- On a known-good run, save a baseline per step: the set of element names/ids `perceive`
  saw. Store it with the recording.
- On later runs, compare. A step landing somewhere structurally different is a real
  failure even when every locator resolved.
- Pixel diffing is the wrong tool — Oracle pages legitimately differ on employee names,
  timestamps and row counts. Structure is stable; pixels are not.
- Screenshots stay for HUMANS to audit. Vision (Tier 3) becomes the escalation when the
  structural check is ambiguous.

Compare against the LAST KNOWN-GOOD run, not the original recording: write-back already
means the recording drifts forward with the application.

Evidence this is the missing piece: on the BCPC bulk job the only thing that caught a
silent no-op was ORACLE disabling its own Save button because nothing had changed. The
application knew the task had not happened. The tool did not.

## Parked / future (recorded so ideas aren't lost)
- **Auto re-run to VERIFY a repair (Tier 2b).** After a healed run writes its
  repairs back, go Home and replay the recording again automatically. A second run
  that needs NO healing is machine-checkable proof the repair was right; today
  that proof only exists because a human reads the log. This closes the gap the
  Redwood case study exposes — the heals there were correct, but nothing in the
  system knew it.
  **The blocker is side effects, and it is a hard one.** Re-running is free for a
  read-only navigation flow and destructive for anything that CREATES a record —
  a second pass books the absence twice. So this needs recordings to declare
  whether they are safe to repeat (a `rerun_safe` flag set at record time), and
  the default must be NO. Worth building for the navigation-heavy regression
  suites, which are the ones that break on Oracle upgrades anyway.
  Narrower variant if the flag proves unworkable: re-run only far enough to
  re-resolve the healed step, not the whole flow.
- Tier 3 vision — the privacy question now has a concrete example rather than a
  worry. A `typetest` run ended on a Person Management results page showing two
  employees' names, person numbers and national IDs. The ELEMENT LIST from that page
  is labels and ids; a SCREENSHOT of it is a payroll record. That is the argument for
  vision staying local even if the text tier one day does not.
- Retry-with-feedback: if a heal picks wrong, the NEXT step fails. Idea: re-heal the
  original step in place, telling the LLM "you picked X, the next action failed, choose
  differently." Do NOT rewind to step 1 (expensive; re-runs side effects like created
  records). Build only after seeing how often first-pick is wrong.
- Prompt size on big pages: 200-element grids bloat the prompt. Filter candidates
  (by tag/role) before sending if it bites. Prompt-size problem, not a training problem.
- NO fine-tuning. Healing is a MATCH task squarely within base-model ability; quality
  comes from the prompt, not training. Phase 3 finding: models win on instruction-
  following, not domain knowledge. Revisit training only if prompting plateaus with real
  failure data.
- Two-field goal (short human goal for healing vs. detailed AI-driving prompt): only
  split when AI-mode authoring is actually used. One short goal serves both today.

## Known issue surfaced during envelope work (separate, parked)
- Perceive reports elements but NOT their values, so a filled field looks identical to
  an empty one. did_change returns "no change" after a successful type, and AI mode then
  thinks the type failed and repeats it. Only bites AI mode (overlay/manual don't rely on
  did_change to confirm a type). Low priority since authoring is via overlay/manual.
- Credentials in recordings: AI-mode login run saved a plaintext password into the goal
  string. Confirms login must be a deterministic block reading ${creds} from .env, NOT a
  recorded flow. (Delete any test recording that captured a real password.)