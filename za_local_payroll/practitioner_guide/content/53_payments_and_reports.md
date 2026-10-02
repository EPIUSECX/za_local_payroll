# Payroll Payments & Reports

With the payroll posted, pay employees and use the reports to validate and reconcile the run.

## Paying employees (EFT)

`za_local_payroll` enables one bank-specific format: **FNB Online Banking Enterprise CSV**. ABSA, Nedbank and Standard Bank are deliberately disabled until a current official specification and controlled bank acceptance test are completed.

Create a **Payroll Payment Batch** from a submitted Payroll Entry, review the employee rows/control total, then submit the batch and generate its private file. The Payroll Entry and Salary Slips must be submitted, currency must be ZAR, employee/company bank data must pass validation, and the payment date must be inside the permitted window. The source hash freezes the snapshot; cancel/amend the batch if payroll or bank data changes.

Export requires Payroll Payment Batch write access and an authorised HR Manager, Accounts Manager or System Manager role. Do not distribute the private file through email or public attachments.

## Recording the bank settlement

When the bank confirms payment, open the submitted batch and select **Record Bank Settlement** with the bank posting
date. This posts one Bank Entry from the batch snapshot: a debit to Payroll Payable for each employee's net pay and a
credit to the company bank account. Payroll Payable for the period then clears to zero, apart from any third-party
deductions (for example union dues) that you pay separately. A batch can be settled once; the entry links back to it.
Requires submit permission on the batch.

> Employees must have valid banking details (and *Not Paid Electronically* unticked). Reconcile the file total to Payroll Payable and perform an FNB low-value acceptance upload before first production use and after any bank specification change.

## Distributing payslips

Print or email the **SA Salary Slip** print format. It reflects the SA earnings, deductions, employer contributions and statutory figures.

## Reports

The **SA Payroll** workspace provides the validation and reconciliation reports:

| Report | Use |
|---|---|
| **Payroll Register** | All employees with earnings, deductions, net pay and statutory amounts for the period. Your primary review and reconciliation view. |
| **EMP201 Report** | PAYE, UIF, SDL and ETI totals for the month — the basis for the EMP201 declaration. |
| **Statutory Submissions Summary** | PAYE (including directive tax, 4115), employee and employer UIF and SDL, less ETI generated, for any period. Its total equals the EMP201 liability for the month. |
| **Retirement Fund Deductions** | Retirement contributions by employee/component, to reconcile against fund schedules. |
| **Department Cost Analysis** | Payroll cost by department. |
| **EMP201 Report** / **Payroll Register** | Use with company and period filters; restricted to payroll roles. |

Standard HRMS reports (Salary Register, Bank Remittance, Income Tax Computation) remain available too.

## Month-end reconciliation routine

1. Payroll Register totals = General Ledger payroll postings.
2. PAYE Payable – SARS balance = EMP201 PAYE.
3. UIF (employee + employer) = EMP201 UIF.
4. SDL = EMP201 SDL.
5. ETI total = sum of `za_monthly_eti` across slips.
6. Payroll Payable = EFT batch net pay.

When these tie out, you are ready to declare on the EMP201.

## Next

Move to statutory submissions, starting with the [EMP201 Monthly Declaration](../full-suite-statutory-submissions/emp201).
