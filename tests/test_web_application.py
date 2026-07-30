from __future__ import annotations

import unittest

from answerable.web.app import ResultView, Screen, WebApplication

UX_001 = "UX-001"
UX_002 = "UX-002"
UX_003 = "UX-003"
UX_004 = "UX-004"
UX_005 = "UX-005"
UX_006 = "UX-006"
UX_007 = "UX-007"
UX_008 = "UX-008"
UX_009 = "UX-009"
UX_010 = "UX-010"


class WebApplicationTests(unittest.TestCase):
    def test_phase_16_result_is_immediately_understandable_and_accessible(self) -> None:
        rendered = WebApplication().render_result(
            ResultView(
                "NOT_ANSWERABLE_YET",
                "The period is missing.",
                ("Revenue rose.",),
                ("Campaign caused revenue.",),
                ("Define the period.",),
                ("Stable definition",),
            )
        )
        self.assertIn("<h1>Verdict:", rendered)
        self.assertLess(rendered.index("Verdict:"), rendered.index("Complete provenance"))
        self.assertIn('aria-labelledby="allowed-claims"', rendered)
        self.assertIn('aria-labelledby="forbidden-claims"', rendered)
        self.assertIn('role="tree"', rendered)
        self.assertIn("Skip to result", rendered)
        self.assertNotIn("<script", rendered)

    def test_phase_16_all_normative_screens_are_navigable(self) -> None:
        self.assertEqual(len(WebApplication.navigation()), 15)
        self.assertIn(Screen.WARRANT_HISTORY, WebApplication.navigation())
        self.assertIn(Screen.BENCHMARKS, WebApplication.navigation())


if __name__ == "__main__":
    unittest.main()
