# Support

## Supported technical scope

Support targets the pinned Frappe, ERPNext and HRMS v16 release line with
`za_local_core` and `za_local_payroll` installed. Include release tags/framework
commits, company currency, payroll period/frequency, sanitised component metadata,
expected and actual calculations, and a complete traceback.

The supported application boundary is documented in [README.md](README.md). In
particular:

- SARS employer records are controlled internal working papers, not direct filing
  or PAYE BRS import files;
- only the identified FNB Online Banking Enterprise CSV adapter is available;
- unsupported bank, filing and benefit formats remain disabled or Preview; and
- the legacy `za_local` and extracted payroll engines must not both be active.

## Production support prerequisites

A deployment is supportable for live payroll only when its release record holds:

- approved statutory sources, rates and component/SARS-code mappings;
- employer/practitioner sign-off of employee facts, ETI, retirement, medical and
  fringe-benefit treatments;
- reconciled representative parallel payroll cycles;
- finance approval of payroll, employer-contribution and liability GL postings;
- FNB test acceptance plus bank-portal maker/checker and statement evidence;
- SARS working-paper-to-filing/payment reconciliation evidence; and
- tested encrypted backup, restore and rollback procedures.

Automated tests show that encoded rules execute consistently; they do not certify
that a deployment is legally compliant or that its source data is true.

## Data handling

Never attach production employee, medical, banking, tax, certificate, filing or
backup data to public support channels. Reproduce on a sanitised disposable site.
Security reports follow [SECURITY.md](SECURITY.md).
