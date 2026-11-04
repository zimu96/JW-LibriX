#
#  Utility/Condivisione.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Condividere una pubblicazione: il file locale e l'indirizzo del sito.

L'INDIRIZZO DEL SITO E' STATO MISURATO, NON INDOVINATO
------------------------------------------------------
Il sito risponde 404 a quasi tutto quello che si prova a scrivere a mano, e
alla pagina giusta si arriva solo da un indirizzo che sa il sito.  Quindi
sono state provate le forme, una per una:

    https://www.jw.org/                                     200  -> /it/
    https://www.jw.org/it/                                  200
    https://www.jw.org/find?pub=sn&lang=I                   404
    https://www.jw.org/it/biblioteca/libri/                 404
    https://www.jw.org/it/biblioteca-digitale/libri/        200
    https://www.jw.org/open?srcid=sn&lang=I                 200  -> la home
    https://www.jw.org/open?docid=1102009080&srcid=sn       200  -> la pagina

L'ultima e' quella che serve.  ``docid`` e' il MepsDocumentId e ``srcid`` e'
la sigla della pubblicazione, e i due si prendono dal pacchetto che e'
gia' sul disco:

    https://www.jw.org/open?docid=1102009080&srcid=sn
      -> https://www.jw.org/en/library/music-songs/Sing-to-Jehovah/God-Is-Love/
         titolo: "God Is Love"

IL LIMITE, DICHIARATO
---------------------
``srcid`` da solo porta alla home del sito: **non c'e' un indirizzo
calcolabile per la pubblicazione intera.**  Il sito la chiama con un suo
slug leggibile — ``lff`` diventa ``puoi-vivere-felice-per-sempre/`` — e lo
slug cambia a ogni traduzione, quindi non si può ricavare dalla sigla.

Qui, per una pubblicazione, si condivide la pagina del **primo capitolo**.
Non e' la pagina della pubblicazione: e' la prima pagina che il sito
riconosce come sua.  Le due cose diverse restano distinte nel codice, e per
un audio o un video si usa sempre il documentid esatto, che e' quello giusto.

IL FILE LOCALE
--------------
Un pacchetto scaricato e' una cartella di 161 MB: non c'e' un file da
mandare.  "Condividi file" mette quindi **il percorso sulla lavagnetta**, che
e' quello che si puo' incollare in una chat, in un campo di un program's
di messaggi o nella barra di un file manager.  Il pacchetto resta dove e' e
non viene spostato ne' copiato: 161 MB copiati di nascosto sarebbero il modo
piu' rapido per riempire un disco.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SITO = "https://www.jw.org"


def primo_documento(cartella: Path) -> int | None:
    """Il MepsDocumentId del primo capitolo, o None.

    Serve per l'indirizzo della pubblicazione: vedi la nota in cima, il sito
    non ha un indirizzo calcolabile per la pubblicazione intera.

    Si prende il `MepsDocumentId` e non il `DocumentId`: sono due numeri
    diversi, e solo il primo e' quello che il sito conosce.  Per `sn` il primo
    capitolo e' `DocumentId` 0 e `MepsDocumentId` 1102009235, e con il numero
    sbagliato l'indirizzo porta a una pagina che non c'e'.
    """
    nome = Path(cartella).name
    database = Path(cartella) / "contents" / f"{nome}.db"
    if not database.is_file():
        return None
    try:
        connessione = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        riga = connessione.execute(
            "SELECT MepsDocumentId FROM Document ORDER BY DocumentId LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connessione.close()
    return int(riga[0]) if riga and riga[0] is not None else None


def url_documento(docid: int, sigla: str) -> str:
    """L'indirizzo nel sito di un capitolo, un audio o un video."""
    return f"{SITO}/open?docid={int(docid)}&srcid={sigla}"


def url_traccia(voce: dict, sigla: str) -> str | None:
    """L'indirizzo di una voce dei media, se ha un DocumentId.

    Una voce che non ha `mepsDocumentId` non ha un indirizzo: si rimanda a
    None e chi chiama non mette la voce nel menù.  Un indirizzo che porta
    alla pagina sbagliata è peggio di un indirizzo che non c'è, perché
    l'utente lo apre e vede che non è quella cosa che pensava.
    """
    docid = voce.get("mepsDocumentId") or voce.get("mepsdocumentid")
    if not docid:
        return None
    try:
        return url_documento(int(docid), sigla)
    except (TypeError, ValueError):
        return None


def url_pubblicazione(cartella: Path, sigla: str) -> str | None:
    """L'indirizzo di una pubblicazione scaricata.

    Il sito non ha un indirizzo per la pubblicazione intera (vedi la nota in
    cima), quindi si prende il primo capitolo.  Se il pacchetto non c'è o non
    ha capitoli, si rimanda a None: senza un documentid non si può scrivere
    un indirizzo che il sito accetterebbe.
    """
    docid = primo_documento(cartella)
    if docid is None:
        return None
    return url_documento(docid, sigla)


def percorso_locale(cartella: Path) -> Path:
    """Il percorso della cartella del pacchetto, come si vede sul disco."""
    return Path(cartella).expanduser()


def condividi_file(cartella: Path, widget=None) -> tuple[bool, str]:
    """Mette il percorso del pacchetto sulla lavagnetta.

    Ritorna (fatto, messaggio): il chiamante lo mostra nella barra di stato,
    perche' un'azione senza risposta sembra un'azione che non e' successa.

    Il percorso viene messo come testo e non come collegamento a un file:
    `mimeData.setUrls` metterebbe un collegamento che solo alcune
    applicazioni aprono, e su un pacchetto di 161 MB la cosa utile da
    incollare è il percorso.

    Niente viene copiato ne' spostato: 161 MB presi in copia di nascosto
    riempiono un disco, e il pacchetto è una copia scaricabile mentre il
    segnalibro è la sola cosa che non lo è.
    """
    percorso = percorso_locale(cartella)
    appoggio = widget
    if appoggio is None:
        try:
            from PyQt6.QtWidgets import QApplication
            appoggio = QApplication.instance()
        except ImportError:
            return False, "PyQt6 non c'è: niente lavagnetta"
    if appoggio is None:
        return False, "Non c'è nessuna finestra a cui dare la lavagnetta"

    appoggio.clipboard().setText(str(percorso))
    return True, f"Copiare il percorso: {percorso}"