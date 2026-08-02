"""Company-scoped South African payroll statutory master setup."""

from __future__ import annotations

from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import getdate
from za_local_core.files import read_packaged_json
from za_local_core.localisation import is_south_african_company

from za_local_payroll.utils.statutory_rates import get_tax_year_for_date

PAYROLL_PERIOD_FILES = (
	"payroll_period_2025.json",
	"payroll_period_2026.json",
	"payroll_period_2027.json",
)
INCOME_TAX_SLAB_FILES = (
	"tax_slabs_2025.json",
	"tax_slabs_2026.json",
	"tax_slabs_2027.json",
)
TAX_REBATE_FILES = (
	"tax_rebates_2025.json",
	"tax_rebates_2026.json",
	"tax_rebates_2027.json",
)
PUBLIC_HOLIDAY_FILES = (
	"holiday_list_2025.json",
	"holiday_list_2026.json",
	"holiday_list_2027.json",
)


def ensure_all_company_tax_configuration() -> dict[str, dict]:
	"""Create missing statutory masters for every South African company."""
	ensure_sa_public_holiday_lists()
	return {
		company: ensure_company_tax_configuration(company)
		for company in frappe.get_all(
			"Company",
			filters={"country": "South Africa"},
			pluck="name",
			order_by="creation asc",
		)
	}


def ensure_sa_public_holiday_lists() -> list[str]:
	"""Create reference lists of official holidays without assigning weekly offs."""
	if not frappe.db.exists("DocType", "Holiday List"):
		return []

	synchronized = []
	for filename in PUBLIC_HOLIDAY_FILES:
		for source in _read_records(filename):
			name = source["holiday_list_name"]
			doc = (
				frappe.get_doc("Holiday List", name)
				if frappe.db.exists("Holiday List", name)
				else frappe.new_doc("Holiday List")
			)
			desired = [
				(str(row["holiday_date"]), row.get("description") or "", int(row.get("weekly_off") or 0))
				for row in source.get("holidays") or []
			]
			current = [
				(str(row.holiday_date), row.description or "", int(row.weekly_off or 0))
				for row in doc.get("holidays") or []
			]
			if (
				not doc.is_new()
				and str(doc.from_date) == str(source["from_date"])
				and str(doc.to_date) == str(source["to_date"])
				and current == desired
			):
				synchronized.append(name)
				continue

			doc.holiday_list_name = name
			doc.from_date = source["from_date"]
			doc.to_date = source["to_date"]
			doc.set("holidays", [])
			for row in source.get("holidays") or []:
				doc.append("holidays", row)
			doc.flags.ignore_permissions = True
			if doc.is_new():
				doc.insert(ignore_permissions=True)
			else:
				doc.save(ignore_permissions=True)
			synchronized.append(doc.name)
	return synchronized


def configure_new_south_african_company(doc, method=None) -> None:
	"""Create statutory masters after a South African Company is inserted."""
	if doc.country == "South Africa":
		ensure_company_tax_configuration(doc.name)


def ensure_company_tax_configuration(company: str) -> dict:
	"""Create missing company periods, slabs, rebates and medical credits.

	Existing records and child rows are never overwritten. Legislative changes
	must therefore be introduced as new effective-dated annual fixtures.
	"""
	_validate_company(company)
	period_names = {}
	created = []

	for filename in PAYROLL_PERIOD_FILES:
		for record in _read_records(filename):
			original_name = record["name"]
			actual_name, was_created = _ensure_company_record(record, company)
			period_names[original_name] = actual_name
			if was_created:
				created.append(actual_name)

	for filename in INCOME_TAX_SLAB_FILES:
		for record in _read_records(filename):
			actual_name, was_created = _ensure_company_record(record, company)
			if was_created:
				created.append(actual_name)

	settings = frappe.get_single("Tax Rebates and Medical Tax Credit")
	for filename in TAX_REBATE_FILES:
		data = read_packaged_json("za_local_payroll", "setup", "data", filename)
		_upsert_missing_child_rows(settings, "tax_rebates_rate", data, period_names)
		_upsert_missing_child_rows(settings, "medical_tax_credit", data, period_names)
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)

	return {"created": created, "payroll_periods": period_names}


