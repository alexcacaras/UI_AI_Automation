
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

                // 7. last resort: the element's own visible text
                if (!name) name = el.innerText || '';

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

            // column index -> header text, built at most once per grid per perceive
            const hdrCache = {};
            function headerFor(gridEl, column) {
                const key = gridEl.id || 'grid';
                if (!hdrCache[key]) {
                    const map = {};
                    gridEl.querySelectorAll('.oj-datagrid-column-header-cell').forEach(h => {
                        try {
                            const c = gridEl.getContextByNode(h);
                            if (!c) return;
                            const idx = (c.index !== undefined) ? c.index
                                      : (c.indexes ? c.indexes.column : undefined);
                            if (idx === undefined) return;
                            const t = (h.innerText || '').trim().replace(/\\s+/g, ' ');
                            if (t) map[idx] = t.slice(0, 40);
                        } catch (e) {}
                    });
                    hdrCache[key] = map;
                }
                return hdrCache[key][column] || '';
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
                if (g) {
                    // The column index is ALWAYS included. Time card headers are
                    // multi-level (a date row above a "Quantity" row) and we only
                    // reach the inner level — so all 14 day columns come back named
                    // "Quantity". Without the index, 14 cells per row share a name
                    // and find_by_name picks whichever comes first.
                    // The date is deliberately NOT used: it drifts every pay period,
                    // while row/column do not. A human-readable label belongs in its
                    // own field later (Phase 6 healer), never in the matched name.
                    const hdr = headerFor(g.gridEl, g.column);
                    const base = 'row ' + (g.row + 1) + ', ';
                    name = hdr ? (base + hdr + ' (col ' + g.column + ')')
                               : (base + 'col ' + g.column);
                } else {
                    name = getName(el);
                    if (!name) {
                        const tag = el.tagName.toLowerCase();
                        const role = el.getAttribute('role') || '';
                        if (tag === 'input' || tag === 'textarea' || role === 'textbox' || role === 'combobox') {
                            name = 'text field';
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
                if (g) {
                    // durable identity for a cell — replay resolves on these,
                    // never on the throwaway ui-id
                    item.grid = g.grid;
                    item.row = g.row;
                    item.column = g.column;
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



    




        