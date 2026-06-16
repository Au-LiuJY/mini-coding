#!/usr/bin/env python3
"""MiniCode Python - 轻量级终端编码助手主入口文件

架构说明：
┌─────────────────────────────────────────────────────────────────────┐
│                        main() 入口函数                              │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 1. 参数解析层 (argparse)                                      │  │
│  │ 2. 配置加载层 (runtime/config)                                │  │
│  │ 3. 核心服务初始化层                                           │  │
│  │    ├── Tool Registry (工具注册)                               │  │
│  │    ├── Permission Manager (权限管理)                          │  │
│  │    ├── Model Adapter (模型适配器)                             │  │
│  │    ├── Context Manager (上下文窗口管理)                       │  │
│  │    ├── Memory Manager (跨会话记忆)                           │  │
│  │    ├── User Profile Manager (用户配置)                        │  │
│  │    └── App Store (全局状态管理)                               │  │
│  │ 4. 交互模式分发层                                             │  │
│  │    ├── 非TTY模式 (管道输入)                                   │  │
│  │    └── TTY模式 (交互式终端)                                   │  │
│  │ 5. 资源清理层 (finally)                                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

模块依赖关系：
├── agent_loop        → 执行Agent单轮推理
├── cli_commands      → 处理本地CLI命令
├── config            → 加载运行时配置
├── history           → 管理对话历史
├── local_tool_shortcuts → 解析工具快捷调用
├── manage_cli        → 处理管理命令
├── model_registry    → 创建模型适配器
├── permissions       → 权限管理
├── prompt            → 构建系统提示词
├── tools             → 工具注册表
├── tooling           → 工具执行上下文
├── tui               → 终端UI组件
├── tty_app           → TTY交互式应用
└── workspace         → 工作路径解析
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

# 核心业务模块导入
from minicode.agent_loop import run_agent_turn  # Agent推理循环
from minicode.cli_commands import try_handle_local_command  # CLI命令处理
from minicode.config import load_runtime_config  # 运行时配置加载
from minicode.history import load_history_entries, save_history_entries  # 对话历史
from minicode.local_tool_shortcuts import parse_local_tool_shortcut  # 工具快捷调用解析
from minicode.manage_cli import maybe_handle_management_command  # 管理命令处理
from minicode.model_registry import create_model_adapter  # 模型适配器工厂
from minicode.permissions import PermissionManager  # 权限管理器
from minicode.prompt import build_system_prompt  # 系统提示词构建
from minicode.tools import create_default_tool_registry  # 工具注册表
from minicode.tooling import ToolContext  # 工具执行上下文
from minicode.tui.transcript import format_transcript_text  # 对话记录格式化
from minicode.tui.types import TranscriptEntry  # 对话记录类型
from minicode.tty_app import run_tty_app  # TTY应用入口
from minicode.workspace import resolve_tool_path  # 工作路径解析


def _handle_local_command(user_input: str, tools) -> str | None:
    """处理本地命令（非AI调用的内置命令）

    职责：
    - 处理 /tools 命令：列出所有可用工具
    - 委托给 try_handle_local_command 处理其他本地命令

    Args:
        user_input: 用户输入的命令
        tools: 工具注册表实例

    Returns:
        命令执行结果字符串，或None表示未处理
    """
    if user_input == "/tools":
        return "\n".join(f"{tool.name}: {tool.description}" for tool in tools.list())
    local_result = try_handle_local_command(user_input, tools=tools, cwd=str(Path.cwd()))
    return local_result


def _render_banner(runtime: dict | None, cwd: str, permission_summary: list[str], counts: dict[str, int]) -> str:
    """渲染启动横幅（ASCII艺术风格）

    职责：
    - 显示应用名称和版本信息
    - 显示当前配置的模型名称
    - 显示当前工作目录
    - 显示权限摘要（最多2条）
    - 显示技能/服务器/对话统计

    Args:
        runtime: 运行时配置字典
        cwd: 当前工作目录路径
        permission_summary: 权限摘要列表
        counts: 统计信息字典（skillCount, mcpCount, transcriptCount）

    Returns:
        格式化的横幅字符串
    """
    model = runtime["model"] if runtime else "unconfigured"
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  🤖 MiniCode Python - Your Terminal Coding Assistant    ║",
        "╠══════════════════════════════════════════════════════════╣",
        f"║  Model: {model:<46} ║",
        f"║  CWD: {cwd:<50} ║",
    ]
    if permission_summary:
        for perm in permission_summary[:2]:  # 只显示前2个权限摘要
            lines.append(f"║  {perm:<60} ║")
    lines.append("╠══════════════════════════════════════════════════════════╣")
    lines.append(
        f"║  📊 Skills: {counts['skillCount']:>2} | MCP Servers: {counts['mcpCount']:>2} | "
        f"Transcript: {counts['transcriptCount']:>3} ║"
    )
    lines.append("╚══════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def _render_quick_start() -> str:
    """渲染快速入门指南

    职责：
    - 展示常用命令快捷方式
    - 提供使用示例
    - 帮助用户快速上手

    Returns:
        格式化的快速入门字符串
    """
    return """
