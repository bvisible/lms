import frappe

from . import __version__ as app_version

app_name = "frappe_lms"
app_title = "Learning"
app_publisher = "Frappe"
app_description = "Open Source Learning Management System built with Frappe Framework"
app_icon_url = "/assets/lms/images/lms-logo.png"
app_icon_title = "Learning"
app_icon_route = "/lms"
app_color = "grey"
app_email = "jannat@frappe.io"
app_license = "AGPL"
required_apps = ["frappe/payments"]


def get_lms_path():
	path = "lms"
	if frappe.conf and frappe.conf.get("lms_path"):
		path = frappe.conf.get("lms_path")
	return path.strip("/")


# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/lms/css/lms.css"
# app_include_js = "/assets/lms/js/lms.js"

# include js, css files in header of web template
# web_include_css = "/assets/lms/css/lms.css"
web_include_js = []

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "lms/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# //// Neoffice — le bouton de test des vidéos, hors du fichier amont.
doctype_js = {"LMS Settings": "public/js/neoffice_lms_settings.js"}
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "lms.install.before_install"
# //// Neoffice — our Item custom fields (lms_course, lms_access_months…) were created only in
# //// after_migrate; a fresh site ran the setup wizard before any migrate and the Item hook
# //// keep_the_course_price_honest died on "Unknown column lms_access_months" (CI, 2026-09-03).
after_install = [
	"lms.lms.neoffice_video.setup_custom_fields",
	"lms.lms.neoffice_commerce.setup_custom_fields",
	"lms.lms.neoffice_commerce.setup_cart_fields",
	"lms.install.after_install",
]
after_sync = "lms.install.after_sync"
before_uninstall = "lms.install.before_uninstall"
setup_wizard_complete = "lms.demo.demo_data.create_demo_data"
after_migrate = [
	"lms.sqlite.build_index_in_background",
	"lms.lms.doctype.lms_payment.lms_payment.add_unique_payment_id_constraint",
	"lms.lms.docperm_shadow.warn_about_shadowed_permlevels",
	# //// Neoffice — three entries added to upstream's after_migrate (36c69d63, d3b10e3f,
	# //// 5213816b). They create the custom fields our code reads: the LMS Enrollment access
	# //// dates, Item.lms_course / lms_access_months, and the chosen-offer marker carried by
	# //// the Quotation / Sales Order / Sales Invoice items. Upstream knows none of them.
	# //// At the merge: keep ours, appended after whatever upstream adds to the list.
	# Neoffice: subscription-gated video access fields on LMS Enrollment
	"lms.lms.neoffice_video.setup_custom_fields",
	# Neoffice: Item.lms_course — the bridge that lets the webshop sell a course
	"lms.lms.neoffice_commerce.setup_custom_fields",
	# Neoffice: le marquage de la durée choisie, sur les trois documents du panier
	"lms.lms.neoffice_commerce.setup_cart_fields",
]

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "lms.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"LMS Course": "lms.lms.permissions.course_query_conditions",
	"Course Chapter": "lms.lms.permissions.chapter_query_conditions",
	"LMS Course Progress": "lms.lms.permissions.course_record_query_conditions",
	"LMS Video Watch Duration": "lms.lms.permissions.course_record_query_conditions",
	"LMS Course Review": "lms.lms.permissions.course_record_query_conditions",
	"LMS Enrollment": "lms.lms.permissions.enrollment_query_conditions",
	"LMS Lesson Note": "lms.lms.permissions.lesson_note_query_conditions",
	"LMS Coupon": "lms.lms.permissions.coupon_query_conditions",
	"LMS Certificate": "lms.lms.doctype.lms_certificate.lms_certificate.get_permission_query_conditions",
	"LMS Live Class": "lms.lms.doctype.lms_live_class.lms_live_class.get_permission_query_conditions",
	"LMS Batch": "lms.lms.doctype.lms_batch.lms_batch.get_permission_query_conditions",
	"LMS Program": "lms.lms.doctype.lms_program.lms_program.get_permission_query_conditions",
	"Course Lesson": "lms.lms.doctype.course_lesson.course_lesson.get_permission_query_conditions",
	"LMS Certificate Evaluation": "lms.lms.doctype.lms_certificate_evaluation.lms_certificate_evaluation.get_permission_query_conditions",
	"LMS Batch Enrollment": "lms.lms.doctype.lms_batch_enrollment.lms_batch_enrollment.get_permission_query_conditions",
	"LMS Quiz": "lms.lms.permissions.quiz_query_conditions",
	"LMS Assignment": "lms.lms.permissions.assignment_query_conditions",
	"LMS Programming Exercise": "lms.lms.permissions.programming_exercise_query_conditions",
	"LMS Quiz Submission": "lms.lms.permissions.quiz_submission_query_conditions",
	"LMS Assignment Submission": "lms.lms.permissions.assignment_submission_query_conditions",
	"LMS Programming Exercise Submission": "lms.lms.permissions.programming_exercise_submission_query_conditions",
}

