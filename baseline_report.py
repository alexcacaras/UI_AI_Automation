"""Read a captured baseline and report which steps DID something - offline.

    py baseline_report.py test_broken
    py baseline_report.py test_broken --last-run     (the unblessed capture)
    py baseline_report.py test_broken -v             (show what changed)

WHY THIS IS A SCRIPT AND NOT A CHECK INSIDE replay
    This is level 1 - "did the action do anything?" - and it is NOT ready to
    decide whether a run passes. Two things are already known to make it fire on
    a perfectly good run:

      - perceive cannot see typed text. A field holding "Smith" fingerprints
        identically to an empty one, so a successful `type` looks like a no-op.
        Blind sensor, not a quiet application.
      - some clicks genuinely change nothing structural. `test_broken` step 7
        (`click Search`) produced zero change on a run watched end to end and
        confirmed correct by a human.

    So the useful move is to look at the numbers on runs already trusted, and
    find out how noisy the signal is, BEFORE anything acts on it. Same reason
    test_heal.py exists: seconds per iteration, no browser, no Oracle.

HOW TO READ IT
    A capture holds one page state per step plus one after the last step, and
    each state is the page as it was BEFORE its step ran. So the effect of step
    N is the difference between state N and state N+1 - which is why the report
    is indexed by step, not by state.
"""
import sys
import baseline

# Steps whose "no change" is EXPECTED, and why. These are not exemptions - the
# report still prints the finding - they are the explanation printed beside it,
# so a real no-op is not lost in a column of known-harmless ones.
EXPECTED_QUIET = {
    # ASCII only. PowerShell's console is cp1252 here, and an em-dash prints as
    # a replacement character in the middle of the explanation.
    "type": "perceive cannot see typed values - blind, not quiet",
    "scroll": "scrolling changes what is on screen, not what exists",
    "wait": "a wait is not supposed to do anything",
}


def report(name, which="baseline", verbose=False):
    path = (baseline.path_for(name) if which == "baseline"
            else baseline.last_run_path(name))
    data = baseline.load(name) if which == "baseline" else _load(path)
    if data is None:
        print(f"no capture at {path}")
        return
    fmt = data.get("format", 1)
    if fmt != baseline.FORMAT:
        print(f"WARNING: capture is format {fmt}, this code expects "
              f"{baseline.FORMAT} - recapture before trusting these numbers")

    states = data["states"]
    print(f"{name}  ({data.get('captured', '?')})  {len(states)} states, "
          f"{len(states) - 1} steps\n")

    quiet = []
    for i in range(len(states) - 1):
        step, nxt = states[i], states[i + 1]
        diff = baseline.compare(step["elements"], nxt["elements"])
        action = step["action"]
        label = f"{i:>3} {action:<8} {step['step_name'][:30]:<32}"

        if diff["same"]:
            note = EXPECTED_QUIET.get(action, "")
            quiet.append((i, action, step["step_name"], note))
            print(f"{label} NO CHANGE" + (f"   ({note})" if note else "   <-- ?"))
        else:
            print(f"{label} changed  +{len(diff['added']):<3} "
                  f"-{len(diff['removed']):<3} ~{len(diff['recount']):<3} "
                  f"overlap {diff['overlap']:5.1f}%")
            if verbose:
                for key in diff["added"][:6]:
                    print(f"        + {key[0] or '(no id)'} | {key[1][:50]}")
                for key in diff["removed"][:6]:
                    print(f"        - {key[0] or '(no id)'} | {key[1][:50]}")
                for key, was, now in diff["recount"][:6]:
                    print(f"        ~ {key[1][:40]}  {was} -> {now}")

    unexplained = [q for q in quiet if not q[3]]
    print(f"\n{len(quiet)} of {len(states) - 1} steps changed nothing; "
          f"{len(unexplained)} of those are unexplained:")
    for i, action, step_name, _ in unexplained:
        print(f"   step {i}: {action} {step_name}")
    if not unexplained:
        print("   (none)")


def _load(path):
    import json
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        raise SystemExit(1)
    report(args[0],
           which="last-run" if "--last-run" in sys.argv else "baseline",
           verbose="-v" in sys.argv)
