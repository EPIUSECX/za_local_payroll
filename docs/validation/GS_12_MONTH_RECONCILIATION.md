> **Evidence copy.** This is the report as written on 7 October 2026 for the Global Services 12-month
> sample. The build and comparison scripts and the source workbook are kept in the `cohenix_development`
> repository under `docs/za-payroll-reconciliation`. The reconciliation workbook is
> [GS_12_MONTH_RECONCILIATION.xlsx](GS_12_MONTH_RECONCILIATION.xlsx).

# South Africa payroll localisation: 12-month reconciliation

**Site:** `cohenix.localhost` (development, not production) | **Company:** Metric Engineering (Pty) Ltd (MET)
**Stack:** Frappe/ERPNext 16.50.0, HRMS 16.20.1, `za_local_core` 2.0.0, `za_local_payroll` 2.1.0, `za_local_bma` 0.1.0
**Source data:** `GS Test Employee12MonthReport.xlsx` (11 employees, Oct 2025 to Sep 2026, printed 2026/10/06)
**Date:** 7 October 2026 | **Workbook:** [MET_GS_Reconciliation.xlsx](MET_GS_Reconciliation.xlsx)

All employees are fictitious ("Thabo Mokoena - 001" through "Michael O'Connor - 011"). Company registration numbers, tax references and bank numbers are test values.

## 1. Verdict

**CONDITIONAL GO** for monthly-paid, salaried South African employees on the standard PAYE/UIF/SDL path. **NO-GO** for claiming full-suite readiness until the untested areas in section 8 are exercised.

| Measure (132 employee-months) | Result |
|---|---|
| Earnings, every line item | **Exact** (R11,730,357.81, 0 differences) |
| UIF employee and employer | **Exact** (R23,379.84 each) |
| SDL | Exact except R0.01 in one cell (R115,752.79 vs R115,752.80) |
| Company contributions total | Exact except the same R0.01 |
| PAYE, cells within R0.05 | 93 of 132 |
| PAYE, cents-level rounding (max R0.38) | 14 more |
| PAYE, March/April 2026 tax-table timing | 22 cells; Mar + Apr combined within R0.02 to R0.07 per employee |
| PAYE, employee 003 retirement | 3 cells (-R73.38, +R73.41, -R84.77) |
| 12-month PAYE | R3,478,043.44 vs R3,478,128.40: **-R84.96** (R84.77 is employee 003) |
| Overrides or manual amounts | **None** |

Confidence that the localisation reproduces this payroll for this population: **high (about 90%)**. Confidence in the whole SA suite: **moderate (about 60%)**, because most of it was not exercised (section 8).

## 2. How the source system calculates (reverse-engineered, then confirmed)

I modelled the source in an independent Python script (no app code) before touching the site. It reproduces the source PAYE to the cent for every month except the three exceptions above.

1. **Cumulative year-to-date method** (SARS Fourth Schedule para 9(3)): annualise the average remuneration to date, tax it, take the portion for months elapsed, subtract PAYE already paid. This is what `za_local_payroll` implements, so no engine change was needed.
2. **PAYE base:** earnings less non-taxable reimbursements (`COMM_REIMBURSE`, `EXPCLAIM`) less retirement-annuity contributions (`RAF`).
3. **SDL base:** the same, 1%. **UIF:** 1% each side, capped at R17,712 (R177.12).
4. **BONUS is an annual (once-off) payment.** This was my first modelling error: I initially treated it as regular pay, which made employee 002 look as if it were taxed at a 41% top rate. Switching BONUS to Annual Payment fixed it to the cent.
5. **Medical credit:** employee 006 gets R364 per month in 2025/26 and R376 in 2026/27, matching the packaged rates.
6. **Tax tables:** 2025/26 and 2026/27 brackets, rebates and credits in the packaged rate pack match the source to the cent.

## 3. What was configured

Full register in the workbook (Configuration Register sheet).

