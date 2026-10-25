# //// Neoffice — added file (no upstream equivalent): the former address of the public courses
# //// page. The page is /our-courses now (every address is English, maintenance#1860); a link that
# //// already left in an e-mail, a printed QR code or a bookmark must not break, so this answers with
# //// a permanent redirect that keeps the query string. At the merge: kept whole, nothing upstream.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

"""The former address of the courses page: /nos-formations leads to /our-courses.

The category filter was named ``categorie`` there and is ``category`` now; any other parameter
travels unchanged, so a campaign tag on an old link is not lost.

NOTE the file name: the route is /nos-formations (hyphen), a www controller is named with an
UNDERSCORE (see our_courses.py).
"""

from urllib.parse import urlencode

import frappe

# Modules that still import the rule from here (the theme's website_features.sync_all, before it
# moved to lms.lms.neoffice_commerce): an app of the fleet may be updated a wave before the other.
from lms.lms.neoffice_commerce import COURSES_URL, showing_courses  # noqa: F401

no_cache = 1

RENAMED_PARAMETERS = {"categorie": "category"}


def get_context(context):
	request = getattr(frappe.local, "request", None)
	query = request.args.items(multi=True) if request else frappe.form_dict.items()
	parameters = [(RENAMED_PARAMETERS.get(key, key), value) for key, value in query]

	target = COURSES_URL
	if parameters:
		target += "?" + urlencode(parameters)
	frappe.local.flags.redirect_location = target
	raise frappe.Redirect
