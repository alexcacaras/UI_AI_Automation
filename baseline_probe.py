import baseline as b

# a time card cell going 10 -> 8, plus an untouched neighbour
before = [{"id": "", "name": "row 1, Quantity (col 9)", "row": 0, "value": "10"},
          {"id": "", "name": "row 1, Quantity (col 10)", "row": 0, "value": "10"},
          {"id": "sv", "name": "Save", "value": ""}]
after  = [{"id": "", "name": "row 1, Quantity (col 9)", "row": 0, "value": "8"},
          {"id": "", "name": "row 1, Quantity (col 10)", "row": 0, "value": "10"},
          {"id": "sv", "name": "Save", "value": ""}]

print("FORMAT =", b.FORMAT)
print("fingerprint:", b.fingerprint(before))

d = b.compare(b.fingerprint(before), b.fingerprint(after))
print("\nLEVEL 1 (sees values):")
print("   same     =", d["same"], "   <- False means level 1 now catches the type")
print("   revalued =", d["revalued"])

d2 = b.compare(b.fingerprint(before), b.fingerprint(after), ignore_values=True)
print("\nLEVEL 2 (ignore_values=True):")
print("   same     =", d2["same"], "   <- True means no false alarm across runs")

# checkbox
cb_a = [{"id": "act", "name": "Active", "checked": False}]
cb_b = [{"id": "act", "name": "Active", "checked": True}]
d3 = b.compare(b.fingerprint(cb_a), b.fingerprint(cb_b))
print("\nCHECKBOX ticked: same =", d3["same"], " revalued =", d3["revalued"])

# a typed DATE drifting across runs must still be ignorable
dt_a = [{"id": "d", "name": "Date", "value": "09/27/2026"}]
dt_b = [{"id": "d", "name": "Date", "value": "09/28/2026"}]
print("\nTYPED DATE drift, ignore_dates=True: same =",
      b.compare(b.fingerprint(dt_a), b.fingerprint(dt_b), ignore_dates=True)["same"])

# a format-2 capture must not be misread as states
print("\nformat-2 triple tolerated:",
      b.compare([["x", "y", 1]], [["x", "y", 1]])["same"])

# ---------------------------------------------------------------------------
# LEVEL 3 - did the value the step asked for actually land?
# ---------------------------------------------------------------------------
from replay import _check_value_landed          # noqa: E402

typed = {"action": "type", "name": "Time Type", "value": "regula"}
before = b.observe([], typed, 3)


def after(els):
    return b.observe(els, typed, 4)


cases = [
    ("exact match",
     after([{"id": "c", "name": "row 1, Time Type", "value": "regula"}]), False),
    # Oracle's search-select resolves a partial - phase5.md says typing partially
    # and letting the LOV settle is the DESIGNED behaviour, so equality would
    # fail every search-select in the project.
    ("resolved to 'Regular'",
     after([{"id": "c", "name": "row 1, Time Type", "value": "Regular"}]), False),
    # Measured on test1: the final capture caught the cell mid-edit, so the CELL
    # read empty while the input INSIDE it held the value. Pinning the check to
    # one element would fail a run that worked.
    ("landed on the inner input",
     after([{"id": "c", "name": "row 1, Time Type", "value": ""},
            {"id": "inp", "name": "Time Type", "value": "regula"}]), False),
    # Type a name into a search and it comes back as a result ROW, whose NAME is
    # that text. "Is it on the page" has to include that.
    ("appeared as a name",
     after([{"id": "r1", "name": "Regular hours row"}]), False),
    ("never appeared",
     after([{"id": "c", "name": "row 1, Time Type", "value": ""}]), True),
]

print("\nLEVEL 3 (True = warned):")
for label, state, expect in cases:
    got = _check_value_landed(before, state)
    print(f"   {label:<28} {got}   {'ok' if got == expect else 'UNEXPECTED'}")

not_a_type = b.observe([], {"action": "click", "name": "Save"}, 1)
print(f"   {'non-type step skipped':<28} "
      f"{_check_value_landed(not_a_type, after([]))}   ok")
