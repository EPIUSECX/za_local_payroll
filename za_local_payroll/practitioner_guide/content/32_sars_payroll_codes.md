# SARS Payroll Codes

**SARS Payroll Code** records are the income, deduction and employer-contribution codes that appear on the IRP5/IT3(a) certificate. Each Salary Component maps to one of these codes so that, at year-end, the IRP5 groups amounts under the correct SARS code.

## Seeded codes

A default set of SARS codes is seeded on install. Open the **SARS Payroll Code** list (SA Payroll workspace) to review them. Each record carries:

| Field | Meaning |
|---|---|
| Code | The SARS code, e.g. `3601` (income), `4102` (PAYE), `4141` (UIF). |
| Description | Human-readable label. |
| Category | Income, Deduction, Tax Credit or Employer Contribution. |
| Tax Treatment | Taxable, Non-Taxable or Reference. |
| Print Sequence | Controls ordering on the IRP5. |
| Active | Whether the code is in use. |

## Common codes you will use

| Code | Typical use |
|---|---|
| 3601 | Income — normal remuneration (salary/wages); also notice pay. |
| 3605 | Annual payment (bonus, 13th cheque) and leave paid out on resignation. |
| 3606 | Commission. |
| 3607 | Overtime. |
| 3701 | Travel allowance (fixed). |
| 3702 / 3703 | Reimbursive travel allowance (taxable / non-taxable portion). |
| 3713 | Other allowances (housing, cellphone, uniform). |
| 3801 / 3802 / 3805 | Fringe benefits: general (including low-interest loans) / use of motor vehicle / residential accommodation. |
| 3810 | Medical scheme fees paid by the employer (fringe benefit). |
| 3901 | Gratuities and severance benefits (lump sum under a directive). |
| 4001 / 4003 / 4006 | Pension / provident / retirement annuity fund contributions. |
| 4005 | Medical scheme contributions (including the employer's, deemed paid by the employee). |
| 4102 | PAYE. |
| 4115 | Tax on a lump sum under a directive. |
| 4118 | ETI. |
| 4141 | UIF (employee + employer). |
| 4142 | SDL. |
| 4472 / 4474 | Employer pension / medical scheme contributions. |
| 3697 / 3698 | Gross retirement-funding / non-retirement-funding totals (calculated, not mapped). |

The seeded master follows **SARS PAYE BRS v25.3.0**. Codes that BRS does not recognise as source codes
(4007, 4008, 4010, 4476, 4477 and 4497) are inactive; do not map components to them.

> Always confirm codes against the current **SARS PAYE BRS (Business Requirements Specification)** for the tax year you are filing. Codes and their validation rules are updated periodically.

## Mapping components to codes

You assign the SARS code on each **Salary Component** via the `za_local_payroll` *SARS Payroll Code* field. You can also tick *Exclude from IRP5* on components that should never appear on the certificate (for example working-paper-only items such as union subscriptions). A component excluded from the IRP5 or treated as *Working Paper Only* needs no SARS code; every other earning and deduction does, and payroll stops if one is missing. This mapping is covered next in [Salary Components & SA Treatment](salary-components).

## Permissions

SARS Payroll Code, Tax Rebates and ETI Slab are statutory configuration. They are editable by **System Manager** and **HR Manager**, and readable by **HR User**, so payroll staff can verify the codes and rates being applied without holding the System Manager role.

## Next

Configure [Salary Components & SA Treatment](salary-components).
