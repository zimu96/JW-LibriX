#
#  Rete.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""C'e' internet?  Una risposta che non fa mai aspettare.

``noto()`` risponde subito con l'ultimo esito conosciuto (all'inizio si suppone
di si'): serve a chi deve decidere cosa mostrare mentre disegna.  ``controlla()``
fa la prova vera — una connessione al server dei contenuti — e va chiamata da un
thread; ``aggiorna_ogni()`` la ripete a intervalli, cosi' se la rete va e viene
i pulsanti seguono.
"""

from __future__ import annotations

import socket

SERVER = ("app.jw-cdn.org", 443)
_online = True

#: Rete chiusa a forza: vale solo al primissimo avvio, finche' l'utente non
#: ha scelto la cartella dati.
_bloccata = False


def blocca(bloccata: bool) -> None:
    """Chiude (o riapre) la rete di tutto il programma.

    OFFLINE FINO ALLA SCELTA DELLA CARTELLA DATI
    --------------------------------------------
    Al primissimo avvio tutto quello che l'app scaricasse (Bibbia, notizie,
    copertine) finirebbe nella cartella predefinita, prima che l'utente abbia
    scelto dove vuole i dati.  Tutte le richieste del programma passano da
    `urllib.request.urlopen`, quindi basta chiudere quello: chi chiama
    riceve un `URLError`, che gia' gestisce come «sono offline».  Non si
    scrive niente nelle impostazioni: vale per questo avvio, e dopo la
    scelta l'app si riavvia con la rete aperta.
    """
    global _bloccata
    import urllib.error
    import urllib.request
    _bloccata = bool(bloccata)
    if not _bloccata or getattr(urllib.request.urlopen, "_chiuso_da_rete", False):
        return
    originale = urllib.request.urlopen

    def urlopen_offline(*argomenti, **opzioni):
        if _bloccata:
            raise urllib.error.URLError("offline: prima si sceglie la cartella dati")
        return originale(*argomenti, **opzioni)

    urlopen_offline._chiuso_da_rete = True
    urllib.request.urlopen = urlopen_offline


def noto() -> bool:
    """L'ultimo esito conosciuto.  Non fa rete."""
    return _online and not _bloccata


def controlla(timeout: float = 2.0) -> bool:
    """La prova vera.  Fa rete: da un thread."""
    global _online
    if _bloccata:
        return False
    try:
        with socket.create_connection(SERVER, timeout=timeout):
            _online = True
    except OSError:
        _online = False
    return _online
