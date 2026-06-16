"""Demonstrate O(1) vs O(n^2) scaling behavior."""
import time

def f_original(n):
    s = 0
    for i in range(n):
        for j in range(n):
            s += (i * j) % 7
    return s

def f_optimized(n):
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

print(f"{'n':>8}  {'original(s)':>14}  {'optimized(s)':>14}  {'ratio':>8}  {'result_ok':>8}")
print(f"{'─'*8}  {'─'*14}  {'─'*14}  {'─'*8}  {'─'*8}")
for n in [100, 500, 1000, 2000, 5000]:
    t0 = time.perf_counter()
    r1 = f_original(n)
    t1 = time.perf_counter()
    r2 = f_optimized(n)
    t2 = time.perf_counter()
    ratio = (t1 - t0) / (t2 - t0) if (t2 - t0) > 0 else float('inf')
    ok = "[OK]" if r1 == r2 else "[FAIL]"
    print(f"{n:>8}  {(t1-t0):>14.6f}  {(t2-t0):>14.6f}  {ratio:>8.0f}x  {ok:>8}")
