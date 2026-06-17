
## PHASE 3 — DETAILED BREAKDOWN (current work)

The goal of Phase 3 is a working AI decider with enough scaffolding that it
doesn't wander, loop, or run forever. Built in small testable steps.

### 3.1 — Basic LLM decider ✅ DONE
`ask_llm(elements, goal)` builds a prompt (goal + element list + commands.md),
calls local Ollama (qwen3:14b), returns a command string. Proven: picks `click 3`
correctly on fake data and drives real Oracle with human-approve.

### 3.2 — Human-in-the-loop harness ✅ DONE
Loop prints the AI's proposed command; Enter accepts, typing overrides. Lets us
watch and correct while the AI learns the task. Login stays manual/deterministic
before the AI takes over.

### 3.3 — Action history (NEXT — highest value)
Keep a short list of the last N (command, result) pairs and put it in the prompt.
Fixes the #1 observed failure: the AI re-clicking the same stuck element forever
because each decision is currently stateless. "You already tried click 18 twice,
it failed" lets it try something else.

### 3.4 — Stop condition / done detection
Give the AI a clear success criterion in the goal ("you are done when the search
results table appears") and rely on history so it can recognize completion and
emit `done` instead of running forever.

### 3.5 — Output parsing / cleanup
Strip any `<think>…</think>` reasoning and stray text so only the bare command
reaches the parser. Handle the AI returning junk gracefully (ask again / skip).

### 3.6 — Overlay / intercept handling
Observed: Navigator flyout elements get stamped but are covered by an overlay
(`intercepts pointer events`), so clicks time out and the AI loops. Investigate
manually (drive Navigator by hand), then decide: prefer home-page tiles, or make
click more robust against overlays. (May fold into Phase 1 settle-gate work.)

### 3.7 — Model swap via env
Make the model name an env var so qwen3:14b / mistral-small / phi4 / qwen2.5-coder
can be A/B tested for speed and accuracy without code changes.

### Phase 3 exit criteria
The AI, given a goal + history, drives a multi-step real-Oracle flow end to end
with NO human overrides, recognizes when it's done, and doesn't loop on stuck
elements. (Login still handled deterministically beforehand.)