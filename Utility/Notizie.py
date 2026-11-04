#
#  Utility/Notizie.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le notizie vere: la pagina "Cosa c'e' di nuovo" di jw.org.

L'INDIRIZZO E' STATO MISURATO, NON INDOVINATO
---------------------------------------------
Le notizie non arrivano da nessuna API: arrivano da una pagina.  L'host delle
API e' ``b.jw-cdn.org`` (vedi `Utility/Mediator.py`), ma le notizie stanno
soltanto in

    https://www.jw.org/it/cosa-nuovo/

Ho provato sei varianti di feed (``/it/rss/cosa-nuovo.xml``, ``/it/feed/``,
``/feed/``, ``?output=xml``, ...) e tutte danno 404 o restituiscono la pagina
stessa.  Quindi non c'e' un feed: c'e' una pagina, e si legge quella.

La pagina e' in italiano perche' anche l'app e' in italiano: il percorso comincia
con ``/it/`` e finisce con il nome della sezione.  Cambiando lingua si cambia
quest'ultimo pezzo, non l'host — vedi `_percorso`.

LA FORMA DELLA PAGINA, MISURATA SU QUELLA VIVA
----------------------------------------------
Ogni voce e' un ``<div class="synopsis ...">`` e dentro ci sono i campi con
classi che non cambiano:

    <p class="meta pubDate">2026-09-30</p>
    <p class="contextTitle">NEWS</p>
    <h3><a href="/it/news/...">Il titolo</a></h3>
    <p class="desc">La descrizione</p>

e l'immagine e' in un attributo ``data-img-size-md='...'`` dentro uno
``<span class='jsRespImg'>``, perche' la pagina serve la stessa foto in
cinque misure e sceglie con il CSS.

PERCHE' SI CERCA UNA VOCE E NON UNA SEZIONE
-------------------------------------------
Il blocco di benvenuto ("Scopri cosa c'e' di nuovo") ha la stessa classe ma
non ha una data, e il suo link punta alla pagina stessa.  Se non si distingue,
il primo elemento della lista sarebbe sempre la pagina che si sta gia'
leggendo: sembrerebbe una notizia e aprendo l'utente resterebbe li' senza
capire perche'.

La prova e' la data (``<p class="meta pubDate">``), non la classe: e' un dato
vero del contenuto, mentre la classe e' un nome di questo template e può
cambiare senza avviso.

CHE COSA NON E' UNA NOTIZIA
--------------------------
Nella pagina ci sono anche cose che **non sono articoli da leggere**: i numeri
nuovi delle riviste e le canzoni.  Il 2 ottobre 2026, delle 19 voci cinque
erano di questo tipo:

    4   /biblioteca-digitale/riviste/torre-di-guardia-studio-dicembre-2026/
        -> La Torre di Guardia, dicembre 2026: e' una pubblicazione
    1   /biblioteca-digitale/musica/canzoni/Ho-fede-in-te/
        -> e' una canzone

Mostrarle fra le notizie era sbagliato in due modi.  Primo: l'utente premeva
una card perche' credeva di leggere un articolo e gli si offriva il numero di
dicembre da scaricare.  Secondo, e peggiore: la stessa cosa compariva **due
volte**, nella striscia delle notizie e nella sezione Novita' che la cerca
anche lei.  Due posti per la stessa cosa, e il giorno che uno dei due dice
una cosa diversa dall'altro non si sa quale sia quella giusta.

Quindi `voci()` restituisce **solo gli articoli**, e gli altri due tipi si
riconoscono dalla famiglia dell'indirizzo — l'unica cosa misurata e stabile,
perche' `docClass` non e' un tipo di pubblicazione (vedi sotto).

IL `docClass` NON C'E' NEL CATALOGO
----------------------------------
Ogni voce porta nella classe un numero come ``docClass-137``.  Sembrava la
chiave per capire che cosa e', ma cercato in ``catalog.db`` per l'italiano:

    tipo 137: 0 righe      tipo 142: 0 righe      tipo 152: 0 righe

