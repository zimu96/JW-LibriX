#
#  ArticleView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""La schermata dell'articolo: il testo, il pannello di lato, i colori.

E' la schermata in cui si sta di piu'.  Ci sono tre cose:

  - a sinistra il capitolo, che occupa tutto lo spazio quando e' la Bibbia e
    lascia 250 pixel quando e' una pubblicazione (per il pannello di lato);
  - a destra il pannello dei versetti, che c'e' solo per le pubblicazioni;
  - in alto a destra i sei colori e il cestino, che colorano la selezione.

PERCHE' LO SPLITTER E NON UNA LARGHEZZA FISSA
---------------------------------------------
Swift metteva 250 pixel fissi con ``frame(width: 250)`` e il testo prendeva
``geometryReader.size.width - 250``.  Qui c'e' uno ``QSplitter`` con gli
stessi due pannelli e le stesse dimensioni iniziali, ma la divisione si
puo' trascinare.  Comportamento identico all'apertura, solo piu' comodo
dopo: e' la stessa cosa che fa ``NSSplitView`` su macOS.

I SEI COLORI
------------
Gli stessi sei valori del progetto originale.  Ogni colore e' un pulsante
che sembra un pennello, e accanto c'e' il cestino: il cestino non e' un
colore, e' l'operazione "togli", e per questo passa -1 invece di un numero
da 1 a 6.
"""
from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QSize, Qt, QPoint, QPointF, QTimer, QUrl, pyqtSignal as Signal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtGui import QCursor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollBar,
    QSplitter,
    QToolButton,
    QWidget,
)

from SubViews.VeloImmagine import VeloImmagine
from SubViews.PannelloRiferimenti import PannelloRiferimenti
from SubViews.WebBrowserArticleView import WebBrowserArticleView
from Utility import tema
from Utility.Structures.Generals import BlockRange, Document, Publication
from Utility.Stuff import HIGHLIGHT_HEX, highlight_color, icon, icona_tabler, CHIARO
from Utility.UserData.BookmarkManager import BookmarkManager
from Utility.UserData.HighlightManager import HighlightManager

# La larghezza del pannello di lato, come nel progetto originale.
PANNELLO_LARGHEZZA = 420


#: colore dell'app (1 giallo, 2 verde, 3 azzurro, 4 rosa, 5 arancio, 6 viola)
#: -> numero del file originale di Windows (highlightN)
_FILE_ORIGINALE = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 4}
_ATTESA_SEGNALIBRO_MS = 4000


def _icona_pastiglia(indice: int, lato: int = 26) -> QIcon:
    """La pastiglia originale di Windows (Files/icons/colorate), chiara o scura."""
    from Utility.Stuff import ICON_DIR

    variante = "" if tema.tema_attivo() else "_dark"
    percorso = (ICON_DIR / "colorate"
                / f"highlight{_FILE_ORIGINALE[indice]}{variante}.scale-200.png")
    pixmap = QPixmap(str(percorso))
    return QIcon(pixmap) if not pixmap.isNull() else QIcon()


def Lingua_bibbia() -> str:
    from Utility import Lingua

    return Lingua.bibbia_simbolo()


def Lingua_nome(simbolo: str) -> str:
    from Utility import Lingua

    voce = Lingua.per_simbolo(simbolo) or {}
    return voce.get("nome_vernacolare") or voce.get("nome") or simbolo


def _stile_popup(c: dict) -> str:
    return (f"#barraColori {{ background-color: {c['pannello']};"
            f" border: 1px solid {c['bordo']}; border-radius: 8px; }}"
            " QToolButton { background: transparent; border: none; border-radius: 6px;"
            " padding: 2px; }"
            f" QToolButton:hover {{ background-color: {c['hover']}; }}")


@lru_cache(maxsize=None)
def _icona_menu(nome: str, lato: int = 22, chiaro: bool = True) -> QIcon:
    """Un'icona del menu del versetto, presa dall'app originale (chiara o scura).

    I file originali hanno molto margine trasparente: si ritaglia il disegno e
    lo si adatta al lato, cosi' tutte le icone hanno lo stesso peso.
    """
    from PyQt6.QtGui import QBitmap, QPainter, QRegion
    from Utility.Stuff import ICON_DIR

    variante = "" if chiaro else "_dark"
    immagine = QPixmap(str(ICON_DIR / "menu_versetto" / f"{nome}{variante}.png")).toImage()
    if immagine.isNull():
        return QIcon()
    riquadro = QRegion(QBitmap.fromImage(immagine.createAlphaMask())).boundingRect()
    disegno = QPixmap.fromImage(immagine.copy(riquadro))
    lato2 = lato * 2
    interno = int(lato2 * 0.8)
    disegno = disegno.scaled(interno, interno, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    finale = QPixmap(lato2, lato2)
    finale.fill(Qt.GlobalColor.transparent)
    pittore = QPainter(finale)
    pittore.drawPixmap((lato2 - disegno.width()) // 2,
                       (lato2 - disegno.height()) // 2, disegno)
    pittore.end()
    return QIcon(finale)


#: Le misure comuni a tutti i menu che compaiono sul testo: stesse icone, stessi
#: pulsanti, stesse pastiglie.
LATO_ICONA = 34
LATO_TASTO = 52
PASTIGLIA = QSize(46, 36)


class _BarraPopup(QFrame):
    """Base dei menu sul testo: una riga di pulsanti grandi, uguali fra loro."""

    def __init__(self, padre=None) -> None:
        super().__init__(padre, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("barraColori")
        self.setStyleSheet(_stile_popup(tema.colori(tema.tema_attivo())))
        self._riga = QHBoxLayout(self)
        self._riga.setContentsMargins(8, 6, 8, 6)
        self._riga.setSpacing(4)

    def _tasto(self, icona: QIcon, aiuto: str, azione=None, grande: bool = False) -> QToolButton:
        tasto = QToolButton(self)
        tasto.setIcon(icona)
        tasto.setIconSize(PASTIGLIA if grande else QSize(LATO_ICONA, LATO_ICONA))
        tasto.setMinimumSize(LATO_TASTO + (PASTIGLIA.width() - LATO_ICONA if grande else 0),
                             LATO_TASTO)
        tasto.setToolTip(aiuto)
        tasto.setCursor(Qt.CursorShape.PointingHandCursor)
        if azione is not None:
            tasto.clicked.connect(azione)
        self._riga.addWidget(tasto)
        return tasto

    def _chiudi_ed_emetti(self, segnale, *args):
        return lambda _=False: (self.close(), segnale.emit(*args))

    def mostra_sotto(self, punto: QPoint) -> None:
        self.adjustSize()
        self.move(punto)
        self.show()


class BarraColori(_BarraPopup):
    """I sei colori, e sotto la mano il cestino, il segnalibro e la gemma.

    Un clic su un colore sottolinea; tenendo premuto a lungo compare il
    segnalibro di quel colore.  Il cestino c'e' solo se la selezione tocca una
    sottolineatura gia' presente.
    """

    colorePremuto = Signal(int)
    segnalibroRichiesto = Signal(int)
    togliPremuto = Signal()
    gemmaPremuta = Signal()

    def __init__(self, padre=None, con_cestino: bool = False,
                 con_gemma: bool = False) -> None:
        super().__init__(padre)
        self._lungo = False
        for indice in range(1, len(HIGHLIGHT_HEX) + 1):
            tasto = self._tasto(_icona_pastiglia(indice), "", grande=True)
            tasto.pressed.connect(lambda i=indice: self._premuto(i))
            tasto.released.connect(lambda i=indice: self._rilasciato(i))
        if con_cestino:
            c = tema.colori(tema.tema_attivo())
            self._tasto(icona_tabler("trash", c["icona"], int(LATO_ICONA * 0.8)),
                        "Togli la sottolineatura",
                        self._chiudi_ed_emetti(self.togliPremuto))
        self._tasto(_icona_menu("segnalibro", LATO_ICONA, tema.tema_attivo()), "Aggiungi un segnalibro",
                    self._chiudi_ed_emetti(self.segnalibroRichiesto, 1))
        if con_gemma:
            self._tasto(_icona_menu("gemma", LATO_ICONA, tema.tema_attivo()), "Guida alle ricerche",
                        self._chiudi_ed_emetti(self.gemmaPremuta))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._scaduto)
        self._attivo = 0

    def _premuto(self, indice: int) -> None:
        self._attivo = indice
        self._lungo = False
        self._timer.start(_ATTESA_SEGNALIBRO_MS)

    def _scaduto(self) -> None:
        self._lungo = True
        indice = self._attivo
        menu = QMenu(self)
        azione = menu.addAction(icon("bookmark.fill", CHIARO), "Aggiungi ai segnalibri")
        azione.triggered.connect(lambda: self.segnalibroRichiesto.emit(indice))
        menu.exec(QCursor.pos())
        self.close()

    def _rilasciato(self, indice: int) -> None:
        self._timer.stop()
        if not self._lungo and indice == self._attivo:
            self.close()
            self.colorePremuto.emit(indice)


class BarraVersetto(_BarraPopup):
    """Il menu che compare premendo il numero di un versetto.

    Gemma (guida alle ricerche), nota, segnalibro, condividi e una freccia che
    apre i sei colori per sottolineare tutto il versetto.
    """

    gemmaPremuta = Signal()
    notaPremuta = Signal()
    traduzioniPremute = Signal()
    segnalibroPremuto = Signal()
    condividiPremuto = Signal()
    copiaPremuta = Signal()
    colorePremuto = Signal(int)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        for nome, aiuto, segnale in (
                ("gemma", "Guida alle ricerche", self.gemmaPremuta),
                ("nota", "Aggiungi una nota", self.notaPremuta),
                ("traduzioni", "Il versetto in altre lingue", self.traduzioniPremute),
                ("segnalibro", "Aggiungi un segnalibro", self.segnalibroPremuto),
                ("condividi", "Condividi il versetto", self.condividiPremuto),
                ("copia", "Copia il versetto", self.copiaPremuta)):
            self._tasto(_icona_menu(nome, LATO_ICONA, tema.tema_attivo()), aiuto,
                        self._chiudi_ed_emetti(segnale))
        self._piu = self._tasto(_icona_menu("avanti", LATO_ICONA, tema.tema_attivo()),
                                "Sottolinea il versetto", self._mostra_colori)

    def _mostra_colori(self) -> None:
        self._piu.hide()
        for indice in range(1, len(HIGHLIGHT_HEX) + 1):
            self._tasto(_icona_pastiglia(indice), "",
                        self._chiudi_ed_emetti(self.colorePremuto, indice), grande=True)
        self.adjustSize()


class _Velo(QWidget):
    """Un riquadro del colore del tema sopra il capitolo mentre si prepara.

    Il capitolo si ricostruisce dopo il caricamento (parole selezionabili,
    sottolineature, scorrimento): finche' non e' tutto pronto si tiene coperto,
    cosi' non si vede il bianco di Chromium ne' il testo che si assesta.
    """

    def __init__(self, padre: QWidget) -> None:
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        padre.installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def eventFilter(self, oggetto, evento) -> bool:
        from PyQt6.QtCore import QEvent
        if evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def copri(self, massimo_ms: int = 2500) -> None:
        sfondo = tema.colori(tema.tema_attivo())["sfondo"]
        self.setStyleSheet(f"background-color: {sfondo};")
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self._timer.start(massimo_ms)

    def scopri(self, dopo_ms: int = 60) -> None:
        self._timer.start(dopo_ms)


class _FrecciaPagina(QWidget):
    """La freccia che cambia pagina, ai lati del capitolo.

    COME SI VEDE
    -----------
    Stando ferma e' **invisibile**: e' un tondo scuro con la freccia
    bianca, e si vede solo quando il puntatore e' sulla sua zona.  Il
    colore e' quello dell'app (il viola e il nero traslucido), e la
    freccia e' bianca come le icone della fascia.

    IL PUNTATORE LA TROVA
    ---------------------
    La zona in cui la freccia si accende e' un po' piu' grande del
    tondo: il puntatore non deve centrare il pixel esatto per farla
    comparire, altrimenti e' un tiro a segno e l'utente non la preme
    mai.  La zona e' pero' stretta: il capitolo si legge, e la freccia
    non deve stare li' sempre, a coprire il testo.
    """

    #: La larghezza (e l'altezza) del tondo: e' un cerchio.
    LATO = 44
    #: Quanto la zona e' piu' larga del tondo, per lato.
    MARGINE = 12

    clic = Signal()

    def __init__(self, simbolo: str, aiuto: str, padre=None) -> None:
        super().__init__(padre)
        self.setToolTip(aiuto)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._pixmap = icon(simbolo, "#ffffff", 24).pixmap(24, 24)
        #: La pagina sotto la freccia: la rotella va li'.  E' una funzione
        #: perche' il widget interno di Chromium nasce quando la pagina
        #: viene disegnata, e quindi cambia.
        self._pagina = None
        #: Questa freccia ha qualcosa da fare?  Se non ha, non si accende
        #: mai: agli estremi del capitolo non c'e' pagina dopo (o prima).
        self.disponibile = True
        self.setVisible(False)

    def contiene(self, punto: QPoint) -> bool:
        """Il punto e' nella zona in cui questa freccia si accende?"""
        zona = self.geometry().adjusted(-self.MARGINE, -self.MARGINE,
                                        self.MARGINE, self.MARGINE)
        return zona.contains(punto)

    def mousePressEvent(self, evento) -> None:
        self.clic.emit()

    def wheelEvent(self, evento) -> None:
        """La rotella va al capitolo, non alla freccia.

        LA FRECCIA STA SOTTO IL PUNTATORE
        ----------------------------------
        La freccia compare quando il puntatore e' sulla sua zona, e li' la
        freccia ci resta **sopra**: il puntatore che e' sopra un pulsante
        non vede piu' la pagina, e la rotella non scorreva niente.  Il
        capitolo sembrava bloccato, e ogni tanto tornava indietro.

        Per questo l'evento della rotella viene passato alla pagina, che e'
        sotto la freccia.
        """
        pagina = self._pagina() if self._pagina else None
        if pagina is None:
            evento.ignore()
            return
        from PyQt6.QtWidgets import QApplication

        # L'evento va alla pagina cosi' com'e': quello che conta per lo
        # scorrimento e' la rotella, non il punto (che qui e' quello della
        # freccia).
        QApplication.sendEvent(pagina, evento)
        evento.accept()

    def paintEvent(self, evento) -> None:
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QColor, QPainter

        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        pittore.setPen(Qt.PenStyle.NoPen)
        # Il fondo: il viola dell'app, un po' trasparente, cosi' il testo
        # sotto si vede e la freccia non sembra un buco nella pagina.
        pittore.setBrush(QColor(100, 57, 139, 220))
        pittore.drawEllipse(QRectF(0, 0, self.width(), self.height()))
        if self._pixmap is not None:
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            pittore.drawPixmap(x, y, self._pixmap)
        pittore.end()


