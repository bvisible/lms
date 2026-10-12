# //// Neoffice — added file (no upstream equivalent): the progress of the customers' employees.
import time
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms import neoffice_enter as ne
from lms.lms import neoffice_team as nt

HOST = "dmis.neoffice.me"
OTHER = "other.neoffice.me"
SECRET = "test-secret-for-dmis-0123456789abcdef"
OTHER_SECRET = "test-secret-for-other-0123456789abcdef"
COURSES = {"BIEN": "Bien démarrer", "VENDRE": "Vendre avec Neoffice"}


def claims(purpose="lms-enter", iss=HOST, sub="jean.dupont@client-example.ch", **over):
	now = int(time.time())
	base = {
		"v": 1,
		"purpose": purpose,
		"iss": iss,
		"sub": sub,
		"name": over.pop("name", "Jean Dupont"),
		"customer": over.pop("customer", "DMIS SA"),
		"source": "instance",
		"iat": now,
		"exp": now + 60,
		"jti": frappe.generate_hash(length=32),
	}
	base.update(over)
	return base


def team_progress(token):
	"""The endpoint without its rate limiter, which reads the request instead of the arguments."""
	return nt.team_progress.__wrapped__(token)


class TestLearnerProgress(UnitTestCase):
	def setUp(self):
		frappe.conf["neoffice_lms_instance_secrets"] = {HOST: SECRET, OTHER: OTHER_SECRET}
		frappe.db.delete("Neoffice External Learner", {"instance": ["in", [HOST, OTHER]]})
		frappe.local.response = frappe._dict()
		self.jean = ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		self.marie = ne.ensure_learner(
			ne.verify_token(ne.sign_token(SECRET, claims(sub="marie.martin@client-example.ch", name="Marie Martin")))
		)
		self.eve = ne.ensure_learner(
			ne.verify_token(
				ne.sign_token(
					OTHER_SECRET, claims(iss=OTHER, sub="eve@autre-example.ch", name="Eve", customer="Autre SA")
				)
			)
		)

	def tearDown(self):
		frappe.conf.pop("neoffice_lms_instance_secrets", None)
		frappe.db.rollback()

	def enrolled(self):
		"""Jean follows two courses (one lesson done in the first), Marie none, Eve one."""
		real = frappe.get_all

		def get_all(doctype, *args, **kwargs):
			if doctype == "LMS Enrollment":
				members = kwargs.get("filters", {}).get("member", [None, []])[1]
				data = [
					frappe._dict(member=self.jean, course="BIEN", progress=45.46),
					frappe._dict(member=self.jean, course="VENDRE", progress=0),
					frappe._dict(member=self.eve, course="BIEN", progress=100),
				]
				course = kwargs.get("filters", {}).get("course")
				return [r for r in data if r.member in members and (not course or r.course == course)]
			if doctype == "LMS Course":
				return [frappe._dict(name=k, title=v) for k, v in COURSES.items()]
			if doctype == "LMS Course Progress":
				return [frappe._dict(member=self.jean, course="BIEN", lessons=7)]
			return real(doctype, *args, **kwargs)

		return patch.object(frappe, "get_all", get_all)

	def test_a_learner_who_has_not_opened_a_course_is_listed_once_without_a_course(self):
		rows = nt.learner_rows(instance=HOST)
		marie = [r for r in rows if r["email"] == "marie.martin@client-example.ch"]
		self.assertEqual(len(marie), 1)
		self.assertEqual((marie[0]["course"], marie[0]["progress"], marie[0]["lessons_done"]), (None, 0, 0))
		self.assertEqual((marie[0]["customer"], marie[0]["instance"], marie[0]["enabled"]), ("DMIS SA", HOST, 1))

	def test_one_row_per_learner_and_course_with_progress_and_lessons_done(self):
		with self.enrolled():
			rows = nt.learner_rows(instance=HOST)
		jean = [r for r in rows if r["email"] == "jean.dupont@client-example.ch"]
		self.assertEqual(
			[(r["course"], r["course_title"], r["progress"], r["lessons_done"]) for r in jean],
			[("BIEN", "Bien démarrer", 45.5, 7), ("VENDRE", "Vendre avec Neoffice", 0, 0)],
		)
		self.assertEqual(len(rows), 3)

	def test_the_filters_narrow_by_instance_customer_and_course(self):
		with self.enrolled():
			self.assertEqual({r["instance"] for r in nt.learner_rows(instance=OTHER)}, {OTHER})
			self.assertEqual({r["email"] for r in nt.learner_rows(customer="Autre SA")}, {"eve@autre-example.ch"})
			by_course = nt.learner_rows(course="BIEN")
			self.assertEqual({r["email"] for r in by_course}, {"jean.dupont@client-example.ch", "eve@autre-example.ch"})
			self.assertTrue(all(r["course"] == "BIEN" for r in by_course))

	def test_an_instance_reads_its_own_team_grouped_by_person(self):
		with self.enrolled():
			team = nt.team_of(HOST)
		self.assertEqual({p["email"] for p in team}, {"jean.dupont@client-example.ch", "marie.martin@client-example.ch"})
		jean = next(p for p in team if p["email"].startswith("jean"))
		self.assertEqual([c["title"] for c in jean["courses"]], ["Bien démarrer", "Vendre avec Neoffice"])
		self.assertEqual(jean["courses"][0], {"title": "Bien démarrer", "progress": 45.5, "lessons_done": 7})
		for person in team:
			self.assertEqual(set(person), {"email", "full_name", "enabled", "last_seen", "courses"})

	def test_the_report_has_columns_and_the_rows(self):
		from lms.lms.report.neoffice_learner_progress.neoffice_learner_progress import execute

		columns, data = execute({"instance": HOST})
		self.assertIn("progress", {c["fieldname"] for c in columns})
		self.assertEqual({r["instance"] for r in data}, {HOST})


