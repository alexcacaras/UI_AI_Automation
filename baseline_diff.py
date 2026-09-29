"""Why did level 2 warn? Compare the blessed baseline to the last run - offline.

    py baseline_diff.py test1

replay says "step N does not match the known-good run: 92%". This says WHICH
elements differ, which is the only way to tell a real wrong-page from the
window being a different width. No browser, no Oracle, instant.

Written after a test1 run warned on all seven steps and a human who had watched
it said the two runs looked identical. They did: five of the six differences
were one virtualized grid column, and the sixth was a button that comes and
goes with whether the card has unsaved changes.
"""
import io
import json
import sys

import baseline


def main(name):
    good = baseline.load(name)
    if good is None:
        raise SystemExit(f"no blessed baseline for {name!r}")
    try:
        last = json.load(io.open(baseline.last_run_path(name), encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        raise SystemExit(f"no last-run capture for {name!r} - replay it once")

    if len(good["states"]) != len(last["states"]):
        print(f"WARNING: baseline has {len(good['states'])} states, last run "
              f"{len(last['states'])} - the recording changed, so the steps "
              f"below are not lined up")

    clean = True
    for i, (g, c) in enumerate(zip(good["states"], last["states"])):
        # The same comparison level 2 makes, so this explains THAT warning and
        # not a differently-configured one.
        d = baseline.compare(g["elements"], c["elements"],
                             ignore_dates=True, ignore_values=True)
        if d["same"]:
            continue
        clean = False
        print(f"\nstep {i} ({g['action']} {g['step_name'][:30]}): "
              f"{g['count']} -> {c['count']} elements, overlap {d['overlap']:.0f}% "
              f"({d['cells']} grid cells, {d['anonymous']} unidentified)")
        for k in d["removed"]:
            print(f"    gone now: id={k[0] or '(none)':<14} {k[1][:60]}")
        for k in d["added"]:
            print(f"    new now : id={k[0] or '(none)':<14} {k[1][:60]}")
    if clean:
        print(f"{name}: last run matches the baseline on every step")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    main(sys.argv[1])
