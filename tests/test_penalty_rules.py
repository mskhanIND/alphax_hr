import unittest
from datetime import date

from alphax_hr.saudi import penalties as p


class PenaltyRules(unittest.TestCase):
    def test_occurrence_within_180_days(self):
        on = date(2026, 7, 1)
        self.assertEqual(p.occurrence([], on), 1)
        self.assertEqual(p.occurrence([date(2026, 6, 1), date(2026, 3, 1)], on), 3)
        self.assertEqual(p.occurrence([date(2025, 12, 1)], on), 1)  # older than 180 days resets

    def test_steps_repeat_last(self):
        steps = [{"action": "Warning"}, {"action": "Deduction", "percent": 10}]
        self.assertEqual(p.step_for(steps, 1)["action"], "Warning")
        self.assertEqual(p.step_for(steps, 5)["percent"], 10)
        with self.assertRaises(ValueError):
            p.step_for([{"action": "Fine"}], 1)

    def test_days_and_caps(self):
        self.assertAlmostEqual(p.penalty_days({"action": "Deduction", "percent": 25}), 0.25)
        self.assertEqual(p.penalty_days({"action": "Suspension", "days": 9}), 5)
        self.assertEqual(p.penalty_days({"action": "Warning"}), 0)
        self.assertEqual(p.capped(2, 4), (1, True))
        self.assertEqual(p.capped(1, 0), (1, False))
        self.assertEqual(p.daily_wage(9000), 300)

    def test_late_bands(self):
        self.assertTrue(p.late_matches(10, None, 15))
        self.assertFalse(p.late_matches(20, None, 15))
        self.assertTrue(p.late_matches(90, 61, None))


if __name__ == "__main__":
    unittest.main()
