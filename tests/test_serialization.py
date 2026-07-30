from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime

from answerable.domain.models import (
    AnalysisType,
    CheckPlan,
    CheckSpec,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    Metric,
    Population,
    QuestionContract,
    TimeWindow,
)
from answerable.domain.serialization import canonical_json, fingerprint, from_dict, to_dict


class SerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = QuestionContract(
            question_id="qst_01",
            raw_question="What happened?",
            normalized_question="Describe revenue.",
            language="en",
            analysis_type=AnalysisType.DESCRIPTIVE,
            population=Population(description="Paid customers"),
            unit_of_analysis="customer",
            outcome=Metric(metric_id="revenue", definition="Net revenue", value_type="number"),
            time=TimeWindow(
                observation_start=datetime(2026, 1, 1, tzinfo=UTC),
                observation_end=datetime(2026, 1, 31, tzinfo=UTC),
            ),
        )

    def test_INV_006_round_trip_preserves_question_contract(self) -> None:
        payload = to_dict(self.contract)
        restored = from_dict(QuestionContract, payload)
        self.assertEqual(restored, self.contract)

    def test_INV_006_canonical_json_is_order_independent(self) -> None:
        left = {"b": 2, "a": {"d": 4, "c": 3}}
        right = {"a": {"c": 3, "d": 4}, "b": 2}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(fingerprint(left), fingerprint(right))

    def test_INV_006_canonical_json_uses_stable_compact_encoding(self) -> None:
        encoded = canonical_json(to_dict(self.contract))
        self.assertEqual(
            encoded, json.dumps(json.loads(encoded), sort_keys=True, separators=(",", ":"))
        )

    def test_INV_006_rejects_naive_datetime(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            TimeWindow(
                observation_start=datetime(2026, 1, 1),
                observation_end=datetime(2026, 1, 2, tzinfo=UTC),
            )

    def test_INV_006_serializes_nested_tuples_lists_dicts_and_enums(self) -> None:
        plan = CheckPlan(
            plan_id="plan_01",
            assessment_id="asm_01",
            checks=(
                CheckSpec(
                    check_id="chk_01",
                    check_type="schema",
                    check_version="1.0",
                    requirement_id="INV-006",
                    executor="python",
                    severity_on_failure="blocker",
                    parameters={"columns": ["a", "b"], "strict": True},
                ),
            ),
        )
        encoded = to_dict(plan)
        self.assertEqual(encoded["checks"][0]["parameters"]["columns"], ["a", "b"])

    def test_phase_6_check_spec_validates_cost_and_dependencies(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            CheckSpec("a", "schema", "1", "FR-PLAN-001", "python", "blocker", estimated_cost=-1)
        with self.assertRaisesRegex(ValueError, "itself"):
            CheckSpec(
                "a",
                "schema",
                "1",
                "FR-PLAN-001",
                "python",
                "blocker",
                dependencies=("a",),
            )

    def test_INV_006_serializes_evidence_graph_payloads(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph_01",
            nodes=(EvidenceNode("node_01", "Fact", {"value": 1}),),
            edges=(EvidenceEdge("node_01", "node_02", "supports"),),
        )
        restored = from_dict(EvidenceGraph, to_dict(graph))
        self.assertEqual(restored, graph)

    def test_INV_006_rejects_unknown_fields_and_wrong_shapes(self) -> None:
        payload = to_dict(self.contract)
        payload["unknown"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            from_dict(QuestionContract, payload)
        with self.assertRaisesRegex(TypeError, "dataclass"):
            from_dict(str, {})  # type: ignore[type-var]

    def test_INV_006_rejects_unsupported_values(self) -> None:
        with self.assertRaisesRegex(TypeError, "unsupported"):
            canonical_json({1, 2, 3})
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            canonical_json(datetime(2026, 1, 1))

    def test_INV_006_validates_domain_value_objects(self) -> None:
        with self.assertRaisesRegex(ValueError, "description"):
            Population(description=" ")
        with self.assertRaisesRegex(ValueError, "required"):
            Metric(metric_id="", definition="", value_type="number")
        with self.assertRaisesRegex(ValueError, "numerator"):
            Metric(
                metric_id="conversion",
                definition="Converted / eligible",
                value_type="ratio",
                numerator="converted",
            )
        with self.assertRaisesRegex(ValueError, "precede"):
            TimeWindow(
                observation_start=datetime(2026, 2, 1, tzinfo=UTC),
                observation_end=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_INV_006_rejects_blank_question_contract_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "blank"):
            QuestionContract(
                question_id="",
                raw_question="What happened?",
                normalized_question="Describe revenue.",
                language="en",
                analysis_type=AnalysisType.DESCRIPTIVE,
                population=Population(description="Paid customers"),
                unit_of_analysis="customer",
                outcome=Metric(metric_id="revenue", definition="Net revenue", value_type="number"),
                time=TimeWindow(
                    observation_start=datetime(2026, 1, 1, tzinfo=UTC),
                    observation_end=datetime(2026, 1, 2, tzinfo=UTC),
                ),
            )

    def test_INV_006_rejects_invalid_nested_serialized_shapes(self) -> None:
        payload = to_dict(self.contract)
        payload["time"]["observation_start"] = 42
        with self.assertRaisesRegex(TypeError, "datetime"):
            from_dict(QuestionContract, payload)

        payload = to_dict(self.contract)
        payload["population"] = "not-an-object"
        with self.assertRaisesRegex(TypeError, "Population"):
            from_dict(QuestionContract, payload)

        payload = to_dict(self.contract)
        payload["assumptions"] = "not-an-array"
        with self.assertRaisesRegex(TypeError, "tuple"):
            from_dict(QuestionContract, payload)

        check_payload = {
            "check_id": "chk_01",
            "check_type": "schema",
            "check_version": "1.0",
            "requirement_id": "INV-006",
            "executor": "python",
            "severity_on_failure": "blocker",
            "parameters": [],
        }
        with self.assertRaisesRegex(TypeError, "dict"):
            from_dict(CheckSpec, check_payload)


if __name__ == "__main__":
    unittest.main()
