
#perceive fileS
def perceive(page):
        elements = page.evaluate("""
        () => {
            const ACTIONABLE = 'a,button,input,select,textarea,[role="button"],[role="link"],[role="tab"],[role="textbox"],[role="combobox"],[role="menuitem"],[role="checkbox"],[role="option"],div[id*="groupNode"],div[id*="nvgpgl"],li.FndSearchSuggestLIItem,.oj-datagrid-cell';

            function isVisible(el) {
                const s = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
            }

            function getName(el) {
                // 1. direct attributes
                let name = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || '';


                // 1.5 icon buttons: the action name lives on a child <img>'s alt/title
                if (!name) {
                    const img = el.querySelector('img');
                    if (img) name = img.getAttribute('alt') || img.getAttribute('title') || '';
                }

                // 2. aria-labelledby: label text lives in another element, referenced by id
                if (!name) {
                    const labelledBy = el.getAttribute('aria-labelledby');
                    if (labelledBy) {
                        const labelEl = document.getElementById(labelledBy);
                        if (labelEl) name = labelEl.innerText || labelEl.textContent || '';
                    }
                }

                // 3. STANDARD HTML: <label for="thisId"> — the universal mechanism
                if (!name && el.id) {
                    const forLabel = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                    if (forLabel) name = forLabel.innerText || forLabel.textContent || '';
                }

                // 4. STANDARD HTML: an enclosing <label> ancestor wrapping the input
                if (!name) {
                    const wrapLabel = el.closest('label');
                    if (wrapLabel) name = wrapLabel.innerText || wrapLabel.textContent || '';
                }

                // 5. Oracle oj- fallback: input id ends "|input", label/hint ends "|hint" or "|label"
                if (!name && el.id && el.id.endsWith('|input')) {
                    const base = el.id.slice(0, -6);
                    const hintEl = document.getElementById(base + '|hint') || document.getElementById(base + '|label');
                    if (hintEl) name = hintEl.innerText || hintEl.textContent || '';
                }

                // 6. PROXIMITY (last resort): unlabeled input -> label/text directly above it.
                //    Oracle drawer comboboxes link their label to the OPEN filter-input, leaving the
                //    collapsed input nameless. Only cue is the label sitting just above the box.
                if (!name) {
                    const r = el.getBoundingClientRect();
                    let best = null, bestGap = 60;
                    document.querySelectorAll('label, span').forEach(cand => {
                        const t = (cand.innerText || cand.textContent || '').trim();
                        if (!t || t.length > 40 || cand.children.length > 0) return;
                        const cr = cand.getBoundingClientRect();
                        const above = r.top - cr.bottom;
                        const alignedX = Math.abs(cr.left - r.left) < 40;
                        if (above >= 0 && above < bestGap && alignedX) {
                            best = t; bestGap = above;
                        }
                    });
                    if (best) name = best;
                }

                // 7. last resort: the element's own visible text.
                // NOT for <select>: its innerText is every <option> concatenated
                // ("Acknowledgments" + "Bill to" + "Bills of lading" + ...), one
                // per line — the element's CONTENTS, not its name. Steps then carry a
                // 60-line "name" that no name+tag lookup can ever match and that
                // buries the healer's prompt in noise (see test9 / test10).
                // Only <select> is excluded — an <li role="option"> still gets its
                // name from innerText, which is how Oracle's own dropdown options
                // (BCPC_TRUSTEES and friends) are found.
                if (!name && el.tagName.toLowerCase() === 'select') {
                    // A real label was already tried above. Fall back to the HTML
                    // name attribute, never to the selected option — the selected
                    // option is STATE, and recording state as identity is the bug
                    // that made a category step call itself "DEFAULT".
                    name = el.getAttribute('name') || '';
                } else if (!name) {
                    name = el.innerText || '';
                }

                return name.trim();
            }
                                 
            function isClickable(el) {
                // form fields are reliably interactable even if their own label/hint
                // overlaps the center point — don't over-filter them
                const tag = el.tagName.toLowerCase();
                if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;

                const r = el.getBoundingClientRect();
                const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                if (!top) return false;
                return el === top || el.contains(top) || top.contains(el);
            }

            // ---- ORACLE JET DATA GRID (time card etc.) ----------------------
            // Grid cells carry NO durable id: their ids are a jQuery counter
            // (ui-id-138) that renumbers every session. The only real identity
            // is {grid, row, column}, which the JET component hands us.
            // Only the cell ITSELF gets grid identity — descendants (the
            // search-select input that appears in edit mode) keep normal naming.
            function gridInfo(el) {
                if (!el.classList.contains('oj-datagrid-cell')) return null;
                const gridEl = el.closest('oj-data-grid');
                if (!gridEl || !gridEl.getContextByNode) return null;
                try {
                    const ctx = gridEl.getContextByNode(el);
                    if (!ctx || !ctx.indexes) return null;
                    return { gridEl: gridEl, grid: gridEl.id || '',
                             row: ctx.indexes.row, column: ctx.indexes.column };
                } catch (e) { return null; }
            }

            // column index -> {name, date}, built at most once per grid per perceive.
            //
            // TIME CARD HEADERS ARE THREE LEVELS DEEP, measured in DevTools on a
            // real card rather than assumed:
            //
            //   index | level 0                   | level 1          | level 2
            //   ------|---------------------------|------------------|----------
            //     0   | 09/27/2026 - 10/10/2026   | Scheduled Hours  | Assignment
            //     1   |                           |                  | Time Type
            //     9   | Sunday, September 27      | 10               | Quantity
            //    22   | Saturday, October 10      | 10               | Quantity
            //
            // The old version kept whichever cell it saw LAST, which is level 2 -
            // which is why all fourteen day columns come back called "Quantity"
            // and need the column index to tell them apart.
            //
            // Now both are kept. The DEEPEST level is the name (the actual field),
            // level 0 is the date. Level 1 is scheduled hours - real data that
            // changes between runs, so it is deliberately dropped.
            //
            // Written generically, not for the time card: deepest = name, level 0
            // = date, and a grid with only one header level simply has no date.
            // Column 0's level 0 is the PAY PERIOD itself, which falls out of the
            // same rule for free and is what outcome verification wants to assert.
            const hdrCache = {};
            function headerInfo(gridEl, column) {
                const key = gridEl.id || 'grid';
                if (!hdrCache[key]) {
                    const byLevel = {};        // idx -> {level: text}
                    gridEl.querySelectorAll('.oj-datagrid-column-header-cell').forEach(h => {
                        try {
                            const c = gridEl.getContextByNode(h);
                            if (!c) return;
                            const idx = (c.index !== undefined) ? c.index
                                      : (c.indexes ? c.indexes.column : undefined);
                            if (idx === undefined) return;
                            const lvl = (c.level !== undefined) ? c.level : 0;
                            const t = (h.innerText || '').trim().replace(/\\s+/g, ' ');
                            if (!t) return;
                            if (!byLevel[idx]) byLevel[idx] = {};
                            byLevel[idx][lvl] = t.slice(0, 40);
                        } catch (e) {}
                    });
                    const map = {};
                    Object.keys(byLevel).forEach(idx => {
                        const levels = Object.keys(byLevel[idx])
                                             .map(Number).sort((a, b) => a - b);
                        const deepest = levels[levels.length - 1];
                        map[idx] = {
                            name: byLevel[idx][deepest],
                            // only a date if there IS an outer level; on a
                            // single-level grid level 0 is the name itself and
                            // repeating it as a date would be a lie
                            date: (levels.length > 1) ? byLevel[idx][levels[0]] : ''
                        };
                    });
                    hdrCache[key] = map;
                }
                return hdrCache[key][column] || { name: '', date: '' };
            }

            document.querySelectorAll('[data-ai-index]').forEach(el => el.removeAttribute('data-ai-index'));
            document.querySelectorAll('[data-ai-name]').forEach(el => el.removeAttribute('data-ai-name'));
            document.querySelectorAll('[data-ai-grid]').forEach(el => {
                ['data-ai-grid', 'data-ai-row', 'data-ai-col']
                    .forEach(a => el.removeAttribute(a));
            });

            const items = [];
            let n = 0;
            document.querySelectorAll(ACTIONABLE).forEach(el => {
                if (!isVisible(el)) return;
                if (!isClickable(el)) return;

                // Grid cells short-circuit BEFORE getName. Two reasons:
                // 1. a cell has no label of its own — its meaning is its position
                // 2. getName's proximity fallback scans the whole document per
                //    element; ~100 cells would make that scan run ~100x a perceive
                const g = gridInfo(el);
                let name;
                let gridDate = '';      // the cell's column date, if the grid has one
                if (g) {
                    // The column index is ALWAYS included. Time card headers are
                    // multi-level (a date row above a "Quantity" row) and we only
                    // reach the inner level — so all 14 day columns come back named
                    // "Quantity". Without the index, 14 cells per row share a name
                    // and find_by_name picks whichever comes first.
                    // The date is deliberately NOT used: it drifts every pay period,
                    // while row/column do not. A human-readable label belongs in its
                    // own field later (Phase 6 healer), never in the matched name.
                    const hdr = headerInfo(g.gridEl, g.column);
                    gridDate = hdr.date;
                    const base = 'row ' + (g.row + 1) + ', ';
                    name = hdr.name ? (base + hdr.name + ' (col ' + g.column + ')')
                                    : (base + 'col ' + g.column);
                } else {
                    name = getName(el);
                    if (!name) {
                        const tag = el.tagName.toLowerCase();
                        const role = el.getAttribute('role') || '';
                        if (tag === 'input' || tag === 'textarea' || role === 'textbox' || role === 'combobox') {
                            name = 'text field';
                        } else if (tag === 'select') {
                            // A <select> with no label and no name attribute. It
                            // USED to fall back to its own innerText, which named
                            // it after every option it contains — useless as a
                            // locator. Now that that is gone it would drop out of
                            // the list entirely, and an element that is not in the
                            // list never gets a data-ai-index, so it cannot be
                            // clicked at all. A placeholder keeps it reachable,
                            // exactly like 'text field' above; its id is what
                            // resolve() will actually match on.
                            name = 'dropdown';
                        } else {
                            return;
                        }
                    }
                }

                n = n + 1;
                el.setAttribute('data-ai-index', String(n));
                // Stamp the name so overlay.elementInfo can READ it instead of
                // recomputing. getName has 7 naming tiers to elementInfo's 3, so
                // recomputing there can yield a DIFFERENT string for the same
                // element — and record/replay then disagree on any id-less one.
                // One implementation makes invariant #1 structural, not a rule.
                el.setAttribute('data-ai-name', name);

                const item = {
                    index: n,
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    name: name.slice(0, 100),
                    id: el.id || ''
                };

                // STATE, not identity. NOTHING matches on these fields - not
                // resolve(), not did_change(), not fingerprint(), and
                // actions.identity() copies a fixed field list into a recorded
                // step so a value can never leak into a recording. They are
                // captured now so a later check can ask the question perceive
                // has never been able to answer: did that type actually land?
                // A field holding "Smith" has always fingerprinted identically
                // to an empty one - a blind sensor, not a quiet application.
                //
                // 'value' in el rather than a tag whitelist: Redwood comboboxes
                // are <input>, but so are a dozen other things, and asking the
                // element whether it HAS a value is more honest than
                // maintaining a list of tags that do.
                //
                // aria-checked BEFORE .checked: Oracle ticks plenty of divs
                // with role="checkbox" that have no .checked property at all,
                // and reading only .checked would report false for a box that
                // is visibly ticked. A silent wrong answer is worse than none.
                const t = (el.getAttribute('type') || '').toLowerCase();
                if (t === 'checkbox' || t === 'radio' ||
                    el.getAttribute('role') === 'checkbox') {
                    const aria = el.getAttribute('aria-checked');
                    item.checked = (aria !== null) ? (aria === 'true') : !!el.checked;
                } else if ('value' in el && typeof el.value === 'string') {
                    // A <button> also has .value, and it is almost always the
                    // empty string - so a bare "does it have a value" test
                    // stamps value='' onto every button on the page. Noise
                    // today, and noise inside the fingerprint later.
                    //
                    // But an EMPTY form field must still be reported: "this box
                    // is empty" is precisely what level 1 needs to see change
                    // when a type lands. So form fields are always captured,
                    // empty or not, and everything else only when it actually
                    // holds something. Found with the headless fixture, not
                    // guessed at.
                    const tg = el.tagName.toLowerCase();
                    const isField = (tg === 'input' || tg === 'textarea' || tg === 'select');
                    if (isField || el.value !== '') {
                        // sliced like name: a textarea holding a paragraph
                        // would otherwise bloat every element list
                        item.value = el.value.slice(0, 100);
                    }
                }

                if (g) {
                    // durable identity for a cell — replay resolves on these,
                    // never on the throwaway ui-id
                    item.grid = g.grid;
                    item.row = g.row;
                    item.column = g.column;
                    // The column's DATE, kept deliberately OUT of `name`.
                    // resolve() matches on name, so folding the date in would
                    // break test1.json and every other grid recording - and
                    // phase5.md is right that the date drifts every pay period
                    // while row/column do not. Identity stays positional; this
                    // rides alongside it, which is the "human-readable label,
                    // separate from name" already parked in phase5.md.
                    if (gridDate) item.col_date = gridDate;

                    // THE CELL'S CONTENT. A grid cell is a <div>, so it has no
                    // .value property and the state branch above skips it
                    // entirely - which meant a time card typed from 10 to 8
                    // still looked completely unchanged to perceive. Found by
                    // running it on a real card; the headless fixture has no
                    // grid and could never have shown it.
                    //
                    // Always set, even when empty: an empty cell becoming "8"
                    // is exactly the signal, same reasoning as form fields.
                    // This is CONTENT, not identity - `name` stays positional
                    // (row/column), so resolve(), find_by_grid and every
                    // existing recording are untouched.
                    item.value = (el.innerText || '').trim()
                                     .replace(/\\s+/g, ' ').slice(0, 100);
                    // Stamp it on the element too, so overlay.elementInfo can READ
                    // this answer instead of recomputing it. Invariant #1: one
                    // implementation means perceive and overlay cannot drift apart.
                    el.setAttribute('data-ai-grid', g.grid);
                    el.setAttribute('data-ai-row', String(g.row));
                    el.setAttribute('data-ai-col', String(g.column));
                }
                items.push(item);
            });
            return items;
        }
    """)
        return elements