class ArticleView(QWidget):
    """Il testo, il pannello, e i sei colori."""

    #: Chiede di tornare indietro (il pulsante con la freccia e il nome)
    goBack = Signal()
    #: Un segnalibro e' stato scelto: la finestra apra quel punto
    posizioneScelta = Signal(object)
    #: Un messaggio breve per l'utente (segnalibro aggiunto, rimosso, ...)
    avviso = Signal(str)
    #: Sottolineature o segnalibri sono cambiati: la sezione Ricerche si rilegge
    segniCambiati = Signal()
    #: La barra del riquadro dei riferimenti e' stata premuta: la ``Voce``
    #: della pubblicazione da aprire a schermo intero
    riferimentoDaAprire = Signal(object)
    #: Un video nel testo e' stato premuto: (indirizzo webpubvid, testo del link)
    videoDaProporre = Signal(str, str)
    #: E' stato scaricato un pacchetto: la sezione Scaricati si rilegge
    pacchettoScaricato = Signal()
    #: Avanzamento (0-100) dello scaricamento della Guida, dal thread di lavoro
    _avanzamentoGuida = Signal(int)
    #: Uno scaricamento della Bibbia in un'altra lingua e' finito (simbolo)
    _scaricoFinito = Signal(str)
    #: Si apre la schermata dei contenuti multimediali (il widget gia' pronto)
    contenutiDaAprire = Signal(object)

    def __init__(self, pub: Publication, file_path: str, prev_text: str,
                 document: Document | None = None, parent=None,
                 ancora: str = "", a_un_giorno: bool = False,
                 pagine: list | None = None,
                 indice_pagina: int = -1) -> None:
        super().__init__(parent)
        self.pub = pub
        self.document = document
        self.prev_text = prev_text
        self.file_path = file_path
        # Le Scritture del giorno sono un documento che contiene tutto il
        # mese.  Con `a_un_giorno` la pagina mostra un giorno solo, e le
        # frecce nella barra passano al precedente e al successivo.
        self._a_un_giorno = bool(a_un_giorno)
        self._giorno_corrente = -1
        self._giorni_totali = 0
        self._titolo_giorno = ""
        # I capitoli di una pubblicazione (o della Bibbia) sono pagine dello
        # stesso libro: le frecce cambiano pagina senza creare una schermata
        # nuova, cosi' il pulsante indietro torna all'elenco e non accumula
        # un passaggio per ogni capitolo letto.
        self._pagine = list(pagine) if pagine else []
        try:
            self._indice_pagina = int(indice_pagina)
        except (TypeError, ValueError):
            self._indice_pagina = -1
        if self._pagine and not 0 <= self._indice_pagina < len(self._pagine):
            self._indice_pagina = 0
        self._frecce_pagina: list = []
        # I due pulsanti che cambiano pagina, ai lati del capitolo.  Sono
        # **sempre nascosti** e compaiono solo quando il puntatore arriva
        # sulla loro zona: vedi `_FrecciaPagina` e `_mousemove`.
        self._frecce_lato: list = []
        self._titolo_barra = None
        # L'ultima selezione fatta nella pagina: testo, paragrafo e id.  La
        # riempie il messaggio `mode: 3` e la usano sia il colore sia il
        # segnalibro, cosi' non si rilegge una selezione che il menu' ha
        # nel frattempo coperto.
        self._selezione: dict = {"testo": "", "paragrafo": 0, "ancora": ""}
        self._preferisce_spartito = False
        self._spartito_visibile = False

        # `ancora` e' il punto della pagina da cui partire, e la lascia il
        # motore: vedi `WebBrowserArticleView._va_all_ancora`.  Vuota per tutte
        # le pagine che si aprono dall'inizio, e non e' un parametro che
        # serve a qualcosa d'altro.
        self.article = WebBrowserArticleView(pub=pub, file_path=file_path,
                                              document=document, parent=self,
                                              ancora=ancora)
        self.pannello = PannelloRiferimenti(self)
        self.pannello.chiuso.connect(self._chiudi_riferimento)
        self.pannello.aperturaRichiesta.connect(self.riferimentoDaAprire.emit)

        # LA BARRA DI SCORRIMENTO: QUELLA DEL PROGRAMMA
        # ------------------------------------------------
        # Il capitolo e' una pagina web, e il motore ci disegna la sua barra:
        # grigia di una misura sua, e diversa da tutte le altre.  In ogni
        # altra sezione la barra e' quella del programma — 6 pixel, viola, la
        # maniglia sottile — e questa non puo' essere un'altra.
        #
        # Qui la barra e' **quella del programma**, accanto al capitolo, e il
        # motore non disegna piu' la sua (il CSS della pagina la mette a
        # zero).  Le due cose vanno d'accordo: quando la pagina scorre, la
        # barra segue, e quando la barra si muove, la pagina va li'.
        self.contenitore = QWidget(self)
        disposizione = QHBoxLayout(self.contenitore)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)
        disposizione.addWidget(self.article.web, 1)
        self._barra = QScrollBar(Qt.Orientation.Vertical, self.contenitore)
        self._barra.valueChanged.connect(self._barra_mossa)
        disposizione.addWidget(self._barra)
        #: Quando la barra viene aggiornata **dalla pagina**, il suo
        #: cambiamento non deve rimandare la pagina indietro.
        self._aggiornando = False
        #: Il giro che chiede alla pagina quanto e' scesa.  None finche' la
        #: pagina non e' pronta.
        self._timer_barra = None

        # Lo splitter tiene insieme il capitolo e il riquadro dei riferimenti.
        # Il riquadro sta nascosto e compare quando si preme un riferimento.
        self._velo = _Velo(self.contenitore)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(self.contenitore)
        self.splitter.addWidget(self.pannello)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setChildrenCollapsible(False)
        # Il riquadro di lato non viene mai nascosto: resta a larghezza zero.
        # Mostrarlo per la prima volta crea al volo la vista di Chromium, e su
        # KDE questo faceva sparire e riapparire la finestra.
        self._riquadro(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)

        # LE FRECCE AI LATI
        # ------------------
        # Le due frecce che cambiano pagina stanno ai due lati del capitolo
        # e sono **sempre nascoste**: compaiono quando il puntatore passa
        # sulla loro zona.  Vedi `_costruisci_le_frecce`.
        self._costruisci_le_frecce()
        for motore in self._motori():
            # Il puntatore che si muove **senza** premere arriva solo se il
            # motore ascolta il mouse: senza questo, gli eventi di movimento
            # arrivano solo mentre un pulsante e' premuto, e le frecce si
            # accenderebbero solo trascinando.
            motore.setMouseTracking(True)
        self._installa_i_filtri()
        for freccia in self._frecce_lato:
            freccia.installEventFilter(self)

        # LA MISURA DEL TESTO DI ADESSO
        # ------------------------------
        # Il capitolo nasce lontano dalla finestra, e la finestra non passa
        # da `navigate` per aprirlo.  Perche' il testo non parta dalla
        # misura di prima, il capitolo chiede qui la misura scelta: e' il
        # posto unico, ed e' gia' limitata.
        self.imposta_dimensione_testo(tema.dimensione_testo())
        self._copri_il_capitolo()

        # La figura a schermo intero: un riquadro sopra tutto, che sparisce
        # quando si clicca.  Nascosto, non tolto: e' il modo piu' semplice per
        # non doverlo ricreare ogni volta.
        #
        # Il velo e' la classe unica del programma (`VeloImmagine`): e' lo
        # stesso che si apre per le foto delle notizie, e quindi fa le
        # stesse cose — si vede a schermo intero dentro l'app e va sullo
        # schermo esterno.
        self.velo = VeloImmagine(self)

        # I collegamenti fra la pagina e questa schermata.
        self.article.highlightRequested.connect(self._aggiungi_evidenziazione)
        self.article.selectionMenuRequested.connect(self._mostra_menu_selezione)
        self.article.verseMenuRequested.connect(self._mostra_menu_versetto)
        self.pannello.azioneRichiesta.connect(self._azione_riquadro)
        self._verso_gemma = 0
        self._scaricoFinito.connect(self._scarico_finito)
        self._timer_lingue = QTimer(self)
        self._timer_lingue.timeout.connect(self._aggiorna_lingue)
        self._voci_gemma: list = []
        self._percentuale = -1
        self._avanzamentoGuida.connect(self._mostra_avanzamento_guida)
        self._versetto: dict = {"verso": 0, "ancora": "", "testo": ""}
        self.article.imageToShow.connect(self._mostra_immagine)
        self.article.riferimentoRichiesto.connect(self._apri_riferimento)
        # Il popup e' modale: se partisse dentro il callback con cui la pagina ci
        # consegna il clic, Chromium cadrebbe.  Si emette al giro dopo.
        self.article.videoRichiesto.connect(
            lambda video, testo: QTimer.singleShot(
                0, lambda: self.videoDaProporre.emit(video, testo)))
        self.article.paginaPronta.connect(self._pagina_pronta)

        self.article.carica()

    # ------------------------------------------------------------------
    # LA BARRA DI SCORRIMENTO DEL CAPITOLO
    # ------------------------------------------------------------------

    def _chiedi_lo_scorrimento(self) -> None:
        """Chiede alla pagina quanto e' alta e quanto si e' sceso.

        La domanda va fatta ogni tanto, e non a ogni evento: la pagina
        puo' scorrere da sola (l'ancora, il ritorno all'inizio del capitolo)
        e la barra deve accorgersene.

        Il giro e' ogni 150 millisecondi: abbastanza perche' la barra non
        resti ferma mentre l'utente scorre, e non tanto da occupare il
        programma.
        """
        if not self._vivo():
            return
        self.article.web.run(
            "({y: window.scrollY, h: document.documentElement.scrollHeight, "
            "v: window.innerHeight})",
            self._aggiorna_la_barra)

    def _aggiorna_la_barra(self, dati) -> None:
        """La pagina ha detto la sua altezza e dove si trova: la barra segue."""
        if not isinstance(dati, dict):
            return
        try:
            alto = int(dati.get("h") or 0)
            visto = int(dati.get("v") or 0)
            giusto = int(dati.get("y") or 0)
        except (TypeError, ValueError):
            return
        corsa = max(0, alto - visto)
        self._aggiornando = True
        self._barra.setRange(0, corsa)
        if self._barra.value() != min(giusto, corsa):
            self._barra.setValue(min(giusto, corsa))
        self._aggiornando = False

    def _barra_mossa(self, valore: int) -> None:
        """La barra e' stata tirata: la pagina va a quel punto."""
        if self._aggiornando:
            return
        if not self._vivo():
            return
        self.article.web.run(f"window.scrollTo(0, {int(valore)});")

    def _vivo(self) -> bool:
        """Il capitolo esiste ancora?

        Il capitolo puo' essere chiuso mentre la pagina si sta caricando:
        e' quello che succede quando si torna indietro.
        """
        try:
            self.article.web  # noqa: B018 - se il C++ e' sparito, qui solleva
        except RuntimeError:
            return False
        return True

    def _installa_i_filtri(self) -> None:
        """Mette il filtro dove il mouse della pagina arriva davvero.

        IL WIDGET INTERNO DI CHROMIUM
        ------------------------------
        Il `QWebEngineView` non riceve il mouse: lo riceve il **widget
        interno** che Chromium ci mette dentro, e quel widget nasce quando
        la pagina viene disegnata la prima volta.  Un filtro messo solo sul
        motore non vede niente: e' quello che e' successo, e le frecce non
        comparivano.

        Per questo il filtro va sul motore **e** sui suoi figli, e va
        rimesso a ogni pagina caricata: il widget interno puo' essere
        rifatto, e il filtro sul vecchio non servirebbe piu'.

        QUI NON SI RICARICA LA PAGINA
        ------------------------------
        Il filtro e' un filtro: mette i filtri e basta.  Se qui dentro ci
        finisse anche il caricamento della pagina, la pagina si
        ricaricherebbe da sola — e il capitolo ripartirebbe da capo
        mentre l'utente lo sta leggendo, e la scrittura del giorno
        perderebbe i suoi giorni.
        """
        for motore in self._motori():
            motore.installEventFilter(self)
            for figlio in motore.findChildren(QWidget):
                figlio.installEventFilter(self)

    # ------------------------------------------------------------------
    # LA BARRA: QUI NON C'E' PIU'
    # ------------------------------------------------------------------

    def toolbar(self, andata=None) -> None:
        """Il capitolo **non ha** una barra sua.

        LA BARRA DEL CAPITOLO ERA UN PEZZO DI BARRA IN PIU'
        ---------------------------------------------------
        Fra la fascia viola e il capitolo c'era una riga con il nome del
        libro, il nome del capitolo e le due frecce di pagina.  Una riga
        intera per dire due cose che la finestra dice gia' altrove: la
        freccia indietro della fascia porta indietro, e il nome del libro
        si vede gia' nella sezione da cui si e' entrati.

        E la riga costava: toglieva un pezzo di schermo al capitolo, e il
        capitolo e' la cosa che si sta guardando.

        LE FRECCE SONO ANDATE AI LATI
        ----------------------------
        Le due frecce che cambiavano pagina non sono sparite: sono ai
        due lati del capitolo, e compaiono **solo** quando il puntatore
        arriva sulla loro zona.  Sempre nascoste, mai accese da sole: una
        freccia che sta li' ferma e non serve a niente finche' non la si
        cerca.

        Per il resto la schermata e' come prima: i colori compaiono solo
        quando c'e' una selezione, e i segnalibri stanno nella fascia.
        """
        return None

    # ------------------------------------------------------------------
    # LE FRECCE AI LATI DEL CAPITOLO
    # ------------------------------------------------------------------

    def _costruisci_le_frecce(self) -> None:
        """Le due frecce che cambiano pagina, ai lati del capitolo.

        SEMPRE NASCOSTE
        ---------------
        Le frecce non stanno sempre li': stanno nascoste e compaiono solo
        quando il puntatore passa sulla loro zona.  Il puntatore che
        arriva a destra vede la freccia di destra, e quella di sinistra
        resta nascosta; se va a sinistra, e' la viceversa.  Il capitolo
        si legge senza frecce in giro, e chi vuole la pagina successiva la
        chiama.

        IL PULSANTE E' SEMPRE SOPRA LA PAGINA
        -------------------------------------
        Il pulsante e' figlio di questa schermata, non del motore: il
        motore disegna la pagina e il pulsante sta **sopra**, e il
        puntatore li vede entrambi.
        """
        if not (self._a_un_giorno or self._pagine):
            return

        if self._a_un_giorno:
            aiuto_precedente = "Giorno precedente"
            aiuto_successivo = "Giorno successivo"
        elif self.pub.isBible:
            aiuto_precedente = "Capitolo precedente"
            aiuto_successivo = "Capitolo successivo"
        else:
            aiuto_precedente = "Pagina precedente"
            aiuto_successivo = "Pagina successiva"

        for passo, simbolo, aiuto in ((-1, "chevron.left", aiuto_precedente),
                                      (1, "chevron.right", aiuto_successivo)):
            pulsante = _FrecciaPagina(simbolo, aiuto, self)
            pulsante._pagina = self._widget_della_pagina
            pulsante.clic.connect(
                lambda _=False, p=passo: self._cambia_pagina(p))
            pulsante.setVisible(False)
            self._frecce_lato.append(pulsante)
        self._frecce_pagina = list(self._frecce_lato)
        self._aggiorna_frecce_pagina()

    def _accendi_la_freccia(self, punto) -> None:
        """Accende la freccia della zona in cui sta il puntatore.

        UNA SOLA PER VOLTA
        -------------------
        Il puntatore e' in un posto solo: se e' a destra compare la freccia
        di destra, e quella di sinistra sparisce.  Se e' in mezzo, non
        compare nessuna: sono due frecce, non quattro.

        La freccia che **non** porta da nessuna parte non si accende
        mai: agli estremi del capitolo non c'e' pagina dopo (o prima), e
        una freccia che non porta niente e' una promessa falsa.
        """
        for freccia in self._frecce_lato:
            freccia.setVisible(freccia.disponibile and freccia.contiene(punto))

    def eventFilter(self, oggetto, evento) -> bool:
        """Il puntatore dentro il motore: la freccia della zona compare.

        IL FILTRO E' SU MOTORE E SUI SUOI FIGLI
        ------------------------------------------
        Il `QWebEngineView` non riceve il mouse: lo riceve il **widget
        interno** che Chromium ci mette dentro.  Un filtro messo solo sul
        motore non vede niente: e' quello che e' successo, e le frecce non
        comparivano.

        Qui il filtro e' su tutti e due (vedi `_installa_i_filtri`), e
        guarda **dentro** ai motori: e' l'unico modo per vedere il
        puntatore che si muove sulla pagina.

        Si guarda anche l'**entrata** del puntatore nella pagina: quando
        il cursore entra dalla destra, la freccia di destra deve accendersi
        subito, e non un movimento dopo.

        E LE FRECCE SI ACCENDONO DA SE'
        -------------------------------
        Il puntatore che arriva **sulla freccia** non e' piu' dentro il
        motore: e' sulla freccia.  Se non si curasse di questo, la freccia
        si accenderebbe e si spegnerebbe subito, e non la si potrebbe
        neanche premere.
        """
        from PyQt6.QtCore import QEvent

        tipo = evento.type()
        if isinstance(oggetto, _FrecciaPagina):
            if tipo == QEvent.Type.Enter:
                oggetto.setVisible(oggetto.disponibile)
            elif tipo == QEvent.Type.Leave:
                oggetto.setVisible(False)
            return False

        if tipo in (QEvent.Type.MouseMove, QEvent.Type.Enter,
                    QEvent.Type.HoverMove) and self._dentro_a_un_motore(oggetto):
            punto = self._punto_del_mouse(oggetto, evento)
            if punto is not None:
                self._accendi_la_freccia(punto)
        return super().eventFilter(oggetto, evento)

    def _dentro_a_un_motore(self, oggetto) -> bool:
        """L'oggetto e' la pagina (o un suo figlio)?"""
        for motore in self._motori():
            if oggetto is motore:
                return True
            try:
                if motore.isAncestorOf(oggetto):
                    return True
            except RuntimeError:
                continue
        return False

    @staticmethod
    def _punto_del_mouse(oggetto, evento):
        """Il punto del mouse, in un modo che va bene per ogni evento.

        `QMouseEvent` ha `pos()` e `position()`; `QEnterEvent` ha solo
        `position()`.  Con `pos()` su un evento di entrata il programma
        stampava un errore ogni volta che il puntatore entrava nella
        pagina — e, per peggio, non accendeva la freccia.
        """
        for nome in ("position", "pos"):
            metodo = getattr(evento, nome, None)
            if metodo is None:
                continue
            try:
                valore = metodo()
            except TypeError:
                continue
            if hasattr(valore, "toPoint"):
                return valore.toPoint()
            try:
                return QPoint(int(valore.x()), int(valore.y()))
            except AttributeError:
                continue
        return None

    def _widget_della_pagina(self):
        """Il widget che riceve davvero il mouse: quello interno di Chromium.

        Il `QWebEngineView` non riceve il mouse: lo riceve il widget
        interno che Chromium ci mette dentro, e quel widget nasce quando
        la pagina viene disegnata.  La rotella va li', altrimenti la
        freccia — che sta sotto il puntatore — si trattiene la pagina.
        """
        motore = self.article.web
        for figlio in motore.findChildren(QWidget):
            return figlio
        return motore

    def _motori(self) -> tuple:
        """I motori di questa schermata: il capitolo e il pannello di lato."""
        return (self.article.web, self.pannello.web)

    def _riquadro(self, aperto: bool) -> None:
        """Apre il riquadro di lato alla sua larghezza, o lo chiude a zero."""
        self.pannello.setMaximumWidth(16777215 if aperto else 0)
        self.pannello.setMinimumWidth(PANNELLO_LARGHEZZA if aperto else 0)
        self.splitter.handle(1).setVisible(aperto)
        totale = max(self.splitter.width(), 2 * PANNELLO_LARGHEZZA)
        larghezza = PANNELLO_LARGHEZZA if aperto else 0
        self.splitter.setSizes([totale - larghezza, larghezza])

    def _apri_riferimento(self, href: str) -> None:
        """Un riferimento e' stato premuto: il riquadro compare e lo mostra."""
        self._mostra_nel_riquadro(lambda: self.pannello.apri(href))

    def _riferimento_versetto(self, verso: int) -> str:
        return f"{(self.prev_text or '').strip()} {self.pub.chapter}:{verso}".strip()

    def _apri_gemma(self) -> None:
        """La gemma: le pubblicazioni che citano il versetto selezionato.

        Tutto avviene nel riquadro di lato: se la Guida alle ricerche non e'
        scaricata, il riquadro lo dice e ha il pulsante per scaricarla.
        """
        verso = int(self._selezione.get("paragrafo", 0) or 0)
        if verso <= 0:
            self.avviso.emit("Seleziona un versetto per usare la gemma.")
            return
        self._verso_gemma = verso
        self._mostra_gemma()

    def _mostra_nel_riquadro(self, rendi) -> None:
        """Prepara il contenuto del riquadro e lo apre solo quando e' pronto.

        Aprirlo subito lo mostrava bianco per qualche istante.  Si aspetta la
        fine del caricamento (al massimo 1,5 secondi) e poi si allarga.
        """
        if self.pannello.maximumWidth() == 0:
            web = self.pannello.web
            fatto = [False]

            def apri(*_) -> None:
                if fatto[0]:
                    return
                fatto[0] = True
                try:
                    web.loadFinished.disconnect(apri)
                except TypeError:
                    pass
                self._riquadro(True)

            web.loadFinished.connect(apri)
            QTimer.singleShot(1500, apri)
        rendi()

    def _mostra_riquadro(self, titolo: str, pagina: str) -> None:
        self._mostra_nel_riquadro(
            lambda: self.pannello.mostra_html("Guida alle ricerche", titolo, pagina))

    def _mostra_gemma(self) -> None:
        from Utility import GemmaRicerche

        verso = self._verso_gemma
        nome = self._riferimento_versetto(verso)
        if GemmaRicerche.percorso_db() is None:
            self._mostra_riquadro(nome, GemmaRicerche.pagina_scarica(
                nome, tema.colori(tema.tema_attivo()),
                tema.nome_css(tema.tema_attivo()), tema.ACCENTO))
            self.pannello.chiedi(
                "Guida alle ricerche",
                "Per vedere le pubblicazioni collegate a questo versetto serve la "
                "Guida alle ricerche (circa 110 MB).\n\nVuoi scaricarla adesso?",
                "Scarica", self._scarica_guida)
            return
        self._voci_gemma = GemmaRicerche.pubblicazioni(
            int(self.pub.book or 0), int(self.pub.chapter or 0), verso)
        self._mostra_nel_riquadro(lambda: self.pannello.metti_riferimento(
            "jwl:gemma", GemmaRicerche.riferimento(nome, self._voci_gemma),
            radice=True))

    def _mostra_avanzamento_guida(self, percentuale: int) -> None:
        if percentuale == self._percentuale:
            return
        self._percentuale = percentuale
        from Utility import GemmaRicerche

        self.pannello.mostra_html(
            "Guida alle ricerche", self._riferimento_versetto(self._verso_gemma),
            GemmaRicerche.pagina_scarica(
                self._riferimento_versetto(self._verso_gemma),
                tema.colori(tema.tema_attivo()), tema.nome_css(tema.tema_attivo()),
                tema.ACCENTO, in_corso=True, percentuale=percentuale))

    def _azione_riquadro(self, azione: str) -> None:
        if azione == "jwl:scarica-guida":
            self._scarica_guida()
        elif azione == "jwl:traduzioni":
            self._mostra_traduzioni()
        elif azione.startswith(("jwl:lingue", "jwl:lingua/", "jwl:ordine/",
                                "jwl:scarica/", "jwl:ferma/", "jwl:elimina/")):
            self._azione_lingue(azione)
        elif azione.startswith("jwl:pub/"):
            try:
                voce = self._voci_gemma[int(azione.rsplit("/", 1)[1])]
            except (ValueError, IndexError):
                return
            self.pannello.apri_estratto(
                voce["documento"], voce["inizio"], voce["fine"],
                voce["titolo"] or voce["sigla"], voce["breve"], voce["simbolo"],
                Lingua_bibbia())

    def _scarica_guida(self) -> None:
        from Utility import GemmaRicerche
        from Utility.JWPubManager import scarica_jwpub

        colori = tema.colori(tema.tema_attivo())
        schema = tema.nome_css(tema.tema_attivo())
        nome = self._riferimento_versetto(self._verso_gemma)
        self._mostra_riquadro(nome, GemmaRicerche.pagina_scarica(
            nome, colori, schema, tema.ACCENTO, in_corso=True))

        self._percentuale = -1

        def avanza(letti: int, totale: int) -> None:
            if totale > 0:
                self._avanzamentoGuida.emit(int(letti * 100 / totale))

        def fatto(_percorso, errore) -> None:
            if errore is not None:
                self._mostra_riquadro(nome, GemmaRicerche.pagina_scarica(
                    nome, colori, schema, tema.ACCENTO,
                    errore="Non riesco a scaricare la Guida alle ricerche."))
                return
            self.pacchettoScaricato.emit()
            self._mostra_gemma()

        from Utility import Lingua

        scarica_jwpub(GemmaRicerche.SIMBOLO, 0, lingua=Lingua.bibbia_simbolo(),
                      completion=fatto, on_progress=avanza)

    # ------------------------------------------------------------------
    # IL MENU DEL NUMERO DEL VERSETTO
    # ------------------------------------------------------------------

    def _mostra_menu_versetto(self, x: int, y: int, verso: int,
                              ancora: str, testo: str) -> None:
        self._versetto = {"verso": verso, "ancora": ancora, "testo": testo}
        self._selezione = {"testo": testo, "paragrafo": verso, "ancora": ancora}
        punto = self.article.web.mapToGlobal(QPoint(int(x), int(y)))
        barra = BarraVersetto(self)
        barra.gemmaPremuta.connect(self._apri_gemma)
        barra.notaPremuta.connect(self._nota_versetto)
        barra.segnalibroPremuto.connect(
            lambda: self._aggiungi_segnalibro(1))
        barra.traduzioniPremute.connect(self._mostra_traduzioni)
        barra.condividiPremuto.connect(self._condividi_versetto)
        barra.copiaPremuta.connect(self._copia_versetto)
        barra.colorePremuto.connect(self._colora_versetto)
        barra.mostra_sotto(punto)

    # ------------------------------------------------------------------
    # LE LINGUE DELLE ALTRE TRADUZIONI
    # ------------------------------------------------------------------

    def _mostra_lingue(self, sostituisci: bool = False) -> None:
        from Utility import Traduzioni

        self.pannello.metti_riferimento(
            "jwl:lingue", Traduzioni.elenco_lingue(), sostituisci=sostituisci)

    def _azione_lingue(self, azione: str) -> None:
        from Utility import Traduzioni

        comando, _, argomento = azione[4:].partition("/")
        if comando == "lingue":
            self._mostra_lingue()
        elif comando == "lingua":
            Traduzioni.alterna(argomento)
            self._mostra_lingue(sostituisci=True)
        elif comando == "ordine":
            # Il nuovo ordine arriva a trascinamento finito: la pagina e' gia'
            # nell'ordine giusto, quindi non serve ridisegnarla.
            Traduzioni.riordina(argomento.split(","))
        elif comando == "ferma":
            Traduzioni.ferma(argomento)
            self._mostra_lingue(sostituisci=True)
        elif comando == "scarica":
            nome = (Lingua_nome(argomento))
            self.pannello.chiedi(
                "Scaricare la Bibbia?",
                f"Scarico la Bibbia in {nome}: {Traduzioni.TOTALE} capitoli, circa "
                "13 MB.\n\nPuoi anche non farlo: i capitoli si scaricano da soli "
                "quando li leggi.",
                "Scarica", lambda: self._avvia_scaricamento(argomento))
        elif comando == "elimina":
            nome = Lingua_nome(argomento)
            self.pannello.chiedi(
                "Eliminare la Bibbia?",
                f"Elimino dal disco la Bibbia in {nome}.\n\nSi puo' riscaricare "
                "quando vuoi.",
                "Elimina", lambda: self._elimina_lingua(argomento))

    def _avvia_scaricamento(self, simbolo: str) -> None:
        from Utility import Traduzioni

        if Traduzioni.avvia_scaricamento(simbolo, self._scaricoFinito.emit):
            self._timer_lingue.start(2000)
        self._mostra_lingue(sostituisci=True)

    def _elimina_lingua(self, simbolo: str) -> None:
        from Utility import Traduzioni

        Traduzioni.elimina(simbolo)
        self.pacchettoScaricato.emit()
        self._mostra_lingue(sostituisci=True)
        self.avviso.emit("Bibbia eliminata")

    def _scarico_finito(self, simbolo: str) -> None:
        self.pacchettoScaricato.emit()
        self.avviso.emit(f"Bibbia in {Lingua_nome(simbolo)} scaricata")
        self._aggiorna_lingue()

    def _aggiorna_lingue(self) -> None:
        """Mentre scarica, aggiorna i contatori della pagina delle lingue."""
        import json
        from Utility import Traduzioni

        corrente = self.pannello._storia[-1][0] if self.pannello._storia else ""
        in_corso = [s for s in Traduzioni.scelte() if Traduzioni.in_corso(s) is not None]
        if not in_corso:
            self._timer_lingue.stop()
            if corrente == "jwl:lingue":
                self._mostra_lingue(sostituisci=True)
            return
        if corrente != "jwl:lingue":
            return
        for simbolo in in_corso:
            testo = f"Scarico… {Traduzioni.in_corso(simbolo)}/{Traduzioni.TOTALE} capitoli"
            self.pannello.web.page().runJavaScript(
                "document.querySelectorAll('[data-stato=%s]').forEach(function(e)"
                "{e.textContent=%s});" % (json.dumps(simbolo), json.dumps(testo)))

    def _mostra_traduzioni(self) -> None:
        """Lo stesso versetto nelle lingue scelte, nel riquadro di lato."""
        from Utility import Traduzioni

        verso = self._versetto["verso"]
        libro, capitolo = int(self.pub.book or 0), int(self.pub.chapter or 0)
        nome = self._riferimento_versetto(verso)
        self._mostra_nel_riquadro(lambda: self.pannello.carica(
            f"jwl:traduzioni/{libro}/{capitolo}/{verso}",
            lambda: Traduzioni.versetto(libro, capitolo, verso, nome)))

    def _nota_versetto(self) -> None:
        from SubViews.DialoghiNote import DialogoNota
        from Utility.UserData.NoteManager import NoteManager

        info = self._versetto
        riferimento = self._riferimento_versetto(info["verso"])
        dialogo = DialogoNota(self, riferimento, f"{riferimento}\n{info['testo']}\n\n")
        if dialogo.exec() and dialogo.risultato:
            NoteManager.crea(*dialogo.risultato)
            self.segniCambiati.emit()
            self.avviso.emit("Nota aggiunta")

    def _copia_versetto(self) -> None:
        from PyQt6.QtWidgets import QApplication

        info = self._versetto
        QApplication.clipboard().setText(
            f"{info['testo']} ({self._riferimento_versetto(info['verso'])})")
        self.avviso.emit("Versetto copiato")

    def _condividi_versetto(self) -> None:
        """Testo e collegamento a jw.org negli appunti, pronti da incollare."""
        from PyQt6.QtWidgets import QApplication
        from Utility import Lingua

        info = self._versetto
        codice = (f"{int(self.pub.book or 0):02d}{int(self.pub.chapter or 0):03d}"
                  f"{info['verso']:03d}")
        link = ("https://www.jw.org/finder?srcid=jwlshare&wtlocale="
                f"{Lingua.bibbia_simbolo()}&prefer=lang&bible={codice}&pub=nwtsty")
        QApplication.clipboard().setText(
            f"{info['testo']} ({self._riferimento_versetto(info['verso'])})\n{link}")
        self.avviso.emit("Versetto e collegamento copiati: puoi incollarli dove vuoi")

    def _colora_versetto(self, colore: int) -> None:
        import json

        self.article.web.run(
            "typeof __jwlSelezionaVersetto === 'function'"
            f" ? __jwlSelezionaVersetto({json.dumps(self._versetto['ancora'])}) : false;",
            lambda ok: self._evidenzia(colore) if ok else None)

    def _chiudi_riferimento(self) -> None:
        """Il riquadro si svuota e sparisce: la pagina torna a tutta larghezza."""
        self._riquadro(False)
        QTimer.singleShot(0, self.pannello.svuota)

    def _nascondi_le_frecce(self) -> None:
        """Le frecce spariscono tutte: il puntatore non e' su nessuna."""
        for freccia in self._frecce_lato:
            freccia.setVisible(False)

    def leaveEvent(self, evento) -> None:
        """Il puntatore esce dalla schermata: le frecce spariscono."""
        self._nascondi_le_frecce()
        super().leaveEvent(evento)

    def resizeEvent(self, evento) -> None:
        """La schermata cambia misura: le frecce tornano ai loro posti."""
        super().resizeEvent(evento)
        self._metti_le_frecce_ai_posti()

    def _metti_le_frecce_ai_posti(self) -> None:
        """Le frecce ai due lati del capitolo, a meta' altezza."""
        if not self._frecce_lato:
            return
        motore = self.article.web
        alto = motore.mapTo(self, QPoint(0, 0))
        lato = _FrecciaPagina.LATO
        y = alto.y() + max(0, (motore.height() - lato) // 2)
        sinistra, destra = self._frecce_lato[0], self._frecce_lato[1]
        sinistra.setGeometry(alto.x() + 6, y, lato, lato)
        destra.setGeometry(alto.x() + motore.width() - lato - 6, y, lato, lato)

    # ------------------------------------------------------------------
    # UN GIORNO PER PAGINA E I CAPITOLI
    # ------------------------------------------------------------------

    def _aggiorna_titolo_barra(self) -> None:
        """Il titolo al centro della barra dice cosa si sta leggendo."""
        if self._titolo_barra is None:
            return
        if self._a_un_giorno and self._titolo_giorno:
            testo = self._titolo_giorno
        elif self.pub.isBible:
            testo = str(self.pub.chapter or 0)
        else:
            testo = self.document.title if self.document else ""
        self._titolo_barra.setText(testo)

    def _copri_il_capitolo(self) -> None:
        """Il capitolo si prepara sotto un velo del colore del tema (niente lampo bianco)."""
        from PyQt6.QtGui import QColor
        sfondo = tema.colori(tema.tema_attivo())["sfondo"]
        self.article.web.page().setBackgroundColor(QColor(sfondo))
        self._velo.copri()

    def _pagina_pronta(self) -> None:
        """La pagina e' pronta: nelle Scritture del giorno si mostra un giorno.

        Il documento del mese contiene tutti i giorni, uno sotto l'altro.
        La pagina e' gia' arrivata al paragrafo di oggi (`ancora`), ma
        sotto e sopra ci sono gli altri; qui si chiede alla pagina di
        lasciarne visibile uno solo.  Le frecce della barra cambiano giorno
        senza ricaricare il file.

        IL FILTRO TORNA SUL WIDGET INTERNO
        -----------------------------------
        Il widget interno di Chromium nasce quando la pagina viene
        disegnata, e il prima non c'era.  Senza il filtro su di lui il
        puntatore che si muove sulla pagina non arriva a nessuna parte,
        e le frecce ai lati non si accendono mai.
        """
        self._velo.scopri()
        self._installa_i_filtri()
        self._metti_le_frecce_ai_posti()

        # LA BARRA DEVE SAPERE DOVE SI E' LA PAGINA
        # ------------------------------------------
        # Il giro comincia quando la pagina e' pronta: prima non c'e' niente
        # da misurare, e la barra mostrerebbe un vuoto.
        if self._timer_barra is None:
            self._timer_barra = QTimer(self)
            self._timer_barra.setInterval(150)
            self._timer_barra.timeout.connect(self._chiedi_lo_scorrimento)
        self._timer_barra.start()

        if not self._a_un_giorno:
            return
        import json
        ancora = json.dumps(self.article.ancora or "")
        self.article.web.run(
            "typeof __jwlMostraGiornoDaAncora === 'function'"
            f" ? __jwlMostraGiornoDaAncora({ancora}) : null;",
            self._giorno_mostrato,
        )

    def _giorno_mostrato(self, dati) -> None:
        """Il giorno e' stato cambiato: si aggiornano titolo e frecce."""
        if not isinstance(dati, dict):
            return
        try:
            indice = int(dati.get("indice", -1))
            totale = int(dati.get("totale", 0))
        except (TypeError, ValueError):
            return
        self._giorno_corrente = indice
        self._giorni_totali = totale
        self._titolo_giorno = str(dati.get("titolo") or "")
        ancora = str(dati.get("ancora") or "")
        if ancora:
            # Se la pagina si ricarica, si torna al giorno che si stava
            # leggendo e non a quello di oggi.
            self.article.ancora = ancora
        self._aggiorna_titolo_barra()
        self._aggiorna_frecce_pagina()

    def _cambia_giorno(self, passo: int) -> None:
        if not self._a_un_giorno or self._giorni_totali <= 0:
            return
        nuovo = self._giorno_corrente + int(passo)
        if nuovo < 0 or nuovo >= self._giorni_totali:
            return
        self.article.web.run(
            "typeof __jwlMostraGiorno === 'function'"
            f" ? __jwlMostraGiorno({nuovo}) : null;",
            self._giorno_mostrato,
        )

    def _cambia_pagina(self, passo: int) -> None:
        """La freccia e' stata premuta: giorno, capitolo o pagina."""
        if self._a_un_giorno:
            self._cambia_giorno(passo)
            return
        if not self._pagine:
            return
        self.vai_a_pagina(self._indice_pagina + int(passo))

    def vai_a_pagina(self, indice: int) -> None:
        """Apre un altro capitolo nello stesso articolo.

        Non si crea una schermata nuova: la pagina, il titolo e il pannello
        sono gli stessi, cambia solo il documento.  Cosi' il pulsante
        indietro torna all'elenco dei capitoli una volta sola, anche dopo
        aver letto dieci capitoli di fila.
        """
        if not self._pagine:
            return
        if indice < 0 or indice >= len(self._pagine):
            return
        if indice == self._indice_pagina:
            return
        pagina = self._pagine[indice]
        self._indice_pagina = indice

        nuova_pub = pagina.get("pub")
        if nuova_pub is not None:
            self.pub = nuova_pub
        capitolo = pagina.get("capitolo")
        if capitolo is not None:
            self.pub.chapter = int(capitolo)
        documento = pagina.get("document")
        self.document = documento
        self.file_path = str(pagina.get("file_path") or "")

        self.article.pub = self.pub
        self.article.document = documento
        self.article.file_path = self.file_path
        self.article.ancora = str(pagina.get("ancora") or "")
        self._selezione = {"testo": "", "paragrafo": 0, "ancora": ""}
        self._chiudi_riferimento()
        self._spartito_visibile = False
        self._copri_il_capitolo()
        self.article.carica()
        if self._preferisce_spartito and self.ha_spartito():
            self.mostra_spartito(True)
        self._aggiorna_titolo_barra()
        self._aggiorna_frecce_pagina()

    def _mostra_freccia(self, numero: int, visibile: bool) -> None:
        """Dice se una delle due frecce puo' accendersi.

        NON LA MOSTRA: LA FRECCIA SI ACCENDE DA SE'
        --------------------------------------------
        Le frecce sono sempre nascoste e compaiono solo quando il
        puntatore e' sulla loro zona (vedi `_accendi_la_freccia`).  Qui si
        dice solo **se** quella freccia ha qualcosa da fare: agli estremi
        del capitolo la freccia non porta da nessuna parte, e quindi non
        si accende mai.

        Il predicato e' sulla freccia e non qui perche' a cambiare pagina
        si cambia anche il capitolo, e le frecce restano le stesse: e'
        l'unico posto dove la lista delle pagine e' la stessa.
        """
        if 0 <= numero < len(self._frecce_lato):
            freccia = self._frecce_lato[numero]
            freccia.disponibile = bool(visibile)
            if not visibile:
                freccia.setVisible(False)

    def _aggiorna_frecce_pagina(self) -> None:
        """Dice quali frecce possono accendersi, alla pagina che si guarda."""
        if not self._frecce_lato:
            return
        if self._a_un_giorno:
            valido = self._giorno_corrente >= 0 and self._giorni_totali > 0
            self._mostra_freccia(0, valido and self._giorno_corrente > 0)
            self._mostra_freccia(
                1, valido and self._giorno_corrente < self._giorni_totali - 1)
            return
        if self._pagine:
            valido = 0 <= self._indice_pagina < len(self._pagine)
            self._mostra_freccia(0, valido and self._indice_pagina > 0)
            self._mostra_freccia(
                1, valido and self._indice_pagina < len(self._pagine) - 1)
            return
        self._mostra_freccia(0, False)
        self._mostra_freccia(1, False)

    def ricarica(self) -> None:
        """Ricarica il capitolo.

        E' quello che fa il tasto dell'aggiornamento mentre si legge: il
        capitolo torna come era, con le figure di nuovo dentro e le
        sottolineature rimesse.  Non e' una schermata nuova: si sta leggendo
        lo stesso capitolo, e riaprirlo da capo farebbe perdere il posto
        dove si era arrivati.
        """
        self.article.carica()

    def imposta_dimensione_testo(self, percentuale: int) -> None:
        """Ingrandisce o riduce il testo del capitolo e del pannello.

        Qui il testo e' una pagina HTML gia' impaginata dal pacchetto, quindi
        non c'e' un `body` da cambiare come nella notizia: si usa lo zoom del
        motore, che e' la stessa cosa che fa un browser quando si preme
        Ctrl+piu'.  Si applica a entrambi i riquadri, altrimenti il capitolo
        cambierebbe misura e i versetti accanto resterebbero piccoli.

        Il valore e' una percentuale: 100 e' la misura normale.  Lo zoom
        resta sul `QWebEngineView`, quindi vale anche per le pagine che
        verranno caricate dopo, senza doverlo riapplicare a ogni capitolo.
        """
        try:
            valore = int(percentuale)
        except (TypeError, ValueError):
            valore = 100
        fattore = max(0.5, min(3.0, valore / 100.0))
        for motore in self._motori():
            try:
                motore.setZoomFactor(fattore)
            except (AttributeError, RuntimeError):
                pass

    # ------------------------------------------------------------------
    # LE SOTTOLINEATURE
    # ------------------------------------------------------------------

    def _mostra_menu_selezione(self, x: int, y: int, testo: str,
                               paragrafo: int, ancora: str,
                               evidenziata: bool = False) -> None:
        """Il menu dei colori, sotto la selezione appena fatta.

        PERCHE' QUI E NON NELLA FASCIA
        ------------------------------
        I sei colori non stanno piu' sempre in alto: senza una selezione non
        c'e' niente da colorare, e una fila di pastiglie accese su una pagina
        che non ha nessuna selezione sembra parte del testo invece che uno
        strumento.  Il menu compare **solo** quando serve, nel punto in cui
        serve, e sparisce quando si chiude.

        IL MENU E' BLOCCANTE, E VA BENE
        -------------------------------
        ``QMenu.exec`` apre un ciclo di eventi locale: la selezione dentro
        Chromium resta ferma mentre il menu e' aperto, perche' nessuno la
        tocca.  Quando l'utente sceglie un colore, ``_evidenzia`` chiama la
        pagina e la selezione e' ancora quella giusta.

        ANCHE IL SEGNALIBRO STA QUI
        ---------------------------
        Se si e' selezionato del testo, quel testo e' gia' la descrizione
        migliore del punto: il segnalibro lo usa come anteprima.  Chi vuole
        segnare un punto **senza** selezionare niente ha il pulsante nella
        fascia in alto.
        """
        # Il testo e il paragrafo arrivano gia' da Python: la pagina li ha
        # mandati al rilascio del mouse.  Si tengono qui perche' il menu' e'
        # bloccante e i comandi che partono dopo devono sapere su cosa stanno
        # lavorando.
        self._selezione = {
            "testo": testo or "",
            "paragrafo": int(paragrafo or 0),
            "ancora": ancora or "",
        }

        # Le coordinate arrivano dalla pagina e sono relative ad essa.
        punto = self.article.web.mapToGlobal(QPoint(int(x), int(y)))
        barra = BarraColori(self, con_cestino=evidenziata,
                            con_gemma=bool(self.pub.isBible))
        barra.gemmaPremuta.connect(self._apri_gemma)
        barra.colorePremuto.connect(self._evidenzia)
        barra.segnalibroRichiesto.connect(self._aggiungi_segnalibro)
        barra.togliPremuto.connect(lambda: self._evidenzia(-1))
        barra.mostra_sotto(punto)

    def _icona_colore(self, indice: int) -> QIcon:
        """Un quadratino pieno del colore della sottolineatura numero ``indice``."""
        icona = QPixmap(16, 16)
        icona.fill(highlight_color(indice))
        return QIcon(icona)

    # ------------------------------------------------------------------
    # I SEGNALIBRI
    # ------------------------------------------------------------------

    def _titolo_documento(self) -> str:
        """Il titolo da mettere accanto a una sottolineatura o a un segnalibro."""
        if self.pub.isBible:
            nome = (self.prev_text or "").strip()
            capitolo = self.pub.chapter or ""
            return f"{nome} {capitolo}".strip() or "Bibbia"
        if self.document is not None and self.document.title:
            return self.document.title
        return self.pub.displayTitle or self.pub.title or "Pubblicazione"

    def _document_id(self) -> int:
        return self.document.documentId if self.document is not None else 0

    def _aggiungi_segnalibro(self, colore: int) -> None:
        """Salva il segnalibro sulla selezione appena fatta."""
        paragrafo = int(self._selezione.get("paragrafo", 0) or 0)
        if paragrafo <= 0:
            self.avviso.emit(
                "Segnalibro non aggiunto: non riesco a capire il punto.")
            return
        salvato = BookmarkManager.add_bookmark(
            pub=self.pub,
            document_id=self._document_id(),
            identifier=paragrafo,
            title=self._titolo_documento(),
            snippet=str(self._selezione.get("testo", "")),
            color=colore,
        )
        if not salvato:
            self.avviso.emit("Segnalibro non salvato ⚠️")
            return
        self.segniCambiati.emit()
        self.avviso.emit("Segnalibro aggiunto 🔖")

    def _segnalibro_dalla_posizione(self, colore: int) -> None:
        """Segna il paragrafo che si sta guardando, senza selezione.

        La pagina sa quale paragrafo e' dentro la finestra: lo chiede a lei
        invece di indovinarlo da Python, dove non c'e' nessuna nozione di
        «dove sta guardando l'utente».
        """
        is_bible = "true" if self.pub.isBible else "false"
        self.article.web.run(
            "typeof __jwlPosizioneVisibile === 'function'"
            " ? __jwlPosizioneVisibile({}) : null;".format(is_bible),
            lambda dati: self._salva_segnalibro_posizione(dati, colore),
        )

    def _salva_segnalibro_posizione(self, dati, colore: int) -> None:
        if not isinstance(dati, dict):
            self.avviso.emit("Segnalibro non aggiunto: la pagina non risponde.")
            return
        paragrafo = int(dati.get("paragrafo", 0) or 0)
        if paragrafo <= 0:
            self.avviso.emit(
                "Segnalibro non aggiunto: non riesco a capire il punto.")
            return
        salvato = BookmarkManager.add_bookmark(
            pub=self.pub,
            document_id=self._document_id(),
            identifier=paragrafo,
            title=self._titolo_documento(),
            snippet=str(dati.get("testo", "")),
            color=colore,
        )
        if not salvato:
            self.avviso.emit("Segnalibro non salvato ⚠️")
            return
        self.segniCambiati.emit()
        self.avviso.emit("Segnalibro aggiunto 🔖")

    def menu_segnalibri(self, punto=None) -> None:
        """Il menu' dei segnalibri di questa pubblicazione.

        IL PULSANTE E' NELLA FASCIA, IL MENU' E' DI QUI
        --------------------------------------------------
        Il tasto «Segnalibri» sta adesso nella fascia viola, accanto
        all'aggiornamento e ai tre puntini: e' il posto dei comandi della
        finestra, e li' c'e' in tutte le schermate.  Il menu', pero', e' di
        questa schermata: sa di quale pubblicazione si tratta, conosce i
        segnalibri di quella e sa metterne uno qui.

        `punto` e' dove il menu' deve aprirsi: lo passa la finestra, che
        sa dove sta il suo pulsante.  Se non c'e', il menu' si apre dove
        capita.
        """
        self._menu_segnalibri(punto)

    def _menu_segnalibri(self, punto=None) -> None:
        """L'elenco dei segnalibri di questa pubblicazione.

        Il menu si costruisce **ogni volta**: un segnalibro aggiunto un minuto
        fa deve comparire subito, senza riaprire la schermata.  Costa una
        lettura del database, che qui e' poche righe.
        """
        menu = QMenu(self)
        nome_pubblicazione = (self.pub.displayTitle or self.pub.title
                              or self.pub.keySymbol)
        intestazione = menu.addAction(f"Segnalibri — {nome_pubblicazione}")
        intestazione.setEnabled(False)

        segnalibri = BookmarkManager.get_bookmarks(self.pub)
        for segno in segnalibri:
            testo = segno.title
            if segno.snippet:
                breve = " ".join(segno.snippet.split())
                if len(breve) > 60:
                    breve = breve[:60] + "…"
                testo = f"{testo} — {breve}"
            azione = menu.addAction(self._icona_colore(segno.color), testo)
            azione.triggered.connect(
                lambda _=False, s=segno: self.posizioneScelta.emit(s))

        if not segnalibri:
            vuoto = menu.addAction("Nessun segnalibro in questa pubblicazione")
            vuoto.setEnabled(False)

        menu.addSeparator()
        aggiungi = menu.addMenu(QIcon(icon("bookmark.fill", CHIARO)),
                                "Aggiungi segnalibro qui")
        for indice in range(1, len(HIGHLIGHT_HEX) + 1):
            azione = aggiungi.addAction(self._icona_colore(indice),
                                        f"Colore {indice}")
            azione.triggered.connect(
                lambda _=False, c=indice: self._segnalibro_dalla_posizione(c))

        if segnalibri:
            rimuovi = menu.addMenu(QIcon(icon("trash", CHIARO)),
                                   "Rimuovi un segnalibro")
            for segno in segnalibri:
                azione = rimuovi.addAction(self._icona_colore(segno.color),
                                           segno.title)
                azione.triggered.connect(
                    lambda _=False, s=segno: self._rimuovi_segnalibro(s))

        pulsante = self.sender()
        if punto is None:
            if isinstance(pulsante, QPushButton):
                punto = pulsante.mapToGlobal(QPoint(0, pulsante.height()))
            else:
                punto = self.mapToGlobal(QPoint(0, 0))
        menu.exec(punto)

    def _rimuovi_segnalibro(self, segno) -> None:
        BookmarkManager.remove_bookmark(segno.ID)
        self.segniCambiati.emit()
        self.avviso.emit("Segnalibro rimosso")

    def _evidenzia(self, colore: int) -> None:
        """Manda alla pagina il colore, o -1 per togliere."""
        if colore == -1:
            self.article.evidenzia(-1)
        else:
            self.article.evidenzia(colore)

    def _aggiungi_evidenziazione(self, paragrafo: int, inizio: int, fine: int,
                                 colore: int) -> None:
        """La pagina ha colorato qualcosa: si scrive nel database e si ridisegna."""
        blocco = BlockRange(identifier=paragrafo, startToken=inizio, endToken=fine)
        HighlightManager.add_highlight(
            color=colore,
            new_block_range=blocco,
            pub=self.pub,
            document_id=self._document_id(),
            snippet=str(self._selezione.get("testo", "")),
            title=self._titolo_documento(),
        )
        self.article.ripristina_evidenziazioni()
        self.segniCambiati.emit()

    # ------------------------------------------------------------------
    # LA FIGURA A SCHERMO INTERO
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # CANTICI: TESTO E SPARTITO
    # ------------------------------------------------------------------
    # Il canzoniere ha due versioni di ogni cantico: il testo digitale (la pagina
    # scaricata) e lo spartito, un'immagine SVG dentro il pacchetto
    # (``<documento>_I_sub.svg``).  Le note e le parole dello spartito sono nere,
    # quindi l'SVG sta su un riquadro bianco anche con il tema scuro.

    def _file_spartito(self):
        if self.document is None:
            return None
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        from Utility.JWPubManager import pub_dir_name
        try:
            cartella = get_documents_directory() / pub_dir_name(self.pub) / "contents"
            return next(iter(cartella.glob(f"{self.document.documentId}_*_sub.svg")), None)
        except (OSError, AttributeError):
            return None

    def ha_spartito(self) -> bool:
        return self._file_spartito() is not None

    def spartito_attivo(self) -> bool:
        return self._spartito_visibile

    def mostra_spartito(self, attivo: bool) -> None:
        """Passa dal testo allo spartito e viceversa."""
        self._preferisce_spartito = bool(attivo)
        file = self._file_spartito()
        if not attivo or file is None:
            if self._spartito_visibile:
                self._spartito_visibile = False
                self.article.carica()
            return
        import base64
        from Utility import tema
        colori = tema.colori(tema.tema_attivo())
        svg = base64.b64encode(file.read_bytes()).decode("ascii")
        pagina = (
            "<html><head><meta charset='UTF-8'><style>"
            f"body{{margin:0;padding:14px;background:{colori['sfondo']};}}"
            ".foglio{background:#ffffff;border-radius:6px;padding:14px;}"
            "img{display:block;width:100%;height:auto;}"
            "::-webkit-scrollbar{width:0;}"
            "</style></head><body><div class='foglio'>"
            f"<img src='data:image/svg+xml;base64,{svg}'></div></body></html>")
        self._spartito_visibile = True
        self.article.web.setHtml(pagina, QUrl("about:blank"))

    def immagini_della_pagina(self) -> list[bytes]:
        """I byte delle immagini che la pagina mostra, nell'ordine."""
        return [dati for dati in self.article.images if dati]

    def _voci_contenuti(self) -> list[dict]:
        """Immagini, video e audio della pagina, in ordine, pronti per l'elenco.

        Nelle pagine di adunanza, dopo i contenuti propri vengono quelli dei
        documenti citati (se il loro pacchetto e' scaricato), raggruppati per titolo.
        """
        from Utility import CatalogoMedia, JWPubManager, Lingua, MediaScaricati

        lingua = Lingua.da_numero(getattr(self.pub, "mepsLanguageId", Lingua.PREDEFINITA))

        def prepara(v: dict) -> bool:
            if v["tipo"] == "immagine":
                try:
                    with open(v["file"], "rb") as f:
                        dati = f.read()
                except OSError:
                    return False
                v.update(dati=dati, miniatura=dati)
                return True
            sigla, traccia, numero = v["sigla"], v["traccia"], v["numero"]
            formato = "VIDEO" if v["tipo"] == "video" else "AUDIO"
            titolo = ""
            if not numero:
                titolo = (CatalogoMedia.voce_di(sigla, lingua, traccia) or {}).get("title") or ""
            v["titolo"] = v["titolo"] or titolo or f"{sigla} n. {traccia}"
            v["lingua"], v["formato"] = lingua, formato
            file = None if numero else MediaScaricati.file_di(sigla, lingua, traccia, formato)
            v["file"] = str(file) if file else ""
            v["scaricato"] = file is not None
            v["miniatura"] = None
            return True

        voci: list[dict] = []
        if self.document is not None and not getattr(self.pub, "isBible", False):
            elenco = JWPubManager.contenuti_del_documento(self.pub, self.document.ID)
            if self._chiave_file_esterni() is not None:
                elenco += JWPubManager.contenuti_citati(self.pub, self.document.ID, elenco)
            voci = [v for v in elenco if prepara(v)]
        if not voci:
            for i, dati in enumerate(self.immagini_della_pagina(), start=1):
                voci.append({"tipo": "immagine", "titolo": f"Immagine {i}",
                             "dati": dati, "miniatura": dati})
        return voci

    def _chiave_file_esterni(self) -> str | None:
        """La chiave dei file esterni se la pagina e' di un'adunanza, se no None."""
        if (self.prev_text or "").strip() != "Adunanze" or self.document is None:
            return None
        from Utility import FileEsterni
        return FileEsterni.chiave(self.pub, self.document)

    def ha_contenuti(self) -> bool:
        return (self._chiave_file_esterni() is not None
                or bool(self.immagini_della_pagina()) or bool(self._voci_contenuti()))

    def apri_galleria(self) -> None:
        """I contenuti multimediali della pagina, in una schermata dedicata."""
        from SubViews.ContenutiView import ContenutiView
        voci = self._voci_contenuti()
        chiave = self._chiave_file_esterni()
        if not voci and chiave is None:
            return
        self.contenutiDaAprire.emit(
            ContenutiView(self._titolo_documento(), voci, chiave=chiave))

    def _mostra_immagine(self, grezzi: bytes) -> None:
        """Mostra una figura sopra tutto; un clic la chiude.

        DUE POSTI, NON UNO
        ------------------
        La figura va a tutto schermo **dentro l'app** — il velo, come e'
        sempre — e se c'e' uno schermo scelto nelle impostazioni va anche li',
        in una finestra tutta sua, come fanno i video.

        Non e' una cosa che sostituisce l'altra: sono due posti dove guardare
        la stessa figura, e serve avere entrambi.  Chi ha l'app davanti la
        vede nel velo; chi guarda l'altro monitor la vede li'.  Con una sola
        delle due, chi guarda l'altro schermo non vede niente e chi guarda
        l'app ha il video o la figura che gli occupa tutta la finestra.

        E si apre solo con il clic del mouse, perche' e' il clic che chiede di
        guardare una figura per bene: il velo, da solo, non toglie niente a
        nessuno e si vede gia' a schermo intero dentro l'app.
        """
        pixmap = QPixmap()
        if not pixmap.loadFromData(grezzi):
            return
        self.velo.mostra(pixmap)

