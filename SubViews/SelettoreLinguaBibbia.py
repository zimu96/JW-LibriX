#
#  SelettoreLinguaBibbia.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il menu per scegliere la lingua della Bibbia, dentro l'app (niente finestre).

Mostra prima le lingue preferite (la stella), poi le altre.  Ogni lingua dice
se e' scaricata (si legge anche senza internet) o si legge online, e ha il
pulsante per scaricarla o eliminarla.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Utility import BibbiaOnline, Lingua, Traduzioni, tema
from Utility.JWPubManager import bible_package
from Utility.Stuff import icon, icona_tabler

MASSIMO_RIGHE = 60
TOTALE = Traduzioni.TOTALE


def stato(simbolo: str) -> tuple[str, bool]:
    """(testo, scaricata): lo stato di una lingua per l'utente."""
    if bible_package(simbolo) is not None or BibbiaOnline.capitoli_su_disco(simbolo) >= TOTALE:
        return "Scaricata", True
    capitoli = BibbiaOnline.capitoli_su_disco(simbolo)
    if Traduzioni.in_corso(simbolo) is not None:
        return f"Scarico… {Traduzioni.in_corso(simbolo)}/{TOTALE}", False
    if capitoli:
        return f"Online · {capitoli} capitoli sul disco", False
    return "Online", False


