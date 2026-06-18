
## PHASE 3 — DETAILED BREAKDOWN (current work)

The goal of Phase 3 is a working AI decider with enough scaffolding that it
doesn't wander, loop, or run forever. Built in small testable steps.

## 3.0 — Perception edge cases solved during Phase 3
(These are Phase 1 perception concerns, but were cracked while building the
Phase 3 decider, so recorded here. Each found via DevTools on the live page.)
## PERCEPTION EDGE CASES — SOLVED (reference)

Hard-won Oracle Redwood widget quirks and their fixes. Each was found via
DevTools investigation on the live page. Keep this list — these recur.

### Custom-element wrappers not matched by selector
Problem: Oracle wraps real inputs in custom elements (`<oj-input-date>`,
`<oj-select-single>`, Navigator `groupNode` divs) that the ACTIONABLE selector
doesn't query, so perceive never sees them.
Fix: the real `<input>` inside usually DOES match (`[role=combobox]` etc). The
issue is naming, not matching — see getName below. (Navigator needed
`div[id*="groupNode"]` / `div[id*="nvgpgl"]` added to ACTIONABLE.)

### getName — universal label resolution (THE core fix)
Oracle uses many labeling conventions. getName tries them in order:
1. aria-label / title / placeholder
2. aria-labelledby → referenced element's text
3. `<label for="id">` — STANDARD HTML, the universal mechanism (needs
   CSS.escape because Oracle ids contain dots/pipes)
4. enclosing `<label>` ancestor
5. Oracle suffix fallback: id ends `|input` → try `|hint` then `|label`
6. PROXIMITY (last resort, only non-standard step): unlabeled input → label
   text directly above it (vertical gap 0–60px, left-aligned within 40px)
7. own innerText

### Date field (`oj-input-date`)
Not a vision case. Wrapper is custom + unmatched, but contains a real
`<input id=...|input role=combobox>` whose label lives in `<span id=...|hint>`.
Solved by the `|hint` fallback (step 5), later generalized.

### Searchselect comboboxes (collapsed = nameless)
oj-select-single comboboxes only expose their named filter-input
(`oj-searchselect-filter-...`) when FOCUSED/OPEN. When collapsed, the value-input
has no standard label link. Drive them: focus (type a letter) → ArrowDown → Enter.
Cost-drawer comboboxes (Fund/Department/Function/Program/Project) had NO label
link at all → solved by proximity (step 6). Validated across 2 client instances.

### "Submit doesn't advance" = required fields, NOT a bug
Empty required fields below the fold silently block Submit. This is a DATA
condition to report, not a tool failure. (Future: perceive role=alert /
oj-message-error so the AI knows WHY Submit won't advance.)

### Combobox click intercept
Clicking a combobox can be intercepted by a hint overlay. Fix: focus() the input
instead of click() to dodge the intercept.

### Cross-client validated
Universal getName + proximity confirmed working on a SECOND client instance
(different dynamic ids, different form structure). Perception is client-agnostic.

- **Below-the-fold elements**: perceive only sees rendered/in-view elements
  (isVisible requires width/height > 0). Content further down a long page
  (extra springboard tiles, "Show More", lower form fields) won't appear until
  scrolled into view. Human workaround: scroll + wait. FUTURE (for AI driving):
  a scroll-and-re-perceive step so the AI can reach below-fold elements.

### 3.1 — Basic LLM decider  DONE
`ask_llm(elements, goal)` builds a prompt (goal + element list + commands.md),
calls local Ollama (qwen3:14b), returns a command string. Proven: picks `click 3`
correctly on fake data and drives real Oracle with human-approve.

### 3.2 — Human-in-the-loop harness  DONE
Loop prints the AI's proposed command; Enter accepts, typing overrides. Lets us
watch and correct while the AI learns the task. Login stays manual/deterministic
before the AI takes over.

### 3.2b — Declarative `fill <name> <value>` command  DONE (bridge to AI driving)
Name-based fill via Playwright get_by_role(name) — same accessibility-tree
resolution that makes test_change_assignment.py work. One declarative action
instead of the manual focus→type→ArrowDown→Enter ballet. TWO KEY FIXES found by
testing: (1) .focus() not .click() to dodge the |hint overlay intercept;
(2) an ~800ms pause between .fill() and Enter so Oracle's searchselect dropdown
populates before Enter commits it (race condition). Works standalone on comboboxes,
finds by name even when collapsed. Without this, forms are human- but not AI-drivable.

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