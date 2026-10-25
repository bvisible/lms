# //// Neoffice — added file (no upstream equivalent): the public courses page, its switch, its
# //// menu entry and the guard of the SPA (maintenance#1860). Modelled on the careers page tests of
# //// hrms (TestThePageAndTheMenu): one truth table, then each consequence of it.
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint

from lms.lms import neoffice_commerce as commerce
from lms.www import nos_formations, our_courses
from lms.www._lms import get_context as spa_context

URL = commerce.COURSES_URL
LEGACY = commerce.LEGACY_COURSES_URL


def _menu_urls():
	return [r.url for r in frappe.get_doc("Website Settings").get("top_bar_items") or []]


def _clear_menu_of_the_courses():
	settings = frappe.get_doc("Website Settings")
	for row in [r for r in settings.get("top_bar_items") or [] if r.url in (URL, LEGACY)]:
		settings.remove(row)
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)


def _set_switch(value):
	frappe.db.set_single_value("LMS Settings", "neo_show_on_website", value)


def _published(count):
	return patch("frappe.db.count", return_value=count)


class CoursesPageTestCase(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()


class TestTheRule(CoursesPageTestCase):
	def test_the_page_is_shown_only_with_the_switch_and_a_published_course(self):
		cases = [
			(1, 3, True),
			(1, 0, False),
			(0, 3, False),
			(0, 0, False),
		]
		for switch, published, expected in cases:
			_set_switch(switch)
			with _published(published):
				self.assertEqual(commerce.showing_courses(), expected, (switch, published))

	def test_the_state_says_why_the_page_is_hidden(self):
		_set_switch(1)
		with _published(0):
			state = commerce.courses_page_state()
		self.assertTrue(state["enabled"])
		self.assertFalse(state["open"])
		self.assertEqual(state["published"], 0)
		self.assertTrue(state["url"].endswith(URL))

		_set_switch(0)
		with _published(2):
			state = commerce.courses_page_state()
		self.assertFalse(state["enabled"])
		self.assertFalse(state["open"])
		self.assertEqual(state["published"], 2)

	def test_the_settings_form_receives_the_state_when_it_opens(self):
		_set_switch(1)
		doc = frappe.get_single("LMS Settings")
		doc.run_onload()
		state = doc.get("__onload").get("courses_page")
		self.assertIn("published", state)
		self.assertIn("enabled", state)

	def test_the_status_line_is_under_the_switch_and_the_videos_follow_it(self):
		fields = {f["fieldname"]: f for f in commerce.SETTINGS_FIELDS["LMS Settings"]}
		self.assertEqual(fields["neo_page_status"]["fieldtype"], "HTML")
		self.assertEqual(fields["neo_page_status"]["insert_after"], "neo_show_on_website")
		self.assertEqual(fields["neo_video_section"]["insert_after"], "neo_page_status")


class TestTheGuardOfTheSpa(CoursesPageTestCase):
	"""/lms serves the first course being created, the learners and the apps' entries: only a guest is refused."""

	def refused(self, app_path, user="Guest", guest_access=1, shown=False):
		frappe.set_user(user)
		frappe.db.set_single_value("LMS Settings", "allow_guest_access", guest_access)
		with patch.object(commerce, "showing_courses", return_value=shown):
			return commerce.guest_gets_page_not_found(app_path)

	def test_a_guest_is_refused_on_the_home_and_the_list_of_a_site_with_no_course(self):
		for app_path in (None, "", "courses", "courses/", "/courses"):
			self.assertTrue(self.refused(app_path), app_path)

	def test_a_guest_sees_the_list_when_the_site_shows_its_courses(self):
		for app_path in (None, "courses"):
			self.assertFalse(self.refused(app_path, shown=True), app_path)

	def test_a_signed_in_user_is_never_refused(self):
		for app_path in (None, "courses", "courses/new/edit"):
			self.assertFalse(self.refused(app_path, user="Administrator"), app_path)

	def test_a_deeper_address_is_a_deliberate_link_and_is_left_alone(self):
		for app_path in ("courses/some-course", "courses/some-course/learn/1.1", "batches", "programs"):
			self.assertFalse(self.refused(app_path), app_path)

	def test_a_site_without_guest_access_keeps_its_sign_in_redirect(self):
		# the SPA sends a guest to /login by itself; a 404 would take that from an invited learner
		self.assertFalse(self.refused("courses", guest_access=0))

	def test_the_spa_answers_page_not_found_to_a_guest_and_serves_a_signed_in_user(self):
		frappe.db.set_single_value("LMS Settings", "allow_guest_access", 1)
		frappe.form_dict.app_path = "courses"
		with (
			patch.object(commerce, "showing_courses", return_value=False),
			patch("lms.www._lms.get_boot", return_value=frappe._dict()),
			patch("lms.www._lms.capture"),
		):
			frappe.set_user("Guest")
			with self.assertRaises(frappe.DoesNotExistError):
				spa_context()
			frappe.set_user("Administrator")
			context = spa_context()
		self.assertIn("meta", context)
		frappe.form_dict.pop("app_path", None)


class TestThePublicPage(CoursesPageTestCase):
	def test_the_page_answers_page_not_found_when_the_site_does_not_show_its_courses(self):
		with patch.object(our_courses, "showing_courses", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				our_courses.get_context(frappe._dict())

	def test_the_page_lists_the_courses_when_the_site_shows_them(self):
		with patch.object(our_courses, "showing_courses", return_value=True):
			context = our_courses.get_context(frappe._dict())
		self.assertIn("free_courses", context)
		self.assertIn("paid_courses", context)

	def test_the_category_filter_is_read_from_the_english_parameter(self):
		frappe.form_dict.category = "No such category"
		try:
			with patch.object(our_courses, "showing_courses", return_value=True):
				context = our_courses.get_context(frappe._dict())
			self.assertIsNone(context.chosen_category)
		finally:
			frappe.form_dict.pop("category", None)

	def test_the_template_leads_to_the_new_address_only(self):
		html = (Path(our_courses.__file__).parent / "our-courses.html").read_text()
		self.assertNotIn(LEGACY, html)
		self.assertNotIn("categorie", html)
		self.assertIn(f'href="{URL}?category=', html)


class TestTheFormerAddress(CoursesPageTestCase):
	def redirect_of(self, **parameters):
		frappe.form_dict.update(parameters)
		try:
			with patch.object(frappe.local, "request", None, create=True):
				with self.assertRaises(frappe.Redirect) as raised:
					nos_formations.get_context(frappe._dict())
			self.last_status = raised.exception.http_status_code
			return frappe.local.flags.redirect_location
		finally:
			for key in parameters:
				frappe.form_dict.pop(key, None)

	def test_it_leads_to_the_new_address(self):
		self.assertEqual(self.redirect_of(), URL)

	def test_the_category_keeps_its_value_under_the_new_name(self):
		self.assertEqual(self.redirect_of(categorie="Hatha Yoga"), f"{URL}?category=Hatha+Yoga")

	def test_any_other_parameter_travels_with_it(self):
		self.assertEqual(self.redirect_of(utm_source="mail"), f"{URL}?utm_source=mail")

	def test_the_old_import_path_of_the_rule_still_works(self):
		# the theme's website_features.sync_all imported it from here before it moved
		self.assertIs(nos_formations.showing_courses, commerce.showing_courses)

	def test_the_address_is_a_permanent_redirect(self):
		self.redirect_of()
		self.assertEqual(self.last_status, 301)


class TestTheMenuFollowsThePage(CoursesPageTestCase):
	def setUp(self):
		super().setUp()
		_clear_menu_of_the_courses()

	def test_the_entry_is_put_when_the_page_is_shown_and_removed_when_it_is_not(self):
		with patch.object(commerce, "showing_courses", return_value=True):
			commerce.sync_courses_link()
		self.assertEqual(_menu_urls().count(URL), 1)

		with patch.object(commerce, "showing_courses", return_value=True):
			commerce.sync_courses_link()
		self.assertEqual(_menu_urls().count(URL), 1, "idempotent")

		with patch.object(commerce, "showing_courses", return_value=False):
			commerce.sync_courses_link()
		self.assertNotIn(URL, _menu_urls())

	def test_the_entry_that_led_to_the_former_address_is_moved_and_keeps_its_label(self):
		settings = frappe.get_doc("Website Settings")
		settings.append("top_bar_items", {"label": "Nos cours maison", "url": LEGACY})
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)

		with patch.object(commerce, "showing_courses", return_value=True):
			commerce.sync_courses_link()
		rows = [r for r in frappe.get_doc("Website Settings").top_bar_items if r.url in (URL, LEGACY)]
		self.assertEqual([(r.url, r.label) for r in rows], [(URL, "Nos cours maison")])

	def test_the_former_entry_goes_when_the_page_is_hidden(self):
		settings = frappe.get_doc("Website Settings")
		settings.append("top_bar_items", {"label": "Nos formations", "url": LEGACY})
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)

		with patch.object(commerce, "showing_courses", return_value=False):
			commerce.sync_courses_link()
		self.assertNotIn(LEGACY, _menu_urls())
		self.assertNotIn(URL, _menu_urls())

	def test_both_entries_at_once_leave_the_new_one_only(self):
		settings = frappe.get_doc("Website Settings")
		settings.append("top_bar_items", {"label": "Nos formations", "url": LEGACY})
		settings.append("top_bar_items", {"label": "Our courses", "url": URL})
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)

		with patch.object(commerce, "showing_courses", return_value=True):
			commerce.sync_courses_link()
		urls = _menu_urls()
		self.assertEqual((urls.count(URL), urls.count(LEGACY)), (1, 0))


