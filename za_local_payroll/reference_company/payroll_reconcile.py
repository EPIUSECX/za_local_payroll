"""Stage 9: payroll GL reconciliation, payment batch, EMP201, IRP5/IT3(a) and EMP501."""

import csv
import io
import json

import frappe
from frappe.utils import flt, get_last_day, getdate

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.payroll_setup import EVIDENCE, a

MONTH_NAMES = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
]


def _try(label, fn, out):
	frappe.db.commit()
	try:
		fn()
	except Exception as exc:
		frappe.db.rollback()
		out[label] = {"blocked": True, "message": frappe.utils.strip_html(str(exc))[:300]}
		return
	out[label] = {"blocked": False}


# ---------------------------------------------------------------- GL ---------------
def reconcile_payroll_gl() -> dict:
	"""Prove Salary Slips = accrual/contribution journals = account movements, per Payroll Entry."""
	require_reference_site()
	results = []
	entries = frappe.get_all(
		"Payroll Entry",
		filters={"company": C.COMPANY, "docstatus": 1},
		fields=["name", "start_date", "end_date", "payroll_frequency", "salary_slip_based_on_timesheet"],
		order_by="start_date",
	)
	for pe in entries:
		slips = frappe.get_all(
			"Salary Slip", filters={"payroll_entry": pe.name, "docstatus": 1}, pluck="name"
		)
		mappings = frappe.get_all(
			"Salary Component Account",
			filters={"company": C.COMPANY},
			fields=["parent", "account", "za_liability_account"],
		)
		comp_accounts = {r.parent: r.account for r in mappings}
		liability_accounts = {r.parent: r.za_liability_account for r in mappings if r.za_liability_account}
		expected = {}
		net = 0.0
		for name in slips:
			s = frappe.get_doc("Salary Slip", name)
			net += flt(s.net_pay)
			for table, sign in (("earnings", 1), ("deductions", -1)):
				for r in s.get(table):
					if frappe.get_cached_value(
						"Salary Component", r.salary_component, "do_not_include_in_accounts"
					):
						continue
					acc = comp_accounts.get(r.salary_component)
					expected[acc] = expected.get(acc, 0) + sign * flt(r.amount)
			for r in s.company_contribution:
				acc = comp_accounts.get(r.salary_component)
				expected[acc] = expected.get(acc, 0) + flt(r.amount)
				liability = liability_accounts.get(r.salary_component)
				if liability:
					# ACC-1 fix: each contribution accrues to its own liability.
					expected[liability] = expected.get(liability, 0) - flt(r.amount)
				else:
					expected["__contrib_payable__"] = expected.get("__contrib_payable__", 0) + flt(r.amount)
		journals = frappe.get_all(
			"Journal Entry Account",
			filters={"reference_type": "Payroll Entry", "reference_name": pe.name, "docstatus": 1},
			pluck="parent",
			distinct=True,
		)
		gl = {}
		for je in journals:
			for g in frappe.get_all(
				"GL Entry",
				filters={"voucher_no": je, "is_cancelled": 0},
				fields=["account", "debit", "credit"],
			):
				gl[g.account] = round(gl.get(g.account, 0) + flt(g.debit) - flt(g.credit), 2)
		payable = a("Payroll Payable")
		# Net pay and employer contributions credit Payroll Payable; any deduction mapped to
		# Payroll Payable itself (e.g. union subscriptions held for remittance) adds to it.
		expected_payable = round(-net - expected.pop("__contrib_payable__", 0) + expected.pop(payable, 0), 2)
		checks = {}
		for acc, amount in expected.items():
			checks[acc] = {
				"expected_net_debit": round(amount, 2),
				"gl_net_debit": gl.get(acc, 0.0),
				"ok": abs(round(amount, 2) - gl.get(acc, 0.0)) <= 0.05,
			}
		checks[payable] = {
			"expected_net_debit": expected_payable,
			"gl_net_debit": gl.get(payable, 0.0),
			"ok": abs(expected_payable - gl.get(payable, 0.0)) <= 0.05,
		}
		results.append(
			{
				"payroll_entry": pe.name,
				"period": f"{pe.start_date}..{pe.end_date}",
				"frequency": pe.payroll_frequency,
				"slips": len(slips),
				"net_pay": round(net, 2),
				"journals": journals,
				"balanced": abs(sum(gl.values())) < 0.01,
				"all_ok": all(c["ok"] for c in checks.values()),
				"checks": checks,
			}
		)
	balances = {}
	for name in (
		"PAYE Payable - SARS",
		"UIF Employee Contribution",
		"UIF Employer Contribution",
		"SDL Payable - SARS",
		"Payroll Payable",
		"Pension Fund Payable",
		"Provident Fund Payable",
		"Retirement Annuity Payable",
		"Medical Aid Payable",
		"Salaries and Wages",
		"UIF Employer Expense",
		"SDL Expense",
		"Pension Fund Employer Expense",
	):
		acc = a(name)
		row = frappe.db.sql(
			"select sum(debit)-sum(credit) from `tabGL Entry` where account=%s and is_cancelled=0", acc
		)[0][0]
		balances[name] = round(flt(row), 2)
	out = {
		"entries": results,
		"account_balances_year": balances,
		"entries_ok": sum(1 for r in results if r["all_ok"] and r["balanced"]),
		"entries_total": len(results),
	}
	(EVIDENCE / "payroll_gl_reconciliation.json").write_text(json.dumps(out, indent=1, default=str))
	return {k: v for k, v in out.items() if k != "entries"} | {
		"failing": [r["payroll_entry"] for r in results if not r["all_ok"]]
	}


