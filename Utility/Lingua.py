#
#  Lingua.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 04/10/26.
#

"""La lingua dell'app: numero, simbolo, nome, e dov'e' salvata.

IL PROBLEMA CHE QUESTO MODULO RISOLVE
------------------------------------
La lingua era scritta a mano in sei posti, e i sei posti erano uguali e
sbagliati nello stesso modo.  Il pezzo che si ripeteva, parola per parola:

    {"E": 0, "I": 4}.get(lingua, 4)
    {0: "E", 4: "I"}.get(pub.mepsLanguageId, "I")

Lo si trovava in `SidebarView.py`, `HomeView.py`, `PubView.py`,
`DownloadsView.py`, `UpdatesView.py` e `Copertine.py`.  Sei dizionari di due
voci, in sei file, che dicono tutti la stessa cosa.

E LA COSA CHE MANCAVA ERA IL MOTIVO PER CUI ESISTONO
---------------------------------------------------
Quei due dizionari hanno dentro solo l'italiano e l'inglese, e il `4` di
riferimento e' l'italiano.  Quindi l'app non aveva una lingua: aveva
l'italiano con una eccezione per l'inglese.  Nell'app originale di Windows e
Android la lista delle lingue c'e', e sono 874.

DOVE VENGONO I NOMI DELLE LINGUE
--------------------------------
Dal `mepsunit.db` dell'app originale di Windows, che ha 1446 lingue con
`LanguageId`, `Symbol`, `EnglishName` e `VernacularName`:

    0  E  English                  English
    4  I  Italian                  Italiano
    1  S  Spanish                  Espanol
    3  F  French                   Francais

Quel file pesa 29 MB e sta nella cartella dei file originali, non dentro il
programma: non si puo' caricare a ogni avvio, e non si puo' copiare dentro
`Files/` perche' 29 MB di dati per una lista che ne occupa 112 KB.

Quindi il file e' stato **letto una volta e ridotto**: in `Files/lingue.json`
ci sono solo le 874 lingue che hanno pubblicazioni in `catalog.db`, con il
numero, il simbolo, il nome inglese, il nome nella propria lingua e quante
pubblicazioni ha.  Il file e' stato generato, non scritto a mano: nessun
nome e' inventato e ogni lingua ha almeno una pubblicazione, quindi la lista
non promette niente che il catalogo non abbia.

IL NUMERO E IL SIMBOLO NON SONO LA STESSA COSA
----------------------------------------------
Il catalogo e la Bibbia usano il **numero** (`MepsLanguageId = 4`); il
server dei media e il mediator usano il **simbolo** (`langwritten=I`).  Sono
due chiavi diverse della stessa cosa, e ogni passaggio dall'una all'altra
prima era scritto a mano.  Qui ci sono `da_numero()` e `da_simbolo()` e non
si scrive piu' nessuna delle due.

I RITORNI DI RIPIEGO NON SONO CASUALI
------------------------------------
Sono gli stessi che c'erano prima, cambiati solo di posto:

  * `da_simbolo` su un simbolo sconosciuto dà l'italiano, perche' il valore
    di default era 4 e adesso continua a essere 4;
  * `da_numero` su un numero che non è nel file dà il numero come testo,
    perche' il valore di default era `str(numero)` e adesso fa lo stesso.

Quindi un chiamante che sbaglia riceve ancora qualcosa di usabile e non un
errore, e una lingua che non è nel catalogo non blocca la finestra.

SENZA DIPENDENZE
----------------
`json` della libreria standard, come nel resto del progetto.
"""

import json
import sys
from pathlib import Path

# La radice del progetto in `sys.path`, perche' questo file si puo' lanciare
# da solo (`python3 Utility/Lingua.py`) e in quel modo `Utility` non
# verrebbe trovato.  Lo stesso trucco di `JWLibraryApp.py`.
if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Utility.Extensions.Ext_FileManager import BUNDLE_DIR

# Il file con le lingue, dentro `Files/`.  112 KB, generato dal
# `mepsunit.db` dell'originale: vedi la spiegazione in cima.
FILE_LINGUE = "lingue.json"

# La chiave dentro `impostazioni.json`.  Stessa cartella del tema, campo
# diverso, e `tema.salva_impostazione()` fa in modo che l'uno non cancelli
# l'altro.
CAMPO_LINGUA = "lingua"

#: L'italiano, che e' quello di prima e quello di default.
#:
#: Non e' una scelta: `DBManager.swift` aveva `WHERE MepsLanguageId = 4` e il
#: progetto originale metteva 4 anche quando costruiva una `Publication` di
#: prova.  Il default resta 4, quindi un utente che non ha mai toccato la
#: lingua vede esattamente l'app di prima.
PREDEFINITA = 4

