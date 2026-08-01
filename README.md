# SA Localisation Payroll

South African payroll localisation for PAYE, UIF, SDL, ETI, benefits, employer declarations, and payment controls on Frappe HRMS.

Runtime dependencies are Frappe/ERPNext/HRMS v16 and `za_local_core`. The app preserves existing SA Payroll DocType names and database tables so the monolithic `za_local` data can be transferred in place.

See the [detailed migration and compliance plan](MIGRATION_PLAN.md).

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
bench get-app $ZA_LOCAL_CORE_REPO --branch main
bench --site $SITE_NAME install-app za_local_core
bench get-app $URL_OF_THIS_REPO --branch main
bench --site $SITE_NAME install-app za_local_payroll
```

Do not enable both payroll engines. While `za_local` remains installed, this app deliberately suppresses its duplicate controller, client-script, and scheduler hooks. Follow [MIGRATION_PLAN.md](MIGRATION_PLAN.md) for inventory, shadow calculation, cutover, rollback, and practitioner sign-off requirements.

The packaged statutory rates and filing mappings require annual source verification and payroll-practitioner approval before a production tax year is opened. Unsupported SARS BRS exports and unsupported bank formats fail explicitly instead of presenting a generic file as an accepted filing/payment format.

## Safe validation

The repository supports non-mutating checks from the bench container:

```bash
python -m compileall -q apps/za_local_payroll/za_local_payroll
uvx ruff check apps/za_local_payroll/za_local_payroll
```

Site lifecycle and end-to-end payroll tests must run on a disposable test-site copy; do not run them against a production payroll site.

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/za_local_payroll
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

## License

MIT
