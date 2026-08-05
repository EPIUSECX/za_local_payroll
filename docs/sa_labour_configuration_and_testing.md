# SA Labour Configuration and Testing Practitioner Guide

This guide describes the labour, leave, termination, Employment Equity, skills,
and Business Trip controls currently implemented by SA Localisation Workplace.

## Scope and operating model

The app provides controlled records, validations, and working papers. It does not
replace the Basic Conditions of Employment Act (BCEA), collective agreements,
bargaining-council rules, sector determinations, current Department of Employment
and Labour forms, SETA rules, or professional judgement.

| Capability | Readiness |
|---|---|
| BCEA leave and termination decision support | Preview; opt-in and deliberately limited |
| Sectoral/NMW reference records | Controlled Manual; no automatic employee assignment or payroll block |
| Employment Equity working papers | Controlled Manual; not official EEA forms or filing output |
| WSP/ATR and skills records | Controlled Manual; not SETA submission/acceptance or B-BBEE scoring |
| Business Trip and Expense Claim hand-off | Operational workflow subject to company policy, accounts approval, and payroll tax review |

## Roles and privacy prerequisites

Before configuration:

1. Create named ZA Compliance Reviewer and ZA Compliance Manager users in
   `za_local_core`. Do not use shared accounts.
2. Limit HR Manager and compliance roles to users with a documented need.
3. Configure Company User Permissions and test a user restricted to another
   company.
4. Keep race, disability, remuneration, movement, appointment, accreditation,
   training-completion, review, and external-filing evidence private.
5. Confirm the responsible party's POPIA lawful basis, purpose, retention,
   data-subject, breach, and disclosure procedures.

Employment Equity reports require Company and Employee read permission. Small
positive cells are hidden by default; only ZA Compliance Reviewer, ZA Compliance
Manager, or System Manager can request revealed cells.

## 1. Configure BCEA Leave Types

The Leave Application override is opt-in. For each governed Leave Type:

1. Open **Leave Type**.
2. Enable **Apply BCEA Validation**.
3. select an explicit **BCEA Leave Category**. The controller never infers a
   category from the Leave Type name.
4. For sick leave, retain **Medical Certificate Required After (Days)** at two or
   a stricter company value. A value above two does not make the statutory control
   more permissive.
5. Set **Applicable Gender** only where a reviewed policy/lawful rule requires it.
6. For injury leave, use category **Occupational Injury Leave**.

Implemented Leave Application behaviour:

- A governed sick-leave application requires **Medical Certificate Evidence**
  when its calendar duration exceeds the configured threshold, or when it is more
  than the second distinct sick-leave occasion in the preceding eight weeks.
- Touching or overlapping prior sick-leave ranges count as one occasion.
- Governed family-responsibility leave cannot exceed three days across submitted
  applications in the employee's 12-month service-anniversary cycle.
- A configured Applicable Gender must match the Employee's Gender.
- An annual-leave application of at least 21 days produces an informational review
  message; it is not an entitlement calculation or approval.

Not automated: the 36-month sick-leave cycle/first-six-month accrual, family-
responsibility eligibility and qualifying event/proof, maternity/parental/adoption
entitlements, hours-of-work provisions, earnings-threshold effects, collective
agreements, and annual-leave allocation. Configure those in HRMS and obtain labour-
practitioner approval.

### Leave tests

Use synthetic employees and records:

1. Save a non-governed Leave Type application: only standard HRMS rules should run.
2. Save governed sick leave of more than two consecutive calendar days without
   evidence: save should be blocked.
3. Attach a private medical certificate: the same record should pass this control.
4. Submit two separate sick-leave occasions, then create a third within eight
   weeks without evidence: save should be blocked.
5. Create family-responsibility applications totalling more than three days in one
   service-anniversary cycle: the excess should be blocked.
6. Use a gender-specific Leave Type for an Employee with a different Gender: save
   should be blocked.

Do not use real medical documents in automated or public test environments.

## 2. Configure termination decision support

Employee Separation includes a South African final-settlement section.

1. Set **Termination Type** and **Actual Termination Date**. The resignation-letter
   date is not used as a substitute.
2. Record **Reviewed BCEA Weekly Remuneration**, **Reviewed BCEA Daily
   Remuneration**, and a **BCEA Remuneration Basis** explaining source period,
   inclusions, exclusions, and reviewer reasoning.
3. An HR Manager or System Manager enables **BCEA Remuneration Reviewed**. The app
   records reviewer and timestamp when the snapshot changes.
4. Review calculated notice days, completed service years, severance, annual-leave
   payout days, and amount.
5. Submit Employee Separation only after case review. An authorised user can then
   create one Employee Final Settlement through the protected action.

Implemented calculations:

