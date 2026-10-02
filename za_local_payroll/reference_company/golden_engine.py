"""Independent South African payroll expectation engine (SARS method).

Pure Python by design: no Frappe and no za_local_payroll imports. Inputs are the
persona definitions, the variable-pay schedule and the golden statutory dataset
built from archived official SARS / DEL / Compensation Fund publications.

Method (Fourth Schedule para 9 average method, as applied in the SARS tax
deduction tables): the year-to-date balance of remuneration is annualised over
the periods paid; tax on that annual equivalent less rebates is pro-rated to the
periods paid; annual payments are taxed in full at the marginal rate when paid;
the medical scheme fees tax credit is allowed for each month of membership;
retirement fund contributions are deductible up to the lesser of 27.5% of
remuneration and the annual monetary cap.
"""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

GOLDEN = Path("/home/user/za_evidence/golden/golden_statutory_2026_27.json")  # standalone default


def d(value: str) -> date:
	y, m, dd = (int(x) for x in value.split("-"))
	return date(y, m, dd)


def bracket_tax(income: float, brackets) -> float:
	if income <= 0:
		return 0.0
	for lower, upper, base, rate in brackets:
		if upper is None or income <= upper:
			return base + (income - lower) * rate / 100
	return 0.0


def age_on(dob: date, when: date) -> int:
	return when.year - dob.year - ((when.month, when.day) < (dob.month, dob.day))


@dataclass
class Month:
	"""Golden inputs and outputs for one employee pay period."""

	period: str
	regular: float = 0.0  # PAYE-included periodic remuneration (after inclusion %)
	annual: float = 0.0  # annual payments taxed in full
	cash_earnings: float = 0.0  # cash earnings paid (gross on slip)
	uif_basis: float = 0.0
	sdl_remuneration: float = 0.0
	retirement: float = 0.0
	other_deductions: float = 0.0
	lump_sum_tax: float = 0.0
	employer_pension: float = 0.0
	medical_member: bool = False
	medical_dependants: int = 0
	eti_remuneration: float = 0.0
	out: dict = field(default_factory=dict)


class GoldenEngine:
	def __init__(self, golden_path: Path = GOLDEN):
		self.g = json.loads(golden_path.read_text())
		self.ty = self.g["tax_years"]["2026-2027"]
		self.tax_year_end = d(self.ty["effective_to"])

	# ---- statutory helpers -------------------------------------------------
	def rebates(self, dob: date) -> float:
		age = age_on(dob, self.tax_year_end)
		r = self.ty["rebates"]
		return r["primary"] + (r["secondary"] if age >= 65 else 0) + (r["tertiary"] if age >= 75 else 0)

	def mtc_monthly(self, dependants: int) -> float:
		m = self.ty["medical_tax_credit_monthly"]
		return (
			m["main"]
			+ (m["first_dependant"] if dependants >= 1 else 0)
			+ m["additional"] * max(0, dependants - 1)
		)

	def official_rate(self, day: date) -> float:
		for start, end, rate in self.ty["official_interest_rate"]:
			if d(start) <= day and (end is None or day <= d(end)):
				return rate
		raise ValueError(f"No official rate for {day}")

	def loan_benefit(self, balance, actual_rate, start: date, end: date) -> float:
		total = 0.0
		day = start
		while day <= end:
			days_in_year = 366 if calendar.isleap(day.year) else 365
			total += balance * max(0, self.official_rate(day) - actual_rate) / 100 / days_in_year
			day += timedelta(days=1)
		return round(total, 2)

	def eti(self, remuneration: float, qualifying_month: int, hours: float) -> float:
		if qualifying_month < 1 or qualifying_month > 24 or hours <= 0:
			return 0.0
		ratio = min(1.0, hours / self.g["eti"]["standard_hours"])
		r = remuneration / ratio
		first = qualifying_month <= 12
		if r < 2500:
			amount = r * (0.60 if first else 0.30)
		elif r < 5500:
			amount = 1500 if first else 750
		elif r < 7500:
			amount = (1500 - 0.75 * (r - 5500)) if first else (750 - 0.375 * (r - 5500))
		else:
			amount = 0.0
		return round(max(0.0, amount) * ratio, 2)

	# ---- PAYE / UIF / SDL for one employee's year ---------------------------
	def run_employee(
		self,
		dob: date,
		months: list[Month],
		periods_in_year: int = 12,
		uif_cap=None,
		eti_hours: float = 0,
		eti_first_month: int | None = None,
	) -> list[Month]:
		uif_cap = uif_cap if uif_cap is not None else self.g["uif"]["monthly_ceiling"]
		ret = self.ty["retirement"]
		paid = 0.0
		reg_ytd = ann_ytd = ret_ytd = 0.0
		mtc_to_date = 0.0
		for k, m in enumerate(months, start=1):
			reg_ytd += m.regular
			ann_ytd += m.annual
			ret_ytd += m.retirement
			ae = reg_ytd / k * periods_in_year
			contrib_annual = ret_ytd / k * periods_in_year
			allowed = min(contrib_annual, ret["percentage"] / 100 * (ae + ann_ytd), ret["annual_cap"])
			taxable = ae - allowed
			if m.medical_member:
				mtc_to_date += self.mtc_monthly(m.medical_dependants) * 12 / periods_in_year
			regular_tax = bracket_tax(taxable, self.ty["paye_brackets"]) - self.rebates(dob)
			liability = max(0.0, regular_tax * k / periods_in_year - mtc_to_date) if regular_tax > 0 else 0.0
			annual_tax = (
				(
					bracket_tax(taxable + ann_ytd, self.ty["paye_brackets"])
					- bracket_tax(taxable, self.ty["paye_brackets"])
				)
				if ann_ytd
				else 0.0
			)
			cumulative = liability + annual_tax
			paye = max(0.0, round(cumulative - paid, 2))
			paid += paye
			uif = round(min(m.uif_basis, uif_cap) * self.g["uif"]["employee_rate"] / 100, 2)
			allowed_month = m.retirement * (allowed / contrib_annual) if contrib_annual else 0.0
			sdl = round(max(0.0, m.sdl_remuneration - allowed_month) * self.g["sdl"]["rate"] / 100, 2)
			net = round(m.cash_earnings - paye - uif - m.retirement - m.other_deductions - m.lump_sum_tax, 2)
			m.out = {
				"annual_equivalent": round(ae, 2),
				"retirement_allowed_annual": round(allowed, 2),
				"taxable_annual": round(taxable, 2),
				"rebates": self.rebates(dob),
				"mtc_to_date": round(mtc_to_date, 2),
				"paye": paye,
				"uif_employee": uif,
				"uif_employer": uif,
				"sdl": sdl,
				"net_pay": net,
				"employer_cost": round(m.cash_earnings + uif + sdl + m.employer_pension, 2),
			}
		return months
