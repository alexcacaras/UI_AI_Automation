
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

def find_by_position(elements, row, column):
    """Resolve a grid cell by {row, column} alone, when the GRID's id changed.

    find_by_grid matches grid AND row AND column, so renaming the grid element
    loses a cell whose position is still perfectly intact. The position is the
    identity (invariant #12) — the grid's own id is just where it lives.

    Returns (element_or_None, match_count). More than one match means several
    grids on the page share the position, which is not identity any more, so
    the caller falls through rather than guessing.

    This exists because the Phase 6 healer was asked to do it and could not.
    Handed a step with row=0 col=9 and ~250 elements, gemma answered
    "row 2, col 22" and wrote a confident rationalisation for it. That is an
    exact numeric lookup across near-identical lines — dictionary work, not
    language work. Doing it here also keeps it off the LLM path entirely.
    """
    if row is None or column is None:
        return None, 0
    matches = [e for e in elements
               if e.get("grid") and e.get("row") == row and e.get("column") == column]
    return (matches[0] if len(matches) == 1 else None), len(matches)


def resolve(elements, step):
    """Find the element a recorded step means, trying locators TIGHT to LOOSE.

    Returns (element_or_None, rank) where rank says HOW it matched. replay logs
    that, so a locator degrading from 'id' to 'name+tag' is visible BEFORE the
    day it fails outright.

        1  grid           {grid, row, column}   unique by construction
        2  grid-position  {row, column}         grid renamed, cell didn't move
        3  id             exact id
        4  name+tag       EXACTLY ONE candidate
        5  name+tag       first of several — a guess, logged loudly

    Falling through is the whole point: today a step with an id that no longer
    exists (ui-id-N renumbers every session) fails outright, even when its name
    would have found it. This can only find MORE than before — a step that
    resolves on rank 1 or 2 never reaches the lower ranks.

    Rank 4 is where the two "Search" magnifiers live. Today find_by_name silently
    returns the first of them; here the guess is at least reported. If rank 4
    starts showing up in real runs, that is the evidence for adding a scope_id
    rank rather than guessing at one now.
    """
    if step.get("grid"):
        el = find_by_grid(elements, step["grid"], step.get("row"), step.get("column"))
        if el is not None:
            return el, "grid"

        # The grid element was renamed but the cell's position is unchanged.
        # Deterministic, so it belongs here and not in the healer.
        el, count = find_by_position(elements, step.get("row"), step.get("column"))
        if el is not None:
            return el, "grid-position"
        if count > 1:
            print(f"   {count} grids share row={step.get('row')} "
                  f"col={step.get('column')} — position is not unique here")

    if step.get("id"):
        el = find_by_id(elements, step["id"])
        if el is not None:
            return el, "id"

    name = step.get("name", "")
    tag = step.get("tag", "")
    if name:
        matches = [e for e in elements if e["name"] == name and e["tag"] == tag]
        if len(matches) == 1:
            return matches[0], "name+tag"
        if len(matches) > 1:
            return matches[0], f"GUESS name+tag ({len(matches)} candidates)"

    return None, "no match"


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
    elif target == 'grid':
        # HORIZONTAL — the only sideways scroller. Oracle data grids (time card)
        # scroll their day columns in <grid>:databody; the frozen columns
        # (Assignment, Time Type) sit in a separate scroller and don't move.
        # Positive = right, negative = left.
        # Needed at RECORD time: the grid is virtualized, so off-screen columns
        # aren't in the DOM and get no badge until you scroll to them. Replay
        # scrolls on its own (see find_by_grid), but the recorder can't.
        moved = page.evaluate("""
            (amount) => {
                const g = document.querySelector('oj-data-grid');
                if (!g || !g.id) return false;
                const body = document.getElementById(g.id + ':databody');
                if (!body) return false;
                body.scrollBy(amount, 0);
                return true;
            }
        """, amount)
        if not moved:
            print("no oj-data-grid on this page")
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