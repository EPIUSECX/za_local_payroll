# SA Labour: BCEA, Skills, EE & Travel

The **SA Labour** module provides selected BCEA decision support, governed labour
references, Employment Equity working papers, WSP/ATR records, and Business Trip
management. It does not replace a labour practitioner, official form, or external
portal.

## BCEA leave controls

The Leave Application override applies only when the Leave Type has **Apply BCEA
Validation** enabled and an explicit **BCEA Leave Category**.

- Governed sick leave requires private medical-certificate evidence when an
  absence exceeds the configured threshold (never more permissive than two
  consecutive days), or is more than the second distinct occasion in eight weeks.
- Governed family-responsibility leave is capped at three days per 12-month
  service-anniversary cycle.
- A configured Applicable Gender is enforced.
- Workplace Injury leave requires category **Occupational Injury Leave**.
- The annual-leave 21-day message is informational, not an entitlement decision.

## BCEA leave standards

The app ships the BCEA minimums as reference data (`setup/data/bcea_leave_standards.json`,
each entitlement tied to a cited source) and builds from them on every migrate for a site
that has a South African company:

- **Leave Types** with the BCEA flag and category already set: Annual, Sick, Family
  Responsibility, Maternity, Parental, Adoption, Commissioning Parental and Occupational
  Injury, each named "... (BCEA)". They are inert until something allocates them. The
  maternity, parental, adoption and commissioning types are leave without pay, because the
  UIF Fund pays the benefit.
- **Draft Leave Policies** "SA BCEA Annual and Family Leave" for a 5-day and a 6-day week.
  A draft policy cannot be assigned. Submitting it is what enables it.

Existing Leave Types and Policies are never edited, and nothing is submitted or allocated
for you.

### Setting up a client

1. **Create the company policy:** `create_company_leave_policies(company, work_days_per_week,
   annual_days, family_days)`. Days default to the minimum (annual 15 days for a 5-day
   week and 18 for a 6-day week; family responsibility 3). A figure below the minimum is
   refused. An employer may grant more.
2. **Review and submit the policy.** A second person should submit it.
3. **Assign it on each employee's own cycle:** `assign_leave_policy_by_cycle(policy, company)`.
   The cycle runs 12 months from the date of joining, not the calendar or tax year. Use
   `dry_run=1` first. Annual leave accrues monthly on the day of joining and unused days
   expire 182 days after the cycle ends.
4. **Grant sick leave:** `allocate_sick_leave_by_cycle(company, work_days_per_week)`. Sick
   leave runs on a **36-month** cycle (30 days for a 5-day week, 36 for a 6-day week).
   Pass `already_taken` for sick leave used earlier in the cycle outside this system.

### Why sick leave is not in the policy

HRMS allows one submitted Leave Policy Assignment per employee for any overlapping period.
The 12-month annual cycle and the 36-month sick cycle overlap, so two policies cannot both
be assigned. Sick leave is granted as a direct Leave Allocation per employee instead.

### Decisions built in

- Sick leave grants the full cycle entitlement from day one. The Act gives one day per 26
  days worked in the first six months. Granting more is permitted, and modelling the ramp
  would need a scheduled top-up job.
- Family responsibility leave is refused until the employee has completed four months of
  service, and is capped at three days in the service-anniversary cycle.
- Not covered: part-time and variable-hours employees (the 1-in-17 rule), collective
  agreements and sectoral determinations that give more, the shared maternity and parental
  pool (below), and the earnings-threshold effects.

### Maternity, parental, adoption and commissioning leave

On 3 October 2025 the Constitutional Court (*Van Wyk v Minister of Employment and Labour*,
CCT 308/23) declared the BCEA parental-leave provisions invalid and set an interim regime,
suspended for 36 months, under which all parents share one pool of four months and ten
days. The app provides the leave types but does not track the shared pool. Treat the
entitlement as Controlled Manual and verify the current position before relying on it.

## Termination controls

**Employee Separation** requires an actual termination date and termination type.
It calculates service-based 7/14/28-day notice, operational-requirements severance
at one reviewed week per completed year, and governed annual-leave payout from
HRMS ledger days × reviewed daily remuneration. HR Manager/System Manager must
record and confirm the remuneration basis; Salary Structure base is not used as a
substitute. A protected action can create one Employee Final Settlement after
submission.

The practitioner must approve classification, alternatives/refusal, agreements,
notice treatment, remuneration, tax directive, certificate of service, and all
case-specific obligations.

## Labour and skills masters

