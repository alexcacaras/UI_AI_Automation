"""Phase 6 — outcome verification, STEP 1: record a structural baseline.

WHY THIS EXISTS
    `run passed` means every step FOUND an element. It does not mean the action
    did anything, or that the flow ended where it was supposed to. A bulk job
    resolved every step, reported green, and changed nothing — ORACLE caught it,
    by disabling its own Save button. The application knew the task had not
    happened. The tool did not.

    So we need a machine-readable picture of what the pages looked like on a run
    that was known good. This file builds that picture and stores it. Comparing
    two pictures is deliberately NOT here yet: the tolerances have to be written
    after looking at real captures of real recordings, not guessed at first.

WHAT A FINGERPRINT IS, AND WHY IT IS (id, name) PAIRS
    The same signature `actions.did_change` uses — and for the same reason
    (invariant #5). Split ids and names into two separate sets and every element
    WITHOUT an id collapses into a single entry, so a page full of id-less
    elements looks unchanged no matter what happens to it. The pair keeps them
    distinct. Reusing the existing signature also means level 1 ("did the action
    do anything?") is the check the codebase already has, applied in a new place,
    rather than a second definition of "changed" that can drift from the first.

STRUCTURE, NEVER PIXELS
    Oracle pages legitimately differ run to run on employee names, timestamps and
    row counts, so a screenshot diff would fail on all of them and prove nothing.
    Element identity is the stable part.

    One thing is filtered on purpose: a grid cell's `ui-id-N`. That is a jQuery
    counter that renumbers every session (invariant #12), so it would differ on
    every single run and bury any real change in noise. The cell's NAME
    ("row 1, Quantity (col 9)") is positional and stable, so the pair keeps the
    name and drops the id.

WHAT IT CANNOT SEE YET — read this before trusting a capture
    perceive returns index/tag/role/name/id and nothing else. No value, no
    checked, no disabled. So a text field with "Smith" in it fingerprints
    IDENTICALLY to an empty one, and a successful `type` looks like a no-op.
    That is a blind sensor, not a quiet application, and it is why the first
    comparison work is offline analysis rather than a live alarm.

PRIVACY
    Element names include real employee names and person numbers, exactly like
    the recordings do. Baselines live UNDER recordings/, which is gitignored, so
    they inherit that protection instead of needing a second decision.
"""
import json
import os
import re
import shutil
import time

RECORDINGS = "recordings"
BASELINES = os.path.join(RECORDINGS, "baselines")

# 1 = [id, name] pairs.
# 2 = [id, name, count] triples.
# 3 = [id, name, state, count] quads - state is the element's CONTENTS.
FORMAT = 3

# The jQuery counter. Not an identity — a sequence number that restarts.
_THROWAWAY_ID = re.compile(r"^ui-id-\d+$")

# A perceived data-grid cell, recognised by the name perceive gives it:
# "row 1, Quantity (col 9)" or "row 1, col 9". Parsing a name is normally a
# smell, but perceive OWNS this format (it builds it in one place), so the two
# cannot drift the way a guess about someone else's markup would.
_CELL_NAME = re.compile(r"^row \d+, .*col \d+")


def _is_cell(el):
    """True for a perceived Oracle JET data-grid cell.

    Detected by the PRESENCE of the key, not its truthiness: row 0 and column 0
    are real positions, and `el.get("row")` reads both of those as missing.
    """
    return "row" in el


