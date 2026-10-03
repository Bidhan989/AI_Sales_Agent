let leads = [], selected = null;
const $ = (id) => document.getElementById(id);
const esc = (s = "") => String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[m]);

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.style.display = "block";
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.style.display = "none"), 4500);
}
async function api(path, method = "POST", body) {
  const r = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || `Request failed (${r.status})`);
  return d;
}
async function busy(btn, fn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { toast("Error: " + e.message); }
  finally { if (btn) btn.disabled = false; }
}
const tag = (label) => `<span class="tag ${/^LIVE/.test(label) ? "live" : "sim"}">${esc(label.split(" (")[0])}</span>`;

async function load() {
  const [l, s, c] = await Promise.all([api("/api/leads", "GET"), api("/api/stats", "GET"), api("/api/config", "GET")]);
  leads = l;
  renderStats(s); renderConfig(c); renderLeads(); renderHot();
}

function renderConfig(c) {
  $("modes").innerHTML = `<div>AI ${tag(c.ai_mode)}</div><div>Email ${tag(c.email_mode)}</div>
    <div>Research <span class="tag live">LIVE (real sites only)</span></div>
    <div>Apollo / Clay <span class="tag sim">SIMULATED</span></div>
    <div>n8n alert ${c.n8n_webhook ? '<span class="tag live">LIVE</span>' : '<span class="tag sim">OFF</span>'}</div>
    ${c.test_recipient ? `<div class="muted">All mail → ${esc(c.test_recipient)}</div>` : ""}`;
  const i = c.icp;
  $("icp").innerHTML = `<div>${i.min_employees}–${i.max_employees} employees</div><div>Score ≥ ${i.min_score}</div><div>Roles: ${esc(i.target_roles.slice(0, 4).join(", "))}…</div><div class="muted">Edit data/icp.json</div>`;
}

function renderStats(s) {
  const items = [["Leads", s.leads], ["Researched", s.researched], ["Qualified", s.qualified], ["Emails ready", s.emails_generated], ["Emails sent", s.emails_sent], ["Replies", s.replies], ["Interested", s.interested]];
  $("stats").innerHTML = items.map(([k, v]) => `<div><span>${k}</span><strong>${v}</strong></div>`).join("");
}

function badgeClass(st) {
  if (["Qualified", "Interested"].includes(st)) return "good";
  if (["Disqualified", "Not Interested"].includes(st)) return "bad";
  if (["Needs Review"].includes(st)) return "warn";
  return "";
}
function renderLeads() {
  $("leads").innerHTML = leads.map((l) => `
    <tr class="${l.id === selected ? "sel" : ""}" onclick="openLead(${l.id})">
      <td><div class="company">${esc(l.company)}</div><div class="contact">${esc(l.industry || "")} · ${l.employees || "?"} emp</div></td>
      <td><div>${esc(l.contact_name)}</div><div class="contact">${esc(l.contact_role)}</div></td>
      <td><b>${l.analyzed ? l.fit_score : "—"}</b></td>
      <td><span class="badge ${l.status === "Interested" ? "hot" : badgeClass(l.status)}">${esc(l.status)}</span></td>
      <td><button class="btn" onclick="event.stopPropagation();openLead(${l.id})">Inspect</button></td>
    </tr>`).join("");
}
function renderHot() {
  const hot = leads.filter((l) => l.status === "Interested");
  $("hot").innerHTML = hot.map((l) => `<div class="alert">🔥 <b>HOT LEAD</b> — ${esc(l.contact_name)}, ${esc(l.company)}<br>
    <span class="muted">"${esc(l.reply_text)}"</span><br>Suggested action: contact within 24 hours. (${esc(l.email)})</div>`).join("");
}