def get_missing_current_tax_configuration(company: str, date_value=None) -> list[str]:
	"""Return actionable gaps for one company and payroll date.

	Companies outside South Africa have no South African statutory setup to
	complete, so they report no gaps and are never blocked by this app.
	"""
	if not is_south_african_company(company):
		return []
	date_value = getdate(date_value or frappe.utils.today())
	tax_year = get_tax_year_for_date(date_value)
	missing = []
	period = frappe.db.get_value(
		"Payroll Period",
		{
			"company": company,
			"start_date": ["<=", date_value],
			"end_date": [">=", date_value],
		},
		"name",
	)
	if not period:
		missing.append(_("Payroll Period for {0} ({1})").format(company, tax_year))

	slab = frappe.db.get_value(
		"Income Tax Slab",
		{
			"company": company,
			"effective_from": ["<=", date_value],
			"disabled": 0,
			"docstatus": 1,
		},
		"name",
		order_by="effective_from desc",
	)
	if not slab:
		missing.append(_("submitted Income Tax Slab for {0} ({1})").format(company, tax_year))

	if period:
		settings = frappe.get_single("Tax Rebates and Medical Tax Credit")
		if not any(row.payroll_period == period for row in settings.tax_rebates_rate or []):
			missing.append(_("Tax Rebate row for Payroll Period {0}").format(period))
		if not any(row.payroll_period == period for row in settings.medical_tax_credit or []):
			missing.append(_("Medical Tax Credit row for Payroll Period {0}").format(period))
	return missing


def validate_current_tax_configuration(company: str, date_value=None) -> None:
	"""Block payroll when mandatory statutory masters are incomplete."""
	missing = get_missing_current_tax_configuration(company, date_value)
	if missing:
		frappe.throw(
			_("South African payroll setup is incomplete:<br>{0}").format(
				"<br>".join(f"• {frappe.utils.escape_html(item)}" for item in missing)
			),
			title=_("Incomplete South African Payroll Setup"),
		)


def _validate_company(company: str) -> None:
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("A valid Company is required to configure South African payroll."))
	if frappe.db.get_value("Company", company, "country") != "South Africa":
		frappe.throw(_("Company {0} is not configured for South Africa.").format(company))


def _read_records(filename: str) -> list[dict]:
	data = read_packaged_json("za_local_payroll", "setup", "data", filename)
	return data if isinstance(data, list) else [data]


def _ensure_company_record(source: dict, company: str) -> tuple[str, bool]:
	record = deepcopy(source)
	doctype = record["doctype"]
	base_name = record["name"]
	name = _get_company_scoped_name(doctype, base_name, company)
	record["name"] = name
	record["company"] = company
	if frappe.db.exists(doctype, name):
		return name, False

	doc = frappe.get_doc(record)
	doc.insert(ignore_permissions=True)
	if doc.meta.is_submittable and doc.docstatus == 0:
		doc.submit()
	return doc.name, True


def _get_company_scoped_name(doctype: str, base_name: str, company: str) -> str:
	if frappe.db.exists(doctype, base_name):
		existing_company = frappe.db.get_value(doctype, base_name, "company")
		if existing_company in (None, "", company):
			return base_name
	if frappe.db.count("Company", {"country": "South Africa"}) <= 1:
		return base_name
	abbr = frappe.db.get_value("Company", company, "abbr") or company
	return f"{base_name} - {abbr}"


def _upsert_missing_child_rows(
	settings,
	child_field: str,
	data: dict,
	period_names: dict[str, str],
) -> None:
	existing = {row.payroll_period for row in settings.get(child_field) or []}
	for source in data.get(child_field) or []:
		row = deepcopy(source)
		row["payroll_period"] = period_names.get(row["payroll_period"], row["payroll_period"])
		if row["payroll_period"] in existing:
			continue
		settings.append(child_field, row)
		existing.add(row["payroll_period"])
