"""Move the Leave Type BCEA section from the Connections tab into the Details tab.

A Section Break whose ``insert_after`` is the last field of the Details tab is carried past
the Limits and Connections tab breaks, so the BCEA fields showed up under Connections. The
field definition now anchors the section after ``earning_component``. A site that already
created the field keeps the old anchor, because custom fields are created without overwriting
site customisation. Move it only if it still has the original anchor.
"""

import frappe

CUSTOM_FIELD = "Leave Type-za_bcea_section"
OLD_ANCHOR = "rounding"
NEW_ANCHOR = "earning_component"


def execute():
	if not frappe.db.exists("Custom Field", CUSTOM_FIELD):
		return
	if frappe.db.get_value("Custom Field", CUSTOM_FIELD, "insert_after") != OLD_ANCHOR:
		return
	frappe.db.set_value("Custom Field", CUSTOM_FIELD, "insert_after", NEW_ANCHOR, update_modified=False)
	frappe.clear_cache(doctype="Leave Type")
