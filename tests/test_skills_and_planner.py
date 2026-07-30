from __future__ import annotations

import unittest

from answerable.domain.models import CheckSpec
from answerable.planning.errors import (
    CyclicCheckPlan,
    DuplicateCheck,
    DuplicateSkill,
    MissingDependency,
    UnknownCheckType,
)
from answerable.planning.planner import CheckPlanner, PlanningContext
from answerable.planning.registry import CheckTypeRegistry, SkillRegistry
from answerable.planning.skills import Skill, SkillProposal


class StaticSkill(Skill):
    def __init__(self, skill_id: str, checks: tuple[CheckSpec, ...]) -> None:
        self.skill_id = skill_id
        self.version = "1.0.0"
        self.applies_to = frozenset({"descriptive"})
        self._checks = checks

    def propose(self, context: PlanningContext) -> SkillProposal:
        del context
        return SkillProposal(checks=self._checks)


def check(
    check_id: str,
    check_type: str = "schema",
    *,
    dependencies: tuple[str, ...] = (),
    mandatory: bool = False,
    disclosure: str = "metadata_only",
    cost: int = 1,
) -> CheckSpec:
    return CheckSpec(
        check_id=check_id,
        check_type=check_type,
        check_version="1.0.0",
        requirement_id="FR-PLAN-001",
        executor="python",
        severity_on_failure="blocker",
        dependencies=dependencies,
        mandatory=mandatory,
        disclosure=disclosure,
        estimated_cost=cost,
    )


class SkillRegistryAndPlannerTests(unittest.TestCase):
    def test_phase_6_registry_rejects_duplicate_skill_version(self) -> None:
        registry = SkillRegistry()
        registry.register(StaticSkill("quality", ()))
        with self.assertRaises(DuplicateSkill):
            registry.register(StaticSkill("quality", ()))

    def test_FR_PLAN_004_unknown_check_type_is_rejected(self) -> None:
        skills = SkillRegistry()
        skills.register(StaticSkill("quality", (check("unknown", "invented"),)))
        planner = CheckPlanner(skills, CheckTypeRegistry(("schema",)))
        with self.assertRaises(UnknownCheckType):
            planner.build(PlanningContext("descriptive"))

    def test_FR_PLAN_005_cycle_is_rejected(self) -> None:
        skills = SkillRegistry()
        skills.register(
            StaticSkill(
                "quality",
                (
                    check("a", dependencies=("b",)),
                    check("b", dependencies=("a",)),
                ),
            )
        )
        planner = CheckPlanner(skills, CheckTypeRegistry(("schema",)))
        with self.assertRaises(CyclicCheckPlan):
            planner.build(PlanningContext("descriptive"))

    def test_FR_PLAN_001_plan_is_deterministic_and_topological(self) -> None:
        skills = SkillRegistry()
        skills.register(
            StaticSkill(
                "quality",
                (
                    check("b", dependencies=("a",), cost=3),
                    check("a", disclosure="none", cost=2),
                ),
            )
        )
        planner = CheckPlanner(skills, CheckTypeRegistry(("schema",)))
        first = planner.build(PlanningContext("descriptive"))
        second = planner.build(PlanningContext("descriptive"))
        self.assertEqual(first, second)
        self.assertEqual(tuple(item.check_id for item in first.checks), ("a", "b"))
        self.assertEqual(first.preview.estimated_cost, 5)
        self.assertEqual(first.preview.maximum_disclosure, "metadata_only")

    def test_FR_PLAN_002_mandatory_checks_are_always_present(self) -> None:
        planner = CheckPlanner(
            SkillRegistry(),
            CheckTypeRegistry(("schema",)),
            mandatory_checks=(check("required", mandatory=True),),
        )
        plan = planner.build(PlanningContext("descriptive"))
        self.assertEqual(tuple(item.check_id for item in plan.checks), ("required",))
        self.assertTrue(plan.checks[0].mandatory)

    def test_phase_6_rejects_duplicates_missing_dependencies_and_disclosure(self) -> None:
        checks = CheckTypeRegistry(("schema",))

        duplicate_skills = SkillRegistry()
        duplicate_skills.register(StaticSkill("a", (check("same"),)))
        duplicate_skills.register(StaticSkill("b", (check("same"),)))
        with self.assertRaises(DuplicateCheck):
            CheckPlanner(duplicate_skills, checks).build(PlanningContext("descriptive"))

        missing_skill = SkillRegistry()
        missing_skill.register(StaticSkill("missing", (check("a", dependencies=("absent",)),)))
        with self.assertRaises(MissingDependency):
            CheckPlanner(missing_skill, checks).build(PlanningContext("descriptive"))

        disclosure_skill = SkillRegistry()
        disclosure_skill.register(StaticSkill("disclosure", (check("a", disclosure="secret"),)))
        with self.assertRaisesRegex(ValueError, "disclosure"):
            CheckPlanner(disclosure_skill, checks).build(PlanningContext("descriptive"))

    def test_phase_6_empty_plan_has_no_disclosure_or_cost(self) -> None:
        plan = CheckPlanner(SkillRegistry(), CheckTypeRegistry(("schema",))).build(
            PlanningContext("descriptive")
        )
        self.assertEqual(plan.preview.maximum_disclosure, "none")
        self.assertEqual(plan.preview.estimated_cost, 0)
        self.assertEqual(plan.preview.check_count, 0)


if __name__ == "__main__":
    unittest.main()
