#
#  PannelloRiferimenti.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il riquadro di destra: versetti, cantici e pubblicazioni citate.

Sta nascosto e compare quando si preme un riferimento nel testo.  In cima ha
una barra viola col logo della pubblicazione (la Bibbia per un versetto), il suo
nome e il riferimento aperto; sotto, il testo.  La barra si preme: apre la
pubblicazione a schermo intero (``aperturaRichiesta``).

I riferimenti dentro il riquadro si aprono nel riquadro stesso, uno sopra
l'altro: la freccia in alto a sinistra torna al precedente, e la X chiude il
riquadro.  Quello che sta nella pagina di sinistra non si tocca.

DA DOVE SI LEGGE
----------------
Prima dal disco, poi dalla cache, e dal sito solo se la modalita' Offline e'
spenta.  Con Offline acceso il riquadro lo dice e offre «Leggi online», che
e' un gesto esplicito dell'utente.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer, QUrl, pyqtSignal as Signal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from SubViews.Conferma import ConfermaApp
from Utility import Aggiornamenti, RiferimentiWol, tema
from Utility.Extensions.Ext_DispatchQueue import background
from Utility.Stuff import icon
from WebBrowserView import Bridge, WebEnginePage

LATO_LOGO = 32
LINK_ONLINE = "jwl:online"


class _Pagina(WebEnginePage):
    """Una pagina che non naviga: un riferimento premuto lo gestisce il riquadro.

    Parte da `WebEnginePage`, quella del progetto, che ha il ponte con Python:
    gli script che il programma mette in ogni pagina lo cercano, e senza di lui
    protestano a ogni caricamento.
    """

    riferimento = Signal(str)
    leggiOnline = Signal()
    azione = Signal(str)

    def acceptNavigationRequest(self, url, tipo, principale) -> bool:
        if tipo == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            indirizzo = url.toString()
            if indirizzo.startswith(LINK_ONLINE):
                self.leggiOnline.emit()
            elif indirizzo.startswith("jwl:"):
                self.azione.emit(indirizzo)
            elif RiferimentiWol.e_riferimento(indirizzo):
                self.riferimento.emit(indirizzo)
            return False
        return True


class _Titolo(QWidget):
    """Logo e nomi: si preme per aprire la pubblicazione."""

    clicked = Signal()

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.clicked.emit()


