/* Preview simulator — renders pages produced by dev/preview/build.py
   (which in turn renders them with the real bot code). */
"use strict";

let DATA = null;
const state = {
  hasPhone: false,
  awaiting: null,       // null | "anon"
  lastBotMessage: null, // DOM node whose content gets "edited" like Telegram does
  currentPage: null,
};

const $ = (selector) => document.querySelector(selector);
const chat = () => $("#chat");

/* ------------------------------------------------------------------ utils */
function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.remove("hidden");
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.add("hidden"), 2600);
}

function htmlToText(value) {
  const div = document.createElement("div");
  div.innerHTML = value
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<\/?(b|i|u|code|pre|s)>/g, "");
  return div.textContent;
}

function now() {
  return new Date().toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
}

/* ---------------------------------------------------------------- rendering */
function keyboard(page, container, onCallback) {
  const kb = document.createElement("div");
  kb.className = "kb";
  (page.rows || []).forEach((row) => {
    const line = document.createElement("div");
    line.className = "kb-row";
    row.forEach((button) => {
      const style = button.style || "primary";
      if (button.url) {
        const link = document.createElement("a");
        link.className = style;
        link.href = button.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = button.text;
        line.appendChild(link);
      } else {
        const element = document.createElement("button");
        element.className = style;
        element.textContent = button.text;
        element.onclick = () => onCallback(button.callback);
        line.appendChild(element);
      }
    });
    kb.appendChild(line);
  });
  container.appendChild(kb);
}

