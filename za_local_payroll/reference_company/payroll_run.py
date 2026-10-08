"""Stage 8: run the 2026/27 payroll year month by month for the reference company."""

import json

import frappe
from frappe.utils import add_days, get_first_day, get_last_day, getdate

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site
from za_local_payroll.reference_company.payroll_setup import a
from za_local_payroll.reference_company.schedule import (
	ADDITIONAL_SALARY,
	CANCELLED_ADDITIONAL_SALARY,
	MONTHS,
	TERMINATION,
)


def employee_for(persona: str) -> str:
	from za_local_payroll.reference_company.personas import PERSONAS, sa_id

	keys = list(PERSONAS)
	spec = PERSONAS[persona]
	return frappe.db.get_value(
		"Employee", {"za_id_number": sa_id(spec[3], keys.index(persona) + 1, spec[2])}, "name"
	)


def month_bounds(month: str):
	start = getdate(f"{month}-01")
	return start, get_last_day(start)


def stage_additional_salaries() -> dict:
	require_reference_site()
	created = []
	for persona, component, amount, month, kind in ADDITIONAL_SALARY:
		employee = employee_for(persona)
		start, end = month_bounds(month)
		filters = {"employee": employee, "salary_component": component, "amount": amount, "docstatus": 1}
		if frappe.db.exists(
			"Additional Salary", filters | ({"payroll_date": end} if kind != "recurring" else {})
		):
			continue
		doc = {
			"doctype": "Additional Salary",
			"employee": employee,
			"company": C.COMPANY,
			"salary_component": component,
			"amount": amount,
			"currency": "ZAR",
			"payroll_date": end,
		}
		if kind.startswith("recurring"):
			to_month = kind.split(":")[1]
			doc.update(
				{
					"is_recurring": 1,
					"from_date": start,
					"to_date": month_bounds(to_month)[1],
					"payroll_date": None,
				}
			)
		if kind == "overwrite":
			doc["overwrite_salary_structure_amount"] = 1
		if component in ("Performance Bonus", "13th Cheque"):
			doc["deduct_full_tax_on_selected_payroll_date"] = 1
		add = frappe.get_doc(doc)
		add.insert(ignore_permissions=True)
		add.submit()
		created.append(add.name)
	for persona, component, amount, month in CANCELLED_ADDITIONAL_SALARY:
		employee = employee_for(persona)
		if frappe.db.exists("Additional Salary", {"employee": employee, "amount": amount, "docstatus": 2}):
			continue
		add = frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": employee,
				"company": C.COMPANY,
				"salary_component": component,
				"amount": amount,
				"currency": "ZAR",
				"payroll_date": month_bounds(month)[1],
			}
		)
		add.insert(ignore_permissions=True)
		add.submit()
		add.cancel()
		created.append(f"{add.name} (cancelled)")
	commit_stage()
	return {"created": created}


def stage_termination_inputs() -> dict:
	"""Termination earnings for the leaver, entered through Additional Salary (supported flow)."""
	require_reference_site()
	t = TERMINATION
	employee = employee_for(t["persona"])
	frappe.db.set_value("Employee", employee, "relieving_date", t["relieving_date"])
	end = getdate(t["relieving_date"])
	daily = 32000 * 12 / 260
	leave = round(daily * t["leave_days"], 2)
	out = {"employee": employee, "leave_payout": leave}
	for component, amount in (
		("Leave Payout", leave),
		("Notice Pay", t["notice_pay"]),
		("Severance Benefit", t["severance"]),
	):
		if not frappe.db.exists(
			"Additional Salary", {"employee": employee, "salary_component": component, "docstatus": 1}
		):
			add = frappe.get_doc(
				{
					"doctype": "Additional Salary",
					"employee": employee,
					"company": C.COMPANY,
					"salary_component": component,
					"amount": amount,
					"currency": "ZAR",
					"payroll_date": end,
					"deduct_full_tax_on_selected_payroll_date": int(component != "Severance Benefit"),
				}
			)
			add.insert(ignore_permissions=True)
			add.submit()
	if not frappe.db.exists("Tax Directive", {"directive_number": t["directive_number"]}):
		directive = frappe.get_doc(
			{
				"doctype": "Tax Directive",
				"employee": employee,
				"company": C.COMPANY,
				"directive_number": t["directive_number"],
				"directive_type": "Severance / Lump Sum",
				"effective_from": "2026-11-01",
				"effective_to": "2027-02-28",
				"fixed_amount": t["directive_tax"],
				"notes": "SYNTHETIC directive - not issued by SARS",
			}
		)
		directive.insert(ignore_permissions=True)
		directive.submit()
		out["directive"] = directive.name
	commit_stage()
	return out