def fingerprint(elements):
    """Reduce one perceive() result to the part that should be stable.

    Returns sorted [id, name, count] triples.

    NOT the perceive order: perceive walks the DOM, so a re-render that moves a
    button changes the order without changing what is on the page. Sorted on the
    way out so two captures of the same page are byte-identical and a human diff
    of the file is readable.

    WHY THE COUNT, and not just presence
        A Redwood Navigator page perceives 126 elements that collapse to 28
        distinct (id, name) pairs — roughly 78% of what was on screen is a
        duplicate of something else, mostly id-less elements sharing a name.
        As a plain set, an action that adds a FOURTH copy of something already
        there three times changes nothing, and level 1 would call it a no-op.

        Row counts do legitimately vary between runs, so the comparison may well
        end up ignoring this number on some steps. That is the point: storing it
        lets the comparison decide. A field that was never captured cannot be
        reconsidered later.
    """
    counts = {}
    for el in elements:
        name = (el.get("name") or "").strip()
        el_id = (el.get("id") or "").strip()
        if _is_cell(el) or _THROWAWAY_ID.match(el_id):
            el_id = ""          # keep the cell, drop its throwaway id
        key = (el_id, name, _state(el))
        counts[key] = counts.get(key, 0) + 1
    # JSON has no tuples: lists round-trip and stay readable.
    return sorted([i, n, s, c] for (i, n, s), c in counts.items())


def _state(el):
    """An element's CONTENTS, as a short string. '' when it has none.

    FORMAT 3. perceive used to report only what an element WAS, never what it
    HELD, so a field containing "Smith" fingerprinted identically to an empty
    one and a successful type looked exactly like a no-op. That was a blind
    sensor, not a quiet application, and it is why `type` was exempt from the
    level 1 warning and why AI mode retyped fields it had already filled.

    Kept as one short string rather than separate fields because it goes in the
    KEY: an element whose contents changed is a different entry, so level 1's
    existing "did anything move?" question answers itself with no new logic.

    The [x] / [ ] shape rather than True/False so a human reading the JSON can
    see at a glance which boxes were ticked.
    """
    if "checked" in el:
        return "[x]" if el["checked"] else "[ ]"
    if "value" in el:
        return "=" + str(el["value"])
    return ""


# Date shapes that appear in Oracle element names. Kept deliberately narrow —
# anything vaguer starts blurring real differences.
#   08/26/2026, 8/26/26, 26-08-2026   (both orders; the recording convention is
#                                      dd/mm/yy, invariant #9, but pages render
#                                      mm/dd/yyyy)
#   2026-09-09                        (ISO)
#   Oct-26, Dec-2026                  (Oracle accounting period)
_DATE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b\d{4}-\d{1,2}-\d{1,2}\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s]\d{2,4}\b"
)


def _undate(name):
    """'Date Range 08/26/2026 - 09/09/2026' -> 'Date Range <date> - <date>'."""
    return _DATE.sub("<date>", name)


def _as_counts(rows, ignore_dates=False, ignore_values=False):
    """[[id, name, state, count], ...] -> {(id, name, state): count}.

    With ignore_dates, names AND states are compared with their dates blanked,
    so a page whose rolling window advanced overnight still matches itself.
    State too, not just name: invariant #9 says dates are TYPED, so a date
    drifts inside a field's value exactly as it does inside a column header.

    With ignore_values, state is dropped entirely - see compare().
    """
    counts = {}
    for row in rows:
        # Tolerate a format-2 triple. replay refuses a stale baseline before it
        # ever reaches here, but compare() is also called on fresh captures from
        # two different code paths, and silently reading a count as a state
        # would be the kind of wrong that looks like data.
        if len(row) == 4:
            i, n, s, c = row
        else:
            i, n, c = row
            s = ""
        if ignore_values:
            s = ""
        elif ignore_dates:
            s = _undate(s)
        key = (i, _undate(n) if ignore_dates else n, s)
        counts[key] = counts.get(key, 0) + c
    return counts


