#
#  Copertine.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le copertine e le locandine, prese dal CDN.

DUE FAMIGLIE, E NON SI CONFONDONO
---------------------------------
Le copertine sono dei **libri** e si chiedono per la sigla breve:

    img/p/{chiave}/{lingua}/pt/{chiave}_{lingua}_{taglia}.jpg
    img/p/{chiave}/{edizione}/{lingua}/pt/{chiave}_{lingua}_{edizione}_{taglia}.jpg

Le locandine sono di **articoli e video** e si chiedono per il docid:

    img/p/{docid}/univ/{segmento}/{docid}_univ_{forma}_{taglia}.jpg

La differenza non e' una scelta: sono due famiglie diverse, con due
identificatori diversi.  Chiedere una copertina con il docid dà sempre 403,
e chiedere una locandina con la sigla anche.  Tenere i due indirizzi in due
funzioni e' il modo per non confonderli.

LA CHIAVE E' KeySymbol, NON Symbol
---------------------------------
``Symbol`` e' il simbolo lungo usato nelle API (``w26``, ``mwb26``) e
``KeySymbol`` e' quello breve che sta nel nome del file (``w``, ``mwb``).
Con il simbolo lungo il CDN risponde 403 e la griglia si riempie di
spazi vuoti senza che nessuno capisca perche'.

L'EDIZIONE DEI PERIODICI
------------------------
Nei periodici c'e' un pezzo in piu'.  ``IssueTagNumber`` e' un numero tipo
20260500 e l'edizione e' la prima parte: ``20260500 // 100 = 202605``.
Senza divisione l'indirizzo non esiste.

LA MATRICE FORMA-TAGLIA
-----------------------
Non tutte le forme hanno tutte le taglie.  ``xl`` esiste solo dove la forma
e' abbastanza grande a meritarla: chiederla a una panoramica o a una
piccola quadrata dà 403.  Per questo la tabella e' un **dizionario
forma -> taglie**, non una lista sola: una lista accetterebbe combinazioni
che il CDN non ha, e ogni combinazione sbagliata costa una richiesta e un
403.

I 403 NON SI RIPETONO
--------------------
Un 403 e' una risposta, non un errore: vuol dire che quell'immagine non
esiste.  Il caso vero e' Svegliatevi, che esce a novembre: gli altri mesi
non esistono e il 403 e' la risposta giusta.  Quei 403 si ricordano, cosi'
non si richiedono a ogni disegno, e la copertina risulta semplicemente
vuota.  E' quello che deve succedere: il glifo del libro sotto
l'immagine e' il ripiego, non la condizione normale.