- minimum notice: 7 days for service under six months, 14 days from six months to
  under one year, and 28 days from one year;
- severance: only `Dismissal - Operational`, one reviewed week per completed year;
- leave payout: positive HRMS ledger balances for Leave Types governed as Annual
  Leave, multiplied by reviewed daily remuneration; and
- completed years: whole service anniversaries at Actual Termination Date.

These are calculation controls, not a legal conclusion. Before approval, the
practitioner must confirm the termination reason, alternatives/refusal, collective
agreement, notice/pay/waiver, remuneration definition, tax directive, certificate
of service, and case-specific obligations.

### Termination tests

- Missing Actual Termination Date or Termination Type must block save.
- A termination date before Date of Joining must block save.
- Test service dates immediately before/on the six-month and one-year boundaries.
- Non-operational termination must calculate zero severance.
- Operational dismissal without reviewed positive weekly remuneration must block.
- Annual leave payout must use only positive governed ledger balances and reviewed
  daily remuneration.
- A user outside HR Manager/System Manager must not confirm the remuneration.
- Creating a second final settlement for the same Employee must be blocked.

## 3. Configure wage and bargaining references

Create or review:

- **SETA** and **Bargaining Council**, then link the applicable records on Company;
- **Industry Specific Contribution** with contribution type, rate, and effective
  dates; and
- **Sectoral Minimum Wage** with exact worker category, sector/position,
  effective dates, source reference, private source evidence, independent reviewer,
  and private review evidence.

The app keeps General NMW, EPWP, Schedule 2 learnership, sector-specific, and
special/excluded categories separate. Submitted reference rows remain
`Controlled Manual - No Automatic Employee Assignment`; they do not select an
employee, evaluate actual ordinary hours, alter salary, or block payroll.

For 1 March 2026, the source anchors are R30.23 per ordinary hour for the general
NMW and R16.62 for EPWP; qualifying learnerships use the applicable Schedule 2
allowance. The 2026 draft references seeded by the app are not approved until a
different reviewer submits them with private source/review evidence.

## 4. Configure Employment Equity

### Company and Employee data

On Company, review:

- **Designated Employer for EE**;
- **Employment Equity Sector**;
- **Default Employment Equity Target Plan**; and
- **EE Small-cell Suppression Threshold** (default five).

On Employee, review Race, Gender, Occupational Level, disability classification,
Date of Joining, Relieving Date, and Company. These are sensitive working data;
the application does not determine a person's classification.

### Target plan and movements

Create **Employment Equity Target Plan** with company, plan dates, sector, exact
source basis, governed ZA Statutory Source where required, source reference,
private source evidence, threshold, and effective target rows. A different
reviewer with an authorised compliance role must submit it with private review
evidence.

Create and submit **Employment Equity Movement** for appointments, promotions,
demotions, transfers, terminations, and other movements. Capture the reviewed
demographic snapshot and either a source document or private evidence.

The target-plan controller records the Employment Equity Amendment baseline as
1 January 2025 and the sector-target regulations as 15 April 2025. It constrains
sector-target plans to the current period ending 31 August 2030. A practitioner
must still select the correct EEA17 sector, EAP/target basis, annual goals, and
reasonable grounds.

### Working-paper reports

| Report | Implemented basis | Not an assertion of |
|---|---|---|
| EE Workforce Profile | Active-at-reporting-date employees grouped by occupational level, gender, disability, and race | Official EEA2/EEA4 population totals |
| EEA2 Income Differentials | Latest effective submitted Salary Structure Assignment base per employee; monthly proxy | Total remuneration or official EEA4 income-differential output |
| EEA4 Employment Equity Plan | Current headcount compared with the latest effective rows of one submitted target plan | A filed EEA13 plan or official EEA4 form |
| EE Workforce Movement | Submitted explicit movement records between From/To dates | Inferred HR movement history |

All reports require Company and reporting dates (or From/To dates). The target
report also requires a submitted plan for that company and date. Suppressed cells
must remain suppressed in exports shared outside the approved review group.

### Employment Equity tests

1. Run each report without Company/date: it must fail with a clear requirement.
2. Use a user without Company permission: access must be denied.
3. Create multiple submitted Salary Structure Assignments: the remuneration proxy
   must use only the latest effective one.
4. Create a positive cell below threshold: count and remuneration must be hidden.
5. Attempt **Show Small Cells** as HR Manager without compliance role: access must
   be denied.
6. Select a draft, other-company, or out-of-period target plan: report must fail.
7. Confirm each report displays the Controlled Manual message.

## 5. Configure WSP, ATR, and skills records

### Governed masters

1. **SETA**: maintain code/name and a current authority/source reference.
2. **Skills Development Facilitator**: company, effective dates, appointed User,
   private appointment evidence, independent reviewer, and review evidence. Submit
   before WSP/ATR use.
