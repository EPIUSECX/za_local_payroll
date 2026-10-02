frappe.query_reports["EE Plan Progress"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			on_change: (report) => set_latest_plan(report),
		},
		{ fieldname: "target_plan", label: __("Employment Equity Target Plan"), fieldtype: "Link", options: "Employment Equity Target Plan", reqd: 1 },
		{ fieldname: "reporting_date", label: __("Reporting Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "show_small_cells", label: __("Reveal Small Cells (authorised reviewers only)"), fieldtype: "Check", default: 0 },
	],
	// Opened from the workspace or the setup checklist, show the company's
	// current plan rather than an empty "set filters" page.
	onload: (report) => set_latest_plan(report),
};

function set_latest_plan(report) {
	const company = report.get_filter_value("company");
	if (!company) {
		return;
	}
	frappe.db
		.get_list("Employment Equity Target Plan", {
			filters: { company: company, docstatus: 1 },
			fields: ["name"],
			order_by: "plan_end_date desc",
			limit: 1,
		})
		.then((plans) => {
			const plan = plans.length ? plans[0].name : "";
			if (report.get_filter_value("target_plan") !== plan) {
				report.set_filter_value("target_plan", plan);
			}
		});
}
