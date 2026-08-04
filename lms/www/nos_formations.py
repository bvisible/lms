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

    # 🔴 L'interrupteur d'abord : une maison qui ne vend pas de formation ne doit
    # pas exposer une page de catalogue vide. C'est exactement ce que fait la
    # boutique avec `Webshop Settings.enabled` — sans quoi un visiteur tombe sur
    # une promesse que personne ne tient.
    if not showing_courses():
        raise frappe.DoesNotExistError

    context.no_cache = 1
    context.free_courses = _courses(paid=False)
    context.paid_courses = _courses(paid=True)

    # Les catégories réellement portées par des cours publiés — jamais la liste
    # brute du doctype, qui traîne encore « Web Development » et « Finance »
    # depuis les données de démonstration du LMS. Une catégorie vide est un
    # filtre qui ne rend rien : mieux vaut ne pas la proposer.
    toutes = context.free_courses + context.paid_courses
    vues, ordre = {}, []
    for c in toutes:
        if not c.get("category"):
            continue
        if c.category not in vues:
            vues[c.category] = 0
            ordre.append(c.category)
        vues[c.category] += 1
    context.categories = [{"name": n, "count": vues[n]} for n in sorted(ordre)]

    # Le filtre passe par l'URL : un lien vers « /nos-formations?categorie=Hatha
    # Yoga » se partage et se met en favori, ce qu'un filtre en JavaScript ne
    # permet pas.
    choisie = (frappe.form_dict.get("categorie") or "").strip()
    context.chosen_category = choisie if choisie in vues else None
    if context.chosen_category:
        context.free_courses = [c for c in context.free_courses if c.get("category") == choisie]
        context.paid_courses = [c for c in context.paid_courses if c.get("category") == choisie]

    context.nothing_yet = not toutes
    context.title = frappe.db.get_single_value("Website Settings", "app_name") or "Formations"
    return context


def showing_courses() -> bool:
    """Le site montre-t-il ses formations ?

    Deux conditions, et la seconde compte autant que la première : l'interrupteur
    doit être mis, ET il doit y avoir au moins un cours publié. Une page de
    catalogue vide annonce un métier qu'on n'exerce pas.
    """
    if not frappe.db.get_single_value("LMS Settings", "neo_show_on_website"):
        return False
    return bool(frappe.db.count("LMS Course", {"published": 1}))


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
        row.price_label = _price(row.course_price, row.currency) if paid else None
        row.lms_url = "/lms/courses/{0}".format(row.name)
        row.shop_url = None
        row.access = None

        row.offers = []

        if paid:
            # 🔴 Un cours peut se vendre en PLUSIEURS offres — trois mois, un an,
            # permanent. Le code n'en lisait qu'une, sans tri : la première
            # venue. Mesuré avec deux offres réelles (12 mois à 180.–, 3 mois à
            # 95.–), la carte n'annonçait que celle créée en dernier, et le prix
            # affiché venait du COURS, pas de l'article qu'on achetait.
            from lms.lms.neoffice_commerce import offers_for

            row.offers = offers_for(row.name)
            for offre in row.offers:
                offre["access"] = (
                    frappe._("Permanent access") if not offre["months"] else _n_months(offre["months"])
                )
                offre["price_label"] = _price(offre["price"], row.currency)

            if row.offers:
                # Le prix annoncé est celui qu'on paiera — donc celui de
                # l'article, jamais `course_price`, que rien ne tient à jour dès
                # lors que la vente passe par la boutique.
                row.price_label = row.offers[0]["price_label"]
                if len(row.offers) > 1:
                    row.price_label = frappe._("from {0}").format(row.price_label)
                row.access = row.offers[0]["access"] if len(row.offers) == 1 else None
                row.shop_url = row.offers[0]["route"]

    return rows


def _price(amount, currency) -> str:
    """« CHF 180.– », la convention du design system Neoffice.

    fmt_money ne préfixe pas le symbole (CHF n'en a pas de renseigné dans le
    doctype Currency), et un montant rond s'écrit avec un tiret, pas « .00 ».
    """
    amount = frappe.utils.flt(amount)
    cur = currency or "CHF"
    if amount == int(amount):
        return "{0} {1}.–".format(cur, int(amount))
    return "{0} {1}".format(cur, frappe.utils.fmt_money(amount, precision=2))


def _n_months(months: int) -> str:
    if months % 12 == 0:
        years = months // 12
        if years == 1:
            return frappe._("1 year of access")
        return frappe._("{0} years of access").format(years)
    return frappe._("{0} months of access").format(months)

