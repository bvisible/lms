//// Neoffice — added file (no upstream equivalent), 23db77a3, then f54b1a51, 8f21c065,
//// 94eb465e, fe726a28, 90b267aa.
//// The desk-side form script for LMS Settings: the Infomaniak credentials, the
//// connection test and the video list. Deliberately NOT in upstream's lms_settings.js
//// (it is bound through the `doctype_js` hook instead), so this fork never fights a
//// merge over a file upstream edits.
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

// ⚠️ **nginx refuse les corps de plus de 50 Mo** (`client_max_body_size`, valeur
// du gabarit bench). Une vidéo de cours en pèse dix fois plus, et le refus
// arrive sous forme d'une page 413 illisible. On le dit AVANT le dépôt, avec le
// poids du fichier choisi : un message clair vaut mieux qu'un échec au bout de
// trois minutes d'attente.
const NB_UPLOAD_MAX = 50 * 1024 * 1024;

function nb_taille(octets) {
	if (!octets) return "";
	const mo = octets / (1024 * 1024);
	return mo >= 1024 ? (mo / 1024).toFixed(1) + " Go" : Math.round(mo) + " Mo";
}

function nb_upload_video() {
	frappe.call({
		method: "lms.lms.neoffice_video.list_folders",
		freeze: true,
		freeze_message: __("Calling Infomaniak…"),
		callback(r) {
			const dossiers = r.message || [];
			// Le dossier décide de la protection : le média hérite de la
			// restriction du dossier. Ce n'est pas un rangement, c'est un droit.
			const options = dossiers.map((d) => ({
				value: d.id,
				label: d.path + (d.protected ? " — " + __("protected") : " — " + __("public")),
			}));
			const protege = (dossiers.find((d) => d.protected) || {}).id;

			const d = new frappe.ui.Dialog({
				title: __("Upload a video"),
				fields: [
					{
						fieldname: "video",
						fieldtype: "Attach",
						label: __("Video file"),
						reqd: 1,
						description: __("The file goes to your Infomaniak space, and is removed from this server afterwards."),
					},
					{
						fieldname: "folder",
						fieldtype: "Select",
						label: __("Folder"),
						options: options,
						default: protege,
						description: __("A protected folder makes the video unplayable without a signed link — that is where course videos belong. A public folder is for free teasers."),
					},
					{ fieldtype: "HTML", fieldname: "etat" },
				],
				primary_action_label: __("Send to Infomaniak"),
				primary_action(v) {
					if (!v.video) return;
					const etat = d.fields_dict.etat.$wrapper;
					d.get_primary_btn().prop("disabled", true);
					etat.html(`<div class="text-muted">${__("Sending…")}</div>`);
					frappe.call({
						method: "lms.lms.neoffice_video.start_upload",
						args: { file_url: v.video, folder: v.folder },
						callback(res) {
							const jeton = (res.message || {}).token;
							if (!jeton) return;
							// La tâche tourne en fond : un fichier de 800 Mo
							// dépasse largement le délai de garde d'une requête
							// web. On demande où elle en est.
							const suivre = setInterval(() => {
								frappe.call({
									method: "lms.lms.neoffice_video.upload_status",
									args: { token: jeton },
									callback(s) {
										const out = s.message || {};
										if (out.state === "done") {
											clearInterval(suivre);
											d.hide();
											frappe.show_alert({
												message: __("« {0} » is on Infomaniak, in {1}.",
													[out.name, out.folder || "/"]),
												indicator: "green",
											}, 10);
										} else if (out.state === "failed") {
											clearInterval(suivre);
											d.get_primary_btn().prop("disabled", false);
											etat.html(`<div class="text-danger">${out.message || __("The upload failed.")}</div>`);
										} else {
											etat.html(`<div class="text-muted">${__("Sending to Infomaniak — this can take a few minutes.")}</div>`);
										}
									},
								});
							}, 3000);
						},
					});
				},
			});

			// Prévenir sur le poids AVANT de lancer quoi que ce soit.
			d.fields_dict.video.df.onchange = () => {
				const url = d.get_value("video");
				if (!url) return;
				frappe.db.get_value("File", { file_url: url }, "file_size").then((f) => {
					const taille = (f.message || {}).file_size;
					if (taille > NB_UPLOAD_MAX) {
						d.fields_dict.etat.$wrapper.html(
							`<div class="text-danger">${__("This file is {0}. The server refuses uploads over {1} — ask your administrator to raise the limit, or upload it in the Infomaniak manager.",
								[nb_taille(taille), nb_taille(NB_UPLOAD_MAX)])}</div>`
						);
					} else {
						d.fields_dict.etat.$wrapper.html(
							`<div class="text-muted">${nb_taille(taille)}</div>`
						);
					}
				});
			};

			d.show();
			frappe.call({
				method: "lms.lms.neoffice_video.space_left",
				callback(s) {
					const p = s.message || {};
					if (p.limit) {
						d.set_df_property("video", "description",
							__("{0} of {1} uploads used on the « {2} » plan ({3} videos in the space). A deleted video does not give its slot back.",
								[p.used, p.limit, p.pack || "—", p.present]));
					}
				},
			});
		},
	});
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
		frm.add_custom_button(__("Upload a video"), () => nb_upload_video(), __("Videos"));

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

// The status line under « Show the courses on the website » (maintenance#1860): is the public
// courses page online, hidden or off, why, and where it is. The same block as the jobs page in
// HR's settings. It reads the switch as it stands on the screen and the number of published
// courses the server counted when the form opened; it holds no state of its own.
frappe.ui.form.on("LMS Settings", {
	refresh(frm) {
		nb_render_courses_page(frm);
	},
	neo_show_on_website(frm) {
		nb_render_courses_page(frm);
	},
});

function nb_courses_page_sentence(enabled, published) {
	// The words name the page, never a bare « Online » or « Hidden » that another app's catalogue
	// would translate its own way. Tones are the design system's status tones.
	if (!enabled) {
		return [
			__("Page switched off"),
			"muted",
			__(
				"The page is switched off: its address answers “page not found” to visitors, and the site's menu has no entry. Signed-in learners still reach their courses.",
			),
		];
	}
	if (published) {
		const count =
			published === 1
				? __("{0} published course", [published])
				: __("{0} published courses", [published]);
		return [__("Page online"), "success", __("The page is online: {0}.", [count])];
	}
	return [
		__("Page hidden"),
		"warn",
		__(
			"The page is switched on but hidden: no course is published. It appears with the first published course.",
		),
	];
}

function nb_render_courses_page(frm) {
	const field = frm.get_field("neo_page_status");
	const state = (frm.doc.__onload || {}).courses_page;
	if (!field || !state) return;
	nb_courses_page_style();

	const enabled = !!frm.doc.neo_show_on_website;
	const [label, tone, text] = nb_courses_page_sentence(enabled, state.published);
	const online = enabled && state.published > 0;
	const link = online
		? `<a class="nb-state__url" href="${encodeURI(state.url)}" target="_blank" rel="noopener">${frappe.utils.escape_html(
				state.url.replace(/^https?:\/\//, ""),
		  )}</a>`
		: "";
	// A change not saved yet is not in force: say so rather than announce a page that is not there.
	const unsaved = frm.is_dirty()
		? `<p class="nb-state__text text-muted">${__("Not saved yet: the page changes when you save.")}</p>`
		: "";
	field.$wrapper.html(`
		<div class="nb-state">
			<div class="nb-state__head">
				<span class="nb-pill nb-pill--${tone}"><span class="nb-pill__dot"></span>${label}</span>
				${link}
			</div>
			<p class="nb-state__text">${text}</p>
			${unsaved}
		</div>`);
}

function nb_courses_page_style() {
	if (document.getElementById("nb-state-style")) return;
	$(`<style id="nb-state-style">
		.nb-state{display:flex;flex-direction:column;gap:10px;padding:16px 18px;border:1px solid var(--border-color);border-radius:var(--border-radius-lg, 12px);margin-bottom:8px}
		.nb-state__head{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
		.nb-state__url{font-size:13px;color:var(--text-muted);text-decoration:underline;text-underline-offset:3px}
		.nb-state__text{margin:0;max-width:68ch;color:var(--text-color);line-height:1.5}
		.nb-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:999px;font-size:12.5px;font-weight:500;white-space:nowrap}
		.nb-pill__dot{width:6px;height:6px;border-radius:50%;background:currentColor}
		.nb-pill--success{background:#E6F4EA;color:#15803D}.nb-pill--warn{background:#FDF3DC;color:#A16207}
		.nb-pill--muted{background:var(--sand-100, var(--bg-light-gray));color:var(--t3, var(--text-muted))}
		[data-theme="dark"] .nb-pill--success{background:rgba(21,128,61,.18);color:#86EFAC}
		[data-theme="dark"] .nb-pill--warn{background:rgba(161,98,7,.2);color:#FCD34D}
	</style>`).appendTo(document.head);
}