# Le due lingue che c'erano prima, per quando serve sapere se il file e'
# sparito: senza `Files/lingue.json` il programma deve comunque partire e
# mostrare italiano e inglese, che sono le due che c'erano.
_DUE = (
    {"id": 0, "simbolo": "E", "nome": "English", "nome_vernacolare": "English",
     "pubblicazioni": 0},
    {"id": 4, "simbolo": "I", "nome": "Italian", "nome_vernacolare": "Italiano",
     "pubblicazioni": 0},
)

_cache: list[dict] | None = None

#: La lingua scelta in questa sessione.  `None` vuol dire "non l'ho ancora
#: cambiata", e allora la si legge dal file.  La si tiene qui perche' leggere
#: un file a ogni chiamata costerebbe una lettura per ogni riga di elenco
#: che si disegna, e il file non cambia da solo.
_scelta: int | None = None


def lingue() -> list[dict]:
    """Tutte le lingue del catalogo, ordinate per numero.

    Il risultato viene tenuto in memoria: il file non cambia durante la vita
    del programma e ogni schermata lo chiede piu' volte.

    Se il file non c'e' o non e' JSON si ricade sulle due lingue di prima, e
    non su un'eccezione: un file di dati mancante non e' un motivo per non
    aprire la finestra.
    """
    global _cache
    if _cache is not None:
        return _cache

    letto = None
    percorso = BUNDLE_DIR / "Files" / FILE_LINGUE
    try:
        grezzo = json.loads(percorso.read_text(encoding="utf-8"))
        letto = grezzo.get("lingue") if isinstance(grezzo, dict) else None
    except (OSError, ValueError, AttributeError):
        letto = None

    if not isinstance(letto, list) or not letto:
        print(f"{FILE_LINGUE} non leggibile: uso italiano e inglese ⚠️")
        _cache = list(_DUE)
        return _cache

    _cache = [voce for voce in letto if isinstance(voce, dict) and voce.get("id") is not None]
    return _cache


def ricarica() -> None:
    """Dimentica la lista tenuta in memoria.  Serve solo nelle prove."""
    global _cache
    _cache = None


def per_id(numero) -> dict | None:
    """La voce di una lingua dal numero, o None se non c'e'."""
    try:
        chiave = int(numero)
    except (TypeError, ValueError):
        return None
    for voce in lingue():
        if voce.get("id") == chiave:
            return voce
    return None


def per_simbolo(simbolo) -> dict | None:
    """La voce di una lingua dal simbolo, o None se non c'e'."""
    if not simbolo:
        return None
    testo = str(simbolo).strip().upper()
    for voce in lingue():
        if str(voce.get("simbolo", "")).upper() == testo:
            return voce
    return None


def iso_da_simbolo(simbolo) -> str:
    """Il codice ISO a due lettere di un simbolo, o "" se non si sa.

    Serve agli indirizzi di `www.jw.org`, dove il pezzo di lingua e' a due
    lettere (`/it/`, `/es/`) e non e' il simbolo del programma (`I`, `S`).
    Con lo spagnolo verrebbe `/s/`, che non esiste; con `es` la pagina c'e'.

    Il dato viene da `Files/lingue.json`, dove il campo si chiama come nella
    tabella dell'originale (`IsoAlpha2Code`).  Non si deduce dal nome della
    lingua: con 874 lingue non si puo' scrivere una regola che le copra tutte
    senza indovinare, e un indirizzo indovinato e' un 404.

    Non si rimette il simbolo al posto del codice quando il codice non c'e':
    sono due cose diverse, e `I` al posto di `it` produrrebbe `/i/...`, che e'
    un indirizzo che non esiste.  Chi chiama deve decidere cosa fare con la
    stringa vuota, e di solito e' lasciare che la pagina risponda 404.
    """
    voce = per_simbolo(simbolo)
    return str((voce or {}).get("iso") or "")


def iso_corrente() -> str:
    """Il codice ISO della lingua scelta, o "" se non c'e'.

    Come sopra, ma per la lingua scelta: `Notizie` la usa per l'indirizzo
    senza dover passare il simbolo ogni volta.
    """
    voce = corrente_voce()
    return str((voce or {}).get("iso") or "")


def da_simbolo(simbolo) -> int:
    """Il NUMERO di una lingua dal simbolo.  Italiano se non si sa.

    Era `{0: "E", 4: "I"}.get(simbolo, 4)` in tre file.  Ora e' qui, e il
    ripiego e' sempre 4 come prima.
    """
    voce = per_simbolo(simbolo)
    return PREDEFINITA if voce is None else voce["id"]


