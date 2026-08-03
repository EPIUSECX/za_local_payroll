# Changelog

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
