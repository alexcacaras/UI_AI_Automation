"""Break one step of a recording on purpose, so the Phase 6 healer can be tested.

WHY THIS EXISTS
    Waiting for Oracle to rename a button is not a test strategy. This makes a
    broken locator on demand, so healing is repeatable and the prompt can be
    iterated in minutes.

WHAT IT BREAKS, AND WHY BOTH
    Ranked locators (actions.resolve) try grid -> id -> name+tag. Blanking only
    the id is NOT enough any more: resolve falls straight through to name+tag,
    finds the element, prints "locator degraded", and passes. The healer never
    fires. So this blanks the id AND staleness the name (and, for a grid cell,
    the grid/row/column too, which is rank 1).

HOW THE NAME IS BROKEN
    Not gibberish. Gibberish gives the model nothing to match on, so -1 would be
    the CORRECT answer and you would learn nothing. The default is a plausible
    stale label - drop the leading word, as if Oracle had reworded it:
        "Team Time Cards" -> "Time Cards"
    Pass --name to choose the stale label yourself.

USAGE
    python corrupt_step.py test                 # list the steps, pick one
    python corrupt_step.py test 13              # break step 13
    python corrupt_step.py test 13 --name Cards # break it with your own label

    -> writes recordings/test_broken.json, leaving recordings/test.json alone
    then replay 'test_broken' the way you normally replay a recording.
"""
import argparse
import json
import os

RECORDINGS = "recordings"


def load(name):
    path = os.path.join(RECORDINGS, f"{name}.json")
    if not os.path.exists(path):
        raise SystemExit(f"no recording named '{name}' in {RECORDINGS}/")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # tolerate both shapes, exactly as replay.py does
    if isinstance(data, dict):
        return data, data["steps"]
    return {"name": name, "goal": "", "steps": data}, data


def describe(step):
    bits = [step.get("action", "?")]
    if step.get("name"):
        bits.append(f'"{step["name"]}"')
    if step.get("value"):
        bits.append(f'value={step["value"]!r}')
    if step.get("tag"):
        bits.append(f'<{step["tag"]}>')
    if step.get("id"):
        bits.append(f'id={step["id"]}')
    if step.get("grid"):
        bits.append(f'grid row={step.get("row")} col={step.get("column")}')
    return "  ".join(bits)


def list_steps(steps):
    print("steps (only click / type / select can be healed):\n")
    for i, step in enumerate(steps, 1):
        healable = step.get("action") in ("click", "type", "select")
        print(f"  {i:>3}{' ' if healable else '*'} {describe(step)}")
    print("\n  * not a resolvable step - nothing to break")


def stale_name(name):
    """A plausible reworded label, as if the page had changed under us."""
    words = name.split()
    if len(words) > 1:
        return " ".join(words[1:])
    return None            # single word: caller must supply one


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording", help="name without .json, e.g. test")
    ap.add_argument("step", nargs="?", type=int, help="1-based step number")
    ap.add_argument("--name", help="the stale label to use instead of the real one")
    ap.add_argument("--out", help="output recording name (default <recording>_broken)")
    ap.add_argument("--blank-position", action="store_true",
                    help="grid cells: wipe row/column too, not just the grid id. "
                         "This is the WORST case, not the realistic one — a cell's "
                         "identity IS its position, so wiping it leaves nothing to "
                         "heal from and no model can recover it.")
    args = ap.parse_args()

    envelope, steps = load(args.recording)

    if args.step is None:
        list_steps(steps)
        return

    if not 1 <= args.step <= len(steps):
        raise SystemExit(f"step {args.step} is out of range (1..{len(steps)})")

    step = steps[args.step - 1]
    if step.get("action") not in ("click", "type", "select"):
        raise SystemExit(
            f"step {args.step} is a '{step.get('action')}' - it does not resolve an "
            "element, so there is no locator to break. Pick a click/type/select step."
        )

    broken_name = args.name or stale_name(step.get("name", ""))
    if not broken_name:
        raise SystemExit(
            f'step {args.step} is named "{step.get("name")}" - one word, so there is no '
            "sensible way to reword it automatically. Pass --name yourself, e.g.\n"
            f'    python corrupt_step.py {args.recording} {args.step} --name "Find"'
        )

    print(f"breaking step {args.step}: {describe(step)}\n")
    print(f'  name  "{step.get("name")}"  ->  "{broken_name}"')
    if step.get("id"):
        print(f'  id    {step["id"]}  ->  (blank)')
    step["name"] = broken_name
    step["id"] = ""

    if step.get("grid"):
        # How a grid step ACTUALLY breaks: Oracle renames the grid element, so
        # find_by_grid (which matches grid AND row AND column) misses — but the
        # step still carries row/column, and heal_step puts them in the prompt.
        # That is a healable failure. Wiping row/column instead deletes the only
        # identity a cell has; the day columns then differ by nothing the model
        # can see, and a wrong pick is guaranteed rather than unlucky.
        if args.blank_position:
            print(f'  grid  {step["grid"]} row={step.get("row")} '
                  f'col={step.get("column")}  ->  (all blank — worst case)')
            for key in ("grid", "row", "column"):
                step.pop(key, None)
        else:
            print(f'  grid  {step["grid"]}  ->  "{step["grid"]}_renamed"  '
                  f'(row/column kept — this is the realistic break)')
            step["grid"] = f'{step["grid"]}_renamed'

    out_name = args.out or f"{args.recording}_broken"
    if out_name == args.recording:
        raise SystemExit("refusing to overwrite the original recording")
    envelope["name"] = out_name
    out_path = os.path.join(RECORDINGS, f"{out_name}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)

    print(f"\nwrote {out_path}  (original untouched)")
    print(f"now replay '{out_name}'. Without the healer it should stop at step "
          f"{args.step}; with it, it should recover and finish.")


if __name__ == "__main__":
    main()