def run_month(
	month: str, frequency: str = "Monthly", timesheet: int = 0, submit: bool = True, start=None, end=None
) -> dict:
	require_reference_site()
	if not start:
		start, end = month_bounds(month)
	existing = frappe.db.get_value(
		"Payroll Entry",
		{
			"company": C.COMPANY,
			"start_date": start,
			"end_date": end,
			"payroll_frequency": frequency,
			"salary_slip_based_on_timesheet": timesheet,
			"docstatus": 1,
		},
		"name",
	)
	if existing:
		return {"payroll_entry": existing, "existing": True}
	pe = frappe.get_doc(
		{
			"doctype": "Payroll Entry",
			"company": C.COMPANY,
			"posting_date": end,
			"payroll_frequency": frequency,
			"start_date": start,
			"end_date": end,
			"currency": "ZAR",
			"exchange_rate": 1,
			"payroll_payable_account": a("Payroll Payable"),
			"cost_center": f"Head Office - {C.ABBR}",
			"payment_account": a("FNB Business Cheque"),
			"salary_slip_based_on_timesheet": timesheet,
		}
	)
	pe.insert(ignore_permissions=True)
	pe.fill_employee_details()
	pe.save(ignore_permissions=True)
	commit_stage()  # Desk saves before Submit; HRMS rolls back on slip errors
	pe.submit()  # creates draft Salary Slips
	pe.reload()
	slips = frappe.get_all("Salary Slip", filters={"payroll_entry": pe.name}, pluck="name")
	out = {"payroll_entry": pe.name, "slips": len(slips)}
	if submit:
		pe.submit_salary_slips()
		commit_stage()
		pe.reload()
		out["contribution_je"] = pe.make_company_contribution_entry()
	commit_stage()
	return out


def run_year(through: str | None = None) -> dict:
	require_reference_site()
	results = {}
	for month in MONTHS:
		if month == "2026-11":
			results["termination_inputs"] = stage_termination_inputs()
		results[month] = run_month(month)
		if through and month == through:
			break
	paths.payroll().mkdir(parents=True, exist_ok=True)
	(paths.payroll() / "payroll_year_runs.json").write_text(json.dumps(results, indent=1, default=str))
	return results


def run_frequencies() -> dict:
	"""Weekly and fortnightly runs for September 2026, and one timesheet month."""
	require_reference_site()
	out = {}
	week_start = getdate("2026-08-31")  # Monday
	for i in range(4):
		s = add_days(week_start, 7 * i)
		out[f"weekly_{i + 1}"] = run_month(None, "Weekly", start=s, end=add_days(s, 6))
	for i in range(2):
		s = add_days(week_start, 14 * i)
		out[f"fortnight_{i + 1}"] = run_month(None, "Fortnightly", start=s, end=add_days(s, 13))
	out["timesheet"] = _run_timesheet_month("2026-09")
	commit_stage()
	return out


def _run_timesheet_month(month):
	from za_local_payroll.reference_company.personas import PERSONAS

	employee = employee_for("H01_hourly")
	start, end = month_bounds(month)
	if not frappe.db.exists("Timesheet", {"employee": employee, "start_date": [">=", start], "docstatus": 1}):
		activity = (
			"Execution"
			if frappe.db.exists("Activity Type", "Execution")
			else frappe.get_doc({"doctype": "Activity Type", "activity_type": "Execution"})
			.insert(ignore_permissions=True)
			.name
		)
		logs = []
		day = start
		while day <= end and len(logs) < 15:
			if day.weekday() < 5:
				logs.append(
					{
						"activity_type": activity,
						"from_time": f"{day} 08:00:00",
						"to_time": f"{day} 16:00:00",
						"hours": 8,
						"is_billable": 0,
					}
				)
			day = add_days(day, 1)
		ts = frappe.get_doc(
			{"doctype": "Timesheet", "employee": employee, "company": C.COMPANY, "time_logs": logs}
		)
		ts.insert(ignore_permissions=True)
		ts.submit()
	return run_month(month, "Monthly", timesheet=1)


def probe_termination_month() -> dict:
	"""Process November as installed (severance at 100% PAYE inclusion) without submitting,
	capture the leaver's slip, then remove the draft run so it can be reprocessed."""
	require_reference_site()
	inputs = stage_termination_inputs()
	result = run_month("2026-11", submit=False)
	employee = employee_for(TERMINATION["persona"])
	slip = frappe.get_doc("Salary Slip", {"payroll_entry": result["payroll_entry"], "employee": employee})
	captured = {
		"inputs": inputs,
		"earnings": {r.salary_component: r.amount for r in slip.earnings},
		"deductions": {r.salary_component: r.amount for r in slip.deductions},
		"gross": slip.gross_pay,
		"net": slip.net_pay,
		"severance_paye_inclusion": frappe.db.get_value(
			"Salary Component", "Severance Benefit", "za_paye_inclusion_percentage"
		),
	}
	pe = frappe.get_doc("Payroll Entry", result["payroll_entry"])
	pe.cancel()
	commit_stage()
	(paths.payroll() / "termination_probe_as_installed.json").write_text(
		json.dumps(captured, indent=1, default=str)
	)
	return captured


