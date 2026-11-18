"""The shipped Sidebar and Dock files are what the module-first desk renders."""

import json
from pathlib import Path

import frappe
from frappe.tests.classes import UnitTestCase


class TestShippedNavigation(UnitTestCase):
	def _app(self):
		return Path(frappe.get_app_path("za_local_payroll"))

	def _sidebars(self):
		return [
			json.loads(p.read_text(encoding="utf-8")) for p in sorted(self._app().glob("*/sidebar/*/*.json"))
		]

	def test_there_is_a_sidebar_for_each_module(self):
		modules = {
			line for line in (self._app() / "modules.txt").read_text(encoding="utf-8").split("\n") if line
		}
		self.assertEqual(modules, {sidebar["module"] for sidebar in self._sidebars()})

	def test_rows_open_in_the_current_tab(self):
		for sidebar in self._sidebars():
			for row in sidebar["items"]:
				self.assertFalse(
					row.get("open_in_new_tab"), f"{sidebar['title']}: '{row['label']}' opens in a new tab"
				)

	def test_every_sidebar_has_a_rail_entry_with_a_duotone_icon(self):
		dock = json.loads(
			(self._app() / "dock" / "za_local_payroll" / "za_local_payroll.json").read_text(encoding="utf-8")
		)
		self.assertEqual(
			"za_local_core", dock.get("mount_on"), "This app's rail entries belong on core's rail"
		)
		entries = {row["link_to"]: row for row in dock["items"] if row["link_type"] == "Sidebar"}
		for sidebar in self._sidebars():
			self.assertIn(sidebar["title"], entries)
			self.assertTrue(entries[sidebar["title"]]["icon"].endswith("-duotone"))
			self.assertTrue(sidebar["header_icon"].endswith("-duotone"))

	def test_every_report_is_reachable_from_a_sidebar(self):
		linked = {row.get("link_to") for sidebar in self._sidebars() for row in sidebar["items"]}
		for path in self._app().glob("*/report/*/*.json"):
			if path.stem != path.parent.name:
				continue
			report = json.loads(path.read_text(encoding="utf-8"))
			self.assertIn(report["report_name"], linked, f"{report['report_name']} is not in a sidebar")
