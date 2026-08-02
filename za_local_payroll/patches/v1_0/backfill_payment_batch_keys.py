import hashlib

import frappe
from frappe import _


def execute():
	if not frappe.db.table_exists("Payroll Payment Batch") or not frappe.db.has_column(
		"Payroll Payment Batch", "batch_key"
	):
		return

	active = frappe.get_all(
		"Payroll Payment Batch",
		filters={"docstatus": ["<", 2], "payroll_entry": ["is", "set"]},
		fields=["name", "payroll_entry"],
		order_by="creation, name",
	)
	by_payroll_entry = {}
	for row in active:
		by_payroll_entry.setdefault(row.payroll_entry, []).append(row.name)

	duplicates = {payroll_entry: names for payroll_entry, names in by_payroll_entry.items() if len(names) > 1}
	if duplicates:
		details = "<br>".join(
			f"{frappe.utils.escape_html(payroll_entry)}: {', '.join(frappe.utils.escape_html(name) for name in names)}"
			for payroll_entry, names in sorted(duplicates.items())
		)
		frappe.throw(
			_("Resolve duplicate active Payroll Payment Batches before migrating:<br>{0}").format(details),
			title=_("Duplicate Payroll Payment Batches"),
		)

	for payroll_entry, names in by_payroll_entry.items():
		frappe.db.set_value(
			"Payroll Payment Batch",
			names[0],
			"batch_key",
			hashlib.sha256(payroll_entry.encode()).hexdigest(),
			update_modified=False,
		)

	cancelled = frappe.get_all(
		"Payroll Payment Batch",
		filters={"docstatus": 2},
		fields=["name", "payroll_entry", "batch_key"],
	)
	for row in cancelled:
		if row.batch_key:
			continue
		frappe.db.set_value(
			"Payroll Payment Batch",
			row.name,
			"batch_key",
			hashlib.sha256(f"{row.payroll_entry}|cancelled|{row.name}".encode()).hexdigest(),
			update_modified=False,
		)
