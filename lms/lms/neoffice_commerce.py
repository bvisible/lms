#//// Neoffice — added file (no upstream equivalent). Landed with d3b10e3f « un cours
#//// porte son article et sa table de durées » / eceb4034, then grown by the 2026-08
#//// « formations » series (5213816b, 0541a6d5, d830e554, 23db77a3, ac912227, 7a226d63,
#//// 9061b8d1, c203b62a, af7114c1, 94eb465e, ff0fa700, c1ce5a17, 796f67bd, 0b5ddd66).
#//// Sells a course as an ordinary ERPNext Item, so the webshop cart, TWINT, Stripe, the
#//// invoice and the accounting entries all apply to it. Upstream's paid_course flow
#//// carries its own checkout (LMS Payment + the `payments` app) and knows none of that.
#//// Kept in a module of its own so the touch points inside upstream files stay
#//// one-liners. At the merge: kept whole — only its entries in hooks.py and its one
#//// import in lms/lms/utils.py meet upstream.
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
        # ------------------------------------------------------------------
        # Les vidéos. La configuration existait — dans `site_config.json`,
        # c'est-à-dire nulle part pour qui n'a pas de terminal.
        #
        # 🔑 Jérémy, le 2026-08-04 : *« on n'a rien par rapport à Infomaniak.
        # Comment ça se passe pour les liens avec le système d'Infomaniak pour
        # les vidéos ? »* — la question qu'on se pose forcément devant un écran
        # de réglages qui n'en parle pas.
        # ------------------------------------------------------------------
        {
            "fieldname": "neo_video_section",
            "fieldtype": "Section Break",
            "label": "Videos (Infomaniak VOD)",
            "insert_after": "neo_show_on_website",
            # Ouverte. Repliée, elle cachait la seule réponse à « où se règlent
            # les vidéos ? » derrière un chevron que personne n'ouvre.
            "collapsible": 0,
            # ⚠️ **Pas de HTML ici.** Une balise dans une description passe par
            # l'assainisseur de Frappe, qui la réécrit — guillemets simples
            # changés en doubles — et la chaîne stockée ne correspond alors plus
            # au `msgid` du fichier de traduction : le texte reste en anglais
            # sans que rien ne signale l'écart. Le lien vers le manager est un
            # BOUTON (voir `neoffice_lms_settings.js`), pas un morceau de donnée.
            "description": "Where the lesson videos are hosted. Leave empty to keep whatever is in the site configuration — filling these takes over. The three values come from the Infomaniak manager: Streaming / VOD gives the channel and the account, and the API tokens of your profile give the key.",
        },
        # ⚠️ Les libellés évitent « compte », « identifiant », « jeton » seuls :
        # Chrome a pris « Compte » + un champ masqué pour un formulaire de
        # connexion et y a versé un login enregistré (« Daniel » + un mot de
        # passe), par-dessus la vraie valeur. Nommer les champs par leur
        # fournisseur suffit à casser l'heuristique — et le script du doctype
        # coupe le remplissage pour de bon.
        {
            "fieldname": "neo_vod_channel",
            "fieldtype": "Data",
            "label": "Infomaniak video channel",
            "insert_after": "neo_video_section",
            "description": "The channel number of the VOD space, from the Infomaniak manager.",
        },
        {
            "fieldname": "neo_vod_account",
            "fieldtype": "Data",
            "label": "Infomaniak account number",
            "insert_after": "neo_vod_channel",
            "description": "Every call carries it; without it the API answers a bare « access denied ».",
        },
        {
            "fieldname": "neo_vod_token",
            "fieldtype": "Password",
            "label": "Infomaniak API key",
            "insert_after": "neo_vod_account",
            "description": "An Infomaniak token carrying the VOD scope. It never leaves the server — the player receives a link signed for five minutes, never the key.",
        },
        # ------------------------------------------------------------------
        # L'interrupteur de la caisse, en tête de l'onglet des paiements.
        # ------------------------------------------------------------------
        {
            "fieldname": "neo_sell_via_shop",
            "fieldtype": "Check",
            "label": "Sell the courses through the shop",
            # Après le Tab Break, donc AU-DESSUS de `payment_section` — que le
            # script amont masque quand l'app Payments manque. Dedans, notre
            # interrupteur disparaîtrait avec elle.
            "insert_after": "payment_settings_tab",
            "default": "1",
            "description": "On, a course is bought like any other article — cart, VAT, TWINT, card terminal, invoice — and everything below is left aside. Off, the course module takes the money itself through its own gateway, and none of that applies.",
        },
    ]
}


