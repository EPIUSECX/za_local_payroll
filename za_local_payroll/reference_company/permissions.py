"""Stage 14: role/permission and segregation-of-duties matrix generated from the live site.

For each synthetic user (and Guest) and each statutory DocType, records
frappe.has_permission for read/create/submit/cancel against the reference
company. The matrix is evidence of what the shipped roles allow; the SoD
conclusions are drawn in the acceptance report.
"""

import json

import frappe

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.governance import acting_as
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.payroll_setup import EVIDENCE

DOCTYPES = (
	"ZA Statutory Source",
	"ZA Statutory Rate Pack",
	"ZA Company Compliance Profile",
	"ZA Compliance Obligation",
	"ZA Feature Readiness",
	"ZA Filing",
	"ZA Submission Receipt",
	"South Africa VAT Settings",
	"VAT201 Return",
	"Sales Invoice",
	"Purchase Invoice",
	"Salary Component",
	"Salary Structure",
	"Salary Slip",
	"Payroll Entry",
	"Additional Salary",
	"EMP201 Submission",
	"IRP5 Certificate",
	"EMP501 Reconciliation",
	"Tax Directive",
	"Employee",
	"Employee Separation",
	"Leave Application",
	"Employment Equity Target Plan",
	"Workplace Skills Plan",
	"COIDA Annual Return",
	"COIDA Settings",
	"Workplace Injury",
	"OID Claim",
	"ZA Processing Activity",
	"ZA Data Subject Request",
	"ZA Personal Information Incident",
	"ZA PAIA Manual",
)
PTYPES = ("read", "create", "write", "submit", "cancel")


def _probe(doctype, ptype):
	try:
		return bool(frappe.has_permission(doctype, ptype))
	except Exception:
		return None


def stage_permission_matrix() -> dict:
	require_reference_site()
	users = {key: email for key, (email, _name, _roles) in C.USERS.items()}
	users["guest"] = "Guest"
	matrix, missing = {}, []
	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			missing.append(doctype)
			continue
		submittable = frappe.get_meta(doctype).is_submittable
		matrix[doctype] = {}
		for key, email in users.items():
			with acting_as(email):
				row = {p: _probe(doctype, p) for p in PTYPES if submittable or p not in ("submit", "cancel")}
			matrix[doctype][key] = "".join(
				p[0].upper() if row.get(p) else "-"
				for p in PTYPES
				if submittable or p not in ("submit", "cancel")
			)
	sod = {
		"payroll_user_submits_payroll_entry": matrix.get("Payroll Entry", {}).get("payroll_user", ""),
		"hr_manager_create_and_submit_coida_return": matrix.get("COIDA Annual Return", {}).get(
			"hr_manager", ""
		),
		"hr_manager_create_and_submit_injury": matrix.get("Workplace Injury", {}).get("hr_manager", ""),
		"preparer_vat201": matrix.get("VAT201 Return", {}).get("preparer", ""),
		"reviewer_vat201": matrix.get("VAT201 Return", {}).get("reviewer", ""),
		"payroll_manager_emp201": matrix.get("EMP201 Submission", {}).get("payroll_manager", ""),
		"guest_any_access": sorted(dt for dt, row in matrix.items() if row.get("guest", "").strip("-")),
	}
	roles = {key: sorted(frappe.get_roles(email)) for key, email in users.items()}
	out = {
		"legend": "R=read C=create W=write S=submit X=cancel(C in 5th position) '-'=denied",
		"columns": list(PTYPES),
		"users": roles,
		"matrix": matrix,
		"missing_doctypes": missing,
		"sod_probe": sod,
		"company": C.COMPANY,
	}
	(EVIDENCE / "permission_matrix.json").write_text(json.dumps(out, indent=1, default=str))
	return out
