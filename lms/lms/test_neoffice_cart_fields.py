# //// Neoffice — added file (no upstream equivalent): the course-offer fields of a sales line show only on a line
# //// that sells a course (maintenance#1469). Every invoice, order and quotation line showed « Mois d'accès » at 0.
import frappe
from frappe.tests.utils import FrappeTestCase

from lms.lms import neoffice_commerce as commerce


class TestTheCourseFieldsShowOnlyOnACourseLine(FrappeTestCase):
	def test_both_fields_wait_for_an_offer_on_every_sales_line(
		self,
	):  # role-check: ok run by after_migrate, not a user
		commerce.setup_cart_fields()
		for doctype in commerce.CART_DOCTYPES:
			for fieldname in ("lms_offer", "lms_months"):
				depends_on = frappe.db.get_value(
					"Custom Field", {"dt": doctype, "fieldname": fieldname}, "depends_on"
				)
				self.assertEqual(depends_on, "eval:doc.lms_offer", f"{doctype}.{fieldname}")

	def test_an_existing_field_gets_the_condition_at_the_next_migrate(
		self,
	):  # role-check: ok run by after_migrate
		name = frappe.db.get_value("Custom Field", {"dt": "Sales Invoice Item", "fieldname": "lms_months"})
		commerce.setup_cart_fields()
		name = name or frappe.db.get_value(
			"Custom Field", {"dt": "Sales Invoice Item", "fieldname": "lms_months"}
		)
		frappe.db.set_value("Custom Field", name, "depends_on", None)
		commerce.setup_cart_fields()
		self.assertEqual(frappe.db.get_value("Custom Field", name, "depends_on"), "eval:doc.lms_offer")
