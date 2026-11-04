#
#  MepsAPI.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le API del server: il manifesto dei media, e quello che si puo' scaricare.

PERCHE' QUESTO MODULO ESISTE
-----------------------------
Perche' il server risponde, e risponde bene.  Una sola richiesta restituisce
tutto quello che serve su una pubblicazione: ogni formato, ogni lingua,
la durata, la risoluzione, il bitrate, se ha i sottotitoli, e l'indirizzo
con il checksum per controllare che il download sia integro.  Non serve
interrogare un file alla volta.

QUEL CHE E' STATO VERIFICATO, E QUELLO CHE NO
----------------------------------------------
Questo file nasce perche' un modulo scritto altrove indicava due indirizzi.
Sono stati provati entrambi, e nessuno dei due esiste:

    pub-media.jw.org/GETPUBMEDIALINKS   il dominio non e' nel DNS
    mediator.jw.org/v1/...              HTTP 404

Quello che funziona e' un terzo, gia' usato dal progetto:

    b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS    HTTP 200, 128.376 byte

Quindi qui sotto c'e' l'indirizzo che risponde.  Se un giorno smette di
rispondere, la cosa da cambiare e' ``BASE_MEDIA`` e nient'altro: e' l'unico
posto dove l'indirizzo esiste.

LA LOGICA DI LETTURA ERA GIUSTA
-------------------------------
Il modulo di prima leggeva bene la risposta, solo che dall'indirizzo morto.
La forma dei dati qui e' quello che arriva davvero, verificata:

    files -> lingua -> formato -> lista di voci
    ogni voce ha: title, label, format, formatDescr, filesize,
                  duration, bitRate, frameWidth, frameHeight, frameRate,
                  subtitled, edition, specialty, markers, track, hasTrack,
                  docid, booknum, mimetype, pub, trackImage
    ogni voce ha un file: url, checksum, modifiedDatetime, stream

I campi che servono per il video e l'audio sono quasi tutti in quella lista.
``frameHeight``, ``frameWidth`` e ``frameRate`` dicono la risoluzione;
``bitRate`` dice la qualita'; ``duration`` dice quanto dura; ``subtitled``
dice se ci sono i sottotitoli.  Non serve sapere nulla di piu' per offrire
un file in ogni risoluzione: e' gia' scritto.

LA GRANULARITA' PER CAPITOLO: COME FUNZIONA DAVVERO
--------------------------------------------------
Qui sotto la versione precedente diceva che il server accetta ``booknum`` e
``chapid`` e che si scarica il capitolo solo.  Era una conclusione
affrettata, e va corretta perche' un'API che promette una cosa e ne fa
un'altra e' peggio di un'API che non esiste.

Quello che e' stato misurato, sulla Bibbia in italiano:

    booknum=24                    HTTP 200, 1 voce, hasTrack=0
    booknum=24, chapid=51         HTTP 200, 1 voce, hasTrack=0
    track=1                       HTTP 404
    senza parametri               HTTP 200, 1 voce, hasTrack=0

Le prime due rispondono 200 ma restituiscono LA PUBBLICAZIONE INTERA, cioe'
lo stesso pacchetto da 122 MB.  Non filtrano niente: il parametro viene
accettato e ignorato.  Il 200 dice che la richiesta e' valida, non che il
risultato sia quello che si voleva.  Un ``assert status == 200`` avrebbe
dato la stessa risposta.

Il modo vero per avere un capitolo solo NON e' un parametro, e' un campo:
``hasTrack``.  Quando e' vero vuol dire che la pubblicazione ha tracce
separate, e nella risposta sono gia' tutte, una voce per traccia, con
l'indirizzo proprio:

    sjj_I: 172 voci, di cui 165 con hasTrack

    "1 Le qualita' di Geova"   track 1   .../sjj_I_01.rtf
    "2 Geova e' il tuo nome"   track 2   .../sjj_I_02.rtf

Quindi si chiede la pubblicazione e si sceglie la traccia dalla risposta.
Non si chiede "solo la traccia 1": si ricevono tutte e si prende quella che
si vuole.  Per una pubblicazione con 165 tracce sono 165 voci in una
risposta sola, che e' veloce, e non 165 richieste.

