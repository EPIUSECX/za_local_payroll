# Changelog

## 2.1.0 - 2026-08-05

Found by running a real 20-employee March 2023 payroll against a balanced parallel
register. Every input matched to the cent and PAYE landed exactly on the register's
figure, which is what made the three defects below visible rather than plausible.

### Added

- Statutory data for tax year 2023-2024, so a prior-year parallel run is possible.
  The app previously shipped 2024-2025 onward only and could not run an earlier
  period at all. Brackets, rebates, tax thresholds and medical tax credits are
  unchanged from 2024-2025; the travel, subsistence and COIDA figures are the
  2023/24 values.

### Fixed

- SDL and UIF ignored `za_sdl_applicable` and `za_uif_applicable` on any earning
  flagged `do_not_include_in_total`, because `get_statutory_earning_basis` skipped
  those rows before reading the flag. Taxable fringe benefits were therefore left
  out of the leviable amount, under-declaring the levy. The leviable amount is
  remuneration under the Fourth Schedule, and paragraph 1 of that Schedule includes
  the cash equivalent of Seventh Schedule taxable benefits, so the flag now decides
  alone. On the register above this understated SDL by R369.98.
- Company Car Benefit, Housing Fringe Benefit, Low Interest Loan Fringe Benefit and
  Other Fringe Benefit shipped as not UIF or SDL leviable despite being taxed at
  100%. They are remuneration and are now flagged accordingly. COIDA flags are left
  as shipped: the COID Act defines earnings separately and that needs its own ruling.
- An employee whose medical scheme is wholly employer-funded received no medical tax
  credit, because `get_medical_aid_credits` skipped any Employee Private Benefit with
  no private contribution. Section 6A read with paragraph 12A of the Seventh Schedule
  treats an employer contribution as a taxable benefit of the employee, so the credit
  is due regardless of who pays. An employer medical aid contribution on the slip now
  counts as membership evidence.
- A cancelled or deleted Salary Slip left its Employee ETI Log behind. The log keys
  on the slip name, Frappe reissues that name when a slip is re-created for the same
  employee and period, and the stale log then blocked slip creation, so a period
  could not be re-run without clearing logs by hand. Only a draft log is reused now,
  and a slip takes its log with it when deleted.
- `test_payroll_lifecycle_integration` hardcoded the Gender "Male", which fails on a
  site where the setup wizard never created the full Gender list. It uses the
  existing `ensure_gender` helper.

## 2.0.1 - 2026-08-03

- Documented the two-app suite: `za_local_finance` is retired and the SA VAT module
  ships inside `za_local_core` from 2.0.0.
- The Desk navigation fix for the SA Labour and SA COIDA workspaces lands in
  `za_local_core` 2.0.0; both apps must be updated together.

## 2.0.0 - 2026-08-03

### Absorbed SA Localisation Workplace

The SA Labour and SA COIDA modules moved into this app from the separate
`za_local_workplace` app, which is retired. The suite is now three apps: core,
finance, and payroll and HR.

- BCEA leave and termination, Employment Equity, skills development (WSP/ATR),
  business trips, workplace injuries, OID claims and the COIDA Return of Earnings
  all ship here now. The app is titled **SA Localisation Payroll & HR**.
- Nothing was rewritten. Module names, DocType names, fieldnames and tables are
  unchanged, so no data is migrated or re-entered.
- `patches.v1_2.adopt_workplace_modules` re-points the two Module Def and
  Workspace records to this app and de-registers `za_local_workplace` using
  `remove_from_installed_apps`, never `remove_app` — an uninstall would have
  dropped every labour, injury, claim and COIDA record.
- Setup for the absorbed modules lives in `setup/workplace.py` and
  `setup/workplace_custom_fields.py`; both apps had defined `DEFAULT_PRINT_FORMATS`
  and a `setup/custom_fields.py`.
- The absorbed monthly Employment Equity and COIDA rate reminders now run from
  this app's existing `monthly` scheduler entry rather than a second one.
- `za_local_workplace_runtime_owner` is superseded by
  `za_local_payroll_runtime_owner` for the legacy side-by-side cutover gate.

### Upgrading from 1.x

Update this app and run `bench --site <site> migrate`. Do not run
`bench uninstall-app za_local_workplace`.

## 1.2.0 - 2026-08-03

- The guide pages this app publishes into Frappe Wiki are now withdrawn when the
  app is uninstalled. Neither Wiki DocType has a module field, so `remove_app`
  could not reclaim them and all 22 pages stayed live after the app was gone.
  Pages contributed by the other localisation apps are untouched.

## 1.1.0 - 2026-08-03

- Added workspace metrics: eight statutory number cards and four charts covering
  PAYE, UIF, SDL, ETI, net pay and certificate status.
- Surfaced the app's own features in the workspace. Nineteen DocTypes were
  previously unreachable, including the fringe-benefit set, Payroll Payment
  Batch, Tax Directive, UIF U19 Declaration and Employee Final Settlement.
- Removed a broken link to the legacy ZA Local Setup DocType and the
  India-specific Salary Payments via ECS report.

## 1.0.0 - 2026-08-02

- Gated every HRMS entry point on company country. Companies outside South
  Africa keep stock HRMS payroll, including the standard bank entry, and are
  no longer blocked by South African statutory setup they cannot complete.
- Tagged the app's Property Setters with their owning module, with a backfill
  patch, so uninstall no longer orphans them on core HRMS DocTypes.
- Added country-gating and uninstall-hygiene regression tests.
- Extracted PAYE, UIF, SDL, ETI, benefits, employer declarations,
  certificates and payroll-payment workflows from the legacy `za_local` app.
- Corrected Salary Structure visibility so `max_benefits` is hidden without
  hiding the timesheet frequency, Salary Component or hourly-rate fields.
- Restored upstream HRMS recurring and overwrite Additional Salary behaviour,
  flexible-benefit ledger tracking, loan repayment, exchange-rate and rounding
  handling.
- Corrected full-tax additional earnings, date-effective UIF/SDL, retirement
  limits, medical-credit membership periods, ETI gross-up/qualifying months and
  generated-versus-utilised ETI accounting.
- Connected supported company-car, housing and low-interest-loan fringe benefits
  to taxable non-cash Salary Slip rows while keeping them out of cash pay.
- Hardened EMP201, IRP5/IT3(a), EMP501 and Payroll Payment Batch permissions,
  snapshots, totals and duplicate controls.
- Removed or disabled generic exports that could be mistaken for a SARS BRS
  import file. Employer declarations remain controlled internal working papers;
  external filing and payment evidence must be captured through approved
  operational controls.
- Added fresh-site master data, deterministic synthetic end-to-end scenarios,
  federated practitioner guides and Frappe v16 CI.
- Corrected documentation to distinguish automated evidence from statutory,
  practitioner, bank and employer approval.

No changelog entry is a compliance certificate. Review [TESTING.md](TESTING.md)
and the release sign-off record before production use.
