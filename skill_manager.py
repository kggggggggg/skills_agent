"""
技能管理器

负责从 .skills 目录自动加载技能
"""
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    location: str
    content: Optional[str] = None


class SkillManager:
    def __init__(self, extensions_dir: Optional[str] = None):
        # Default skills directory is `<repo>/.skills`.
        self.extensions_dir = Path(extensions_dir) if extensions_dir else Path(__file__).parent / ".skills"
        self._skills: dict[str, Skill] = {}
        # identifier -> canonical skill name
        # identifiers include: skill name, folder name, location (raw/resolved)
        self._index: dict[str, str] = {}
        self._loaded_skills: set[str] = set()
        self._auto_load_skills()

    def _auto_load_skills(self):
        if not self.extensions_dir.exists():
            return

        for skill_dir in self.extensions_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                content = skill_file.read_text(encoding="utf-8")
                metadata = self._parse_front_matter(content)

                skill_name = metadata.get("name", skill_dir.name)
                skill = Skill(
                    name=skill_name,
                    description=metadata.get("description", ""),
                    location=str(skill_file),
                )
                self._skills[skill_name] = skill

                # Build lookup index for more flexible identifiers
                self._index[skill_name] = skill_name
                self._index[skill_dir.name] = skill_name
                self._index[str(skill_file)] = skill_name
                try:
                    self._index[str(skill_file.resolve())] = skill_name
                except Exception:
                    pass
            except Exception:
                continue

    def _parse_front_matter(self, content: str) -> dict:
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        metadata = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return metadata

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def load_skill(self, skill_name: str) -> str:
        identifier = (skill_name or "").strip()
        canonical = self._index.get(identifier)

        if canonical is None:
            # If the caller passes a path, try normalizing it to a resolved location.
            # This enables `load_skill(<location>)` from the skills list.
            try:
                candidate = Path(identifier).expanduser()
                if candidate.exists() or "/" in identifier or "\\" in identifier:
                    canonical = self._index.get(str(candidate.resolve()))
            except Exception:
                canonical = None

        if canonical is None or canonical not in self._skills:
            return f"<skill-error>技能 '{skill_name}' 不存在</skill-error>"

        if canonical in self._loaded_skills:
            return f"<skill-already-loaded>{canonical}</skill-already-loaded>"

        skill = self._skills[canonical]
        try:
            content = Path(skill.location).read_text(encoding="utf-8")
            skill.content = content
            self._loaded_skills.add(canonical)
            return f'<skill-loaded name="{canonical}">\n{content}\n</skill-loaded>'
        except FileNotFoundError:
            return f"<skill-error>技能文件不存在: {skill.location}</skill-error>"
        except Exception as e:
            return f"<skill-error>加载技能失败: {str(e)}</skill-error>"


skill_manager = SkillManager()
