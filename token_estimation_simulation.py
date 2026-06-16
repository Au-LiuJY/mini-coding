"""
Token 估算误差对系统稳定性的影响 — 最小可复现模拟

设计：
  - 30 条混合 messages（system/user/assistant/tool_result）
  - 启发式估算器（角色固定开销 + 字符 x0.3）
  - 真实值模拟器（真实比例 1.33x + ±15% 噪声）
  - EWMA multiplier 自适应校准
  - 10 轮在线迭代 + 1 轮回放验证
"""

import json
import math
import random
import time

random.seed(0)

# ============================================================
# 1. 构造 30 条混合 messages
# ============================================================

def build_30_messages() -> list[dict]:
    msgs = [
        {"role": "system",    "content": "You are MiniCode, a terminal-first AI coding assistant."},
        {"role": "user",      "content": "帮我看看这个项目结构"},
        {"role": "assistant", "content": "好的，我来分析当前工作目录的项目结构。"},
        {"role": "tool_result","content": "📁 MiniCode-Python\n├── minicode/\n│   ├── agent_loop.py\n│   ├── context_manager.py\n│   └── memory.py\n├── tests/\n└── benchmarks/"},
        {"role": "user",      "content": "帮我分析一下 context_manager.py 中 token 估算的误差"},
        {"role": "assistant", "content": "我在 context_manager.py 中找到了 estimate_messages_tokens 函数。"},
        {"role": "tool_result","content": "def estimate_messages_tokens(messages):\n    return sum(estimate_message_tokens(m) for m in messages)"},
        {"role": "user",      "content": "帮我优化这个函数的性能"},
        {"role": "assistant", "content": "我来看一下性能瓶颈在哪里。首先检查调用链："},
        {"role": "tool_result","content": "estimate_messages_tokens 被 compact_messages 调用，位于行 1010/1079/1119/1140"},
        {"role": "user",      "content": "详细解释一下这个代码的作用"},
        {"role": "assistant", "content": "estimate_messages_tokens 用于计算整个 message 列表的 token 总数。"},
        {"role": "tool_result","content": "每次 compaction 循环都会调用 estimate_messages_tokens，复杂度 O(n*k)"},
        {"role": "user",      "content": "这个 token 估算准不准？"},
        {"role": "assistant", "content": "目前估算用的是启发式 字符数*0.3 + 角色开销，和实际 tokenizer 有差异。"},
        {"role": "tool_result","content": "实际 tokenizer 对比：estimate=1240, actual=1650, 误差 +33%"},
        {"role": "user",      "content": "帮我写一个 EWMA 校准器来修正这个误差"},
        {"role": "assistant", "content": "好的，我来实现 TokenEstimationCalibrator，使用 EWMA 动态调整 multiplier。"},
        {"role": "tool_result","content": "class TokenEstimationCalibrator:\n    def __init__(self, alpha=0.3):\n        self.alpha = alpha\n        self.multiplier = 1.0"},
        {"role": "user",      "content": "这个校准器的收敛速度怎么样？"},
        {"role": "assistant", "content": "EWMA 的收敛速度取决于 alpha 参数。alpha 越大响应越快但噪声越多。"},
        {"role": "tool_result","content": "收敛测试：iter=0 mult=1.00  iter=1 mult=1.10  iter=5 mult=1.28  iter=10 mult=1.32"},
        {"role": "user",      "content": "能不能加到 context_manager 里？"},
        {"role": "assistant", "content": "可以，但需要先确认调用点和数据流是否支持。"},
        {"role": "tool_result","content": "调用点分析：estimate_messages_tokens 被 compact_messages 和 adapter 调用"},
        {"role": "user",      "content": "那 compaction 决策会不会受误差影响？"},
        {"role": "assistant", "content": "会。如果低估了实际 tokens，compaction 会过早停止，可能导致上下文溢出。"},
        {"role": "tool_result","content": "溢出风险：低估 33% 意味着 target_tokens=100k 时实际已达 133k，超过模型限制"},
        {"role": "user",      "content": "那高估呢？"},
        {"role": "assistant", "content": "高估会导致 compaction 过度激进，丢弃太多有用上下文，影响回答质量。"},
        {"role": "tool_result","content": "过度压缩：高估 20% 时 target_tokens 剩余 80k 但实际只有 64k，浪费 16k 容量"},
        {"role": "user",      "content": "校准器能同时解决这两个问题吗？"},
        {"role": "assistant", "content": "EWMA 校准器能动态追踪 bias 并修正，将误差控制在 5% 以内。"},
        {"role": "tool_result","content": "修正后误差：校准前 +33%, 校准后 +2.1%, 提升 15 倍"},
        {"role": "user",      "content": "那还不赶紧加上去"},
        {"role": "assistant", "content": "好的，我这就加！需要在 estimate_messages_tokens 中加入 multiplier 调用。"},
        {"role": "tool_result","content": "修改完成：estimate_messages_tokens 现在内部调用 apply_token_estimation_multiplier"},
    ]
    # 补齐 30 条
    while len(msgs) < 30:
        msgs.append({"role": "user", "content": f"继续分析第 {len(msgs)+1} 个方面"})
        msgs.append({"role": "assistant", "content": f"好的，第 {len(msgs)+1} 个方面的分析结果如下。"})
    return msgs[:30]

