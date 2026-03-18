# CLAUDE.md — Guía para el asistente de IA

Este archivo le indica a Claude cómo trabajar dentro de este proyecto.

## Qué es este proyecto

**CONDORNEXUS** es una aplicación de escritorio nativa (PyQt5) para gestionar cuentas por cobrar en empresas ecuatorianas. Funciona completamente en local: sin servidor HTTP, sin navegador, sin suscripción.

Características principales:
- **Multi-software** — Adapter Pattern: Contifico API, Alegra API, o cualquier XLS/CSV via normalizador universal
- **Normalizador XLS** — auto-detecta el formato de cartera de cualquier software contable
- **Normalizador de contactos** — importa agendas de clientes desde XLS/CSV con fuzzy matching, sin sobreescribir datos manuales
- **Score de clientes** — clasificación confiable / medio / riesgoso basada en comportamiento de pagos
- **Acciones sugeridas** — lista diaria priorizada con flujo de procesamiento por importancia
- **Centro de mensajes** — historial completo de interacciones por cliente
- **Automatización** — scheduler en background siempre activo, evalúa facturas cada hora
- **Historial de cargas** — últimas 5 cargas con snapshot completo, restauración sin necesidad del XLS original
- **Exportar resultados** — XLSX con headers estilizados o CSV UTF-8 con BOM (compatible Excel Windows)
- **Notificaciones de escritorio** — balloon notifications via QSystemTrayIcon cuando el scheduler detecta nuevas facturas vencidas
- **Búsqueda global** — barra de búsqueda con Ctrl+F que opera sobre Cartera, Acciones, Mensajes y Cotizaciones
- **Módulo de Cotizaciones** — pre-facturación: crea, gestiona y envía cotizaciones; cliente híbrido con autocomplete de contactos existentes; convierte cotizaciones aceptadas en acciones de cobro

