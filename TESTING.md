# Payroll Verification and Release Gates

Run lifecycle tests only on a disposable site with Frappe, ERPNext, HRMS,
`za_local_core` and `za_local_payroll` installed. A green automated run is
necessary but does not approve an employer, tax year, bank file or SARS filing.

## Current automated evidence

The 2026-08-02 production-candidate exercise used deterministic fictional data on
an isolated site with the extracted applications and no legacy `za_local` app.
The recorded suite result was 141 payroll tests and 296 tests across the four
extracted apps. The synthetic end-to-end data included:

- 15 submitted Salary Slips with gross pay R281,500, deductions R40,508.87 and
  net pay R240,991.13;
- a timesheet case of 8 hours at R500, a recurring R1,500 Additional Salary, a
  R35,000 overwrite and a R10,000 full-tax bonus;
- six EMP201 working papers with PAYE R23,676.09, UIF R2,845.44, SDL R2,250,
  ETI generated R7,875 and ETI utilised R6,750;
- one EMP501 reconciliation, two certificates and one Payroll Payment Batch with
  a control total of R43,879.94; and
- repeated-migrate and backup/restore fingerprint comparisons.

Salary Slip, certificate and statutory print outputs were visually inspected in
that synthetic run. These figures prove only repeatability of the staged fixture;
they are not production data, bank acceptance or practitioner certification.

## Automated commands

Use the actual bench and disposable site names for the environment:

```bash
cd apps/za_local_payroll
uvx ruff check za_local_payroll
uvx ruff format --check za_local_payroll
git diff --check

cd ../..
bench --site <disposable-site> migrate
bench --site <disposable-site> run-tests --app za_local_payroll
```

Repeat `migrate` and compare schema/data fingerprints. Migration must stop with an
actionable error if duplicate active Payroll Payment Batches already exist.

## Mandatory payroll scenarios

Retain the Salary Slip, Payroll Entry, linked Journal Entries, relevant employer
working papers/certificates, calculation worksheet and reviewer identity.

1. Below-threshold and high-income employees across every PAYE bracket and age
   rebate boundary.
2. Employee below and above the dated UIF cap; employee and employer legs must
   each equal 1% of capped UIF remuneration.
3. Medical membership with zero, one and multiple dependants, including a
   part-year start/end and an unrelated private benefit that must not earn credit.
4. Pension code 4001, provident code 4003 and retirement-annuity code 4006 below
   and above the 27.5% and annual monetary limits.
5. Once-off full-tax bonus, recurring Additional Salary and overwrite Additional
   Salary that replaces rather than duplicates the structure row.
6. ETI at qualifying months 12/13/24/25, actual part-time hours, 160-hour
   gross-up/down, minimum-wage failure, exclusions, PAYE cap and March/September
   versus August/February carry treatment.
7. Mid-year joiner, leaver, final settlement, leave payout, directive and loan
   repayment submit/cancel/amend paths.
8. Timesheet payroll with visible Salary Component, hourly rate and frequency
   fields, and the correct hours-times-rate earning.
9. Company car with/without a maintenance plan, housing and low-interest loan
   benefits. Confirm taxable/certificate effects without cash-net-pay inflation.
10. Multi-company and transferred-employee certificate isolation.
11. Payroll Entry cancellation/amendment, confirming employer-contribution
   accruals reverse exactly once.
12. Multi-currency payroll where supported by the employer's policy.

## Reconciliation controls

- EMP201 PAYE/UIF/SDL and **ETI utilised** agree to submitted Salary Slips and
  the EMP201 calculation; ETI generated, available, utilised and carried forward
  remain separately traceable.
- Payroll and employer-contribution accruals agree to the General Ledger.
- Payroll Payment Batch source hash and control total agree to submitted Salary
  Slips and Payroll Payable; a second active batch is rejected.
- The generated FNB file is private and agrees to the submitted batch. Its
  generation is not proof of bank acceptance or payment.
- EMP201 is labelled **Prepared Working Paper** and recomputes at submit.
- IRP5/IT3(a) uses submitted Salary Slips in the selected Company/period and has
  the correct certificate type, reason code and directives.
- EMP501 reconciles submitted EMP201 records to submitted certificates. The
  separate third leg—actual PAYE payments—must be tied manually to SARS
  receipts/statements.

## Human and external release gates

Do not approve live payroll until the release record includes:

- at least two representative parallel payroll cycles and every frequency used;
- written South African payroll/tax-practitioner approval of official sources,
  rates, Income Tax Slabs, mappings, ETI, benefits, directives and test vectors;
- confirmation against the current SARS employer guide and current PAYE BRS;
- controlled eFiling/e@syFile test or dry-run evidence and a documented manual
  filing/payment/reconciliation procedure;
- low-value FNB OBE acceptance of the exact generated CSV, independent bank-portal
  approval and bank-statement reconciliation;
- finance sign-off of payroll, liabilities and employer contributions in the GL;
- permissions/POPIA review and private-file access tests; and
- migration, encrypted-backup restore and rollback rehearsal.

The employer remains responsible for employee facts, ETI eligibility, fund
classification, medical membership, benefit valuation, directives and all final
submissions and payments.
