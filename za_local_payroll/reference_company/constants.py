"""Synthetic identifiers for the reference company. None of these are real."""

COMPANY = "Cohenix ZA Localisation Reference Company (Pty) Ltd"
ABBR = "CZAREF"
TRADING_NAME = "Cohenix ZA Reference"
# Synthetic: CIPC format YYYY/NNNNNN/07, VAT 10 digits starting 4, PAYE 7xxxxxxxxx,
# SDL Lxxxxxxxxx, UIF Uxxxxxxxxx (BRS 8.2 modulus-10 valid). None are issued registrations.
REGISTRATION_NUMBER = "2026/900001/07"
INCOME_TAX_REFERENCE = "9000000019"  # passes the SARS modulus-10 check (BRS 8.1)
VAT_NUMBER = "4900000017"
PAYE_REFERENCE = "7900000011"
SDL_REFERENCE = "L900000011"
UIF_REFERENCE = "U900000011"
COIDA_REFERENCE = "990000001"

NON_VAT_COMPANY = "Cohenix ZA Non-VAT Reference (Pty) Ltd"
NON_VAT_ABBR = "CZANV"
FOREIGN_COMPANY = "Cohenix UK Reference Ltd"
FOREIGN_ABBR = "CUKREF"

FY_2025 = ("2025-03-01", "2026-02-28")
FY_2026 = ("2026-03-01", "2027-02-28")

# Synthetic users for segregation of duties. Domain .test never resolves.
USERS = {
	"preparer": ("za.preparer@cohenix-ref.test", "Pat Preparer", ["ZA Compliance User", "Accounts Manager"]),
	"reviewer": ("za.reviewer@cohenix-ref.test", "Rae Reviewer", ["ZA Compliance Reviewer"]),
	# EE-PERM-1: EE small-cell reveal also needs Employee read, which ZA Compliance Reviewer lacks.
	"ee_reviewer": ("za.ee.reviewer@cohenix-ref.test", "Lee Equity", ["ZA Compliance Reviewer", "HR User"]),
	"approver": ("za.approver@cohenix-ref.test", "Avi Approver", ["ZA Compliance Manager"]),
	"submitter": ("za.submitter@cohenix-ref.test", "Sam Submitter", ["ZA Compliance Manager"]),
	"accounts_user": ("za.accounts.user@cohenix-ref.test", "Ace Accounts", ["Accounts User"]),
	"accounts_manager": ("za.accounts.manager@cohenix-ref.test", "Ama Accounts", ["Accounts Manager"]),
	"payroll_user": ("za.payroll.user@cohenix-ref.test", "Pia Payroll", ["Payroll User", "HR User"]),
	"payroll_manager": ("za.payroll.manager@cohenix-ref.test", "Pam Payroll", ["Payroll Manager", "HR User"]),
	"hr_manager": ("za.hr.manager@cohenix-ref.test", "Hal HR", ["HR Manager", "HR User"]),
	"hr_reviewer": ("za.hr.reviewer@cohenix-ref.test", "Rio Review", ["HR Manager", "HR User"]),
	"employee": ("za.employee.self@cohenix-ref.test", "Eve Employee", ["Employee"]),
	"foreign_accounts": ("uk.accounts@cohenix-ref.test", "Uma UK", ["Accounts User"]),
}
