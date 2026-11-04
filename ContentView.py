#
#  ContentView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""La schermata di base: importa backup, esporta backup.

Tre sezioni della barra laterale puntano qui senza dire niente di diverso:
Home, Multimedia e Adunanze.  Nell'app originale era la stessa schermata
per tutte e tre, e i tre pulsanti di backup erano tutto quello che c'era.

Si puo' passare un titolo per distinguerle.  Il progetto originale non lo
faceva, quindi il titolo resta facoltativo e la schermata di base e' uguale a
quella di allora: se si aggiunge un titolo, cambia solo la riga in alto.

PERCHE' I BACKUP SONO QUI E NON IN UN MENU
-------------------------------------------
Perche' l'azione e' frequente e perche' e' l'unica cosa che non richiede
nessun pacchetto scaricato: si puo' fare backup anche con la cartella dei
dati vuota, e in quel momento non c'e' nient'altro su cui premere.
"""

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from Utility.UserData.BackupManager import BackupManager


class ContentView(QWidget):
    """I due pulsanti di backup."""

    #: Quando un backup e' stato creato o importato, la finestra puo' dirlo
    messaggio = Signal(str)

    def __init__(self, titolo: str | None = None, parent=None) -> None:
        super().__init__(parent)

        riga = QHBoxLayout()
        importa = QPushButton("Importa backup", self)
        importa.clicked.connect(self.importa_backup)
        etichetta = QLabel("JW LibriX", self)
        etichetta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etichetta.setStyleSheet("font-size: 20px; font-weight: 600; padding: 8px;")
        esporta = QPushButton("Esporta backup", self)
        esporta.clicked.connect(self.esporta_backup)

        riga.addWidget(importa)
        riga.addWidget(etichetta, 1)
        riga.addWidget(esporta)

        disposizione = QVBoxLayout(self)
        if titolo:
            intestazione = QLabel(titolo, self)
            intestazione.setAlignment(Qt.AlignmentFlag.AlignCenter)
            intestazione.setStyleSheet("font-size: 26px; font-weight: 700; padding: 16px;")
            disposizione.addWidget(intestazione)
        disposizione.addStretch(1)
        disposizione.addLayout(riga)
        disposizione.addStretch(1)

    # ------------------------------------------------------------------

    def importa_backup(self) -> None:
        """Sceglie un file .jwlibrary e lo importa, con la barra."""
        def fine(riepilogo, errore):
            if riepilogo:
                self.messaggio.emit(BackupManager.testo_riepilogo(riepilogo))
        BackupManager.restore_backup(parent=self, su_fine=fine)

    def esporta_backup(self) -> None:
        """Sceglie dove salvare e scrive il backup, con la barra."""
        def fine(percorso, errore):
            if percorso:
                self.messaggio.emit(f"Backup salvato in {percorso} \u2705")
        BackupManager.create_backup(parent=self, su_fine=fine)
