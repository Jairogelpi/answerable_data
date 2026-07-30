from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from answerable.domain.models import CheckSpec

if TYPE_CHECKING:
    from answerable.planning.planner import PlanningContext


@dataclass(frozen=True, slots=True)
class SkillProposal:
    checks: tuple[CheckSpec, ...]
    clarifications: tuple[str, ...] = ()


class Skill(ABC):
    skill_id: str
    version: str
    applies_to: frozenset[str]

    @abstractmethod
    def propose(self, context: PlanningContext) -> SkillProposal:
        raise NotImplementedError
