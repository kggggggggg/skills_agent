from __future__ import annotations

import time
from typing import Any


class ModelCallTracer:
    """
    打印每次“实际模型调用”的分割线（配合 before_model/after_model）。

    - 计数：每次 before_model +1
    - 耗时：before_model 记录 perf_counter，after_model 计算差值
    - token：尽量从 state["messages"] 最后一个 AIMessage 的 metadata 中提取
    """

    def __init__(self, *, console: Any, printer: Any):
        self.console = console
        self.printer = printer
        self.model_call_count = 0
        self.model_call_started_at: float | None = None

    def reset(self):
        self.model_call_count = 0
        self.model_call_started_at = None

    def before(self) -> None:
        self.model_call_count += 1
        self.model_call_started_at = time.perf_counter()
        self.printer.close()
        self.console.rule(f"Model Call #{self.model_call_count} START", style="dim")

    def after(self, state: dict) -> None:
        elapsed = None
        if isinstance(self.model_call_started_at, (int, float)):
            elapsed = time.perf_counter() - self.model_call_started_at

        in_tokens, out_tokens, total_tokens = self._extract_token_usage(state)

        self.printer.close()
        parts: list[str] = []
        if elapsed is not None:
            parts.append(f"{elapsed:.2f}s")
        if any(v is not None for v in (in_tokens, out_tokens, total_tokens)):
            parts.append(
                f"tok in={in_tokens or '?'} out={out_tokens or '?'} total={total_tokens or '?'}"
            )
        suffix = f" ({' | '.join(parts)})" if parts else ""
        self.console.rule(f"Model Call #{self.model_call_count} END{suffix}", style="dim")

    def _extract_token_usage(self, state: dict) -> tuple[int | None, int | None, int | None]:
        messages = state.get("messages") or []
        last_ai = None
        for msg in reversed(messages):
            if type(msg).__name__ == "AIMessage":
                last_ai = msg
                break
        if last_ai is None:
            return None, None, None

        usage = (
            getattr(last_ai, "usage_metadata", None)
            or getattr(last_ai, "response_metadata", None)
            or {}
        )
        if not isinstance(usage, dict):
            return None, None, None

        token_usage = (
            usage.get("token_usage")
            if isinstance(usage.get("token_usage"), dict)
            else usage
        )

        in_tokens = (
            token_usage.get("input_tokens")
            or token_usage.get("prompt_tokens")
            or token_usage.get("input")
            or token_usage.get("prompt")
        )
        out_tokens = (
            token_usage.get("output_tokens")
            or token_usage.get("completion_tokens")
            or token_usage.get("output")
            or token_usage.get("completion")
        )
        total_tokens = token_usage.get("total_tokens") or token_usage.get("total")

        def _to_int(v: Any) -> int | None:
            try:
                return int(v)
            except Exception:
                return None

        return _to_int(in_tokens), _to_int(out_tokens), _to_int(total_tokens)

