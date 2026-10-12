# //// Neoffice — added file (no upstream equivalent).
# //// The address a lesson link opens: `{{ InstanceLink("/app/item/new", "…") }}` points to the
# //// Neoffice of the person who follows the course. The base address is decided HERE, from what
# //// the site knows, and is never read from the lesson or from the address of the page.
# //// At the merge: kept whole; only its macro branch in LessonContent.vue meets upstream.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""The base address of the learner's own Neoffice, for the lesson macro InstanceLink.

Two ways to host a course (see the plan: Obsidian Neoffice/Formations-LMS/19):

- the course lives on the customer's own Neoffice (the LMS app of the instance): the link is
  relative to the same site, no setting but one flag in `site_config.json`:

      bench --site <site> set-config neoffice_lms_mode instance

- the course lives on our hub (the default): the link is built with the instance registered for the
  learner. Until the learners are registered, nobody is linked: the lesson then shows its label as a
  plain sentence, without a link.

- the person is on the staff of an accounting firm, which has one Neoffice per client: the hub's app (hooks
  `neoffice_lms_fiduciary_instances` and `neoffice_lms_fiduciary_open`) says which clients they may open and mints the
  signed link into the chosen one, landing on the lesson's screen (`open_instance`). The mandate, the firm's approval and
  the person's rights are checked by the hub at every click, never here.

Whatever the way, a link is only built for a desk path of a doctype (`/app/<doctype>`,
`/app/<doctype>/new`, `/app/<doctype>/view/list`), and an instance only if its address is an https
origin in the list of allowed domains (`site_config.json`: `neoffice_lms_allowed_domains`, by default
`.neoffice.me` and `.neoffice.ch`).
"""

import re

import frappe
from frappe import _

# Same rules as frontend/src/utils/instanceLink.ts (unit-tested on both sides).
PATH_RE = re.compile(r"^/app/[a-z0-9][a-z0-9_-]{0,60}(?:/(?:new|view/(?:list|report|kanban)))?$")
ORIGIN_RE = re.compile(r"^https://[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62}){1,4}$")
DEFAULT_ALLOWED_DOMAINS = (".neoffice.me", ".neoffice.ch")


def hosting_mode() -> str:
	"""`instance` when this site is the customer's own Neoffice, `hub` otherwise (the default)."""
	return "instance" if (frappe.conf.get("neoffice_lms_mode") or "").lower() == "instance" else "hub"


def allowed_domains() -> tuple:
	configured = frappe.conf.get("neoffice_lms_allowed_domains")
	if isinstance(configured, (list, tuple)) and configured:
		return tuple(str(d).lower() for d in configured if str(d).startswith("."))
	return DEFAULT_ALLOWED_DOMAINS


def is_allowed_path(path) -> bool:
	return isinstance(path, str) and bool(PATH_RE.match(path))


def clean_origin(url) -> str | None:
	"""The https origin of a registered instance address, or None if it is not acceptable.

	Accepts `https://dmis.neoffice.me` and `https://dmis.neoffice.me/` (a trailing slash is removed);
	refuses http, a path, a port, credentials, an address that is not under an allowed domain, and a
	look-alike (`dmis.neoffice.me.evil` does not end with `.neoffice.me`).
	"""
	if not isinstance(url, str):
		return None
	origin = url.strip().rstrip("/").lower()
	if not ORIGIN_RE.match(origin):
		return None
	host = origin[len("https://") :]
	if not any(host.endswith(domain) and len(host) > len(domain) for domain in allowed_domains()):
		return None
	return origin


def build_url(base: str, path: str) -> str | None:
	"""The address of a link: the path alone for an empty base, the origin and the path otherwise."""
	if not is_allowed_path(path):
		return None
	if not base:
		return path
	origin = clean_origin(base)
	return f"{origin}{path}" if origin else None


def linked_instance_origin() -> str | None:
	"""The origin of the instance registered for the current learner, None when nobody is linked.

	The register of learners comes with the second step of the plan; until the doctype exists
	nobody is linked.
	"""
	if frappe.session.user == "Guest" or not frappe.db.exists("DocType", "Neoffice External Learner"):
		return None
	url = frappe.db.get_value(
		"Neoffice External Learner",
		{"user": frappe.session.user, "enabled": 1},
		"instance_url",
	)
	return clean_origin(url)


def fiduciary_options() -> list:
	"""The client instances the logged-in person may open from a lesson, as the hub's app lists them; empty elsewhere.

	``[{"instance": <id the hub opens>, "label": <client>, "host": <address shown to tell two clients apart>}]``
	"""
	if frappe.session.user == "Guest" or hosting_mode() == "instance":
		return []
	for method in frappe.get_hooks("neoffice_lms_fiduciary_instances") or []:
		options = []
		for option in frappe.get_attr(method)() or []:
			instance = str(option.get("instance") or "").strip()
			if instance:
				options.append(
					{
						"instance": instance[:140],
						"label": str(option.get("label") or instance)[:140],
						"host": str(option.get("host") or "")[:100],
					}
				)
		if options:
			return options
	return []


@frappe.whitelist(allow_guest=True)
def get_instance_base():
	"""{"mode": "local" | "linked" | "fiduciary" | "none", "base": <origin or empty>} for the lesson macro InstanceLink.

	``fiduciary`` also carries ``options``: the clients the person may choose among (see `fiduciary_options`).
	"""
	if hosting_mode() == "instance":
		return {"mode": "local", "base": ""}
	origin = linked_instance_origin()
	if origin:
		return {"mode": "linked", "base": origin}
	options = fiduciary_options()
	if options:
		return {"mode": "fiduciary", "base": "", "options": options}
	return {"mode": "none", "base": ""}


@frappe.whitelist()
def open_instance(instance: str = None, path: str = None):
	"""Send the logged-in fiduciary to the Neoffice of one of their clients, signed in, on the screen of the lesson.

	Opened in a new tab by the lesson link. The instance must be one the hub offers this very person, the path a desk path
	of a doctype; the hub mints the one-time link and journals it. A refusal is a plain page, never a JSON error.
	"""
	if frappe.session.user == "Guest":
		raise frappe.PermissionError
	try:
		if not is_allowed_path(path) or instance not in {o["instance"] for o in fiduciary_options()}:
			raise frappe.PermissionError
		for method in frappe.get_hooks("neoffice_lms_fiduciary_open") or []:
			url = frappe.get_attr(method)(instance, path)
			# The hub's own link into a client's instance: https, and the signed-login door of the instance.
			if isinstance(url, str) and url.startswith("https://") and "/api/method/neoffice_theme.sso.sso_login?" in url:
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = url
				return
			break
		raise frappe.PermissionError
	except frappe.PermissionError:
		frappe.clear_messages()
		frappe.respond_as_web_page(
			_("Access refused"),
			_("You do not have access to this client."),
			http_status_code=403,
			indicator_color="red",
		)