## Arquitectura del proyecto

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
│   ├── base_provider.py           # ABC AccountingProvider (contrato multi-software)
│   ├── providers/
│   │   ├── __init__.py            # get_provider() factory + _REGISTRY lazy
│   │   ├── contifico_provider.py  # Adapter Contifico → AccountingProvider
│   │   ├── alegra_provider.py     # Adapter Alegra (MOCK_MODE=True hasta tener cliente)
│   │   └── excel_provider.py      # Adapter universal XLS/CSV via normalizador
│   ├── database.py                # Re-exporta app/database.py (lista explícita)
│   ├── config.py                  # Re-exporta app/config_manager.py
│   ├── cobros.py                  # Re-exporta cobros_service
│   ├── email_service.py           # Re-exporta email_service
│   ├── message_service.py         # Re-exporta message_service
│   ├── scoring.py                 # Re-exporta scoring_service
│   ├── automation.py              # Re-exporta automation_service
│   ├── contifico.py               # Re-exporta ContificoService / ContificoError
│   └── cotizaciones.py            # Re-exporta cotizacion_service
│
├── ui/                            # Widgets principales de la ventana (PyQt5)
│   ├── launcher.py                # Ventana de bienvenida "Entrar a CONDORNEXUS"
│   ├── main_window.py             # QMainWindow — 8 pestañas + toolbar búsqueda + tray icon
│   ├── dashboard_widget.py        # Tab 🏠 Dashboard: métricas, acciones del día, estadísticas, actividad
│   ├── acciones_widget.py         # Tab 🎯 Acciones: scores + acciones + ProcesarAccionDialog
│   ├── mensajes_widget.py         # Tab 💬 Mensajes: historial filtrado + registrar interacción
│   ├── contifico_widget.py        # Tab 🔄 Nexo: sync facturas/contactos + métricas
│   ├── cotizaciones_widget.py     # Tab 💼 Cotizaciones: lista, filtros, envío, duplicar, convertir
│   ├── cotizacion_form_dialog.py  # Diálogo crear/editar: cliente híbrido + tabla ítems + validez
│   └── procesar_accion_dialog.py  # Diálogo secuencial: tono + canal + envío por importancia
│
├── app/                           # Capa interna — modificar aquí, core/ lo re-exporta
│   ├── database.py                # SQLite WAL (12 tablas, fuente de verdad)
│   ├── config_manager.py          # Singleton JSON — get_provider() / set_provider()
│   ├── utils.py                   # Resolución de rutas (bundled vs source)
│   ├── services/
│   │   ├── cobros_service.py      # Parser especializado Contifico (buckets 30/60/90/120d)
│   │   ├── xls_normalizer.py      # Normalizador universal XLS/XLSX/CSV de cartera
│   │   ├── contactos_normalizer.py# Normalizador de agendas de contactos XLS/CSV
│   │   ├── export_service.py      # Exportar cartera a XLSX (openpyxl) o CSV (UTF-8 BOM)
│   │   ├── contifico_service.py   # Cliente HTTP API Contifico (urllib.request, stdlib)
│   │   ├── email_service.py       # SMTP (Gmail/Hotmail/Yahoo via yagmail)
│   │   ├── message_service.py     # Generación de mensajes desde plantillas DB
│   │   ├── cotizacion_service.py  # Generación de mensajes de cotización (email/WhatsApp)
│   │   ├── pdf_extractor.py       # Extracción de datos de RIDEs ecuatorianos
│   │   ├── rides_scanner.py       # QThread: escaneo RIDES con fuzzy matching
│   │   ├── scoring_service.py     # Score 0-100 por cliente
│   │   └── automation_service.py  # Scheduler + motor de reglas + cola de eventos Qt
│   └── ui/
│       ├── cobros_widget.py       # Tab 📊 Cartera — usa xls_normalizer + exportar + historial
│       ├── historial_dialog.py    # Diálogo: últimas 5 cargas, Restaurar / Eliminar
│       ├── pdf_drop_widget.py     # Tab 📄 PDFs drag & drop
│       ├── settings_dialog.py     # Diálogo ⚙ Ajustes en acordeón (estilos inline)
│       ├── plantillas_dialog.py   # Editor de plantillas
│       ├── contifico_dialog.py    # Diálogo avanzado sync contactos
│       └── confirm_dialog.py      # Confirmación envío masivo
│
├── data/
│   ├── config.json                # EXCLUIDO DEL REPO — credenciales del usuario
│   ├── cobros.db                  # EXCLUIDO DEL REPO — SQLite local
│   └── templates/                 # Mapeos de columnas para el normalizador XLS
│       ├── contifico_xls.json     # Delega a cobros_service (parser especializado)
│       ├── alegra_xls.json        # Exportación plana de Alegra
│       └── monica_xls.json        # Exportación de Monica 11
│
├── styles/styles.qss              # Tema Rosé Pine Dawn para Qt
├── resources/icon.ico
├── requirements.txt               # Solo dependencias desktop (sin FastAPI/uvicorn)
├── CobradordFacturas.spec         # Spec PyInstaller → produce dist\CONDORNEXUS\CONDORNEXUS.exe
├── BUILD.bat                      # Compilar (paso 1 de distribución)
└── PREPARAR_PARA_TESTER.bat       # Limpiar datos de sesión del dist (paso 2)
```

## Flujo de ejecución

```
python main.py
    └── main/__main__.py
            ├── init_db()          ← crea/migra 12 tablas SQLite
            ├── activar()          ← scheduler siempre ON al arrancar
            ├── LauncherWindow()   ← ventana "Entrar a CONDORNEXUS"
            └── MainWindow()
                    ├── QToolBar   → búsqueda global (Ctrl+F), opera sobre tabs 1,2,3,5
                    ├── QSystemTrayIcon → notificaciones de nuevas facturas vencidas
                    ├── QTimer(5s) → poll de eventos del scheduler (sin bloquear Qt)
                    ├── Tab 0 🏠 DashboardWidget   → core/database + core/automation + estadísticas
                    ├── Tab 1 📊 CobrosWidget       → xls_normalizer + exportar + historial cargas
                    ├── Tab 2 🎯 AccionesWidget     → core/scoring + ProcesarAccionDialog
                    ├── Tab 3 💬 MensajesWidget     → core/database
                    ├── Tab 4 🔄 ContificoWidget    → core/providers/contifico_provider
                    ├── Tab 5 💼 CotizacionesWidget → core/database + core/cotizaciones
                    ├── Tab 6 📄 PdfDropWidget      → pdf_extractor + rides_scanner
                    └── Tab 7 ⚙  Ajustes           → placeholder que abre SettingsDialog
