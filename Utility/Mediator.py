#
#  Utility/Mediator.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il mediator: le sezioni di media che l'app chiama «in demand».

L'HO CERCATO NEL POSTO SBAGLIATO UNA VOLTA
-----------------------------------------
Prima avevo scritto che il mediator era morto, perche'
``mediator.jw.org`` rispondeva 404.  Non e' morto: avevo l'host sbagliato.
L'host e' lo stesso di ``pub-media``, quello che il programma usa gia':

    https://mediator.jw.org/v1/...            404   <- quello che avevo provato
    https://b.jw-cdn.org/apis/mediator/v1/...  200   <- quello vero

Non l'avevo trovato perche' non c'era in nessun file di progetto: l'ho
trovato in un traccia di traffico vero (``jw.org-chrome-net-export-log.json``,
1,4 GB), dove l'app aveva fatto la richiesta.  Un indirizzo che funziona si
scopre guardando come lo chiama qualcun altro, non provando a indovinare.

LA FORMA DELLA RISPOSTA, MISURATA
---------------------------------
    {
      "category": {
        "key": "LatestVideos",
        "type": "ondemand",
        "name": "Ultimi video",
        "description": "Guarda i video piu' recenti di JW Broadcasting",
        "tags": [...],
        "images": {...},
        "parentCategory": ...,
        "media": [ {...}, ... ]
      },
      "pagination": {"totalCount": 9, "offset": 0, "limit": 500},
      "language":  {"languageCode": "I", "locale": "it", ...}
    }

Ogni voce di ``media`` ha:

    title, description, firstPublished, duration,
    durationFormattedMinSec, tags, files, images, availableLanguages

e dentro ``files`` c'e' **una voce per risoluzione**, ognuna con:

    label ("240p"), frameWidth, frameHeight, bitRate, mimetype,
    progressiveDownloadURL, checksum, filesize, subtitled,
    subtitles: {"url": "....vtt"}

PERCHE' LE RISOLUZIONI SONO DENTRO E NON FUORI
------------------------------------------------
Perche' un video si scarica in una risoluzione e si guarda in un'altra, e
sono due scelte diverse.  Tenendole in una lista sola si puo' mostrare
«240p, 480p, 720p» accanto al titolo e scaricare quella che si vuole, senza
chiedere niente due volte.  Con una risposta che ti da' una risoluzione sola
il lettore non sa che le altre esistono.

LE VOCI SONO GIA' COME LE VUOLE `MediaView`
-------------------------------------------
`voci()` rimappa ogni media in un dizionario con gli stessi nomi che usa
gia' la sezione Media: ``mimetype``, ``title``, ``duration``, ``frameWidth``,
``frameHeight``, ``bitRate``, ``subtitled``, ``label``.

Il perche' e' importante: la sezione Media ha gia' i filtri (`_e_audio`,
`_e_video`), il disegno, le anteprime e il tempo di riproduzione, e quei
filtri guardano proprio quei campi.  Rimappare vuol dire che il mediator non
aggiunge una seconda lista da tenere aggiornata: e' lo stesso codice che
gia' funziona, con dentro dati nuovi.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from Utility.tema import AUTOMATICA, PER_TAGLIO

BASE = "https://b.jw-cdn.org/apis/mediator/v1"

#: La larghezza minima del riquadro del video, in pixel, oltre la quale non
#: si scende sotto le risoluzioni piu' grandi.
#:
#: Su questa macchina Qt non trova una scheda video ("No RHI backend. Using
#: CPU conversion") e ridimensiona con la CPU sul filo del discorso: il
#: programma smette di rispondere con il video da 1280x720.  Perche' allora si
#: sceglie la risoluzione adatta alla casella.
#:
#: Il numero non e' una misura di questa finestra: e' la larghezza sotto la
#: quale un video ridimensionato si vede male, e sotto la quale si prende
#: quello che c'e'.  Il lettore chiama `scegli_risoluzione()` quando il video
#: parte e gli passa la sua larghezza, quindi il numero qui e' solo il
#: minimo sotto il quale non si pretende di stare.
LATO_SCELTO = 0

