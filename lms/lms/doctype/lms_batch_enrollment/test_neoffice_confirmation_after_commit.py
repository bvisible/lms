# //// Neoffice — added file (no upstream equivalent): the batch confirmation mail is queued after the commit, never
# //// sent from inside the insert (see LMSBatchEnrollment.after_insert).
from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from lms.lms.test_helpers import BaseTestUtils

MODULE = "lms.lms.doctype.lms_batch_enrollment.lms_batch_enrollment"


class TestBatchConfirmationMailAfterCommit(BaseTestUtils):
	"""Our frappe fork sends a mail at once, and that send commits. Sent from after_insert, the confirmation mail ended
	the per-member savepoint of a bulk enrolment: the first student was enrolled and the request failed."""

	def setUp(self):
		super().setUp()
		suffix = frappe.generate_hash(length=8)
		self.staff = self._create_user(
			f"batch-mail-staff-{suffix}@example.com",
			"Mail",
			"Staff",
			["Moderator", "Course Creator", "Batch Evaluator"],
			user_type="System User",
		)
		self.student = self._create_user(
			f"batch-mail-student-{suffix}@example.com", "Mail", "Student", ["LMS Student"]
		)
		self.batch = frappe.get_doc(
			{
				"doctype": "LMS Batch",
				"title": f"Batch mail {suffix}",
				"start_date": add_days(nowdate(), 1),
				"end_date": add_days(nowdate(), 10),
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "Europe/Zurich",
				"description": "Batch for the confirmation mail test",
				"batch_details": "Batch for the confirmation mail test",
				"instructors": [{"instructor": self.staff.name}],
			}
		).insert()

	def test_the_mail_is_queued_after_the_commit_not_sent_in_the_insert(self):
		with (
			patch(f"{MODULE}.send_confirmation_email") as sent_now,
			patch(f"{MODULE}.frappe.enqueue") as enqueue,
		):
			frappe.set_user(self.staff.name)
			enrollment = frappe.get_doc(
				{"doctype": "LMS Batch Enrollment", "batch": self.batch.name, "member": self.student.name}
			).insert()

		sent_now.assert_not_called()
		enqueue.assert_any_call(
			f"{MODULE}.send_confirmation_email_job", enrollment=enrollment.name, enqueue_after_commit=True
		)

	def test_the_job_sends_the_mail_of_an_enrolment_that_was_kept(self):
		with patch(f"{MODULE}.frappe.enqueue"):
			frappe.set_user(self.staff.name)
			enrollment = frappe.get_doc(
				{"doctype": "LMS Batch Enrollment", "batch": self.batch.name, "member": self.student.name}
			).insert()

		from lms.lms.doctype.lms_batch_enrollment.lms_batch_enrollment import send_confirmation_email_job

		with patch(f"{MODULE}.send_confirmation_email") as send:
			send_confirmation_email_job(enrollment.name)
			send_confirmation_email_job("an enrolment that was rolled back")

		send.assert_called_once()
		self.assertEqual(send.call_args.args[0].name, enrollment.name)
