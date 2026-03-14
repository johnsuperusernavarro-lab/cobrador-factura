"""
email_service.py — Envío de emails por SMTP (Gmail, Hotmail/Outlook, Yahoo)
Usa smtplib de la librería estándar; no requiere dependencias externas.
"""

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

# (host, puerto)
_SMTP_SERVERS: dict[str, tuple[str, int]] = {
    "gmail":   ("smtp.gmail.com",        587),
    "hotmail": ("smtp-mail.outlook.com", 587),
    "outlook": ("smtp-mail.outlook.com", 587),
    "yahoo":   ("smtp.mail.yahoo.com",   587),
}


def _detectar_proveedor(address: str) -> str:
    domain = address.split("@")[-1].lower() if "@" in address else ""
    if "gmail" in domain:
        return "gmail"
    if any(x in domain for x in ("hotmail", "outlook", "live", "msn")):
        return "hotmail"
    if "yahoo" in domain:
        return "yahoo"
    return "gmail"


class EmailService:

    def __init__(self, email: str, password: str, provider: str = ""):
        self.email    = email
        self.password = password
        self.provider = provider or _detectar_proveedor(email)

    def _smtp_params(self) -> tuple[str, int]:
        return _SMTP_SERVERS.get(self.provider, _SMTP_SERVERS["gmail"])

    # ── Envío ─────────────────────────────────────────────────────────────

    def enviar(self, destinatarios: list[str], asunto: str,
               cuerpo: str, ruta_pdf: "Path | None" = None) -> tuple[bool, str]:
        """
        Envía un email con adjunto opcional.
        Retorna (éxito: bool, mensaje_error: str).
        """
        if not destinatarios:
            return False, "Sin destinatarios"
        if not self.email or not self.password:
            return False, (
                "Configura el correo en ⚙ Ajustes antes de enviar.\n"
                "(Menú: botón ⚙ en la barra inferior)"
            )

        try:
            host, port = self._smtp_params()

            msg = EmailMessage()
            msg["From"]    = self.email
            msg["To"]      = ", ".join(destinatarios)
            msg["Subject"] = asunto
            msg.set_content(cuerpo)

            if ruta_pdf and Path(ruta_pdf).exists():
                with open(ruta_pdf, "rb") as f:
                    msg.add_attachment(
                        f.read(),
                        maintype="application",
                        subtype="pdf",
                        filename=Path(ruta_pdf).name,
                    )

            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ctx)
                smtp.login(self.email, self.password)
                smtp.send_message(msg)

            return True, ""

        except Exception as exc:
            return False, str(exc)

    # ── Verificación ──────────────────────────────────────────────────────

    def verificar_credenciales(self) -> tuple[bool, str]:
        """Comprueba la conexión SMTP sin enviar nada. Retorna (ok, msg)."""
        if not self.email or not self.password:
            return False, "Correo o contraseña vacíos"
        try:
            host, port = self._smtp_params()
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ctx)
                smtp.login(self.email, self.password)
            return True, "OK"
        except Exception as exc:
            return False, str(exc)
