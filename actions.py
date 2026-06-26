
#The actions file helper functions

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