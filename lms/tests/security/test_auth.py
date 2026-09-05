import frappe
from frappe.tests.test_api import FrappeAPITestCase

from lms.auth import authenticate
from lms.lms.test_helpers import BaseTestUtils


class TestAuth(BaseTestUtils, FrappeAPITestCase):
	def setUp(self):
		super().setUp()
		# //// Neoffice — lms.auth.authenticate() is a no-op unless the site config
		# //// carries block_endpoints; upstream's own CI sets it with `bench set-config`,
		# //// our reusable workflow does not, so the test sets (and restores) it itself.
		self._block_endpoints_before = frappe.conf.get("block_endpoints")
		frappe.conf.block_endpoints = 1
		self.normal_user = self._create_user("normal-user@example.com", "Normal", "User", ["LMS Student"])

	def test_allowed_path(self):
		frappe.form_dict.cmd = "ping"
		frappe.session.user = self.normal_user.name
		authenticate()
		frappe.session.user = "Administrator"

	def test_not_allowed_path(self):
		frappe.form_dict.cmd = "frappe.auth.get_logged_user"
		frappe.session.user = self.normal_user.name
		self.assertRaises(frappe.PermissionError, authenticate)
		frappe.session.user = "Administrator"

	def tearDown(self):
		frappe.conf.block_endpoints = self._block_endpoints_before
		super().tearDown()
