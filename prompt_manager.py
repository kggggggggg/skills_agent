"""
Prompt 管理器

负责加载固定的 base prompt 和动态生成技能列表 prompt
"""
from pathlib import Path
from typing import Optional, Tuple
from skill_manager import SkillManager
from jinja2 import Environment


class PromptManager:
    def __init__(
            self,
            prompts_dir: Optional[str] = None,
            extensions_dir: Optional[str] = None
    ):
        self.prompts_dir = Path(prompts_dir) if prompts_dir else Path(__file__).parent / "prompts"
        self.skill_manager = SkillManager(extensions_dir)

    def get_system_prompt(self) -> str:
        """获取完整的 system prompt（固定 + 动态拼接）"""
        base_prompt, skills_prompt = self.get_system_prompts()
        parts = [p.strip() for p in (base_prompt, skills_prompt) if p and p.strip()]
        return "\n\n".join(parts)

    def get_system_prompts(self) -> Tuple[str, str]:
        """获取分离的两个 system prompt"""
        return self.get_base_prompt(), self.get_skills_prompt()

    def get_base_prompt(self) -> str:
        """获取固定的基础 prompt"""
        base_file = self.prompts_dir / "system_prompt.md"
        if base_file.exists():
            return base_file.read_text(encoding="utf-8").strip()
        return ""

    def get_skills_prompt(self) -> str:
        """获取动态生成的技能列表 prompt"""
        skills = self.skill_manager.list_skills()
        if not skills:
            return ""

        template_file = self.prompts_dir / "skills_template.md"
        if not template_file.exists():
            return ""

        env = Environment(autoescape=False)
        template = env.from_string(template_file.read_text(encoding="utf-8"))
        return template.render(skills=skills).strip()


prompt_manager = PromptManager()
