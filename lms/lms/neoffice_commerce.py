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
from frappe.utils import add_months, cint, flt, getdate, nowdate

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


# Le cours porte l'article et la gamme de prix — exactement comme une
# `Booking Profile` porte son article et sa table de forfaits.
#
# 🔑 Pourquoi la table plutôt que plusieurs articles (Jérémy, 2026-08-03) :
# « si on fait plusieurs articles on risque d'avoir des dérives sur les
# articles ». C'est vrai et c'était déjà commencé — deux articles pour le même
# cours Hatha avaient déjà deux noms, deux descriptions, deux images et deux
# routes (`/cours/…` et `/services/…`). Un cours, un article, un texte ; les
# durées sont des lignes, pas des produits.
COURSE_FIELDS = {
    "LMS Course": [
        {
            "fieldname": "neo_shop_section",
            "fieldtype": "Section Break",
            "label": "Selling",
            "insert_after": "currency",
            "collapsible": 1,
        },
        {
            "fieldname": "neo_item",
            "fieldtype": "Link",
            "label": "Item",
            "options": "Item",
            "insert_after": "neo_shop_section",
            "description": "The article that sells this course. Its shop page is where it is bought.",
        },
        {
            "fieldname": "neo_offers",
            "fieldtype": "Table",
            "label": "Offers",
            "options": "LMS Course Offer",
            "insert_after": "neo_item",
            "depends_on": "neo_item",
            "description": "One line per access duration. Left empty, the article's own price applies.",
        },
    ]
}


# Le site montre-t-il ses formations ? La boutique a `Webshop Settings.enabled`
# depuis toujours ; les formations n'avaient rien, et une maison qui n'en vend
# pas se retrouvait avec une entrée de menu et une page de catalogue vide.
SETTINGS_FIELDS = {
    "LMS Settings": [
        {
            "fieldname": "neo_website_section",
            "fieldtype": "Section Break",
            "label": "The public catalogue",
            # 🔴 PAS après `allow_guest_access` : une Section Break n'ouvre pas
            # seulement la sienne, elle FERME la précédente — « Ne pas permettre
            # d'avancer les vidéos », « Désactiver la PWA » et le reste du bloc
            # général se retrouvaient rangés sous « Le catalogue public ». Le
            # même piège que sur la fiche article ce matin, refait le soir même.
            # Posée sur le DERNIER champ du bloc général, elle est fermée par la
            # section « Notifications » qui suit.
            "insert_after": "livecode_url",
            "collapsible": 0,
        },
        {
            "fieldname": "neo_show_on_website",
            "fieldtype": "Check",
            "label": "Show the courses on the website",
            "insert_after": "neo_website_section",
            "default": "1",
            "description": "Adds « Our courses » to the site menu and opens /nos-formations. Off, the page and the menu entry disappear.",
        },
    ]
}


def setup_custom_fields():
    """Idempotent — safe on every migrate."""
    create_custom_fields(ITEM_FIELDS, ignore_validate=True)
    create_custom_fields(SETTINGS_FIELDS, ignore_validate=True)
    _move_the_catalogue_section()
    _switch_on_where_there_are_courses()
    if frappe.db.exists("DocType", "LMS Course Offer"):
        create_custom_fields(COURSE_FIELDS, ignore_validate=True)
    _put_the_section_back_where_it_belongs()


def _move_the_catalogue_section():
    """Remettre la section au bon endroit là où elle a déjà été posée."""
    nom = frappe.db.get_value("Custom Field", {"dt": "LMS Settings", "fieldname": "neo_website_section"}, "name")
    if not nom:
        return
    if frappe.db.get_value("Custom Field", nom, "insert_after") == "livecode_url":
        return
    if not frappe.get_meta("LMS Settings").get_field("livecode_url"):
        return
    frappe.db.set_value("Custom Field", nom, "insert_after", "livecode_url")
    frappe.db.set_value(
        "Custom Field",
        {"dt": "LMS Settings", "fieldname": "neo_show_on_website"},
        "insert_after",
        "neo_website_section",
    )
    frappe.clear_cache(doctype="LMS Settings")