LA CACHE
--------
Il file va tenuto, perche' la rete e' lenta e la copertina non cambia.
La misura del progetto precedente: 20 secondi la griglia da quattrocento a
cache fredda, un decimo di secondo a cache calda.  La differenza la fa
tutto.
"""
from __future__ import annotations

import hashlib
import urllib.error
import urllib.request

# Il server delle immagini.  E' un dominio diverso da quello dei media:
# i media stanno su b.jw-cdn.org, le immagini su cms-imgp.  Sono due
# servizi e non si scambiano.
HOST = "https://cms-imgp.jw-cdn.org"

# Le taglie che esistono, per forma.  Verificate con richieste vere: il
# 403 di una combinazione che non c'e' e' una risposta, non un errore.
TAGLIE_LOC = {
    "pnr": ("xs", "sm", "md", "lg"),
    "lsr": ("xs", "sm", "md", "lg", "xl"),
    "lss": ("xs", "sm", "md", "lg", "xl"),
    "sqr": ("xs", "sm", "md", "lg", "xl"),
    "sqs": ("xs", "sm", "md", "lg"),
    "wss": ("xs", "sm", "lg"),
}
#: La forma di default: e' la piu' diffusa e ha tutte le taglie.
FORMA = "lsr"

# Gli indirizzi che si sa gia' non esistere.  Non si richiedono due volte.
_mancanti: set[str] = set()

#: Le copertine "ufficiali": il catalogo delle pubblicazioni dice, per ogni
#: pubblicazione, i nomi delle sue immagini (120, 270 e 600 pixel), e stanno su
#: questo server.  E' la fonte dell'applicazione originale, e le ha quasi tutte;
#: gli indirizzi di `cms-imgp` sono indovinati e per molti titoli danno 403.
BASE_CATALOGO = "https://app.jw-cdn.org/catalogs/publications/"
_LARGHEZZE = {"xs": 120, "sm": 270, "md": 270, "lg": 600}
#: lingua (numero) -> ((data del catalogo), {(sigla, numero): {larghezza: nome}})
_IMMAGINI_CATALOGO: dict[int, tuple] = {}


def _immagini_del_catalogo(lingua_id: int) -> dict:
    """Le immagini del catalogo per una lingua, lette una volta e tenute in memoria."""
    import sqlite3

    from Utility.Extensions.Ext_FileManager import get_documents_directory

    percorso = get_documents_directory() / "catalog.db"
    try:
        data = percorso.stat().st_mtime
    except OSError:
        return {}
    tenuto = _IMMAGINI_CATALOGO.get(lingua_id)
    if tenuto and tenuto[0] == data:
        return tenuto[1]

    indice: dict = {}
    try:
        connessione = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
        try:
            righe = connessione.execute(
                "SELECT p.KeySymbol, p.IssueTagNumber, i.Width, i.NameFragment "
                "FROM Publication p "
                "JOIN PublicationAsset a ON a.PublicationId = p.Id "
                "JOIN PublicationAssetImageMap m ON m.PublicationAssetId = a.Id "
                "JOIN ImageAsset i ON i.Id = m.ImageAssetId "
                "WHERE p.MepsLanguageId = ?", (lingua_id,)).fetchall()
        finally:
            connessione.close()
    except sqlite3.Error:
        return {}
    for sigla, numero, larghezza, nome in righe:
        indice.setdefault((sigla, int(numero or 0)), {})[int(larghezza)] = nome
    _IMMAGINI_CATALOGO[lingua_id] = (data, indice)
    return indice


def url_dal_catalogo(pub, taglia: str = "lg") -> str:
    """L'indirizzo ufficiale della copertina di quella pubblicazione, o "".

    Si sceglie la larghezza che la taglia chiede; se non c'e' la piu' vicina
    piu' grande, e in mancanza la piu' grande che ci sia.
    """
    sigla = getattr(pub, "keySymbol", None)
    if not sigla:
        return ""
    try:
        lingua_id = int(getattr(pub, "mepsLanguageId", 0) or 0)
        if lingua_id <= 0:
            from Utility import Lingua
            lingua_id = Lingua.corrente_id()
        numero = int(getattr(pub, "issueTagNumber", 0) or 0)
    except (TypeError, ValueError):
        return ""
    larghezze = _immagini_del_catalogo(lingua_id).get((sigla, numero))
    if not larghezze:
        return ""
    voluta = _LARGHEZZE.get(taglia, 600)
    scelta = min((w for w in larghezze if w >= voluta), default=max(larghezze))
    return BASE_CATALOGO + larghezze[scelta]


def indirizzi_copertina(pub, taglia: str = "lg") -> list[str]:
    """Gli indirizzi dove cercare la copertina, nell'ordine in cui si provano.

    Sono UNA lista sola, usata sia per leggere la cache sia per scaricare: se le
    due cose costruissero gli indirizzi ognuna per conto suo, una copertina gia'
    scaricata non si ritroverebbe in cache e verrebbe richiesta ogni volta.
    """
    chiave = getattr(pub, "keySymbol", None)
    if not chiave:
        return []
    lingua = _lingua(pub)
    numero = getattr(pub, "issueTagNumber", 0) or 0
    elenco = [url_dal_catalogo(pub, taglia),
              url_copertina(chiave, lingua, taglia)]
    if numero:
        elenco.append(url_copertina(chiave, lingua, taglia, str(numero)))
    return [indirizzo for indirizzo in elenco if indirizzo]


# ---------------------------------------------------------------------------
# GLI INDIRIZZI
# ---------------------------------------------------------------------------


def url_copertina(chiave: str, lingua: str | None = None, taglia: str = "lg",
                  edizione: str = "") -> str:
    """L'indirizzo della copertina di un libro.

    :param chiave: il **KeySymbol** breve, non il Symbol
    :param lingua: la lingua scritta, ``I`` per l'italiano.  Senza questo si
        usa la lingua scelta dall'utente, e non la lettera "I": un valore
        predefinito viene calcolato quando il modulo viene importato, quindi
        "I" significherebbe "italiano per sempre" e una copertina italiana
        sopra una pubblicazione spagnola.
    :param taglia: ``xs``, ``sm``, ``md`` o ``lg``
    :param edizione: per i periodici, l'anno e il mese (``202611``).  Se
        e' vuoto non si mette, e l'indirizzo e' quello dei libri.

    Il nome del parametro e' ``chiave`` e non ``symbolo`` di proposito:
    il nome ricorda cosa va passato, e ``symbolo`` e' il nome lungo che
    qui non funziona.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()
    if edizione:
        return (f"{HOST}/img/p/{chiave}/{edizione}/{lingua}/pt/"
                f"{chiave}_{lingua}_{edizione}_{taglia}.jpg")
    return f"{HOST}/img/p/{chiave}/{lingua}/pt/{chiave}_{lingua}_{taglia}.jpg"


def url_locandina(docid, forma: str = FORMA, taglia: str = "xl") -> str:
    """L'indirizzo della locandina di un articolo o di un video.

    ATTENZIONE ALL'ORDINE: ``/univ/`` sta SEMPRE, e solo dopo viene
    ``art`` o ``wpub``.  Saltarlo produce un 403 che sembra "immagine
    assente" e che si perde tempo a cercare altrove.

    :param docid: il numerone che nel CMS identifica la pagina
    :param forma: pnr panoramica, lsr orizzontale, sqr e sqs quadrate
    :param taglia: una di quelle che la forma accetta

    Una combinazione che il CDN non ha restituisce stringa vuota, e non un
    indirizzo che dà 403: e' la stessa cosa detta prima, detta nel punto
    in cui si può evitare di chiedere.
    """
    if forma not in TAGLIE_LOC:
        return ""
    if taglia not in TAGLIE_LOC[forma]:
        return ""
    return (f"{HOST}/img/p/{docid}/univ/art/"
            f"{docid}_univ_{forma}_{taglia}.jpg")


