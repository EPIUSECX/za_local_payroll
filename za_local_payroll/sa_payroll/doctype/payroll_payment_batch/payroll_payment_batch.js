// Copyright (c) 2025, Cohenix and contributors
// For license information, please see license.txt

const EFT_ROLES = ["HR Manager", "Accounts Manager", "System Manager"];

frappe.ui.form.on("Payroll Payment Batch", {
	setup(frm) {
		frm.set_query("bank_account", () => ({
			filters: {
				company: frm.doc.company,
				is_company_account: 1,
				disabled: 0,
			},
		}));
	},

	refresh(frm) {
		// Once the bank confirms payment, post it from the same snapshot the file was built from.
		if (frm.doc.docstatus === 1 && !frm.doc.settlement_journal_entry && frm.has_perm("submit")) {
			frm.add_custom_button(__("Record Bank Settlement"), () => {
				frappe.prompt(
					{fieldname: "posting_date", fieldtype: "Date", label: __("Bank Posting Date"), reqd: 1, default: frm.doc.payment_date},
					(values) => frm.call({doc: frm.doc, method: "record_bank_settlement", args: values, freeze: true}).then(() => frm.reload_doc()),
					__("Record Bank Settlement"),
					__("Post"),
				);
			});
		}
		if (frm.doc.docstatus !== 1 || !can_generate_eft(frm)) {
			return;
		}

		frm.add_custom_button(__("Generate FNB OBE CSV"), async () => {
			try {
				const response = await frappe.call({
					method: "za_local_payroll.utils.integrations.eft_file_generator.generate_eft_file",
					args: {payment_batch: frm.doc.name},
					freeze: true,
					freeze_message: __("Validating payroll and generating the private FNB file..."),
				});
				const result = response.message || {};
				await frm.reload_doc();
				frappe.show_alert({
					message: result.reused ? __("Existing private EFT file reused") : __("Private EFT file generated"),
					indicator: "green",
				});
				if (result.file_url) {
					window.open(encodeURI(result.file_url), "_blank", "noopener");
				}
			} catch (error) {
				frappe.show_alert({message: __("EFT file generation failed"), indicator: "red"});
			}
		});
	},

	bank_format(frm) {
		const format = frm.doc.bank_format;
		if (!format || format === "FNB OBE CSV") return;
		// A format an installed app has registered (an onboarded layout) is automated.
		frappe
			.call({ method: "za_local_payroll.utils.extension_points.registered_bank_format_names", type: "GET" })
			.then((r) => {
				if ((r.message || []).includes(format)) return;
				frappe.msgprint({
					title: __("Manual Bank Onboarding Required"),
					message: __("Automated {0} payroll files are disabled until the bank's current official layout has been verified and onboarded.", [format]),
					indicator: "orange",
				});
			});
	},
});

function can_generate_eft(frm) {
	return frm.has_perm("write") && EFT_ROLES.some((role) => frappe.user.has_role(role));
}
