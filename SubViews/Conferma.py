#
#  Conferma.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La domanda sì/no dell'app: un riquadro viola dentro la finestra."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from Utility import tema


class ConfermaApp(QFrame):
    """Una domanda sì/no dentro l'app, nello stile viola (niente finestre di sistema).

    E' un riquadro figlio di ``padre``: copre tutto il padre e lo segue quando
    cambia misura.  Non blocca: ``su_si`` parte solo se si preme il pulsante.
    """

    @staticmethod
    def chiedi(padre, titolo: str, testo: str, si: str, su_si) -> "ConfermaApp":
        for vecchia in padre.findChildren(ConfermaApp):
            vecchia._chiudi()
        return ConfermaApp(padre, titolo, testo, si, su_si)

    def eventFilter(self, oggetto, evento) -> bool:
        if evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def __init__(self, padre, titolo: str, testo: str, si: str, su_si) -> None:
        super().__init__(padre)
        self.setObjectName("velo")
        self.setStyleSheet("#velo { background-color: rgba(0, 0, 0, 150); }")
        scheda = QFrame(self)
        scheda.setObjectName("scheda")
        scheda.setFixedWidth(340)
        scheda.setStyleSheet(
            "#scheda { background-color: #2b2b2b; border-radius: 10px; }"
            " #scheda QLabel { color: #f2f2f2; background: transparent; }"
            f" #testata {{ background-color: {tema.ACCENTO};"
            " border-top-left-radius: 10px; border-top-right-radius: 10px; }"
            " QPushButton { border: none; border-radius: 6px; padding: 9px 18px;"
            " font-weight: 700; color: #ffffff; }"
            f" #si {{ background-color: {tema.ACCENTO}; }}"
            " #si:hover { background-color: #7a49a6; }"
            " #no { background-color: #444444; } #no:hover { background-color: #555555; }")
        colonna = QVBoxLayout(scheda)
        colonna.setContentsMargins(0, 0, 0, 16)
        colonna.setSpacing(12)
        testata = QFrame(scheda)
        testata.setObjectName("testata")
        riga_testata = QHBoxLayout(testata)
        riga_testata.setContentsMargins(16, 12, 16, 12)
        titolo_label = QLabel(titolo, testata)
        titolo_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        riga_testata.addWidget(titolo_label)
        colonna.addWidget(testata)
        corpo = QLabel(testo, scheda)
        corpo.setWordWrap(True)
        corpo.setContentsMargins(16, 0, 16, 0)
        colonna.addWidget(corpo)
        pulsanti = QHBoxLayout()
        pulsanti.setContentsMargins(16, 0, 16, 0)
        pulsanti.addStretch(1)
        no = QPushButton("Annulla", scheda)
        no.setObjectName("no")
        conferma = QPushButton(si, scheda)
        conferma.setObjectName("si")
        for bottone in (no, conferma):
            bottone.setCursor(Qt.CursorShape.PointingHandCursor)
            pulsanti.addWidget(bottone)
        colonna.addLayout(pulsanti)
        no.clicked.connect(self._chiudi)
        conferma.clicked.connect(lambda: (self._chiudi(), su_si()))
        esterno = QVBoxLayout(self)
        esterno.addWidget(scheda, 0, Qt.AlignmentFlag.AlignCenter)
        padre.installEventFilter(self)
        self.setGeometry(padre.rect())
        self.show()
        self.raise_()

    def _chiudi(self) -> None:
        self.parentWidget().removeEventFilter(self)
        self.hide()
        self.deleteLater()