def compare(before, after, ignore_dates=False, ignore_values=False):
    """Difference between two fingerprints, in both directions.

    IGNORE_VALUES IS OPT-IN FOR THE SAME REASON IGNORE_DATES IS
        An element's CONTENTS mean opposite things in the two comparisons:
          - within a run (level 1), a value changing is the whole point. It is
            the evidence the type landed - the thing perceive was blind to
            until FORMAT 3, and the reason `type` was exempt from the warning.
          - across runs (level 2), contents legitimately differ every time. A
            time card holds different hours, a results page different people.
            Compare them and every run alarms, which is precisely the daily
            false alarm ignore_dates exists to stop.
        Level 2 passes True; level 1 must not. Level 3 does not use this path
        at all - it reads the stored states directly, which is why they are
        kept in the file rather than normalised away at capture time.

    IGNORE_DATES IS OPT-IN, AND MUST STAY THAT WAY
        A date changing means OPPOSITE things in the two comparisons:
          - across runs (level 2), the rolling window advanced overnight and
            `Date Range 08/25/2026 - 09/08/2026` became `08/26 - 09/09`. Drift,
            and a daily false alarm if it is not ignored.
          - within a run (level 1), the dates moved BECAUSE the step worked -
            clicking "next pay period" changes little else on a time card. Blur
            them there and a working step reports as a silent no-op.
        Same data, opposite meaning, so the caller decides rather than the
        function. Level 2 passes True; level 1 must not.

        Note this only affects MATCHING. Real dates stay in the stored file, so
        level 3 ("did the right pay period load?") can still read them back and
        check them properly. Normalising at capture time would delete them.

    ONE function for two questions, deliberately:
      - level 1, within a run: before = the page a step started on, after = the
        page the next step started on. Nothing different means the step did
        nothing perceivable.
      - level 2, across runs: before = the known-good capture of step N, after =
        this run's capture of step N. Different means the flow is somewhere the
        good run never went.
    Two definitions of "different" would eventually disagree, and then a step
    could be a no-op by one measure and fine by the other.

    `recount` is separate from added/removed on purpose: the same elements in
    different quantities (a table gaining a row) is a much weaker signal than
    elements appearing or vanishing, and row counts legitimately vary between
    runs. Keeping them apart lets a caller weigh them differently.
    """
    a = _as_counts(before, ignore_dates, ignore_values)
    b = _as_counts(after, ignore_dates, ignore_values)
    added = sorted(k for k in b if k not in a)
    removed = sorted(k for k in a if k not in b)
    recount = sorted((k, a[k], b[k]) for k in a if k in b and a[k] != b[k])
    union = len(set(a) | set(b))

    # STRUCTURE vs DATA. On a results page the ids are structure and the names
    # are data: a journal row is an <a> whose name is its inner text, so it
    # perceives as "Record $39,151 RBC Loan ..." and legitimately differs every
    # time the data does. Overlap on ids alone says "same page, different rows";
    # overlap on the full pair says "same page, same rows". A caller comparing
    # two RUNS needs both to tell data churn from a wrong page.
    #
    # None, not 100, when neither side has a single id — an Oracle page can be
    # almost entirely id-less, and inventing a perfect score for "no evidence"
    # is how a check quietly stops checking.
    ids_a = {i for i, _, _ in a if i}
    ids_b = {i for i, _, _ in b if i}
    id_union = len(ids_a | ids_b)

    # `renamed` is what DATA CHURN actually looks like: the same id carrying a
    # different name. An ADF row cell (AP1:t1:0:cl2) whose text is an employee
    # name or a journal description is the same element showing different data.
    by_id_a = {i: n for i, n, _ in a if i}
    by_id_b = {i: n for i, n, _ in b if i}
    renamed = sorted((i, by_id_a[i], by_id_b[i])
                     for i in set(by_id_a) & set(by_id_b)
                     if by_id_a[i] != by_id_b[i])

    # REVALUED: the same element holding something different. FORMAT 3's whole
    # point, and the direct parallel to `renamed` - that one is "the same id
    # showing different text", this one is "the same control holding different
    # contents". A field going from empty to "Smith", a checkbox being ticked,
    # a time card cell going 10 -> 8.
    #
    # Sets rather than single values because an (id, name) pair can appear more
    # than once on a page - fourteen empty Quantity cells share a name - so the
    # honest answer is "these states were present before, those after".
    #
    # Note `same` does NOT need to consider this: state is part of the key, so
    # anything revalued already shows up as one added plus one removed. This
    # exists to make the REPORT readable, not to detect the change.
    states_a, states_b = {}, {}
    for i, n, s in a:
        states_a.setdefault((i, n), set()).add(s)
    for i, n, s in b:
        states_b.setdefault((i, n), set()).add(s)
    revalued = sorted(
        (i, n, sorted(states_a[(i, n)]), sorted(states_b[(i, n)]))
        for (i, n) in set(states_a) & set(states_b)
        if states_a[(i, n)] != states_b[(i, n)]
    )

    # Differences among elements with NO id are the ones nothing can explain.
    # This was learned the hard way: two different Oracle Time Management pages
    # scored 100% on id overlap, because every element that DISTINGUISHED them
    # ("Attestations", "Time Card Status") was id-less, while all the shared
    # chrome carried the ids. A caller must not read a high id_overlap as
    # "structure is fine" while this number is non-zero — the identified
    # elements agreeing says nothing about the ones that were never identified.
    # GRID CELLS ARE NOT ANONYMOUS, and counting them as such made the warning
    # claim the opposite of the truth. A cell has no id because fingerprint
    # DROPS its ui-id on purpose (a jQuery counter, invariant #12) - its real
    # identity is {grid, row, column}, which is exactly what its name encodes.
    #
    # It matters because a grid is VIRTUALIZED: only the columns scrolled into
    # view exist in the DOM, and how many that is depends on window width
    # (phase5.md - one run rendered columns 0-18, a wider window 0-22). So a
    # whole column coming and going between two runs is the window changing,
    # not the flow going somewhere else. Observed on test1: two runs a human
    # watched and confirmed identical differed by all five cells of col 18,
    # and the message said "this could be a different page".
    cells = (sum(1 for _, n, _ in added if _CELL_NAME.match(n))
             + sum(1 for _, n, _ in removed if _CELL_NAME.match(n)))
    anonymous = (sum(1 for i, n, _ in added if not i and not _CELL_NAME.match(n))
                 + sum(1 for i, n, _ in removed if not i and not _CELL_NAME.match(n)))

    return {
        "added": added,
        "removed": removed,
        "recount": recount,
        "renamed": renamed,
        "revalued": revalued,
        "anonymous": anonymous,
        "cells": cells,
        "overlap": (100.0 * len(set(a) & set(b)) / union) if union else 100.0,
        "id_overlap": (100.0 * len(ids_a & ids_b) / id_union) if id_union else None,
        "same": not (added or removed or recount),
    }


