const agentMeta = {
  director: { name: "Director", role: "Product Strategy", glyph: "D", color: "#71e3df" },
  researcher: { name: "Researcher", role: "Companion Quality", glyph: "R", color: "#b48cff" },
  engineer: { name: "Engineer", role: "Implementation", glyph: "E", color: "#6ea8ff" },
  reviewer: { name: "Reviewer", role: "Independent Review", glyph: "V", color: "#f5c36b" },
  performance: { name: "Performance", role: "Runtime & Latency", glyph: "P", color: "#7ce0a6" },
  ux: { name: "UX", role: "Product Simplicity", glyph: "U", color: "#ef8fc7" }
};

const metricLabels = {
  architecture: "Architecture", persona: "Persona", memory: "Memory", learning: "Learning", agency: "Agency", localLatency: "Latency", ux: "UX"
};

let payload = { state: { agents: {}, metrics: {}, events: [] }, pullRequests: [], commits: [], workflows: [] };
let activeTab = "prs";

function safeStatus(value) {
  return String(value || "idle").toLowerCase().replace(/[^a-z_]/g, "");
}
function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" }).format(date);
}
function avatarHtml(key) {
  const meta = agentMeta[key];
  return `<div class="avatar" style="--agent:${meta.color}">${meta.glyph}</div>`;
}

function renderHeader() {
  const state = payload.state || {};
  const status = safeStatus(state.status);
  const companyStatus = document.querySelector("#companyStatus");
  companyStatus.className = `status-pill status-${status}`;
  companyStatus.innerHTML = `<span class="status-dot"></span>${status.replaceAll("_", " ") || "idle"}`;
  document.querySelector("#currentPriority").textContent = state.currentPriority || "Tidak ada prioritas aktif.";
  document.querySelector("#cycleId").textContent = state.cycleId || "cycle —";
  document.querySelector("#connectionState").textContent = payload.configured ? "GitHub connected" : "GitHub token belum terhubung";
  document.querySelector("#lastSync").textContent = `Sync ${formatTime(payload.fetchedAt || state.updatedAt)}`;
}

function renderMetrics() {
  const metrics = payload.state.metrics || {};
  const entries = Object.entries(metrics).filter(([,value]) => Number.isFinite(Number(value)));
  const average = entries.length ? entries.reduce((sum,[,v]) => sum + Number(v),0) / entries.length : 0;
  document.querySelector("#qualityAverage").textContent = entries.length ? `${average.toFixed(1)}/10` : "—";
  document.querySelector("#metricBars").innerHTML = entries.map(([key,value]) => {
    const numeric = Math.max(0, Math.min(10, Number(value)));
    return `<div class="metric-row"><span>${metricLabels[key] || key}</span><div class="metric-track"><div class="metric-fill" style="width:${numeric * 10}%"></div></div><span class="metric-value">${numeric.toFixed(1)}</span></div>`;
  }).join("") || `<div class="empty">Belum ada metrics.</div>`;
}

function renderOffice() {
  const stateAgents = payload.state.agents || {};
  const office = document.querySelector("#office");
  office.innerHTML = Object.keys(agentMeta).map((key) => {
    const meta = agentMeta[key];
    const agent = stateAgents[key] || { status: "idle", task: "Belum ada tugas aktif" };
    const status = safeStatus(agent.status);
    return `<button class="desk agent-${status}" data-agent="${key}">
      <div class="avatar-wrap">${avatarHtml(key)}<div><div class="agent-name">${meta.name}</div><div class="agent-role">${meta.role}</div></div></div>
      <div class="desk-status"><span class="work-light"></span>${status.replaceAll("_"," ")}</div>
      <p class="desk-task">${escapeHtml(agent.task || "Belum ada tugas aktif")}</p>
    </button>`;
  }).join("");
  office.querySelectorAll(".desk").forEach((desk) => desk.addEventListener("click", () => openAgent(desk.dataset.agent)));
}

function renderEvents() {
  const events = Array.isArray(payload.state.events) ? [...payload.state.events].slice(-12).reverse() : [];
  document.querySelector("#eventFeed").innerHTML = events.map((event) => `<div class="event"><span class="event-time">${escapeHtml(event.at || "—")}</span><span class="event-actor">${escapeHtml(event.actor || "System")}</span><span class="event-message">${escapeHtml(event.message || "")}</span></div>`).join("") || `<div class="empty">Belum ada aktivitas.</div>`;
}

function renderWork() {
  let items = [];
  if (activeTab === "prs") {
    items = (payload.pullRequests || []).map((pr) => ({ title: `#${pr.number} ${pr.title}`, meta: `${pr.draft ? "Draft" : "Open"} · ${pr.branch || "branch"}`, side: formatTime(pr.updatedAt), url: pr.url, state: pr.draft ? "reviewing" : "working" }));
  } else if (activeTab === "ci") {
    items = (payload.workflows || []).map((run) => ({ title: run.name, meta: `${run.event || "event"} · ${run.branch || "—"}`, side: run.conclusion || run.status || "—", url: run.url, state: run.conclusion === "failure" ? "error" : run.status === "completed" ? "completed" : "testing" }));
  } else {
    items = (payload.commits || []).map((commit) => ({ title: commit.message, meta: commit.sha, side: formatTime(commit.at), url: commit.url, state: "completed" }));
  }
  document.querySelector("#workList").innerHTML = items.map((item) => `<a class="work-item" href="${item.url || "#"}" target="_blank" rel="noreferrer"><span class="work-indicator"></span><div><div class="work-title">${escapeHtml(item.title)}</div><div class="work-meta">${escapeHtml(item.meta)}</div></div><span class="work-side">${escapeHtml(item.side)}</span></a>`).join("") || `<div class="empty">Tidak ada data pada bagian ini.</div>`;
}

function openAgent(key) {
  const meta = agentMeta[key];
  const agent = (payload.state.agents || {})[key] || { status: "idle", task: "Belum ada tugas aktif" };
  const dialog = document.querySelector("#agentDialog");
  document.querySelector("#dialogAvatar").innerHTML = avatarHtml(key);
  document.querySelector("#dialogRole").textContent = meta.role;
  document.querySelector("#dialogName").textContent = meta.name;
  const status = safeStatus(agent.status);
  const statusEl = document.querySelector("#dialogStatus");
  statusEl.className = `status-pill status-${status}`;
  statusEl.textContent = status.replaceAll("_"," ");
  document.querySelector("#dialogTask").textContent = agent.task || "Belum ada tugas aktif";
  dialog.showModal();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}

async function refresh() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const next = await response.json();
    if (next && next.state) payload = next;
  } catch (error) {
    payload.state = payload.state || {};
    payload.state.status = "blocked";
    payload.state.currentPriority = "Dashboard tidak dapat mengambil status worker.";
  }
  renderHeader(); renderMetrics(); renderOffice(); renderEvents(); renderWork();
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((button) => button.classList.remove("active"));
  tab.classList.add("active"); activeTab = tab.dataset.tab; renderWork();
}));
document.querySelector("#dialogClose").addEventListener("click", () => document.querySelector("#agentDialog").close());
document.querySelector("#agentDialog").addEventListener("click", (event) => { if (event.target === event.currentTarget) event.currentTarget.close(); });

refresh();
setInterval(refresh, 20000);