class TestTeamCall(UnitTestCase):
	def setUp(self):
		frappe.conf["neoffice_lms_instance_secrets"] = {HOST: SECRET, OTHER: OTHER_SECRET}
		frappe.db.delete("Neoffice External Learner", {"instance": ["in", [HOST, OTHER]]})
		frappe.local.response = frappe._dict()
		ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		ne.ensure_learner(
			ne.verify_token(
				ne.sign_token(OTHER_SECRET, claims(iss=OTHER, sub="eve@autre-example.ch", name="Eve", customer="Autre SA"))
			)
		)

	def tearDown(self):
		frappe.conf.pop("neoffice_lms_instance_secrets", None)
		frappe.db.rollback()

	def test_an_instance_gets_its_team_and_only_its_team(self):
		out = team_progress(ne.sign_token(SECRET, claims("lms-team", sub="admin@client-example.ch")))
		self.assertTrue(out["ok"])
		self.assertEqual([p["email"] for p in out["learners"]], ["jean.dupont@client-example.ch"])
		out = team_progress(ne.sign_token(OTHER_SECRET, claims("lms-team", iss=OTHER, sub="admin@autre-example.ch")))
		self.assertEqual([p["email"] for p in out["learners"]], ["eve@autre-example.ch"])

	def test_an_instance_cannot_ask_for_another_ones_team(self):
		# it signs with its own secret: the issuer it names decides whose secret checks the signature
		token = ne.sign_token(SECRET, claims("lms-team", iss=OTHER, sub="admin@client-example.ch"))
		self.assertEqual(team_progress(token), {"ok": False})
		self.assertEqual(frappe.local.response["http_status_code"], 403)

	def test_the_other_purposes_do_not_open_the_team(self):
		for purpose in ("lms-enter", "lms-leave", "other", None):
			frappe.local.response = frappe._dict()
			self.assertEqual(team_progress(ne.sign_token(SECRET, claims(purpose))), {"ok": False}, purpose)
			self.assertEqual(frappe.local.response["http_status_code"], 403)

	def test_a_team_token_does_not_enter_nor_leave(self):
		token = ne.sign_token(SECRET, claims("lms-team"))
		with self.assertRaises(ne.EnterRefused):
			ne.verify_token(token)
		self.assertEqual(ne.leave.__wrapped__(token), {"ok": False})

	def test_forged_garbage_and_replayed_tokens_get_nothing(self):
		self.assertEqual(team_progress(ne.sign_token("not-the-secret", claims("lms-team"))), {"ok": False})
		self.assertEqual(team_progress("garbage"), {"ok": False})
		self.assertEqual(team_progress(None), {"ok": False})
		token = ne.sign_token(SECRET, claims("lms-team"))
		self.assertTrue(team_progress(token)["ok"])
		self.assertEqual(team_progress(token), {"ok": False})
