#
#  BibleBooksView.swift -> BibleBooksView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""I 66 libri della Bibbia, in due gruppi.

Il gruppo e' deciso dall'indice, non dal nome: i primi 39 sono
Scritture Ebraico-Aramaiche, gli ultimi 27 Scritture Greche Cristiane.  Lo
stesso criterio del progetto originale, che scriveva i due intervalli
esplicitamente (``ForEach(0...38)`` e ``ForEach(39...65)``) e per questo non
poteva sbagliarsi.

Tre colori, non uno.  Non e' una decorazione: distingue i tre gruppi di
libri che il testo biblico usa (Torah, Profeti, Scritti, e poi i Vangeli, le
Lettere, l'Apocalisse).  Ogni libro ha il suo colore e resta quello.

I COLORI SONO QUI, IN UN ELENCO
-------------------------------
``bibleBookColors`` e' un elenco di 66 numeri, e i numeri sono 1, 2 o 3.  La
casa dei colori e' dentro questa funzione.  Se un domani l'elenco non
abbastanza lungo, ``getBibleColor`` legge oltre la fine e il libro sparisce
senza dire niente: e' una delle trappole elencate in COME-FUNZIONA.txt
sezione 14, "un elenco di nomi e' una rete con i buchi".
"""

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (QBoxLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from Utility.Stuff import Stuff
from Utility.Structures.ButtonStyle import bible_button

# Un colore per libro: 1, 2 o 3.  66 numeri, nell'ordine dei libri.
BIBLE_BOOK_COLORS = [
    1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3,
    3, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 1,
]

# I tre colori dei tre gruppi, presi dagli asset originali.
COLORI_GRUPPI = {1: 0x3B3547, 2: 0x746B84, 3: 0x544C63}
COLORE_SCONOSCIUTO = 0x0000FF

# Dove finisce il primo gruppo.  39 libri ebraico-aramaici, 27 greci cristiani.
PRIMO_GROUP_FINE = 38


#: Le misure dell'originale (pixel logici): ogni libro e' un riquadro 176x50, con
#: 2 pixel fra l'uno e l'altro; le Scritture Ebraico-Aramaiche stanno su 4
#: colonne, le Greche Cristiane su 3, affiancate.
LARGHEZZA_LIBRO = 176
ALTEZZA_LIBRO = 50
DISTANZA = 2
COLONNE_EBRAICHE = 4
COLONNE_GRECHE = 3
MARGINE = 24
VUOTO_FRA_I_GRUPPI = 26


class _SchedaBibbia(QLabel):
    """Una scheda: stessi nomi di oggetto e stile delle tab della Biblioteca."""

    clic = Signal(int)

    def __init__(self, indice: int, testo: str) -> None:
        super().__init__(testo.upper())
        self._indice = indice
        self.setObjectName("tab")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def attendi(self, attiva: bool) -> None:
        nome = "tabAttiva" if attiva else "tab"
        if self.objectName() != nome:
            self.setObjectName(nome)
            self.style().unpolish(self)
            self.style().polish(self)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self._indice)
        super().mousePressEvent(evento)


class _PaginaLibri(QScrollArea):
    """La pagina scorrevole dei libri: avvisa quando cambia la larghezza."""

    def __init__(self, su_larghezza, padre=None) -> None:
        super().__init__(padre)
        self._su_larghezza = su_larghezza

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self._su_larghezza(self.viewport().width())


class BibleBooksView(QWidget):
    """La griglia dei 66 libri: i due gruppi affiancati, come nell'originale."""

    bookChosen = Signal(int)
    #: Un documento delle schede Introduzione / Indice / Appendici: (meps, titolo).
    documentChosen = Signal(int, str)

    def __init__(self, bible_books, parent=None, sezioni=None, titoli=None) -> None:
        super().__init__(parent)
        self.bible_books = bible_books
        self._titoli = titoli or ["SCRITTURE EBRAICO-ARAMAICHE", "SCRITTURE GRECHE CRISTIANE"]
        self._sezioni = list(sezioni or [])
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.setSpacing(0)
        self._pila = QStackedWidget(self)
        if len(self._sezioni) == 6:
            esterno.addWidget(self._barra_schede())
        esterno.addWidget(self._pila, 1)
        self._pila.addWidget(self._pagina_libri())
        self._pagina_elenco = None
        self._scegli(1 if len(self._sezioni) == 6 else 0)

    def _barra_schede(self) -> QWidget:
        """Le schede nello stesso stile delle tab della Biblioteca: barra dritta."""
        from Utility import tema
        barra = QWidget(self)
        tema.sfondo(barra, "strisciaTab")
        barra.setFixedHeight(48)
        riga = QHBoxLayout(barra)
        riga.setContentsMargins(18, 0, 18, 0)
        riga.setSpacing(0)
        self._schede = []
        for posizione, (testo, _) in enumerate(self._sezioni):
            scheda = _SchedaBibbia(posizione, testo)
            scheda.clic.connect(self._scegli)
            self._schede.append(scheda)
            riga.addWidget(scheda)
        riga.addStretch(1)
        return barra

    def _scegli(self, posizione: int) -> None:
        """0 Introduzione, 1 Libri, 2 Indice, 3-5 Appendici A, B, C."""
        for i, scheda in enumerate(getattr(self, "_schede", [])):
            scheda.attendi(i == posizione)
        if posizione == 1 or len(self._sezioni) != 6:
            self._pila.setCurrentIndex(0)
            return
        voci = self._sezioni[posizione][1]
        if self._pagina_elenco is not None:
            self._pila.removeWidget(self._pagina_elenco)
            self._pagina_elenco.deleteLater()
        self._pagina_elenco = self._pagina_documenti(voci)
        self._pila.addWidget(self._pagina_elenco)
        self._pila.setCurrentWidget(self._pagina_elenco)

    def _pagina_documenti(self, voci) -> QWidget:
        scorribile = QScrollArea(self)
        scorribile.setWidgetResizable(True)
        interno = QWidget()
        colonna = QVBoxLayout(interno)
        colonna.setContentsMargins(MARGINE, 12, MARGINE, MARGINE)
        colonna.setSpacing(0)
        colonna.setAlignment(Qt.AlignmentFlag.AlignTop)
        for meps, titolo, livello in voci:
            if not meps:
                intestazione = QLabel(titolo)
                intestazione.setStyleSheet(
                    "font-size: 12px; font-weight: 700; background: transparent; "
                    f"padding: 16px 6px 4px {6 + 16 * livello}px;")
                colonna.addWidget(intestazione)
                continue
            riga = QPushButton(titolo)
            riga.setFlat(True)
            riga.setCursor(Qt.CursorShape.PointingHandCursor)
            riga.setFixedHeight(44)
            riga.setStyleSheet(
                "QPushButton { text-align: left; background: transparent; border: none; "
                "border-bottom: 1px solid rgba(128,128,128,0.25); font-size: 14px; "
                f"padding: 0 6px 0 {6 + 16 * livello}px; }} "
                "QPushButton:hover { background: rgba(128,128,128,0.12); }")
            riga.clicked.connect(lambda _=False, m=meps, t=titolo: self.documentChosen.emit(m, t))
            colonna.addWidget(riga)
        scorribile.setWidget(interno)
        return scorribile

    def _pagina_libri(self) -> QWidget:
        scorribile = _PaginaLibri(self._adatta_ai_gruppi, self)
        scorribile.setWidgetResizable(True)
        interno = QWidget()
        pagina = QBoxLayout(QBoxLayout.Direction.LeftToRight, interno)
        self._pagina_libri_layout = pagina
        pagina.setContentsMargins(MARGINE, 18, MARGINE, MARGINE)
        pagina.setSpacing(VUOTO_FRA_I_GRUPPI)
        pagina.setAlignment(Qt.AlignmentFlag.AlignTop)
        if self.bible_books:
            pagina.addLayout(self._gruppo(
                self._titoli[0], 0, PRIMO_GROUP_FINE, COLONNE_EBRAICHE), 0)
            pagina.addLayout(self._gruppo(
                self._titoli[1], PRIMO_GROUP_FINE + 1,
                len(self.bible_books) - 1, COLONNE_GRECHE), 0)
        pagina.addStretch(1)
        scorribile.setWidget(interno)
        return scorribile

    def _adatta_ai_gruppi(self, larghezza: int) -> None:
        """Finestra stretta: Scritture Greche sotto quelle Ebraiche.

        Affiancati servono due gruppi di colonne piu' i margini.  Se la
        finestra e' piu' stretta (metà schermo) i gruppi si impilano e non
        serve scorrere in orizzontale; a tutto schermo restano affiancati.
        L'ordine dei libri non cambia.
        """
        pagina = getattr(self, "_pagina_libri_layout", None)
        if pagina is None:
            return
        passo = LARGHEZZA_LIBRO + DISTANZA
        serve = (2 * MARGINE + COLONNE_EBRAICHE * passo + VUOTO_FRA_I_GRUPPI
                 + COLONNE_GRECHE * passo)
        direzione = (QBoxLayout.Direction.LeftToRight if larghezza >= serve
                     else QBoxLayout.Direction.TopToBottom)
        if pagina.direction() != direzione:
            pagina.setDirection(direzione)

    def _gruppo(self, titolo: str, primo: int, ultimo: int, colonne: int) -> QVBoxLayout:
        colonna = QVBoxLayout()
        colonna.setSpacing(10)
        colonna.setAlignment(Qt.AlignmentFlag.AlignTop)
        colonna.addWidget(self._titolo(titolo))
        colonna.addWidget(self._griglia(primo, ultimo, colonne), 0, Qt.AlignmentFlag.AlignTop)
        colonna.addStretch(1)
        return colonna

    @staticmethod
    def _titolo(testo: str) -> QLabel:
        etichetta = QLabel(testo)
        etichetta.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        etichetta.setStyleSheet(
            "font-size: 15px; font-weight: 600; background: transparent;")
        return etichetta

    def _griglia(self, primo: int, ultimo: int, colonne: int) -> QWidget:
        """La griglia dei libri da ``primo`` a ``ultimo``, su ``colonne`` colonne."""
        contenitore = QWidget()
        griglia = QGridLayout(contenitore)
        griglia.setContentsMargins(0, 0, 0, 0)
        griglia.setSpacing(DISTANZA)

        colonna = 0
        riga = 0
        for indice in range(primo, ultimo + 1):
            if indice >= len(self.bible_books):
                break
            libro = self.bible_books[indice]
            colore = (BIBLE_BOOK_COLORS[indice]
                      if indice < len(BIBLE_BOOK_COLORS) else 0)
            pulsante = bible_button(libro.shortName, self._colore(colore))
            pulsante.setFixedSize(LARGHEZZA_LIBRO, ALTEZZA_LIBRO)
            pulsante.clicked.connect(lambda _=False, i=indice: self.bookChosen.emit(i))
            griglia.addWidget(pulsante, riga, colonna)
            colonna += 1
            if colonna == colonne:
                colonna = 0
                riga += 1
        return contenitore

    @staticmethod
    def _colore(numero: int):
        return Stuff.hex_color(COLORI_GRUPPI.get(numero, COLORE_SCONOSCIUTO))