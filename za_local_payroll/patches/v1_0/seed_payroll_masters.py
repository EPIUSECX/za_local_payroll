"""Seed missing payroll masters once during the extraction upgrade."""

from za_local_payroll.setup.masters import seed_payroll_masters


def execute() -> None:
	seed_payroll_masters()
