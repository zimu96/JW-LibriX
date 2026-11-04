#
#  PlaylistView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le playlist: l'elenco, gli elementi, il taglio.

Si arriva da «Ricerche».  L'elenco mostra le playlist; premendone una si vedono i
suoi elementi, con i comandi per riordinarli, tagliarli e toglierli.  «Riproduci»
suona tutta la playlist dal primo elemento (o da quello premuto), rispettando
l'inizio e la fine scelti per ognuno.

I file arrivano dal menu dei video e degli audio scaricati («Aggiungi alla
playlist»): una playlist non scarica niente, mette in fila quello che c'e'.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Utility.UserData import PlaylistManager as PM

LARGHEZZA = 760


def formatta(ms: int | None) -> str:
    if not ms:
        return "0:00"
    secondi = int(ms) // 1000
    return f"{secondi // 60}:{secondi % 60:02d}"


def leggi_tempo(testo: str) -> int | None:
    """«1:05», «65» o «0:05.5» -> millisecondi.  None se vuoto, ValueError se sbagliato."""
    testo = (testo or "").strip().replace(",", ".")
    if not testo:
        return None
    totale = 0.0
    for parte in testo.split(":"):
        totale = totale * 60 + float(parte)
    if totale < 0:
        raise ValueError("negativo")
    return int(round(totale * 1000))


def _senza_cornice(finestra: QDialog) -> None:
    finestra.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)


def chiedi_testo(padre, titolo: str, testo_iniziale: str = "") -> str | None:
    finestra = QInputDialog(padre)
    finestra.setLabelText(titolo)
    finestra.setTextValue(testo_iniziale)
    finestra.setOkButtonText("Ok")
    finestra.setCancelButtonText("Annulla")
    _senza_cornice(finestra)
    if finestra.exec() == QDialog.DialogCode.Accepted:
        return finestra.textValue().strip() or None
    return None


class _Taglio(QDialog):
    """Il popup del taglio: da dove a dove."""

    def __init__(self, padre, titolo: str, inizio: int, fine: int | None) -> None:
        super().__init__(padre)
        _senza_cornice(self)
        self.setObjectName("popupTaglio")
        self.risultato: tuple | None = None
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(20, 16, 20, 16)
        colonna.setSpacing(8)
        nome = QLabel(f"Taglia «{titolo}»", self)
        nome.setWordWrap(True)
        nome.setStyleSheet("font-weight: 600;")
        colonna.addWidget(nome)
        self.da = QLineEdit(formatta(inizio) if inizio else "", self)
        self.da.setPlaceholderText("dall'inizio  (minuti:secondi)")
        self.a = QLineEdit(formatta(fine) if fine else "", self)
        self.a.setPlaceholderText("fino alla fine  (minuti:secondi)")
        for etichetta, campo in (("Parte da", self.da), ("Si ferma a", self.a)):
            colonna.addWidget(QLabel(etichetta, self))
            colonna.addWidget(campo)
        self.errore = QLabel("", self)
        self.errore.setStyleSheet("color: #e74c3c;")
        colonna.addWidget(self.errore)
        riga = QHBoxLayout()
        togli = QPushButton("Togli il taglio", self)
        annulla = QPushButton("Annulla", self)
        salva = QPushButton("Salva", self)
        salva.setDefault(True)
        for b in (togli, annulla, salva):
            riga.addWidget(b)
        colonna.addLayout(riga)
        togli.clicked.connect(self._togli)
        annulla.clicked.connect(self.reject)
        salva.clicked.connect(self._salva)
        self.setMinimumWidth(340)

    def _togli(self) -> None:
        self.risultato = (None, None)
        self.accept()

    def _salva(self) -> None:
        try:
            inizio, fine = leggi_tempo(self.da.text()), leggi_tempo(self.a.text())
        except ValueError:
            self.errore.setText("Scrivi i tempi come minuti:secondi, per esempio 1:05.")
            return
        if inizio is not None and fine is not None and fine <= inizio:
            self.errore.setText("La fine deve essere dopo l'inizio.")
            return
        self.risultato = (inizio, fine)
        self.accept()


