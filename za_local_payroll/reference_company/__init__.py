"""Synthetic South African reference-company harness.

Recreates the Cohenix ZA Localisation Reference Company on a disposable
developer-mode ``*.test`` site so the full za_local suite can be configured,
exercised and reconciled from a clean installation. Every record it creates is
fictional. It never runs on a production site and is not called by any install,
migrate or patch hook.

Entry point::

    bench --site <site>.test execute za_local_payroll.reference_company.run.run_all
"""
