#
#  BarraBackup.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La barra di avanzamento di importa/esporta, dentro la finestra.

Stesso stile di ``ConfermaApp``: un riquadro viola sopra un velo scuro, niente
finestre di sistema.  Il lavoro gira in un thread, cosi' la finestra non si
blocca e la barra si muove.  Mostra la fase, la percentuale e il tempo
trascorso; alla fine dice «completato» e si chiude da sola, oppure mostra
l'errore con un pulsante per chiuderlo.

Uso::

    BarraBackup.esegui(finestra, "Importo il backup",
                       lambda progresso: Formato.importa_backup(p, progresso),
                       al_termine)          # al_termine(risultato, errore)
"""

import threading
import time

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout)

from Utility import tema


class _Ponte(QObject):
    """Porta i messaggi dal thread alla finestra."""
    avanza = Signal(float, str)
    finito = Signal(object, object)


class BarraBackup(QFrame):

    @staticmethod
    def esegui(padre, titolo: str, lavoro, al_termine=None) -> "BarraBackup":
        finestra = padre.window() if padre is not None else padre
        for vecchia in finestra.findChildren(BarraBackup):
            vecchia._chiudi()
        return BarraBackup(finestra, titolo, lavoro, al_termine)

    def eventFilter(self, oggetto, evento) -> bool:
        if evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def __init__(self, padre, titolo: str, lavoro, al_termine) -> None:
        super().__init__(padre)
        self._al_termine = al_termine
        self._chiusa = False
        self._inizio = time.monotonic()
        self._fermo = False
        self.setObjectName("velo")
        self.setStyleSheet("#velo { background-color: rgba(0, 0, 0, 170); }")
        scheda = QFrame(self)
        scheda.setObjectName("scheda")
        scheda.setFixedWidth(400)
        scheda.setStyleSheet(
            "#scheda { background-color: #2b2b2b; border-radius: 10px; }"
            " #scheda QLabel { color: #f2f2f2; background: transparent; }"
            f" #testata {{ background-color: {tema.ACCENTO};"
            " border-top-left-radius: 10px; border-top-right-radius: 10px; }"
            " QProgressBar { background: #444444; border: none; border-radius: 6px;"
            " height: 12px; text-align: center; color: transparent; }"
            f" QProgressBar::chunk {{ background: {tema.ACCENTO}; border-radius: 6px; }}"
            " QPushButton { border: none; border-radius: 6px; padding: 9px 18px;"
            f" font-weight: 700; color: #ffffff; background-color: {tema.ACCENTO}; }}")
        colonna = QVBoxLayout(scheda)
        colonna.setContentsMargins(0, 0, 0, 16)
        colonna.setSpacing(12)

        testata = QFrame(scheda)
        testata.setObjectName("testata")
        riga = QHBoxLayout(testata)
        riga.setContentsMargins(16, 12, 16, 12)
        t = QLabel(titolo, testata)
        t.setStyleSheet("font-size: 15px; font-weight: 700;")
        riga.addWidget(t)
        colonna.addWidget(testata)

        self._fase = QLabel("Avvio\u2026", scheda)
        self._fase.setWordWrap(True)
        self._fase.setContentsMargins(16, 0, 16, 0)
        colonna.addWidget(self._fase)

        self._barra = QProgressBar(scheda)
        self._barra.setRange(0, 1000)
        self._barra.setTextVisible(False)
        riga_barra = QHBoxLayout()
        riga_barra.setContentsMargins(16, 0, 16, 0)
        riga_barra.addWidget(self._barra)
        colonna.addLayout(riga_barra)

        self._info = QLabel("0%  \u00b7  0 s", scheda)
        self._info.setStyleSheet("color: #bdbdbd; font-size: 12px;")
        self._info.setContentsMargins(16, 0, 16, 0)
        colonna.addWidget(self._info)

        self._chiudi_bottone = QPushButton("Chiudi", scheda)
        self._chiudi_bottone.setVisible(False)
        self._chiudi_bottone.clicked.connect(self._chiudi)
        riga_pulsante = QHBoxLayout()
        riga_pulsante.setContentsMargins(16, 0, 16, 0)
        riga_pulsante.addStretch(1)
        riga_pulsante.addWidget(self._chiudi_bottone)
        colonna.addLayout(riga_pulsante)

        esterno = QVBoxLayout(self)
        esterno.addWidget(scheda, 0, Qt.AlignmentFlag.AlignCenter)
        padre.installEventFilter(self)
        self.setGeometry(padre.rect())
        self.show()
        self.raise_()

        self._tempo = QTimer(self)
        self._tempo.timeout.connect(self._aggiorna_tempo)
        self._tempo.start(200)

        self._ponte = _Ponte(self)
        self._ponte.avanza.connect(self._avanza)
        self._ponte.finito.connect(self._finito)

        def corri() -> None:
            try:
                risultato = lavoro(lambda f, testo="": self._ponte.avanza.emit(float(f), str(testo)))
                self._ponte.finito.emit(risultato, None)
            except Exception as errore:  # noqa: BLE001 - l'errore va mostrato
                self._ponte.finito.emit(None, errore)

        threading.Thread(target=corri, daemon=True).start()

    def _avanza(self, frazione: float, testo: str) -> None:
        if self._fermo:
            return
        self._barra.setValue(int(max(0.0, min(1.0, frazione)) * 1000))
        if testo:
            self._fase.setText(testo)
        self._aggiorna_tempo()

    def _aggiorna_tempo(self) -> None:
        if self._fermo:
            return
        secondi = int(time.monotonic() - self._inizio)
        self._info.setText(f"{self._barra.value() // 10}%  \u00b7  {secondi} s")

    def _finito(self, risultato, errore) -> None:
        self._fermo = True
        self._tempo.stop()
        secondi = int(time.monotonic() - self._inizio)
        if errore is not None:
            self._fase.setText(f"Non riuscito: {errore}")
            self._info.setText("")
            self._chiudi_bottone.setVisible(True)
            self._notifica(None, errore)
            return
        self._barra.setValue(1000)
        self._fase.setText("Completato \u2713")
        self._info.setText(f"100%  \u00b7  {secondi} s")
        QTimer.singleShot(900, lambda: (self._chiudi(), self._notifica(risultato, None)))

    def _notifica(self, risultato, errore) -> None:
        funzione, self._al_termine = self._al_termine, None
        if funzione:
            funzione(risultato, errore)

    def _chiudi(self) -> None:
        if self._chiusa:
            return
        self._chiusa = True
        self._tempo.stop()
        try:
            self.parentWidget().removeEventFilter(self)
        except RuntimeError:
            pass
        self.hide()
        self.deleteLater()
