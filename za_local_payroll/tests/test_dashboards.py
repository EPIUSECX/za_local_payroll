"""The payroll, COIDA and labour metrics must carry the site's own currency.

This app owns most of the suite's metrics and had no dashboard coverage, which is
why every one of them shipped denominated in Frappe's default.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase
from za_local_core.dashboards import CARD_DOCTYPE, CHART_DOCTYPE, display_currency

from za_local_payroll.install import (
	PAYROLL_MODULE,
	PAYROLL_NUMBER_CARDS,
	after_migrate,
	repair_payroll_metrics,
	seed_payroll_dashboards,
)
from za_local_payroll.setup.workplace import (
	COIDA_MODULE,
	COIDA_NUMBER_CARDS,
	LABOUR_MODULE,
	LABOUR_NUMBER_CARDS,
	seed_workplace_dashboards,
)

OWNED_MODULES = (
	(PAYROLL_MODULE, PAYROLL_NUMBER_CARDS),
	(COIDA_MODULE, COIDA_NUMBER_CARDS),
	(LABOUR_MODULE, LABOUR_NUMBER_CARDS),
)


class TestPayrollDashboardCurrency(IntegrationTestCase):
	def seed(self):
		seed_payroll_dashboards()
		seed_workplace_dashboards()

	def test_the_repair_is_reachable_on_a_fresh_install(self):
		"""``install_app`` marks every patch complete before it runs
		``after_install``, so the repair patch could not execute on a fresh install,
		and ``seed_dashboards`` skips records that already exist. The currency
		stamped during install was permanent. The defect was the wiring, so both
		call sites are asserted here."""
		from za_local_payroll import hooks

		self.assertEqual("za_local_payroll.install.repair_payroll_metrics", hooks.setup_wizard_complete)
		self.assertIs(frappe.get_attr(hooks.setup_wizard_complete), repair_payroll_metrics)
		self.assertIn("repair_payroll_metrics", after_migrate.__code__.co_names)

	def test_the_repair_covers_every_module_this_app_owns(self):
		"""A module left out of the repair keeps the installer's currency forever."""
		self.seed()
		stale = [cards[0]["label"] for _, cards in OWNED_MODULES]
		for card in stale:
			frappe.db.set_value(CARD_DOCTYPE, card, "currency", "INR")

		# The setup wizard passes its payload positionally; it must be optional.
		repair_payroll_metrics(None)

		for card in stale:
			self.assertEqual(
				frappe.db.get_value(CARD_DOCTYPE, card, "currency"),
				display_currency(),
				f"{card} was not restamped",
			)

	def test_every_seeded_metric_is_denominated_in_the_site_currency(self):
		self.seed()
		expected = display_currency()
		self.assertTrue(expected)

		for module, _cards in OWNED_MODULES:
			for doctype in (CARD_DOCTYPE, CHART_DOCTYPE):
				for name in frappe.get_all(doctype, filters={"module": module}, pluck="name"):
					self.assertEqual(
						frappe.db.get_value(doctype, name, "currency"),
						expected,
						f"{doctype} {name} is not denominated in the site currency",
					)
