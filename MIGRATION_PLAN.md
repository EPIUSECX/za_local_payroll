# SA Localisation Payroll Migration Plan

Status: extraction and isolated-site implementation complete. Payroll code,
metadata, setup, documentation and tests are owned by this app and have passed
legacy-compatible and legacy-free E2E runs. Production cutover remains gated by
restore evidence, independent practitioner and bank acceptance, and parallel-run
sign-off in `za_local_core/VALIDATION_AND_SIGNOFF.md`.

## Purpose and boundary

`za_local_payroll` is the South African HRMS foundation and payroll statutory engine. It owns employee legal/tax
identity extensions, payroll configuration, PAYE, UIF, SDL, ETI, retirement and medical credits, fringe benefits,
payroll payments, employer declarations, IRP5/IT3(a), directives and payroll accounting integration.

It depends on `za_local_core` for approved effective-dated sources, filing/evidence controls and company compliance
profiles. `za_local_workplace` depends on this app and consumes payroll bases through public services; payroll does
not import workplace controllers.

## Existing source to move

| Current source in `za_local` | Destination/treatment |
|---|---|
| `za_local/sa_payroll/` | Move all payroll DocTypes, children, reports, print formats and controllers while preserving names/tables. |
| `overrides/salary_slip.py` | Decompose into classification, statutory-basis, PAYE, benefits, totals and audit services; retain a thin controller override. |
| `overrides/payroll_entry.py` | Move employee validation, payroll processing and bank-entry integration; restore all upstream HRMS lifecycle behaviour. |
| `overrides/additional_salary.py` | Move only SA validation; reuse HRMS recurring/overwrite behaviour instead of replacing it. |
| `overrides/salary_structure_assignment.py` | Move annual bonus/opening-entry behaviour after field/schema validation. |
| Payroll-specific `overrides/journal_entry.py` | Move safe payroll cleanup/admin tools; require explicit development-only opt-in. |
| `utils/tax_utils.py`, `statutory_rates.py`, `eti_utils.py` | Refactor into deterministic, effective-dated calculation services. Rate records come from core. |
| `utils/payroll_utils.py`, `lump_sum_tax_utils.py` | Move and align with the supported HRMS API; remove duplicated upstream logic. |
| `utils/emp501_utils.py` and `utils/sars_xml_generator.py` | Move reconciliation and export logic; do not label non-BRS files as SARS filing files. |
| `utils/fringe_benefit_utils.py`, `travel_allowance_utils.py`, `termination_utils.py` | Move and complete the currently partial legal treatments. |
| `integrations/eft_generator.py` and payroll payment code | Move into versioned, bank-specific payment adapters with maker/checker controls. |
| Payroll client scripts under `public/js/` | Move employee/benefit/payroll/salary scripts; remove aggressive DOM section hiding. |
| Payroll CSS and Salary Slip/IRP5 templates | Move; share escaped components and retain statutory snapshots. |
| `config/sa_payroll.py`, payroll workspace/onboarding/tours/sidebar | Move with corrected routes and permissions. |
| Payroll portions of setup, Custom Fields, Property Setters and statutory JSON | Convert to payroll-owned fixtures, core rate records and versioned data patches. |
| Payroll practitioner pages and payroll tests | Move to this repo and register pages with core. |

### Custom-field ownership

Payroll becomes the sole owner of:

- Employee tax number, identity/passport, tax status, residency, directive and ETI eligibility data.
- Employee payroll banking, payment method and tax-certificate demographic/address snapshot inputs.
- Payroll Settings South African defaults and supported calculation options.
- Salary Component SARS code, PAYE/UIF/SDL/COIDA applicability, treatment, inclusion and reimbursement metadata.
- Salary Structure/Assignment annual bonus and payroll classification fields.
- Salary Slip statutory bases, PAYE adjustment, ETI, retirement excess and company-contribution fields.
- Payroll Entry payment-routing and employee bank-entry status fields.
- Company PAYE/UIF/SDL registration references and payroll filing contacts.

