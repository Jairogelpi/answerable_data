from __future__ import annotations

from dataclasses import dataclass

from answerable.domain.models import CheckSpec
from answerable.planning.errors import CyclicCheckPlan, DuplicateCheck, MissingDependency
from answerable.planning.registry import CheckTypeRegistry, SkillRegistry

_DISCLOSURE_ORDER = {
    "none": 0,
    "metadata_only": 1,
    "sample_redacted": 2,
    "raw_rows": 3,
}


@dataclass(frozen=True, slots=True)
class PlanningContext:
    analysis_type: str


@dataclass(frozen=True, slots=True)
class PlanPreview:
    estimated_cost: int
    maximum_disclosure: str
    check_count: int


@dataclass(frozen=True, slots=True)
class PlannedCheckPlan:
    checks: tuple[CheckSpec, ...]
    clarifications: tuple[str, ...]
    preview: PlanPreview


class CheckPlanner:
    def __init__(
        self,
        skills: SkillRegistry,
        check_types: CheckTypeRegistry,
        *,
        mandatory_checks: tuple[CheckSpec, ...] = (),
    ) -> None:
        self._skills = skills
        self._check_types = check_types
        self._mandatory_checks = mandatory_checks

    def build(self, context: PlanningContext) -> PlannedCheckPlan:
        checks = list(self._mandatory_checks)
        clarifications: list[str] = []
        for skill in self._skills.applicable(context.analysis_type):
            proposal = skill.propose(context)
            checks.extend(proposal.checks)
            clarifications.extend(proposal.clarifications)
        by_id: dict[str, CheckSpec] = {}
        for check in checks:
            self._check_types.require(check.check_type)
            if check.check_id in by_id:
                raise DuplicateCheck(f"duplicate check id: {check.check_id}")
            if check.disclosure not in _DISCLOSURE_ORDER:
                raise ValueError(f"unknown disclosure level: {check.disclosure}")
            by_id[check.check_id] = check
        ordered = self._topological(by_id)
        maximum = max(
            (check.disclosure for check in ordered),
            key=_DISCLOSURE_ORDER.__getitem__,
            default="none",
        )
        return PlannedCheckPlan(
            checks=ordered,
            clarifications=tuple(sorted(set(clarifications))),
            preview=PlanPreview(
                estimated_cost=sum(check.estimated_cost for check in ordered),
                maximum_disclosure=maximum,
                check_count=len(ordered),
            ),
        )

    @staticmethod
    def _topological(by_id: dict[str, CheckSpec]) -> tuple[CheckSpec, ...]:
        missing = {
            dependency
            for check in by_id.values()
            for dependency in check.dependencies
            if dependency not in by_id
        }
        if missing:
            raise MissingDependency(f"missing check dependencies: {sorted(missing)}")
        pending = {key: set(check.dependencies) for key, check in by_id.items()}
        ordered: list[CheckSpec] = []
        while pending:
            ready = sorted(key for key, dependencies in pending.items() if not dependencies)
            if not ready:
                raise CyclicCheckPlan("check dependencies contain a cycle")
            for key in ready:
                ordered.append(by_id[key])
                del pending[key]
            for dependencies in pending.values():
                dependencies.difference_update(ready)
        return tuple(ordered)
