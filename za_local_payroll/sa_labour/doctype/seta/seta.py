import frappe
from frappe import _
from frappe.model.document import Document


class SETA(Document):
	def validate(self):
		if not self.source_reference:
			frappe.msgprint(
				_(
					"Record the current authority/source reference before using this SETA in an approved WSP or ATR."
				),
				alert=True,
				indicator="orange",
			)
