"""
LangGraph/LangChain 流式消息适配层。

这里的职责是把 LangGraph 的 stream_mode="messages" 输出（message, metadata）
解析成对 StreamPrinter（渲染器）的调用。

通用的终端格式渲染逻辑在 utils/stream_printer.py（StreamPrinter）中。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from rich.console import Console

from .stream_printer import StreamPrinter


class LangChainStreamPrinter:
    """
    LangChain/LangGraph 的 messages 流式输出适配器。

    设计原则：不继承 StreamPrinter，而是组合一个渲染器实例（StreamPrinter），
    本类只负责“解析 message → 调用渲染器”。
    """

    def __init__(self, console: Optional[Console] = None, width: Optional[int] = None):
        self._renderer = StreamPrinter(console, width=width)
        self.tool_calls: dict[int, dict[str, str]] = {}
        # contents[idx][chunk_type] = 已看到的累计内容
        self.contents: dict[int, dict[str, str]] = {}
        self.content_current_idx: Optional[int] = None

    def reset(self):
        """重置状态（通常每次用户输入前调用）"""
        self._renderer.close()
        self.tool_calls = {}
        self.contents = {}
        self.content_current_idx = None

    # ---- renderer passthroughs (agent/debug code depends on these) ----
    def close(self):
        self._renderer.close()

    def get_input(self, prompt: str = "👤 请输入") -> str:
        return self._renderer.get_input(prompt)

    def print_welcome(self, subtitle: str = "输入 'exit' 或 'quit' 退出程序"):
        return self._renderer.print_welcome(subtitle)

    def print_goodbye(self, message: str = "再见! 👋"):
        return self._renderer.print_goodbye(message)

    def print_error(self, error_msg: str):
        return self._renderer.print_error(error_msg)

    def print_user_input(self, user_input: str):
        return self._renderer.print_user_input(user_input)

    def print_tool_result(self, content: str, max_length: int = 500):
        return self._renderer.print_tool_result(content, max_length=max_length)

    def print_tool_call(self, name: str, args: Dict[str, Any]):
        return self._renderer.print_tool_call(name, args)

    def print_chunk(self, text: str, section_type: str = "text"):
        return self._renderer.print_chunk(text, section_type=section_type)

    def process_message(self, message: Any, metadata: Optional[Dict] = None):
        """
        处理 LangGraph 流式 message。

        Args:
            message: LangChain/LangGraph 消息对象（如 AIMessageChunk/ToolMessage）
            metadata: 目前不强依赖，保留用于未来扩展
        """
        msg_type = type(message).__name__

        if msg_type == "ToolMessage":
            self._renderer.print_tool_result(getattr(message, "content", ""))
            return

        self._process_tool_calls(message)
        self._process_content(message)

    def _process_tool_calls(self, message: Any):
        """处理 tool_call_chunks"""
        msg_type = type(message).__name__

        if msg_type != "AIMessageChunk":
            return

        if hasattr(message, "tool_call_chunks") and message.tool_call_chunks:
            for tc in message.tool_call_chunks:
                idx = tc.get("index", 0)
                if idx not in self.tool_calls:
                    self.tool_calls[idx] = {"name": "", "args": "", "id": ""}

                if tc.get("name"):
                    self.tool_calls[idx]["name"] += tc["name"]
                if tc.get("args"):
                    self.tool_calls[idx]["args"] += tc["args"]
                if tc.get("id"):
                    self.tool_calls[idx]["id"] = tc["id"]
            return

        # 没有更多 tool_call_chunks 但之前累计过，尝试落地打印
        if not self.tool_calls:
            return

        for tool_call in self.tool_calls.values():
            try:
                parsed_args = json.loads(tool_call["args"])
            except json.JSONDecodeError:
                continue
            self._renderer.print_tool_call(tool_call["name"], parsed_args)

        self.tool_calls = {}

    def _process_content(self, message: Any):
        """处理 message.content"""
        content = getattr(message, "content", None)
        if not content:
            return

        for mc in content:
            # 兼容：某些情况下 content 直接是 str
            if type(mc) == str:
                if not mc:
                    continue
                if self.content_current_idx is None:
                    self.content_current_idx = 0
                self._renderer.print_chunk(mc, "text")
                continue

            if not isinstance(mc, dict):
                continue

            idx = mc.get("index", 0)
            chunk_type = mc.get("type")
            if chunk_type not in ["thinking", "text"]:
                continue

            text = mc.get(chunk_type, "")
            if not text:
                continue

            # 切换区块（不同 index）
            if self.content_current_idx is not None and self.content_current_idx != idx:
                # 强制结束上一段边框：即使 section_type 相同，也要在 index 之间分割。
                self._renderer.close()

            if self.content_current_idx is None or self.content_current_idx != idx:
                self.content_current_idx = idx

            if idx not in self.contents:
                self.contents[idx] = {"thinking": "", "text": ""}

            prev = self.contents[idx].get(chunk_type, "")
            # 兼容两种流式：delta（增量）或 cumulative（累计到目前为止）
            if text.startswith(prev):
                delta = text[len(prev) :]
                self.contents[idx][chunk_type] = text
            else:
                delta = text
                self.contents[idx][chunk_type] = prev + text

            if not delta:
                continue

            self._renderer.print_chunk(delta, chunk_type)
