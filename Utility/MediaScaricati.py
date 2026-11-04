#
#  MediaScaricati.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 10/10/26.
#

"""I video e gli audio scaricati, e come si chiamano.

IL PROBLEMA
-----------
Un pacchetto scaricato e' una **cartella** (``sjj_I/contents/sjj_I.db``) e la
sezione Scaricati la vede.  Un video scaricato dalla nuvoletta di una card
e' invece un **file sciolto** nella radice dei dati:

    wsb_I_02_r720P.mp4

Non e' dentro nessuna cartella, e `JWPubManager.scaricate()` — che guarda solo
le cartelle con un ``contents/*.db`` — non lo vede.  Il risultato era che si
scaricava un video, la nuvoletta spariva, e il video non compariva da nessuna
parte del programma: sparito, con la sola prova che il file era sul disco.

PERCHE' IL NOME SI PARSA E NON SI CERCA
---------------------------------------
Il nome lo scrive il server e ha una forma fissa:

    sigla_lingua_traccia_rAltezzaP.mp4
    |     |      |      |
    |     |      |      la risoluzione: `r720P`, `r480P`, `r240P`
    |     |      la traccia a due cifre: `02`
    |     il simbolo della lingua: `I`, `S`
    la sigla della pubblicazione

La sigla non si indovina dal titolo e la risoluzione non si sa: si leggono
dal nome, che e' un fatto — il titolo per come lo conosce l'utente sta nel
catalogo, e la risoluzione per come la sa la riga della sezione.

I FILE MESSI A MANO
-------------------
La sezione mostra quello che c'e' sul disco da **qualunque parte venga**: il
download dalla nuvoletta, o un file copiato dentro la cartella dei dati da
fuori che abbia la forma del nome.  Per l'utente e' la stessa cosa — l'ha
scaricato lui — e dividerli sarebbe inventare due categorie che su un disco
non hanno un segno per essere riconosciute.
"""

from pathlib import Path

from Utility.CatalogoMedia import voce_di
from Utility.Extensions.Ext_FileManager import get_documents_directory

_VIDEO = (".mp4", ".m4v", ".mov")
_AUDIO = (".mp3", ".m4a", ".aac")
_TUTTI = _VIDEO + _AUDIO


def _pulito(sigla: str) -> str:
    """La sigla togliendo il marchio che il server ci mette davanti.

    Il `naturalKey` di una voce del mediator comincia con `pub-` o con
    `docid-`, e quel pezzo **non fa parte del nome del file**:

        docid-1112024060_I_1_VIDEO   ->   1112024060_I_cnt_1_r240P.mp4
        pub-jwb-142_I_2_VIDEO        ->   jwb-142_I_02_r240P.mp4

    Senza toglierlo, la sigla della voce e quella del nome non sono la stessa
    cosa e il confronto fallisce sempre: il file c'e' e il programma non lo
    vede.  E' il caso di tutta la categoria «Aggiornamenti dal Corpo
    Direttivo», che sono 56 video.
    """
    for marchio in ("pub-", "docid-", "pub_", "docid_"):
        if sigla.startswith(marchio):
            return sigla[len(marchio):]
    return sigla


def _tokens(nome: str) -> list:
    """Il nome di un media senza l'estensione, diviso in pezzi.

    La risoluzione (`r240P`, `r720P`) viene **tolta**, e non perche' non
    serva ma perche' e' un numero che sembra una traccia: senza toglierla,
    `wsb_I_02_r720P.mp4` avrebbe due numeri e il confronto cercherebbe la
    traccia 720.

    Un brano non ha risoluzione: `iam-1_I_01.mp3` si ferma alla traccia.  Non
    e' una forma diversa, e' la stessa con un pezzo in meno.
    """
    pezzi = Path(nome).stem.split("_")
    if pezzi and _e_risoluzione(pezzi[-1]):
        pezzi = pezzi[:-1]
    return pezzi


