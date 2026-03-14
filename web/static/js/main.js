// ── Utilidades globales ───────────────────────────────────────────────────

/**
 * Llama a la API y devuelve JSON. Lanza error si la respuesta no es ok.
 */
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

const get  = (path) => api("GET",    path);
const post = (path, body) => api("POST",   path, body);
const put  = (path, body) => api("PUT",    path, body);
const del  = (path) => api("DELETE", path);

// ── Toast ─────────────────────────────────────────────────────────────────

function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className = "show " + type;
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = ""; }, 3000);
}

// ── Navegacion activa ─────────────────────────────────────────────────────

function markActiveNav() {
  const path = window.location.pathname.replace("/", "") || "index";
  document.querySelectorAll(".nav-item").forEach(el => {
    const href = el.getAttribute("href") || "";
    const key  = href.replace("/", "") || "index";
    el.classList.toggle("active", key === path);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  markActiveNav();
});

// ── Secciones colapsables ──────────────────────────────────────────────────
// Llamar desde cada pagina que use secciones: initSections(primerAbierto)

function initSections(primerAbierto = true) {
  document.querySelectorAll(".section-header").forEach((header, i) => {
    const body  = header.parentElement.querySelector(".section-body");
    const arrow = header.querySelector(".arrow");
    if (!body) return;

    // Estado inicial
    const cerrar = primerAbierto ? i > 0 : true;
    if (cerrar) {
      body.classList.add("hidden");
      if (arrow) arrow.textContent = "▸";
    } else {
      body.classList.remove("hidden");
      if (arrow) arrow.textContent = "▾";
    }

    // Un solo handler por header usando onclick (no acumula duplicados)
    header.onclick = () => {
      body.classList.toggle("hidden");
      if (arrow) arrow.textContent = body.classList.contains("hidden") ? "▸" : "▾";
    };
  });
}

// ── Formateo ──────────────────────────────────────────────────────────────

function fmt$(n) {
  return "$\u00a0" + Number(n).toLocaleString("es-EC", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtFecha(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function badgeEstado(estado) {
  const map = {
    vencida:    ["badge-vencida",    "Vencida"],
    por_vencer: ["badge-por-vencer", "Por vencer"],
    vigente:    ["badge-vigente",    "Vigente"],
  };
  const [cls, label] = map[estado] || ["", estado];
  return `<span class="badge ${cls}">${label}</span>`;
}
