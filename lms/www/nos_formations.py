# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""Public presentation page for the course catalogue.

Rendered live from the published courses, so adding a course updates the page
on its own — a hand-written page goes stale the first time the catalogue moves.

NOTE the file name: the route is /nos-formations (hyphen) but a www controller
must be named with an UNDERSCORE, or Frappe never finds it and the template
renders with no context.
"""

import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.free_courses = _courses(paid=False)
    context.paid_courses = _courses(paid=True)
    context.title = frappe.db.get_single_value("Website Settings", "app_name") or "Formations"
    return context


def _courses(paid: bool) -> list:
    rows = frappe.get_all(
        "LMS Course",
        filters={"published": 1, "paid_course": 1 if paid else 0},
        fields=[
            "name",
            "title",
            "short_introduction",
            "image",
            "course_price",
            "currency",
            "enable_certification",
            "category",
        ],
        order_by="course_price desc, title",
    )

    for row in rows:
        row.lessons = frappe.db.count("Course Lesson", {"course": row.name})
        # Formaté ici : le namespace frappe.utils n'est pas garanti côté Jinja,
        # et le prix sortait sans sa devise.
        row.price_label = (
            frappe.utils.fmt_money(row.course_price, currency=row.currency or "CHF")
            if paid
            else None
        )
        row.lms_url = "/lms/courses/{0}".format(row.name)
        row.shop_url = None
        row.access = None

        if paid:
            item = frappe.db.get_value(
                "Item", {"lms_course": row.name, "disabled": 0}, ["name", "lms_access_months"], as_dict=True
            )
            if item:
                months = int(item.lms_access_months or 0)
                row.access = frappe._("Permanent access") if not months else _n_months(months)
                route = frappe.db.get_value(
                    "Website Item", {"item_code": item.name, "published": 1}, "route"
                )
                if route:
                    row.shop_url = "/" + route.lstrip("/")

    return rows


def _n_months(months: int) -> str:
    if months % 12 == 0:
        years = months // 12
        if years == 1:
            return frappe._("1 year of access")
        return frappe._("{0} years of access").format(years)
    return frappe._("{0} months of access").format(months)

