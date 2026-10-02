"""Generate configuration evidence matrices from the live reference site.

Every table is read from the database at run time, so the evidence describes
the configuration that was actually tested, not the configuration intended.
Output: <evidence root>/config/*.md and config_evidence.json.
"""

import json

import frappe
from frappe.utils import flt

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.guard import require_reference_site


def _md(title, columns, rows, note=None):
	out = [f"# {title}", ""]
	if note:
		out += [note, ""]
	out.append("| " + " | ".join(columns) + " |")
	out.append("|" + "|".join("---" for _ in columns) + "|")
	for row in rows:
		out.append(
			"| "
			+ " | ".join(
				str(row.get(c, "") if row.get(c) is not None else "").replace("|", "/").replace("\n", " ")
				for c in columns
			)
			+ " |"
		)
	return "\n".join(out) + "\n"


def _sources():
	return frappe.get_all(
		"ZA Statutory Source",
		fields=[
			"name",
			"catalog_key",
			"authority",
			"title",
			"version",
			"effective_from",
			"effective_to",
			"status",
			"reviewed_by",
			"sha256_checksum",
		],
		order_by="catalog_key",
	)


def _rate_packs():
	rows = []
	for pack in frappe.get_all(
		"ZA Statutory Rate Pack",
		filters={"docstatus": 1},
		fields=[
			"name",
			"domain",
			"title",
			"source",
			"effective_from",
			"effective_to",
			"status",
			"reviewed_by",
		],
		order_by="domain, effective_from",
	):
		for item in frappe.get_all(
			"ZA Statutory Rate Item",
			filters={"parent": pack.name},
			fields=["rule_key", "numeric_value", "text_value", "unit"],
			order_by="idx",
		):
			rows.append(
				{
					"pack": pack.name,
					"domain": pack.domain,
					"effective_from": pack.effective_from,
					"effective_to": pack.effective_to,
					"source": pack.source,
					"rule_key": item.rule_key,
					"value": item.text_value or flt(item.numeric_value),
					"unit": item.unit,
				}
			)
	return rows


def _salary_components():
	fields = [
		"name",
		"type",
		"za_sars_payroll_code",
		"za_payroll_treatment",
		"za_paye_inclusion_percentage",
		"is_tax_applicable",
		"za_uif_applicable",
		"za_sdl_applicable",
		"za_coida_applicable",
		"za_is_reimbursement",
		"do_not_include_in_total",
		"statistical_component",
	]
	meta = frappe.get_meta("Salary Component")
	fields = [f for f in fields if f == "name" or meta.has_field(f)]
	used = set(
		frappe.get_all(
			"Salary Detail", filters={"parenttype": "Salary Slip"}, pluck="salary_component", distinct=True
		)
	)
	if frappe.db.exists("DocType", "Company Contribution"):
		used |= set(
			frappe.get_all(
				"Company Contribution",
				filters={"parenttype": "Salary Slip"},
				pluck="salary_component",
				distinct=True,
			)
		)
	rows = frappe.get_all("Salary Component", fields=fields, order_by="type, name")
	for row in rows:
		row["used_in_slips"] = int(row.name in used)
		row["sars_description"] = (
			frappe.db.get_value("SARS Payroll Code", row.get("za_sars_payroll_code"), "description")
			if row.get("za_sars_payroll_code") and frappe.db.exists("DocType", "SARS Payroll Code")
			else ""
		)
	return rows


def _structures():
	rows = []
	for s in frappe.get_all(
		"Salary Structure",
		filters={"company": C.COMPANY, "docstatus": 1},
		fields=["name", "payroll_frequency"],
		order_by="name",
	):
		doc = frappe.get_doc("Salary Structure", s.name)
		for table in ("earnings", "deductions"):
			for d in doc.get(table):
				rows.append(
					{
						"structure": s.name,
						"frequency": s.payroll_frequency,
						"table": table,
						"component": d.salary_component,
						"formula": d.formula if d.amount_based_on_formula else "",
						"amount": d.amount if not d.amount_based_on_formula else "",
						"condition": d.condition or "",
					}
				)
		for d in doc.get("company_contribution") or []:
			rows.append(
				{
					"structure": s.name,
					"frequency": s.payroll_frequency,
					"table": "company_contribution",
					"component": d.salary_component,
					"formula": d.formula if d.amount_based_on_formula else "",
					"amount": d.amount if not d.amount_based_on_formula else "",
					"condition": d.condition or "",
				}
			)
	return rows


