# //// Neoffice — added file (no upstream equivalent)
# //// « One item, one offer » seen from the course (neoffice-maintenance#1074).
# //// A course designates the article it is sold under in its own « Article » field (`LMS Course.neo_item`). The guard read only the old
# //// direction (`Item.lms_course`), which stays empty on a site that moved to this field: a course could take the article of a bookable
# //// service without a word. The act is played by a Course Creator, the person who does it.
# //// The bookable service belongs to another app (`Booking Profile`): a site without it has no such guard to test and these tests skip.

import unittest

import frappe
from frappe.tests.roles import as_role
from frappe.tests.utils import FrappeTestCase

ITEM = "_Test One Offer Bookable"
FREE = "_Test One Offer Free"


def _the_bookings_are_here():
	return frappe.db.exists("DocType", "Booking Profile") and frappe.get_meta("LMS Course").has_field("neo_item")


@unittest.skipUnless(_the_bookings_are_here(), "Booking Profile (the bookings app) is not on this site")
class TestOneItemOneOfferFromTheCourse(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from neoffice_theme.tests import salon_fixture as fx

		cls.creator = fx.an_account_with("one-offer-creator", "Course Creator")
		provider = fx.a_user("one-offer-provider")
		fx.a_service(ITEM, {provider: [(fx.MONDAY, "09:00", "12:00")]})
		fx.an_item(FREE)

	def _the_course(self, item):
		return frappe.get_doc(
			{
				"doctype": "LMS Course",
				"title": "_Test One Offer Course",
				"short_introduction": "A filmed programme",
				"description": "<p>A filmed programme</p>",
				"instructors": [{"instructor": self.creator}],
				"neo_item": item,
			}
		)

	def test_a_course_on_the_article_of_a_bookable_service_is_refused(self):
		with as_role(self.creator):
			with self.assertRaises(frappe.ValidationError) as caught:
				self._the_course(ITEM).insert()
		self.assertIn("already bookable", str(caught.exception))
		self.assertFalse(frappe.db.exists("LMS Course", {"neo_item": ITEM}))

	def test_a_course_on_a_free_article_is_still_made(self):
		with as_role(self.creator):
			course = self._the_course(FREE).insert()
		self.assertEqual(course.neo_item, FREE)