# ---------------------------------------------------------------- payment ---------------
def stage_payment_batch() -> dict:
	"""FNB OBE batch for the October 2026 payroll, with negative and idempotency checks."""
	require_reference_site()
	from za_local_payroll.utils.integrations.eft_file_generator import generate_eft_file

	pe = frappe.db.get_value(
		"Payroll Entry",
		{"company": C.COMPANY, "start_date": "2026-10-01", "payroll_frequency": "Monthly", "docstatus": 1},
		"name",
	)
	bank = frappe.db.get_value("Bank Account", {"company": C.COMPANY, "is_company_account": 1}, "name")
	controls = {}

	def new(fmt="FNB OBE CSV", date="2026-10-25"):
		return frappe.get_doc(
			{
				"doctype": "Payroll Payment Batch",
				"payroll_entry": pe,
				"company": C.COMPANY,
				"payment_date": date,
				"bank_account": bank,
				"bank_format": fmt,
			}
		)

	_try("unsupported_bank_absa", lambda: new("ABSA").insert(ignore_permissions=True), controls)
	_try("payment_date_in_past", lambda: new(date="2026-09-30").insert(ignore_permissions=True), controls)
	batch_name = frappe.db.get_value("Payroll Payment Batch", {"payroll_entry": pe, "docstatus": 1}, "name")
	if not batch_name:
		batch = new()
		batch.insert(ignore_permissions=True)
		batch.submit()
		batch_name = batch.name
		frappe.db.commit()
	_try("duplicate_active_batch", lambda: new().insert(ignore_permissions=True), controls)
	first = generate_eft_file(payment_batch=batch_name)
	second = generate_eft_file(payment_batch=batch_name)
	frappe.db.commit()
	batch = frappe.get_doc("Payroll Payment Batch", batch_name)
	content = frappe.get_doc("File", {"file_url": first["file_url"]}).get_content()
	if isinstance(content, bytes):
		content = content.decode()
	rows = list(csv.reader(io.StringIO(content)))
	detail = rows[4:]
	csv_total = round(sum(flt(r[4]) for r in detail), 2)
	slip_net = round(
		sum(
			flt(x)
			for x in frappe.get_all(
				"Salary Slip", filters={"payroll_entry": pe, "docstatus": 1}, pluck="net_pay"
			)
		),
		2,
	)
	(EVIDENCE / "fnb_obe_october_2026.csv").write_text(content)

	# Snapshot change: alter an employee bank account after submission -> regeneration must be refused.
	employee_account = frappe.db.get_value(
		"Employee",
		detail
		and frappe.get_all(
			"Salary Slip", filters={"payroll_entry": pe, "docstatus": 1}, pluck="employee", limit=1
		)[0],
		"za_payroll_payable_bank_account",
	)
	original_no = frappe.db.get_value("Bank Account", employee_account, "bank_account_no")
	frappe.db.set_value("Bank Account", employee_account, "bank_account_no", "62099999999")
	frappe.db.set_value("Payroll Payment Batch", batch_name, "eft_file_path", None)
	frappe.db.commit()
	_try("regenerate_after_bank_change", lambda: generate_eft_file(payment_batch=batch_name), controls)
	frappe.db.set_value("Bank Account", employee_account, "bank_account_no", original_no)
	frappe.db.set_value("Payroll Payment Batch", batch_name, "eft_file_path", first["file_url"])
	frappe.db.commit()

	# Settle net pay from the bank (HRMS bank entry) and show what remains in Payroll Payable.
	bank_je = _bank_entry(pe)
	payable = a("Payroll Payable")
	remaining = frappe.db.sql(
		"""select sum(credit)-sum(debit) from `tabGL Entry` where account=%s and is_cancelled=0
		and (voucher_no in (select parent from `tabJournal Entry Account` where reference_name=%s and docstatus=1))""",
		(payable, pe),
	)[0][0]
	out = {
		"payroll_entry": pe,
		"batch": batch_name,
		"batch_total": flt(batch.total_amount),
		"batch_employees": batch.total_employees,
		"csv_rows": len(detail),
		"csv_total": csv_total,
		"slip_net_total": slip_net,
		"fnb_hash_total": batch.fnb_hash_total,
		"source_hash": batch.eft_source_hash,
		"file": first,
		"regenerate_reused": second.get("reused"),
		"file_is_private": frappe.db.get_value("File", {"file_url": first["file_url"]}, "is_private"),
		"bank_entry": bank_je,
		"payroll_payable_remaining_for_entry": round(flt(remaining), 2),
		"controls": controls,
	}
	(EVIDENCE / "payment_batch.json").write_text(json.dumps(out, indent=1, default=str))
	return out


