"""
流式输出管理器 - 用于美化 AI 流式输出的通用模块

支持：
- 带边框的流式内容输出
- 工具调用展示
- 多区块切换（思考/回复）
- 颜色主题
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich import box
from rich.cells import cell_len
from typing import Optional, Dict, Any
import json


class StreamPrinter:
    """流式输出管理器"""

    # 默认颜色主题
    DEFAULT_THEME = {
        "thinking": {
            "title": "🧠 AI 思考",
            "border": "bold magenta",
            "text": "magenta",
        },
        "text": {
            "title": "🤖 AI 回复",
            "border": "bold cyan",
            "text": "cyan",
        },
        "tool_call": {
            "title": "🔧 调用工具",
            "border": "bold yellow",
            "text": "white",
        },
        "tool_result": {
            "title": "📤 工具结果",
            "border": "bold blue",
            "text": "dim",
        },
        "user": {
            "title": "👤 用户",
            "border": "bold green",
            "text": "white",
        },
        "error": {
            "title": "❌ 错误",
            "border": "bold red",
            "text": "bold red",
        },
        "welcome": {
            "title": "🤖 交互式 AI Agent",
            "border": "bold cyan",
            "text": "cyan",
        },
    }

    def __init__(self, console: Optional[Console] = None, theme: Optional[Dict] = None, width: Optional[int] = None):
        """
        初始化流式输出管理器

        Args:
            console: Rich Console 实例，如果不提供则创建新的
            theme: 自定义颜色主题，如果不提供则使用默认主题
            width: 边框宽度，默认使用终端宽度
        """
        self.console = console or Console()
        self.theme = theme or self.DEFAULT_THEME
        self._current_section: Optional[str] = None
        self._section_idx: Optional[int] = None
        self._width = width or self.console.width or 80  # 使用终端宽度
        self._has_content = False  # 当前区块是否有任何输出（用于跳过开头空白等）
        self._line_open = False  # 当前行是否已输出左边框并处于行内
        self._line_cell_len = 0  # 当前行已输出内容的显示宽度（用于手动换行）
        self._ever_printed = False  # 是否已经输出过任何内容（用于区块之间留空行）
        self._printed_messages = set()  # 用于去重

    def _get_style(self, section_type: str) -> Dict[str, str]:
        """获取指定区块的样式配置"""
        return self.theme.get(section_type, self.theme["text"])

    def _print_header(self, section_type: str):
        """打印区块头部边框"""
        if self._current_section == section_type:
            return

        # 如果已有打开的区块，先关闭
        if self._current_section:
            self._print_footer()

        self._current_section = section_type
        self._has_content = False
        self._line_open = False
        self._line_cell_len = 0
        style = self._get_style(section_type)
        title = style["title"]
        border_style = style["border"]

        # 区块之间留一行空行，避免视觉上“挤在一起”
        if self._ever_printed:
            self.console.print()

        # 画满行 + 标题居中（避免 header 宽度计算误差导致自动换行）
        inner_width = max(0, self._width - 2)
        title_segment = f" {title} "
        title_width = Text(title_segment).cell_len

        if title_width >= inner_width:
            inner = title_segment
        else:
            remaining = inner_width - title_width
            left = remaining // 2
            right = remaining - left
            inner = ("─" * left) + title_segment + ("─" * right)

        header = f"╭{inner}╮"
        self.console.print(f"[{border_style}]{header}[/{border_style}]")
        self._ever_printed = True

    def _print_footer(self):
        """打印区块底部边框"""
        if not self._current_section:
            return

        # 若当前仍在行内，先换行，保证 footer 对齐
        if self._line_open:
            self.console.print()
            self._line_open = False
            self._line_cell_len = 0

        style = self._get_style(self._current_section)
        border_style = style["border"]
        footer = "╰" + "─" * (self._width - 2) + "╯"

        self.console.print(f"[{border_style}]{footer}[/{border_style}]")
        self._current_section = None
        self._has_content = False
        self._line_open = False
        self._line_cell_len = 0
        self._ever_printed = True

    def _print_line_prefix(self):
        """打印行前缀（左边框）"""
        if not self._current_section:
            return
        style = self._get_style(self._current_section)
        border_style = style["border"]
        self.console.print(f"[{border_style}]│[/{border_style}] ", end="")

    def _print_line_content(self, content: str):
        """打印一行内容"""
        if not self._current_section:
            return

        style = self._get_style(self._current_section)["text"]

        if self._line_open:
            self.console.print()
            self._line_open = False
            self._line_cell_len = 0

        self._print_line_prefix()
        self.console.print(content, end="", style=style)
        self.console.print()
        self._line_open = False
        self._line_cell_len = 0
        self._has_content = True

    def _stream_write(self, text: str, section_type: str):
        """以“只打印一次”的方式流式写入文本（逐字符但不回放整行）。"""
        if not text:
            return

        self._print_header(section_type)
        style = self._get_style(section_type)["text"]
        max_content_width = max(1, self._width - 4)  # "│ " 占 2 格；留 2 格余量避免自动折行

        for char in text:
            if char == "\n":
                # 跳过区块最开头的换行，避免 PyCharm 等环境出现“第一行空行”观感
                if not self._has_content and not self._line_open:
                    continue

                # 空行也要输出边框
                if not self._line_open:
                    self._print_line_prefix()
                self.console.print()
                self._line_open = False
                self._has_content = True
                self._line_cell_len = 0
                continue

            # 跳过区块最开头的空白，避免边框后面一堆无意义空格导致“格式错乱”观感
            if not self._has_content and not self._line_open and char.strip() == "":
                continue

            if not self._line_open:
                self._print_line_prefix()
                self._line_open = True
                self._has_content = True
                self._line_cell_len = 0

            char_width = cell_len(char)
            if self._line_cell_len + char_width > max_content_width:
                self.console.print()
                self._print_line_prefix()
                self._line_open = True
                self._line_cell_len = 0

            self.console.print(char, end="", style=style)
            self._line_cell_len += char_width

    def print_chunk(self, text: str, section_type: str = "text"):
        """
        打印流式内容块

        Args:
            text: 要打印的文本内容
            section_type: 区块类型 (thinking/text/tool_call/tool_result/user/error/welcome)
        """
        if not text:
            return

        self._stream_write(text, section_type)

    def print_tool_call(self, name: str, args: Dict[str, Any]):
        """
        打印工具调用信息

        Args:
            name: 工具名称
            args: 工具参数
        """
        # 关闭当前区块
        if self._current_section:
            self._print_footer()

        args_text = json.dumps(args, ensure_ascii=False, indent=2)
        syntax = Syntax(args_text, "json", theme="monokai", line_numbers=False)
        style = self._get_style("tool_call")

        self.console.print(Panel(
            syntax,
            title=f"[{style['border']}]{style['title']}: {name}[/{style['border']}]",
            box=box.ROUNDED,
            border_style=style["border"].replace("bold ", ""),
            padding=(1, 2)
        ))
        self._ever_printed = True

    def print_tool_result(self, content: str, max_length: int = 500):
        """
        打印工具调用结果

        Args:
            content: 结果内容
            max_length: 最大显示长度，超出则截断
        """
        # 关闭当前区块
        if self._current_section:
            self._print_footer()

        display_content = content[:max_length] + "..." if len(content) > max_length else content
        style = self._get_style("tool_result")

        self.console.print(Panel(
            Text(display_content, style=style["text"]),
            title=f"[{style['border']}]{style['title']}[/{style['border']}]",
            box=box.ROUNDED,
            border_style=style["border"].replace("bold ", ""),
            padding=(1, 2)
        ))
        self._ever_printed = True

    def print_user_input(self, user_input: str):
        """打印用户输入"""
        # 关闭当前区块
        if self._current_section:
            self._print_footer()

        style = self._get_style("user")
        self.console.print(Panel(
            Text(user_input),
            title=f"[{style['border']}]{style['title']}[/{style['border']}]",
            box=box.ROUNDED,
            border_style=style["border"].replace("bold ", ""),
            padding=(1, 2)
        ))
        self._ever_printed = True

    def print_welcome(self, subtitle: str = "输入 'exit' 或 'quit' 退出程序"):
        """打印欢迎信息"""
        style = self._get_style("welcome")
        welcome_text = Text()
        welcome_text.append(f"{style['title']}\n", style=style["border"])
        welcome_text.append(subtitle, style="dim")

        self.console.print(Panel(
            welcome_text,
            box=box.ROUNDED,
            border_style=style["border"].replace("bold ", ""),
            padding=(1, 2)
        ))
        self._ever_printed = True

    def print_goodbye(self, message: str = "再见! 👋"):
        """打印告别信息"""
        # 关闭当前区块
        if self._current_section:
            self._print_footer()

        style = self._get_style("welcome")
        self.console.print(Panel(
            Text(message, style=style["border"], justify="center"),
            box=box.ROUNDED,
            border_style=style["border"].replace("bold ", ""),
            padding=(1, 2)
        ))
        self._ever_printed = True

    def print_error(self, error_msg: str):
        """打印错误信息"""
        # 关闭当前区块
        if self._current_section:
            self._print_footer()

        style = self._get_style("error")
        self.console.print(Panel(
            Text(error_msg, style=style["text"]),
            title=f"[{style['border']}]{style['title']}[/{style['border']}]",
            box=box.ROUNDED,
            border_style=style["border"].replace("bold ", ""),
            padding=(1, 2)
        ))
        self._ever_printed = True

    def close(self):
        """关闭当前区块，清理状态"""
        if self._current_section:
            self._print_footer()
        self._current_section = None
        self._section_idx = None
        self._has_content = False
        self._line_open = False
        self._line_cell_len = 0

    def get_input(self, prompt: str = "👤 请输入") -> str:
        """获取用户输入"""
        # 关闭当前区块
        if self._current_section:
            self._print_footer()
        return self.console.input(f"\n[bold green]{prompt}:[/bold green] ")
