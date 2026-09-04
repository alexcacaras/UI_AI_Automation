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

### Unproven, kept anyway
The recorded-path context (all steps, with the failing one marked, plus "the steps
after this must stay reachable") is built and costs ~270 tokens. It has NOT been shown
to change an outcome — both proven heals were winnable on the label alone, so every
prompt variant passes them. Keep it (rare call, cheap, can only help on hard cases)
but do not claim it works until a heal with several equally-plausible candidates
turns on it.

### Not done in Tier 1
- `select` steps cannot heal — only the click/type branch is hooked.
- No write-back. That is Tier 2.

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

## Act 2 — write-back (NEXT PHASE, not now)
After a successful heal, write the corrected locator back into the recording so the
NEXT run finds it deterministically and never calls the LLM again. This is what makes
the recording LEARN. Deferred deliberately:
- For id-full elements: write back the new id — clean.
- For id-less elements (calendar cells, some Oracle divs): there's no id to write. This
  forces Phase 0's RANKED LOCATORS — append a new way to find it (scoped CSS / position),
  re-ranking over time. That's a real chunk of design; keep it out of Act 1.

## Parked / future (recorded so ideas aren't lost)
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