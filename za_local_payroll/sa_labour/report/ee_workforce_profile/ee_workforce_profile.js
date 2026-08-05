frappe.query_reports["Ee Workforce Profile"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{ fieldname: "reporting_date", label: __("Reporting Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "show_small_cells", label: __("Reveal Small Cells (authorised reviewers only)"), fieldtype: "Check", default: 0 },
	],
};