class SelettoreLinguaBibbia(QFrame):
    """Un riquadro sopra la Bibbia con l'elenco delle lingue."""

    linguaScelta = Signal(int)
    scaricaRichiesta = Signal(str)
    eliminaRichiesta = Signal(str)
    fermaRichiesta = Signal(str)

    def __init__(self, padre: QWidget) -> None:
        super().__init__(padre)
        self.setObjectName("velo")
        self.setStyleSheet("#velo { background-color: rgba(0, 0, 0, 150); }")
        scheda = QFrame(self)
        scheda.setObjectName("scheda")
        scheda.setFixedSize(460, 560)
        scheda.setStyleSheet(
            "#scheda { background-color: #2b2b2b; border-radius: 10px; }"
            " #scheda QLabel { color: #f2f2f2; background: transparent; }"
            f" #testata {{ background-color: {tema.ACCENTO};"
            " border-top-left-radius: 10px; border-top-right-radius: 10px; }"
            " QLineEdit { background: #3a3a3a; color: #f2f2f2; border: none;"
            " border-radius: 6px; padding: 8px; }"
            " QToolButton { background: transparent; border: none; border-radius: 6px;"
            " padding: 4px; color: #f2f2f2; }"
            " QToolButton:hover { background-color: #444444; }"
            " #riga { border-bottom: 1px solid #3d3d3d; }"
            " #riga:hover { background-color: #333333; }"
            " #nota { color: #a8a8a8; font-size: 12px; }"
            " QScrollArea { background: #2b2b2b; border: none; }"
            " #contenuto { background: #2b2b2b; }")
        colonna = QVBoxLayout(scheda)
        colonna.setContentsMargins(0, 0, 0, 12)
        colonna.setSpacing(8)
        testata = QFrame(scheda)
        testata.setObjectName("testata")
        riga_testata = QHBoxLayout(testata)
        riga_testata.setContentsMargins(16, 10, 8, 10)
        titolo = QLabel("Lingua della Bibbia", testata)
        titolo.setStyleSheet("font-size: 15px; font-weight: 700;")
        riga_testata.addWidget(titolo, 1)
        chiudi = QToolButton(testata)
        chiudi.setIcon(icon("xmark", "#ffffff", 20))
        chiudi.clicked.connect(self.chiudi)
        riga_testata.addWidget(chiudi)
        colonna.addWidget(testata)
        self.cerca = QLineEdit(scheda)
        self.cerca.setPlaceholderText("Cerca una lingua…")
        self.cerca.textChanged.connect(self._riempi)
        cerca_riga = QHBoxLayout()
        cerca_riga.setContentsMargins(12, 0, 12, 0)
        cerca_riga.addWidget(self.cerca)
        colonna.addLayout(cerca_riga)
        self._area = QScrollArea(scheda)
        self._area.setWidgetResizable(True)
        self._area.setFrameShape(QFrame.Shape.NoFrame)
        colonna.addWidget(self._area, 1)
        esterno = QVBoxLayout(self)
        esterno.addWidget(scheda, 0, Qt.AlignmentFlag.AlignCenter)
        padre.installEventFilter(self)
        self.setGeometry(padre.rect())
        self._barre: dict[str, tuple] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._aggiorna_progressi)
        self._timer.start(500)
        self._riempi()
        self.show()
        self.raise_()
        self.cerca.setFocus()

    def eventFilter(self, oggetto, evento) -> bool:
        if evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def chiudi(self) -> None:
        self._timer.stop()
        self.parentWidget().removeEventFilter(self)
        self.hide()
        self.deleteLater()

    def aggiorna(self) -> None:
        self._riempi()

    def _ordinate(self, testo: str) -> list[dict]:
        tutte = Lingua.lingue()
        if testo:
            chiave = testo.lower()
            return [v for v in tutte
                    if chiave in (v.get("nome") or "").lower()
                    or chiave in (v.get("nome_vernacolare") or "").lower()][:MASSIMO_RIGHE]
        preferite = [v for s in Lingua.preferite() if (v := Lingua.per_simbolo(s))]
        altre = sorted((v for v in tutte if v["simbolo"] not in Lingua.preferite()),
                       key=lambda v: -int(v.get("pubblicazioni") or 0))
        attuale = Lingua.bibbia_voce()
        elenco = preferite + ([attuale] if attuale and attuale not in preferite else [])
        elenco += [v for v in altre if v not in elenco]
        return elenco[:MASSIMO_RIGHE]

    def _aggiorna_progressi(self) -> None:
        """Fa avanzare le barre degli scaricamenti; ridisegna se uno e' iniziato o finito."""
        attivi = Traduzioni.scaricamenti()
        if set(attivi) != set(self._barre):
            self._riempi()
            return
        for simbolo, (barra, testo) in self._barre.items():
            fatti = attivi[simbolo]
            barra.setValue(fatti)
            testo.setText(f"Scarico… {fatti * 100 // TOTALE}%  ({fatti}/{TOTALE} capitoli)")

    def _riempi(self) -> None:
        self._barre = {}
        contenuto = QWidget()
        contenuto.setObjectName("contenuto")
        colonna = QVBoxLayout(contenuto)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(0)
        in_uso = Lingua.bibbia_simbolo()
        preferite = Lingua.preferite()
        for voce in self._ordinate(self.cerca.text().strip()):
            colonna.addWidget(self._riga(voce, in_uso, preferite))
        if not self.cerca.text().strip():
            nota = QLabel("Cerca per vedere le altre lingue.", contenuto)
            nota.setObjectName("nota")
            nota.setContentsMargins(16, 10, 16, 6)
            colonna.addWidget(nota)
        colonna.addStretch(1)
        self._area.setWidget(contenuto)

    def _riga(self, voce: dict, in_uso: str, preferite: list) -> QWidget:
        simbolo = voce["simbolo"]
        testo, scaricata = stato(simbolo)
        riga = QFrame()
        riga.setObjectName("riga")
        layout = QHBoxLayout(riga)
        layout.setContentsMargins(8, 6, 8, 6)
        stella = QToolButton(riga)
        stella.setIcon(icona_tabler(
            "star", "#f5c542" if simbolo in preferite else "#8a8a8a", 22))
        stella.setToolTip("Lingua preferita")
        stella.clicked.connect(lambda: (Lingua.alterna_preferita(simbolo), self._riempi()))
        layout.addWidget(stella)
        nomi = QVBoxLayout()
        nomi.setSpacing(0)
        nome = QLabel(voce.get("nome_vernacolare") or voce["nome"], riga)
        nome.setStyleSheet("font-weight: 700;" if simbolo == in_uso else "")
        stato_label = QLabel(("In uso · " if simbolo == in_uso else "") + testo, riga)
        stato_label.setObjectName("nota")
        nomi.addWidget(nome)
        nomi.addWidget(stato_label)
        fatti = Traduzioni.in_corso(simbolo)
        if fatti is not None:
            barra = QProgressBar(riga)
            barra.setRange(0, TOTALE)
            barra.setValue(fatti)
            barra.setTextVisible(False)
            barra.setFixedHeight(6)
            barra.setStyleSheet(
                "QProgressBar { background: #444444; border: none; border-radius: 3px; }"
                f" QProgressBar::chunk {{ background: {tema.ACCENTO}; border-radius: 3px; }}")
            nomi.addWidget(barra)
            self._barre[simbolo] = (barra, stato_label)
            stato_label.setText(f"Scarico… {fatti * 100 // TOTALE}%  ({fatti}/{TOTALE} capitoli)")
        layout.addLayout(nomi, 1)
        if fatti is not None:
            ferma = QToolButton(riga)
            ferma.setIcon(icon("xmark", "#d0d0d0", 22))
            ferma.setToolTip("Ferma lo scaricamento")
            ferma.clicked.connect(lambda: self.fermaRichiesta.emit(simbolo))
            layout.addWidget(ferma)
        elif simbolo != "I" or bible_package("I") is None:
            azione = QToolButton(riga)
            if scaricata or BibbiaOnline.capitoli_su_disco(simbolo):
                if bible_package(simbolo) is None:
                    azione.setIcon(icona_tabler("trash", "#d0d0d0", 22))
                    azione.setToolTip("Elimina dal disco")
                    azione.clicked.connect(lambda: self.eliminaRichiesta.emit(simbolo))
                    layout.addWidget(azione)
            else:
                azione.setIcon(icona_tabler("download", "#d0d0d0", 22))
                azione.setToolTip("Scarica la Bibbia (si legge anche senza internet)")
                azione.clicked.connect(lambda: self.scaricaRichiesta.emit(simbolo))
                layout.addWidget(azione)
        riga.setCursor(Qt.CursorShape.PointingHandCursor)
        riga.mousePressEvent = lambda e, n=voce["id"]: (
            self.linguaScelta.emit(n) if e.button() == Qt.MouseButton.LeftButton else None)
        return riga
