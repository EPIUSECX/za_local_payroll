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

<!-- za-local-coverage-matrix:start -->
## South African compliance coverage

This matrix is the same in every package of the suite. It shows what each package
covers, how far the app goes, and what stays outside it. Read the live values in
the Desk under **SA Overview → Feature Readiness**.

| Package | What it adds |
| --- | --- |
| `za_local_core` | VAT, tax invoices, VAT201, and the shared governance foundation: statutory sources, rate packs, filings, POPIA and PAIA registers |
| `za_local_payroll` | Payroll and statutory payroll returns, BCEA leave and termination, Employment Equity, skills development and COIDA |
| `za_local_bma` | Recruitment, employee lifecycle and Payroll Operations around the payroll engine |

**Reading the matrix**

| Mark | Meaning |
| --- | --- |
| Preview | Implemented and tested. A practitioner must sign off client-specific treatment before production use |
| Controlled Manual | The app prepares, reconciles and approves. The filing, payment or decision happens outside the app, and a person records the receipt |
| Controlled Integration | A flow exists, but every endpoint, mapping and credential needs separate approval |
| Data only | Reference records the app stores or uses. It does not calculate or decide |
| Extends | Adds controls around a feature that another package owns |
| — | Not part of this package |

No capability ships as Production. A status describes the software's readiness, not
legal certification. Rates are only as current as the approved rate packs.

### Payroll tax and statutory returns

| Obligation | core | payroll | bma | Stays outside the app |
| --- | --- | --- | --- | --- |
| PAYE (Income Tax Act, Fourth Schedule): cumulative year-to-date method, age rebates, medical credits, retirement cap, annual payments such as bonuses | — | Preview | Extends: corrections, off-cycle runs, back pay | Annual approval of rates; PAYE is declared through EMP201 |
| UIF contributions | — | Preview | Preview: UIF declaration data | Declarations and payments to the Fund |
| Skills Development Levy | — | Preview | — | Payment through EMP201 |
| Employment Tax Incentive | — | Preview | — | Claim through EMP201 |
| Retirement funds and medical scheme credits | — | Preview | — | Fund returns |
| Fringe benefits (Seventh Schedule): company car, accommodation, low-interest loan | — | Preview | — | Other benefits need practitioner evidence for valuation |
| Tax directives, lump sums and severance tax | — | Preview | Extends: termination pay waits for the directive | Obtaining the directive from SARS |
| Travel allowance, subsistence and business trips | — | Preview | — | Practitioner review of reimbursive rates |
| EMP201 monthly declaration | — | Controlled Manual | Extends: period locks after EMP201 | Submission and payment on SARS eFiling |
| IRP5 / IT3(a) and EMP501 reconciliation | — | Controlled Manual | Extends: Year-End Readiness report | No SARS BRS import file and no e@syFile submission |
| Payroll bank files | — | Controlled Manual: FNB Online Banking CSV | Controlled Manual: further bank layouts, split pay | Bank acceptance test and portal authorisation |
| Deduction orders: maintenance, garnishees, staff loans | — | — | Preview | Court orders, caps and consent are the client's decision |
| Mid-year take-on and parallel runs | — | — | Controlled Manual | Review of each source export |
| Leave liability, bonus accruals, cost allocation | — | — | Preview | Valuation basis agreed with the client and auditor |

### Labour and workplace

| Obligation | core | payroll | bma | Stays outside the app |
| --- | --- | --- | --- | --- |
| BCEA leave: annual, sick (36-month cycle), family responsibility, maternity, parental, adoption | — | Preview: Leave Types, draft policies, cycle assignment, sick-leave allocator | — | Part-time and variable hours, collective agreements, shared parental-leave pool |
| BCEA termination: notice, severance, leave payout | — | Preview | Controlled Manual: resignation notice is the greater of contract and BCEA notice | Hours-of-work rules, earnings-threshold effects, case law |
| Certificate of Service | — | — | Controlled Manual | Legal review of wording |
| Sectoral minimum wages and bargaining councils | Data only: rate pack | Data only | — | Council agreements and determinations |
| Employment Equity (EEA) | — | Controlled Manual: working papers, not certified EEA forms | Preview: voluntary EE declaration, applicant EE mix | Nothing is filed with the Department |
| Skills development: WSP, ATR, SETA records | — | Controlled Manual | — | SETA portal, grants, B-BBEE scoring |
| COIDA Return of Earnings | — | Controlled Manual | — | eCOID submission and assessment response |
| Workplace injury and OID claims | — | Preview | — | Choosing the applicable report, deadline and disease process |

### VAT and corporate compliance

| Obligation | core | payroll | bma | Stays outside the app |
| --- | --- | --- | --- | --- |
| VAT registration, supply classification, tax-invoice controls | Preview | — | — | Company-specific supply treatment |
| Tax invoices, credit and debit notes | Preview | — | — | Practitioner sign-off |
| VAT201 return | Controlled Manual | — | — | Submission on SARS eFiling |
| Specialist VAT: mixed supplies, imported services, customs, second-hand goods, fixed property, bad debts, gold, diesel refunds, payments basis | Not implemented | — | — | Practitioner handling |
| Corporate and provisional tax | Catalogue entry only | — | — | Everything |
| CIPC annual returns and beneficial ownership | Controlled Manual | — | — | The portal process |

### Privacy, governance and people lifecycle

| Obligation | core | payroll | bma | Stays outside the app |
| --- | --- | --- | --- | --- |
| Statutory sources and effective-dated rate packs with independent approval | Controlled Manual | Uses it | — | Obtaining and reviewing the publications |
| Compliance obligations, calendar, filings and submission receipts | Controlled Manual | Uses it for EMP201 and EMP501 | — | The authority's acknowledgement |
| POPIA and PAIA registers | Controlled Manual | Restricted access to health and EE data | Preview: candidate consent, retention schedule, de-identification (off by default) | Regulator submissions and incident-notification decisions |
| Recruitment, candidate portal, SA ID and tax-number checks, work permits | — | — | Preview | Client approval matrix, notice wording, POPIA review |
| Preboarding and payroll readiness (identity, bank, tax, UIF) | — | Employee SA fields | Preview | First-payslip reconciliation |
| Offboarding, clearance and access removal | — | — | Controlled Manual | External-system revocation |
| Sage 300 People handoff | — | — | Controlled Integration | Each client endpoint and credential |

### Not covered by any package

SARS BRS and e@syFile transmission, eFiling submission, eCOID and CF-2A transmission,
certified Employment Equity forms and filing, SETA portal submission and grant
eligibility, B-BBEE scoring, corporate and provisional tax, the specialist VAT
scenarios above, UIF benefit claims, bargaining-council determinations, and tracking
of the shared maternity and parental-leave pool.

*Reviewed 8 October 2026 against `za_local_core` 2.0.0, `za_local_payroll` 2.1.0 and
`za_local_bma` 0.1.0. Update this section in all three READMEs together.*
<!-- za-local-coverage-matrix:end -->

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
