"""South African controls for HRMS Leave Application."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_years, cint, date_diff, flt, getdate
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication

ANNUAL_LEAVE_CATEGORY = "Annual Leave"
FAMILY_RESPONSIBILITY_CATEGORY = "Family Responsibility Leave"
SICK_LEAVE_CATEGORY = "Sick Leave"
MEDICAL_CERTIFICATE_THRESHOLD_DAYS = 2
REPEATED_ABSENCE_LOOKBACK_DAYS = 56


class ZALeaveApplication(LeaveApplication):
	"""Apply configured BCEA leave controls without inferring from names."""

	def validate(self):
		super().validate()
		leave_type = self._get_governed_leave_type()
		if leave_type:
			self.validate_medical_certificate(leave_type)
			self.validate_bcea_requirements(leave_type)
		self.validate_gender_specific_leave()

	def _get_governed_leave_type(self):
		if not self.leave_type:
			return None
		leave_type = frappe.get_cached_doc("Leave Type", self.leave_type)
		if not cint(leave_type.za_bcea_compliant):
			return None
		if not leave_type.za_bcea_leave_category:
			frappe.throw(
				_("Set BCEA Leave Category on Leave Type {0} before using BCEA validation.").format(
					self.leave_type
				),
				title=_("BCEA Leave Category Required"),
			)
		return leave_type

	def validate_medical_certificate(self, leave_type):
		"""Require evidence for long or repeated governed sick-leave occasions."""
		if leave_type.za_bcea_leave_category != SICK_LEAVE_CATEGORY:
			return

		configured_threshold = cint(leave_type.za_medical_certificate_required_after)
		threshold = (
			min(MEDICAL_CERTIFICATE_THRESHOLD_DAYS, configured_threshold)
			if configured_threshold > 0
			else MEDICAL_CERTIFICATE_THRESHOLD_DAYS
		)
		reasons = []
		consecutive_calendar_days = date_diff(self.to_date, self.from_date) + 1
		if consecutive_calendar_days > threshold:
			reasons.append(_("the absence exceeds {0} consecutive days").format(threshold))

		prior_occasions = self._count_prior_sick_leave_occasions()
		if prior_occasions >= 2:
			reasons.append(_("this is more than the second sick-leave occasion within eight weeks"))

		if reasons and not self._has_medical_certificate():
			frappe.throw(
				_("Medical-certificate evidence is required because {0}.").format(_(" and ").join(reasons)),
				title=_("Medical Certificate Required"),
			)

	def _count_prior_sick_leave_occasions(self) -> int:
		sick_leave_types = frappe.get_all(
			"Leave Type",
			filters={
				"za_bcea_compliant": 1,
				"za_bcea_leave_category": SICK_LEAVE_CATEGORY,
			},
			pluck="name",
		)
		if not sick_leave_types:
			return 0

		current_start = getdate(self.from_date)
		window_start = add_days(current_start, -REPEATED_ABSENCE_LOOKBACK_DAYS)
		applications = frappe.get_all(
			"Leave Application",
			filters={
				"employee": self.employee,
				"leave_type": ["in", sick_leave_types],
				"docstatus": 1,
				"name": ["!=", self.name or "New"],
				"from_date": ["<=", current_start],
				"to_date": [">=", window_start],
			},
			fields=["from_date", "to_date"],
			order_by="from_date asc, to_date asc",
		)
		return count_distinct_leave_occasions(applications)

	def _has_medical_certificate(self) -> bool:
		return bool(self.za_medical_certificate)

	def validate_bcea_requirements(self, leave_type):
		category = leave_type.za_bcea_leave_category
		if category == ANNUAL_LEAVE_CATEGORY:
			self.validate_annual_leave_bcea()
		elif category == FAMILY_RESPONSIBILITY_CATEGORY:
			self.validate_family_leave_bcea()

	def validate_annual_leave_bcea(self):
		if flt(self.total_leave_days) >= 21:
			frappe.msgprint(
				_("This application records at least 21 consecutive days of annual leave."),
				indicator="blue",
				title=_("Annual Leave Review"),
			)

	def validate_family_leave_bcea(self):
		"""Enforce the configured three-day cap in the employee's service cycle."""
		employee = frappe.get_cached_doc("Employee", self.employee)
		cycle_start, cycle_end = get_service_anniversary_cycle(employee.date_of_joining, self.from_date)
		family_leave_types = frappe.get_all(
			"Leave Type",
			filters={
				"za_bcea_compliant": 1,
				"za_bcea_leave_category": FAMILY_RESPONSIBILITY_CATEGORY,
			},
			pluck="name",
		)
		applications = frappe.get_all(
			"Leave Application",
			filters={
				"employee": self.employee,
				"leave_type": ["in", family_leave_types],
				"from_date": [">=", cycle_start],
				"to_date": ["<=", cycle_end],
				"docstatus": 1,
				"name": ["!=", self.name or "New"],
			},
			fields=["total_leave_days"],
		)
		total_taken = sum(flt(row.total_leave_days) for row in applications)
		if total_taken + flt(self.total_leave_days) > 3:
			frappe.throw(
				_(
					"Family responsibility leave exceeds the configured three-day cap for "
					"the current service cycle. Already taken: {0} days."
				).format(total_taken),
				title=_("Family Responsibility Leave Limit"),
			)

	def validate_gender_specific_leave(self):
		if not self.leave_type:
			return
		leave_type = frappe.get_cached_doc("Leave Type", self.leave_type)
		if not leave_type.za_applicable_gender:
			return
		employee_gender = frappe.get_cached_value("Employee", self.employee, "gender")
		if employee_gender != leave_type.za_applicable_gender:
			frappe.throw(
				_("Leave type {0} is only configured for {1} employees.").format(
					self.leave_type, leave_type.za_applicable_gender
				)
			)


def count_distinct_leave_occasions(applications) -> int:
	"""Merge touching date ranges so one illness is counted once."""
	periods = sorted(
		((getdate(row.from_date), getdate(row.to_date)) for row in applications),
		key=lambda period: (period[0], period[1]),
	)
	if not periods:
		return 0

	count = 1
	current_end = periods[0][1]
	for from_date, to_date in periods[1:]:
		if from_date <= add_days(current_end, 1):
			current_end = max(current_end, to_date)
			continue
		count += 1
		current_end = to_date
	return count


def get_service_anniversary_cycle(date_of_joining, reference_date):
	"""Return the 12-month service cycle containing the reference date."""
	if not date_of_joining:
		frappe.throw(_("Employee Date of Joining is required for leave-cycle validation."))
	joining_date = getdate(date_of_joining)
	reference = getdate(reference_date)
	cycle_start = add_years(joining_date, reference.year - joining_date.year)
	if cycle_start > reference:
		cycle_start = add_years(joining_date, reference.year - joining_date.year - 1)
	cycle_end = add_days(add_years(cycle_start, 1), -1)
	return cycle_start, cycle_end
