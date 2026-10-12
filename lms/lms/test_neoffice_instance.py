# //// Neoffice — added file (no upstream equivalent): the rules of the InstanceLink address.
from unittest.mock import patch as unittest_patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms import neoffice_instance as ni


class TestInstanceLinkAddress(UnitTestCase):
	def tearDown(self):
		for key in ("neoffice_lms_mode", "neoffice_lms_allowed_domains"):
			frappe.conf.pop(key, None)

	def test_path_is_a_desk_path_of_a_doctype(self):
		for path in ("/app/item", "/app/item/new", "/app/nora-demo/new", "/app/quotation/view/list"):
			self.assertTrue(ni.is_allowed_path(path), path)
		for path in (
			"/app/item?x=1",
			"/app/item#a",
			"/app/item/DOC-1",
			"/api/method/frappe.ping",
			"/login",
			"//evil.example/app/item",
			"https://evil.example/app/item",
			"/app/Item",
			"/app/item/../user",
			"",
			None,
			12,
		):
			self.assertFalse(ni.is_allowed_path(path), path)

	def test_origin_must_be_https_under_an_allowed_domain(self):
		self.assertEqual(ni.clean_origin("https://dmis.neoffice.me"), "https://dmis.neoffice.me")
		self.assertEqual(ni.clean_origin(" https://DMIS.neoffice.me/ "), "https://dmis.neoffice.me")
		self.assertEqual(ni.clean_origin("https://cabinet.neoffice.ch"), "https://cabinet.neoffice.ch")
		for url in (
			"http://dmis.neoffice.me",
			"https://dmis.neoffice.me/app",
			"https://dmis.neoffice.me:8000",
			"https://user:pw@dmis.neoffice.me",
			"https://dmis.neoffice.me.evil.example",
			"https://neoffice.me",
			"https://evilneoffice.me",
			"https://client.example.com",
			"javascript:alert(1)",
			"",
			None,
		):
			self.assertIsNone(ni.clean_origin(url), url)

	def test_the_list_of_domains_comes_from_the_site_config(self):
		frappe.conf["neoffice_lms_allowed_domains"] = [".client-example.ch"]
		self.assertEqual(ni.clean_origin("https://erp.client-example.ch"), "https://erp.client-example.ch")
		self.assertIsNone(ni.clean_origin("https://dmis.neoffice.me"))

	def test_build_url(self):
		self.assertEqual(ni.build_url("", "/app/item/new"), "/app/item/new")
		self.assertEqual(ni.build_url("https://dmis.neoffice.me", "/app/item/new"), "https://dmis.neoffice.me/app/item/new")
		self.assertIsNone(ni.build_url("", "/login"))
		self.assertIsNone(ni.build_url("https://evil.example", "/app/item"))
		self.assertIsNone(ni.build_url("https://dmis.neoffice.me", "/app/item?x=1"))

	def test_a_site_is_a_hub_unless_it_says_it_is_an_instance(self):
		self.assertEqual(ni.hosting_mode(), "hub")
		frappe.conf["neoffice_lms_mode"] = "Instance"
		self.assertEqual(ni.hosting_mode(), "instance")
		self.assertEqual(ni.get_instance_base(), {"mode": "local", "base": ""})

	def test_nobody_is_linked_yet_on_a_hub(self):
		self.assertEqual(ni.get_instance_base(), {"mode": "none", "base": ""})


