"""Accept the last run as the new known-good baseline.

    py bless.py test_broken          # show what would change, then confirm
    py bless.py test_broken --yes    # skip the confirmation
    py bless.py                      # list recordings that have a capture

WHY THIS IS A SEPARATE COMMAND AND NOT A SWITCH IN .env
    A `.env` flag has to be set BEFORE the run, but "was that run any good?" can
    only be answered AFTER watching it. A pre-run switch forces you to commit to
    trusting a run you have not seen yet, and if it is ever left switched on,
    every subsequent run silently redefines "good" - which is exactly the
    laundering the no-laundering rule exists to prevent. A command you run
    afterwards puts the decision where the evidence is, and has no state to
    forget.

WHEN YOU NEED IT
    Rarely. `replay` refreshes the baseline by itself after a run that compared
    clean and needed no healing, so a baseline keeps up with small legitimate
    drift on its own. This is for the case automation cannot judge:

      - Oracle changed the UI. Every page differs from the baseline, every step
        warns, and the stored picture is not WRONG, it is OLD. Somebody has to
        look at a run and say "yes, this is the new normal".
      - The run needed the healer. Heals can be entirely correct - a recording
        made against the classic Navigator once survived the Redwood shell on
        four of them - and nothing in the system knows it. A human does.

SAFETY
    The previous baseline is always kept as <name>.previous.json, so a bless you
    regret is one file copy away from being undone.
"""
import json
import os
import sys

import baseline


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


def summarise(good, run):
    """Print what blessing would change, per step.

    The point is that you SEE the difference before accepting it. A UI upgrade
    should look like many steps changing a lot; a bless that shows one step
    moving slightly is worth a second thought before it becomes the truth
    everything is measured against.
    """
    old, new = good["states"], run["states"]
    if len(old) != len(new):
        print(f"  state count differs: baseline has {len(old)}, this run has "
              f"{len(new)} - the recording itself changed")
        return

    changed = 0
    for i, (a, b) in enumerate(zip(old, new)):
        diff = baseline.compare(a["elements"], b["elements"])
        if diff["same"]:
            continue
        changed += 1
        label = f"{b['action']} {b['step_name'][:28]}".strip()
        # Sizes, not just the percentage - a page five times larger than the
        # baseline scored 76% "the same", because overlap counts each distinct
        # element once however many copies of it are on screen.
        print(f"  step {i:>3} {label:<32} {diff['overlap']:5.1f}% the same "
              f"(+{len(diff['added'])} -{len(diff['removed'])}; "
              f"{a['count']} -> {b['count']} elements)")
    if not changed:
        print("  no differences - the baseline already matches this run")
    else:
        print(f"  {changed} of {len(old)} states differ")
    return changed


def bless(name, assume_yes=False):
    run = _load_json(baseline.last_run_path(name))
    if run is None:
        print(f"no captured run for '{name}' - replay it once first "
              f"(nothing to bless)")
        return False
    if run.get("format") != baseline.FORMAT:
        print(f"that capture is format {run.get('format')}, this code expects "
              f"{baseline.FORMAT} - replay it again to recapture")
        return False

    good = _load_json(baseline.path_for(name))
    print(f"{name}: run of {run.get('captured', '?')}, "
          f"{len(run['states'])} page states")
    if good is None:
        print("  no existing baseline - this run would become the first one")
    else:
        print(f"  current baseline is from {good.get('captured', '?')}\n")
        summarise(good, run)

    if not assume_yes:
        # A bless overwrites the definition of "correct" for this recording.
        # That deserves a keystroke, not a silent success.
        answer = input("\nmake this run the known-good baseline? (y/n): ").strip().lower()
        if answer != "y":
            print("left alone")
            return False

    path = baseline.save(name, run["states"], run.get("goal", ""))
    print(f"blessed -> {path}")
    if good is not None:
        print(f"previous kept as {name}.previous.json")
    return True


def list_available():
    try:
        files = sorted(os.listdir(baseline.BASELINES))
    except FileNotFoundError:
        print("no captures yet - replay something first")
        return
    names = sorted({f[: -len(".last-run.json")] for f in files
                    if f.endswith(".last-run.json")})
    if not names:
        print("no captured runs yet - replay something first")
        return
    print("recordings with a captured run:\n")
    for n in names:
        marker = "" if baseline.exists(n) else "   (no baseline yet)"
        print(f"   {n}{marker}")
    print("\n  py bless.py <name>")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        list_available()
    else:
        bless(args[0], assume_yes="--yes" in sys.argv or "-y" in sys.argv)
