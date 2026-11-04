#
#  DialoghiNote.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I popup per scrivere una nota e per gestire le etichette.

Tutti senza cornice e senza barra del titolo, come gli altri popup dell'app.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from SubViews.PlaylistView import chiedi_testo
from Utility.UserData import TagManager


def _senza_cornice(finestra) -> None:
    finestra.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)


class DialogoNota(QDialog):
    """Titolo e testo di una nota.  ``risultato`` = (titolo, testo) se si salva."""

    def __init__(self, padre, titolo: str = "", testo: str = "") -> None:
        super().__init__(padre)
        _senza_cornice(self)
        self.risultato: tuple[str, str] | None = None
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(20, 16, 20, 16)
        colonna.setSpacing(8)
        intestazione = QLabel("Modifica la nota" if (titolo or testo) else "Nuova nota", self)
        intestazione.setStyleSheet("font-weight: 600;")
        colonna.addWidget(intestazione)
        self.titolo = QLineEdit(titolo, self)
        self.titolo.setPlaceholderText("Titolo")
        colonna.addWidget(self.titolo)
        self.testo = QPlainTextEdit(testo, self)
        self.testo.setPlaceholderText("Scrivi la nota…")
        self.testo.setMinimumHeight(160)
        colonna.addWidget(self.testo)
        riga = QHBoxLayout()
        riga.addStretch(1)
        annulla = QPushButton("Annulla", self)
        salva = QPushButton("Salva", self)
        salva.setDefault(True)
        riga.addWidget(annulla)
        riga.addWidget(salva)
        colonna.addLayout(riga)
        annulla.clicked.connect(self.reject)
        salva.clicked.connect(self._salva)
        self.setMinimumWidth(420)

    def _salva(self) -> None:
        titolo, testo = self.titolo.text().strip(), self.testo.toPlainText().strip()
        if not titolo and not testo:
            self.reject()
            return
        self.risultato = (titolo or testo.splitlines()[0][:60], testo)
        self.accept()


class DialogoEtichette(QDialog):
    """Elenco delle etichette: nuova, rinomina, elimina."""

    def __init__(self, padre) -> None:
        super().__init__(padre)
        _senza_cornice(self)
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(20, 16, 20, 16)
        colonna.setSpacing(8)
        intestazione = QLabel("Etichette", self)
        intestazione.setStyleSheet("font-weight: 600;")
        colonna.addWidget(intestazione)
        self.elenco = QListWidget(self)
        self.elenco.setMinimumHeight(180)
        colonna.addWidget(self.elenco)
        riga = QHBoxLayout()
        for testo, azione in (("Nuova", self._nuova), ("Rinomina", self._rinomina),
                              ("Elimina", self._elimina)):
            b = QPushButton(testo, self)
            b.clicked.connect(lambda _=False, a=azione: a())
            riga.addWidget(b)
        riga.addStretch(1)
        chiudi = QPushButton("Chiudi", self)
        chiudi.setDefault(True)
        chiudi.clicked.connect(self.accept)
        riga.addWidget(chiudi)
        colonna.addLayout(riga)
        self.setMinimumWidth(380)
        self._riempi()

    def _riempi(self) -> None:
        self.elenco.clear()
        for e in TagManager.etichette():
            voce = QListWidgetItem(f"{e['nome']}  ({e['note']})")
            voce.setData(Qt.ItemDataRole.UserRole, e)
            self.elenco.addItem(voce)

    def _scelta(self) -> dict | None:
        voce = self.elenco.currentItem()
        return voce.data(Qt.ItemDataRole.UserRole) if voce else None

    def _nuova(self) -> None:
        nome = chiedi_testo(self, "Nome della nuova etichetta")
        if nome:
            TagManager.crea(nome)
            self._riempi()

    def _rinomina(self) -> None:
        e = self._scelta()
        if e is None:
            return
        nome = chiedi_testo(self, "Nuovo nome", e["nome"])
        if nome:
            TagManager.rinomina(e["id"], nome)
            self._riempi()

    def _elimina(self) -> None:
        e = self._scelta()
        if e is None:
            return
        domanda = QMessageBox(self)
        domanda.setText(f"Elimino l'etichetta «{e['nome']}»?\n\nLe note restano.")
        domanda.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        domanda.setDefaultButton(QMessageBox.StandardButton.No)
        _senza_cornice(domanda)
        if domanda.exec() == QMessageBox.StandardButton.Yes:
            TagManager.elimina(e["id"])
            self._riempi()


def menu_etichette_nota(padre, note_id: int, dopo) -> None:
    """Il menu per mettere e togliere le etichette a una nota."""
    from PyQt6.QtGui import QCursor

    menu = QMenu(padre)
    attive = set(TagManager.della_nota(note_id))
    for e in TagManager.etichette():
        azione = menu.addAction(e["nome"])
        azione.setCheckable(True)
        azione.setChecked(e["id"] in attive)
        azione.triggered.connect(
            lambda stato, i=e["id"]: (TagManager.imposta(note_id, i, bool(stato)), dopo()))
    if menu.actions():
        menu.addSeparator()
    nuova = menu.addAction("Nuova etichetta…")

    def crea() -> None:
        nome = chiedi_testo(padre, "Nome della nuova etichetta")
        tag_id = TagManager.crea(nome) if nome else None
        if tag_id is not None:
            TagManager.imposta(note_id, tag_id, True)
            dopo()

    nuova.triggered.connect(crea)
    menu.exec(QCursor.pos())