def _switch_on_where_there_are_courses():
    """Une instance qui montrait déjà ses formations doit continuer.

    🔴 **Le `default` d'un Custom Field ne s'applique PAS à un Single qui existe
    déjà.** `LMS Settings` est un Single créé de longue date : la case est
    arrivée à zéro malgré `"default": "1"`, la page a répondu 404 et l'entrée du
    menu a disparu — sur une instance où les formations marchaient la minute
    d'avant. Mesuré sur osiris.

    On ne pose donc la valeur qu'une fois, et seulement là où il y a quelque
    chose à montrer : un site sans cours publié reste éteint, ce qui est le bon
    défaut pour tous les autres.
    """
    if frappe.db.exists("Singles", {"doctype": "LMS Settings", "field": "neo_show_on_website"}):
        return
    if not frappe.db.count("LMS Course", {"published": 1}):
        return
    frappe.db.set_single_value("LMS Settings", "neo_show_on_website", 1)


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
    champs = ["item_code"]
    marque = frappe.db.has_column("Sales Invoice Item", "lms_offer")
    if marque:
        champs += ["lms_offer", "lms_months"]

    lines = frappe.get_all("Sales Invoice Item", filters={"parent": invoice.name}, fields=champs)
    if not lines:
        return []

    courses = []
    for line in lines:
        # 🔑 La durée MARQUÉE sur la ligne l'emporte : c'est celle que le client
        # a choisie et payée. La relire sur l'article donnerait la durée
        # d'aujourd'hui, qui a pu changer entre l'achat et l'encaissement — et
        # sur un article qui vend trois durées, elle ne voudrait rien dire.
        if marque and line.get("lms_offer"):
            course = course_sold_by(line.item_code)
            if course:
                courses.append((course, int(line.get("lms_months") or 0)))
                continue

        # Sans marquage : le chemin historique, un article = une durée.
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
def keep_the_course_price_honest(doc, method=None):
    """Le prix annoncé par le cours doit être celui qu'on paiera.

    🔑 Trois états possibles, et un seul est bâtard :

    - **pas d'article** → le cours est ouvert, gratuit. Rien à faire : c'est le
      cas de tous les cours d'introduction, et ça marche depuis toujours.
    - **un article** → le cours est vendu, aux prix de sa table d'offres. Le
      champ `course_price` reprend alors **la moins chère** — il ne peut plus
      contredire la caisse.
    - **payant mais sans article** → le cours réclame de l'argent que personne
      ne peut lui donner. `paid_course` bloque l'inscription, la boutique n'a
      rien à vendre, et le visiteur remplit un formulaire qui ne mène nulle
      part. On le dit ici, au seul endroit où quelqu'un peut le corriger.

    ⚠️ `paid_course` n'est PAS dérivé de la présence d'un article : c'est le
    verrou du LMS lui-même, celui qui empêche de s'inscrire sans payer. Le
    mettre à zéro ouvrirait le cours à tout le monde. Seul le PRIX est dérivé.
    """
    offres = offers_for(doc.name)

    if offres:
        moins_chere = offres[0]["price"]
        if flt(doc.get("course_price")) != flt(moins_chere):
            doc.course_price = moins_chere
        if not doc.get("paid_course"):
            doc.paid_course = 1
        _align_the_item_price(offres[0])
        return

    if doc.get("paid_course") and doc.get("published"):
        frappe.msgprint(
            _(
                "This course is marked as paid but no article sells it: nobody can buy "
                "it. Set the article and its offers in the « Selling » section, or "
                "uncheck « Paid course » to open it."
            ),
            title=_("Paid, and unbuyable"),
            indicator="orange",
        )


