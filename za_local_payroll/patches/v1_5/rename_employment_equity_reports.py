import frappe

# The reports carried each other's statutory form numbers: the income-differential
# report was labelled EEA2 and the plan-progress report EEA4. On the Department of
# Employment and Labour's forms, EEA2 is the Employment Equity Report and EEA4 the
# Income Differential Statement.
RENAMED = {
	"Eea2 Income Differentials": "EEA4 Income Differential Statement",
	"Eea4 Employment Equity Plan": "EE Plan Progress",
}


def execute():
	"""Remove the misnamed report records; model sync recreates them under the new names.

	Deleted directly rather than through ``delete_doc``: in developer mode a
	standard report's ``on_trash`` deletes its module folder, which is the
	renamed report's new home.
	"""
	for old in RENAMED:
		if frappe.db.exists("Report", old):
			frappe.db.delete("Has Role", {"parenttype": "Report", "parent": old})
			frappe.db.delete("Report", old)
