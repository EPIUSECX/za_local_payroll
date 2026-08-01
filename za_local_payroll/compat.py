"""Explicit runtime cutover rules for side-by-side migration."""

import frappe


def dedicated_payroll_hooks_active() -> bool:
	"""Enable dedicated hooks only after an explicit side-by-side cutover."""
	try:
		installed_apps = set(frappe.get_installed_apps() or ())
		configured_owner = (frappe.conf.get("za_local_payroll_runtime_owner") or "").strip().lower()
		if configured_owner:
			return configured_owner == "dedicated"
		return "za_local" not in installed_apps
	except Exception:
		return True