`Salary Component.za_coida_applicable` remains payroll-owned because it is part of salary-component classification;
workplace receives the persisted COIDA basis through a supported service. Leave Type and Employee Separation BCEA
entitlement fields are workplace-owned. Payroll owns settlement calculations and journals that consume an approved
termination/leave payload.

## Existing payroll model retained and hardened

Move all existing `sa_payroll` DocTypes, including:

- SARS Payroll Code, Tax Directive, Tax Rebates and Medical Tax Credit, ETI and travel-rate records;
- Employee Private Benefit/Type and fringe-benefit subtype records;
- EMP201 Submission, EMP501 Reconciliation/references and IRP5 Certificate child tables;
- Employee ETI Log, Payroll Payment Batch, UIF U19 Declaration;
- final settlement, leave encashment, retirement, bursary, cellphone, vehicle, housing and loan benefit records;
- Company Contribution and supporting child tables.

Required model changes:

- Move common statutory rate values to approved core rate packs and retain domain-specific rule tables here.
- Add uniqueness for company/employee/period/certificate/reconciliation where duplicate statutory records are
  invalid; never rely on check-then-insert alone.
- Add `amended_from`, immutable submitted snapshots and no-copy certificate identifiers where required.
- Separate generated, utilised and carried-forward ETI explicitly.
- Store calculation trace records containing inputs, rule/source versions, intermediate bases and rounded outputs.
- Scope settings and statutory masters by Company where multi-company differences are possible.

## Statutory payroll capability to complete

### Deterministic calculation pipeline

For every Salary Slip, calculate in this order:

1. Reuse HRMS structure, recurring Additional Salary, overwrite, benefit-ledger, loan, exchange-rate and rounding
   behaviour.
2. Classify components from explicit metadata; missing required SARS codes/treatments fail readiness checks.
3. Persist PAYE, UIF, SDL, COIDA, remuneration and ETI bases separately.
4. Compute retirement deductions, fringe benefits, travel inclusion and medical credits.
5. Compute PAYE using the slip period and approved tax-year source, including full-tax additional earnings.
6. Compute UIF/SDL using the slip end date and payroll frequency.
7. Compute ETI eligibility, gross-up/pro-rating, generated/utilised/carry-forward values and employer PAYE cap.
8. Call HRMS net-pay logic so loans, exchange rates and rounding remain correct.
9. Persist a readable calculation trace and reconcile displayed breakup fields to posted deductions.

No statutory helper may default to `today()` when a transaction date exists, guess a missing row, infer treatment
from component-name substrings, or return zero for missing mandatory configuration.

### PAYE and annual reconciliation

Implement approved annualisation, rebates, medical credits, retirement limits, variable remuneration, directives,
bonuses, lump sums, prior employment/opening balances, mid-year joins/leavers and multiple payroll frequencies.
Guard zero remaining periods and support amendments without recomputing historical documents against current
rates.

Add golden test vectors at every bracket boundary and for age/rebate transitions, leap years, full-tax bonuses,
retirement caps and final-pay scenarios. Statutory values must be independently checked against the applicable
SARS employer guide and BRS version before release.

### ETI

Complete all eligibility/exclusion rules, actual-hours handling, 160-hour remuneration gross-up and incentive
pro-rating, minimum-wage tests, qualifying-month count, first/second 12-month tables, PAYE liability cap,
carry-forward and reconciliation-month treatment. Use submitted ETI logs to establish claimed qualifying months;
calendar months since joining are insufficient.

ETI generated, utilised and carried forward must reconcile employee-to-EMP201-to-EMP501 without treating them as
the same value.

### Fringe benefits and allowances

Replace disconnected subtype DocTypes with one effective-dated benefit service that adds the correct taxable and
reporting component to the Salary Slip. Cover, with source-backed rules and practitioner-approved examples:

