# BUILD BLUEPRINT — Reference While Coding

This is the "what am I building and how does it connect" doc. It pins down the
**data shapes** and the **seams** (the expensive-to-change stuff), suggests a
**starting file layout** (the cheap-to-change stuff — move things freely later),
and lists the **decided rules** so far.

Principle: design the data + seams up front; discover the exact files as you go.
Start in few files; split a file only when it clearly does two different jobs.

---

## 1. The four responsibilities (the seams)

These are WHAT the pieces do and how they hand off. Files can move; these roles don't.

```
  PERCEIVE  ──>  page becomes a numbered list of actionable elements
                 (+ full locator bundle per element)
       │
       ▼
   DECIDE    ──>  something picks the next action by index
                 (Phase 3: the LLM. For now: YOU, by hand.)
       │
       ▼
   EXECUTE   ──>  run one generic action against the page, safely
                 (settle-wait built in, screenshot on fail, guardrail check)
       │
       ▼
   OBSERVE   ──>  re-perceive → fresh list → loop
```

Iron rule that ties it together: **indices are only valid for the current snapshot.**
Always re-perceive → fresh indices → act → re-perceive. Never reuse old indices.

---

## 2. Data shapes (from Phase 0 — the spine)

The thing PERCEIVE produces (one element):

```
{
  index, tag, role, name, id, type, text,
  ariaLabel, placeholder, title, href,
  css, xpath, box:{x,y,width,height}
}
```
- `name` = accessible name chain: aria-label || title || placeholder || innerText
- each element is stamped in the DOM with data-ai-index = index

The thing DECIDE produces (one action) — examples:

```
{ "action": "navigate", "url": "https://..." }
{ "action": "click",    "index": 7 }
{ "action": "type",     "index": 3, "text": "RCSD BU" }
{ "action": "press",    "key": "Escape" }
{ "action": "done",     "reason": "Reached Manage Invoices" }
```

The things EXECUTE/replay consume later (from Phase 0): Step, Block, InstructionSet,
Run, ClientConfig. Not needed for the first build — perceive + execute come first.

---

## 3. The nine primitive actions (locked in 2.1)

| action     | params            | notes |
|------------|-------------------|-------|
| navigate   | url               | first step / jump to known page |
| click      | index             | the workhorse; by index, never by text |
| type       | index, text       | REPLACE by default (focus → Ctrl+A → type) |
| press      | key               | Enter / Tab / Escape (Escape closes stuck dialogs) |
| scroll     | direction, [amount]| RARE fallback only — see rule below |
| wait       | seconds           | manual override only; settle-wait is automatic |
| read       | —                 | re-perceive without acting ("look again") |
| screenshot | —                 | manual; also automatic on failure |
| done       | reason            | ends the loop |

Collapsed from old main.py: click_text + click_input → single `click` by index.
Not included yet (add only when first needed): `hover`.

---

## 4. Decided rules (reference these while building)

**Settle-wait is built into every action.** Each action runs the Oracle settle gate
BEFORE acting — automatically, invisibly. The agent never has to remember it.
Settle gate = networkidle + no visible progress dialog + no visible aria-busy="true"
+ main components carry `oj-complete`. Stacked on top of Playwright's own auto-wait
(visible/enabled/stable).

**Wait duration is configurable via env var.** The blunt `wait` action and the
settle-gate timeouts read a value from env/config (e.g. `AGENT_WAIT_SECONDS`,
default tunable to 2 / 3 / 5 / 10). Don't hard-code wait times.

**Scroll: lean on auto-scroll-into-view; `scroll` is a rare escape hatch.**
Playwright's click/fill auto-scroll the target into view, including Oracle inner-table
scrollers (`oj-table-scroller`). So most reaching-an-element needs NO scroll action.
Use `scroll` only for lazy-loaded content not yet in the DOM, and when used it scrolls
a SPECIFIC element (the scroller), not the window. (This was a real past failure:
page-scroll did nothing because the scrollable thing was an inner div.)

