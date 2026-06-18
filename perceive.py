from playwright.sync_api import sync_playwright
from ollama_test import ask_llm

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
def click(page, index):
    locator = page.locator(f'[data-ai-index="{index}"]')
    tag = locator.evaluate("el => el.tagName.toLowerCase()")
    if tag in ("input", "textarea", "select"):
        locator.focus()      # inputs: focus dodges the hint-overlay intercept
    else:
        locator.click()

def fill_by_name(page, name, value):
    try:
        
        loc = page.get_by_role("combobox", name=name)
        if loc.count() == 0:
            loc = page.get_by_role("textbox", name=name)
        if loc.count() == 0:
            print(f"no field named '{name}' found")
            return
        loc = loc.first              
        loc.focus()
        loc.press("ControlOrMeta+a")
        loc.fill(value)
        page.wait_for_timeout(1000)
        loc.press("Enter")
        print(f"filled '{name}' = '{value}'")
    except Exception as e:
        print(f"fill failed: {e}")


def run_loop(page):
     done = False
     while not done:
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=13000)
        except:
            pass    # some Oracle pages never fully idle — don't hang, just proceed
        elements = []
        for attempt in range(5):
            page.wait_for_timeout(2000)
            try:
                elements = perceive(page)
            except Exception as e:
                print(f"perceive failed, retrying {e}")
                page.wait_for_timeout(1000)
                continue
            if len(elements) > 6:
                break
            print(f"page looks empty ({len(elements)} elements), waiting...")
        print("\n--- PAGE NOW ---")
        for el in elements:
            print(el)
        cmd = input("\naction? (click N / type N text / nav URL / press N / wait / fill / done):").strip()
        #goal = "Navigate to My Client Groups and search for an employee"
        #ai_cmd = ask_llm(elements, goal).strip()
        #print(f"\n AI wants to:{ai_cmd}")
        #cmd = input("Press Enter to run it, or type your own command to override: ").strip()
        #if cmd == "":
            #cmd = ai_cmd
        try:
            if cmd == "done":
                done = True
            elif cmd.startswith("click "):
                index = int(cmd.split()[1])
                click(page, index)
            elif cmd.startswith("type "):
                parts = cmd.split(maxsplit=2)
                index = int(parts[1])
                text = parts[2]
                press_enter = text.endswith(" Enter")
                if press_enter:
                    text = text[:-6]
                page.locator(f'[data-ai-index="{index}"]').focus()   # focus, not click
                page.keyboard.type(text)
                if press_enter:
                    page.keyboard.press("Enter")
            elif cmd.startswith("fill "):
                rest = cmd.split(maxsplit=1)[1]                       
                if "|" not in rest:
                    print("usage: fill <field name> | <value>")
                else:
                    name, value = rest.split("|", 1)
                    fill_by_name(page, name.strip().strip('\'"'), value.strip().strip('\'"'))
            elif cmd.startswith("nav "):
                url = cmd.split(maxsplit=1)[1]
                page.goto(url)
            elif cmd.startswith("press "):
                parts = cmd.split()
                key = parts[1]
                count = int(parts[2]) if len(parts) > 2 else 1   
                for _ in range(count):
                    page.keyboard.press(key)
            elif cmd == "wait":
                page.wait_for_timeout(3000)
            else:
                print("didnt understand that - try: click 9 / type 9 hello / nav http://... / press Enter / wait / fill / done")
        except Exception as e:
            print(f"action failed {e}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    page = browser.new_page(no_viewport=True)
    page.goto("https://fa-euum-test-saasfaprod1.fa.ocs.oraclecloud.com")
    input("Log in manually in the browser, then press Enter here to let the AI take over...")
    
    run_loop(page)

    input("press enter to close")
    browser.close()



    




        