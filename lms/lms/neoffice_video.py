# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""Subscription-gated video playback for LMS lessons (Infomaniak VOD).

Course videos live on Infomaniak VOD in a `key_restricted` folder, which makes
them unplayable without a short-lived HMAC token. This module is the only place
that mints such a token, and it only does so for a learner whose course access
is currently valid. Revoking access is therefore passive: once
`access_valid_till` is in the past, no token is ever issued again and the
existing one dies within 300 seconds.

Everything lives in a dedicated module on purpose: this fork tracks upstream
closely, so the touch points inside upstream files stay one-liners.

Site config keys:
    infomaniak_vod_channel   e.g. 15883
    infomaniak_vod_account   e.g. 21501
    infomaniak_vod_token     Bearer token carrying the VOD scope
"""

import re

import frappe
import requests
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_months, getdate, nowdate

API_BASE = "https://api.infomaniak.com/1/vod/channel"
API_TIMEOUT = 20

# {{ SecureVideo("1jijk03umkoek") }} — the lesson body never holds a playable URL,
# only the media id, so a leaked body is worthless without this endpoint.
SECURE_VIDEO_RE = re.compile(r"\{\{\s*SecureVideo\(\s*[\"']([^\"']+)[\"']\s*\)\s*\}\}")

SHARE_CACHE_KEY = "neoffice_vod_share"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Custom fields rather than doctype edits: LMS Enrollment belongs to upstream,
# and this fork merges from upstream regularly.
ENROLLMENT_FIELDS = {
    "LMS Enrollment": [
        {
            "fieldname": "neoffice_access_section",
            "fieldtype": "Section Break",
            "label": _("Subscription Access"),
            "insert_after": "progress",
        },
        {
            "fieldname": "subscription",
            "fieldtype": "Link",
            "label": _("Subscription"),
            "options": "Subscription",
            "insert_after": "neoffice_access_section",
            "description": _("Paying for this subscription extends the access period."),
        },
        {
            "fieldname": "access_from",
            "fieldtype": "Date",
            "label": _("Access From"),
            "insert_after": "subscription",
        },
        {
            "fieldname": "access_valid_till",
            "fieldtype": "Date",
            "label": _("Access Valid Till"),
            "insert_after": "access_from",
            "description": _("Empty means permanent access."),
        },
    ]
}


def setup_custom_fields():
    """Idempotent — safe to run on every migrate."""
    create_custom_fields(ENROLLMENT_FIELDS, ignore_validate=True)


# ---------------------------------------------------------------------------
# Access control — the single source of truth
# ---------------------------------------------------------------------------


def get_course_access(course: str, member: str = None) -> dict:
    """Return whether `member` may currently watch `course`, and why not.

    This is the ONE guard. Both the lesson payload and the playback token go
    through it, so the UI can never show a lesson whose video would be refused,
    nor the reverse.
    """
    member = member or frappe.session.user

    if member == "Guest":
        return {"allowed": False, "reason": "guest"}

    # Moderators and the course's own instructors always get through.
    from lms.lms.utils import can_modify_course

    if can_modify_course(course):
        return {"allowed": True, "reason": "moderator"}

    enrollment = frappe.db.get_value(
        "LMS Enrollment",
        {"member": member, "course": course},
        ["name", "access_from", "access_valid_till"],
        as_dict=True,
    )
    if not enrollment:
        return {"allowed": False, "reason": "not_enrolled"}

    today = getdate(nowdate())

    if enrollment.access_from and getdate(enrollment.access_from) > today:
        return {
            "allowed": False,
            "reason": "not_started",
            "access_from": enrollment.access_from,
        }

    # No expiry set means perpetual access: enrollments created before this
    # feature existed must keep working.
    if enrollment.access_valid_till and getdate(enrollment.access_valid_till) < today:
        return {
            "allowed": False,
            "reason": "expired",
            "access_valid_till": enrollment.access_valid_till,
        }

    return {"allowed": True, "reason": "enrolled"}


def has_active_course_access(course: str, member: str = None) -> bool:
    """Boolean shorthand over `get_course_access`."""
    return get_course_access(course, member).get("allowed", False)


def access_denied_message(access: dict) -> str:
    """User-facing explanation for a refused access."""
    reason = access.get("reason")
    if reason == "expired":
        return _("Your access to this course expired on {0}.").format(
            frappe.format(access.get("access_valid_till"), {"fieldtype": "Date"})
        )
    if reason == "not_started":
        return _("Your access to this course starts on {0}.").format(
            frappe.format(access.get("access_from"), {"fieldtype": "Date"})
        )
    if reason == "guest":
        return _("Please log in to watch this video.")
    return _("You are not enrolled in this course.")


# ---------------------------------------------------------------------------
# Infomaniak VOD client
# ---------------------------------------------------------------------------


def _config() -> dict:
    conf = frappe.conf
    channel = conf.get("infomaniak_vod_channel")
    account = conf.get("infomaniak_vod_account")
    token = conf.get("infomaniak_vod_token")
    if not (channel and account and token):
        frappe.throw(_("Video hosting is not configured on this site."))
    return {"channel": channel, "account": account, "token": token}


def _request(method: str, path: str, payload: dict = None) -> dict:
    cfg = _config()
    url = "{0}/{1}{2}".format(API_BASE, cfg["channel"], path)
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": "Bearer {0}".format(cfg["token"]),
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        # Omitting `account` yields a bare 403 vod_access_denied — undocumented.
        params={"account": cfg["account"]},
        json=payload,
        timeout=API_TIMEOUT,
    )
    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code >= 400 or body.get("result") == "error":
        frappe.log_error(
            "Infomaniak VOD {0} {1}".format(method, path)[:140],
            "HTTP {0}\n{1}".format(response.status_code, response.text[:2000]),
        )
        frappe.throw(_("The video service is temporarily unavailable."))

    return body.get("data") or {}


def _get_or_create_share(media_id: str) -> str:
    """Return the Share id that fronts `media_id`, creating it if needed.

    A token is minted against a Share, never against a Media — asking for a
    token on a media id returns 404 on the Share model. Shares are permanent,
    so the mapping is cached rather than looked up on every playback.
    """
    cache = frappe.cache()
    cached = cache.hget(SHARE_CACHE_KEY, media_id)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else cached

    for share in _request("GET", "/share") or []:
        if share.get("target_id") == media_id:
            cache.hset(SHARE_CACHE_KEY, media_id, share["id"])
            return share["id"]

    created = _request("POST", "/share", {"target": media_id})
    share_id = created.get("id")
    if not share_id:
        frappe.throw(_("The video service is temporarily unavailable."))

    cache.hset(SHARE_CACHE_KEY, media_id, share_id)
    return share_id


def _mint_token(share_id: str) -> str:
    """Mint a playback token. Lives 300 seconds."""
    data = _request("POST", "/share/{0}/token".format(share_id), {})
    if isinstance(data, str):
        return data
    frappe.throw(_("The video service is temporarily unavailable."))


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Billing → access period
# ---------------------------------------------------------------------------


def _period_months(subscription: str) -> int:
    """Months granted by one billing cycle of this subscription."""
    plans = frappe.get_all(
        "Subscription Plan Detail",
        filters={"parent": subscription},
        fields=["plan"],
        limit=1,
    )
    if not plans:
        return 1

    interval, count = (
        frappe.db.get_value(
            "Subscription Plan", plans[0].plan, ["billing_interval", "billing_interval_count"]
        )
        or ("Month", 1)
    )
    count = count or 1
    interval = (interval or "Month").strip().lower()
    if interval == "year":
        return 12 * count
    if interval == "month":
        return count
    # Day / Week plans are not a sensible course period; treat as one month.
    return 1


def extend_access_for_subscription(subscription: str) -> int:
    """Push every enrollment on this subscription one period further.

    Cumulative from the current expiry — `max(current, today) + one period` — so
    paying early never costs the learner the days already paid for. Same rule as
    the cloud instances (neoffice_devops.cloud.instance_validity).
    """
    enrollments = frappe.get_all(
        "LMS Enrollment",
        filters={"subscription": subscription},
        fields=["name", "access_valid_till"],
    )
    if not enrollments:
        return 0

    months = _period_months(subscription)
    today = getdate(nowdate())

    for enrollment in enrollments:
        current = getdate(enrollment.access_valid_till) if enrollment.access_valid_till else None
        base = max(current, today) if current else today
        frappe.db.set_value(
            "LMS Enrollment",
            enrollment.name,
            "access_valid_till",
            add_months(base, months),
        )

    return len(enrollments)


def _extend_from_invoice(invoice) -> None:
    if (invoice.get("outstanding_amount") or 0) > 0.01:
        return
    if not invoice.get("subscription"):
        return

    count = extend_access_for_subscription(invoice.subscription)
    if count:
        frappe.logger().info(
            "LMS course access extended for {0} enrollment(s) via {1}".format(
                count, invoice.name
            )
        )


def on_invoice_paid(doc, method=None):
    """Sales Invoice → on_update_after_submit."""
    _extend_from_invoice(doc)


def on_payment_entry_submitted(doc, method=None):
    """Payment Entry → on_submit.

    A Payment Entry settles its invoices with `db_set`, which does NOT fire
    `on_update_after_submit`. Without this second hook, a real payment would
    never extend anyone's course access.
    """
    for reference in doc.get("references") or []:
        if reference.reference_doctype != "Sales Invoice" or not reference.reference_name:
            continue
        invoice = frappe.db.get_value(
            "Sales Invoice",
            reference.reference_name,
            ["name", "outstanding_amount", "subscription"],
            as_dict=True,
        )
        if invoice:
            _extend_from_invoice(invoice)


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


def extract_media_ids(body: str) -> list:
    """Media ids referenced by a lesson body."""
    return SECURE_VIDEO_RE.findall(body or "")


@frappe.whitelist()
def get_playback_url(lesson: str, media: str = None) -> dict:
    """Return a signed, short-lived embed URL for a lesson video.

    Must never be cached: each learner gets their own token, and it expires in
    five minutes.
    """
    frappe.local.response_headers = getattr(frappe.local, "response_headers", {})

    lesson_doc = frappe.db.get_value(
        "Course Lesson",
        lesson,
        ["name", "course", "body", "content", "include_in_preview"],
        as_dict=True,
    )
    if not lesson_doc:
        frappe.throw(_("Lesson not found."), frappe.DoesNotExistError)

    known = set(extract_media_ids(lesson_doc.body)) | set(
        extract_media_ids(lesson_doc.content)
    )
    if media and media not in known:
        # Refuse to sign a media the lesson does not reference, otherwise this
        # endpoint would mint tokens for the whole catalogue.
        frappe.throw(_("This video does not belong to the lesson."))

    media_id = media or (sorted(known)[0] if known else None)
    if not media_id:
        frappe.throw(_("This lesson has no protected video."))

    # A preview lesson is watchable by anyone; everything else needs live access.
    if not lesson_doc.include_in_preview:
        access = get_course_access(lesson_doc.course)
        if not access["allowed"]:
            frappe.throw(access_denied_message(access), frappe.PermissionError)

    share_id = _get_or_create_share(media_id)
    token = _mint_token(share_id)

    return {
        "url": "https://player.vod2.infomaniak.com/embed/{0}?{1}".format(share_id, token),
        "media": media_id,
        # The player is reloaded before this runs out; the caller re-requests.
        "expires_in": 300,
    }
