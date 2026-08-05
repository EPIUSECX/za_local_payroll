from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_years, flt, getdate, now_datetime
from za_local_core.governance import canonical_sha256

from za_local_payroll.services.statutory_rates import (
	resolve_coida_cap,
	resolve_coida_industry_rate,
	resolve_coida_minimum_assessment,
)
from za_local_payroll.utils.coida_utils import get_coida_salary_slip_rows

MONEY_FIELDS = (
	"uncapped_annual_earnings",
	"coida_annual_earnings_cap",
	"total_annual_earnings",
	"excluded_annual_earnings",
	"director_earnings",
	"assessment_rate",
	"assessment_before_minimum",
	"minimum_assessment",
	"assessment_fee",
)


class COIDAAnnualReturn(Document):
	def validate(self):
		self.set_and_validate_assessment_period()
		if self.total_annual_earnings:
			self.calculate_assessment_fee()

	def before_submit(self):
		"""Refuse submission when reviewed payroll or approved rates changed."""
		if not self.source_snapshot_hash:
			frappe.throw(_("Fetch Earnings before submitting the COIDA Annual Return."))
		calculation = self._build_calculation()
		if self.source_snapshot_hash != calculation.source_snapshot_hash:
			frappe.throw(
				_(
					"Payroll, employee director classification, or approved COIDA rates changed after "
					"the return was prepared. Fetch Earnings and review the return again."
				),
				title=_("COIDA Source Snapshot Changed"),
			)
		self._compare_authoritative_totals(calculation)
		self.calculated_on = now_datetime()

	def set_and_validate_assessment_period(self):
		"""Require a 1 March to end-February assessment year."""
		if not self.fiscal_year:
			return

		fiscal_year = frappe.get_cached_doc("Fiscal Year", self.fiscal_year)
		expected_from = getdate(f"{getdate(fiscal_year.year_start_date).year}-03-01")
		expected_to = add_days(add_years(expected_from, 1), -1)
		if (
			getdate(fiscal_year.year_start_date) != expected_from
			or getdate(fiscal_year.year_end_date) != expected_to
		):
			frappe.throw(
				_(
					"Fiscal Year {0} is not a valid COIDA assessment year. Configure a Fiscal Year from "
					"1 March to the last day of February."
				).format(frappe.bold(self.fiscal_year)),
				title=_("Invalid COIDA Assessment Year"),
			)

		self.from_date = expected_from
		self.to_date = expected_to

	def calculate_assessment_fee(self):
		"""Resolve the approved rate server-side and calculate the fee."""
		if not self.company or not self.industry_class or not self.from_date:
			self.assessment_rate = 0
			self.assessment_before_minimum = 0
			self.minimum_assessment = 0
			self.assessment_fee = 0
			return

		resolution = resolve_coida_industry_rate(
			self.company,
			self.industry_class,
			self.from_date,
		)
		self.assessment_rate = flt(resolution.value)
		self.assessment_rate_rule = resolution.rule_key
		self.assessment_rate_source = resolution.source_reference
		minimum = resolve_coida_minimum_assessment(self.employer_category, self.from_date)
		self.minimum_assessment = flt(minimum.value, 2)
		self.minimum_assessment_rule = minimum.rule_key
		self.minimum_assessment_source = minimum.source_reference
		self.assessment_before_minimum = flt(
			flt(self.total_annual_earnings) * flt(self.assessment_rate) / 100,
			2,
		)
		self.assessment_fee = flt(max(self.assessment_before_minimum, self.minimum_assessment), 2)

	def on_submit(self):
		self.db_set(
			{"status": "Submitted", "submission_date": frappe.utils.today()},
			update_modified=False,
		)

	def on_cancel(self):
		self.db_set(
			{"status": "Cancelled", "submission_date": None},
			update_modified=False,
		)

	@frappe.whitelist(methods=["POST"])
	def fetch_employee_data(self):
		"""Refresh the immutable source-slip working-paper snapshot."""
		self.check_permission("write")
		if not self.company or not self.from_date or not self.to_date:
			frappe.throw(_("Company and assessment period are required to fetch employee data."))
		if not self.industry_class:
			frappe.throw(_("Select the company's COIDA Industry Class before fetching employee data."))
		if not frappe.db.table_exists("Salary Slip"):
			frappe.throw(
				_(
					"Salary Slip data is unavailable. Install and configure HRMS before fetching payroll earnings."
				)
			)

		self._apply_calculation(self._build_calculation())
		return self

	def _build_calculation(self) -> frappe._dict:
		rows = get_coida_salary_slip_rows(self.company, self.from_date, self.to_date)
		cap_resolution = resolve_coida_cap(self.from_date)
		rate_resolution = resolve_coida_industry_rate(
			self.company,
			self.industry_class,
			self.from_date,
		)
		minimum_resolution = resolve_coida_minimum_assessment(self.employer_category, self.from_date)
		directors = self._get_explicit_directors({row.employee for row in rows})
		running_assessable = {}
		snapshots = []
		for row in rows:
			assessable = flt(row.assessable_earnings, 2)
			remaining_cap = max(0, flt(cap_resolution.value) - running_assessable.get(row.employee, 0))
			capped = flt(min(assessable, remaining_cap), 2)
			running_assessable[row.employee] = flt(
				running_assessable.get(row.employee, 0) + assessable,
				2,
			)
			payload = {
				"salary_slip": row.salary_slip,
				"employee": row.employee,
				"period_start": str(getdate(row.start_date)),
				"period_end": str(getdate(row.end_date)),
				"gross_earnings": flt(row.gross_earnings, 2),
				"assessable_earnings": assessable,
				"capped_assessable_earnings": capped,
				"is_director": int(row.employee in directors),
			}
			payload["source_hash"] = canonical_sha256(payload)
			snapshots.append(payload)

		gross_total = flt(sum(row["gross_earnings"] for row in snapshots), 2)
		assessable_total = flt(sum(row["capped_assessable_earnings"] for row in snapshots), 2)
		director_total = flt(
			sum(row["capped_assessable_earnings"] for row in snapshots if row["is_director"]),
			2,
		)
		calculation = frappe._dict(
			earnings_snapshot=snapshots,
			total_employees=len({row["employee"] for row in snapshots}),
			source_slip_count=len(snapshots),
			uncapped_annual_earnings=gross_total,
			coida_annual_earnings_cap=flt(cap_resolution.value, 2),
			total_annual_earnings=assessable_total,
			excluded_annual_earnings=flt(max(0, gross_total - assessable_total), 2),
			director_earnings=director_total,
			assessment_rate=flt(rate_resolution.value),
			assessment_before_minimum=flt(assessable_total * flt(rate_resolution.value) / 100, 2),
			minimum_assessment=flt(minimum_resolution.value, 2),
			cap_rate_rule=cap_resolution.rule_key,
			cap_rate_source=cap_resolution.source_reference,
			assessment_rate_rule=rate_resolution.rule_key,
			assessment_rate_source=rate_resolution.source_reference,
			minimum_assessment_rule=minimum_resolution.rule_key,
			minimum_assessment_source=minimum_resolution.source_reference,
		)
		calculation.assessment_fee = flt(
			max(calculation.assessment_before_minimum, calculation.minimum_assessment), 2
		)
		calculation.source_snapshot_hash = canonical_sha256(
			{
				"company": self.company,
				"from_date": str(getdate(self.from_date)),
				"to_date": str(getdate(self.to_date)),
				"industry_class": self.industry_class,
				"cap": calculation.coida_annual_earnings_cap,
				"cap_rule": calculation.cap_rate_rule,
				"assessment_rate": calculation.assessment_rate,
				"assessment_rule": calculation.assessment_rate_rule,
				"employer_category": self.employer_category,
				"minimum_assessment": calculation.minimum_assessment,
				"minimum_rule": calculation.minimum_assessment_rule,
				"rows": snapshots,
			}
		)
		return calculation

	def _apply_calculation(self, calculation: frappe._dict) -> None:
		self.set("earnings_snapshot", [])
		for row in calculation.earnings_snapshot:
			self.append("earnings_snapshot", row)
		for fieldname in (
			"total_employees",
			"source_slip_count",
			*MONEY_FIELDS,
			"cap_rate_rule",
			"cap_rate_source",
			"assessment_rate_rule",
			"assessment_rate_source",
			"minimum_assessment_rule",
			"minimum_assessment_source",
			"source_snapshot_hash",
		):
			self.set(fieldname, calculation.get(fieldname))
		self.calculated_on = now_datetime()

	def _compare_authoritative_totals(self, calculation: frappe._dict) -> None:
		for fieldname in ("total_employees", "source_slip_count", *MONEY_FIELDS):
			current = flt(self.get(fieldname), 2)
			expected = flt(calculation.get(fieldname), 2)
			if current != expected:
				frappe.throw(
					_("{0} changed from {1} to {2}. Fetch Earnings before submission.").format(
						self.meta.get_label(fieldname),
						current,
						expected,
					),
					title=_("COIDA Return Is Stale"),
				)

	def _get_explicit_directors(self, employees: set[str]) -> set[str]:
		if not employees:
			return set()
		if not frappe.get_meta("Employee").has_field("za_coida_director"):
			frappe.throw(_("Employee field za_coida_director is required for deterministic COIDA reporting."))
		return set(
			frappe.get_all(
				"Employee",
				filters={"name": ["in", sorted(employees)], "za_coida_director": 1},
				pluck="name",
			)
		)