#: LE CATEGORIE SONO STATE RISCATTE, E NON CONCLuse a caso
#: ========================================================
#: Prima c'erano sette chiavi, sei delle quali video e una sola audio
#: (`KingdomMelodies`, scritta "Inni").  Il risultato era una scheda Audio
#: con **una** card: 109 brani in una categoria sola, e nient'altro, mentre
#: il contenitore `Audio` del server ne conteneva **undici**, con 705 brani.
#:
#: Le chiavi non sono indovinate.  Sono quattro le fonti, tutte misurate:
#:
#:   1. il log di traffico vero (`jw.org-chrome-net-export-log.json`, 1,4 GB),
#:      dove l'app aveva chiesto `.../categories/I/<chiave>`: da li' sono
#:      usciti `VODPgmEvt*`, le `2014Convention`...`2026Convention`,
#:      `VOXGBUpdates`, `Satellite`, `MidweekMeeting`, `TeachingToolbox`;
#:
#:   2. l'elenco che il server dà da solo, `.../categories/I` **senza**
#:      chiave: risponde `{"categories": [...], "language": {...}}` con 17
#:      voci.  E' li' che si vede che esiste un contenitore `Audio` — e che
#:      non elenca i suoi figli, quindi da solo non basta (vedi sotto);
#:
#:   3. `python3 -m Utility.Mediator`, che stampa per ogni chiave il nome,
#:      il numero di voci e quante sono audio e quante video;
#:
#:   4. la stessa richiesta con `?detailed=1`, che apre un contenitore.
#:      E' la fonte che mancava: vedi sotto.
#:
#: LA TRAPPOLA DEL CONTENITORE `Audio`
#: ----------------------------------
#: `.../categories/I/Audio` esiste e risponde 200, ma `type` vale
#: `"container"` e `media` e' una lista **vuota**: e' una teca, non un
#: elenco.  Chiedere `Audio` come se fosse una categoria dava zero voci e il
#: programma concludeva che l'audio non esistesse.
#:
#: Con `?detailed=1` la **stessa** richiesta risponde 200 con dentro
#: `subcategories`: undici voci, ognuna coi **suoi** media gia' dentro, e
#: tutti `type == "audio"`.  Misurato:
#:
#:     ?detailed=1    Audio -> 11 sottocategorie, 705 media
#:     senza          Audio -> 0 media
#:     senza, radice  17 voci, `Audio` compresa, senza figli
#:
#: Quindi `detailed=1` scende di **un** livello alla volta e non di piu':
#: la radice con `detailed=1` restituisce le stesse undici voci ma coi figli
#: **vuoti**.  Si apre un contenitore alla volta, fino a quelli che hanno i
#: media (i rami video finiscono al terzo livello).
#:
#: Non c'e' un endpoint per i figli: `Audio/children`, `Audio/subcategories`,
#: `subcategories/I/Audio` e `categories?parent=Audio` danno tutti 404, e
#: aggiungere `?parentCategory=`, `?flat=`, `?depth=2` al elenco non cambia
#: niente (sempre 17 voci).  Con `detailed=1` il contenitore basta da solo.
#:
#: I FIGLI DI `Audio` SONO UNDICI, E SONO QUESTI
#: --------------------------------------------
#: Contando le voci per tipo, misurate in italiano con `?detailed=1`:
#:
#:     AudioInternationalMusic  "Musica internazionale"      4 audio
#:     AudioOriginalSongs       "Canzoni"                   119 audio
#:     SJJMeetings              "...Versione per le adunanze" 164 audio
#:     SJJChorus                "...Versione cantata"         65 audio
#:     SJJInstrumental          "...Versione strumentale"      3 audio
#:     Vocal                    "...Versione corale"         113 audio
#:     AudioChildrenSongs       "Canzoni per bambini"         84 audio
#:     KingdomMelodies          "Melodie del Regno"          109 audio
#:     GNJST1Soundtrack         "...colonna sonora 1"         14 audio
#:     GNJST2Soundtrack         "...colonna sonora 2"         15 audio
#:     GNJST3Soundtrack         "...colonna sonora 3"         15 audio
#:
#: Tutte e undici rispondono **anche da sole**, una per una e senza
#: `detailed=1`, con dentro i media: quindi stanno in `CATEGORIE` come le
#: altre e `MediaView` le apre con la solita `voci()`.  `voci()` non cambia:
#: ogni voce ha `title` vero ("1. Le qualities di Geova", non un numero),
#: `mimetype` `audio/mpeg`, `url`, `checksum` e `naturalKey`, quindi
#: scaricamento, nuvoletta e riconoscimento sul disco funzionano come
#: prima — la sigla del file e' dentro il `naturalKey` (`pub-sjjm_I_1_AUDIO`
#: -> `sjjm_I_001.mp3`).
#:
#: ANCHE LE IMMAGINI CI SONO
#: -------------------------
#: Su queste undici, `immagini_categoria` restituisce **20 indirizzi
#: ciascuna** — mentre la misura fatta in precedenza su diciannove chiavi
#: aveva trovato un'immagine sola (`KingdomMelodies`): quelle diciannove non
#: contenevano queste dieci.  E i 705 media hanno tutti la loro locandina
#: su `cms-imgp.jw-cdn.org`.
#:
#: LE DUE VOCI CHE NON SONO FIGLIE DI `Audio`
#: ------------------------------------------
#: `VOXDramaticBibleReading` e' l'unica categoria **mista** (10 video, 7
#: audio): la stessa lettura drammatica esiste in entrambe le forme.  Quindi
#: appare in tutte e due le schede, e dentro ognuna mostra solo la sua
#: parte — vedi `MediaView._quando_video`.
#:
#: `VOXDramas`, "Videoracconti", ha dentro **audio, non video**: 13 su 13,
#: verificato.  In italiano lo chiamano "Videoracconti", ma il contenuto che
#: scarica il server e' un brano audio: percio' sta nella scheda Audio e non
#: nella scheda Video.  Tutte e due stanno nella radice delle 17 voci, non
#: tra i figli di `Audio`.
#:
#: La chiave e' il pezzo finale dell'indirizzo:
#:     .../mediator/v1/categories/I/LatestVideos
#:
#: I nomi sono quelli che il server scrive in `category.name`, misurati.
#: Prima erano sbagliati su sei voci: `StudioNewsReports` si chiama
#: "News e annunci" e non "Notizie dai rulli", `StudioMonthlyPrograms`
#: "Programmi mensili" e non "Programmi del mese", `KingdomMelodies`
#: "Melodie del Regno" e non "Inni".  Comunque il nome definitivo lo chiede
#: il server a ogni avvio (`nome_categoria`): questi sono solo quello che si
#: vede mentre la richiesta non e' ancora arrivata.
CATEGORIE = (
    # ---- Video ----
    ("LatestVideos", "Ultimi video",
     "Guarda i video piu' recenti di JW Broadcasting"),
    ("StudioFeatured", "Video in primo piano",
     "I video scelti dalla redazione"),
    ("StudioTalks", "Discorsi",
     "I discorsi tenuti ai congressi"),
    ("StudioNewsReports", "News e annunci",
     "Le notizie dai luoghi"),
    ("StudioMonthlyPrograms", "Programmi mensili",
     "Il programma di ogni mese"),
    ("VODPgmEvtMorningWorship", "Adorazione mattutina",
     "Le riprese dell'adorazione mattutina"),
    ("VODPgmEvtAnnMtg", "Adunanza annuale",
     "Le adunanze annuali"),
    ("VODPgmEvtGilead", "Diplomi di Galaad",
     "Il conferimento dei diplomi a Galaad"),
    ("VODPgmEvtSpecial", "Varie",
     "Programmi ed eventi particolari"),
    ("VOXGBUpdates", "Aggiornamenti dal Corpo Direttivo",
     "Gli aggiornamenti del Corpo Direttivo"),
    ("TeachingToolbox", "Kit dell'insegnante",
     "I video per chi insegna"),
    ("MidweekMeeting", "Adunanza infrasettimanale",
     "I video per l'adunanza infrasettimanale"),
    ("Satellite", "Satellite",
     "I programmi via satellite"),
    ("Other", "Altro",
     "Quello che non sta nelle altre voci"),
    ("FeaturedLibraryVideos", "In primo piano",
     "I video scelti dalla redazione"),
    # ---- Audio ----
    ("AudioInternationalMusic", "Musica internazionale",
     "Le canzoni in altre lingue"),
    ("AudioOriginalSongs", "Canzoni",
     "Le canzoni originali"),
    ("SJJMeetings", "Cantiamo a Geova con gioia — Versione per le adunanze",
     "I cantici che si cantano in adunanza"),
    ("SJJChorus", "Cantiamo a Geova con gioia — Versione cantata",
     "Gli stessi cantici cantati dal coro"),
    ("SJJInstrumental", "Cantiamo a Geova con gioia — Versione strumentale",
     "Gli stessi cantici suonati, senza voce"),
    ("Vocal", "Cantiamo a Geova — Versione corale",
     "I cantici in versione corale"),
    ("AudioChildrenSongs", "Canzoni per bambini",
     "Le canzoni per i bambini"),
    ("GNJST1Soundtrack", "La buona notizia secondo Gesù (colonna sonora 1)",
     "La musica del primo ciclo"),
    ("GNJST2Soundtrack", "La buona notizia secondo Gesù (colonna sonora 2)",
     "La musica del secondo ciclo"),
    ("GNJST3Soundtrack", "La buona notizia secondo Gesù (colonna sonora 3)",
     "La musica del terzo ciclo"),
    ("KingdomMelodies", "Melodie del Regno",
     "I cantici e gli inni"),
    ("VOXDramaticBibleReading", "Brani biblici recitati",
     "Le parti bibliche recitate"),
    ("VOXDramas", "Videoracconti",
     "I racconti recitati, da ascoltare"),
    # ---- Miste: compaiono in entrambe le schede ----
    ("FeaturedLibraryLanding", "In evidenza",
     "La pagina principale"),
)

