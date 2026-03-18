"""
ui/main_window.py — Ventana principal del Cobrador de Facturas (Desktop v3.0)

6 pestañas nativas PyQt5 — sin servidor HTTP, sin navegador.
Toda la lógica viene de core/ (llamadas directas a Python).
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar,
    QLabel, QPushButton, QWidget,
    QToolBar, QLineEdit, QSystemTrayIcon, QMenu, QAction, QShortcut, QApplication,
)

from app.utils import get_bundle_dir

# Pestañas del núcleo existente (probadas y funcionando)
from app.ui.cobros_widget    import CobrosWidget
from app.ui.pdf_drop_widget  import PdfDropWidget
from app.ui.settings_dialog  import SettingsDialog

# Pestañas nuevas (llaman a core/ directamente)
from ui.dashboard_widget      import DashboardWidget
from ui.acciones_widget       import AccionesWidget
from ui.mensajes_widget       import MensajesWidget
from ui.contifico_widget      import ContificoWidget
from ui.cotizaciones_widget   import CotizacionesWidget

ICON_PATH = get_bundle_dir() / "resources" / "icon.ico"
QSS_PATH  = get_bundle_dir() / "styles"    / "styles.qss"


class MainWindow(QMainWindow):
    """
    Ventana principal con todas las funcionalidades del Cobrador.
    Se muestra después de hacer clic en "Iniciar" en el Launcher.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CONDORNEXUS")
        self.setMinimumSize(960, 620)

        # Ajustar tamaño inicial al 90% de la pantalla disponible, con tope razonable
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().availableGeometry()
        w = min(1200, int(screen.width()  * 0.92))
        h = min(720,  int(screen.height() * 0.90))
        self.resize(w, h)

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._build_tabs()
        self._build_status_bar()
        self._build_search_toolbar()
        self._setup_tray()
        self._cargar_estilos()

        # Polling de eventos del scheduler (cada 5 s, no bloquea el hilo Qt)
        self._timer_eventos = QTimer(self)
        self._timer_eventos.timeout.connect(self._poll_eventos_scheduler)
        self._timer_eventos.start(5000)

        # Ctrl+F → foco al buscador global
        sc = QShortcut(QKeySequence("Ctrl+F"), self)
        sc.activated.connect(self._search_global.setFocus)

    # ── Construcción ────────────────────────────────────────────────────────

    def _build_tabs(self):
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.West)   # pestañas a la izquierda (look desktop)

        # ── Tab 1: Dashboard ─────────────────────────────────────────────
        self._dashboard = DashboardWidget()
        self._dashboard.status_msg.connect(self._set_status)
        self._dashboard.tab_request.connect(self._tabs.setCurrentIndex)
        self._tabs.addTab(self._dashboard, "🏠  Dashboard")

        # ── Tab 2: Cartera XLS ───────────────────────────────────────────
        self._cobros = CobrosWidget()
        self._cobros.status_msg.connect(self._set_status)
        self._tabs.addTab(self._cobros, "📊  Cartera")

        # ── Tab 3: Acciones sugeridas ────────────────────────────────────
        self._acciones = AccionesWidget()
        self._acciones.status_msg.connect(self._set_status)
        self._tabs.addTab(self._acciones, "🎯  Acciones")

        # ── Tab 4: Centro de mensajes ────────────────────────────────────
        self._mensajes = MensajesWidget()
        self._mensajes.status_msg.connect(self._set_status)
        self._tabs.addTab(self._mensajes, "💬  Mensajes")

        # ── Tab 5: Contifico ─────────────────────────────────────────────
        self._contifico = ContificoWidget()
        self._contifico.status_msg.connect(self._set_status)
        self._contifico.facturas_sincronizadas.connect(self._cobros.cargar_desde_cache)
        self._tabs.addTab(self._contifico, "🔄  Nexo")

        # ── Tab 6: Cotizaciones ──────────────────────────────────────────
        self._cotizaciones = CotizacionesWidget()
        self._cotizaciones.status_msg.connect(self._set_status)
        self._tabs.addTab(self._cotizaciones, "💼  Cotizaciones")

        # ── Tab 7: PDF / RIDEs ───────────────────────────────────────────
        self._pdf_drop = PdfDropWidget()
        self._pdf_drop.status_msg.connect(self._set_status)
        self._tabs.addTab(self._pdf_drop, "📄  PDFs")

        # ── Tab 8: Ajustes (M14 — acceso visible en el panel lateral) ────
        self._tabs.addTab(QWidget(), "⚙  Ajustes")   # placeholder que abre el diálogo

        # Refrescar tabs dependientes cuando se activan
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self._tabs)

    def _build_status_bar(self):
        self._status = QStatusBar()
        self._status.setSizeGripEnabled(True)
        self.setStatusBar(self._status)
        self._set_status("Listo")

        # Marca pequeña en la status bar — siempre visible
        lbl_marca = QLabel(
            '<span style="color:#286983; font-weight:600;">CONDOR</span>'
            '<span style="color:#ea9d34; font-weight:800;">NEXUS</span>'
        )
        lbl_marca.setTextFormat(2)  # Qt.RichText
        lbl_marca.setStyleSheet("font-size:11px; padding: 0 6px 0 12px;")
        self._status.addPermanentWidget(lbl_marca)

        btn_ajustes = QPushButton("⚙  Ajustes")
        btn_ajustes.setFlat(True)
        btn_ajustes.setStyleSheet(
            "QPushButton { color: #9893a5; font-size: 11px; padding: 0 10px; "
            "border: none; background: transparent; }"
            "QPushButton:hover { color: #286983; }"
        )
        btn_ajustes.setToolTip("Configurar correo, WhatsApp y datos de la empresa")
        btn_ajustes.clicked.connect(self._abrir_ajustes)
        self._status.addPermanentWidget(btn_ajustes)

    def _build_search_toolbar(self):
        toolbar = self.addToolBar("Búsqueda global")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet(
            "QToolBar { border-bottom: 1px solid #d6cec5; background: #fffaf3; "
            "padding: 3px 10px; spacing: 6px; }"
        )

        lbl = QLabel("🔍")
        lbl.setStyleSheet("font-size:14px; padding-right:2px;")
        toolbar.addWidget(lbl)

        self._search_global = QLineEdit()
        self._search_global.setPlaceholderText("Buscar en toda la app…  (Ctrl+F)")
        self._search_global.setClearButtonEnabled(True)
        self._search_global.setFixedWidth(300)
        self._search_global.setStyleSheet(
            "QLineEdit { border:1px solid #d6cec5; border-radius:6px; "
            "padding:4px 8px; font-size:12px; background:#faf4ed; }"
            "QLineEdit:focus { border-color:#286983; }"
        )
        self._search_global.textChanged.connect(self._on_busqueda_global)
        toolbar.addWidget(self._search_global)

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        if ICON_PATH.exists():
            self._tray.setIcon(QIcon(str(ICON_PATH)))
        self._tray.setToolTip("CONDORNEXUS")

        tray_menu = QMenu()
        act_show = QAction("Abrir CONDORNEXUS", self)
        act_show.triggered.connect(self._mostrar_ventana)
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(QApplication.quit)
        tray_menu.addAction(act_show)
        tray_menu.addSeparator()
        tray_menu.addAction(act_quit)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _mostrar_ventana(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._mostrar_ventana()

    def _poll_eventos_scheduler(self):
        try:
            from app.services.automation_service import pop_eventos
            for evento in pop_eventos():
                if evento["tipo"] == "nuevas_vencidas":
                    n = evento["datos"]["n_nuevas"]
                    self._tray.showMessage(
                        "CONDORNEXUS — Nuevas facturas vencidas",
                        f"{n} factura(s) nueva(s) vencida(s) detectadas por el scheduler.",
                        QSystemTrayIcon.Warning,
                        7000,
                    )
        except Exception:
            pass

    def _on_busqueda_global(self, texto: str):
        texto = texto.strip()
        idx_actual = self._tabs.currentIndex()

        # Tabs con capacidad de búsqueda: Cartera(1), Acciones(2), Mensajes(3), Cotizaciones(5)
        TABS_BUSCABLES = [1, 2, 3, 5]

        if not texto:
            for i in TABS_BUSCABLES:
                w = self._tabs.widget(i)
                if hasattr(w, "buscar"):
                    w.buscar("")
            return

        # Intentar primero en el tab activo
        w_actual = self._tabs.widget(idx_actual)
        if hasattr(w_actual, "buscar") and w_actual.buscar(texto):
            return

        # Si no hay resultados, buscar en los otros tabs
        for i in TABS_BUSCABLES:
            if i == idx_actual:
                continue
            w = self._tabs.widget(i)
            if hasattr(w, "buscar") and w.buscar(texto):
                self._tabs.setCurrentIndex(i)
                return

    def _cargar_estilos(self):
        if QSS_PATH.exists():
            self.setStyleSheet(QSS_PATH.read_text(encoding="utf-8"))

    # ── Eventos ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status.showMessage(msg, 8000)

    def _abrir_ajustes(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def _on_tab_changed(self, index: int):
        """Refresca el contenido del tab activo si implementa refrescar()."""
        # Tab de Ajustes (M14): interceptar y abrir diálogo, volver al tab anterior
        if self._tabs.tabText(index).strip().startswith("⚙"):
            self._tabs.setCurrentIndex(self._tabs.currentIndex()
                                       if self._tabs.currentIndex() != index else 0)
            self._abrir_ajustes()
            return

        widget = self._tabs.widget(index)
        if hasattr(widget, "refrescar"):
            self._set_status("Cargando…")
            widget.refrescar()
            self._set_status("Listo")