def _e_risoluzione(pezzo: str) -> bool:
    """`r240P` e' una risoluzione; `cnt` e un'etichetta; `02` e' una traccia."""
    if len(pezzo) < 2 or pezzo[0] not in "rR":
        return False
    return pezzo[1:-1].isdigit() and pezzo[-1] in "Pp"


def _numeri(pezzi: list) -> list:
    """I pezzi che sono numeri, nell'ordine in cui compaiono.

    Sono le tracce.  Piu' di uno e' normale: `jwb_I_201904_11_r240P.mp4` ha
    il mese (`201904`) e poi il giorno (`11`), e la voce del mediator porta
    `pub-jwb_I_201904_11_VIDEO`, quindi anche lei due numeri.  Per questo il
    confronto non prende «il primo numero» e non prende «l'ultimo»: chiede
    che i numeri del **file** contengano, nello stesso ordine, quelli della
    voce — cosi' `jwb` con `[201904]` non prende `jwb_I_201905_11` e non
    prende `jwbvod26_I_43`.
    """
    return [int(p) for p in pezzi if p.isdigit()]


def _parsa(nome: str) -> dict | None:
    """Il nome del file diviso nei suoi pezzi, o None se non e' un media.

    Un nome che non ha la forma di un media scaricato — un pacchetto, una
    copertina, un file di servizio — resta fuori: e' la radice dei dati, e
    dentro c'e' di tutto.  Guarda l'elenco di `get_documents_directory()`.

    TRE FORME, TUTTE VERE, MISURATE SUL SERVER
    ------------------------------------------
    Il nome non e' sempre `<sigla>_<lingua>_<traccia>`: ci sono tre famiglie
    diverse, e il parser vecchio ne riconosceva una.

        jwb-142_I_02_r240P.mp4        la forma normale
        jwb-141_s-Vad_I_02_r240P.mp4  con un pezzo in piu' in mezzo
        jlp_I_r240P.mp4               senza numero di traccia
        1112024060_I_cnt_1_r240P.mp4  con `cnt_` davanti alla traccia

    Il parser vecchio chiedeva tre pezzi esatti e una lingua tutta alfabetica,
    quindi delle quattro ne accettava **una**.  Le altre tre finivano fuori
    dalla sezione Scaricati e non contavano come scaricate: il file c'era, la
    nuvoletta non si spegneva, e l'utente guardava un video che aveva gia'
    scaricato e che il programma diceva di no.

    Adesso non si pretendono pezzi fissi: la sigla e' il primo pezzo, la
    lingua e' il primo pezzo dopo la sigla che non contiene numeri, e le
    tracce sono **tutti** i numeri che si trovano.  Ognuna delle quattro
    famiglie ci torna dentro, e una quinta che non ho ancora visto ci
   Entrerebbe lo stesso, perche' la regola non guarda la forma: guarda cosa c'e'.
    """
    estensione = Path(nome).suffix.lower()
    if estensione not in _TUTTI:
        return None

    pezzi = _tokens(nome)
    if len(pezzi) < 2:
        return None

    sigla = pezzi[0]
    if not sigla or len(sigla) < 2:
        return None

    lingua = ""
    numeri = _numeri(pezzi[1:])
    for pezzo in pezzi[1:]:
        if not any(c.isdigit() for c in pezzo):
            lingua = pezzo
            break

    return {
        "sigla": sigla,
        "lingua": lingua,
        "traccia": numeri[0] if numeri else 0,
        "tracce": numeri,
        "risoluzione": (Path(nome).stem.split("_")[-1]
                        if _e_risoluzione(Path(nome).stem.split("_")[-1])
                        else ""),
        "formato": "VIDEO" if estensione in _VIDEO else "AUDIO",
    }