```

## Arquitectura multi-software (Adapter Pattern)

### AccountingProvider (core/base_provider.py)
Contrato abstracto que todo proveedor debe cumplir:
```python
class AccountingProvider(ABC):
    @property
    @abstractmethod
    def nombre(self) -> str: ...

    @abstractmethod
    def verificar_conexion(self) -> tuple[bool, str]: ...

    @abstractmethod
    def get_cartera(self, progreso_cb=None) -> list[dict]: ...

    @abstractmethod
    def get_contactos(self, progreso_cb=None) -> list[dict]: ...
```

### Proveedores registrados (core/providers/__init__.py)
| type en config | Clase | Estado |
|---|---|---|
| `contifico` | ContificoProvider | ✅ producción |
| `excel` | ExcelProvider | ✅ producción (usa xls_normalizer) |
| `alegra` | AlegraProvider | ⚠️ MOCK_MODE=True (cableado listo) |

Para activar Alegra real: cambiar `MOCK_MODE = False` en `alegra_provider.py`.

### Para agregar un nuevo software
1. Crear `core/providers/nuevo_provider.py` heredando `AccountingProvider`
2. Registrar en `_REGISTRY` de `core/providers/__init__.py`
3. Si tiene API: implementar `_get()` con su auth
4. Si solo tiene Excel: usar `ExcelProvider` con un nuevo JSON en `data/templates/`

## Normalizador XLS universal (app/services/xls_normalizer.py)

### Función principal
```python
resultado = normalizar_cartera("cartera.xlsx")
resultado.software      # "Contifico" | "Alegra" | "Monica" | "Genérico EC" | ...
resultado.facturas      # list[dict] en formato interno estándar
resultado.advertencias  # filas omitidas con motivo
```

### Lógica de detección
1. **¿Es Contifico?** — busca `"FAC"` en columna 2 (≥2 ocurrencias). Si sí → parser especializado `cobros_service.parse_reporte()` con buckets 30/60/90/120 días.
2. **¿Es plano?** — busca fila de encabezado (≥3 celdas de texto). Mapea columnas por fuzzy matching (rapidfuzz, score mínimo 72) contra tabla de sinónimos en español e inglés.
3. **Fechas** — acepta DD/MM/YYYY, YYYY-MM-DD, serial numérico Excel. Normaliza a DD/MM/YYYY.
4. **Falla con error descriptivo** si no hay columna de cliente o de monto.

### Sinónimos clave reconocidos
| Campo | Sinónimos |
|---|---|
| `cliente` | Cliente, Razón Social, Nombre, Customer... |
| `monto_pendiente` | Saldo, Pendiente, Balance, Por Cobrar, Outstanding... |
| `fecha_vencimiento` | Vencimiento, Fecha Venc, Due Date, F. Vencimiento... |
| `factura_no` | Factura, Número, Comprobante, Invoice, Voucher... |

## Normalizador de contactos (app/services/contactos_normalizer.py)

```python
resultado = normalizar_contactos("agenda.xlsx")
resultado.contactos     # list[dict] con nombre, email, telefono, cedula_ruc
resultado.advertencias  # filas sin email ni teléfono

importados, omitidos = importar_contactos_a_db(resultado.contactos)
# omitidos = entradas con fuente='manual' y confianza>=1.0 (no se sobreescriben)
```

Usa el mismo mecanismo de fuzzy matching que `xls_normalizer` pero con sinónimos propios para campos de contacto: nombre, email, teléfono, CI/RUC. `score_cutoff=70`.

## Exportar resultados (app/services/export_service.py)

```python
ok, msg = exportar_xlsx(facturas, "ruta/destino.xlsx")
# Headers con fondo verde #286983, texto blanco, ancho automático de columnas

