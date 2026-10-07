"""Seed and apply the BCEA leave standards on HRMS.

What this module does, and what it deliberately leaves to a person:

* ``ensure_bcea_leave_standards`` creates the BCEA Leave Types (inert until a policy
  allocates them) and draft template Leave Policies. It never edits a Leave Type or
  Leave Policy that already exists, and never submits a policy.
* ``create_company_leave_policies`` builds company-named draft policies from the
  templates. A policy below the statutory minimum is refused.
* ``assign_leave_policy_by_cycle`` assigns a submitted policy to employees on their
  own 12-month service cycle.
* ``allocate_sick_leave_by_cycle`` grants sick leave on the 36-month cycle as a direct
  Leave Allocation, because HRMS allows only one policy assignment per employee for any
  overlapping period.

Submitting a Leave Policy is the step that enables it. A second person should do it.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate
from za_local_core.localisation import get_south_african_companies

from za_local_payroll.utils.bcea_leave import (
	ANNUAL,
	FAMILY,
	SICK,
	annual_leave_days,
	family_leave_days,
	leave_type_specs,
	policy_templates,
	service_cycle,
	sick_leave_allocation,
	sick_leave_days,
	validate_not_below_minimum,
)

LEAVE_ROLES = ("HR Manager", "System Manager")


def ensure_bcea_leave_standards() -> dict:
	"""Create missing BCEA Leave Types and draft template policies. Idempotent."""
	summary = {"leave_types": [], "policies": []}
	if not get_south_african_companies():
		return summary
	if not frappe.db.exists("DocType", "Leave Policy"):
		return summary
	if not frappe.get_meta("Leave Type").has_field("za_bcea_compliant"):
		return summary

	for spec in leave_type_specs():
		name = spec["leave_type_name"]
		if frappe.db.exists("Leave Type", name):
			continue
		frappe.get_doc({"doctype": "Leave Type", "za_bcea_compliant": 1, **spec}).insert(
			ignore_permissions=True
		)
		summary["leave_types"].append(name)

	for template in policy_templates():
		if frappe.db.exists("Leave Policy", {"title": template["title"]}):
			continue
		_insert_policy(template["title"], template["allocations"])
		summary["policies"].append(template["title"])
	return summary


def _insert_policy(title: str, allocations: dict[str, float]) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Leave Policy",
			"title": title,
			"leave_policy_details": [
				{"leave_type": leave_type, "annual_allocation": days}
				for leave_type, days in allocations.items()
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist(methods=["POST"])
def create_company_leave_policies(
	company: str,
	work_days_per_week: int = 5,
	annual_days: float | None = None,
	family_days: float | None = None,
) -> dict:
	"""Create a draft annual and family responsibility Leave Policy for a company.

	Days default to the statutory minimum. An employer may grant more, never less.
	The policy stays in draft: someone other than the preparer submits it.
	"""
	frappe.only_for(LEAVE_ROLES)
	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("You cannot access company {0}.").format(company), frappe.PermissionError)
	weeks = cint(work_days_per_week)
	annual = float(annual_days) if annual_days not in (None, "") else annual_leave_days(weeks)
	family = float(family_days) if family_days not in (None, "") else family_leave_days()
	validate_not_below_minimum({ANNUAL: annual, FAMILY: family}, weeks)
	title = f"{company} - Annual and Family Leave - {weeks}-day week"
	existing = frappe.db.get_value("Leave Policy", {"title": title}, "name")
	return {"annual_family": existing or _insert_policy(title, {ANNUAL: annual, FAMILY: family})}


@frappe.whitelist(methods=["POST"])
def assign_leave_policy_by_cycle(
	leave_policy: str,
	company: str,
	employees: list | str | None = None,
	as_of: str | None = None,
	carry_forward: int | None = None,
	dry_run: int = 1,
) -> list[dict]:
	"""Assign a submitted Leave Policy on each employee's own service cycle.

	The cycle is 12 months from the date of joining. The assignment starts on the cycle's
	start date and ends the day before the next cycle begins. With ``dry_run`` set,
	nothing is created.
	"""
	frappe.only_for(LEAVE_ROLES)
	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("You cannot access company {0}.").format(company), frappe.PermissionError)
	policy = frappe.get_doc("Leave Policy", leave_policy)
	if policy.docstatus != 1:
		frappe.throw(
			_("Leave Policy {0} is a draft. Have it reviewed and submitted before assigning it.").format(
				leave_policy
			),
			title=_("Policy Not Submitted"),
		)
	reference = getdate(as_of or nowdate())
	filters = {"company": company, "status": "Active", "date_of_joining": ["<=", reference]}
	if employees:
		names = frappe.parse_json(employees) if isinstance(employees, str) else employees
		filters["name"] = ["in", names]
	if carry_forward is None:
		carry_forward = 1 if any(row.leave_type == ANNUAL for row in policy.leave_policy_details) else 0

	plan = []
	for employee in frappe.get_all(
		"Employee", filters=filters, fields=["name", "employee_name", "date_of_joining"], order_by="name"
	):
		start, end = service_cycle(employee.date_of_joining, reference, 12)
		existing = frappe.db.exists(
			"Leave Policy Assignment",
			{
				"employee": employee.name,
				"leave_policy": leave_policy,
				"docstatus": 1,
				"effective_from": start,
			},
		)
		row = {
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"effective_from": str(start),
			"effective_to": str(end),
			"action": "skip (already assigned)" if existing else "assign",
		}
		if not existing and not cint(dry_run):
			doc = frappe.get_doc(
				{
					"doctype": "Leave Policy Assignment",
					"employee": employee.name,
					"leave_policy": leave_policy,
					"effective_from": start,
					"effective_to": end,
					"carry_forward": cint(carry_forward),
				}
			)
			doc.insert()
			doc.submit()
			row["assignment"] = doc.name
		plan.append(row)
	return plan


@frappe.whitelist(methods=["POST"])
def allocate_sick_leave_by_cycle(
	company: str,
	work_days_per_week: int = 5,
	sick_days: float | None = None,
	employees: list | str | None = None,
	as_of: str | None = None,
	already_taken: dict | str | None = None,
	dry_run: int = 1,
) -> list[dict]:
	"""Grant sick leave for each employee's current 36-month cycle.

	One Leave Allocation per employee, from the cycle start to the day before the next
	cycle. ``already_taken`` maps employee to days used earlier in the cycle outside this
	system. The full cycle entitlement is granted from day one, which is more generous
	than the Act's one day per 26 days worked in the first six months, and so permitted.
	"""
	frappe.only_for(LEAVE_ROLES)
	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("You cannot access company {0}.").format(company), frappe.PermissionError)
	reference = getdate(as_of or nowdate())
	taken = frappe.parse_json(already_taken) if isinstance(already_taken, str) else (already_taken or {})
	filters = {"company": company, "status": "Active", "date_of_joining": ["<=", reference]}
	if employees:
		names = frappe.parse_json(employees) if isinstance(employees, str) else employees
		filters["name"] = ["in", names]

	plan = []
	for employee in frappe.get_all(
		"Employee", filters=filters, fields=["name", "employee_name", "date_of_joining"], order_by="name"
	):
		spec = sick_leave_allocation(
			employee.date_of_joining,
			reference,
			cint(work_days_per_week),
			sick_days,
			float(taken.get(employee.name) or 0),
		)
		existing = frappe.db.exists(
			"Leave Allocation",
			{
				"employee": employee.name,
				"leave_type": SICK,
				"docstatus": 1,
				"from_date": spec["from_date"],
			},
		)
		row = {
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"from_date": str(spec["from_date"]),
			"to_date": str(spec["to_date"]),
			"days": spec["days"],
			"action": "skip (already allocated)" if existing else "allocate",
		}
		if not existing and not cint(dry_run):
			doc = frappe.get_doc(
				{
					"doctype": "Leave Allocation",
					"employee": employee.name,
					"leave_type": SICK,
					"from_date": spec["from_date"],
					"to_date": spec["to_date"],
					"new_leaves_allocated": spec["days"],
					"description": _("BCEA sick leave: 36-month cycle"),
				}
			)
			doc.insert()
			doc.submit()
			row["allocation"] = doc.name
		plan.append(row)
	return plan
