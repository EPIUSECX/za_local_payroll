# SA COIDA Configuration and Testing Practitioner Guide

This guide covers the implemented Compensation Fund working papers and workflows:
governed rates, Return of Earnings, workplace injuries, OID claims, and medical
reports.

## Scope and legal boundary

SA Localisation Workplace does not transmit data to eCOID, file CF-2A/W.As.8 or
accident/occupational-disease forms, obtain a Letter of Good Standing, determine
Compensation Fund acceptance, or certify legal compliance. **Submit** in Frappe
means an internally locked working paper or claim record only.

The employer and appointed COIDA practitioner remain responsible for registration,
classification, reportability, prescribed forms, deadlines, earnings treatment,
assessment reconciliation, external filing, receipts, objections/revisions, and
retention.

## Roles, privacy, and prerequisites

Before configuration:

- Company, Employees, and a Fiscal Year exactly from 1 March to the last day of
  February exist.
- `za_local_payroll` is installed and Salary Components/Salary Slips have reviewed
  COIDA classifications and persisted `za_coida_basis` values.
- `za_local_core` contains approved, effective ZA Statutory Sources and Rate Packs.
- Company has the correct COIDA registration number and each Employee has an
  explicit COIDA Director Classification where applicable.
- HRMS Leave Types include a governed `Occupational Injury Leave` type if injury
  leave creation will be used.
- Only HR Manager/System Manager has Workplace Injury and OID Claim access;
  Company User Permissions and private-file handling have been tested.

Injury, diagnosis, ID, medical, recovery, compensation, witness, and investigation
data is restricted personal information. Keep attachments private and do not use
production health records in public support or test environments.

## 1. Configure approved COIDA rates

### Preferred source: ZA Statutory Rate Pack

The Return of Earnings resolves, at the assessment period start:

- `coida.annual_earnings_cap`;
- `coida.minimum_assessment` or `coida.domestic_minimum_assessment`; and
- company/class rate `coida.assessment_rate.<Company>.<Industry Class>`, falling
  back to governed class rate `coida.assessment_rate.<Industry Class>`.

Create these rules in an approved, effective `ZA Statutory Rate Pack` backed by an
approved `ZA Statutory Source`. The source hash/reference is copied to the Return
of Earnings snapshot. If no approved value applies, calculation fails; the app
does not guess from today's date or select an arbitrary row.

### Controlled migration fallback

`COIDA Settings` is a site-wide Single. Its registration/reference fields are
legacy/shared metadata; the canonical company registration is on Company.
Industry Rate child rows are not standalone masters and are used only by the
approved migration fallback when no core rate applies.

To use that temporary fallback:

1. Enable **Allow Legacy Rate Fallback**.
2. Set exact effective dates, source reference, general and domestic minimums,
   and private source evidence.
3. Add exactly one applicable company/class row (or one unscoped class row) with
   a positive assessment rate.
4. A ZA Compliance Manager/System Manager different from the preparer runs
   **Approve Legacy Rate Fallback**.

Changing controlled fields resets approval to Draft. The fallback is rejected
outside its dates, without private evidence/reviewer details, or when company/
class matches are missing or ambiguous. It is a migration control, not the normal
long-term rate source.

For the period beginning 1 March 2026, Gazette 54577 Notice 3910 verifies a
R668,000 per-employee annual ceiling, R1,621 general minimum, and R560 domestic-
employer minimum. These anchors still require an approved operational rate pack
and the correct employer category/class.

## 2. Prepare payroll earnings evidence

The COIDA Annual Return uses submitted Salary Slips whose **end date** falls in
the assessment year. This assigns a cross-boundary payroll period to one year and
prevents double counting; it does not require the slip to be fully contained.

Normal split-suite basis:

- `Salary Slip.za_coida_basis`, persisted by `za_local_payroll`, is authoritative.
- Gross Pay is retained for reconciliation, not used as the assessable basis.
- The app caps the accumulated assessable basis per employee for the year.

Compatibility fallback, used only if the Salary Slip field is absent:

- sum earnings whose Salary Component is explicitly COIDA-applicable;
- exclude reimbursements, reimbursive travel, Working Paper Only treatments,
  statistical rows, and rows excluded from totals where those classifications
  exist.

Before preparing a return, reconcile Salary Component classifications and each
slip's COIDA basis to payroll. Confirm directors/members using
`Employee.za_coida_director`; designation text is not inferred.

## 3. Create the COIDA Annual Return

