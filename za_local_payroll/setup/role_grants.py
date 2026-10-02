"""PERM-1: least-privilege payroll roles on the standard HRMS payroll DocTypes.

A Payroll Manager runs payroll, EMP201, IRP5 and EMP501, with a second Payroll
Manager as the recorded reviewer. Grants are added once and never re-applied over an
administrator's own rules (see ``za_local_core.role_grants``).
"""

from za_local_core.role_grants import grant_permissions

RUN = ("read", "write", "create", "submit", "cancel", "report", "print", "export")
READ = ("read", "report")

PAYROLL_GRANTS = (
	("Payroll Entry", "Payroll Manager", RUN),
	("Salary Slip", "Payroll Manager", (*RUN, "email")),
	("Additional Salary", "Payroll Manager", RUN),
	("Salary Structure Assignment", "Payroll Manager", READ),
	("Salary Structure", "Payroll Manager", READ),
	("Salary Component", "Payroll Manager", READ),
	("Payroll Period", "Payroll Manager", ("read",)),
	("Income Tax Slab", "Payroll Manager", ("read",)),
	("Employee", "Payroll Manager", READ),
	("Company", "Payroll Manager", ("read",)),
	("Payroll Entry", "Payroll User", ("read", "write", "create", "report")),
	("Salary Slip", "Payroll User", ("read", "report", "print")),
	("Additional Salary", "Payroll User", ("read", "write", "create", "report")),
	# The payroll, labour and COIDA setup checklists send these roles to confirm
	# the governing rate packs are approved and to review Payroll Settings.
	# Approval and settings changes stay with the compliance and HR roles.
	("ZA Statutory Source", "Payroll Manager", ("read",)),
	("ZA Statutory Rate Pack", "Payroll Manager", ("read",)),
	("ZA Statutory Source", "HR Manager", ("read",)),
	("ZA Statutory Rate Pack", "HR Manager", ("read",)),
	("Payroll Settings", "Payroll Manager", ("read",)),
)


def grant_payroll_permissions() -> list[str]:
	return grant_permissions(PAYROLL_GRANTS)
