#
#  BibleChaptersView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""I capitoli di un libro.

Una griglia di numeri, e nient'altro.  Il numero di capitoli lo dice la
query dei libri (``MAX(ChapterNumber)``), quindi qui non si deve sapere
quanti capitoli ha il Salterio: si mettono tanti pulsanti quanti ne sono
stati trovati, e il libro giusto ha i capitoli giusti.

IL COLORE DEI CAPITOLI
---------------------
Qui, a differenza dei libri, il colore serve a una cosa sola: i capitoli
lunghi hanno il numero su due righe (``Mela``, 10 capitoli, sta stretto in
una casella piccola).  E' una sciocchezza, ma e' quello che faceva l'app
originale e si vede subito.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget

from Utility.Structures.ButtonStyle import bible_button

# Le colonne della griglia dei capitoli.
COLONNE = 12
# La dimensione della casella, come nel LazyVGrid (minimo 40, distanza 20).
CASELLA = 48
SPAZIO = 12

# I colori: 1 scuro, 2 medio chiaro, 3 grigio.
COLORI = {1: 0x3B3547, 2: 0x746B84, 3: 0x544C63}
COLORI_ALTERNATIVI = [1, 2, 3, 2]


class BibleChaptersView(QWidget):
    """La griglia dei capitoli di un libro."""

    #: Un capitolo e' stato scelto
    chapterChosen = Signal(int)

    def __init__(self, bible_book, parent=None) -> None:
        super().__init__(parent)
        self.bible_book = bible_book

        scorribile = QScrollArea(self)
        scorribile.setWidgetResizable(True)
        interno = QWidget()
        griglia = QGridLayout(interno)
        griglia.setSpacing(SPAZIO)

        for numero in range(1, (bible_book.chapters or 0) + 1):
            colore = COLORI[COLORI_ALTERNATIVI[(numero - 1) % len(COLORI_ALTERNATIVI)]]
            pulsante = bible_button(str(numero), self._colore(colore))
            pulsante.setFixedSize(CASELLA, CASELLA)
            pulsante.clicked.connect(lambda _=False, n=numero: self.chapterChosen.emit(n))
            griglia.addWidget(pulsante, (numero - 1) // COLONNE,
                              (numero - 1) % COLONNE)
        # Le righe restano alla misura della casella, in alto a sinistra:
        # senza questo la griglia si allarga a tutta l'altezza della finestra.
        griglia.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        griglia.setContentsMargins(SPAZIO, SPAZIO, SPAZIO, SPAZIO)

        scorribile.setWidget(interno)
        disposizione = QVBoxLayout(self)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.addWidget(scorribile)

    def toolbar(self, andata=None) -> list:
        """Solo il nome del libro: per tornare indietro ci sono le frecce della fascia."""
        from PyQt6.QtWidgets import QPushButton, QToolBar

        barra = QToolBar(self)
        barra.setMovable(False)
        titolo = QPushButton(self.bible_book.fullName, self)
        titolo.setStyleSheet("font-size: 18px; font-weight: 700; text-align: left;")
        titolo.setFlat(True)
        barra.addWidget(titolo)
        return [barra]

    @staticmethod
    def _colore(numero: int):
        from Utility.Stuff import Stuff
        return Stuff.hex_color(COLORI.get(numero, COLORI[1]))