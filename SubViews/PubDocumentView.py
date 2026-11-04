#
#  PubDocumentView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 20/08/21.
#

"""I capitoli di una pubblicazione.

Un capitolo e' una riga, con il titolo di contesto davanti quando c'e'.  Il
titolo di contesto (``ContextTitle``) e' il nome del capitolo superiore: in
un articolo di rivista dice in che numero e' comparso, e senza quello un
elenco di titoli non si distingue.

IL NUMERO CHE CONTA
-------------------
Il pulsante apre il capitolo, e il capitolo si cerca con
``MepsDocumentId``, non con ``DocumentId``.  Sono due numeri diversi che non
coincidono mai: il primo vale dentro un pacchetto solo, il secondo e' quello
della URL su wol.jw.org.  Prendere il numero sbagliato non da un errore, da
una pagina vuota.
"""

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Utility.JWPubManager import JWPubManager
from Utility.Stuff import icon, CHIARO


class PubDocumentView(QWidget):
    """L'elenco dei capitoli di una pubblicazione."""

    #: Un capitolo e' stato scelto
    documentChosen = Signal(object)
    #: Si torna all'elenco delle pubblicazioni
    goBack = Signal()

    def __init__(self, pub, parent=None) -> None:
        super().__init__(parent)
        self.pub = pub
        self.documents = JWPubManager.get_documents(pub=pub)

        scorribile = QScrollArea(self)
        scorribile.setWidgetResizable(True)
        interno = QWidget()
        elenco = QVBoxLayout(interno)
        elenco.setContentsMargins(10, 10, 10, 10)

        # LE RIGHE SONO RIGHE, E NON TESTO SU UN FONDO
        # ------------------------------------------------
        # Prima erano `QPushButton` piatti con uno stile scritto a mano
        # («text-align: left; padding: 6px»): senza fondo, senza bordo, con il
        # testo del colore del testo su uno sfondo scuro.  Il risultato era
        # una schermata spoglia che non sembrava dell'applicazione, e il testo
        # piatto su uno sfondo piatto si leggeva come un campo nel quale si
        # puo' scrivere.
        #
        # Adesso il nome `capitoloPub` e il foglio di stile fanno il disegno, e
        # qui dentro c'e' solo il testo e il collegamento.  E' la stessa cosa
        # che vale per `#rigaMedia` e per le card: una riga che si preme ha lo
        # stesso aspetto ovunque, altrimenti ogni elenco del programma ha un
        # aspetto suo e non si capisce che siano la stessa cosa.
        for documento in self.documents:
            testo = (f"{documento.contextTitle} - {documento.title}"
                     if documento.contextTitle else documento.title)
            pulsante = QPushButton(testo, interno)
            pulsante.setObjectName("capitoloPub")
            pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
            pulsante.clicked.connect(
                lambda _=False, d=documento: self.documentChosen.emit(d))
            elenco.addWidget(pulsante)

        elenco.addStretch(1)
        scorribile.setWidget(interno)

        disposizione = QVBoxLayout(self)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.addWidget(scorribile)

    def toolbar(self, andata=None) -> list:
        """Il pulsante "indietro" e il nome della pubblicazione."""
        from PyQt6.QtWidgets import QToolBar

        barra = QToolBar(self)
        barra.setMovable(False)
        indietro = QPushButton(icon("chevron.left", CHIARO), "  Pubblicazioni", self)
        indietro.clicked.connect(self.goBack.emit)
        barra.addWidget(indietro)
        barra.addSeparator()
        titolo = QPushButton(self.pub.displayTitle, self)
        titolo.setStyleSheet("font-size: 18px; font-weight: 700; text-align: left;")
        titolo.setFlat(True)
        barra.addWidget(titolo)
        return [barra]