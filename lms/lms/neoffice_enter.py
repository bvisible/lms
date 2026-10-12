# //// Neoffice — added file (no upstream equivalent).
# //// The door of a customer's employees into the courses of this site (the hub): a signed link made by the
# //// customer's own Neoffice, the "Formation" entry of its help panel (neoffice_theme.lms_enter), opens a session on
# //// an account created for that person, on this site only, labelled with the instance it comes from. Plan: Obsidian
# //// Neoffice/Formations-LMS/19 (the two doors; this is door A).
# //// Built like the fiduciary single sign-on of the instances (neoffice_theme.sso): the signed token IS the
# //// credential, HMAC compared in constant time, short life, one use, a refusal is a plain 403 page and a trace
# //// that never holds the token or the secret.
# //// At the merge: kept whole.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""Single sign-on of a customer's employee into the courses of this site.

Token: ``<base64url(json)>.<hex hmac-sha256(json, secret of the instance)>`` where the secret is the
instance's ``sso_secret`` (the one the hub already holds to open the instances for the fiduciaries), and
the json is::

    {"v": 1, "purpose": "lms-enter", "iss": "dmis.neoffice.me", "sub": "jean@client.ch",
     "name": "Jean Dupont", "customer": "DMIS SA", "models": ["Compta"], "source": "instance",
     "iat": 1790000000, "exp": 1790000060, "jti": "<32 hex>"}

- ``purpose`` keeps this token apart from the others signed with the same secret (the hub's tokens that
  open an instance have no such claim and are refused here, and this one is refused by the instance);
- ``iss`` is the host of the instance; it is read BEFORE the signature only to find the secret to check the
  signature with, and the instance can therefore only speak for itself;
- the account is ``<local>+<label>-<4 hex of the host>@<domain>``: the same mailbox, one account per
  instance, never an account the site already had. A person who works for two customers gets two accounts
  and two labels.

The way out: when a person's account is disabled or deleted on the instance, the instance tells this site with a token of
``purpose`` ``lms-leave`` (:func:`leave`); the learner is switched off and the account here is disabled. A later entry
signed by the same instance switches it back on, but only if the instance was the one to switch it off.

