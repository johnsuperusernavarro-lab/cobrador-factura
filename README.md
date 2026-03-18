# CONDORNEXUS — Gestión de Cuentas por Cobrar

**CONDORNEXUS** es una aplicación de escritorio nativa (PyQt5) para gestión inteligente de cuentas por cobrar y cotizaciones en empresas ecuatorianas. Funciona completamente en local: sin servidor HTTP, sin navegador, sin suscripción.

Compatible con cualquier software contable que exporte a XLS/XLSX/CSV, además de integración directa con la API de Contifico y la API de Alegra.

---

## Tabla de contenidos

1. [Características principales](#características-principales)
2. [Pantallas y flujo de uso](#pantallas-y-flujo-de-uso)
3. [Módulo de Cotizaciones](#módulo-de-cotizaciones)
4. [Arquitectura multi-software](#arquitectura-multi-software)
5. [Normalizador XLS universal](#normalizador-xls-universal)
6. [Normalizador de contactos](#normalizador-de-contactos)
7. [Score de clientes](#score-de-clientes)
8. [Flujo de datos interno](#flujo-de-datos-interno)
9. [Integración Nexo (Contifico API)](#integración-nexo-contifico-api)
10. [Base de datos SQLite](#base-de-datos-sqlite)
11. [Plantillas de mensaje](#plantillas-de-mensaje)
12. [Instalación y ejecución (desarrollo)](#instalación-y-ejecución-desarrollo)
13. [Compilar y distribuir como .exe portable](#compilar-y-distribuir-como-exe-portable)
14. [Estructura del proyecto](#estructura-del-proyecto)
15. [Stack técnico](#stack-técnico)
16. [Seguridad y privacidad](#seguridad-y-privacidad)

---

## Características principales

### Gestión de cartera multi-software

- **Auto-detección de formato** — carga XLS/XLSX/CSV de Contifico, Alegra, Monica 11 o cualquier exportación plana sin configuración previa
- **Sincronización via API** — descarga facturas pendientes y contactos directamente desde Contifico (Nexo) o Alegra
- **Filtros dinámicos** — vencidas / por vencer / todas; buscador en tiempo real por cliente o número de factura
- **Menú contextual** — clic derecho sobre cualquier fila: copiar, abrir WhatsApp, enviar email, marcar gestionado
- **Historial de cargas** — últimas 5 cargas con snapshot completo; restaura cualquiera sin necesidad del archivo XLS original
- **Exportar resultados** — exporta las filas visibles a XLSX (headers estilizados) o CSV (UTF-8 BOM, compatible Excel Windows)

### Cotizaciones y pre-facturación

- **Módulo completo de cotizaciones** — crea, edita, envía y convierte cotizaciones a flujo de cobro
- **Cliente híbrido** — campo de texto libre con autocompletar desde contactos existentes; linkeo opcional con datos de email/teléfono de la BD
- **Editor de ítems intuitivo** — tabla con Tab/Enter para navegar y agregar filas; totales calculados automáticamente
- **Estado y ciclo de vida** — máquina de estados: pendiente → enviada → aceptada / rechazada, con transiciones contextuales
- **Columna "Vence en X días"** — calculada en tiempo real con código de color (rojo si vencida, dorado si quedan ≤ 5 días)
- **Duplicar cotización** — crea una copia en estado "pendiente" con un solo clic
- **Envío multicanal** — genera mensaje a partir de plantilla configurable; email se copia al portapapeles, WhatsApp abre el navegador

### Comunicación y seguimiento

- **Email SMTP** — Gmail, Hotmail, Yahoo; envío individual y masivo con diálogo de confirmación
- **WhatsApp** — genera enlace `wa.me` con mensaje precargado; abre el chat directamente en el navegador
- **Tono adaptativo** — amable (clientes confiables) / neutro / firme (clientes riesgosos) — seleccionado automáticamente por el score
- **Plantillas editables** — 4 plantillas por defecto (vencida × email/WhatsApp, por_vencer × email/WhatsApp); editor de texto completo

### Automatización e inteligencia

- **Scheduler en background** — evalúa la cartera cada hora desde el primer arranque, sin intervención del usuario
- **Motor de reglas** — genera `acciones_sugeridas` con prioridad basada en días de atraso y clasificación de riesgo
- **Score de clientes** — recalculado automáticamente al cargar cartera nueva; persiste entre sesiones en SQLite
- **Procesar por importancia** — diálogo secuencial que recorre todas las acciones ordenadas de mayor a menor riesgo
- **Notificaciones de escritorio** — balloon notification de Windows cuando el scheduler detecta nuevas facturas vencidas

### Productividad

- **Dashboard con métricas en vivo** — total por cobrar, facturas vencidas, clientes en riesgo, mensajes enviados; cards clickeables navegan al módulo correspondiente
- **Estadísticas de recuperación** — tabla mensual con enviados, monto gestionado y barra de actividad visual por mes
- **Búsqueda global** — barra de búsqueda en la barra de herramientas (Ctrl+F); busca en Cartera, Acciones, Mensajes y Cotizaciones desde cualquier tab activo
- **Centro de mensajes** — historial completo de emails, WhatsApps y notas manuales; filtros por cliente, tipo e intervalo de tiempo
- **Importar contactos** — normaliza agendas XLS/CSV de cualquier software y las upsertea en la BD sin sobreescribir datos manuales
- **PDF / RIDEs** — drag & drop de comprobantes electrónicos ecuatorianos; extrae datos al instante y auto-detecta si la factura está vencida
- **Datos 100% locales** — `data/cobros.db` (SQLite WAL) y `data/config.json` nunca salen del equipo

---

## Pantallas y flujo de uso

### Launcher — "Entrar a CONDORNEXUS"

La primera ventana que aparece al abrir la app. Muestra el logo de **CONDORNEXUS**, la versión y un único botón **"▶ Entrar a CONDORNEXUS"**. Al hacer clic:

1. Inicia el scheduler en background (siempre activo)
2. Crea/migra la base de datos SQLite si no existe
3. Abre la ventana principal con las 8 pestañas

---

### Barra de herramientas global

Siempre visible en la parte superior de la ventana, debajo del menú.

- **Buscador global** (300px, Ctrl+F) — escribe cualquier texto y filtra en tiempo real:
  - Primero intenta en el tab activo
  - Si no hay resultados, cambia automáticamente al primer tab donde sí los haya (Cartera → Acciones → Mensajes → Cotizaciones)
  - Limpiar el campo restaura la vista sin filtros

---

### 🏠 Dashboard

Vista general del estado de la cartera en tiempo real.

**Métricas superiores (4 cards clickeables):**

| Card | Valor mostrado | Navega a |
|---|---|---|
| Total por cobrar | Suma de `monto_pendiente` de toda la cartera | Tab Cartera |
| Facturas vencidas | Cantidad con `tipo = "vencida"` | Tab Cartera |
| Clientes en riesgo | Clientes con score ≥ 66 | Tab Acciones |
| Mensajes enviados | Total de registros en `mensajes_log` | Tab Mensajes |

**Panel "Acciones del día"** — muestra las 5 acciones sugeridas más urgentes. Cada fila incluye:
- Borde izquierdo con el color del nivel de riesgo (rojo/dorado/azul)
- Nombre del cliente con wrap automático (sin truncamiento)
- Número de factura y monto
- Botón **✓ Listo** para marcar la acción como completada sin abrir el diálogo completo

**Panel "Estadísticas de recuperación"** — tabla de los últimos 6 meses:

| Columna | Descripción |
|---|---|
| Mes | Año-Mes (ej. `2025-03`) |
| Enviados | Total de mensajes enviados ese mes |
| Monto gestionado | Suma de montos de facturas contactadas |
| Actividad | Barra visual proporcional al mes de mayor actividad |

**Panel "Actividad reciente"** — tabla con las últimas interacciones del `mensajes_log`: fecha, cliente, canal, resumen.

**Banner de bienvenida** — visible solo cuando no hay facturas cargadas; guía al usuario a cargar su primer XLS o conectar con Nexo.

---

### 📊 Cartera

Gestión principal de facturas pendientes.

**Carga de datos:**
- Botón **"📂 Abrir XLS / XLSX / CSV"** — auto-detección del software de origen (Contifico, Alegra, Monica, Genérico)
- Botón **"🔗 Conectar Nexo"** — sincroniza directamente desde la API de Contifico sin necesidad de exportar archivos
- Indicador del software origen detectado (ej. `"Contifico"`, `"Alegra"`, `"Genérico EC"`)

**Filtros y búsqueda:**
- Pills de filtro: **Todas** / **Vencidas** / **Por Vencer**
- **Buscador en tiempo real** — filtra por nombre de cliente o número de factura con botón de limpiar integrado
- Leyenda de iconos: `●` contacto completo · `◑` contacto parcial · `○` sin contacto · `✎` con nota

**Panel de detalle (al seleccionar una fila):**
- Muestra todos los campos de la factura: cliente, factura N°, fecha emisión, fecha vencimiento, monto, saldo pendiente, email, teléfono
- Botón **Email** — abre diálogo de envío con mensaje generado por plantilla
- Botón **WhatsApp** — abre `wa.me/...` con mensaje precargado; deshabilitado con tooltip explicativo si no hay teléfono
- Tooltips dinámicos: si falta el teléfono, indica cómo agregarlo desde Nexo o escaneando RIDEs

**Menú contextual (clic derecho):**
- Copiar datos del cliente al portapapeles
- Abrir WhatsApp (deshabilitado si no hay teléfono)
- Enviar Email
- Marcar como gestionado

**Barra de acciones inferior:**

| Botón | Función |
|---|---|
| 📧 Envío masivo | Abre diálogo de confirmación y envía a todos los filtrados |
| 📥 Importar contactos | Abre XLS/CSV de agenda y hace upsert en BD |
| 💾 Exportar | Guarda las filas visibles en XLSX o CSV |
| 🕐 Historial | Muestra últimas 5 cargas; permite restaurar o eliminar |

---

### 🎯 Acciones

Módulo de priorización y procesamiento de cobros.

**Tabla de scores (panel izquierdo ~30%):**

| Columna | Descripción |
|---|---|
| Cliente | Razón social |
| Score | 0–100 (tooltip explica la escala) |
| Nivel | confiable / medio / riesgoso |
| Vencidas | Cantidad de facturas vencidas |
| Días prom. | Promedio de días de atraso |

Al seleccionar un cliente en la tabla de scores, la tabla de acciones se filtra automáticamente mostrando solo sus acciones pendientes.

**Tabla de acciones (panel derecho ~70%):**

| Columna | Descripción |
|---|---|
| Fecha | Fecha sugerida para actuar |
| Cliente | Razón social |
| Factura | Número de comprobante |
| Monto | Saldo pendiente |
| Acción | Texto de la acción sugerida |
| Botones | ▶ Procesar · ✎ Modificar |

**Botón "▶ Procesar por importancia"** — abre `ProcesarAccionDialog`:

```
Por cada acción (ordenadas: riesgoso → medio → confiable):
  1. Muestra: cliente, score, nivel, factura, monto, días vencida
  2. Selector de TONO: [Amable] [Neutro] [Firme]
       amable → plantilla "por_vencer"
       firme  → plantilla "vencida"
       neutro → plantilla del tipo real de la factura
  3. Selector de CANAL: [Email] [WhatsApp]
  4. Área de texto editable con el mensaje generado
  5. Botones: [Enviar] [Completar sin enviar] [Posponer +1 día] [◀ Anterior] [▶ Siguiente]

Al cerrar: resumen "X enviados, Y completados sin envío"
```

**Botón "🔄 Evaluar ahora"** — ejecuta el motor de reglas inmediatamente en thread daemon y refresca ambas tablas.

**Botón "📊 Actualizar scores"** — recalcula todos los scores desde `facturas_cache`.

---

### 💬 Mensajes

Historial centralizado de todas las interacciones con clientes.

**Filtros:**
- Campo de texto: filtra por nombre de cliente (en tiempo real)
- ComboBox tipo: Todos / cobranza / seguimiento / otro
- ComboBox período: Todos / Últimos 7 días / Últimos 30 días / Este mes

**Tabla de historial** (columnas: Fecha · Cliente · Factura · Tipo · Canal · Enviado por · Mensaje)

**Panel "Registrar interacción"** (colapsable con animación):
- Campos: cliente, factura N°, tipo, canal
- Área de texto para describir la interacción (resultado de llamada, acuerdo de pago, etc.)
- Botones: Guardar / Cancelar

Tipos de interacción registradas automáticamente: email enviado, WhatsApp abierto, nota manual.

---

### 🔄 Nexo (Contifico)

Integración con el sistema contable.

**Estado de conexión** — badge que muestra `✓ Conectado` o `✗ Error`; si falta el token muestra botón **"⚙ Configurar token"** que abre Ajustes directamente.

**Cards de métricas (2×2):**
- Contactos en BD / Facturas en cache / Vencidas / Por vencer

**Importar cartera pendiente:**
- Descarga todas las facturas con saldo pendiente desde la API
- Equivalente a cargar el XLS pero totalmente automático
- También actualiza contactos y recalcula scores
- Barra de progreso y log de texto durante la sincronización
- Al terminar, el tab Cartera se refresca automáticamente

**Sincronizar contactos:**
- Abre `ContificoDialog` con opciones avanzadas (selección por lotes, preview)
- Upsert de email y teléfono para todos los clientes

---

### 💼 Cotizaciones

Módulo completo de pre-facturación para el ciclo comercial.

#### Vista principal

La pantalla de Cotizaciones usa un diseño adaptativo:

- **Estado vacío** — cuando no hay ninguna cotización, se muestra un ícono grande, una descripción del módulo y un botón **"＋ Crear primera cotización"** que guía al usuario a empezar
- **Vista con datos** — tabla de cotizaciones + barra de acciones + pills de filtro con contadores

**Pills de filtro (con conteo en vivo):**

| Pill | Muestra |
|---|---|
| Todas | Total de cotizaciones en el sistema |
| Pendientes | Cotizaciones en estado `pendiente` |
| Enviadas | Cotizaciones en estado `enviada` |
| Aceptadas | Cotizaciones en estado `aceptada` |
| Rechazadas | Cotizaciones en estado `rechazada` |

**Tabla de cotizaciones (5 columnas):**

| Columna | Contenido |
|---|---|
| N° | ID de la cotización (auto-incremental) |
| Cliente | Nombre o razón social |
| Total | Suma de todos los ítems (formateado con símbolo $) |
| Estado | Badge con color por estado |
| Vence en | Calculado dinámicamente desde `creada_en + validez_dias - hoy` |

**Columna "Vence en"** — código de color:
- Texto normal si quedan más de 5 días
- **Dorado** (`#ea9d34`) si quedan 1–5 días
- **Rojo** (`#b4637a`) si ya venció (días negativos)

**Barra de acciones (se habilita al seleccionar una cotización):**

| Botón | Función |
|---|---|
| ✏ Editar | Abre el formulario en modo edición |
| 📤 Enviar | Abre diálogo de envío multicanal |
| 📋 Duplicar | Crea copia en estado `pendiente` con todos los ítems |
| ↔ Estado | Cambia el estado con transiciones contextuales |
| 🔗 Convertir | Marca la cotización como aceptada y abre el tab Cartera |
| 🗑 Eliminar | Elimina la cotización y todos sus ítems (CASCADE) |

#### Formulario de cotización (Crear / Editar)

Accedido desde el botón **"＋ Nueva"** o **"✏ Editar"**.

**Campos del encabezado:**

| Campo | Descripción |
|---|---|
| Cliente | Campo de texto libre con autocompletar desde contactos de la BD |
| Email | Se autocompleta si se selecciona un contacto existente |
| Teléfono | Se autocompleta si se selecciona un contacto existente |
| Notas | Observaciones generales de la cotización |

**Campo Cliente — enfoque híbrido:**

El campo acepta texto libre para clientes nuevos, pero ofrece autocompletar (QCompleter con `MatchContains`) sobre los contactos existentes en la BD. Al seleccionar un contacto:
- Se vincula mediante `contacto_id` (FK nullable en la tabla `cotizaciones`)
- Se autocompletan `email` y `teléfono`
- Se muestra un badge `✓ {nombre_contacto}` bajo el campo confirmando el vínculo

Si el usuario escribe un nombre sin seleccionar de la lista, la cotización queda como cliente libre sin vínculo a contacto.

**Validez de la cotización:**

Presets rápidos con botones: **15 días** · **30 días** · **60 días**. También editable con un spinner numérico. Debajo se muestra la fecha exacta de vencimiento calculada dinámicamente (`creada_en + validez_dias`).

**Tabla de ítems:**

La tabla tiene 4 columnas: **Descripción** · **Cantidad** · **Precio Unitario** · **Total**.

- La columna **Total** es de solo lectura, con fondo calculado (`#f0ede8`) y texto en color pine; se actualiza automáticamente al cambiar cantidad o precio
- **Navegación intuitiva**: Tab o Enter en la última columna de la última fila agrega automáticamente una fila nueva y posiciona el cursor en la descripción
- **Hint visual**: cuando la tabla está vacía, aparece una etiqueta superpuesta `"Agrega un ítem para comenzar — usa Tab para avanzar entre columnas"` sobre el área de la tabla; desaparece en cuanto se agrega el primer ítem
- Al abrir el formulario en modo **Nuevo**, se agrega una primera fila vacía automáticamente y el foco va directo a la descripción

**Total general:**

Se muestra actualizado en tiempo real debajo de la tabla con formato `$ X,XXX.XX`. Al guardar, se persiste en el campo `total` de la cotización.

**Validaciones al guardar:**

- El campo Cliente no puede estar vacío
- Si se proporcionó email, debe contener `@`
- Aviso (no bloqueante) si se guardó sin email ni teléfono, ya que no se podrá enviar
- Confirmación al cerrar el formulario si hay cambios no guardados y la tabla tiene ítems

#### Envío de cotización

El diálogo **"📤 Enviar"** muestra:

1. **Vista previa del mensaje** — generada por `cotizacion_service.generar_mensaje_cotizacion()` con los datos de la cotización y los ítems; el usuario puede editar el texto antes de enviar
2. **Selector de canal**: Email o WhatsApp
3. **Nota de comportamiento**:
   - **Email** → el mensaje se copia al portapapeles; se indica que el cliente de correo del usuario se abre con el destinatario pre-cargado
   - **WhatsApp** → abre `wa.me/5939XXXXXXXX?text=...` en el navegador con el mensaje URL-encoded

Al confirmar el envío:
- El estado de la cotización cambia automáticamente a `enviada`
- Se registra la interacción en `mensajes_log`
- La tabla de cotizaciones se refresca

**Normalización de teléfonos ecuatorianos:**
`09XXXXXXXX` → `5939XXXXXXXX` (prefijo Ecuador para wa.me)

#### Cambio de estado contextual

El diálogo **"↔ Estado"** no muestra un desplegable genérico, sino botones contextuales según el estado actual:

| Estado actual | Transiciones disponibles |
|---|---|
| `pendiente` | → Enviada · → Rechazada |
| `enviada` | → Aceptada · → Rechazada |
| `aceptada` | → Pendiente (reabrir) |
| `rechazada` | → Pendiente (reabrir) |

Cada botón tiene su propio color (pine para aceptada/enviada, love para rechazada, muted para reabrir).

#### Convertir a cobro

El botón **"🔗 Convertir"** marca la cotización como `aceptada` y navega al tab Cartera. El flujo de carga del XLS o sincronización con Nexo se usa para registrar la factura real una vez emitida en el sistema contable.

#### Duplicar cotización

Crea una copia completa de la cotización seleccionada (encabezado + todos los ítems) con estado `pendiente` y fecha de creación actual. Útil para cotizaciones recurrentes o variaciones de precio.

---

### 📄 PDFs

Procesamiento de RIDEs (comprobantes electrónicos ecuatorianos).

**Drag & drop** — arrastra uno o varios PDFs sobre el área indicada.

**Por cada PDF procesado:**
- Extracción automática: razón social, factura N°, fecha emisión, emails, teléfono, total, descripción
- **Auto-detección de tipo** — compara la fecha de emisión con hoy; pre-selecciona "vencida" o "por_vencer" en el combo
- Preview del mensaje generado con la plantilla de la BD
- Botones: Enviar por Email / Abrir WhatsApp

**Doble clic sobre un ítem** — abre diálogo con todos los datos extraídos del PDF (razón social, factura, fecha, total, emails, teléfono, descripción).

---

### ⚙ Ajustes

Accesible desde:
- La pestaña **"⚙ Ajustes"** en la barra lateral (abre el diálogo y vuelve al tab anterior)
- El botón **"⚙ Ajustes"** en la barra de estado inferior

Secciones en acordeón (cada una colapsable independientemente):

| Sección | Configuración |
|---|---|
| **Correo electrónico** | Dirección, contraseña de aplicación, servidor SMTP, puerto |
| **Remitente** | Nombre, empresa, cargo (para la firma automática) |
| **Datos bancarios** | Banco, número de cuenta, tipo de cuenta, CI/RUC |
| **Contifico / Nexo API** | Token de API (Contifico → Configuración → Integraciones) |
| **Proveedor activo** | Selecciona entre Contifico, Alegra o Excel como fuente principal |

Todos los datos se guardan en `data/config.json` y nunca se hardcodean en el código.

---

## Módulo de Cotizaciones

### Arquitectura interna

```
ui/cotizaciones_widget.py        ← Tab principal (QStackedWidget: empty state / contenido)
ui/cotizacion_form_dialog.py     ← Formulario crear/editar (QDialog)
app/services/cotizacion_service.py ← Generación de mensajes y URLs WhatsApp
core/cotizaciones.py             ← Re-exporta cotizacion_service para uso desde ui/
app/database.py                  ← 8 funciones CRUD + 2 tablas nuevas
```

### Tablas de base de datos

**`cotizaciones`** — encabezado de cada cotización:

```sql
CREATE TABLE IF NOT EXISTS cotizaciones (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    cliente       TEXT     NOT NULL,
    contacto_id   INTEGER  REFERENCES contactos(id) ON DELETE SET NULL,  -- nullable
    email         TEXT,
    telefono      TEXT,
    estado        TEXT     DEFAULT 'pendiente',   -- pendiente|enviada|aceptada|rechazada
    validez_dias  INTEGER  DEFAULT 30,
    notas         TEXT,
    total         REAL     DEFAULT 0,
    creada_en     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`cotizacion_items`** — líneas de cada cotización:

```sql
CREATE TABLE IF NOT EXISTS cotizacion_items (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    cotizacion_id INTEGER  NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,
    descripcion   TEXT     NOT NULL,
    cantidad      REAL     DEFAULT 1,
    precio_unit   REAL     DEFAULT 0,
    total         REAL     DEFAULT 0
);
```

### Funciones CRUD (`app/database.py`)

| Función | Descripción |
|---|---|
| `crear_cotizacion(datos, items)` | Inserta cotización + ítems en transacción atómica |
| `get_cotizacion(id)` | Devuelve dict con todos los campos de una cotización |
| `get_cotizaciones(estado=None)` | Lista cotizaciones, filtradas opcionalmente por estado |
| `get_items_cotizacion(cotizacion_id)` | Lista de ítems de una cotización |
| `actualizar_estado_cotizacion(id, estado)` | Cambia estado y actualiza `actualizada_en` |
| `actualizar_cotizacion(id, datos, items)` | Reemplaza encabezado e ítems en transacción |
| `eliminar_cotizacion(id)` | Elimina cotización y sus ítems (CASCADE automático) |
| `buscar_contactos_para_cotizacion(texto)` | Fuzzy search sobre `contactos` para el autocompletar |

Todas estas funciones están re-exportadas en `core/database.py` (lista explícita).

### Servicio de mensajes (`app/services/cotizacion_service.py`)

```python
asunto, cuerpo = generar_mensaje_cotizacion(cotizacion, items, canal="email")
# canal: "email" | "whatsapp"
# Usa ConfigManager para el nombre del remitente y empresa
# No usa message_service.py (esa capa es exclusiva para cobros)

url = generar_url_whatsapp(telefono, mensaje)
# Normaliza 09XXXXXXXX → 5939XXXXXXXX
# Devuelve "https://wa.me/5939XXXXXXXX?text=..."
```

### Máquina de estados completa

```
                    ┌──────────┐
                    │ pendiente│ ◀─────────────────────────┐
                    └────┬─────┘                           │
                         │ enviar / cambiar estado         │
                    ┌────▼─────┐                     reabrir
                    │  enviada │                           │
                    └────┬─────┘                           │
                ┌────────┴────────┐                        │
                │                 │                        │
          ┌─────▼────┐      ┌─────▼──────┐                │
          │ aceptada │      │ rechazada  │ ───────────────┘
          └─────┬────┘      └────────────┘
                │
          convertir a cobro
                │
          Tab Cartera
```

---

## Arquitectura multi-software

La capa `core/providers/` implementa el **Adapter Pattern** para desacoplar completamente la UI de cualquier fuente de datos contable.

### Contrato `AccountingProvider` (`core/base_provider.py`)

```python
class AccountingProvider(ABC):
    @property
    @abstractmethod
    def nombre(self) -> str: ...           # "Contifico", "Alegra", "Excel/CSV"

    @abstractmethod
    def verificar_conexion(self) -> tuple[bool, str]: ...    # (ok, mensaje_legible)

    @abstractmethod
    def get_cartera(self, progreso_cb=None) -> list[dict]: ...   # facturas normalizadas

    @abstractmethod
    def get_contactos(self, progreso_cb=None) -> list[dict]: ... # contactos enriquecidos
```

Cada proveedor transforma su fuente de datos al formato interno estándar; la UI nunca sabe qué software se está usando.

### Proveedores registrados

| `type` en `config.json` | Clase | Estado | Fuente |
|---|---|---|---|
| `contifico` | `ContificoProvider` | ✅ producción | API REST Contifico |
| `excel` | `ExcelProvider` | ✅ producción | XLS/XLSX/CSV via normalizador |
| `alegra` | `AlegraProvider` | ⚠️ MOCK\_MODE=True (cableado listo) | API REST Alegra |

Para activar Alegra real: cambiar `MOCK_MODE = False` en `core/providers/alegra_provider.py`.

### Factory `get_provider()` (`core/providers/__init__.py`)

```python
from core.providers import get_provider

proveedor = get_provider()              # lee ConfigManager automáticamente
facturas  = proveedor.get_cartera()    # list[dict] en formato interno estándar
```

El registro es lazy: los módulos de cada proveedor solo se importan cuando se usan por primera vez.

### Agregar soporte para un nuevo software

1. Crear `core/providers/nuevo_provider.py` heredando `AccountingProvider`
2. Registrar la clase en `_REGISTRY` de `core/providers/__init__.py`
3. **Si tiene API REST**: implementar `_get(endpoint)` con su esquema de autenticación
4. **Si solo exporta Excel**: crear `data/templates/nuevo_xls.json` con mapeo de columnas y usar `ExcelProvider`

---

## Normalizador XLS universal

`app/services/xls_normalizer.py` — detecta y parsea carteras de cualquier software sin configuración manual.

### API pública

```python
from app.services.xls_normalizer import normalizar_cartera

resultado = normalizar_cartera("cartera.xlsx", progreso_cb=None)

resultado.software      # "Contifico" | "Alegra" | "Monica" | "Genérico EC" | ...
resultado.facturas      # list[dict]  — formato interno estándar
resultado.advertencias  # list[str]   — filas omitidas con motivo
resultado.col_map       # dict        — mapa campo→índice detectado (útil para debug)
```

### Algoritmo de detección (en orden)

```
1. Abrir el archivo con xlrd (.xls binario) u openpyxl (.xlsx/.csv)

2. _es_formato_contifico(ws)
   └─ Escanea primeras 50 filas buscando "FAC" en columna 2 (≥ 2 ocurrencias)
   └─ SÍ → _parse_contifico() → cobros_service.parse_reporte()
           Maneja buckets de antigüedad 0-30 / 30-60 / 60-90 / 90-120 / +120 días
   └─ NO → continuar

3. _encontrar_encabezado_xls(ws)
   └─ Busca la primera fila con ≥ 3 celdas de texto no vacías → fila de encabezados

4. _mapear_columnas(headers)
   └─ rapidfuzz.process.extractOne() con score_cutoff=72
   └─ Contra tabla _SINONIMOS: 10 campos × múltiples sinónimos en español e inglés

5. _validar_columnas_minimas()
   └─ Requiere al menos: campo "cliente" + algún campo de monto
   └─ Lanza ValueError descriptivo si faltan

6. _inferir_software(headers)
   └─ Detecta keywords específicos por software para nombrar la fuente detectada

7. _fila_a_factura(row, col_map)
   └─ Normaliza montos (coma→punto, símbolo $), fechas, strings vacíos
   └─ Omite filas con monto_pendiente = 0 o sin nombre de cliente
```

### Sinónimos reconocidos

| Campo interno | Sinónimos aceptados |
|---|---|
| `cliente` | Cliente, Razón Social, Nombre, Beneficiario, Customer, Client Name... |
| `monto_pendiente` | Saldo, Pendiente, Balance, Por Cobrar, Outstanding, Amount Due... |
| `fecha_vencimiento` | Vencimiento, Fecha Venc, Vence, Due Date, F. Vencimiento, Expiry... |
| `factura_no` | Factura, Número, Comprobante, No., Invoice, Voucher, Document... |
| `fecha_emision` | Emisión, Fecha, F. Emisión, Issue Date, Date... |
| `email` | Email, Correo, E-mail, Mail... |
| `telefono` | Teléfono, Tel, Celular, Phone, Mobile... |

### Normalización de fechas

Acepta y convierte automáticamente a `DD/MM/YYYY`:
- `DD/MM/YYYY` — formato ecuatoriano nativo
- `YYYY-MM-DD` — ISO 8601
- `MM/DD/YYYY` — Excel norteamericano (detectado cuando el "día" > 12)
- Número serial Excel (días desde 1900-01-01)

---

## Normalizador de contactos

`app/services/contactos_normalizer.py` — importa agendas de clientes desde cualquier XLS/XLSX/CSV.

### API pública

```python
from app.services.contactos_normalizer import normalizar_contactos, importar_contactos_a_db

resultado = normalizar_contactos("agenda.xlsx")
resultado.contactos     # list[dict] con nombre, email, telefono, cedula_ruc
resultado.advertencias  # filas sin email ni teléfono (ignoradas)

importados, omitidos = importar_contactos_a_db(resultado.contactos)
# importados = contactos nuevos o actualizados
# omitidos   = entradas con fuente='manual' y confianza≥1.0 (respetadas)
```

### Comportamiento de upsert

- Si el cliente **no existe** en la BD: se inserta con `fuente='excel'`
- Si el cliente **existe con fuente manual** (`confianza >= 1.0`): se respeta y no se sobreescribe
- Si el cliente **existe con fuente automática**: se actualiza el email/teléfono si el nuevo es más completo

Usa el mismo fuzzy matching (rapidfuzz, `score_cutoff=70`) que el normalizador de cartera, con sinónimos propios para campos de contacto: nombre / email / teléfono / CI/RUC.

---

## Score de clientes

Calculado por `app/services/scoring_service.py` sobre los datos de `facturas_cache`.

### Fórmula

```
score = 30
      + (n_vencidas × 15)
      + (días_promedio_atraso × 0.5)
      + (10 si n_vencidas > 2)

score = max(0, min(100, score))
```

### Clasificaciones y tono de comunicación

| Score | Clasificación | Color UI | Tono automático | Plantilla usada |
|---|---|---|---|---|
| 0 – 35 | **confiable** | pine `#286983` | amable | `por_vencer` |
| 36 – 65 | **medio** | gold `#ea9d34` | neutro | tipo real de la factura |
| 66 – 100 | **riesgoso** | love `#b4637a` | firme | `vencida` |

El score persiste en la tabla `score_clientes` y se recalcula automáticamente al:
- Cargar un nuevo archivo XLS/XLSX/CSV
- Sincronizar facturas desde la API de Nexo
- Usar el botón "📊 Actualizar scores" en el tab Acciones
- Cada hora via el scheduler en background

---

## Flujo de datos interno

### Cargar cartera desde XLS/XLSX/CSV

```
Usuario abre archivo en tab Cartera
    └── cobros_widget._cargar_xls(ruta)
            └── xls_normalizer.normalizar_cartera(ruta)
                    ├── _es_formato_contifico? → cobros_service.parse_reporte()
                    └── _parse_generico() → _mapear_columnas() → _fila_a_factura()
            └── Enriquece cada factura con email/teléfono de tabla contactos
            └── db.guardar_facturas_cache(facturas)
            └── db.registrar_carga_historial(...)   → guarda snapshot completo
            └── db.limpiar_historial_antiguo(5)     → descarta cargas más antiguas
            └── scoring_service.recalcular_todos_los_scores()   [thread daemon]
            └── Refresca la lista con los datos normalizados
```

### Restaurar desde historial

```
Tab Cartera → "🕐 Historial" → HistorialDialog
    └── Muestra últimas 5 cargas (fecha, software, n_facturas, monto, archivo)
    └── Usuario elige "Restaurar"
            └── db.restaurar_desde_historial(carga_id)
                    └── Lee cargas_snapshot → devuelve list[dict] en formato estándar
            └── CobrosWidget muestra esas facturas sin requerir el XLS original
```

### Sincronizar cartera desde Nexo (API)

```
Tab Nexo → "📥 Sincronizar Facturas"
    └── _SyncFacturasWorker (QThread)
            └── ContificoService.get_facturas_pendientes()   [urllib.request, sin bloqueo Qt]
            └── db.guardar_facturas_cache(facturas)
            └── db.upsert_contacto() para cada cliente encontrado
            └── recalcular_todos_los_scores()
            └── emit facturas_sincronizadas
                    └── CobrosWidget.cargar_desde_cache()   [refresco automático]
```

### Ciclo de vida de una cotización

```
"＋ Nueva" → CotizacionFormDialog (modo crear)
    └── Usuario ingresa cliente (texto libre o selecciona de autocompletar)
    └── Agrega ítems: Tab/Enter navega y crea filas nuevas automáticamente
    └── Elige validez: 15d / 30d / 60d o valor personalizado
    └── Guardar → db.crear_cotizacion(datos, items)
    └── CotizacionesWidget.refrescar() → tabla actualizada

"📤 Enviar" → _EnviarCotizacionDialog
    └── cotizacion_service.generar_mensaje_cotizacion(cot, items, canal)
    └── Email: mensaje copiado al portapapeles + log en mensajes_log
    └── WhatsApp: apertura de wa.me en navegador + log en mensajes_log
    └── db.actualizar_estado_cotizacion(id, "enviada")

"↔ Estado" → _CambiarEstadoDialog (botones contextuales por estado actual)
    └── db.actualizar_estado_cotizacion(id, nuevo_estado)

"🔗 Convertir" → estado → "aceptada" + navegar a Tab Cartera
```

### Scheduler en background + notificaciones (thread-safe)

```
main/__main__.py → activar()   [se llama al arrancar, unconditional]
    └── automation_service.activar()
            └── threading.Timer(3600, _evaluar_loop)   [thread daemon]
                    └── evaluar_facturas()
                            └── db.get_facturas_cache()
                            └── aplicar_reglas() → db.crear_accion_sugerida()
                            └── scoring_service.recalcular_todos_los_scores()
                            └── detecta nuevas vencidas → _push_evento("nuevas_vencidas", ...)
                            └── schedule next Timer(3600, ...)

MainWindow._poll_eventos_scheduler()   [QTimer cada 5s — hilo Qt]
    └── pop_eventos() → lista de eventos desde queue.Queue
    └── tray.showMessage(...)   [balloon notification de Windows]
```

### Señales inter-widget (via `main_window.py`)

```
ContificoWidget.facturas_sincronizadas  →  CobrosWidget.cargar_desde_cache
DashboardWidget.tab_request(int)        →  QTabWidget.setCurrentIndex
[todos los widgets].status_msg(str)     →  QStatusBar.showMessage (8 segundos)
```

Los widgets **nunca se referencian directamente entre sí**. Toda comunicación pasa por `MainWindow._build_tabs()`.

---

## Integración Nexo (Contifico API)

Cliente implementado en `app/services/contifico_service.py` usando únicamente `urllib.request` (stdlib, sin dependencias externas).

### Autenticación

```
Header: Authorization: Bearer <api_token>
Base URL: https://api.contifico.com/sistema/api/v1
```

El token se almacena en `data/config.json` bajo la clave `provider.api_token` y nunca se hardcodea en el código.

### Endpoints utilizados

| Endpoint | Método | Uso |
|---|---|---|
| `/documento/?tipo_documento=FAC&estado=P` | GET | Facturas pendientes de cobro |
| `/persona/` | GET | Contactos (email, teléfono, RUC/CI) |

### Formato interno de factura (estándar de todos los proveedores)

```python
{
    "cliente":           str,    # razón social
    "factura_no":        str,    # ej. "001-001-000123456"
    "fecha_emision":     str,    # "DD/MM/YYYY"
    "fecha_vencimiento": str,    # "DD/MM/YYYY"
    "descripcion":       str,
    "monto":             float,  # total original de la factura
    "monto_pendiente":   float,  # saldo pendiente (redondeado a 2 decimales)
    "tipo":              str,    # "vencida" | "por_vencer"
    "email":             str,
    "telefono":          str,
    "cedula_ruc":        str,
}
```

Este diccionario es producido por **todos los proveedores** (Contifico, Excel, Alegra), garantizando que la UI siempre recibe la misma estructura independientemente del software origen.

---

## Base de datos SQLite

Archivo: `data/cobros.db` — modo WAL para concurrencia segura entre el hilo Qt y el scheduler en background.
Toda interacción pasa exclusivamente por funciones declaradas en `app/database.py`.

### Tablas (12 en total)

| Tabla | Descripción | Columnas clave |
|---|---|---|
| `contactos` | Email y teléfono por cliente | `razon_social`, `email`, `telefono`, `fuente`, `confianza` |
| `plantillas` | Plantillas de mensaje editables | `tipo` (vencida/por\_vencer), `canal` (email/whatsapp), `asunto`, `cuerpo` |
| `facturas_enviadas` | Historial de envíos con monto | `factura_no`, `fecha_envio`, `canal`, `monto` — evita duplicados por día |
| `facturas_cache` | Última cartera cargada | `factura_no`, `cliente`, `monto_pendiente`, `tipo`, JSON completo |
| `score_clientes` | Score 0-100 por cliente | `cliente`, `score`, `clasificacion`, `dias_promedio`, `n_vencidas` |
| `mensajes_log` | Historial de interacciones | `cliente`, `canal`, `tipo`, `contenido`, `enviado_por`, `fecha` |
| `acciones_sugeridas` | Cola del motor de reglas | `cliente`, `factura_no`, `prioridad`, `estado`, `fecha_sugerida` |
| `config_sistema` | KV store interno | `clave`, `valor` |
| `cargas_historial` | Metadatos de las últimas 5 cargas | `software_origen`, `n_facturas`, `monto_total`, `nombre_archivo` |
| `cargas_snapshot` | Snapshot completo por carga | `carga_id` (FK CASCADE), todos los campos de cada factura |
| `cotizaciones` | Encabezado de cotizaciones | `cliente`, `contacto_id` (FK nullable), `estado`, `validez_dias`, `total` |
| `cotizacion_items` | Ítems de cada cotización | `cotizacion_id` (FK CASCADE), `descripcion`, `cantidad`, `precio_unit`, `total` |

`cargas_snapshot` usa `ON DELETE CASCADE` sobre `cargas_historial`: eliminar una carga borra automáticamente su snapshot.
`cotizacion_items` usa `ON DELETE CASCADE` sobre `cotizaciones`: eliminar una cotización borra automáticamente todos sus ítems.

### Campo `fuente` en tabla `contactos`

| Valor | Origen del dato |
|---|---|
| `manual` | Ingresado manualmente por el usuario |
| `contifico_api` | Importado desde la API de Contifico |
| `contifico_facturas` | Extraído de facturas sincronizadas desde Contifico |
| `rides_scan` | Extraído de un RIDE PDF |
| `excel` | Importado desde columnas email/teléfono del XLS (normalizador de contactos) |

### Regla crítica: re-exportación explícita en `core/database.py`

`core/database.py` re-exporta funciones de `app/database.py` con una **lista explícita**. Toda función nueva en `app/database.py` debe agregarse manualmente a esa lista, de lo contrario los widgets de `ui/` lanzarán `AttributeError` al arrancar.

---

## Plantillas de mensaje

### Variables disponibles en el cuerpo de las plantillas (cobros)

```
{cliente}         Razón social del cliente
{factura_no}      Número de factura  (ej. 001-001-000123)
{fecha}           Fecha de vencimiento en DD/MM/YYYY
{total}           Monto pendiente formateado con $ y decimales
{descripcion}     Descripción del producto o servicio facturado
```

### Placeholders de firma — resueltos automáticamente desde `config.json`

```
[TU NOMBRE]        →  config.remitente.nombre
[TU EMPRESA]       →  config.remitente.empresa
[TU CARGO]         →  config.remitente.cargo
[TU BANCO]         →  config.banco.nombre
[NUMERO DE CUENTA] →  config.banco.numero
[TIPO DE CUENTA]   →  config.banco.tipo
[CI/RUC]           →  config.banco.ci
```

### Plantillas por defecto (creadas en la primera ejecución)

| ID | Tipo | Canal | Uso |
|---|---|---|---|
| 1 | `por_vencer` | `email` | Recordatorio amable antes del vencimiento |
| 2 | `por_vencer` | `whatsapp` | Recordatorio corto para WhatsApp |
| 3 | `vencida` | `email` | Cobro formal de factura vencida |
| 4 | `vencida` | `whatsapp` | Cobro directo por WhatsApp |

### Mensajes de cotización

Los mensajes generados para cotizaciones se producen por `cotizacion_service.generar_mensaje_cotizacion()` y **no** usan la tabla `plantillas` (que es exclusiva para cobros). El servicio construye el mensaje con:
- Encabezado de saludo personalizado (nombre del remitente desde ConfigManager)
- Tabla de ítems formateada para el canal (texto plano para WhatsApp, estructura más rica para email)
- Total general destacado
- Condiciones de validez y fecha de vencimiento de la cotización
- Datos bancarios si están configurados

---

## Instalación y ejecución (desarrollo)

### Requisitos del sistema

- Windows 10 / 11 (64-bit)
- Python 3.14 — instalado en `C:\Users\USERS\AppData\Local\Programs\Python\Python314\`
- Git (opcional, para clonar el repositorio)

### Instalación

```bash
git clone <url-del-repo>
cd cobrador_Desktop

"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m pip install -r requirements.txt
```

### Ejecución

```bash
# Opción A — script de entrada directo
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" main.py

# Opción B — como módulo (funciona desde cualquier ruta)
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m main
```

### Primera configuración tras ejecutar

1. Hacer clic en **"▶ Entrar a CONDORNEXUS"** en la ventana de lanzamiento
2. Abrir **⚙ Ajustes** (barra lateral o botón en la barra inferior)
3. Configurar:
   - **Correo**: dirección de email + contraseña de aplicación (no la contraseña normal de Gmail; generarla en Cuenta Google → Seguridad → Contraseñas de aplicación)
   - **Remitente**: nombre, empresa y cargo para la firma automática en mensajes
   - **Contifico / Nexo API**: token desde Contifico → Configuración → Integraciones → API
   - **Datos bancarios**: banco, número de cuenta, tipo y CI/RUC para incluir en mensajes de cobro
4. En el tab **Cartera**: cargar un XLS/XLSX/CSV, o ir al tab **Nexo** para sincronizar desde la API
5. En el tab **Cotizaciones**: crear la primera cotización con **"＋ Nueva"**

### Dependencias (`requirements.txt`)

| Paquete | Versión | Motivo |
|---|---|---|
| `PyQt5` | ≥ 5.15 | Interfaz gráfica nativa Windows |
| `pdfplumber` | ≥ 0.9 | Extracción de texto estructurado de RIDEs PDF |
| `xlrd` | **== 1.2.0** | Única versión compatible con `.xls` binario Excel 97-2003 |
| `rapidfuzz` | ≥ 2.0 | Fuzzy matching para auto-detección de columnas XLS y contactos |
| `yagmail` | ≥ 0.15 | Wrapper SMTP optimizado para Gmail |
| `pyperclip` | ≥ 1.8 | Copiar al portapapeles (mensajes WhatsApp y cotizaciones) |
| `openpyxl` | ≥ 3.1 | Lectura de `.xlsx` modernos y exportación con headers estilizados |

> **Nota importante sobre `xlrd`**: Contifico exporta `.xls` en formato binario Excel 97-2003. La versión `xlrd >= 2.0` eliminó soporte para este formato. La versión `1.2.0` es obligatoria y está fijada en `requirements.txt`.

---

## Compilar y distribuir como .exe portable

El resultado final es una **carpeta autocontenida** (`dist/CONDORNEXUS/`) que incluye Python embebido, todas las DLLs de Qt, las dependencias y los assets. El usuario final no necesita instalar Python ni ninguna librería.

### Paso 1 — Compilar

Doble clic en **`BUILD.bat`** (o ejecútalo desde la terminal).

```bat
BUILD.bat
```

- Llama a PyInstaller con el spec `CobradordFacturas.spec`
- Demora entre 2 y 4 minutos la primera vez
- Resultado: `dist\CONDORNEXUS\` con `CONDORNEXUS.exe` y todos sus archivos de soporte

El spec incluye automáticamente:
- `styles/styles.qss` — tema visual
- `resources/icon.ico` — icono de la aplicación
- `data/templates/` — JSONs del normalizador XLS (necesarios en runtime)
- Todas las DLLs de PyQt5, pdfplumber, pdfminer (via `collect_all`)

### Paso 2 — Limpiar datos de sesión del desarrollador

Doble clic en **`PREPARAR_PARA_TESTER.bat`**.

```bat
PREPARAR_PARA_TESTER.bat
```

Elimina de `dist\CONDORNEXUS\data\`:
- `config.json` — credenciales del desarrollador
- `cobros.db` — base de datos con datos de prueba

El nuevo usuario arrancará con la app completamente limpia y configurará sus propios datos.

### Paso 3 — Empaquetar y distribuir

Comprimir la carpeta `dist\CONDORNEXUS\` en un ZIP:

```
CONDORNEXUS.zip
  └── CONDORNEXUS\
        ├── CONDORNEXUS.exe         ← doble clic para abrir
        ├── styles\
        │   └── styles.qss
        ├── resources\
        │   └── icon.ico
        ├── data\
        │   └── templates\          ← JSONs del normalizador (incluidos en el bundle)
        │       ├── contifico_xls.json
        │       ├── alegra_xls.json
        │       └── monica_xls.json
        └── _internal\              ← DLLs de Python y Qt (no tocar)
```

### Lo que hace el usuario nuevo

1. Descarga y extrae `CONDORNEXUS.zip`
2. Abre la carpeta `CONDORNEXUS\`
3. Doble clic en `CONDORNEXUS.exe`
4. La app crea `data/config.json` y `data/cobros.db` automáticamente en la primera ejecución
5. Hace clic en **"▶ Entrar a CONDORNEXUS"**
6. Va a **⚙ Ajustes** y configura su correo y/o token de Nexo

### Prerrequisito de compilación (solo una vez en el equipo del desarrollador)

```bash
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m pip install pyinstaller
```

---

## Estructura del proyecto

```
cobrador_Desktop/
│
├── main.py                        # Punto de entrada (doble clic / python main.py)
│
├── main/
│   └── __main__.py                # Orquesta: init_db → activar → LauncherWindow → MainWindow
│
├── core/                          # Lógica de negocio pura — SIN UI, SIN HTTP directo
│   ├── __init__.py                # Re-exporta database.py y ConfigManager
│   ├── base_provider.py           # ABC AccountingProvider + ProviderError
│   ├── providers/
│   │   ├── __init__.py            # get_provider() factory + _REGISTRY lazy
│   │   ├── contifico_provider.py  # Adapter Contifico API → AccountingProvider
│   │   ├── alegra_provider.py     # Adapter Alegra API (MOCK_MODE=True)
│   │   └── excel_provider.py      # Adapter XLS/CSV via xls_normalizer
│   ├── database.py                # Re-exporta app/database.py (lista explícita)
│   ├── config.py                  # Re-exporta app/config_manager.py
│   ├── cobros.py                  # Re-exporta cobros_service
│   ├── cotizaciones.py            # Re-exporta cotizacion_service
│   ├── email_service.py           # Re-exporta email_service
│   ├── message_service.py         # Re-exporta message_service
│   ├── scoring.py                 # Re-exporta scoring_service
│   ├── automation.py              # Re-exporta automation_service
│   └── contifico.py               # Re-exporta ContificoService / ContificoError
│
├── ui/                            # Widgets principales de la ventana (PyQt5)
│   ├── launcher.py                # Ventana de bienvenida "Entrar a CONDORNEXUS"
│   ├── main_window.py             # QMainWindow — 8 tabs + toolbar búsqueda + tray icon
│   ├── dashboard_widget.py        # Tab 🏠 Dashboard: métricas, estadísticas, actividad
│   ├── acciones_widget.py         # Tab 🎯 Acciones: scores + acciones + ProcesarAccionDialog
│   ├── mensajes_widget.py         # Tab 💬 Mensajes: historial filtrado + registrar interacción
│   ├── contifico_widget.py        # Tab 🔄 Nexo: sync facturas/contactos + métricas
│   ├── cotizaciones_widget.py     # Tab 💼 Cotizaciones: lista + filtros + acciones
│   ├── cotizacion_form_dialog.py  # Formulario crear/editar cotización (QDialog)
│   └── procesar_accion_dialog.py  # Diálogo secuencial: tono + canal + envío por importancia
│
├── app/                           # Capa interna — toda la lógica reside aquí
│   ├── database.py                # SQLite WAL (12 tablas, fuente de verdad única)
│   ├── config_manager.py          # Singleton JSON — get_provider() / set_provider()
│   ├── utils.py                   # Resolución de rutas (bundled vs source)
│   ├── services/
│   │   ├── cobros_service.py      # Parser especializado Contifico (buckets 30/60/90/120d)
│   │   ├── xls_normalizer.py      # Normalizador universal XLS/XLSX/CSV de cartera
│   │   ├── contactos_normalizer.py# Normalizador de agendas de contactos XLS/CSV
│   │   ├── export_service.py      # Exportar cartera a XLSX (openpyxl) o CSV (UTF-8 BOM)
│   │   ├── cotizacion_service.py  # Generación de mensajes y URLs WhatsApp para cotizaciones
│   │   ├── contifico_service.py   # Cliente HTTP Contifico (urllib.request, stdlib)
│   │   ├── email_service.py       # SMTP (yagmail — Gmail/Hotmail/Yahoo)
│   │   ├── message_service.py     # Generación de mensajes desde plantillas DB (cobros)
│   │   ├── pdf_extractor.py       # Extracción de datos de RIDEs ecuatorianos
│   │   ├── rides_scanner.py       # QThread: escaneo RIDES con fuzzy matching
│   │   ├── scoring_service.py     # Score 0-100 por cliente
│   │   └── automation_service.py  # Scheduler en background + motor de reglas + cola eventos Qt
│   └── ui/
│       ├── cobros_widget.py       # Tab 📊 Cartera (carga XLS, filtros, envío, exportar, historial)
│       ├── historial_dialog.py    # Diálogo: últimas 5 cargas, Restaurar / Eliminar
│       ├── pdf_drop_widget.py     # Tab 📄 PDFs drag & drop
│       ├── settings_dialog.py     # Diálogo ⚙ Ajustes en acordeón (estilos inline)
│       ├── plantillas_dialog.py   # Editor de plantillas de mensaje
│       ├── contifico_dialog.py    # Diálogo avanzado sync contactos
│       └── confirm_dialog.py      # Confirmación antes de envío masivo
│
├── data/                          # EXCLUIDO DEL REPO (.gitignore)
│   ├── config.json                # Credenciales y configuración del usuario
│   ├── cobros.db                  # Base de datos SQLite local (12 tablas)
│   └── templates/                 # Mapeos de columnas para el normalizador XLS
│       ├── contifico_xls.json     # Delega a cobros_service (parser especializado)
│       ├── alegra_xls.json        # Exportación plana de Alegra
│       └── monica_xls.json        # Exportación de Monica 11
│
├── styles/
│   └── styles.qss                 # Tema Rosé Pine Dawn para Qt
├── resources/
│   └── icon.ico                   # Icono de la aplicación
│
├── requirements.txt               # Dependencias Python (solo desktop, sin FastAPI)
├── config.example.json            # Plantilla de configuración sin secretos
├── CobradordFacturas.spec         # Spec de PyInstaller para compilar CONDORNEXUS.exe
├── BUILD.bat                      # Compilar → dist\CONDORNEXUS\
├── PREPARAR_PARA_TESTER.bat       # Limpiar datos de sesión del dist antes de distribuir
└── EJECUTAR.bat                   # Atajo para ejecutar en desarrollo
```

---

## Stack técnico

| Componente | Tecnología | Versión | Motivo de elección |
|---|---|---|---|
| UI framework | PyQt5 | ≥ 5.15 | Nativo Windows, sin Electron, sin navegador |
| Base de datos | SQLite WAL | stdlib | Local, sin servidor, concurrencia segura |
| HTTP cliente | urllib.request | stdlib | Sin dependencias externas en runtime |
| PDF parsing | pdfplumber | ≥ 0.9 | Mejor extracción de tablas en RIDEs ecuatorianos |
| XLS binario | xlrd | == 1.2.0 | Única versión con soporte `.xls` Excel 97-2003 |
| XLSX moderno | openpyxl | ≥ 3.1 | Lectura y exportación con headers estilizados |
| Fuzzy matching | rapidfuzz | ≥ 2.0 | Detección de columnas XLS y contactos con variaciones |
| Email SMTP | yagmail | ≥ 0.15 | Abstracción SMTP; soporte OAuth Gmail |
| Clipboard | pyperclip | ≥ 1.8 | Copiar mensajes WhatsApp y cotizaciones al portapapeles |
| Empaquetado | PyInstaller | ≥ 6.0 | `.exe` autocontenido sin Python instalado |
| Python runtime | CPython | 3.14.x | Ruta fija en el equipo de desarrollo |

### Por qué local-first (sin servidor, sin nube)

- **Privacidad empresarial** — los datos de cartera y cotizaciones (deudas, clientes, montos, precios) nunca salen del equipo ni pasan por servidores de terceros
- **Sin dependencia de internet** — funciona con cortes de red o VPN corporativa; solo la sincronización con Nexo requiere conexión
- **Sin suscripción** — el ejecutable compilado es autónomo; no requiere licencia en línea ni cuenta de usuario
- **Control de datos sensibles** — cumple requerimientos de auditoría y gobierno de datos de empresas medianas y grandes ecuatorianas

---

## Seguridad y privacidad

- `data/config.json` y `data/cobros.db` están en `.gitignore` y **nunca se suben al repositorio**
- Las plantillas de mensaje usan `{variable}` y `[PLACEHOLDER]` resueltos únicamente en runtime
- Los mensajes de cotización se generan en `cotizacion_service.py` y toman el nombre del remitente de `ConfigManager`, nunca de texto hardcodeado
- Ningún token, contraseña, email, RUC, CI ni número de cuenta se hardcodea en el código fuente
- Ningún nombre de empresa (propia ni de clientes) se hardcodea en el código fuente; todos los filtros de email usan el email configurado en Ajustes via `ConfigManager`
- El archivo `config.example.json` documenta la estructura esperada sin ningún valor real
- Toda comunicación con APIs externas (Contifico, Alegra) usa HTTPS y el token se pasa por header `Authorization`, nunca por URL

---

## Licencia

Uso interno. Adapta libremente para tu empresa.
