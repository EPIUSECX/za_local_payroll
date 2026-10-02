"""Evidence locations for the reference-company harness.

Inputs (archived official sources, golden statutory dataset) and outputs
(evidence JSON, PDFs, CSVs) live under one root, set per site with
``bench --site <site> set-config za_reference_evidence_dir <path>``.
"""

from pathlib import Path

import frappe

ROOT = Path(frappe.conf.get("za_reference_evidence_dir") or "/home/user/za_evidence")
SOURCES = ROOT / "sources"
GOLDEN_FILE = ROOT / "golden" / "golden_statutory_2026_27.json"
PAYROLL = ROOT / "payroll"
VAT = ROOT / "vat"
