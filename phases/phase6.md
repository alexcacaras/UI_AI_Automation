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

## Act 1 — recover the run (THIS PHASE)
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

## Act 2 — write-back (NEXT PHASE, not now)
After a successful heal, write the corrected locator back into the recording so the
NEXT run finds it deterministically and never calls the LLM again. This is what makes
the recording LEARN. Deferred deliberately:
- For id-full elements: write back the new id — clean.
- For id-less elements (calendar cells, some Oracle divs): there's no id to write. This
  forces Phase 0's RANKED LOCATORS — append a new way to find it (scoped CSS / position),
  re-ranking over time. That's a real chunk of design; keep it out of Act 1.

## Parked / future (recorded so ideas aren't lost)
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