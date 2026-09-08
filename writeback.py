"""Phase 6 Tier 2 — write repaired locators back into a recording.

WHY
    A step that resolves on a LOOSER locator than rank 1 is still passing, but it
    is passing by fallback: the tight locator lost the element and something
    weaker found it. Every future run pays that fallback again, and a healed step
    pays a model call every single run. Writing the repair back makes the next run
    match on rank 1 — deterministic, instant, free. This is what makes a recording
    learn instead of decay.

WHEN IT WRITES — end of a PASSING run, from a buffer. Never at resolve time.
    A repair is a claim that the new locator points at the element the step meant.
    At resolve time there is no evidence for that claim; the evidence is the rest
    of the run continuing to work on the page this step landed on. The asymmetry
    is the argument: buffering and losing a repair to a later failure costs one
    run (the next run re-degrades, or re-heals, and offers the repair again),
    while writing early and being wrong costs the RECORDING, permanently.

    Caveat worth remembering: replay verifies an element was FOUND, never that the
    action DID anything, so "the run passed" is the best evidence available rather
    than proof. That is why the backup below is part of the feature.

WHAT IT WILL NOT DO
    Repair a "GUESS name+tag" match. A guess means several elements matched and
    resolve() took the first with no evidence it is the right one. Writing that
    element's id back would freeze an arbitrary pick as rank-1 truth AND delete
    the loud GUESS warning that is the only signal the step is ambiguous. The
    drift would go invisible at the same moment it went permanent.
"""
import json
import os
import shutil
import time

RECORDINGS = "recordings"
BACKUPS = os.path.join(RECORDINGS, "backups")
KEEP_BACKUPS = 5

# Ranks that mean "something looser than the tightest locator won". A step that
# matched on 'grid' or 'id' is already as tight as it gets — nothing to repair.
#
# 'healed' is here because of what a real Oracle upgrade proved: a recording made
# against the classic Navigator survived the Redwood shell, where EVERY navigation
# id had been renamed. Four heals carried it, and it landed on the right record —
# but it paid four model calls to reach answers it had already found twice before,
# and would pay them again every run forever. That is the waste write-back exists
# to remove.
#
# Two gates were tried and both were WRONG, which is worth recording so they are
# not re-invented:
#   1. "a heal followed by another heal is suspect" — no. In a whole-UI migration
#      consecutive heals are what a legitimate repair LOOKS like.
#   2. "only write back if a later step resolves at rank 1" — no. In a total id
#      change nothing resolves at rank 1 anywhere, so this refuses to repair
#      exactly the case the healer exists for.
# Both failed the same way: they infer "did this work?" from HOW LOCATORS
# RESOLVED, which is a property of the locators, not of the task. Proving the task
# succeeded needs an end-state check the tool does not have yet. Until it does,
# the evidence is "the run completed", and the protection is the backup plus the
# provenance below — recoverable, rather than provably right.
REPAIRABLE_RANKS = ("grid-position", "name+tag", "healed")


def plan_repair(step, el, rank, reason=""):
    """Work out which recorded fields would make this step match on rank 1 next run.

    Returns {field: new_value} containing ONLY fields that actually differ from
    what the step already says, or None when nothing should be written. Deciding
    this separately from writing it means the decision is testable without
    touching a file.
    """
    if rank not in REPAIRABLE_RANKS:
        return None

    changes = {}

    if el.get("grid"):
        # A grid cell's identity is {grid, row, column} (invariant #12). Refresh
        # all three from the element we actually landed on, and force the id
        # BLANK: a cell's ui-id-N is a jQuery counter that renumbers every
        # session, so recording it would give resolve() a confident wrong answer
        # on the very next run.
        wanted = {
            "grid": el["grid"],
            "row": el.get("row"),
            "column": el.get("column"),
            "name": el.get("name", ""),
            "tag": el.get("tag", ""),
            "id": "",
        }
    else:
        # Non-grid: the id is the tight locator, so write today's id (or blank,
        # if this element genuinely has none — then name+tag stays the best
        # locator it has and refreshing it is still worth doing).
        wanted = {
            "id": el.get("id") or "",
            "name": el.get("name", ""),
            "tag": el.get("tag", ""),
        }

    for field, value in wanted.items():
        if step.get(field) != value:
            changes[field] = value

    if changes and rank == "healed":
        # PROVENANCE. A heal rewrites the locator, so without this the step would
        # silently stop describing what a human meant: "Oracle Logo Home" becomes
        # "Actions" and nobody — including the person who recorded it — can tell
        # what the step was ever for. Keeping the old values makes the recording
        # readable, auditable, and revertable one step at a time instead of only
        # by restoring the whole backup file.
        #
        # `originally` survives repeated heals: each repair overwrites the
        # immediate previous locator, but the label a HUMAN actually recorded is
        # the one worth never losing.
        previous = step.get("healed_from") or {}
        changes["healed_from"] = {
            "name": step.get("name", ""),
            "id": step.get("id", ""),
            "tag": step.get("tag", ""),
            "when": time.strftime("%Y-%m-%d"),
            "reason": (reason or "")[:300],
            "originally": previous.get("originally") or step.get("name", ""),
        }

    return changes or None


def describe_repair(changes, step):
    """One line per changed field, old -> new, for the run log."""
    lines = []
    for field, value in changes.items():
        if field == "healed_from":
            # The provenance block is for reading in the FILE, not for dumping
            # into the console — printing the whole dict buries the actual change.
            lines.append(f'      (keeping provenance: was "{value["name"]}"'
                         f' id={value["id"] or "(none)"})')
            continue
        old = step.get(field)
        lines.append(f"      {field}: {old!r} -> {value!r}")
    return "\n".join(lines)


def _backup(path, name):
    """Copy the recording aside before the first write to it.

    recordings/ is gitignored, so there is no `git checkout` to undo a bad
    write-back. This is the undo.
    """
    os.makedirs(BACKUPS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUPS, f"{name}.{stamp}.json")
    shutil.copy2(path, dest)

    # Keep the newest few, so the folder doesn't grow forever but a bad repair
    # noticed a couple of runs later is still recoverable.
    mine = sorted(f for f in os.listdir(BACKUPS)
                  if f.startswith(f"{name}.") and f.endswith(".json"))
    for old in mine[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUPS, old))
        except OSError:
            pass
    return dest


def _write_atomic(path, data):
    """Serialise first, then replace in one move.

    json.dump straight onto the real path truncates it before writing a byte —
    a crash or a serialisation error halfway through leaves a destroyed
    recording. Building the whole text first means a failure happens before
    anything is overwritten, and os.replace is atomic on Windows and POSIX.
    """
    text = json.dumps(data, indent=2)
    json.loads(text)                      # free insurance: it must read back
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def apply_repairs(name, data, repairs):
    """Write buffered repairs into recordings/<name>.json.

    `data` is the envelope replay already loaded ({name, goal, steps}, or a bare
    list for an old recording) with its step dicts still inside it, so mutating
    them here and re-dumping `data` preserves the envelope exactly — no
    reconstruction, nothing to get wrong.

    `repairs` is a list of (step_index, changes) as planned by plan_repair.
    """
    if not repairs:
        return False

    path = os.path.join(RECORDINGS, f"{name}.json")
    steps = data["steps"] if isinstance(data, dict) else data

    backup = _backup(path, name)
    for step_index, changes in repairs:
        steps[step_index].update(changes)
    _write_atomic(path, data)

    print(f"   write-back: repaired {len(repairs)} step(s) in {path}")
    print(f"   backup: {backup}")
    return True
