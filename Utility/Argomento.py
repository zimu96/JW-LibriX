#
#  Argomento.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""L'argomento principale della home di jw.org.

COSA E'
-------
La home di jw.org ha, subito sotto l'intestazione, un riquadro grande con
l'argomento del giorno: la foto, il **titolo in grassetto**, due righe di
introduzione e il tasto «Trova la risposta».  Il titolo e il tasto portano
allo stesso articolo.

Nell'app questo riquadro sta sotto il testo del giorno, e l'articolo si
apre **dentro l'app**, come fanno le notizie: dal titolo o dalla foto.  Il
tasto del sito non c'e': diceva quello che il titolo diceva gia'.

IL PEZZO E' NELLA PAGINA, E L'API NON SERVE
--------------------------------------------
Il sito lo prende con un'API:

    b.jw-cdn.org/apis/alerts/list?type=news&lang=I&limit=1&context=homePage

ma quell'API vuole un token firmato che si prende a un altro indirizzo, e
il 20 ottobre 2026 rispondeva con una lista vuota.  Lo stesso riquadro e'
però **nella pagina** che il sito manda al browser: la classe `billboard` e
il titolo `billboardTitle` sono l'uno e l'altro, e la pagina si scarica
senza token.

Quindi si legge la pagina: una richiesta, nessun token, e il dato e' lo
stesso che il sito mostra.  Se un giorno l'API torna a funzionare e la
pagina smette di portare il riquadro, si cambia qui e non in tre posti.

IL RILIEVO E' SULLA CLASSE, NON SULLA POSIZIONE
----------------------------------------------
Il riquadro si cerca per la sua classe (`billboardTitle`, `billboardDescription`,
`billboardButton`), non per la sua posizione nella pagina: la home cambia
mezzo ogni settimana, e un blocco che sta "dopo il primo banner" smetterebbe
di funzionare senza che nulla lo dica.

SENZA DIPENDENZE
----------------
Come il resto del progetto: `re` e la libreria standard, niente `requests` e
niente BeautifulSoup.  Il HTML di una pagina pubblica non e' un linguaggio
che cambia sotto i piedi, e un programma che si installa con un comando solo
non puo' chiedere di installare un pacchetto.
"""

from __future__ import annotations

import re

from Utility.Extensions.Ext_String import pulito_html
from Utility.Extensions.Ext_Web import ErrorePagina, scarica_pagina

HOST = "https://www.jw.org"

#: Il pezzo di lingua nel percorso.  Non e' il codice del programma: dentro
#: un indirizzo di jw.org l'italiano e' ``/it/`` e l'inglese ``/en/``.
#:
#: Vedi `Utility.Notizie.percorso`, che fa la stessa cosa per la pagina delle
#: notizie: due tabelle uguali in due moduli, e ognuno sa la sua.
PEZZI_LINGUA = {"I": "it", "E": "en"}

#: L'inizio di un riquadro `billboard`.
#:
#: Il pezzo dopo `billboard` non puo' essere una parola: i figli del
#: riquadro sono `billboard-media`, `billboard-content` e
#: `billboard-content-text`, e senza questa guarda il programma prendere per
#: confine del riquadro il primo dei figli, tagliando il riquadro a meta'.
BILBOARD = re.compile(r'<div class="billboard(?![-\w])')

#: Il titolo: dentro l'`h3` c'e' il collegamento all'articolo.
TITOLO = re.compile(
    r'<h3 class="billboardTitle[^"]*">\s*<a href="([^"]+)"[^>]*>(.*?)</a>',
    re.S)

#: La descrizione: due righe di introduzione, dentro un `div`.
DESCRIZIONE = re.compile(
    r'<div class="billboardDescription[^"]*">(.*?)</div>', re.S)

#: La foto del riquadro, messa come sfondo della casella.
FOTO = re.compile(
    r'class="billboard-media-image"[^>]*background-image:\s*url\(([^)]+)\)')


class ErroreArgomento(Exception):
    """La home non e' arrivata, o non aveva il riquadro."""


