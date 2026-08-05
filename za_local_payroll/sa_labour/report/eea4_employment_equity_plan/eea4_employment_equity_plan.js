frappe.query_reports["Eea4 Employment Equity Plan"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{ fieldname: "target_plan", label: __("Employment Equity Target Plan"), fieldtype: "Link", options: "Employment Equity Target Plan", reqd: 1 },
		{ fieldname: "reporting_date", label: __("Reporting Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "show_small_cells", label: __("Reveal Small Cells (authorised reviewers only)"), fieldtype: "Check", default: 0 },
	],
};
