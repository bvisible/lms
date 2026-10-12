# //// Neoffice — added file (no upstream equivalent): the signed entry of a customer's employee.
import time

import frappe
from frappe.tests import UnitTestCase

from lms.lms import neoffice_enter as ne

HOST = "dmis.neoffice.me"
SECRET = "test-secret-for-dmis-0123456789abcdef"


def claims(**over):
	now = int(time.time())
	base = {
		"v": 1,
		"purpose": "lms-enter",
		"iss": HOST,
		"sub": "jean.dupont@client-example.ch",
		"name": "Jean Dupont",
		"customer": "DMIS SA",
		"models": ["Comptabilité"],
		"source": "instance",
		"iat": now,
		"exp": now + 60,
		"jti": frappe.generate_hash(length=32),
	}
	base.update(over)
	return base


class TestVerifyToken(UnitTestCase):
	def setUp(self):
		frappe.conf["neoffice_lms_instance_secrets"] = {HOST: SECRET}

	def tearDown(self):
		frappe.conf.pop("neoffice_lms_instance_secrets", None)
		frappe.conf.pop("neoffice_lms_allowed_domains", None)

	def sign(self, payload, secret=SECRET):
		return ne.sign_token(secret, payload)

	def refused(self, token, reason):
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.verify_token(token)
		self.assertEqual(ctx.exception.reason, reason)
		return ctx.exception

	def test_a_valid_token_gives_its_claims(self):
		out = ne.verify_token(self.sign(claims(sub="Jean.Dupont@Client-Example.ch")))
		self.assertEqual(out["iss"], HOST)
		self.assertEqual(out["sub"], "jean.dupont@client-example.ch")

	def test_malformed_tokens(self):
		for token in (None, "", "abc", "a.b", "x" * 5000, 12):
			self.refused(token, "malformed token")

	def test_the_signature_decides(self):
		good = self.sign(claims())
		body, sig = good.rsplit(".", 1)
		self.refused(body + "." + ("0" * len(sig)), "invalid signature")
		self.refused(self.sign(claims(), secret="another-secret"), "invalid signature")
		# a claim changed after signing
		other = self.sign(claims(sub="boss@client-example.ch"))
		self.refused(body + "." + other.rsplit(".", 1)[1], "invalid signature")

	def test_the_instance_must_be_known_and_allowed(self):
		self.refused(self.sign(claims(iss="unknown.neoffice.me")), "no secret registered for this instance")
		frappe.conf["neoffice_lms_instance_secrets"]["evil.example.com"] = SECRET
		self.refused(self.sign(claims(iss="evil.example.com")), "unknown or refused instance")
		for host in ("DMIS.neoffice.me", "dmis.neoffice.me/x", "dmis.neoffice.me:8000", "neoffice.me", ""):
			self.refused(self.sign(claims(iss=host)), "unknown or refused instance")

	def test_a_token_of_another_purpose_is_refused(self):
		for over in ({"purpose": "other"}, {"purpose": None}, {"v": 2}, {"v": None}):
			exc = self.refused(self.sign(claims(**over)), "not an lms-enter token")
			self.assertTrue(exc.signed)
		# the hub's tokens that open an instance carry no such purpose
		hub_v2 = {"v": 2, "aud": HOST, "act": {"email": "a@b.ch"}, "firm": "F", "tpl": "T", "iat": int(time.time()), "exp": int(time.time()) + 60, "jti": "x" * 32, "iss": HOST}
		self.refused(self.sign(hub_v2), "not an lms-enter token")

	def test_time_claims(self):
		now = int(time.time())
		self.refused(self.sign(claims(exp=now - 10, iat=now - 70)), "token expired")
		self.refused(self.sign(claims(exp=now + 3600, iat=now)), "token lifetime or issue date not acceptable")
		self.refused(self.sign(claims(iat=now + 100, exp=now + 120)), "token lifetime or issue date not acceptable")
		self.refused(self.sign(claims(iat=now + 30, exp=now + 20)), "token lifetime or issue date not acceptable")
		for over in ({"exp": None}, {"exp": "9999999999"}, {"iat": True}, {"exp": True}):
			self.refused(self.sign(claims(**over)), "iat or exp missing")

	def test_jti_and_sub(self):
		self.refused(self.sign(claims(jti="short")), "jti missing")
		self.refused(self.sign(claims(jti=None)), "jti missing")
		for sub in ("", "no-at-sign", None, 12, "a@b", "x" * 200 + "@client-example.ch"):
			self.refused(self.sign(claims(sub=sub)), "sub is not an e-mail address")

	def test_a_token_is_used_once(self):
		jti = frappe.generate_hash(length=32)
		ne.consume_once(jti, int(time.time()) + 60)
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.consume_once(jti, int(time.time()) + 60)
		self.assertEqual(ctx.exception.reason, "token already used")


