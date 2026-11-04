"""L'avanzamento degli scaricamenti di video e audio, per chi lo vuole vedere.

La finestra principale scarica; altre schermate (il pannello Contenuti del
timer) vogliono mostrare la barra sulla loro riga.  Si parlano da qui, con
una chiave che dice quale media e': (sigla, traccia, numero, tipo), la stessa
di `JWPubManager._chiave_media`.

    iniziato(chiave, totale)        il file e' scelto e parte
    avanza(chiave, scritti, totale) byte arrivati
    finito(chiave, esito)           "ok", "errore" o "annullato"

I segnali si possono emettere anche dal thread dello scaricamento: Qt li
consegna sul main thread da solo.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class _Canale(QObject):
    iniziato = pyqtSignal(object, int)
    avanza = pyqtSignal(object, int, int)
    finito = pyqtSignal(object, str)


_canale: _Canale | None = None


def canale() -> _Canale:
    global _canale
    if _canale is None:
        _canale = _Canale()
    return _canale


def chiave_di(voce: dict):
    """La chiave di una voce di media, o None se non ne ha abbastanza."""
    try:
        return (voce["sigla"], int(voce["traccia"]), int(voce.get("numero") or 0),
                voce["tipo"])
    except (KeyError, TypeError, ValueError):
        return None