def configure_termination_workaround(non_taxable_severance: bool = True) -> str:
	"""Practitioner workaround for PAY-TERM-1 (configuration only).

	Severance is excluded from annualised PAYE (0% inclusion) and the SARS directive
	tax is deducted through Tax on Lump Sum (code 4115), posting to PAYE Payable.
	"""
	require_reference_site()
	frappe.db.set_value(
		"Salary Component",
		"Severance Benefit",
		{
			"za_paye_inclusion_percentage": 0,
			"za_uif_applicable": 0,
			"za_sdl_applicable": 0,
			"za_coida_applicable": 0,
		},
	)
	lstax = frappe.get_doc("Salary Component", "Tax on Lump Sum")
	if not any(r.company == C.COMPANY for r in lstax.accounts):
		lstax.append("accounts", {"company": C.COMPANY, "account": a("PAYE Payable - SARS")})
		lstax.save(ignore_permissions=True)
	employee = employee_for(TERMINATION["persona"])
	end = getdate(TERMINATION["relieving_date"])
	if not frappe.db.exists(
		"Additional Salary", {"employee": employee, "salary_component": "Tax on Lump Sum", "docstatus": 1}
	):
		add = frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": employee,
				"company": C.COMPANY,
				"salary_component": "Tax on Lump Sum",
				"amount": TERMINATION["directive_tax"],
				"currency": "ZAR",
				"payroll_date": end,
			}
		)
		add.insert(ignore_permissions=True)
		add.submit()
	commit_stage()
	if non_taxable_severance:
		# Final configuration: the directive tax is the only tax on the severance benefit.
		frappe.db.set_value("Salary Component", "Severance Benefit", {"is_tax_applicable": 0})
		commit_stage()
	return employee


def apply_termination_workaround_and_run() -> dict:
	"""Configure the PAY-TERM-1 workaround (taxable severance retained), then run November."""
	require_reference_site()
	employee = configure_termination_workaround(non_taxable_severance=False)
	result = run_month("2026-11")
	slip = frappe.get_doc("Salary Slip", {"payroll_entry": result["payroll_entry"], "employee": employee})
	result["leaver_slip"] = {
		"name": slip.name,
		"earnings": {r.salary_component: r.amount for r in slip.earnings},
		"deductions": {r.salary_component: r.amount for r in slip.deductions},
		"net": slip.net_pay,
	}
	(paths.payroll() / "termination_with_workaround.json").write_text(
		json.dumps(result, indent=1, default=str)
	)
	return result


def cancel_payroll_entry(payroll_entry: str) -> dict:
	"""Cancel a submitted Payroll Entry with submitted slips and its contribution accrual."""
	require_reference_site()
	out = {"payroll_entry": payroll_entry}
	for je in frappe.get_all(
		"Journal Entry Account",
		filters={"reference_type": "Payroll Entry", "reference_name": payroll_entry, "docstatus": 1},
		pluck="parent",
		distinct=True,
	):
		frappe.get_doc("Journal Entry", je).cancel()
		out.setdefault("cancelled_journals", []).append(je)
	slips = frappe.get_all(
		"Salary Slip", filters={"payroll_entry": payroll_entry, "docstatus": 1}, pluck="name"
	)
	for slip in slips:
		frappe.get_doc("Salary Slip", slip).cancel()
	out["cancelled_slips"] = len(slips)
	frappe.get_doc("Payroll Entry", payroll_entry).cancel()
	commit_stage()
	out["gl_rows_live"] = frappe.db.count(
		"GL Entry", {"voucher_no": ["in", out.get("cancelled_journals", [])], "is_cancelled": 0}
	)
	out["eti_logs_live"] = (
		frappe.db.count("Employee ETI Log", {"against_salary_slip": ["in", slips], "docstatus": 1})
		if slips
		else 0
	)
	return out


def rerun_termination_month_non_taxable_severance() -> dict:
	require_reference_site()
	pe = frappe.db.get_value(
		"Payroll Entry",
		{"company": C.COMPANY, "start_date": "2026-11-01", "payroll_frequency": "Monthly", "docstatus": 1},
		"name",
	)
	cancelled = cancel_payroll_entry(pe) if pe else None
	frappe.db.set_value("Salary Component", "Severance Benefit", {"is_tax_applicable": 0})
	commit_stage()
	result = run_month("2026-11")
	employee = employee_for(TERMINATION["persona"])
	slip = frappe.get_doc("Salary Slip", {"payroll_entry": result["payroll_entry"], "employee": employee})
	result.update(
		{
			"cancellation": cancelled,
			"leaver_slip": {
				"name": slip.name,
				"earnings": {r.salary_component: r.amount for r in slip.earnings},
				"deductions": {r.salary_component: r.amount for r in slip.deductions},
				"net": slip.net_pay,
			},
		}
	)
	(paths.payroll() / "termination_final.json").write_text(json.dumps(result, indent=1, default=str))
	return result
