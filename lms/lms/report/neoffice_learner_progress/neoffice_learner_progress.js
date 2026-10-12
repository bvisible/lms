// //// Neoffice — added file (no upstream equivalent): filters of the learners' progress report.
frappe.query_reports["Neoffice Learner Progress"] = {
	filters: [
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Data" },
		{ fieldname: "instance", label: __("Instance"), fieldtype: "Data" },
		{ fieldname: "course", label: __("Course"), fieldtype: "Link", options: "LMS Course" },
	],
};