def percorso(lingua: str | None = None) -> str:
    """Il pezzo di indirizzo della home, per la lingua.

    La home e' la radice del sito: ``/it/`` per l'italiano, ``/en/`` per
    l'inglese.  Non e' la pagina delle notizie (``/it/cosa-nuovo/``): sono
    due pagine diverse, e prendere quella sbagliata fa leggere un elenco di
    articoli al posto di un argomento.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()

    from Utility import Lingua
    pezzo = PEZZI_LINGUA.get(lingua)
    if pezzo is None:
        # Una lingua senza codice noto: si lascia il simbolo e la pagina
        # risponde 404.  Meglio un riquadro vuoto per un motivo vero che un
        # argomento in una lingua che non e' quella scelta.
        pezzo = Lingua.iso_da_simbolo(lingua) or lingua.lower()
    return f"/{pezzo}/"


def indirizzo(lingua: str | None = None) -> str:
    """L'indirizzo della home, per la lingua."""
    return HOST + percorso(lingua)


def _blocco(pagina: str) -> str:
    """Il pezzo di pagina che contiene il riquadro, o "".

    Si prende dal primo riquadro al secondo: dentro, i figli hanno nomi
    che cominciano con `billboard-` e non vengono scambiati per un altro
    riquadro (vedi `BILBOARD`).
    """
    primo = BILBOARD.search(pagina)
    if primo is None:
        return ""
    secondo = BILBOARD.search(pagina, primo.end())
    if secondo is None:
        return pagina[primo.start():]
    return pagina[primo.start():secondo.start()]


def argomento(pagina: str) -> dict:
    """L'argomento dentro una pagina gia' scaricata.

    Restituisce un dizionario vuoto se il riquadro non c'e': una home senza
    argomento e' una home normale, non un errore.  Chi chiama decide cosa
    fare di un dizionario vuoto, e non lo fa qui perche' qui si legge, e non
    si decide.
    """
    blocco = _blocco(pagina)
    if not blocco:
        return {}

    titolo = TITOLO.search(blocco)
    if titolo is None:
        return {}
    collegamento = titolo.group(1)
    if not collegamento.startswith("/"):
        # Un collegamento assoluto si prende come sta; uno relativo si
        # mette sotto il sito, che e' l'unico posto in cui può stare.
        if not collegamento.startswith("http"):
            return {}

    descrizione = DESCRIZIONE.search(blocco)
    testo_descrizione = pulito_html(descrizione.group(1)) if descrizione else ""

    foto = FOTO.search(blocco)

    return {
        "titolo": pulito_html(titolo.group(2)),
        "descrizione": testo_descrizione,
        "url": collegamento if collegamento.startswith("http")
                else HOST + collegamento,
        "immagine": foto.group(1) if foto else "",
    }


def aggiorna(lingua: str | None = None) -> dict:
    """Scarica la home e restituisce l'argomento, o un dizionario vuoto.

    La home e' una pagina sola e pesa poco.  Si rilegge quando la Home
    compare e ogni tanto, e non a ogni giro: l'argomento cambia una volta
    alla settimana, e rileggerlo ogni volta che si apre il programma non
    trova niente di nuovo.
    """
    try:
        pagina = scarica_pagina(indirizzo(lingua))
    except ErrorePagina as errore:
        raise ErroreArgomento(str(errore)) from errore
    return argomento(pagina)


def _prova() -> int:
    """Prova dal vivo: l'argomento di adesso.

        python3 -m Utility.Argomento
    """
    try:
        voce = aggiorna("I")
    except ErroreArgomento as errore:
        print(f"Argomento: la home non e' arrivata ⚠️  {errore}")
        return 1
    if not voce:
        print("Argomento: la home non ha il riquadro (o e' cambiata)")
        return 1
    print(f"{indirizzo('I')}")
    print(f"  titolo:       {voce['titolo']}")
    print(f"  descrizione:  {voce['descrizione']}")
    print(f"  url:          {voce['url']}")
    print(f"  immagine:     {voce['immagine']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_prova())
