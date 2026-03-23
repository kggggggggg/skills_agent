from __future__ import annotations

import json
from typing import Any, Optional


class DebugCommands:
    """
    处理交互式 CLI 的内置调试命令。

    目标：让 agent.py 的主循环尽量清晰，只负责：
    - 读输入
    - 交给 DebugCommands 处理内置命令
    - 否则走 agent.stream(...)
    """

    def __init__(
        self,
        *,
        printer: Any,
        console: Any,
        agent: Any,
        config: dict,
        base_prompt: str,
        skills_prompt: str,
        on_clear: Optional[Any] = None,
        merged_prompt: Optional[str] = None,
    ):
        self.printer = printer
        self.console = console
        self.agent = agent
        self.config = config
        self.base_prompt = base_prompt
        self.skills_prompt = skills_prompt
        self.merged_prompt = merged_prompt or f"{base_prompt}\n\n{skills_prompt}".strip()
        self.on_clear = on_clear

    def handle(self, user_input: str) -> bool:
        text = (user_input or "").strip()
        if not text.startswith("/"):
            return False

        if text.startswith("/prompt"):
            _, *parts = text.split()
            mode = parts[0] if parts else "full"
            self.printer.print_tool_result(self._prompt_text(mode), max_length=20000)
            self.console.print()
            return True

        if text.startswith("/history"):
            checkpoint_tuple = (
                self.agent.checkpointer.get_tuple(self.config)
                if hasattr(self.agent, "checkpointer")
                else None
            )
            if not checkpoint_tuple:
                self.printer.print_tool_result("暂无历史消息（还没有产生 checkpoint）。", max_length=2000)
            else:
                self.printer.print_tool_result(self._format_history_from_checkpoint(checkpoint_tuple), max_length=20000)
            self.console.print()
            return True

        if text in {"/clear", "/clear-history", "/reset"}:
            self.printer.print_tool_result(self._clear_history(), max_length=2000)
            if callable(self.on_clear):
                try:
                    self.on_clear()
                except Exception:
                    pass
            self.console.print()
            return True

        if text in {"/help", "/?"}:
            self.printer.print_tool_result(self._help_text(), max_length=2000)
            self.console.print()
            return True

        return False

    def _help_text(self) -> str:
        return "\n".join(
            [
                "内置调试命令：",
                "- /prompt            查看合并后的 system prompt",
                "- /prompt base       只看基础 prompt",
                "- /prompt skills     只看 skills 列表 prompt",
                "- /history           查看当前 thread 的历史消息（来自 checkpointer）",
                "- /clear             清空当前 thread 的历史消息",
            ]
        )

    def _prompt_text(self, mode: str = "full") -> str:
        mode_norm = (mode or "full").strip().lower()
        if mode_norm in {"base"}:
            return self.base_prompt
        if mode_norm in {"skills"}:
            return self.skills_prompt
        if mode_norm in {"full", "all", "merged"}:
            return self.merged_prompt
        return f"未知参数: {mode}\n可用: /prompt, /prompt base, /prompt skills"

    def _format_history_from_checkpoint(self, checkpoint_tuple: Any) -> str:
        checkpoint = getattr(checkpoint_tuple, "checkpoint", None) or checkpoint_tuple.get("checkpoint")
        channel_values = checkpoint.get("channel_values", {}) if isinstance(checkpoint, dict) else {}

        messages = channel_values.get("messages")
        if not messages:
            keys = ", ".join(sorted(channel_values.keys()))
            return f"未找到 messages 历史。当前 checkpoint channels: {keys or '(empty)'}"

        lines: list[str] = []
        for msg in messages:
            msg_type = type(msg).__name__
            role = {
                "HumanMessage": "user",
                "AIMessage": "assistant",
                "SystemMessage": "system",
                "ToolMessage": "tool",
            }.get(msg_type, msg_type)

            content = getattr(msg, "content", msg)
            content_str = self._content_to_str(content)
            lines.append(f"[{role}] {content_str}")

        return "\n".join(lines)

    def _content_to_str(self, content: Any) -> str:
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    chunks.append(
                        item.get("text")
                        or item.get("thinking")
                        or json.dumps(item, ensure_ascii=False)
                    )
                else:
                    chunks.append(str(item))
            text = "".join(chunks).strip()
        else:
            text = str(content).strip()

        return text if text else "(empty)"

    def _clear_history(self) -> str:
        cp = getattr(self.agent, "checkpointer", None)
        thread_id = self.config.get("configurable", {}).get("thread_id")
        if not cp or not thread_id:
            return "无法清空：缺少 checkpointer 或 thread_id。"

        cleared_any = False

        # InMemorySaver: checkpoints stored in `storage[thread_id][checkpoint_ns][checkpoint_id]`.
        try:
            if hasattr(cp, "storage") and thread_id in cp.storage:
                cp.storage.pop(thread_id, None)
                cleared_any = True
        except Exception:
            pass

        # Pending writes indexed by (thread_id, checkpoint_ns, checkpoint_id)
        try:
            if hasattr(cp, "writes"):
                keys = [
                    k
                    for k in list(cp.writes.keys())
                    if isinstance(k, tuple) and k and k[0] == thread_id
                ]
                for k in keys:
                    cp.writes.pop(k, None)
                if keys:
                    cleared_any = True
        except Exception:
            pass

        return f"已清空历史（thread_id={thread_id}）。" if cleared_any else f"暂无可清空的历史（thread_id={thread_id}）。"
