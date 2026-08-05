<div align="center">

<img src="za_local_payroll/public/images/za_local_payroll_logo.svg" height="128" alt="SA Localisation Payroll and HR logo">

# SA Localisation Payroll &amp; HR

**South African payroll, SARS employer reporting, BCEA, Employment Equity, skills development and COIDA for Frappe HR**

[![CI](https://github.com/EPIUSECX/za_local_payroll/actions/workflows/ci.yml/badge.svg)](https://github.com/EPIUSECX/za_local_payroll/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](license.txt)
[![Frappe v16](https://img.shields.io/badge/frappe-v16-0089ff.svg)](https://frappeframework.com)

</div>

## What this app is

SA Localisation Payroll &amp; HR turns Frappe HR into a South African payroll and
HR system. It adds PAYE with rebates and medical credits, UIF, SDL, the
Employment Tax Incentive, fringe benefits, and the employer reporting SARS
expects — EMP201, IRP5/IT3(a) and EMP501.

It also covers what an employer owes to people and to the Department of
Employment and Labour rather than to SARS: basic conditions of employment,
employment equity, skills development, workplace injuries and the Compensation
Fund. Those modules — SA Labour and SA COIDA — were a separate app until 1.x and
are part of this one from 2.0.0, because they read the same employee and
remuneration data and are never installed without payroll.

It **extends** HRMS payroll; it does not replace it. Salary Structure, Additional
Salary, Salary Slip and Payroll Entry remain the documents your team already
knows, and HRMS keeps ownership of the calculation and persistence path.

## Why it exists

South African payroll is unforgiving. PAYE is annualised and re-based every
period, ETI has eligibility rules that depend on hours actually worked, and the
figures on an IRP5 must reconcile to the EMP201s that were declared months
earlier. Getting any of it quietly wrong produces an under-declaration that
surfaces at year-end, with penalties.

This app keeps the statutory logic inside the HRMS calculation path rather than
beside it, sources every rate from an approved and date-effective record, and
refuses to run payroll at all when mandatory statutory masters are missing — a
loud failure instead of a silent zero.

## Key features

- **PAYE** — annualised calculation with age-based rebates, medical scheme fees
  and additional medical expenses tax credits, retirement-fund deduction caps,
  travel-allowance inclusion percentages, and full-tax treatment for additional
  earnings such as a 13th cheque.
- **UIF and SDL** — contribution bases derived from explicit per-component
  applicability flags, with the statutory ceiling applied per employee.
- **Employment Tax Incentive** — eligibility, the minimum-wage test, 160-hour
  gross-up and pro-rata, qualifying months, generated versus utilised ETI, the
  PAYE-liability cap and carry-forward, with a per-employee audit log.
- **Fringe benefits** — company car, residential accommodation and low-interest
  loans as dated, submittable records that feed the slip as taxable rows.
- **Payroll frequencies** — monthly, plus timesheet and hourly structures, with
  duplicate-period protection per employee.
- **Employer contributions** — UIF employer, SDL and COIDA-applicable components
  posted as a separate, idempotent accrual journal.
- **EMP201** — monthly working paper with a database-enforced unique active
  period key, so a duplicate declaration cannot be created by a race.
- **IRP5 / IT3(a) and EMP501** — certificates and reconciliation built from
  submitted slips, with SARS payroll codes, directive handling and PDF output.
- **Payroll payment batch** — FNB Online Banking Enterprise CSV, generated from
  an immutable snapshot with a source hash and control total, attached privately
  and regenerated idempotently.
- **BCEA leave and termination** — opt-in per Leave Type, with sick-leave medical
  evidence rules, the three-day family-responsibility cap, gender-specific leave,
  service-based notice, operational-requirements severance and a governed
  annual-leave payout feeding final settlement.
- **Employment Equity** — workforce profile, remuneration-proxy, target-plan and
  movement working papers, with small-cell privacy controls and permission-aware
  company filtering.
- **Skills development** — SETA, Skills Development Facilitator, OFO occupation,
  training provider, Workplace Skills Plan, Annual Training Report and completion
  records.
- **Business trips** — date-based allowances, mileage at a governed rate,
  accommodation and expense totals, with optional draft Expense Claim creation.
- **Workplace injuries and OID claims** — restricted incident records, draft leave
  and claim creation, one-way claim status transitions, post-submission medical
  reports and external receipt evidence.
- **COIDA** — March-to-February Return of Earnings built from the payroll COIDA
  earnings basis, with per-employee caps, governed rates and minimums, an
  immutable source snapshot and stale-source detection.

## Country scope

South African payroll and BCEA rules apply only to companies whose country is
South Africa. On a multi-country site, every other company keeps stock HRMS
behaviour — including the standard HRMS bank entry — and is never blocked by South
African statutory setup it cannot complete. BCEA leave controls are additionally
opt-in per Leave Type through the governed `za_bcea_compliant` flag, so an
ungoverned leave type is never subject to BCEA rules.

## Privacy

Workplace injuries and OID claims contain health information, and Employment
Equity records contain race, gender and disability data. Both are
special-category personal information under POPIA. Review the role and User
Permission scoping on these DocTypes for your organisation before go-live — a
default that suits one employer may be too broad for another. Governance
registers live in `za_local_core`.

## Capability status

| Capability | Status | What that means |
| --- | --- | --- |
| Payroll calculation (PAYE, UIF, SDL, ETI) | Preview | Implemented and tested against 2026/27 controls; annual rate approval and parallel payroll are still required |
| Fringe benefits | Preview | Company car, accommodation and low-interest loans only; valuations need practitioner sign-off |
| EMP201 working paper | Controlled Manual | Prepared in-app, declared and paid externally |
| IRP5/IT3(a) and EMP501 | Controlled Manual | Certificates and reconciliation are produced; **no SARS BRS import file or e@syFile submission is generated** |
| Payroll bank output | Controlled Manual | FNB OBE CSV only; bank-portal dual authorisation and bank acceptance testing are mandatory |
| BCEA leave and termination | Preview | Decision support, not a complete entitlement, hours-of-work, collective-agreement or case-law engine |
| Employment Equity working papers | Controlled Manual | Report names are retained for compatibility and are **not** certified EEA forms; nothing is filed with the Department |
| WSP / ATR working papers | Controlled Manual | SETA-specific templates, grant eligibility, portal submission and B-BBEE scoring stay external |
| COIDA Return of Earnings | Controlled Manual | Submit is internal approval only; no CF-2A/W.As.8 transmission to eCOID, and no assessment response is captured |
| Workplace injury and OID claim | Preview | The seven-day tracker is operational support, not a determination of the applicable report, deadline or occupational-disease process |

Read the live values in the Desk under **SA Overview → Feature Readiness**.

### Where the rates come from

Three governed layers, in order:

1. submitted `za_local_core` rate packs for shared scalar values;
2. payroll-owned annual packs for ETI, lump-sum and fringe-benefit rule tables;
3. HRMS Income Tax Slabs plus the payroll rebate and medical-credit master.

If no submitted core pack applies, packaged scalar values may be used as a
technical fallback. **That fallback is not practitioner approval.**

## Under the hood

- [Frappe Framework](https://frappeframework.com), [ERPNext](https://erpnext.com)
  and [Frappe HR](https://frappe.io/hr).
- [`za_local_core`](https://github.com/EPIUSECX/za_local_core) — statutory sources,
  approved rate packs, filings and submission receipts.

Existing SA Payroll DocType names and tables are retained, so data from the legacy
`za_local` app can be transferred in place under the controlled process in
[MIGRATION_PLAN.md](MIGRATION_PLAN.md).

## Production setup

Install after ERPNext, HRMS and `za_local_core`:

```bash
bench get-app za_local_core https://github.com/EPIUSECX/za_local_core.git --branch main
bench get-app za_local_payroll https://github.com/EPIUSECX/za_local_payroll.git --branch main
bench --site <your-site> install-app za_local_core
bench --site <your-site> install-app za_local_payroll
bench --site <your-site> migrate
```

Creating a South African Company seeds its Payroll Periods, Income Tax Slabs,
rebates and medical credits automatically. Before the first run, confirm salary
component mappings, SARS payroll codes, employee statutory data and opening
balances.

**Do not run a first live payroll without a parallel run.** See
[docs/sa_payroll_configuration_and_testing.md](docs/sa_payroll_configuration_and_testing.md).

## Development setup

```bash
bench --site <dev-site> set-config allow_tests true
bench --site <dev-site> run-tests --app za_local_payroll
uvx ruff check apps/za_local_payroll
uvx ruff format --check apps/za_local_payroll
```

Lifecycle and end-to-end tests create and submit payroll documents. Run them only
on a disposable site or an approved restored copy, never on a production payroll
site.

## Documentation

| Document | Purpose |
| --- | --- |
| [TESTING.md](TESTING.md) | How to verify a deployment |
| [docs/sa_payroll_configuration_and_testing.md](docs/sa_payroll_configuration_and_testing.md) | Configuration and parallel-run guidance |
| [docs/sa_payroll_compliance_remediation_2026_27.md](docs/sa_payroll_compliance_remediation_2026_27.md) | 2026/27 statutory alignment record |
| [docs/sa_labour_configuration_and_testing.md](docs/sa_labour_configuration_and_testing.md) | Labour, EE and skills setup and verification |
| [docs/sa_coida_configuration_and_testing.md](docs/sa_coida_configuration_and_testing.md) | COIDA setup and verification |
| [MIGRATION_PLAN.md](MIGRATION_PLAN.md) | What this app owns and how it was extracted |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [SECURITY.md](SECURITY.md) | Reporting a vulnerability |
| [SUPPORT.md](SUPPORT.md) | Getting help |

Practitioner and end-user pages are contributed to the federated guide published
by `za_local_core`. Release evidence and remaining gates live in that
repository's `VALIDATION_AND_SIGNOFF.md`.

## Filing and banking boundary

EMP201, IRP5/IT3(a) and EMP501 output is an internal **working paper**. This app
does not produce a SARS BRS import file and does not submit to eFiling or
e@syFile. Declaration, payment and submission are manual; capture the
acknowledgement as a core Submission Receipt.

The payment batch supports **FNB Online Banking Enterprise CSV only**. Other
banks are not implemented. Obtain written bank acceptance of the exact format and
control total before a first live payment run, and rely on the bank portal's own
dual authorisation — this app does not enforce maker/checker on the file itself.

## Uninstalling

`bench uninstall-app` removes this app's DocTypes and every schema customisation
it owns; Custom Fields, Property Setters, Print Formats and Workspaces all carry
an owning module. It also withdraws the guide pages this app published into Frappe
Wiki, which have no module for Frappe to reclaim them by, along with any guide
group left empty. Pages contributed by the other localisation apps stay.

Business and audit records are deliberately retained. Salary Components, Payroll
Periods, Income Tax Slabs, salary slips, certificates and filing evidence are a
company's payroll history, not app schema. Remove them only through a reviewed
data decision.

## Contributing

```bash
cd apps/za_local_payroll
pre-commit install
```

Ruff, ESLint, Prettier and pyupgrade run on commit. A change to a statutory value
must arrive with its source record, its effective dates and a test.

## License

MIT — see [license.txt](license.txt).
