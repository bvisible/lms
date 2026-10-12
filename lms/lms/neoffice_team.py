# //// Neoffice — added file (no upstream equivalent).
# //// The progress of the people who follow the courses as the employees of a customer's Neoffice (the learners of
# //// lms.lms.neoffice_enter): one report for Neoffice, one signed call for each instance that reads ITS team only.
# //// Plan: Obsidian Neoffice/Formations-LMS/19, step "suivi".
# //// At the merge: kept whole.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""Who follows which course, and how far, for the customers' employees.

``learner_rows`` is the one query: a row per (learner, course), or per learner who has not opened a course yet. The report
``Neoffice Learner Progress`` shows it to the staff of the hub, filtered by instance, customer or course. ``team_progress``
gives an instance the same, for the learners that came from that instance and no other: the instance proves who it is with
the token it already signs for the entry (``purpose`` ``lms-team``, the secret of ``neoffice_enter``).
"""

import frappe
from frappe.rate_limiter import rate_limit

from lms.lms import neoffice_enter

TEAM_PURPOSE = "lms-team"
SAVEPOINT = "neo_lms_team"


def learner_rows(instance=None, customer=None, course=None) -> list:
	"""``[{customer, instance, email, full_name, enabled, last_seen, course, course_title, progress, lessons_done}]``."""
	filters = {}
	if instance:
		filters["instance"] = instance
	if customer:
		filters["customer"] = customer
	learners = frappe.get_all(
		"Neoffice External Learner",
		filters=filters,
		fields=["user", "learner_email", "full_name", "instance", "customer", "enabled", "last_seen"],
		order_by="customer asc, instance asc, learner_email asc",
		limit_page_length=0,
	)
	if not learners:
		return []
	users = [row.user for row in learners if row.user]
	enrollment_filters = {"member": ["in", users or [""]]}
	if course:
		enrollment_filters["course"] = course
	enrollments = {}
	for row in frappe.get_all(
		"LMS Enrollment",
		filters=enrollment_filters,
		fields=["member", "course", "progress"],
		order_by="course asc",
		limit_page_length=0,
	):
		enrollments.setdefault(row.member, []).append(row)
	courses = {row.course for rows in enrollments.values() for row in rows}
	titles = (
		{c.name: c.title for c in frappe.get_all("LMS Course", {"name": ["in", list(courses)]}, ["name", "title"])}
		if courses
		else {}
	)
	done = {}
	if courses:
		for row in frappe.get_all(
			"LMS Course Progress",
			filters={"member": ["in", users], "course": ["in", list(courses)], "status": "Complete"},
			fields=["member", "course", "count(name) as lessons"],
			group_by="member, course",
			limit_page_length=0,
		):
			done[(row.member, row.course)] = row.lessons

	rows = []
	for learner in learners:
		base = {
			"customer": learner.customer or "",
			"instance": learner.instance,
			"email": learner.learner_email,
			"full_name": learner.full_name or "",
			"enabled": 1 if learner.enabled else 0,
			"last_seen": learner.last_seen,
		}
		taken = enrollments.get(learner.user, [])
		if not taken and not course:
			rows.append({**base, "course": None, "course_title": "", "progress": 0, "lessons_done": 0})
		for enrollment in taken:
			rows.append(
				{
					**base,
					"course": enrollment.course,
					"course_title": titles.get(enrollment.course) or enrollment.course,
					"progress": round(float(enrollment.progress or 0), 1),
					"lessons_done": done.get((learner.user, enrollment.course), 0),
				}
			)
	return rows


def team_of(instance: str) -> list:
	"""What an instance may read about its own learners: grouped by person, nothing about the account or the site."""
	people = {}
	for row in learner_rows(instance=instance):
		person = people.setdefault(
			row["email"],
			{
				"email": row["email"],
				"full_name": row["full_name"],
				"enabled": row["enabled"],
				"last_seen": str(row["last_seen"]) if row["last_seen"] else None,
				"courses": [],
			},
		)
		if row["course"]:
			person["courses"].append(
				{"title": row["course_title"], "progress": row["progress"], "lessons_done": row["lessons_done"]}
			)
	return list(people.values())


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60, ip_based=True)
def team_progress(t: str = None):
	"""The progress of the learners that came from the instance which signs ``t``, and of no other instance."""
	frappe.db.savepoint(SAVEPOINT)
	signed = False
	try:
		claims = neoffice_enter.verify_token(t, purpose=TEAM_PURPOSE)
		signed = True
		neoffice_enter.consume_once(claims["jti"], claims["exp"])
		frappe.local.response["http_status_code"] = 200
		return {"ok": True, "learners": team_of(claims["iss"])}
	except neoffice_enter.EnterRefused as e:
		return neoffice_enter._refuse_call(e, t if (signed or e.signed) else None, what="team")
	except Exception:
		return neoffice_enter._refuse_call(
			neoffice_enter.EnterRefused("unexpected error", detail=frappe.get_traceback()),
			t if signed else None,
			what="team",
		)