async function openLead(id) {
  selected = id; renderLeads();
  const l = leads.find((x) => x.id === id); if (!l) return;
  const ev = await api(`/api/leads/${id}/events`, "GET");
  let pain = [];
  try { pain = JSON.parse(l.pain_points || "[]"); } catch { pain = l.pain_points ? [l.pain_points] : []; }
  let checks = [];
  try { checks = JSON.parse(l.qualification_checks || "[]"); } catch {}
  const canFollow = l.status === "Contacted" && !l.stopped && !l.reply_text;
  $("detail").innerHTML = `<div class="detail-grid">
    <div class="card"><h3>Account</h3><h2>${esc(l.company)}</h2>
      <p class="muted">${esc(l.description)}</p>
      <p><b>${esc(l.contact_name)}</b> · ${esc(l.contact_role)}</p><p class="muted">${esc(l.email)} · ${esc(l.website)}</p>
      <small class="muted">Source: ${esc(l.data_source)}</small>
      <div class="actions">
        <button class="btn" onclick="act(this,'analyze',${id})">${l.analyzed ? "Re-run" : "Run"} AI analysis</button>
        <button class="btn" onclick="act(this,'send',${id})" ${l.qualified && !l.stopped && l.status === "Qualified" ? "" : "disabled"}>Send initial email</button>
        <button class="btn" onclick="act(this,'followup',${id})" ${canFollow ? "" : "disabled"}>Send follow-up (${l.followup_count || 0}/2)</button>
        <button class="btn" onclick="if(confirm('Delete lead?'))act(this,'del',${id})">Delete</button>
      </div></div>
    <div class="card"><h3>Qualification (rules decide)</h3>
      <div class="score">${l.analyzed ? l.fit_score : "—"}<small style="font-size:14px;color:#8f96aa"> / 100</small></div>
      ${checks.map((c) => `<div class="check ${c[1] ? "ok" : "no"}">${esc(c[0])} <small>${esc(c[2])}</small></div>`).join("") || '<p class="muted">Not analyzed yet.</p>'}
      <p class="source">${l.ai_source ? tag(l.ai_source) : ""} ${esc(l.ai_source || "")}<br>Research: ${esc(l.research_note || "—")}</p></div>
    <div class="card"><h3>Research & pain points</h3>
      <p class="email">${esc(l.research || "Run AI analysis.")}</p>
      <p class="email"><b>Pain-point hypotheses:</b><br>${pain.map((p) => "• " + esc(p)).join("<br>") || "None."}</p></div>
    <div class="card"><h3>Outreach</h3>
      <p><b>${esc(l.outreach_subject || "No outreach (disqualified or not generated)")}</b></p>
      <p class="email">${esc(l.outreach_body)}</p></div>
    <div class="card wide"><h3>Reply handling (AI intent classifier)</h3>
      ${l.reply_text ? `<p class="email">"${esc(l.reply_text)}"</p><p><span class="badge ${l.reply_intent === "POSITIVE" ? "hot" : ""}">${esc(l.reply_intent)}</span></p>` : ""}
      <textarea id="reply-text" placeholder="Paste a prospect's reply here…"></textarea>
      <div class="actions"><button class="btn" onclick="classify(this,${id})">Classify reply</button>
      <button class="btn" onclick="act(this,'simulate-reply',${id})">Use sample positive reply</button></div></div>
    <div class="card wide"><h3>Activity log (CRM)</h3>
      ${ev.map((e) => `<div class="tl"><b>${esc(e.kind)}</b> · ${esc(e.ts.replace("T", " ").slice(0, 16))}<br>${esc(e.detail)}</div>`).join("") || '<p class="muted">No activity yet.</p>'}</div>
  </div>`;
}

async function act(btn, what, id) {
  await busy(btn, async () => {
    if (what === "del") { await api(`/api/leads/${id}`, "DELETE"); selected = null; $("detail").innerHTML = '<div class="empty">Select a lead above.</div>'; await load(); return; }
    const d = await api(`/api/leads/${id}/${what}`);
    if (what === "send" || what === "followup") toast(d.message);
    if (what === "simulate-reply") toast(`Classified: ${d.intent}. ${d.alert || ""}`);
    await load(); openLead(id);
  });
}
async function classify(btn, id) {
  const text = $("reply-text").value.trim();
  if (!text) return toast("Paste a reply first.");
  await busy(btn, async () => {
    const d = await api(`/api/leads/${id}/reply`, "POST", { text });
    toast(`Classified: ${d.intent} — ${d.summary || ""}`);
    await load(); openLead(id);
  });
}
async function runAll() {
  await busy($("runbtn"), async () => {
    toast("Running pipeline… (AI calls take a few seconds each)");
    const d = await api("/api/pipeline/run");
    toast(`Analyzed ${d.analyzed.length}, qualified ${d.qualified.length}, sent ${d.sent.length}.`);
    await load(); if (selected) openLead(selected);
  });
}
async function runFollowups() {
  await busy(null, async () => {
    const d = await api("/api/followups/run?force=true");
    toast(d.followed_up.length ? `Follow-ups sent: ${d.followed_up.join(", ")}` : "No leads need a follow-up.");
    await load(); if (selected) openLead(selected);
  });
}
function toggleForm() { $("addform").hidden = !$("addform").hidden; }
async function addLead() {
  const g = (k) => $(k).value.trim();
  await busy(null, async () => {
    await api("/api/leads", "POST", { company: g("f-company"), website: g("f-website"), industry: g("f-industry"), employees: g("f-employees"), contact_name: g("f-name"), contact_role: g("f-role"), email: g("f-email"), description: g("f-desc") });
    document.querySelectorAll("#addform input").forEach((i) => (i.value = ""));
    toast("Lead added."); await load();
  });
}
async function uploadCsv(input) {
  const f = input.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  await busy(null, async () => {
    const r = await fetch("/api/leads/upload", { method: "POST", body: fd });
    const d = await r.json(); if (!r.ok) throw new Error(d.detail);
    toast(`Imported ${d.added} leads.`); await load();
  });
  input.value = "";
}
load();