def _align_the_item_price(offre: dict) -> None:
    """Le tarif de l'article suit l'offre la moins chère.

    🔴 Vu à l'écran : l'en-tête de la fiche annonçait **CHF 180.00** — le prix
    de liste de l'article — pendant que « 3 mois à 95.– » était coché juste en
    dessous. Le sélecteur corrige l'affichage en JavaScript, mais un prix faux
    entre le chargement et le script reste un prix faux ; et le catalogue, les
    recommandations et le référencement lisent celui-là, pas le nôtre.

    Le tarif de l'article devient donc le « à partir de » de la gamme. Il ne
    décide plus de rien — la ligne de panier porte le prix de l'offre choisie —
    mais il ne ment plus.
    """
    liste = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    if not liste:
        return
    nom = frappe.db.get_value(
        "Item Price", {"item_code": offre["item"], "price_list": liste, "selling": 1}, "name"
    )
    if not nom:
        return
    if flt(frappe.db.get_value("Item Price", nom, "price_list_rate")) != flt(offre["price"]):
        frappe.db.set_value("Item Price", nom, "price_list_rate", flt(offre["price"]))


def _the_selling_item(course: str) -> str | None:
    """L'article qui vend ce cours, selon le cours lui-même.

    Le lien vit désormais sur le COURS — `LMS Course.neo_item` — exactement
    comme `Booking Profile.item` : la chose vendue désigne son article, et non
    l'inverse. Tant qu'un cours n'a pas été repris, on retombe sur l'ancien sens
    (`Item.lms_course`) pour ne casser aucune vente en cours.
    """
    if not frappe.get_meta("LMS Course").has_field("neo_item"):
        return None
    item = frappe.db.get_value("LMS Course", course, "neo_item")
    if item and frappe.db.get_value("Item", item, "disabled") == 0:
        return item
    return None


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

    # 🔑 Le modèle voulu : UN article sur le cours, et une table de durées —
    # comme une prestation réservable porte son article et ses forfaits. Le prix
    # de l'article devient secondaire : il ne sert que là où la table est vide.
    porteur = _the_selling_item(course)
    lignes = frappe.get_all(
        "LMS Course Offer",
        filters={"parent": course, "parenttype": "LMS Course"},
        fields=["label", "months", "price"],
        order_by="idx asc",
    ) if frappe.db.exists("DocType", "LMS Course Offer") else []

    if porteur and lignes:
        route = frappe.db.get_value("Website Item", {"item_code": porteur, "published": 1}, "route")
        if not route:
            return []
        route = "/" + route.lstrip("/")
        offres = [
            {
                "item": porteur,
                "label": l.label,
                "months": int(l.months or 0),
                "price": flt(l.price),
                # Une seule fiche boutique : c'est la DURÉE qui se choisit
                # dessus, comme des dates se choisissent sur une location.
                "route": route,
            }
            for l in lignes
        ]
        offres.sort(key=lambda o: (o["price"], o["months"]))
        return offres

    # Le chemin historique — un article par durée — reste lu tant que la flotte
    # n'est pas passée à la table. Il n'est plus la façon de faire.
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


# ---------------------------------------------------------------------------
# Making the catalogue reachable
# ---------------------------------------------------------------------------