# Les réglages de la caisse du module de formation. Ils ne servent QUE lorsque
# c'est lui qui encaisse — c'est-à-dire jamais chez nous. On ne les supprime pas
# (ils sont à l'amont), on les efface de l'écran tant que la boutique vend.
#
# `default_currency` n'en est PAS : la fiche du cours s'en sert pour libeller un
# prix, et le catalogue public l'affiche. Il reste visible.
CAISSE_DU_LMS = (
    "payment_gateway",
    "exception_country",
    "apply_gst",
    "show_usd_equivalent",
    "apply_rounding",
    "send_payment_reminders_for_batch",
    "send_payment_reminders_for_course",
    "no_payments_app",
    "payments_app_is_not_installed",
)


def setup_custom_fields():
    """Idempotent — safe on every migrate."""
    create_custom_fields(ITEM_FIELDS, ignore_validate=True)
    create_custom_fields(SETTINGS_FIELDS, ignore_validate=True)
    _move_the_catalogue_section()
    _hide_the_inert_switches()
    _fold_the_lms_checkout_away()
    _tell_the_truth_about_signup()
    _seed_the_singles()
    _switch_on_where_there_are_courses()
    if frappe.db.exists("DocType", "LMS Course Offer"):
        create_custom_fields(COURSE_FIELDS, ignore_validate=True)
    _put_the_section_back_where_it_belongs()


# Trois cases de l'onglet « Général » qui n'ont rien à y faire — vérifié le
# 2026-08-03 en cherchant leur consommateur dans tout le module, bundles exclus.
#
#   default_home       — AUCUN code ne le lit. Il ne fait rien.
#   persona_captured   — drapeau ÉCRIT par le code (`utils.py:persona_captured`)
#   demo_data_present  — drapeau ÉCRIT par le code au retrait des données de démo
#
# Les deux drapeaux ne sont pas des réglages : ce sont des marques que le
# logiciel se pose à lui-même. Les cocher ne fait rien, les décocher non plus —
# sauf semer le doute, parce que « Données de démonstration présentes » a l'air
# de promettre un nettoyage.
#
# 🔑 Un interrupteur qui ne fait rien est pire qu'un manque : on l'essaie, il ne
# se passe rien, et on doute de tout l'écran.
INERTES = (
    "default_home",
    "persona_captured",
    "demo_data_present",
    # L'onglet « Batch Settings » : des cases seulement DÉCLARÉES dans le fichier
    # de types du SPA (`LMSSettings.ts`), lues par personne.
    "show_day_view",
    "show_dashboard",
    "show_courses",
    "show_students",
    "show_assessments",
    "show_discussions",
    "show_emails",
    # Les modèles de demande de mentorat : aucun consommateur.
    "mentor_request_creation",
    "mentor_request_status_update",
)

# 🔴 L'onglet « Barre latérale » entier. `DesktopLayout.vue` monte
# **NeoCockpitLMSSidebar** à la place de l'`AppSidebar` d'origine, et notre barre
# construit ses entrées elle-même — elle ne lit aucune de ces cases. Les régler
# ne change rien à ce que voit l'apprenant.
#
# Jérémy, en regardant l'écran : *« il y a encore un menu barre latérale où je
# ne sais pas comment nous on l'a bougé, est-ce que ça marche ? »* — non.
ONGLETS_INERTES = ("sidebar_tab", "sidebar_section")


