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