def _bank_entry(payroll_entry):
	"""Record the bank's payment through the batch's own settlement action (PAY-PAY-1 fix)."""
	batch = frappe.db.get_value(
		"Payroll Payment Batch", {"payroll_entry": payroll_entry, "docstatus": 1}, "name"
	)
	return frappe.get_doc("Payroll Payment Batch", batch).record_bank_settlement("2026-10-25")


# ---------------------------------------------------------------- EMP201 ---------------
def stage_emp201() -> dict:
	require_reference_site()
	controls, months = {}, []
	fiscal_year = frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-03-01"}, "name")
	for i, month_number in enumerate([3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2]):
		month = MONTH_NAMES[month_number - 1]
		name = frappe.db.get_value(
			"EMP201 Submission",
			{"company": C.COMPANY, "fiscal_year": fiscal_year, "month": month, "docstatus": 1},
			"name",
		)
		if not name:
			doc = frappe.get_doc(
				{
					"doctype": "EMP201 Submission",
					"company": C.COMPANY,
					"fiscal_year": fiscal_year,
					"month": month,
					"posting_date": get_last_day(
						getdate(f"{2026 if month_number >= 3 else 2027}-{month_number:02d}-01")
					),
				}
			)
			with acting_as(user("payroll_manager")):
				doc.insert(ignore_permissions=True)
				if i == 0:
					_try(
						"preparer_submits_own_emp201",
						lambda: _submit_copy("EMP201 Submission", doc.name, user("payroll_manager")),
						controls,
					)
			doc = frappe.get_doc("EMP201 Submission", doc.name)
			doc.reviewed_by = user("payroll_reviewer")
			with acting_as(user("payroll_reviewer")):
				doc.submit()
			name = doc.name
			if i == 0:
				_try(
					"duplicate_period",
					lambda: frappe.get_doc(
						{
							"doctype": "EMP201 Submission",
							"company": C.COMPANY,
							"fiscal_year": fiscal_year,
							"month": month,
							"posting_date": doc.posting_date,
						}
					).insert(ignore_permissions=True),
					controls,
				)
		e = frappe.get_doc("EMP201 Submission", name)
		start, end = e.submission_period_start_date, e.submission_period_end_date
		slips = frappe.get_all(
			"Salary Slip",
			filters={"company": C.COMPANY, "docstatus": 1, "end_date": ["between", [start, end]]},
			pluck="name",
		)
		paye = uif = sdl = eti = 0.0
		for s in slips:
			doc = frappe.get_doc("Salary Slip", s)
			eti += flt(doc.za_monthly_eti)
			for r in doc.deductions:
				code = frappe.get_cached_value("Salary Component", r.salary_component, "za_sars_payroll_code")
				paye += flt(r.amount) if code in ("4102", "4115") else 0
				uif += flt(r.amount) if code == "4141" else 0
			for r in doc.company_contribution:
				code = frappe.get_cached_value("Salary Component", r.salary_component, "za_sars_payroll_code")
				uif += flt(r.amount) if code == "4141" else 0
				sdl += flt(r.amount) if code == "4142" else 0
		months.append(
			{
				"emp201": name,
				"month": f"{start}",
				"slips": len(slips),
				"paye_slips": round(paye, 2),
				"paye_emp201": e.gross_paye_before_eti,
				"uif_slips": round(uif, 2),
				"uif_emp201": e.uif_payable,
				"sdl_slips": round(sdl, 2),
				"sdl_emp201": e.sdl_payable,
				"eti_generated_slips": round(eti, 2),
				"eti_generated": e.eti_generated_current_month,
				"eti_carried_in": e.eti_carried_forward_from_previous,
				"eti_available": e.total_eti_available,
				"eti_utilised": e.eti_utilized_current_month,
				"eti_carry_out": e.eti_to_be_carried_forward,
				"eti_refund_flag": e.eti_reconciliation_refund,
				"net_paye_payable": e.net_paye_payable,
				"status": e.status,
				"ok": all(
					abs(x - y) <= 0.01
					for x, y in (
						(paye, e.gross_paye_before_eti),
						(uif, e.uif_payable),
						(sdl, e.sdl_payable),
						(eti, e.eti_generated_current_month),
					)
				),
			}
		)

	# BRS-REF-1: a PAYE reference failing the SARS modulus-10 check is refused on the Company.
	def bad_paye_reference():
		company = frappe.get_doc("Company", C.COMPANY)
		company.za_paye_reference_number = C.PAYE_REFERENCE[:-1] + str((int(C.PAYE_REFERENCE[-1]) + 1) % 10)
		company.save(ignore_permissions=True)

	_try("invalid_paye_reference_check_digit", bad_paye_reference, controls)
	totals = {
		k: round(sum(flt(m[k]) for m in months), 2)
		for k in (
			"paye_emp201",
			"uif_emp201",
			"sdl_emp201",
			"eti_generated",
			"eti_utilised",
			"net_paye_payable",
		)
	}
	out = {
		"months": months,
		"totals": totals,
		"all_months_ok": all(m["ok"] for m in months),
		"controls": controls,
	}
	march = months[0]["emp201"]
	out["march_filing"] = _payroll_filing_lifecycle("EMP201 Submission", march, "2026-04-07", controls)
	(EVIDENCE / "emp201_year.json").write_text(json.dumps(out, indent=1, default=str))
	return {k: v for k, v in out.items() if k != "months"} | {
		"not_ok": [m["month"] for m in months if not m["ok"]]
	}