Sono zero.  Se la classificazione fosse usata quello, tutto finirebbe fra gli
articoli e le quattro riviste resterebbero dove sono adesso.  Percio' qui si
usa l'indirizzo e il numero si lascia stare: e' un dato del sito, e senza un
posto corrispondente nel catalogo non c'e' niente da confrontare.

DOVE VANO I DUE TIPI ESCLUSI
---------------------------
Non spariscono: sono gia' in due posti veri.  Le riviste sono pubblicazioni
del catalogo (``w``, tipo 14, numero ``20261200``) e la sezione Novita' le
trova da sola; le canzoni sono tracce audio e le vede la sezione Multimedia.
Per questo non si duplica niente qui dentro: si toglie solo quello che era
sbagliato.

LE NOTIZIE SI APRONO DENTRO L'APP
---------------------------------
Una notizia e' una pagina web, e il programma ha gia' un motore di pagine
(`WebBrowserView.WebView`).  Per questo questo modulo **non** apre un browser
di sistema: restituisce l'indirizzo e chi ascolta ci mette dentro quel motore.
Aprire il browser del sistema sarebbe un salto fuori dall'app, con un'altra
finestra, un'altra barra e il pulsante indietro che non funziona piu'.

SENZA DIPENDENZE
----------------
Niente ``requests``, niente ``BeautifulSoup``: si legge con ``re`` e
``html``, come nel resto del progetto.  Il HTML di una pagina pubblica non e'
un linguaggio che cambia sotto i piedi, e una libreria da installare con pip
renderebbe il programma non installabile con un comando.
"""

from __future__ import annotations

import re

from Utility.Extensions.Ext_String import pulito_html
from Utility.Extensions.Ext_Web import ErrorePagina, scarica_pagina

HOST = "https://www.jw.org"

#: La pagina da cui si legge, per lingua.  Italiano e inglese sono le due
#: lingue che il programma usa; per le altre si compone il percorso.
#:
#: I due nomi sono misurati, non tradotti: avevo messo ``new-articles``
#: perche' suona come la sezione inglese, e dà 404.  Quello vero e'
#: ``whats-new``, e contiene le stesse notizie con i titoli in inglese
#: (24 voci, stesse struttura, stesse date).  La prova che sia la pagina
#: giusta e non un 404 morbido e' che dentro ci sono le notizie: sulla
#: home ``https://www.jw.org/en/`` non ce n'e' nessuna.
SEZIONI = {"I": "cosa-nuovo", "E": "whats-new"}

#: Il pezzo di lingua che va nell'indirizzo, che **non** e' il codice del
#: programma: vedi `percorso`.  Italiano e inglese sono le due lingue che il
#: programma usa davvero; le altre sono messe per completezza e valgono solo
#: se la sezione esiste anche in quella lingua, cosa che vale solo per due.
PEZZI_LINGUA = {"I": "it", "E": "en"}

#: I mesi in italiano, per `data_in_italiano`.  Sta qui in cima e non dove
#: nasce la funzione: una tabella usata prima di essere definita funziona
#: solo per caso, e finisce col funzionare finche' nessuno la chiama presto.
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")


class ErroreNotizie(Exception):
    """La pagina non e' arrivata, o non e' quello che si aspettava."""


def percorso(lingua: str | None = None) -> str:
    """Il pezzo di indirizzo che cambia con la lingua.

    Non si indovina: per l'italiano la sezione si chiama ``cosa-nuovo``,
    per l'inglese ``whats-new``, e sono nomi diversi per la stessa cosa.

    LA LINGUA NELL'INDIRIZZO NON E' IL CODICE DEL PROGRAMMA
    ------------------------------------------------------
    Il codice della lingua dentro il programma e' ``I`` e ``E`` — e cosi' lo
    chiama anche il mediator — ma nel percorso di una pagina di jw.org il
    pezzo e' a due lettere: ``/it/``, ``/en/``.  Con la ``I`` si ottiene
    ``/i/cosa-nuovo/``, che e' 404; con ``it`` la pagina c'e'.  Non e' una
    differenza di stile: e' un indirizzo che non esiste.

    Per le lingue con regione il pezzo sono due (``pt-br``, ``zh-cn``), e
    non si possono comporre: si mettono in tabella quelle che il programma
    conosce.  Una lingua che non c'e' in tabella non viene trattata come se
    fosse l'italiano: si compone con il suo codice, la pagina risponde 404,
    e la sezione resta vuota **per un motivo vero**.  Tornare silenziosamente
    all'italiano mostrerebbe notizie in un'altra lingua senza dire niente.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()

    # Il codice ISO sta in `Lingua`, che e' il posto unico dove la tabella
    # dell'originale viene letta.  Qui non si ricopia: una copia significa
    # che un giorno il dato cambia in un posto e non nell'altro, e la pagina
    # di una lingua comincia a rispondere 404 senza che nulla lo dica.
    #
    # `PEZZI_LINGUA` viene prima perche' i due valori che c'erano sono stati
    # misurati sul sito e non dedotti: `it` e `en` sono quelli giunti.
    from Utility import Lingua
    pezzo = PEZZI_LINGUA.get(lingua)
    if pezzo is None:
        # Se la lingua non ha un codice ISO si lascia il simbolo e la pagina
        # risponde 404: meglio una sezione vuota per un motivo vero che
        # notizie italiane sotto una lingua che non e' l'italiano.
        pezzo = Lingua.iso_da_simbolo(lingua) or lingua.lower()
    sezione = SEZIONI.get(lingua)
    if sezione is None:
        sezione = lingua.lower()
    return f"/{pezzo}/{sezione}/"


