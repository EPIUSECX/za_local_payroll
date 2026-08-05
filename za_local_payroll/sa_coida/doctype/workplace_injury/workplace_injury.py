from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, get_datetime, getdate, now_datetime
from za_local_core.governance import validate_populated_private_attachments

INJURY_LEAVE_CATEGORY = "Occupational Injury Leave"


class WorkplaceInjury(Document):
	def before_insert(self):
		self.reported_by = self.reported_by or frappe.session.user
		self.incident_reported_on = self.incident_reported_on or now_datetime()

	def validate(self):
		self.validate_dates()
		self.validate_incident_controls()
		validate_populated_private_attachments(self)
		if self.requires_leave and not self.leave_days:
			self.calculate_leave_days()
		self.set_statutory_deadline_status()

	def before_submit(self):
		if self.requires_claim:
			for fieldname in (
				"incident_mechanism",
				"body_part_affected",
				"investigation_summary",
			):
				if not self.get(fieldname):
					frappe.throw(
						_("{0} is required before submitting a claimable injury.").format(
							self.meta.get_label(fieldname)
						)
					)
		if self.requires_leave:
			self._validate_injury_leave_type()

	def validate_dates(self):
		if getdate(self.injury_date) > getdate():
			frappe.throw(_("Injury Date cannot be in the future"))
		if self.expected_recovery_date and getdate(self.expected_recovery_date) < getdate(self.injury_date):
			frappe.throw(_("Expected Recovery Date cannot be before Injury Date"))
		if self.return_to_work_date and getdate(self.return_to_work_date) < getdate(self.injury_date):
			frappe.throw(_("Return to Work Date cannot be before Injury Date"))
		if self.incident_reported_on and self.injury_time:
			incident_on = get_datetime(f"{self.injury_date} {self.injury_time}")
			if get_datetime(self.incident_reported_on) < incident_on:
				frappe.throw(_("Incident Reported On cannot be before the injury date and time."))

	def validate_incident_controls(self):
		if self.medical_attention_required and not self.medical_provider:
			frappe.throw(_("Medical Provider is required when medical attention was provided."))
		if self.has_witnesses and not (self.witness_details or "").strip():
			frappe.throw(_("Witness Details are required when witnesses are recorded."))
		if self.compensation_submitted_on:
			if not self.compensation_submission_reference:
				frappe.throw(_("Compensation Submission Reference is required after external submission."))
			if not self.compensation_receipt_evidence:
				frappe.throw(
					_("Private Compensation Receipt Evidence is required after external submission.")
				)

	def calculate_leave_days(self):
		self.leave_days = (
			date_diff(self.expected_recovery_date, self.injury_date) + 1 if self.expected_recovery_date else 7
		)

	def set_statutory_deadline_status(self):
		if not self.requires_claim:
			self.statutory_report_due_on = None
			self.statutory_deadline_status = "Not Required"
			return
		self.statutory_report_due_on = add_days(self.injury_date, 7)
		if self.compensation_submitted_on:
			self.statutory_deadline_status = (
				"Submitted On Time"
				if getdate(self.compensation_submitted_on) <= getdate(self.statutory_report_due_on)
				else "Submitted Late"
			)
		elif getdate() > getdate(self.statutory_report_due_on):
			self.statutory_deadline_status = "Overdue"
		else:
			self.statutory_deadline_status = "Due"

	def on_submit(self):
		"""Create requested linked drafts and fail the injury transaction on errors."""
		if self.requires_leave:
			self.create_leave_application()
		if self.requires_claim:
			self.create_oid_claim()

	def create_leave_application(self):
		"""Create a draft occupational-injury leave request for normal approval."""
		if self.leave_application:
			return self.leave_application
		if not frappe.db.table_exists("Leave Application"):
			frappe.throw(_("Leave Application is unavailable. Install and configure HRMS first."))
		self._validate_injury_leave_type()

		leave_application = frappe.new_doc("Leave Application")
		leave_application.update(
			{
				"employee": self.employee,
				"leave_type": self.injury_leave_type,
				"from_date": self.injury_date,
				"to_date": add_days(self.injury_date, cint(self.leave_days) - 1),
				"description": _("Workplace Injury: {0}").format(self.name),
			}
		)
		leave_application.insert()
		self.db_set("leave_application", leave_application.name, update_modified=False)
		frappe.msgprint(
			_("Draft Leave Application {0} created for review").format(frappe.bold(leave_application.name)),
			alert=True,
			indicator="green",
		)
		return leave_application.name

	def create_oid_claim(self):
		"""Create a draft OID claim or fail the injury transaction."""
		if self.oid_claim:
			return self.oid_claim

		oid_claim = frappe.new_doc("OID Claim")
		oid_claim.update(
			{
				"workplace_injury": self.name,
				"employee": self.employee,
				"company": self.company,
				"injury_date": self.injury_date,
				"injury_type": self.injury_type,
				"injury_location": self.injury_location,
				"injury_description": self.injury_description,
				"external_submission_reference": self.get("compensation_submission_reference"),
				"external_submitted_on": self.get("compensation_submitted_on"),
				"external_receipt_evidence": self.get("compensation_receipt_evidence"),
			}
		)
		oid_claim.insert()
		self.db_set("oid_claim", oid_claim.name, update_modified=False)
		frappe.msgprint(
			_("OID Claim {0} created").format(frappe.bold(oid_claim.name)),
			alert=True,
			indicator="green",
		)
		return oid_claim.name

	@frappe.whitelist(methods=["POST"])
	def create_oid_claim_after_submit(self):
		self.check_permission("write")
		self._require_submitted()
		if self.oid_claim:
			return self.oid_claim
		self.db_set("requires_claim", 1, update_modified=False)
		self.requires_claim = 1
		self.before_submit()
		return self.create_oid_claim()

	@frappe.whitelist(methods=["POST"])
	def create_leave_application_after_submit(self, leave_days=None, injury_leave_type=None):
		self.check_permission("write")
		self._require_submitted()
		if self.leave_application:
			return self.leave_application

		leave_days = cint(leave_days or self.leave_days)
		if leave_days <= 0:
			frappe.throw(_("Leave Days must be greater than zero."))
		self.injury_leave_type = injury_leave_type or self.injury_leave_type
		self._validate_injury_leave_type()
		self.db_set(
			{
				"requires_leave": 1,
				"leave_days": leave_days,
				"injury_leave_type": self.injury_leave_type,
			},
			update_modified=False,
		)
		self.leave_days = leave_days
		return self.create_leave_application()

	def _validate_injury_leave_type(self):
		if not self.injury_leave_type:
			frappe.throw(_("Select a governed Occupational Injury Leave Type."))
		category = frappe.db.get_value(
			"Leave Type",
			self.injury_leave_type,
			"za_bcea_leave_category",
		)
		if category != INJURY_LEAVE_CATEGORY:
			frappe.throw(
				_("Leave Type {0} must use BCEA Leave Category {1}.").format(
					frappe.bold(self.injury_leave_type),
					frappe.bold(INJURY_LEAVE_CATEGORY),
				)
			)

	def _require_submitted(self):
		if self.docstatus != 1:
			frappe.throw(_("This action is available only for a submitted Workplace Injury."))

	def on_cancel(self):
		if self.leave_application and frappe.db.exists("Leave Application", self.leave_application):
			leave_application = frappe.get_doc("Leave Application", self.leave_application)
			if leave_application.docstatus == 0:
				leave_application.delete()
			elif leave_application.docstatus == 1:
				leave_application.cancel()

		if self.oid_claim and frappe.db.exists("OID Claim", self.oid_claim):
			oid_claim = frappe.get_doc("OID Claim", self.oid_claim)
			if oid_claim.docstatus == 0:
				oid_claim.delete()
			elif oid_claim.docstatus == 1:
				oid_claim.cancel()
