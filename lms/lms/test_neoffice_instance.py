# //// Neoffice — added file (no upstream equivalent): the rules of the InstanceLink address.
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