def indirizzo(lingua: str | None = None) -> str:
    return HOST + percorso(lingua)


#: Le famiglie di indirizzo che sono articoli da leggere.  Solo queste due.
#:
#: La lista e' **chiusa**: quello che non e' qui non e' un articolo.  Una
#: lista aperta — "tutto quello che non comincia per X" — lascerebbe passare
#: le riviste, le canzoni e qualunque cosa nuova il sito aggiunga, e
#: ognuna di quelle comparirebbe due volte: qui e nella sezione che la
#: cerca giustamente.  Meglio che una famiglia nuova resti fuori finche'
#: nessuno ha deciso dove metterla.
FAMIGLIE_DI_ARTICOLI = ("news/", "biblioteca-digitale/articoli/")

#: Le famiglie che NON sono articoli, e dove vanno invece.  Serve solo alla
#: prova: quando il sito aggiunge una famiglia nuova, qui si scrive dove
#: finisce, e senza questa riga sparirebbe dalla lista senza che nulla lo
#: segnali.  Sono tutte misurate sulle pagine del 2 e 3 ottobre 2026.
DOVE_VA_IL_RESTO = {
    "biblioteca-digitale/riviste/": "sezione Novita' — e' una pubblicazione",
    "biblioteca-digitale/articoli/": "restano nelle Notizie (articolo)",
    "biblioteca-digitale/musica/": "sezione Multimedia — e' una traccia audio",
}