def _hide_the_inert_switches():
    """Masquer ce qui ne répond pas. Par Property Setter : rien n'est perdu.

    On ne touche pas au doctype amont — un `Property Setter` se retire d'un
    clic, et une fusion depuis l'amont ne se bat contre rien.
    """
    meta = frappe.get_meta("LMS Settings")
    bouge = False

    # L'onglet de la barre latérale : on masque le Tab Break, tout ce qui suit
    # part avec lui jusqu'au suivant.
    onglet = next(
        (f.fieldname for f in meta.fields
         if f.fieldtype == "Tab Break" and (f.label or "") == "Sidebar"),
        None,
    )
    for champ in list(INERTES) + ([onglet] if onglet else []):
        if not meta.get_field(champ):
            continue
        nom = "LMS Settings-%s-hidden" % champ
        if frappe.db.exists("Property Setter", nom):
            continue
        frappe.get_doc({
            "doctype": "Property Setter",
            "name": nom,
            "doctype_or_field": "DocField",
            "doc_type": "LMS Settings",
            "field_name": champ,
            "property": "hidden",
            "property_type": "Check",
            "value": "1",
        }).insert(ignore_permissions=True)
        bouge = True
    if bouge:
        frappe.clear_cache(doctype="LMS Settings")


def _property_setter(champ, propriete, valeur, type_="Data"):
    """Poser une propriété sur un champ amont, sans toucher au doctype."""
    nom = "LMS Settings-%s-%s" % (champ, propriete)
    if frappe.db.exists("Property Setter", nom):
        frappe.db.set_value("Property Setter", nom, "value", valeur)
        return False
    frappe.get_doc({
        "doctype": "Property Setter",
        "name": nom,
        "doctype_or_field": "DocField",
        "doc_type": "LMS Settings",
        "field_name": champ,
        "property": propriete,
        "property_type": type_,
        "value": valeur,
    }).insert(ignore_permissions=True)
    return True


def _fold_the_lms_checkout_away():
    """Tant que la boutique vend, la caisse du module de formation s'efface.

    🔑 Jérémy, le 2026-08-04, devant l'onglet « Paramètres de paiement » :
    *« là on ne met rien, donc on est d'accord (…) je pense qu'il faut un bouton
    pour désactiver tout ça, puis utiliser le shop, parce qu'actuellement ce
    n'est pas clair. »*

    Un écran de réglages qu'on remplit pour rien est une invitation à se
    tromper : régler une passerelle ici ouvrirait un second tunnel d'achat, qui
    ne connaît ni le panier, ni la TVA, ni TWINT, ni la facture. On ne supprime
    rien pour autant — l'interrupteur rend tout le bloc, à qui le veut
    vraiment.
    """
    meta = frappe.get_meta("LMS Settings")
    bouge = False
    for champ in CAISSE_DU_LMS:
        if not meta.get_field(champ):
            continue
        bouge |= _property_setter(champ, "depends_on", "eval:!doc.neo_sell_via_shop")

    if meta.get_field("default_currency"):
        # Elle survit à l'effacement : le catalogue public libelle ses prix
        # avec, et la fiche du cours la reprend. Dire à quoi elle sert évite de
        # la croire liée à la caisse qui vient de disparaître.
        bouge |= _property_setter(
            "default_currency",
            "description",
            "Labels the prices shown in the course catalogue. The actual billing "
            "currency is the company's, decided by the shop.",
            "Text",
        )
    if bouge:
        frappe.clear_cache(doctype="LMS Settings")


