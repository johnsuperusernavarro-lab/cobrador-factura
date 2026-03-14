"""
rides_scanner.py — QThread que escanea la carpeta RIDES/ en background

Señales emitidas:
  progreso(actual: int, total: int, nombre_archivo: str)
  sugerencia(nombre_contifico: str, email: str, telefono: str, confianza: float)
  terminado(n_actualizados: int)
  error(mensaje: str)
"""

import re
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

RIDES_PATH = Path.home() / "Documents" / "RIDES"

# Umbral de confianza para fuzzy match (0-100)
UMBRAL_AUTO    = 80   # Guardar automáticamente
UMBRAL_REVISAR = 60   # Marcar para revisión manual


def _limpiar(texto: str) -> str:
    lineas = [" ".join(l.split()) for l in texto.splitlines()]
    return "\n".join(lineas)


def _extraer_email_tel(ruta_pdf: Path) -> tuple[str, str]:
    """Extrae email y teléfono del cliente del RIDE."""
    try:
        import pdfplumber
    except ImportError:
        return "", ""

    texto_bruto = ""
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for pagina in pdf.pages:
                texto_bruto += (pagina.extract_text() or "") + "\n"
    except Exception:
        return "", ""

    texto  = _limpiar(texto_bruto)
    lineas = texto.splitlines()

    # ── Teléfono del cliente (cerca de "Dirección:") ──
    telefono = ""
    m = re.search(r"Direcci.n:.*?Tel.fono:\s*([\d\s]+)", texto)
    if m:
        telefono = re.sub(r"\s+", "", m.group(1))[:15]

    # ── Email del cliente (después de "Fecha Emisión:") ──
    email = ""
    idx_dir = next((i for i, l in enumerate(lineas)
                    if re.search(r"Direcci.n:", l)), None)
    if idx_dir is not None:
        email_texto = ""
        recolectando = False
        for linea in lineas[idx_dir:]:
            if "Correo:" in linea:
                recolectando = True
                email_texto += linea.split("Correo:", 1)[1]
                continue
            if recolectando:
                s = linea.strip()
                if re.search(r"C.digo|Informaci.n|Formas\s+de\s+pago|Subtotal", s):
                    break
                if len(s) > 60:
                    break
                email_texto += s
        email_sin_espacios = "".join(email_texto.split())
        encontrados = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w{2,6}", email_sin_espacios)
        validos = [e for e in encontrados
                   if "interbalanzas" not in e.lower()]
        if validos:
            email = validos[0]

    return email, telefono


class RidesScanner(QThread):
    progreso  = pyqtSignal(int, int, str)       # actual, total, nombre_archivo
    sugerencia = pyqtSignal(str, str, str, float)  # nombre_contifico, email, tel, confianza
    terminado = pyqtSignal(int)                 # n_actualizados
    error     = pyqtSignal(str)

    def __init__(self, clientes_contifico: list[str], parent=None):
        super().__init__(parent)
        self.clientes_contifico = clientes_contifico
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        if not RIDES_PATH.exists():
            self.error.emit(f"Carpeta RIDES no encontrada: {RIDES_PATH}")
            self.terminado.emit(0)
            return

        try:
            from rapidfuzz import process as rfprocess, fuzz
        except ImportError:
            self.error.emit("Instala rapidfuzz: pip install rapidfuzz")
            self.terminado.emit(0)
            return

        pdfs = sorted(RIDES_PATH.glob("*.pdf"))
        total = len(pdfs)

        if total == 0:
            self.terminado.emit(0)
            return

        n_actualizados = 0

        for idx, ruta_pdf in enumerate(pdfs, 1):
            if self._stop:
                break

            nombre_archivo = ruta_pdf.stem  # Sin extensión
            self.progreso.emit(idx, total, ruta_pdf.name)

            # Fuzzy match contra lista de clientes de Contifico
            if self.clientes_contifico:
                resultado = rfprocess.extractOne(
                    nombre_archivo.upper(),
                    [c.upper() for c in self.clientes_contifico],
                    scorer=fuzz.token_sort_ratio,
                )
                if resultado:
                    _, score, idx_cliente = resultado
                    nombre_cliente = self.clientes_contifico[idx_cliente]

                    if score >= UMBRAL_REVISAR:
                        email, telefono = _extraer_email_tel(ruta_pdf)
                        self.sugerencia.emit(
                            nombre_cliente,
                            email,
                            telefono,
                            float(score)
                        )
                        n_actualizados += 1

        self.terminado.emit(n_actualizados)