def da_numero(numero) -> str:
    """Il SIMBOLO di una lingua dal numero.  Il numero come testo se non si sa.

    Era `{0: "E", 4: "I"}.get(numero, "I")` in tre file.  Il ripiego e'
    `str(numero)`, non "I": con una lingua che non c'e' nel catalogo il
    numero e' comunque l'informazione giusta da passare al server, e
    scrivere "I" scaricherebbe l'italiano mentre l'utente ne ha chiesta un
   'altra.
    """
    voce = per_id(numero)
    if voce is None:
        return str(numero)
    return str(voce.get("simbolo") or numero)


def titolo(voce: dict) -> str:
    """Il nome da mostrare nel menu: quello nella propria lingua.

    Il nome nella propria lingua e non quello inglese perche' e' quello che
    serve a chi sta scegliendo: chi cerca ilDeutsch lo riconosce da
    «Deutsch» e non da «German».
    """
    if not isinstance(voce, dict):
        return ""
    return str(voce.get("nome_vernacolare") or voce.get("nome") or "")


def cerca(testo: str) -> list[dict]:
    """Le lingue il cui nome contiene `testo`, in ordine di quante pubblicazioni ha.

    Serve al campo di ricerca del menu.  La ricerca e' sui due nomi, quello
    inglese e quello nella propria lingua, perche' il nome con cui uno cerca
    una lingua non e' sempre quello scritto in un campo solo: il portoghese
    sta in «Portuguese (Brazil)» in inglese e in «Portugues (Brasil)» in
    portoghese, e nessuno dei due nomi contiene la parola con l'accento.

    IL SIMBOLO NON SI CERCA, E PERCHE'
    ----------------------------------
    Nella prima versione si cercava anche nel simbolo (`I`, `S`, `CHC`), e
    cercando una lettera sola uscivano 254 lingue invece di trenta: il
    simbolo e' fatto di lettere, e una lettera sola dentro `CHC` o `CNS`
    contiene quasi tutte le lingue cinesi e altre ancora.  Il campo e'
    scritto da una persona che cerca il nome di una lingua, e il simbolo e'
    il codice del server: cercarlo aggiungeva rumore senza aggiungere una
    lingua che si potesse scegliere.

    Il simbolo serve, ma in un posto solo: `da_simbolo()` e `da_numero()`, che
    lo chiedono sapendo gia' di quale lingua si tratta.
    """
    ago = (testo or "").strip().lower()
    if not ago:
        return ordinate(lingue())
    trovate = []
    for voce in lingue():
        campi = (voce.get("nome"), voce.get("nome_vernacolare"))
        if any(ago in str(campo or "").lower() for campo in campi):
            trovate.append(voce)
    return ordinate(trovate)


def ordinate(elenco: list[dict]) -> list[dict]:
    """Dalle più pubblicazioni alle meno.  A parità, per nome."""
    def chiave(voce: dict):
        return (-int(voce.get("pubblicazioni") or 0), titolo(voce).lower())
    return sorted(elenco, key=chiave)


def corrente_id() -> int:
    """Il numero della lingua scelta.  Italiano se non c'e' scelta.

    Non viene letto da un file a ogni chiamata, e qui si vede come.

    `_scelta` la rimpiazzava `salva()`, quindi chi non cambiava la lingua non
    entrava mai in quel ramo: il valore finiva per essere letto da `_campo_salvato`
    — che chiama `tema.impostazioni()`, e quello il file lo apre e lo parsava —
    **a ogni chiamata**.  Il commento diceva il contrario del codice, che e' il
    modo peggiore in cui un difetto possa starsene buono: la riga giusta accanto
    a quella che non lo e'.

    La domanda e' chi chiama `corrente_id()`.  Non sono gli impostatori: e'
    `MediaView`, una volta per ogni card che costruisce, per sapere in che lingua
    mettere la riga sotto il titolo.  Con 300 card erano 300 letture del file
    delle impostazioni per rivedere la stessa griglia.

    Quindi qui si scrive `_scelta` anche quando si legge, e da quel momento il
    file non viene piu' toccato finche' la lingua non cambia — ed e' `salva()`,
    che la cambia davvero, a rimettere tutto a posto.
    """
    global _scelta
    if _scelta is not None:
        return _scelta
    salvato = _campo_salvato()
    _scelta = salvato if salvato is not None else PREDEFINITA
    return _scelta


def corrente_voce() -> dict | None:
    """La voce della lingua scelta, o None se il file delle lingue manca."""
    return per_id(corrente_id())


def corrente_simbolo() -> str:
    """Il simbolo della lingua scelta.  Quello che vuole il server."""
    return da_numero(corrente_id())


