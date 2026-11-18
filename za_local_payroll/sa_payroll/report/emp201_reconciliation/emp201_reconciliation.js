frappe.query_reports["EMP201 Reconciliation"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
	],
	formatter(value, row, column, data, default_formatter) {
		// EMP201 files UIF as one figure, so its parts have nothing to compare: show blanks, not R 0.00.
		if (["emp201_amount", "difference"].includes(column.fieldname) && data && data[column.fieldname] == null) {
			return "";
		}
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "check" && data?.check) {
			const indicator = { Agrees: "green", Differs: "red" }[data.check] || "gray";
			value = `<span class="indicator-pill ${indicator}">${value}</span>`;
		}
		return value;
	},
};