# ---------------------------------------------------------------------------
# LA CACHE
# ---------------------------------------------------------------------------


def cartella_cache() -> str:
    """Dove stanno i file scaricati."""
    from Utility.Structures.Paths import Paths
    cartella = Paths.root / "copertine"
    cartella.mkdir(parents=True, exist_ok=True)
    return str(cartella)


def _percorso(indirizzo: str) -> str:
    """Il nome del file in cache, univoco per indirizzo."""
    nome = hashlib.md5(indirizzo.encode("utf-8")).hexdigest()[:20]
    estensione = ".jpg"
    return f"{cartella_cache()}/{nome}{estensione}"


def gia_in_cache(indirizzo: str) -> bytes | None:
    """I byte dell'immagine gia' scritti in cache.  MAI dalla rete.

    Il fratello di `scarica` che non scarica niente, e serve per una cosa
    precisa: **disegnare subito quello che c'e'**.

    `dati_anteprima` e' la funzione giusta per un thread in background, dove
    un'attesa non costa niente.  Non e' la funzione giusta per costruire una
    griglia: li' l'immagine arriva mezzo secondo dopo, e per un secondo e
    mezzo la card mostra il glifo al posto della locandina — e la seconda
    volta che si apre la stessa sezione quella mezza seconda la si ripaga
    anche se l'immagine e' gia' sul disco.

    Quindi il chiamante fa cosi':

        1. mette subito quello che c'e' in cache (`gia_in_cache`)
        2. manda alla rete, in background, solo quello che manca (`scarica`)

    E' la stessa regola di `dati_gia_in_cache`, quello delle copertine: una
    funzione sola per la domanda «e' gia' qui?», senza rete dentro.
    """
    if not indirizzo:
        return None
    try:
        with open(_percorso(indirizzo), "rb") as f:
            dati = f.read()
        return dati or None
    except OSError:
        return None


def mancante(indirizzo: str) -> bool:
    """Questo indirizzo ha gia' risposto che l'immagine non esiste?

    E' la domanda che il chiamante si fa **prima** di chiedere, per non
    ripetere una richiesta che ha gia' detto no.

    Serve perche' `scarica` mette in `_mancanti` gli indirizzi che hanno
    risposto 403 o 404, e li tiene per tutta la sessione.  Senza questa
    domanda, un caller che ritenta a ogni ridisegno continuerebbe a chiedere
    immagini che non esistono: non riceverebbe niente, quindi non saprebbe che
    sono finite, quindi ripartirebbe — un ciclo che non si ferma e che
    tiene la connessione occupata.

    Il 403 del CDN e' anche veloce: un indirizzo messo fra i mancanti viene
    restituito subito e senza rete, quindi chiederlo costa niente.
    """
    return bool(indirizzo) and indirizzo in _mancanti


def scarica(indirizzo: str) -> bytes | None:
    """I byte dell'immagine, dalla cache o dal CDN.

    None quando l'immagine non esiste: un 403 e' una risposta e vuol dire
    che quell'immagine non c'e', quindi non si distingue dal 404 e non si
    tiene come un errore.
    """
    if not indirizzo or indirizzo in _mancanti:
        return None

    percorso = _percorso(indirizzo)
    try:
        with open(percorso, "rb") as f:
            dati = f.read()
        if dati:
            return dati
    except OSError:
        pass

    try:
        richiesta = urllib.request.Request(
            indirizzo, headers={"User-Agent": "JWLibrary/1.0"})
        with urllib.request.urlopen(richiesta, timeout=20) as risposta:
            dati = risposta.read()
    except urllib.error.HTTPError:
        # 403 o 404: l'immagine non esiste. Si ricorda, e non si chiede
        # piu' per questa sessione.
        _mancanti.add(indirizzo)
        return None
    except (urllib.error.URLError, OSError) as errore:
        print(f"Copertina non raggiungibile: {indirizzo} ⚠️  {errore}")
        return None

    if not dati:
        return None
    try:
        with open(percorso, "wb") as f:
            f.write(dati)
    except OSError as errore:
        print(f"Copertina non messa in cache ⚠️  {errore}")
    return dati


# ---------------------------------------------------------------------------
# LE ANTEPRIME DEI MEDIA
# ---------------------------------------------------------------------------
#
# Un media ha piu' modi di avere un'immagine, e vanno provati in ordine perche'
# ognuno e' piu' affidabile e piu' economico del successivo.
#
# Due famiglie di provenienza, due famiglie di costi:
#
#     LOCALE   dentro il pacchetto scaricato, in ``contents/``.  Non
#              costa niente e non consuma banda: e' gia' sul disco.
#     RETE     dal CDN.  Costa una richiesta e un attesa.
#
# La regola e' la stessa delle copertine e non e' una scelta: **prima
# quello che c'e' in casa, dalla rete solo quello che non c'e'**.  Se il
# media e' scaricato, scaricare anche l'immagine significa scaricare due
# volte la stessa cosa.