``per_traccia()`` e' la funzione che fa questo, e ``capitolo()`` e' tenuta
perche' qualcuno potrebbe chiamarla: restituisce la pubblicazione intera ed
e' detto chiaramente nel docstring, cosi' nessuno la usa pensando che
filtri.

SENZA DIPENDENZE
----------------
Niente ``requests``.  Si usa ``urllib`` della libreria standard, come nel
resto del progetto: un programma che si installa con pip e' un programma
che va installato, e questa app si apre con ``python3 JWLibraryApp.py``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

# L'unico indirizzo che esiste.  Se un giorno risponde diversamente, e' qui.
BASE_MEDIA = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"

# Quanto si aspetta una risposta.  Sono 128 KB per una pubblicazione con
# molti formati: trenta secondi sono abbondanti e non fanno aspettare
# un errore per sempre.
TIMEOUT = 30


class ErroreMeps(Exception):
    """Il server ha risposto, ma non con quello che serviva."""


def _chiedi(parametri: dict) -> dict:
    """Una richiesta al server, e la risposta come dizionario."""
    completi = dict(parametri)
    completi.setdefault("output", "json")
    indirizzo = f"{BASE_MEDIA}?{urllib.parse.urlencode(completi)}"
    try:
        with urllib.request.urlopen(indirizzo, timeout=TIMEOUT) as risposta:
            corpo = risposta.read()
    except urllib.error.HTTPError as errore:
        # Il 400 e' il caso normale quando si chiede una lingua che non
        # esiste, e va detto in chiaro: "questa lingua non c'e'", non
        # "errore sconosciuto".
        if errore.code == 400:
            raise ErroreMeps(
                f"Il server non capisce la richiesta {completi} ⚠️") from errore
        raise ErroreMeps(
            f"Il server risponde {errore.code} a {indirizzo} ⚠️") from errore
    except urllib.error.URLError as errore:
        raise ErroreMeps(f"Nessuna risposta dal server: {errore.reason} ⚠️") from errore
    try:
        return json.loads(corpo)
    except ValueError as errore:
        raise ErroreMeps("La risposta non è JSON ⚠️") from errore


def _appiattisci(dati: dict) -> list[dict]:
    """Le voci di tutte le lingue e tutti i formati, in una lista sola.

    La risposta e' a tre livelli: files -> lingua -> formato -> lista.  Chi
    la usa deve sapere solo della lista, e il formato e la lingua restano
    dentro ogni voce, perche' servono per scegliere cosa scaricare.
    """
    voci = []
    for lingua, formati in (dati.get("files") or {}).items():
        for formato, elenco in formati.items():
            if isinstance(elenco, dict):
                elenco = [elenco]
            for voce in elenco or []:
                if not isinstance(voce, dict):
                    continue
                aggiunta = dict(voce)
                aggiunta["lingua"] = lingua
                aggiunta.setdefault("formato", formato)
                voci.append(aggiunta)
    return voci