- **Company:** PAYE, UIF, SDL, income-tax and VAT references (test values); holiday list "MET South Africa 2025-2027" with a Holiday List Assignment.
- **Accounts:** Salaries and Wages, UIF Employer Expense, SDL Expense, PAYE Payable - SARS, UIF Employee and Employer Contribution, SDL Payable - SARS, Staff Deductions Payable, Retirement Annuity Payable.
- **Salary components (16 new, 4 seeded statutory):** SALARY, LAPTOP_ALLOW, SOFT_ALLOW, LIFE_COVER, HBR, PS_RISK, GS_VARIABLE, BONUS, REFERAL, COMM_REIMBURSE, EXPCLAIM, LIFE_COVER_DED, LIFE_COVER_ADD, LAPTOP_LEASE, PAYMENT, RAF, plus PAYE, UIF Employee/Employer, SDL. Each carries a SARS code, treatment, PAYE inclusion %, and UIF/SDL/COIDA flags set explicitly.
- **Salary Structure:** "MET GS Consultant Monthly" (SALARY = base, PAYE, UIF employer, SDL).
- **11 employees** with SA ID numbers, tax references, addresses and test bank details (the IRP5 step needs them).
- **23 Salary Structure Assignments:** split at 1 Oct 2025, 1 Mar 2026 (new Income Tax Slab) and at mid-year salary changes (employee 010 on 1 Jun 2026).
- **206 Additional Salary records** for every non-structure item (recurring where the amount repeats).
- **Employee Private Benefit** for 006 (main member, R1,915 contribution) for the medical credit.
- **Take-on** (`BMA Payroll Take-On`, year-to-date basis, 1 Mar to 30 Sep 2025): prepared by a Payroll Admin test user and submitted by a Payroll Manager test user. Maker-checker honoured.
- **Payroll:** 12 Payroll Entries run through the documented flow (submit entry, review draft slips, Submit Salary Slips), 132 submitted slips, 24 balanced accrual journals (debits = credits = R11,869,490.44).
- **Statutory outputs:** 12 EMP201 working papers (prepared and reviewed by different users), interim EMP501 (Mar to Aug 2026) with 11 submitted IRP5 certificates. IRP5 PAYE total (R1,730,242.06) equals EMP201 PAYE for the period.

## 4. What was wrong, and what was fixed

| # | Issue | Type | Action |
|---|---|---|---|
| 1 | `za_local_bma` `take_on_periods_before` read `slip.get("payroll_period")`. On HRMS 16.20 `payroll_period` is a property, so it returned `None` and take-on periods counted as 0. PAYE annualised on 2 periods instead of 8 (R75,886 for 001 in Oct 2025). | **Product defect** | Fixed in `za_local_bma/payroll_ops/takeon.py` (uncommitted); regression test added in `tests/test_bma_units.py` (passes with the fix, fails without). The existing take-on test used monthly history, which hides this. |
| 2 | Payroll blocked: no holiday calendar reached the company. | Preflight (by design) | Holiday list and assignment created. |
| 3 | Salary components had no account rows for MET. | Setup gap | Accounts and component account rows created. |
| 4 | BONUS modelled as regular pay. | My error | Changed to Annual Payment. |
| 5 | `RAF` flagged "statistical" still counted in total deductions. | Observation | Reverted to a normal retirement deduction. Statistical flag does not remove it from totals or the GL. |
| 6 | IRP5 blocked: residential address and bank details missing. | Gate working | Test data added. |
| 7 | EMP201 creation needs Payroll Manager. Payroll User and BMA Payroll Administrator cannot create it. | Role design | Used two Payroll Manager test users. Check this fits your operating model. |

## 5. Differences that remain, with root cause

1. **March and April 2026 (22 cells, offsetting).** The source calculated March 2026 with the 2025/26 tables (rebate R17,235, medical credit R364) and corrected in April. My independent model reproduces the source's March PAYE to R0.02 using the old tables. The system applies the 2026/27 tables from 1 March 2026, which is the legal position. Per employee, March + April differ by R0.02 to R0.07, and every later month matches. **The source is not "100% accurate" for March 2026.** Confirm with Global Services how their table load date is set. Replicating the source here would need a fixed pre-April slab, which the system cannot do correctly because rebates and credits are looked up by payroll period, not by slab.
2. **Employee 003 retirement (3 cells).** Source Jan/Feb differ by -R73.38/+R73.41 (reverses), and August by -R84.77 (persists to year-end). The source seems to allow a lower retirement deduction than the RAF memo line in those months. Cause unknown. I could not find a cap or rule that explains it.
3. **Cents-level rounding.** The system runs R0.02 to R0.07 below the source in most months and up to R0.38 in February (the year-end period). Consistent with the source rounding the annualised income slightly differently. Immaterial, but not "to the cent" for those cells.
4. **TOT:DED for 003.** The source shows RAF as a memo line outside total deductions. The system deducts it, so total deductions differ by R7,080.91 to R7,607.25 a month. Making it a non-deducting memo (do-not-include-in-total) matched the source but left Payroll Payable R88,702.66 lower than slip net pay in the GL, so I rejected it.
5. **Source naming and unknowns.** `SOFT_ALL` and `SOFT_ALLOW` are the same item; `LIFE_COVER` appears as both an earning and a deduction (a component name must be unique, so the deduction is `LIFE_COVER_DED`). I read `HBR` and `PS_RISK` footer lines as hours and `MEDAID` as the contribution; the source report does not label them, so confirm these readings.

