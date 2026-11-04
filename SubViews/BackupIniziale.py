#
#  BackupIniziale.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il riquadro «Vuoi importare il backup della vecchia versione?».

Compare all'apertura, dentro la finestra e nello stile dell'app (come
``ConfermaApp``: niente finestra del sistema).  La casella «Non mostrare piu'»
si ricorda in ``impostazioni.json`` con la chiave ``backup_iniziale_nascosto``
e vale qualunque pulsante si prema.  Se non si spunta, alla prossima apertura
ricompare.
"""
from __future__ import annotations

import json

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

from Utility import tema

CHIAVE = "backup_iniziale_nascosto"


def _file():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / "impostazioni.json"


def nascosto() -> bool:
    try:
        percorso = _file()
        if percorso.is_file():
            return bool(json.loads(percorso.read_text(encoding="utf-8")).get(CHIAVE, False))
    except (OSError, ValueError):
        pass
    return False


def imposta_nascosto(valore: bool) -> None:
    try:
        percorso = _file()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        dati = {}
        if percorso.is_file():
            try:
                dati = json.loads(percorso.read_text(encoding="utf-8"))
            except ValueError:
                dati = {}
        dati[CHIAVE] = bool(valore)
        percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a salvare la scelta ⚠️  {errore}")


class BackupIniziale(QFrame):
    """Il riquadro sopra la finestra, con il velo scuro dietro."""

    @staticmethod
    def mostra_se_serve(padre, su_importa) -> "BackupIniziale | None":
        """Lo mostra se l'utente non ha detto «non mostrare piu'»."""
        if nascosto():
            return None
        for vecchio in padre.findChildren(BackupIniziale):
            vecchio._chiudi()
        return BackupIniziale(padre, su_importa)

    def eventFilter(self, oggetto, evento) -> bool:
        if evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def __init__(self, padre, su_importa) -> None:
        super().__init__(padre)
        self.setObjectName("velo")
        self.setStyleSheet("#velo { background-color: rgba(0, 0, 0, 150); }")
        scheda = QFrame(self)
        scheda.setObjectName("scheda")
        scheda.setFixedWidth(400)
        scheda.setStyleSheet(
            "#scheda { background-color: #2b2b2b; border-radius: 10px; }"
            " #scheda QLabel { color: #f2f2f2; background: transparent; }"
            " #scheda QCheckBox { color: #cfcfcf; spacing: 8px; }"
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
        titolo = QLabel("Importare il backup?", testata)
        titolo.setStyleSheet("font-size: 15px; font-weight: 700;")
        riga_testata.addWidget(titolo)
        colonna.addWidget(testata)

        corpo = QLabel(
            "Vuoi importare il backup della vecchia versione di JW Library "
            "(file .jwlibrary di Android, Windows, iPhone o iPad)?\n\n"
            "Si portano i preferiti, i segnalibri, le sottolineature e gli "
            "appunti. Le pubblicazioni non si scaricano: i preferiti restano "
            "nella Home con la nuvoletta per scaricarli.\n\n"
            "Lo puoi fare anche dopo, da Impostazioni \u203a Backup.", scheda)
        corpo.setWordWrap(True)
        corpo.setContentsMargins(16, 0, 16, 0)
        colonna.addWidget(corpo)

        self._casella = QCheckBox("Non mostrare pi\u00f9", scheda)
        self._casella.setContentsMargins(16, 0, 16, 0)
        riga_casella = QHBoxLayout()
        riga_casella.setContentsMargins(16, 0, 16, 0)
        riga_casella.addWidget(self._casella)
        colonna.addLayout(riga_casella)

        pulsanti = QHBoxLayout()
        pulsanti.setContentsMargins(16, 0, 16, 0)
        pulsanti.addStretch(1)
        no = QPushButton("No", scheda)
        no.setObjectName("no")
        si = QPushButton("S\u00ec, importa\u2026", scheda)
        si.setObjectName("si")
        for bottone in (no, si):
            bottone.setCursor(Qt.CursorShape.PointingHandCursor)
            pulsanti.addWidget(bottone)
        colonna.addLayout(pulsanti)

        no.clicked.connect(self._no)
        si.clicked.connect(lambda: (self._chiudi(), su_importa()))

        esterno = QVBoxLayout(self)
        esterno.addWidget(scheda, 0, Qt.AlignmentFlag.AlignCenter)
        padre.installEventFilter(self)
        self.setGeometry(padre.rect())
        self.show()
        self.raise_()

    def _no(self) -> None:
        self._chiudi()

    def _chiudi(self) -> None:
        # La scelta della casella vale anche per «Si'»: chi ha importato e ha
        # spuntato non vuole piu' vedere la domanda.
        if self._casella.isChecked():
            imposta_nascosto(True)
        self.parentWidget().removeEventFilter(self)
        self.hide()
        self.deleteLater()
