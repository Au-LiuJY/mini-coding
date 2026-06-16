"""
EWMA multiplier 收敛模拟
========================
场景：真实 tokens = 估算 tokens × 1.32 (固定偏差) + 高斯噪声 σ=5%
系统通过 EWMA 动态调整 multiplier，使得 估算×multiplier ≈ 真实
"""

import random, math, statistics

random.seed(42)

# ── 1. 构造 30 条混合 messages ──────────────────────────────────
ROLES = ["user", "assistant", "tool_result", "system"]

messages = []
for i in range(30):
    role = ROLES[i % 4]  # 循环分配
    if role == "tool_result":
        content = f"Tool output for call_{i} with result data: {random.randint(100,999)}"
    elif role == "system":
        content = f"System instruction block {i//4 + 1}: You are a helpful assistant."
    elif role == "assistant":
        content = f"This is assistant response #{i} with some reasoning and conclusion."
    else:
        content = f"User message #{i}: Can you help me with task number {random.randint(1,99)}?"
    messages.append({"role": role, "content": content})

print(f"构造了 {len(messages)} 条 messages")
print(f"  system: {sum(1 for m in messages if m['role']=='system')}")
print(f"  user:   {sum(1 for m in messages if m['role']=='user')}")
print(f"  assistant: {sum(1 for m in messages if m['role']=='assistant')}")
print(f"  tool_result: {sum(1 for m in messages if m['role']=='tool_result')}")
print()

# ── 2. 启发式估算函数 ──────────────────────────────────────────
def estimate_tokens(msg: dict) -> int:
    """简单启发式：按字符数 × 0.3 + 角色开销"""
    role_overhead = {"system": 4, "user": 3, "assistant": 3, "tool_result": 6}
    char_count = len(msg["content"])
    return int(char_count * 0.3) + role_overhead.get(msg["role"], 3)

def estimate_messages_tokens(msgs: list) -> int:
    return sum(estimate_tokens(m) for m in msgs)

# ── 3. 真实 tokens 函数（固定比例 + 噪声）────────────────────
def real_messages_tokens(msgs: list) -> int:
    """模拟 API 返回的真实 token 数：估算值 × 1.32 + 5% 高斯噪声"""
    estimated = estimate_messages_tokens(msgs)
    bias = 1.32            # 固定低估 32%
    noise = random.gauss(0, estimated * 0.05)  # 5% 噪声
    return int(estimated * bias + noise)

# ── 4. EWMA 校准循环 ───────────────────────────────────────────
def ewma_multiplier_simulation(alpha: float = 0.3, iterations: int = 10):
    """
    每轮：
      1. 系统收到真实 tokens (API 返回)
      2. 计算 ratio = 真实 / 估算
      3. multiplier = EWMA(ratio)
      4. 修正后估算 = 估算 × multiplier
      5. 计算修正后误差
    """
    estimated = estimate_messages_tokens(messages)  # 固定输入
    multiplier = 1.0          # 初始值
    history = []

    print(f"{'轮次':>4} | {'估算':>6} | {'真实':>6} | {'multiplier':>10} | {'修正后':>6} | {'修正误差%':>8}")
    print("-" * 60)

    for t in range(1, iterations + 1):
        real = real_messages_tokens(messages)
        ratio = real / estimated

        # EWMA 更新
        multiplier = alpha * ratio + (1 - alpha) * multiplier

        corrected = int(estimated * multiplier)
        err_pct = (corrected - real) / real * 100

        history.append({
            "round": t, "estimated": estimated, "real": real,
            "ratio": ratio, "multiplier": multiplier,
            "corrected": corrected, "err_pct": err_pct
        })

        # 对真实值随机微调每次不同
        print(f"{t:>4} | {estimated:>6} | {real:>6} | {multiplier:>10.4f} | {corrected:>6} | {err_pct:>+7.2f}%")

    print("-" * 60)
    print(f"EWMA α={alpha}")
    print(f"  最终 multiplier: {history[-1]['multiplier']:.4f}")
    print(f"  最终修正误差:   {history[-1]['err_pct']:+.2f}%")
    print(f"  未修正时误差:   {(estimated - history[-1]['real'])/history[-1]['real']*100:+.2f}%")
    print()

    # 收敛速度指标：误差首次进入 ±5% 的轮次
    for h in history:
        if abs(h["err_pct"]) < 5:
            print(f"  → 第 {h['round']} 轮进入 ±5% 误差带")
            break
    else:
        print(f"  → 10 轮内未进入 ±5% 误差带")

    return history

# ── 5. 运行 ─────────────────────────────────────────────────────
h1 = ewma_multiplier_simulation(alpha=0.3, iterations=10)

print("=" * 60)
print("对比：α=0.1 (慢收敛) vs α=0.5 (快跟踪)")
print("=" * 60)

for alpha in [0.1, 0.5]:
    print(f"\n── α={alpha} ──")
    estimated = estimate_messages_tokens(messages)
    multiplier = 1.0
    for t in range(1, 11):
        real = real_messages_tokens(messages)
        ratio = real / estimated
        multiplier = alpha * ratio + (1 - alpha) * multiplier
        corrected = int(estimated * multiplier)
        err = (corrected - real) / real * 100
        print(f"  第{t:>2}轮 | multiplier={multiplier:.4f} | 修正误差={err:+.2f}%")