def perceive_readable(page):
    """What the page SAYS about itself - text you cannot click or type into.

    WHY THIS IS A SEPARATE FUNCTION AND NOT MORE OF `ACTIONABLE`
        perceive() stamps data-ai-index as it goes, and everything downstream
        addresses elements by that index. A status message is not clickable, so
        it must never get one - but if it sat in the same list, resolve() could
        still match it on name+tag and replay would then do
        click(page, el["index"]) on an element that has no index. A step that
        works today would start raising KeyError. Separate channel, separate
        list: indices, overlay badges, resolve() and the healer prompt are all
        exactly as they were.

    WHAT IT EXISTS FOR
        `test_broken` step 7 searches Manage Journals and gets nothing back.
        The click WORKED, the query ran, it returned an empty set - and the
        fingerprint was identical either way, so "the action did nothing" and
        "the action did something that produced nothing" were the same picture.
        Oracle was saying "No results found." on screen the whole time.

    THE SELECTOR IS NARROW ON PURPOSE, and every entry was measured in DevTools
    rather than guessed (phase1.md: bare oj- matched 2,185 elements and meant
    nothing):
      - role=status / role=alert   the standard ARIA "I am announcing
                                   something" roles
      - aria-live                  what the page itself marks as an
                                   announcement. "No results found." sits in a
                                   polite live region, which is the most
                                   honest signal available: the application
                                   labelled it, we did not infer it.
      - id ending emptyTxt         the ADF empty-table message. Observed as
                                   ..._ATp:t1::emptyTxt on Manage Journals; the
                                   suffix is an ADF convention, not a one-off.
      - oj-messages / summary      Redwood's message boxes.

    Short text only. A live region can wrap a large container, and collecting a
    whole page of prose would swamp the fingerprint with something that is not
    a status at all.
    """
    return page.evaluate("""
        () => {
            const READABLE = '[role="status"],[role="alert"],[aria-live="polite"],'
                           + '[aria-live="assertive"],[id$="emptyTxt"],'
                           + '.oj-messages,.oj-message-summary';

            function isVisible(el) {
                const s = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return s.display !== 'none' && s.visibility !== 'hidden' &&
                       r.width > 0 && r.height > 0;
            }

            const seen = new Set();
            const out = [];
            document.querySelectorAll(READABLE).forEach(el => {
                if (!isVisible(el)) return;
                const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                // 200 chars: a status message is a sentence. Anything longer is
                // a container that happens to be live, not an announcement.
                if (!text || text.length > 200) return;
                // A live region often wraps the very element it announces, so
                // the same sentence arrives twice. Key on both so a page CAN
                // legitimately say the same thing in two places.
                const key = (el.id || '') + '|' + text;
                if (seen.has(key)) return;
                seen.add(key);
                out.push({
                    text: text,
                    id: el.id || '',
                    role: el.getAttribute('role') || '',
                    live: el.getAttribute('aria-live') ||
                          (el.closest('[aria-live]')
                             ? el.closest('[aria-live]').getAttribute('aria-live') : '')
                });
            });
            return out;
        }
    """)



    




        