"""South African controls for HRMS Employee Separation."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now
from hrms.hr.doctype.employee_separation.employee_separation import EmployeeSeparation
from za_local_core.localisation import is_south_african_company

from za_local_payroll.utils.termination_utils import (
	calculate_bcea_notice_period,
	calculate_completed_service_years,
	calculate_leave_payout_on_termination,
	calculate_severance_pay,
)

REMUNERATION_REVIEW_ROLES = {"HR Manager", "System Manager"}
REMUNERATION_SNAPSHOT_FIELDS = (
	"za_bcea_weekly_remuneration",
	"za_bcea_daily_remuneration",
	"za_bcea_remuneration_basis",
)


class ZAEmployeeSeparation(EmployeeSeparation):
	"""Calculate auditable BCEA settlement values from governed inputs."""

	@property
	def za_localisation_applies(self) -> bool:
		"""Whether BCEA termination rules govern this separation's company."""
		company = self.get("company")
		if not company and self.get("employee"):
			company = frappe.get_cached_value("Employee", self.employee, "company")
		return is_south_african_company(company)

	def validate(self):
		super().validate()
		if not self.za_localisation_applies:
			return
		employee = frappe.get_cached_doc("Employee", self.employee)
		termination_date = self._set_actual_termination_date(employee)
		self._validate_termination_type()
		self._validate_remuneration_review()
		self.za_notice_period_days = calculate_bcea_notice_period(employee, termination_date)
		self.za_completed_service_years = calculate_completed_service_years(
			employee.date_of_joining, termination_date
		)
		self.za_severance_pay = calculate_severance_pay(
			employee,
			termination_date,
			self.za_termination_type,
			weekly_remuneration=self.za_bcea_weekly_remuneration,
			remuneration_reviewed=self.za_bcea_remuneration_reviewed,
		)
		leave_payout = calculate_leave_payout_on_termination(
			employee,
			termination_date,
			daily_remuneration=self.za_bcea_daily_remuneration,
			remuneration_reviewed=self.za_bcea_remuneration_reviewed,
		)
		self.za_leave_payout_days = leave_payout["days"]
		self.za_leave_payout = leave_payout["amount"]

	def _set_actual_termination_date(self, employee):
		termination_date = self.za_termination_date or employee.relieving_date
		if not termination_date:
			frappe.throw(
				_(
					"Set Actual Termination Date or the Employee Relieving Date before "
					"calculating the final settlement. Resignation Letter Date is not a "
					"termination-date substitute."
				),
				title=_("Actual Termination Date Required"),
			)
		self.za_termination_date = getdate(termination_date)
		return self.za_termination_date

	def _validate_termination_type(self):
		if not self.za_termination_type:
			frappe.throw(
				_("Termination Type is required for the South African final settlement."),
				title=_("Termination Type Required"),
			)

	def _validate_remuneration_review(self):
		if not cint(self.za_bcea_remuneration_reviewed):
			self.za_bcea_remuneration_reviewed_by = None
			self.za_bcea_remuneration_reviewed_on = None
			return

		if not (self.za_bcea_remuneration_basis or "").strip():
			frappe.throw(
				_("Document the BCEA remuneration basis before marking it reviewed."),
				title=_("Remuneration Basis Required"),
			)

		roles = set(frappe.get_roles(frappe.session.user))
		if not roles.intersection(REMUNERATION_REVIEW_ROLES):
			frappe.throw(
				_("Only an HR Manager or System Manager may confirm BCEA remuneration."),
				frappe.PermissionError,
				title=_("BCEA Remuneration Review Not Permitted"),
			)

		previous = self.get_doc_before_save()
		snapshot_changed = not previous or any(
			previous.get(fieldname) != self.get(fieldname) for fieldname in REMUNERATION_SNAPSHOT_FIELDS
		)
		if snapshot_changed or not self.za_bcea_remuneration_reviewed_by:
			self.za_bcea_remuneration_reviewed_by = frappe.session.user
			self.za_bcea_remuneration_reviewed_on = now()

	@frappe.whitelist(methods=["POST"])
	def create_final_settlement(self):
		"""Create one final-settlement document from the reviewed snapshot."""
		self.check_permission("write")
		if not self.za_localisation_applies:
			frappe.throw(
				_("Final Settlement is a South African statutory process and does not apply to {0}.").format(
					self.get("company") or self.employee
				)
			)
		frappe.has_permission("Employee Final Settlement", "create", throw=True)
		if self.docstatus != 1:
			frappe.throw(_("Employee Separation must be submitted first"))

		existing = frappe.db.exists("Employee Final Settlement", {"employee": self.employee})
		if existing:
			frappe.throw(_("Final Settlement already created: {0}").format(existing))

		settlement = frappe.get_doc(
			{
				"doctype": "Employee Final Settlement",
				"employee": self.employee,
				"separation_date": self.za_termination_date,
				"termination_type": self.za_termination_type,
				"notice_period_days": self.za_notice_period_days,
				"severance_pay": flt(self.za_severance_pay),
				"leave_payout": flt(self.za_leave_payout),
			}
		).insert()

		frappe.msgprint(_("Final Settlement created: {0}").format(settlement.name))
		return settlement.name