messages = build_30_messages()

# ============================================================
# 2. 估算 token 函数（启发式）
# ============================================================

ROLE_OVERHEAD = {
    "system": 3, "user": 4, "assistant": 3,
    "assistant_tool_call": 7, "tool_result": 6,
}

def estimate_message_tokens(msg: dict) -> int:
    overhead = ROLE_OVERHEAD.get(msg.get("role", ""), 3)
    content = msg.get("content", "")
    if isinstance(content, str):
        return overhead + int(len(content) * 0.3)
    return overhead

def estimate_messages_tokens(msgs: list) -> int:
    return sum(estimate_message_tokens(m) for m in msgs)

# ============================================================
# 3. "真实" token 函数（固定比例 1.33x + 噪声）
# ============================================================

def actual_message_tokens(msg: dict) -> int:
    est = estimate_message_tokens(msg)
    noise = random.gauss(0, 0.08)  # ±8% 噪声
    ratio = 1.33 * (1 + noise)
    return max(1, int(est * ratio))

def actual_messages_tokens(msgs: list) -> int:
    return sum(actual_message_tokens(m) for m in msgs)

# ============================================================
# 4. EWMA Multiplier 校准器
# ============================================================

class EWMACalibrator:
    def __init__(self, alpha=0.3, initial=1.0, min_mult=0.8, max_mult=2.0):
        self.alpha = alpha
        self.multiplier = initial
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.samples = []

    def record_sample(self, estimated: int, actual: int):
        if estimated <= 0:
            return
        ratio = actual / estimated
        # EWMA 更新
        self.multiplier = self.alpha * ratio + (1 - self.alpha) * self.multiplier
        self.multiplier = max(self.min_mult, min(self.max_mult, self.multiplier))
        self.samples.append(ratio)

    def apply(self, estimated: int) -> int:
        return int(estimated * self.multiplier)

# ============================================================
# 5. 模拟 10 轮在线迭代
# ============================================================

def simulate():
    calibrator = EWMACalibrator(alpha=0.3)

    print(f"{'iter':>4s}  {'估(原始)':>10s}  {'估(校准)':>10s}  {'真值':>10s}  {'raw_err':>8s}  {'cal_err':>8s}  {'mult':>6s}  {'cal_samples':>12s}")
    print("-" * 85)

    for iteration in range(1, 11):
        est_raw = estimate_messages_tokens(messages)
        est_cal = calibrator.apply(est_raw)
        actual  = actual_messages_tokens(messages)

        raw_err = (actual - est_raw) / est_raw * 100
        cal_err = (actual - est_cal) / est_cal * 100 if est_cal > 0 else 0.0

        # 记录校准样本
        calibrator.record_sample(est_raw, actual)

        cal_samples_str = f"{calibrator.samples[-1]:.3f}" if calibrator.samples else "N/A"
        print(f"{iteration:>4d}  {est_raw:>10d}  {est_cal:>10d}  {actual:>10d}"
              f"  {raw_err:>+7.1f}%  {cal_err:>+7.1f}%  {calibrator.multiplier:>5.3f}  {cal_samples_str:>12s}")

    # 回放验证：用同一个消息集再测一次校准后误差
    print(f"\n=== 回放验证（同一消息集，不用再校准）===")
    est_raw = estimate_messages_tokens(messages)
    est_cal = calibrator.apply(est_raw)
    actual  = actual_messages_tokens(messages)
    raw_err = (actual - est_raw) / est_raw * 100
    cal_err = (actual - est_cal) / est_cal * 100
    print(f"  原始估算:    {est_raw:>8d}  → 误差 {raw_err:>+6.1f}%")
    print(f"  校准后估算:  {est_cal:>8d}  → 误差 {cal_err:>+6.1f}%")
    print(f"  真实值:      {actual:>8d}")
    print(f"  最终 multiplier: {calibrator.multiplier:.4f}")
    print(f"  （注：实际 ratio 约 1.33x，calibrator 收敛到 {calibrator.multiplier:.3f} 即完成追踪）")

    # 推导系统级影响
    print(f"\n=== 系统稳定性影响推演 ===")
    est_pct = (actual - est_cal) / actual * 100
    print(f"  校准后误差: {est_pct:+.1f}%")
    if abs(est_pct) < 5:
        print(f"  ✅ 误差 <5%，compaction 决策可靠，上下文溢出风险低")
    elif est_pct < -5:
        print(f"  ❌ 低估 {-est_pct:.0f}% → 溢出风险: 实际已达 {(1 - est_pct/100):.1f}x target")
    else:
        print(f"  ⚠️ 高估 {est_pct:.0f}% → 过度压缩: 浪费约 {est_pct:.0f}% 上下文容量")


if __name__ == "__main__":
    simulate()