def ensure_courses_link(label: str = None, url: str = "/nos-formations") -> str:
    """Poser l'entrée « Nos formations » dans le menu du site, une fois.

    🔴 La page existait et **rien ne pointait dessus**. Une page que personne ne
    peut atteindre n'existe pas du point de vue d'un client, et le menu du site
    est l'endroit où il regarde. Exactement la panne qu'avait déjà connue la
    boutique — dont l'entrée avait disparu lors d'une refonte — et celle que
    `neoffice_theme.booking.shop.ensure_shop_link` corrige pour « Réserver ».

    Idempotent sur l'URL, pas sur le libellé : une entrée que le propriétaire a
    renommée reste cette entrée, et en ajouter une seconde reviendrait à
    discuter avec le site de ce que son propre menu raconte.

    Délibérément une commande qu'on lance plutôt qu'un hook : une maison qui ne
    vend aucun cours n'a pas à voir pousser « Nos formations » dans son menu, et
    un menu est une chose que le propriétaire du site arrange.
    """
    settings = frappe.get_doc("Website Settings")
    rows = settings.get("top_bar_items") or []

    for row in rows:
        if (row.url or "").rstrip("/") == url.rstrip("/"):
            return row.label

    # ⚠️ Le libellé d'un menu est une **donnée**, pas un `df.label` : la barre du
    # site l'affiche tel quel, sans le traduire. Il doit donc être stocké DÉJÀ
    # traduit — et dans la langue du SITE, pas dans celle de la session qui
    # lance la commande, qui n'en a souvent aucune. Sans le `lang`, l'entrée
    # s'appelait « Our courses » au milieu d'un menu français. Mesuré.
    label = label or _("Our courses", lang=frappe.db.get_default("lang") or "fr")
    settings.append("top_bar_items", {"label": label, "url": url})
    settings.flags.ignore_permissions = True
    settings.save(ignore_permissions=True)
    return label


def sync_courses_link(doc=None, method=None, url: str = "/nos-formations") -> None:
    """Le menu suit l'interrupteur — on met, on retire.

    🔑 `ensure_courses_link` ne fait qu'ajouter : c'est une commande qu'on lance
    une fois. Ici c'est l'inverse — un réglage qu'on bascule, et le menu doit
    suivre **dans les deux sens**. Décocher la case et laisser l'entrée mènerait
    le visiteur à une page qui n'existe plus.

    Posé sur `LMS Settings.on_update` : le geste et sa conséquence au même
    endroit, sans rien à relancer à la main.
    """
    from lms.www.nos_formations import showing_courses

    montrer = showing_courses()
    settings = frappe.get_doc("Website Settings")
    rows = settings.get("top_bar_items") or []
    presente = [r for r in rows if (r.url or "").rstrip("/") == url.rstrip("/")]

    if montrer and not presente:
        ensure_courses_link(url=url)
        return

    if not montrer and presente:
        for r in presente:
            settings.remove(r)
        settings.flags.ignore_permissions = True
        settings.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# La durée choisie, du panier jusqu'à l'inscription
# ---------------------------------------------------------------------------

CART_DOCTYPES = ("Quotation Item", "Sales Order Item", "Sales Invoice Item")


def setup_cart_fields():
    """Le marquage qui dit « cette ligne est une offre de cours », et laquelle.

    🔑 Deux champs et pas un : `lms_offer` porte le libellé — ce que le client a
    choisi, lisible sur sa facture — et `lms_months` porte la durée, qui est ce
    qui accorde réellement l'accès. Un seul entier ne suffirait pas : **zéro
    signifie permanent**, on ne pourrait donc pas distinguer « offre permanente »
    de « pas d'offre du tout ». Le libellé sert de présence.

    La durée est FIGÉE sur la ligne, pas relue au moment du paiement : entre
    l'achat et l'encaissement, la table des offres a pu changer, et le client a
    droit à ce qu'il a acheté.
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(
        {
            dt: [
                {
                    "fieldname": "lms_offer",
                    "fieldtype": "Data",
                    "label": "Course offer",
                    "insert_after": "item_name",
                    "read_only": 1,
                    "no_copy": 0,
                    "print_hide": 0,
                },
                {
                    "fieldname": "lms_months",
                    "fieldtype": "Int",
                    "label": "Access months",
                    "insert_after": "lms_offer",
                    "read_only": 1,
                    "print_hide": 1,
                },
            ]
            for dt in CART_DOCTYPES
        },
        ignore_validate=True,
    )


def _offer_named(course: str, label: str) -> dict | None:
    for offre in offers_for(course):
        if offre["label"] == label:
            return offre
    return None


def course_sold_by(item_code: str) -> str | None:
    """Le cours que vend cet article — dans le sens neuf, puis dans l'ancien."""
    if not item_code:
        return None
    if frappe.get_meta("LMS Course").has_field("neo_item"):
        course = frappe.db.get_value("LMS Course", {"neo_item": item_code}, "name")
        if course:
            return course
    return frappe.db.get_value("Item", item_code, "lms_course")


