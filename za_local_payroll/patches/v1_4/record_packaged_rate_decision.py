import frappe


def execute():
	"""GOV-4: keep a running payroll working on upgrade, as an explicit, visible setting.

	Sites that already ran payroll without an approved Payroll rate pack relied on the
	packaged rates; enable the new setting for them so the next pay run does not stop.
	New sites, and sites with an approved pack, keep it off.
	"""
	if not frappe.db.exists("Salary Slip", {"docstatus": 1}):
		return
	if frappe.db.exists("ZA Statutory Rate Pack", {"domain": "Payroll", "docstatus": 1}):
		return
	frappe.db.set_single_value("Payroll Settings", "za_allow_packaged_statutory_rates", 1)