def _articolo(percorso: str) -> bool:
    """Questa voce e' un articolo da leggere?

    L'indirizzo comincia con la lingua, `/it/news/...`, quindi il confronto
    non si fa col percorso intero.  E la famiglia non e' nemmeno il primo
    pezzo dopo la lingua: per gli articoli l'indirizzo e'
    `/it/biblioteca-digitale/articoli/...`, quindi la famiglia comincia al
    **secondo** pezzo.

    Percio' si toglie la lingua e si prova il resto contro ogni famiglia.
    Il confronto e' su pezzi interi, con la barra finale: cercare
    `"articoli"` senza la barra prenderebbe anche `/articoli-miei/`, che non
    e' la sezione che si vuole e che non e' mai stata vista.

    MISURATO, E IL NUMERO NON FACEVA SOSPETTARE NULLA
    ----------------------------------------------
    Con il confronto sul primo pezzo dopo la lingua la lista ne teneva 8 su
    20 e perdeva tutti e cinque gli articoli di `/biblioteca-digitale/
    articoli/`: restavano solo le notizie.  Con il confronto giusto ne tiene
    13, e le 5 scartate sono le 4 riviste e la canzone, cioe' esattamente
    quello che non e' un articolo.

    Otto sembrava un numero giusto.  Una lista piu' corta sembra sempre
    giusta, ed e' per questo che il numero va contato e non guardato: se
    dodici voci diventano otto, qualcosa e' stato buttato via, e l'unica
    domanda da fare e' *cosa*.
    """
    pezzi = [p for p in percorso.split("/") if p]
    if len(pezzi) < 2:
        return False
    resto = "/".join(pezzi[1:])
    return any(resto.startswith(famiglia) for famiglia in FAMIGLIE_DI_ARTICOLI)


def voci(pagina: str) -> list:
    """Le notizie dentro una pagina gia' scaricata.

    Si prende il testo, non la pagina: e' cosi' che si puo' provare la lettura
    sulla pagina salvata del 29 settembre senza andare a scaricare niente, e
    vedere se i titoli sono gli stessi.  E' il confronto fra i due che dice se
    la lettura regge.
    """
    trovate = []
    # Si taglia su `class="synopsis` e non su un `<div ...>` generico: e' la
    # classe che sta all'inizio di ogni voce, e cid come segnaposto tiene il
    # testo che segue fino alla voce dopo, senza dover contare i `<div>` che
    # si annidano (e che cambiano da una voce all'altra).
    for blocco in pagina.split('<div class="synopsis')[1:]:
        titolo = re.search(r'<h3>\s*<a href="([^"]+)"[^>]*>(.*?)</a>',
                           blocco, re.S)
        if titolo is None:
            continue
        data = re.search(r'<p class="meta pubDate">([^<]*)</p>', blocco)
        # Una voce senza data non e' una notizia: e' il blocco di benvenuto,
        # che rimanda alla pagina stessa.  Vedi il docstring.
        if data is None:
            continue
        sezione = re.search(r'<p class="contextTitle">\s*(.*?)\s*</p>',
                            blocco, re.S)
        descrizione = re.search(r'<p class="desc">(.*?)</p>', blocco, re.S)
        # `data-img-size-md` e' la misura di mezzo: la piu' piccola delle
        # cinque.  Una striscia di card e' alta 124 pixel, e scaricare la
        # versione grande per metterla in 124 pixel costerebbe quattro volte
        # la banda per la stessa immagine piu' sfocata.
        immagine = re.search(r"data-img-size-md='([^']+)'", blocco)
        if immagine is None:
            immagine = re.search(r"data-img-size-xs='([^']+)'", blocco)
        # il filtro e' sul percorso, non sull'host e non sulla pagina: due
        # notizie hanno lo stesso identico aspetto e una e' un articolo e
        # l'altra no.  Solo l'indirizio lo distingue, ed e' l'unica cosa che
        # il sito mette in chiaro.
        if not _articolo(titolo.group(1)):
            continue
        trovate.append({
            "titolo": pulito_html(titolo.group(2)),
            "sezione": pulito_html(sezione.group(1) if sezione else ""),
            "data": pulito_html(data.group(1)),
            "descrizione": pulito_html(descrizione.group(1) if descrizione else ""),
            "url": HOST + titolo.group(1),
            "immagine": immagine.group(1) if immagine else "",
        })
    return trovate