# L'onglet « Paramètres d'inscription ». Rien n'y est inerte — c'est même
# l'inverse, et c'est le problème : **deux de ces trois cases débordent
# largement des formations**, ce que leur onglet ne laisse pas soupçonner.
#
# 🔑 Jérémy, le 2026-08-04 : *« il faudrait voir ce que ça fait parce que nous,
# on utilise l'inscription de l'ERP, donc je ne sais pas. »*
#
# Vérifié dans le code, pas deviné :
#   `disable_signup`        → recopié dans **Website Settings** à chaque
#                             enregistrement (`lms_settings.py:validate_signup`)
#                             : la création de compte se ferme pour TOUT le
#                             site, boutique et portail compris.
#   `user_category` /       → le crochet `signup_form_template` de `hooks.py`
#   `custom_signup_content`   fait servir le formulaire du module de formation
#                             **à la place de celui du site** dès que l'un des
#                             deux est renseigné (`plugins.show_custom_signup`,
#                             lu par `frappe/www/login.py`).
#
# On ne les masque donc pas : on écrit ce qu'elles font vraiment.
VERITES_INSCRIPTION = {
    "disable_signup": "Closes account creation for the WHOLE website — saving copies this switch into Website Settings, so the shop and the customer portal stop accepting new accounts too, not only the courses.",
    "user_category": "Adds a category question to the sign-up form. Careful: filling this — or the content beside it — makes the course module's form REPLACE the site's standard sign-up form, for every visitor.",
    "custom_signup_content": "Shown on the sign-up form. As soon as it holds anything, the course module's form replaces the site's standard one, for every visitor. Leave it empty when accounts are created by the shop or by the ERP.",
}


def _tell_the_truth_about_signup():
    meta = frappe.get_meta("LMS Settings")
    bouge = False
    for champ, texte in VERITES_INSCRIPTION.items():
        if meta.get_field(champ):
            bouge |= _property_setter(champ, "description", texte, "Text")
    if bouge:
        frappe.clear_cache(doctype="LMS Settings")


# 🔴 Quatrième fois dans la même semaine : **le `default` d'un champ ne
# s'applique pas à un Single qui existe déjà**. Sans ce semis,
# `neo_sell_via_shop` naît à 0 sur toutes les instances en service — donc « la
# boutique ne vend pas », donc la caisse du LMS réapparaît et le bouton d'achat
# cesse de pointer sur le panier. Le contraire de ce qu'on installe.
def _seed_the_singles():
    reglages = frappe.get_single("LMS Settings")

    if reglages.get("neo_sell_via_shop") in (None, "", 0, "0"):
        frappe.db.set_single_value("LMS Settings", "neo_sell_via_shop", 1)

    if not reglages.get("default_currency"):
        devise = frappe.get_cached_value(
            "Company", frappe.defaults.get_user_default("Company"), "default_currency"
        ) if frappe.defaults.get_user_default("Company") else None
        devise = devise or frappe.db.get_value("Company", {}, "default_currency")
        if devise:
            frappe.db.set_single_value("LMS Settings", "default_currency", devise)

    _remonter_la_config_video(reglages)


def _remonter_la_config_video(reglages):
    """Faire remonter à l'écran ce qui était caché dans `site_config.json`.

    🔑 Jérémy, le 2026-08-04, devant les trois champs neufs : *« c'est bon mais
    vide… »* — et il a raison. Les vidéos jouaient, la configuration existait,
    mais dans un fichier que l'écran ne montrait pas. Un formulaire vide dit
    « rien n'est réglé », ce qui était faux : c'est le même mensonge que la
    période de regroupement affichée à blanc ce matin.

    On recopie donc une fois, champ par champ, et seulement ce qui manque. Le
    fichier reste lu ensuite — rien ne casse si quelqu'un vide un champ.
    """
    paires = (
        ("neo_vod_channel", "infomaniak_vod_channel"),
        ("neo_vod_account", "infomaniak_vod_account"),
        ("neo_vod_token", "infomaniak_vod_token"),
    )
    a_poser = {
        champ: frappe.conf.get(cle)
        for champ, cle in paires
        if not reglages.get(champ) and frappe.conf.get(cle)
    }
    if not a_poser:
        return

    for champ, valeur in a_poser.items():
        reglages.set(champ, valeur)
    reglages.flags.ignore_permissions = True
    reglages.flags.ignore_mandatory = True
    reglages.save(ignore_permissions=True)
    frappe.logger().info("LMS: video configuration lifted out of site_config ({0})".format(
        ", ".join(a_poser)))


