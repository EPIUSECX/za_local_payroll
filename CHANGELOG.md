# Changelog

## Unreleased

- Extracted and hardened PAYE, UIF, SDL, ETI, benefits, employer declarations,
  certificates and payroll-payment workflows from the legacy monolith.
- Corrected Salary Structure field visibility, recurring/overwrite handling,
  statutory totals, rate dating, permissions and setup integrity.
- Added conservative defaults for blank PAYE, UIF, SDL and COIDA component links
  so calculations, reports and salary-slip statutory summaries use one mapping.
- Added fresh-site statutory masters, deterministic E2E payroll controls,
  federated guides and Frappe v16 CI.