# ----------------------------------------------------------------------
# LA LINGUA DELLA BIBBIA, E LE LINGUE PREFERITE
# ----------------------------------------------------------------------
#
# La Bibbia puo' stare in una lingua diversa da quella dell'app: si cambia dal
# menu della Bibbia senza toccare il resto.  Senza una scelta propria segue la
# lingua dell'app.

CAMPO_BIBBIA = "lingua_bibbia"
CAMPO_PREFERITE = "lingue_bibbia_preferite"


def bibbia_id() -> int:
    """Il numero della lingua della Bibbia (quella dell'app se non scelta)."""
    from Utility import tema
    try:
        numero = int(tema.impostazioni().get(CAMPO_BIBBIA))
    except (TypeError, ValueError):
        return corrente_id()
    return numero if per_id(numero) is not None else corrente_id()


def bibbia_simbolo() -> str:
    return da_numero(bibbia_id())


def bibbia_voce() -> dict | None:
    return per_id(bibbia_id())


def imposta_bibbia(numero) -> bool:
    """Sceglie la lingua della Bibbia.  True se e' cambiata."""
    from Utility import tema
    voce = per_id(numero)
    if voce is None or voce["id"] == bibbia_id():
        return False
    tema.salva_impostazione(CAMPO_BIBBIA, voce["id"])
    return True


def preferite() -> list[str]:
    """I simboli delle lingue preferite per la Bibbia."""
    from Utility import tema
    elenco = tema.impostazioni().get(CAMPO_PREFERITE)
    return [str(x) for x in elenco] if isinstance(elenco, list) else []


def alterna_preferita(simbolo: str) -> None:
    from Utility import tema
    elenco = preferite()
    if simbolo in elenco:
        elenco.remove(simbolo)
    else:
        elenco.append(simbolo)
    tema.salva_impostazione(CAMPO_PREFERITE, elenco)


def _campo_salvato() -> int | None:
    """Il numero salvato nel file, o None se non c'e' o non e' una lingua."""
    from Utility import tema
    grezzo = tema.impostazioni().get(CAMPO_LINGUA)
    if grezzo is None:
        return None
    try:
        numero = int(grezzo)
    except (TypeError, ValueError):
        return None
    # Una lingua salvata che il catalogo non ha piu' non viene accettata:
    # ripartire da quella lascerebbe la finestra con una lista vuota senza
    # dire niente.  Si torna all'italiano, che c'e' sicuramente.
    return numero if per_id(numero) is not None else None


def imposta(numero) -> bool:
    """Cambia la lingua.  True se e' cambiata davvero.

    Il valore viene tenuto in memoria e scritto nel file delle impostazioni,
    che e' la stessa cartella del tema ma un campo diverso: cambiar la lingua
    non tocca il tema e cambiare il tema non tocca la lingua.

    Un numero che non e' nel catalogo viene rifiutato e non scritto: e' quasi
    sempre un refuso, e scriverlo lascerebbe il programma senza lingue al
    riavvio successivo.
    """
    global _scelta
    voce = per_id(numero)
    if voce is None:
        print(f"Lingua sconosciuta: {numero!r} ⚠️")
        return False
    if _scelta == voce["id"]:
        return False
    _scelta = voce["id"]
    from Utility import tema
    tema.salva_impostazione(CAMPO_LINGUA, voce["id"])
    return True


def simboli() -> list[str]:
    """Tutti i simboli, per chi li usa come lista di ricerca."""
    return [str(voce.get("simbolo")) for voce in lingue()]


def _prova() -> None:
    """Le prove di questo file, senza Qt e senza rete.

        python3 Utility/Lingua.py
    """
    elenco = lingue()
    print(f"lingue nel file: {len(elenco)}")
    for voce in elenco[:6]:
        print(f"  {voce['id']:4}  {voce['simbolo']:4}  {titolo(voce):24} "
              f"{voce.get('pubblicazioni', 0)} pubblicazioni")

    print("\ntraduzioni:")
    for numero in (0, 4, 1, 999):
        print(f"  numero {numero:4} -> simbolo {da_numero(numero)!r}")
    for simbolo in ("E", "I", "S", "XX"):
        print(f"  simbolo {simbolo:4} -> numero  {da_simbolo(simbolo)}")

    print(f"\nlingua corrente: {corrente_id()} = {corrente_simbolo()} "
          f"({titolo(corrente_voce()) or 'nome assente'})")
    print("ricerca 'port':", [titolo(v) for v in cerca("port")])
    print("ricerca 'spa':", [titolo(v) for v in cerca("spa")])


if __name__ == "__main__":
    _prova()