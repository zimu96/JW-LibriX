#
#  CatalogoMedia.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il catalogo dei media: che cosa e' uscito di recente, e cosa c'e' da insegnare.

PERCHE' SERVE UN CATALOGO ANCHE PER I VIDEO
--------------------------------------------
Il catalogo delle pubblicazioni elenca i **libri**.  Non elenca i media: per
l'italiano, tutte e 3.741 le voci hanno come formato ``application/x-jwpub``,
e un video non c'e'.  Quindi «le ultime novita' sui video e sull'audio» non
sono una domanda a cui il catalogo delle pubblicazioni possa rispondere, e
non si risponde con quello.

Esiste pero' un secondo catalogo, sullo stesso server e con lo stesso
manifest:

    https://app.jw-cdn.org/catalogs/media/I.json.gz

Misurato il 5 ottobre 2026: 872 KB compressi, 7,3 megabyte scompattati, 4.848
righe, e la data del server era **lo stesso giorno**.  Cambia quindi con la
frequenza del primo, e si tiene come lui.

IL FORMATO: UNA RIGA PER VOCE, NON UN OGGETTO UNO
-------------------------------------------------
Il file non e' un oggetto JSON: e' **JSON su una riga per riga**.  Infatti
scompattando tutto e facendo ``json.loads`` si ottiene

    json.decoder.JSONDecodeError: Extra data: line 2 column 1 (char 38)

che sembra un file rotto e non e' niente del genere: sono 4.848 documenti
JSON attaccati, uno per riga.  Ogni riga ha una chiave ``type``:

    catalogSchemaVersion   una volta, all'inizio
    language               la lingua di questo catalogo
    category               un gruppo di media
    media-item             un video o un pezzo di audio
    signature              la firma del catalogo

E LE CATEGORIE SONO LE SEZIONI DELL'APP ORIGINALE
-------------------------------------------------
Non e' un'ipotesi: sono le sezioni con lo stesso nome e le stesse voci.
`TeachingToolbox`, per esempio, si chiama «Kit dell'insegnante» e ha dentro
quattro voci sui video che si possono usare per insegnare — che e' la
seconda sezione della schermata iniziale dell'app originale.

    TeachingToolbox   «Kit dell'insegnante»       4 voci
    ConvReleases      «Pubblicazioni al congresso» 3 sottogruppi
    VideoOnDemand     «Categorie»                14 sottogruppi
    Audio             «Audio»                    20 sottogruppi
    LatestAudioVideo  «Latest»                   19 voci (crescono)

`LatestAudioVideo` e' la risposta alla domanda «le ultime novita'»: sono
quindici voci, con la data di pubblicazione e la durata, e sono ordinate
dalla piu' recente.  Non si calcola nulla e non si sceglie una data a caso:
e' il server che dice quali sono le ultime.

IL PERCHE' NON SI USA `firstPublished` PER ILLEGGERE IL «RECENTE»
-----------------------------------------------------------------
Perche' si potrebbe, e sarebbe un calcolo: si prende la data di ogni voce e
si tiene quelle degli ultimi trenta giorni.  Ma allora la lista cambierebbe
ogni giorno alle prime ore del mattino, perche' dipenderebbe da quando e' passato
il tempo, e non da quando e' uscito qualcosa.  Il gruppo `Latest` e' scritto
da chi ha fatto il catalogo: se un giorno ci mette dentro una voce di settembre,
e' perche' quella ci sta, e non perche' il programma ha contato i giorni.

`firstPublished` serve, pero', a **mostrare** la data, che e' una cosa che
all'utente serve sapere.

LE MINIATURE VENGONO DA LUI
---------------------------
Ogni voce ha dentro `images`, con gli indirizzi gia' scritti:

    images -> sqr -> xs, sm, md, lg, xl
            -> lsr -> xs, sm, md, lg, xl

