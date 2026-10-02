"""Variable-pay schedule for the payroll year, shared by the harness and the golden engine.

The golden engine reads this module and ``personas.PERSONAS`` only; it never reads
Salary Slips or za_local_payroll calculation code, so expected values stay
independent of the implementation under test.
"""

# (persona, component, amount, month 'YYYY-MM', kind) kind: once | recurring:<to YYYY-MM> | overwrite
ADDITIONAL_SALARY = [
	# Overtime - irregular, annualised with ordinary remuneration (average method)
	*[
		("P13_overtime", "Overtime", amt, m, "once")
		for m, amt in (
			("2026-03", 1500),
			("2026-05", 3200),
			("2026-06", 800),
			("2026-08", 2500),
			("2026-09", 1200),
			("2026-11", 4000),
			("2026-12", 600),
			("2027-02", 1800),
		)
	],
	# Commission - recurring Jun-Aug plus a once-off adjustment in October
	("P14_commission", "Commission", 2000, "2026-06", "recurring:2026-08"),
	("P14_commission", "Commission", 1500, "2026-10", "once"),
	# Annual payments - taxed in full when paid
	("P15_bonus", "Performance Bonus", 20000, "2026-06", "once"),
	("P15_bonus", "13th Cheque", 30000, "2026-12", "once"),
	# Reimbursive travel at the prescribed R4.95/km x 150 km, and a business reimbursement
	("P17_reimbursive_travel", "Reimbursive Travel", 742.50, "2026-03", "recurring:2027-02"),
	("P17_reimbursive_travel", "Business Expense Reimbursement", 1200, "2026-07", "once"),
	# Overwrite: replace Basic for one month rather than adding a second Basic row
	("P02_normal", "Basic", 26000, "2026-07", "overwrite"),
]

# Additional Salary created then cancelled; must not affect payroll.
CANCELLED_ADDITIONAL_SALARY = [("P13_overtime", "Overtime", 9999, "2026-04")]

TERMINATION = {
	"persona": "P19_termination",
	"relieving_date": "2026-11-30",
	"leave_days": 12,
	"notice_pay": 32000,
	"severance": 88615.38,  # 12 completed years x 1 week (32,000 x 12 / 52), BCEA s41 minimum
	"directive_number": "SYNTH-DIR-0001",
	# Prior lump sums of R500,000 bring the aggregate to R588,615.38, so the lump-sum
	# table taxes R38,615.38 at 18%. A nil-tax directive cannot be captured (gap DIR-1).
	"previous_lump_sums": 500000,
	"directive_tax": 6950.77,
}

MONTHS = [f"{y}-{m:02d}" for y, m in [(2026, m) for m in range(3, 13)] + [(2027, 1), (2027, 2)]]