ok, msg = exportar_csv(facturas, "ruta/destino.csv")
# UTF-8 con BOM (utf-8-sig) para compatibilidad con Excel en Windows
```

Exporta exactamente las filas visibles (post-filtro), no toda la cache.

## Módulo de Cotizaciones

### Servicio (app/services/cotizacion_service.py)
Genera mensajes de cotización (no usa las plantillas de cobranza; tiene su propio template).

```python
from core.cotizaciones import generar_mensaje_cotizacion, generar_url_whatsapp

asunto, cuerpo = generar_mensaje_cotizacion(cotizacion_dict, items_list, canal="email")
url = generar_url_whatsapp(telefono, mensaje)
```

### Cliente híbrido (cotizacion_form_dialog.py)
- Campo de texto libre + `QCompleter` con `MatchContains` sobre tabla `contactos`
- Al seleccionar contacto existente: rellena `email` y `teléfono` automáticamente y asigna `contacto_id`
- Si el cliente es nuevo: `contacto_id = NULL` en BD; el texto se guarda como está
- El campo `_lbl_contacto` solo aparece cuando hay un contacto vinculado (oculto por defecto)

### Tabla de ítems (cotizacion_form_dialog.py)
- Column "Total (auto)" es no editable: `setFlags(~Qt.ItemIsEditable)` + fondo `#f0ede8`
- Tab/Enter en la última celda de la última fila → agrega nueva fila con auto-focus
- Overlay hint en el viewport de la tabla cuando no hay ítems (evento `Resize` del viewport)
- Al crear nueva cotización: se agrega automáticamente una primera fila vacía

### Flujo Cotizaciones
```
Tab Cotizaciones
    ├── Lista filtrable por estado (pills con conteo en tiempo real)
    ├── Columna "Vence" calculada: "Vence en Xd" / "Venció hace Xd" / fecha DD/MM/YYYY
    ├── Empty state con CTA cuando no hay cotizaciones
    ├── Botones de acción deshabilitados hasta que haya selección
    │
    ├── Nueva / Editar → CotizacionFormDialog
    │       ├── Cliente híbrido (texto libre + autocomplete contactos)
    │       ├── Presets validez: 15d / 30d / 60d + spinbox + fecha calculada
    │       ├── Tabla ítems con total automático
    │       ├── Validación: email con @, advertencia si no hay contacto
    │       └── Cancel con advertencia si hay cambios no guardados
    │
    ├── Enviar → _EnviarCotizacionDialog
    │       ├── Selector canal (Email / WhatsApp) con preview editable
    │       ├── Email → copia al portapapeles
    │       ├── WhatsApp → abre wa.me con mensaje prellenado
    │       └── Al confirmar: actualiza estado a "enviada" + registra en mensajes_log
    │
    ├── Duplicar → crea copia con estado="pendiente"
    │
    ├── Cambiar estado → _CambiarEstadoDialog
    │       └── Botones contextuales según estado actual (no dropdown técnico)
    │
    └── Convertir a cobro
            ├── Solo disponible para estado "enviada" o "aceptada"
            └── Llama a db.crear_accion(tipo="seguimiento_cotizacion")
```

### Estados de cotización y transiciones
| Estado | Transiciones disponibles |
|---|---|
| `pendiente` | → enviada, → rechazada |
| `enviada` | → aceptada, → rechazada, → pendiente |
| `aceptada` | → enviada, → rechazada |
| `rechazada` | → pendiente |

## Tablas SQLite (app/database.py)

12 tablas — modo WAL para concurrencia segura entre hilo Qt y scheduler.

| Tabla | Descripción |
|---|---|
| `contactos` | Email y teléfono por cliente. `fuente` distingue manual/contifico_api/rides_scan/excel |
| `plantillas` | 4 plantillas por defecto (vencida/por_vencer × email/whatsapp) |
| `facturas_enviadas` | Historial de envíos — evita duplicados por día. Incluye campo `monto` |
| `facturas_cache` | Última cartera cargada (XLS o API) — fuente del scheduler |
| `score_clientes` | Score 0-100, clasificación, días prom. atraso, n vencidas |
| `mensajes_log` | Todas las interacciones: email, WhatsApp, cotizaciones, notas manuales |
| `acciones_sugeridas` | Cola de acciones del motor de reglas con prioridad y estado |
| `config_sistema` | KV store interno (también guarda n_vencidas previo para el scheduler) |
| `cargas_historial` | Metadatos de las últimas 5 cargas: software, n_facturas, monto_total, archivo |
| `cargas_snapshot` | Snapshot completo de facturas por carga (ON DELETE CASCADE) |
| `cotizaciones` | Cabecera de cotización: cliente, contacto_id (nullable), email, teléfono, estado, validez_dias, total |
| `cotizacion_items` | Ítems de cotización (ON DELETE CASCADE): descripcion, cantidad, precio_unit, total |

