# SA Localisation Payroll

South African payroll localisation for Frappe HRMS v16. The app extends the
upstream Salary Structure, Additional Salary, Salary Slip and Payroll Entry
workflows; it does not replace HRMS payroll.

Runtime dependencies are Frappe, ERPNext, HRMS and `za_local_core`. Existing
SA Payroll DocType names and database tables are retained so that data from the
legacy `za_local` app can be transferred in place under the controlled process
in [MIGRATION_PLAN.md](MIGRATION_PLAN.md).

## Supported application scope

| Area | Current application behaviour | Release boundary |
|---|---|---|
| Salary Structure | Hides only the unused `max_benefits` leaf field. Timesheet frequency, Salary Component and hourly-rate fields remain visible and editable. | Verify the form after every HRMS upgrade. |
| Additional Salary | Reuses HRMS recurring, disabled-record and overwrite semantics. SA code only partitions company contributions and preserves benefit-ledger bookkeeping. | Test recurring dates and overwrite replacement in every release. |
| PAYE, UIF and SDL | Uses dated payroll inputs, explicit component metadata and mandatory configuration. Full-tax additional earnings, loan repayments, exchange rates and HRMS rounding remain in the calculation path. | Annual rate and mapping approval is mandatory. |
| ETI | Calculates eligibility, minimum-wage tests, 160-hour gross-up/down, qualifying months, generated ETI, utilised ETI and carry-forward. | Employee facts and eligibility require employer/practitioner review. |
| Retirement and medical credits | Applies the configured retirement limit and date-effective medical membership/dependant data. | Fund classification and membership evidence require review. |
| Fringe benefits | Supports submitted company-car, housing and low-interest-loan detail records as non-cash taxable rows. | Other benefit types and all underlying valuations require practitioner sign-off. |
| EMP201, IRP5/IT3(a), EMP501 | Produces controlled internal working papers and reconciliation records from submitted payroll documents. | No SARS BRS file or direct electronic filing is produced. External filing and payment evidence remain controlled manual steps. |
| Payroll payment file | Supports the identified FNB Online Banking Enterprise CSV adapter through a submitted Payroll Payment Batch with a source hash and control total. | The app does not enforce independent maker/checker approval. Bank-portal dual authorisation and bank acceptance are mandatory. |

The statutory engine uses three governed data layers:

1. submitted `za_local_core` Payroll rate packs for shared scalar rates;
2. payroll-owned structured annual packs for ETI, lump-sum and fringe-benefit
   rule tables; and
3. HRMS Income Tax Slabs plus the payroll rebate/medical-credit master for PAYE.

If no submitted core pack applies, compatible packaged scalar values may be used
as a technical fallback. That fallback is not practitioner approval. Feature
readiness remains **Preview** until the official source, dated configuration and
parallel calculations have been signed off.

## Installation

```bash
bench get-app $ZA_LOCAL_CORE_REPO --branch main
bench --site $SITE_NAME install-app za_local_core
bench get-app $URL_OF_THIS_REPO --branch main
bench --site $SITE_NAME install-app za_local_payroll
bench --site $SITE_NAME migrate
```

Do not activate the legacy and extracted payroll engines together. While
`za_local` remains installed, duplicate payroll hooks are deliberately
suppressed; this coexistence is a migration aid, not a supported steady state.
Do not archive or remove the legacy repository until the inventory, restored
backup, rollback and parallel-run evidence in [MIGRATION_PLAN.md](MIGRATION_PLAN.md)
has been approved.

## Verification and operating documentation

- [Configuration and practitioner test guide](docs/sa_payroll_configuration_and_testing.md)
- [2026/27 remediation verification note](docs/sa_payroll_compliance_remediation_2026_27.md)
- [Test evidence and release gates](TESTING.md)
- [Security policy](SECURITY.md)
- [Support boundary](SUPPORT.md)

Practitioner and end-user Markdown pages are contributed to the federated guide
published by `za_local_core`. The cross-app release record, validation checklist
and cutover runbook in the core repository remain authoritative for a deployment.

## Safe local checks

```bash
python -m compileall -q apps/za_local_payroll/za_local_payroll
uvx ruff check apps/za_local_payroll/za_local_payroll
git diff --check
```

Lifecycle and end-to-end tests create and submit payroll documents. Run them only
on a disposable site or an approved restored copy, never on a production payroll
site.

## Uninstalling

`bench uninstall-app` removes this suite's DocTypes and every schema
customisation it owns: Custom Fields, Property Setters, Print Formats and
Workspaces all carry an owning module, and `za_local_core` additionally removes
the `ZA Compliance` roles, which Frappe cannot reclaim by module.

Business and audit records are deliberately retained. Salary Components,
Payroll Periods, Income Tax Slabs, approved statutory sources, rate packs,
filings and submission receipts are a company's payroll and compliance history,
not app schema. Remove them only through a reviewed data decision.

## License

MIT
