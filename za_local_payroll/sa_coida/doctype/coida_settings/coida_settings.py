import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime
from za_local_core.governance import validate_private_evidence

from za_local_payroll.utils.coida_utils import validate_industry_rates


class COIDASettings(Document):
	def validate(self):
		self.validate_industry_rates()
		self._invalidate_changed_legacy_fallback()
		self._validate_legacy_fallback_configuration()

	def validate_industry_rates(self):
		"""Ensure industry rates are valid and unambiguous."""
		result = validate_industry_rates(self.industry_rates)
		if not result["valid"]:
			frappe.throw("<br>".join(result["errors"]), title=_("Invalid COIDA Industry Rates"))

	@frappe.whitelist(methods=["POST"])
	def approve_legacy_rate_fallback(self):
		"""Approve a temporary migration fallback with independent evidence."""
		self.check_permission("write")
		frappe.only_for(("ZA Compliance Manager", "System Manager"))
		if not self.allow_legacy_rate_fallback:
			frappe.throw(_("Enable the legacy-rate fallback before requesting approval."))
		if frappe.session.user == self.legacy_rate_prepared_by:
			frappe.throw(
				_("The user who prepared the legacy-rate fallback cannot approve it."),
				frappe.PermissionError,
			)
		self._validate_legacy_fallback_configuration(require_approval=False)
		validate_private_evidence(self, "legacy_rate_evidence", required=True)
		self.db_set(
			{
				"legacy_rate_fallback_status": "Approved",
				"legacy_rate_reviewed_by": frappe.session.user,
				"legacy_rate_reviewed_on": now_datetime(),
			},
			update_modified=True,
		)
		return {"status": "Approved"}

	def _invalidate_changed_legacy_fallback(self):
		previous = self.get_doc_before_save()
		if not previous:
			if self.allow_legacy_rate_fallback:
				self.legacy_rate_prepared_by = frappe.session.user
				self.legacy_rate_fallback_status = "Draft"
			return

		controlled_fields = (
			"allow_legacy_rate_fallback",
			"legacy_rate_effective_from",
			"legacy_rate_effective_to",
			"legacy_rate_source_reference",
			"legacy_minimum_assessment",
			"legacy_domestic_minimum_assessment",
			"legacy_rate_evidence",
			"industry_rates",
		)
		if any(self.get(fieldname) != previous.get(fieldname) for fieldname in controlled_fields):
			self.legacy_rate_prepared_by = frappe.session.user
			self.legacy_rate_fallback_status = "Draft"
			self.legacy_rate_reviewed_by = None
			self.legacy_rate_reviewed_on = None

	def _validate_legacy_fallback_configuration(self, *, require_approval=True):
		if not self.allow_legacy_rate_fallback:
			return
		for fieldname in (
			"legacy_rate_effective_from",
			"legacy_rate_effective_to",
			"legacy_rate_source_reference",
			"legacy_rate_evidence",
			"legacy_minimum_assessment",
			"legacy_domestic_minimum_assessment",
		):
			if not self.get(fieldname):
				frappe.throw(
					_("{0} is required for the controlled legacy-rate fallback.").format(
						self.meta.get_label(fieldname)
					)
				)
		if getdate(self.legacy_rate_effective_from) > getdate(self.legacy_rate_effective_to):
			frappe.throw(_("Legacy Rate Effective From cannot be after Effective To."))
		if flt(self.legacy_minimum_assessment) <= 0 or flt(self.legacy_domestic_minimum_assessment) <= 0:
			frappe.throw(_("Both approved legacy minimum assessments must be greater than zero."))
		validate_private_evidence(self, "legacy_rate_evidence", required=True)
		if require_approval and self.legacy_rate_fallback_status == "Approved":
			if not self.legacy_rate_reviewed_by or not self.legacy_rate_reviewed_on:
				frappe.throw(_("Approved legacy-rate fallback controls require reviewer evidence."))
