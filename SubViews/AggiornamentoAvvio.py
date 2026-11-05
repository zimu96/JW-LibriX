#
#  AggiornamentoAvvio.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il popup dell'avvio: «C'e' un aggiornamento».

All'apertura della finestra, in background, si controlla se c'e' una versione
nuova dell'app e, **solo se e' installato**, del timer.  Se c'e' qualcosa,
compare questo popup dentro l'app: un tasto scarica tutto, prima il plugin e
poi l'app, con una barra che mostra la percentuale.  Finito, l'app si riavvia.

Niente rete, niente da aggiornare o errore nel controllo: nessun popup.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout)

from Utility import AggiornaApp, Plugin


class _Avviso(QDialog):
    _passo = Signal(str, int)      # testo, percentuale (-1 = non si sa)
    _fine = Signal(str)            # errore ('' = tutto fatto)

    def __init__(self, padre, trovato: dict) -> None:
        super().__init__(padre)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._trovato = trovato
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(22, 18, 22, 18)
        colonna.setSpacing(10)
        titolo = QLabel("C'è un aggiornamento", self)
        titolo.setStyleSheet("font-weight: 600; font-size: 15px;")
        colonna.addWidget(titolo)

        righe = []
        if trovato.get("timer"):
            righe.append(f"• Timer adunanze: versione {trovato['timer']} "
                         f"(hai la {Plugin.versione('timer') or '?'})")
        if trovato.get("app"):
            righe.append("• JW-LibriX: versione nuova disponibile")
        self.testo = QLabel("\n".join(righe) + "\n\nVuoi scaricarlo adesso?", self)
        self.testo.setWordWrap(True)
        colonna.addWidget(self.testo)

        self.barra = QProgressBar(self)
        self.barra.setRange(0, 100)
        self.barra.setFixedHeight(10)
        self.barra.setTextVisible(False)
        self.barra.setVisible(False)
        colonna.addWidget(self.barra)
        self.stato = QLabel("", self)
        self.stato.setVisible(False)
        colonna.addWidget(self.stato)

        riga = QHBoxLayout()
        riga.addStretch(1)
        self.no = QPushButton("Più tardi", self)
        self.si = QPushButton("Scarica", self)
        self.si.setDefault(True)
        riga.addWidget(self.no)
        riga.addWidget(self.si)
        colonna.addLayout(riga)
        self.setMinimumWidth(440)

        self.no.clicked.connect(self.reject)
        self.si.clicked.connect(self._scarica)
        self._passo.connect(self._mostra_passo)
        self._fine.connect(self._finito)

    def _scarica(self) -> None:
        self.si.setEnabled(False)
        self.no.setEnabled(False)
        self.barra.setVisible(True)
        self.stato.setVisible(True)
        threading.Thread(target=self._lavoro, daemon=True).start()

    def _lavoro(self) -> None:
        """Nel thread: prima il plugin, poi l'app.  Se il primo fallisce ci si ferma."""
        t = self._trovato
        if t.get("timer"):
            self._passo.emit("Scarico il timer…", 0)

            def su_progresso(letti: int, totale: int) -> None:
                self._passo.emit("Scarico il timer…",
                                 min(99, letti * 100 // totale) if totale else -1)

            errore = Plugin.installa("timer", su_progresso, t["timer"])
            if errore:
                self._fine.emit(f"Timer: {errore}")
                return
            self._passo.emit("Timer aggiornato", 100)
        if t.get("app"):
            self._passo.emit("Scarico l'app…", 0)
            if AggiornaApp.e_appimage():
                errore = AggiornaApp.aggiorna_appimage(
                    t["app"], lambda p: self._passo.emit("Scarico l'app…", p))
            else:
                self._passo.emit("Scarico l'app…", -1)
                errore = AggiornaApp.aggiorna(t["app"])
            if errore:
                self._fine.emit(f"App: {errore}")
                return
            self._passo.emit("App aggiornata", 100)
        self._fine.emit("")

    def _mostra_passo(self, testo: str, percento: int) -> None:
        if percento < 0:
            self.barra.setRange(0, 0)
            self.stato.setText(testo)
        else:
            self.barra.setRange(0, 100)
            self.barra.setValue(percento)
            self.stato.setText(f"{testo} {percento}%")

    def _finito(self, errore: str) -> None:
        if errore:
            self.barra.setVisible(False)
            self.stato.setText(errore)
            self.no.setText("Chiudi")
            self.no.setEnabled(True)
            return
        self.barra.setRange(0, 100)
        self.barra.setValue(100)
        self.stato.setText("Fatto: riavvio l'app…")
        from SubViews.SettingsView import riavvia_app
        QTimer.singleShot(600, riavvia_app)

    def done(self, risultato: int) -> None:
        if not self.si.isEnabled() and not self.no.isEnabled():
            return                      # sta scaricando: non si chiude a meta'
        super().done(risultato)


class _Controllo(QObject):
    trovato = Signal(object)


def avvia(finestra) -> None:
    """Controlla in background e, se serve, mostra il popup sopra `finestra`."""
    controllo = _Controllo(finestra)
    finestra._controllo_aggiornamenti = controllo      # tiene vivo l'oggetto

    def mostra(trovato: dict) -> None:
        if trovato.get("app") or trovato.get("timer"):
            _Avviso(finestra, trovato).exec()

    controllo.trovato.connect(mostra)

    def lavoro() -> None:
        try:
            trovato = AggiornaApp.controlla_avvio()
        except Exception:  # noqa: BLE001 - un controllo che fallisce non deve disturbare
            return
        controllo.trovato.emit(trovato)

    threading.Thread(target=lavoro, daemon=True).start()
