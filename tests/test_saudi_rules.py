"""Unit tests for the Saudi rules engine (no Frappe needed)."""
import unittest
from datetime import date
from decimal import Decimal

from alphax_hr.saudi import documents, eosb, gosi, leave, nitaqat


class GOSITests(unittest.TestCase):
    def test_classification_uses_registration_not_hire_date(self):
        self.assertEqual(gosi.classify(True, date(2019, 5, 1)), gosi.LEGACY)
        self.assertEqual(gosi.classify(True, date(2024, 7, 3)), gosi.NEW)
        self.assertEqual(gosi.classify(True, date(2024, 7, 2)), gosi.LEGACY)
        self.assertEqual(gosi.classify(True, None), gosi.UNCLASSIFIED)
        self.assertEqual(gosi.classify(False, None), gosi.NON_SAUDI)

    def test_legacy_saudi_rates(self):
        c = gosi.calculate(is_saudi=True, gosi_registration_date=date(2015, 1, 1),
                           basic=10000, housing=2500, period_date=date(2026, 10, 31))
        self.assertEqual(c.employee_rate, Decimal("9.75"))
        self.assertEqual(c.employer_rate, Decimal("11.75"))
        self.assertEqual(c.employee_amount, Decimal("1218.75"))
        self.assertEqual(c.employer_amount, Decimal("1468.75"))

    def test_new_system_steps_up_each_july(self):
        expected = {
            date(2025, 1, 31): "9.75",   # 9 + 0.75
            date(2025, 7, 31): "10.25",  # 9.5 + 0.75
            date(2026, 6, 30): "10.25",
            date(2026, 7, 31): "10.75",  # 10 + 0.75
            date(2027, 7, 31): "11.25",
            date(2028, 7, 31): "11.75",
            date(2031, 1, 31): "11.75",
        }
        for period, rate in expected.items():
            c = gosi.calculate(is_saudi=True, gosi_registration_date=date(2024, 9, 1),
                               basic=8000, housing=2000, period_date=period)
            self.assertEqual(c.employee_rate, Decimal(rate), period)
        c = gosi.calculate(is_saudi=True, gosi_registration_date=date(2024, 9, 1),
                           basic=8000, housing=2000, period_date=date(2026, 7, 31))
        self.assertEqual(c.employer_rate, Decimal("12.75"))  # 10 + 0.75 + 2

    def test_non_saudi_employer_hazard_only(self):
        c = gosi.calculate(is_saudi=False, gosi_registration_date=None,
                           basic=6000, housing=1500, period_date=date(2026, 10, 31))
        self.assertEqual(c.employee_amount, Decimal("0.00"))
        self.assertEqual(c.employer_amount, Decimal("150.00"))

    def test_wage_cap(self):
        c = gosi.calculate(is_saudi=True, gosi_registration_date=date(2010, 1, 1),
                           basic=50000, housing=10000, period_date=date(2026, 10, 31))
        self.assertEqual(c.wage, Decimal("45000"))
        self.assertIn("wage_capped", c.warnings)

    def test_unclassified_is_flagged_not_guessed(self):
        c = gosi.calculate(is_saudi=True, gosi_registration_date=None,
                           basic=5000, housing=1000, period_date=date(2026, 10, 31))
        self.assertEqual(c.system, gosi.UNCLASSIFIED)
        self.assertEqual(c.total, Decimal("0"))
        self.assertIn("gosi_registration_date_missing", c.warnings)

    def test_missing_rate_raises(self):
        with self.assertRaises(ValueError):
            gosi.rate_for(gosi.NEW, date(2024, 1, 1))


