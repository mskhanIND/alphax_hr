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

    def test_below_3000_does_not_count(self):
        rows = [{"is_saudi": True, "wage": 2500}, {"is_saudi": True, "wage": 3500}, {"is_saudi": True, "wage": 4500},
                {"is_saudi": False, "wage": 4000}]
        r = nitaqat.ratio(rows)
        self.assertEqual(r["saudi_weighted"], 1.5)
        self.assertEqual((r["saudis_not_counted"], r["saudis_counted_partially"]), (1, 1))

    def test_schedule(self):
        self.assertEqual(nitaqat.full_count_wage_on(date(2026, 11, 5)), 4000)
        self.assertEqual(nitaqat.full_count_wage_on(date(2027, 4, 24)), 4000)
        self.assertEqual(nitaqat.full_count_wage_on(date(2027, 4, 25)), 5000)
        self.assertEqual(nitaqat.full_count_wage_on(date(2028, 4, 25)), 6000)
        self.assertEqual([w for _, w in nitaqat.upcoming(date(2026, 11, 5))], [5000, 6000])

    def test_forecast(self):
        rows = [{"is_saudi": True, "wage": 4500, "name": "A"}, {"is_saudi": True, "wage": 5500, "name": "B"},
                {"is_saudi": False, "wage": 3000, "name": "C"}]
        f = nitaqat.forecast(rows, nitaqat.NitaqatPolicy(), nitaqat.upcoming(date(2026, 11, 5)))
        self.assertEqual([x["name"] for x in f[0]["stop_counting_fully"]], ["A"])
        self.assertEqual(f[0]["stop_counting_fully"][0]["raise_needed"], 500)
        self.assertEqual(f[0]["after"]["saudi_weighted"], 1.5)
        self.assertEqual(sorted(x["name"] for x in f[1]["stop_counting_fully"]), ["A", "B"])
        self.assertEqual(f[1]["monthly_cost_all_below"], 2000)


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


class Article80Tests(unittest.TestCase):
    def test_contract_year(self):
        from alphax_hr.saudi import absence
        self.assertEqual(absence.contract_year_start(date(2021, 3, 10), date(2026, 11, 5)), date(2026, 3, 10))
        self.assertEqual(absence.contract_year_start(date(2021, 12, 10), date(2026, 11, 5)), date(2025, 12, 10))
        self.assertEqual(absence.contract_year_start(date(2020, 2, 29), date(2026, 11, 5)), date(2026, 2, 28))

    def test_runs_bridge_holidays(self):
        from datetime import timedelta
        from alphax_hr.saudi import absence
        start = date(2026, 10, 1)
        codes = ["P", "A", "A", "H", "H", "A", "A", "A", "A", "A", "H", "A", "A", "A"]
        days = [(start + timedelta(days=i), c) for i, c in enumerate(codes)]
        s = absence.evaluate(days, date(2026, 1, 1))
        self.assertEqual((s["consecutive"], s["consecutive_from"], s["year_total"]), (10, date(2026, 10, 2), 10))
        self.assertEqual(absence.stage(s), ["consecutive_warning"])
        days.append((start + timedelta(days=14), "L"))  # leave breaks the run
        self.assertEqual(absence.evaluate(days, date(2026, 1, 1))["consecutive"], 0)

    def test_unmarked_days_count_only_when_asked(self):
        from alphax_hr.saudi import absence
        days = [(date(2026, 10, i), "?") for i in range(1, 22)]
        self.assertEqual(absence.evaluate(days, date(2026, 1, 1))["year_total"], 0)
        s = absence.evaluate(days, date(2026, 1, 1), counts_unmarked=True)
        self.assertEqual(absence.stage(s), ["consecutive_warning", "year_warning", "consecutive_limit"])


class TerminationTests(unittest.TestCase):
    def test_notice(self):
        from alphax_hr.saudi import termination as t
        self.assertEqual(t.notice_days(t.INDEFINITE, t.EMPLOYEE), 30)
        self.assertEqual(t.notice_days(t.INDEFINITE, t.EMPLOYER), 60)
        self.assertEqual(t.notice_days(t.INDEFINITE, t.EMPLOYER, monthly_paid=False), 30)
        self.assertEqual(t.notice_days(t.FIXED, t.EMPLOYER), 0)
        self.assertEqual(t.notice_shortfall(60, date(2026, 10, 1), date(2026, 10, 31)), 30)
        self.assertEqual(t.notice_shortfall(30, None, date(2026, 10, 31)), 30)
        self.assertEqual(t.notice_shortfall(30, date(2026, 9, 1), date(2026, 10, 31)), 0)
        self.assertEqual(t.notice_pay(9000, 30), 9000.0)

    def test_article77(self):
        from alphax_hr.saudi import termination as t
        self.assertEqual(t.article77(t.INDEFINITE, 6000, 10), 30000.0)       # 15 days x 10 years
        self.assertEqual(t.article77(t.INDEFINITE, 6000, 1), 12000.0)        # at least two months
        self.assertEqual(t.article77(t.FIXED, 6000, 2, remaining_days=270), 54000.0)
        self.assertEqual(t.article77(t.FIXED, 6000, 2, remaining_days=20), 12000.0)
        self.assertEqual(t.article77(t.INDEFINITE, 6000, 10, agreed=50000), 50000.0)


class PunchTypeTests(unittest.TestCase):
    def test_untyped_first_in_last_out(self):
        from datetime import datetime
        from alphax_hr.saudi import attendance as a
        d = lambda h, m=0: datetime(2026, 11, 10, h, m)
        logs = [(d(8, 2), None), (d(8, 3), None), (d(12), None), (d(13), None), (d(17, 5), None)]
        self.assertEqual(a.resolve_types(logs), [(d(8, 2), "IN"), (d(17, 5), "OUT")])
        self.assertEqual(a.resolve_types([(d(8), None), (d(8, 2), None)]), [(d(8), "IN")])  # double tap = one punch
        typed = [(d(8), "IN"), (d(17), "OUT")]
        self.assertEqual(a.resolve_types(typed), typed)
        p = a.pair_logs(a.resolve_types(logs))
        self.assertFalse(p.missing_punch)
        self.assertAlmostEqual(p.hours, 9.05, places=2)
