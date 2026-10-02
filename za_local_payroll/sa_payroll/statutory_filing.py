"""Maker-checker and compliance-filing controls for EMP201, EMP501 and IRP5 working papers.

A payroll working paper is prepared by one user and submitted by a different, recorded
Payroll Manager. Once submitted, EMP201 and EMP501 hand a private, checksummed working
paper to the core ZA Filing, whose own review, approval and SARS receipt controls then
apply. Submission to SARS itself happens on eFiling or e@syFile, outside the system.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, now_datetime
from frappe.utils.file_manager import save_file
from za_local_core.governance import validate_accountable_actor

REVIEW_ROLES = ("Payroll Manager", "System Manager")


def set_preparer(doc) -> None:
	if not doc.get("prepared_by"):
		doc.prepared_by = frappe.session.user


def require_independent_review(doc) -> None:
	"""Only the recorded reviewer, who is neither creator nor preparer, may submit."""
	if not doc.get("prepared_by"):
		doc.prepared_by = doc.owner
	validate_accountable_actor(
		doc,
		"reviewed_by",
		REVIEW_ROLES,
		"submit",
		additional_excluded_users=(doc.prepared_by,),
	)
	doc.reviewed_on = now_datetime()


def emp201_due_date(period_end, company: str | None = None):
	"""Fourth Schedule para 2(1): within seven days after the month end.

	A due date on a weekend or a holiday in the company's default Holiday List moves
	to the last business day before it.
	"""
	due = add_days(getdate(period_end), 7)
	holidays = set()
	holiday_list = company and frappe.db.get_value("Company", company, "default_holiday_list")
	if holiday_list:
		holidays = {
			getdate(day) for day in frappe.get_all("Holiday", {"parent": holiday_list}, pluck="holiday_date")
		}
	while due.weekday() >= 5 or due in holidays:
		due = add_days(due, -1)
	return due


def create_filing(
	doc,
	*,
	obligation_setting: str,
	period_start,
	period_end,
	declared_amount: float,
	ledger_amount: float,
	payload: dict,
) -> str:
	"""Create one idempotent ZA Filing from a submitted payroll working paper."""
	if doc.docstatus != 1:
		frappe.throw(_("Submit {0} before creating its ZA Filing.").format(doc.doctype))
	if doc.get("za_filing"):
		return doc.za_filing
	frappe.has_permission("ZA Filing", "create", throw=True)
	obligation = frappe.db.get_single_value("Payroll Settings", obligation_setting)
	if not obligation:
		frappe.throw(
			_("Set {0} in Payroll Settings before creating the ZA Filing.").format(
				frappe.get_meta("Payroll Settings").get_label(obligation_setting)
			)
		)
	missing = [
		doc.meta.get_label(fieldname)
		for fieldname in ("filing_due_date", "filing_reviewer", "filing_approver")
		if not doc.get(fieldname)
	]
	if missing:
		frappe.throw(_("Complete {0} before creating the ZA Filing.").format(", ".join(missing)))

	content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str).encode()
	checksum = hashlib.sha256(content).hexdigest()
	file_doc = save_file(
		f"{doc.name}-working-paper.json",
		content,
		doc.doctype,
		doc.name,
		is_private=1,
		df="working_paper_file",
	)
	filing = frappe.get_doc(
		{
			"doctype": "ZA Filing",
			"company": doc.company,
			"obligation": obligation,
			"period_start": period_start,
			"period_end": period_end,
			"due_date": doc.filing_due_date,
			"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
			"ledger_amount": flt(ledger_amount, 2),
			"declared_amount": flt(declared_amount, 2),
			"paid_amount": 0,
			"reviewed_by": doc.filing_reviewer,
			"approved_by": doc.filing_approver,
			"working_paper": file_doc.file_url,
			"working_paper_sha256": checksum,
		}
	)
	try:
		filing.insert()
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		frappe.throw(
			_(
				"An active ZA Filing already exists for {0} from {1} to {2}. Cancel it before filing again."
			).format(obligation, period_start, period_end)
		)
	doc.db_set(
		{"za_filing": filing.name, "working_paper_file": file_doc.file_url, "working_paper_sha256": checksum},
		update_modified=False,
	)
	return filing.name


def payroll_liability_ledger_amount(company: str, from_date, to_date, components) -> tuple[float, list[str]]:
	"""Net credits to the liability accounts of the given components on payroll journals.

	``components`` maps a salary component to the slip table it came from. A deduction is
	credited to its Salary Component Account; an employer contribution to its
	Liability Account. Returns the amount and any component whose liability cannot be
	identified because it falls back to Payroll Payable.
	"""
	accounts, unidentified = set(), []
	for component, table in sorted(components.items()):
		mapping = frappe.db.get_value(
			"Salary Component Account",
			{"parent": component, "company": company},
			["account", "za_liability_account"],
			as_dict=True,
		)
		account = mapping and (
			mapping.za_liability_account if table == "company_contribution" else mapping.account
		)
		if account:
			accounts.add(account)
		else:
			unidentified.append(component)
	if not accounts:
		return 0.0, unidentified
	amount = frappe.db.sql(
		"""
		select coalesce(sum(jea.credit - jea.debit), 0)
		from `tabJournal Entry Account` jea
		join `tabJournal Entry` je on je.name = jea.parent
		where je.docstatus = 1 and je.company = %(company)s
			and je.posting_date between %(from_date)s and %(to_date)s
			and jea.account in %(accounts)s
			and exists (
				select 1 from `tabJournal Entry Account` ref
				where ref.parent = je.name and ref.reference_type = 'Payroll Entry'
			)
		""",
		{"company": company, "from_date": from_date, "to_date": to_date, "accounts": tuple(accounts)},
	)[0][0]
	return flt(amount, 2), unidentified


def record_receipt(doc, **receipt) -> str:
	"""Record SARS's response on the approved ZA Filing (shared with VAT201)."""
	from za_local_core.sa_vat.filing import record_submission_receipt

	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted {0} can record SARS submission evidence.").format(doc.doctype))
	return record_submission_receipt(doc, **receipt)