def _vat():
	settings = frappe.get_doc("South Africa VAT Settings", {"company": C.COMPANY})
	keys = [
		"vat_registration_number",
		"standard_vat_rate",
		"statutory_control_date",
		"statutory_rate_pack",
		"statutory_source",
		"vat_registration_threshold",
		"vat_voluntary_threshold",
		"no_invoice_threshold",
		"full_invoice_threshold",
		"vat_filing_category",
		"vat_filing_frequency",
		"output_vat_account",
		"input_vat_account",
		"capital_input_vat_account",
		"import_input_vat_account",
	]
	setting_rows = [{"setting": k, "value": settings.get(k)} for k in keys]
	templates = []
	for doctype in ("Sales Taxes and Charges Template", "Purchase Taxes and Charges Template"):
		for t in frappe.get_all(doctype, filters={"company": C.COMPANY}, pluck="name", order_by="name"):
			doc = frappe.get_doc(doctype, t)
			for row in doc.taxes:
				templates.append(
					{
						"doctype": doctype.split()[0],
						"template": t,
						"account": row.account_head,
						"rate": row.rate,
						"classification": row.get("custom_vat_return_classification") or "",
					}
				)
	items = frappe.get_all(
		"Item",
		filters={"item_code": ["like", "REF-%"]},
		fields=["item_code", "item_name", "custom_sa_vat_category", "is_zero_rated"],
		order_by="item_code",
	)
	return setting_rows, templates, items


def _obligations():
	return (
		frappe.get_all(
			"ZA Compliance Obligation",
			fields=["name", "company", "obligation_type", "frequency", "status"],
			filters={"company": C.COMPANY},
		)
		if frappe.get_meta("ZA Compliance Obligation").has_field("obligation_type")
		else frappe.get_all("ZA Compliance Obligation", fields=["name"])
	)


def _readiness():
	return frappe.get_all(
		"ZA Feature Readiness", filters={"company": C.COMPANY}, fields=["*"], order_by="name"
	)


def stage_config_evidence() -> dict:
	require_reference_site()
	out_dir = paths.ROOT / "config"
	out_dir.mkdir(parents=True, exist_ok=True)
	data = {
		"sources": _sources(),
		"rate_packs": _rate_packs(),
		"salary_components": _salary_components(),
		"structures": _structures(),
		"readiness": _readiness(),
	}
	vat_settings, templates, items = _vat()
	data.update({"vat_settings": vat_settings, "tax_templates": templates, "vat_items": items})
	files = {
		"01_statutory_sources.md": _md(
			"Statutory sources",
			[
				"catalog_key",
				"authority",
				"title",
				"version",
				"effective_from",
				"effective_to",
				"status",
				"reviewed_by",
				"sha256_checksum",
			],
			data["sources"],
		),
		"02_rate_packs.md": _md(
			"Approved statutory rate packs",
			["domain", "pack", "effective_from", "effective_to", "source", "rule_key", "value", "unit"],
			data["rate_packs"],
		),
		"03_vat_settings.md": _md("South Africa VAT Settings", ["setting", "value"], vat_settings),
		"04_tax_templates.md": _md(
			"VAT tax templates", ["doctype", "template", "account", "rate", "classification"], templates
		),
		"05_vat_items.md": _md(
			"VAT item classification",
			["item_code", "item_name", "custom_sa_vat_category", "is_zero_rated"],
			items,
		),
		"06_salary_components.md": _md(
			"Salary components and SARS codes",
			[
				"name",
				"type",
				"za_sars_payroll_code",
				"sars_description",
				"za_payroll_treatment",
				"za_paye_inclusion_percentage",
				"is_tax_applicable",
				"za_uif_applicable",
				"za_sdl_applicable",
				"za_coida_applicable",
				"za_is_reimbursement",
				"do_not_include_in_total",
				"used_in_slips",
			],
			data["salary_components"],
		),
		"07_salary_structures.md": _md(
			"Salary structures",
			["structure", "frequency", "table", "component", "formula", "amount", "condition"],
			data["structures"],
		),
		"08_feature_readiness.md": _md(
			"Feature readiness",
			["domain", "feature_code", "feature_name", "status", "blocking_reason"],
			data["readiness"],
		),
	}
	for name, text in files.items():
		(out_dir / name).write_text(text)
	(out_dir / "config_evidence.json").write_text(json.dumps(data, indent=1, default=str))
	return {"files": sorted(files), "counts": {k: len(v) for k, v in data.items()}}
