#
#  CodaPlaylist.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Suona una playlist: un elemento dopo l'altro, rispettando il taglio.

Si appoggia al motore unico (``Lettore.motore()``), lo stesso del mini player e
del lettore grande: non ne crea uno suo.  Il primo elemento lo fa partire la
finestra (``suona_primo``), che sa aprire il lettore giusto; i successivi li
suona il motore, sullo stesso lettore.

IL TAGLIO
---------
Un elemento ha un inizio e una fine (millisecondi).  All'avvio si salta
all'inizio; mentre suona si guarda la posizione e, arrivati alla fine — o alla
fine naturale del file, se non c'e' un limite — si passa al successivo.

LA CODA SI FERMA DA SOLA
------------------------
Se nel motore parte un file diverso da quello che la coda ha chiesto (l'utente
ha scelto altro), la coda si disattiva: non deve saltare un brano che non e' suo.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QTimer

from Utility import Lettore
from Utility.UserData import PlaylistManager

#: Prima di questo tempo dall'avvio di un elemento non si controlla la fine:
#: il motore puo' ancora riportare la posizione di prima.
TEMPO_DI_ASSESTAMENTO_MS = 700
MARGINE_FINE_MS = 300


class CodaPlaylist(QObject):

    def __init__(self, suona_primo, parent=None) -> None:
        super().__init__(parent)
        self._suona_primo = suona_primo
        self._elementi: list[dict] = []
        self._indice = -1
        self._attiva = False
        self._percorso: Path | None = None
        self._cronometro = QTimer(self)
        self._cronometro.setSingleShot(True)
        self._pronta = True
        self._agganciata = False

    @property
    def attiva(self) -> bool:
        return self._attiva

    def parti(self, elementi: list[dict], indice: int = 0) -> bool:
        """Comincia da un elemento.  False se non c'e' niente da suonare."""
        utili = [e for e in elementi
                 if PlaylistManager.percorso_file(e["file"]).is_file()]
        if not utili:
            return False
        scelto = elementi[indice]["id"] if 0 <= indice < len(elementi) else utili[0]["id"]
        self._elementi = utili
        self._indice = next((i for i, e in enumerate(utili) if e["id"] == scelto), 0)
        self._attiva = True
        self._aggancia()
        self._suona(primo=True)
        return True

    def ferma(self) -> None:
        self._attiva = False

    def avanti(self) -> None:
        if not self._attiva:
            return
        if self._indice + 1 < len(self._elementi):
            self._indice += 1
            self._suona(primo=False)
        else:
            self._attiva = False
            Lettore.motore().sospendi()

    # ------------------------------------------------------------------

    def _aggancia(self) -> None:
        if not self._agganciata:
            Lettore.motore().mosso.connect(self._controlla)
            self._agganciata = True

    def _suona(self, primo: bool) -> None:
        elemento = self._elementi[self._indice]
        percorso = PlaylistManager.percorso_file(elemento["file"])
        self._percorso = percorso
        self._pronta = False
        if primo:
            self._suona_primo(percorso, elemento["titolo"])
        else:
            Lettore.motore().suona(percorso, elemento["titolo"])
        inizio = elemento.get("inizio_ms") or 0
        if inizio:
            QTimer.singleShot(250, lambda: self._salta(percorso, inizio))
        QTimer.singleShot(TEMPO_DI_ASSESTAMENTO_MS, self._assestata)

    def _salta(self, percorso: Path, inizio: int) -> None:
        if self._attiva and self._percorso == percorso:
            Lettore.motore().volta_alla_posizione(inizio)

    def _assestata(self) -> None:
        self._pronta = True

    def _controlla(self, posizione: int, durata: int) -> None:
        if not self._attiva or not self._pronta or self._percorso is None:
            return
        if self._percorso.name not in (Lettore.motore().sorgente() or ""):
            self._attiva = False
            return
        elemento = self._elementi[self._indice]
        fine = elemento.get("fine_ms")
        if not fine and durata > 1000:
            fine = durata - MARGINE_FINE_MS
        if fine and posizione >= fine:
            self.avanti()
