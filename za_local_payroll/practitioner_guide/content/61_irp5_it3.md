# IRP5 / IT3(a) Certificates

The **IRP5 Certificate** is each employee's annual tax certificate. Where no employees' tax was deducted (e.g. below the threshold), the same record functions as an **IT3(a)**. `za_local_payroll` builds the certificate by grouping the year's salary-slip amounts under their SARS payroll codes.

## When

At the annual reconciliation and, where required, the interim reconciliation. The interim period is 1 March to 31 August; the annual period runs to the last day of February. Generate and reconcile certificates before finalising the internal [EMP501](emp501) working paper.

The app's certificate/PDF and generic exports are not the SARS BRS payroll-import or encrypted reconciliation format. Use approved SARS capture/import tooling and retain external submission evidence.

## How the certificate is built

For each employee, the engine sums all submitted salary-slip components for the tax year and groups them by **SARS Payroll Code** into:

- **Income details** (e.g. 3601 normal income, 3605 annual payment, travel allowance codes, fringe-benefit codes).
- **Deduction details** (e.g. 4001/4003/4006 retirement, 4005 medical including the employer's contribution deemed paid by the employee, 4102 PAYE, 4115 directive tax, 4141 UIF).
- **Employer contribution details** (e.g. 4472 employer pension, 4474 employer medical, equal to 3810).
- **Tax credits**: 4116 medical scheme fees tax credit and 4118 ETI.
- **Totals**: 3696/3697/3698 gross totals and 4149 total tax, SDL and UIF.

The employer's tax ID on the certificate is the Company's **Income Tax Reference Number**, never its VAT number.

Components marked **Exclude from IRP5** are omitted. The header pulls the employee's identity, tax reference and addresses from the [Employee master](../full-suite-employees/employee-master), and the employer details (name, PAYE reference) from the Company.

## Step-by-step

1. **Generate the certificates** for the company and tax year (individually or in bulk from the SA Payroll workspace).

2. **Review each certificate.** Confirm:
   - Employee **ID/passport** and **income tax reference number** are present and valid.
   - **Residential and postal addresses** are complete (required by SARS).
   - Income, deduction and contribution lines carry the right **SARS codes** and amounts.
   - The certificate totals agree with the employee's salary-slip sums for the year.

3. **Independent review.** Each certificate records **Prepared By** (the user who generated it). A different Payroll Manager, named in **Reviewed By**, submits it; the preparer cannot. From the EMP501 Reconciliation, **Submit Certificates as Reviewer** submits every reviewed draft certificate in one step and submits none if one fails.

4. **Handle directives.** If the employee had a lump sum or final settlement, the relevant **Tax Directive** number must appear — see [Tax Directives & Final Settlements](directives-and-final-settlements).

5. **Print / export.** Use the **IRP5 Employee Certificate** print format (or **IRP5-it3 Certificate** for IT3(a) cases) to produce the PDF.

## Audit trail

IRP5 Certificate has change tracking enabled, so edits to a certificate are recorded — important for a SARS audit. Prefer regenerating from corrected source data over hand-editing amounts.

## Common issues

- **Missing tax reference number** — capture it on the Employee before generating.
- **Totals don't match** — a salary slip was amended after generation; regenerate the certificate.
- **Code missing on a line** — the source Salary Component has no SARS payroll code; fix the component and regenerate.

## Next

Consolidate the year with the [EMP501 Annual Reconciliation](emp501).