def aggiorna(lingua: str | None = None) -> list:
    """Scarica la pagina e restituisce le notizie, dalla piu' recente.

    Senza `lingua` si usa la lingua scelta dall'utente.  Il default non e' la
    lettera "I": un valore predefinito viene calcolato quando il modulo viene
    importato, quindi vuol dire "notizie in italiano per sempre" e il menu
    della lingua non cambierebbe nulla.

    L'ordine e' quello del server (dal piu' recente) e non viene riordinato:
    la pagina e' gia' in ordine cronologico, e riordinare qui sarebbe
    rifare un lavoro che il server ha fatto e che potrebbe sbagliare.
    """
    try:
        pagina = scarica_pagina(indirizzo(lingua))
    except ErrorePagina as errore:
        raise ErroreNotizie(str(errore)) from errore
    return voci(pagina)


def data_in_italiano(iso: str) -> str:
    """La data ``2026-09-30`` diventa ``30 settembre 2026``.

    Il mese lo scrive il server gia' in italiano nella pagina ("2026-09-24" e'
    l'ISO grezzo, ma il resto della pagina e' italiano), quindi qui si
    traduce solo il numero e si mette l'anno dopo.  Senza questo la riga
    direbbe ``2026-09-24`` accanto a titoli italiani, e sembrerebbe un
    dettaglio lasciato a meta'.
    """
    if not iso:
        return ""
    parti = iso.split("-")
    if len(parti) != 3:
        return iso
    try:
        anno, mese, giorno = (int(p) for p in parti)
    except ValueError:
        return iso
    if not 1 <= mese <= 12:
        return iso
    return f"{giorno} {MESI[mese - 1]} {anno}"


def scarta(pagina: str) -> list:
    """Le voci della pagina che **non** sono articoli.

    Serve a una cosa sola: a dire, quando le categorie cambiano, che cosa
    e' stato tolto e perche'.  Senza, sparirebbero cinque voci al giorno
    senza che nulla lo segnali, e la sezione sembrerebbe piu' corta a caso.

    IL CONTEGGIO DEVE ESSERE QUELLO DI `voci()`
    ---------------------------------------------
    Si richiede anche la data, come in `voci()`.  Senza, il blocco di
    benvenuto — "Scopri cosa c'e' di nuovo", che rimanda alla pagina
    stessa — verrebbe contato qui come scartato, e la prova direbbe che e'
    finito da qualche parte quando invece non e' mai stato una voce.  Due
    numeri che contano cose diverse sono peggio di nessun numero.
    """
    fuori = []
    for blocco in pagina.split('<div class="synopsis')[1:]:
        titolo = re.search(r'<h3>\s*<a href="([^"]+)"[^>]*>', blocco)
        if titolo is None:
            continue
        if re.search(r'<p class="meta pubDate">', blocco) is None:
            continue
        if not _articolo(titolo.group(1)):
            fuori.append(titolo.group(1))
    return fuori


def _prova() -> int:
    """Prova dal vivo: quante notizie ci sono e se i titoli si leggono.

        python3 -m Utility.Notizie
    """
    try:
        elenco = aggiorna("I")
    except ErroreNotizie as errore:
        print(f"Notizie: il server non risponde ⚠️  {errore}")
        return 1
    pagina = scarica_pagina(indirizzo("I"))
    scartate = scarta(pagina)
    print(f"{indirizzo('I')}\n{len(elenco)} notizie, {len(scartate)} scartate")
    for dove in sorted(set(scartate)):
        famiglia = "/".join([p for p in dove.split("/") if p][1:3]) + "/"
        print(f"   scartata: {famiglia:36} -> "
              f"{DOVE_VA_IL_RESTO.get(famiglia, 'DOVE FINISCE: nessuna nota')}")
    print()
    for voce in elenco:
        con = "con" if voce["immagine"] else "senza"
        print(f"  {data_in_italiano(voce['data']):18} [{voce['sezione'][:20]:20}]"
              f" {voce['titolo'][:56]}")
        print(f"      {voce['url']}")
        print(f"      {con} immagine")
    return 0


if __name__ == "__main__":
    raise SystemExit(_prova())