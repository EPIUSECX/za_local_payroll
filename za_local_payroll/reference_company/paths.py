"""Evidence locations for the reference-company harness.

Inputs (archived official sources, golden statutory dataset) and outputs
(evidence JSON, PDFs, CSVs) live under one root, set per site with
``bench --site <site> set-config za_reference_evidence_dir <path>``.

Each location is a function, not a module constant: the root depends on the site's
configuration, and a constant computed at import would pin the first site's value for
every site served by the same process.
"""

from pathlib import Path

import frappe


def root() -> Path:
	return Path(frappe.conf.get("za_reference_evidence_dir") or "/home/user/za_evidence")


def sources() -> Path:
	return root() / "sources"


def golden_file() -> Path:
	return root() / "golden" / "golden_statutory_2026_27.json"


def payroll() -> Path:
	return root() / "payroll"


def vat() -> Path:
	return root() / "vat"
