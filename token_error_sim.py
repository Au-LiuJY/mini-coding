"""最小可复现模拟：token 估算误差对系统稳定性的影响 + EWMA 校准收敛演示"""
import random
import math

random.seed(42)

# ====== 1. 构造 30 条混合 messages ======
ROLES = ["system", "user", "assistant", "tool_result"]
CONTENT_POOL = [
    "Hello, how can I help you today?", "Let me check the code.",
    "The function returns a dictionary with keys: status, data, error.",
    "def foo(x): return x * 2", "Error: connection timeout after 30s",
    "请分析一下这段代码的性能瓶颈", "{\"result\": \"ok\", \"count\": 42}",
    "Sure, here is the implementation plan:", "Based on the analysis,",
    "Tool completed successfully with 3 files modified.",
    "I need to review the requirements first.",
    "The PID controller output is: 0.873", "Let me trace the execution path...",
    "Memory usage: 45.2 MB, CPU: 12%", "Please verify the changes.",
    "## System Architecture\n- Agent Loop\n- Tools\n- Memory",
    "def estimate_tokens(text): return len(text) // 4",
    "File not found: /tmp/data.csv", "Retrying with exponential backoff...",
    "context_id: abc-123, session: test-456",
    "Elapsed: 2.3s, tokens: 1450, cost: $0.029",
    "The quick brown fox jumps over the lazy dog.",
    "status=200, body={'id': 42, 'name': 'test'}",
    "WARNING: disk usage at 87%", "Processing batch 7/10...",
    "This is a long message that simulates a detailed code review " * 3,
    "Short msg", "Medium length message with some content here",
    "Tool call: read_file(path='main.py', offset=0, limit=100)",
    "Tool result: found 3 matches in 2 files",
]

messages = []
for i in range(30):
    role = ROLES[i % 4]
    content = CONTENT_POOL[i % len(CONTENT_POOL)]
    msg = {"role": role, "content": content}
    if role == "tool_result":
        msg["tool_use_id"] = f"tool_{i}"
    messages.append(msg)


# ====== 2. 启发式估算 tokens ======
ROLE_OVERHEAD = {"system": 3, "user": 4, "assistant": 3, "tool_result": 6}

def estimate_message_tokens(msg: dict) -> int:
    role = msg.get("role", "")
    overhead = ROLE_OVERHEAD.get(role, 3)
    content = msg.get("content", "")
    char_count = len(content)
    text_tokens = max(1, char_count // 4)  # 约 4 chars/token
    return overhead + text_tokens

def estimate_messages_tokens(msgs: list) -> int:
    return sum(estimate_message_tokens(m) for m in msgs)


# ====== 3. "真实" tokens（固定比例 + 噪声） ======
def real_messages_tokens(msgs: list) -> int:
    """真实 token 数 = 估算值 * 1.35 + 噪声 ±10%"""
    est = estimate_messages_tokens(msgs)
    noise = est * 0.1 * (random.random() * 2 - 1)  # ±10%
    return int(est * 1.35 + noise)


# ====== 4. EWMA Multiplier 校准 ======
def ewma_multiplier_convergence(messages, iterations=10, alpha=0.3):
    """演示 EWMA multiplier 如何在 10 次 API 调用中收敛"""
    multiplier = 1.0  # 初始无校准
    print(f"{'Iter':>4s}  {'Estimated':>10s}  {'Real':>10s}  {'Ratio':>8s}  {'EWMA Mult':>10s}  {'Adjusted':>10s}  {'Error%':>8s}")
    print("-" * 75)

    for i in range(iterations):
        est = estimate_messages_tokens(messages)
        real = real_messages_tokens(messages)

        if i == 0:
            # 首次无校准，直接用 1.0
            ratio = real / est
            multiplier = 1.0
            adjusted = est
        else:
            ratio = real / est
            multiplier = alpha * ratio + (1 - alpha) * multiplier
            adjusted = int(est * multiplier)

        error_pct = (real - adjusted) / real * 100
        print(f"{i:>4d}  {est:>10d}  {real:>10d}  {ratio:>8.4f}  {multiplier:>10.4f}  {adjusted:>10d}  {error_pct:>+7.1f}%")

    print(f"\n✅ EWMA multiplier 从 1.0 收敛到 {multiplier:.4f}")
    print(f"   校准前误差: {((real_messages_tokens(messages) - estimate_messages_tokens(messages))/real_messages_tokens(messages)*100):+.1f}%")
    print(f"   校准后误差: {((real_messages_tokens(messages) - int(estimate_messages_tokens(messages)*multiplier))/real_messages_tokens(messages)*100):+.1f}%")


# ====== 5. 演示失败模式 ======
def demonstrate_failure_modes(messages):
    est = estimate_messages_tokens(messages)
    real = real_messages_tokens(messages)
    ratio = real / est
    print(f"\n{'='*70}")
    print(f"估算 tokens: {est}  |  真实 tokens: {real}  |  偏差比: {ratio:.3f}")
    print(f"{'='*70}\n")

    # 假设上下文限制 8000 tokens
    limit = 8000

    # 低估失败模式
    print("🔴 低估 tokens 的失败模式:")
    print(f"  ① 上下文溢出: 估算 {est}, 系统认为剩余 {limit-est}, 发请求后实际 {real} 超限")
    if est < limit < real:
        print(f"     → 真实已超 {limit}, API 调用直接失败")
    print(f"  ② Compaction 提前终止: 压缩目标 {limit//2}, 估算达标但实际仍超 {int(limit//2 * ratio)}")
    print(f"  ③ 预算失控: 按估算计费 {est*0.003:.2f}$, 实际 {real*0.003:.2f}$, 偏差 {(real-est)*0.003:.2f}$")

    # 高估失败模式（构造高估场景）
    over_est = int(real * 1.4)
    print(f"\n🟡 高估 tokens 的失败模式 (假设估算={over_est}, 真实={real}):")
    print(f"  ① 过早 compaction: 在 {over_est} 触发压缩, 实际才 {real}, 浪费计算资源")
    print(f"  ② 上下文利用率低: 窗口 {limit}, 压缩到 {int(limit*0.5)}, 实际只用 {int(limit*0.5/ratio)}")
    print(f"  ③ 无意义丢弃: 系统判定 {over_est} > {limit} 开始丢消息, 实际 {real} 远未到阈值")


if __name__ == "__main__":
    # 先打印消息概要
    print(f"构造了 {len(messages)} 条 messages:")
    for i, m in enumerate(messages):
        print(f"  [{i:>2d}] {m['role']:>15s}  |  {m['content'][:50]}")
    print()

    # 展示 EWMA 收敛
    ewma_multiplier_convergence(messages, iterations=10, alpha=0.3)
    print()

    # 展示失败模式
    demonstrate_failure_modes(messages)
