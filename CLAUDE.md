# CLAUDE.md — Guía para el asistente de IA

Este archivo le indica a Claude cómo trabajar dentro de este proyecto.

## Qué es este proyecto

**Cobrador de Facturas** es una aplicación de escritorio Python/PyQt5 para gestionar
cuentas por cobrar. Permite importar carteras de Contifico, sincronizar contactos desde
su API, y enviar recordatorios de pago por email y WhatsApp.

## Estructura del proyecto

```
cobrador/
├── main.py                        # Punto de entrada GUI (PyQt5)
├── enviar_facturas.py             # Script CLI legacy (batch)
├── config.example.json            # Plantilla de configuración (copiar a data/config.json)
├── CobradordFacturas.spec         # Configuración de PyInstaller para generar .exe
├── COBRADOR_GUI.bat               # Lanzador: usa Python 3.14 en AppData
├── BUILD.bat                      # Compilar a .exe (llama a PyInstaller con el .spec)
├── PREPARAR_PARA_TESTER.bat       # Elimina data/ del dist antes de entregar a un tester
├── app/
│   ├── config_manager.py          # Singleton JSON config (data/config.json)
│   ├── database.py                # SQLite ORM — tablas: contactos, plantillas, facturas_enviadas
│   ├── utils.py                   # Resolución de rutas (bundled vs. source)
│   ├── services/
│   │   ├── cobros_service.py      # Parseo del XLS CarteraPorCobrar de Contifico
│   │   ├── contifico_service.py   # Cliente HTTP de la API REST de Contifico
│   │   ├── email_service.py       # Envío SMTP (Gmail, Hotmail, Yahoo)
│   │   ├── message_service.py     # Generación de mensajes desde plantillas DB
│   │   ├── pdf_extractor.py       # Extracción de datos de RIDEs (PDF ecuatorianos)
│   │   └── rides_scanner.py       # QThread: escaneo de carpeta RIDES con fuzzy matching
│   └── ui/
│       ├── main_window.py         # QMainWindow con dos pestañas + status bar
│       ├── cobros_widget.py       # Pestaña 1: Cartera XLS + acciones
│       ├── contifico_dialog.py    # Diálogo: sincronizar contactos desde API Contifico
│       ├── pdf_drop_widget.py     # Pestaña 2: Drag & drop de PDFs
│       ├── settings_dialog.py     # Diálogo: acordeón con 4 secciones colapsables
│       ├── plantillas_dialog.py   # Diálogo: editor de plantillas de mensajes
│       └── confirm_dialog.py      # Diálogo: confirmación antes de envío masivo
├── data/                          # EXCLUIDO DEL REPO (.gitignore)
│   ├── config.json                # Credenciales y configuración del usuario
│   └── cobros.db                  # Base de datos SQLite
├── styles/
│   └── styles.qss                 # Estilos Qt (tema Rosé Pine Dawn)
└── resources/
    └── icon.ico                   # Ícono de la aplicación
```

## Convenciones del código

