# Cobrador de Facturas

Herramienta de escritorio para gestionar cuentas por cobrar. Importa la cartera desde
**Contifico**, sincroniza los contactos de tus clientes via la API, y envía recordatorios
de pago por **email** y **WhatsApp** con un clic.

---

## Características

- **Importar cartera XLS** — carga el reporte `CarteraPorCobrar.xls` de Contifico y muestra las facturas por vencer y vencidas con sus montos
- **Sincronización Contifico API** — importa automáticamente el email y teléfono de todos tus clientes desde la API de Contifico
- **Envío de emails** — envía recordatorios de cobro personalizados por SMTP (Gmail, Hotmail, Yahoo)
- **WhatsApp** — genera el enlace `wa.me` con el mensaje listo para enviar desde WhatsApp Web
- **PDF Rápido** — arrastra un RIDE ecuatoriano (PDF) y extrae los datos del cliente al instante
- **Plantillas editables** — 4 plantillas personalizables: por vencer / vencida × email / WhatsApp
- **Escáner RIDES** — escanea tu carpeta de RIDEs y cruza los clientes con fuzzy matching para completar contactos faltantes
- **Historial de envíos** — evita reenvíos duplicados el mismo día

---

## Instalación

### Requisitos

- Python 3.10 o superior
- Windows (la ruta de RIDES usa `Documents/RIDES` por defecto)

### Pasos

```bash
# 1. Clona el repositorio
git clone <url-del-repo>
cd cobrador

# 2. Instala las dependencias
pip install -r requirements.txt

# 3. Ejecuta la aplicación
python main.py
```

En el primer arranque la aplicación abre sin configuración. Ve a **⚙ Ajustes** para ingresar tus datos (ver sección **Configuración**).

---

## Configuración

Toda la configuración se gestiona desde el diálogo **⚙ Ajustes** dentro de la aplicación. No es necesario editar archivos manualmente.

Los datos se guardan en `data/config.json`, que está excluido del repositorio por `.gitignore` y nunca se sube a GitHub.

### Secciones del diálogo Ajustes

El diálogo usa paneles colapsables — haz clic en cada sección para expandirla:

| Sección | Campos |
|---------|--------|
| **Correo Electrónico** | Proveedor (Gmail / Hotmail / Yahoo), dirección, contraseña de aplicación |
| **WhatsApp** | Tu número de teléfono (aparece en la firma) |
| **Remitente** | Nombre, empresa y cargo (usados en la firma de los mensajes) |
| **Datos Bancarios** | Banco, titular, número de cuenta, tipo y C.I./RUC (incluidos en los mensajes de cobro) |

> Los datos bancarios y de remitente se insertan automáticamente en cada mensaje al momento de generarlo — no quedan guardados en las plantillas ni en la base de datos.

### Contraseña de aplicación para Gmail

Gmail requiere una **contraseña de aplicación** (no tu contraseña normal):
1. Activa la verificación en 2 pasos en tu cuenta de Google
2. Ve a `myaccount.google.com` → Seguridad → Contraseñas de aplicación
3. Genera una para "Correo" y pégala en el campo correspondiente

### Token de la API de Contifico

Encuéntralo en Contifico → **Configuración → Integraciones → API**. Se ingresa en el diálogo **🔗 Contifico** dentro de la aplicación.

---

## Uso

### Flujo principal — Cartera XLS

1. Abre la aplicación con `python main.py` o haciendo doble clic en `COBRADOR_GUI.bat`
2. Haz clic en **🔗 Contifico** para sincronizar los contactos de tus clientes desde la API
3. Haz clic en **📂 Cargar XLS** y selecciona tu reporte `CarteraPorCobrar.xls`
4. La lista mostrará las facturas con íconos de conectividad:
   - `●` — tiene email y teléfono
   - `◑` — tiene solo uno
   - `○` — sin contacto
5. Usa los filtros pill para navegar: **Todos · Vencidas (n) · Por Vencer (n) · Sin Contacto (n)**
6. Selecciona una factura — el panel derecho muestra el cliente, monto y mensaje generado
7. Usa **📧 Email**, **💬 WhatsApp** o **📋 Copiar** para enviar
8. Para enviar todos los emails pendientes en lote: **⚡ Procesar Todo**

