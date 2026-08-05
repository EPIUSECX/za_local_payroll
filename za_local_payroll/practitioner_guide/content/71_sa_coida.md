# SA COIDA: Return of Earnings, Injuries & Claims

The **SA COIDA** module prepares a governed Return of Earnings working paper and
tracks workplace injuries, OID claims, and medical-report evidence. It does not
file with eCOID, certify a CF-2A/W.As.8, obtain a Letter of Good Standing, or prove
Compensation Fund acceptance.

## Governed rates

The preferred source is an approved, effective **ZA Statutory Rate Pack** for:

- annual per-employee earnings cap;
- company/class assessment percentage; and
- general or domestic-employer minimum assessment.

`COIDA Settings` is a site-wide Single. Its Industry Rate rows are used only by an
independently prepared/reviewed migration fallback when no approved core rate
applies. The fallback requires exact dates, source reference, private evidence,
positive minimums, and exactly one applicable company/class rate; changes reset
approval.

For the period beginning 1 March 2026, Gazette 54577 Notice 3910 verifies a
R668,000 annual cap per employee, R1,621 general minimum, and R560 domestic-
employer minimum. Operational use still requires the approved rate pack and
correct employer category/class.

## Return of Earnings working paper

1. Create **COIDA Annual Return** with Company, exact Industry Class, Employer
   Category, and a Fiscal Year exactly from 1 March to end-February.
2. Run **Fetch Earnings**. Submitted Salary Slips are assigned by **end date**, so
   a cross-boundary slip is counted once.
3. The normal source is payroll's persisted `Salary Slip.za_coida_basis`; Gross Pay
   is reconciliation data, not the assessable basis.
4. Review hashed source-slip rows, employee/slip counts, uncapped gross, excluded
   amount, capped assessable earnings, explicit director subtotal, rule/source
   references, assessment before minimum, minimum, and final fee.
5. Reconcile to payroll and obtain COIDA/business approval before Frappe Submit.

The return caps accumulated assessable earnings per employee, applies the approved
percentage and minimum, and blocks submit if payroll, director classification,
rates, hashes, or totals changed after Fetch Earnings. Frappe Submit only locks the
internal working paper. File externally and retain declaration, reference, receipt,
assessment, payment, and revision/objection evidence in the approved record system.

## Workplace Injury

Only HR Manager/System Manager can access Workplace Injury and OID Claim records.
Capture incident facts, reporter/time, mechanism, body part, witnesses,
investigation, medical attention/provider, recovery/return-to-work, and whether
governed leave or an OID claim is required.

Claimable injury submission requires mechanism, body part, and investigation.
Requested leave and claim drafts are created in the same transaction; a failure
aborts submission. Protected actions can create either after submit if identified
later. External Compensation Fund date requires a reference and private receipt.

The operational seven-day status is calculated from Injury Date. A practitioner
must determine the applicable statutory trigger, form, deadline, occupational-
disease route, and late-report action; the field is not a legal conclusion.

## OID Claim and medical reports

Submitting an OID Claim sets status `Submitted`. HR Manager/System Manager may
perform only:

- `Submitted` → `Under Review`, `Approved`, or `Rejected`;
- `Under Review` → `Approved` or `Rejected`; and
- `Approved` → `Paid`.

Approval requires positive compensation; Paid requires a payment date. Linked
injury status is synchronised. Medical rows require report date, provider, type,
and diagnosis; future dates are blocked, and a premature Final Report warns. Add
rows directly in Draft or through the protected post-submit action.

Medical attachments must be private. The app does not calculate medical cost,
disablement, pension, rehabilitation, prescribed-form completeness, or claim
acceptance.

The current role matrix does not expose cancel/amend for injuries, claims, or the
annual return to ordinary HR/System Manager users. Corrections remain an
administrator-controlled residual process; never edit submitted rows directly.

## Privacy and approval gate

Treat identity, injury, witness, diagnosis, recovery, compensation, and medical
evidence as restricted personal information. Verify role assignment, Company User
Permissions, private files/direct URLs, exports, shares, retention, backups,
restored-site access, and role removal.

Production requires recorded COIDA, payroll, HR/health-and-safety, privacy, and
authorised business-signatory approval. All eCOID/Compensation Fund filing and
authority outcomes remain Controlled Manual.

## Official source

[Gazette 54577 Notice 3910 and CF-2A form](https://www.gov.za/sites/default/files/gcis_document/202604/54577gen3910.pdf)
