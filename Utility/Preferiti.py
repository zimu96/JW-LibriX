#
#  Preferiti.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I Preferiti: le pubblicazioni che l'utente tiene a portata di mano.

PERCHE' UN FILE E NON UNA TABELLA DEL DATABASE
---------------------------------------------
Sono tre righe e sono dell'utente.  Una tabella SQLite per tre righe e' un
database da aprire, interrogare e chiudere ogni volta che la Home viene
costruita, e il file dei Preferiti si puo' copiare, guardare e correggere
con un editor di testo.  Il criterio e' quello scritto nel progetto
precedente: "per la sezione Studio personale si puo' implementare per
ultima e in modo semplice".

NON SE NE INVENTANO
-------------------
Un Preferito che non c'e' e' peggio di nessun Preferito.  Se l'app metteva
li' tre pubblicazioni a caso per riempire la griglia, l'utente non saprebbe
quale toccare per cambiarla, e la griglia insegnerebbe il contrario di
quello che sembra.

COME SI AGGIUNGE E SI TOGLIE
----------------------------
Con il tasto destro sul titolo di una riga dell'elenco delle
pubblicazioni, e con il tasto destro su un Preferito per toglierlo.  Il
tasto destro e' la via giusta perche' non ruba spazio a nessuno e non si
confonde con il clic che apre la pubblicazione.

IL FORMATO DEL FILE
-------------------
Un dizionario per pubblicazione, e ogni voce con il suo testo:

    {
      "pubblicazione": "nwtsty",
      "lingua": "I",
      "titolo": "Traduzione del Nuovo Mondo"
    }

La chiave e' la sigla e la lingua insieme, perche' la stessa sigla in due
lingue sono due pubblicazioni diverse e una non puo' sostituire l'altra.

UN MEDIA AGGIUNGE DUE CAMPI, E NON E' UNA COSA A PARTE
------------------------------------------------------
Una card dei media e' una traccia precisa, e il Preferito deve ricordarla:

    {
      "pubblicazione": "wsb",
      "lingua": "I",
      "titolo": "Perche' studiare la Bibbia?",
      "traccia": 2,
      "formato": "VIDEO"
    }