| DocType | Purpose |
|---|---|
| **SETA** | Authority master linked from Company; requires a current source reference before governed use |
| **Skills Development Facilitator** | Company/effective-dated appointment with private appointment and independent-review evidence |
| **OFO Occupation** | Source-backed OFO code/version and effective dates |
| **Training Provider** | Provider registration and accreditation scope/dates/private evidence |
| **Bargaining Council** | Company/sector reference master |
| **Industry Specific Contribution** | Effective-dated sector contribution working reference |
| **Sectoral Minimum Wage** | Source-backed, independently reviewed Controlled Manual reference for exact worker category |
| **Business Trip Settings** | Site-wide mileage/Expense Claim configuration |
| **Business Trip Region** | Active region with daily and incidental allowance values |

Sectoral Minimum Wage never auto-assigns a worker category or blocks payroll.
Practitioners must review actual ordinary hours, inclusions/exclusions, sector/
bargaining rules, and special categories. For 1 March 2026, verification anchors
are R30.23/hour general NMW and R16.62/hour EPWP; qualifying learnerships use the
Schedule 2 allowance. Seeded references remain drafts until independently approved.

## WSP, ATR, and employee training

1. Submit a company-specific **Skills Development Facilitator** appointment with a
   different reviewer and private evidence.
2. Maintain source-backed **SETA**, **OFO Occupation**, and governed **Training
   Provider** records.
3. **Workplace Skills Plan** links Fiscal Year, SETA, submitted SDF, OFO/providers,
   and planned rows; it calculates the budget.
4. **Annual Training Report** must match a submitted WSP's Company/Fiscal Year/SETA
   and requires private completion evidence per row; it calculates actual spend.
5. **Skills Development Record** links individual training to the governed WSP,
   optional ATR, OFO, provider, dates, cost, and private completion evidence.

Frappe Submit records independent internal approval only. `Filed Externally`
requires reference, date, and private evidence on a draft/amended WSP or ATR. SETA
templates, consultation, grant/levy reconciliation, portal acceptance, and B-BBEE
points remain Controlled Manual; the app sets B-BBEE points to zero.

## Employment Equity working papers

Employee race, gender, occupational level, disability, service dates, and Company
drive the reports. Use **Employment Equity Target Plan** to record the exact sector/
EAP/employer-plan source and effective target rows with independent review. Record
appointments, promotions, demotions, transfers, and terminations as submitted
**Employment Equity Movement** evidence.

| Report | Basis |
|---|---|
| **EE Workforce Profile** | Active-at-date workforce composition |
| **EEA4 Income Differential Statement** | Latest effective submitted Salary Structure Assignment base; monthly proxy. Working paper for the EEA4 form |
| **EE Plan Progress** | Active-at-date headcount compared with latest effective rows of one submitted target plan; supports the EEA2 report |
| **EE Workforce Movement** | Aggregated submitted movement records for a date range |

These are not certified EEA forms. Company/date filters and permissions are
mandatory. Positive cells below the configured threshold (default five) are
suppressed. Revealing them needs ZA Compliance Reviewer or Manager (or System Manager) **and** Employee read
access, so grant Employee read only to the named EE reviewer. An HR Manager without the reviewer role cannot
reveal small cells. The preparer of a target plan cannot submit it; a ZA Compliance Reviewer does.

The Employment Equity Amendment Act baseline is 1 January 2025; the 18-sector
numerical-target regulations commenced on 15 April 2025 and the current five-year
period ends 31 August 2030. An EE practitioner must approve designated-employer
status, EEA17 sector, EAP/target basis, annual goals, reasonable grounds, form
version, external filing, and compliance evidence.

## Business Trips

**Business Trip** totals daily/incidental allowances, private-car mileage, other
transport receipts, accommodation, and other expenses. Generate Allowances works
only in Draft and requires an active region. Private-car mileage uses the explicit
site-wide setting when present, otherwise the date-effective payroll travel rate.

When enabled, submission creates a draft Expense Claim and resolves the approver
from Employee Expense Approver or the reporting manager's User. Failure aborts the
trip submission. Company policy, receipts, approval, tax treatment, and payment
remain HR/payroll/accounts responsibilities.

## Privacy and approval gate

Race, disability, remuneration, training, and evidence are restricted personal
information. Apply Company User Permissions, permission level 1, private files,
small-cell suppression, retention, and tested cross-company denial.

Before production, obtain recorded labour, Employment Equity, SDF/skills,
payroll/accounts, privacy, and business-owner approval. External DEL, SETA,
bargaining-council, and B-BBEE processes remain Controlled Manual.

## Next

Configure [SA COIDA](sa-coida) for Return of Earnings and injury/claim working
papers.