def describe_change(before, after):
    """What changed between two perceives, in words. For AI mode's history.

    WHY THIS REPLACED A BOOLEAN
        `actions.did_change` answered "changed" or "no change" from (id, name)
        alone. So a successful type - the element list identical, only the
        field's contents different - came back "no change", and AI mode's
        history recorded a working action as a failed one. phase3.md says that
        history exists so the model stops repeating what did not work, so the
        model was being told to retype a field it had just filled correctly.
        The blind sensor and the misleading history were one bug.

    STRUCTURE vs CONTENTS, told apart the same way level 1 and level 2 are:
    compare twice, once seeing values and once ignoring them. If the run with
    values sees a difference and the run without does not, then the page is the
    same page and something on it now holds something else - which is a
    completely different situation from having navigated somewhere new, and the
    old boolean could not distinguish them.
    """
    fa, fb = fingerprint(before), fingerprint(after)
    full = compare(fa, fb)
    if full["same"]:
        return "no change"

    structure = compare(fa, fb, ignore_values=True)
    if structure["same"]:
        if full["revalued"]:
            _, name, was, now = full["revalued"][0]
            more = (f" (+{len(full['revalued']) - 1} more)"
                    if len(full["revalued"]) > 1 else "")
            return (f"changed: {name[:40]!r} now {'/'.join(now)}, "
                    f"was {'/'.join(was)}{more}")
        return "changed: contents"
    return (f"changed: page (+{len(structure['added'])} elements, "
            f"-{len(structure['removed'])})")