# ---------------------------------------------------------------- IRP5 / EMP501 ---------------
def stage_certificates() -> dict:
	require_reference_site()
	from za_local_payroll.reference_company.golden_compare import build_golden
	from za_local_payroll.reference_company.golden_engine import GoldenEngine
	from za_local_payroll.reference_company.payroll_run import employee_for
	from za_local_payroll.reference_company.personas import PERSONAS

	fiscal_year = frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-03-01"}, "name")
	golden = build_golden(GoldenEngine(paths.GOLDEN_FILE))
	results, errors = [], []
	for key in PERSONAS:
		employee = employee_for(key)
		name = frappe.db.get_value(
			"IRP5 Certificate",
			{
				"employee": employee,
				"tax_year": fiscal_year,
				"reconciliation_period": "Final",
				"docstatus": ("<", 2),
			},
			"name",
		)
		try:
			if not name:
				doc = frappe.get_doc(
					{
						"doctype": "IRP5 Certificate",
						"employee": employee,
						"company": C.COMPANY,
						"tax_year": fiscal_year,
						"reconciliation_period": "Final",
						"from_date": "2026-03-01",
						"to_date": "2027-02-28",
						"certificate_type": "IRP5",
						"certificate_number": f"REF-{key[:3]}-2027",
					}
				)
				with acting_as(user("payroll_manager")):
					doc.insert(ignore_permissions=True)
					doc.generate_certificate_data()
					doc.save(ignore_permissions=True)
				name = doc.name
			doc = frappe.get_doc("IRP5 Certificate", name)
			readiness = (
				doc.validate_statutory_readiness(throw=False)
				if hasattr(doc, "validate_statutory_readiness")
				else None
			)
			income = {r.income_code: flt(r.amount) for r in doc.income_details}
			deductions = {r.deduction_code: flt(r.amount) for r in doc.deduction_details}
			contrib = {r.contribution_code: flt(r.amount) for r in doc.company_contribution_details}
			slips = frappe.get_all(
				"Salary Slip",
				filters={
					"employee": employee,
					"docstatus": 1,
					"company": C.COMPANY,
					"start_date": [">=", "2026-03-01"],
					"end_date": ["<=", "2027-02-28"],
				},
				pluck="name",
			)
			exp = golden.get(key, {})
			results.append(
				{
					"persona": key,
					"certificate": name,
					"type": doc.certificate_type,
					"status": doc.status,
					"reason_code": doc.get("it3a_reason_code") or doc.get("reason_code"),
					"income": income,
					"deductions": deductions,
					"contributions": contrib,
					"gross_taxable_income": doc.gross_taxable_income,
					"paye_cert": doc.paye,
					"uif_cert": doc.uif,
					"sdl_cert": doc.sdl,
					"eti_cert": doc.get("eti") or doc.get("total_eti"),
					"slips": len(slips),
					"golden_paye_year": round(sum(m["paye"] for m in exp.values()), 2) if exp else None,
					"readiness": readiness,
					"mapping_errors": getattr(doc, "_mapping_errors", None),
				}
			)
		except Exception as exc:
			frappe.db.rollback()
			errors.append({"persona": key, "error": frappe.utils.strip_html(str(exc))[:400]})
	frappe.db.commit()
	out = {"certificates": results, "errors": errors}
	(EVIDENCE / "irp5_certificates.json").write_text(json.dumps(out, indent=1, default=str))
	return {"generated": len(results), "errors": errors}


