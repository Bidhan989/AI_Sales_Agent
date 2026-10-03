let leads = [];

async function load() {
  leads = await (await fetch("/api/leads")).json();
  render();
}

function esc(s = "") {
  return String(s).replace(
    /[&<>"']/g,
    (m) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[m],
  );
}

function render() {
  document.getElementById("leads").innerHTML = leads
    .map(
      (l) => `
        <tr>
            <td><div class="company">${esc(l.company)}</div><div class="contact">${esc(l.industry || "")}</div></td>
            <td><div>${esc(l.contact_name)}</div><div class="contact">${esc(l.contact_role)}</div></td>
            <td><b>${l.fit_score || "—"}</b></td>
            <td><span class="badge ${l.status === "Qualified" || l.status === "Interested" ? "good" : ""}">${esc(l.status)}</span></td>
            <td><button class="btn" onclick="openLead(${l.id})">Inspect</button></td>
        </tr>`,
    )
    .join("");

  document.getElementById("s-leads").textContent = leads.length;
  document.getElementById("s-qualified").textContent = leads.filter(
    (x) => x.status === "Qualified",
  ).length;
  document.getElementById("s-contacted").textContent = leads.filter(
    (x) => x.status === "Contacted",
  ).length;
  document.getElementById("s-interested").textContent = leads.filter(
    (x) => x.status === "Interested",
  ).length;

  const hasLive = leads.some((x) =>
    (x.last_action || "").includes("LIVE GEMINI"),
  );
  const modeEl = document.getElementById("mode");
  if (modeEl) {
    modeEl.textContent = hasLive ? "Live Gemini Engine" : "Hybrid Demo Mode";
  }
}

async function openLead(id) {
  const l = leads.find((x) => x.id === id);
  if (!l) return;

  let formattedPainPoints = esc(l.pain_points || "");
  if (l.pain_points && l.pain_points.startsWith("[")) {
    try {
      const arr = JSON.parse(l.pain_points);
      if (Array.isArray(arr)) {
        formattedPainPoints = arr.map((p) => `• ${esc(p)}`).join("<br>");
      }
    } catch (e) {
      // Keep original string on parse error
    }
  }

  document.getElementById("detail").innerHTML = `
        <div class="detail-grid">
            <div class="card">
                <h3>Account</h3>
                <h2>${esc(l.company)}</h2>
                <p class="muted">${esc(l.description)}</p>
                <p><b>${esc(l.contact_name)}</b> · ${esc(l.contact_role)}</p>
                <p class="muted">${esc(l.email)}</p>
                <small class="muted">Pipeline: ${esc(l.data_source || "Apollo.io Sourced -> Clay Enriched")}</small>
                <div class="actions" style="margin-top:12px;">
                    <button class="btn" onclick="analyze(${id})">Run AI analysis</button>
                    <button class="btn" onclick="simulateReply(${id})">Simulate positive reply</button>
                    <button class="btn" onclick="sendMail(${id})">Send / simulate email</button>
                </div>
            </div>
            <div class="card">
                <h3>AI qualification</h3>
                <div class="score">${l.fit_score || "—"}<small style="font-size:14px;color:#8f96aa"> / 100</small></div>
                <p class="source">${esc(l.last_action || "Not analyzed yet")}</p>
            </div>
            <div class="card">
                <h3>Research & pain points</h3>
                <p class="email"><b>Hypothesis:</b> ${esc(l.research || "Run AI analysis to generate this.")}</p>
                <p class="email"><b>Identified Pain Points:</b><br>${formattedPainPoints || "None generated yet."}</p>
            </div>
            <div class="card">
                <h3>Personalized outreach</h3>
                <p><b>${esc(l.outreach_subject || "No subject yet")}</b></p>
                <p class="email" style="white-space: pre-wrap;">${esc(l.outreach_body || "Run AI analysis to generate the message.")}</p>
            </div>
        </div>`;
}

async function analyze(id) {
  await fetch(`/api/leads/${id}/analyze`, { method: "POST" });
  await load();
  openLead(id);
}

async function sendMail(id) {
  const r = await fetch(`/api/leads/${id}/send`, { method: "POST" });
  const d = await r.json();
  alert(d.message || "Done");
  await load();
  openLead(id);
}

async function simulateReply(id) {
  const r = await fetch(`/api/leads/${id}/simulate-reply`, { method: "POST" });
  const d = await r.json();
  alert(d.message || "Done");
  await load();
  openLead(id);
}

async function runAll() {
  for (const l of leads) {
    await fetch(`/api/leads/${l.id}/analyze`, { method: "POST" });
  }
  await load();
  if (leads.length > 0) openLead(leads[0].id);
  alert(
    "Demo workflow complete: all sample leads were analyzed and qualified/disqualified.",
  );
}

load();
