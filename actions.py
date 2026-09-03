
#The actions file helper functions
#=============================================
#---------------helper actions---------------
#=============================================
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

#=============================================
#------------------helpers--------------------
#=============================================

def did_change(before, after):
    before_sig = {(el["id"], el["name"]) for el in before}
    after_sig  = {(el["id"], el["name"]) for el in after}
    if before_sig == after_sig:
        return "no change"
    else:
        return "changed"
    
def search_element(elements, target):
    for el in elements:
        if el["index"] == target:
            return el
    return None

def find_by_id(elements, target_id):
    for el in elements:
        if el["id"] == target_id:
            return el
    return None

def find_by_name(elements, target_name, target_tag):
    for el in elements:
        if el["name"] == target_name and el["tag"] == target_tag:
            return el
    return None

def find_by_grid(elements, grid, row, column):
    """Resolve an Oracle data-grid cell by {grid, row, column}.

    The tightest locator available for a grid cell — there is no durable id
    (ui-id-N renumbers every session) and names collide across day columns.
    perceive puts these three fields on every cell it stamps.
    """
    for el in elements:
        if el.get("grid") == grid and el.get("row") == row and el.get("column") == column:
            return el
    return None

def scroll_grid_h(page, grid, amount):
    """Scroll a data grid's day columns sideways, or reset to the far left.

    The grid is virtualized (scroll-policy="auto"): columns that are off-screen
    do NOT exist in the DOM, and how many are rendered depends on window width.
    So a missing column may just mean "not scrolled there yet".

    Note getElementById, not querySelector — the id contains a colon
    ("timecard-datagrid:databody"), which is a CSS selector operator.
    """
    return page.evaluate("""
        ([grid, amount]) => {
            const body = document.getElementById(grid + ':databody');
            if (!body) return false;
            if (amount === 'reset') { body.scrollLeft = 0; }
            else { body.scrollBy(amount, 0); }
            return true;
        }
    """, [grid, amount])

#=============================================
#---------------do helper actions-------------
#=============================================

def identity(el):
    """The durable fields of a perceived element, for recording into a step.

    Oracle JET data-grid cells (time card) have NO usable id: theirs is a
    jQuery counter (ui-id-138) that renumbers every session. Their real
    identity is {grid, row, column}, which perceive reads from the JET
    component. We BLANK the id for those, because replay prefers id whenever
    one is present — recording a known-bad id makes replay fail confidently
    instead of falling through to the grid fields.
    """
    step = {"id": el["id"], "name": el["name"], "role": el["role"], "tag": el["tag"]}
    if "grid" in el:
        step["id"] = ""
        step["grid"] = el["grid"]
        step["row"] = el["row"]
        step["column"] = el["column"]
    return step


def do_click(page, index, elements):
    click(page, index)
    el = search_element(elements, index)
    pending_step = {"action": "click", **identity(el)}
    return pending_step

def wait_for_lov_options(page, timeout=10000, step=400):
    """Wait until an open Oracle search-select dropdown has options with REAL text.

    A fixed sleep races the query: options can exist with EMPTY text while still
    rendering, and Enter then commits nothing. Proven the hard way in grid_probe.
    """
    waited = 0
    while waited < timeout:
        ready = page.evaluate("""
            () => [...document.querySelectorAll('.oj-listview-cell-element')]
                    .some(o => o.getBoundingClientRect().height > 0 &&
                               (o.innerText || '').trim() !== '')
        """)
        if ready:
            return True
        page.wait_for_timeout(step)
        waited += step
    return False


def do_type_python(page, index, text, press_enter, elements):
    el = search_element(elements, index)
    loc = page.locator(f'[data-ai-index="{index}"]')
    is_grid = bool(el) and "grid" in el

    if is_grid:
        # A data-grid cell needs a trusted CLICK to reach mode='edit'; focus()
        # alone leaves it in 'navigation' and the keystrokes go nowhere.
        # And a search-select cell fires an async query PER KEYSTROKE — typing at
        # full speed leaves it stuck on a stale "No matches found", so pace it.
        loc.click()
        page.wait_for_timeout(500)
        page.keyboard.type(text, delay=120)
    else:
        loc.focus()
        page.keyboard.type(text)

    if press_enter:
        if is_grid:
            wait_for_lov_options(page)     # don't press Enter into an empty list
        page.keyboard.press("Enter")

    pending_step = {"action": "type", **identity(el), "value": text, "enter": press_enter}
    return pending_step

def do_type_live(page, index, elements):
    # capture keystrokes the user types into the focused field
    page.evaluate("""
        window.capturedText = '';
        window._captureHandler = (e) => {
            if (e.key === 'Backspace') { window.capturedText = window.capturedText.slice(0,-1); }
            else if (e.key === 'CapsLock') { window._sealed = true; }
            else if (e.key.length === 1) { window.capturedText += e.key; }
        };
        window._sealed = false;
        document.addEventListener('keydown', window._captureHandler);
    """)
    page.locator(f'[data-ai-index="{index}"]').click()   # open/focus the field
    page.wait_for_function("window._sealed === true", timeout=0)   # wait for CapsLock seal
    text = page.evaluate("window.capturedText")
    page.evaluate("document.removeEventListener('keydown', window._captureHandler)")
    el = search_element(elements, index)
    pending_step = {"action": "type", **identity(el), "value": text, "enter": False}
    return pending_step


def scroll(page, target, amount):
    if target == 'page':
        page.evaluate("(amount) => window.scrollBy(0, amount)", amount)
    elif target == 'table':
        page.evaluate("""
            (amount) => {
            const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
            let el = document.elementFromPoint(cx, cy);
            while (el && !(el.scrollHeight > el.clientHeight + 5 &&
            ['auto','scroll'].includes(getComputedStyle(el).overflowY))) {
            el = el.parentElement;
            }
            if (el) { el.scrollBy(0, amount); }
            }
        """, amount)
    elif target == 'navigator':
        page.evaluate("""
            (amount) => {
            const el = document.querySelector('[id*="_UISnvr"][id*="nv_pgl"]');
            if (el && el.scrollHeight > el.clientHeight + 5) {
                el.scrollBy(0, amount);
            } else {
                const nav = document.querySelector('[id*="_UISnvr"]');
                if (nav) {
                    const scroller = [...nav.querySelectorAll('*')].find(e =>
                        e.scrollHeight > e.clientHeight + 5 &&
                        ['auto','scroll'].includes(getComputedStyle(e).overflowY));
                    if (scroller) scroller.scrollBy(0, amount);
                }
            }
            }
        """, amount)
    else:
        print(f"unknown scroll target: {target}")

def select_option_forgiving(page, index, value):
    locator = page.locator(f'[data-ai-index="{index}"]')
    try:
        locator.select_option(label=value)          # exact match first
    except Exception:
        # fall back: case-insensitive match against the option texts
        options = locator.evaluate("""el =>
            [...el.options].map(o => o.text.trim())
        """)
        match = next((o for o in options if o.lower() == value.strip().lower()), None)
        if match is None:
            raise Exception(f"no option matching '{value}' (options: {options})")
        locator.select_option(label=match)