def stage_emp501() -> dict:
	"""Final 2026/27 EMP501: certificates (generated + submitted per employee), EMP201 links, controls."""
	require_reference_site()
	from za_local_payroll.reference_company.payroll_run import employee_for
	from za_local_payroll.reference_company.personas import PERSONAS

	fiscal_year = frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-03-01"}, "name")
	certificates, errors, controls = {}, {}, {}
	for key in PERSONAS:
		employee = employee_for(key)
		if not frappe.db.exists("Salary Slip", {"employee": employee, "docstatus": 1, "company": C.COMPANY}):
			continue
		name = frappe.db.get_value(
			"IRP5 Certificate",
			{
				"employee": employee,
				"tax_year": fiscal_year,
				"reconciliation_period": "Final",
				"docstatus": ("<", 2),
			},
			"name",
		)
		try:
			if not name:
				doc = frappe.get_doc(
					{
						"doctype": "IRP5 Certificate",
						"employee": employee,
						"company": C.COMPANY,
						"tax_year": fiscal_year,
						"reconciliation_period": "Final",
						"from_date": "2026-03-01",
						"to_date": "2027-02-28",
						"certificate_type": "IRP5",
						"certificate_number": f"REF-{key[:3]}-2027",
					}
				)
				with acting_as(user("payroll_manager")):
					doc.insert(ignore_permissions=True)
					doc.generate_certificate_data()
					doc.save(ignore_permissions=True)
				name = doc.name
			doc = frappe.get_doc("IRP5 Certificate", name)
			if doc.docstatus == 0:
				if not controls:
					with acting_as(user("payroll_manager")):
						_try(
							"preparer_submits_own_irp5",
							lambda: _submit_copy("IRP5 Certificate", name, user("payroll_manager")),
							controls,
						)
				doc.reviewed_by = user("payroll_reviewer")
				with acting_as(user("payroll_reviewer")):
					doc.submit()
			frappe.db.commit()
			certificates[employee] = name
		except Exception as exc:
			frappe.db.rollback()
			errors[key] = frappe.utils.strip_html(str(exc))[:400]
	name = frappe.db.get_value(
		"EMP501 Reconciliation",
		{
			"company": C.COMPANY,
			"tax_year": fiscal_year,
			"reconciliation_period": "Final",
			"docstatus": ("<", 2),
		},
		"name",
	)
	if not name:
		ref = frappe.db.get_value(
			"Company",
			C.COMPANY,
			["za_paye_reference_number", "za_sdl_reference_number", "za_uif_reference_number"],
			as_dict=True,
		)
		emp501 = frappe.get_doc(
			{
				"doctype": "EMP501 Reconciliation",
				"company": C.COMPANY,
				"tax_year": fiscal_year,
				"reconciliation_period": "Final",
				"submission_date": "2026-10-01",
				"status": "Draft",
				"from_date": "2026-03-01",
				"to_date": "2027-02-28",
				"paye_reference_number": ref.za_paye_reference_number,
				"sdl_reference_number": ref.za_sdl_reference_number,
				"uif_reference_number": ref.za_uif_reference_number,
			}
		)
		with acting_as(user("payroll_manager")):
			emp501.insert(ignore_permissions=True)
			emp501.fetch_emp201_submissions()
		emp501.reload()
		for employee, cert in certificates.items():
			emp501.append(
				"irp5_certificates",
				{
					"irp5_certificate": cert,
					"employee": employee,
					"employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
				},
			)
		emp501.reviewed_by = user("payroll_reviewer")
		emp501.save(ignore_permissions=True)
		frappe.db.commit()
		name = emp501.name
	emp501 = frappe.get_doc("EMP501 Reconciliation", name)
	if emp501.docstatus == 0:
		# Missing certificate: drop one row and try to submit.
		removed = emp501.irp5_certificates[0]

		def without_one():
			doc = frappe.get_doc("EMP501 Reconciliation", name)
			doc.irp5_certificates = doc.irp5_certificates[1:]
			doc.submit()

		_try("missing_certificate", without_one, controls)

		def duplicate_link():
			doc = frappe.get_doc("EMP501 Reconciliation", name)
			doc.append(
				"irp5_certificates",
				{"irp5_certificate": removed.irp5_certificate, "employee": removed.employee},
			)
			doc.submit()

		_try("duplicate_certificate", duplicate_link, controls)

		def missing_month():
			doc = frappe.get_doc("EMP501 Reconciliation", name)
			doc.emp201_submissions = doc.emp201_submissions[1:]
			doc.submit()

		_try("missing_emp201_month", missing_month, controls)

		def missing_registration():
			doc = frappe.get_doc("EMP501 Reconciliation", name)
			doc.sdl_reference_number = None
			doc.submit()

		_try("missing_sdl_reference", missing_registration, controls)
		with acting_as(user("payroll_manager")):
			_try(
				"preparer_submits_own_emp501",
				lambda: _submit_copy("EMP501 Reconciliation", name, user("payroll_manager")),
				controls,
			)
		emp501 = frappe.get_doc("EMP501 Reconciliation", name)
		try:
			with acting_as(user("payroll_reviewer")):
				emp501.submit()
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			controls["final_submit_error"] = frappe.utils.strip_html(str(exc))[:800]
	emp501 = frappe.get_doc("EMP501 Reconciliation", name)
	out = {
		"emp501": name,
		"docstatus": emp501.docstatus,
		"status": emp501.status,
		"emp201_rows": len(emp501.emp201_submissions),
		"certificates": len(emp501.irp5_certificates),
		"total_paye": emp501.total_paye,
		"total_uif": emp501.total_uif,
		"total_sdl": emp501.total_sdl,
		"total_eti_utilised": emp501.total_eti,
		"total_tax_payable": emp501.total_tax_payable,
		"certificate_errors": errors,
		"controls": controls,
	}
	if emp501.docstatus == 1:
		out["filing"] = _payroll_filing_lifecycle("EMP501 Reconciliation", name, "2027-05-31", controls)
	(EVIDENCE / "emp501_final.json").write_text(json.dumps(out, indent=1, default=str))
	return out


