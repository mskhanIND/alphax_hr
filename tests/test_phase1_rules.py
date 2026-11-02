"""Phase 1 rules: identity, IBAN, statutory special leaves, sick cycles, service periods."""
import unittest
from datetime import date

from alphax_hr.saudi import identity, leave, leave_rules as lr


class IdentityTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(identity.classify_id("1012345678"), (identity.SAUDI, None))
        self.assertEqual(identity.classify_id(" 2398765432 "), (identity.RESIDENT, None))
        self.assertEqual(identity.classify_id("3012345678"), (identity.BORDER, None))
        self.assertEqual(identity.classify_id("23987654"), (None, "id_wrong_length"))
        self.assertEqual(identity.classify_id("23A8765432"), (None, "id_not_digits"))
        self.assertEqual(identity.classify_id("9012345678"), (None, "id_bad_prefix"))
        self.assertEqual(identity.classify_id(""), (None, None))

    def test_iban(self):
        self.assertIsNone(identity.iban_error("SA03 8000 0000 6080 1016 7519"))  # IBAN registry example
        self.assertEqual(identity.iban_error("SA0380000000608010167518"), "iban_bad_checksum")
        self.assertEqual(identity.iban_error("SA038000000060801016751"), "iban_wrong_length")
        self.assertEqual(identity.iban_error("SA03-8000"), "iban_bad_characters")
        self.assertIsNone(identity.iban_error(None))


def req(**kw):
    base = dict(from_date=date(2026, 3, 1), to_date=date(2026, 3, 3), total_days=3, gender="Male",
                date_of_joining=date(2020, 1, 1))
    base.update(kw)
    return lr.Request(**base)


def codes(rule, request):
    return [c for c, _ in lr.check(rule, request)]


class SpecialLeaveTests(unittest.TestCase):
    def test_maternity(self):
        rule = lr.default_rule(lr.MATERNITY)
        self.assertEqual(codes(rule, req(gender="Male", total_days=10, event_date=date(2026, 3, 20))), ["leave_gender"])
        self.assertIn("leave_max_days", codes(rule, req(gender="Female", total_days=90, event_date=date(2026, 3, 20))))
        # may start at most 28 days before the expected delivery
        self.assertIn("leave_too_early", codes(rule, req(gender="Female", from_date=date(2026, 2, 1), event_date=date(2026, 3, 20))))
        self.assertEqual(codes(rule, req(gender="Female", from_date=date(2026, 2, 21), to_date=date(2026, 5, 15),
                                        total_days=84, event_date=date(2026, 3, 20))), [])
        self.assertIn("leave_event_date_required", codes(rule, req(gender="Female")))

    def test_paternity_within_seven_days_after_birth(self):
        rule = lr.default_rule(lr.PATERNITY)
        birth = date(2026, 3, 1)
        self.assertEqual(codes(rule, req(from_date=date(2026, 3, 2), to_date=date(2026, 3, 4), event_date=birth)), [])
        self.assertIn("leave_too_early", codes(rule, req(from_date=date(2026, 2, 28), to_date=date(2026, 3, 1), total_days=2, event_date=birth)))
        self.assertIn("leave_too_late", codes(rule, req(from_date=date(2026, 3, 7), to_date=date(2026, 3, 9), event_date=birth)))
        self.assertIn("leave_max_days", codes(rule, req(to_date=date(2026, 3, 4), total_days=4, event_date=birth)))

    def test_bereavement_relations(self):
        rule = lr.default_rule(lr.BEREAVEMENT)
        self.assertEqual(codes(rule, req(relation="Mother", event_date=date(2026, 3, 1))), [])
        self.assertIn("leave_relation_not_allowed", codes(rule, req(relation="Brother", event_date=date(2026, 3, 1))))
        sib = lr.default_rule(lr.SIBLING)
        self.assertEqual(codes(sib, req(relation="Brother", event_date=date(2026, 3, 1))), [])
        self.assertIn("leave_max_days", codes(sib, req(relation="Sister", total_days=5, to_date=date(2026, 3, 5), event_date=date(2026, 3, 1))))
        self.assertIn("leave_relation_required", codes(sib, req(event_date=date(2026, 3, 1))))

    def test_hajj_service_and_once(self):
        rule = lr.default_rule(lr.HAJJ)
        self.assertIn("leave_min_service", codes(rule, req(date_of_joining=date(2025, 6, 1), total_days=10)))
        self.assertEqual(codes(rule, req(total_days=12)), [])
        self.assertIn("leave_lifetime_limit", codes(rule, req(total_days=12, previous_uses=1)))
        self.assertIn("leave_max_days", codes(rule, req(total_days=16)))

    def test_iddah(self):
        self.assertEqual(lr.default_rule(lr.IDDAH_MUSLIM).max_days, 130)
        self.assertEqual(lr.default_rule(lr.IDDAH_OTHER).max_days, 15)
        self.assertIn("leave_gender", codes(lr.default_rule(lr.IDDAH_MUSLIM), req(event_date=date(2026, 3, 1))))

    def test_all_kinds_have_defaults(self):
        for kind in lr.KINDS:
            self.assertEqual(lr.default_rule(kind).kind, kind)