Non e' un secondo tipo di Preferito: e' lo stesso elenco, con **quale**
traccia.  La card dei Preferiti mostra la stessa cosa che mostra in
Multimedia — la stessa traccia, la stessa nuvoletta — perche' e' la stessa
voce in un altro posto, e una voce senza `traccia` e' una pubblicazione
intera, come tutte quelle gia' salvate.
"""
from __future__ import annotations

import json

FILE_PREFERITI = "preferiti.json"


def _percorso():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / FILE_PREFERITI


def leggi() -> list[dict]:
    """I Preferiti, nell'ordine in cui sono stati messi.

    Un file illeggibile non e' un errore che blocca l'app: si restituisce
    una lista vuota e si dice.  Meglio una Home senza Preferiti che
    un'home che non si apre.
    """
    try:
        percorso = _percorso()
        if not percorso.is_file():
            return []
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        if not isinstance(dati, list):
            return []
        return [voce for voce in dati if isinstance(voce, dict) and voce.get("pubblicazione")]
    except (OSError, ValueError) as errore:
        print(f"Preferiti illeggibili, uso una lista vuota ⚠️  {errore}")
        return []


def scrivi(preferiti: list[dict]) -> None:
    """Scrive i Preferiti.  Se non si puo', lo dice e non si finge niente."""
    try:
        percorso = _percorso()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(preferiti, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a salvare i Preferiti ⚠️  {errore}")


def _traccia(v: dict) -> int | None:
    """La traccia salvata in una voce, o None se e' una pubblicazione intera.

    ``None`` e ``0`` vogliono dire la stessa cosa: una voce senza una traccia
    sua.  Il file di prima non aveva il campo, e una voce di oggi con la
    traccia vuota sono la stessa pubblicazione intera.
    """
    t = v.get("traccia")
    if t in (None, "", 0):
        return None
    try:
        return int(t)
    except (TypeError, ValueError):
        return None


def _numero(traccia) -> int | None:
    """La traccia come numero, o None se non c'e' o non e' un numero."""
    if traccia in (None, "", 0):
        return None
    try:
        numero = int(traccia)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def chiave(sigla: str, lingua: str | None = None, traccia=None) -> str:
    """L'identita' di un Preferito: sigla, lingua e, se c'e', la traccia.

    LA LINGUA C'ENTRA
    -----------------
    La stessa sigla in due lingue sono due pubblicazioni diverse.  Con una
    sola sigla, mettere l'italiano cancellerebbe l'inglese.

    LA TRACCIA C'ENTRA DAL MOMENTO CHE SI SALVA
    -------------------------------------------
    Una card dei media e' una **traccia** precisa — `wsb` traccia 1 e `wsb`
    traccia 2 sono due video diversi, non la stessa cosa in due punti — e
    mettere fra i Preferiti «wsb traccia 2» non deve anche far comparire, o
    togliere, «wsb traccia 1».  La traccia entra nella chiave solo quando c'e':
    senza traccia la chiave e' quella di prima, cosi' i Preferiti gia' salvati
    si ritrovano identici.

    Senza `lingua` si usa quella scelta dall'utente, e non "I": un valore
    predefinito viene calcolato quando il modulo viene importato, quindi
    significherebbe "le chiavi dei Preferiti sono sempre italiane" e un
    Preferito spagnolo non si troverebbe piu'.

    LA LINGUA VUOTA E' L'ITALIANO, PER UN MOTIVO CONCRETO
    ----------------------------------------------------
    Il file dei Preferiti c'era gia' quando c'era una sola lingua e la sigla
    era `nwtsty_I`.  Se `v.get("lingua", ...)` non ci mette niente, il valore
    di prima era `I`: vuol dire che **non scrivere la lingua** e' la stessa
    cosa che scrivere l'italiano.  Cosi' i Preferiti gia' salvati continuano
    a valere e non spariscono dalla lista quando si cambia lingua.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()
    base = f"{sigla}_{lingua}"
    numero = _numero(traccia)
    # Il `#` non si trova in una sigla ne' in un simbolo di lingua: la chiave
    # di una traccia non puo' coincidere con quella della pubblicazione.
    return f"{base}#{numero}" if numero is not None else base


def c_e_(sigla: str, lingua: str | None = None, traccia=None) -> bool:
    """Questo pezzo e' gia' fra i Preferiti?

    Con la traccia si chiede di quella traccia; senza, della pubblicazione
    intera.  Sono due domande diverse: la stella accanto a una traccia dice
    «questa traccia e' qui», quella accanto a una pubblicazione dice «il
    pacchetto e' qui».
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()
    cercata = chiave(sigla, lingua, traccia)
    return any(chiave(v.get("pubblicazione", ""), v.get("lingua", "I"),
                      _traccia(v)) == cercata
               for v in leggi())


def aggiungi(pub, traccia=None, formato: str = "", titolo: str = "") -> bool:
    """Mette una pubblicazione, o una sua traccia, fra i Preferiti.

    :param pub: una Publication del catalogo
    :param traccia: il numero della traccia per un media, o None per la
        pubblicazione intera
    :param formato: ``"VIDEO"`` o ``"AUDIO"`` per una traccia
    :param titolo: il titolo da mostrare; vuoto prende quello della
        pubblicazione.  Per una traccia il titolo e' quello della traccia,
        che non e' il titolo della pubblicazione.
    :returns: True se e' stata aggiunta, False se c'era gia'.

    Non si toglie e si rimette: se c'e' gia' non si fa niente e si dice
    che c'era.  Togliere e rimettere cambierebbe la posizione nella
    griglia, e la posizione e' scelta dell'utente.
    """
    sigla, lingua = pub.keySymbol, _lingua(pub)
    numero = _numero(traccia)
    if c_e_(sigla, lingua, numero):
        return False
    preferiti = leggi()
    voce = {"pubblicazione": sigla, "lingua": lingua,
            "titolo": titolo or getattr(pub, "title", "") or sigla}
    if numero is not None:
        voce["traccia"] = numero
        voce["formato"] = str(formato or "").upper()
    preferiti.append(voce)
    scrivi(preferiti)
    return True


def togli(sigla: str, lingua: str | None = None, traccia=None) -> bool:
    """Toglie una pubblicazione, o una sua traccia, dai Preferiti.

    Senza `lingua` si toglie dalla lingua scelta: vedi `chiave` perche' il
    default non puo' essere "I".  Senza `traccia` si toglie la pubblicazione
    intera e non le singole tracce: sono due Preferiti diversi.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()
    numero = _numero(traccia)
    cercata = chiave(sigla, lingua, numero)
    preferiti = leggi()
    rimasti = [v for v in preferiti
               if chiave(v.get("pubblicazione", ""), v.get("lingua", "I"),
                         _traccia(v)) != cercata]
    if len(rimasti) == len(preferiti):
        return False
    scrivi(rimasti)
    return True


def _lingua(pub) -> str:
    """La lingua scritta di una pubblicazione, in forma breve.

    Il catalogo la chiama ``mepsLanguageId`` e la tiene come numero; la
    cartella del pacchetto la chiama con le lettere.  Serve la forma
    breve, perche' e' quella con cui si cerca la cartella e quella con cui
    si chiede al server.
    """
    from Utility import Lingua

    # Il numero viene dalla tabella del catalogo e il simbolo e' quello con cui
    # si cerca la cartella e si chiede al server: le due cose non si indovinano
    # l'una dall'altra, e il passaggio e' in `Lingua.da_numero`.
    return Lingua.da_numero(getattr(pub, "mepsLanguageId", Lingua.PREDEFINITA))


def titoli() -> list[tuple[str, str, str]]:
    """I Preferiti come terne (sigla, lingua, titolo), per la griglia."""
    return [(v.get("pubblicazione", ""), v.get("lingua", "I"),
             v.get("titolo") or v.get("pubblicazione", ""))
            for v in leggi()]


def voci() -> list[dict]:
    """I Preferiti come sono scritti, traccia compresa.

    `titoli` perde la traccia — una terna non ha dove metterla — e la Home
    che disegna le card ha bisogno di sapere **quale** traccia e' stata messa
    fra i Preferiti: e' quella che la card fa partire.  Qui si restituiscono i
    dizionari interi e chi disegna prende quello che gli serve.
    """
    return list(leggi())