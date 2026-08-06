from za_local_core.dashboards import repair_metric_presentation

from za_local_payroll.install import PAYROLL_CHARTS, PAYROLL_MODULE, PAYROLL_NUMBER_CARDS
from za_local_payroll.setup.workplace import (
	COIDA_CHARTS,
	COIDA_MODULE,
	COIDA_NUMBER_CARDS,
	LABOUR_CHARTS,
	LABOUR_MODULE,
	LABOUR_NUMBER_CARDS,
)


def execute() -> None:
	"""Restamp metric currency from the site default.

	Number Card and Dashboard Chart persist a currency, and the metrics are seeded
	during app installation -- before the setup wizard has set the real one. They
	were therefore stamped with Frappe's shipped default and kept rendering South
	African statutory figures with a rupee symbol.
	"""
	repair_metric_presentation(PAYROLL_MODULE, cards=PAYROLL_NUMBER_CARDS, charts=PAYROLL_CHARTS)
	repair_metric_presentation(COIDA_MODULE, cards=COIDA_NUMBER_CARDS, charts=COIDA_CHARTS)
	repair_metric_presentation(LABOUR_MODULE, cards=LABOUR_NUMBER_CARDS, charts=LABOUR_CHARTS)
