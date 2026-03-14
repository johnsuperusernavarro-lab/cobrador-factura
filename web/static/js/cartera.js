// cartera.js — Logica de la pagina Cartera
let _facturas = [];
let _filtro = "todos";
let _seleccionada = null;

// ── Carga XLS ─────────────────────────────────────────────────────────────
document.getElementById("xls-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const form = new FormData();
  form.append("archivo", file);

  toast("Procesando XLS...", "info");
  try {
    const res = await fetch("/api/cobros/cargar-xls", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail);
    const data = await res.json();
    _facturas = data.facturas;
    actualizarMetricas(data.stats);
    renderTabla();
    document.getElementById("btn-procesar").style.display = "";
    toast(`${_facturas.length} facturas cargadas`, "success");
  } catch (err) {
    toast("Error: " + err.message, "error");
  }
  e.target.value = "";
});

// ── Filtros ───────────────────────────────────────────────────────────────
document.querySelectorAll("[data-filtro]").forEach(btn => {
  btn.addEventListener("click", () => {
    _filtro = btn.dataset.filtro;
    document.querySelectorAll("[data-filtro]").forEach(b => {
      b.className = "btn btn-secondary";
    });
    btn.className = "btn btn-primary";
    renderTabla();
  });
});

// ── Render tabla ──────────────────────────────────────────────────────────
function renderTabla() {
  const tbody = document.getElementById("cartera-tbody");
  const lista = _filtro === "todos"
    ? _facturas
    : _filtro === "sin_contacto"
      ? _facturas.filter(f => !f.email && !f.telefono)
      : _facturas.filter(f => f.estado === _filtro);

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty"><div class="empty-icon">🔍</div><h3>Sin resultados</h3></div></td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map((f, i) => `
    <tr style="cursor:pointer;" onclick="seleccionar(${i})">
      <td>${f.numero}</td>
      <td>${f.cliente}</td>
      <td>${fmtFecha(f.fecha_emision)}</td>
      <td>${fmtFecha(f.fecha_vencimiento)}</td>
      <td style="font-weight:600;">${fmt$(f.saldo)}</td>
      <td>${badgeEstado(f.estado)}</td>
      <td>
        <button class="btn btn-secondary" style="padding:4px 10px;font-size:11px;"
          onclick="event.stopPropagation(); abrirWhatsappDirecto(${i})">💬</button>
        <button class="btn btn-primary" style="padding:4px 10px;font-size:11px;"
          onclick="event.stopPropagation(); enviarEmailDirecto(${i})">📧</button>
      </td>
    </tr>
  `).join("");
}

// ── Metricas ──────────────────────────────────────────────────────────────
function actualizarMetricas(stats) {
  if (!stats) return;
  document.getElementById("m-vencido").textContent    = fmt$(stats.vencido    ?? 0);
  document.getElementById("m-por-vencer").textContent = fmt$(stats.por_vencer ?? 0);
  document.getElementById("m-vigente").textContent    = fmt$(stats.vigente    ?? 0);
  document.getElementById("m-total").textContent      = fmt$(stats.total      ?? 0);
}

// ── Seleccion de fila ─────────────────────────────────────────────────────
async function seleccionar(idx) {
  const lista = _filtro === "todos" ? _facturas
    : _filtro === "sin_contacto" ? _facturas.filter(f => !f.email && !f.telefono)
    : _facturas.filter(f => f.estado === _filtro);

  _seleccionada = lista[idx];
  document.getElementById("panel-mensaje").style.display = "";
  document.getElementById("panel-cliente").textContent =
    `${_seleccionada.cliente} · ${_seleccionada.numero} · ${fmt$(_seleccionada.saldo)}`;

  const info = [];
  if (_seleccionada.email)    info.push(`✉ ${_seleccionada.email}`);
  if (_seleccionada.telefono) info.push(`📱 ${_seleccionada.telefono}`);
  document.getElementById("panel-info").textContent = info.join("   ") || "Sin datos de contacto";

  try {
    const data = await post("/api/cobros/mensaje", { factura: _seleccionada });
    document.getElementById("panel-texto").value = data.mensaje;
  } catch {
    document.getElementById("panel-texto").value = "";
  }
}

// ── Acciones ──────────────────────────────────────────────────────────────
function copiarMensaje() {
  const txt = document.getElementById("panel-texto").value;
  navigator.clipboard.writeText(txt).then(() => toast("Copiado", "success"));
}

async function abrirWhatsapp() {
  if (!_seleccionada?.telefono) { toast("Sin numero de telefono", "error"); return; }
  const msg = encodeURIComponent(document.getElementById("panel-texto").value);
  const tel = _seleccionada.telefono.replace(/\D/g, "");
  window.open(`https://wa.me/${tel}?text=${msg}`, "_blank");
}

async function enviarEmail() {
  if (!_seleccionada?.email) { toast("Sin email", "error"); return; }
  toast("Enviando email...", "info");
  try {
    await post("/api/cobros/enviar-email", {
      factura: _seleccionada,
      mensaje: document.getElementById("panel-texto").value,
    });
    toast("Email enviado", "success");
  } catch (err) {
    toast("Error: " + err.message, "error");
  }
}

function abrirWhatsappDirecto(idx) {
  const lista = _filtro === "todos" ? _facturas
    : _filtro === "sin_contacto" ? _facturas.filter(f => !f.email && !f.telefono)
    : _facturas.filter(f => f.estado === _filtro);
  _seleccionada = lista[idx];
  abrirWhatsapp();
}

function enviarEmailDirecto(idx) {
  const lista = _filtro === "todos" ? _facturas
    : _filtro === "sin_contacto" ? _facturas.filter(f => !f.email && !f.telefono)
    : _facturas.filter(f => f.estado === _filtro);
  _seleccionada = lista[idx];
  enviarEmail();
}

// ── Procesar todo ─────────────────────────────────────────────────────────
document.getElementById("btn-procesar").addEventListener("click", async () => {
  if (!confirm(`Enviar emails a TODOS los clientes con contacto?\n(${_facturas.filter(f=>f.email).length} facturas)`)) return;
  toast("Procesando...", "info");
  try {
    const res = await post("/api/cobros/procesar-todo", { facturas: _facturas });
    toast(`Enviados: ${res.enviados} · Errores: ${res.errores}`, "success");
  } catch (err) {
    toast("Error: " + err.message, "error");
  }
});