## 6. Derived inputs you should not mistake for source data

The sample starts in October 2025, so the 1 Mar to 30 Sep 2025 opening balances are **derived**, not supplied. I solved taxable income and PAYE to date so that October matches, then checked November to February independently (they match to the cent, except the 003 items above). For constant earners the opening taxable figure is not uniquely identifiable; I chose the value closest to seven times average monthly pay. Treat October 2025 as calibration. November 2025 to September 2026 is the real test, and April to September 2026 depends on no fitted values. **Ask Global Services for the actual March to September 2025 totals** to remove this caveat. The table is in the workbook.

## 7. Controls and evidence

- **Backup before changes:** `20261007_073830-cohenix_localhost-database.sql.gz`, SHA-256 `3f751d25b9904771c9823e0246ec75cc4bc77f5557c56d68daafcf69a75a9310` (site `private/backups`, with files). Restore was not rehearsed.
- **Statutory rates:** Payroll Settings "Allow Packaged Statutory Rates" is **ticked**. No approved `ZA Statutory Rate Pack` or source evidence exists, so this is a recorded practitioner decision, not governance. The packaged rates matched the source for both years, but I did not retrieve or archive SARS publications.
- **Maker-checker:** exercised for take-on, EMP201, IRP5, EMP501. Not exercised for payment batches.
- **Not run:** the app test suites (`bench run-tests`), because the skill restricts them to a disposable site. Static checks (`ruff check`, `ruff format --check`) pass on the two edited files. The new unit test was run in isolation.
- **Reproducibility:** `scripts/` holds the build and comparison scripts. They use a local harness (`run.sh`, `hdr.py`) with absolute paths from this session, so adapt paths before reuse.
- **Copy-edit:** not run. The `copy-edit` skill was not available in this session. Enable it under Customize > Skills before the report goes to a client.

## 8. Not tested (limits of the confidence level)

ETI (all 11 are above R7,500 and over 29), fixed travel allowance, company car, housing and low-interest-loan fringe benefits, tax directives and lump sums, final settlements, age 65+ rebates, dependants beyond a main member, the retirement cap actually binding, weekly and fortnightly pay, mid-period joiners and leavers, unpaid leave, loans and garnishees, annual IRP5/EMP501 for a completed year, bank payment batches and FNB EFT, VAT, COIDA and the labour modules (`za_local_finance` and `za_local_workplace` are not installed on this site), and a source-evidenced rate-pack approval flow.

## 9. Confidence by domain

| Domain | Confidence | Basis |
|---|---|---|
| Payroll calculation, tested scenarios | High | 132 months; earnings, UIF, SDL exact; PAYE explained to R84.96 over 12 months |
| Payroll calculation, whole product | Moderate | Section 8 |
| Technical (install, config, runs) | Moderate-high | One real defect found and fixed; no test suite run |
| Statutory reporting (EMP201/IRP5/EMP501) | Moderate | EMP201 x12 and interim EMP501 tie to payroll; annual cycle and BRS filing untested |
| Payments | Not assessed | |
| VAT, workplace, COIDA | Not assessed | Apps not installed |
| Documentation | Moderate | Take-on guide does not warn that the year-to-date basis depended on the property fix |
| Operations (backup/restore, go-live) | Low | Restore not rehearsed; no parallel run |

## 10. Conditions before go-live and next actions

1. Commit the `za_local_bma` fix and its test (waiting on your decision; nothing is committed).
2. Get actual March to September 2025 totals from Global Services and rerun to remove the derived-balance caveat.
3. Ask Global Services why March 2026 used 2025/26 tables, and what drives employee 003's retirement deduction in Jan, Feb and Aug.
4. Approve a source-backed Payroll rate pack and archive the SARS publications, then untick "Allow Packaged Statutory Rates".
5. Run the section 8 scenarios on a disposable site, plus two accepted parallel cycles and a restore rehearsal.
