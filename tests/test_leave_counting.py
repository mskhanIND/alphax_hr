import unittest
from datetime import date

from alphax_hr.saudi import leave_counting as lc

# Saudi week-end: Friday + Saturday. November 2026: Fri 6, Sat 7, Fri 13, Sat 14.
WEEKENDS = {date(2026, 11, d) for d in (6, 7, 13, 14, 20, 21)}
HOLIDAYS = {date(2026, 11, 10)}  # a Tuesday public holiday


class LeaveCounting(unittest.TestCase):
    def test_calendar_counts_everything(self):
        r = lc.count(date(2026, 11, 5), date(2026, 11, 11), WEEKENDS, HOLIDAYS, lc.Policy())
        self.assertEqual(r.days, 7)

    def test_working_days_only(self):  # marriage leave: 5 working days
        r = lc.count(date(2026, 11, 8), date(2026, 11, 12), WEEKENDS, HOLIDAYS, lc.Policy(lc.WORKING))
        self.assertEqual((r.days, r.holidays_skipped), (4, 1))

    def test_skip_holidays_only(self):
        r = lc.count(date(2026, 11, 5), date(2026, 11, 11), WEEKENDS, HOLIDAYS, lc.Policy(lc.SKIP_HOLIDAYS))
        self.assertEqual((r.days, r.holidays_skipped, r.weekends_skipped), (6, 1, 0))

    def test_sandwich_inside_request(self):
        p = lc.Policy(lc.WORKING, lc.SANDWICH_IN)
        r = lc.count(date(2026, 11, 5), date(2026, 11, 8), WEEKENDS, HOLIDAYS, p)  # Thu..Sun
        self.assertEqual((r.days, r.sandwiched), (4, 2))
        r = lc.count(date(2026, 11, 6), date(2026, 11, 8), WEEKENDS, HOLIDAYS, p)  # starts on the weekend
        self.assertEqual((r.days, r.weekends_skipped), (1, 2))
        r = lc.count(date(2026, 11, 9), date(2026, 11, 11), WEEKENDS, HOLIDAYS, p)  # holiday not sandwiched
        self.assertEqual(r.days, 2)
        r = lc.count(date(2026, 11, 9), date(2026, 11, 11), WEEKENDS, HOLIDAYS, lc.Policy(lc.WORKING, lc.SANDWICH_IN, True))
        self.assertEqual(r.days, 3)

    def test_sandwich_across_requests(self):
        p = lc.Policy(lc.WORKING, lc.SANDWICH_ACROSS)
        # Thursday 5th approved earlier; now Sunday 8th: Fri+Sat between count on this request
        r = lc.count(date(2026, 11, 8), date(2026, 11, 8), WEEKENDS, HOLIDAYS, p, leave_before=date(2026, 11, 5))
        self.assertEqual((r.days, r.adjacent_days), (3, 2))
        r = lc.count(date(2026, 11, 8), date(2026, 11, 8), WEEKENDS, HOLIDAYS, p, leave_before=date(2026, 11, 4))
        self.assertEqual(r.days, 1)  # a working day in between: no sandwich
        r = lc.count(date(2026, 11, 8), date(2026, 11, 8), WEEKENDS, HOLIDAYS, lc.Policy(lc.WORKING, lc.SANDWICH_IN), leave_before=date(2026, 11, 5))
        self.assertEqual(r.days, 1)

    def test_half_day_and_text(self):
        r = lc.count(date(2026, 11, 9), date(2026, 11, 9), WEEKENDS, HOLIDAYS, lc.Policy(lc.WORKING), half_day=True)
        self.assertEqual(r.days, 0.5)
        self.assertIn("day(s)", lc.count(date(2026, 11, 5), date(2026, 11, 8), WEEKENDS, HOLIDAYS, lc.Policy(lc.WORKING)).describe())


if __name__ == "__main__":
    unittest.main()
