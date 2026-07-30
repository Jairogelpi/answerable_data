from __future__ import annotations

from answerable.planning.errors import DuplicateSkill, UnknownCheckType
from answerable.planning.skills import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[tuple[str, str], Skill] = {}

    def register(self, skill: Skill) -> None:
        key = (skill.skill_id, skill.version)
        if key in self._skills:
            raise DuplicateSkill(f"skill already registered: {skill.skill_id}@{skill.version}")
        self._skills[key] = skill

    def applicable(self, analysis_type: str) -> tuple[Skill, ...]:
        return tuple(
            skill
            for key, skill in sorted(self._skills.items())
            if analysis_type in skill.applies_to
        )


class CheckTypeRegistry:
    def __init__(self, check_types: tuple[str, ...]) -> None:
        self._check_types = frozenset(check_types)

    def require(self, check_type: str) -> None:
        if check_type not in self._check_types:
            raise UnknownCheckType(f"unknown check type: {check_type}")
