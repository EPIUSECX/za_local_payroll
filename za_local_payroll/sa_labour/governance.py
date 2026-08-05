"""Shared governance controls for Employment Equity and skills records."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime
from za_local_core.governance import REVIEW_ROLES, validate_accountable_actor, validate_private_evidence


def set_preparer(doc) -> None:
	if not doc.get("prepared_by"):
		doc.prepared_by = frappe.session.user


def validate_independent_review(
	doc,
	*,
	evidence_field: str = "review_evidence",
	status_field: str = "status",
) -> None:
	"""Require a recorded independent reviewer and private review evidence."""
	validate_private_evidence(doc, evidence_field, required=True)
	actor = validate_accountable_actor(doc, "reviewed_by", REVIEW_ROLES, "approve")
	doc.reviewed_on = now_datetime()
	doc.set(status_field, "Internally Approved")
	if actor == doc.get("prepared_by"):
		frappe.throw(
			_("The preparer and reviewer must be different users."),
			frappe.PermissionError,
		)


def validate_date_range(doc, from_field: str = "effective_from", to_field: str = "effective_to") -> None:
	start = doc.get(from_field)
	end = doc.get(to_field)
	if start and end and getdate(end) < getdate(start):
		frappe.throw(
			_("{0} cannot be before {1}.").format(
				doc.meta.get_label(to_field), doc.meta.get_label(from_field)
			)
		)


def validate_company_access(company: str, permission_type: str = "read") -> None:
	if not company:
		frappe.throw(_("Company is required."))
	frappe.has_permission("Company", permission_type, company, throw=True)


def validate_governed_link(
	doctype: str,
	name: str | None,
	*,
	company: str | None = None,
	require_submitted: bool = True,
) -> frappe._dict:
	if not name:
		frappe.throw(_("{0} is required.").format(doctype))
	fields = ["name"]
	meta = frappe.get_meta(doctype)
	if meta.is_submittable:
		fields.append("docstatus")
	if meta.has_field("company"):
		fields.append("company")
	if meta.has_field("active"):
		fields.append("active")
	row = frappe.db.get_value(doctype, name, fields, as_dict=True)
	if not row:
		frappe.throw(_("{0} {1} does not exist.").format(doctype, frappe.bold(name)))
	if require_submitted and meta.is_submittable and row.docstatus != 1:
		frappe.throw(_("{0} {1} must be submitted before use.").format(doctype, frappe.bold(name)))
	if company and row.get("company") and row.company != company:
		frappe.throw(_("{0} {1} belongs to a different company.").format(doctype, frappe.bold(name)))
	if row.get("active") == 0:
		frappe.throw(_("{0} {1} is inactive.").format(doctype, frappe.bold(name)))
	return row


def validate_external_filing_evidence(doc) -> None:
	"""External filing is manual; require private evidence before claiming it occurred."""
	if doc.get("external_filing_status") == "Filed Externally":
		if not doc.get("external_filing_reference") or not doc.get("external_filing_date"):
			frappe.throw(_("External filing reference and date are required for a filed working paper."))
		validate_private_evidence(doc, "external_filing_evidence", required=True)