#: Che cosa ha dentro ogni categoria: `"video"`, `"audio"` o `"entrambe"`.
#:
#: PERCHE' E' UNA TABELLA E NON UNA PROVA SUL SERVER
#: -------------------------------------------------
#: Il posto per decidere se una categoria va nella scheda Audio o in quella
#: Video era una richiesta HTTP: `Mediator.voci(chiave)[:3]`, per ogni
#: categoria, ogni volta che la griglia si ridisegnava.  Sono una decina di
#: richieste di rete **per disegnare una griglia**, sul thread che tiene la
#: finestra: finestre a scatti, e con la rete lenta la sezione non
#: disegnava niente.
#:
#: E la prova era sbagliata anche quando andava: `[:3]`, cioe' le prime tre
#: voci.  In `VOXDramaticBibleReading` le prime tre sono video, quindi la
#: categoria — che ha 7 audio — **spariva dalla scheda Audio**, ed era
#: proprio la categoria che si stava cercando.
#:
#: La risposta vera la da' il campo `type` di ogni voce, che il server
#: scrive per ognuna (`"video"` o `"audio"`).  Qui e' gia' contato e scritto:
#: la tabella sopra e' quello che `python3 -m Utility.Mediator` misura, e
#: cambiare questa riga non richiede di aprire la finestra.
NATURA = {
    "LatestVideos": "video",
    "StudioFeatured": "video",
    "StudioTalks": "video",
    "StudioNewsReports": "video",
    "StudioMonthlyPrograms": "video",
    "VODPgmEvtMorningWorship": "video",
    "VODPgmEvtAnnMtg": "video",
    "VODPgmEvtGilead": "video",
    "VODPgmEvtSpecial": "video",
    "VOXGBUpdates": "video",
    "TeachingToolbox": "video",
    "MidweekMeeting": "video",
    "Satellite": "video",
    "Other": "video",
    "FeaturedLibraryVideos": "video",
    "FeaturedLibraryLanding": "video",
    "AudioInternationalMusic": "audio",
    "AudioOriginalSongs": "audio",
    "SJJMeetings": "audio",
    "SJJChorus": "audio",
    "SJJInstrumental": "audio",
    "Vocal": "audio",
    "AudioChildrenSongs": "audio",
    "GNJST1Soundtrack": "audio",
    "GNJST2Soundtrack": "audio",
    "GNJST3Soundtrack": "audio",
    "KingdomMelodies": "audio",
    "VOXDramaticBibleReading": "entrambe",
    "VOXDramas": "audio",
}


def immagini_categoria(chiave: str, lingua: str | None = None) -> list:
    """Gli indirizzi dell'immagine **della categoria**, o [] se non ce n'e'.

    Una categoria non e' un pezzo di contenuto: e' una **scelta**, quindi non
    ha la copertina di una canzone.  Ma alcune ne hanno un'immagine propria,
    e senza usarla la card mostra il glifo generico davanti a un nome che
    l'utente conosce gia': sembra che il programma non abbia niente da
    mostrarne.

    Misurato sulle diciannove categorie: **una sola** ha un'immagine —
    `KingdomMelodies`, «Melodie del Regno», con forme `sqs`, `sqr`, `pnr`,
    `wss` e `wsr`.  Le altre diciotto rispondono con `images` vuoto.  Non e'
    un taglio: e' quello che il server ha, e va usato dove c'e' senza
    inventare un'immagine dove non c'e'.

    Vengono rimandate **tutte** le misure, come per i media: una puo' non
    esistere sul CDN mentre un'altra c'e', e `Copertine` prova in fila.

    Il risultato e' tenuto in memoria per la sessione: sono poche richieste e
    la griglia le ridisegna a ogni cambio di scheda.
    """
    if not chiave:
        return []
    if chiave in _IMMAGINI_CATEGORIA:
        return _IMMAGINI_CATEGORIA[chiave]
    uscite: list = []
    try:
        dati = _chiedi(chiave, lingua)
        categoria = dati.get("category") or {}
        immagini = categoria.get("images") or {}
        for forma, misura in (("sqr", "md"), ("wss", "sm"), ("sqs", "md"),
                              ("wsr", "sm"), ("pnr", "lg")):
            gruppo = immagini.get(forma)
            if not isinstance(gruppo, dict):
                continue
            preferita = gruppo.get(misura)
            if preferita:
                uscite.append(preferita)
            for chiave_misura in ("sm", "md", "xs", "lg", "xl"):
                altro = gruppo.get(chiave_misura)
                if altro and altro not in uscite:
                    uscite.append(altro)
    except ErroreMediator:
        # Un errore di rete NON vuol dire «nessuna immagine»: non si ricorda.
        return []
    _IMMAGINI_CATEGORIA[chiave] = uscite
    return uscite


#: Le immagini di categoria gia' lette, per non chiederle due volte.
_IMMAGINI_CATEGORIA: dict = {}
_LETTE_DA_DISCO = False


def _file_immagini_categorie():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / "immagini_categorie.json"


def immagini_categoria_gia_note(chiave: str, lingua: str | None = None) -> list:
    """Le immagini della categoria che si conoscono GIA', senza rete.

    E' quella che si usa per disegnare: `immagini_categoria` chiede al server, e
    chiamata 19 volte mentre si costruisce la griglia di Audio o Video fermava
    la finestra per circa un secondo.  Quello che si sa viene dalla memoria o
    dal file di una volta scorsa; il resto lo porta `precarica_immagini`, da un
    thread.
    """
    global _LETTE_DA_DISCO
    if not _LETTE_DA_DISCO:
        _LETTE_DA_DISCO = True
        try:
            salvate = json.loads(_file_immagini_categorie().read_text(encoding="utf-8"))
            for k, v in salvate.items():
                _IMMAGINI_CATEGORIA.setdefault(k, list(v))
        except (OSError, ValueError, AttributeError):
            pass
    return list(_IMMAGINI_CATEGORIA.get(chiave, []))


