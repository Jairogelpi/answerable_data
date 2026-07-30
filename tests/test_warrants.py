from __future__ import annotations

import unittest

from answerable.warrants import AnalysisPlan, WarrantIssuer

FR_WARRANT_001 = "FR-WARRANT-001"
FR_WARRANT_002 = "FR-WARRANT-002"
FR_WARRANT_003 = "FR-WARRANT-003"
FR_WARRANT_004 = "FR-WARRANT-004"
FR_WARRANT_005 = "FR-WARRANT-005"


def payload() -> dict[str, object]:
    return {key: {} for key in WarrantIssuer.REQUIRED}


class WarrantTests(unittest.TestCase):
    def test_phase_14_canonical_warrant_is_immutable_exportable_and_verifiable(self) -> None:
        source = payload()
        record = WarrantIssuer().issue("w1", 1, source, signer="engine", secret=b"key")
        source["verdict"] = "mutated"
        self.assertNotEqual(record.data["verdict"], "mutated")
        self.assertTrue(WarrantIssuer.verify(record, b"key"))
        self.assertFalse(WarrantIssuer.verify(record, b"wrong"))
        self.assertEqual(WarrantIssuer.export(record, "json"), record.canonical_json)
        self.assertIn("## Verdict", WarrantIssuer.export(record, "markdown"))
        self.assertIn("<!doctype html>", WarrantIssuer.export(record, "html"))

    def test_phase_14_unsigned_and_superseding_warrants_remain_verifiable(self) -> None:
        old = WarrantIssuer().issue("w1", 1, payload())
        new = WarrantIssuer().issue("w2", 2, payload(), supersedes="w1")
        self.assertTrue(WarrantIssuer.verify(old))
        self.assertEqual(new.supersedes, "w1")
        with self.assertRaises(ValueError):
            WarrantIssuer().issue("bad", 1, {"verdict": "x"})

    def test_phase_14_analysis_plan_is_complete_and_separate(self) -> None:
        plan = AnalysisPlan(
            "question",
            "ATE",
            ("data",),
            ("clean",),
            "revenue",
            "DID",
            ("parallel trends",),
            "clustered CI",
            ("placebo",),
            "event study",
            "associational",
            ("pretrend passes",),
            "notebook.ipynb",
        )
        self.assertEqual(plan.method, "DID")
        with self.assertRaises(ValueError):
            AnalysisPlan("", "", (), (), "", "", (), "", (), "", "", ())


if __name__ == "__main__":
    unittest.main()
