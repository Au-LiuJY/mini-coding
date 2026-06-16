"""Performance Review: (i*j)%7 double-loop summation

Original:
    def f(n):
        s = 0
        for i in range(n):
            for j in range(n):
                s += (i * j) % 7
        return s
"""

import time
import sys

# ── Original (baseline) ──────────────────────────────────────────────────

def f_original(n):
    s = 0
    for i in range(n):
        for j in range(n):
            s += (i * j) % 7
    return s

# ── Fix 1: hoist loop-invariant (i % 7) out of inner loop ──────────────
# Issue #3: (i % 7) is computed n times instead of n^2 times
# Also adds local refs to avoid global lookups (Issue #4 mitigation)

def f_fix1(n):
    s = 0
    rn = range(n)
    for i in rn:
        im7 = i % 7
        for j in rn:
            s += (im7 * j) % 7
    return s

# ── Fix 2: precompute 7x7 lookup table ──────────────────────────────────
# (i*j)%7 = ((i%7)*(j%7))%7, so only 49 unique values exist
# Replaces modulo computation with table lookup (Issue #2)

def f_fix2(n):
    lut = [[(a * b) % 7 for b in range(7)] for a in range(7)]
    s = 0
    rn = range(n)
    for i in rn:
        row = lut[i % 7]
        for j in rn:
            s += row[j % 7]
    return s

# ── Fix 3: O(1) mathematical solution ──────────────────────────────────
# count[k] = how many numbers in [0, n-1] have remainder k mod 7
# sum = sum_a sum_b count[a] * count[b] * ((a*b) % 7)

def f_fix3(n):
    m = n // 7
    r = n % 7
    cnt = [m + (1 if k < r else 0) for k in range(7)]
    lut = [[(a * b) % 7 for b in range(7)] for a in range(7)]
    total = 0
    for a in range(7):
        ca = cnt[a]
        row = lut[a]
        for b in range(7):
            v = row[b]
            if v:
                total += ca * cnt[b] * v
    return total

# ── Fix 4: fully unrolled O(1) without lookup table ────────────────────

def f_fix4(n):
    m = n // 7
    r = n % 7
    cnt = [m + (1 if k < r else 0) for k in range(7)]
    total = 0
    for a in range(7):
        ca = cnt[a]
        if not ca:
            continue
        for b in range(7):
            cb = cnt[b]
            if not cb:
                continue
            total += ca * cb * ((a * b) % 7)
    return total

# ── Correctness verification ─────────────────────────────────────────────

def verify():
    test_cases = [0, 1, 2, 3, 7, 8, 14, 15, 21, 100]
    all_ok = True
    for n in test_cases:
        orig = f_original(n)
        f1 = f_fix1(n)
        f2 = f_fix2(n)
        f3 = f_fix3(n)
        f4 = f_fix4(n)
        ok = (f1 == orig and f2 == orig and f3 == orig and f4 == orig)
        mark = "[OK]" if ok else "[FAIL]"
        print(f"  n={n:3d}  orig={orig:6d}  f1={f1:6d}  f2={f2:6d}  "
              f"f3={f3:6d}  f4={f4:6d}  {mark}")
        if not ok:
            all_ok = False
    return all_ok

# ── Performance benchmark ────────────────────────────────────────────────

def benchmark():
    N = 2000
    print()
    print("=" * 65)
    print("Performance (n = 2000, 3-run avg)")
    print("=" * 65)

    funcs = [
        ("original (O(n^2))", f_original),
        ("fix1 (hoisting)",   f_fix1),
        ("fix2 (LUT 7x7)",    f_fix2),
        ("fix3 (O(1) table)", f_fix3),
        ("fix4 (O(1) simple)", f_fix4),
    ]

    results = []
    for name, fn in funcs:
        fn(10)  # warmup
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            r = fn(N)
            t = time.perf_counter() - t0
            times.append(t)
        avg = sum(times) / len(times)
        results.append((name, avg, r))
        print(f"  {name:22s}  {avg:.6f}s  result={r}")

    baseline = results[0][1]
    print()
    print("  --- Speedup ---")
    for name, avg, _ in results[1:]:
        ratio = baseline / avg if avg > 0 else float('inf')
        print(f"  {name:22s}  {ratio:.1f}x")

# ── Complexity summary ───────────────────────────────────────────────────

def complexity_summary():
    print()
    print("=" * 65)
    print("Complexity Comparison")
    print("=" * 65)
    print(f"  {'Version':22s}  {'Time':18s}  {'Space':18s}")
    print(f"  {'-'*22}  {'-'*18}  {'-'*18}")
    print(f"  {'original':22s}  {'O(n^2)':18s}  {'O(1)':18s}")
    print(f"  {'fix1 (hoisting)':22s}  {'O(n^2)':18s}  {'O(1)':18s}")
    print(f"  {'fix2 (LUT 7x7)':22s}  {'O(n^2)':18s}  {'O(1)':18s}")
    print(f"  {'fix3/fix4 (O(1))':22s}  {'O(1)':18s}  {'O(1)':18s}")

# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("Correctness Verification")
    print("=" * 65)
    if verify():
        print("  [OK] All implementations match")
    else:
        print("  [FAIL] Mismatch detected")
        sys.exit(1)

    benchmark()
    complexity_summary()