def precarica_immagini(chiavi, lingua: str | None = None) -> None:
    """Chiede al server le immagini che mancano e le scrive su disco.

    Fa rete: va chiamata da un thread.
    """
    immagini_categoria_gia_note("")      # prima quello che c'e' su disco
    cambiate = False
    for chiave in chiavi:
        if chiave not in _IMMAGINI_CATEGORIA:
            immagini_categoria(chiave, lingua)
            cambiate = cambiate or chiave in _IMMAGINI_CATEGORIA
    if cambiate:
        try:
            file = _file_immagini_categorie()
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(_IMMAGINI_CATEGORIA), encoding="utf-8")
        except OSError:
            pass


class ErroreMediator(Exception):
    """Il mediator ha risposto qualcosa che non va, o non ha risposto."""


def _chiedi(percorso: str, lingua: str | None = None) -> dict:
    """Una richiesta al mediator, in chiaro.

    Senza `lingua` si usa quella scelta dall'utente.  Il default non e' la
    lettera "I": un valore predefinito viene calcolato quando il modulo viene
    importato, quindi scrivere "I" qui significa "italiano per sempre", e
    cambiare lingua dal menu non cambierebbe niente.

    LA STRINGA VUOTA NON E' UNA LINGUA
    ----------------------------------
    Qui il controllo era `if lingua is None`, e non andava bene.  `""` non e'
    `None`, quindi passava oltre e l'indirizzo veniva:

        .../mediator/v1/categories//StudioNewsReports

    con due barre in mezzo.  Quello e' un 404, misurato.  E chi passa `""`?
    `MediaView`, che ha `self._lingua = ""` fino a quando l'utente non
    sceglie una pubblicazione: quindi aprendo la sezione Multimedia e
    premendo una linguetta delle categorie, senza aver prima scelto nulla, si
    chiedeva una lingua inesistente.  Lo stesso valeva per `_chiedi_nomi`, che
    gira all'avvio: per questo i nomi delle sei linguette non arrivavano
    mai e restavano quelli scritti a mano.

    Il controllo e' `if not lingua`, e non `if lingua == ""`, perche' il
    punto vero e' un altro: **una lingua che non e' stata detta non e' una
    lingua**.  Sia che arrivi come `None` sia che arrivi come `""`, la
    domanda e' la stessa — «quale lingua? non lo so, usa quella scelta» — e
    la risposta e' la stessa.

    Il timeout e' corto (20 secondi) perche' questa funzione gira in un
    thread e il chiamante non puo' accorgersi che e' bloccato: senza timeout
    un thread appeso resta appeso per sempre e la sezione resta vuota senza
    dire niente.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()
    url = f"{BASE}/categories/{urllib.parse.quote(lingua)}/{percorso}"
    richiesta = urllib.request.Request(url, headers={"User-Agent": "JWLibrary"})
    try:
        with urllib.request.urlopen(richiesta, timeout=20) as risposta:
            corpo = risposta.read()
    except urllib.error.HTTPError as errore:
        raise ErroreMediator(f"{url}: HTTP {errore.code}") from errore
    except (urllib.error.URLError, OSError) as errore:
        raise ErroreMediator(f"{url}: {errore}") from errore
    try:
        dati = json.loads(corpo)
    except ValueError as errore:
        raise ErroreMediator(f"{url}: la risposta non e' JSON") from errore
    if not isinstance(dati, dict):
        raise ErroreMediator(f"{url}: la risposta non e' un dizionario")
    return dati


def _chiave_naturale(voce: dict) -> dict:
    """Il `naturalKey` di una voce, diviso nei pezzi che servono altrove.

    IL NOME DEL FILE E' IL `naturalKey` MENO DUE PEZZI
    -------------------------------------------------
    Ogni voce del mediator ha una `naturalKey` con tre pezzi in piu' di
    quella che si trova nel nome del file:

        naturalKey      pub-iam-1_I_1_AUDIO
        file sul disco  iam-1_I_01.mp3
                       ^^^  ^^ ^       il prefisso `pub-`, il tipo in
                                          fondo, e la traccia a una cifra

    Quindi: si toglie `pub-` davanti, si toglie `_AUDIO` o `_VIDEO` in fondo,
    e quello che resta si separa con `_`:

        pub-iam-1_I_1_AUDIO   ->   iam-1   I   1
        (sigla)          (lingua) (traccia)

    Perche' serve: `_media_sul_disco` chiede «questo file c'e' gia'?» con
    sigla, lingua e traccia, e senza questi tre campi la domanda non
    poteva essere fatta — quindi la nuvoletta di una card audio restava
    sempre quella del download anche dopo aver scaricato.

    UNA TRACCIA CHE NON E' UN NUMERO
    -------------------------------
    C'e' almeno una voce con `pub-jlp_I_x_VIDEO`, cioe' traccia `x`, e il
    file si chiama `jlp_I_x_r240P.mp4`.  Non e' un numero e non si finge:
    `traccia` resta 0 e `MediaScaricati.file_di` non trovera' niente, che
    e' la verita' — meglio che inventare `x` = 24 per far combaciare un
    numero a caso.

    Se `naturalKey` non c'e', si prova `languageAgnosticNaturalKey`, che ha
    la stessa forma senza il pezzo della lingua.  Se non c'e' nemmeno
    quello, si restituisce un dizionario vuoto: la voce si mostra lo stesso,
    e semplicemente non si puo' dire se e' gia' scaricata.
    """
    vuoto = {"sigla": "", "lingua": "", "traccia": 0, "nomeFile": ""}
    grezza = (voce.get("naturalKey")
              or voce.get("languageAgnosticNaturalKey") or "")
    if not grezza:
        return vuoto
    # `pub-iam-1_I_1_AUDIO` -> `iam-1_I_1`
    if grezza.startswith("pub-"):
        grezza = grezza[4:]
    pezzi = grezza.split("_")
    if pezzi and pezzi[-1].upper() in ("AUDIO", "VIDEO"):
        pezzi = pezzi[:-1]
    if len(pezzi) < 2:
        return vuoto
    sigla, lingua = pezzi[0], pezzi[1]
    # TUTTI i numeri che vengono dopo, non solo il primo: il nome sul disco li
    # ha tutti e nello stesso ordine.  Misurato:
    #
    #     pub-jwb_I_202104_02_VIDEO  ->  jwb_I_202104_02_r240P.mp4
    #     pub-jwb_I_201904_11_VIDEO  ->  jwb_I_201904_11_r240P.mp4
    #
    # Sono il mese e il giorno.  Prendendo solo il primo, la voce diceva
    # «traccia 202104» mentre il file ha [202104, 02]: i due numeri non
    # coincidevano e il confronto falliva **sempre**, quindi quei video si
    # scaricavano e il programma continuava a dire che non erano scaricati.
    # Sono i video di «Adorazione mattutina» e dell'adunanza: centinaia.
    tracce = [int(p) for p in pezzi[2:] if p.isdigit()]
    traccia = tracce[0] if tracce else 0
    return {"sigla": sigla, "lingua": lingua, "traccia": traccia,
            "tracce": tracce,
            # il nome **senza** estensione e senza risoluzione: quello che
            # c'e' sul disco comincia cosi'.  Il pezzo tolto in fondo e' il
            # tipo (`_AUDIO`, `_VIDEO`), che nel nome del file non c'e'.
            "nomeFile": "_".join(pezzi)}


def _immagini(media: dict) -> list:
    """Le locandine di una voce: **tutte** quelle che il server manda.

    IL MEDIATOR NON USA `trackImage`
    --------------------------------
    `MepsAPI` mette l'immagine in `trackImage` e `Copertine.url_anteprima`
    la cerca li'.  Il mediator la mette in `images`, e con quattro forme
    diverse dentro:

        "pnr"  ritratto, verticale      -> il libro in piedi
        "wss"  watch screen, 16:9       -> l'immagine col video dentro
        "lsr"  landscape, 16:9          -> l'orizzontale piu' grande
        "sqr"  quadrato                 -> la miniatura piccola

    Ognuna ha dentro le proprie misure ("lg", "sm", "xl", "md") e non
    hanno tutte le stesse: `lsr` c'e' solo in "xl", `wss` in "lg" e "sm",
    `sqr` solo in "md".

    IL PERCHE' DI QUESTO ORDINE
    ---------------------------
    La riga della sezione Media ha uno spazio di 56x32, cioe' un 16:9.  Per
    quello la forma giusta e' `wss` in "sm".  Vengono dopo `lsr` e `sqr`
    perche' sono orizzontale e quadrato, quindi entrambe vanno bene come
    ripiego.  `pnr` viene per ultima perche' e' verticale: in 56x32 una
    foto ritratta viene tagliata e si vede solo la faccia di chi e' nella
    foto.

    Non si sceglie la misura piu' grande perche' "e' meglio": 56x32 pixel
    sono 56x32, e scaricare la versione grande per metterla in un riquadro
    piccolo e' traffico sprecato e un'immagine ridotta che sembra sfocata.

    LE MISURE NON SONO TUTTE LI'
    -----------------------------
    Il ritorno e' una **lista**, non un indirizzo solo, perche' una misura puo'
    non esistere sul CDN mentre l'altra c'e'.  Misurato su «Melodie del Regno»:
    dei 109 inni, 18 hanno `sqr/md` che risponde **403** e `sqr/lg` che
    risponde 200 (49 350 byte contro i 30 000 dell'altra).  Sono le stesse
    locandine, misurate due volte dal server, e solo una delle due e' stata
    pubblicata.

    Con una scelta sola — la prima che si trova nel documento — quei 18 inni
    restavano senza immagine, e il sintomo era «manca il riquadro di
    anteprima» su un terzo della categoria.  Non era un difetto del
    programma: era una misura che non c'era e un'altra che c'era.

    Quindi si restituiscono tutte, dalla preferita in poi, e chi scarica le
    prova in fila: `Copertine.scarica` ricorda i 403 per tutta la sessione,
    quindi il tentativo sbagliato costa una volta e non piu'.
    """
    immagini = media.get("images")
    if not isinstance(immagini, dict):
        return []
    uscite: list = []
    for forma, misura in (("wss", "sm"), ("lsr", "xl"), ("sqr", "md"),
                          ("pnr", "lg")):
        gruppo = immagini.get(forma)
        if not isinstance(gruppo, dict):
            continue
        preferita = gruppo.get(misura)
        if preferita:
            uscite.append(preferita)
        # le altre misure della stessa forma, dalla piu' piccola alla piu'
        # grande: cosi' se la preferita non esiste si prende prima quella che
        # costa meno traffico, che e' anche la piu' adatta a un riquadro
        # piccolo.  Vedi sopra perche' non si comincia dalla piu' grande.
        for chiave in ("sm", "md", "xs", "lg", "xl"):
            altro = gruppo.get(chiave)
            if altro and altro not in uscite:
                uscite.append(altro)
    return uscite


def _files(media: dict) -> list:
    """I file di una voce, dal campo piu' profondo in quello piu' esterno.

    Il campo si chiama `files` ed e' una lista.  Ma una voce che non ha piu'
    versioni potrebbe averlo come dizionario, e la lista vuota e' un caso
    diverso dal campo assente: la prima non ha niente da mostrare, la seconda
    non ha ancora risposto.  Qui si accettano i tre e si restituisce sempre
    una lista, cosi' il chiamante non deve controllare.
    """
    grezzi = media.get("files")
    if isinstance(grezzi, dict):
        return [grezzi]
    if isinstance(grezzi, list):
        return [f for f in grezzi if isinstance(f, dict)]
    return []


def voci(chiave: str, lingua: str | None = None) -> list:
    """I media di una categoria, nel formato che `MediaView` gia' capisce.

    Ogni voce ha i campi che la sezione Media usa gia': `mimetype`, `title`,
    `duration`, `frameWidth`, `frameHeight`, `bitRate`, `subtitled`, `label`.
    Se un media ha piu' risoluzioni escono piu' voci, una per risoluzione:
    e' quello che l'utente scarica, quindi e' la cosa che va mostrata.

    UNA VOCE PER RISOLUZIONE, E NON UNA CON TUTTE
    ----------------------------------------------
    Le risoluzioni dentro `files` sono alternative dello stesso video, e
    vanno mostrate come voci separate perche' l'utente ne scarica una.  Se
    si tenessero insieme in una voce sola, il filtro per risoluzione della
    sezione Media non avrebbe niente su cui lavorare: controllerebbe un
    campo che non esiste.
    """
    dati = _chiedi(chiave, lingua)
    categoria = dati.get("category")
    if not isinstance(categoria, dict):
        raise ErroreMediator(f"{chiave}: la risposta non ha 'category'")
    media = categoria.get("media")
    if not isinstance(media, list):
        return []

    uscite = []
    for voce in media:
        if not isinstance(voce, dict):
            continue
        titolo = voce.get("title") or voce.get("description") or ""
        secondi = voce.get("duration") or 0
        # sigla, lingua e traccia servono a `MediaView._media_sul_disco` per
        # chiedere al disco se il file c'e' gia'.  Vedi `_chiave_naturale`.
        dove = _chiave_naturale(voce)
        files = _files(voce)
        if not files:
            # Una voce senza file non si puo' scaricare, e si mostra lo
            # stesso: il titolo e' un'informazione vera anche senza il
            # file.  Quello che non si fa e' inventare un mimetype, perche'
            # `MediaView._e_video()` classifica un video dal mimetype o
            # dalla risoluzione, e con entrambi vuoti la voce resterebbe
            # fuori da tutte e due le liste senza che nulla lo segnali.
            uscite.append({
                "title": titolo,
                "label": "",
                "mimetype": "",
                "duration": secondi,
                "durataTesto": voce.get("durationFormattedMinSec") or "",
                "frameWidth": 0,
                "frameHeight": 0,
                "bitRate": 0,
                "subtitled": False,
                "subtitlesUrl": "",
                "url": "",
                "checksum": "",
                "filesize": 0,
                "categoria": chiave,
                "pubblicato": voce.get("firstPublished"),
                "scaricabile": False,
                **dove,
                # `formato` e' il campo che dicono «questa voce e' un media»
                # e che le voci del mediator non avevano.  Senza, la
                # nuvoletta cade nel ramo delle **pubblicazioni** di
                # `HomeView._stato_nuvoletta` — che cerca una cartella
                # `<sigla>_<lingua>_<anno>`, non esiste per `sjjm` — e
                # risponde «scarica» **anche con il file sul disco**: il
                # brano scaricato restava con la nuvoletta e sembrava non
                # essere mai stato salvato.
                #
                # Il valore e' quello che scrivono `MediaScaricati` e
                # `Preferiti`, cioe' VIDEO o AUDIO e non l'estensione.  Una
                # voce senza `type` resta con `formato` vuoto: inventare
                # «AUDIO» a un tipo che il server non ha detto significherebbe
                # cercare un file che potrebbe non essere quello.
                "formato": ("VIDEO" if voce.get("type") == "video"
                            else "AUDIO" if voce.get("type") == "audio"
                            else ""),
                # il tipo che scrive il server: `"audio"` o `"video"`.  E'
                # piu' sicuro del mimetype, perche' e' quello che mette il
                # server accanto al file, e senza di questo una voce audio
                # finirebbe nella scheda Video se il mimetype manca.
                "tipo": voce.get("type") or "",
            })
            continue
        # la locandina sta FUORI dal ciclo sui file: e' la stessa per tutte
        # le risoluzioni dello stesso video, quindi metterla per voce
        # significa scaricare la stessa immagine quattro volte.
        indirizzi = _immagini(voce)
        # UNA VOCE PER VIDEO, E LE RISOLUZIONI DENTRO
        # --------------------------------------------
        # Prima si faceva una voce per risoluzione, e la stessa lezione
        # compariva quattro volte di fila: quattro righe identiche con lo
        # stesso titolo e la stessa locandina, che differivano solo per
        # "240p" e "360p".  In un elenco di 36 righe che vengono da 9 video
        # sembrava un catalogo pieno di doppioni.
        #
        # Le risoluzioni sono alternative dello stesso file, non voci
        # diverse: vanno dentro la voce, nella lista `risoluzioni`, e la
        # riga le mostra una volta sola.  Il video che parte e' il piu'
        # grande disponibile, perche' e' quello che l'utente vuole guardare e
        # gli altri si scelgono scaricandoli.
        #
        # IL COME' SI SCEGLIE IL PIU' GRANDE, E NON IL PRIMO
        # ----------------------------------------------------
        # Il primo file della lista non e' per forza il piu' grande: misurato,
        # arriva `r240P` ma l'ordine non e' garantito dal server.  Si sceglie
        # dai pixel, che sono un numero e non un nome: "720p" scritto nella
        # sigla potrebbe essere un'etichetta e i pixel no.
        def _pixel(f: dict) -> int:
            try:
                return int(f.get("frameWidth") or 0) * int(f.get("frameHeight") or 0)
            except (TypeError, ValueError):
                return 0

        ordinate = sorted(files, key=_pixel)   # dalla piu' piccola
        # LA RISOLUZIONE NON E' SEMPRE LA PIU' GRANDE
        # ---------------------------------------------
        # Lo era, e su questa macchina il programma si impiantava: con un
        # video da 1280x720 dentro un riquadro grande la meta' della finestra,
        # Qt non trova una scheda video e lo dice:
        #
        #     QRhi ... No RHI backend. Using CPU conversion.
        #
        # Cioe' **decodifica e ridimensiona con la CPU**, sul filo del
        # discorso, venticinque volte al secondo.  Il ciclo di eventi gira
        # (misurato: 20 cicli al secondo prima, durante e dopo) ma la CPU e'
        # al massimo e la finestra sembra bloccata.
        #
        # Non e' una misura di quante schede video ci sono: e' una realta'
        # di questa installazione, e qui la risposta giusta e' non chiedere il
        # massimo.
        #
        # Si sceglie la risoluzione **piu' vicina alla casella del video**:
        # il video che entra gia' della misura giusta non va ridimensionato,
        # e il lavoro della CPU diventa quello di copiare i pixel invece di
        # decodificare e scalare.  Se il riquadro e' piccolo — e su questa
        # macchina e' l'unica risoluzione che non fa impiantare il
        # programma — si prende la piu' piccola disponibile.
        #
        # Il resto delle risoluzioni resta nella voce, quindi scegliere
        # quella che si vuole non richiede un'altra richiesta al server.
        scelta = ordinate[0]
        if LATO_SCELTO > 0:
            for f in ordinate:
                larghezza = int(f.get("frameWidth") or 0)
                if larghezza >= LATO_SCELTO:
                    scelta = f
                    break
            else:
                # nessuna e' abbastanza grande: la piu' grande, che e' anche
                # la piu' adatta a un riquadro piu' piccolo
                scelta = ordinate[-1]
        migliore = scelta
        sottotitoli = migliore.get("subtitles")
        # La lista delle risoluzioni, per estensione e non per numero di
        # pixel: "240p, 360p, 720p" si legge, "312000, 2304000" no.
        estensioni = [str(f.get("label") or "") for f in ordinate
                      if f.get("label")]
        uscite.append({
            # gli stessi nomi che usa gia' la sezione Media, cosi' gli
            # stessi filtri e gli stessi disegni funzionano
            "title": titolo,
            # `label` non e' piu' una risoluzione sola ma **tutte** quelle che
            # ci sono: la riga le mostra una volta e non quattro volte.
            "label": " · ".join(estensioni),
            "mimetype": migliore.get("mimetype") or "",
            # `duration` in secondi e non la stringa "8m 36s": la sezione
            # Media ci fa sopra `minuti:secondi` da sola e butta via un
            # numero che non e' un numero.  La stringa formattata dal server
            # resta in `durataTesto`.
            "duration": secondi,
            "durataTesto": voce.get("durationFormattedMinSec") or "",
            "frameWidth": migliore.get("frameWidth") or 0,
            "frameHeight": migliore.get("frameHeight") or 0,
            "bitRate": migliore.get("bitRate") or 0,
            "subtitled": any(bool(f.get("subtitled")) for f in ordinate),
            "subtitlesUrl": ((sottotitoli.get("url") or "")
                             if isinstance(sottotitoli, dict) else ""),
            # Il file che parte e' il piu' **piccolo** disponibile, e non il
            # piu' grande.  Il motivo e' in `scegli_risoluzione`: su questa
            # macchina non c'e' una scheda video e ridimensionare 1280x720
            # con la CPU fa impiantare il programma.  Il lettore chiama
            # `scegli_risoluzione` quando parte e gli passa la larghezza
            # della sua casella, quindi da soltanto la risoluzione adatta.
            "url": migliore.get("progressiveDownloadURL") or "",
            "checksum": migliore.get("checksum") or "",
            "filesize": migliore.get("filesize") or 0,
            # Tutte le risoluzioni, per chi volesse scegliere: la lista e'
            # quella vera del server, non quella ricavata dai pixel.
            "risoluzioni": [
                {
                    "label": str(f.get("label") or ""),
                    "url": f.get("progressiveDownloadURL") or "",
                    "checksum": f.get("checksum") or "",
                    "filesize": f.get("filesize") or 0,
                    "frameWidth": f.get("frameWidth") or 0,
                    "frameHeight": f.get("frameHeight") or 0,
                }
                for f in ordinate if f.get("progressiveDownloadURL")
            ],
            # il nome che `Copertine.url_anteprima` cerca: vedi
            # `_immagini`.  Senza, le righe del mediator avrebbero il glifo
            # del film e nessuna immagine, che sembrerebbe una lista di
            # video senza locandine.
            #
            # `url` e' la prima, quella che si preferisce; `alternative` sono
            # le altre misure, da provare se la prima risponde 403 — misurato
            # su 18 inni su 109 che hanno la `md` assente e la `lg` presente.
            "trackImage": (
                {"url": indirizzi[0],
                 "alternative": indirizzi[1:]}
                if indirizzi else {}
            ),
            "categoria": chiave,
            "pubblicato": voce.get("firstPublished"),
            "scaricabile": bool(migliore.get("progressiveDownloadURL")),
            # sigla, lingua e traccia, presi dal `naturalKey`: sono le tre
            # cose che `_media_sul_disco` passa a `MediaScaricati.file_di`
            # per chiedere al disco se quel file c'e' gia'.  Vedi
            # `_chiave_naturale`.
            **dove,
            # VIDEO o AUDIO, per lo stesso motivo spiegato nel ramo di sopra:
            # senza questa chiave la nuvoletta di un media scaricato dice
            # ancora «scarica».
            "formato": ("VIDEO" if voce.get("type") == "video"
                        else "AUDIO" if voce.get("type") == "audio"
                        else ""),
            # il tipo che scrive il server accanto al file.  E' la risposta
            # piu' sicura di «questo e' un audio o un video?»: i due campi
            # che si usavano prima, mimetype e risoluzione, si ricavano da
            # altre risposte e quando mancano la voce non finiva da nessuna
            # parte — restava fuori dalla griglia Audio e fuori da quella
            # Video, senza che nulla lo segnalasse.
            "tipo": voce.get("type") or "",
        })
    return uscite


def scegli_risoluzione(voce: dict, larghezza_video: int,
                       scelta: str = "") -> dict:
    """La voce giusta per una casella larga `larghezza_video` pixel.

    Riscrive dentro la voce l'indirizzo, il checksum e la dimensione della
    risoluzione scelta, e restituisce la voce stessa.

    PERCHE' RISCRIE E NON RESTITUISCE UNA COPIA
    ------------------------------------------
    Perche' la voce e' quella che finisce sulla riga della lista e quella su
    cui si preme play: se si restituisse una copia, la riga mostrerebbe la
    risoluzione piccola e si partirebbe con la grande, e non si saprebbe
    quale delle due sia quella giusta guardando la finestra.

    Il valore di partenza e' quello di `voci()`, cioe' la piu' piccola: cosi'
    il programma parte leggero anche se nessuno chiama questa funzione, e
    migliora solo quando qualcuno sa che la casella e' grande.

    LA SCELTA DELL'UTENTE, E QUANDO NON C'E'
    ----------------------------------------
    `scelta` vuota o `"auto"` = si misura la casella, e non cambia niente.

    Altrimenti puo' essere un'etichetta vera di quel video — "720p", e "1080p"
    solo se quel video ce l'ha — oppure una delle tre posizioni delle
    impostazioni: `bassa`, `media`, `alta`.

    Se quello che ha chiesto **non esiste in questo video** si prende lo stesso
    quello che si prendeva senza chiederlo, e si dice quale: la funzione mette
    `risoluzioneInUso` dentro la voce.  Serve perche' la scelta si ricorda da
    una volta all'altra: se l'utente sceglie 1080p e poi apre un video che ha
    solo fino a 720p, senza questo controllo si partirebbe con un indirizzo che
    non esiste e il video non partirebbe.  Con il controllo parte a 720p e il
    menu mostra la spunta su 720p, che e' la verita'.

    Le posizioni `bassa`/`media`/`alta` invece sono sempre valide, e non hanno
    bisogno di questo: sono un posto nella lista, non una risoluzione.
    """
    risoluzioni = voce.get("risoluzioni")
    if not isinstance(risoluzioni, list) or not risoluzioni:
        return voce
    ordinate = sorted(risoluzioni,
                      key=lambda r: int(r.get("frameWidth") or 0))
    scelta = _la_risoluzione(ordinate, larghezza_video, scelta)
    voce["url"] = scelta.get("url") or voce.get("url") or ""
    voce["checksum"] = scelta.get("checksum") or ""
    voce["filesize"] = scelta.get("filesize") or 0
    voce["frameWidth"] = scelta.get("frameWidth") or 0
    voce["frameHeight"] = scelta.get("frameHeight") or 0
    # Quale delle disponibili sta girando davvero: il menu ci mette la spunta
    # e il lettore la usa per la scritta del tasto.  Senza, il menu mostrerebbe
    # la spunta dove l'utente aveva chiesto, non dove il video sta.
    voce["risoluzioneInUso"] = scelta.get("label") or ""
    voce["label"] = (f"in riproduzione: {scelta.get('label') or '?'} "
                     f"su {len(ordinate)} disponibili")
    return voce


def _la_risoluzione(ordinate: list, larghezza_video: int, scelta: str) -> dict:
    """Un file della lista, quello giusto.

    `ordinate` va dalla piu' piccola alla piu' grande, che e' l'ordine in cui
    le mette `voci()`.

    La scelta dell'utente ha la precedenza, ma solo se esiste: un'etichetta
    che quel video non ha non porta a niente, e il fallback e' la misura della
    casella, che e' cioe' quello che il programma avrebbe fatto comunque.
    """
    # Una posizione nella lista: sempre valida, perche' non nomina un file.
    if scelta in PER_TAGLIO:
        if scelta == "bassa":
            return ordinate[0]
        if scelta == "alta":
            return ordinate[-1]
        # "media": la piu' vicina alla meta'.  Su due file (bassa e alta) non
        # c'e' una meta', e si prende la piu' piccola: e' quella che non
        # fa impiantare il programma su una macchina senza scheda video.
        meta = (len(ordinate) - 1) / 2
        return ordinate[round(meta)]

    # Un'etichetta vera: solo se questo video ce l'ha.
    if scelta and scelta != AUTOMATICA:
        for r in ordinate:
            if str(r.get("label") or "") == scelta:
                return r
        # Non esiste: si va avanti e si lascia decidere la misura, senza
        # fermarsi, che altrimenti un video non partirebbe.

    # AUTOMATICA: la piu' piccola, e poi la prima che sta nella casella.
    if larghezza_video > LATO_SCELTO:
        for r in ordinate:
            if int(r.get("frameWidth") or 0) >= larghezza_video:
                return r
        # nessuna e' abbastanza grande: la piu' grande, che e' anche la
        # piu' adatta a un riquadro piu' piccolo
        return ordinate[-1]
    return ordinate[0]


def nome_categoria(chiave: str, lingua: str | None = None) -> str:
    """Il nome che il server dà alla categoria.

    Si chiede al server e non si tiene una tabella: il nome può cambiare con
    la lingua — per esempio ho misurato `category.name` = "Ultimi video" con
    `languageCode` "I" — e una tabella scritta a mano direbbe la parola
    sbagliata in un'altra lingua senza che nulla lo segnali.

    Per questo il default non e' "I": e' la lingua scelta, cosi' cambiando
    lingua cambia anche il nome della sezione, che e' la cosa che si vede.
    """
    dati = _chiedi(chiave, lingua)
    categoria = dati.get("category")
    if isinstance(categoria, dict):
        return categoria.get("name") or chiave
    return chiave


def categorie_di(natura: str) -> list:
    """Le categorie che hanno dentro media di un certo tipo.

    `natura` e' `"video"`, `"audio"` o `"entrambe"`.  Il risultato sono le
    terne gia' di `CATEGORIE`, quindi chi le mostra non deve cercare il nome
    in un secondo posto.

    UNA CHIAVE MISTA COMPAARE DUE VOLTE
    -----------------------------------
    `VOXDramaticBibleReading` ha 10 video e 7 audio: e' vera per entrambe le
    schede, quindi `categorie_di("video")` e `categorie_di("audio")` la
    restituiscono entrambe.  E' quello che deve succedere — la stessa
    lettura si puo' guardare e si puo' ascoltare — e la griglia dentro la
    scheda poi mostra solo la parte giusta, perche' a filtrare e'
    `MediaView._quando_video`, non questa funzione.

    Una chiave che non sta in `NATURA` non viene restituita: e' una categoria
    che qualcuno ha aggiunto alla tabella sopra senza dire che tipo e', e
    mostrarla in una scheda a caso e' peggio che non mostrarla.  Il conto si
    vede con `python3 -m Utility.Mediator`, che lo segnala.
    """
    return [c for c in CATEGORIE
            if NATURA.get(c[0]) == natura
            or (natura == "video" and NATURA.get(c[0]) == "entrambe")
            or (natura == "audio" and NATURA.get(c[0]) == "entrambe")]


def _prova() -> int:
    """Prova il modulo: che cosa risponde davvero, adesso.

        python3 -m Utility.Mediator

    Serve a una cosa sola: quando le categorie cambiano, o il mediator
    sparisce, accorgersene con un comando invece che con una sezione vuota
    e nessun messaggio.
    """
    from Utility import Lingua
    lingua = Lingua.corrente_simbolo()
    print(f"lingua scelta: {lingua} "
          f"({Lingua.titolo(Lingua.corrente_voce()) or 'senza nome'})")
    # Una riga per categoria, con dentro il conto dei due tipi: e' il numero
    # che fa capire se una categoria sta nella scheda giusta.  Una categoria
    # audio elencata fra i video e' il difetto che questa stampa serve a
    # trovare, quindi si vede subito e non serve aprire la finestra.
    sbagliate = 0
    for chiave, nome, _descrizione in CATEGORIE:
        try:
            elenco = voci(chiave, lingua)
        except ErroreMediator as errore:
            print(f"  {nome:26} {errore}")
            continue
        n_audio = sum(1 for v in elenco
                      if (v.get("mimetype") or "").lower().startswith("audio/"))
        n_video = sum(1 for v in elenco
                      if (v.get("mimetype") or "").lower().startswith("video/"))
        natura = NATURA.get(chiave, "?")
        # Il conto e la tabella devono dire la stessa cosa: se la tabella
        # dice "audio" e il server non ha audio, la tabella ha ragione.
        vero = ("audio" if n_audio and not n_video else
                "video" if n_video and not n_audio else
                "entrambe" if n_audio and n_video else "vuota")
        concorda = (vero == natura or (vero == "vuota" and natura == "?"))
        if not concorda:
            sbagliate += 1
        print(f"  {nome:26} {len(elenco):4} voci"
              f"  audio={n_audio:4} video={n_video:4}"
              f"  [{natura:8}{'' if concorda else '  NON CONCORDA: era ' + vero}]"
              f"  (dal server: {nome_categoria(chiave, lingua)!r})")
    if sbagliate:
        print(f"\n  ATTENZIONE: {sbagliate} categorie hanno un'altra natura"
              f" rispetto alla tabella NATURA.")
    else:
        print("\n  La tabella NATURA combacia con quello che c'è sul server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_prova())