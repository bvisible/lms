# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""Selling courses as ordinary ERPNext Items, through the webshop.

Why not the LMS's own paid_course flow: it carries its own checkout
(``LMS Payment`` + the ``payments`` app) which knows nothing about the webshop
cart, TWINT, Stripe Terminal or ERPNext invoicing — all of which Neoffice
already runs. Selling a course as an Item reuses that whole chain and leaves a
real accounting trail.

The bridge is one field: ``Item.lms_course``. Paying the invoice grants the
enrolment; ``Item.lms_access_months`` says for how long (0 = permanent).

Access itself is enforced elsewhere — see neoffice_video.get_course_access.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_months, getdate, nowdate

ITEM_FIELDS = {
    "Item": [
        {
            "fieldname": "lms_section",
            "fieldtype": "Section Break",
            "label": _("Online Course"),
            "insert_after": "description",
            "collapsible": 1,
        },
        {
            "fieldname": "lms_course",
            "fieldtype": "Link",
            "label": _("Course"),
            "options": "LMS Course",
            "insert_after": "lms_section",
            "description": _("Paying an invoice for this item enrols the buyer in this course."),
        },
        {
            "fieldname": "lms_access_months",
            "fieldtype": "Int",
            "label": _("Access Duration (months)"),
            "insert_after": "lms_course",
            "depends_on": "lms_course",
            "description": _("0 means permanent access."),
        },
    ]
}


def setup_custom_fields():
    """Idempotent — safe on every migrate."""
    create_custom_fields(ITEM_FIELDS, ignore_validate=True)


# ---------------------------------------------------------------------------
# Who bought it
# ---------------------------------------------------------------------------


def _buyer_user(invoice) -> str | None:
    """The User to enrol, or None when it cannot be established.

    Deliberately conservative, like cloud/instance_validity: enrolling the wrong
    person is worse than enrolling nobody, so an ambiguous invoice is logged and
    skipped rather than guessed at.
    """
    candidates = []

    if invoice.get("contact_email"):
        candidates.append(invoice.contact_email)

    customer = invoice.get("customer")
    if customer:
        primary = frappe.db.get_value("Customer", customer, "customer_primary_contact")
        if primary:
            email = frappe.db.get_value("Contact", primary, "email_id")
            if email:
                candidates.append(email)

        # Contacts linked to this customer, when no primary one is set.
        linked = frappe.get_all(
            "Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Contact"},
            pluck="parent",
        )
        for contact in linked:
            email = frappe.db.get_value("Contact", contact, "email_id")
            if email:
                candidates.append(email)

    for email in candidates:
        if email and frappe.db.exists("User", email):
            return email

    return None


# ---------------------------------------------------------------------------
# Granting
# ---------------------------------------------------------------------------


def _grant(course: str, member: str, months: int) -> str:
    """Create or extend the enrolment. Cumulative, like the cloud instances."""
    name = frappe.db.get_value("LMS Enrollment", {"member": member, "course": course}, "name")
    today = getdate(nowdate())

    if not name:
        doc = frappe.get_doc(
            {
                "doctype": "LMS Enrollment",
                "member": member,
                "course": course,
                "access_from": today,
                "access_valid_till": add_months(today, months) if months else None,
            }
        ).insert(ignore_permissions=True)
        return doc.name

    if not months:
        # A permanent purchase clears any expiry the learner had.
        frappe.db.set_value("LMS Enrollment", name, "access_valid_till", None)
        return name

    current = frappe.db.get_value("LMS Enrollment", name, "access_valid_till")
    base = max(getdate(current), today) if current else today
    frappe.db.set_value("LMS Enrollment", name, "access_valid_till", add_months(base, months))
    return name


def grant_courses_for_invoice(invoice) -> list:
    """Enrol the buyer in every course sold by this invoice's lines."""
    lines = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": invoice.name},
        fields=["item_code"],
    )
    if not lines:
        return []

    courses = []
    for line in lines:
        course, months = (
            frappe.db.get_value("Item", line.item_code, ["lms_course", "lms_access_months"])
            or (None, None)
        )
        if course:
            courses.append((course, int(months or 0)))
    if not courses:
        return []

    member = _buyer_user(invoice)
    if not member:
        frappe.log_error(
            "LMS: buyer not resolvable on {0}".format(invoice.name)[:140],
            "Invoice {0} sells {1} course(s) but no User could be matched from "
            "contact_email or the customer's contacts, so nobody was enrolled.\n"
            "Courses: {2}".format(invoice.name, len(courses), [c for c, _ in courses]),
        )
        return []

    granted = []
    for course, months in courses:
        granted.append(_grant(course, member, months))

    frappe.logger().info(
        "LMS: {0} enrolled in {1} course(s) via {2}".format(member, len(granted), invoice.name)
    )
    return granted


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def _if_paid(invoice):
    if (invoice.get("outstanding_amount") or 0) > 0.01:
        return
    grant_courses_for_invoice(invoice)


def on_invoice_paid(doc, method=None):
    """Sales Invoice → on_update_after_submit."""
    _if_paid(doc)


def on_payment_entry_submitted(doc, method=None):
    """Payment Entry → on_submit.

    A Payment Entry settles its invoices with `db_set`, which never fires
    on_update_after_submit — without this second hook a real payment would
    enrol nobody. Same trap as neoffice_video and as the cloud instances.
    """
    for reference in doc.get("references") or []:
        if reference.reference_doctype != "Sales Invoice" or not reference.reference_name:
            continue
        invoice = frappe.db.get_value(
            "Sales Invoice",
            reference.reference_name,
            ["name", "outstanding_amount", "customer", "contact_email"],
            as_dict=True,
        )
        if invoice:
            _if_paid(invoice)