**Type = replace by default.** focus → Ctrl+A → type new value. Append-at-position is
fragile on Redwood (proven). To MODIFY an existing value (e.g. "add XX to name"):
read current value → combine in Python → replace whole field. Let code do the string
math, not the cursor. (Exception seen: the IP task could append at the end — rare.)
The AI doesn't need perfect cursor control; replace covers ~all cases.

**Dropdown-after-typing is handled by the loop, not a verb.** Type a few chars → LOV
dropdown appears → page changed → re-perceive → the options are now numbered elements
→ click the match by index. Prompt guidance (Phase 3): "after typing, prefer clicking
the matching dropdown option over typing the full value."

**Every action is crash-proof.** Wrap in try/except: on failure, auto-screenshot,
capture error text, return a structured {ok:false, error:...} — never throw and kill
the loop. Oracle is flaky by nature; the loop must survive a failed step.

**Guardrails checked before executing.** Compare the action/step `risk_level` against
client config flags: dry_run / allow_writes / allow_destructive. A `write` action in
dry-run is SKIPPED + logged, not performed. (Contains the known Save-button problem.)

**Table = summary + first 5 rows (configurable).** Don't dump 200 rows. Show a summary
line (columns + row count) + first N rows (default 5) each with a data-ai-index. If the
target row isn't in the sample, the agent FILTERS/searches the table first to bring it
to the top — it does not request all rows.

---

## 5. Suggested STARTING file layout (move freely later)

Start small. This is a suggestion, not a contract. Split a file when it visibly does
two jobs.

```
project/
  agent/
    perceive.py      # PERCEIVE: settle gate + element extraction + stamping
    actions.py       # EXECUTE: the nine primitives + index→handle resolver
    loop.py          # the perceive→decide→execute→observe driver
                     #   (Phase 3 plugs the LLM in here; for now, manual/hardcoded)
  config/
    <client>.yaml    # ClientConfig (Phase 0 shape) — secrets via env var names
  .env               # actual secrets + AGENT_WAIT_SECONDS etc.
  main.py            # entry point: load config, open browser, run loop
```

Likely reality: `perceive.py` and `actions.py` may START as ONE file
(e.g. `engine.py`) because they share the page object and the index handshake, and
split out once each is solid. That's expected and fine.

Reused from existing code:
- perception extraction logic  ← from ai_healer `_get_page_summary` (+ Phase 1 fixes)
- screenshot + SQLite logging   ← from Ui_Automation.py
- instance detection + persistent profile ← from Ui_Automation.py
- login page objects (3 variants) ← become login blocks later

---

## 6. The handshake to get right FIRST (the core of the first build)

The single most important mechanic. Build and prove this before anything else:

```
1. settle gate runs (page is "done")
2. perceive(page):
     - run extraction JS via page.evaluate(...)
     - JS stamps each kept element: el.setAttribute('data-ai-index', n)
     - returns the numbered list to Python
3. you (or later the LLM) pick an index, e.g. 7
4. execute click(7):
     - page.locator('[data-ai-index="7"]').click()
     - Playwright auto-waits + auto-scrolls-into-view
5. re-perceive  (old index 7 is now meaningless — fresh list)
```

If this round-trip works reliably on a real Oracle page, the project is real.
Everything else is built on top of it.

---

## 7. Build order from here

1. **perceive()** — port locked Phase-1 JS into Python; settle gate first; fixed
   accessible-name extraction; returns the ~42-element stamped list.
2. **click(index)** — the index→handle resolver. Prove the handshake (section 6).
3. Remaining primitives — type, navigate, press, wait, screenshot, done, scroll, read.
4. Crash-proofing + auto-screenshot wrapper around every action.
5. Guardrail check (dry_run etc.) before execute.
6. Table summary + 5-row sampling in perceive.
7. (Phase 3) Replace "you pick the index" with "the LLM picks the index."

Test against a real logged-in Oracle page at each step. No LLM until step 7.
```