Where the secret of an instance comes from: the hook ``neoffice_lms_instance_secret`` (a function taking
the host; the hub's app answers from its Cloud Instance), then ``site_config.json``'s
``neoffice_lms_instance_secrets`` (``{"host": "secret"}``, enough for a test).
"""

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, now_datetime, nowdate, validate_email_address

from lms.lms import neoffice_instance

PURPOSE = "lms-enter"
LEAVE_PURPOSE = "lms-leave"
MAX_TOKEN_LENGTH = 4096
MAX_LIFETIME = 300  # a token living longer than this is refused, whatever the instance signed
CLOCK_SKEW = 5
NONCE_GRACE = 60
SESSION_HOURS = 8
REFUSAL_LOG_LIMIT = 20
REFUSAL_LOG_WINDOW = 600
SIGNED_REFUSAL_MEMORY = 86400
SAVEPOINT = "neo_lms_enter"
LEARNER_ROLE = "LMS Student"
HOST_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62}){1,4}$")
# Where a learner may be sent after the entry: the LMS, nowhere else.
NEXT_RE = re.compile(r"^/lms(?:/[A-Za-z0-9._~%!$&'()*+,;=:@-]+)*/?$")
DEFAULT_NEXT = "/lms"


class EnterRefused(Exception):
	"""A token this site will not honour. ``reason`` is logged, ``message`` shown, ``signed`` says the signature checked."""

	def __init__(self, reason, message=None, detail=None, signed=False):
		super().__init__(reason)
		self.reason = reason
		self.message = message
		self.detail = detail
		self.signed = signed


def _b64url_decode(value: str) -> bytes:
	return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_token(secret: str, payload: dict) -> str:
	"""The transport, as the instance makes it: used by the tests and by anything that needs to mint a token here."""
	body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
	sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
	return base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + sig


def instance_secret(host: str) -> str | None:
	"""The ``sso_secret`` of an instance, from the hub's app (hook), then from this site's configuration."""
	for method in frappe.get_hooks("neoffice_lms_instance_secret") or []:
		secret = frappe.get_attr(method)(host)
		if secret:
			return secret
	registered = frappe.conf.get("neoffice_lms_instance_secrets")
	if isinstance(registered, dict):
		secret = registered.get(host)
		if isinstance(secret, str) and secret:
			return secret
	return None


def verify_token(token, now: int | None = None, purpose: str = PURPOSE) -> dict:
	"""The claims of a token, once its signature and every claim checked. Raises EnterRefused.

	``purpose`` is the one the caller expects: an entry token cannot switch an access off, nor the other way round.
	"""
	if not token or not isinstance(token, str) or "." not in token or len(token) > MAX_TOKEN_LENGTH:
		raise EnterRefused("malformed token")
	body_b64, sig = token.rsplit(".", 1)
	try:
		body = _b64url_decode(body_b64)
		claims = json.loads(body)
	except (binascii.Error, ValueError):
		raise EnterRefused("malformed token")
	if not isinstance(claims, dict):
		raise EnterRefused("malformed token")
	# Not trusted yet: only the host, to find the secret that decides whether the rest is trusted.
	host = claims.get("iss")
	if not isinstance(host, str) or not HOST_RE.match(host) or not neoffice_instance.clean_origin(f"https://{host}"):
		raise EnterRefused("unknown or refused instance")
	secret = instance_secret(host)
	if not secret:
		raise EnterRefused("no secret registered for this instance")
	expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected, sig):
		raise EnterRefused("invalid signature")

	# Signed by that instance from here on: a bad claim is the instance's bug, refused and logged in full.
	def refuse(reason, message=None):
		return EnterRefused(reason, message, detail=f"instance: {host}\nreason: {reason}", signed=True)

	if claims.get("v") != 1 or claims.get("purpose") != purpose:
		raise refuse(f"not an {purpose} token")
	now = int(time.time() if now is None else now)
	exp, iat = claims.get("exp"), claims.get("iat")
	for value in (exp, iat):
		if not isinstance(value, int) or isinstance(value, bool):
			raise refuse("iat or exp missing")
	if exp < now:
		raise refuse("token expired", _("This link has expired. Please open it again from your Neoffice."))
	if exp - now > MAX_LIFETIME or iat > exp or iat - now > CLOCK_SKEW:
		raise refuse("token lifetime or issue date not acceptable")
	jti = claims.get("jti")
	if not isinstance(jti, str) or not 16 <= len(jti) <= 128:
		raise refuse("jti missing")
	email = (claims.get("sub") or "").strip().lower() if isinstance(claims.get("sub"), str) else ""
	if not email or len(email) > 140 or not validate_email_address(email):
		raise refuse("sub is not an e-mail address")
	claims["sub"] = email
	return claims


def consume_once(jti: str, exp: int) -> None:
	"""Remember a token id until the token could no longer be used; refuse one already seen (atomic SET NX)."""
	ttl = max(NONCE_GRACE, int(exp) - int(time.time()) + NONCE_GRACE)
	key = frappe.cache.make_key(f"neo_lms_enter_jti:{jti}")
	# nosemgrep: semgrep-rules.rules.frappe-cache-breaks-multitenancy
	if not frappe.cache.set(key, 1, nx=True, ex=ttl):
		raise EnterRefused(
			"token already used",
			_("This link was already used. Please open it again from your Neoffice."),
			signed=True,
		)


def portal_user_name(email: str, host: str) -> str:
	"""``jean@client.ch`` on ``dmis.neoffice.me`` -> ``jean+dmis-3fa9@client.ch``: same mailbox, one account per instance."""
	local, _, domain = email.partition("@")
	label = re.sub(r"[^a-z0-9]", "", host.split(".")[0])[:20] or "inst"
	digest = hashlib.sha1(host.encode()).hexdigest()[:4]
	return f"{local}+{label}-{digest}@{domain}"


def ensure_learner(claims: dict) -> str:
	"""The account of the person named by the claims: found, or created. Returns the user name.

	A user name the site already had is never taken over: the account is ours only if a learner row points to it.
	"""
	host, email = claims["iss"], claims["sub"]
	raw_name = claims.get("name")
	full_name = (raw_name if isinstance(raw_name, str) and raw_name.strip() else email.partition("@")[0]).strip()[:140]
	raw_customer = claims.get("customer")
	customer = raw_customer.strip()[:140] if isinstance(raw_customer, str) else ""
	models = claims.get("models")
	models_text = "\n".join(str(m)[:80] for m in models[:20]) if isinstance(models, list) else ""
	source = "Fiduciary" if claims.get("source") == "fiduciary" else "Instance"

	row_name = frappe.db.get_value("Neoffice External Learner", {"instance": host, "learner_email": email}, "name")
	user_name = portal_user_name(email, host)
	if row_name:
		row = frappe.get_doc("Neoffice External Learner", row_name)
		user_name = row.user or user_name
	else:
		row = None

	if not frappe.db.exists("User", user_name):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": user_name,
				"first_name": full_name or user_name,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		)
		user.flags.ignore_permissions = True
		user.flags.no_welcome_mail = True
		user.insert()
		user.add_roles(LEARNER_ROLE)
	elif row is None:
		raise EnterRefused(
			"account name already taken by a regular user",
			detail=f"instance: {host}\naccount: {user_name}",
			signed=True,
		)

	if row is None:
		row = frappe.get_doc(
			{
				"doctype": "Neoffice External Learner",
				"learner_email": email,
				"instance": host,
				"user": user_name,
				"first_seen": now_datetime(),
			}
		)
	if row.get("left_instance") and not row.enabled:
		# The instance reported that this person left, and now signs an entry for them: it considers them an employee
		# again. An access switched off here (left_instance unset) is Neoffice's decision, which the instance never undoes.
		row.enabled = 1
		row.left_instance = 0
	row.full_name = full_name
	row.customer = customer
	row.access_models = models_text
	row.source = source
	row.last_seen = now_datetime()
	row.flags.ignore_permissions = True
	row.save()
	if not row.enabled:
		raise EnterRefused(
			"learner switched off",
			_("Your access to the courses has been switched off. Please ask the administrator of your Neoffice."),
			detail=f"instance: {host}\naccount: {user_name}",
			signed=True,
		)
	if row.access_valid_till and getdate(row.access_valid_till) < getdate(nowdate()):
		raise EnterRefused(
			"access ended",
			_("Your access to the courses has ended. Please ask the administrator of your Neoffice."),
			detail=f"instance: {host}\naccount: {user_name}",
			signed=True,
		)
	if not frappe.db.get_value("User", user_name, "enabled"):
		raise EnterRefused("account disabled", detail=f"account: {user_name}", signed=True)
	return user_name


def safe_next(path) -> str:
	"""Where to send the learner: an address of the LMS, and the LMS home otherwise."""
	if isinstance(path, str) and len(path) <= 200 and "//" not in path and ".." not in path and NEXT_RE.match(path):
		return path
	return DEFAULT_NEXT


def _may_log_refusal(reason, signed_token=None) -> bool:
	if signed_token:
		try:
			signature = signed_token.rsplit(".", 1)[-1]
			seen = hashlib.sha256(f"{signature}|{reason}".encode()).hexdigest()[:40]
			key = frappe.cache.make_key(f"neo_lms_enter_signed_refusal:{seen}")
			# nosemgrep: semgrep-rules.rules.frappe-cache-breaks-multitenancy
			return bool(frappe.cache.set(key, 1, nx=True, ex=SIGNED_REFUSAL_MEMORY))
		except Exception:
			return True
	try:
		key = frappe.cache.make_key("neo_lms_enter_refusals")
		# nosemgrep: semgrep-rules.rules.frappe-cache-breaks-multitenancy
		frappe.cache.set(key, 0, nx=True, ex=REFUSAL_LOG_WINDOW)
		return int(frappe.cache.incr(key)) <= REFUSAL_LOG_LIMIT
	except Exception:
		return False


def _refuse(e: EnterRefused, signed_token=None) -> None:
	"""A plain 403 page and a trace for Neoffice, without the token or the secret."""
	try:
		frappe.db.rollback(save_point=SAVEPOINT)
	except Exception:
		frappe.db.rollback()
	frappe.clear_messages()
	frappe.logger("lms").warning(f"Learner entry refused: {e.reason}")
	if _may_log_refusal(e.reason, signed_token):
		frappe.log_error(f"Learner entry refused: {e.reason}"[:140], e.detail or e.reason)
		frappe.local.flags.commit = True
	frappe.respond_as_web_page(
		_("Access refused"),
		e.message or _("This link is not valid. Please open it again from your Neoffice."),
		http_status_code=403,
		indicator_color="red",
	)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60, ip_based=True)
def enter(t: str = None, next: str = None):
	"""Verify the signed link of an instance and open a session for the person it names, on this site only."""
	frappe.db.savepoint(SAVEPOINT)
	signed = False
	try:
		claims = verify_token(t)
		signed = True
		consume_once(claims["jti"], claims["exp"])
		user = ensure_learner(claims)
		session_end = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).isoformat()
		frappe.local.login_manager.login_as(user, session_end=session_end, audit_user=f"instance:{claims['iss']}")
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = safe_next(next)
	except EnterRefused as e:
		_refuse(e, t if (signed or e.signed) else None)
	except Exception:
		_refuse(
			EnterRefused(
				"unexpected error",
				_("The access could not be opened. Please try again or contact Neoffice."),
				frappe.get_traceback(),
			),
			t if signed else None,
		)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60, ip_based=True)
def leave(t: str = None):
	"""A customer's Neoffice reports that a person left (account disabled or deleted): their access here is switched off.

	The token is signed like the entry token, with ``purpose`` ``lms-leave``. The account of the person is disabled and its
	sessions end (``Neoffice External Learner.on_update``). Only the instance a learner came from can switch them off, and an
	access already switched off here stays as Neoffice left it. Answers ``{"ok": true, "found": <a learner existed>}``.
	"""
	frappe.db.savepoint(SAVEPOINT)
	signed = False
	try:
		claims = verify_token(t, purpose=LEAVE_PURPOSE)
		signed = True
		consume_once(claims["jti"], claims["exp"])
		row_name = frappe.db.get_value(
			"Neoffice External Learner", {"instance": claims["iss"], "learner_email": claims["sub"]}, "name"
		)
		if row_name:
			row = frappe.get_doc("Neoffice External Learner", row_name)
			if row.enabled:
				row.enabled = 0
				row.left_instance = 1
				row.flags.ignore_permissions = True
				row.save()
		frappe.local.response["http_status_code"] = 200
		return {"ok": True, "found": bool(row_name)}
	except EnterRefused as e:
		return _refuse_call(e, t if (signed or e.signed) else None)
	except Exception:
		return _refuse_call(EnterRefused("unexpected error", detail=frappe.get_traceback()), t if signed else None)


def _refuse_call(e: EnterRefused, signed_token=None, what: str = "leave") -> dict:
	"""The refusal of an API call: a 403 with no detail, and the same trace as the entry door (no token, no secret)."""
	try:
		frappe.db.rollback(save_point=SAVEPOINT)
	except Exception:
		frappe.db.rollback()
	frappe.logger("lms").warning(f"Learner {what} refused: {e.reason}")
	if _may_log_refusal(e.reason, signed_token):
		frappe.log_error(f"Learner {what} refused: {e.reason}"[:140], e.detail or e.reason)
		frappe.local.flags.commit = True
	frappe.local.response["http_status_code"] = 403
	return {"ok": False}
