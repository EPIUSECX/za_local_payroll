from za_local_payroll.setup.role_grants import grant_payroll_permissions


def execute():
	"""PERM-1: a payroll year needed System Manager plus HR Manager plus Payroll Manager."""
	grant_payroll_permissions()
