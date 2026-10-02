"""Every role a setup checklist is shown to can open every step it is sent to.

Walking the checklists in the Desk as their own roles found the Accounts Manager
sent to statutory sources it could not read, the Payroll Manager to Payroll
Settings and a report it could not open, and the Payroll Manager not shown the
payroll checklist at all.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase
from za_local_core.onboarding import localisation_onboardings

# Steps that are System Manager work by design. A checklist may show them to
# other roles, who then hand them to an administrator.
SYSTEM_MANAGER_STEPS = {
	"Assign the ZA Compliance Roles": "Roles are assigned on User, which only a System Manager administers.",
	"Publish the Practitioner Guides": "Publishing writes Wiki pages for the whole site.",
}


class TestSetupChecklists(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.users = {}

	def _user(self, role):
		if role in self.users:
			return self.users[role]
		email = f"_test.checklist.{frappe.scrub(role)}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": role, "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		user.roles = []
		user.append("roles", {"role": role})
		user.save(ignore_permissions=True)
		self.users[role] = email
		return email

	def _can_open(self, step, user):
		if step.action == "View Report":
			with self.set_user(user):
				return frappe.get_doc("Report", step.reference_report).is_permitted()
		ptype = "create" if step.action == "Create Entry" else "read"
		return frappe.has_permission(step.reference_document, ptype, user=user)

	def test_payroll_checklist_is_shown_to_payroll_managers(self):
		roles = frappe.get_doc("Module Onboarding", "SA Payroll Onboarding").get_allowed_roles()
		self.assertIn("Payroll Manager", roles)

	def test_every_role_shown_a_checklist_can_open_its_steps(self):
		onboardings = localisation_onboardings()
		self.assertEqual(5, len(onboardings))
		failures = []
		for name in onboardings:
			onboarding = frappe.get_doc("Module Onboarding", name)
			roles = [
				role
				for role in onboarding.get_allowed_roles()
				if role not in ("System Manager", "Administrator")
			]
			for row in onboarding.steps:
				step = frappe.get_doc("Onboarding Step", row.step)
				if step.name in SYSTEM_MANAGER_STEPS or not (
					step.reference_document or step.reference_report
				):
					continue
				for role in roles:
					if not self._can_open(step, self._user(role)):
						failures.append(f"{name}: {role} cannot open '{step.title}'")
		self.assertEqual([], failures)

	def test_checklist_steps_say_what_to_do(self):
		"""The panel shows the action label, so it must be the step's own instruction."""
		for name in localisation_onboardings():
			for row in frappe.get_doc("Module Onboarding", name).steps:
				step = frappe.get_doc("Onboarding Step", row.step)
				self.assertEqual(step.title, step.action_label, step.name)