has_permission = {
	"LMS Course": "lms.lms.permissions.course_has_permission",
	"Course Chapter": "lms.lms.permissions.chapter_has_permission",
	"LMS Course Progress": "lms.lms.permissions.course_record_has_permission",
	"LMS Video Watch Duration": "lms.lms.permissions.course_record_has_permission",
	"LMS Course Review": "lms.lms.permissions.course_record_has_permission",
	"LMS Enrollment": "lms.lms.permissions.enrollment_has_permission",
	"LMS Lesson Note": "lms.lms.permissions.lesson_note_has_permission",
	"LMS Coupon": "lms.lms.permissions.coupon_has_permission",
	"LMS Live Class": "lms.lms.doctype.lms_live_class.lms_live_class.has_permission",
	"LMS Batch": "lms.lms.doctype.lms_batch.lms_batch.has_permission",
	"LMS Program": "lms.lms.doctype.lms_program.lms_program.has_permission",
	"LMS Certificate": "lms.lms.doctype.lms_certificate.lms_certificate.has_permission",
	"Course Lesson": "lms.lms.doctype.course_lesson.course_lesson.has_permission",
	"LMS Certificate Evaluation": "lms.lms.doctype.lms_certificate_evaluation.lms_certificate_evaluation.has_permission",
	"LMS Batch Enrollment": "lms.lms.doctype.lms_batch_enrollment.lms_batch_enrollment.has_permission",
	"File": "lms.lms.permissions.file_has_permission",
	"LMS Quiz": "lms.lms.permissions.assessment_has_permission",
	"LMS Assignment": "lms.lms.permissions.assessment_has_permission",
	"LMS Programming Exercise": "lms.lms.permissions.assessment_has_permission",
	"LMS Question": "lms.lms.permissions.has_authored_content_permission",
	"LMS Quiz Submission": "lms.lms.permissions.assessment_submission_has_permission",
	"LMS Assignment Submission": "lms.lms.permissions.assessment_submission_has_permission",
	"LMS Programming Exercise Submission": "lms.lms.permissions.assessment_submission_has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Web Template": "lms.overrides.web_template.CustomWebTemplate",
}

# Document Events
# ---------------
# Hook on document methods and events

CHILD_ROW_MOVE_GATE = "lms.lms.permissions.refuse_moving_child_rows_out_of_content_the_user_cannot_write"