def observe(elements, step=None, step_index=None):
    """One captured page state, labelled enough to read the file without counting.

    The step fields are for a HUMAN opening the baseline — nothing compares on
    them. `step` is None for the final capture, which belongs to no step.
    """
    return {
        "step_index": step_index,
        "action": step.get("action", "") if step else "(final state)",
        "step_name": (step.get("name") or step.get("value") or "") if step else "",
        # Whether this step acted on an Oracle data-grid cell. Recorded because
        # a CLICK on a cell only flips it to edit mode - same id, same name, no
        # new elements - so level 1 calls it a no-op on every single grid run.
        # loop.py already bypasses its recording gate for exactly this reason
        # (invariant #7's sibling); replay had no way to know.
        "is_grid": bool(step.get("grid")) if step else False,
        # LEVEL 3. What this step ASKED FOR, kept beside what the page ended up
        # holding. The recording knows the intent and the capture knows the
        # result; storing both in one file is what lets "did the value I asked
        # for actually land?" be answered offline, not just live.
        "typed": (step.get("value", "") or "")
                 if step and step.get("action") == "type" else "",
        "count": len(elements),
        "elements": fingerprint(elements),
    }


def path_for(name):
    """The BLESSED baseline — the known-good run everything is compared against."""
    return os.path.join(BASELINES, f"{name}.json")


def last_run_path(name):
    """The most recent capture, blessed or not. Overwritten every run."""
    return os.path.join(BASELINES, f"{name}.last-run.json")


def exists(name):
    return os.path.exists(path_for(name))


def _write(path, name, states, goal):
    os.makedirs(BASELINES, exist_ok=True)
    data = {
        # A stale capture must be DETECTABLE, not silently misread. Format 1 was
        # [id, name] pairs; format 2 is [id, name, count] triples, and a
        # comparison handed the wrong one would read the count as absent rather
        # than as a different shape. Bump this whenever the triple changes.
        "format": FORMAT,
        "recording": name,
        "goal": goal,
        "captured": time.strftime("%Y-%m-%d %H:%M:%S"),
        "states": states,
    }
    text = json.dumps(data, indent=2)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)      # atomic: a crash can never leave half a file
    return path


def save_last_run(name, states, goal=""):
    """Record what THIS run saw, always, whether or not it is trusted.

    Separate from the blessed baseline on purpose. The blessed one must not be
    overwritten by a pass that nothing verified, but a run that leaves no trace
    is a run that can never be compared to anything — and comparing two captures
    of the same recording is the only way to find out which fields are actually
    stable. This file is the second sample, at the cost of one write.
    """
    return _write(last_run_path(name), name, states, goal)


def save(name, states, goal=""):
    """Write the blessed baseline for a recording.

    Any existing one is kept as `<name>.previous.json` rather than dropped. That
    only fires once a verified run is allowed to REFRESH the baseline (it can't
    yet — first capture wins), and it is here so the first refresh is never the
    moment a known-good picture gets lost.

    No rotation beyond that, unlike writeback's backups: a baseline is an
    OBSERVATION and can be regenerated by re-running a known-good flow. The
    recording cannot be re-derived, which is why that one is backed up properly
    and this one is not.
    """
    path = path_for(name)
    if os.path.exists(path):
        os.makedirs(BASELINES, exist_ok=True)
        shutil.copy2(path, os.path.join(BASELINES, f"{name}.previous.json"))
    return _write(path, name, states, goal)


def load(name):
    """The stored baseline, or None if this recording has never had a good run."""
    try:
        with open(path_for(name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
