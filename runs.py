import os
from replay import replay

def build_order():
    files = [f[:-5] for f in os.listdir("recordings") if f.endswith(".json")]
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")
    picks = input("Pick Order(e.g '1,2,3'):").strip()
    order = [files[int(p) - 1] for p in picks.split(",")]
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