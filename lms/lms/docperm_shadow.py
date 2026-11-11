# Copyright (c) 2026, FOSS United and Contributors
# For license information, please see license.txt

"""Report the LMS permlevel permissions a site's Custom DocPerm rows have made inert.

`frappe.model.meta.Meta.set_custom_permissions` replaces a doctype's permissions with its
Custom DocPerm rows whenever any exist, so a single row written by Role Permissions Manager
discards every permission row LMS ships for that doctype -- including the permlevel > 0 rows
that keep a field out of reach. The shipped rows stay in `tabDocPerm` and simply stop
applying, so nothing raises and nothing is logged. This has to be looked for.
"""

import click
import frappe


def get_module_list(app):
	"""frappe moved this between releases: v15 and v16 expose it on `frappe`,
	develop on `frappe.modules.utils`. This line installs on all three."""
	getter = getattr(frappe, "get_module_list", None)
	if getter is None:
		from frappe.modules.utils import get_module_list as getter

	return getter(app)


ALERT_TITLE = "Custom DocPerm rows are shadowing the permlevel permissions LMS ships"

# Doctypes LMS shadows on purpose, on every site: install.py (User, Event),
# lms/patches/v1_0/custom_perm_for_discussions.py and api.py::give_discussions_permission
# (Discussion Topic, Discussion Reply). The list is the one
# lms/patches/v2_0/restore_system_manager_perms.py already carries the standard rows across
# for. They are frappe's doctypes, so the module scope below excludes them too; this is here
# so widening that scope cannot quietly turn LMS's own shadow into an alert.
LMS_MANAGED_CUSTOM_DOCPERM_DOCTYPES = ("User", "Event", "Discussion Topic", "Discussion Reply")


def get_shadowed_permlevel_rows() -> dict[str, list[tuple[str, int]]]:
	"""Return each LMS doctype whose Custom DocPerm rows have replaced its shipped
	permissions, mapped to the (role, permlevel) rows that stopped applying."""
	candidates = _get_lms_doctypes()
	if not candidates:
		return {}

	shadowed_doctypes = set(
		frappe.get_all("Custom DocPerm", filters={"parent": ("in", candidates)}, pluck="parent")
	)
	if not shadowed_doctypes:
		return {}

	inert_rows = frappe.get_all(
		"DocPerm",
		filters={
			"parent": ("in", shadowed_doctypes),
			"parenttype": "DocType",
			"permlevel": (">", 0),
		},
		fields=["parent", "role", "permlevel"],
		order_by="parent asc, permlevel asc, role asc",
	)

	# //// Neoffice — a shipped (role, permlevel) row that the Custom DocPerm set carries
	# again is NOT inert: set_custom_permissions applies the custom copy. Upstream listed every
	# shipped permlevel > 0 row of a customised doctype, so after the reconcile patches had
	# copied them (lms/patches/v2_0/reconcile_custom_docperm_permlevels.py) the alert still
	# fired on every migrate, for ever, and its own "stops reporting once the rows apply again"
	# was never true (neoffice-maintenance#1963, #1843). Same coverage rule as the patch's
	# add_missing_custom_docperm: a custom row for that (role, permlevel) exists. Remove when
	# upstream filters the covered rows.
	carried = {
		(row.parent, row.role, row.permlevel)
		for row in frappe.get_all(
			"Custom DocPerm",
			filters={"parent": ("in", shadowed_doctypes), "permlevel": (">", 0)},
			fields=["parent", "role", "permlevel"],
		)
	}

	shadowed: dict[str, list[tuple[str, int]]] = {}
	for row in inert_rows:
		if (row.parent, row.role, row.permlevel) in carried:  # //// Neoffice — see above
			continue
		shadowed.setdefault(row.parent, []).append((row.role, row.permlevel))
	return shadowed


def warn_about_shadowed_permlevels() -> None:
	"""after_migrate: name the LMS permlevel rows this site is no longer applying."""
	shadowed = get_shadowed_permlevel_rows()
	if not shadowed:
		return

	frappe.log_error(title=ALERT_TITLE, message=_describe_shadow(shadowed))
	click.secho(
		f"{ALERT_TITLE}: {', '.join(shadowed)}. See Error Log for the rows and the fix.",
		fg="yellow",
	)


def _get_lms_doctypes() -> set[str]:
	# `istable` doctypes are skipped by set_custom_permissions, so a child table cannot be
	# shadowed. Modules come from lms/modules.txt rather than a LIKE pattern: the app ships
	# both "LMS" and "Job", and a "%LMS%" filter drops every Job doctype without saying so.
	doctypes = frappe.get_all(
		"DocType",
		filters={"module": ("in", get_module_list("lms")), "custom": 0, "istable": 0},
		pluck="name",
	)
	return set(doctypes) - set(LMS_MANAGED_CUSTOM_DOCPERM_DOCTYPES)


def _describe_shadow(shadowed: dict[str, list[tuple[str, int]]]) -> str:
	lines = [
		"These LMS doctypes carry Custom DocPerm rows, so the permissions LMS ships for them",
		"are replaced at runtime and the field-level rows below no longer apply. Fields at those",
		"permlevels become unreadable, and any value saved into them is silently reset.",
		"",
	]
	for doctype, rows in shadowed.items():
		inert = ", ".join(f"{role} (permlevel {permlevel})" for role, permlevel in rows)
		custom_rows = frappe.db.count("Custom DocPerm", {"parent": doctype})
		plural = "" if custom_rows == 1 else "s"
		lines.append(f"  {doctype} - inert under {custom_rows} Custom DocPerm row{plural}: {inert}")
	lines += [
		"",
		"Open Role Permissions Manager for each doctype above and add the listed role and",
		"permlevel rows back, or delete that doctype's Custom DocPerm rows to fall back to what",
		"LMS ships. This runs on every migrate and stops reporting once the rows apply again.",
	]
	return "\n".join(lines)
