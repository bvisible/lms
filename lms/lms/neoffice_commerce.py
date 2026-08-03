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
from frappe.utils import add_months, flt, getdate, nowdate

# 🔴 `insert_after: "description"` posait la section dans l'onglet **Détails**,
# entre la description et la suite — et une Section Break n'ouvre pas seulement
# la sienne, elle FERME la précédente : « Marque », « PDF », « Média » et
# « Article alcoolisé » se retrouvaient rangés sous « Cours en ligne », qui ne
# les concerne en rien. Vu à l'écran le 2026-08-03.
#
# La place juste est l'onglet **Vente** : vendre un cours est un fait
# commercial, au même titre que l'unité de vente ou la remise maximale. Posée
# après `max_discount`, la section ferme proprement le bloc à deux colonnes et
# la section « Détails du client » ferme la nôtre.
#
# ⚠️ PAS de `_()` sur les libellés : ils sont évalués à l'IMPORT du module, donc
# sans langue d'utilisateur, et la traduction obtenue est écrite en dur dans le
# Custom Field. On stocke l'anglais ; Frappe traduit au rendu, pour chacun dans
# sa langue.
ITEM_FIELDS = {
    "Item": [
        {
            "fieldname": "lms_section",
            "fieldtype": "Section Break",
            "label": "Online Course",
            "insert_after": "max_discount",
            "collapsible": 1,
        },
        {
            "fieldname": "lms_course",
            "fieldtype": "Link",
            "label": "Course",
            "options": "LMS Course",
            "insert_after": "lms_section",
            "description": "Paying an invoice for this item enrols the buyer in this course.",
        },
        {
            "fieldname": "lms_access_months",
            "fieldtype": "Int",
            "label": "Access Duration (months)",
            "insert_after": "lms_course",
            "depends_on": "lms_course",
            "description": "0 means permanent access.",
        },
    ]
}


def setup_custom_fields():
    """Idempotent — safe on every migrate."""
    create_custom_fields(ITEM_FIELDS, ignore_validate=True)
    _put_the_section_back_where_it_belongs()


def refuse_course_on_a_bookable_item(doc, method=None):
    """Un article vend un cours OU se réserve, jamais les deux.

    🔴 Un article porte **un seul prix**, et les deux offres n'ont aucune raison
    de valoir la même chose. Mesuré le 2026-08-03 sur osiris : trois articles
    vendaient un cours à 90/120/180 et ont reçu, en devenant réservables, le
    prix de la **séance** — 35/28/22. La page du cours a continué d'annoncer
    l'ancien prix pendant que le panier facturait le nouveau. Personne n'avait
    rien fait de mal : rien n'interdisait la combinaison.

    Le garde-fou vit des deux côtés — ici pour l'article qu'on rend vendeur d'un
    cours, et dans `Booking Profile.validate` pour l'article qu'on rend
    réservable. Quel que soit l'ordre, le second geste est refusé.

    Pour vendre les deux, il faut **deux articles** : « le programme filmé » et
    « la séance ». C'est d'ailleurs déjà la règle côté réservation, où un
    article ne peut porter qu'une seule prestation.
    """
    if not doc.get("lms_course"):
        return
    if not frappe.db.exists("DocType", "Booking Profile"):
        return

    profil = frappe.db.get_value("Booking Profile", {"item": doc.name}, "name")
    if not profil:
        return

    frappe.throw(
        _(
            "{0} is already bookable ({1}), so it cannot also sell a course: an item "
            "carries one price, and a class and a filmed programme are rarely worth "
            "the same. Create a second item for the course."
        ).format(doc.name, profil),
        title=_("One item, one offer"),
    )


def _put_the_section_back_where_it_belongs():
    """Remettre la section au bon endroit sur ce qui est déjà installé.

    `create_custom_fields` ne crée que ce qui manque : un champ déjà posé garde
    la place qu'on lui avait donnée. Les instances installées avant la
    correction gardaient donc « Cours en ligne » dans l'onglet Détails, où il
    happait Marque, PDF et Média.

    Fait ici plutôt que dans un patch : cette fonction tourne à chaque migrate
    sur toute la flotte, et déplacer un champ est idempotent — au deuxième
    passage il n'y a plus rien à faire.
    """
    bouge = False
    for df in ITEM_FIELDS["Item"]:
        nom = frappe.db.get_value("Custom Field", {"dt": "Item", "fieldname": df["fieldname"]}, "name")
        if not nom:
            continue
        if frappe.db.get_value("Custom Field", nom, "insert_after") == df["insert_after"]:
            continue
        # Le champ d'ancrage doit exister, sinon le formulaire se réordonne au
        # hasard : mieux vaut ne rien bouger que casser la mise en page.
        if not frappe.get_meta("Item").get_field(df["insert_after"]):
            continue
        frappe.db.set_value("Custom Field", nom, "insert_after", df["insert_after"])
        bouge = True

    if bouge:
        frappe.clear_cache(doctype="Item")


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