def url_anteprima(voce: dict) -> str:
    """L'indirizzo dell'anteprima di un media, o "" se non si puo' sapere.

    :param voce: una voce della risposta del server, come la restituisce
        :func:`MepsAPI.media`

    Restituisce **uno** indirizzo: il preferito.  Per provarli tutti e uscire
    appena uno risponde c'e' `indirizzi_del_media`; questa resta per i
    chiamanti che vogliono un indirizzo e basta, come il player.
    """
    # 1. l'indirizzo gia' scritto dal server: il dato vero, e non si
    #    ricostruisce niente
    immagine = voce.get("trackImage") or {}
    if isinstance(immagine, dict) and immagine.get("url"):
        return immagine["url"]
    # 2. la locandina ricostruita dal docid
    docid = voce.get("docid")
    if docid:
        return url_locandina(docid, "lsr", "xs")
    # 3. niente: non si sa, e non si indovina
    return ""


def indirizzi_del_media(voce: dict) -> list:
    """Gli indirizzi della locandina di un media, dal preferito in poi.

    Perche' una lista e non uno: una misura puo' non esistere sul CDN mentre
    un'altra della stessa immagine c'e'.  Misurato su «Melodie del Regno»:
    `sqr/md` risponde 403 e `sqr/lg` risponde 200 sugli stessi 18 inni.  Con
    un solo indirizzo, un terzo della categoria restava senza immagine e il
    difetto si vedeva come «manca il riquadro di anteprima», che e' un
    rimprovero al programma per una cosa che era un 403.

    Sono due pezzi, presi da due posti, e si mettono insieme perche' la voce
    non sa da quale arriva: `MepsAPI` scrive `trackImage` con dentro solo
    `url`, il mediator scrive `url` e `alternative`.
    """
    if not isinstance(voce, dict):
        return []
    immagine = voce.get("trackImage")
    if isinstance(immagine, dict):
        usciti = []
        for chiave in ("url", "alternative"):
            valore = immagine.get(chiave)
            if isinstance(valore, str) and valore:
                usciti.append(valore)
            elif isinstance(valore, list):
                usciti.extend(str(v) for v in valore if v)
        if usciti:
            return usciti
    diretto = voce.get("trackImageUrl")
    if diretto:
        return [str(diretto)]
    docid = voce.get("docid")
    return [url_locandina(docid, "lsr", "xs")] if docid else []


def locandina_del_media(voce: dict, solo_cache: bool = False,
                        pub=None, rapida: bool = False) -> bytes | None:
    """I byte della locandina di un media, video o audio che sia.

    IL PERCHE' DI UNA FUNZIONE NUOVA
    --------------------------------
    La locandina di un media era cercata in tre posti con tre criteri
    diversi, e i tre non trovavano la stessa immagine:

        griglia della sezione   `mepsDocumentId` -> niente, resta il glifo
        player grande           `CatalogoMedia.miniatura_di(pubSymbol)`
        striscia in fondo       `CatalogoMedia.miniatura_di(pubSymbol)`

    Il primo non trovava niente perche' il mediator non scrive
    `mepsDocumentId`: scrive l'indirizzo in `trackImage.url`.  E gli altri
    due non trovavano niente perche' cercano `pubSymbol`, che il mediator
    non scrive neppure — e il secondo, peggio, trattava l'indirizzo come se
    fosse un percorso sul disco (`Path(indirizzo).is_file()`), che con un
    `https://` e' sempre falso: **non funzionava con nessuna voce, neanche
    con quelle che aveva una sigla**.

    Il risultato era che la card, il riquadro del player e la striscia in
    fondo mostravano tre immagini diverse quando ne trovavano una, e il
    glifo quando non trovavano niente.

    L'ORDINE, E PERCHE' PRIMA QUELLO CHE IL SERVER HA SCRITTO
    -------------------------------------------------------
        1. `trackImage` dalla cache   — e' l'indirizzo che c'era gia'
           quando la voce e' arrivata, quindi il file in cache c'e' o non
           c'e' e non si chiede niente
        2. `trackImage` dalla rete    — se `solo_cache` e' falso, e
           provando tutte le misure: vedi `indirizzi_del_media`
        3. il pacchetto e il `docid`  — per i media che vengono da una
           pubblicazione scaricata, dove l'immagine e' dentro il pacchetto

    Il primo punto viene **prima** del pacchetto perche' e' quello che il
    server ha scritto per questa voce precisa: e' l'immagine di *quel*
    brano o di *quel* video, mentre la copertina del libro e' la stessa per
    tutti i 109 cantici e sembrerebbe un pezzo fuori posto.

    `solo_cache` serve alla griglia: li' la domanda e' «disegna subito
    quello che c'e'?», e la rete la chiede in un thread.

    `rapida` e' per le griglie: si ferma alla prima misura che risponde (la
    preferita) invece di scaricarle tutte per prendere la piu' grande, che
    per una miniatura di 100 pixel e' lavoro e banda sprecati (5 richieste
    invece di 1).  Il player grande non la usa e continua a cercare la migliore.
    """
    if not isinstance(voce, dict):
        return None
    candidati = []
    for indirizzo in indirizzi_del_media(voce):
        dati = gia_in_cache(indirizzo) if solo_cache else scarica(indirizzo)
        if dati:
            candidati.append(dati)
            if rapida:
                break
    if candidati:
        # La piu' grande: `indirizzi_del_media` da' piu' misure della
        # stessa immagine, e la prima che risponde non e' per forza la
        # migliore — e' solo quella che c'e'.  Una copertina media scalata
        # nel riquadro grande e' la causa dello «sgranato» che si vedeva.
        return max(candidati, key=len)
    # I media di una pubblicazione scaricata: la locandina e' dentro il
    # pacchetto, e non ha senso chiederla in rete.
    return dati_anteprima(voce, pub) if not solo_cache else None