function botMessage(page, { edit = false, target = chat(), onCallback = handleCallback } = {}) {
  let node = edit ? state.lastBotMessage : null;
  if (!node) {
    node = document.createElement("div");
    node.className = "msg bot";
    target.appendChild(node);
  }
  node.innerHTML = "";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = htmlToText(page.text);
  node.appendChild(bubble);
  if (page.rows && page.rows.length) keyboard(page, bubble, onCallback);
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${page.id} · ${now()}${edit ? " · ویرایش همان پیام" : ""}`;
  node.appendChild(meta);
  if (target === chat()) state.lastBotMessage = node;
  target.scrollTop = target.scrollHeight;
  return node;
}

function plainBot(text, target = chat()) {
  const node = document.createElement("div");
  node.className = "msg bot";
  node.innerHTML = `<div class="bubble">${htmlToText(text)}</div>`
    + `<div class="meta">${now()}</div>`;
  target.appendChild(node);
  target.scrollTop = target.scrollHeight;
  state.lastBotMessage = null;
  return node;
}

function userMessage(text) {
  const node = document.createElement("div");
  node.className = "msg user";
  node.innerHTML = `<div class="bubble">${htmlToText(text)}</div>`
    + `<div class="meta">${now()}</div>`;
  chat().appendChild(node);
  chat().scrollTop = chat().scrollHeight;
}

/* ------------------------------------------------------------------ flows */
function showReplyKeyboard() {
  const box = $("#replykb");
  box.innerHTML = "";
  const button = document.createElement("button");
  button.textContent = DATA.phone.button;
  button.onclick = sharePhone;
  box.appendChild(button);
  box.classList.remove("hidden");
}

function hideReplyKeyboard() {
  $("#replykb").classList.add("hidden");
}

function askPhone(prefix) {
  plainBot((prefix ? prefix + "\n\n" : "") + DATA.phone.request);
  showReplyKeyboard();
  updateInfo();
}

function sharePhone() {
  userMessage("📱 +98 912 *** 4567");
  state.hasPhone = true;
  hideReplyKeyboard();
  plainBot(DATA.phone.saved);
  openPage(DATA.start, false);
  updateInfo();
}

function pageById(id) {
  return DATA.pages[id] || DATA.admin_pages[id] || null;
}

function openPage(id, edit = true) {
  const page = pageById(id);
  if (!page) {
    toast(DATA.texts.expired);
    return;
  }
  state.currentPage = id;
  state.awaiting = id === "anon:new" ? "anon" : null;
  botMessage(page, { edit });
  updateInfo();
}

function handleCallback(callback) {
  if (!callback) return;
  if (!state.hasPhone) {
    toast("⛔ " + DATA.phone.gate_callback);
    askPhone();
    return;
  }
  const action = DATA.actions[callback];
  if (action) {
    if (action.toast && action.toast !== "—") toast(action.toast);
    if (action.goto) openPage(action.goto);
    return;
  }
  openPage(callback);
}

function handleText(text) {
  userMessage(text);
  if (!state.hasPhone) {
    askPhone(DATA.phone.invalid);
    return;
  }
  if (text === "/start" || text === "/menu") {
    openPage(DATA.start, false);
    return;
  }
  if (text === "/help") { openPage("nav:help", false); return; }
  if (text === "/admin") {
    document.querySelector('[data-tab="admin"]').click();
    return;
  }
  if (state.awaiting === "anon") {
    if (text.trim().length < 5) { plainBot(DATA.anon.too_short); return; }
    state.awaiting = null;
    plainBot(DATA.anon.sent);
    plainBot("🛠 (برای ادمین) پیام ناشناس جدید #A7F3 — در تب «پنل ادمین» قابل مشاهده است.");
    openPage(DATA.start, false);
    return;
  }
  openPage(DATA.start, false);
}

function restart() {
  chat().innerHTML = "";
  state.hasPhone = false;
  state.awaiting = null;
  state.lastBotMessage = null;
  userMessage("/start");
  askPhone();
}

function updateInfo() {
  const info = $("#sim-info");
  const rows = [
    ["شماره ثبت شده", state.hasPhone ? "✅ بله" : "⛔ خیر (گیت فعال)"],
    ["صفحه‌ی فعلی", state.currentPage || "—"],
    ["در انتظار", state.awaiting || "—"],
    ["منبع کاتالوگ", DATA.catalog.source],
    ["تعداد صفحات", Object.keys(DATA.pages).length],
  ];
  info.innerHTML = rows.map(([k, v]) => `<li><span>${k}</span><span>${v}</span></li>`).join("");
  $("#sim-state").textContent = state.hasPhone ? "آنلاین" : "در انتظار شماره";
}

/* ------------------------------------------------------------------ admin */
function openAdmin(id) {
  const page = DATA.admin_pages[id] || DATA.pages[id];
  if (!page) { toast(DATA.texts.expired); return; }
  const target = $("#admin-chat");
  target.innerHTML = "";
  botMessage(page, { edit: false, target, onCallback: (callback) => {
    const action = DATA.actions[callback];
    if (action) {
      if (action.toast && action.toast !== "—") toast(action.toast);
      if (action.goto) openAdmin(action.goto);
      return;
    }
    if (DATA.admin_pages[callback]) { openAdmin(callback); return; }
    if (DATA.pages[callback]) {
      toast("این دکمه کاربر را به ربات عادی برمی‌گرداند: " + callback);
      return;
    }
    toast(DATA.texts.expired);
  }});
  state.lastBotMessage = null;
}

/* ----------------------------------------------------------------- source */
let FILES = [];
function renderFiles(filter = "") {
  const list = $("#file-list");
  const items = FILES.filter((file) => file.path.includes(filter));
  list.innerHTML = items
    .map((file) => `<li data-path="${file.path}">${file.path}<span>${file.size}B</span></li>`)
    .join("");
  list.querySelectorAll("li").forEach((item) => {
    item.onclick = async () => {
      list.querySelectorAll("li").forEach((other) => other.classList.remove("active"));
      item.classList.add("active");
      const path = item.dataset.path;
      const response = await fetch(`/api/source?path=${encodeURIComponent(path)}`);
      const payload = await response.json();
      $("#code-path").textContent = path;
      $("#code-size").textContent = `${payload.size} بایت`;
      $("#code").textContent = payload.content || payload.error || "";
    };
  });
  $("#file-count").textContent = items.length;
}

/* ----------------------------------------------------------------- verify */
async function runVerify() {
  const box = $("#verify-result");
  box.innerHTML = "<div class='check'><span class='dot'></span>در حال بررسی…</div>";
  const response = await fetch("/api/verify");
  const payload = await response.json();
  box.innerHTML = payload.checks
    .map((check) => `<div class="check ${check.ok ? "ok" : "bad"}">
        <span class="dot"></span><span>${check.name}</span><small>${check.detail}</small>
      </div>`)
    .join("");
}

async function loadZipInfo() {
  const response = await fetch("/api/build-info");
  const info = await response.json();
  $("#zip-info").innerHTML = `
    <li><span>نام فایل</span><span>${info.name}</span></li>
    <li><span>حجم دقیق</span><span>${info.bytes.toLocaleString("fa-IR")} بایت</span></li>
    <li><span>زمان ساخت</span><span>${info.built_at}</span></li>`;
  $("#download-link").href = `/download?v=${encodeURIComponent(info.name)}`;
}

/* ------------------------------------------------------------------- boot */
async function boot() {
  DATA = await (await fetch(`/app-data.json?t=${Date.now()}`)).json();
  $("#meta").textContent =
    `v${DATA.version} · build ${DATA.build_id} · کاتالوگ: ${DATA.catalog.source}`
    + ` (${DATA.catalog.total} مورد) · استایل دکمه‌ها: `
    + (DATA.supports_button_styles ? "پشتیبانی می‌شود" : "نسخه‌ی کتابخانه پشتیبانی نمی‌کند");

  FILES = DATA.sources;
  renderFiles();
  $("#file-filter").oninput = (event) => renderFiles(event.target.value.trim());

  $("#admin-sections").innerHTML = Object.keys(DATA.admin_pages)
    .filter((id) => id.split(":").length <= 2)
    .map((id) => `<li><span>${id}</span><span>${DATA.admin_pages[id].title}</span></li>`)
    .join("");

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll(".tab").forEach((other) => other.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      $(`#tab-${tab.dataset.tab}`).classList.add("active");
      if (tab.dataset.tab === "admin" && !$("#admin-chat").children.length) {
        openAdmin(DATA.admin_start);
      }
      if (tab.dataset.tab === "download") loadZipInfo();
    };
  });

  $("#composer").onsubmit = (event) => {
    event.preventDefault();
    const value = $("#input").value.trim();
    if (!value) return;
    $("#input").value = "";
    handleText(value);
  };
  document.querySelectorAll(".shortcuts button").forEach((button) => {
    button.onclick = () => handleText(button.dataset.cmd);
  });
  $("#restart").onclick = restart;
  $("#admin-restart").onclick = () => openAdmin(DATA.admin_start);
  $("#run-verify").onclick = runVerify;
  $("#rebuild").onclick = async () => {
    toast("در حال ساخت دوباره…");
    const response = await fetch("/api/rebuild");
    const payload = await response.json();
    toast(payload.ok ? "✅ دوباره ساخته شد" : "❌ " + payload.error);
    if (payload.ok) location.reload();
  };

  restart();
}

boot();