def scaricati() -> list:
    """I media sciolti sul disco, uno per file, in ordine di nome.

    Ogni voce e' un dizionario con cio' che serve alle righe della sezione:

        nome        il nome del file, per il cestino e i messaggi
        sigla       la pubblicazione (``wsb``)
        lingua      il simbolo della lingua (``I``)
        traccia     il numero (``2``)
        risoluzione la risoluzione nel nome (``r720P``) o "" se non c'e'
        formato     ``VIDEO`` o ``AUDIO``
        titolo      quello del catalogo, o il nome del file se il catalogo
                    non lo conosce: un file messo a mano mostra un nome vero
                    invece di un buco
        file        il percorso intero, quello che si suona e si cancella
        peso        i byte, perche' la riga dice quanto e' grande

    IL TITOLO VIENE DAL CATALOGO, LA RIGA DAL DISCO
    -----------------------------------------------
    Il catalogo puo' non esserci (si sta aggiornando, o e' sparito): il
    titolo diventa il nome del file, che e' comunque un nome che dice
    qualcosa.  Un'eccezione dentro `voce_di` non deve far cadere la lista:
    si mostra una riga in meno piuttosto che niente.
    """
    radice = get_documents_directory()
    lista: list = []
    for percorso in sorted(radice.iterdir()):
        if not percorso.is_file():
            continue
        pezzi = _parsa(percorso.name)
        if pezzi is None:
            continue
        try:
            voce = voce_di(pezzi["sigla"], pezzi["lingua"], pezzi["traccia"])
        except Exception:  # noqa: BLE001
            voce = None
        titolo = (voce or {}).get("title") or ""
        if not titolo:
            titolo = percorso.name
        try:
            peso = percorso.stat().st_size
        except OSError:
            peso = 0
        pezzi.update({
            "nome": percorso.name,
            "titolo": titolo,
            "file": percorso,
            "peso": peso,
        })
        lista.append(pezzi)
    return lista


#: L'indice dei media sul disco, con la data della cartella per sapere se
#: vale ancora.  Vedi `_indice`.
_INDICE: dict = {"quando": None, "voci": {}}


def _indice() -> dict:
    """I media sul disco, per nome in minuscolo.

    UNA SOLTA LETTURA PER TUTTE LE DOMANDE
    -------------------------------------
    `file_di` viene chiamata una volta per card, e le card sono fino a
    trecento: leggere la cartella trecento volte e' spreco.  E serve anche
    per un altro motivo — per confrontare **senza distinzione di
    maiuscole**, e su un filesystem che distingue `S-34v_...` da
    `s-34v_...` un `glob` sbagliato semplicemente non trova niente.

    La distinzione non e' un capriccio: il server scrive la chiave
    `pub-s-34v_I_24_VIDEO` e il file `S-34v_I_024_r240P.mp4`.  La stessa
    sigla, una volta minuscola e una volta maiuscola, nella stessa risposta.
    Con le lettere che non tornavano, quei video della categoria «Altro» si
    scaricavano e risultavano sempre non scaricati.

    L'indice vale finche' la cartella non cambia, e si butta quando cambia:
    lo dice la data di modifica della cartella, che e' una domanda sola e
    costa niente rispetto a rileggere tutti i nomi.
    """
    radice = get_documents_directory()
    try:
        quando = radice.stat().st_mtime_ns
    except OSError:
        return {}
    if _INDICE.get("quando") == quando:
        return _INDICE["voci"]
    voci: dict[str, Path] = {}
    try:
        for percorso in radice.iterdir():
            if percorso.suffix.lower() not in _TUTTI:
                continue
            voci[percorso.name.casefold()] = percorso
    except OSError:
        return {}
    _INDICE["quando"] = quando
    _INDICE["voci"] = voci
    return voci


