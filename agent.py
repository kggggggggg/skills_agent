from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import after_model, before_model
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from rich.console import Console

from prompt_manager import prompt_manager
from tools import get_all_tools
from utils.debug_commands import DebugCommands
from utils.langgraph_stream_printer import LangChainStreamPrinter
from utils.model_call_tracer import ModelCallTracer


def load_env() -> None:
    load_dotenv(".env")


def get_config() -> RunnableConfig:
    thread_id = (os.getenv("MODEL_THREAD_ID") or "1").strip() or "1"
    return {"configurable": {"thread_id": thread_id}}


def build_llm() -> Any:
    def get_thinking_config() -> dict[str, Any] | None:
        mode = (os.getenv("MODEL_THINKING") or "").strip().lower()
        if mode in {"", "0", "false", "off", "disabled", "no"}:
            return None
        if mode in {"1", "true", "on", "enabled", "yes"}:
            try:
                budget = int(os.getenv("MODEL_THINKING_BUDGET") or "10000")
            except Exception:
                budget = 10000
            return {"budget_tokens": budget, "type": "enabled"}
        return None

    llm_kwargs: dict[str, Any] = {
        "api_key": os.getenv("MODEL_API_KEY"),
        "model": os.getenv("MODEL_NAME"),
        "base_url": os.getenv("MODEL_BASE_URL"),
        "model_provider": os.getenv("MODEL_PROVIDER"),
    }
    thinking_cfg = get_thinking_config()
    if thinking_cfg:
        llm_kwargs["thinking"] = thinking_cfg
    return init_chat_model(**llm_kwargs)


def build_middlewares(tracer: ModelCallTracer):
    @before_model
    def model_call_start(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        tracer.before()
        return {}

    @after_model
    def model_call_end(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        tracer.after(state)
        return {}

    return [model_call_start, model_call_end]


def build_agent(llm: Any, tracer: ModelCallTracer):
    merged_prompt = prompt_manager.get_system_prompt()
    return create_agent(
        llm,
        tools=get_all_tools(),
        system_prompt=SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": merged_prompt,
                    "cache_control": {"type": "ephemeral"}  # 缓存！
                }
            ]
        ),
        middleware=build_middlewares(tracer),
        checkpointer=InMemorySaver(),
    )


def main() -> None:
    load_env()

    console = Console()
    printer = LangChainStreamPrinter(console)
    tracer = ModelCallTracer(console=console, printer=printer)

    llm = build_llm()
    agent = build_agent(llm, tracer)

    config = get_config()
    base_prompt, skills_prompt = prompt_manager.get_system_prompts()
    merged_prompt = prompt_manager.get_system_prompt()

    printer.print_welcome("输入 'exit'/'quit' 退出；/prompt 查看系统提示词；/history 查看历史消息；/clear 清空历史")
    debug = DebugCommands(
        printer=printer,
        console=console,
        agent=agent,
        config=config,
        base_prompt=base_prompt,
        skills_prompt=skills_prompt,
        merged_prompt=merged_prompt,
        on_clear=tracer.reset,
    )

    while True:
        try:
            user_input = printer.get_input("👤 请输入").strip()

            if user_input.lower() in ["exit", "quit", "退出"]:
                printer.print_goodbye()
                break

            if not user_input:
                continue

            if debug.handle(user_input):
                continue

            printer.reset()
            printer.print_user_input(user_input)

            chunks = agent.stream(
                {"messages": HumanMessage(content=user_input)},
                config,
                stream_mode="messages",
            )

            for message, metadata in chunks:
                printer.process_message(message, metadata)

            printer.close()
            console.print()

        except KeyboardInterrupt:
            printer.print_goodbye()
            break
        except Exception as e:
            printer.print_error(str(e))


if __name__ == "__main__":
    main()
