"""Il visore di immagini e documenti, con zoom e spostamento.

Sta sopra la schermata che lo contiene (come `VeloImmagine`) e mostra un'immagine
o un documento (PDF, e Word/Excel/LibreOffice convertiti in PDF).  Comandi: zoom,
adatta, pagina avanti e indietro; con il mouse la rotella fa zoom e il
trascinamento sposta.

Due modi, uguali sullo schermo dell'app e su quello esterno: «Adatta» (tutta
l'immagine in vista) e «Riempi» (l'immagine copre tutto lo schermo, tagliando i
bordi).  «Ruota» gira di 90 gradi, per i documenti scansionati per traverso.

Se c'e' lo schermo esterno, li' si vede la stessa cosa: stesso punto e stesso
zoom *rispetto al modo scelto*, ma calcolato sul **suo** schermo (le proporzioni
dei due monitor sono diverse).  Senza schermo esterno non si replica niente.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRectF, Qt, QTimer
from PyQt6.QtGui import (QColor, QImageReader, QKeySequence, QPainter, QPixmap,
                         QShortcut, QTransform)
from PyQt6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Utility import FileEsterni, RenderPdf
from Utility.Extensions import on_main

SCALA_PAGINA = 2.5
FATTORE_ZOOM = 1.25


class VisoreDocumento(QWidget):
    """Immagine o documento a tutta schermata, con zoom e replica sullo schermo esterno."""

    def __init__(self, padre: QWidget) -> None:
        super().__init__(padre)
        self.setObjectName("visoreDocumento")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#visoreDocumento { background-color: #111; }"
            " QPushButton { background-color: #64398b; color: white; border: none;"
            " border-radius: 4px; padding: 6px 12px; min-width: 22px; }"
            " QPushButton:hover { background-color: #a77fd4; }"
            " QPushButton:disabled { background-color: #333; color: #777; }"
            " QLabel { color: #ddd; }")
        self.setVisible(False)
        self._documento: RenderPdf.Documento | None = None
        self._pagina = 0
        self._adatta = True
        self._replicato = False
        self._riempi = False
        self._rotazione = 0
        self._originale = QPixmap()
        self._richiesta = 0

        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(0)

        barra = QWidget(self)
        riga = QHBoxLayout(barra)
        riga.setContentsMargins(12, 8, 12, 8)
        riga.setSpacing(6)
        self._titolo = QLabel("", barra)
        self._titolo.setStyleSheet("font-weight: 600;")
        riga.addWidget(self._titolo, 1)
        self._indietro = self._tasto(riga, "◀", "Pagina precedente", lambda: self._vai(-1))
        self._conta = QLabel("", barra)
        riga.addWidget(self._conta)
        self._avanti = self._tasto(riga, "▶", "Pagina successiva", lambda: self._vai(1))
        riga.addSpacing(12)
        self._tasto(riga, "−", "Riduci", lambda: self._zoom(1 / FATTORE_ZOOM))
        self._percentuale = QLabel("", barra)
        self._percentuale.setMinimumWidth(48)
        self._percentuale.setAlignment(Qt.AlignmentFlag.AlignCenter)
        riga.addWidget(self._percentuale)
        self._tasto(riga, "+", "Ingrandisci", lambda: self._zoom(FATTORE_ZOOM))
        self._tasto_modo = self._tasto(riga, "Riempi", "", self._commuta_modo)
        self._tasto(riga, "⟳", "Ruota di 90 gradi", self._ruota)
        self._aggiorna_modo()
        riga.addSpacing(12)
        self._tasto(riga, "✕", "Chiudi (Esc)", self.chiudi)
        colonna.addWidget(barra)

        self._scena = QGraphicsScene(self)
        self._scena.setBackgroundBrush(QColor("#111"))
        self._elemento = QGraphicsPixmapItem()
        self._elemento.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scena.addItem(self._elemento)
        self._vista = QGraphicsView(self._scena, self)
        self._vista.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._vista.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._vista.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._vista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._vista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._vista.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform
                                   | QPainter.RenderHint.Antialiasing)
        self._vista.viewport().installEventFilter(self)
        colonna.addWidget(self._vista, 1)

        self._messaggio = QLabel("", self._vista)
        self._messaggio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._messaggio.setWordWrap(True)
        self._messaggio.setStyleSheet("font-size: 15px; padding: 24px;")
        self._messaggio.hide()

        # Subito (veloce, senza lisciatura) e poi, a mano ferma, una volta in bella.
        self._timer_replica = QTimer(self)
        self._timer_replica.setSingleShot(True)
        self._timer_replica.setInterval(0)
        self._timer_replica.timeout.connect(lambda: self._replica(veloce=True))
        self._timer_bella = QTimer(self)
        self._timer_bella.setSingleShot(True)
        self._timer_bella.setInterval(150)
        self._timer_bella.timeout.connect(lambda: self._replica(veloce=False))
        for barra_scorrimento in (self._vista.horizontalScrollBar(),
                                  self._vista.verticalScrollBar()):
            barra_scorrimento.valueChanged.connect(self._ridisegna_fuori)

        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        # Esc chiude il visore anche se il fuoco e' altrove nella finestra
        esc.setContext(Qt.ShortcutContext.WindowShortcut)
        esc.activated.connect(self.chiudi)
        padre.installEventFilter(self)

    @staticmethod
    def _tasto(riga, testo: str, aiuto: str, azione) -> QPushButton:
        tasto = QPushButton(testo)
        tasto.setToolTip(aiuto)
        tasto.setCursor(Qt.CursorShape.PointingHandCursor)
        tasto.clicked.connect(lambda _=False: azione())
        riga.addWidget(tasto)
        return tasto

    # ------------------------------------------------------------------
    # APRIRE E CHIUDERE
    # ------------------------------------------------------------------

    def apri(self, percorso: str, titolo: str = "") -> None:
        """Apre un'immagine o un documento."""
        self._chiudi_documento()
        self._richiesta += 1
        richiesta = self._richiesta
        self._riparti()
        self._titolo.setText(titolo)
        self._elemento.setPixmap(QPixmap())
        self._mostra()
        tipo = FileEsterni.tipo_di(percorso)
        if tipo == "immagine":
            self._apri_immagine(percorso)
        else:
            self._apri_documento(percorso, richiesta)

    def apri_pixmap(self, pixmap: QPixmap, titolo: str = "") -> None:
        """Apre un'immagine gia' in memoria (le figure di capitoli, notizie e contenuti)."""
        if pixmap is None or pixmap.isNull():
            return
        self._chiudi_documento()
        self._richiesta += 1
        self._riparti()
        self._titolo.setText(titolo)
        self._mostra()
        self._imposta_pagina(pixmap, 0, 1)

    def _apri_immagine(self, percorso: str) -> None:
        lettore = QImageReader(percorso)
        lettore.setAutoTransform(True)
        immagine = lettore.read()
        if immagine.isNull():
            self._dice(f"Non riesco a leggere questa immagine.\n{lettore.errorString()}")
            return
        self._imposta_pagina(QPixmap.fromImage(immagine), 0, 1)

    def _apri_documento(self, percorso: str, richiesta: int) -> None:
        from Utility.Extensions.Ext_DispatchQueue import background

        self._dice("Preparo il documento...")
        esito: dict = {}

        def lavoro() -> None:
            try:
                esito["pdf"] = FileEsterni.in_pdf(percorso)
            except Exception as errore:  # noqa: BLE001
                esito["errore"] = str(errore)

        def pronto() -> None:
            if richiesta != self._richiesta or not self.isVisible():
                return
            if "errore" in esito:
                self._dice(esito["errore"])
                return
            try:
                self._documento = RenderPdf.Documento(esito["pdf"])
            except Exception as errore:  # noqa: BLE001
                self._dice(str(errore))
                return
            if self._documento.pagine == 0:
                self._dice("Il documento e' vuoto.")
                return
            self._messaggio.hide()
            self._pagina = 0
            self._disegna_pagina()

        background(lavoro, completion=pronto)

    def chiudi(self) -> None:
        """Chiude il visore, e lo schermo esterno torna com'era."""
        self._richiesta += 1
        self.setVisible(False)
        self._chiudi_documento()
        self._elemento.setPixmap(QPixmap())
        if self._replicato:
            self._replicato = False
            try:
                from SubViews.SchermoEsterno import istanza
                esterno = istanza()
                if esterno is not None:
                    esterno.toglie_figura()
            except ImportError:
                pass

    def _chiudi_documento(self) -> None:
        if self._documento is not None:
            self._documento.chiudi()
            self._documento = None

    def _mostra(self) -> None:
        padre = self.parentWidget()
        if padre is not None:
            self.setGeometry(padre.rect())
        self._messaggio.hide()
        self._aggiorna_comandi()
        self.raise_()
        self.setVisible(True)
        self.setFocus()

    def _dice(self, testo: str) -> None:
        self._messaggio.setText(testo)
        self._messaggio.setGeometry(self._vista.rect())
        self._messaggio.show()
        self._messaggio.raise_()

    # ------------------------------------------------------------------
    # PAGINE E ZOOM
    # ------------------------------------------------------------------

    def _disegna_pagina(self) -> None:
        immagine = self._documento.pagina(self._pagina, SCALA_PAGINA)
        if immagine.isNull():
            self._dice("Non riesco a disegnare questa pagina.")
            return
        self._imposta_pagina(QPixmap.fromImage(immagine), self._pagina, self._documento.pagine)

    def _riparti(self) -> None:
        """Ogni apertura comincia in «Adatta» e senza rotazione."""
        self._riempi = False
        self._rotazione = 0
        self._aggiorna_modo()

    def _imposta_pagina(self, pixmap: QPixmap, pagina: int, totale: int) -> None:
        self._originale = pixmap
        self._metti_il_pixmap()
        self._conta.setText(f"{pagina + 1} / {totale}" if totale > 1 else "")
        self._aggiorna_comandi(totale)
        self._adatta_alla_vista()

    def _metti_il_pixmap(self) -> None:
        """Il pixmap originale, girato della rotazione scelta."""
        pixmap = self._originale
        if self._rotazione:
            pixmap = pixmap.transformed(QTransform().rotate(self._rotazione),
                                        Qt.TransformationMode.SmoothTransformation)
        self._elemento.setPixmap(pixmap)
        self._scena.setSceneRect(QRectF(pixmap.rect()))

    def _ruota(self) -> None:
        if self._originale.isNull():
            return
        self._rotazione = (self._rotazione + 90) % 360
        self._metti_il_pixmap()
        self._adatta_alla_vista()

    def _aggiorna_comandi(self, totale: int | None = None) -> None:
        if totale is None:
            totale = self._documento.pagine if self._documento else 1
        molte = totale > 1
        self._indietro.setVisible(molte)
        self._avanti.setVisible(molte)
        self._conta.setVisible(molte)
        self._indietro.setEnabled(self._pagina > 0)
        self._avanti.setEnabled(self._pagina < totale - 1)

    def _vai(self, passo: int) -> None:
        if self._documento is None:
            return
        nuova = max(0, min(self._documento.pagine - 1, self._pagina + passo))
        if nuova != self._pagina:
            self._pagina = nuova
            self._disegna_pagina()

    def _zoom(self, fattore: float) -> None:
        self._adatta = False
        self._vista.scale(fattore, fattore)
        self._dopo_zoom()

    def _scala_adatta(self, larghezza: float, altezza: float, riempi: bool = False) -> float:
        """La scala che fa stare (o coprire, con ``riempi``) l'immagine in quel rettangolo."""
        pixmap = self._elemento.pixmap()
        if pixmap.isNull() or larghezza < 1 or altezza < 1:
            return 1.0
        rapporti = (larghezza / pixmap.width(), altezza / pixmap.height())
        return max(rapporti) if riempi else min(rapporti)

    def _adatta_alla_vista(self) -> None:
        """Rimette l'immagine nel modo scelto (Adatta o Riempi), al centro."""
        self._adatta = True
        if not self._elemento.pixmap().isNull():
            vista = self._vista.viewport().size()
            scala = self._scala_adatta(vista.width(), vista.height(), self._riempi)
            self._vista.resetTransform()
            self._vista.scale(scala, scala)
            self._vista.centerOn(self._elemento)
        self._dopo_zoom()

    def _dopo_zoom(self) -> None:
        self._percentuale.setText(f"{round(self._zoom_relativo() * 100)}%")
        self._ridisegna_fuori()

    def _zoom_relativo(self) -> float:
        """Lo zoom rispetto al modo scelto: 1 = come dopo «Adatta» o «Riempi»."""
        vista = self._vista.viewport().size()
        base = self._scala_adatta(vista.width(), vista.height(), self._riempi)
        return self._vista.transform().m11() / base

    def _commuta_modo(self) -> None:
        self._riempi = not self._riempi
        self._aggiorna_modo()
        self._adatta_alla_vista()

    def _aggiorna_modo(self) -> None:
        """Il tasto propone l'altro modo: «Riempi» se si e' in Adatta, e viceversa."""
        if self._riempi:
            self._tasto_modo.setText("Adatta")
            self._tasto_modo.setToolTip("Mostra tutta l'immagine, con i bordi (qui e sullo schermo esterno)")
        else:
            self._tasto_modo.setText("Riempi")
            self._tasto_modo.setToolTip("L'immagine copre tutto lo schermo, tagliando i bordi "
                                        "(qui e sullo schermo esterno)")

    def _ridisegna_fuori(self, *_args) -> None:
        self._timer_replica.start()
        self._timer_bella.start()

    # ------------------------------------------------------------------
    # LO SCHERMO ESTERNO
    # ------------------------------------------------------------------

    def _replica(self, veloce: bool = False) -> None:
        """Mostra sullo schermo esterno lo stesso punto allo stesso zoom.

        Il punto al centro della vista e lo zoom relativo all'adattamento sono
        quelli di qui; la scala vera e' quella che adatta l'immagine allo schermo
        esterno, cosi' «Adatta» riempie quel monitor e non lascia bordi che
        dipendono dalla forma della finestra dell'app.  ``veloce`` salta la
        lisciatura: serve mentre si trascina, poi arriva la versione bella.
        """
        pixmap = self._elemento.pixmap()
        if not self.isVisible() or pixmap.isNull():
            return
        try:
            from SubViews.SchermoEsterno import istanza
        except ImportError:
            return
        esterno = istanza()
        if esterno is None:
            return
        dimensione = esterno.size()
        larghezza, altezza = dimensione.width(), dimensione.height()
        if larghezza < 2 or altezza < 2:
            return
        scala = (self._scala_adatta(larghezza, altezza, self._riempi)
                 * max(self._zoom_relativo(), 1e-6))
        centro = self._vista.mapToScene(self._vista.viewport().rect().center())
        zona = QRectF(centro.x() - larghezza / scala / 2, centro.y() - altezza / scala / 2,
                      larghezza / scala, altezza / scala)

        uscita = QPixmap(dimensione)
        uscita.fill(QColor("#111"))
        visibile = zona.intersected(QRectF(pixmap.rect()))
        if not visibile.isEmpty():
            bersaglio = QRectF((visibile.x() - zona.x()) * scala, (visibile.y() - zona.y()) * scala,
                               visibile.width() * scala, visibile.height() * scala)
            pittore = QPainter(uscita)
            pittore.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, not veloce)
            pittore.drawPixmap(bersaglio, pixmap, visibile)
            pittore.end()
        esterno.mostra_immagine(uscita)
        self._replicato = True

    # ------------------------------------------------------------------
    # EVENTI
    # ------------------------------------------------------------------

    def eventFilter(self, oggetto, evento) -> bool:
        tipo = evento.type()
        if oggetto is self.parentWidget() and tipo == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(oggetto.rect())
        elif oggetto is self._vista.viewport():
            if tipo == QEvent.Type.Wheel:
                self._zoom(FATTORE_ZOOM if evento.angleDelta().y() > 0 else 1 / FATTORE_ZOOM)
                return True
            if tipo == QEvent.Type.MouseButtonDblClick:
                self._adatta_alla_vista()
                return True
        return super().eventFilter(oggetto, evento)

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self._messaggio.setGeometry(self._vista.rect())
        if self._adatta and self.isVisible():
            on_main(self._adatta_alla_vista)
        else:
            self._ridisegna_fuori()

    def keyPressEvent(self, evento) -> None:
        tasto = evento.key()
        if tasto in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom(FATTORE_ZOOM)
        elif tasto == Qt.Key.Key_Minus:
            self._zoom(1 / FATTORE_ZOOM)
        elif tasto in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self._vai(1)
        elif tasto in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self._vai(-1)
        elif tasto == Qt.Key.Key_R:
            self._ruota()
        elif tasto == Qt.Key.Key_0:
            self._adatta_alla_vista()
        else:
            super().keyPressEvent(evento)
