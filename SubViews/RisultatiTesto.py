#
#  RisultatiTesto.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""L'elenco a tendina dei passi di testo trovati, sotto la barra di ricerca.

Non e' una schermata: e' un riquadro che si apre sotto la barra della Biblioteca
mentre si scrive, con pochi risultati (versetti e articoli) e le parole trovate
in grassetto.  Premere una riga manda il risultato a chi ascolta; non prende il
focus, cosi' la barra resta quella in cui si sta scrivendo.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QToolButton, QPushButton, QVBoxLayout

MAX_RIGHE = 3
MAX_RIGHE_WEB = 5


class _Riga(QFrame):
    premuta = Signal()
    #: Voce scelta nei tre puntini: "apri" o "scarica"
    azione = Signal(str)

    def __init__(self, titolo: str, anteprima: str, parent=None,
                 con_menu: bool = False, miniatura: bool = False,
                 scaricabile: bool = False, preferito: bool = False) -> None:
        self._preferito = preferito
        super().__init__(parent)
        self.setObjectName("rigaPiatta")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        esterna = QHBoxLayout(self)
        esterna.setContentsMargins(10, 6, 6, 6)
        esterna.setSpacing(10)
        if scaricabile:
            # La nuvoletta con la freccia in giu', come nelle card di Pubblicazioni e Video.
            from Utility.Stuff import icon
            # Identico al tasto delle card (MediaView._aggiungi_comandi): stesso nome
            # di stile, piatto, 20x20, nuvoletta bianca da 16.
            self.scarica = QPushButton(self)
            self.scarica.setObjectName("bottoneCard")
            self.scarica.setFixedSize(20, 20)
            self.scarica.setFlat(True)
            self.scarica.setIcon(icon("cloud.download", "#ffffff", 16))
            self.scarica.setToolTip("Scarica")
            self.scarica.setCursor(Qt.CursorShape.PointingHandCursor)
            self.scarica.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.scarica.clicked.connect(lambda: self.azione.emit("scarica"))
        self.miniatura = None
        if miniatura:
            # L'anteprima a sinistra, come sul sito (riempita quando arriva l'immagine).
            self.miniatura = QLabel(self)
            self.miniatura.setFixedSize(96, 54)
            self.miniatura.setStyleSheet("background: rgba(128,128,128,0.15); border-radius: 4px;")
            esterna.addWidget(self.miniatura, 0, Qt.AlignmentFlag.AlignTop)
        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)
        t = QLabel(titolo, self)
        t.setObjectName("titoloNovita")
        a = QLabel(anteprima, self)
        a.setObjectName("sottoCard")
        a.setTextFormat(Qt.TextFormat.RichText)
        a.setWordWrap(True)
        # Il testo lungo non deve allargare la riga: i tasti a destra restano visibili.
        t.setMinimumWidth(10)
        a.setMinimumWidth(10)
        from PyQt6.QtWidgets import QSizePolicy
        a.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        colonna.addWidget(t)
        colonna.addWidget(a)
        self._colonna_testo = colonna
        self.barra = None
        esterna.addLayout(colonna, 1)
        if con_menu:
            # I TRE PUNTINI: aprire subito dal sito o scaricare, senza tornare indietro.
            tre = QToolButton(self)
            tre.setText("⋮")
            tre.setToolTip("Apri o scarica")
            tre.setAutoRaise(True)
            tre.setCursor(Qt.CursorShape.PointingHandCursor)
            tre.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            tre.clicked.connect(lambda: self._menu(tre))
            esterna.addWidget(tre, 0, Qt.AlignmentFlag.AlignTop)
        if scaricabile:
            # Tutto a destra, dopo i tre puntini.
            esterna.addWidget(self.scarica, 0, Qt.AlignmentFlag.AlignVCenter)

    def avvia_barra(self) -> None:
        """La barra «sto scaricando», la stessa delle card (scaricaBarraCard)."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QProgressBar
        if self.barra is None:
            self.barra = QProgressBar(self)
            self.barra.setObjectName("scaricaBarraCard")
            self.barra.setTextVisible(False)
            self.barra.setRange(0, 0)
            self.barra.setFixedHeight(5)
            self._colonna_testo.addWidget(self.barra)
        self.barra.show()
        if getattr(self, "scarica", None) is not None:
            self.scarica.setEnabled(False)
        # Se per qualche motivo non finisce mai, dopo 5 minuti si toglie.
        QTimer.singleShot(300000, self.ferma_barra)

    def ferma_barra(self) -> None:
        try:
            if self.barra is not None:
                self.barra.hide()
        except RuntimeError:
            pass

    def imposta_stato(self, scaricato: bool) -> None:
        """Gia' scaricato: la nuvoletta diventa una spunta, senza azione."""
        b = getattr(self, "scarica", None)
        if b is None:
            return
        from Utility.Stuff import icon, icona_tabler
        if scaricato:
            self.ferma_barra()
            b.setIcon(icona_tabler("check-circle", "#8fd18f", 16))
            b.setToolTip("Già scaricato")
            b.setEnabled(False)
        else:
            b.setIcon(icon("cloud.download", "#ffffff", 16))
            b.setToolTip("Scarica")
            if self.barra is None or not self.barra.isVisible():
                b.setEnabled(True)

    def imposta_immagine(self, pixmap) -> None:
        if self.miniatura is not None and not pixmap.isNull():
            self.miniatura.setPixmap(pixmap.scaled(
                self.miniatura.width(), self.miniatura.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation))

    def _menu(self, bottone) -> None:
        menu = QMenu(self)
        menu.addAction("Apri subito").triggered.connect(lambda: self.azione.emit("apri"))
        menu.addAction("Scarica").triggered.connect(lambda: self.azione.emit("scarica"))
        menu.addAction("Togli dai Preferiti" if self._preferito else "Metti nei Preferiti"
                       ).triggered.connect(lambda: self.azione.emit("preferito"))
        menu.exec(bottone.mapToGlobal(bottone.rect().bottomLeft()))

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.premuta.emit()


