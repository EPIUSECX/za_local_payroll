# SA Localisation Payroll Migration and Cutover Plan

## Status and purpose

The payroll implementation has been extracted from the legacy `za_local` app
into `za_local_payroll`, with shared source governance supplied by
`za_local_core`. The extracted application has automated and synthetic
end-to-end evidence, but a particular employer is not production-approved until
the human gates in this plan have been completed.

This document governs transfer from the monolith. It is not permission to run
both payroll engines in parallel on the same live Payroll Entry.

## Ownership after migration

`za_local_payroll` owns:

- SA employee tax, identity, ETI and payroll-banking extensions;
- Salary Component SARS code and PAYE/UIF/SDL/COIDA classifications;
- Salary Structure and Assignment payroll fields;
- Salary Slip statutory bases, company contributions and calculation state;
- PAYE, UIF, SDL, ETI, retirement, medical-credit and supported fringe-benefit
  calculations;
- EMP201, IRP5/IT3(a), EMP501, directives, U19 and final-settlement records;
- Payroll Payment Batch and its supported FNB OBE CSV adapter; and
- payroll workspaces, print formats, reports, tests and practitioner pages.

`za_local_core` owns common statutory-source evidence, shared effective-dated
scalar rate packs, company compliance profiles, filing evidence and the
federated guide. Workplace and finance applications consume payroll results
through their own bounded integrations; they must not activate legacy payroll
controllers.

Existing DocType names and tables are intentionally retained. Migration changes
application/module ownership rather than recreating submitted statutory records.

## Important behavioural corrections

The extracted app intentionally differs from defective legacy behaviour:

- only `max_benefits` is hidden; the section containing
  `salary_slip_based_on_timesheet`, `payroll_frequency`, `salary_component` and
  `hour_rate` remains visible;
- HRMS remains authoritative for recurring, disabled and overwrite Additional
  Salary selection;
- full-tax additional earnings are retained in PAYE, and HRMS net-pay logic
  retains loans, exchange rates and rounding;
- UIF and SDL resolve against the Salary Slip period and explicit component
  classifications;
- ETI distinguishes generated, available, utilised and carried-forward amounts;
- medical credits require a positive, date-effective membership/contribution
  record and use its dependant count;
- supported fringe benefits become non-cash taxable Salary Slip rows; and
- EMP201, certificates and EMP501 are internal controlled working papers, not
  SARS BRS submission files.

These corrections can produce legitimate differences from legacy payroll.
Every difference must be classified and approved; it must not be hidden by
altering submitted historical Salary Detail rows.

## Pre-migration inventory

Before installing the extracted apps, record and checksum:

1. installed app versions and framework commits;
2. payroll DocTypes, Custom Fields, Property Setters, hooks and scheduled jobs;
3. Companies, Payroll Settings, components, SARS mappings, slabs, rebates,
   benefits and rate/source records;
4. submitted Salary Slips, Payroll Entries, Additional Salaries, declarations,
   certificates, directives and payment batches;
5. employee, company and period counts plus payroll, statutory, GL and payment
   control totals; and
6. encrypted database and private/public file backups with a tested decryption
   key and restore location.

Do not put employee or banking data in source control or a public issue.

## Staged migration procedure

1. Restore a representative encrypted backup to an isolated staging site.
2. Install `za_local_core` and `za_local_payroll` while retaining `za_local` only
   as a dormant migration source. Confirm duplicate hooks are suppressed.
3. Run `bench --site <site> migrate` twice. Review patch logs and verify that the
   second run is idempotent.
4. Verify DocType/module ownership and all mandatory custom fields. Do not rewrite
   submitted Salary Detail snapshots.
5. Configure and approve statutory sources and rate records for every payroll
   date under test. Verify Income Tax Slabs, rebates/medical credits and packaged
   structured rules separately.
6. Run representative historical calculations without submitting replacements.
   Compare every earning, deduction, company contribution, base, tax, net pay,
   GL amount and certificate total.
7. Record each difference as a corrected defect, approved statutory change,
   configuration correction or unresolved blocker.
8. Execute the scenarios and reconciliations in [TESTING.md](TESTING.md).
9. Obtain practitioner, payroll, finance, security and bank approvals.
10. Rehearse rollback, then schedule the live cutover between payroll cycles.

## Parallel-run and cutover gates

At minimum, complete two representative monthly parallel cycles. Also exercise
every frequency actually used by the employer, a timesheet/hourly employee,
recurring and overwrite Additional Salary, a full-tax bonus, ETI, medical and
retirement cases, supported fringe benefits, a joiner/leaver and an amendment.

The cutover record must show:

- gross-to-net and per-component agreement or approved differences;
- employee and employer UIF, SDL, PAYE and ETI generated/utilised reconciliation;
- payroll and employer-contribution GL agreement;
- Payroll Payment Batch source hash/control total and FNB test acceptance;
- submitted EMP201-to-certificate internal reconciliation;
- manual tie-out of EMP201 declarations and actual SARS payments to the SARS
  statement/receipts;
- certificate validation against the current PAYE BRS and the selected external
  eFiling/e@syFile process; and
- permissions, private-file access, backup and restore evidence.

No automated result replaces the employer's decision about ETI eligibility,
benefit valuation, directive treatment, fund classification or employee facts.

## External filing and payment boundary

The app does not produce a SARS PAYE BRS import file and does not submit EMP201,
IRP5/IT3(a) or EMP501 directly. The internal reconciliation covers submitted
EMP201 records and submitted certificates; the third external leg—amounts paid to
SARS—must be evidenced and reconciled manually against eFiling/e@syFile and SARS
statements.

The FNB OBE CSV is a payment instruction, not proof of payment. The application
does not enforce independent maker/checker separation. Use bank-portal dual
authorisation, retain the accepted bank response and reconcile the bank statement.

## Rollback and legacy retirement

Rollback is performed at a release boundary from the tested encrypted backup. Do
not mix old and new engines inside one Payroll Entry and do not delete new audit,
source or evidence records.

Archive the old `za_local` repository only after:

- the restored-backup and rollback rehearsals pass;
- production inventory/control totals are preserved;
- all parallel-run and human gates are signed;
- no site still imports, installs or schedules `za_local`; and
- an immutable source tag and migration backup remain accessible under the
  organisation's retention policy.

Until then, keep the legacy repository read-only rather than deleting it.
