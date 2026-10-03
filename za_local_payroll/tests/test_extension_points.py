"""Extension points let a private app add payroll behaviour without changing this app."""

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll.utils import extension_points
from za_local_payroll.utils.integrations import eft_file_generator as eft
from za_local_payroll.utils.integrations.eft_file_generator import PaymentRecipient


def _recipient(slip, amount, account="12345678901"):
	return PaymentRecipient(
		salary_slip=slip,
		employee="EMP-1",
		recipient_name="Test Employee",
		bank_account="ACC-1",
		account_number=account,
		account_type_code="1",
		branch_code="250655",
		amount=amount,
		recipient_reference="Salary 202608 EMP-1",
	)


class _Renderer:
	validated: ClassVar[list] = []

	@staticmethod
	def validate_company_account(account):
		_Renderer.validated.append(account)

	@staticmethod
	def render(snapshot):
		return {"content": "row", "control_total": "1", "filename": "TEST.csv"}


RENDERER = _Renderer()


def _hooks(mapping):
	return lambda name, *args, **kwargs: mapping.get(name, [])


class TestExtensionPoints(UnitTestCase):
	def test_no_hooks_keep_default_behaviour(self):
		with patch.object(frappe, "get_hooks", _hooks({})):
			self.assertFalse(extension_points.is_supplementary_entry("PAY-1"))
			self.assertEqual(extension_points.prior_period_count(None, 4), 4)
			self.assertEqual(extension_points.bank_formats(), {})
			with self.assertRaises(frappe.ValidationError):
				eft.normalize_bank_format("Investec Bulk Payment")

	def test_registered_bank_format_is_accepted_and_rendered(self):
		hooks = {"za_payroll_bank_formats": [f"{__name__}._formats"]}
		with patch.object(frappe, "get_hooks", _hooks(hooks)):
			self.assertEqual(eft.normalize_bank_format("investec bulk payment"), "Investec Bulk Payment")
			self.assertIs(eft._renderer("Investec Bulk Payment"), RENDERER)
			self.assertIsNone(eft._renderer("FNB OBE CSV"))

	def test_recipient_hook_may_split_but_not_change_totals(self):
		batch = SimpleNamespace(name="B")
		split = {"za_payroll_payment_recipients": [f"{__name__}._split"]}
		with patch.object(frappe, "get_hooks", _hooks(split)):
			rows = eft._apply_recipient_hooks([_recipient("SAL-1", "1000.00")], batch)
		self.assertEqual([r.amount for r in rows], ["300.00", "700.00"])
		bad = {"za_payroll_payment_recipients": [f"{__name__}._inflate"]}
		with patch.object(frappe, "get_hooks", _hooks(bad)):
			with self.assertRaises(frappe.ValidationError):
				eft._apply_recipient_hooks([_recipient("SAL-1", "1000.00")], batch)

	def test_supplementary_and_period_hooks_are_consulted(self):
		hooks = {
			"za_payroll_supplementary_entry": [f"{__name__}._is_supplementary"],
			"za_payroll_prior_period_count": [f"{__name__}._add_two"],
		}
		with patch.object(frappe, "get_hooks", _hooks(hooks)):
			self.assertTrue(extension_points.is_supplementary_entry("SUPP-1"))
			self.assertFalse(extension_points.is_supplementary_entry("PAY-1"))
			self.assertEqual(extension_points.prior_period_count(None, 3), 5)


def _formats():
	return {"Investec Bulk Payment": f"{__name__}.RENDERER"}


def _split(recipients, batch):
	row = recipients[0]
	return [
		PaymentRecipient(**{**row.__dict__, "amount": "300.00", "account_number": "11111111111"}),
		PaymentRecipient(**{**row.__dict__, "amount": "700.00"}),
	]


def _inflate(recipients, batch):
	return [PaymentRecipient(**{**recipients[0].__dict__, "amount": "1000.01"})]


def _is_supplementary(name):
	return name.startswith("SUPP")


def _add_two(slip, count):
	return count + 2