class RisultatiTesto(QFrame):
    """Il riquadro.  ``scelto`` porta il dizionario del risultato premuto."""

    scelto = Signal(dict)
    #: Un'azione dei tre puntini di un risultato online: ("apri"|"scarica", risultato)
    azioneWeb = Signal(str, dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("popupRicerca")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._colonna = QVBoxLayout(self)
        self._colonna.setContentsMargins(4, 4, 4, 4)
        self._colonna.setSpacing(0)
        self.hide()

    def mostra(self, risultati: list[dict], sotto, larghezza: int,
               web: list[dict] | None = None, stato: str = "") -> None:
        """Riempie e apre il riquadro; ``sotto`` e' il punto (nel padre) dove appoggiarlo.

        Prima i risultati nel testo scaricato (``risultati``), poi quelli di
        jw.org (``web``, solo se c'e' internet).  Sono lo stesso riquadro: una
        ricerca sola, due provenienze.
        """
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().deleteLater()
        web = web or []
        if not risultati and not web and not stato:
            self.hide()
            return
        if risultati:
            intestazione = QLabel("Nel testo scaricato", self)
            intestazione.setObjectName("nota")
            intestazione.setContentsMargins(10, 4, 10, 2)
            self._colonna.addWidget(intestazione)
            for r in risultati[:MAX_RIGHE]:
                riga = _Riga(r["titolo"], r["anteprima"], self)
                riga.premuta.connect(lambda r=r: self._premuto(r))
                self._colonna.addWidget(riga)
        if web:
            intestazione = QLabel("Su jw.org", self)
            intestazione.setObjectName("nota")
            intestazione.setContentsMargins(10, 6, 10, 2)
            self._colonna.addWidget(intestazione)
            for r in web[:MAX_RIGHE_WEB]:
                titolo = r["titolo"] + (f"  ·  {r['contesto']}" if r.get("contesto") else "")
                # Una pubblicazione (non un articolo): ha i tre puntini.
                e_pub = bool(r.get("sigla")) and not r.get("docid")
                riga = _Riga(titolo, r.get("anteprima", ""), self, con_menu=e_pub)
                riga.premuta.connect(lambda r=r: self._premuto(r))
                riga.azione.connect(lambda a, r=r: self._azione(a, r))
                self._colonna.addWidget(riga)
        if stato:           # cosa sta succedendo con la parte online
            nota = QLabel(stato, self)
            nota.setObjectName("nota")
            nota.setContentsMargins(10, 6, 10, 4)
            self._colonna.addWidget(nota)
        # I widget aggiunti a un riquadro GIA' visibile restano nascosti finche' il
        # ciclo degli eventi non li mostra, e `adjustSize` li salterebbe: il riquadro
        # si ridurrebbe a una striscia vuota.  Si mostrano subito, a mano.
        for i in range(self._colonna.count()):
            figlio = self._colonna.itemAt(i).widget()
            if figlio is not None:
                figlio.show()
        self.setFixedWidth(max(300, larghezza))
        # Mai piu' alto dello spazio sotto la barra: si tolgono le ultime righe.
        padre = self.parentWidget()
        if padre is not None:
            libero = padre.height() - sotto.y() - 8
            while self._colonna.count() > 2 and self._colonna.sizeHint().height() > libero:
                ultimo = self._colonna.takeAt(self._colonna.count() - 1).widget()
                if ultimo is not None:
                    ultimo.hide()
                    ultimo.deleteLater()
        self._colonna.activate()
        self.adjustSize()
        self.move(sotto)
        self.show()
        self.raise_()

    def _azione(self, azione: str, risultato: dict) -> None:
        self.hide()
        self.azioneWeb.emit(azione, risultato)

    def _premuto(self, risultato: dict) -> None:
        self.hide()
        self.scelto.emit(risultato)
