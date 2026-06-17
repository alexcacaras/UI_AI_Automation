# Phase 1 — Perception Layer (Design Locked)

**Status: DESIGN COMPLETE** (spec locked from real Oracle DOM dumps; `perceive()` not yet built)

Phase 1 defines how the agent *sees* an Oracle Fusion / Redwood page: it turns a
live page into a short, numbered list of actionable elements the LLM can reason over,
each carrying a full locator bundle for later recording/replay.

Every decision below is backed by real console dumps from live RCSD instances
(DEV5 Home shell + TEST HCM person-search), not assumptions.

---

## The headline finding

On the **heaviest** Redwood page tested (HCM person-search results, full employee grid):

```
TOTAL elements: 2,690
ACTIONABLE + visible + named: 42
```

**A 98.4% reduction.** The agent never sees 2,690 nodes — it sees ~42, which is a
clean, readable list for a local 14B model. The ~1,800 repeating table cells vanish
because they are not actionable-and-named. This is the result that proves the whole
approach is viable on Oracle's worst screens.

---

## Key lessons from the real DOM

1. **Oracle is semantic.** IDs like `groupNode_tools`, `groupNode_payables`,
   `resultsTable:DisplayName` are stable and meaningful — NOT anonymous `div_9328`.
   This was the biggest risk to the approach; the page disproved it.

2. **Bare `oj-` is meaningless.** EVERY Redwood node carries an `oj-` class (even
   `<html>` and `<meta>`). Filtering on `oj-` matched 2,185 elements — it's noise,
   not signal. Only *specific* suffixes matter: `oj-dialog`, `oj-popup`, `oj-table`,
   `oj-progress-dialog`, `oj-button`, `oj-complete`.

3. **Heavy pages are dominated by repeating data rows.** The noise isn't `svg`/`img`
   chrome — it's hundreds of identical `oj-table-data-cell` / `oj-listview-item`
   rows. A results table with 200 employees = thousands of near-identical nodes.

4. **Most dialogs are pre-rendered but hidden.** A single page had many
   `role="dialog"` nodes (#85, #162, #190, all the `pill-*-popup` filter dialogs,
   manage-columns dialog) — almost all closed/hidden. "Flag dialogs" must mean
   "open AND visible dialogs," which is why the visibility check is load-bearing,
   not polish.

---

## LOCKED: the perception filter

Keep an element only if ALL three are true:

1. **Visible** — `display !== none`, `visibility !== hidden`, and bounding rect
   has width > 0 and height > 0.
2. **Actionable role** — one of: `a, button, input, select, textarea,
   [role=button], [role=link], [role=tab], [role=textbox], [role=combobox],
   [role=menuitem], [role=checkbox], [role=option]`.
3. **Has a usable name** — non-empty result of
   `aria-label || title || placeholder || innerText` (trimmed).

This single filter took 2,690 → 42. **No viewport restriction needed** — the filter
alone gets the list small enough, so we capture all matching elements regardless of
scroll position. (Resolves the earlier "viewport vs everything" open question:
everything-that-passes-the-filter.)

---

## LOCKED: per-element signature (the locator bundle)

For each kept element, capture:

```
index        # sequential number shown to the LLM
tag          # lowercase tag name
role         # aria/explicit role
name         # accessible name: aria-label || title || placeholder || innerText (FIX vs old code)
id           # element id (often semantic in Oracle)
type         # input type
text         # visible/rendered text
ariaLabel
placeholder
title
href
css          # ranked locator: short css path
xpath        # ranked locator: last-resort xpath
box          # {x, y, width, height} screen position
```

**Text-extraction fix:** the heavy dump missed visible labels like "Joyce Westbay"
because old code read `textContent` at the node. Use the rendered accessible-name
chain (`aria-label || title || placeholder || innerText`) — that's what produced 42
correctly-named elements in the count test.

---

## LOCKED: index → handle stamp

As each element is enumerated, stamp it:

```js
el.setAttribute("data-ai-index", String(n));
```

The LLM returns `{ "action": "click", "index": 7 }`; the executor clicks
`[data-ai-index="7"]`. Lossless, zero text-matching ambiguity.

**Iron rule:** indices are valid ONLY for the current snapshot. Redwood re-renders
constantly. Never act on indices from a previous perceive. Always:
**re-perceive → fresh indices → act → re-perceive.**

---

## LOCKED: settle gate (run BEFORE every perceive)

Oracle must be "done" before we read it, or we perceive a half-rendered page.
Ingredients identified from the dump:

1. `page.wait_for_load_state("networkidle")`
2. No **visible** progress dialog (`oj-sp-message-progress-dialog` /
   `oj-c-dialog ... progress` becomes visible during save/load).
3. No **visible** element with `aria-busy="true"` (Oracle flips this during load;
   seen as `aria-busy="false"` when idle).
4. Main content components carry `oj-complete` (Redwood stamps this when a component
   finishes initializing).

Exact selectors tuned at build time; these are the confirmed signals.

---

## LOCKED: rank & trim for the prompt

Capture all that pass the filter, but order what the LLM sees:

1. **Open, visible dialogs float to the TOP.** If a modal is blocking, the agent must
   deal with it first (e.g. click `Done`) before anything else. Do NOT suppress
   modals — surface them. (Hidden/closed dialogs are excluded by the visibility
   filter anyway.)
2. **Collapse big repeating tables to a SUMMARY + SAMPLE**, not N individual rows.
   A table perceives as: a summary line (`[table] resultsTable — columns: Name,
   Business Title, Person Number, Assignment Status…, 200 rows`) followed by the
   **first 5 rows** as a sample, each with its key cell text and its own
   `data-ai-index` so the agent can click a sampled row. Five is enough for the model
   to understand the table's shape and to act when the target is near the top.
   **Sample size is a config value (default 5), not hard-coded** — tune once we see
   model behavior.
   - **When the target row is NOT in the sample:** the agent's correct move is to
     *filter/search the table first* (e.g. type into the search box), which brings
     the target into the top rows — NOT to dump all 200 rows. This mirrors how a
     human uses the page (nobody scrolls 200 rows). Bake this guidance into the
     table handler and prompt.
3. Everything else in document order.

---

## Phase 1 checklist

| Step | Status |
|---|---|
| 1.1 See reality (real Oracle dumps) | DONE — twice (Home shell + HCM grid) |
| 1.2 Element signature defined | DONE — bundle locked, text-extraction fix noted |
| 1.3 Index + `data-ai-index` stamp | DONE — proven in console |
| 1.4 Settle gate spec | DONE — signals identified (networkidle + no visible progress dialog + no visible aria-busy + oj-complete) |
| 1.5 Rank & trim rules | DONE — dialogs-first, collapse tables, filter does the heavy lift |

---

## Next: build `perceive()` (first real code)

Port the locked console JS into a Python function on a real Playwright page:
- runs the settle gate first
- returns the structured ~42-element list with `data-ai-index` stamped and the
  fixed accessible-name extraction
- run it from a logged-in script against a real page and confirm the list matches
  what a human sees

This becomes the perception core of the new `main.py` engine (Phase 3 loop later
consumes it).