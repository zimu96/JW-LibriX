#
#  RicercaLocale.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La ricerca dentro la pubblicazione che si sta leggendo.

Si apre sotto la lente della fascia, senza cambiare schermata: un campo, la
casella «Cerca ovunque» e i risultati.  Si cerca scrivendo oppure premendo
Invio.  Vale per qualunque pubblicazione e per la Bibbia.  Premere un risultato
lo apre sopra la pagina di adesso, quindi «indietro» torna dov'eri.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from SubViews.RisultatiTesto import _Riga
from Utility import RicercaTesto
from Utility.Extensions.Ext_DispatchQueue import background

LARGHEZZA = 480
MAX_RIGHE = 8
MIN_CARATTERI = 2


class RicercaLocale(QFrame):
    """Il riquadro di ricerca.  ``scelto`` porta il risultato premuto."""

    scelto = Signal(dict)

    def __init__(self, parent, sigla: str, nome: str) -> None:
        super().__init__(parent)
        self.setObjectName("popupRicerca")
        self._sigla = sigla
        self._numero = 0
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(10, 10, 10, 8)
        colonna.setSpacing(6)

        self.campo = QLineEdit(self)
        self.campo.setPlaceholderText(f"Cerca in «{nome}»")
        self.campo.setClearButtonEnabled(True)
        self.campo.setMinimumHeight(30)
        colonna.addWidget(self.campo)
        self.ovunque = QCheckBox("Cerca ovunque", self)
        colonna.addWidget(self.ovunque)
        self.stato = QLabel("", self)
        self.stato.setObjectName("nota")
        colonna.addWidget(self.stato)
        self._righe = QVBoxLayout()
        self._righe.setSpacing(0)
        colonna.addLayout(self._righe)

        self._attesa = QTimer(self)
        self._attesa.setSingleShot(True)
        self._attesa.setInterval(300)
        self._attesa.timeout.connect(self._cerca)
        self.campo.textChanged.connect(lambda _t: self._attesa.start())
        self.campo.returnPressed.connect(self._cerca)
        self.ovunque.toggled.connect(lambda _s: self._cerca())
        self.campo.installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._focus_cambiato)
        self.setFixedWidth(LARGHEZZA)
        self.hide()

    # ------------------------------------------------------------------

    def apri(self, punto: QPoint) -> None:
        """Si apre con il bordo destro al punto dato (sotto la lente)."""
        self._svuota()
        self.campo.clear()
        self.adjustSize()
        padre = self.parentWidget()
        x = max(8, min(punto.x() - self.width(), padre.width() - self.width() - 8))
        self.move(x, punto.y())
        self.show()
        self.raise_()
        self.campo.setFocus()

    def chiudi(self) -> None:
        self._numero += 1
        self.hide()

    def eventFilter(self, oggetto, evento) -> bool:
        if (oggetto is self.campo and evento.type() == QEvent.Type.KeyPress
                and evento.key() == Qt.Key.Key_Escape):
            self.chiudi()
            return True
        return super().eventFilter(oggetto, evento)

    def _focus_cambiato(self, _vecchio, nuovo) -> None:
        try:
            if self.isVisible() and nuovo is not None and not self.isAncestorOf(nuovo):
                self.chiudi()
        except RuntimeError:
            pass

    def _svuota(self) -> None:
        while self._righe.count():
            elemento = self._righe.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().deleteLater()
        self.stato.setText("")

    def _cerca(self) -> None:
        domanda = self.campo.text().strip()
        self._numero += 1
        numero = self._numero
        if len(domanda) < MIN_CARATTERI:
            self._svuota()
            self.adjustSize()
            return
        sigla = None if self.ovunque.isChecked() else self._sigla
        trovati: list = []

        def lavoro() -> None:
            trovati.extend(RicercaTesto.cerca(domanda, MAX_RIGHE, sigla))

        def fatto() -> None:
            if numero != self._numero:
                return
            try:
                self._mostra(trovati)
            except RuntimeError:
                pass

        background(lavoro, completion=fatto)

    def _mostra(self, risultati: list[dict]) -> None:
        self._svuota()
        if not risultati:
            self.stato.setText("Nessun risultato." if self.ovunque.isChecked()
                               else "Nessun risultato qui. Prova «Cerca ovunque».")
        for r in risultati:
            riga = _Riga(r["titolo"], r["anteprima"], self)
            riga.premuta.connect(lambda r=r: self._premuto(r))
            self._righe.addWidget(riga)
        self.adjustSize()

    def _premuto(self, risultato: dict) -> None:
        self.chiudi()
        self.scelto.emit(risultato)
