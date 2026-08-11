"""Frappe integration points owned by the South African payroll app."""

from za_local_payroll.compat import dedicated_payroll_hooks_active

app_name = "za_local_payroll"
app_title = "SA Localisation Payroll & HR"
app_publisher = "Cohenix"
app_description = (
	"South African payroll and HR localisation: PAYE, UIF, SDL, ETI, employer "
	"declarations, payment controls, BCEA, Employment Equity, skills development "
	"and COIDA on Frappe HRMS."
)
app_email = "info@cohenix.com"
app_license = "mit"

za_local_practitioner_guide_provider = "za_local_payroll.practitioner_guide.provider.get_guide_sections"

required_apps = ["erpnext", "hrms", "za_local_core"]

before_install = "za_local_payroll.install.before_install"
after_install = "za_local_payroll.install.after_install"
after_migrate = "za_local_payroll.install.after_migrate"
before_uninstall = "za_local_payroll.install.before_uninstall"
after_uninstall = "za_local_core.navigation.sync_shared_navigation"

# The wizard is the first point at which the real company currency exists, and
# metrics seeded during install carry whatever default preceded it.
setup_wizard_complete = "za_local_payroll.install.repair_payroll_metrics"

if dedicated_payroll_hooks_active():
	app_include_css = "/assets/za_local_payroll/css/payroll.css"
	doctype_js = {
		"COIDA Annual Return": "public/js/coida_annual_return.js",
		"Employee": "public/js/employee.js",
		"Payroll Entry": "public/js/payroll_entry.js",
		"Employee Benefit Claim": "public/js/employee_benefit_claim.js",
		"Salary Structure": "public/js/salary_structure.js",
		"Salary Structure Assignment": "public/js/salary_structure_assignment.js",
		"OID Claim": "public/js/oid_claim.js",
		"Workplace Injury": "public/js/workplace_injury.js",
	}
	extend_doctype_class = {
		"Salary Slip": [
			"za_local_payroll.sa_payroll.fringe_benefits.salary_slip.FringeBenefitSalarySlipMixin",
		],
	}
	override_doctype_class = {
		"Employee Separation": "za_local_payroll.overrides.employee_separation.ZAEmployeeSeparation",
		"Leave Application": "za_local_payroll.overrides.leave_application.ZALeaveApplication",
		"Salary Slip": "za_local_payroll.overrides.salary_slip.ZASalarySlip",
		"Payroll Entry": "za_local_payroll.overrides.payroll_entry.ZAPayrollEntry",
		"Additional Salary": "za_local_payroll.overrides.additional_salary.ZAAdditionalSalary",
		"Salary Structure Assignment": (
			"za_local_payroll.overrides.salary_structure_assignment.ZASalaryStructureAssignment"
		),
	}
	doc_events = {
		"Company": {
			"after_insert": "za_local_payroll.setup.statutory.configure_new_south_african_company",
			"on_update": "za_local_payroll.setup.statutory.classify_company_salary_components",
		},
		"Journal Entry": {
			"on_trash": "za_local_payroll.overrides.journal_entry.on_trash",
			"on_cancel": "za_local_payroll.overrides.journal_entry.on_cancel",
		},
	}
	scheduler_events = {
		"daily_long": [
			"za_local_payroll.tasks.daily",
			"za_local_payroll.sa_payroll.fringe_benefits.tasks.refresh_fringe_benefit_statuses",
		],
		"weekly_long": ["za_local_payroll.tasks.weekly"],
		"monthly_long": ["za_local_payroll.tasks.monthly"],
	}
