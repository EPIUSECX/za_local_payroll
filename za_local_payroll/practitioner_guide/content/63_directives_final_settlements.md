# Tax Directives & Final Settlements

Lump-sum payments — severance, retirement lump sums, and some leave payouts — are taxed under a separate SARS regime and usually require a **Tax Directive**. `za_local_payroll` supports this through the Tax Directive DocType and a structured final-settlement process.

## When a Tax Directive is needed

A SARS tax directive is required for lump-sum amounts such as severance/retrenchment benefits and retirement fund lump sums, and for certain other once-off payments. The directive tells you the exact tax to withhold, and its **directive number** must appear on the employee's IRP5.

## 1. Capture the Tax Directive

Apply for the directive on SARS eFiling, then record it in `za_local_payroll`:

1. Go to **Tax Directive → New**.
2. Set the **Employee**, **Company** and **Directive Type**: *Severance / Lump Sum* (tax on a lump sum = the directive amount, under 4115), *Fixed Amount* (a fixed monthly PAYE), *Reduced Tax Rate* (PAYE at the directed rate), *Standard Directive* or *Garnishee Order*.
3. Enter the **Directive Number**, **Effective From / To** and the amount or rate SARS specified, and attach the SARS directive as a private **Directive Attachment**.
4. Set **Status** to *Active*. Only an Active directive covering the slip date is applied. Payroll Managers can create, submit, cancel and amend directives.

## 2. Process the final settlement

When an employee leaves:

1. Use **Employee Separation** to drive the final-settlement salary slip where available.
2. The final pay is processed on a salary slip with the components **separated**: Notice Pay, Leave Payout, Severance Benefit, and Tax on Lump Sum.
3. A slip carrying a severance or lump-sum component is refused unless an **Active** directive of type **Severance /
   Lump Sum** covers the slip date. The tax deducted is the directive amount, under SARS code 4115, and the lump sum
   is excluded from the normal PAYE average. A nil directive amount is allowed when the SARS directive is attached.
   The severance component is treated per its SA payroll treatment (e.g. excluded from UIF/SDL).
4. The **Tax Directive number** is referenced so it carries through to the IRP5.

The settlement record is a controlled calculation and approval record. It does not fabricate a Salary Slip. Capture the approved final components through the normal Payroll Entry/Salary Slip flow so HRMS account, loan, exchange-rate, rounding and submission controls remain active.

> Without a referenced Tax Directive, the EMP501 readiness checks will flag employees who received lump sums. Capture the directive before finalising year-end.

## 3. Leave encashment

For leave paid out outside a full termination, `za_local_payroll` provides a **Leave Encashment** process (DocType *Leave Encashment Sa*). Use it to process the leave payout with correct SA tax treatment, separate from the final-settlement flow.

## 4. Verify on the certificate

On the employee's [IRP5](irp5-it3), confirm the lump-sum income appears under the correct SARS code, the **directive number** is shown, and the tax matches the directive. Then include the certificate in the [EMP501](emp501).

## Checklist for a leaver

- [ ] Tax Directive obtained from SARS and captured.
- [ ] Final salary slip with separated notice pay / leave payout / severance / lump-sum tax.
- [ ] Lump-sum tax matches the directive.
- [ ] Employee status updated; last working day recorded.
- [ ] IRP5 generated with the directive number.

## Section complete

That completes the full-suite payroll lifecycle. Continue with the [SA Labour](../sa-labour-coida/sa-labour) and [SA COIDA](../sa-labour-coida/sa-coida) modules, or the [Reference & Operations](../reference-operations/custom-fields-reference) section.