1. Create **COIDA Annual Return**.
2. Select Company, exact Industry Class, Employer Category, and a Fiscal Year that
   runs from 1 March to the last day of February. Any other Fiscal Year is blocked.
3. Run **Fetch Earnings**.
4. Review:
   - source-slip count and employee count;
   - uncapped gross earnings;
   - capped COIDA assessable earnings and excluded difference;
   - explicit director subtotal;
   - cap/rate/minimum rule keys and source references;
   - assessment before minimum, minimum, and final assessment fee; and
   - calculated timestamp and source snapshot hash.
5. Reconcile to payroll and approved sources. Save and obtain practitioner/business
   approval.
6. Submit only to lock the reviewed internal working paper.

Fetch Earnings creates one hashed snapshot row per Salary Slip. Before submit, the
controller rebuilds the calculation and blocks if payroll, director classification,
approved rates, source hash, or authoritative totals changed. Re-fetch and review;
do not bypass the control.

The final assessment fee is the greater of capped assessable earnings multiplied
by the approved percentage rate, and the applicable general/domestic minimum.

### External filing

Export/print is a working paper only. The COIDA Annual Return has no eCOID transport
or authoritative Compensation Fund receipt/assessment workflow. File through the
supported Compensation Fund channel, retain the external declaration, reference,
receipt, assessment, payment, revision/objection evidence, and reconcile them in
the organisation's approved record system. Do not describe Frappe Submission Date
as the external filing date.

## 4. Record a Workplace Injury

Capture:

- Employee/Company, injury date/time/location, type, severity, and description;
- reporter and timestamp (set on insert);
- mechanism, body part, witnesses, and investigation summary;
- medical-attention/provider, expected recovery, and return-to-work date;
- whether governed occupational-injury leave or an OID claim is required; and
- Compensation Fund submission reference/date and private receipt evidence after
  external submission.

Validation includes:

- no future injury date;
- recovery/return-to-work cannot precede injury;
- reported timestamp cannot precede injury date/time;
- provider is required when medical attention is recorded;
- witness details are required when witnesses are recorded; and
- external submission date requires both reference and private receipt evidence.

For a claimable injury, Incident Mechanism, Body Part Affected, and Investigation
Summary are mandatory before submit.

If **Requires Leave** is selected, submit creates a draft Leave Application with
the configured Occupational Injury Leave Type. If **Requires OID Claim** is
selected, submit creates a draft OID Claim. Either failure aborts the injury
submission. Protected POST actions can create either draft after submission when
the requirement is identified later.

The record calculates an operational due date seven days from Injury Date and
labels it Due/Overdue/Submitted On Time/Submitted Late. This is a workflow aid,
not a legal determination: the practitioner must confirm the applicable accident
or occupational-disease form, statutory trigger, deadline, and late-report action.

## 5. Manage an OID Claim

An OID Claim may be created from an injury or manually. When linked, Employee and
Company must agree and missing injury details are copied from the injury.

Submission sets Claim Date (today when absent) and status `Submitted`. HR Manager
or System Manager with write permission may use the protected action for only:

- `Submitted` → `Under Review`, `Approved`, or `Rejected`;
- `Under Review` → `Approved` or `Rejected`; and
- `Approved` → `Paid`.

Approval requires Compensation Amount greater than zero. Paid requires Payment
Date on/after Claim Date. Rejected and Paid are terminal in this implemented state
machine. The linked injury status maps to Investigating, Treating, or Closed.

Frappe claim status tracks the internal/external progress supplied by the user; it
does not prove Compensation Fund acceptance or payment.

The current role matrix does not grant ordinary HR/System Manager users cancel or
amend permission for Workplace Injury, OID Claim, or COIDA Annual Return. Treat
record correction as an administrator-controlled residual process until a reviewed
role-based correction workflow is released. Never edit submitted records directly
in the database.

## 6. Add OID Medical Reports

In Draft, add child rows directly. After submission, HR Manager/System Manager
uses **Add Medical Report**. Each row requires Report Date, Medical Provider,
Report Type, and Diagnosis; Attachment is optional. The parent blocks future report
dates and warns if a Final Report is recorded before the claim is Approved/Paid.

The child record does not calculate medical cost, disablement, pension,
rehabilitation, prognosis, or statutory medical-form completeness. Verify the
attachment is a private File and follow the organisation's medical-record access
and retention procedure.

## Desk test matrix