@frappe.whitelist(allow_guest=True)
def add_offer_to_cart(item_code: str, offer: str):
    """Mettre au panier la durée choisie sur la fiche boutique.

    🔴 `update_cart` de webshop ne sait pas transporter un choix : elle ne prend
    qu'un article et une quantité. La durée voulue se perdait donc entre la page
    et le panier — c'est exactement pour cela qu'on avait fini par créer un
    article par durée. On passe donc par la boutique pour la mécanique (le
    devis, le client, la fiscalité), puis on marque la ligne et on y pose le
    prix de l'offre.
    """
    course = course_sold_by(item_code)
    if not course:
        frappe.throw(_("{0} does not sell a course.").format(item_code))

    choix = _offer_named(course, offer)
    if not choix:
        frappe.throw(_("Unknown offer: {0}").format(offer))

    from webshop.webshop.shopping_cart.cart import _get_cart_quotation, update_cart

    update_cart(item_code, qty=1)

    doc = _get_cart_quotation()
    ligne = None
    for row in doc.items or []:
        if row.item_code == item_code:
            ligne = row  # la dernière l'emporte : c'est celle qu'on vient d'ajouter
    if not ligne:
        frappe.throw(_("The line could not be found in the cart."))

    ligne.lms_offer = choix["label"]
    ligne.lms_months = choix["months"]
    ligne.rate = choix["price"]
    ligne.price_list_rate = choix["price"]
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"offer": choix["label"], "price": choix["price"]}


def hold_the_offer_price(doc, method=None):
    """Quotation before_validate — une ligne marquée garde le prix de son offre.

    Sans cela, le contrôleur retarife la ligne depuis la liste de prix de
    l'article à chaque enregistrement, et l'offre « 3 mois » repasserait au prix
    de l'offre par défaut au premier changement de panier. Le même geste que
    pour les options de réservation : ce qui est marqué est à nous, et se
    réécrit à chaque tour.
    """
    if doc.get("order_type") != "Shopping Cart" or doc.docstatus != 0:
        return
    if not frappe.db.has_column("Quotation Item", "lms_offer"):
        return

    for row in doc.items or []:
        if not row.get("lms_offer"):
            continue
        course = course_sold_by(row.item_code)
        if not course:
            continue
        choix = _offer_named(course, row.lms_offer)
        if not choix:
            continue
        row.lms_months = choix["months"]
        row.rate = choix["price"]
        row.price_list_rate = choix["price"]


def course_offer_count(item_code: str) -> int:
    """Combien d'offres vend cet article — pour la vignette du catalogue.

    🔴 Une vignette affichait « CHF 90.00 » pour un cours vendu 90 ou 140 selon
    la durée : le prix le plus bas présenté comme LE prix. Il y manquait le
    « dès », et le client découvrait le reste sur la fiche.

    ⚠️ Compté en UNE requête pour toute la page, pas une par vignette : un
    catalogue de cent articles aurait payé deux cents allers-retours pour une
    mention de trois lettres. Le résultat vit le temps de la requête HTTP.
    """
    if not item_code:
        return 0
    if not frappe.db.exists("DocType", "LMS Course Offer"):
        return 0

    cache = getattr(frappe.local, "_lms_offer_counts", None)
    if cache is None:
        rows = frappe.db.sql(
            """
            SELECT c.neo_item AS item, COUNT(*) AS n
            FROM `tabLMS Course Offer` o
            JOIN `tabLMS Course` c ON c.name = o.parent
            WHERE IFNULL(c.neo_item, '') != ''
            GROUP BY c.neo_item
            """,
            as_dict=True,
        )
        cache = {r.item: cint(r.n) for r in rows}
        frappe.local._lms_offer_counts = cache
    return cache.get(item_code, 0)
