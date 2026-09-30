"""Exercise perceive() headless against a fixture - no browser login, ~2 seconds.

phase1.md asks for exactly this check, and says why: BOTH perceive bugs in that
doc shipped because the change was verified by READING rather than RUNNING. One
was a backslash inside the JS (Python ate it before the browser saw it, and
Python's own syntax check passes happily); the other was a selector that simply
never matched.

    py perceive_probe.py
"""
from playwright.sync_api import sync_playwright

from perceive import perceive, perceive_readable

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

<!-- read-only text: the step 5 channel. None of these may get an index. -->
<div id="x:t1::emptyTxt" role="cell">No results found.</div>
<div aria-live="polite"><span>2 items selected</span></div>
<div role="alert">Enter a value.</div>
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.set_content(HTML)

    els = perceive(pg)
    print(f"{len(els)} actionable elements (JS parsed OK)\n")
    for e in els:
        extra = ""
        if "value" in e:
            extra += f"  value={e['value']!r}"
        if "checked" in e:
            extra += f"  checked={e['checked']}"
        print(f"  {e['index']:>2} <{e['tag']}> {e['name']!r:<24} id={e['id']!r:<10}{extra}")

    read = perceive_readable(pg)
    print(f"\n{len(read)} readable messages (separate channel, no index):")
    for r in read:
        print(f"     {r['text']!r:<26} role={r['role']!r:<8} live={r['live']!r:<8} id={r['id']!r}")

    # THE INVARIANT THIS FILE EXISTS TO PROTECT: the two channels must not mix.
    # A readable message in the actionable list would get matched by resolve()
    # and then clicked by index - an index it does not have.
    names = {e["name"] for e in els}
    leaked = [r["text"] for r in read if r["text"] in names]
    print(f"\nreadable text leaked into the actionable list: {leaked or 'none'}")
    b.close()