def dati_anteprima(voce: dict, pub=None) -> bytes | None:
    """I byte dell'anteprima di un media, locale prima.

    L'ordine e' questo:

        1. la locandina dentro il pacchetto, per ``docid``
        2. la copertina del libro dentro il pacchetto
        3. l'indirizzo che il server ha gia' scritto (``trackImage``)
        4. la locandina ricostruita dal ``docid``

    I primi due sono locali e non costano niente.  Il terzo e il quarto
    sono di rete e si usano solo quando il media non e' scaricato.

    I DUE LIVELLI DI RETE NON SONO SCAMBIABILI
    -----------------------------------------
    Misurato su tre pubblicazioni reali:

        lff       72 voci con docid, 112 con trackImage
        sjj        0 voci con docid, 165 con trackImage
        nwtsty     0 e 0:  la Bibbia non ha immagini per i suoi media

    Per il canzoniere non c'e' nessun ``docid`` e si vede solo con
    ``trackImage``.  Per ``lff`` le voci con la durata hanno il ``docid`` e
    il ``trackImage`` vuoto.  Togliendone uno, meta' delle immagini non
    compare, e meta' di quelle non compaiono sono quelle in cima, che si
    vedono di piu'.

    Se tutti e quattro falliscono si mette il glifo.  La mancanza
    dell'immagine non e' un errore e non viene trattata come tale.

    Non tocca Qt: si puo' chiamare da un thread, e va chiamato dal thread
    perche' fa I/O di rete.
    """
    docid = voce.get("docid")

    # --- 1 e 2: il pacchetto, se c'e' ---
    if pub is not None:
        dati = locandina_locale(pub, docid)
        if dati:
            return dati
        dati = copertina_locale(pub)
        if dati:
            return dati

    # --- 3: l'indirizzo gia' scritto dal server ---
    immagine = voce.get("trackImage") or {}
    if isinstance(immagine, dict) and immagine.get("url"):
        dati = scarica(immagine["url"])
        if dati:
            return dati

    # --- 4: la locandina ricostruita dal docid ---
    if docid:
        return scarica(url_locandina(docid, "lsr", "xs"))

    return None


# ---------------------------------------------------------------------------
# LE IMMAGINI PER Qt
# ---------------------------------------------------------------------------


def pacchetto_locale(pub) -> str:
    """La cartella del pacchetto, se e' gia' scompattato.  Altrimenti "".

    Se il pacchetto non c'e' la risposta e' una stringa vuota e non
    ``None``: un percorso vuoto si puo' usare subito, e ``None``
    obbligherebbe a controllare due cose diverse.
    """
    try:
        from Utility.Extensions.Ext_FileManager import (
            extracted_jwpub_exist, get_documents_directory)
        from Utility.JWPubManager import pub_dir_name

        cartella = get_documents_directory() / pub_dir_name(pub)
        if extracted_jwpub_exist(url=cartella):
            return str(cartella)
    except (ImportError, OSError):
        pass
    return ""