def file_di(sigla: str, lingua: str, traccia, formato: str | None = None) -> Path | None:
    """Il file di quella traccia che e' sul disco, o None.

    `traccia` puo' essere un numero solo oppure **l'elenco** dei numeri della
    traccia, che e' quello che danno le voci del mediator: un video di
    «Adorazione mattutina» e' `jwb_I_202104_02_r240P.mp4`, e i suoi numeri sono
    due (il mese e il giorno).  Con un numero solo il confronto non tornava
    mai e quei video risultavano scaricati che non erano mai scaricati.

    `formato` dice quale file si cerca: ``"VIDEO"`` o ``"AUDIO"``.  Serve
    perche' lo stesso programma esce in due formati, e il file che c'e' sul
    disco puo' essere uno solo dei due: la Torre di Guardia ha l'audio
    scaricato e il video no.  Senza il formato, «Guarda il video» poteva
    trovarsi l'audio e suonare la voce al posto delle immagini.

    SI CERCANO TUTTE LE RISOLUZIONI, E SI PRENDE LA PIU' GRANDE
    -----------------------------------------------------------
    Se l'utente ha preso il 720p e poi il 180p sono due file, ``..._r720P.mp4``
    e ``..._r180P.mp4``, e per il lettore qualsiasi dei due va bene: il file
    e' vero e il video si guarda.  Fra due si prende il piu' grande, che e'
    quello che l'utente ha scelto per primo e quello che si vede meglio.

    IL CONFRONTO E' «SIGLA + TRACCE CONTENUTE», E NON UNA PREFISSO FISSO
    ------------------------------------------------------------------
    Il prefisso che c'era prima, `sigla_lingua_traccia02_`, funzionava solo
    per la forma piu' comune.  Ma il nome sul disco ha tre altre forme, e con
    quel prefisso non ne trovava nessuna:

        jwb-141_s-Vad_I_02_r240P.mp4   c'e' un pezzo in piu' in mezzo
        jlp_I_r240P.mp4                non c'e' il numero di traccia
        1112024060_I_cnt_1_r240P.mp4   c'e' `cnt_` davanti alla traccia

    Il file c'era, il programma diceva che non era scaricato, e l'utente
    riscaricava quello che aveva gia' scaricato.  Sono 56 video su «Aggiornamenti
    dal Corpo Direttivo» e tutti i video con un indicatore di serie in mezzo.

    Quindi si cercano due fatti che sono uguali **da entrambe le parti**: la
    sigla — senza il marchio `pub-` o `docid-` che ci mette il server e che nel
    nome non c'e' — e i numeri della traccia, che nel file devono comparire
    nello stesso ordine.  Il resto del nome non si guarda: `I`, `s-Vad` e
    `cnt` possono essere quello che vogliono.

    `traccia` a zero (la famiglia `x`, cioe' i brani biblici recitati che non
    hanno numero) accetta il file con la sola sigla: sono file con una sigla
    tutta loro, quindi non si confonde con nessuno.
    """
    sigla = _pulito(sigla or "")
    if not sigla:
        return None
    voci = [int(t) for t in traccia] if isinstance(traccia, (list, tuple)) \
        else ([int(traccia)] if traccia else [])

    candidati = []
    for nome, percorso in _indice().items():
        pezzi = _tokens(percorso.name)
        if len(pezzi) < 2:
            continue
        if _pulito(pezzi[0]).casefold() != sigla.casefold():
            continue
        if _numeri(pezzi[1:]) != voci:
            continue
        if formato and _formato_del_file(percorso) != formato:
            continue
        candidati.append(percorso)
    if not candidati:
        return None
    return max(candidati, key=_peso_del_file, default=None)


def _formato_del_file(percorso: Path) -> str:
    """``"VIDEO"`` o ``"AUDIO"``, secondo l'estensione del file."""
    return "VIDEO" if Path(percorso).suffix.lower() in _VIDEO else "AUDIO"


def _peso_del_file(percorso: Path) -> int:
    """I byte del file, o zero se non si puo' sapere."""
    try:
        return percorso.stat().st_size
    except OSError:
        return 0