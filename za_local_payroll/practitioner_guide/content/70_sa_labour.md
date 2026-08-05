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

The app does not automate the full sick-leave cycle, family-responsibility
eligibility/events, maternity/parental/adoption entitlements, hours-of-work rules,
earnings-threshold effects, collective agreements, or annual-leave allocation.
Those remain Preview/Controlled Manual.

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

| Compatibility report name | Actual implemented basis |
|---|---|
| **EE Workforce Profile** | Active-at-date workforce composition |
| **EEA2 Income Differentials** | Latest effective submitted Salary Structure Assignment base; monthly proxy |
| **EEA4 Employment Equity Plan** | Active-at-date headcount compared with latest effective rows of one submitted target plan |
| **EE Workforce Movement** | Aggregated submitted movement records for a date range |

These are not certified EEA forms. Company/date filters and permissions are
mandatory. Positive cells below the configured threshold (default five) are
suppressed; only ZA Compliance Reviewer/Manager or System Manager may reveal them.

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