def copertina_locale(pub):
    """La copertina che e' GIA' dentro il pacchetto, come dati.

    PERCHE' PRIMA IL LOCALE E POI LA RETE
    ------------------------------------
    Se la pubblicazione e' scaricata, la copertina e' gia' sul disco:
    dentro ``contents/``, e il nome del file e' scritto nel
    ``manifest.json``.  Chiederla alla rete sarebbe scaricare due volte
    la stessa immagine, e per di piu' consumare banda per qualcosa che si
    ha gia'.

    La regola e' semplice e non ha eccezioni: **prima quello che c'e' in
    casa, dalla rete solo quello che non c'e'**.

    Un pacchetto non ha sempre la copertina: la Bibbia e' una cartella di
    capitoli e non ha nessun manifesto.  In quel caso si va alla rete, e va
    bene: e' il caso in cui non c'e' davvero niente in locale.

    :returns: i byte del file, o None se in locale non c'e'.
    """
    import json
    import pathlib

    cartella = pacchetto_locale(pub)
    if not cartella:
        return None
    radice = pathlib.Path(cartella)

    manifesto = radice / "manifest.json"
    try:
        dati = json.loads(manifesto.read_text(encoding="utf-8"))
        immagini = dati.get("publication", {}).get("images", [])
    except (OSError, ValueError):
        return None

    # type 'c' e' la copertina, 't' sono le miniature quadrate.
    # La piu' grande fra le 'c': fra piu' copertine si prende la maggiore,
    # perche' e' quella che si vede meglio rimpicciolita.
    copertine = [i for i in immagini
                 if isinstance(i, dict) and i.get("type") == "c"
                 and i.get("fileName")]
    if not copertine:
        return None
    copertine.sort(key=lambda i: int(i.get("width") or 0), reverse=True)

    for voce in copertine:
        # 'contents' e' la cartella dove stanno i file: il nome che c'e'
        # nel manifesto e' solo il nome, non il percorso.
        percorso = radice / "contents" / voce["fileName"]
        try:
            contenuto = percorso.read_bytes()
            if contenuto:
                return contenuto
        except OSError:
            continue
    return None


def scarica_copertina(pub, taglia: str = "lg") -> bytes | None:
    """La copertina dalla rete, provando i due indirizzi possibili.

    PERCHE' DUE INDIRIZZI E NON UNO
    -------------------------------
    Il percorso con l'edizione si usa per i periodici, e per un libro senza
    edizione.  Ma il CDN non e' coerente: misurato sulla stessa
    pubblicazione,

        img/p/lff/I/pt/lff_I_lg.jpg              200
        img/p/lff/202601/I/pt/lff_I_202601_lg.jpg  403

    La stessa pubblicazione, lo stesso file, e uno dei due indirizzi e'
    sbagliato.  Non si puo' scegliere in anticipo quale sia quello
    giusto, perche' la regola dipende dal titolo e non si scrive a mano.

    Quindi si prova il semplice e, se risponde 403, si prova con
    l'edizione.  Il 403 si ricorda, quindi la seconda volta non si
    richiede piu' niente: una richiesta in piu' al primo disegno e zero
    nei successivi.

    L'EDIZIONE E' IL NUMERO INTERO, E NON I DUE PRIMI MESI
    -------------------------------------------------------
    Qui c'era `str(numero // 100)`, che toglieva gli ultimi due zeri.  Misurato
    sullo stesso numero della Torre di Guardia:

        IssueTagNumber = 20150101      (il numero nel catalogo)
        numero // 100   = 201501       (quello che il codice costruiva)  403
        numero          = 20150101     (quello che funziona)            200

    Non e' una scienza: `IssueTagNumber` e' gia' il numero che va nel
    percorso, e la divisione era un tentativo di fare «anno e mese» che il
    CDN non chiede.  Con la divisione, **nessun** periodico trovava la sua
    copertina — e il sintomo era il segnaposto, che sembra la cosa giusta.

    IL NUMERO FINISCE CON DUE ZERI QUANDO IL GIORNO NON C'E'
    -------------------------------------------------------
    Un numero come `20260900` (Settembre 2026) finisce con `00`: e' un numero
    mensile senza un giorno preciso.  Per quelli non si trova niente, e va
    bene: sono numeri che non sono ancora usciti, e il segnaposto dice la
    verita' meglio di una copertina che non c'e'.
    """
    for indirizzo in indirizzi_copertina(pub, taglia):
        dati = scarica(indirizzo)
        if dati:
            return dati
    return None


def pixmap_da_dati(dati: bytes):
    """Dai byte dell'immagine a un QPixmap, o None.

    Questa funzione e' separata da ``pixmap_copertina`` per un motivo
    preciso: **qui dentro non c'e' rete**.  Solo la decodifica, che e'
    roba di memoria e ci mette un millisecondo.

    Il motivo e' che il caricamento delle copertine deve poter essere
    diviso in due: la rete in un thread, la decodifica sul main thread.
    ``QPixmap`` non si puo' costruire in un thread secondario — e' un
    oggetto grafico e va creato dove c'e' la ``QApplication`` — quindi
    il confine deve stare esattamente qui, e non piu' in dentro.
    """
    from PyQt6.QtGui import QPixmap

    if not dati:
        return None
    immagine = QPixmap()
    if not immagine.loadFromData(dati):
        return None
    return immagine