### Flujo rápido — PDF

1. Ve a la pestaña **PDF Rápido**
2. Arrastra un RIDE (PDF de factura electrónica ecuatoriana) al área de drop
3. El sistema extrae automáticamente los datos del cliente
4. Edita el mensaje si es necesario y envía

### Editar plantillas de mensajes

Haz clic en **📝 Plantillas** para personalizar los 4 mensajes:
- Por vencer / Email
- Por vencer / WhatsApp
- Vencida / Email
- Vencida / WhatsApp

Variables de factura disponibles en plantillas: `{cliente}`, `{factura_no}`, `{fecha}`, `{total}`, `{descripcion}`, `{empresa}`

Los datos de firma y banco (`[TU NOMBRE]`, `[TU BANCO]`, `[NÚMERO DE CUENTA]`, etc.) se resuelven automáticamente desde **⚙ Ajustes** — no es necesario escribirlos en cada plantilla.

---

## Estructura del proyecto

```
cobrador/
├── main.py                    # Punto de entrada GUI
├── enviar_facturas.py         # Script CLI (uso por lotes, legacy)
├── requirements.txt           # Dependencias Python
├── config.example.json        # Plantilla de configuración (referencia)
├── CobradordFacturas.spec     # Configuración de PyInstaller
├── COBRADOR_GUI.bat           # Lanzador de la aplicación (doble clic)
├── BUILD.bat                  # Compilar a .exe con PyInstaller
├── PREPARAR_PARA_TESTER.bat   # Limpiar datos antes de entregar a un tester
├── app/
│   ├── config_manager.py      # Gestión de data/config.json
│   ├── database.py            # SQLite: contactos, plantillas, historial
│   ├── utils.py               # Resolución de rutas (bundled vs. source)
│   ├── services/
│   │   ├── contifico_service.py   # API REST de Contifico (/persona/)
│   │   ├── cobros_service.py      # Parser del XLS CarteraPorCobrar
│   │   ├── email_service.py       # Envío SMTP
│   │   ├── message_service.py     # Generación de mensajes (resuelve placeholders)
│   │   ├── pdf_extractor.py       # Extracción de datos de RIDEs
│   │   └── rides_scanner.py       # Escáner de carpeta RIDES con fuzzy matching
│   └── ui/
│       ├── main_window.py         # QMainWindow con dos pestañas
│       ├── cobros_widget.py       # Pestaña 1: Cartera XLS + acciones
│       ├── pdf_drop_widget.py     # Pestaña 2: Drag & drop de PDFs
│       ├── settings_dialog.py     # Ajustes (accordion): correo, WhatsApp, remitente, banco
│       ├── contifico_dialog.py    # Diálogo: sincronizar contactos desde API Contifico
│       ├── plantillas_dialog.py   # Editor de plantillas de mensajes
│       └── confirm_dialog.py      # Confirmación antes de envío masivo
├── styles/
│   └── styles.qss             # Tema visual (Rosé Pine Dawn)
├── resources/
│   └── icon.ico               # Ícono de la aplicación
└── data/                      # Excluido del repo (.gitignore)
    ├── config.json            # Tu configuración privada
    └── cobros.db              # Base de datos local (contactos, plantillas, historial)
```

---

## Empaquetado como ejecutable

Para generar un `.exe` standalone:

```bash
# Opción 1 — doble clic
BUILD.bat

# Opción 2 — desde terminal
"C:\Users\USERS\AppData\Local\Programs\Python\Python314\python.exe" -m PyInstaller CobradordFacturas.spec --clean
```

El ejecutable queda en `dist\CobradordFacturas\CobradordFacturas.exe`.

### Antes de entregar el ejecutable a un tester

Ejecutar `PREPARAR_PARA_TESTER.bat` — elimina `config.json` y `cobros.db` de la carpeta `dist/` para que el tester arranque con la aplicación limpia.

---

## Notas sobre el script CLI

`enviar_facturas.py` es la versión original por línea de comandos. Procesa PDFs
de las carpetas `por_vencer/` y `vencidas/` y envía los emails automáticamente.
Requiere que `data/config.json` tenga completas las secciones `email`, `remitente` y `banco`.

---

## Licencia

Uso interno. Adapta libremente para tu empresa.
