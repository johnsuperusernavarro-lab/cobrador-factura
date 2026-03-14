# Cobrador de Facturas

Herramienta para gestionar cuentas por cobrar. Importa la cartera desde **Contifico**,
sincroniza los contactos de tus clientes via API, y envía recordatorios de pago por
**email** y **WhatsApp** con un clic.

Disponible como **app web** (abre en el navegador, sin instalar nada) y como
**app de escritorio** para Windows.

---

## Demo en línea

**https://cobrador-factura.onrender.com**

> En el plan gratuito de Render la app puede tardar ~30 segundos en despertar
> si no ha sido usada recientemente.

---

## Características

- **Cartera XLS** — importa el reporte `CarteraPorCobrar.xls` de Contifico y muestra facturas vencidas y por vencer con sus montos
- **Sincronización Contifico API** — trae el email y teléfono de todos tus clientes automáticamente
- **Envío de emails** — recordatorios personalizados por SMTP (Gmail, Hotmail, Yahoo)
- **WhatsApp** — genera el enlace `wa.me` con el mensaje listo para enviar
- **PDF / RIDEs** — arrastra un RIDE ecuatoriano y extrae los datos del cliente al instante
- **Plantillas editables** — mensajes personalizables por tipo (vencida / por vencer / PDF) y canal (email / WhatsApp)
- **Historial de envíos** — evita reenvíos duplicados el mismo día

---

## Versión web (recomendada)

### Uso en línea

Abre **https://cobrador-factura.onrender.com** en cualquier navegador. No requiere instalar nada.

### Uso local (sin internet)

```bash
# 1. Clona el repositorio
git clone https://github.com/johnsuperusernavarro-lab/cobrador-factura.git
cd cobrador-factura

# 2. Instala las dependencias
pip install -r requirements.txt

# 3. Ejecuta la app web
python main_web.py
```

Se abre el navegador automaticamente en `http://localhost:8000`.

O simplemente haz doble clic en **`COBRADOR_WEB.bat`**.

### Compilar como .exe (sin necesitar Python)

Doble clic en **`BUILD_WEB.bat`** — genera `dist\CobradordFacturas\CobradordFacturas.exe`.

Para entregar a un tester, ejecuta **`PREPARAR_TESTER_WEB.bat`** antes de comprimir la carpeta.

---

## Configuración

En la app ve a **Ajustes** e ingresa:

| Sección | Campos |
|---|---|
| **Correo electronico** | Proveedor, direccion, contrasena de aplicacion |
| **WhatsApp** | Tu numero de telefono |
| **Remitente** | Nombre, empresa y cargo (usados en la firma) |
| **Datos bancarios** | Banco, titular, numero de cuenta, tipo y CI/RUC |
| **Contifico API** | Token de API |

Los datos se guardan en `data/config.json`, excluido del repositorio por `.gitignore`.

### Contrasena de aplicacion para Gmail

Gmail requiere una **contrasena de aplicacion** (no tu contrasena normal):
1. Activa verificacion en 2 pasos en tu cuenta de Google
2. Ve a `myaccount.google.com` → Seguridad → Contrasenas de aplicacion
3. Genera una para "Correo" y pegala en Ajustes

### Token de Contifico

Encuéntralo en Contifico → **Configuracion → Integraciones → API**.

---

## Variables disponibles en plantillas

En el editor de plantillas puedes usar:

`{cliente}` `{factura_no}` `{fecha}` `{total}` `{descripcion}`

Los datos de firma (`[TU NOMBRE]`, `[TU BANCO]`, `[NUMERO DE CUENTA]`, etc.)
se resuelven automaticamente desde Ajustes al generar cada mensaje.

---

## Estructura del proyecto

```
cobrador/
├── main_web.py                # Servidor FastAPI (version web)
├── main.py                    # App de escritorio PyQt5 (legacy)
├── requirements.txt           # Dependencias Python
├── config.example.json        # Plantilla de configuracion (referencia)
├── render.yaml                # Configuracion de deploy en Render
├── CobradordFacturas_Web.spec # PyInstaller — version web
├── CobradordFacturas.spec     # PyInstaller — version desktop
├── COBRADOR_WEB.bat           # Lanzar version web localmente
├── BUILD_WEB.bat              # Compilar version web a .exe
├── PREPARAR_TESTER_WEB.bat    # Limpiar datos antes de entregar
├── app/
│   ├── api/                   # Endpoints FastAPI (REST)
│   │   ├── cobros.py          # Cartera XLS, mensajes, envio email
│   │   ├── config_api.py      # Leer y guardar configuracion
│   │   ├── plantillas_api.py  # CRUD de plantillas
│   │   ├── contifico_api.py   # Sincronizacion de contactos
│   │   └── pdfs_api.py        # Extraccion de RIDEs, envio email
│   ├── services/
│   │   ├── contifico_service.py   # API REST de Contifico
│   │   ├── cobros_service.py      # Parser del XLS CarteraPorCobrar
│   │   ├── email_service.py       # Envio SMTP
│   │   ├── message_service.py     # Generacion de mensajes
│   │   └── pdf_extractor.py       # Extraccion de datos de RIDEs
│   ├── config_manager.py      # Gestion de data/config.json
│   ├── database.py            # SQLite: contactos, plantillas, historial
│   └── utils.py               # Resolucion de rutas
├── web/                       # Frontend (HTML + CSS + JS)
│   ├── index.html             # Dashboard
│   ├── cartera.html           # Cartera XLS
│   ├── pdfs.html              # PDFs / RIDEs
│   ├── plantillas.html        # Editor de plantillas
│   ├── contifico.html         # Sincronizacion Contifico
│   ├── ajustes.html           # Configuracion
│   └── static/
│       ├── css/main.css       # Tema Rose Pine Dawn
│       └── js/
│           ├── main.js        # Utilidades globales (API, toast, nav)
│           └── cartera.js     # Logica de la pagina Cartera
├── resources/
│   └── icon.ico
└── data/                      # Excluido del repo (.gitignore)
    ├── config.json            # Tu configuracion privada
    └── cobros.db              # Base de datos SQLite
```

---

## Licencia

Uso interno. Adapta libremente para tu empresa.