💡 Quick Start Guide:
  📝 Edit files:     edit_file.py or patch_file.py
  🔍 Search code:    /grep <pattern> or grep_files tool
  🏃 Run commands:   /cmd <command> or run_command tool
  🧠 Think deeply:   Use sequential_thinking MCP tool
  📚 View skills:    /skills
  ❓ Get help:       /help

🚀 Try saying:
  "帮我分析这个项目的结构"
  "用 TDD 方式实现 XX 功能"
  "系统性地调试这个 bug"
  "帮我写个技术方案"
"""


def _append_transcript(transcript: list[TranscriptEntry], **kwargs) -> None:
    """向对话记录追加条目

    职责：
    - 自动生成递增的条目ID
    - 封装TranscriptEntry对象创建

    Args:
        transcript: 对话记录列表
        **kwargs: TranscriptEntry的字段参数（kind, body, toolName, status等）
    """
    transcript.append(TranscriptEntry(id=len(transcript) + 1, **kwargs))


def _make_cli_permission_prompt():
    """创建CLI权限提示回调函数

    职责：
    - 为非TTY环境提供简单的权限确认机制
    - 支持多选和单选两种权限请求方式
    - 返回标准化的决策响应（allow_once/deny_once）

    Returns:
        权限提示回调函数
    """

    def _prompt(request: dict) -> dict:
        print(f"\n{request.get('summary', 'Permission Request')}")
        choices = request.get("choices", [])
        if choices:
            for choice in choices:
                print(f"  [{choice.get('key', '')}] {choice.get('label', '')}")
            answer = input("Choose: ").strip()
            for choice in choices:
                if answer == choice.get("key"):
                    return {"decision": choice.get("decision", "allow_once")}
        answer = input("Allow? (y/n): ").strip().lower()
        return {"decision": "allow_once" if answer in ("y", "yes") else "deny_once"}

    return _prompt


def _configure_stdio_for_unicode() -> None:
    """配置标准输入输出为UTF-8编码

    职责：
    - 确保stdout/stderr支持Unicode字符（如emoji、中文）
    - 处理编码错误时使用replace策略
    - 兼容不同Python版本和终端环境
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _save_transcript_file(cwd: str, permissions, transcript: list[TranscriptEntry], output_path: str) -> str:
    """保存对话记录到文件

    职责：
    - 解析并验证目标路径（通过权限检查）
    - 自动创建必要的父目录
    - 将对话记录格式化为文本并写入

    Args:
        cwd: 当前工作目录
        permissions: 权限管理器实例
        transcript: 对话记录列表
        output_path: 输出文件路径

    Returns:
        实际保存的文件路径
    """
    target = resolve_tool_path(ToolContext(cwd=cwd, permissions=permissions), output_path, "write")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_transcript_text(transcript), encoding="utf-8")
    return str(target)


