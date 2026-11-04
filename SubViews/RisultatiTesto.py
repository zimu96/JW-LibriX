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
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

MAX_RIGHE = 6


class _Riga(QFrame):
    premuta = Signal()

    def __init__(self, titolo: str, anteprima: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rigaPiatta")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(10, 6, 10, 6)
        colonna.setSpacing(1)
        t = QLabel(titolo, self)
        t.setObjectName("titoloNovita")
        a = QLabel(anteprima, self)
        a.setObjectName("sottoCard")
        a.setTextFormat(Qt.TextFormat.RichText)
        a.setWordWrap(True)
        colonna.addWidget(t)
        colonna.addWidget(a)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.premuta.emit()


class RisultatiTesto(QFrame):
    """Il riquadro.  ``scelto`` porta il dizionario del risultato premuto."""

    scelto = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("popupRicerca")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._colonna = QVBoxLayout(self)
        self._colonna.setContentsMargins(4, 4, 4, 4)
        self._colonna.setSpacing(0)
        self.hide()

    def mostra(self, risultati: list[dict], sotto, larghezza: int) -> None:
        """Riempie e apre il riquadro; ``sotto`` e' il punto (nel padre) dove appoggiarlo."""
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().deleteLater()
        if not risultati:
            self.hide()
            return
        intestazione = QLabel("Nel testo", self)
        intestazione.setObjectName("nota")
        intestazione.setContentsMargins(10, 4, 10, 2)
        self._colonna.addWidget(intestazione)
        for r in risultati[:MAX_RIGHE]:
            riga = _Riga(r["titolo"], r["anteprima"], self)
            riga.premuta.connect(lambda r=r: self._premuto(r))
            self._colonna.addWidget(riga)
        self.setFixedWidth(max(300, larghezza))
        self.adjustSize()
        self.move(sotto)
        self.show()
        self.raise_()

    def _premuto(self, risultato: dict) -> None:
        self.hide()
        self.scelto.emit(risultato)