### Governed rates and Return of Earnings

1. Missing/unapproved/out-of-period cap, rate, or minimum must block calculation.
2. Ambiguous fallback company/class rows must block.
3. Changing a fallback setting must invalidate its approval.
4. A non-March Fiscal Year must be rejected.
5. A cross-boundary slip must belong only to the year containing its end date.
6. Reimbursement/non-applicable components must not enter the compatibility basis.
7. Two employees must each receive their own cap; never cap the company total.
8. Explicit director classification must control the director subtotal.
9. General and domestic employer minimums must be selected correctly.
10. After Fetch Earnings, change payroll/director/rate data: submit must report a
    stale source and require re-fetch.
11. Cancelled Salary Slips must not be counted.

### Workplace Injury

1. Future Injury Date, invalid recovery/return date, or reported-before-injury
   timestamp must be blocked.
2. Medical attention without provider and witnesses without details must be
   blocked.
3. A claimable injury without mechanism/body/investigation must be blocked.
4. Required leave with a non-governed Leave Type must be blocked.
5. Force Leave Application or OID Claim insert failure: injury submit must roll
   back and remain Draft.
6. After external submission date, missing reference or private receipt must block.
7. Employee/HR User without HR Manager/System Manager must not read the injury.

### OID Claim and medical reports

1. Linked Employee/Company mismatch must be blocked.
2. Claim/payment dates before injury/claim must be blocked.
3. Test every allowed transition and at least one disallowed backward/skip
   transition.
4. Approved without positive compensation and Paid without payment date must fail.
5. Unauthorised users must not change submitted status or add a report.
6. A future medical report date must fail; a premature Final Report must warn.
7. Verify the administrator-controlled correction procedure preserves the audit
   trail and linked injury status; ordinary HR users must not be told they can
   cancel/amend these records.

### Privacy and cross-company access

- Verify Employee role has no Workplace Injury/OID Claim list or document access.
- Verify HR users restricted to another Company cannot access source payroll or
  working papers.
- Confirm health/medical/external receipt attachments are private and inaccessible
  by direct URL to an unauthorised session.
- Test exports, shares, backups, restored-site permissions, and role removal.

## Troubleshooting

- **Missing approved COIDA rate:** approve an effective core rate pack; use the
  migration fallback only with separate preparer/reviewer and private evidence.
- **No earnings:** confirm submitted slips end in the assessment period and have
  reviewed `za_coida_basis` values.
- **Unexpected excluded amount:** reconcile gross pay to COIDA basis component by
  component; Excluded Annual Earnings includes both non-assessable amounts and the
  effect of per-employee capping.
- **Return is stale:** re-fetch after any payroll, director, employer-category,
  class, cap, rate, or minimum change and repeat practitioner review.
- **Leave creation fails:** configure HRMS, employee leave approver/allocation as
  applicable, and a governed Occupational Injury Leave Type.
- **Claim transition fails:** use the protected action, check current status, role,
  compensation amount, and payment date.
- **External filing not reflected:** the annual return does not receive eCOID
  status; retain the authoritative response in the approved external evidence
  process.

## Human approval gates

- COIDA practitioner: registration, employer category, class/rate, earnings basis,
  cap/minimum, ROE, prescribed injury/claim forms, deadlines, and outcomes.
- Payroll owner: Salary Component classification, persisted basis, employee/slip
  completeness, and reconciliation.
- HR/health-and-safety owner: incident facts, investigation, leave, return to work,
  medical evidence, and corrective actions.
- Information Officer/privacy/security owner: lawful processing, roles, Company
  restrictions, private files, retention, disclosures, logs, backups, and breach
  response.
- Authorised business signatory: external declarations, portal submission,
  assessment/payment/revision evidence, and residual-risk acceptance.

## Official verification anchors

- [Compensation for Occupational Injuries and Diseases Act](https://www.labour.gov.za/DocumentCenter/Acts/Compensation%20for%20Occupational%20Injuries%20and%20Diseases/Act%20-%20Compensation%20for%20Occupational%20Injuries%20and%20Diseases.pdf)
- [2026 COIDA Gazette 54577 Notice 3910 and CF-2A form](https://www.gov.za/sites/default/files/gcis_document/202604/54577gen3910.pdf)
- [Compensation Fund Return of Earnings guidance](https://www.labour.gov.za/DocumentCenter/Pages/COID_How_To_Submit_Earnings_Statements_to_the_Compensation_Fund.aspx)