def sells_through_the_shop() -> bool:
    """La boutique encaisse-t-elle les cours ? Oui, sauf décision contraire.

    Le silence vaut oui : une instance mise à jour n'a pas encore le champ, et
    répondre non ferait basculer son bouton d'achat vers une caisse que
    personne n'a configurée.
    """
    valeur = frappe.db.get_single_value("LMS Settings", "neo_sell_via_shop")
    return valeur is None or bool(cint(valeur))


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


def warn_about_the_second_tunnel(doc, method=None):
    """Régler une passerelle ici rouvre un second tunnel de paiement.

    🔴 Le module de formation a son propre encaissement (`LMS Payment` + l'app
    `payments`). Neoffice ne l'utilise pas : un cours se vend **en article**, par
    le panier, avec TVA, TWINT, terminal et facture. Les deux peuvent pourtant
    coexister — et alors le même cours s'achète de deux façons, dont une qui ne
    laisse aucune trace comptable.

    Aujourd'hui il dort : aucune passerelle réglée, zéro `LMS Payment`, et les
    trois cours payants pointent vers la boutique. On le dit avant qu'il ne se
    réveille, pas après.

    Depuis l'arrivée de l'interrupteur, l'avertissement ne se déclenche plus que
    sur la **contradiction** : une passerelle réglée alors que la boutique est
    censée vendre. Éteindre l'interrupteur est un choix assumé, et on ne
    sermonne pas quelqu'un qui vient de le faire exprès.
    """
    if not doc.get("payment_gateway"):
        return
    if not sells_through_the_shop():
        return

    frappe.msgprint(
        _(
            "A payment gateway here opens the course module's OWN checkout, which "
            "knows nothing about the cart, TWINT, the card terminal or invoicing. "
            "In Neoffice a course is sold as an article — see the « Selling » "
            "section of the course. Leave this empty unless you really want two "
            "ways to buy the same course."
        ),
        title=_("Two checkouts for the same course"),
        indicator="orange",
    )


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


@frappe.whitelist(allow_guest=True)
def get_shop_route(course: str) -> str | None:
    """Public shop route of the Item selling this course, or None.

    The course page uses it to point its buy button at the cart. Without it the
    LMS falls back to its own checkout, and two purchase tunnels coexist for the
    same course — the LMS one bypassing the cart, TWINT, Stripe and the invoice.

    Quand plusieurs offres existent, c'est **la moins chère** — « à partir de »,
    la convention de toute gamme. Le catalogue, lui, les montre toutes : un
    bouton unique ne peut pas poser un choix, une liste si.

    Et si l'interrupteur « Vendre les cours par la boutique » est éteint, on ne
    renvoie rien : c'est là tout l'effet du bouton, et il vaut mieux qu'il en
    ait un.

    🔴 Ouverte aux visiteurs, et il fallait déjà qu'elle soit ouverte tout
    court : le décorateur manquait, donc `CourseCardOverlay.vue` recevait un
    403 et retombait sur le tunnel du LMS — précisément les deux tunnels que
    ce fichier existe pour éviter, celui du LMS ne connaissant ni le panier,
    ni TWINT, ni Stripe, ni la facture. Constaté le 2026-08-20 sur osiris,
    depuis la fiche d'un cours à 90.–.

    Elle ne révèle rien : la route d'un article DÉJÀ publié dans la boutique,
    que n'importe qui peut lire en parcourant le catalogue.
    """
    if not sells_through_the_shop():
        return None
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