- employer-provided vehicles, including determined value, maintenance plan and PAYE inclusion;
- housing/accommodation formula and abatements;
- low/no-interest loans using the date-effective official rate and outstanding balance;
- employer medical contributions and medical credits;
- bursaries, cellphone/data, fuel cards and private expenses;
- reimbursive travel and travel allowances;
- retirement and insurance contributions.

Unsupported benefit types must be visibly `Preview` and cannot silently remain Active without affecting payroll.

### Termination and final settlement

Create a versioned contract from workplace to payroll containing termination reason, service dates, approved leave
units/rate, notice/severance entitlement and directive details. Payroll calculates normal remuneration, leave
encashment, notice, severance/lump sums, deductions and tax through the standard Salary Slip/Additional Salary
path. Remove fixed-percentage leave tax and all `ignore_permissions` document fabrication.

### UIF U19 and employer declarations

Rebuild U19 from the official form/data requirements: scoped employment period, hours, remuneration, reason,
contributions and employer/employee particulars. Do not report lifetime UIF totals.

EMP201 must reconcile PAYE, SDL, UIF and ETI to submitted Salary Slips and GL/payment entries. EMP501 must compare
EMP201 totals to submitted IRP5/IT3(a) certificates and block unexplained differences. Draft/cancelled records do
not count as coverage.

### IRP5/IT3(a) and SARS BRS

Implement a versioned BRS exporter with exhaustive code/category treatment, fixed record layouts, validation
rules, control totals and import-result evidence. Generic CSV/XML files must not be called filing files. Correctly
separate taxable, non-taxable, reference, deduction, tax-credit and employees-tax totals; include directives and
both applicable UIF portions according to the approved BRS interpretation.

Certificate generation must be queued, cached/batched, permission-gated and deterministic. Period inclusion rules
must be consistent across Salary Slip, EMP201, EMP501 and IRP5.

### Payroll payments

Create a bank-adapter interface with explicit bank/file/version identifiers, beneficiary validation, amount and
control totals, duplicate-payment protection, maker/checker approval, file hash and bank response evidence.
Generic EFT output is a controlled payment instruction, not proof of payment. Payroll Entry must use a real
doctype-class override/service hook rather than a short-lived migrate-time monkey patch.

## Defects to resolve during extraction

- Hide only `max_benefits`; never hide a form section containing timesheet/hourly fields.
- Restore recurring Additional Salary, overwrite alias, flexible-benefit ledger, loans, exchange rates and rounding.
- Add or remove every referenced custom field; CI must detect code/schema drift.
- Include full-tax additional earnings and update both deduction rows and tax-breakup state.
- Correct medical-credit eligibility/effective dates and part-year membership.
- Correct ETI gross-up, qualifying months, minimum wage and PAYE cap.
- Resolve UIF/SDL/rates by Salary Slip period and fail loudly on missing packs.
- Remove arbitrary rebate/credit fallback rows and component-name classification.
- Replace erroneous vehicle/housing/loan benefit formulas.
- Prevent migrations from rewriting submitted Salary Detail or submitted statutory masters.
- Restore Payroll Entry/Salary Slip superclass lifecycle validation.
- Correct EMP201 fiscal-period resolution, IRP5 period selection, reconciliation and permissions.
- Fix U19 scoping, payroll reports, print escaping and duplicated templates.
- Gate every whitelisted read/write and preserve traceback logging.

## Public contracts

Payroll exposes versioned, permission-aware services:

- `get_statutory_bases(salary_slip)` including persisted COIDA basis;
- `get_employee_remuneration(company, employee, from_date, to_date, basis)`;
- `get_payroll_reconciliation(company, period)`;
- `create_termination_settlement(approved_workplace_payload)`;
- `get_payroll_readiness(company, period)`.

Consumers must not query Salary Detail or payroll child tables directly when a service exists. Events include
`payroll_slip_submitted`, `payroll_slip_cancelled`, `employer_declaration_approved` and `payment_batch_completed`,
with versioned payloads and no unnecessary personal data.

## Migration sequence

1. Freeze a checksum inventory of payroll DocTypes, fields, hooks, source records, submitted slips/certificates and
   monetary control totals.