class SickCycleTests(unittest.TestCase):
    def test_cycle_runs_a_year_from_first_sick_day(self):
        prev = [(date(2026, 1, 10), 20), (date(2026, 5, 1), 15)]
        self.assertEqual(lr.sick_cycle_usage(prev, date(2026, 9, 1)), (date(2026, 1, 10), 35.0))
        # a year after the first sick day a new cycle starts
        self.assertEqual(lr.sick_cycle_usage(prev, date(2027, 1, 10)), (date(2027, 1, 10), 0.0))
        self.assertEqual(lr.sick_cycle_usage([], date(2026, 9, 1)), (date(2026, 9, 1), 0.0))

    def test_new_cycle_mid_history(self):
        prev = [(date(2025, 1, 1), 30), (date(2026, 2, 1), 10), (date(2026, 6, 1), 5)]
        self.assertEqual(lr.sick_cycle_usage(prev, date(2026, 7, 1)), (date(2026, 2, 1), 15.0))

    def test_split_description(self):
        text = leave.describe_sick_split(leave.sick_leave_split(25, 10))
        self.assertEqual(text, "5 day(s) full pay · 5 day(s) 75% pay")


class ServicePeriodTests(unittest.TestCase):
    def test_periods_follow_the_joining_anniversary(self):
        self.assertEqual(leave.service_period(date(2021, 7, 15), date(2026, 11, 2)), (5, date(2026, 7, 15), date(2027, 7, 14)))
        self.assertEqual(leave.service_period(date(2021, 7, 15), date(2026, 7, 14)), (4, date(2025, 7, 15), date(2026, 7, 14)))
        self.assertEqual(leave.service_period(date(2024, 2, 29), date(2025, 3, 1)), (1, date(2025, 2, 28), date(2026, 2, 27)))

    def test_entitlement_by_service_year(self):
        self.assertEqual(leave.entitlement_for_service_year(4), 21)
        self.assertEqual(leave.entitlement_for_service_year(5), 30)
        self.assertEqual(leave.entitlement_for_service_year(0, base=25), 25)


if __name__ == "__main__":
    unittest.main()


def test_annual_days_policy_contract_and_legal_minimum():
    from alphax_hr.saudi.leave import annual_days, POLICY_FIXED, POLICY_LAW
    assert annual_days(0) == (21, "law")
    assert annual_days(5) == (30, "law")
    assert annual_days(0, POLICY_FIXED, 30) == (30, "company")       # IRSAA: 30 for everyone
    assert annual_days(0, POLICY_FIXED, 30, contract_days=35) == (35, "contract")
    assert annual_days(0, POLICY_LAW, contract_days=25) == (25, "contract")
    assert annual_days(6, POLICY_LAW, contract_days=25) == (30, "legal_minimum")
    assert annual_days(6, POLICY_FIXED, 21) == (30, "legal_minimum")


def test_senior_years_counted_from_company_date():
    from datetime import date
    from alphax_hr.saudi.leave import annual_days, senior_year_index
    # joined 2020; company counts seniority from 2027-01-01
    assert senior_year_index(date(2020, 3, 1), date(2027, 3, 1), date(2027, 1, 1)) == 0
    assert senior_year_index(date(2020, 3, 1), date(2032, 3, 1), date(2027, 1, 1)) == 5
    assert senior_year_index(date(2020, 3, 1), date(2027, 3, 1), None) == 7
    # company gives 35 after 5 years counted from 2027: not yet, but the legal 30 still applies
    assert annual_days(7, base=25, senior=35, senior_after=5, senior_index=0) == (30, "legal_minimum")
    assert annual_days(12, base=25, senior=35, senior_after=5, senior_index=5) == (35, "law")
    assert annual_days(2, base=25, senior=35, senior_after=5, senior_index=0) == (25, "law")