### Regla crítica: core/database.py usa lista explícita
`core/database.py` re-exporta funciones de `app/database.py` con una lista explícita en el import. **Toda función nueva en `app/database.py` debe agregarse manualmente a esa lista**, de lo contrario los widgets de `ui/` que usan `import core.database as db` lanzarán `AttributeError` al arrancar.

Funciones de cotizaciones actualmente exportadas:
```python
crear_cotizacion, get_cotizacion, get_cotizaciones, get_items_cotizacion,
actualizar_estado_cotizacion, actualizar_cotizacion, eliminar_cotizacion,
buscar_contactos_para_cotizacion
```

## Flujo Cartera multi-software
1. Usuario abre `.xls` / `.xlsx` / `.csv` en tab Cartera
2. `xls_normalizer.normalizar_cartera(ruta)` auto-detecta el formato
3. Retorna `DetectionResult` con `facturas` en formato interno estándar
4. Se enriquece con email/teléfono de tabla `contactos`
5. Se guarda en `facturas_cache` → scheduler lo evalúa sin recargar
6. `db.registrar_carga_historial(...)` guarda metadatos + snapshot completo
7. `db.limpiar_historial_antiguo(mantener=5)` descarta cargas más antiguas
8. `scoring_service.recalcular_todos_los_scores()` corre en thread daemon

**Mismo flujo desde Nexo API:**
1. Tab Nexo → "Sincronizar Facturas"
2. `ContificoProvider.get_cartera()` → `ContificoService.get_facturas_pendientes()`
3. `db.guardar_facturas_cache(facturas)` + upsert contactos
4. Señal `facturas_sincronizadas` → `CobrosWidget.cargar_desde_cache()` refresca automáticamente

## Flujo Historial de cargas
1. Tab Cartera → botón **"🕐 Historial"** → `HistorialDialog`
2. Muestra últimas 5 cargas: fecha, software, n° facturas, monto total, archivo
3. Botón **Restaurar**: `db.restaurar_desde_historial(carga_id)` devuelve las facturas del snapshot
4. `CobrosWidget` muestra esas facturas sin necesidad del XLS original
5. Botón **Eliminar**: `db.eliminar_carga_historial(carga_id)` borra carga + snapshot (CASCADE)

## Flujo Scheduler → notificaciones Qt (thread-safe)
```
automation_service.evaluar_facturas()  [thread daemon]
    └── detecta más vencidas que en la evaluación anterior
    └── _push_evento("nuevas_vencidas", {"n_nuevas": N})  [queue.Queue thread-safe]

MainWindow._poll_eventos_scheduler()   [QTimer cada 5s, hilo Qt]
    └── pop_eventos() → lista de eventos
    └── tray.showMessage(...)  [balloon notification de Windows]
```
**Nunca llamar a Qt directamente desde un thread daemon.** Toda señal cruzada usa la cola `queue.Queue` + polling `QTimer`.

## Flujo Acciones — Procesar por importancia
1. Tab Acciones → "▶ Procesar por importancia"
2. `ProcesarAccionDialog(acciones, scores, facturas_idx)`
3. Ordena: riesgoso (score alto) → medio → confiable
4. Por cada acción: muestra cliente, score, factura, selector canal (email/WA) y tono (amable/neutro/firme)
5. Tono → tipo de plantilla: amable=por_vencer, neutro=tipo real, firme=vencida
6. Mensaje editable antes de enviar
7. Al enviar/completar: `db.completar_accion(id)` → avanza a la siguiente
8. Al cerrar: muestra resumen (enviados / completados sin envío)

