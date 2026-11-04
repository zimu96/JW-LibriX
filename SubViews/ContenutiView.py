#
#  ContenutiView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I contenuti multimediali di una pagina, nell'ordine in cui servono all'adunanza.

Una schermata come le altre (dentro la fascia viola e la barra in alto), senza
menu laterale: un elenco di immagini, video e audio nello stesso ordine in cui
compaiono nella pagina, ognuno con il suo tasto per aprirlo o scaricarlo.
Le immagini si aprono nel velo (e sullo schermo esterno, se scelto); i video e
gli audio li apre la finestra principale.

Ogni voce e' un dizionario: ``tipo`` ("immagine", "video", "audio"),
``titolo``, ``miniatura`` (byte o None), ``dati`` (byte dell'immagine),
``scaricato`` (bool) e, per i media, quello che serve per chiederli al server.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from SubViews.VeloImmagine import VeloImmagine
from Utility import FileEsterni, tema
from Utility.Stuff import icona_tabler

LARGHEZZA_MINIATURA = 176
ALTEZZA_MINIATURA = 99
_ETICHETTA = {"immagine": "Immagine", "video": "Video", "audio": "Audio",
              "documento": "Documento"}
_ICONA = {"immagine": "image", "video": "video", "audio": "music",
          "documento": "document-text"}


class _Riga(QFrame):
    """Una voce: numero, miniatura, titolo e tasti."""

    def __init__(self, posizione: int, voce: dict, colori: dict, vista) -> None:
        super().__init__()
        self.setObjectName("rigaContenuto")
        self._voce, self._vista = voce, vista
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"#rigaContenuto {{ background-color: {colori['pannello']};"
            f" border: 1px solid {colori['bordo']}; border-radius: 8px; }}"
            f" #rigaContenuto:hover {{ background-color: {colori['hover']}; }}"
            f" QLabel {{ background: transparent; color: {colori['testo']}; }}")
        riga = QHBoxLayout(self)
        riga.setContentsMargins(12, 10, 12, 10)
        riga.setSpacing(14)

        numero = QLabel(str(posizione), self)
        numero.setFixedWidth(28)
        numero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        numero.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {colori['grigio']};")
        riga.addWidget(numero)

        miniatura = QLabel(self)
        miniatura.setFixedSize(LARGHEZZA_MINIATURA, ALTEZZA_MINIATURA)
        miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        miniatura.setStyleSheet(f"background-color: {colori['griglia']}; border-radius: 6px;")
        pixmap = QPixmap()
        if voce.get("miniatura") and pixmap.loadFromData(voce["miniatura"]):
            miniatura.setPixmap(pixmap.scaled(
                LARGHEZZA_MINIATURA, ALTEZZA_MINIATURA,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            miniatura.setPixmap(icona_tabler(
                _ICONA[voce["tipo"]], colori["icona"], 40).pixmap(40, 40))
        riga.addWidget(miniatura)

        testi = QVBoxLayout()
        testi.setSpacing(2)
        titolo = QLabel(voce.get("titolo") or _ETICHETTA[voce["tipo"]], self)
        titolo.setWordWrap(True)
        titolo.setStyleSheet("font-size: 14px; font-weight: 600;")
        genere = _ETICHETTA[voce["tipo"]]
        if voce.get("esterno"):
            genere += " · file esterno" + (" · non trovato" if voce.get("mancante") else "")
        elif voce["tipo"] != "immagine":
            genere += " · sul disco" if voce.get("scaricato") else " · in streaming"
        sotto = QLabel(genere, self)
        sotto.setStyleSheet(f"font-size: 12px; color: {colori['grigio']};")
        testi.addStretch(1)
        testi.addWidget(titolo)
        testi.addWidget(sotto)
        testi.addStretch(1)
        riga.addLayout(testi, 1)

        apri = QPushButton("Mostra" if voce["tipo"] in ("immagine", "documento")
                           else "Riproduci", self)
        apri.setCursor(Qt.CursorShape.PointingHandCursor)
        apri.setEnabled(not voce.get("mancante"))
        apri.clicked.connect(lambda: vista.apri_voce(voce))
        riga.addWidget(apri)
        if voce.get("esterno") and vista.modificabile:
            togli = QPushButton("Rimuovi", self)
            togli.setObjectName("secondario")
            togli.setToolTip("Toglie il file da questo elenco; sul computer non viene cancellato")
            togli.setCursor(Qt.CursorShape.PointingHandCursor)
            togli.clicked.connect(lambda: vista.rimuovi_voce(voce))
            riga.addWidget(togli)
        if voce["tipo"] in ("video", "audio") and not voce.get("scaricato"):
            scarica = QPushButton("Scarica", self)
            scarica.setObjectName("secondario")
            scarica.setCursor(Qt.CursorShape.PointingHandCursor)
            scarica.clicked.connect(lambda: vista.scarica_voce(voce))
            riga.addWidget(scarica)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and not self._voce.get("mancante"):
            self._vista.apri_voce(self._voce)


class ContenutiView(QWidget):
    """L'elenco dei contenuti di una pagina."""

    goBack = Signal()
    mediaRichiesto = Signal(dict)
    scaricaRichiesta = Signal(dict)

    def __init__(self, titolo: str, voci: list[dict], parent=None,
                 chiave: str | None = None) -> None:
        super().__init__(parent)
        colori = tema.colori(tema.tema_attivo())
        self._titolo = titolo
        #: Con una chiave (pagina di adunanza) si possono aggiungere file esterni.
        self._chiave = chiave
        self._voci_pagina = voci
        self._voci = self._con_esterni()
        self.setStyleSheet(
            " QPushButton { background-color: #64398b; color: white; border: none;"
            " border-radius: 4px; padding: 7px 18px; }"
            " QPushButton:hover { background-color: #a77fd4; }"
            f" QPushButton#secondario {{ background: transparent; color: {colori['testo']};"
            f" border: 1px solid {colori['bordo']}; }}"
            f" QPushButton#secondario:hover {{ border-color: {colori['testo']}; }}")

        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(0)

        testata = QWidget(self)
        riga = QHBoxLayout(testata)
        riga.setContentsMargins(18, 14, 18, 10)
        riga.setSpacing(12)
        indietro = QPushButton("Torna alla pagina", testata)
        indietro.setIcon(icona_tabler("chevron-left", "#ffffff", 16))
        indietro.setCursor(Qt.CursorShape.PointingHandCursor)
        indietro.clicked.connect(self.goBack.emit)
        riga.addWidget(indietro)
        intestazione = QLabel(f"Contenuti multimediali — {titolo}", testata)
        intestazione.setStyleSheet("font-size: 17px; font-weight: 600;")
        riga.addWidget(intestazione, 1)
        self._quanti = QLabel("", testata)
        self._quanti.setStyleSheet(f"color: {colori['grigio']};")
        riga.addWidget(self._quanti)
        if chiave:
            aggiungi = QPushButton("Aggiungi file", testata)
            aggiungi.setIcon(icona_tabler("plus", "#ffffff", 16))
            aggiungi.setToolTip("Immagini, video, audio, PDF, Word, Excel, LibreOffice")
            aggiungi.setCursor(Qt.CursorShape.PointingHandCursor)
            aggiungi.clicked.connect(self.aggiungi_file)
            riga.addWidget(aggiungi)
        colonna.addWidget(testata)

        scorribile = QScrollArea(self)
        scorribile.setWidgetResizable(True)
        scorribile.setFrameShape(QFrame.Shape.NoFrame)
        self._colori = colori
        self._scorribile = scorribile
        self._riempi()
        colonna.addWidget(scorribile, 1)

        self.velo = VeloImmagine(self)

    @property
    def modificabile(self) -> bool:
        return self._chiave is not None

    def _riempi(self) -> None:
        interno = QWidget()
        elenco = QVBoxLayout(interno)
        elenco.setContentsMargins(18, 4, 18, 18)
        elenco.setSpacing(8)
        gruppo = None
        for posizione, voce in enumerate(self._voci, start=1):
            if voce.get("gruppo") != gruppo:
                gruppo = voce.get("gruppo")
                if gruppo:
                    intestazione = QLabel(f"Dal documento citato: {gruppo}", interno)
                    intestazione.setWordWrap(True)
                    intestazione.setStyleSheet(
                        f"font-size: 14px; font-weight: 600; padding: 14px 2px 2px 2px;"
                        f" color: {self._colori['grigio']};")
                    elenco.addWidget(intestazione)
            elenco.addWidget(_Riga(posizione, voce, self._colori, self))
        elenco.addStretch(1)
        self._scorribile.setWidget(interno)
        self._quanti.setText(f"{len(self._voci)} elementi")

    def _con_esterni(self) -> list[dict]:
        """I file aggiunti a mano vanno in cima, cosi' si vedono senza scorrere."""
        if not self._chiave:
            return self._voci_pagina
        return [FileEsterni.voce(p) for p in FileEsterni.leggi(self._chiave)] + self._voci_pagina

    def _ricarica_esterni(self) -> None:
        self._voci = self._con_esterni()
        self._riempi()

    def aggiungi_file(self) -> None:
        """Sceglie uno o piu' file dal computer e li aggiunge all'elenco."""
        formati = sorted(FileEsterni.IMMAGINI | FileEsterni.VIDEO | FileEsterni.AUDIO
                         | FileEsterni.PDF | FileEsterni.OFFICE)
        filtro = ("File supportati (" + " ".join(f"*{e}" for e in formati) + ");;Tutti i file (*)")
        scelti, _ = QFileDialog.getOpenFileNames(self, "Aggiungi file", "", filtro)
        if not scelti:
            return
        scartati = FileEsterni.aggiungi(self._chiave, scelti)
        self._ricarica_esterni()
        if scartati:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Formato non supportato",
                "Questi file non sono stati aggiunti:\n" + "\n".join(scartati))

    def rimuovi_voce(self, voce: dict) -> None:
        """Toglie il file dall'elenco, senza toccarlo sul disco."""
        FileEsterni.togli(self._chiave, voce["percorso"])
        self._ricarica_esterni()

    def apri_voce(self, voce: dict) -> None:
        if voce.get("esterno") and voce["tipo"] in ("immagine", "documento"):
            self.velo.apri(voce["file"], voce.get("titolo") or "")
            return
        if voce["tipo"] == "immagine":
            pixmap = QPixmap()
            if voce.get("dati") and pixmap.loadFromData(voce["dati"]):
                self.velo.mostra(pixmap)
            return
        self.mediaRichiesto.emit(voce)

    def scarica_voce(self, voce: dict) -> None:
        self.scaricaRichiesta.emit(voce)
