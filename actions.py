
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

#=============================================
#---------------do helper actions-------------
#=============================================

def do_click(page, index, elements):
    click(page, index)
    el = search_element(elements, index)
    pending_step = {"action": "click", "id": el["id"], "name": el["name"], "role": el["role"], "tag": el["tag"]}
    return pending_step

def do_type_python(page, index, text, press_enter, elements):
    page.locator(f'[data-ai-index="{index}"]').focus()
    page.keyboard.type(text)
    if press_enter:
        page.keyboard.press("Enter")
    el = search_element(elements, index)
    pending_step = {"action": "type", "id": el["id"], "name": el["name"], "role": el["role"], "tag": el["tag"], "value": text, "enter": press_enter}
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
    pending_step = {"action": "type", "id": el["id"], "name": el["name"], "role": el["role"], "tag": el["tag"], "value": text, "enter": False}
    return pending_step