class TestAccounts(UnitTestCase):
	def setUp(self):
		frappe.conf["neoffice_lms_instance_secrets"] = {HOST: SECRET}
		frappe.db.delete("Neoffice External Learner", {"instance": HOST})

	def tearDown(self):
		frappe.conf.pop("neoffice_lms_instance_secrets", None)
		frappe.db.rollback()

	def test_the_account_name_keeps_the_mailbox_and_the_instance_apart(self):
		self.assertEqual(ne.portal_user_name("jean@client.ch", HOST), ne.portal_user_name("jean@client.ch", HOST))
		a = ne.portal_user_name("jean@client.ch", "dmis.neoffice.me")
		b = ne.portal_user_name("jean@client.ch", "dmis.other-example.ch")
		self.assertNotEqual(a, b)
		self.assertTrue(a.startswith("jean+dmis-") and a.endswith("@client.ch"))

	def test_first_entry_creates_the_account_and_the_row_then_finds_them(self):
		c = ne.verify_token(ne.sign_token(SECRET, claims()))
		user = ne.ensure_learner(c)
		self.assertTrue(frappe.db.exists("User", user))
		self.assertEqual(frappe.db.get_value("User", user, "user_type"), "Website User")
		self.assertIn(ne.LEARNER_ROLE, frappe.get_roles(user))
		row = frappe.get_doc("Neoffice External Learner", {"instance": HOST, "learner_email": "jean.dupont@client-example.ch"})
		self.assertEqual((row.user, row.customer, row.access_models, row.instance_url), (user, "DMIS SA", "Comptabilité", f"https://{HOST}"))
		again = ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims(customer="DMIS SA 2"))))
		self.assertEqual(again, user)
		self.assertEqual(frappe.db.count("Neoffice External Learner", {"instance": HOST}), 1)
		self.assertEqual(frappe.db.get_value("Neoffice External Learner", row.name, "customer"), "DMIS SA 2")

	def test_an_account_the_site_already_had_is_never_taken_over(self):
		name = ne.portal_user_name("staff@client-example.ch", HOST)
		frappe.get_doc({"doctype": "User", "email": name, "first_name": "Regular", "send_welcome_email": 0}).insert(ignore_permissions=True)
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims(sub="staff@client-example.ch"))))
		self.assertEqual(ctx.exception.reason, "account name already taken by a regular user")
		self.assertFalse(frappe.db.exists("Neoffice External Learner", {"learner_email": "staff@client-example.ch"}))

	def test_a_switched_off_or_ended_learner_is_refused(self):
		user = ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		row = frappe.get_doc("Neoffice External Learner", {"instance": HOST, "learner_email": "jean.dupont@client-example.ch"})
		row.enabled = 0
		row.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("User", user, "enabled"), 0)
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		self.assertEqual(ctx.exception.reason, "learner switched off")
		row.reload()
		row.enabled = 1
		row.access_valid_till = frappe.utils.add_days(frappe.utils.nowdate(), -1)
		row.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("User", user, "enabled"), 1)
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		self.assertEqual(ctx.exception.reason, "access ended")

	def test_where_a_learner_is_sent(self):
		self.assertEqual(ne.safe_next("/lms/courses/bien-demarrer-avec-neoffice"), "/lms/courses/bien-demarrer-avec-neoffice")
		self.assertEqual(ne.safe_next("/lms"), "/lms")
		for path in (None, "", "/app", "//evil.example", "https://evil.example", "/lms/../app", "/lms//x", "lms", "/lmsx", "/lms/?x=1"):
			self.assertEqual(ne.safe_next(path), "/lms", path)

	def test_the_instance_url_of_a_linked_learner_comes_from_its_row(self):
		from lms.lms import neoffice_instance

		user = ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		original = frappe.session.user
		try:
			frappe.set_user(user)
			self.assertEqual(neoffice_instance.get_instance_base(), {"mode": "linked", "base": f"https://{HOST}"})
		finally:
			frappe.set_user(original)


