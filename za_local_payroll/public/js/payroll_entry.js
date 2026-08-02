frappe.ui.form.on("Payroll Entry", {
	refresh(frm) {
		if (
			frm.doc.docstatus !== 1 ||
			!(frm.doc.salary_slips_submitted || frm.doc.__onload?.submitted_ss)
		) {
			return;
		}

		frm.remove_custom_button(__("Make Bank Entry"));
		frm.add_custom_button(
			__("Create Payroll Payment Batch"),
			() => {
				frappe.new_doc("Payroll Payment Batch", {
					payroll_entry: frm.doc.name,
					company: frm.doc.company,
					payment_date: frm.doc.posting_date,
				});
			},
			__("Payments")
		).addClass("btn-primary");
	},
});