2. Install core/payroll beside `za_local`; do not activate duplicate overrides.
3. Import statutory sources/rates and fail readiness until practitioner approval is present.
4. Transfer DocType module and Custom Field ownership in place. Create missing fields through versioned patches.
5. Backfill statutory bases/calculation traces only for drafts or into separate audit records; never alter submitted
   Salary Detail snapshots.
6. Run shadow calculations over representative historical payrolls and produce per-slip/per-component differences.
7. Resolve every difference as defect, intentional rule correction or legacy exception with practitioner approval.
8. Enable services and hooks one lifecycle at a time behind feature flags.
9. Run parallel payroll for at least two monthly cycles plus weekly/fortnightly and year-end scenarios.
10. Cut over declarations, certificates and payments only after payroll totals, GL, bank controls and prior filings
    reconcile.
11. Retain deprecated Python/API forwarders for one major version; remove old owners after two release cycles.

Rollback re-enables old hooks at a release boundary. It must not mix engines within one Payroll Entry or delete new
audit/evidence records.

## Test and assurance plan

### Automated

- Fresh install, dependency order, repeated migrate and populated upgrade tests.
- Real DocType insert/save/submit/cancel/amend lifecycle tests, not controller methods on unsaved mocks only.
- Golden PAYE/UIF/SDL/ETI vectors across three tax years and every boundary/effective-date transition.
- Monthly, weekly, fortnightly, daily and off-cycle payrolls.
- Joining, leaving, unpaid leave, recurring/overwrite additional pay, loans and multi-currency cases.
- Every fringe benefit, travel, retirement and medical-credit treatment.
- EMP201/EMP501/IRP5/U19 reconciliation, BRS validation and amendments.
- Permission denial, POPIA field-level access, cross-company isolation and export redaction.
- Payment adapter control totals, duplicates, rejection and resubmission.
- Query-count and queue tests for 1,000+ employees.
- Backup/restore followed by monetary and certificate checksum comparison.

### End-to-end payroll scenarios

- Salaried employee through assignment, monthly payroll, GL, payment, EMP201 and IRP5.
- Timesheet/hourly employee with visible component/rate fields and correct frequency.
- Commission/bonus with full tax and retirement/medical interactions.
- ETI employee across qualifying month 12/13/24/25, part-time hours and PAYE cap.
- Employee with vehicle, medical, retirement, travel and loan benefits.
- Mid-year joiner and leaver with leave, notice, severance and directive.
- Cancel/amend/re-run without duplication.
- Multi-company and restricted payroll-user access.

### Sign-off

Require independent payroll-practitioner approval of statutory vectors and BRS mappings, HR/payroll operational
approval of workflows, finance approval of GL/payment reconciliation, bank file validation against bank test tools,
and engineering/security approval of migration, performance and permissions.

## Documentation deliverables

- Payroll implementation and company-readiness guide.
- Component/SARS-code classification matrix.
- PAYE, UIF, SDL and ETI calculation manuals with worked examples.
- Benefit, allowance, retirement and medical-credit handbook.
- Payroll run, exception, amendment, final settlement and payment runbooks.
- EMP201, EMP501, IRP5/IT3(a), U19 and directive practitioner guides.
- BRS/bank adapter version support matrix and controlled-manual disclaimers.
- Migration, parallel-run, rollback and troubleshooting guides.

CI must reject undocumented Production features, unreferenced statutory values, broken guide links, schema/code
field drift and mismatched examples.

## Exit criteria

- Every payroll field, hook, DocType, report and calculation has one owner.
- Representative payrolls reconcile gross-to-net, GL, payment, EMP201, EMP501 and certificates with zero unexplained
  differences.
- Historical and amended calculations are deterministic and source-backed.
- All critical/high audit findings are closed with regression tests.
- Fresh install, populated upgrade, repeated migrate, backup and restore pass.
- Performance targets pass at production workforce scale.
- Payroll practitioner, HR operations, finance, security and technical sign-offs are recorded.