def pixmap_quadrata(immagine, lato: int):
    """Una copertina che riempie un riquadro quadrato, senza deformarsi.

    IL PROBLEMA CHE RISOLVE, MISURATO
    ---------------------------------
    Su `ypq` la copertina e' 599x771.  La card dei Preferiti e' 150x150.  Il
    ``QPixmap`` dentro una ``QLabel`` piu' piccola **non viene ridotto**: la
    ``QLabel`` lo disegna a dimensione naturale e lo taglia.  Il risultato e'
    una copertina che sembra zoomata tre volte, e di cui non si legge ne' il
    titolo ne' la figura: sembra un'immagine sbagliata.

    Due modi per evitarlo, e solo uno va bene:

    ``setScaledContents(True)``   riduce davvero, ma schiaccia: un 599x771 in
                                  un quadrato diventa largo e basso, e una
                                  copertina schiacciata sembra rotta.

    quello qui sotto            riduce tenendo le proporzioni fino a coprire il
                                riquadro, e poi ritaglia il centro.  Una
                                copertina tagliata sembra una miniatura, che e'
                                  quello che deve sembrare.

    IL CENTRO E NON L'ANGOLO
    -----------------------
    Il ritaglio parte dal centro perche' il titolo e la figura di una
    copertina sono al centro.  Con l'angolo in alto a sinistra si taglia via
    proprio quello che si voleva vedere, e si tiene il bordo, che e' la parte
    meno informativa.

    Se l'immagine e' gia' quadrata si limita a ridurre.  Se il riquadro non
    esiste o l'immagine e' vuota, la restituisce com'e': meglio una card con
    l'immagine storta che una card vuota.
    """
    from PyQt6.QtCore import QRect, Qt

    if lato <= 0:
        return immagine
    if immagine is None or immagine.isNull():
        return immagine

    larghezza, altezza = immagine.width(), immagine.height()
    if larghezza <= 0 or altezza <= 0:
        return immagine

    quadrato = immagine.toImage()
    if larghezza == altezza:
        # `_A_QPIXMAP` anche qui, e non solo nell'altra strada.
        #
        # Il ramo dell'immagine gia' quadrata restituiva direttamente il
        # risultato di `scaled`, che e' un **QImage**.  Chi chiama questa
        # funzione la mette in una `QLabel` con `setPixmap`, e li' Qt dice:
        #
        #     TypeError: setPixmap(self, a0: QPixmap): argument 1 has
        #                unexpected type 'QImage'
        #
        # Il tipo di ritorno era quindi diverso a seconda della forma della
        # foto, e l'errore compariva solo con le immagini quadrate.  E'
        # comparso quando sono arrivate le foto delle notizie, che sono
        # quadrate; sulle copertine dei libri, che sono portrait, il ramo
        # giusto era l'altro e il difetto era dormito.
        #
        # Non e' una differenza che si vede leggendo: le due strade facevano
        # la stessa cosa e restituivano la stessa immagine.  Il tipo no.
        return _A_QPIXMAP(quadrato.scaled(
            lato, lato, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    # 1. si riduce fino a COPRIRE il quadrato, tenendo le proporzioni
    grande = quadrato.scaled(
        lato, lato, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation)

    # 2. e si ritaglia il centro del risultato
    x = max(0, (grande.width() - lato) // 2)
    y = max(0, (grande.height() - lato) // 2)
    ritagliato = grande.copy(QRect(x, y, lato, lato))
    return _A_QPIXMAP(ritagliato)


def pixmap_riempi(immagine, larghezza: int, altezza: int):
    """Come `pixmap_quadrata`, per un riquadro di qualunque forma.

    Riduce tenendo le proporzioni fino a coprire il riquadro e ritaglia il
    centro: niente deformazione e niente immagine fuori posto.
    """
    from PyQt6.QtCore import QRect, Qt

    if larghezza <= 0 or altezza <= 0:
        return immagine
    if immagine is None or immagine.isNull():
        return immagine
    grande = immagine.toImage().scaled(
        larghezza, altezza, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation)
    x = max(0, (grande.width() - larghezza) // 2)
    y = max(0, (grande.height() - altezza) // 2)
    return _A_QPIXMAP(grande.copy(QRect(x, y, larghezza, altezza)))


def _A_QPIXMAP(immagine):
    """Da ``QImage`` a ``QPixmap``.  Sta in una funzione perche' l'import di
    ``QPixmap`` deve succedere sul main thread: una ``QPixmap`` costruita in
    un thread secondario e' un errore che Qt segnala a caso."""
    from PyQt6.QtGui import QPixmap

    risultato = QPixmap()
    risultato.convertFromImage(immagine)
    return risultato


def pixmap_copertina(pub, taglia: str = "lg"):
    """La copertina di una pubblicazione, come immagine per Qt.

    ATTENZIONE: CHIAMA LA RETE
    --------------------------
    Questa funzione fa I/O di rete e non va chiamata dal main thread
    mentre si disegna.  Nella griglia delle pubblicazioni non viene usata:
    li' il caricamento passa da ``carica_in_background``, che scarica in
    un thread e decodifica sul main.

    Va bene per una schermata che mostra quattro righe, dove anche un
    secondo di attesa non si vede.  Male per una griglia di 3.741 righe:
    il congelamento e' certo, e la finestra si blocca e poi riparte
    mentre le immagini arrivano una alla volta.

    :returns: un QPixmap, o None se l'immagine non esiste.

    None e' un risultato normale, non un errore: due libri su quaranta non
    hanno copertina su nessuna taglia, e per quelli si mostra il glifo.

    IL NOME CHE SI USA
    ------------------
    ``pub.keySymbol``, non ``pub.symbol``.  Il simbolo lungo dà 403 e il
    glifo sembra una copertina scaricata male invece che un'immagine che
    non c'e'.
    """
    return pixmap_da_dati(dati_copertina(pub, taglia))


def dati_gia_in_cache(pub, taglia: str = "lg") -> bytes | None:
    """I byte della copertina, **solo** dalla cache.  MAI dalla rete.

    PERCHE' ESISTE, E NON `dati_copertina`
    -------------------------------------
    `dati_copertina` controlla la cache e poi, se non c'e', chiede al CDN.  E'
    la funzione giusta per un thread in background, dove un secondo di attesa
    non costa niente perche' l'utente sta guardando altro.

    Non e' la funzione giusta per **disegnare una griglia**: li' la copertina
    arriva almeno mezzo secondo dopo, e per un secondo e mezzo la card mostra
    l'icona al posto dell'immagine.  E la seconda volta che si apre la stessa
    categoria quella mezza seconda la si ri-paga — con la copertina gia' sul
    disco da prima, quindi senza alcun motivo.

    Qui si leggono **solo i file**: niente rete, niente attesa, e quando il file
    non c'e' si risponde subito None.  Il chiamante fa cosi':

        1. mette subito quello che c'e' in cache, e la griglia e' completa subito
        2. manda alla rete, in background, solo quello che manca

    I due indirizzi sono provati nello stesso ordine di `scarica_copertina`:
    prima quello semplice e poi quello con l'edizione.  Se l'ordine cambiasse,
    una copertina gia' scaricata non si troverebbe piu' in cache e verrebbe
    richiesta di nuovo ogni volta.

    ATTENZIONE: non si mette niente in `_mancanti`.  Quella lista serve a non
    ripetere una richiesta che ha risposto 403, e qui non ci sono richieste.
    """
    # Il pacchetto prima della cache: e' sul disco, non costa niente, e la
    # copertina li' e' quella vera e non una miniatura.
    dati = copertina_locale(pub)
    if dati:
        return dati

    for indirizzo in indirizzi_copertina(pub, taglia):
        try:
            with open(_percorso(indirizzo), "rb") as f:
                dati = f.read()
            if dati:
                return dati
        except OSError:
            continue
    return None


def dati_copertina(pub, taglia: str = "lg") -> bytes | None:
    """I BYTE della copertina.  Nessuna immagine, nessun Qt.

    Questa e' la funzione che si puo' chiamare da un thread: legge il
    pacchetto, controlla la cache, e se non c'e' chiede al CDN.  Non
    tocca Qt, quindi non importa dove gira.

    Va usata insieme a ``pixmap_da_dati``, che va chiamata sul main
    thread perche' crea un ``QPixmap``.
    """
    # 1. il pacchetto: e' gia' sul disco, non costa niente
    dati = copertina_locale(pub)
    if dati:
        return dati
    # 2. la rete, provando i due indirizzi
    return scarica_copertina(pub, taglia)


def locandina_locale(pub, docid):
    """La locandina di un articolo, se e' dentro il pacchetto.

    Gli articoli hanno le immagini dentro il pacchetto scompattato, con lo
    stesso criterio delle copertine.  Quando l'articolo e' scaricato si
    prende da li', e non si chiede niente alla rete.
    """
    import json
    import pathlib

    cartella = pacchetto_locale(pub)
    if not cartella:
        return None
    radice = pathlib.Path(cartella)
    try:
        dati = json.loads((radice / "manifest.json").read_text(encoding="utf-8"))
        immagini = dati.get("publication", {}).get("images", [])
    except (OSError, ValueError):
        return None
    for voce in immagini:
        if not isinstance(voce, dict):
            continue
        nome = voce.get("fileName") or ""
        # il docid e' dentro il nome del file: 1102015820_univ_lsr-1200x600.jpg
        if str(docid) not in nome:
            continue
        # 'univ_lsr' e' la piu' diffusa e serve per la maggior parte dei
        # posti; le altre forme servono a chi chiede il formato.
        if "_univ_lsr" in nome:
            try:
                contenuto = (radice / "contents" / nome).read_bytes()
                if contenuto:
                    return contenuto
            except OSError:
                continue
    return None


def _lingua(pub) -> str:
    """La lingua scritta, in forma breve.

    Era un dizionario di due voci scritto qui: con la lingua nuova non e'
    piu' italiano e inglese e basta, quindi il dizionario non rispondeva piu'.
    """
    from Utility import Lingua
    return Lingua.da_numero(getattr(pub, "mepsLanguageId", Lingua.PREDEFINITA))


def pixmap_locandina(docid, forma: str = FORMA, taglia: str = "xl"):
    """La locandina di un articolo o di un video, come immagine per Qt."""
    from PyQt6.QtGui import QPixmap

    dati = scarica(url_locandina(docid, forma, taglia))
    if not dati:
        return None
    immagine = QPixmap()
    if not immagine.loadFromData(dati):
        return None
    return immagine