## Flujo PDF Rápido
1. Drag & drop de RIDE PDF → `pdf_extractor.extraer_datos()`
2. Extrae: razon_social, factura_no, fecha, emails, teléfono, total, descripción
3. **Auto-detección de tipo**: compara la fecha extraída con hoy → pre-selecciona "vencida" o "por_vencer"
4. Doble clic sobre un ítem → diálogo con todos los campos extraídos
5. Preview del mensaje generado con plantilla DB
6. Envío por email o apertura de WhatsApp Web

## Score de clientes

| Rango | Clasificación | Tono | Color |
|---|---|---|---|
| 0 – 35 | confiable | amable | pine (#286983) |
| 36 – 65 | medio | neutro | gold (#ea9d34) |
| 66 – 100 | riesgoso | firme | love (#b4637a) |

Fórmula: `score = 30 + (n_vencidas × 15) + (días_promedio × 0.5) + (10 si n_vencidas > 2)`

## Reglas de la capa core/

- `core/` contiene **re-exportaciones** de `app/` y los **providers**.
- Nunca duplicar lógica: cambiar en `app/services/`, se refleja automáticamente en `core/`.
- La UI llama a `core/` o a `app/ui/` directamente, **nunca a `app/services/` desde `ui/`**.
- `core/providers/` es la única excepción donde hay lógica nueva (adapters).
- **Toda función nueva en `app/database.py` debe agregarse a la lista de importación en `core/database.py`** — es una lista explícita, no un `import *`.

## Reglas de la capa ui/

- No I/O bloqueante en el hilo Qt. Usar `QThread` o `threading.Thread(daemon=True)` + `QTimer.singleShot(0, callback)`.
- Señal de estado: `status_msg = pyqtSignal(str)` → conectada al QStatusBar.
- Todos los widgets implementan `refrescar()` → llamado por `main_window.py` al cambiar de tab.
- Señales inter-widget van por `main_window.py` (nunca referencias directas entre widgets).
- Widgets grandes (Dashboard, Nexo) deben envolverse en `QScrollArea` para evitar compresión vertical.
- La clasificación de riesgo se codifica visualmente como borde izquierdo de 4px en el frame de la fila (`_CLS_COLOR = {"confiable":_PINE, "medio":_GOLD, "riesgoso":_LOVE}`), no como badge separado.
- Las cards del Dashboard son clickeables: `card.setCursor(Qt.PointingHandCursor)` + `mousePressEvent` que emite `tab_request(int)`.

## Convenciones de código

- **Python 3.14** en `C:\Users\USERS\AppData\Local\Programs\Python\Python314\`
- **PyQt5** — diálogos heredan `QDialog`, widgets heredan `QWidget`
- **SQLite WAL mode** — toda interacción pasa por funciones de `app/database.py`
- **ConfigManager.get()** — nunca leer `data/config.json` directamente
- **No credenciales hardcodeadas** — todo en `data/config.json` (excluido del repo)
- **HTTP solo stdlib** — `urllib.request` sin requests ni httpx

## Estilos Qt (styles/styles.qss)

Tema Rosé Pine Dawn. Paleta de colores:

| Variable | Hex | Uso |
|---|---|---|
| `_PINE` | `#286983` | Acciones primarias, confiable |
| `_LOVE` | `#b4637a` | Peligro, riesgoso |
| `_GOLD` | `#ea9d34` | Advertencia, medio |
| `_FOAM` | `#56949f` | Información |
| `_TEXT` | `#575279` | Texto principal |
| `_MUTED` | `#9893a5` | Texto secundario, labels |
| `_SUBTLE` | `#797593` | Etiquetas de sección |
| `_BG` | `#faf4ed` | Fondo general |
| `_SURF` | `#fffaf3` | Superficies elevadas |
| `_OVR` | `#f2e9e1` | Overlay / hover |
| `_CALC` | `#f0ede8` | Fondo columnas calculadas (ej. Total en tabla ítems) |

Clases de botón activas en `styles.qss`:

| Selector | Uso |
|---|---|
| `QPushButton[class="primary"]` | Acción principal (solo funciona en widgets que cargan el QSS global) |
| `QPushButton[class="secondary"]` | Acción secundaria |
| `QPushButton[class="whatsapp"]` | Botón WhatsApp |
| `QPushButton[class="danger"]` | Acción destructiva |
| `QPushButton[class="filter-pill"]` | Filtros de cartera |

**Importante:** Los widgets en `ui/` y `app/ui/` aplican estilos **inline** (f-strings con la paleta) porque el selector `[class="..."]` del QSS global no les aplica de forma fiable en PyQt5. `settings_dialog.py` usa `setStyleSheet()` inline en sus botones "Guardar" por esta misma razón.

## Branding CONDORNEXUS

- Nombre oficial: **CONDORNEXUS** (todo en mayúsculas)
- Tipografía: `CONDOR` en blanco weight 400 letter-spacing 5px + `NEXUS` en gold `#ea9d34` weight 800
- La integración con Contifico se llama **"Nexo"** en la UI (no "Contifico")
- El botón de cargar desde API dice **"🔗 Conectar Nexo"** (no "Contifico")
- El tab de sincronización dice **"🔄 Nexo"** en la barra lateral

## Datos sensibles

- **Nunca** hardcodear emails, contraseñas, tokens, cuentas bancarias, CI o teléfonos
- **Nunca** hardcodear el nombre de ninguna empresa (ni del desarrollador ni del cliente) en el código fuente
- `data/config.json` y `data/cobros.db` están en `.gitignore`
- Las plantillas de mensaje usan `{variable}` y `[PLACEHOLDER]` resueltos en runtime
- Los filtros de email en `pdf_extractor.py` y `rides_scanner.py` usan `ConfigManager` para obtener el email del remitente — nunca un nombre de empresa hardcodeado

## Comandos útiles

```bash
# Ejecutar en desarrollo
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" main.py

# Ejecutar via módulo
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m main

# Compilar a .exe (paso 1)
BUILD.bat
# → produce dist\CONDORNEXUS\CONDORNEXUS.exe

# Limpiar datos de sesión del dist (paso 2)
PREPARAR_PARA_TESTER.bat
# → elimina config.json y cobros.db del dist; listo para comprimir y entregar

# Validar sintaxis de un módulo editado
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -c "import ast, sys; ast.parse(open('ui/cotizaciones_widget.py').read()); print('OK')"
```

## Qué NO hacer

- No agregar lógica de negocio en `ui/` — va en `app/services/` (accesible via `core/`)
- No crear conexiones SQLite directas — usar funciones de `app/database.py`
- No bloquear el hilo Qt con red o I/O — usar `QThread` o thread daemon
- No llamar a Qt (widgets, señales, tray) desde un thread daemon — usar `queue.Queue` + `QTimer` polling
- No subir `data/config.json` ni `data/cobros.db` al repositorio
- No usar `python` o `python3` en comandos — ruta completa a Python 3.14
- No hardcodear el nombre de empresa (propia ni de clientes) en código ni en la UI
- No hardcodear nombres de empresa como filtros en el parsing de emails — usar `ConfigManager` para obtener el email del remitente
- No llamar a `app/services/` directamente desde `ui/` — pasar por `core/`
- No reimplementar parsing de XLS — usar `xls_normalizer.normalizar_cartera()`
- No reimplementar HTTP — usar el proveedor correspondiente en `core/providers/`
- No usar badge/widget separado para clasificación de riesgo — usar borde izquierdo de 4px en el frame
- No poner `setMaximumHeight()` fijo en frames con contenido dinámico — rompe el layout en pantallas pequeñas
- No referenciar directamente widgets entre sí — toda señal inter-widget pasa por `main_window.py`
- No usar el nombre "Contifico" en texto visible al usuario — usar "Nexo" en la UI
- No agregar funciones a `app/database.py` sin agregarlas también a la lista de importación en `core/database.py`
- No usar `setProperty("class", "primary")` en widgets de `app/ui/` o `ui/` — usar `setStyleSheet()` inline; el selector QSS no aplica de forma fiable en esos widgets
- No generar mensajes de cotización con `message_service.py` — usar `cotizacion_service.py` (tiene su propio template de pre-facturación, distinto al de cobranza)