def montant_lisible(valeur, devise: str = None) -> str:
    """Un prix pour un client : avec sa devise, toujours.

    🔴 `fmt_money` retire le symbole dès que le défaut global
    `hide_currency_symbol` vaut « Yes » — ce qui est le cas sur nos instances,
    et se défend au DESK : chaque colonne y annonce déjà sa monnaie en en-tête.
    Sur la fiche publique d'un cours, il ne restait que « 90 ». Quatre-vingt-dix
    quoi ? La boutique, à deux clics de là, affiche « CHF 90.00 » pour le même
    cours. Constaté le 2026-08-20 sur osiris.

    On formate donc le nombre sans devise, puis on remet la devise à la main,
    du côté que la fiche Currency indique. Deux décimales comme la boutique :
    deux prix pour un même cours ne doivent pas s'écrire différemment.
    """
    from frappe.utils import flt, fmt_money

    nombre = fmt_money(flt(valeur), 2)
    if not devise:
        return nombre
    symbole = frappe.db.get_value("Currency", devise, "symbol", cache=True) or devise
    a_droite = frappe.db.get_value("Currency", devise, "symbol_on_right", cache=True)
    return f"{nombre} {_(symbole)}" if a_droite else f"{_(symbole)} {nombre}"


def _pin_guest_cart() -> None:
    """Un seul identifiant d'invité pour toute la requête.

    Webshop frappe l'identifiant d'un visiteur sans compte quand il manque —
    mais il ne peut le poser que sur la RÉPONSE. Dans la même requête,
    `frappe.request.cookies` n'en a donc toujours aucun, et chaque appel en
    invente un nouveau : deux paniers pour un seul visiteur, dont un invisible.

    On le frappe une fois et on le remet dans les cookies de CETTE requête,
    ce que webshop lirait si le navigateur l'avait déjà appris.
    """
    if frappe.session.user != "Guest" or not getattr(frappe, "request", None):
        return
    if frappe.request.cookies.get("guest_session_id"):
        return
    try:
        from webshop.webshop.shopping_cart.guest_cart import get_guest_session_id
        from werkzeug.datastructures import ImmutableMultiDict

        cookies = dict(frappe.request.cookies)
        cookies["guest_session_id"] = get_guest_session_id()
        frappe.request.cookies = ImmutableMultiDict(cookies)
    except Exception:
        # Un visiteur n'a pas à voir une trace d'exécution parce que son panier
        # s'est dédoublé : la suite sait travailler sans cet épinglage.
        frappe.log_error("LMS: identifiant de panier invité", frappe.get_traceback())


def _panier_du_visiteur():
    """Le panier ouvert — celui d'un client connecté, ou celui d'un invité.

    🔴 `_get_cart_quotation()` ne convient pas à un visiteur sans compte : elle
    OUVRE le panier au lieu de le retrouver, et l'ouvrir exige un client, donc
    un contact, donc un lien — d'où « Link Document Type doit être défini en
    premier », affiché en pleine figure d'un visiteur qui voulait acheter un
    cours. `update_cart` vient pourtant de faire le travail juste avant : le
    devis existe, il suffit de le lire. Constaté le 2026-08-20 sur osiris.
    """
    from webshop.webshop.shopping_cart.cart import _get_cart_quotation

    if frappe.session.user != "Guest":
        return _get_cart_quotation()

    jeton = None
    try:
        jeton = frappe.request.cookies.get("guest_session_id") if frappe.request else None
    except Exception:
        jeton = None
    if not jeton:
        return None
    nom = frappe.db.get_value(
        "Quotation",
        {"guest_session_id": jeton, "docstatus": 0, "status": "Draft"},
        "name",
        order_by="modified desc",
    )
    return frappe.get_doc("Quotation", nom) if nom else None


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

    from webshop.webshop.shopping_cart.cart import update_cart

    _pin_guest_cart()
    update_cart(item_code, qty=1)

    doc = _panier_du_visiteur()
    if not doc:
        frappe.throw(_("Your basket could not be opened."))
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
