"""
message_service.py — Genera mensajes desde plantillas SQLite
"""

from app import database as db
from app.config_manager import ConfigManager


class MessageService:
    def __init__(self):
        pass

    def _vars_config(self, canal: str) -> dict:
        """Devuelve los placeholders de remitente y banco según el canal."""
        cfg = ConfigManager.get()
        rem = cfg.get_remitente()
        ban = cfg.get_banco()
        ema = cfg.get_email()
        wa  = cfg.get_whatsapp()

        nombre  = rem.get("nombre", "")
        empresa = rem.get("empresa", "")
        cargo   = rem.get("cargo", "")
        telefono = wa.get("mi_telefono", "")
        correo   = ema.get("address", "")

        b_nombre  = ban.get("nombre", "")
        b_titular = ban.get("titular", "")
        b_numero  = ban.get("numero", "")
        b_tipo    = ban.get("tipo", "Cta. Corriente")
        b_ci      = ban.get("ci", "")

        return {
            "[TU NOMBRE]":          nombre,
            "[TU EMPRESA]":         empresa,
            "[TU CARGO]":           cargo,
            "[TELÉFONO]":           telefono,
            "[TU CORREO]":          correo,
            "[TU BANCO]":           b_nombre,
            "[TITULAR DE CUENTA]":  b_titular,
            "[NÚMERO DE CUENTA]":   b_numero,
            "[CÉDULA]":             b_ci,
            # variante tipo en plantilla de email
            "Cta. Corriente: [NÚMERO DE CUENTA]": f"{b_tipo}: {b_numero}",
            "Cta. Corriente: *[NÚMERO DE CUENTA]*": f"{b_tipo}: *{b_numero}*",
        }

    def generar(self, cliente_datos: dict, tipo: str, canal: str) -> str:
        """
        Genera el mensaje final reemplazando variables en la plantilla.

        cliente_datos debe tener:
          cliente, factura_no, fecha, total, descripcion

        tipo:  'por_vencer' | 'vencida'
        canal: 'email' | 'whatsapp'

        Retorna: (asunto, cuerpo) para email, o solo cuerpo para whatsapp
        """
        plantilla = db.get_plantilla(tipo, canal)
        if not plantilla:
            return "", f"[Sin plantilla para {tipo}/{canal}]"

        desc = cliente_datos.get("descripcion") or "los productos/servicios adquiridos"
        cfg = ConfigManager.get()
        vars_reemplazo = {
            "cliente":    cliente_datos.get("cliente", ""),
            "factura_no": cliente_datos.get("factura_no", ""),
            "fecha":      cliente_datos.get("fecha", cliente_datos.get("fecha_emision", "")),
            "total":      str(cliente_datos.get("total", cliente_datos.get("monto_pendiente", ""))),
            "descripcion": desc,
            "empresa":    cfg.get_remitente().get("empresa", ""),
        }

        asunto = plantilla["asunto"] or ""
        cuerpo = plantilla["cuerpo"] or ""

        # Variables de factura {cliente}, {factura_no}, etc.
        for key, val in vars_reemplazo.items():
            asunto = asunto.replace(f"{{{key}}}", val)
            cuerpo = cuerpo.replace(f"{{{key}}}", val)

        # Variables de configuración [TU NOMBRE], [TU BANCO], etc.
        for placeholder, val in self._vars_config(canal).items():
            asunto = asunto.replace(placeholder, val)
            cuerpo = cuerpo.replace(placeholder, val)

        return asunto, cuerpo

    def generar_url_whatsapp(self, telefono: str, mensaje: str) -> str:
        """
        Construye la URL wa.me para abrir WhatsApp con el mensaje prellenado.
        El teléfono debe ser ecuatoriano: 09XXXXXXXX → 5930XXXXXXXXX
        """
        import urllib.parse

        tel = telefono.strip().replace(" ", "").replace("-", "")
        if tel.startswith("+"):
            tel = tel[1:]   # quitar + antes de procesar
        if tel.startswith("0"):
            tel = "593" + tel[1:]
        elif not tel.startswith("593"):
            tel = "593" + tel

        encoded = urllib.parse.quote(mensaje)
        return f"https://wa.me/{tel}?text={encoded}"