- **Python 3.14** instalado en `C:\Users\USERS\AppData\Local\Programs\Python\Python314\`; es el intérprete activo con todas las dependencias
- **PyQt5** para toda la UI; los diálogos heredan de `QDialog`, los widgets de `QWidget`
- **Señales Qt** para comunicación entre hilos (`pyqtSignal`) y entre widgets (`status_msg`)
- **SQLite** con WAL mode; toda interacción pasa por `app/database.py`
- **ConfigManager** es un singleton; usar `ConfigManager.get()` para acceder a config
- Las operaciones de red y escaneo de archivos van en `QThread` para no bloquear la UI
- No usar credenciales hardcodeadas — todo va en `data/config.json` (excluido del repo)

## Arquitectura de la UI (estado actual)

### `cobros_widget.py` — Pestaña principal

Layout vertical con 3 zonas:

1. **Fila superior compacta** — cards de métricas (Vencido / Por Vencer) + separador vertical + filtros pill + botón Cargar XLS, todo en una sola fila
2. **Splitter horizontal** — lista de facturas (izquierda) | panel de mensaje (derecha)
   - Panel derecho contiene: `_client_header` (QFrame oculto hasta selección) + editor QTextEdit + botones Copiar/WhatsApp/Email
   - `_client_header` muestra cliente, número de factura y monto en color según estado al hacer clic en un ítem
3. **Barra inferior** — utilidades a la izquierda (Plantillas · Escáner RIDES · Contifico), separador VLine, **⚡ Procesar Todo** a la derecha

**Filtros** usan clase `filter-pill` (no `secondary`) con propiedad `filtro=<clave>` para estilos contextuales en QSS. Los conteos dinámicos se actualizan en `_actualizar_conteos_filtros()`.

### `settings_dialog.py` — Diálogo de ajustes

Usa `CollapsibleSection` (definida en el mismo archivo) para envolver cada `QGroupBox` en un panel acordeón. Las 4 secciones son: Correo Electrónico (abierta por defecto), WhatsApp, Remitente, Datos Bancarios. Un `QScrollArea` envuelve todo el contenido. Los botones Guardar/Cancelar están fuera del scroll, siempre visibles.

### `main_window.py`

- Título de ventana: `"Cobrador de Facturas"` (sin nombre de empresa)
- Status bar: botón **⚙ Ajustes** como link plano (flat, sin borde), label de empresa vacío

### `styles.qss` — clases activas

| Clase / selector | Uso |
|---|---|
| `QPushButton[class="primary"]` | Acción principal (Cargar XLS, Email, Guardar) |
| `QPushButton[class="secondary"]` | Acción secundaria |
| `QPushButton[class="whatsapp"]` | Botón WhatsApp (verde) |
| `QPushButton[class="danger"]` | Acción destructiva |
| `QPushButton[class="filter-pill"]` | Filtros de cartera (pill con estado activo por color) |
| `QPushButton[class="filter-pill"][filtro="vencida"]:checked` | Pill rojo cuando activo |
| `QPushButton[class="filter-pill"][filtro="sin_contacto"]:checked` | Pill dorado cuando activo |
| `QFrame[class="client-header"]` | Header de cliente en panel derecho de cobros |
| `QToolButton[class="section-toggle"]` | Encabezado de sección colapsable en Ajustes |
| `QGroupBox` | Contenedor de sección con borde redondeado y título uppercase |

## Datos sensibles — reglas estrictas

- **Nunca** hardcodear emails, contraseñas, números de cuenta, C.I. o teléfonos en código
- `data/config.json` está en `.gitignore` y es donde viven todas las credenciales
- `config.example.json` es la plantilla pública sin valores reales
- Las plantillas de mensajes en `database.py` usan `[PLACEHOLDERS]` como texto por defecto
- `message_service.py` resuelve los `[PLACEHOLDERS]` en tiempo de ejecución con valores de `ConfigManager`; los datos sensibles nunca quedan escritos en la DB ni en el código
- Los datos de remitente y banco se ingresan desde el diálogo **⚙ Ajustes** y se guardan en `data/config.json`
- El nombre de empresa **no** aparece en la UI ni en el título de ventana (eliminado para distribución a testers)

## Flujos principales

### Flujo Cartera XLS
1. Usuario carga `CarteraPorCobrar.xls` → `cobros_service.parse_reporte()`
2. Se cruzan clientes con tabla `contactos` en SQLite
3. Usuario puede sincronizar contactos desde Contifico API (`contifico_dialog.py`)
4. Envío individual o masivo via `email_service.py`

### Flujo PDF Rápido
1. Drag & drop de RIDE PDF → `pdf_extractor.extraer_datos()`
2. Preview del mensaje generado con plantilla de DB
3. Envío por email o apertura de WhatsApp Web

### Sincronización Contifico
1. `ContificoService` hace GET `/persona/` con paginación automática
2. Normaliza campos (distintas versiones de la API usan nombres diferentes)
3. `db.upsert_contacto()` guarda/actualiza sin borrar contactos manuales

## Dependencias principales

Ver `requirements.txt`. Versiones clave:

```
PyQt5>=5.15.0
pdfplumber>=0.9.0
xlrd==1.2.0      # Solo esta versión soporta .xls legacy de Contifico
rapidfuzz>=2.0.0
pyperclip>=1.8.1
yagmail>=0.15.0  # Solo para el script CLI legacy
```

Todas instaladas en Python 3.14 (`C:\Users\USERS\AppData\Local\Programs\Python\Python314\`).

## Comandos útiles

```bash
# Ejecutar la GUI (doble clic en COBRADOR_GUI.bat, o desde terminal:)
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" main.py

# Ejecutar el script CLI (requiere data/config.json completo)
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" enviar_facturas.py

# Compilar a .exe (doble clic en BUILD.bat, o desde terminal:)
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m PyInstaller CobradordFacturas.spec --clean

# Limpiar dist antes de entregar a tester
PREPARAR_PARA_TESTER.bat
```

## Qué NO hacer

- No agregar lógica de negocio en los archivos de UI — va en `services/`
- No crear nuevas conexiones SQLite directas — usar las funciones de `database.py`
- No bloquear el hilo principal con operaciones de red o I/O pesado — usar `QThread`
- No subir `data/config.json` ni `data/cobros.db` al repositorio
- No usar `python` o `python3` en comandos — usar la ruta completa a Python 3.14
- No hardcodear el nombre de empresa en código fuente ni en la UI
