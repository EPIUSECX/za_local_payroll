"""Stage 2: statutory governance - sources, rate packs, profile and obligations.

Evidence files are the official publications archived during independent
validation (see ``za_evidence/sources``). Values entered into rate packs come
from the independent golden dataset, never from the application's own packaged
data, so the pack is not validated against itself.
"""

import hashlib
import io
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path

import frappe
from frappe.utils.file_manager import save_file

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site


@contextmanager
def acting_as(user: str):
	# The harness impersonates each role to prove maker-checker and permissions. It only runs on
	# an isolated developer-mode test site (require_reference_site), never on a live site.
	previous = frappe.session.user
	frappe.set_user(user)  # nosemgrep
	try:
		yield
	finally:
		frappe.set_user(previous)  # nosemgrep


def user(key: str) -> str:
	return C.USERS[key][0]


def golden() -> dict:
	return json.loads(paths.golden_file().read_text())


def _bundle(name: str, files: list[str]) -> bytes:
	"""Zip several archived publications into one deterministic evidence bundle.

	A rate pack may cite exactly one ZA Statutory Source, so keys that come from
	more than one publication need a bundle (see gap register GOV-6).
	"""
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
		for filename in sorted(files):
			info = zipfile.ZipInfo(filename, date_time=(2026, 10, 1, 0, 0, 0))
			archive.writestr(info, (paths.sources() / filename).read_bytes())
		manifest = {f: hashlib.sha256((paths.sources() / f).read_bytes()).hexdigest() for f in sorted(files)}
		archive.writestr(
			zipfile.ZipInfo("MANIFEST.json", date_time=(2026, 10, 1, 0, 0, 0)),
			json.dumps({"bundle": name, "files": manifest}, indent=1, sort_keys=True),
		)
	return buffer.getvalue()


def _private_file(filename: str, content: bytes) -> str:
	digest = hashlib.sha256(content).hexdigest()
	existing = frappe.db.get_value(
		"File", {"content_hash": hashlib.md5(content).hexdigest(), "is_private": 1}, "file_url"
	)
	if existing:
		return existing
	return save_file(filename, content, None, None, is_private=1).file_url if digest else None


SOURCES = {
	# catalog_key: (seeded?, evidence files, extra metadata for new sources)
	"SARS-VAT-CONTROLS-2026-04-01": (
		True,
		[
			"www.sars.gov.za_tax-rates_other-taxes_.html",
			"www.sars.gov.za_about_sars-tax-and-customs-system_budget_budget-2026-frequently-asked-questions_.html",
			"www.sars.gov.za_businesses-and-employers_government_tax-invoices_.html",
		],
		None,
	),
	"SARS-PAYE-EMPLOYER-GUIDE-2027": (
		True,
		[
			"www.sars.gov.za_guide-for-employers-in-respect-of-employees-tax-2027_.html",
			"www.sars.gov.za_types-of-tax_unemployment-insurance-fund_.html",
			"sars_rate_per_km_2027.pdf",
		],
		None,
	),
	"SARS-PAYE-BRS-2026-27-V25.3.0": (True, ["sars_paye_brs_v25_3_0.pdf"], None),
	"COIDA-GAZETTE-54577-NOTICE-3910": (
		True,
		["coida_gazette_54577.pdf"],
		None,
	),
	"DEL-NMW-GAZETTE-54075-NOTICE-7083": (True, ["nmw_gazette_54075.pdf"], None),
	"DEL-BCEA-EARNINGS-THRESHOLD-2026": (True, ["bcea_threshold_2026.pdf"], None),
	"REF-LABOUR-BUNDLE-2026-05": (
		False,
		["nmw_gazette_54075.pdf", "bcea_threshold_2026.pdf"],
		{
			"authority": "Department of Employment and Labour",
			"title": "Labour bundle: NMW GN7083 (Gazette 54075) + BCEA threshold GN7384 (Gazette 54544)",
			"document_type": "Government Gazette bundle",
			"version": "2026-05",
			"publication_date": "2026-04-17",
			"effective_from": "2026-05-01",
			"effective_to": "2027-02-28",
			"source_url": "https://www.gov.za/sites/default/files/gcis_document/202602/54075rg11941gon7083.pdf",
		},
	),
	"REF-COIDA-BUNDLE-2026": (
		False,
		["coida_gazette_54577.pdf"],
		{
			"authority": "Compensation Fund",
			"title": "COIDA bundle: Gazette 54577 GN3910 + SYNTHETIC reference-company assessment notice",
			"document_type": "Gazette + assessment notice bundle",
			"version": "2026",
			"publication_date": "2026-04-24",
			"effective_from": "2026-03-01",
			"effective_to": "2027-02-28",
			"source_url": "https://www.gov.za/sites/default/files/gcis_document/202604/54577gen3910.pdf",
			"notes": "Assessment rate in this bundle is SYNTHETIC for the reference company. "
			"A real employer must attach its Compensation Fund assessment notice.",
		},
	),
}

