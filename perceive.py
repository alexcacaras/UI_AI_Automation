
#perceive fileS
def perceive(page):
        elements = page.evaluate("""
        () => {
            const ACTIONABLE = 'a,button,input,select,textarea,[role="button"],[role="link"],[role="tab"],[role="textbox"],[role="combobox"],[role="menuitem"],[role="checkbox"],[role="option"],div[id*="groupNode"],div[id*="nvgpgl"]';

            function isVisible(el) {
                const s = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
            }

            function getName(el) {
                // 1. direct attributes
                let name = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || '';

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

            document.querySelectorAll('[data-ai-index]').forEach(el => el.removeAttribute('data-ai-index'));

            const items = [];
            let n = 0;
            document.querySelectorAll(ACTIONABLE).forEach(el => {
                if (!isVisible(el)) return;
                if (!isClickable(el)) return; 
                const name = getName(el);
                if (!name) return;

                n = n + 1;
                el.setAttribute('data-ai-index', String(n));

                items.push({
                    index: n,
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    name: name.slice(0, 100),
                    id: el.id || ''
                });
            });
            return items;
        }
    """)
        return elements



    




        