def _submit_copy(doctype, name, reviewed_by=None):
	doc = frappe.get_doc(doctype, name)
	if reviewed_by:
		doc.reviewed_by = reviewed_by
	doc.submit()


def _payroll_filing_lifecycle(doctype, name, due_date, controls) -> dict:
	"""EMP201-1: hand a submitted payroll working paper to ZA Filing, review, approve, record SARS's response.

	The due date is the synthetic company's; the EMP501 deadline is announced by SARS each year.
	"""
	import hashlib

	from frappe.utils.file_manager import save_file

	settings = frappe.get_single("Payroll Settings")
	field = (
		"za_emp201_compliance_obligation"
		if doctype == "EMP201 Submission"
		else "za_emp501_compliance_obligation"
	)
	code = "ZA-EMP201" if doctype == "EMP201 Submission" else "ZA-EMP501"
	settings.set(
		field, frappe.db.get_value("ZA Compliance Obligation", {"obligation_code": code, "docstatus": 1})
	)
	settings.save(ignore_permissions=True)
	doc = frappe.get_doc(doctype, name)
	if not doc.za_filing:
		doc.db_set(
			{
				"filing_due_date": due_date,
				"filing_reviewer": user("reviewer"),
				"filing_approver": user("approver"),
			}
		)
		with acting_as(user("payroll_manager")):
			_try(
				f"payroll_user_creates_{code.lower()}_filing",
				lambda: frappe.get_doc(doctype, name).create_za_filing(),
				controls,
			)
		with acting_as(user("preparer")):
			frappe.get_doc(doctype, name).create_za_filing()
		filing_name = frappe.db.get_value(doctype, name, "za_filing")
		if frappe.db.get_value("ZA Filing", filing_name, "unexplained_difference"):
			# The declaration must tie to the ledger; a difference is a finding, not something to explain away.
			frappe.db.commit()
			return {
				"filing": filing_name,
				"unexpected_difference": frappe.db.get_value(
					"ZA Filing", filing_name, "unexplained_difference"
				),
			}
		with acting_as(user("reviewer")):
			frappe.get_doc("ZA Filing", filing_name).mark_reviewed()
		with acting_as(user("approver")):
			frappe.get_doc("ZA Filing", filing_name).submit()
		evidence = f"SYNTHETIC SARS acknowledgement - {name} - not a real SARS receipt".encode()
		with acting_as(user("reviewer")):
			file_url = save_file(
				f"{code.lower()}-ack-synthetic.txt", evidence, doctype, name, is_private=1
			).file_url
			receipt = frappe.get_doc(doctype, name).record_submission_receipt(
				authority_reference=f"SYNTH-{code}-{name}",
				response_status="Accepted",
				evidence_file=file_url,
				sha256_checksum=hashlib.sha256(evidence).hexdigest(),
				submitted_by=user("submitter"),
			)
		with acting_as(user("submitter")):
			frappe.get_doc("ZA Submission Receipt", receipt).submit()
		frappe.db.commit()
	filing = frappe.get_doc("ZA Filing", frappe.db.get_value(doctype, name, "za_filing"))
	return {
		"filing": filing.name,
		"status": filing.status,
		"declared_amount": filing.declared_amount,
		"ledger_amount": filing.ledger_amount,
		"unexplained_difference": filing.unexplained_difference,
		"receipt": frappe.db.get_value("ZA Submission Receipt", {"filing": filing.name, "docstatus": 1}),
	}


CERTIFICATE_PDF_PERSONAS = (
	"P03_high_income",
	"P09_retirement_cap",
	"P10_eti_eligible",
	"P18_fringe_benefits",
	"P19_termination",
)


def render_certificate_pdfs() -> list[str]:
	"""Export sample IRP5/IT3(a) certificates through the app's own export, for visual inspection."""
	from za_local_payroll.reference_company.payroll_run import employee_for

	require_reference_site()
	out_dir = EVIDENCE / "pdf"
	out_dir.mkdir(parents=True, exist_ok=True)
	written = []
	for persona in CERTIFICATE_PDF_PERSONAS:
		employee = employee_for(persona)
		name = frappe.db.get_value(
			"IRP5 Certificate",
			{"employee": employee, "docstatus": ["<", 2], "status": ["!=", "Draft"]},
			"name",
			order_by="creation desc",
		)
		if not name:
			continue
		doc = frappe.get_doc("IRP5 Certificate", name)
		kind = doc.get("certificate_type") or "IRP5"
		path = out_dir / f"{kind.replace('(', '').replace(')', '')}_{persona}.pdf"
		path.write_bytes(doc.generate_official_pdf())
		written.append(str(path))
	return written
