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

# 1 = [id, name] pairs. 2 = [id, name, count] triples.
FORMAT = 2

# The jQuery counter. Not an identity — a sequence number that restarts.
_THROWAWAY_ID = re.compile(r"^ui-id-\d+$")


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
        key = (el_id, name)
        counts[key] = counts.get(key, 0) + 1
    # JSON has no tuples: lists round-trip and stay readable.
    return sorted([i, n, c] for (i, n), c in counts.items())


def _as_counts(triples):
    """[[id, name, count], ...] -> {(id, name): count}."""
    return {(i, n): c for i, n, c in triples}


def compare(before, after):
    """Difference between two fingerprints, in both directions.

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
    a, b = _as_counts(before), _as_counts(after)
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
    ids_a = {i for i, _ in a if i}
    ids_b = {i for i, _ in b if i}
    id_union = len(ids_a | ids_b)

    # `renamed` is what DATA CHURN actually looks like: the same id carrying a
    # different name. An ADF row cell (AP1:t1:0:cl2) whose text is an employee
    # name or a journal description is the same element showing different data.
    by_id_a = {i: n for i, n in a if i}
    by_id_b = {i: n for i, n in b if i}
    renamed = sorted((i, by_id_a[i], by_id_b[i])
                     for i in set(by_id_a) & set(by_id_b)
                     if by_id_a[i] != by_id_b[i])

    # Differences among elements with NO id are the ones nothing can explain.
    # This was learned the hard way: two different Oracle Time Management pages
    # scored 100% on id overlap, because every element that DISTINGUISHED them
    # ("Attestations", "Time Card Status") was id-less, while all the shared
    # chrome carried the ids. A caller must not read a high id_overlap as
    # "structure is fine" while this number is non-zero — the identified
    # elements agreeing says nothing about the ones that were never identified.
    anonymous = sum(1 for i, _ in added if not i) + sum(1 for i, _ in removed if not i)

    return {
        "added": added,
        "removed": removed,
        "recount": recount,
        "renamed": renamed,
        "anonymous": anonymous,
        "overlap": (100.0 * len(set(a) & set(b)) / union) if union else 100.0,
        "id_overlap": (100.0 * len(ids_a & ids_b) / id_union) if id_union else None,
        "same": not (added or removed or recount),
    }


def observe(elements, step=None, step_index=None):
    """One captured page state, labelled enough to read the file without counting.

    The step fields are for a HUMAN opening the baseline — nothing compares on
    them. `step` is None for the final capture, which belongs to no step.
    """
    return {
        "step_index": step_index,
        "action": step.get("action", "") if step else "(final state)",
        "step_name": (step.get("name") or step.get("value") or "") if step else "",
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
