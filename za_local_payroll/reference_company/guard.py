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
