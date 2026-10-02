"""Make the 2026/27 Income Tax Slab band limits exact.

HRMS taxes a full band as (to - from + 1). The packaged bands ended at .99
(for example 1 to 245,100.99), so every full band was taxed on R0.99 too much:
up to about R1.89 a year of PAYE per employee. Bands now end on the whole rand.

Only slabs effective from 1 March 2026 are corrected. Earlier tax years are
historical; their slabs are left as they were used.
"""

import frappe


def execute() -> None:
	if not frappe.db.table_exists("Income Tax Slab"):
		return
	slabs = frappe.get_all(
		"Income Tax Slab",
		filters={"effective_from": [">=", "2026-03-01"], "currency": "ZAR"},
		pluck="name",
	)
	if not slabs:
		return
	frappe.db.sql(
		"""update `tabTaxable Salary Slab`
		set to_amount = floor(to_amount)
		where parenttype = 'Income Tax Slab' and parent in %(slabs)s
			and to_amount > 0 and round(to_amount - floor(to_amount), 2) = 0.99""",
		{"slabs": tuple(slabs)},
	)
