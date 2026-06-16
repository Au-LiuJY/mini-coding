"""性能 Review: 原始版 vs 优化版"""

def f_original(n):
    s = 0
    for i in range(n):
        for j in range(n):
            s += (i * j) % 7
    return s


def f_lookup(n):
    table = tuple(tuple((a * b) % 7 for b in range(7)) for a in range(7))
    s = 0
    for i in range(n):
        imod = i % 7
        row = table[imod]
        for j in range(n):
            s += row[j % 7]
    return s


def f_o1(n):
    q, r = divmod(n, 7)
    c = [q + (1 if a < r else 0) for a in range(7)]
    table = [[(a * b) % 7 for b in range(7)] for a in range(7)]
    total = 0
    for a in range(7):
        for b in range(7):
            total += c[a] * c[b] * table[a][b]
    return total


def verify():
    for n in [0, 1, 5, 10, 20, 50, 100]:
        v0 = f_original(n)
        v1 = f_lookup(n)
        v2 = f_o1(n)
        assert v0 == v1 == v2, f"n={n}: {v0} {v1} {v2}"
    print("OK - all versions match, verified!")


import time


def bench(fn, n, label):
    t0 = time.perf_counter()
    r = fn(n)
    t = time.perf_counter() - t0
    print(f"  {label:>25s}  result={r:>12d}  time={t:.4f}s")
    return t


if __name__ == "__main__":
    verify()
    for n in [100, 500, 1000, 3000]:
        print(f"\n--- n={n} ---")
        if n <= 500:
            bench(f_original, n, "f_original O(n^2)")
        else:
            print(f"  {'f_original O(n^2)':>25s}  SKIP (too slow)")
        bench(f_lookup, n, "f_lookup O(n^2)")
        bench(f_o1, n, "f_o1 O(1)")
