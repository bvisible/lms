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

Où se règle l'hébergeur des vidéos :

    Formations › Paramètres › Le catalogue public › **Vidéos (Infomaniak VOD)**
        neo_vod_channel · neo_vod_account · neo_vod_token

    …et à défaut, les clés historiques de `site_config.json` :
        infomaniak_vod_channel · infomaniak_vod_account · infomaniak_vod_token

L'écran passe devant le fichier. Le fichier reste lu — les instances déjà
posées ne bougent pas — mais personne ne devrait avoir besoin d'un terminal
pour brancher un compte vidéo, et personne ne devine une clé qu'aucun écran
ne montre.
"""

import json
import re

import frappe
import requests
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_months, flt, getdate, nowdate

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
        # Idempotency key. Three hooks can carry the same payment (the invoice's
        # on_submit and on_update_after_submit, plus the Payment Entry), so the
        # period would be added several times without a record of what has
        # already been applied.
        {
            "fieldname": "last_grant_invoice",
            "fieldtype": "Data",
            "label": _("Last Granting Invoice"),
            "insert_after": "access_valid_till",
            "read_only": 1,
            "no_copy": 1,
            "description": _("The invoice that last extended this access."),
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
    """L'écran d'abord, le fichier ensuite.

    Un réglage laissé vide n'écrase rien : on retombe sur `site_config.json`,
    champ par champ. Une instance déjà configurée continue donc de jouer ses
    vidéos sans qu'on aille rien retaper.
    """
    conf = frappe.conf
    reglages = frappe.get_cached_doc("LMS Settings")

    channel = reglages.get("neo_vod_channel") or conf.get("infomaniak_vod_channel")
    account = reglages.get("neo_vod_account") or conf.get("infomaniak_vod_account")
    token = None
    if reglages.get("neo_vod_token"):
        token = reglages.get_password("neo_vod_token", raise_exception=False)
    token = token or conf.get("infomaniak_vod_token")

    if not (channel and account and token):
        frappe.throw(
            _(
                "Video hosting is not configured. Fill Channel, Account and Access token "
                "under Learning › Settings › Videos."
            )
        )
    return {"channel": channel, "account": account, "token": token}


@frappe.whitelist()
def list_media() -> list:
    """Les vidéos de l'espace, avec la ligne à coller dans la leçon.

    🔑 Jérémy, le 2026-08-04 : *« on met où dans l'ERP ? pas vu »* — et il n'y
    avait rien à voir. Poser une vidéo demandait de taper à la main
    `{{ SecureVideo("1jijk03umkoek") }}`, avec un identifiant qu'on ne pouvait
    lire que dans le manager Infomaniak, dans un autre onglet. Personne
    n'invente une chaîne de treize caractères.

    On rend donc la liste, et surtout **la ligne toute faite** : l'auteur
    copie, colle dans sa leçon, et n'a jamais à connaître la syntaxe.

    `state` 192 = prêt à jouer. Les autres valeurs sont des étapes d'encodage —
    une vidéo qu'on collerait maintenant ne jouerait pas encore.
    """
    frappe.only_for(("System Manager", "Moderator", "Course Creator"))
    medias = _request("GET", "/media")
    sortie = []
    for m in medias if isinstance(medias, list) else []:
        sortie.append(
            {
                "id": m.get("id"),
                "name": m.get("name") or m.get("id"),
                "duration": m.get("duration"),
                "ready": m.get("state") == 192,
                "macro": '{{ SecureVideo("%s") }}' % m.get("id"),
            }
        )
    return sortie


@frappe.whitelist()
def check_connection() -> dict:
    """Le bouton « Tester » : est-ce que ce compte répond, vraiment ?

    Trois champs recopiés à la main, c'est trois occasions de se tromper, et
    l'erreur ne se voit qu'au moment où un apprenant ouvre une leçon. Un aller-
    retour tout de suite vaut mieux qu'une panne découverte par le client.
    """
    frappe.only_for(("System Manager", "Moderator", "Course Creator"))
    # Volontairement HORS du try : « les trois champs ne sont pas remplis » est
    # une phrase utile, et la masquer derrière « le service a refusé » ferait
    # chercher une panne réseau là où il manque une valeur.
    cfg = _config()
    try:
        # ⚠️ `limit=1` seul fait répondre 422 `validation_rule_offset` : leur
        # pagination veut les deux bornes ou aucune. On demande donc la liste
        # entière — un espace de cours en compte quelques dizaines, pas des
        # milliers.
        espace = _request("GET", "")
        medias = _request("GET", "/media")
    except Exception:
        return {
            "ok": False,
            "channel": cfg["channel"],
            "account": cfg["account"],
            "message": _(
                "Infomaniak refused the call — the channel, the account or the token "
                "is wrong. Their exact answer is in the Error Log."
            ),
        }
    return {
        "ok": True,
        "channel": cfg["channel"],
        "account": cfg["account"],
        "name": (espace or {}).get("channel_name") or (espace or {}).get("slug") or "",
        "media_count": len(medias) if isinstance(medias, list) else None,
    }


def _request(
    method: str, path: str, payload: dict = None, params: dict = None, envelope: bool = False
) -> dict:
    cfg = _config()
    url = "{0}/{1}{2}".format(API_BASE, cfg["channel"], path)
    # Omitting `account` yields a bare 403 vod_access_denied — undocumented.
    query = {"account": cfg["account"]}
    if params:
        query.update(params)
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": "Bearer {0}".format(cfg["token"]),
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        params=query,
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

    return body if envelope else (body.get("data") or {})


def _all_shares() -> list:
    """Every Share on the channel, across every page.

    /share paginates, at 15 items per page by default. Reading only the first
    page means that past the fifteenth video an existing Share is never found —
    so a duplicate would be created on every single playback. Verified against
    the live API: the envelope carries total/pages/page, and per_page is honoured.
    """
    shares = []
    page = 1
    while True:
        body = _request("GET", "/share", params={"page": page, "per_page": 500}, envelope=True)
        batch = body.get("data") or []
        shares.extend(batch)
        if not batch or page >= (body.get("pages") or 1):
            return shares
        page += 1


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

    for share in _all_shares():
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


def extend_access_for_subscription(subscription: str, invoice: str = None) -> int:
    """Push every enrollment on this subscription one period further.

    Cumulative from the current expiry — `max(current, today) + one period` — so
    paying early never costs the learner the days already paid for. Same rule as
    the cloud instances (neoffice_devops.cloud.instance_validity).

    `invoice` makes the call idempotent: the same invoice reaching this code
    twice — and it does, see the hooks below — must not buy two periods.
    """
    enrollments = frappe.get_all(
        "LMS Enrollment",
        filters={"subscription": subscription},
        fields=["name", "access_valid_till", "last_grant_invoice"],
    )
    if not enrollments:
        return 0

    months = _period_months(subscription)
    today = getdate(nowdate())
    extended = 0

    for enrollment in enrollments:
        if invoice and enrollment.last_grant_invoice == invoice:
            continue
        current = getdate(enrollment.access_valid_till) if enrollment.access_valid_till else None
        base = max(current, today) if current else today
        frappe.db.set_value(
            "LMS Enrollment",
            enrollment.name,
            {
                "access_valid_till": add_months(base, months),
                "last_grant_invoice": invoice,
            },
        )
        extended += 1

    return extended


def invoice_outstanding(invoice) -> float:
    """Outstanding amount read from the database, not from the doc in hand.

    Frappe runs the controller's own on_submit before the hooked methods, and
    ERPNext settles the invoice inside it (make_gl_entries → update_outstanding_amt,
    a raw UPDATE). The document we are handed can therefore still carry the
    pre-payment figure while the row is already at zero.
    """
    stored = frappe.db.get_value("Sales Invoice", invoice.name, "outstanding_amount")
    if stored is None:
        stored = invoice.get("outstanding_amount")
    return flt(stored)


def _extend_from_invoice(invoice) -> None:
    if invoice_outstanding(invoice) > 0.01:
        return
    if not invoice.get("subscription"):
        return

    count = extend_access_for_subscription(invoice.subscription, invoice.name)
    if count:
        frappe.logger().info(
            "LMS course access extended for {0} enrollment(s) via {1}".format(
                count, invoice.name
            )
        )


def on_invoice_paid(doc, method=None):
    """Sales Invoice → on_submit AND on_update_after_submit.

    Both, because a webshop order arrives already settled: ERPNext's
    PaymentRequest.set_as_paid() submits the Payment Entry first, then builds
    the invoice with allocate_advances_automatically, so the invoice is born
    with outstanding 0 and never gets updated afterwards. With
    on_update_after_submit alone, nothing fires on a real online purchase —
    measured on osiris, 0 enrollment. `last_grant_invoice` keeps the two hooks
    from paying twice.
    """
    _extend_from_invoice(doc)


def on_payment_entry_submitted(doc, method=None):
    """Payment Entry → on_submit.

    A Payment Entry settles its invoices with `db_set`, which does NOT fire
    `on_update_after_submit`. Without this second hook, a real payment would
    never extend anyone's course access.

    Note this catches the "invoice first, paid later" case only: on the webshop
    tunnel the Payment Entry is submitted against the Sales Order, before the
    invoice exists, so its references hold no Sales Invoice yet. That case is
    covered by on_invoice_paid above.
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
    """Media ids referenced by a lesson — macro form AND editor block.

    Two shapes, because a lesson has two possible bodies:

    - `body`, l'écriture historique : une ligne `{{ SecureVideo("id") }}` ;
    - `content`, ce que produit l'éditeur par blocs : un bloc
      `{"type": "secureVideo", "data": {"media": "id"}}`.

    🔴 Ce garde-fou est ce qui empêche `get_playback_url` de signer n'importe
    quel média du catalogue. S'il ne connaît qu'une des deux formes, une vidéo
    posée depuis l'éditeur se voit répondre « cette vidéo n'appartient pas à la
    leçon » — refus au visionnage, sur une leçon parfaitement valide.
    """
    trouves = list(SECURE_VIDEO_RE.findall(body or ""))

    texte = (body or "").lstrip()
    if texte.startswith("{"):
        try:
            blocs = json.loads(texte).get("blocks") or []
        except (ValueError, AttributeError):
            blocs = []
        for bloc in blocs:
            if isinstance(bloc, dict) and bloc.get("type") == "secureVideo":
                media = (bloc.get("data") or {}).get("media")
                if media and media not in trouves:
                    trouves.append(media)
    return trouves


# allow_guest, like upstream's get_lesson: an anonymous visitor must be able to
# watch a preview lesson, which is the whole point of a free teaser. The gate is
# resolve_lesson_access below, not the decorator — without allow_guest the call is
# rejected before reaching it and the player shows "Internal Server Error".
@frappe.whitelist(allow_guest=True)
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

    # Reuse upstream's resolver rather than re-deriving the rules: it also
    # requires the course to be published and guest access to be allowed before
    # honouring include_in_preview, and it already calls our subscription guard.
    from lms.lms.permissions import resolve_lesson_access

    _is_instructor, can_access = resolve_lesson_access(lesson)
    if not can_access:
        access = get_course_access(lesson_doc.course)
        frappe.throw(access_denied_message(access), frappe.PermissionError)

    share_id = _get_or_create_share(media_id)
    token = _mint_token(share_id)

    return {
        "url": "https://player.vod2.infomaniak.com/embed/{0}?{1}".format(share_id, token),
        "media": media_id,
        # The player is reloaded before this runs out; the caller re-requests.
        "expires_in": 300,
    }