3. **OFO Occupation**: OFO code/version, title, effective dates, source reference,
   and private source evidence where available.
4. **Training Provider**: registration and accreditation scope/dates. If marked
   accredited, body, number, and private evidence are mandatory.

### Workplace Skills Plan

Create WSP with Company, Fiscal Year, SETA, submitted SDF, source reference, and
planned training rows. Each row links an OFO occupation and provider and records
learners/cost. The total budget is calculated; negative values are rejected.
Submission requires at least one row, a different authorised reviewer, and private
review evidence. Submit means **Internally Approved**, not filed.

### Annual Training Report

Create ATR for the same Company, Fiscal Year, SETA, submitted SDF, and submitted
WSP. Each completed row requires OFO, provider, completion details, non-negative
spend, and private completion evidence. The total actual spend is calculated.
Submission requires independent review and private review evidence.

### Skills Development Record

Link Company, Fiscal Year, SETA, submitted WSP, optional submitted ATR, Employee,
OFO, provider, dates, costs, and private completion evidence. When provider
accreditation is required, the provider must be recorded as accredited for the
training dates. Submission requires completion evidence.

`B-BBEE Scoring Status` remains `Controlled Manual - Not Calculated`; `BEC Points`
is set to zero. The application does not calculate B-BBEE skills points.

### External filing evidence

WSP and ATR have `Not Filed`, `Filed Externally`, and `Not Applicable` states.
`Filed Externally` requires an external reference, date, and private evidence.
These fields do not submit to a SETA. Because Frappe submitted documents are
immutable, record the external outcome on a draft/amended working paper according
to the approved operating procedure.

Test WSP/ATR company/SETA/Fiscal Year consistency, draft SDF/WSP rejection,
missing completion evidence, negative values, independent reviewer separation,
provider accreditation dates, private-file enforcement, and Filed Externally
evidence requirements.

## 6. Configure Business Trips

**Business Trip Settings** is site-wide. Set an explicit mileage rate only when
the company intentionally overrides the date-effective payroll travel rate. Set
Expense Claim Types and enable automatic claim creation only after HRMS/ERPNext
approver and expense masters are ready.

Configure active **Business Trip Region** rows with daily and incidental rates.
On a Draft Business Trip, the protected **Generate Allowances** action creates one
row per calendar day for the selected active region. Private-car journeys use
distance × mileage rate; other transport uses receipt amount. Accommodation and
other expenses are summed into Grand Total.

On submit, automatic Expense Claim creation creates a draft claim and resolves
the approver from Employee Expense Approver or the reporting manager's User. If
creation fails, Business Trip submission fails. Cancelling a trip deletes a linked
draft claim; a submitted claim must be cancelled first.

Test invalid dates, inactive/missing region, generation only in Draft, configured
rate versus date-effective fallback, private-car/receipt totals, approver
resolution, owner permissions, duplicate claim prevention, and cancellation.

## External filing limitations

This app has no direct Department of Employment and Labour, SETA, bargaining-
council, B-BBEE, or other labour portal integration. Printed/exported records are
working papers. The responsible practitioner must:

- select the current authority form/template and reporting period;
- reconcile source data to payroll/HR/finance records;
- obtain internal consultation and authorised sign-off;
- file through the authority's supported channel;
- retain the authority reference and private receipt/evidence; and
- document rejected, amended, late, or resubmitted outcomes.

## Production approval checklist

- Labour practitioner approves the exact enabled BCEA/leave/termination controls.
- Employment Equity practitioner approves designated-employer status, sector,
  target plan, reports, privacy suppression, and filing procedure.
- SDF/skills practitioner approves SETA, OFO/provider data, WSP/ATR, grant/levy
  reconciliation, and external evidence procedure.
- Payroll/accounts approve termination hand-off, travel tax treatment, and Expense
  Claim configuration.
- Information Officer/privacy owner approves roles, Company restrictions, private
  files, retention, exports, backups, and incident response.
- Business owner accepts all Controlled Manual limitations and parallel-test
  results before the feature-readiness status is promoted.

## Official verification anchors

- [Basic Conditions of Employment Act](https://www.labour.gov.za/DocumentCenter/Acts/Basic%20Conditions%20of%20Employment/Act%20-%20Basic%20Conditions%20of%20Employment.pdf)
- [2025 Employment Equity Regulations](https://www.labour.gov.za/DocumentCenter/Pages/Employment-Equity-%28EE%29-Regulations-.aspx)
- [2026 National Minimum Wage Gazette 54075 Notice 7083](https://www.gov.za/sites/default/files/gcis_document/202602/54075rg11941gon7083.pdf)
