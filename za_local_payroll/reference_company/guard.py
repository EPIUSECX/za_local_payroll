"""Refuse to run anywhere except an isolated developer-mode test site."""

import frappe
from frappe import _


def require_reference_site() -> None:
	site = (frappe.local.site or "").lower()
	if not frappe.conf.developer_mode or not (site.endswith(".test") or "e2e" in site):
		frappe.throw(
			_("The reference-company harness only runs on a developer-mode .test site."),
			title=_("Isolated Test Site Required"),
		)


def commit_stage() -> None:
	"""Make one stage of the synthetic reference company durable.

	The harness builds a long chain of dependent documents (company, accounts, payroll runs,
	filings) and a later stage reads what an earlier one wrote, often through background-style
	helpers that open their own transaction. Each stage must therefore be committed before the next
	starts. This only ever runs on the isolated developer-mode test site that
	``require_reference_site`` allows, never in a request or on a live site.
	"""
	frappe.db.commit()  # nosemgrep
