# SA Payroll Configuration and Testing Practitioner Guide

This guide explains how to configure, test and validate South African payroll
functionality in `za_local_payroll`.

## Purpose And Scope

SA Payroll extends HRMS for PAYE, UIF, SDL, ETI, retirement treatment, medical
tax credits, supported fringe benefits, employer contributions, payroll reports,
EMP201, EMP501 and IRP5/IT3(a) internal working papers.

HRMS is required. `za_local_payroll` does not replace HRMS payroll: HRMS remains
authoritative for Salary Structure, recurring/overwrite Additional Salary,
Salary Slip, benefit-ledger, loan, exchange-rate and rounding behaviour.

Direct SARS electronic submission is not supported. The app does not generate the SARS BRS payroll-import CSV or encrypted reconciliation file. Generic exports and PDFs are review aids only; capture approved figures through eFiling/e@syFile or use a separately validated BRS-compatible integration.

Use the current [SARS Guide for Employers](https://www.sars.gov.za/guide-for-employers-in-respect-of-employees-tax-2027/) and the applicable PAYE BRS/validation rules as primary references. Archive the exact publications used for annual signoff.

## Annual Statutory Update Checklist

An annual update is a governed source-and-data release, not a normal Desk edit.

Each year, before the first March payroll:

1. Archive the exact official publication as a restricted source record in
   `za_local_core`, including its checksum, effective dates and reviewer.
2. Create, review and submit one non-overlapping core **Payroll** rate pack for
   shared scalar values that changed during the period.
3. Update the payroll-owned structured annual pack for ETI, lump-sum and
   fringe-benefit rule tables through a reviewed code release.
4. Add or update Payroll Period, HRMS Income Tax Slab, rebate/medical-credit and
   other annual fixtures through that release.
5. Back up and migrate a restored staging site. Verify the submitted core pack,
   packaged structured pack and Desk masters separately. A packaged scalar
   fallback is not proof of source approval.
6. Run golden fictional cases on both sides of every effective-date change and
   compare them independently with the official publication.
7. Obtain written practitioner approval before the first affected payroll.

Do not mutate a historical submitted source/rate record or packaged pack after
payroll has used it. Add a dated correction with its own source evidence and
rerun every affected regression and parallel calculation.

## Prerequisites

Before configuring SA Payroll:

- HRMS is installed.
- A South African company exists.
- Payroll Period and Fiscal Year exist.
- Holiday List and Holiday List Assignment are configured.
- Employee records exist.
- Chart of accounts contains payroll expense, payroll payable, PAYE liability, UIF liability, SDL expense, and employer contribution accounts.
- The practitioner has access to HRMS payroll, Salary Components, Salary Structures, Payroll Entry, Employee, EMP201, EMP501, IRP5 Certificate, and payroll reports.

## Required Master Data And Settings

Review or create:

- Company PAYE reference number.
- Company UIF reference number.
- Company SDL reference number.
- Payroll Settings statutory components.
- Payroll Period.
- Income Tax Slab.
- Tax Rebates and Medical Tax Credit.
- SARS Payroll Codes.
- Salary Components with SARS code mappings.
- Employee Type.
- Employees with South African identity and tax fields.
- Date-effective Employee Private Benefit records for private medical scheme contributions and dependants.
- Submitted Fringe Benefit records and linked Company Car, Housing or Low Interest Loan detail records where non-cash benefits apply.
- Salary Structure and Salary Structure Assignment.
- Payroll Entry.
- Approved `ZA Statutory Source` evidence and an applicable submitted core
  Payroll rate pack, where shared scalar rates are governed in core.

## Configuration Tutorial

### 1. Configure Company Statutory References

1. Open `Company`.
2. Capture PAYE reference number.
3. Capture UIF reference number.
4. Capture SDL reference number.
5. Capture COIDA reference where applicable.
6. Save.

Validation:

- EMP501 readiness checks can find employer references.
- IRP5 / IT3(a) certificate fields can be populated from Company.

### 2. Configure Payroll Settings

1. Open `Payroll Settings`.
2. Set the PAYE salary component.
3. Set the UIF employee salary component.
4. Set the UIF employer salary component.
5. Set the SDL salary component.
6. Review any payroll frequency, rounding, or working-day settings required by HRMS.
7. Save.

Validation:

- Statutory components are selectable.
- Components are mapped to the correct salary component type and account rows.

### 3. Review Salary Components

Open `Salary Component` and review:

- Basic Salary.
- Allowances.
- Overtime.
- Commission.
- Bonuses.
- PAYE.
- UIF Employee Contribution.
- UIF Employer Contribution.
- SDL Contribution.
- Pension, provident, retirement annuity, or retirement fund components.
- Medical aid deduction and employer contribution components.
- Non-statutory deductions such as staff loans, garnishee orders, and union subscriptions.

For each component, confirm:

- Type is earning, deduction, or company contribution as intended.
- Account row exists for the company.
- SARS payroll code is mapped where the component must appear on EMP201, IRP5, or deduction reports.
- Components that must not appear on IRP5 are explicitly excluded where the app provides that option.
- SA Payroll Treatment, PAYE Inclusion %, UIF Applicable, SDL Applicable, COIDA Applicable, Reimbursement, and Variable Pay Treatment are configured.
- Fixed travel allowances use 80% PAYE inclusion by default unless the 20% statutory rule is explicitly supportable and documented.
- Reimbursive travel components are separated from fixed travel allowances and reviewed against the prescribed rate for the tax year.
- Retirement deductions use the fund-specific current BRS code: 4001 pension,
  4003 provident and 4006 retirement annuity. Do not use a generic retirement
  label or a seeded default without reviewing the actual fund.
- The ETI wage component flag is set only on remuneration used for the
  applicable minimum-wage comparison.

### 4. Review Tax Tables And Credits

1. Open `Income Tax Slab`.
2. Confirm the relevant South African tax year exists.
3. Confirm all PAYE brackets and rates.
4. Open `Tax Rebates and Medical Tax Credit`.
5. Confirm rebate rows and medical credit rows for the payroll year.
6. Save.

Validation:

- The Salary Structure Assignment can reference the correct Income Tax Slab.
- PAYE calculations use the expected tax year.

### 5. Configure Employees

For each employee:

1. Open `Employee`.
2. Set company, department, designation, date of joining, and employment status.
3. Set Employee Type.
4. Capture South African identity or passport details.
5. Capture income tax reference where available.
6. Capture bank details where salary payment and IRP5 output require them.
7. For a potentially eligible ETI employee, review the exclusion/eligibility
   facts, minimum-wage basis/rate and standard monthly hours. Capture actual
   period hours on the Salary Slip where they differ from the Employee fallback.
8. Capture Employment Equity fields if Labour reports are also used.
9. Save.

Validation:

- Employee can be used on Salary Structure Assignment.
- IRP5 readiness checks do not report avoidable missing fields.

### 6. Configure Medical And Fringe Benefits

Use `Employee Private Benefit` only for date-effective private medical scheme/medical-credit and retirement-annuity data. A medical credit requires an active record with a positive private-medical-aid contribution; capture the dependant count on that record and prevent overlapping active periods.

Use the separate submittable `Fringe Benefit` workflow for non-cash benefits. Link and submit the applicable Company Car, Housing or Low Interest Loan detail record, then submit the Fringe Benefit. Active submitted benefits are added to Salary Slips as taxable non-cash earnings: they affect PAYE and certificate reporting but do not increase cash gross/net pay or accounting earnings.

The generic `Other` benefit route does not determine a legally correct valuation
or SARS classification for the practitioner. Keep it in Preview unless the
value, code, inclusion and supporting evidence have been independently approved.

Validation:

- Company car uses 3.5%, or 3.25% with a maintenance plan, and the documented 80%/20% PAYE inclusion basis.
- Housing follows the paragraph 9 valuation and employee consideration rules using date-effective values.
- Low-interest loan uses current outstanding balance and the date-effective official rate.
- Draft, expired, disabled or unlinked benefit records do not affect payroll.

### 7. Configure Salary Structure

1. Create or open `Salary Structure`.
2. Add earnings.
3. Add deductions.
4. Add company contributions.
5. Ensure all components have account rows for the company.
6. Save and submit if required by HRMS.

For a timesheet/hourly structure, tick **Salary Slip Based on Timesheet** and
verify `Payroll Frequency`, `Salary Component` and `Hour Rate` remain visible.
The app hides only the unused `max_benefits` field. If the whole section is
hidden, stop and clear/rebuild assets or investigate a stale legacy `za_local`
CSS/client script before processing payroll.

### 7A. Configure Additional Salary

- A non-recurring row uses its Payroll Date.
- A recurring row uses `From Date`/`To Date`; HRMS clears Payroll Date and selects
  the record when its effective period includes the Salary Slip.
- Disabled rows are excluded.
- **Overwrite Salary Structure Amount** replaces the matching structure
  component. It must not create a second Basic/allowance row.
- **Deduct Full Tax on Selected Payroll Date** is a separate instruction for the
  selected additional earning. Test it with a bonus and reconcile the added tax.

Recommended test structures:

- Low salary structure.
- High salary structure.
- ETI qualifying structure.
- Medical aid structure.
- Retirement fund structure.
- Retirement cap stress structure.

### 8. Create Salary Structure Assignment

1. Open `Salary Structure Assignment`.
2. Select employee.
3. Select salary structure.
4. Set base amount.
5. Set from date.
6. Select Income Tax Slab.
7. Submit.

Validation:

- Salary Slip can be created from the assignment.
- Income tax slab is populated.

### 9. Process Payroll

1. Open `Payroll Entry`.
2. Select company, payroll period, payroll frequency, start date, and end date.
3. Get employees.
4. Create Salary Slips.
5. Review each Salary Slip.
6. Submit Salary Slips.
7. Submit Payroll Entry where applicable.
8. Post accounting entries.

Validation:

- Salary Slips calculate PAYE, UIF, SDL, ETI, retirement treatment, medical credits, and net pay correctly.
- GL Entries are balanced.
- Payroll payable and statutory liability accounts agree to payroll reports.

## Desk Test Cases

### Test 1: Payroll Settings Statutory Mapping

Steps:

1. Open Payroll Settings.
2. Confirm PAYE, UIF employee, UIF employer, and SDL components.
3. Save.

Expected result:

- Settings save.
- Each statutory component points to the intended Salary Component.

### Test 2: Low Salary PAYE/UIF Scenario

Steps:

1. Create an employee with a low monthly salary.
2. Assign a salary structure.
3. Create and submit a Salary Slip.

Expected result:

- UIF employee and employer calculate up to the monthly cap.
- PAYE reflects tax table, rebates, and taxable income.
- Net pay equals gross less deductions.

### Test 3: High Salary PAYE Scenario

Steps:

1. Create an employee with a high monthly salary.
2. Assign a structure with taxable earnings.
3. Submit a Salary Slip.

Expected result:

- PAYE uses the correct marginal tax brackets.
- UIF is capped.
- SDL is calculated as an employer contribution where configured.

### Test 4: ETI Qualifying Employee

Steps:

1. Create an employee who meets ETI criteria.
2. Capture ETI hours and identity details.
3. Submit a Salary Slip.

Expected result:

- ETI is generated only when all eligibility, exclusion, minimum-wage, hours and
  qualifying-month tests pass.
- Generated ETI is stored on the Salary Slip.
- EMP201 separately shows generated, brought-forward/available, utilised and
  carried-forward ETI. Only utilised ETI, capped by gross PAYE, reduces PAYE
  payable.

### Test 5: Medical Aid Main Member

Steps:

1. Create Employee Private Benefit for medical aid main member.
2. Submit Salary Slip.

Expected result:

- Medical tax credit is applied for the main member.
- PAYE is reduced only by the allowed credit.

### Test 6: Medical Aid Dependants

Steps:

1. Add dependants to the medical aid benefit.
2. Submit Salary Slip.

Expected result:

- Medical credit includes main member, first dependant, and additional dependant rates.
- The credit does not exceed configured statutory treatment.

### Test 7: Pension / Provident / Retirement Annuity

Steps:

1. Add a pension, provident or retirement-annuity deduction component.
2. Map code 4001, 4003 or 4006 respectively and verify the actual fund facts.
3. Submit Salary Slip.

Expected result:

- Retirement deduction is treated as pre-tax where allowed.
- Retirement Fund Deductions report shows the deduction.

### Test 8: Retirement Contribution Cap

Steps:

1. Create a salary slip where annualised retirement contributions exceed the statutory cap.
2. Submit Salary Slip.

Expected result:

- Excess retirement deduction is added back as taxable.
- Read-only retirement taxable excess field shows the excess.
- PAYE is calculated after the add-back.

### Test 9: Company Contributions

Steps:

1. Confirm Payroll Settings identifies the UIF employer and SDL components. The engine must materialise both rows when their bases are positive, even if a zero structure row was removed.
2. Submit Salary Slip.
3. Post Payroll Entry accounting.

Expected result:

- Employee deductions and employer contributions are separated.
- Employer contributions post to expense and payroll payable according to configuration.

### Test 10: Payroll Entry To GL

Steps:

1. Create Payroll Entry.
2. Submit Salary Slips.
3. Submit Payroll Entry and post accounting.
4. Open General Ledger.

Expected result:

- Earnings debit salary expense accounts.
- PAYE, UIF employee, and other deductions credit liability accounts.
- Net pay credits payroll payable.
- Employer contributions post as configured.

### Test 11: EMP201 Creation And Review

Steps:

1. Create `EMP201 Submission`.
2. Select company and month.
3. Fetch EMP201 data.
4. Review PAYE, UIF, SDL, ETI, and total payable.

Expected result:

- EMP201 values agree with submitted Salary Slips.
- ETI reduces PAYE only as allowed.
- Unmapped statutory components are flagged before finalisation.

### Test 12: EMP501 Reconciliation

Steps:

1. Create monthly EMP201 submissions for the reconciliation period.
2. Create `EMP501 Reconciliation`.
3. Select tax year and reconciliation period.
4. Fetch EMP201 references.
5. Validate coverage.

Expected result:

- Missing months are reported (six for an interim reconciliation, twelve for the annual reconciliation).
- EMP501 cannot proceed without required monthly declarations.
- EMP201 totals reconcile to submitted certificate totals before the internal working paper is submitted.
- Actual PAYE/SDL/UIF payments are not stored as the third reconciliation leg;
  tie them manually to SARS receipts/statements before external submission.

### Test 13: IRP5 / IT3(a) Certificate

Steps:

1. Generate or create IRP5 certificates for employees in the reconciliation period.
2. Review employer details.
3. Review employee identity, address, and bank details.
4. Review income, deduction, and employer contribution lines.
5. Print using `IRP5 Employee Certificate`.

Expected result:

- Certificate is linked to the correct EMP501 where applicable.
- Submitted certificates render to PDF.
- Long certificate numbers do not overlap critical text.
- Missing statutory data is visible for practitioner review.
- IRP5 versus IT3(a), the IT3(a) reason code and directive numbers are correct.
- The PDF is a review/certificate output, not a PAYE BRS import file.

### Test 16: FNB Payroll Payment Batch

Steps:

1. Create and submit one Payroll Payment Batch for the Payroll Entry.
2. Generate the supported FNB Online Banking Enterprise CSV.
3. Compare the private file to the batch source hash, employee amounts and
   control total.
4. Upload it to the bank test facility and have a second authorised user approve
   it in the bank portal.

Expected result:

- A duplicate active batch is rejected.
- The FNB adapter version and control total are explicit.
- Bank acceptance/rejection and the bank-statement result are retained outside
  the app's generated-file status. The app does not enforce maker/checker.

### Test 14: SA Salary Slip Print Format

Steps:

1. Open a submitted Salary Slip.
2. Print using `SA Salary Slip`.

Expected result:

- Earnings, deductions, company contributions, statutory amounts, gross pay, net pay, and company details are readable.
- No old app references appear.

### Test 15: Payroll Reports

Steps:

1. Run Payroll Register.
2. Run EMP201 Report.
3. Run Statutory Submissions Summary.
4. Run Department Cost Analysis.
5. Run Retirement Fund Deductions.

Expected result:

- Reports open without errors.
- Filters work for company and period.
- Report totals agree with submitted payroll records.

## Reports And Print Formats To Review

Reports:

- Payroll Register
- EMP201 Report
- Department Cost Analysis
- Statutory Submissions Summary
- Retirement Fund Deductions
- HRMS Salary Register
- HRMS Income Tax Computation
- General Ledger

Print formats:

- SA Salary Slip
- IRP5 Employee Certificate
- IRP5-it3 Certificate

## Common Mistakes And Troubleshooting

- If Salary Slip does not calculate, check Salary Structure Assignment and Income Tax Slab.
- If PAYE is zero unexpectedly, check taxable earnings, rebates, and tax slab.
- If UIF is missing, check Payroll Settings and salary component mapping.
- If SDL is missing, check company contribution rows.
- If EMP201 is incomplete, check submitted Salary Slips and SARS payroll code mappings.
- If EMP501 blocks submission, complete missing EMP201 months or IRP5 certificate references.
- If a timesheet field is missing, confirm only `max_benefits` is hidden and that
  no legacy CSS/JS or stale assets hide the containing section.
- If recurring Additional Salary is absent, check `is_recurring`, effective
  dates, disabled status and the Salary Slip period. Do not add a Payroll Date to
  a recurring record.
- If overwrite creates two rows, stop the run: the selected HRMS overwrite alias
  is not being preserved.
- If ETI does not reduce EMP201 PAYE by the generated amount, first compare
  generated with **utilised** ETI and the gross-PAYE cap; they need not be equal.
- Do not upload a generic EMP501/IRP5 CSV exported from the app to SARS; it is not a BRS payroll-import file.
- If IRP5 PDF is incomplete, review Company, Employee, Address, Salary Component, and certificate line data.
- If GL does not post correctly, review salary component account rows for the company.

## Practitioner Responsibility

Payroll practitioners must validate every official source, rate, employee
classification, fund mapping, medical membership, benefit valuation,
PAYE/UIF/SDL/ETI value, directive, working paper, certificate, bank control total
and GL posting. Only the identified FNB Online Banking Enterprise CSV is enabled,
and it requires formal bank acceptance and independent bank-portal approval.
`za_local_payroll` supports calculation and review; the employer remains
responsible for external filing, payment and legal compliance.