def main() -> None:
    """MiniCode Python 主入口函数

    执行流程：
    ┌────────────────────────────────────────────────────────────┐
    │ 1. 环境初始化                                             │
    │    └─ 配置UTF-8编码                                        │
    │ 2. 参数解析                                               │
    │    └─ 处理命令行参数                                        │
    │ 3. 前置任务处理                                           │
    │    ├─ 日志初始化                                          │
    │    ├─ 配置验证 (--validate-config)                         │
    │    ├─ 安装程序 (--install)                                │
    │    └─ 管理命令处理                                         │
    │ 4. 核心服务初始化                                         │
    │    ├─ 加载运行时配置                                       │
    │    ├─ 初始化权限管理器                                     │
    │    ├─ 创建工具注册表                                       │
    │    ├─ 创建模型适配器                                       │
    │    ├─ 初始化上下文管理器                                   │
    │    ├─ 初始化内存管理器                                     │
    │    ├─ 初始化用户配置管理器                                 │
    │    └─ 初始化应用状态存储                                   │
    │ 5. 交互循环                                               │
    │    ├─ 非TTY模式：处理管道输入                              │
    │    └─ TTY模式：启动交互式终端                              │
    │ 6. 资源清理 (finally)                                     │
    │    └─ 释放工具资源                                        │
    └────────────────────────────────────────────────────────────┘
    """
    # ========== 阶段1: 环境初始化 ==========
    _configure_stdio_for_unicode()

    # ========== 阶段2: 参数解析 ==========
    parser = argparse.ArgumentParser(
        description="MiniCode Python - A lightweight terminal coding assistant",
        add_help=True,
    )
    # 会话管理参数
    parser.add_argument(
        "--resume",
        nargs="?",
        const="latest",
        default=None,
        metavar="SESSION_ID",
        help="Resume a previous session (use 'latest' or session ID)",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all saved sessions and exit",
    )
    parser.add_argument(
        "--session",
        default=None,
        metavar="SESSION_ID",
        help="Start with a specific session ID",
    )
    # 配置管理参数
    parser.add_argument(
        "--install",
        action="store_true",
        help="Run the interactive installer",
    )
    parser.add_argument(
        "--validate-config",
        "--valid-config",
        action="store_true",
        help="Validate configuration and exit",
    )
    # 日志配置参数
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: WARNING)",
    )

    args, remaining_argv = parser.parse_known_args()
    if remaining_argv and not any(not arg.startswith("--") for arg in remaining_argv):
        parser.error(f"unrecognized arguments: {' '.join(remaining_argv)}")

    # ========== 阶段3: 前置任务处理 ==========
    # 初始化日志系统（延迟导入优化启动速度）
    from minicode.logging_config import setup_logging
    setup_logging(level=args.log_level)

    # 配置验证（--validate-config）
    if args.validate_config:
        from minicode.config import format_config_diagnostic
        print(format_config_diagnostic())
        return

    # 安装程序（--install）
    if args.install:
        from minicode.install import main as install_main
        install_main()
        return

    cwd = str(Path.cwd())
    argv = remaining_argv

    # 管理命令处理（如 install-skill, list-skills 等）
    management_argv = [a for a in argv if not a.startswith("--")]
    if maybe_handle_management_command(cwd, management_argv):
        return

    # ========== 阶段4: 核心服务初始化 ==========
    # 加载运行时配置（包含模型信息、环境变量等）
    runtime = None
    try:
        runtime = load_runtime_config(cwd)
    except Exception as e:  # noqa: BLE001
        runtime = None
        print(
            f"⚠️  Warning: Failed to load runtime config: {e}\n",
            file=sys.stderr,
        )
        print(
            "🔧 How to fix this:\n"
            "  1. Set your model name: export ANTHROPIC_MODEL=claude-sonnet-4-20250514\n"
            "  2. Set your API key: export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  3. Or edit ~/.mini-code/settings.json:\n"
            '     {"model": "claude-sonnet-4-20250514", "env": {"ANTHROPIC_API_KEY": "sk-ant-..."}}\n'
            "  4. Restart MiniCode\n\n"
            "📖 For more info: https://github.com/QUSETIONS/MiniCode-Python\n"
            "   Falling back to mock model for now...\n",
            file=sys.stderr,
        )

    # 初始化权限管理器和工具注册表
    prompt_handler = _make_cli_permission_prompt() if sys.stdin.isatty() else None
    tools = create_default_tool_registry(cwd, runtime=runtime)  # 工具注册中心
    permissions = PermissionManager(cwd, prompt=prompt_handler)  # 权限管理

    # 创建模型适配器（统一模型注册表）
    force_mock = runtime is None
    model = create_model_adapter(
        model=runtime.get("model", "") if runtime else "",
        tools=tools,
        runtime=runtime,
        force_mock=force_mock,
    )

    # 初始化上下文管理器（管理Token使用和上下文窗口）
    from minicode.context_manager import ContextManager
    from minicode.logging_config import get_logger
    logger = get_logger("main")
    context_mgr = None
    if runtime:
        context_mgr = ContextManager(model=runtime.get("model", "default"))
        logger.info("Context manager initialized for model: %s", runtime.get("model", "unknown"))

    # 初始化内存管理器（跨会话知识保留）
    from minicode.memory import MemoryManager
    memory_mgr = MemoryManager(project_root=Path(cwd))
    logger.info("Memory manager initialized")

    # 初始化用户配置管理器（用户偏好设置）
    from minicode.user_profile import UserProfileManager
    profile_manager = UserProfileManager(cwd=cwd)
    profile_manager.load_merged()
    logger.info("User profile manager initialized (global=%s, project=%s)",
                profile_manager.global_path.exists(),
                profile_manager.project_path.exists())

    # 初始化应用状态存储（全局状态管理，灵感来自Claude Code的Zustand）
    from minicode.state import create_app_store
    app_store = create_app_store(
        initial={
            "session_id": args.session or "new",
            "workspace": cwd,
            "model": runtime.get("model", "mock") if runtime else "mock",
        }
    )
    logger.info("Store initialized with session: %s", app_store.get_state().session_id)

    # ========== 阶段5: 消息和UI初始化 ==========
    # 构建初始消息（系统提示词）
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                    "memory_context": memory_mgr.get_relevant_context(),  # 注入记忆上下文
                },
            ),
        }
    ]
    history = load_history_entries()  # 加载历史记录
    transcript: list[TranscriptEntry] = []  # 初始化对话记录

    # 显示启动横幅
    print(
        _render_banner(
            runtime,
            cwd,
            permissions.get_summary(),
            {
                "transcriptCount": 0,
                "messageCount": len(messages),
                "skillCount": len(tools.get_skills()),
                "mcpCount": len(tools.get_mcp_servers()),
            },
        )
    )

    # 显示快速入门指南（非TTY环境或配置显示时）
    if not sys.stdin.isatty() or os.environ.get("MINI_CODE_SHOW_GUIDE", "1") == "1":
        print(_render_quick_start())
    else:
        print("")

    # ========== 阶段6: 交互循环 ==========
    try:
        # 非TTY模式（管道输入，如 echo "prompt" | minicode）
        if not sys.stdin.isatty():
            for raw_input in sys.stdin:
                user_input = raw_input.strip()
                if not user_input:
                    continue

                # 命令路由优先级：
                # 1. 退出命令
                if user_input == "/exit":
                    break

                # 2. 保存对话记录命令
                if user_input.startswith("/transcript-save "):
                    output_path = user_input[len("/transcript-save "):].strip()
                    if not output_path:
                        print("Usage: /transcript-save <path>")
                        continue
                    saved_path = _save_transcript_file(cwd, permissions, transcript, output_path)
                    print(f"Saved transcript to {saved_path}")
                    continue

                # 3. 内存命令（记忆管理）
                memory_result = memory_mgr.handle_user_memory_input(user_input)
                if memory_result is not None:
                    _append_transcript(transcript, kind="user", body=user_input)
                    _append_transcript(transcript, kind="assistant", body=memory_result)
                    print(memory_result)
                    continue

                # 4. 本地命令（/tools, /help等）
                local_result = _handle_local_command(user_input, tools)
                if local_result is not None:
                    _append_transcript(transcript, kind="user", body=user_input)
                    _append_transcript(transcript, kind="assistant", body=local_result)
                    print(local_result)
                    continue

                # 5. 工具快捷调用（如 grep:pattern）
                shortcut = parse_local_tool_shortcut(user_input)
                if shortcut is not None:
                    _append_transcript(transcript, kind="user", body=user_input)
                    result = tools.execute(
                        shortcut["toolName"],
                        shortcut["input"],
                        context=ToolContext(cwd=cwd, permissions=permissions),
                    )
                    _append_transcript(
                        transcript,
                        kind="tool",
                        body=result.output,
                        toolName=shortcut["toolName"],
                        status="success" if result.ok else "error",
                    )
                    print(result.output)
                    continue

                # 6. AI对话（默认路由）
                _append_transcript(transcript, kind="user", body=user_input)
                messages.append({"role": "user", "content": user_input})
                history.append(user_input)
                save_history_entries(history)

                # 更新系统提示词（注入记忆上下文）
                messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(
                        cwd,
                        permissions.get_summary(),
                        {
                            "skills": tools.get_skills(),
                            "mcpServers": tools.get_mcp_servers(),
                            "memory_context": memory_mgr.get_relevant_context(query=user_input),
                        },
                    ),
                }

                # 执行Agent推理循环
                permissions.begin_turn()
                messages = run_agent_turn(
                    model=model,
                    tools=tools,
                    messages=messages,
                    cwd=cwd,
                    permissions=permissions,
                    store=app_store,
                    context_manager=context_mgr,
                    runtime=runtime,
                )
                permissions.end_turn()

                # 记录上下文使用统计
                if context_mgr:
                    stats = context_mgr.get_stats()
                    logger.debug("After turn: %d tokens (%.0f%%)", stats.total_tokens, stats.usage_percentage)

                # 提取并显示AI响应
                last_assistant = next((message for message in reversed(messages) if message["role"] == "assistant"),
                                      None)
                if last_assistant:
                    _append_transcript(transcript, kind="assistant", body=last_assistant["content"])
                    print(last_assistant["content"])
            return

        # TTY模式（交互式终端）
        run_tty_app(
            runtime=runtime,
            tools=tools,
            model=model,
            messages=messages,
            cwd=cwd,
            permissions=permissions,
            resume_session=args.resume,
            list_sessions_only=args.list_sessions,
            memory_manager=memory_mgr,
            context_manager=context_mgr,
        )

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Shutting down gracefully...")

    # ========== 阶段7: 资源清理 ==========
    finally:
        logger = get_logger("main")
        logger.info("Shutting down...")

        # 释放工具资源（关闭MCP连接等）
        try:
            tools.dispose()
            logger.info("Tools disposed successfully")
        except Exception as e:
            logger.warning("Error disposing tools: %s", e)

        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()