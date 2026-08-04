// Copyright (c) 2026, Neoffice and contributors
// For license information, please see license.txt
//
// Dans un fichier à part, branché par `doctype_js` : `lms_settings.js` est un
// fichier amont, et ce fork se remet à jour souvent. Une touche ici ne se bat
// avec aucune fusion.

// ⚠️ Un champ masqué précédé d'un champ texte, et Chrome croit tenir un
// formulaire de connexion : il a versé un login enregistré (« Daniel » + un mot
// de passe) par-dessus le compte Infomaniak et la clé d'API. Mesuré le
// 2026-08-04. `autocomplete="off"` seul ne suffit pas — les navigateurs
// l'ignorent sur ce qu'ils prennent pour des identifiants. Ce qui marche : un
// `name` qui ne ressemble à rien de connu, `new-password` sur le champ masqué,
// et les marqueurs que lisent les gestionnaires tiers.
function nb_no_autofill(frm, fieldname, kind) {
	const field = frm.get_field(fieldname);
	const input = field && field.$input;
	if (!input || !input.length) return;
	input.attr({
		autocomplete: kind === "secret" ? "new-password" : "off",
		autocorrect: "off",
		autocapitalize: "off",
		spellcheck: "false",
		name: "neo-" + fieldname + "-" + frappe.utils.get_random(4),
		"data-lpignore": "true",
		"data-1p-ignore": "true",
		"data-form-type": "other",
	});

	// 🔴 Et ça ne suffit toujours pas. Chrome IGNORE `autocomplete` sur ce qu'il
	// prend pour des identifiants — mesuré ici même : « Daniel » revenait dans
	// le numéro de compte et un mot de passe enregistré dans la clé, libellés
	// changés et attributs posés. Ce qu'il respecte, en revanche, c'est
	// `readonly` : un champ en lecture seule n'est jamais rempli. On le libère
	// au premier focus — clic ou tabulation — donc la saisie reste normale.
	if (!input.data("nb-guarded")) {
		input.data("nb-guarded", true);
		input.attr("readonly", true);
		input.on("focus", function () {
			$(this).removeAttr("readonly");
		});
		// Ce que le navigateur a déjà versé avant qu'on arrive n'est pas la
		// valeur du document : on remet l'écran d'accord avec la base.
		if (field.value !== undefined) {
			input.val(field.value === null ? "" : field.value);
		}
	}
	// Le contrôle mot de passe de Frappe note la force de ce qu'on tape et
	// conseille « des symboles, des chiffres et des majuscules ». Une clé d'API
	// ne se choisit pas : le conseil est faux, et la barre bleue fait croire
	// qu'on est en train de définir un mot de passe.
	if (kind === "secret" && field.disable_password_checks) {
		field.disable_password_checks();
		field.$wrapper.find(".password-strength-indicator").addClass("hidden");
	}
}

frappe.ui.form.on("LMS Settings", {
	refresh(frm) {
		["neo_vod_channel", "neo_vod_account"].forEach((f) => nb_no_autofill(frm, f));
		nb_no_autofill(frm, "neo_vod_token", "secret");

		// Le lien vers le manager est ici et pas dans la description du champ :
		// une balise dans une description est réécrite par l'assainisseur, et la
		// traduction ne retrouve plus sa chaîne. Racine du manager exprès — les
		// chemins internes d'Infomaniak bougent, un lien mort aide moins que pas
		// de lien.
		frm.add_custom_button(__("Open the Infomaniak manager"), () => {
			window.open("https://manager.infomaniak.com", "_blank", "noopener");
		}, __("Videos"));

		// Poser une vidéo dans une leçon, c'est y coller une ligne. Encore
		// faut-il pouvoir la lire quelque part : sans cet écran il fallait
		// aller chercher un identifiant de treize caractères dans le manager
		// Infomaniak, dans un autre onglet, et le retaper sans se tromper.
		frm.add_custom_button(__("The available videos"), () => {
			frappe.call({
				method: "lms.lms.neoffice_video.list_media",
				freeze: true,
				freeze_message: __("Calling Infomaniak…"),
				callback(r) {
					const medias = r.message || [];
					if (!medias.length) {
						frappe.msgprint({
							title: __("No video"),
							indicator: "blue",
							message: __("The space holds no video yet. Upload them in the Infomaniak manager."),
						});
						return;
					}
					const d = new frappe.ui.Dialog({
						title: __("The available videos"),
						size: "large",
						fields: [{ fieldtype: "HTML", fieldname: "liste" }],
					});
					const lignes = medias.map((m) => `
						<tr>
							<td>${frappe.utils.escape_html(m.name)}
								${m.ready ? "" : `<span class="text-muted small"> — ${__("still encoding")}</span>`}</td>
							<td><code>${frappe.utils.escape_html(m.macro)}</code></td>
							<td class="text-right">
								<button class="btn btn-xs btn-default nb-copy"
									data-macro="${frappe.utils.escape_html(m.macro)}">${__("Copy")}</button>
							</td>
						</tr>`).join("");
					d.fields_dict.liste.$wrapper.html(`
						<p class="text-muted">${__("Paste the line into the lesson, where the video should play.")}</p>
						<table class="table table-sm"><tbody>${lignes}</tbody></table>`);
					d.$wrapper.on("click", ".nb-copy", function () {
						frappe.utils.copy_to_clipboard($(this).data("macro"));
					});
					d.show();
				},
			});
		}, __("Videos"));

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
							? __("Connected to « {0} » — channel {1}, account {2}, {3} media in the space.",
								[out.name, out.channel, out.account,
									out.media_count == null ? "?" : out.media_count])
							: out.message,
					});
				},
			});
		}, __("Videos"));
	},
});