def media(pub: str, lingua: str | None = None, issue: str | None = None,
          traccia: int | None = None) -> list[dict]:
    """Tutti i file di una pubblicazione, in ogni formato.

    :param pub: la sigla, per esempio ``nwtsty`` o ``sjj``
    :param lingua: il simbolo, per esempio ``I`` per l'italiano.  Senza
        questo si usa la lingua scelta dall'utente: il default non puo' essere
        la lettera "I" perche' un valore predefinito viene calcolato quando il
        modulo viene importato, e quindi significherebbe "italiano per sempre".
    :param issue: per i periodici, il numero dell'edizione
    :param traccia: una sola traccia: la risposta e' piccola (0,2 s invece di 5 s su `sjjm`)

    Il controllo e' `if not lingua` e non `if lingua is None`: la stringa
    vuota non e' `None` e passava oltre, e il server rispondeva «non capisco
    la richiesta» con `langwritten: ""`.  Vedi la nota di `Mediator._chiedi`,
    che spiega perche' la stringa vuota arriva.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()
    # I video senza sigla (gli Aggiornamenti del Corpo Direttivo) si chiedono
    # per documento: `docid-1112024002` diventa il parametro `docid`.
    if str(pub).startswith("docid-"):
        parametri = {"docid": str(pub)[6:], "langwritten": lingua}
    else:
        parametri = {"pub": pub, "langwritten": lingua}
    if issue:
        parametri["issue"] = issue
    if traccia:
        parametri["track"] = int(traccia)
    return _appiattisci(_chiedi(parametri))


def capitolo(pub: str, libro: int, capitolo: int, lingua: str | None = None) -> list[dict]:
    """NON FILTRA.  Restituisce la pubblicazione intera.

    Resta perche' qualcuno potrebbe chiamarla, ma va detto chiaro: il
    server accetta ``booknum`` e ``chapid`` e risponde 200, pero' NON
    applica il filtro e rimanda tutto.  Misurato: sulla Bibbia in italiano
    danno lo stesso identico pacchetto da 122 MB con e senza i due
    parametri.

    Per un capitolo solo si usa ``per_traccia()``, che lavora sulla risposta
    invece che sui parametri.
    """
    return _appiattisci(_chiedi({"pub": pub, "langwritten": lingua,
                                 "booknum": int(libro), "chapid": int(capitolo)}))


def per_traccia(voci: list[dict]) -> list[dict]:
    """Le voci che sono tracce singole, cioe' i file scaricabili a uno a uno.

    Si riconoscono da ``hasTrack``.  E' il campo che dice "questa
    pubblicazione ha tracce separate": quando e' falso non c'e' niente da
    scegliere, e la pubblicazione si scarica come un file solo.
    """
    return [voce for voce in voci if voce.get("hasTrack")]


def traccia_numero(voce: dict) -> int:
    """Il numero della traccia, o 0 se non e' una traccia.

    Il numero arriva in ``track``.  Quando e' 0 la voce non e' una traccia
    singola ma il pacchetto intero, e restituire 0 permette di distinguerle
    senza sapere di piu' sul formato.
    """
    try:
        return int(voce.get("track") or 0)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# LE RISOLUZIONI E I FORMATI
# ---------------------------------------------------------------------------
#
# Il server mette la risoluzione dentro ogni voce e non ha un elenco
# separato delle risoluzioni possibili.  Quindi le risoluzioni disponibili
# per una pubblicazione sono QUELLE CHE HA RISPOSTO, non una lista scritta
# a mano: si deducono dalle voci.  E' il modo giusto, perche' una lista
# scritta a mano si sbaglia e promette formati che il server non ha.


def risoluzioni(voci: list[dict]) -> list[str]:
    """Le risoluzioni distinte presenti nelle voci, dalla piu' alta in giu'.

    Il formato e' "larghezzaxaltezza", come lo chiama il server, per esempio
    ``1920x1080``.  Sono i numeri, non un nome tipo "Full HD": il nome lo
    aggiunge la televisione e cambia da produttore a produttore, e qui non
    si sa quale sia.
    """
    trovate = set()
    for voce in voci:
        larghezza, altezza = voce.get("frameWidth"), voce.get("frameHeight")
        if larghezza and altezza:
            trovate.add(f"{int(larghezza)}x{int(altezza)}")
    def chiave(testo: str) -> int:
        try:
            larghezza, altezza = testo.split("x")
            return int(larghezza) * int(altezza)
        except (ValueError, TypeError):
            return 0
    return sorted(trovate, key=chiave, reverse=True)


def _formato(voce: dict) -> str:
    """Il formato di una voce.

    IL TRABATTO DEL CAMPO "format"
    ------------------------------
    Nella risposta il campo ``format`` DENTRO la voce e' vuoto.  Il formato
    vero e' la chiave del terzo livello: la risposta ha la forma

        files -> "I" -> "JWPUB" -> [ {...}, {...} ]

    e quel "JWPUB" e' il formato, non il campo ``format`` della voce, che
    arriva come stringa vuota.

    Perche' e' una trappola: il campo c'e' con il nome giusto, e chiedendo
    ``voce["format"]`` si ottiene ``""``, che e' falso, e un confronto con
    una stringa vuota non solleva nessun errore.  Il risultato e' una lista
    di formati vuota e un "questo video non esiste" che non ha motivo di
    esistere.

    Per questo qui si legge il livello della risposta, che e' il posto
    dove il formato e' scritto davvero.
    """
    return voce.get("formato") or voce.get("format") or ""


def formati(voci: list[dict]) -> list[tuple[str, str]]:
    """I formati presenti, come coppie (sigla, descrizione).

    La sigla serve per scegliere, la descrizione per mostrarle: ``JWPUB``
    da solo non dice niente a chi legge, ``Pacchetto JWPUB`` sì.
    """
    visti: dict[str, str] = {}
    for voce in voci:
        sigla = _formato(voce)
        if sigla:
            visti.setdefault(sigla, voce.get("formatDescr") or sigla)
    return sorted(visti.items())


def scegli(voci: list[dict], formato: str = "JWPUB") -> dict | None:
    """La prima voce del formato richiesto, o None se non c'e'.

    Se il formato richiesto non c'e' si restituisce None invece di
    qualcosa di diverso: scaricare un PDF quando si chiedeva un pacchetto
    e' peggio che non scaricare niente, perche' l'utente non lo saprebbe.
    """
    for voce in voci:
        if _formato(voce) == formato:
            return voce
    return None


def descrivi(voce: dict) -> str:
    """Una riga che spiega un file, per mostrarlo nella lista.

    Si mette solo quello che c'e'.  Un file senza risoluzione non e' un
    video a risoluzione sconosciuta: e' un audio, e la parola "video" non
    c'entra.
    """
    pezzi = [voce.get("title") or voce.get("label") or voce.get("pub") or "?"]
    pezzi.append(voce.get("formatDescr") or _formato(voce) or "?")
    if voce.get("frameWidth") and voce.get("frameHeight"):
        pezzi.append(f"{int(voce['frameWidth'])}x{int(voce['frameHeight'])}")
    if voce.get("subtitled"):
        pezzi.append("con sottotitoli")
    durata = voce.get("duration")
    if isinstance(durata, (int, float)) and durata > 0:
        secondi = int(durata) % 60
        minuti = int(durata) // 60
        pezzi.append(f"{minuti}:{secondi:02d}")
    dimensione = voce.get("filesize")
    if isinstance(dimensione, (int, float)) and dimensione > 0:
        pezzi.append(f"{dimensione / (1024 * 1024):.1f} MB")
    return " · ".join(str(pezzo) for pezzo in pezzi if pezzo)


# ---------------------------------------------------------------------------
# PROVA A LINEA DI COMANDO
# ---------------------------------------------------------------------------
#
#     python3 Utility/MepsAPI.py               tre pubblicazioni di prova
#     python3 Utility/MepsAPI.py sjj I         una pubblicazione, una lingua
#
# Serve per due cose: per vedere se il server risponde, e per cambiare una
# riga qui dentro e vederla subito, senza avviare la finestra.  E' il posto
# dove mettere le prove quando si scrive una funzione nuova: prima si prova
# qui, poi si collega alla finestra.
#
# Non usa PyQt e non disegna niente: e' roba di rete, e deve poter girare
# anche senza finestra aperta.

_PROVE = [("nwtsty", "I"), ("sjj", "I"), ("lff", "I")]

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        _PROVE = [(sys.argv[1], sys.argv[2])]
    elif len(sys.argv) == 2:
        _PROVE = [(sys.argv[1], "I")]

    for _sigla, _lingua in _PROVE:
        print(f"\n{'=' * 66}\n{_sigla} in {_lingua}\n{'=' * 66}")
        try:
            _voci = media(_sigla, _lingua)
        except ErroreMeps as _errore:
            print(f"  {type(_errore).__name__}: {_errore}")
            continue
        print(f"  {len(_voci)} file")
        print(f"  formati     : {formati(_voci)}")
        _resoluzioni = risoluzioni(_voci)
        print(f"  risoluzioni : {_resoluzioni or '(nessun video in questa pubblicazione)'}")
        _tracce = per_traccia(_voci)
        print(f"  tracce      : {len(_tracce)} file scaricabili a uno a uno")
        for _voce in _voci[:6]:
            print(f"    - {descrivi(_voce)}")
        _pacchetto = scegli(_voci, "JWPUB")
        if _pacchetto:
            print(f"  pacchetto   : {_pacchetto['file']['url']}")
            print(f"  checksum    : {_pacchetto['file'].get('checksum')}")