SYNTHETIC_COIDA_NOTICE = (
	b"SYNTHETIC TEST DOCUMENT - NOT ISSUED BY THE COMPENSATION FUND\n"
	b"Employer: Cohenix ZA Localisation Reference Company (Pty) Ltd\n"
	b"CF registration: 990000001 (synthetic)\nIndustry class: 9 (office/professional, synthetic)\n"
	b"Assessment rate: 0.39 per R100 of assessable earnings (synthetic)\nPeriod: 2026-03-01 to 2027-02-28\n"
)


def stage_governance() -> dict:
	require_reference_site()
	sources = {key: _approve_source(key, *spec) for key, spec in SOURCES.items()}
	g = golden()
	packs = {
		"VAT": _approve_vat_pack(g),
		"Payroll": _ensure_pack(
			"Payroll",
			"Payroll scalars 2026/27 (UIF, SDL, travel, retirement, COIDA cap)",
			sources["SARS-PAYE-EMPLOYER-GUIDE-2027"],
			*C.FY_2026,
			_payroll_items(g),
		),
		"COIDA": _ensure_pack(
			"COIDA",
			"COIDA 2026/27 ceiling, minimum assessments and reference-company rate",
			sources["REF-COIDA-BUNDLE-2026"],
			*C.FY_2026,
			_coida_items(g),
		),
		"Labour-Mar-Apr": _ensure_pack(
			"Labour",
			"Labour NMW 2026-03-01 to 2026-04-30 (BCEA threshold not yet re-determined)",
			sources["DEL-NMW-GAZETTE-54075-NOTICE-7083"],
			"2026-03-01",
			"2026-04-30",
			_nmw_items(g),
		),
		"Labour-May-Feb": _ensure_pack(
			"Labour",
			"Labour NMW + BCEA threshold 2026-05-01 to 2027-02-28",
			sources["REF-LABOUR-BUNDLE-2026-05"],
			"2026-05-01",
			"2027-02-28",
			[
				*_nmw_items(g),
				_item(
					"bcea.earnings_threshold.annual",
					g["labour"]["bcea_earnings_threshold_annual"],
					"Amount",
					2,
				),
			],
		),
	}
	obligations = {
		"VAT201": _ensure_obligation(
			"ZA-VAT201",
			"VAT201 bi-monthly return",
			"VAT",
			"SARS",
			sources["SARS-VAT-CONTROLS-2026-04-01"],
			"Bi-monthly",
			"Last business day of the month after the period (eFiling)",
			"Controlled Manual",
		),
		"EMP201": _ensure_obligation(
			"ZA-EMP201",
			"EMP201 monthly employer declaration",
			"Payroll",
			"SARS",
			sources["SARS-PAYE-EMPLOYER-GUIDE-2027"],
			"Monthly",
			"7th of following month",
			"Controlled Manual",
		),
		"EMP501": _ensure_obligation(
			"ZA-EMP501",
			"EMP501 interim and annual reconciliation",
			"Payroll",
			"SARS",
			sources["SARS-PAYE-BRS-2026-27-V25.3.0"],
			"Six-monthly",
			"SARS filing season dates",
			"Controlled Manual",
		),
		"COIDA-ROE": _ensure_obligation(
			"ZA-COIDA-ROE",
			"COIDA Return of Earnings",
			"COIDA",
			"Compensation Fund",
			sources["COIDA-GAZETTE-54577-NOTICE-3910"],
			"Annual",
			"As published by the Compensation Fund",
			"Controlled Manual",
		),
	}
	profile = _approve_compliance_profile()
	_link_vat_obligation(obligations["VAT201"])
	commit_stage()
	return {"sources": sources, "packs": packs, "obligations": obligations, "profile": profile}


