"""Import app-owned workplace reference data with strict schema checks."""

from __future__ import annotations

from csv import DictReader
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, flt

MASTER_DATA_FILES = {
	("Business Trip Region", "business_trip_region.csv"): {
		"key": "region_name",
		"aliases": {},
	},
	("SETA", "seta_list.csv"): {"key": "seta_name", "aliases": {}},
	("Bargaining Council", "bargaining_council_list.csv"): {
		"key": "council_name",
		"aliases": {"sector": "industry_sector"},
	},
}


def import_csv_data(
	doctype: str,
	csv_filename: str,
	update_existing: bool = False,
	*,
	ignore_permissions: bool = False,
) -> dict[str, int]:
	"""Import one allowlisted app data file and return deterministic counts."""
	configuration = MASTER_DATA_FILES.get((doctype, csv_filename))
	if not configuration:
		frappe.throw(_("The requested workplace reference-data import is not allowed."))

	path = _data_path(csv_filename)
	meta = frappe.get_meta(doctype)
	valid_fields = {field.fieldname: field for field in meta.fields if field.fieldname}
	stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

	with path.open(encoding="utf-8", newline="") as handle:
		reader = DictReader(handle)
		_validate_headers(doctype, reader.fieldnames or [], valid_fields, configuration["aliases"])
		for row_number, raw_row in enumerate(reader, start=2):
			values = _convert_row(raw_row, valid_fields, configuration["aliases"])
			key_field = configuration["key"]
			key_value = values.get(key_field)
			if not key_value:
				frappe.throw(
					_("Row {0} in {1} has no value for {2}.").format(row_number, csv_filename, key_field)
				)

			existing = frappe.db.get_value(doctype, {key_field: key_value}, "name")
			if existing and not update_existing:
				stats["skipped"] += 1
				continue

			doc = frappe.get_doc(doctype, existing) if existing else frappe.new_doc(doctype)
			doc.update(values)
			if existing:
				doc.save(ignore_permissions=ignore_permissions)
				stats["updated"] += 1
			else:
				doc.insert(ignore_permissions=ignore_permissions)
				stats["created"] += 1

	return stats


def import_default_master_data() -> dict[str, dict[str, int]]:
	"""Seed missing app-owned reference rows without overwriting site data."""
	return {
		doctype: import_csv_data(
			doctype,
			filename,
			ignore_permissions=True,
		)
		for doctype, filename in MASTER_DATA_FILES
	}


def _data_path(csv_filename: str) -> Path:
	path = Path(frappe.get_app_path("za_local_payroll", "data", csv_filename)).resolve()
	data_root = Path(frappe.get_app_path("za_local_payroll", "data")).resolve()
	if path.parent != data_root or not path.is_file():
		frappe.throw(_("Workplace reference-data file {0} is unavailable.").format(csv_filename))
	return path


def _validate_headers(doctype, headers, valid_fields, aliases):
	mapped_headers = {aliases.get(header, header) for header in headers}
	unknown = sorted(mapped_headers - valid_fields.keys())
	if unknown:
		frappe.throw(
			_("{0} reference data contains unsupported column(s): {1}.").format(doctype, ", ".join(unknown))
		)


def _convert_row(raw_row, valid_fields, aliases):
	values = {}
	for source_field, value in raw_row.items():
		fieldname = aliases.get(source_field, source_field)
		field = valid_fields[fieldname]
		value = value.strip() if isinstance(value, str) else value
		if value == "":
			continue
		if field.fieldtype in {"Currency", "Float", "Percent"}:
			value = flt(value)
		elif field.fieldtype in {"Check", "Int"}:
			value = cint(value)
		values[fieldname] = value
	return values
