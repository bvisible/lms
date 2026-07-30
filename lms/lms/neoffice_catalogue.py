# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""Catalogue helpers for the Neoffice chrome.

Kept out of upstream's api.py so the fork's merge surface stays small — same
reasoning as neoffice_video.py.
"""

import frappe


@frappe.whitelist(allow_guest=True)
def get_course_categories() -> list:
    """Categories that actually hold a published course, with their count.

    Empty categories are dropped on purpose: the sidebar lists these, and an
    entry that filters down to nothing is a dead end. A fresh Frappe LMS ships
    seven demo categories (Business, Design, Frontend…) with no courses at all.

    allow_guest: the course catalogue is public, so a visitor browsing it must
    be able to narrow it down.
    """
    rows = frappe.db.sql(
        """
        SELECT category.name AS name, category.category AS label, COUNT(course.name) AS total
        FROM `tabLMS Category` AS category
        INNER JOIN `tabLMS Course` AS course
            ON course.category = category.name AND course.published = 1
        GROUP BY category.name, category.category
        HAVING total > 0
        ORDER BY category.category
        """,
        as_dict=True,
    )
    return rows