def _approve_source(catalog_key, seeded, files, metadata) -> str:
	name = frappe.db.get_value(
		"ZA Statutory Source", {"catalog_key": catalog_key, "docstatus": ("<", 2)}, "name"
	)
	if name and frappe.db.get_value("ZA Statutory Source", name, "docstatus") == 1:
		return name
	content = _bundle(catalog_key, files)
	if catalog_key == "REF-COIDA-BUNDLE-2026":
		buffer = io.BytesIO(content)
		with zipfile.ZipFile(buffer, "a") as archive:
			archive.writestr(
				zipfile.ZipInfo("SYNTHETIC_ASSESSMENT_NOTICE.txt", date_time=(2026, 10, 1, 0, 0, 0)),
				SYNTHETIC_COIDA_NOTICE,
			)
		content = buffer.getvalue()
	with acting_as(user("preparer")):
		file_url = save_file(f"{catalog_key}.zip", content, None, None, is_private=1).file_url
		if name:
			doc = frappe.get_doc("ZA Statutory Source", name)
			doc.source_file = file_url
		else:
			doc = frappe.get_doc(
				{
					"doctype": "ZA Statutory Source",
					"catalog_key": catalog_key,
					**metadata,
					"source_file": file_url,
				}
			)
		doc.reviewed_by = user("reviewer")
		doc.flags.ignore_permissions = True
		doc.save()
	with acting_as(user("reviewer")):
		doc = frappe.get_doc("ZA Statutory Source", doc.name)
		doc.submit()
	return doc.name


def _item(rule_key, value, unit, precision=2, notes=None) -> dict:
	row = {"rule_key": rule_key, "unit": unit, "precision": precision, "notes": notes}
	if unit == "Text":
		row["text_value"] = value
	else:
		row["numeric_value"] = value
	return row


def _payroll_items(g) -> list[dict]:
	ty = g["tax_years"]["2026-2027"]
	return [
		_item("uif.monthly_remuneration_cap", g["uif"]["monthly_ceiling"], "Amount"),
		_item("uif.employee_rate", g["uif"]["employee_rate"], "Percentage"),
		_item("uif.employer_rate", g["uif"]["employer_rate"], "Percentage"),
		_item("sdl.rate", g["sdl"]["rate"], "Percentage"),
		_item("travel.reimbursive_rate_per_km", ty["travel"]["reimbursive_rate_per_km"], "Amount"),
		_item(
			"travel.fixed_allowance_default_paye_inclusion_percentage",
			ty["travel"]["fixed_allowance_paye_inclusion"],
			"Percentage",
		),
		_item("retirement.annual_deduction_cap", ty["retirement"]["annual_cap"], "Amount"),
		_item("retirement.deduction_percentage", ty["retirement"]["percentage"], "Percentage"),
		_item("coida.annual_earnings_cap", g["coida"]["annual_earnings_cap"], "Amount"),
	]


def _coida_items(g) -> list[dict]:
	return [
		_item("coida.annual_earnings_cap", g["coida"]["annual_earnings_cap"], "Amount"),
		_item("coida.minimum_assessment", g["coida"]["minimum_assessment"], "Amount"),
		_item("coida.domestic_minimum_assessment", g["coida"]["domestic_minimum_assessment"], "Amount"),
		_item(
			f"coida.assessment_rate.{C.COMPANY}.9",
			0.39,
			"Percentage",
			4,
			"SYNTHETIC reference-company assessment rate per R100",
		),
	]


def _nmw_items(g) -> list[dict]:
	return [
		_item("nmw.general.hourly", g["labour"]["nmw_general_hourly"], "Amount"),
		_item("nmw.epwp.hourly", g["labour"]["nmw_epwp_hourly"], "Amount"),
		_item("nmw.learnership.schedule_2_reference", "Schedule 2 allowances", "Text", 0),
	]


def _approve_vat_pack(g) -> str:
	vat = g["vat"]
	expected = {
		"vat.standard_rate": vat["standard_rate"],
		"vat.registration.compulsory_threshold": vat["compulsory_threshold"],
		"vat.registration.voluntary_threshold": vat["voluntary_threshold"],
		"vat.invoice.no_invoice_max": vat["no_invoice_max"],
		"vat.invoice.full_invoice_threshold": vat["full_invoice_over"],
	}
	name = frappe.db.get_value(
		"ZA Statutory Rate Pack",
		{"domain": "VAT", "effective_from": "2026-04-01", "docstatus": ("<", 2)},
		"name",
	)
	doc = frappe.get_doc("ZA Statutory Rate Pack", name)
	if doc.docstatus == 1:
		return doc.name
	# Independent check of the seeded transcription before approval.
	mismatches = {
		row.rule_key: (row.numeric_value, expected.get(row.rule_key))
		for row in doc.items
		if row.rule_key in expected and float(row.numeric_value) != float(expected[row.rule_key])
	}
	if mismatches or {r.rule_key for r in doc.items} != set(expected):
		frappe.throw(f"Seeded VAT pack disagrees with the golden dataset: {mismatches}")
	doc.source = frappe.db.get_value(
		"ZA Statutory Source", {"catalog_key": "SARS-VAT-CONTROLS-2026-04-01", "docstatus": 1}, "name"
	)
	doc.reviewed_by = user("reviewer")
	doc.flags.ignore_permissions = True
	doc.save()
	with acting_as(user("reviewer")):
		frappe.get_doc("ZA Statutory Rate Pack", doc.name).submit()
	return doc.name


