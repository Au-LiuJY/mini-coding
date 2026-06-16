"""EWMA Multiplier 收敛模拟 — 最小可复现版"""

import random, json, math

# ─── 构造 30 条混合 messages ───────────────────────────────
MESSAGES = [
    {"role": "system",    "content": "You are a helpful coding assistant."},
    {"role": "user",      "content": "写一个 Python 冒泡排序"},
    {"role": "assistant", "content": "以下是冒泡排序实现：\n```python\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n```"},
    {"role": "tool_result", "content": "ok，已经写好了"},
    {"role": "user",      "content": "能加一个优化吗？当一轮没有交换时就提前退出"},
    {"role": "assistant", "content": "好的，加入 early exit 优化："},
] * 5  # 6 种 × 5 = 30 条

# 确保精确 30 条
MESSAGES = MESSAGES[:30]


# ─── 启发式估算 ────────────────────────────────────────────
_ROLE_OVERHEAD = {"system": 4, "user": 4, "assistant": 3, "tool_result": 6}

def estimate_message_tokens(msg: dict) -> int:
    overhead = _ROLE_OVERHEAD.get(msg.get("role", ""), 3)
    content = msg.get("content", "")
    if isinstance(content, str):
        # 启发式：英文字符数 ≈ tokens，中文按 1.5 倍
        char_count = len(content)
        chinese = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
        return overhead + int(char_count * 0.3) + chinese
    return overhead

def estimate_messages_tokens(msgs: list) -> int:
    return sum(estimate_message_tokens(m) for m in msgs)


# ─── "真实" tokens（固定比例 1.35 + 高斯噪声）───────────────
def real_message_tokens(msg: dict) -> int:
    overhead = _ROLE_OVERHEAD.get(msg.get("role", ""), 3)
    content = msg.get("content", "")
    if isinstance(content, str):
        char_count = len(content)
        chinese = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
        base = overhead + int(char_count * 0.3) + chinese
        # 真实值 = 1.35 × 估算 + N(0, 0.12 × base)
        noise = int(random.gauss(0, 0.12 * base))
        return int(base * 1.35) + noise
    return overhead

def real_messages_tokens(msgs: list) -> int:
    return sum(real_message_tokens(m) for m in msgs)


# ─── EWMA Multiplier ───────────────────────────────────────
def update_ewma_multiplier(prev: float, estimate: int, actual: int, alpha: float) -> float:
    """返回新的 multiplier。"""
    if estimate == 0:
        return prev
    ratio = actual / estimate
    return alpha * ratio + (1 - alpha) * prev


# ─── 模拟主流程 ────────────────────────────────────────────
random.seed(42)  # 可复现
ROUNDS = 10
alpha = 0.3       # EWMA 平滑系数
multiplier = 1.0  # 初始为 1（未校准）

print(f"{'轮次':>4s}  {'估算':>6s}  {'真实':>6s}  {'ratio':>6s}  {'multiplier':>10s}  {'校准后':>8s}")
print("-" * 52)

for r in range(1, ROUNDS + 1):
    est = estimate_messages_tokens(MESSAGES)
    real = real_messages_tokens(MESSAGES)
    ratio = real / est
    multiplier = update_ewma_multiplier(multiplier, est, real, alpha)
    calibrated = int(est * multiplier)
    print(f"{r:>4d}  {est:>6d}  {real:>6d}  {ratio:>6.3f}  {multiplier:>10.5f}  {calibrated:>8d}")


# ─── 误差分析 ──────────────────────────────────────────────
print("\n=== 最终分析 ===")
print(f"收敛 multiplier = {multiplier:.5f}")
biases = []
for _ in range(100):
    est = estimate_messages_tokens(MESSAGES[:30])
    real = real_messages_tokens(MESSAGES[:30])
    biases.append(real / est)

biases.sort()
p50 = biases[len(biases)//2]
p95 = biases[int(len(biases)*0.95)]
print(f"P50 误差 (真实/估算) = {p50:.4f}")
print(f"P95 误差 (真实/估算) = {p95:.4f}")
print(f"若不校准，平均偏差 = {sum(biases)/len(biases):.4f} → "
      f"64K context 实际只相当于 {int(65536 / (sum(biases)/len(biases))):,} tokens 可用容量")