def leave(token):
	"""The endpoint without its rate limiter, which reads the request instead of the arguments."""
	return ne.leave.__wrapped__(token)


class TestLeave(UnitTestCase):
	def setUp(self):
		frappe.conf["neoffice_lms_instance_secrets"] = {HOST: SECRET}
		frappe.db.delete("Neoffice External Learner", {"instance": HOST})
		frappe.local.response = frappe._dict()

	def tearDown(self):
		frappe.conf.pop("neoffice_lms_instance_secrets", None)
		frappe.db.rollback()

	def leave_token(self, **over):
		return ne.sign_token(SECRET, claims(purpose="lms-leave", **over))

	def row(self):
		return frappe.get_doc("Neoffice External Learner", {"instance": HOST, "learner_email": "jean.dupont@client-example.ch"})

	def test_a_leave_token_switches_the_learner_and_the_account_off(self):
		user = ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		out = leave(self.leave_token())
		self.assertEqual(out, {"ok": True, "found": True})
		row = self.row()
		self.assertEqual((row.enabled, row.left_instance), (0, 1))
		self.assertEqual(frappe.db.get_value("User", user, "enabled"), 0)

	def test_a_person_the_site_never_saw_is_not_an_error(self):
		self.assertEqual(leave(self.leave_token(sub="nobody@client-example.ch")), {"ok": True, "found": False})
		self.assertFalse(frappe.db.exists("Neoffice External Learner", {"learner_email": "nobody@client-example.ch"}))

	def test_the_two_purposes_are_not_interchangeable(self):
		ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		# an entry token cannot switch anyone off
		out = leave(ne.sign_token(SECRET, claims()))
		self.assertEqual(out, {"ok": False})
		self.assertEqual(frappe.local.response["http_status_code"], 403)
		self.assertEqual(self.row().enabled, 1)
		# and a leave token does not open a session
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.verify_token(self.leave_token())
		self.assertEqual(ctx.exception.reason, "not an lms-enter token")

	def test_only_the_instance_the_learner_came_from_can_switch_them_off(self):
		ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		other = "other.neoffice.me"
		frappe.conf["neoffice_lms_instance_secrets"][other] = "another-secret-0123456789abcdef0123456789"
		token = ne.sign_token("another-secret-0123456789abcdef0123456789", claims(purpose="lms-leave", iss=other))
		self.assertEqual(leave(token), {"ok": True, "found": False})
		self.assertEqual(self.row().enabled, 1)

	def test_a_forged_or_replayed_token_changes_nothing(self):
		ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		self.assertEqual(leave(ne.sign_token("not-the-secret", claims(purpose="lms-leave"))), {"ok": False})
		self.assertEqual(leave("garbage"), {"ok": False})
		self.assertEqual(self.row().enabled, 1)
		token = self.leave_token()
		self.assertEqual(leave(token), {"ok": True, "found": True})
		self.assertEqual(leave(token), {"ok": False})

	def test_an_entry_after_the_instance_left_and_came_back_switches_the_access_on_again(self):
		user = ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		leave(self.leave_token())
		self.assertEqual(frappe.db.get_value("User", user, "enabled"), 0)
		self.assertEqual(ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims()))), user)
		row = self.row()
		self.assertEqual((row.enabled, row.left_instance), (1, 0))
		self.assertEqual(frappe.db.get_value("User", user, "enabled"), 1)

	def test_an_access_switched_off_by_neoffice_is_never_switched_on_by_the_instance(self):
		ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		row = self.row()
		row.enabled = 0
		row.save(ignore_permissions=True)
		# the instance reporting the departure changes nothing of what Neoffice decided...
		self.assertEqual(leave(self.leave_token()), {"ok": True, "found": True})
		self.assertEqual(self.row().left_instance, 0)
		# ...and its next entry stays refused
		with self.assertRaises(ne.EnterRefused) as ctx:
			ne.ensure_learner(ne.verify_token(ne.sign_token(SECRET, claims())))
		self.assertEqual(ctx.exception.reason, "learner switched off")
