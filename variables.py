"""Recorded values that change per run — ${name} placeholders.

WHY
    A recording freezes whatever was typed the day it was made. "09/27/2026" in
    a pay-period field, "san" in a search box. Replay then reproduces that
    exact date forever, so a time card test can only ever test the period it
    was recorded in. Parameterising the value is what turns one recording into
    a test you can point at any period, any employee, any pod.

    This is Phase 0's ${var} design finally reaching the recording format, and
    the ${day} / ${date} item parked in phase5.md 5h.

HOW IT IS AUTHORED — after the fact, on purpose
    You record normally: type the value, seal it with CapsLock. Then you press
    MAKE VARIABLE in the command centre and give it a name, and the step just
    recorded is rewritten from "09/27/2026" to "${pay_period}".

    The obvious alternative was a new seal key in the browser alongside
    CapsLock and Insert. That means touching the overlay keydown listener,
    which is invariant #6 territory (installed once, must not stack or wipe
    capturedText) and the source of several bugs in phase4.md. Rewriting a step
    that is already safely in the recording is pure Python and cannot break
    capture. Same answer, none of the risk.

WHERE VALUES COME FROM
    recordings/vars/<recording>.json — one file per recording, so two tests can
    use ${employee} and mean different people. Replay asks for anything
    missing and offers to save it, so the first run after adding a variable
    fills the file in for you.

    It lives under recordings/ (gitignored) for the same reason baselines do:
    the values ARE the employee names and person numbers.

SUBSTITUTION HAPPENS AT USE, NEVER IN THE STEP
    replay resolves ${name} at the moment it types, and the step dict keeps the
    placeholder. If the substituted value were written back into the step, Tier
    2 write-back would eventually persist it and silently un-parameterise the
    recording — turning a variable back into the frozen literal it replaced,
    with no error and no way to notice.
"""
import json
import os
import re

VARS_DIR = os.path.join("recordings", "vars")

# ${pay_period}, ${employee_id}. Deliberately narrow, and a name MUST start
# with a letter or underscore: the first version allowed digits there, so a
# recorded "${100}" - a price, a currency field, anything Oracle renders with
# braces - parsed as a variable called "100" and would have been silently
# substituted away. Caught by the offline test, not by a run.
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}")


def names_in(text):
    """Every ${name} in one string, in order."""
    return _PLACEHOLDER.findall(str(text or ""))


def names_used(steps):
    """Every variable a recording refers to, de-duplicated, in first-use order."""
    out = []
    for step in steps:
        for name in names_in(step.get("value", "")):
            if name not in out:
                out.append(name)
    return out


def substitute(text, values):
    """Replace ${name} with its value. An UNKNOWN name is left exactly as it is.

    Deliberately not an error and not an empty string. Typing "" into a
    required field produces a confusing Oracle validation failure three steps
    later; leaving "${employee}" visible in the field makes the cause obvious
    in the screenshot and in the level 3 warning.
    """
    return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))),
                            str(text or ""))


def path_for(recording):
    return os.path.join(VARS_DIR, f"{recording}.json")


def load(recording):
    try:
        with open(path_for(recording), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(recording, values):
    os.makedirs(VARS_DIR, exist_ok=True)
    path = path_for(recording)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2)
    os.replace(tmp, path)          # atomic, like baseline._write
    return path


def resolve(recording, steps, interactive=True):
    """The values for this run: stored ones, plus anything still missing.

    Returns (values, missing). `missing` is non-empty only when nobody could be
    asked - the web frontend runs with interactive=False and must never block
    on a terminal prompt (phase7.md), so it gets told what it lacks instead of
    hanging forever.
    """
    wanted = names_used(steps)
    if not wanted:
        return {}, []

    values = load(recording)
    missing = [n for n in wanted if n not in values or values[n] == ""]
    if not missing:
        return values, []

    if not interactive:
        return values, missing

    print(f"\nthis recording uses {len(wanted)} variable(s); "
          f"{len(missing)} need a value:")
    for name in missing:
        values[name] = input(f"   {name} = ").strip()
    if input("save these for next time? (y/n): ").strip().lower() == "y":
        print(f"   saved -> {save(recording, values)}")
    return values, []