def _ensure_pack(domain, title, source, effective_from, effective_to, items) -> str:
	name = frappe.db.get_value(
		"ZA Statutory Rate Pack",
		{
			"domain": domain,
			"effective_from": effective_from,
			"effective_to": effective_to,
			"docstatus": ("<", 2),
		},
		"name",
	)
	if name and frappe.db.get_value("ZA Statutory Rate Pack", name, "docstatus") == 1:
		return name
	with acting_as(user("preparer")):
		doc = (
			frappe.get_doc("ZA Statutory Rate Pack", name)
			if name
			else frappe.new_doc("ZA Statutory Rate Pack")
		)
		doc.update(
			{
				"domain": domain,
				"title": title,
				"source": source,
				"effective_from": effective_from,
				"effective_to": effective_to,
				"reviewed_by": user("reviewer"),
			}
		)
		doc.set("items", items)
		doc.flags.ignore_permissions = True
		doc.save()
	with acting_as(user("reviewer")):
		frappe.get_doc("ZA Statutory Rate Pack", doc.name).submit()
	return doc.name


def _ensure_obligation(code, title, domain, authority, source, frequency, due_rule, capability) -> str:
	name = frappe.db.get_value("ZA Compliance Obligation", {"obligation_code": code, "docstatus": 1}, "name")
	if name:
		return name
	with acting_as(user("preparer")):
		doc = frappe.get_doc(
			{
				"doctype": "ZA Compliance Obligation",
				"obligation_code": code,
				"title": title,
				"domain": domain,
				"authority": authority,
				"source": source,
				"frequency": frequency,
				"due_rule": due_rule,
				"capability": capability,
				"active": 1,
				"effective_from": C.FY_2026[0],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
	with acting_as(user("approver")):
		frappe.get_doc("ZA Compliance Obligation", doc.name).submit()
	return doc.name


def _approve_compliance_profile() -> str:
	name = frappe.db.get_value(
		"ZA Company Compliance Profile", {"company": C.COMPANY, "docstatus": ("<", 2)}, "name"
	)
	if name and frappe.db.get_value("ZA Company Compliance Profile", name, "docstatus") == 1:
		return name
	with acting_as(user("preparer")):
		evidence = save_file(
			"reference-profile-approval.txt",
			b"SYNTHETIC approval memo: reference company registrations confirmed against synthetic letters.",
			None,
			None,
			is_private=1,
		).file_url
		doc = (
			frappe.get_doc("ZA Company Compliance Profile", name)
			if name
			else frappe.new_doc("ZA Company Compliance Profile")
		)
		doc.update(
			{
				"company": C.COMPANY,
				"enabled": 1,
				"effective_from": C.FY_2026[0],
				"vat_registered": 1,
				"paye_registered": 1,
				"uif_registered": 1,
				"sdl_registered": 1,
				"coida_registered": 1,
				"employment_equity_designated": 1,
				"seta": "SERVICES SETA",
				"bargaining_council": "",
				"coida_industry_class": "9",
				"filing_contact": user("approver"),
				"approved_by": user("approver"),
				"approval_evidence": evidence,
				"notes": "Reference company profile - synthetic registrations.",
			}
		)
		doc.flags.ignore_permissions = True
		doc.save()
	with acting_as(user("reviewer")):
		frappe.get_doc("ZA Company Compliance Profile", doc.name).mark_reviewed()
	with acting_as(user("approver")):
		frappe.get_doc("ZA Company Compliance Profile", doc.name).submit()
	return doc.name


def _link_vat_obligation(obligation: str) -> None:
	# Stored for the VAT stage; settings record may not exist yet.
	frappe.flags.za_reference_vat201_obligation = obligation
