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
	"""Repair metrics created before the filter shape was corrected.

	The Desk reads a stored filter as ``[doctype, fieldname, operator, value]``, so
	the three-part filters shipped earlier made it report ``Invalid filter: =``.
	Currency cards also need full numbers, because Frappe renders a zero-valued
	one as ``R NaN``.
	"""
	repair_metric_presentation(PAYROLL_MODULE, cards=PAYROLL_NUMBER_CARDS, charts=PAYROLL_CHARTS)
	repair_metric_presentation(COIDA_MODULE, cards=COIDA_NUMBER_CARDS, charts=COIDA_CHARTS)
	repair_metric_presentation(LABOUR_MODULE, cards=LABOUR_NUMBER_CARDS, charts=LABOUR_CHARTS)
