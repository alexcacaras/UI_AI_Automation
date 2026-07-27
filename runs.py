import os
from replay import replay

def build_order():
    files = [f[:-5] for f in os.listdir("recordings") if f.endswith(".json")]
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")
    while True:
        picks = input("Pick order (e.g. 1,2,3): ").strip()
        try:
            order = [files[int(p) - 1] for p in picks.split(",")]
            if any(int(p) < 1 or int(p) > len(files) for p in picks.split(",")):
                raise ValueError
            break
        except (ValueError, IndexError):
            print("invalid — use numbers from the list, like 1,2,3")
    return order



def run_suite(page, order):
    results = []
    for test in order:
        print(f"\n=== running {test} ===")
        try:
            ok = replay(page, test)
        except Exception as e:
            ok = False
            print(f"{test} crashed: {e}")
        results.append((test, ok))
    print("\n==== RESULTS ====")
    for test, ok in results:
        print(f" {'PASS' if ok else 'FAIL'} {test}")