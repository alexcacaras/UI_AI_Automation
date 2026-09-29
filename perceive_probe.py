from playwright.sync_api import sync_playwright
from perceive import perceive

HTML = """
<label for="nm">Last Name</label><input id="nm" value="Smith">
<input id="empty" aria-label="Empty Field" value="">
<input id="cb" type="checkbox" aria-label="Active" checked>
<input id="cb2" type="checkbox" aria-label="Locked">
<div id="ojcb" role="checkbox" aria-checked="true" aria-label="Oracle Style Box">x</div>
<button id="go">Search</button>
<a href="#" id="lnk">My Client Groups</a>
<select id="sel" aria-label="Purpose"><option>Sold to</option><option>Bill to</option></select>
<textarea id="ta" aria-label="Notes">a long note here</textarea>
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.set_content(HTML)
    els = perceive(pg)
    print(f"{len(els)} elements perceived (JS parsed OK)\n")
    for e in els:
        extra = ""
        if "value" in e:
            extra += f"  value={e['value']!r}"
        if "checked" in e:
            extra += f"  checked={e['checked']}"
        print(f"  {e['index']:>2} <{e['tag']}> {e['name']!r:<24} id={e['id']!r:<8}{extra}")
    b.close()
