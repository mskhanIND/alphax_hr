// AlphaX HR Settings (Desk): technical tools kept out of the AlphaX app — system health and the employee field map.

const AX_STATUS = { ok: ["green", __("OK")], warn: ["orange", __("Warning")], error: ["red", __("Error")] };
const ax_label = (key) => __(key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()));

function ax_health_dialog(frm) {
	frappe.call({ method: "alphax_hr.api.setup.health", freeze: true, freeze_message: __("Running checks…") }).then((r) => {
		const d = r.message || { checks: [], counts: {} };
		const rows = d.checks
			.sort((a, b) => ["error", "warn", "ok"].indexOf(a.status) - ["error", "warn", "ok"].indexOf(b.status))
			.map((c) => {
				const [color, label] = AX_STATUS[c.status] || ["gray", c.status];
				const link = c.link ? ` <a href="${encodeURI(c.link)}" target="_blank">${__("Open")}</a>` : "";
				return `<tr><td><span class="indicator-pill ${color}">${label}</span></td>
					<td><b>${frappe.utils.escape_html(ax_label(c.key))}</b><div class="text-muted small">${frappe.utils.escape_html(c.group || "")}</div></td>
					<td>${frappe.utils.escape_html(c.value == null ? "" : String(c.value))}${c.detail ? `<div class="text-muted small">${frappe.utils.escape_html(c.detail)}</div>` : ""}${link}</td></tr>`;
			}).join("");
		const fixes = new Set(d.checks.filter((c) => c.status !== "ok").map((c) => c.fix));
		const dlg = new frappe.ui.Dialog({
			title: __("System health"),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "body" }],
			primary_action_label: __("Run again"),
			primary_action: () => { dlg.hide(); ax_health_dialog(frm); },
		});
		dlg.fields_dict.body.$wrapper.html(`
			<p class="text-muted">${__("OK")}: ${d.counts.ok || 0} · ${__("Warning")}: ${d.counts.warn || 0} · ${__("Error")}: ${d.counts.error || 0}
			· ${frappe.datetime.str_to_user(d.as_of || "")}</p>
			<table class="table table-bordered"><thead><tr><th style="width:110px">${__("Status")}</th><th>${__("Check")}</th><th>${__("Result")}</th></tr></thead>
			<tbody>${rows}</tbody></table>`);
		if (fixes.has("disable_scripts")) {
			dlg.add_custom_action(__("Disable broken server scripts"), () =>
				frappe.call("alphax_hr.api.setup.disable_broken_scripts").then(() => { dlg.hide(); ax_health_dialog(frm); }));
		}
		if (fixes.has("relax_orphans")) {
			dlg.add_custom_action(__("Make leftover mandatory fields optional"), () =>
				frappe.call("alphax_hr.api.setup.relax_orphan_fields").then(() => { dlg.hide(); ax_health_dialog(frm); }));
		}
		dlg.show();
	});
}

function ax_field_map_dialog(frm) {
	frappe.call({ method: "alphax_hr.api.hr.field_map", freeze: true }).then((r) => {
		const d = r.message || {};
		const esc = frappe.utils.escape_html;
		const mirrors = (d.mirrors || []).map((m) => `<tr><td><b>${esc(m.label)}</b> <span class="text-muted small">${esc(m.fieldname)}</span></td>
			<td>← ${esc(m.from_label)}</td><td>${m.manual ? __("Set in Employee Field Links") : __("Automatic")}</td></tr>`).join("");
		const required = (d.required || []).map((m) => `<tr><td><b>${esc(m.label)}</b> <span class="text-muted small">${esc(m.fieldname)}</span></td>
			<td>${esc(m.fieldtype)}</td><td>${m.mirrored ? __("Filled automatically") : esc(m.step || "")}</td></tr>`).join("");
		const loose = (d.unhandled_id_like || []).map((m) => `<li>${esc(m.label)} <span class="text-muted small">${esc(m.fieldname)}</span></li>`).join("");
		const dlg = new frappe.ui.Dialog({ title: __("Employee field map"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		dlg.fields_dict.body.$wrapper.html(`
			<h5>${__("Filled automatically (duplicates of an AlphaX field)")}</h5>
			<table class="table table-bordered"><tbody>${mirrors || `<tr><td class="text-muted">—</td></tr>`}</tbody></table>
			<h5>${__("Mandatory employee fields and where AlphaX asks for them")}</h5>
			<table class="table table-bordered"><tbody>${required || `<tr><td class="text-muted">—</td></tr>`}</tbody></table>
			${loose ? `<h5>${__("Mandatory ID-like fields not linked yet")}</h5><ul>${loose}</ul>
			<p class="text-muted">${__("Link them in the Employee Field Links table on this form (Site field → same as AlphaX field).")}</p>` : ""}`);
		dlg.show();
	});
}

frappe.ui.form.on("AlphaX HR Settings", {
	refresh(frm) {
		if (frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("System health"), () => ax_health_dialog(frm), __("Tools"));
		}
		if (frappe.user.has_role("System Manager") || frappe.user.has_role("HR Manager")) {
			frm.add_custom_button(__("Employee field map"), () => ax_field_map_dialog(frm), __("Tools"));
		}
		frm.add_custom_button(__("Open AlphaX HR"), () => window.open("/alphax/setup#settings", "_blank"));
	},
});
