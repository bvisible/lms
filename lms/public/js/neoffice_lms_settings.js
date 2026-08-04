// Copyright (c) 2026, Neoffice and contributors
// For license information, please see license.txt
//
// Dans un fichier à part, branché par `doctype_js` : `lms_settings.js` est un
// fichier amont, et ce fork se remet à jour souvent. Une touche ici ne se bat
// avec aucune fusion.

frappe.ui.form.on("LMS Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test the video connection"), () => {
			frappe.call({
				method: "lms.lms.neoffice_video.check_connection",
				freeze: true,
				freeze_message: __("Calling Infomaniak…"),
				callback(r) {
					const out = r.message || {};
					frappe.msgprint({
						title: out.ok ? __("Videos are connected") : __("No answer"),
						indicator: out.ok ? "green" : "red",
						message: out.ok
							? __("Channel {0}, account {1} — {2} media in the space.",
								[out.channel, out.account, out.media_count == null ? "?" : out.media_count])
							: out.message,
					});
				},
			});
		}, __("Videos"));
	},
});
