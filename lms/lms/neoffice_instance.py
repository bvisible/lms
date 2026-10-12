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

Whatever the way, a link is only built for a desk path of a doctype (`/app/<doctype>`,
`/app/<doctype>/new`, `/app/<doctype>/view/list`), and an instance only if its address is an https
origin in the list of allowed domains (`site_config.json`: `neoffice_lms_allowed_domains`, by default
`.neoffice.me` and `.neoffice.ch`).
"""

import re

import frappe

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


@frappe.whitelist(allow_guest=True)
def get_instance_base():
	"""{"mode": "local" | "linked" | "none", "base": <origin or empty>} for the lesson macro InstanceLink."""
	if hosting_mode() == "instance":
		return {"mode": "local", "base": ""}
	origin = linked_instance_origin()
	if origin:
		return {"mode": "linked", "base": origin}
	return {"mode": "none", "base": ""}