class PannelloRiferimenti(QWidget):
    """Barra in cima e pagina sotto, con la cronologia dei riferimenti aperti."""

    chiuso = Signal()
    #: La barra e' stata premuta: la ``Voce`` del riferimento da aprire intera
    aperturaRichiesta = Signal(object)
    #: Un pulsante dentro la pagina del riquadro (``jwl:...``) e' stato premuto
    azioneRichiesta = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        #: (href, Riferimento | None, offline)
        self._storia: list[tuple[str, RiferimentiWol.Riferimento | None, bool]] = []
        #: Le pagine da cui si e' tornati indietro (per il pulsante avanti)
        self._avanti: list = []
        self._richiesta = 0
        self._loghi: dict[str, QPixmap] = {}

        self.barra = QFrame(self)
        self.barra.setObjectName("barraPannello")
        self.barra.setFixedHeight(56)
        self.barra.setStyleSheet(
            f"#barraPannello {{ background-color: {tema.ACCENTO}; }}"
            " #barraPannello QLabel { background: transparent; color: #ffffff; }"
            " #barraPannello QToolButton { background: transparent; border: none; }"
            " #barraPannello QToolButton:hover"
            " { background-color: rgba(255, 255, 255, 40); border-radius: 4px; }"
            " #barraPannello QToolButton:disabled { background: transparent; }")
        riga = QHBoxLayout(self.barra)
        riga.setContentsMargins(6, 0, 6, 0)
        riga.setSpacing(8)

        self.indietro = self._pulsante("chevron.left", "Indietro")
        self.indietro.clicked.connect(self.torna_indietro)
        riga.addWidget(self.indietro)
        self.avanti = self._pulsante("chevron.right", "Avanti")
        self.avanti.clicked.connect(self.vai_avanti)
        riga.addWidget(self.avanti)

        self.area_titolo = _Titolo(self.barra)
        self.area_titolo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.area_titolo.setToolTip("Apri la pubblicazione")
        self.area_titolo.clicked.connect(self._apri_intera)
        contenuto = QHBoxLayout(self.area_titolo)
        contenuto.setContentsMargins(0, 0, 0, 0)
        contenuto.setSpacing(8)
        self.logo = QLabel(self.area_titolo)
        self.logo.setFixedSize(LATO_LOGO, LATO_LOGO)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        contenuto.addWidget(self.logo)
        testi = QVBoxLayout()
        testi.setSpacing(0)
        testi.setContentsMargins(0, 0, 0, 0)
        self.titolo = QLabel("", self.area_titolo)
        self.titolo.setStyleSheet("font-size: 13px; font-weight: 700;")
        self.sottotitolo = QLabel("", self.area_titolo)
        self.sottotitolo.setStyleSheet("font-size: 11px; color: rgba(255,255,255,200);")
        for etichetta in (self.titolo, self.sottotitolo):
            etichetta.setMinimumWidth(10)
            etichetta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            testi.addWidget(etichetta)
        contenuto.addLayout(testi, 1)
        self.logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        riga.addWidget(self.area_titolo, 1)

        self.chiudi = self._pulsante("xmark", "Chiudi")
        self.chiudi.clicked.connect(self.chiuso.emit)
        riga.addWidget(self.chiudi)

        ponte = Bridge(self)
        self.pagina = _Pagina(ponte, self)
        # Azioni che la pagina manda da JavaScript (il trascinamento delle lingue).
        ponte.message.connect(
            lambda m: self.azioneRichiesta.emit(str(m.get("azione", "")))
            if isinstance(m, dict) and m.get("mode") == 99 else None)
        # Si apre al giro di eventi dopo: cambiare la pagina mentre Chromium sta
        # ancora decidendo se accettare la navigazione del clic lo fa cadere.
        self.pagina.riferimento.connect(
            lambda href: QTimer.singleShot(0, lambda: self.apri(href)))
        self.pagina.azione.connect(
            lambda a: QTimer.singleShot(0, lambda: self.azioneRichiesta.emit(a)))
        self.pagina.leggiOnline.connect(
            lambda: QTimer.singleShot(0, self._leggi_online))
        self.web = QWebEngineView(self)
        self.web.setPage(self.pagina)

        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(0)
        colonna.addWidget(self.barra)
        colonna.addWidget(self.web, 1)
        self._aggiorna_barra()

    def _pulsante(self, simbolo: str, aiuto: str) -> QToolButton:
        pulsante = QToolButton(self.barra)
        pulsante.setIcon(icon(simbolo, "#ffffff", 24))
        pulsante.setIconSize(QSize(24, 24))
        pulsante.setFixedSize(38, 38)
        pulsante.setToolTip(aiuto)
        pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
        return pulsante

    # ------------------------------------------------------------------
    # APRIRE, TORNARE, SVUOTARE
    # ------------------------------------------------------------------

    def apri(self, href: str, forza_rete: bool = False,
             sostituisci: bool = False) -> None:
        """Apre un riferimento sopra quello di adesso."""
        self._avanti.clear()
        self._richiesta += 1
        numero = self._richiesta
        rete = forza_rete or Aggiornamenti.automatici()
        tenuto: list = [None]

        def leggi() -> None:
            tenuto[0] = RiferimentiWol.carica(href, rete=rete)

        def pronto() -> None:
            if numero != self._richiesta:
                return
            try:
                if sostituisci and self._storia:
                    self._storia.pop()
                self._storia.append((href, tenuto[0], not rete))
                self._mostra_corrente()
            except RuntimeError:
                pass

        self.titolo.setText("Carico…")
        self.sottotitolo.setText("")
        self.logo.clear()
        self.area_titolo.setEnabled(False)
        self._mostra_pagina(RiferimentiWol.pagina_messaggio(
            "Carico…", *self._colori()))
        background(leggi, completion=pronto)

    def torna_indietro(self) -> None:
        if len(self._storia) > 1:
            self._richiesta += 1
            self._avanti.append(self._storia.pop())
            self._mostra_corrente()

    def vai_avanti(self) -> None:
        if self._avanti:
            self._richiesta += 1
            self._storia.append(self._avanti.pop())
            self._mostra_corrente()

    def metti_riferimento(self, href: str, riferimento, radice: bool = False,
                          sostituisci: bool = False) -> None:
        """Mette nel riquadro un riferimento gia' pronto.

        ``radice=True``: la cronologia riparte da questa pagina;
        ``sostituisci=True``: prende il posto della pagina di adesso.
        """
        self._richiesta += 1
        self._avanti.clear()
        if radice:
            self._storia.clear()
        elif sostituisci and self._storia:
            self._storia.pop()
        self._storia.append((href, riferimento, False))
        self._mostra_corrente()

    def carica(self, href: str, produttore) -> None:
        """Costruisce un riferimento in un thread (``produttore()``) e lo apre."""
        self._avanti.clear()
        self._richiesta += 1
        numero = self._richiesta
        tenuto: list = [None]

        def leggi() -> None:
            tenuto[0] = produttore()

        def pronto() -> None:
            if numero != self._richiesta:
                return
            try:
                self._storia.append((href, tenuto[0], False))
                self._mostra_corrente()
            except RuntimeError:
                pass

        self.titolo.setText("Carico…")
        self.sottotitolo.setText("")
        self.logo.clear()
        self.area_titolo.setEnabled(False)
        self._mostra_pagina(RiferimentiWol.pagina_messaggio(
            "Carico…", *self._colori()))
        background(leggi, completion=pronto)

    def apri_estratto(self, documento: int, inizio: int, fine: int, titolo: str,
                      breve: str, simbolo: str, lingua: str | None = None) -> None:
        """Apre il brano di una pubblicazione citata (dal disco, o dal sito)."""
        from Utility import RiferimentiLocali

        self.carica(f"jwl:doc/{documento}", lambda: RiferimentiLocali.estratto(
            documento, inizio, fine, titolo, breve, simbolo, lingua))

    def mostra_html(self, titolo: str, sottotitolo: str, pagina: str) -> None:
        """Mostra una pagina che non e' un riferimento (la gemma)."""
        self._richiesta += 1
        self._storia.clear()
        self._avanti.clear()
        self.indietro.setEnabled(False)
        self.avanti.setEnabled(False)
        self.area_titolo.setEnabled(False)
        self.titolo.setText(titolo)
        self.sottotitolo.setText(sottotitolo)
        self.logo.clear()
        self._mostra_pagina(pagina)

    def svuota(self) -> None:
        """Dimentica tutto: serve quando la pagina di sinistra cambia."""
        self._richiesta += 1
        self._storia.clear()
        self._avanti.clear()
        self.web.setHtml("")
        self._aggiorna_barra()

    def _leggi_online(self) -> None:
        if self._storia:
            self.apri(self._storia[-1][0], forza_rete=True, sostituisci=True)

    def _apri_intera(self) -> None:
        riferimento = self._storia[-1][1] if self._storia else None
        if riferimento is None or not riferimento.voci:
            return
        voce = riferimento.voci[0]
        if voce.documento or voce.libro:
            self.aperturaRichiesta.emit(voce)

    # ------------------------------------------------------------------
    # DISEGNO
    # ------------------------------------------------------------------

    @staticmethod
    def _colori() -> tuple[dict, str]:
        chiaro = tema.tema_attivo()
        return tema.colori(chiaro), tema.nome_css(chiaro)

    def _mostra_pagina(self, html: str) -> None:
        self.pagina.setBackgroundColor(QColor(self._colori()[0]["sfondo"]))
        self.web.setHtml(html, QUrl(RiferimentiWol.BASE + "/"))

    def _mostra_corrente(self) -> None:
        colori, schema = self._colori()
        _, riferimento, offline = self._storia[-1] if self._storia else ("", None, False)
        if riferimento is not None:
            pagina = RiferimentiWol.pagina_html(
                riferimento, colori, schema, tema.ACCENTO)
        elif offline:
            pagina = RiferimentiWol.pagina_messaggio(
                "Modalità offline: questo riferimento non è scaricato.",
                colori, schema, collegamento=(LINK_ONLINE, "Leggi online"))
        else:
            pagina = RiferimentiWol.pagina_messaggio(
                "Non riesco a leggere questo riferimento: controlla la connessione.",
                colori, schema)
        self._mostra_pagina(pagina)
        self._aggiorna_barra()

    def _aggiorna_barra(self) -> None:
        self.indietro.setEnabled(len(self._storia) > 1)
        self.avanti.setEnabled(bool(self._avanti))
        riferimento = self._storia[-1][1] if self._storia else None
        self.area_titolo.setEnabled(riferimento is not None)
        if riferimento is None:
            self.titolo.setText("Riferimento non disponibile" if self._storia else "")
            self.sottotitolo.setText("")
            self.logo.clear()
            return
        self.titolo.setText(riferimento.titolo)
        self.sottotitolo.setText(riferimento.sottotitolo)
        self._metti_logo(riferimento.immagine)

    def _metti_logo(self, indirizzo: str) -> None:
        self.logo.clear()
        if not indirizzo:
            return
        if indirizzo in self._loghi:
            self._imposta_logo(self._loghi[indirizzo])
            return
        tenuto: list = [None]

        def leggi() -> None:
            tenuto[0] = RiferimentiWol.scarica_immagine(indirizzo)

        def pronto() -> None:
            if not tenuto[0]:
                return
            pixmap = QPixmap()
            if not pixmap.loadFromData(tenuto[0]):
                return
            self._loghi[indirizzo] = pixmap
            try:
                attuale = self._storia[-1][1] if self._storia else None
                if attuale is not None and attuale.immagine == indirizzo:
                    self._imposta_logo(pixmap)
            except RuntimeError:
                pass

        background(leggi, completion=pronto)

    def _imposta_logo(self, pixmap: QPixmap) -> None:
        self.logo.setPixmap(pixmap.scaled(
            LATO_LOGO, LATO_LOGO, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
