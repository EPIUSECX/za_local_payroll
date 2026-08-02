# 2026/27 Payroll Remediation Verification Note

This note covers 1 March 2026 to 28 February 2027. It is not a certificate of
statutory compliance and does not replace employer, practitioner, bank or legal
approval.

## Configured headline values

| Item | Configured value |
|---|---:|
| Primary / secondary / tertiary annual rebates | R17,820 / R9,765 / R3,249 |
| Under-65 / age-65 / age-75 tax thresholds | R99,000 / R153,250 / R171,300 |
| Medical scheme fees credit: main / first dependant / additional dependant, monthly | R376 / R376 / R254 |
| UIF monthly remuneration cap | R17,712 |
| UIF employee / employer rate | 1% / 1% |
| SDL employer rate | 1% |
| Reimbursive travel rate | R4.95/km |
| Retirement deduction limit | 27.5%, limited to R430,000 annually |
| COIDA annual earnings cap | R668,000 per employee |
| Employer-provided housing abatement | R99,000 |

Official-interest-rate entries are date-effective because the prescribed rate
can change during a tax year. Before production use, reconcile every value and
effective date to the applicable SARS guide, Gazette or Department of Employment
and Labour notice. Confirm the COIDA ceiling and the employer's assessment rate
separately.

## Verified application corrections

- Salary Structure hides only `max_benefits`; timesheet frequency, Salary
  Component and hourly-rate fields remain visible.
- HRMS supplies recurring, disabled and overwrite Additional Salary selection.
  Recurring records use effective dates; overwrite replaces the same structure
  component rather than adding a duplicate row.
- Full-tax additional earnings remain in PAYE, and post-statutory net pay still
  includes HRMS loans, exchange rates and rounding.
- UIF and SDL use the Salary Slip end date and explicit component applicability.
- ETI applies exclusion/minimum-wage checks, actual-hours handling, 160-hour
  gross-up/down and qualifying-month history. Generated and utilised ETI are
  separate values; only utilised ETI reduces the current EMP201 PAYE payable.
- Medical credit requires a positive, date-effective private medical scheme
  contribution and uses the dependant count on that benefit record.
- Retirement classification must use the current BRS code for the fund type:
  4001 pension, 4003 provident and 4006 retirement annuity.
- Submitted Company Car, Housing and Low Interest Loan benefits can create
  taxable non-cash Salary Slip rows without increasing cash net pay.
- EMP201, IRP5/IT3(a) and EMP501 provide internal readiness and reconciliation
  controls; draft/cancelled documents do not provide final coverage.

## Rate governance

Shared scalar rates can resolve from one approved, submitted Payroll rate pack in
`za_local_core` for the transaction date. Payroll-owned structured annual packs
remain the technical source for ETI/lump-sum/fringe-benefit rule tables, while
HRMS Income Tax Slabs and the rebate/medical-credit master drive PAYE. A packaged
scalar fallback is not source approval. Archive the official publication and
checksum, approve the source, update both governed layers as applicable, migrate
a restored staging site and obtain practitioner sign-off before opening March.

## External boundary

`za_local_payroll` does not directly submit to SARS and does not produce the
PAYE BRS payroll-import file. PDFs and internal exports are review aids only.
Capture approved figures through the controlled eFiling/e@syFile process and
retain submission and payment evidence.

Payroll bank export is limited to the identified FNB Online Banking Enterprise
CSV through a submitted Payroll Payment Batch. The app does not enforce
independent maker/checker approval; bank-portal dual authorisation, formal bank
acceptance and statement reconciliation are mandatory.

## Required acceptance evidence

On an isolated staging site restored from representative data:

1. rehearse backup, migration, repeat migration and rollback;
2. run static checks and the complete server test suite;
3. execute the matrix in [TESTING.md](../TESTING.md), including timesheet,
   recurring/overwrite pay, ETI, medical, retirement and each supported benefit;
4. reconcile payroll to GL and payment batch;
5. reconcile EMP201 to submitted certificates through EMP501, then manually tie
   the declaration/payment leg to SARS receipts and statements;
6. validate the current BRS and controlled external filing process;
7. inspect roles, cross-company access and private files;
8. obtain low-value FNB acceptance and independent bank approval; and
9. obtain written practitioner/employer approval of sources, mappings,
   calculations, employee facts and filing procedures.

Automated tests cannot determine legal ETI eligibility, benefit valuation, fund
classification, directive applicability, employee facts or whether an authority
changed a rule after release. Those remain explicit human gates.