doc_events = {
	"*": {
		"on_change": [
			"lms.lms.doctype.lms_badge.lms_badge.process_badges",
		]
	},
	"Discussion Reply": {
		"after_insert": "lms.lms.utils.handle_notifications",
		"validate": "lms.lms.utils.validate_discussion_reply",
	},
	"Notification Log": {"on_change": "lms.lms.utils.publish_notifications"},
	# One rule, two entry points: a child row whose stored parent is not the one it is
	# being saved under answers to the parent it is leaving.
	#
	# On the child, because has_child_permission is only ever shown the parent named on
	# the row being saved, so a row moved out of somebody else's quiz is checked against
	# the destination alone. A has_permission entry for a child would never be called --
	# frappe.has_permission returns has_child_permission for an istable doctype before
	# any controller hook for the child is reached.
	#
	# On the parent, because doc_events on a child do NOT fire when its parent saves its
	# own children, and Document.update_child_table db_updates every submitted row by
	# name with no ownership check. A save of the thief's own quiz naming a foreign row
	# is checked for `write` on the destination only, and reaches the child gate never.
	"LMS Quiz": {"validate": CHILD_ROW_MOVE_GATE, "after_insert": "lms.lms.telemetry.quiz_created"},
	"LMS Programming Exercise": {"validate": CHILD_ROW_MOVE_GATE},
	"LMS Assignment": {
		"validate": CHILD_ROW_MOVE_GATE,
		"after_insert": "lms.lms.telemetry.assignment_created",
	},
	"LMS Question": {"validate": CHILD_ROW_MOVE_GATE},
	"LMS Quiz Question": {"validate": CHILD_ROW_MOVE_GATE},
	"LMS Test Case": {"validate": CHILD_ROW_MOVE_GATE},
	"LMS Content Author": {"validate": CHILD_ROW_MOVE_GATE},
	# LMS Program carries `authors` too -- composed into its own has_permission hook
	# rather than registered on the shared gate -- so the same two doors reach its
	# child tables.
	"LMS Program": {"validate": CHILD_ROW_MOVE_GATE},
	"LMS Program Course": {"validate": CHILD_ROW_MOVE_GATE},
	"LMS Program Member": {"validate": CHILD_ROW_MOVE_GATE},
	"User": {
		"validate": "lms.lms.user.validate_username_duplicates",
		"before_insert": "lms.lms.user.add_lms_student_role",
	},
	# Product events for Pulse: one per step a site takes (see lms.lms.telemetry).
	# //// Neoffice — upstream's "LMS Course" and "LMS Settings" telemetry entries live in our merged entries below (see the block marker).
	"Course Chapter": {"after_insert": "lms.lms.telemetry.chapter_created"},
	"Course Lesson": {"after_insert": "lms.lms.telemetry.lesson_created"},
	"LMS Batch": {"on_update": "lms.lms.telemetry.batch_saved"},
	"LMS Live Class": {"after_insert": "lms.lms.telemetry.live_class_created"},
	"LMS Enrollment": {"after_insert": "lms.lms.telemetry.enrolled_in_course"},
	"LMS Batch Enrollment": {"after_insert": "lms.lms.telemetry.enrolled_in_batch"},
	"LMS Certificate": {"after_insert": "lms.lms.telemetry.certificate_issued"},
	# //// Neoffice — two doctypes appear on both sides, so their entries are merged by hand
	# //// (a second "LMS Course" / "LMS Settings" key would silently replace the first in the
	# //// dict literal): "LMS Course" keeps our validate AND upstream's telemetry on_update;
	# //// "LMS Settings" runs both on_update handlers (ours syncs the website menu, upstream's
	# //// reports the payment gateway to Pulse). Re-check this when upstream adds a hook there.
	# //// Neoffice — everything from here to the end of doc_events is ours (36c69d63,
	# //// b2addb4a, d3b10e3f, 5213816b, ac912227, 7a226d63). Upstream's doc_events stops at
	# //// "User": it has no notion of a course being sold as an ERPNext Item, so nothing
	# //// upstream reacts to an invoice, a payment or a cart. Ours does: Sales Invoice and
	# //// Payment Entry grant and extend course access, Item and LMS Course keep one article
	# //// from selling both a course and a booking, Quotation holds the price of the chosen
	# //// offer, LMS Settings syncs the website menu entry and warns about a second payment
	# //// tunnel. At the merge: keep both sides, they touch disjoint doctypes.
	# Neoffice: paying extends course access, exactly like it extends a cloud
	# instance's validity — and, when the invoice sells a course as an Item,
	# creates the enrolment in the first place.
	# on_submit as well as on_update_after_submit: a webshop invoice is created
	# already paid (PaymentRequest.set_as_paid submits the Payment Entry first,
	# then make_invoice with allocate_advances_automatically), so it is never
	# updated after submission and on_update_after_submit alone fires on nothing.
	"Sales Invoice": {
		"on_submit": [
			"lms.lms.neoffice_video.on_invoice_paid",
			"lms.lms.neoffice_commerce.on_invoice_paid",
		],
		"on_update_after_submit": [
			"lms.lms.neoffice_video.on_invoice_paid",
			"lms.lms.neoffice_commerce.on_invoice_paid",
		],
	},
	# A Payment Entry settles invoices via db_set, which never fires
	# on_update_after_submit — this is the hook real payments actually take.
	"Payment Entry": {
		"on_submit": [
			"lms.lms.neoffice_video.on_payment_entry_submitted",
			"lms.lms.neoffice_commerce.on_payment_entry_submitted",
		],
	},
	# Neoffice: un article vend un cours OU se réserve, jamais les deux. Un
	# article porte un seul prix, et les deux offres n'ont aucune raison de
	# valoir la même chose. Le garde-fou existe des deux côtés : celui-ci refuse
	# le cours sur un article déjà réservable, et Booking Profile refuse
	# l'inverse.
	"Item": {
		"validate": "lms.lms.neoffice_commerce.refuse_course_on_a_bookable_item",
	},
	# Neoffice: le prix annoncé par le cours doit être celui qu'on paiera, et un
	# cours payant que personne ne peut acheter doit le dire.
	"LMS Course": {
		"validate": "lms.lms.neoffice_commerce.keep_the_course_price_honest",
		# Neoffice: publishing or withdrawing a course moves the « Our courses » menu entry, and
		# deleting one puts it right once the course is gone (maintenance#1860).
		# //// Neoffice — course_saved now also syncs the "Our courses" menu entry on every course save (0ae090e19 "feat(courses): the public courses page has an English address, the SPA list closes to a guest on a site with no course, the menu follows the publication (maintenance#1860)")
		"on_update": [
			"lms.lms.telemetry.course_saved",
			"lms.lms.neoffice_commerce.course_saved",
		],
		"on_trash": "lms.lms.neoffice_commerce.course_trashed",
	},
	# Neoffice: une ligne de panier marquée garde le prix de l'offre choisie. Le
	# contrôleur la retarifierait sinon depuis la liste de prix de l'article, et
	# « 3 mois » repasserait au prix par défaut au premier changement de panier.
	"Quotation": {
		"before_validate": "lms.lms.neoffice_commerce.hold_the_offer_price",
	},
	# Neoffice: le menu du site suit l'interrupteur « Montrer les formations ».
	# On met ET on retire : décocher la case et laisser l'entrée mènerait le
	# visiteur à une page qui n'existe plus.
	"LMS Settings": {
		"on_update": [
			"lms.lms.neoffice_commerce.sync_courses_link",
			"lms.lms.telemetry.payment_gateway_saved",
		],
		# Neoffice: the status line under the switch « Show the courses on the website » (maintenance#1860).
		# //// Neoffice — new onload hook feeds the switch's status line (online/hidden/off and why) (0ae090e19 "feat(courses): the public courses page has an English address, the SPA list closes to a guest on a site with no course, the menu follows the publication (maintenance#1860)")
		"onload": "lms.lms.neoffice_commerce.settings_onload",
		# Neoffice: régler une passerelle ici rouvrirait le tunnel de paiement du
		# module, qui ignore le panier, TWINT, le terminal et la facturation.
		"validate": "lms.lms.neoffice_commerce.warn_about_the_second_tunnel",
	},
}