class TestFiduciaryDoor(UnitTestCase):
	"""Door B: the staff of an accounting firm chooses a client and the hub opens it."""

	OPTIONS = [
		{"instance": "SRV-0029", "label": "Osiris SA", "host": "osiris.neoffice.me"},
		{"instance": "SRV-0072", "label": "DMIS SA", "host": "dmis.ch"},
	]
	LINK = "https://osiris.neoffice.me/api/method/neoffice_theme.sso.sso_login?token=t"

	def setUp(self):
		self.original_user = frappe.session.user
		self.calls = []
		frappe.local.response = frappe._dict()

	def tearDown(self):
		frappe.set_user(self.original_user)
		frappe.conf.pop("neoffice_lms_mode", None)

	def hooks(self, options=None, link=None):
		def list_instances():
			return self.OPTIONS if options is None else options

		def open_url(instance, path):
			self.calls.append((instance, path))
			return link or self.LINK

		self.fake_instances, self.fake_open = list_instances, open_url
		module = "lms.lms.test_neoffice_instance"
		original = frappe.get_hooks
		hooks = {
			"neoffice_lms_fiduciary_instances": [f"{module}.FIDUCIARY_INSTANCES"],
			"neoffice_lms_fiduciary_open": [f"{module}.FIDUCIARY_OPEN"],
		}
		globals()["FIDUCIARY_INSTANCES"], globals()["FIDUCIARY_OPEN"] = list_instances, open_url
		return unittest_patch.object(
			frappe, "get_hooks", lambda name=None, *a, **k: hooks[name] if name in hooks else original(name, *a, **k)
		)

	def test_a_person_with_clients_is_offered_them_instead_of_nothing(self):
		with self.hooks():
			frappe.set_user("Administrator")
			base = ni.get_instance_base()
		self.assertEqual(base, {"mode": "fiduciary", "base": "", "options": self.OPTIONS})

	def test_a_guest_and_a_person_without_clients_are_offered_nothing(self):
		with self.hooks():
			frappe.set_user("Guest")
			self.assertEqual(ni.get_instance_base(), {"mode": "none", "base": ""})
		with self.hooks(options=[]):
			frappe.set_user("Administrator")
			self.assertEqual(ni.get_instance_base(), {"mode": "none", "base": ""})

	def test_nothing_is_offered_when_the_course_lives_on_an_instance(self):
		frappe.conf["neoffice_lms_mode"] = "instance"
		with self.hooks():
			frappe.set_user("Administrator")
			self.assertEqual(ni.get_instance_base(), {"mode": "local", "base": ""})

	def test_the_options_are_cleaned(self):
		with self.hooks(options=[{"instance": " SRV-1 ", "label": "x" * 300}, {"label": "no id"}, {"instance": ""}]):
			frappe.set_user("Administrator")
			options = ni.fiduciary_options()
		self.assertEqual(len(options), 1)
		self.assertEqual((options[0]["instance"], len(options[0]["label"]), options[0]["host"]), ("SRV-1", 140, ""))

	def test_the_chosen_client_is_opened_through_the_hub(self):
		with self.hooks():
			frappe.set_user("Administrator")
			ni.open_instance("SRV-0029", "/app/nora-demo/new")
		self.assertEqual(self.calls, [("SRV-0029", "/app/nora-demo/new")])
		self.assertEqual(frappe.local.response["type"], "redirect")
		self.assertEqual(frappe.local.response["location"], self.LINK)

	def test_a_client_the_hub_did_not_offer_this_person_is_never_opened(self):
		with self.hooks():
			frappe.set_user("Administrator")
			for instance in ("SRV-9999", "", None, "SRV-0029 "):
				frappe.local.response = frappe._dict()
				ni.open_instance(instance, "/app/item/new")
				self.assertEqual(frappe.local.response.get("http_status_code"), 403, instance)
		self.assertEqual(self.calls, [])

	def test_only_desk_paths_are_opened(self):
		with self.hooks():
			frappe.set_user("Administrator")
			for path in ("/login", "/app/item?x=1", "https://evil.example", "/app/item/DOC-1", "", None):
				frappe.local.response = frappe._dict()
				ni.open_instance("SRV-0029", path)
				self.assertEqual(frappe.local.response.get("http_status_code"), 403, path)
		self.assertEqual(self.calls, [])

	def test_a_link_that_is_not_the_signed_door_of_an_instance_is_refused(self):
		for link in ("http://osiris.neoffice.me/api/method/neoffice_theme.sso.sso_login?token=t", "https://evil.example/", "/app", None):
			with self.hooks(link=link):
				frappe.set_user("Administrator")
				frappe.local.response = frappe._dict()
				ni.open_instance("SRV-0029", "/app/item")
				self.assertEqual(frappe.local.response.get("http_status_code"), 403, link)
				self.assertNotEqual(frappe.local.response.get("type"), "redirect")

	def test_a_guest_cannot_open_anything(self):
		with self.hooks():
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				ni.open_instance("SRV-0029", "/app/item")
		self.assertEqual(self.calls, [])

	def test_the_hubs_refusal_is_a_plain_page(self):
		def refuse(instance, path):
			raise frappe.PermissionError("You do not have access to this client.")

		with self.hooks():
			globals()["FIDUCIARY_OPEN"] = refuse
			frappe.set_user("Administrator")
			ni.open_instance("SRV-0029", "/app/item")
		self.assertEqual(frappe.local.response.get("http_status_code"), 403)
		self.assertNotEqual(frappe.local.response.get("type"), "redirect")
