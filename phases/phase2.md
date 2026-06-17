# Phase 2 — Action Layer (Built & Proven on Real Oracle)

**Status: COMPLETE** — every primitive exercised by hand against a live
Redwood instance, including a full Change Assignment journey.

Phase 2 is the half of the loop that *acts*: given the numbered element list from
`perceive()`, a command names one element by index and does something to it. The
human currently types the commands; in Phase 3 the LLM types them instead. The
loop does not change when the AI goes in — only who produces the command changes.

Every decision below is backed by real terminal runs on live Oracle (login →
navigation → search → record selection → multi-step Redwood flows), not assumptions.

---

## The headline result

By hand, through the generic perceive→act loop, the full **Change Assignment**
flow from `test_change_assignment.py` was driven on real Redwood:

```
login → Me → My Client Groups → Show more quick actions →
Change Assignment → search "Kamaria" (type → role=option dropdown → Enter to select) →
Additional Assignment Info (Info Group combobox perceived)
```

This is the exact journey the *hardcoded* test file performs — but with zero
hardcoded locators. The same loop that handles Classic also handled Redwood. That
is the proof the action set is complete and the architecture works: **the thing
that took a bespoke 200-line test with fallback stacks was done by a generic loop.**

---

## The nine primitives (locked)

| Command            | What it does                                              |
|--------------------|----------------------------------------------------------|
| `click N`          | Click the element at index N                             |
| `type N text`      | Focus index N, type text (appends as-is)                 |
| `type N text Enter`| Type text into N, then press Enter (submit / fire LOV)   |
| `nav URL`          | Navigate to URL                                          |
| `press KEY`        | Press a key on the **currently focused** element (no index)|
| `wait`             | Pause ~3s, then loop re-perceives                        |
| `done`             | End the loop                                             |

Vision (`screenshot`) and explicit `read`/re-perceive are reserved for later phases;
the loop already re-perceives every iteration, so `read` is implicit.

### Resolver
`click(page, index)` resolves an index to a real element via
`page.locator('[data-ai-index="N"]')` — the stamp `perceive()` writes. No
text-matching, no ambiguity: an index points at exactly one stamped element.

---

## Decided rules (confirmed against the live runs)

1. **`press` takes no index; it acts on focus.** This surprised us, then proved
   correct: `press 15 Control+A` failed ("Unknown key: 15 Control"); `press Control+A`
   worked. The pattern is **two lines**: `type 15 madhavi` (focuses the field),
   then `press Enter` on the next line (focus persists). This is just how keyboard
   focus works, and it is reliable.

2. **Key names are capitalized.** `Enter`, `Escape`, `Tab`, `Backspace`,
   `Control+A/C/V`, `ArrowDown/Up/Left/Right`. `press enter` (lowercase) fails;
   `press Enter` works. Confirmed repeatedly on Oracle.

3. **Type replaces or appends — the decider chooses.** `type` appends by default.
   To replace, focus then `press Control+A` then type (clear-then-fill). The
   executor *offers* clearing; it does not force it. The AI decides per field
   (empty field → just type; pre-filled field → clear first). "Python knows how,
   AI decides which."

4. **Dropdowns/LOVs are handled by the re-perceive loop, not a special verb.**
   Typing a partial value makes options appear as `role="option"` elements, which
   perception already catches; the next iteration lists them, and you click one by
   index (or `press Enter` to take the top match). Seen live: typing "Kamaria"
   produced a dozen `role=option` results, `press Enter` selected the top one.

5. **Comboboxes open by typing or `ArrowDown`, never by hunting the visual arrow.**
   The decorative arrow is `role=generic`, unnamed, and correctly filtered out. The
   real control is the `role=combobox` input — operate it the keyboard way.

6. **Every action is crash-proof.** All actions run inside `try/except`; a bad
   command or a failed click prints the error and the loop continues. Unknown
   commands fall through to a help hint. The loop never dies on a single bad step.

---

## Edge cases hit and resolved (all on real Oracle)

- **Duplicate `data-ai-index` ("resolved to 2 elements").** Old stamps from the
  previous perceive lingered on stale elements. Fixed in `perceive()` by clearing
  ALL existing `data-ai-index` attributes before stamping fresh. Enforces the iron
  rule: *indices are valid only for the current snapshot.*

- **`type` "text not associated" bug.** `text` was only set on the Enter path.
  Fixed by always setting `text` first, then optionally stripping a trailing
  " Enter". (A reminder: a variable used after an `if` must be set on every path.)

- **Perceived too early on Redwood.** `domcontentloaded` fires before Redwood
  finishes rendering, so the list came back as the bare shell. A crude
  `wait_for_timeout(3000)` + the `wait` command mitigate it now; the proper settle
  gate (spinner / glass-pane / `oj-complete`) is a Phase 1 refinement for later.

- **Commands only exist if you write the `elif`.** Typing `wait` did nothing until
  the `wait` branch was added. The loop's vocabulary IS the set of branches you
  write — a core mental model for the whole tool.

---

## What "100%" means (established this phase)

A correct tool **perceives and acts on everything actionable** and **reports**
conditions it cannot act through — it does not invent data or bypass permissions.

The Info Group combobox on Additional Assignment Info was the test case: perception
saw it (after the `aria-labelledby` fix), it focused and opened (`aria-expanded:
true`), but the option list was **empty** — for this user, no Info Groups are
configured / permitted. Typing showed nothing; manually clicking the arrow showed
nothing. A human at that screen is equally stuck. That is **not** a tool failure —
it is a data/permissions condition the tool should flag, which is exactly what
regression testing is for. Forcing a pick would be the *wrong* behavior.

---

## Perception upgrade landed during Phase 2

While exercising actions we found and fixed a real, general perception gap:
Redwood controls that label themselves via **`aria-labelledby`** (the label text
lives in a separate `oj-label` element) were computing an empty name and being
dropped. Added a `getName()` helper that resolves `aria-labelledby` before falling
back to own text. The Info Group combobox immediately appeared as
`{role: combobox, name: "Info Group", id: "aai-lov|input"}`. This generalizes to a
whole class of Redwood inputs — a meaningful robustness gain, not a one-off.

---

## Known limitations carried forward (not blocking)

- **Settle gate is crude** (blind 3s wait). Replace with spinner/glass-pane/
  `oj-complete` waits when the AI driving makes timing failures costly. (Phase 1 refinement.)
- **Vision fallback not built.** When perception is genuinely thin (something is
  visible on screen but not in the list), a screenshot channel should let a vision
  model look. The empty-Info-Group page was the textbook trigger we noted. (Phase 8.)
- **Very large quick-action dumps (500+ elements)** perceive correctly but are long;
  the AI will filter rather than read them all. (Prompting concern for Phase 3, not a bug.)

---

## What Phase 2 unlocks

Both halves of the loop now work on real Oracle: perception sees the page (incl.
the hard Redwood controls), and the action layer acts on it crash-proof. The human
reads the list and types `click 79`. **Phase 3 replaces the human `input()` with a
call to the local LLM (qwen3:14b) that reads the same list and outputs the same
command.** The loop is unchanged; only the decider moves from human to model.