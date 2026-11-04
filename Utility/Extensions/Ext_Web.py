#
#  Ext_Web.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Scaricare una pagina e tenerla come testo.

PERCHE' UN MODULO SOLO
-----------------------
Tre pezzi del programma leggono pagine di jw.org: le notizie, l'argomento
principale della home, e quello che serve per altre cose.  Ognuno lo
faceva per suo conto, e ogni copia aveva la sua eccezione: una pagina che
non arriva era un messaggio diverso in ogni posto, e in un posto solo non
arrivava affatto.

Qui c'e' **un** modo di chiedere una pagina, e un solo modo di dire che e'
fallito: `ErrorePagina`.

PERCHE' `urllib` E NON `requests`
---------------------------------
`requests` non e' nella libreria standard, e un programma che si installa con
un comando solo non puo' chiedere di installare un pacchetto.  `urllib` c'e'
sempre, e per una pagina pubblica fa lo stesso lavoro.

IL TEMPO DI ATTESA
------------------
Venti secondi.  Non di piu': una pagina che non arriva in venti secondi non
arrivera, e l'utente che aspetta un riquadro e' un utente che aspetta.
"""

from __future__ import annotations

import urllib.error
import urllib.request

#: L'utente con cui ci si presenta.  Il sito risponde a un browser vero e
#: non a uno script: senza questa riga la pagina che arriva e' quella per
#: i motori di ricerca, che e' un'altra pagina.
UTENTE = "JWLibrary/1.0 (Linux)"

#: Quanto si aspetta una pagina, in secondi.
TEMPO = 20


class ErrorePagina(Exception):
    """La pagina non e' arrivata, o non si e' potuta leggere."""


def scarica_pagina(url: str, timeout: int = TEMPO) -> str:
    """Il testo della pagina, o un `ErrorePagina`.

    Il testo viene decodificato come `utf-8` con i caratteri che non si
    possono sostituire: una pagina rotta non deve far cadere il programma,
    e un punto di domanda al posto di un carattere e' meglio di niente.
    """
    if not url:
        raise ErrorePagina("indirizzo vuoto")
    richiesta = urllib.request.Request(url, headers={"User-Agent": UTENTE})
    try:
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            return risposta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as errore:
        raise ErrorePagina(f"{url}: HTTP {errore.code}") from errore
    except (urllib.error.URLError, OSError) as errore:
        raise ErrorePagina(f"{url}: {errore}") from errore
