# Security Policy

Payroll data includes identity numbers, tax references, remuneration, bank
details, medical/benefit facts, directives and certificates. Treat it as
confidential personal and financial information.

## Reporting a vulnerability

Report suspected vulnerabilities privately to the maintainers. Include the app
version, Frappe/ERPNext/HRMS commits, a sanitised reproduction and impact. Never
put production employee, tax, medical, bank, certificate, backup or filing data
in a public issue, pull request, screenshot or chat transcript.

## Required operating controls

- Grant payroll and statutory roles on least privilege and review them before
  every production release.
- Test low-privilege, cross-company and private-file denial explicitly.
- Store statutory-source evidence, generated payment files, filing evidence and
  backups as restricted private files with retention appropriate to the employer.
- Encrypt backups and protect encryption keys separately; test restore access.
- Rotate credentials and revoke exported files when an incident is suspected.
- Keep supported fixes on the pinned Frappe/ERPNext/HRMS v16 release line and
  reassess permissions after framework upgrades.

Whitelisted methods still enforce DocType and role permissions. `ignore_permissions`
is not an operating substitute for a user permission check.

## Payment and filing boundary

Payroll Payment Batch applies source-hash, control-total and duplicate-batch
controls. It does **not** enforce an independent maker/checker workflow. A person
other than the preparer must approve the batch in the bank portal, and the bank's
accepted/rejected response and statement reconciliation must be retained.

EMP201, IRP5/IT3(a) and EMP501 outputs are internal working papers. External SARS
filing, payment confirmation and BRS/e@syFile validation happen outside this app
and require controlled access and evidence. A generated PDF, CSV or submitted
internal record is not proof that SARS or a bank accepted it.
