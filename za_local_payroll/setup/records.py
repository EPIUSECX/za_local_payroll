"""Payroll DocType links used by Frappe's Connections dashboards."""

import frappe

PAYROLL_DOCTYPE_LINKS = (
	("Employee", "Tax & Compliance", "Tax Directive", "employee"),
	("Employee", "Benefits", "Fringe Benefit", "employee"),
	("Employee", "Benefits", "Company Car Benefit", "employee"),
	("Employee", "Benefits", "Housing Benefit", "employee"),
	("Employee", "Benefits", "Low Interest Loan Benefit", "employee"),
	("Employee", "Benefits", "Cellphone Benefit", "employee"),
	("Employee", "Benefits", "Fuel Card Benefit", "employee"),
	("Employee", "Benefits", "Bursary Benefit", "employee"),
	("Employee", "Payroll", "Leave Encashment SA", "employee"),
	("Employee", "Payroll", "Employee Final Settlement", "employee"),
	("Employee", "Tax & Compliance", "UIF U19 Declaration", "employee"),
	("Company", "Payroll", "Retirement Fund", "company"),
	("Company", "Payroll", "Travel Allowance Rate", "company"),
	("Payroll Entry", "Payroll", "Payroll Payment Batch", "payroll_entry"),
)


def get_payroll_doctype_links() -> list[dict]:
	"""Return only links whose parent and target DocTypes are available."""
	return [
		{
			"doctype": "DocType Link",
			"parent": parent,
			"parentfield": "links",
			"parenttype": "DocType",
			"group": group,
			"link_doctype": target,
			"link_fieldname": link_fieldname,
			"custom": 1,
		}
		for parent, group, target, link_fieldname in PAYROLL_DOCTYPE_LINKS
		if frappe.db.exists("DocType", parent) and frappe.db.exists("DocType", target)
	]


def install_payroll_doctype_links() -> None:
	"""Create missing dashboard links without modifying links owned by other apps."""
	for record in get_payroll_doctype_links():
		filters = {
			"parent": record["parent"],
			"parenttype": "DocType",
			"parentfield": "links",
			"link_doctype": record["link_doctype"],
			"link_fieldname": record["link_fieldname"],
		}
		if not frappe.db.exists("DocType Link", filters):
			frappe.get_doc(record).insert(ignore_permissions=True)
