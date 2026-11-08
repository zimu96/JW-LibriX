"""Versione dell'app e indirizzi dei due repository GitHub.

E' il solo posto dove stanno: Impostazioni e installazione del plugin leggono
da qui.  Per cambiare versione o repository si tocca questo file e basta.
"""
from __future__ import annotations

import os

#: La versione dell'app, come la vede l'utente («V1») e come numero.
ETICHETTA_APP = "V1.0.2"
VERSIONE_APP = "1.0.2"

#: I repository su GitHub, nella forma «utente/nome».  Vuoto = non ancora creato.
REPO_APP = "zimu96/JW-LibriX"
REPO_TIMER = "zimu96/JW-LibriX-timer"

#: Il timer si installa dall'ULTIMA release su GitHub; questa versione serve
#: solo se GitHub non risponde alla domanda «qual e' l'ultima?».
VERSIONE_TIMER = "1.0.5"


def url_app() -> str:
    return f"https://github.com/{REPO_APP}" if REPO_APP else ""


def url_zip_timer(versione: str = "") -> str:
    """Da dove si scarica il timer (la `versione` e' senza «v»; vuota = quella fissata sopra).

    `JWL_TIMER_ZIP` (variabile d'ambiente) vince su tutto: serve per provare
    l'installazione con un file locale (`file:///...`) senza GitHub.
    """
    forzato = os.environ.get("JWL_TIMER_ZIP", "").strip()
    if forzato:
        return forzato
    if not REPO_TIMER:
        return ""
    return f"https://github.com/{REPO_TIMER}/archive/refs/tags/v{versione or VERSIONE_TIMER}.zip"
