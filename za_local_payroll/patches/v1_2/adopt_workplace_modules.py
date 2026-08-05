"""Take over the SA Labour and SA COIDA modules from za_local_workplace.

Both modules moved into this app unchanged: same names, same DocTypes, same
tables. Only the owning app differs, so this re-points the Module Def and
Workspace records and then de-registers the old app.

The old app is dropped with ``remove_from_installed_apps`` rather than
``bench uninstall-app``, because ``remove_app`` would delete every DocType it
owned and take the customer's labour, injury, claim and COIDA records with it.
Nothing is deleted here.
"""

import frappe
from frappe.installer import remove_from_installed_apps

RETIRED_APP = "za_local_workplace"


def execute() -> None:
	from za_local_payroll.setup.workplace import claim_workplace_module_ownership

	claim_workplace_module_ownership()
	if RETIRED_APP in frappe.get_installed_apps():
		remove_from_installed_apps(RETIRED_APP)