def _grant(course: str, member: str, months: int, invoice: str = None) -> str:
    """Create or extend the enrolment. Cumulative, like the cloud instances.

    `invoice` is the idempotency key: the same invoice reaches this code from
    two hooks, and adding the months twice would hand out a free period.
    """
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
                "last_grant_invoice": invoice,
            }
        ).insert(ignore_permissions=True)
        return doc.name

    if invoice and frappe.db.get_value("LMS Enrollment", name, "last_grant_invoice") == invoice:
        return name

    if not months:
        # A permanent purchase clears any expiry the learner had.
        frappe.db.set_value(
            "LMS Enrollment", name, {"access_valid_till": None, "last_grant_invoice": invoice}
        )
        return name

    current = frappe.db.get_value("LMS Enrollment", name, "access_valid_till")
    base = max(getdate(current), today) if current else today
    frappe.db.set_value(
        "LMS Enrollment",
        name,
        {"access_valid_till": add_months(base, months), "last_grant_invoice": invoice},
    )
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
        granted.append(_grant(course, member, months, invoice.name))

    frappe.logger().info(
        "LMS: {0} enrolled in {1} course(s) via {2}".format(member, len(granted), invoice.name)
    )
    return granted


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def _if_paid(invoice):
    from lms.lms.neoffice_video import invoice_outstanding

    if invoice_outstanding(invoice) > 0.01:
        return
    grant_courses_for_invoice(invoice)


def on_invoice_paid(doc, method=None):
    """Sales Invoice → on_submit AND on_update_after_submit.

    on_submit matters because a webshop order arrives already settled. ERPNext's
    PaymentRequest.set_as_paid() (payment_request.py) submits the Payment Entry
    against the Sales Order first, then calls make_invoice(), which inserts the
    invoice with allocate_advances_automatically and submits it. The invoice is
    therefore born with outstanding 0 and is never modified again — so
    on_update_after_submit alone fires on nothing. Measured on osiris before the
    fix: a full purchase through the tunnel enrolled zero learners.

    `last_grant_invoice` on the enrolment stops the two hooks granting twice.
    """
    _if_paid(doc)


def on_payment_entry_submitted(doc, method=None):
    """Payment Entry → on_submit.

    A Payment Entry settles its invoices with `db_set`, which never fires
    on_update_after_submit — without this second hook a payment recorded against
    an existing invoice would enrol nobody. Same trap as neoffice_video and as
    the cloud instances.

    It does NOT cover the webshop tunnel: there the Payment Entry references the
    Sales Order and is submitted before any invoice exists. See on_invoice_paid.
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


# ---------------------------------------------------------------------------
# The course page needs to send the buyer to the cart, not to LMS billing
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def offers_for(course: str) -> list:
    """Toutes les offres qui vendent ce cours, de la moins chère à la plus chère.

    🔴 Un cours peut se vendre en plusieurs offres — trois mois, un an,
    permanent — et c'est même la raison pour laquelle la durée d'accès vit sur
    l'ARTICLE et non sur le cours. Le code, lui, n'en lisait qu'une : un
    `get_value` sans tri, donc **la première venue**. Mesuré sur osiris avec
    deux offres réelles (12 mois à 180.–, 3 mois à 95.–) : le bouton « Acheter »
    et le catalogue pointaient tous deux sur celle créée en DERNIER, et l'autre
    n'existait plus pour personne.

    Une offre sans fiche boutique publiée n'en est pas une : on ne peut pas
    l'acheter, donc on ne l'annonce pas.
    """
    if not course:
        return []

    liste = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    offres = []
    for item in frappe.get_all(
        "Item", filters={"lms_course": course, "disabled": 0}, fields=["name", "item_name", "lms_access_months"]
    ):
        route = frappe.db.get_value("Website Item", {"item_code": item.name, "published": 1}, "route")
        if not route:
            continue
        prix = flt(
            frappe.db.get_value(
                "Item Price", {"item_code": item.name, "price_list": liste, "selling": 1}, "price_list_rate"
            )
        )
        offres.append(
            {
                "item": item.name,
                "label": item.item_name or item.name,
                "months": int(item.lms_access_months or 0),
                "price": prix,
                "route": "/" + route.lstrip("/"),
            }
        )

    # Du moins cher au plus cher : c'est l'ordre dans lequel on lit une gamme,
    # et il rend le choix du bouton unique DÉTERMINISTE.
    offres.sort(key=lambda o: (o["price"], o["months"]))
    return offres


def get_shop_route(course: str) -> str | None:
    """Public shop route of the Item selling this course, or None.

    The course page uses it to point its buy button at the cart. Without it the
    LMS falls back to its own checkout, and two purchase tunnels coexist for the
    same course — the LMS one bypassing the cart, TWINT, Stripe and the invoice.

    Quand plusieurs offres existent, c'est **la moins chère** — « à partir de »,
    la convention de toute gamme. Le catalogue, lui, les montre toutes : un
    bouton unique ne peut pas poser un choix, une liste si.
    """
    offres = offers_for(course)
    return offres[0]["route"] if offres else None