E sono indirizzi che funzionano.  Non si ricostruisce nessun indirizzo a mano,
che e' il modo tipico di mettere nel programma un collegamento che oggi va e
domani no.
"""

import gzip
import json
import os
import time

#: Il catalogo dei media sta sulla stessa base di quello delle pubblicazioni,
#: ma in un altro pezzo: `catalogs/media/` e non `catalogs/publications/`.
#:
#: E' l'unico indirizzo conosciuto, ed e' quello documentato in
#: `jwapi-master/notes.txt`.
BASE_MEDIA = "https://app.jw-cdn.org/catalogs/media/"

#: Come il nome della lingua si scrive nel nome del file: `I.json.gz`.
SUFFISSO = ".json.gz"

#: Il gruppo con le ultime novita'.  Chiave e non nome perche' nel file c'e' il
#: nome, ma la chiave e' quello che non cambia fra le traduzioni: «Latest» e'
#: la parola inglese anche nel catalogo italiano, e cercare il nome significherebbe
#: doverlo sapere in ogni lingua.
GRUPPO_RECENTI = "LatestAudioVideo"

#: Il gruppo dei video da usare per insegnare.  Stessa ragione di sopra: la
#: chiave e' inglese anche nel catalogo italiano, e il nome («Kit
#: dell'insegnante») cambia da lingua a lingua.
GRUPPO_INSEGNANTE = "TeachingToolbox"

#: Quante voci tornano da `kit_insegnante()`.
#:
#: Un numero, e non tutto: se ne tornassero trenta, la sezione della Home
#: diventerebbe una fila lunga e la rotella orizzontale servirebbe sempre.  Il
#: gruppo «Kit dell'insegnante» ne ha quattro e il tetto non si vede mai, ma
#: il numero ci resta perche' il catalogo puo' cambiare.
QUANTE = 5

#: Quante voci tornano da `ultime()`.
#:
#: Il gruppo «Latest» ne aveva quindici il 5 ottobre 2026 e ne ha diciannove
#: adesso: cresce, e tutte quante sono roba uscita davvero di recente,
#: ordinata dal piu' recente al meno recente.  Qui il tetto e' alto e non si
#: vede: la sezione della Home e' una **striscia che scorre in orizzontale**,
#: quindi farne scendere altre non allunga la Home e non nasconde niente —
#: si vedono girando la rotella sotto le card.  Mettere il tetto a cinque
#: nascondeva proprio quello che la sezione e' li' per mostrare: dieci video
#: del 3, 25 e 21 settembre erano gia' scaricati e catalogati, e non si
#: vedevano da nessuna parte.
QUANTE_RECENTI = 40

#: Le voci gia' lette, per lingua.  In memoria, non su disco: il file e' gia'
#: su disco, e rileggerlo e' una decina di centesimi.
_in_memoia: dict = {}


def percorso(lingua: str) -> str:
    """Dove sta il catalogo dei media di quella lingua."""
    from Utility.Extensions.Ext_FileManager import get_documents_directory

    cartella = get_documents_directory() / "userData" / "mediaCatalog"
    cartella.mkdir(parents=True, exist_ok=True)
    return str(cartella / f"{lingua}{SUFFISSO}")


def c_e_file(lingua: str) -> bool:
    """Il catalogo dei media e' gia' scaricato?"""
    return os.path.isfile(percorso(lingua))


def _leggi_righe(lingua: str) -> list:
    """Le righe del catalogo, gia' scompattate.  [] se non c'e' il file.

    Si legge riga per riga e non tutto in un colpo: `read()` su 7,3 megabyte
    e poi `splitlines` fa due copie di quei 7,3 megabyte, e il file si tiene
    in memoria per il tempo di una riga sola.
    """
    try:
        with gzip.open(percorso(lingua), "rt", encoding="utf-8") as f:
            return [json.loads(riga) for riga in f if riga.strip()]
    except (OSError, ValueError, EOFError):
        return []


def _leggi(lingua: str) -> dict:
    """Il catalogo diviso in due: i gruppi e le voci.

    :return: ``{"gruppi": {chiave: gruppo}, "voci": {chiave_breve: voce}}``

    LA CHIAVE BREVE
    ---------------
    Le liste dei gruppi chiamano le voci con un nome, e quel nome non e' il
    `naturalKey` della voce: dentro il catalogo ci sono due forme diverse.

        docid-1001072063_I_1_VIDEO     voci che stanno dentro un documento
        pub-osg_I_126_VIDEO            voci di una pubblicazione intera

    I gruppi usano quasi sempre la seconda.  La chiave che si costruisce qui e'
    la stessa che i gruppi usano, e cosi' la corrispondenza e' diretta e non
    una ricerca nel testo: il numero dentro `keyParts` dice quale
    pubblicazione e' e quale traccia, ed e' un dato, non una stringa da
    interpretare.
    """
    if lingua in _in_memoia:
        return _in_memoia[lingua]

    gruppi: dict = {}
    voci: dict = {}
    for riga in _leggi_righe(lingua):
        tipo = riga.get("type")
        corpo = riga.get("o")
        if not isinstance(corpo, dict):
            continue
        if tipo == "category":
            chiave = corpo.get("key")
            if chiave:
                gruppi[chiave] = corpo
        elif tipo == "media-item":
            naturale = corpo.get("naturalKey")
            if naturale:
                voci[naturale] = corpo
            parti = corpo.get("keyParts") or {}
            if "pubSymbol" in parti:
                pezzi = [f"pub-{parti['pubSymbol']}", parti.get("languageCode", lingua)]
                if parti.get("issueDate"):
                    pezzi.append(str(parti["issueDate"]))
                pezzi.append(str(parti.get("track", "")))
                pezzi.append(parti.get("formatCode", ""))
                voci["_".join(pezzi)] = corpo

    risultato = {"gruppi": gruppi, "voci": voci}
    _in_memoia[lingua] = risultato
    return risultato


def voce_di(sigla: str, lingua: str, traccia: int) -> dict:
    """La voce del catalogo di una traccia precisa, o None.

    SERVE A CHI HA UN FILE SUL DISCO E CERCA IL TITOLO
    ---------------------------------------------------
    `MediaScaricati` elenca i video scaricati dalla nuvoletta e deve scrivere
    il nome che l'utente conosce, non quello del file: il file si chiama
    ``wsb_I_02_r720P.mp4`` ma per l'utente e' «Perche' studiare la Bibbia?».
    Il titolo sta nel catalogo, e il catalogo si cerca con sigla, lingua e
    traccia — le tre cose che il nome del file contiene gia'.

    LA RICERCA E' A MANO E NON NELLA MAPPA GRUPPI
    ---------------------------------------------
    La mappa `voci` di `_leggi` e' indicizzata per chiave naturalKey, che
    non si costruisce a ritroso (contiene un docid e un `issueDate` che nel
    nome del file non ci sono).  E' piu' onesto scorrere le voci e
    confrontare `keyParts`: il catalogo e' gia' in memoria dopo la prima
    lettura, e per un pugno di file sciolti il costo non si vede.
    """
    try:
        catalogo = _leggi(lingua)
    except Exception:  # noqa: BLE001 - un catalogo che non si legge non e'
        return None     # un motivo per fermare la sezione dei scaricati
    for voce in catalogo["voci"].values():
        parti = voce.get("keyParts") or {}
        if parti.get("pubSymbol") != sigla:
            continue
        try:
            if int(parti.get("track")) != int(traccia):
                continue
        except (TypeError, ValueError):
            continue
        return voce
    return None


def miniatura_di(sigla: str, lingua: str = "I") -> str:
    """L'indirizzo della miniatura di una pubblicazione di media, o "".

    SERVE ALLE CARD DEI PREFERITI
    ------------------------------
    Una pubblicazione di **testo** ha una copertina, e la card dei Preferiti
    la chiede a `Copertine`.  Una pubblicazione di **media** — ``wsb``,
    ``whbs`` — una copertina non ce l'ha: il server risponde zero byte, e la
    card resta col glifo del libro, che per un video e' il glifo sbagliato.

    La miniatura del video invece c'e', ed e' **scritta nella voce** del
    catalogo dei media (``images.sqr``): non si ricostruisce e non si chiede
    al server una seconda volta.  Si prende la prima con un formato VIDEO,
    che e' quella che si vede aprendo la pubblicazione; se non ce n'e'
    nessuna video si ripiega su una qualsiasi, perche' una miniatura di
    quello che si e' messo nei Preferiti e' meglio del glifo generico.

    Il catalogo puo' non esserci (si sta aggiornando): allora non c'e'
    miniatura, e la card resta com'era.  La mancanza non e' un errore.
    """
    try:
        voci = _leggi(lingua)["voci"].values()
    except Exception:  # noqa: BLE001
        return ""

    ripiego = ""
    for voce in voci:
        parti = voce.get("keyParts") or {}
        if parti.get("pubSymbol") != sigla:
            continue
        immagini = voce.get("images") or {}
        quadrata = immagini.get("sqr") or {}
        indirizzo = quadrata.get("md") or quadrata.get("lg") or ""
        if not indirizzo:
            continue
        if (parti.get("formatCode") or "").upper() == "VIDEO":
            return indirizzo
        if not ripiego:
            ripiego = indirizzo
    return ripiego


def _tracce_di(sigla: str, lingua: str) -> list:
    """Le tracce di una pubblicazione di media, come coppie (numero, formato).

    Ordinate per numero di traccia, e a pari numero il video prima dell'audio.

    LO STESSO PEZZO, DUE FORMATTI: CI SONO ENTRAMBI
    ----------------------------------------------
    Lo stesso programma e' nel catalogo due volte: una come video e una come
    audio (`pub-osg_I_126_VIDEO` e `pub-osg_I_126_AUDIO`), stessa durata,
    stessa uscita.

    Prima qui si teneva **solo il video** a pari numero, e il risultato era
    che l'audio non esisteva.  E' misurato sulla Torre di Guardia (`sjjm`):
    327 tracce, di cui **164** hanno un audio accanto al video — e il
    programma non ne offriva nessuna.  Il menu' delle cuffie chiedeva
    «l'audio di questo pezzo» e la risposta era sempre «non c'e'».

    Ora la lista tiene **entrambi** i formati.  Chi chiede una traccia sola
    (`prima_traccia_di`, `formato_di_traccia`) continua a prendere il video,
    perche' e' il primo della coppia e perche' e' quello che ha la miniatura.
    """
    try:
        voci = _leggi(lingua)["voci"].values()
    except Exception:  # noqa: BLE001
        return []

    trovate: dict[int, list[str]] = {}
    for voce in voci:
        parti = voce.get("keyParts") or {}
        if parti.get("pubSymbol") != sigla:
            continue
        try:
            numero = int(parti.get("track") or 0)
        except (TypeError, ValueError):
            continue
        if numero <= 0:
            continue
        formato = (parti.get("formatCode") or "").upper()
        formati = trovate.setdefault(numero, [])
        if formato and formato not in formati:
            formati.append(formato)

    risultato: list[tuple[int, str]] = []
    for numero in sorted(trovate):
        formati = trovate[numero]
        # Il video prima dell'audio: e' l'ordine con cui si guarda, e
        # quello che scelgono `prima_traccia_di` e `formato_di_traccia`.
        formati.sort(key=lambda f: 0 if f == "VIDEO" else 1)
        for formato in formati:
            risultato.append((numero, formato))
    return risultato


def tracce_di(sigla: str, lingua: str = "I") -> list:
    """Le tracce di una pubblicazione di media, come lista di (numero, formato).

    Il nome pubblico di `_tracce_di`: chi deve **decidere** — il menu' delle
    cuffie, per dire se c'e' un video e se c'e' un audio — non deve usare una
    funzione con il cancelletto in mezzo al nome, perche' il giorno che la
    funzione cambia dentro, il nome dice che si puo' chiamare e non dice come.

    Serve a chi ha bisogno di sapere **quello che c'e'**, non di aprire la
    prima traccia: per quello c'e' `prima_traccia_di`.

    Vuota se il catalogo non c'e' o non conosce la sigla, come
    `e_di_media`: il catalogo e' una cosa che puo' non essere stata
    scaricata, e non e' un errore da cui ricavare un'eccezione.
    """
    return list(_tracce_di(sigla, lingua))


def e_di_media(sigla: str, lingua: str = "I") -> bool:
    """Questa sigla e' una pubblicazione fatta di video o di audio?

    SERVE A RICONOSCERE UN MEDIA **NON SCARICATO**
    -----------------------------------------------
    `JWPubManager.che_cosa_apre` risponde guardando solo quello che c'e' sul
    disco, e per una pubblicazione di media non ancora scaricata dice
    «pubblicazione»: la card dei Preferiti finiva nella sezione Pubblicazioni,
    che dice «non e' scaricato», invece che nella sezione Multimedia, da cui
    il video parte in streaming.

    Il catalogo dei media sa la risposta **anche senza il pacchetto**: se ha
    una traccia di questa sigla, la pubblicazione e' di media.  Non e' una
    lista scritta a mano — e' la stessa che riempie le strisce della Home.
    """
    return bool(_tracce_di(sigla, lingua))


def prima_traccia_di(sigla: str, lingua: str = "I") -> tuple:
    """(numero, formato) della prima traccia di una pubblicazione di media.

    Una card dei Preferiti senza una traccia sua — un Preferito messo dalla
    sezione Pubblicazioni — fa partire la prima: e' meglio del primo
    fotogramma nero, ed e' quello che l'utente si aspetta premendo un video.

    Il numero puo' essere ``None`` e il formato ``""`` quando il catalogo non
    c'e' o non conosce la sigla: chi chiama lo tratta come «non si sa», non
    come una traccia zero.
    """
    tracce = _tracce_di(sigla, lingua)
    if not tracce:
        return (None, "")
    return (tracce[0][0], tracce[0][1])


def numero_traccia(valore) -> int | None:
    """Una traccia come numero, o ``None`` se non c'e' o non e' un numero.

    TRE MODI DI DIRE «NESSUNA TRACCIA»
    ----------------------------------
    Una card di una pubblicazione intera porta la traccia come ``None``,
    ``""`` o ``0`` a seconda di come e' stata costruita: sono la stessa cosa e
    qui diventano tutte ``None``.  Un numero o una stringa con le cifre
    diventano un intero; tutto il resto — un numero scritto a parole, un
    oggetto — diventa ``None`` invece di un errore, perche' una card con un
    dato storto deve aprire qualcosa, non far cadere il clic.

    La conversione e' una sola perche' la usano la Home, la barra laterale e
    il menu': tre copie scritte a mano sono tre posti dove sbagliarla.
    """
    if valore in (None, "", 0):
        return None
    try:
        numero = int(valore)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def formato_di_traccia(sigla: str, lingua: str, traccia) -> str:
    """``"VIDEO"`` o ``"AUDIO"`` per una traccia, o ``""`` se non si sa.

    SERVE A SCEGLIERE LA SCHEDA GIUSTA
    ----------------------------------
    Premendo una card di una traccia si apre la sezione Multimedia su una
    scheda: il video sulla scheda Video, l'audio sulla scheda Audio.  Il dato
    e' gia' nel catalogo — e' il ``formatCode`` con cui la traccia e' scritta —
    e qui si legge **con la stessa regola** di `_tracce_di`, cioe' il video
    prima dell'audio a pari numero.  Leggerlo con `voce_di` darebbe invece la
    prima voce trovata, che a pari numero puo' essere l'audio, e la scheda
    sarebbe quella sbagliata una volta su due.

    Con la traccia vuota o sconosciuta risponde ``""``: chi chiama decide, e
    di solito ripiega sul video, che e' quello che si guarda.
    """
    numero = numero_traccia(traccia)
    if numero is None:
        return ""
    for n, formato in _tracce_di(sigla, lingua):
        if n == numero:
            return formato
    return ""


def _del_gruppo(lingua: str, gruppo: str, quante: int = QUANTE) -> list:
    """Le voci di un gruppo del catalogo, nell'ordine in cui il gruppo le ha.

    L'ordine non si riordina: e' l'ordine scritto da chi ha fatto il gruppo, e
    per `Latest` e' anche dal piu' recente al meno recente.

    LO STESSO PEZZO, DUE VOLTE: SI TIENE IL VIDEO
    ----------------------------------------------
    Lo stesso programma e' nel catalogo due volte, una come video e una come
    audio: `pub-osg_I_126_VIDEO` e `pub-osg_I_126_AUDIO`, stessa durata, stessa
    uscita.  In una striscia di card diventano due card con lo stesso titolo e
    la stessa durata: un doppione.

    Quindi una voce sola per titolo.  Quando ci sono due si tiene il **video**,
    perche' e' quello che si guarda e ha la miniatura; l'audio si vede solo se
    di quel programma il video non c'e'.  Il titolo e' quello del catalogo,
    ripulito dagli spazi e minuscolo, cosi' «Confido in te» e «Confido  in
    te» sono la stessa voce.  Senza titolo non si puo' paragonare: la voce
    resta, perche' altrimenti sparirebbe dalla sezione.
    """
    catalogo = _leggi(lingua)
    il_gruppo = catalogo["gruppi"].get(gruppo)
    if not il_gruppo:
        return []
    voci = catalogo["voci"]

    citate = []
    for chiave in (il_gruppo.get("media") or []):
        voce = voci.get(chiave)
        if voce is None:
            # Una voce che il gruppo cita e che non c'e': succede, e va
            # saltata.  Continuare a mettere in fila un buco nella sezione
            # e' peggio che non mostrarlo.
            continue
        citate.append(voce)

    # Una voce per titolo.  `dict` tiene l'ordine in cui la chiave e' comparsa
    # la prima volta, quindi l'ordine del gruppo — cioe' dal piu' recente — non
    # si perde anche quando una voce audio viene sostituita da quella video.
    scelte: dict = {}
    for voce in citate:
        titolo = " ".join((voce.get("title") or "").split()).casefold()
        chiave = titolo or voce.get("naturalKey", "")
        formato = (voce.get("formatCode") or "").upper()
        tiene_video = scelte.get(chiave, (None, None))[0] == "VIDEO"
        if chiave not in scelte or (formato == "VIDEO" and not tiene_video):
            scelte[chiave] = (formato, voce)

    return [voce for _, voce in list(scelte.values())[:quante]]


def _durata(voce: dict) -> str:
    """La durata come la scrive l'app originale: `4:10`, e `54:58` se serve.

    I secondi si **troncano**, non si arrotondano.  La differenza e' una
    cifra e sembra niente, ma qui si vede:

        pub-wsb_I_1_VIDEO    duration 214.6 secondi

    Troncando e' `3:34`, che e' vero.  Arrotondando e' `3:35`, e un video
    che dura tre minuti e trentaquattro decimi non dura tre minuti e
    trentacinque: si e' scritto un numero che il file non contiene.

    Python arrotonda anche a meta' esatta sempre verso il pari
    (`round(214.5)` dà `214`), quindi con `round` lo stesso numero sarebbe
    uscito diversamente a seconda del secondo dopo.  Il troncamento non ha
    questo problema: e' la stessa operazione e dà sempre lo stesso numero.
    """
    secondi = voce.get("duration")
    if not isinstance(secondi, (int, float)) or secondi <= 0:
        return ""
    secondi = int(secondi)
    return f"{secondi // 60}:{secondi % 60:02d}"


def _scheda(voce: dict) -> dict:
    """Una voce del catalogo, nel formato che le sezioni della Home usano."""
    parti = voce.get("keyParts") or {}
    immagini = voce.get("images") or {}
    quadrata = immagini.get("sqr") or {}
    return {
        "chiave": voce.get("naturalKey", ""),
        "titolo": voce.get("title") or "",
        # La pubblicazione a cui appartiene, se c'e'.  Serve per aprire: una
        # traccia del catalogo dei media non si ascolta da sola, si ascolta
        # dentro la sua pubblicazione, e la finestra chiede alla pubblicazione
        # che cosa aprire.
        "sigla": parti.get("pubSymbol", ""),
        "lingua": parti.get("languageCode", "I"),
        "docid": parti.get("docID", ""),
        "traccia": parti.get("track", ""),
        "formato": parti.get("formatCode", ""),
        "numero": parti.get("issueDate", ""),
        "durata": _durata(voce),
        "pubblicato": str(voce.get("firstPublished") or "")[:10],
        # L'indirizzo della miniatura e' **scritto nella voce**: non si
        # ricostruisce.  `md` perche' e' la misura che c'e' su tutte, e la
        # riga e' alta 64 pixel: `xs` basterebbe e non si vede la differenza.
        "miniatura": quadrata.get("md") or quadrata.get("lg") or "",
    }


def ultime(lingua: str = "I", quante: int = QUANTE_RECENTI) -> list:
    """Le ultime novita' sui video e sull'audio.

    Tutte quante, e non cinque: il tetto di `QUANTE_RECENTI` e' alto apposta.
    Nella schermata dell'originale questa sezione e' quella sotto «What's New»
    e mostra tutto quello che c'e' nel gruppo «Latest», dalla piu' recente
    alla piu' vecchia.
    """
    return [_scheda(v) for v in _del_gruppo(lingua, GRUPPO_RECENTI, quante)]


def kit_insegnante(lingua: str = "I", quante: int = QUANTE) -> list:
    """I video da usare per insegnare."""
    return [_scheda(v) for v in _del_gruppo(lingua, GRUPPO_INSEGNANTE, quante)]


def _data_sul_server(lingua: str) -> float:
    """Quando il server ha scritto il catalogo dei media.  0 se non si sa."""
    import urllib.request
    from email.utils import parsedate_to_datetime

    try:
        richiesta = urllib.request.Request(BASE_MEDIA + lingua + SUFFISSO,
                                           method="HEAD")
        with urllib.request.urlopen(richiesta, timeout=20) as risposta:
            quando = risposta.headers.get("Last-Modified", "")
        return parsedate_to_datetime(quando).timestamp() if quando else 0.0
    except Exception:  # noqa: BLE001 - una rete che non risponde non e' un errore
        return 0.0


def da_aggiornare(lingua: str = "I") -> bool:
    """Sul server c'e' un catalogo dei media piu' nuovo di quello che ho?

    **Blocca**: una richiesta sola.  Va chiamata da un thread secondario.

    Come per le pubblicazioni la domanda e' sul **confronto delle date**, non
    sul nome: questo catalogo non ha un nome di versione come l'altro, e
    l'unica cosa che dice se e' un altro e' quando e' stato scritto.
    """
    path = percorso(lingua)
    if not os.path.isfile(path):
        return True
    quando = _data_sul_server(lingua)
    if quando <= 0:
        # Non si sa quando e' stato scritto: non si puo' dire che quello di
        # adesso e' piu' vecchio, quindi si lascia stare quello che c'e'.
        return False
    try:
        return quando > os.stat(path).st_mtime + 3600
    except OSError:
        return True


def scarica(lingua: str = "I", forzato: bool = False, completion=None, on_progress=None) -> None:
    """Prende il catalogo dei media se il server ne ha uno piu' nuovo.

    Non blocca.  `completion(percorso, errore)` arriva sul main thread.
    Se c'e' `on_progress`, viene chiamata sul main thread con `(scritti, totale)`.

    PERCHE' IL VECCHIO NON VIENE CANCELLATO PRIMA
    ---------------------------------------------
    Come per il catalogo delle pubblicazioni: un download puo' fermarsi a
    meta'.  Qui pero' il pericolo e' minore — senza questo file la sezione
    delle novita' semplicemente non ha niente da mostrare, e il programma
    continua a funzionare — quindi si puo' scrivere direttamente.  Resta il
    `.part`, pero', cosi' un download interrotto non lascia un file che sembra
    un catalogo intero: il prossimo giro lo rifiinisce da capo invece di
    leggerne metà e dire che non c'è niente.
    """
    import urllib.request
    from Utility.Extensions.Ext_DispatchQueue import on_main

    def fine(errore: str) -> None:
        # `lavoro` gira in un thread secondario, e chi riceve la risposta
        # mostra un toast e ridisegna la schermata: roba di finestra.
        # Chiamato da qui, Qt riempiva il terminale di «Cannot create children
        # for a parent that is in a different thread» e poi si fermava con
        # SIGTRAP.  Si vedeva solo con la cartella dati vuota, l'unico caso in
        # cui il catalogo dei media si scarica davvero all'avvio.
        if completion is not None:
            on_main(lambda: completion(percorso(lingua), errore))

    def lavoro() -> None:
        esito = {"errore": ""}
        if not forzato and not da_aggiornare(lingua):
            esito["errore"] = ""          # niente da fare: non e' un errore
            fine("")
            return
        url = BASE_MEDIA + lingua + SUFFISSO
        provvisorio = percorso(lingua) + ".part"
        try:
            # Usa urlopen con progress callback
            import urllib.request
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as risposta:
                totale = int(risposta.headers.get("Content-Length", 0))
                scritti = 0
                with open(provvisorio, "wb") as f:
                    while True:
                        chunk = risposta.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        scritti += len(chunk)
                        if on_progress is not None and totale > 0:
                            on_main(lambda: on_progress(scritti, totale))
        except Exception as errore:  # noqa: BLE001
            fine(f"download interrotto ({errore})")
            return
        try:
            # Si scompatta e si ricompatta per accorgersi subito se il file
            # che e' arrivato e' un catalogo e non un pezzo di pagina di
            # errore.  Il server risponde 403 con un XML, e quel file
            # scompattato non e' niente: senza questo controllo finirebbe
            # sul disco come se fosse un catalogo.
            with gzip.open(provvisorio, "rt", encoding="utf-8") as f:
                if not any('"type":"category"' in riga for riga in f):
                    raise OSError("non sembra un catalogo dei media")
            os.replace(provvisorio, percorso(lingua))
        except (OSError, EOFError, gzip.BadGzipFile) as errore:
            try:
                os.remove(provvisorio)
            except OSError:
                pass
            esito["errore"] = str(errore)
            fine(esito["errore"])
            return

        # Il nuovo e' sul disco: quello che era in memoria non e' piu' vero.
        _in_memoia.pop(lingua, None)
        fine("")

    from Utility.Extensions.Ext_DispatchQueue import background

    background(lavoro)
    return None


def quando() -> float:
    """Quando e' stato preso l'ultimo catalogo dei media."""
    try:
        return os.stat(percorso("I")).st_mtime
    except OSError:
        return 0.0


def _prova() -> None:
    """Guarda cosa c'è nel catalogo dei media, e lo dice.

    Serve per il comando `--verifica` e per capire, quando qualcosa non si
    vede, se il file c'è e cosa contiene.  Non scrive niente e non scarica
    niente: guarda.
    """
    for lingua in ("I",):
        if not c_e_file(lingua):
            print(f"catalogo dei media {lingua}: non c'è sul disco ⚠️")
            continue
        try:
            size = os.path.getsize(percorso(lingua))
        except OSError:
            size = 0
        print(f"catalogo dei media {lingua}: {size} byte, "
              f"presente da {time.strftime('%d/%m %H:%M', time.localtime(quando()))}")
        catalogo = _leggi(lingua)
        gruppi = catalogo["gruppi"]
        print(f"  gruppi: {', '.join(sorted(gruppi))}")
        print(f"  voci: {len(catalogo['voci'])}")
        for gruppo in (GRUPPO_RECENTI, GRUPPO_INSEGNANTE):
            voci = _del_gruppo(lingua, gruppo, QUANTE)
            nome = gruppi.get(gruppo, {}).get("name", gruppo)
            print(f"  «{nome}»: {len(voci)} voci")
            for voce in voci:
                s = _scheda(voce)
                print(f"    {s['formato']:6} {s['durata']:>6}  {s['pubblicato']}  {s['titolo'][:44]}")