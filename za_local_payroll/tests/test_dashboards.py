"""The payroll, COIDA and labour metrics must show the right figure in the site's own currency.

This app owns most of the suite's metrics and had no dashboard coverage, which is
why every one of them shipped denominated in Frappe's default.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase
from za_local_core.dashboards import (
	CARD_DOCTYPE,
	CHART_DOCTYPE,
	chart_value_field,
	display_currency,
	is_amount_metric,
	metric_currency,
)

from za_local_payroll.install import (
	PAYROLL_CHARTS,
	PAYROLL_MODULE,
	PAYROLL_NUMBER_CARDS,
	after_migrate,
	repair_payroll_metrics,
	seed_payroll_dashboards,
)
from za_local_payroll.setup.workplace import (
	COIDA_CHARTS,
	COIDA_MODULE,
	COIDA_NUMBER_CARDS,
	LABOUR_CHARTS,
	LABOUR_MODULE,
	LABOUR_NUMBER_CARDS,
	seed_workplace_dashboards,
)

OWNED_MODULES = (
	(PAYROLL_MODULE, PAYROLL_NUMBER_CARDS),
	(COIDA_MODULE, COIDA_NUMBER_CARDS),
	(LABOUR_MODULE, LABOUR_NUMBER_CARDS),
)
OWNED_CHARTS = PAYROLL_CHARTS + COIDA_CHARTS + LABOUR_CHARTS


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
		stale = [cards[0] for _, cards in OWNED_MODULES]
		for spec in stale:
			frappe.db.set_value(CARD_DOCTYPE, spec["label"], "currency", "INR")

		# The setup wizard passes its payload positionally; it must be optional.
		repair_payroll_metrics(None)

		for spec in stale:
			self.assertEqual(
				frappe.db.get_value(CARD_DOCTYPE, spec["label"], "currency"),
				metric_currency(spec),
				f"{spec['label']} was not restamped",
			)

	def test_amount_metrics_are_denominated_in_the_site_currency(self):
		"""A count carries no currency: with one, 23 certificates render as "R 23.00"."""
		self.seed()
		expected = display_currency()
		self.assertTrue(expected)

		for doctype, specs, key in (
			(CARD_DOCTYPE, [spec for _, cards in OWNED_MODULES for spec in cards], "label"),
			(CHART_DOCTYPE, OWNED_CHARTS, "chart_name"),
		):
			for spec in specs:
				if not frappe.db.exists(doctype, spec[key]):
					continue
				self.assertEqual(
					frappe.db.get_value(doctype, spec[key], "currency"),
					expected if is_amount_metric(spec) else None,
					f"{doctype} {spec[key]}",
				)

	def test_sum_charts_total_their_field_rather_than_counting_documents(self):
		"""Frappe totals ``value_based_on`` and falls back to ``1`` when it is empty,
		so "PAYE Payable by Month" plotted 1 per month instead of the rand amount."""
		self.seed()
		sum_charts = [spec for spec in OWNED_CHARTS if spec.get("chart_type") == "Sum"]
		self.assertEqual(len(sum_charts), 5)
		for spec in sum_charts:
			if not frappe.db.exists(CHART_DOCTYPE, spec["chart_name"]):
				continue
			self.assertTrue(chart_value_field(spec), spec["chart_name"])
			self.assertEqual(
				frappe.db.get_value(CHART_DOCTYPE, spec["chart_name"], "value_based_on"),
				chart_value_field(spec),
				spec["chart_name"],
			)

	def test_coida_earnings_chart_is_dated_by_the_start_of_the_year(self):
		"""The current return ends next February, outside a "last year" window."""
		spec = next(s for s in COIDA_CHARTS if s["chart_name"] == "SA COIDA Assessable Earnings by Year")
		self.assertEqual(spec["based_on"], "from_date")
