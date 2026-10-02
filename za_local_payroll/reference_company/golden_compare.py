"""Build golden inputs from persona/schedule facts and compare them with submitted slips.

The inputs come from personas.PERSONAS and schedule.py (the facts given to the
system), classified by statute rather than by the app's component configuration.
Statutory outputs come only from golden_engine. Salary Slips are read solely to
compare against.
"""

import json
from datetime import date

import frappe
from frappe.utils import flt, get_last_day

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.golden_engine import GoldenEngine, Month, d
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.payroll_run import employee_for
from za_local_payroll.reference_company.payroll_setup import EVIDENCE
from za_local_payroll.reference_company.personas import PERSONAS
from za_local_payroll.reference_company.schedule import ADDITIONAL_SALARY, MONTHS, TERMINATION

PAYE_TOLERANCE = 0.02  # rounding of the cumulative average method only
TOLERANCE = 0.01

ANNUAL_COMPONENTS = {"Performance Bonus", "13th Cheque", "Leave Payout", "Notice Pay"}
REGULAR_COMPONENTS = {"Overtime", "Commission"}
NON_REMUNERATION = {"Reimbursive Travel", "Business Expense Reimbursement"}


def _month_key(day: date) -> str:
	return f"{day.year}-{day.month:02d}"


def build_golden(engine: GoldenEngine) -> dict:
	results = {}
	for key, (
		_first,
		_last,
		_gender,
		dob,
		joining,
		structure,
		base,
		variable,
		hours,
		_race,
		_level,
		extra,
	) in PERSONAS.items():
		if structure in ("ZA Ref Weekly", "ZA Ref Fortnightly", "ZA Ref Hourly Timesheet"):
			continue
		start = max(d(joining), d("2026-03-01"))
		relieving = d(extra["relieving"]) if extra.get("relieving") else None
		months = []
		for mk in MONTHS:
			first_day = d(f"{mk}-01")
			last_day = get_last_day(first_day)
			if last_day < start or (relieving and first_day > relieving):
				continue
			m = Month(period=mk)
			basic = base
			if change := extra.get("salary_change"):
				if first_day >= d(change[0]):
					basic = change[1]
			for persona, component, amount, month, kind in ADDITIONAL_SALARY:
				if persona == key and component == "Basic" and kind == "overwrite" and month == mk:
					basic = amount
			_add(m, basic, regular=True)
			if structure == "ZA Ref Monthly Pension":
				m.retirement += round(basic * 0.075, 2)
				m.employer_pension += round(basic * 0.10, 2)
			if structure == "ZA Ref Monthly Retirement Cap":
				m.retirement += round(basic * 0.20, 2) + 10000
			if structure in ("ZA Ref Monthly Medical", "ZA Ref Monthly Medical Employer"):
				m.other_deductions += variable
			if structure == "ZA Ref Monthly Medical Employer":
				m.regular += 2000  # employer contribution: taxable benefit, non-cash
				m.sdl_remuneration += 2000
			if structure == "ZA Ref Monthly Travel":
				m.regular += variable * 0.80
				m.sdl_remuneration += variable * 0.80
				m.cash_earnings += variable
				m.uif_basis += variable
			if structure == "ZA Ref Monthly Allowances":
				_add(m, 500, regular=True)  # cellphone allowance (taxable)
				m.cash_earnings += 300  # uniform allowance (exempt)
				m.other_deductions += 150  # union subscription
			if medical := extra.get("medical"):
				if first_day >= d(medical[0]):
					m.medical_member, m.medical_dependants = True, medical[2]
			if extra.get("fringe"):
				car = 450000 * 3.25 / 100
				m.regular += car * 0.80
				m.sdl_remuneration += car * 0.80
				loan = engine.loan_benefit(100000, 2, first_day, last_day)
				m.regular += loan
				m.sdl_remuneration += loan
			for persona, component, amount, month, kind in ADDITIONAL_SALARY:
				if persona != key or component == "Basic":
					continue
				active = (
					month == mk if not kind.startswith("recurring") else (month <= mk <= kind.split(":")[1])
				)
				if not active:
					continue
				if component in NON_REMUNERATION:
					m.cash_earnings += amount
				elif component in ANNUAL_COMPONENTS:
					_add(m, amount, regular=False)
				else:
					_add(m, amount, regular=True)
			if relieving and _month_key(relieving) == mk:
				daily = 32000 * 12 / 260
				_add(m, round(daily * TERMINATION["leave_days"], 2), regular=False)
				_add(m, TERMINATION["notice_pay"], regular=False)
				m.cash_earnings += TERMINATION["severance"]
				m.lump_sum_tax = TERMINATION["directive_tax"]
			m.eti_remuneration = basic
			months.append(m)
		engine.run_employee(d(dob), months)
		if key in ("P10_eti_eligible", "P11_eti_age_fail", "P12_eti_part_time", "P20_it3a_no_paye"):
			for index, m in enumerate(months, start=1):
				eligible = 18 <= _age_end_of_month(dob, m.period) <= 29
				m.out["eti"] = engine.eti(m.eti_remuneration, index, hours) if eligible else 0.0
		results[key] = {
			m.period: {
				**m.out,
				"regular": round(m.regular, 2),
				"annual": m.annual,
				"cash_earnings": round(m.cash_earnings, 2),
				"employer_pension": round(m.employer_pension, 2),
			}
			for m in months
		}
	return results


def _age_end_of_month(dob: str, period: str) -> int:
	born = d(dob)
	end = get_last_day(d(f"{period}-01"))
	return end.year - born.year - ((end.month, end.day) < (born.month, born.day))


