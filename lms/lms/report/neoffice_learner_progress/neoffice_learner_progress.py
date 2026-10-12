# //// Neoffice — added file (no upstream equivalent): the progress of the customers' employees, by customer and instance.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from lms.lms.neoffice_team import learner_rows


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = learner_rows(instance=filters.instance, customer=filters.customer, course=filters.course)
	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "customer", "fieldtype": "Data", "label": _("Customer"), "width": 180},
		{"fieldname": "instance", "fieldtype": "Data", "label": _("Instance"), "width": 190},
		{"fieldname": "full_name", "fieldtype": "Data", "label": _("Full name"), "width": 160},
		{"fieldname": "email", "fieldtype": "Data", "label": _("Learner e-mail"), "width": 220},
		{
			"fieldname": "course",
			"fieldtype": "Link",
			"label": _("Course"),
			"options": "LMS Course",
			"hidden": 1,
			"width": 120,
		},
		{"fieldname": "course_title", "fieldtype": "Data", "label": _("Course Name"), "width": 240},
		{"fieldname": "progress", "fieldtype": "Percent", "label": _("Progress"), "width": 100},
		{"fieldname": "lessons_done", "fieldtype": "Int", "label": _("Lessons completed"), "width": 130},
		{"fieldname": "last_seen", "fieldtype": "Datetime", "label": _("Last seen"), "width": 160},
		{"fieldname": "enabled", "fieldtype": "Check", "label": _("Enabled"), "width": 80},
	]