class TestThePublicationMovesTheMenu(CoursesPageTestCase):
	def test_publishing_or_withdrawing_a_course_syncs_the_menu(self):
		with patch.object(commerce, "sync_courses_menu") as sync:
			commerce.course_saved(frappe._dict(has_value_changed=lambda field: field == "published"))
			sync.assert_called_once()

	def test_saving_a_course_without_touching_its_publication_does_not(self):
		with patch.object(commerce, "sync_courses_menu") as sync:
			commerce.course_saved(frappe._dict(has_value_changed=lambda field: False))
			sync.assert_not_called()

	def test_deleting_a_published_course_syncs_the_menu_once_it_is_gone(self):
		with patch("frappe.enqueue") as enqueue:
			commerce.course_trashed(frappe._dict(published=1))
			enqueue.assert_called_once()
			args, kwargs = enqueue.call_args
			self.assertEqual(args[0], "lms.lms.neoffice_commerce.sync_courses_menu")
			self.assertTrue(kwargs["enqueue_after_commit"])

	def test_deleting_a_draft_leaves_the_menu_alone(self):
		with patch("frappe.enqueue") as enqueue:
			commerce.course_trashed(frappe._dict(published=0))
			enqueue.assert_not_called()

	def test_a_menu_that_cannot_be_written_never_stops_the_publication(self):
		frappe.flags.mute_messages = False
		with (
			patch.object(commerce, "sync_courses_link", side_effect=RuntimeError("boom")),
			patch("frappe.log_error") as log_error,
		):
			commerce.sync_courses_menu()
		log_error.assert_called_once()
		self.assertEqual(log_error.call_args.args[0], "Courses page: menu entry not synced")
		self.assertFalse(frappe.flags.mute_messages, "the messages are given back")

	def test_the_menu_sync_announces_nothing(self):
		def noisy():
			frappe.msgprint("Website cache cleared. Refresh your pages to see changes.", alert=True)

		frappe.flags.mute_messages = False
		frappe.local.message_log = []
		with patch.object(commerce, "sync_courses_link", side_effect=noisy):
			commerce.sync_courses_menu()
		self.assertEqual(frappe.local.message_log, [])

	def test_the_hooks_are_wired(self):
		# an upstream merge rewrites hooks.py: this fails loudly if it drops one of ours
		events = frappe.get_hooks("doc_events")
		course = events["LMS Course"]
		self.assertIn("lms.lms.neoffice_commerce.course_saved", course["on_update"])
		self.assertIn("lms.lms.telemetry.course_saved", course["on_update"])
		self.assertIn("lms.lms.neoffice_commerce.course_trashed", _as_list(course["on_trash"]))
		settings = events["LMS Settings"]
		self.assertIn("lms.lms.neoffice_commerce.sync_courses_link", settings["on_update"])
		self.assertIn("lms.lms.neoffice_commerce.settings_onload", _as_list(settings["onload"]))
		daily = frappe.get_hooks("scheduler_events")["daily"]
		self.assertIn("lms.lms.neoffice_commerce.sync_courses_menu", daily)


def _as_list(value):
	return value if isinstance(value, list) else [value]


class TestTheSwitchOfAnExistingSite(CoursesPageTestCase):
	"""A Single that already exists does not take the `default` of a field added later (measured on osiris)."""

	def forget_the_switch(self):
		frappe.db.delete("Singles", {"doctype": "LMS Settings", "field": "neo_show_on_website"})

	def test_a_site_with_a_published_course_keeps_showing_it(self):
		self.forget_the_switch()
		with _published(2):
			commerce._switch_on_where_there_are_courses()
		self.assertEqual(
			cint(frappe.db.get_single_value("LMS Settings", "neo_show_on_website", cache=False)), 1
		)

	def test_a_site_with_no_published_course_stays_off(self):
		self.forget_the_switch()
		with _published(0):
			commerce._switch_on_where_there_are_courses()
		self.assertEqual(
			cint(frappe.db.get_single_value("LMS Settings", "neo_show_on_website", cache=False)), 0
		)

	def test_a_switch_the_owner_set_is_left_alone(self):
		_set_switch(0)
		with _published(5):
			commerce._switch_on_where_there_are_courses()
		self.assertEqual(
			cint(frappe.db.get_single_value("LMS Settings", "neo_show_on_website", cache=False)), 0
		)