# Scheduled Tasks
# ---------------
scheduler_events = {
	"all": [
		"lms.sqlite.build_index_in_background",
		"lms.lms.doctype.lms_live_class.lms_live_class.retry_pending_invites",
	],
	"hourly": [
		"lms.lms.doctype.lms_certificate_request.lms_certificate_request.schedule_evals",
		"lms.lms.doctype.lms_course.lms_course.update_course_statistics",
		"lms.lms.doctype.lms_certificate_request.lms_certificate_request.mark_eval_as_completed",
		"lms.lms.doctype.lms_live_class.lms_live_class.update_attendance",
	],
	"daily": [
		"lms.job.doctype.job_opportunity.job_opportunity.update_job_openings",
		"lms.lms.doctype.lms_payment.lms_payment.send_payment_reminder",
		"lms.lms.doctype.lms_batch.lms_batch.send_batch_start_reminder",
		"lms.lms.doctype.lms_live_class.lms_live_class.send_live_class_reminder",
		"lms.lms.doctype.lms_course.lms_course.send_notification_for_published_courses",
		"lms.lms.doctype.course_lesson.course_lesson.rename_settled_untitled_lessons",
		# //// Neoffice — the « Our courses » menu entry follows the published courses; this catches
		# //// what a hook cannot see (a course published by a bulk update) (maintenance#1860).
		"lms.lms.neoffice_commerce.sync_courses_menu",
	],
}

fixtures = ["Custom Field", "Function", "Industry", "LMS Category"]

# Testing
# -------

# before_tests = "lms.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	# Finishes Google Calendar sign-in started from an evaluator's Slots tab.
	"frappe.integrations.doctype.google_calendar.google_calendar.google_callback": "lms.lms.api.google_calendar_callback",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "lms.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Add all simple route rules here
website_route_rules = [
	{"from_route": f"/{get_lms_path()}/<path:app_path>", "to_route": "_lms"},
	{"from_route": f"/{get_lms_path()}", "to_route": "_lms"},
	{
		"from_route": "/courses/<course_name>/<certificate_id>",
		"to_route": "certificate",
	},
]

