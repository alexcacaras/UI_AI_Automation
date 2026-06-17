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
                // direct label sources first
                let name = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || '';
                // aria-labelledby: the label text lives in ANOTHER element, referenced by id
                if (!name) {
                    const labelledBy = el.getAttribute('aria-labelledby');
                    if (labelledBy) {
                        const labelEl = document.getElementById(labelledBy);
                        if (labelEl) name = labelEl.innerText || labelEl.textContent || '';
                    }
                }
                // fall back to the element's own visible text
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
    page.locator(f'[data-ai-index="{index}"]').click()

def run_loop(page):
     done = False
     while not done:
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
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
        cmd = input("\naction? (click N / type N text / nav URL / press N / wait / done):").strip()
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
                text = parts[2]                      # always set text first
                press_enter = text.endswith(" Enter")
                if press_enter:
                    text = text[:-6]                 # strip the trailing " Enter"
                click(page, index)
                page.keyboard.type(text)
                if press_enter:
                    page.keyboard.press("Enter")
            elif cmd.startswith("nav "):
                url = cmd.split(maxsplit=1)[1]
                page.goto(url)
            elif cmd.startswith("press "):
                key = cmd.split(maxsplit=1)[1]
                page.keyboard.press(key)
            elif cmd == "wait":
                page.wait_for_timeout(3000)
            else:
                print("didnt understand that - try: click 9 / type 9 hello / nav http://... / press Enter / wait / done")
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



    




        