class _Riga(QFrame):
    clicked = Signal()

    def __init__(self, titolo: str, sotto: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rigaNovita")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.riga = QHBoxLayout(self)
        self.riga.setContentsMargins(12, 8, 8, 8)
        testi = QVBoxLayout()
        testi.setSpacing(2)
        t = QLabel(titolo, self)
        t.setObjectName("titoloNovita")
        t.setWordWrap(True)
        testi.addWidget(t)
        if sotto:
            s = QLabel(sotto, self)
            s.setObjectName("sottoCard")
            testi.addWidget(s)
        self.riga.addLayout(testi, 1)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class PlaylistView(QWidget):
    """L'elenco delle playlist e il dettaglio di una."""

    navigate = Signal(object)
    goBack = Signal()
    messaggio = Signal(str)
    #: (elementi, indice di partenza)
    riproduciRichiesto = Signal(list, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._aperta: int | None = None

        pagina = QWidget()
        esterna = QVBoxLayout(pagina)
        esterna.setContentsMargins(18, 16, 18, 16)
        esterna.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._contenitore = QWidget(pagina)
        self._contenitore.setMaximumWidth(LARGHEZZA)
        self._contenitore.setMinimumWidth(320)
        self._colonna = QVBoxLayout(self._contenitore)
        self._colonna.setContentsMargins(0, 0, 0, 0)
        self._colonna.setSpacing(6)
        self._colonna.setAlignment(Qt.AlignmentFlag.AlignTop)
        esterna.addWidget(self._contenitore)

        scorribile = QScrollArea(self)
        scorribile.setWidgetResizable(True)
        scorribile.setFrameShape(QScrollArea.Shape.NoFrame)
        scorribile.setWidget(pagina)
        radice = QVBoxLayout(self)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.addWidget(scorribile)
        self.aggiorna()

    # ------------------------------------------------------------------

    def aggiorna(self) -> None:
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().deleteLater()
            elif elemento.layout() is not None:
                self._svuota_layout(elemento.layout())
        if self._aperta is None:
            self._elenco()
        else:
            self._dettaglio(self._aperta)

    @staticmethod
    def _svuota_layout(layout) -> None:
        while layout.count():
            e = layout.takeAt(0)
            if e.widget() is not None:
                e.widget().deleteLater()

    def _titolo(self, testo: str) -> QLabel:
        etichetta = QLabel(testo, self._contenitore)
        etichetta.setObjectName("titoloPagina")
        return etichetta

    def _pulsante(self, testo: str, azione) -> QPushButton:
        pulsante = QPushButton(testo, self._contenitore)
        pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
        pulsante.clicked.connect(lambda _=False: azione())
        return pulsante

    # --- elenco ---------------------------------------------------------

    def _elenco(self) -> None:
        self._colonna.addWidget(self._titolo("Playlist"))
        self._colonna.addWidget(self._pulsante("Nuova playlist", self._nuova))
        elenco = PM.playlist()
        if not elenco:
            vuoto = QLabel("Nessuna playlist. Dal menu dei video e degli audio scaricati "
                           "scegli «Aggiungi alla playlist».", self._contenitore)
            vuoto.setObjectName("vuoto")
            vuoto.setWordWrap(True)
            self._colonna.addWidget(vuoto)
        for p in elenco:
            n = p["elementi"]
            riga = _Riga(p["nome"], f"{n} element{'o' if n == 1 else 'i'}", self._contenitore)
            riga.clicked.connect(lambda i=p["id"]: self._apri(i))
            self._colonna.addWidget(riga)

    def _nuova(self) -> None:
        nome = chiedi_testo(self, "Nome della nuova playlist")
        if nome:
            self._apri(PM.crea(nome))

    def _apri(self, tag_id: int | None) -> None:
        self._aperta = tag_id
        self.aggiorna()

    # --- dettaglio ------------------------------------------------------

    def _dettaglio(self, tag_id: int) -> None:
        nome = next((p["nome"] for p in PM.playlist() if p["id"] == tag_id), None)
        if nome is None:
            self._aperta = None
            self._elenco()
            return
        self._colonna.addWidget(self._pulsante("‹  Tutte le playlist", lambda: self._apri(None)))
        self._colonna.addWidget(self._titolo(nome))
        barra = QHBoxLayout()
        elementi = PM.elementi(tag_id)
        riproduci = self._pulsante("Riproduci", lambda: self.riproduciRichiesto.emit(elementi, 0))
        riproduci.setEnabled(bool(elementi))
        barra.addWidget(riproduci)
        barra.addWidget(self._pulsante("Rinomina", lambda: self._rinomina(tag_id, nome)))
        barra.addWidget(self._pulsante("Elimina playlist", lambda: self._elimina(tag_id, nome)))
        barra.addStretch(1)
        self._colonna.addLayout(barra)
        if not elementi:
            vuoto = QLabel("La playlist e' vuota.", self._contenitore)
            vuoto.setObjectName("vuoto")
            self._colonna.addWidget(vuoto)
        for indice, e in enumerate(elementi):
            self._colonna.addWidget(self._riga_elemento(tag_id, elementi, indice))

    def _riga_elemento(self, tag_id: int, elementi: list, indice: int) -> _Riga:
        e = elementi[indice]
        sotto = {PM.AUDIO: "Audio", PM.VIDEO: "Video", PM.IMMAGINE: "Immagine"}.get(e["tipo"], "")
        if e["inizio_ms"] or e["fine_ms"]:
            fine = formatta(e["fine_ms"]) if e["fine_ms"] else "la fine"
            sotto += f"  ·  da {formatta(e['inizio_ms'])} a {fine}"
        if not PM.percorso_file(e["file"]).is_file():
            sotto += "  ·  file non trovato"
        riga = _Riga(e["titolo"], sotto, self._contenitore)
        riga.clicked.connect(lambda: self.riproduciRichiesto.emit(elementi, indice))
        for simbolo, aiuto, azione in (
                ("▲", "Sposta su", lambda: self._sposta(tag_id, e["id"], -1)),
                ("▼", "Sposta giù", lambda: self._sposta(tag_id, e["id"], 1)),
                ("✂", "Taglia", lambda: self._taglia(tag_id, e)),
                ("✕", "Togli dalla playlist", lambda: self._togli(tag_id, e["id"]))):
            b = QToolButton(riga)
            b.setText(simbolo)
            b.setToolTip(aiuto)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, a=azione: a())
            riga.riga.addWidget(b)
        return riga

    def _sposta(self, tag_id: int, item_id: int, passo: int) -> None:
        PM.sposta(tag_id, item_id, passo)
        self.aggiorna()

    def _togli(self, tag_id: int, item_id: int) -> None:
        PM.rimuovi(tag_id, item_id)
        self.aggiorna()

    def _taglia(self, tag_id: int, e: dict) -> None:
        finestra = _Taglio(self, e["titolo"], e["inizio_ms"], e["fine_ms"])
        if finestra.exec() == QDialog.DialogCode.Accepted and finestra.risultato:
            PM.imposta_taglio(e["id"], *finestra.risultato)
            self.aggiorna()

    def _rinomina(self, tag_id: int, nome: str) -> None:
        nuovo = chiedi_testo(self, "Nuovo nome", nome)
        if nuovo:
            PM.rinomina(tag_id, nuovo)
            self.aggiorna()

    def _elimina(self, tag_id: int, nome: str) -> None:
        domanda = QMessageBox(self)
        domanda.setText(f"Elimino la playlist «{nome}»?\n\nI file non si cancellano.")
        domanda.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        domanda.setDefaultButton(QMessageBox.StandardButton.No)
        _senza_cornice(domanda)
        if domanda.exec() == QMessageBox.StandardButton.Yes:
            PM.elimina(tag_id)
            self._aperta = None
            self.aggiorna()