website_redirects = [
	{"source": "/update-profile", "target": "/edit-profile"},
	{"source": "/courses", "target": f"/{get_lms_path()}/courses"},
	{
		"source": r"^/courses/.*$",
		"target": f"/{get_lms_path()}/courses",
	},
	{"source": "/batches", "target": f"/{get_lms_path()}/batches"},
	{
		"source": r"/batches/(.*)",
		"target": f"/{get_lms_path()}/batches",
		"match_with_query_string": True,
	},
	{"source": "/job-openings", "target": f"/{get_lms_path()}/job-openings"},
	{
		"source": r"/job-openings/(.*)",
		"target": f"/{get_lms_path()}/job-openings",
		"match_with_query_string": True,
	},
	{"source": "/statistics", "target": f"/{get_lms_path()}/statistics"},
	{"source": "_lms", "target": f"/{get_lms_path()}"},
]

update_website_context = [
	"lms.widgets.update_website_context",
]

jinja = {
	"methods": [
		# //// Neoffice — three jinja methods prepended to upstream's list (eceb4034, 9061b8d1,
		# //// c203b62a). The shop product page renders the duration selector and the "from
		# //// <price>" badge from them; upstream's list starts at get_lesson_count below.
		# Neoffice: les offres d'un cours, pour le sélecteur de la fiche boutique
		"lms.lms.neoffice_commerce.offers_for",
		"lms.lms.neoffice_commerce.course_sold_by",
		# Combien d'offres vend un article — pour le « dès » des vignettes
		"lms.lms.neoffice_commerce.course_offer_count",
		"lms.lms.utils.get_lesson_count",
		"lms.lms.utils.get_instructors",
		"lms.lms.utils.get_lesson_index",
		"lms.lms.utils.get_lesson_url",
		"lms.lms.utils.get_lms_route",
		"lms.lms.utils.is_instructor",
		"lms.lms.utils.get_palette",
	],
	"filters": [],
}

extend_bootinfo = [
	"lms.lms.utils.extend_bootinfo",
]
## Specify the additional tabs to be included in the user profile page.
## Each entry must be a subclass of lms.lms.plugins.ProfileTab
# profile_tabs = []

## Specify the extension to be used to control what scripts and stylesheets
## to be included in lesson pages. The specified value must be be a
## subclass of lms.plugins.PageExtension
# lms_lesson_page_extension = None

has_website_permission = {
	"LMS Certificate Evaluation": "lms.lms.doctype.lms_certificate_evaluation.lms_certificate_evaluation.has_website_permission",
	"LMS Certificate": "lms.lms.doctype.lms_certificate.lms_certificate.has_website_permission",
}

## Markdown Macros for Lessons
lms_markdown_macro_renderers = {
	"YouTubeVideo": "lms.plugins.youtube_video_renderer",
	"Video": "lms.plugins.video_renderer",
	"Embed": "lms.plugins.embed_renderer",
	"Audio": "lms.plugins.audio_renderer",
	"PDF": "lms.plugins.pdf_renderer",
}

page_renderer = [
	"lms.page_renderers.SCORMRenderer",
]

# set this to "/" to have profiles on the top-level
profile_url_prefix = "/users/"

signup_form_template = "lms.plugins.show_custom_signup"

on_login = "lms.lms.user.on_login"

get_site_info = "lms.activation.get_site_info"

add_to_apps_screen = [
	{
		"name": "lms",
		"logo": "/assets/lms/frontend/learning.svg",
		"title": "Learning",
		"route": f"/{get_lms_path()}",
		"has_permission": "lms.lms.api.check_app_permission",
	}
]

sqlite_search = ["lms.sqlite.LearningSearch"]
auth_hooks = ["lms.auth.authenticate"]
require_type_annotated_api_methods = True

# === Raven membership provider ===
# Hook contract + admin setup: ../raven-membership-provider.md
# TODO: that page is an interim capture. Publish it at docs.frappe.io/learning
# (specs/extensibility.md: "A hook isn't shipped until the docs exist") and delete it.
# LMS contributes its rule types + evaluator to the standalone `raven_integration`
# app via the `raven_membership_providers` hook. See lms/raven_provider.py.
raven_membership_providers = ["lms.raven_provider.get_provider"]

# Settings > Integrations > Raven sits inside the Settings modal, which is open to
# any Moderator, so the endpoints behind it have to be too. raven_integration gates
# on System Manager plus whatever this hook names, and grants the named roles the
# permissions its own doctypes need on install/migrate.
raven_integration_manager_roles = ["Moderator"]