def _add(m: Month, amount: float, regular: bool):
	if regular:
		m.regular += amount
	else:
		m.annual += amount
	m.cash_earnings += amount
	m.uif_basis += amount
	m.sdl_remuneration += amount


def actual_slip(slip_name: str) -> dict:
	s = frappe.get_doc("Salary Slip", slip_name)
	comp = {r.salary_component: flt(r.amount) for r in s.company_contribution}
	ded = {r.salary_component: flt(r.amount) for r in s.deductions}
	cash = sum(
		flt(r.amount)
		for r in s.earnings
		if not frappe.get_cached_value("Salary Component", r.salary_component, "do_not_include_in_total")
	)
	return {
		"slip": s.name,
		"paye": ded.get("PAYE", 0),
		"uif_employee": ded.get("UIF Employee Contribution", 0),
		"uif_employer": comp.get("UIF Employer Contribution", 0),
		"sdl": comp.get("SDL Contribution", 0),
		"eti": flt(s.za_monthly_eti),
		"net_pay": flt(s.net_pay),
		"cash_earnings": round(cash, 2),
		"employer_pension": comp.get("Employer Pension Contribution", 0),
	}


def compare_year() -> dict:
	require_reference_site()
	engine = GoldenEngine(paths.GOLDEN_FILE)
	golden = build_golden(engine)
	rows, failures = [], []
	for key, months in golden.items():
		employee = employee_for(key)
		for period, expected in months.items():
			slip = frappe.db.get_value(
				"Salary Slip",
				{
					"employee": employee,
					"start_date": f"{period}-01",
					"docstatus": 1,
					"payroll_frequency": "Monthly",
				},
				"name",
			)
			if not slip:
				failures.append(
					{"persona": key, "period": period, "field": "slip", "issue": "missing submitted slip"}
				)
				continue
			actual = actual_slip(slip)
			row = {"persona": key, "period": period, "slip": slip}
			for fieldname in (
				"paye",
				"uif_employee",
				"uif_employer",
				"sdl",
				"net_pay",
				"cash_earnings",
				"eti",
				"employer_pension",
			):
				if fieldname not in expected:
					continue
				exp, act = flt(expected[fieldname], 2), flt(actual[fieldname], 2)
				tol = PAYE_TOLERANCE if fieldname in ("paye", "net_pay") else TOLERANCE
				diff = round(act - exp, 2)
				row[fieldname] = {"expected": exp, "actual": act, "diff": diff}
				if abs(diff) > tol:
					failures.append(
						{
							"persona": key,
							"period": period,
							"field": fieldname,
							"expected": exp,
							"actual": act,
							"diff": diff,
						}
					)
			rows.append(row)
	summary = {"compared_slips": len(rows), "failures": len(failures)}
	by_field = {}
	for f in failures:
		by_field.setdefault(f["field"], []).append(f"{f['persona']} {f['period']} {f.get('diff')}")
	summary["failures_by_field"] = {k: len(v) for k, v in by_field.items()}
	EVIDENCE.mkdir(parents=True, exist_ok=True)
	(EVIDENCE / "golden_payroll_expected.json").write_text(json.dumps(golden, indent=1, default=str))
	(EVIDENCE / "golden_payroll_comparison.json").write_text(
		json.dumps({"summary": summary, "failures": failures, "rows": rows}, indent=1, default=str)
	)
	return {"summary": summary, "failures": failures[:80]}


def compare_frequencies() -> dict:
	"""Weekly, fortnightly and timesheet slips against the golden engine."""
	require_reference_site()
	engine = GoldenEngine(paths.GOLDEN_FILE)
	cap = engine.g["uif"]["monthly_ceiling"]
	out = {}
	for key, _frequency, periods, amount in (
		("W01_weekly", "Weekly", 52, 6000),
		("F01_fortnightly", "Fortnightly", 26, 12000),
	):
		employee = employee_for(key)
		slips = frappe.get_all(
			"Salary Slip",
			filters={"employee": employee, "docstatus": 1},
			fields=["name", "start_date"],
			order_by="start_date",
		)
		months = []
		for s in slips:
			m = Month(period=str(s.start_date))
			_add(m, amount, regular=True)
			months.append(m)
		dob = PERSONAS[key][3]
		engine.run_employee(d(dob), months, periods_in_year=periods, uif_cap=round(cap * 12 / periods, 2))
		out[key] = [
			{
				"slip": s.name,
				"expected": {k: m.out[k] for k in ("paye", "uif_employee", "sdl")},
				"actual": {k: actual_slip(s.name)[k] for k in ("paye", "uif_employee", "sdl")},
				"uif_cap_period": round(cap * 12 / periods, 2),
			}
			for s, m in zip(slips, months, strict=True)
		]
	h = employee_for("H01_hourly")
	slip = frappe.db.get_value("Salary Slip", {"employee": h, "docstatus": 1}, "name")
	if slip:
		m = Month(period="2026-09")
		hours = sum(flt(r.working_hours) for r in frappe.get_doc("Salary Slip", slip).timesheets)
		_add(m, hours * 150, regular=True)
		engine.run_employee(d(PERSONAS["H01_hourly"][3]), [m])
		out["H01_hourly"] = {"hours": hours, "expected": m.out, "actual": actual_slip(slip)}
	(EVIDENCE / "golden_frequency_comparison.json").write_text(json.dumps(out, indent=1, default=str))
	return out
