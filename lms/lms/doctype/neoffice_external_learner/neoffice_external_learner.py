# //// Neoffice — added file (no upstream equivalent).
# //// A person who follows a course of this site as the employee of a customer's Neoffice: no account of the site
# //// beforehand, one row per (instance, e-mail), created by the signed entry (lms.lms.neoffice_enter). The account
# //// this row points to is created at the first entry and is never an account the site had before.
# Copyright (c) 2026, Neoffice and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address

from lms.lms import neoffice_instance


class NeofficeExternalLearner(Document):
	def validate(self):
		self.learner_email = (self.learner_email or "").strip().lower()
		if not validate_email_address(self.learner_email):
			frappe.throw(_("{0} is not a valid e-mail address").format(self.learner_email))
		host = (self.instance or "").strip().lower().removeprefix("https://").rstrip("/")
		origin = neoffice_instance.clean_origin(f"https://{host}")
		if not origin:
			frappe.throw(_("{0} is not an instance address this site accepts").format(self.instance))
		self.instance = host
		self.instance_url = origin
		duplicate = frappe.db.exists(
			"Neoffice External Learner",
			{"instance": self.instance, "learner_email": self.learner_email, "name": ("!=", self.name)},
		)
		if duplicate:
			frappe.throw(_("{0} is already registered for {1}").format(self.learner_email, self.instance))

	def on_update(self):
		"""Switching a learner off ends the sessions of the account at once; switching it on again re-enables it."""
		if not self.user or not frappe.db.exists("User", self.user):
			return
		before = self.get_doc_before_save()
		if before is None or bool(before.enabled) == bool(self.enabled):
			return
		frappe.db.set_value("User", self.user, "enabled", 1 if self.enabled else 0)
		if not self.enabled:
			from frappe.sessions import clear_sessions

			clear_sessions(self.user, force=True)