class EOSBTests(unittest.TestCase):
    def test_termination_under_five_years(self):
        r = eosb.calculate(date(2022, 1, 1), date(2024, 12, 31), 10000, eosb.TERMINATION)
        self.assertAlmostEqual(float(r.award), 3 * 10000 / 2, delta=50)

    def test_termination_after_five_years(self):
        r = eosb.calculate(date(2014, 1, 1), date(2023, 12, 31), 12000, eosb.TERMINATION)
        # ~10 years: 5 * 6000 + 5 * 12000 = 90000
        self.assertAlmostEqual(float(r.award), 90000, delta=100)

    def test_resignation_factors(self):
        self.assertEqual(eosb.calculate(date(2023, 1, 1), date(2024, 6, 30), 9000, eosb.RESIGNATION).award, 0)
        three = eosb.calculate(date(2021, 1, 1), date(2023, 12, 31), 9000, eosb.RESIGNATION)
        self.assertAlmostEqual(float(three.award), float(three.gross_award) / 3, delta=0.02)
        seven = eosb.calculate(date(2017, 1, 1), date(2023, 12, 31), 9000, eosb.RESIGNATION)
        self.assertAlmostEqual(float(seven.award), float(seven.gross_award) * 2 / 3, delta=0.02)
        twelve = eosb.calculate(date(2012, 1, 1), date(2023, 12, 31), 9000, eosb.RESIGNATION)
        self.assertEqual(twelve.award, twelve.gross_award)

    def test_article_87_and_80(self):
        r = eosb.calculate(date(2023, 1, 1), date(2024, 6, 30), 9000, eosb.RESIGNATION_ART87)
        self.assertEqual(r.award, r.gross_award)
        r = eosb.calculate(date(2010, 1, 1), date(2024, 6, 30), 9000, eosb.DISMISSAL_ART80)
        self.assertEqual(r.award, 0)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            eosb.calculate(date(2024, 1, 1), date(2023, 1, 1), 1000)
        with self.assertRaises(ValueError):
            eosb.calculate(date(2020, 1, 1), date(2023, 1, 1), 1000, "Retired")


class LeaveTests(unittest.TestCase):
    def test_annual_entitlement(self):
        self.assertEqual(leave.annual_entitlement(date(2022, 3, 1), date(2026, 11, 2)), 21)
        self.assertEqual(leave.annual_entitlement(date(2021, 3, 1), date(2026, 11, 2)), 30)
        self.assertEqual(leave.annual_entitlement(date(2021, 11, 3), date(2026, 11, 2)), 21)

    def test_accrual_switches_on_fifth_anniversary(self):
        full = leave.annual_accrual(date(2015, 1, 1), date(2026, 1, 1), date(2026, 12, 31))
        self.assertAlmostEqual(full, 30, delta=0.1)
        junior = leave.annual_accrual(date(2024, 1, 1), date(2025, 1, 1), date(2025, 12, 31))
        self.assertAlmostEqual(junior, 21, delta=0.1)
        mixed = leave.annual_accrual(date(2021, 7, 1), date(2026, 1, 1), date(2026, 12, 31))
        self.assertTrue(21 < mixed < 30)

    def test_sick_leave_tiers(self):
        self.assertEqual(leave.sick_leave_split(0, 10), [{"tier": 1, "days": 10, "pay_factor": 1.0}])
        split = leave.sick_leave_split(25, 10)
        self.assertEqual(split, [{"tier": 1, "days": 5.0, "pay_factor": 1.0},
                                 {"tier": 2, "days": 5.0, "pay_factor": 0.75}])
        split = leave.sick_leave_split(115, 10)
        self.assertEqual(split[-1]["tier"], "exceeds_statutory")
        self.assertEqual(sum(p["days"] for p in split), 10)


class NitaqatTests(unittest.TestCase):
    def test_ratio_with_partial_weight(self):
        rows = [{"is_saudi": True, "wage": 5000}, {"is_saudi": True, "wage": 3000},
                {"is_saudi": False, "wage": 4000}, {"is_saudi": False, "wage": 4000}]
        r = nitaqat.ratio(rows, nitaqat.NitaqatPolicy(target_percent=50))
        self.assertEqual(r["saudi_weighted"], 1.5)
        self.assertEqual(r["saudization_percent"], round(100 * 1.5 / 3.5, 2))
        self.assertEqual(r["saudis_needed_for_target"], 1)

    def test_empty(self):
        self.assertEqual(nitaqat.ratio([])["saudization_percent"], 0.0)


class DocumentTests(unittest.TestCase):
    def test_buckets(self):
        today = date(2026, 11, 2)
        rows = [{"expiry": date(2026, 10, 1)}, {"expiry": date(2026, 11, 20)},
                {"expiry": date(2026, 12, 20)}, {"expiry": date(2027, 1, 20)},
                {"expiry": date(2027, 6, 1)}, {"expiry": None}]
        self.assertEqual(documents.summarize(rows, today), {
            "expired": 1, "within_30": 1, "within_60": 1, "within_90": 1, "valid": 1, "missing": 1})


if __name__ == "__main__":
    unittest.main()
