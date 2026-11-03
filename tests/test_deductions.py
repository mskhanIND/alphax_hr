import unittest
from datetime import date

from alphax_hr.saudi import deductions as d


class Deductions(unittest.TestCase):
	def test_caps(self):
		self.assertEqual(d.loan_cap(8000), 800)
		self.assertEqual(d.damage_cap(9000), 1500)
		self.assertEqual(d.total_cap(8000), 4000)

	def test_installments(self):
		rows = d.plan_installments(1000, 3, date(2026, 11, 15))
		self.assertEqual([r["amount"] for r in rows], [333.33, 333.33, 333.34])
		self.assertEqual([r["due_month"] for r in rows], [date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)])
		self.assertEqual(d.min_months_for_cap(5000, 8000), 7)  # 800 a month
		self.assertEqual(d.split_by_cap(3200, 1500), [1500, 1500, 200])

	def test_month_check(self):
		ok = d.check_month(8000, [(d.LOAN, 800), (d.STATUTORY, 780), (d.FINE, 500)])
		self.assertTrue(ok.ok, ok.problems)
		bad = d.check_month(8000, [(d.LOAN, 1200)])
		self.assertEqual(bad.problems[0][0], "loan_over_10")
		self.assertTrue(d.check_month(8000, [(d.LOAN, 1200)], consent_for_loans=True).ok)
		half = d.check_month(8000, [(d.LOAN, 2000), (d.CONSENT, 2500)], consent_for_loans=True)
		self.assertEqual([p[0] for p in half.problems], ["over_half_wage"])
		self.assertEqual(half.room, 0)
		self.assertEqual(d.check_month(9000, [(d.DAMAGE, 1600)]).problems[0][0], "damage_over_5_days")
		self.assertTrue(d.check_month(8000, [(d.LOAN, 3000), (d.STATUTORY, 1500)], True, include_statutory=False).ok)


if __name__ == "__main__":
	unittest.main()
