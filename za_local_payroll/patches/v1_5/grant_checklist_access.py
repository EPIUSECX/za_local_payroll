from za_local_payroll.setup.role_grants import grant_payroll_permissions


def execute():
	"""The payroll, labour and COIDA checklists' own roles could not open the pages they point to."""
	grant_payroll_permissions()
