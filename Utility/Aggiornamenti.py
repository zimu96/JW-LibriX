#
#  Aggiornamenti.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Cosa c'e' di nuovo sul server, e cosa ti manca gia'.

CHE DOMANDA FA
---------------
Tre domande, e sono tre diverse:

    il catalogo e' vecchio?      CatalogDb  dice quando e' stato fatto
    un pacchetto e' cambiato?    il checksum del server dice se e' diverso
    manca qualche pacchetto?     quello che ho e quello che c''e sul server

La terza e' quella che l'utente sente di piu': non "c'e' una novita'" ma
"posso scaricare quello che mi serve".

PERCHE' IL CATALOGO NON BASTA
-----------------------------
Il catalogo dice QUALI pubblicazioni esistono, ma non dice se quelle che
hai gia' sono ancora le piu' recenti.  Per saperlo bisogna chiedere al
server il checksum di ogni pacchetto installato, e sono poche decine di
richieste: si fanno in background, una per volta, e non si bloccano la
finestra.

LA RISPOSTA DEL SERVER E' IL CHECKSUM
-------------------------------------
Ogni voce che manda il server ha un ``checksum``: l'MD5 del file.  Se il
checksum di un pacchetto che hai gia' e' diverso da quello di adesso,
quel pacchetto e' cambiato e va riscaricato.  Non c'e' un modo piu'
economico di saperlo, e non c'e' bisogno di confrontare i byte: il checksum
e' la risposta gia' calcolata.

PERCHE' IL FILE DEGLI AGGIORNAMENTI
----------------------------------
Il risultato si scrive in un file.  Serve a tre cose:

    la Home puo' mostrarlo subito, senza aspettare la rete
    l'utente non vede due volte la stessa notizia
    se la rete non c'e', l'ultima cosa nota resta scritta

E' un file solo, e non si cancella a vicenda a nessun'altra impostazione:
l'unica cosa che c'e' dentro e' "quando ho guardato e cosa ho trovato".
"""

import json
import time

from Utility import MepsAPI

FILE_AGGIORNAMENTI = "aggiornamenti.json"
#: Il nome della versione di catalogo che ho sul disco.  Un file suo, per il
#: motivo che c'e' scritto in `catalogo_registrato`.
FILE_VERSIONE_CATALOGO = "catalogo_versione.json"
#: Timestamp dell'ultimo aggiornamento catalogo riuscito (per SettingsView)
FILE_ULTIMO_AGGIORNAMENTO = "ultimo_aggiornamento.json"
#: quanto tempo un controllo resta valido.  Un'ora: abbastanza da non
#: chiedere a ogni apertura, poco da mostrare notizie vecchie.
VALE_PER = 3600


def _percorso():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / FILE_AGGIORNAMENTI


def leggi() -> dict:
    """L'ultimo controllo, o uno vuoto."""
    vuoto = {"quando": 0, "catalogo_vecchio": False,
             "aggiornati": [], "mancanti": [], "controllato": False}
    try:
        percorso = _percorso()
        if not percorso.is_file():
            return vuoto
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        if isinstance(dati, dict):
            vuoto.update(dati)
    except (OSError, ValueError):
        pass
    return vuoto


def scrivi(dati: dict) -> None:
    try:
        percorso = _percorso()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a scrivere gli aggiornamenti ⚠️  {errore}")


def scaduto() -> bool:
    """L'ultimo controllo e' vecchio, o non c'e' mai stato."""
    quando = leggi().get("quando") or 0
    return (time.time() - quando) > VALE_PER


# ---------------------------------------------------------------------------
# IL CATALOGO
# ---------------------------------------------------------------------------
#
# IL CATALOGO ERA UNA VOLTA E SOLO UNA, E ADESSO SI AGGIORNA
# -------------------------------------------------------
# Il catalogo non e' dentro nessun pacchetto: e' l'elenco di tutto quello che
# si puo' scaricare.  Quindi se non si aggiorna, l'applicazione non vede le
# pubblicazioni nuove: restano quelle di quando e' stato scaricato, e non c'e'
# nessun difetto da cui accorgersene.  Una pubblicazione appena uscita sem-
# plicemente non c'e'.
#
# IL DIFETTO CHE C'ERA, E DOVE STAVA
# ---------------------------------
# Il download passava da `FileDownloader.load_file_async`, e li' c'e' una
# riga che va letta prima di usare quella strada:
#
#     if destination.exists():
#         print(f"Il file esista gia' [{destination}]")
#         completion(str(destination), None)
#         return
#
# Il nome del file che arriva dal server e' sempre `catalog.db.gz`, quindi
# se il catalogo c'e' gia' — e c'e' quasi sempre — quella riga dice "sono
# gia' fatto" e non scarica niente.  Il programma non lo sapeva e scriveva
# "File salvato": sembrava un aggiornamento, era un no-op.  Il risultato e'
# che il catalogo non e' mai stato aggiornato da quando esiste, e per questo
# il messaggio "il catalogo da aggiornare" stava lì per sempre: non era un
# promemoria, era la verita'.
#
# PERCHE' QUI NON SI RIESA `load_file_async`
# ------------------------------------------
# Perche' quella funzione scarica sopra il file di destinazione e non lascia
# un posto dove mettere un download in prova.  E il catalogo e' l'unico file
# senza il quale il programma non puo' funzionare: se il download si ferma a
# meta' e il file di prima e' gia' stato sovrascritto, non c'e' piu' niente
# da cui ripartire.
#
# Qui si fa quindi in tre tempi: il download va in un file con un altro
# nome, si controlla che il database si apra, e solo allora quello nuovo
# sostituisce il vecchio.  Se qualcosa va storto, il catalogo di prima e'
# ancora li e il programma funziona.
#
# LA VERSIONE
# ------------
# Il server non ha un numero di versione del catalogo: ha un nome.  Il
# manifest dice `current`, e quel nome e' la versione.  La si ricorda nel
# file degli aggiornamenti quando si scarica, cosi' la prossima volta si
# confronta quella con quella e, se sono uguali, non si chiede altro.

#: Quanto il nostro catalogo deve essere piu' vecchio di quello del server,
#: in secondi, prima di dire che c'e' qualcosa di nuovo.
#:
#: Un'ora, non zero.  Le due date vengono da due posti diversi — l'orario
#: del server e l'orologio di questa macchina — e se i due non sono d'accordo
#: sullo stesso istante un rafforzamento di qualche secondo fa riscaricare
#: 58 megabyte ogni volta che si apre il programma.
TOLLERANZA_CATALOGO = 3600


def _file_catalogo():
    """Il percorso di `catalog.db`, o None se non c'e'.

    None e non un percorso: senza catalogo non c'e' niente da confrontare, e
    la chiamata va saltata invece di rispondere "non so".
    """
    try:
        from Utility.DBManager import CATALOG_DB
        from Utility.Extensions.Ext_FileManager import get_documents_directory

        percorso = get_documents_directory() / CATALOG_DB
        return percorso if percorso.is_file() else None
    except (ImportError, OSError):
        return None


def _file_versione():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / FILE_VERSIONE_CATALOGO


def _file_ultimo_aggiornamento():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / FILE_ULTIMO_AGGIORNAMENTO


def _leggi_json(percorso, default=None):
    """Legge un file JSON, ritorna default se non esiste o è invalido."""
    try:
        if percorso.is_file():
            import json
            return json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return default


def _scrivi_json(percorso, dati: dict) -> None:
    """Scrive un dizionario come JSON formattato."""
    try:
        import json
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a scrivere {percorso.name} ⚠️  {errore}")


def registra_aggiornamento_catalogo() -> None:
    """Scrive il timestamp dell'ultimo aggiornamento catalogo riuscito.
    
    Va chiamato DOPO che il catalogo nuovo e' stato messo al posto di quello
    vecchio (vedi `catalogo_messo_a_giorno`)."""
    try:
        percorso = _file_ultimo_aggiornamento()
        _scrivi_json(percorso, {
            "ultimo_aggiornamento": time.time(),
            "versione_catalogo": catalogo_registrato()
        })
    except Exception as errore:
        print(f"Non riesco a registrare l'ultimo aggiornamento ⚠️  {errore}")


def _file_ultimo_aggiornamento_vecchio():
    """Vecchio percorso: 'ultimo-aggiornamento' (senza .txt, con trattino).
    
    Usato prima della migrazione a 'ultimo_aggiornamento.json'."""
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / "ultimo-aggiornamento"


def _file_catalogo_versione_vecchio():
    """Vecchio percorso: 'catalogo_versione.txt'."""
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / "catalogo_versione.txt"


def leggi_ultimo_aggiornamento() -> str:
    """L'ultimo aggiornamento del catalogo, formattato per SettingsView.
    
    Controlla il file JSON nuovo, poi migra dai vecchi txt se esistono.
    
    :return: data formattata 'gg/mm/aaaa' o 'mai' se mai aggiornato."""
    # 1. Nuovo file JSON (ultimo_aggiornamento.json)
    try:
        percorso = _file_ultimo_aggiornamento()
        dati = _leggi_json(percorso)
        if dati and "ultimo_aggiornamento" in dati:
            return time.strftime("%d/%m/%Y", time.localtime(float(dati["ultimo_aggiornamento"])))
    except (OSError, ValueError, TypeError):
        pass

    # 2. Migrazione dal vecchio file txt (ultimo-aggiornamento)
    try:
        vecchio = _file_ultimo_aggiornamento_vecchio()
        if vecchio.is_file():
            quando = vecchio.read_text(encoding="utf-8").strip()
            # Scrive nel nuovo formato JSON per le prossime volte
            registra_aggiornamento_catalogo()
            # Rimuove il vecchio
            try:
                vecchio.unlink()
            except OSError:
                pass
            return time.strftime("%d/%m/%Y", time.localtime(float(quando)))
    except (OSError, ValueError):
        pass

    return "mai"


def catalogo_registrato() -> str:
    """Il nome della versione di catalogo che ho sul disco, o "".

    Vuota quando non lo sappiamo: il file non c'e' fino alla prima volta che
    si scarica un catalogo da qui.  Non e' un errore, e' semplicemente una
    cosa che non sappiamo ancora: `catalogo_vecchio` in quel caso chiede al
    server e decide con la data.

    IL PERCHE' UN FILE SUO E NON UNA RIGA IN `aggiornamenti.json`
    -----------------------------------------------------------
    Perche' quel file lo scrive anche il controllo delle pubblicazioni, e lo
    riscrive per intero con il risultato di quel controllo.  Il pulsante di
    aggiornamento fa partire **entrambi** i controlli insieme, e quello delle
    pubblicazioni finisce dopo: quando scrive, la riga con la versione del
    catalogo sparisce, e il programma si ritrova a non sapere quale ha
    scaricato neppure mentre ce l'ha davanti.

    Misurato: con la versione in quel file, il pulsante scaricava il
    catalogo, lo sostituiva, e un secondo dopo non sapeva piu' di averlo
    fatto.  Due scrittori e un file solo e' il modo tipico di perdersi
    qualcosa per strada, quindi la versione sta nel file suo.

    ORA IN FORMATO JSON (catalogo_versione.json).
    """
    # 1. Nuovo file JSON
    try:
        percorso = _file_versione()
        dati = _leggi_json(percorso)
        if dati and "versione" in dati:
            return str(dati["versione"]).strip()
    except (OSError, ValueError, TypeError):
        pass

    # 2. Migrazione dal vecchio file txt (catalogo_versione.txt)
    try:
        vecchio = _file_catalogo_versione_vecchio()
        if vecchio.is_file():
            versione = vecchio.read_text(encoding="utf-8").strip()
            if versione:
                # Scrive nel nuovo formato JSON
                _scrivi_json(_file_versione(), {"versione": versione})
                try:
                    vecchio.unlink()
                except OSError:
                    pass
                return versione
    except (OSError, ValueError):
        pass

    return ""


def _ricorda_catalogo(versione: str) -> None:
    """Scrive la versione del catalogo che adesso c'e' sul disco (formato JSON)."""
    try:
        _scrivi_json(_file_versione(), {"versione": versione})
    except Exception as errore:
        print(f"Non riesco a ricordare la versione del catalogo ⚠️  {errore}")


def catalogo_messo_a_giorno() -> None:
    """Dice al file degli aggiornamenti che il catalogo e' quello giusto.

    Senza questo la scritta «il catalogo da aggiornare» resta nella Home
    anche dopo aver scaricato il catalogo nuovo: quel file tiene l'ultimo
    controllo, e l'ultimo controllo e' precedente al download.  Sarebbe
    falso — e una scritta falsa che resta li' e' la prima cosa in cui
    l'utente smette di credere a tutto il resto.

    Si scrive solo il campo del catalogo: `scrivi` riceve il file gia' letto
    e ritoccato, quindi gli aggiornamenti delle pubblicazioni non vengono
    persi.
    """
    dati = leggi()
    dati["catalogo_vecchio"] = False
    scrivi(dati)
    # Registra il timestamp per la SettingsView ("Ultimo aggiornamento")
    registra_aggiornamento_catalogo()


def _data_sul_server(versione: str) -> float:
    """Quando il server ha scritto quella versione.  0 se non si sa.

    E' una richiesta `HEAD`: stessa risposta, nessun corpo.  Un `GET` del
    catalogo per sapere se e' vecchio scaricherebbe 58 megabyte per dare una
    risposta che era in una testata.
    """
    import urllib.request
    from email.utils import parsedate_to_datetime

    try:
        from Utility.Stuff import CATALOG_BASE

        url = CATALOG_BASE + versione + "/catalog.db.gz"
        richiesta = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(richiesta, timeout=20) as risposta:
            quando = risposta.headers.get("Last-Modified", "")
        if not quando:
            return 0.0
        return parsedate_to_datetime(quando).timestamp()
    except Exception:  # noqa: BLE001 - una rete che non risponde non e' un errore
        return 0.0


def catalogo_vecchio() -> bool:
    """Sul server c'e' un catalogo piu' nuovo di quello che ho?

    **Blocca**: fa due richieste al server.  Va chiamata da un thread
    secondario, non dal main thread — dal main thread la finestra resta
    ferma per un paio di secondi e sembra piantata.

    IL PERCHE' DELLA DOMANDA E' CAMBIATO
    ------------------------------------
    Prima guardava solo l'eta' del file e diceva "vecchio" dopo 24 ore, e il
    programma non lo aggiornava mai: quindi la risposta era sempre "vecchio"
    e la scritta "il catalogo da aggiornare" non andava via mai.  Ora la
    domanda e' una sola e vera: se ne esiste uno piu' recente, e se ne
    risponde di no la scritta sparisce.

    IL PERCHE' SI GUARDA LA DATA E NON BASTA IL NOME
    ------------------------------------------------
    Il nome della versione cambia ogni volta che il catalogo viene
    ricostruito sul server, e quello non vuol dire che sia cambiato
    qualcosa: puo' essere la stessa identica lista di pubblicazioni rimessa
    a posto.  Prendere 58 megabyte per quello sarebbe spreco.  Quindi il nome
    dice "c'e' qualcosa di diverso", e la data dice se e' qualcosa di
    diverso *che ci serve*.
    """
    percorso = _file_catalogo()
    if percorso is None:
        # Non c'e' nessun catalogo: questo si puo' dire anche senza rete,
        # ed e' l'unico caso in cui la risposta e' "si'" senza aver chiesto
        # niente al server.
        return True

    from Utility.Stuff import Stuff

    versione = Stuff.get_manifest()
    if not versione:
        # La rete non risponde.  Non si dice "da aggiornare": si direbbe
        # una cosa che non si sa, e resterebbe li' anche se non ci fosse
        # niente da aggiornare.
        return False

    if versione == catalogo_registrato():
        # E' esattamente quello che ho scaricato l'ultima volta: due
        # richieste in tutto e non si guarda manco la data.
        return False

    quando_sul_server = _data_sul_server(versione)
    if quando_sul_server <= 0:
        # Il nome e' diverso ma la data non si sa piu': non si puo' dire che
        # quello di adesso e' piu' vecchio, quindi si prende quello che c'e'.
        return True
    try:
        return quando_sul_server > percorso.stat().st_mtime + TOLLERANZA_CATALOGO
    except OSError:
        return True


def scarica_catalogo(completion=None, on_progress=None) -> None:
    """Prende il catalogo nuovo e mette quello vecchio al suo posto.

    Non blocca e non ferma niente: il download va in un thread, e quando
    arriva `completion(versione, errore)` viene chiamata sul main thread
    come in `FileDownloader.load_file_async`.  Se c'e' `on_progress`, viene
    chiamata sul main thread con `(scritti, totale)`, e serve per la riga
    sottile che mostra che il programma non e' fermo: 58 megabyte senza
    nessun segnale sembrano un programma piantato.

    I TRE TEMPI
    -----------
    Il manifest per primo, perche' il nome della versione sta li' e senza
    quello non si sa cosa scaricare.  Poi il download in un file accanto,
    col nome `catalog.nuovo`, che nessuno andra' a cercare.  Poi il
    controllo: si apre e si fa una domanda, e solo se la risposta arriva il
    nuovo prende il posto del vecchio.

    PERCHE' IL VECCHIO NON VIENE CANCELLATO PRIMA
    ---------------------------------------------
    Perche' il catalogo e' l'unico file senza il quale il programma non
    funziona, e un download puo' fermarsi a meta' per un motivo qualunque:
    la rete cade, la connessione si chiude, il programma viene chiuso.  Se
    il posto del vecchio e' gia' libero, in tutti quei casi il programma si
    ritrova senza catalogo e la sezione Pubblicazioni diventa inutilizzabile.
    Cosi' invece, o il nuovo c'e' ed e' buono, o il vecchio e' ancora intatto
    e nessuno se ne accorge.
    """
    import gzip
    import sqlite3

    from Utility.Extensions.Ext_DispatchQueue import background, on_main
    from Utility.FileDownloader import FileDownloader
    from Utility.Stuff import CATALOG_BASE, Stuff

    # Il risultato passa dal thread di lavoro a quello che ascolta dentro
    # `background`: la sua `completion` viene chiamata senza argomenti, e
    # dentro `Ext_DispatchQueue` c'e' `func()` — quindi non le si puo'
    # passare niente.  Una lista risolve, perche' fra le due c'e' un
    # segnale, e quando parte la callback il lavoro e' finito.
    esito: dict = {"versione": "", "errore": ""}

    def progresso(scritti: int, totale: int) -> None:
        """L'avanzamento arriva dal thread di lavoro e va al main thread."""
        if on_progress is not None:
            on_main(lambda: on_progress(scritti, totale))

    def lavoro() -> None:
        versione = Stuff.get_manifest()
        if not versione:
            esito["errore"] = "non raggiungo il server del catalogo"
            return
        esito["versione"] = versione

        percorso = _file_catalogo()
        if percorso is None:
            # Nessun catalogo: e' il primo, e va messo dove `_file_catalogo`
            # lo cerchera'.  Prima qui si rispondeva «c'e' il catalogo da
            # scaricare» e si usciva, quindi con la cartella dati vuota ne' la
            # schermata di avvio ne' il tasto Aggiorna potevano mai prenderlo.
            from Utility.DBManager import CATALOG_DB
            from Utility.Extensions.Ext_FileManager import get_documents_directory
            percorso = get_documents_directory() / CATALOG_DB
            percorso.parent.mkdir(parents=True, exist_ok=True)
        nuovo = percorso.with_name("catalog.nuovo")

        dati = FileDownloader._scarica(CATALOG_BASE + versione + "/catalog.db.gz",
                                        progresso)
        if dati is None:
            nuovo.unlink(missing_ok=True)
            esito["errore"] = "download interrotto"
            return
        try:
            nuovo.write_bytes(gzip.decompress(dati))
        except (OSError, EOFError, gzip.BadGzipFile):
            nuovo.unlink(missing_ok=True)
            esito["errore"] = "catalogo compresso illeggibile"
            return

        # IL CONTROLLO PRIMA DI SOSTITUIRE
        # --------------------------------
        # Un database che si apre e' una condizione necessaria e non
        # sufficiente: vuol dire che il file e' un database e non un pezzo a
        # meta'.  Se il download si interrompe, il file e' troncato e SQLite
        # lo dice subito — e a quel punto il vecchio resta li' al suo posto.
        #
        # Perche' la domanda e' su Publication e non un `SELECT 1` a caso:
        # `SELECT 1` funziona anche su un database che si apre e non
        # contiene niente, che e' esattamente il file che non si deve mettere
        # al posto del catalogo.  E la lingua 1 non e' scelta a caso: e'
        # l'inglese, quello che c'e' in ogni catalogo.
        try:
            connessione = sqlite3.connect(f"file:{nuovo}?mode=ro", uri=True)
            try:
                connessione.execute(
                    "SELECT COUNT(*) FROM Publication WHERE MepsLanguageId = 1"
                ).fetchone()
            finally:
                connessione.close()
        except sqlite3.Error as errore:
            nuovo.unlink(missing_ok=True)
            esito["errore"] = f"il catalogo nuovo non si apre ({errore})"
            return

        try:
            nuovo.replace(percorso)
        except OSError as errore:
            nuovo.unlink(missing_ok=True)
            esito["errore"] = f"non riesco a mettere il catalogo nuovo ({errore})"
            return
        _ricorda_catalogo(versione)
        catalogo_messo_a_giorno()

    def finito() -> None:
        if completion is not None:
            completion(esito["versione"], esito["errore"])

    background(lavoro, completion=finito)
    return None


# ---------------------------------------------------------------------------
# AUTOMATICI O MANUALI
# ---------------------------------------------------------------------------
#
# LA SCELTA E' DELL'UTENTE E IL PREDEFINITO E' MANUALE
# -----------------------------------------------------
# Il file delle impostazioni e' lo stesso degli altri campi, e si cambia
# un campo solo: cosi' mettere i download manuali non cancella il tema.
#
# Perche' il predefinito e' manuale: il download automatico su una linea
# che non regge lascia file parziali, e l'utente non ha chiesto di
# consumare traffico.  Chi vuole l'automatico lo sceglie, e allora e'
# lui che l'ha voluto.

FILE_IMPOSTAZIONI = "impostazioni.json"


def _file_impostazioni():
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / FILE_IMPOSTAZIONI


def automatici() -> bool:
    """L'utente ha chiesto i controlli automatici?

    Il predefinito e' NO.  ``bool(dati.get(...))`` su una chiave che non
    c'e' dà False, e non si deve scrivere ``"no"`` che in Python è
    vero: una stringa vuota e' vera e un Flag unchecked diventa checked.
    """
    # OFFLINE FINO ALLA SCELTA DELLA CARTELLA DATI
    # --------------------------------------------
    # Al primissimo avvio, finche' l'utente non ha risposto a «Dove salvo i
    # dati?», l'app non va in rete: tutto quello che scaricherebbe finirebbe
    # nella cartella sbagliata.  Non si scrive nelle impostazioni: vale solo
    # fino alla risposta, e poi l'app si riavvia con le sue impostazioni vere.
    from Utility.Structures import Paths as modulo_paths
    if modulo_paths.da_chiedere():
        return False
    try:
        percorso = _file_impostazioni()
        if not percorso.is_file():
            return False
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return bool(dati.get("aggiornamenti_automatici", False))
    except (OSError, ValueError):
        return False


def salva_automatici(vuole: bool) -> None:
    """Scrive la scelta, cambiando un campo solo del file."""
    try:
        percorso = _file_impostazioni()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        dati = {}
        if percorso.is_file():
            try:
                dati = json.loads(percorso.read_text(encoding="utf-8"))
            except ValueError:
                dati = {}
        dati["aggiornamenti_automatici"] = bool(vuole)
        percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a salvare la scelta ⚠️  {errore}")


def _pubblicazioni_installate() -> list:
    """I pacchetti che ci sono gia' sul disco.

    Non si legge il database del catalogo per questo: quello elenca tutto,
    e a noi servono solo quelli che l'utente ha gia' scaricato.  Il nome
    della cartella contiene la sigla, la lingua e l'anno: da li si risale
    alla riga del catalogo.
    """
    from Utility.Extensions.Ext_FileManager import extracted_jwpub_exist, get_documents_directory

    installate = []
    try:
        radice = get_documents_directory()
        for cartella in radice.iterdir():
            if not cartella.is_dir():
                continue
            if not extracted_jwpub_exist(url=cartella):
                continue
            # il nome e' chiaveLinguaAnno, per esempio nwtsty_I_2021
            parti = cartella.name.rsplit("_", 2)
            if len(parti) < 2:
                continue
            sigla, lingua = parti[0], parti[1]
            anno = parti[2] if len(parti) == 3 else "0"
            installate.append((sigla, lingua, anno))
    except OSError:
        pass
    return installate


# ---------------------------------------------------------------------------
# LE NOVITA' DEL CATALOGO
# ---------------------------------------------------------------------------
#
# IL CATALOGO HA GIA' LE NOTIZIE, SCRITTE DA CHI LE HA MESSE NEL CATALOGO
# ----------------------------------------------------------------------
# Il catalogo non e' solo un elenco di pubblicazioni: ha anche la tabella
# `CuratedAsset`, che e' la lista delle cose che qualcuno ha deciso di
# mettere in vetrina.  Sono le sezioni curate dell'applicazione originale:
# quello che si vede nella schermata iniziale sotto il nome «Novita'».
#
# IL NUMERO E' UN NUMERO, E NON UN NOME
# --------------------------------------
# `CuratedAsset.ListType` e' un intero, e non c'e' nessuna tabella che dica
# quale numero sia cosa.  Sono tre, e la lettura e' stata fatta guardando
# cosa c'e' dentro:
#
#     0   quattro voci per lingua, le stesse che l'originale mostra in
#         cima alla schermata iniziale
#     1   una voce per lingua
#     2   le voci nuove: i trattati e le pubblicazioni uscite di recente
#
# Il numero 2 e' quello che serve qui, e non e' un'ipotesi: confrontando le
# sue voci con la schermata dell'applicazione originale le voci coincidono
# una a una.  Nell'originale, sotto «What's New», ci sono «Is Living
# Without Pain or Sadness Possible?», «Do All Religions Please God?»,
# «Is Anyone Listening to Our Prayers?» e «How Will God's Kingdom Solve Our
# Problems?»; in italiano le stesse voci sono «Ansia e dolore faranno sempre
# parte della vita?», «Dio approva tutte le religioni?», «Quando preghi,
# c'e' qualcuno che ti ascolta?» e «Cosa farà il Regno di Dio per risolvere
# i nostri problemi?».  Sono le stesse, riga per riga.
#
# PERCHE' NON SI CERCA LA DATA DI USCITA
# --------------------------------------
# Perche' la colonna `GenerallyAvailableDate`, che sarebbe la risposta
# piu' ovvia, e' vuota in tutto il catalogo: zero righe su 320.559.  Provata
# a leggerla, non e' un campo che questo catalogo riempie.  La lista curata
# invece e' piena, e perche' e' lei che l'applicazione originale usa.

#: La lista del catalogo che e' quella delle novita'.  Cosa sia il numero 2 e'
#: spiegato sopra.
LISTA_NOVITA = 2

#: La lista con le pubblicazioni **in evidenza**, cioe' il numero 0.
#:
#: Sono quattro per lingua, e sono le pubblicazioni che l'originale mostra in
#: cima alla schermata iniziale.  In italiano, misurate il 9 ottobre 2026:
#:
#:     sjj    Cantiamo a Geova con gioia
#:     lmd    Ama le persone. Fai discepoli
#:     th     Applicati alla lettura e all'insegnamento
#:     S-38   Istruzioni per l'adunanza Vita cristiana e ministero
#:
#: Sono proprio pezzi da usare per insegnare, ed e' per questo che vanno nella
#: sezione «Kit dell'insegnante» insieme ai video: nell'originale quella sezione
#: non ha solo video, ha anche le pubblicazioni, e il catalogo dei media —
#: dove stanno i video — non le contiene: li ha solo nel catalogo delle
#: pubblicazioni.
LISTA_IN_EVIDENZA = 0

#: Quanti giorni indietro si guarda per dire che una pubblicazione e' «nuova».
#:
#: Trenta.  Non e' un numero scelto a caso e non e' un trucco: un mese e'
#: l'unita' con cui si guarda il mondo, e quello che si vuole sapere guardando
#: la sezione e' «che cosa e' uscito in questo mese».
#:
#: E non serve un numero piu' corto perche' il controllo gira al massimo una
#: volta all'ora: con una finestra di sette giorni una pubblicazione
#: arrivata sabato sparisce di lunedi', e l'utente che guarda la sezione il
#: lunedi' non la vede e non capisce perche'.  Con trenta giorni resta visible
#: per tutto il mese in cui e' uscita, che e' il tempo in cui qualcuno la cerca.
GIORNI_NUOVE = 30


def nuove_nel_catalogo(lingua: str = "I", giorni: int = GIORNI_NUOVE) -> list:
    """Le pubblicazioni entrate nel catalogo negli ultimi `giorni` giorni.

    :return: lista di dizionari ``sigla``, ``lingua``, ``titolo``, ``numero``,
        ``giorno``, ``scaricabile``.

    PERCHE' UNA COLONNA DEL CATALOGO E NON UNA LISTA SCRITTA QUI
    ----------------------------------------------------------
    Perche' la sezione che mostra cosa si puo' scaricare controllava, fino a
    ieri, quattro sigle scritte a mano piu' i periodici letti dal catalogo.
    Quattro sigle scritte a mano sono quattro nomi che non cambiano: quando
    esce una pubblicazione nuova, non e' che ne compare una di quinta, e
    quindi **non si vede**.  Non e' un difetto di qualcosa che si rompe: e'
    una lista che non puo' crescere.

    Il catalogo invece sa tutto quello che esiste, e per ogni riga sa **quando
    e' entrata**: `PublicationAsset.CatalogedOn`.  Quindi la domanda «che cosa
    e' nuovo?» ha una risposta, ed e' scritta dal server.

    LA COLONNA GIUSTA E' L'ULTIMA, NON LA PRIMA
    --------------------------------------------
    Ogni pubblicazione ha piu' righe in `PublicationAsset` — una per formato,
    una per lingua — e ognuna ha la sua data.  Per un libro nuovo tutte le
    righe hanno la stessa data, e la prima e l'ultima coincidono.  Per un
    periodico no: `w` ha 1.620 righe, e la piu' vecchia e' del 2015, quando il
    primo numero e' entrato nel catalogo.  Prendendo la prima data, la Torre
    di Guardia sarebbe «una pubblicazione del 2015» per sempre, e non
    comparirebbe mai fra le novita': e invece ogni mese esce un numero nuovo.
    Prendendo l'ultima si ottiene la data dell'ultimo numero, che e' quello
    che si vuole dire quando si chiede «e' nuovo?».

    MISURATO
    --------
        T-sfr   2025-10-04        una volta sola
        es27    2026-10-03        una volta sola, e la data e' vera
        sjj     2026-10-04        ripubblicata in questi giorni
        ypq     2016-05-02        non e' nuova, e non deve comparire
        w       2015-07-01 .. 2026-09-15    millecinquecento righe, e la
                                          seconda data e' l'ultimo numero

    QUELLE GIA' SCARICATE NON COMPARIRONO
    -------------------------------------
    Una pubblicazione che l'utente ha gia' scaricata non e' una novita' da
    scaricare: e' una novita' che si ha gia'.  Il confronto e' con quello che
    c'e' davvero sul disco, non con quello che il programma ricorda di aver
    scaricato, cosi' la riga non resta neppure se il pacchetto e' stato
    cancellato a mano.
    """
    percorso = _catalogo()
    if percorso is None:
        return []
    try:
        import sqlite3
    except ImportError:
        return []

    # Il taglio: il catalogo scrive le date come `2026-10-01T06:02:18+00:00`,
    # e il confronto e' fra stringhe.  Funziona perche' la parte che conta e'
    # sempre piu' lunga e sempre uguale — l'anno, il mese, il giorno — quindi
    # l'ordinamento delle stringhe e' quello delle date.  Non si converte in
    # numeri perche' non c'e' bisogno e la conversione sbagliere un secondo di
    # qui si vede.
    taglio = time.strftime("%Y-%m-%d", time.localtime(time.time() - giorni * 86400))
    try:
        connessione = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    except (sqlite3.Error, OSError) as errore:
        print(f"Novita': il catalogo non si apre ⚠️  {errore}")
        return []
    try:
        cursore = connessione.execute(
            """SELECT p.KeySymbol, MAX(p.Title), MAX(a.CatalogedOn),
                      MAX(CASE WHEN a.MimeType = 'application/x-jwpub'
                               THEN 1 ELSE 0 END)
                 FROM Publication p
                 JOIN PublicationAsset a ON a.PublicationId = p.Id
                WHERE p.MepsLanguageId = ? AND a.CatalogedOn >= ?
                GROUP BY p.KeySymbol
                ORDER BY 3 DESC""",
            (int_lingua(lingua), taglio))
    except sqlite3.Error as errore:
        print(f"Novita': il catalogo non si legge ⚠️  {errore}")
        connessione.close()
        return []

    # I numeri dei periodici vengono da `periodici()`, che li sa gia' leggere e
    # mette dentro il numero nella forma che vuole il server (`202612`).  Non
    # si rilegge qui: sono due letture della stessa cosa e, se un domani
    # cambia il modo in cui si prende il numero, cambiando un posto solo
    # cambiano tutti e due.
    numeri = {v["sigla"]: v["numero"] for v in periodici(lingua)}
    scaricate = {(s, l) for s, l, _anno in _pubblicazioni_installate()}

    trovate = []
    for sigla, titolo, quando, ha_pacchetto in cursore:
        if not sigla or (sigla, lingua) in scaricate:
            continue
        trovate.append({
            "sigla": sigla,
            "lingua": lingua,
            "titolo": titolo or sigla,
            # Il numero c'e' solo per i periodici, e `periodici()` e' la
            # fonte: senza numero la richiesta al server torna 400 e il
            # download non parte.
            "numero": numeri.get(sigla, ""),
            "giorno": str(quando or "")[:10],
            # Non e' l'indirizzo del pacchetto: quello si chiede al momento
            # di scaricare.  Qui si dice solo se il pacchetto esiste, e lo si
            # dice perche' c'e' una riga in `PublicationAsset` con dentro un
            # .jwpub.  `DownloadedView` e `PubView` scaricano lo stesso
            # pacchetto dallo stesso posto.
            "scaricabile": bool(ha_pacchetto),
        })
    connessione.close()
    return trovate


def novita_recenti(lingua: str = "I", lista: int = LISTA_NOVITA) -> list:
    """Le voci che il catalogo mette fra le novita'.

    :return: lista di dizionari ``sigla``, ``lingua``, ``titolo``, in
        quell'ordine.

    L'ORDINE E' QUELLO DEL CATALOGO
    ------------------------------
    La lista ha una colonna ``SortOrder`` apposta, e l'ordine dei trattati
    nella schermata dell'originale non e' quello alfabetico ne' quello in
    cui sono usciti: e' quello deciso da chi ha fatto la lista.  Riordinarli
    per titolo cambierebbe la sezione senza chiedere il permesso a nessuno.

    IL TITOLO E' QUELLO DEL CATALOGO
    ---------------------------------
    Non si ricostruisce e non si abbrevia: `Publication.Title` e' il nome
    come l'ha scritto il catalogo, che e' l'unico posto dove c'e' la riga
    scritta da qualcuno che conosce la pubblicazione.  Il titolo breve
    (`ShortTitle`) serve per le schede strette, e qui le righe sono larghe.
    """
    percorso = _catalogo()
    if percorso is None:
        return []
    try:
        import sqlite3
    except ImportError:
        return []
    try:
        # `mode=ro`: si legge e non si scrive.  Un catalogo aperto in scrittura
        # crea il file se non c'e', e andare a mostrare le novita' non puo'
        # creare il file che sta leggendo.
        connessione = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    except (sqlite3.Error, OSError) as errore:
        print(f"Novita': il catalogo non si apre ⚠️  {errore}")
        return []
    try:
        # DISTINCT perche' una pubblicazione ha piu' di una riga in
        # `PublicationAsset` — una per ogni lingua e formato — e senza
        # DISTINCT un trattato comparirebbe nella sezione due volte.
        cursore = connessione.execute(
            """SELECT DISTINCT p.KeySymbol, p.Title
                 FROM CuratedAsset c
                 JOIN PublicationAsset a ON a.Id = c.PublicationAssetId
                 JOIN Publication p ON p.Id = a.PublicationId
                WHERE c.ListType = ? AND p.MepsLanguageId = ?
                ORDER BY c.SortOrder""",
            (lista, int_lingua(lingua)))
    except sqlite3.Error as errore:
        print(f"Novita': il catalogo non si legge ⚠️  {errore}")
        connessione.close()
        return []

    trovate = []
    for sigla, titolo in cursore:
        if not sigla:
            continue
        trovate.append({"sigla": sigla, "lingua": lingua,
                        "titolo": titolo or sigla})
    connessione.close()
    return trovate


def titoli_delle(sigle: list, lingua: str = "I") -> dict:
    """I titoli di alcune pubblicazioni, per sigla.

    Serve alla Home per mettere in una sezione un pezzo scelto — per esempio
    il corso e il libro di «Puoi vivere felice per sempre?» — senza scrivere
    il titolo a mano: il titolo e' quello del catalogo, ed e' l'unico posto
    dove c'e' la riga scritta da qualcuno che conosce la pubblicazione.

    Una sigla che non c'e' nel catalogo non viene restituita, e non viene
    inventata: si vede subito che manca, e non un titolo sbagliato.

    :return: ``{sigla: titolo}`` per le sigle trovate, in un solo accesso al
        catalogo: una richiesta per sigla sarebbe 3.741 interrogazioni per
        quello che e' una sola ricerca.
    """
    percorso = _catalogo()
    if percorso is None or not sigle:
        return {}
    try:
        import sqlite3
    except ImportError:
        return {}
    try:
        connessione = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    except (sqlite3.Error, OSError):
        return {}

    trovati: dict = {}
    try:
        for sigla in sigle:
            riga = connessione.execute(
                """SELECT p.Title
                     FROM Publication p
                    WHERE p.MepsLanguageId = ? AND p.KeySymbol = ?
                    LIMIT 1""",
                (int_lingua(lingua), sigla)).fetchone()
            if riga and riga[0]:
                trovati[sigla] = riga[0]
    except sqlite3.Error:
        pass
    finally:
        connessione.close()
    return trovati


def controlla_una_pubblicazione(sigla: str, lingua: str = "I",
                                numero: str | None = None) -> dict:
    """Chiede al server il checksum di una pubblicazione.

    Restituisce un dizionario piccolo, non la risposta intera: la risposta
    di un pacchetto con 165 tracce sono 128 KB e qui non servono.
    """
    esito = {"sigla": sigla, "lingua": lingua, "url": None,
             "checksum": None, "filesize": 0, "cambiato": False}
    numero = _numero_gia_letto(sigla, numero, lingua)
    try:
        voci = MepsAPI.media(sigla, lingua, numero or None)
    except MepsAPI.ErroreMeps as errore:
        esito["errore"] = str(errore)
        return esito

    pacchetto = MepsAPI.scegli(voci, "JWPUB")
    if pacchetto is None:
        esito["errore"] = "nessun pacchetto JWPUB sul server"
        return esito
    esito["url"] = pacchetto["file"].get("url")
    esito["checksum"] = pacchetto["file"].get("checksum")
    esito["filesize"] = pacchetto.get("filesize") or 0
    esito["titolo"] = pacchetto.get("title") or sigla

    # Per un periodico il titolo che arriva dal pacchetto e' la parola
    # "Edizione normale", che non dice niente: due numeri diversi della stessa
    # rivista avrebbero lo stesso titolo e si capirebbe solo dal checksum
    # quale sia.  Qui si mette il nome del numero, che e' il dato vero.
    #
    # MISURATO, E LA RAGIONE PER CUI NON SI COMPONE
    # ----------------------------------------------
    #     w    ->  "La Torre di Guardia, dicembre 2026"
    #     wp   ->  "La Torre di Guardia, n. 1 2026"
    #
    # `wp` esce due volte l'anno e non ha un mese: dal numero 202609 non si
    # ricava "settembre 2026", che e' falso.  Percio' il nome arriva dal
    # catalogo che lo ha scritto, e non da una formula.
    numero = _numero_gia_letto(sigla, numero, lingua)
    if numero:
        esito["numero"] = numero
        nome_numero = _TITOLI_NUMERI.get((sigla, lingua))
        if nome_numero:
            esito["numero_titolo"] = nome_numero
            esito["titolo"] = nome_numero
    return esito


def confronta(sigla: str, lingua: str, checksum_locale: str | None) -> dict:
    """Il pacchetto sul server e' diverso da quello che ho?

    :param checksum_locale: l'MD5 del pacchetto gia' scompattato, se si
        sa.  Se non si sa non si puo' concludere niente, e si dice "non so"
        invece di "cambiato": fra "cambiato" e "non lo so" la differenza e'
        un download inutile, e un download inutile e' fastidioso.
    """
    esito = controlla_una_pubblicazione(sigla, lingua)
    if esito.get("errore"):
        return esito
    if checksum_locale and esito.get("checksum"):
        esito["cambiato"] = checksum_locale.lower() != str(esito["checksum"]).lower()
    return esito


def cosa_c_e_sul_server(sigla: str, lingua: str = "I",
                        numero: str | None = None) -> dict:
    """TUTTO quello che il server ha per una pubblicazione, non solo il testo.

    TRE FAMIGLIE DI FILE, E SI CONFONDONO
    -------------------------------------
    Una sola richiesta al server restituisce tre cose diverse, e vanno
    tenute separate perche' si comportano in modo diverso:

        JWPUB   il pacchetto con il testo.  Si scarica una volta sola e poi
                non si tocca piu'.
        MP3     l'audio.  Ogni traccia e' un file a se', e sono centinaia:
                vanno contati, non scaricati tutti per vedere se sono nuovi.
        video   le risoluzioni.  Il server le dichiara tutte nella risposta,
                con la larghezza, l'altezza e il bitrate: non c'e' bisogno
                di chiedere nulla per sapere se c'e' un video in 4K.

    PERCHE' SI CONTA E NON SI SCARICA
    ---------------------------------
    Per i video e l'audio la domanda sensata non e' "e' cambiato?" ma
    "quanti file ci sono e a che risoluzione?".  Sono informazioni che il
    server da gia' nella risposta, e sono quelle che servono per decidere
    cosa vale la pena scaricare.  Scaricare centinaia di tracce per
    controllare se sono nuove costerebbe piu' che scaricarle.
    """
    esito = {"sigla": sigla, "lingua": lingua, "errore": None,
             "titolo": sigla,
             "pacchetto": None, "audio": 0, "video": 0,
             "risoluzioni": [], "formati": [], "byte": 0, "tracce": 0,
             "esempi_audio": [], "esempi_video": []}
    # Il numero del periodico, se c'e'.  Senza questo `w` da errore 400 dal
    # server: un periodico senza `issue` non si puo' chiedere, e la sezione
    # Novita' mostrerebbe "non riesco a leggere" per un periodico che
    # esiste e si puo' scaricare benissimo.  Vedi `periodici()`.
    numero = _numero_gia_letto(sigla, numero, lingua)
    if numero:
        esito["numero"] = numero
    try:
        voci = MepsAPI.media(sigla, lingua, numero or None)
    except MepsAPI.ErroreMeps as errore:
        esito["errore"] = str(errore)
        return esito

    esito["formati"] = [sigla_formato for sigla_formato, _ in MepsAPI.formati(voci)]
    esito["risoluzioni"] = MepsAPI.risoluzioni(voci)
    esito["tracce"] = len(MepsAPI.per_traccia(voci))

    for voce in voci:
        formato = MepsAPI._formato(voce)
        mime = (voce.get("mimetype") or "").lower()
        ha_video = bool(voce.get("frameWidth") and voce.get("frameHeight"))
        nome = voce.get("title") or voce.get("label") or ""
        if formato == "JWPUB":
            esito["titolo"] = nome or sigla
            # Il nome del numero, quando e' un periodico.  Va dentro `titolo`
            # e non in un campo nuovo perche' la scheda mostra `titolo` e
            # quel nome e' la cosa che distingue "numero di dicembre" da
            # "numero di novembre": due righe con lo stesso titolo e
            # checksum diversi non si distinguono a occhio.
            #
            # Lo prende il catalogo, non una formula: misurato, `wp` si
            # chiama "La Torre di Guardia, n. 1 2026", e da 202609 non si
            # ricava un mese.  Una formula avrebbe scritto "settembre 2026"
            # sopra un numero che si chiama cosi', che e' falso.
            if numero:
                # `periodico` e NON `voce`: il ciclo esterno sta iterando
                # sulle voci del media e si chiama `voce`, e un ciclo
                # interno con lo stesso nome lo sovrascrive.  Dopo il ciclo
                # `voce` e' l'ultimo dizionario dei periodici, che non ha
                # nessun campo `file`, e la riga sotto va in KeyError:
                #
                #     KeyError: 'file'
                #
                # Il sintomo e' che funziona per `ypq` e non per `w`: per
                # le pubblicazioni senza numero il ciclo non parte e la
                # variabile non viene toccata.  Il difetto era quindi
                # invisibile su quattro pubblicazioni su sei, e la parte che
                # si rompeva era proprio quella nuova.
                # Il nome del numero e' gia' noto: viene da `numero`, che il
                # chiamante ha trovato leggendo i periodici una volta sola.
                # Qui non si rilegge il catalogo: sarebbe una seconda query
                # per ogni periodico del controllo, per una riga che il
                # chiamante ha gia' davanti agli occhi.
                esito["numero_titolo"] = _TITOLI_NUMERI.get((sigla, lingua),
                                                            numero)
                # il nome del numero vince su quello del pacchetto, che per
                # un periodico e' la parola "Edizione normale" e non dice
                # niente
                if esito["numero_titolo"]:
                    esito["titolo"] = esito["numero_titolo"]
            esito["pacchetto"] = {"url": voce["file"].get("url"),
                                  "checksum": voce["file"].get("checksum"),
                                  "filesize": voce.get("filesize") or 0}
            esito["byte"] += voce.get("filesize") or 0
        elif ha_video or mime.startswith("video/"):
            esito["video"] += 1
            esito["byte"] += voce.get("filesize") or 0
            if len(esito["esempi_video"]) < 4 and nome:
                esito["esempi_video"].append(nome)
        elif mime.startswith("audio/") or formato in ("MP3", "M4A", "AAC"):
            esito["audio"] += 1
            esito["byte"] += voce.get("filesize") or 0
            if len(esito["esempi_audio"]) < 4 and nome:
                esito["esempi_audio"].append(nome)

    return esito


# ---------------------------------------------------------------------------
# I PERIODICI: QUELLI CHE HANNO UN NUMERO
# ---------------------------------------------------------------------------
#
# PERCHE' NON BASTA UNA LISTA DI SIGLE
# ----------------------------------
# Un periodico non si chiede come le altre pubblicazioni: `pub=w` senza altro
# parametro dà errore 400 dal server.  Va chiesto con `issue`, cioe' con il
# numero del numero.  Quindi per controllare "La Torre di Guardia" bisogna
# prima sapere qual e' l'ultimo numero, e quel numero cambia.
#
# La domanda "qual e' l'ultimo numero" ha una risposta sola, e sta nel
# catalogo: la tabella `Publication` ha una riga per ogni numero di ogni
# periodico, e la piu' alta per `IssueTagNumber` e' l'ultima.
#
# PERCHE' IL NUMERO SI SCRIVE 20261200 E IL SERVER VUOLE 202612
# -----------------------------------------------------------
# Nel catalogo il numero ha otto cifre e finisce con due zeri:
#
#     20261200   "La Torre di Guardia, dicembre 2026"
#
# e al server si chiede `issue=202612`, sei cifre.  Sono lo stesso numero
# scritto in due modi.  Passare il numero del catalogo cosi' com'e' dà 400,
# e il numero del server cosi' com'e' non trova niente nel catalogo: nessuna
# delle due forme va bene per entrambi, e vanno tradotte.
#
# LA SCELTA DEI PERIODICI E' MISURATA
# -----------------------------------
# In italiano il catalogo ha tre sigle di tipo 14, il tipo dei periodici:
#
#     w    ultimo 20261200   La Torre di Guardia, dicembre 2026
#     wp   ultimo 20260900
#     ws   ultimo 20170500   fermo al 2017
#
# `ws` si lascia fuori perche' l'ultimo numero ha nove anni: chiedere un
# numero del 2017 non porta niente e non c'e' nessun caso in cui sia la
# risposta giusta.  Il limite e' scritto, non lasciato al caso, cosi' quando
# un periodico riprende a uscire si vede subito che era fermo.
#
# In ogni caso la lista si rilegge dal catalogo a ogni controllo e non e' una
# lista scritta qui: se domani il sito aggiunge una rivista, arriva da
# sola senza che nessuno debba ricordarsi di aggiungerla.

#: I periodici fermi da piu' di tanti anni non si controllano.  Otto anni: il
#: piu' vecchio e' il 2017, e oltre non c'e' niente da chiedere.
ANNI_FERMO = 8

#: La tabella dei periodici e' la 14.  Scritta qui perche' e' il numero che
#: il catalogo usa e che non si può dedurre da nient'altro.
TIPO_PERIODICO = 14


def _catalogo() -> Path | None:
    """Il percorso di `catalog.db`, o None se non c'e'.

    `None` e non un percorso: senza catalogo non si puo' sapere qual e'
    l'ultimo numero di un periodico, e la chiamata va saltata.  Provare a
    chiedere `issue=` con un numero inventato produrrebbe un errore 400 che
    sembrerebbe il server rotto.
    """
    try:
        from Utility.DBManager import CATALOG_DB
        from Utility.Extensions.Ext_FileManager import get_documents_directory

        percorso = get_documents_directory() / CATALOG_DB
        return percorso if percorso.is_file() else None
    except (ImportError, OSError):
        return None


def periodici(lingua: str = "I") -> list:
    """I periodici che si controllano, con l'ultimo numero di oggi.

    :return: lista di dizionari ``sigla``, ``numero``, ``titolo``.

    ``numero`` e' gia' nella forma che vuole il server (``202612``) e
    ``titolo`` e' quello scritto dal catalogo ("La Torre di Guardia,
    dicembre 2026"), che e' l'unica riga che dice **quale** numero e'.

    IL TITOLO VIENE DA UN DATO, NON DA UNA FORMULA
    ----------------------------------------------
    Il nome del numero non e' "numero di dicembre": e' quello che ha scritto
    il catalogo.  Una formula (anno + mese presi dal numero) darebbe
    "dicembre 2026", che e' quasi giusto e non e' quello che c'e' scritto
    sull'annuncio, e su una rivista che non esce ogni mese i due nomi non
    coincidono.
    """
    percorso = _catalogo()
    if percorso is None:
        return []
    try:
        import sqlite3
    except ImportError:
        return []
    try:
        # `mode=ro`: si legge e non si scrive.  Un catalogo aperto in scrittura
        # crea il file se non c'e', e un controllo degli aggiornamenti che
        # crea il file che sta controllando e' una cosa che non deve succedere.
        connessione = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    except (sqlite3.Error, OSError) as errore:
        print(f"Periodici: il catalogo non si apre ⚠️  {errore}")
        return []
    try:
        cursore = connessione.execute(
            """SELECT KeySymbol, MAX(IssueTagNumber), IssueTitle
                 FROM Publication
                WHERE MepsLanguageId = ?
                  AND PublicationTypeId = ?
                  AND Year >= ?
                GROUP BY KeySymbol
                ORDER BY 2 DESC""",
            (int_lingua(lingua), TIPO_PERIODICO, time.localtime().tm_year - ANNI_FERMO))
    except sqlite3.Error as errore:
        print(f"Periodici: il catalogo non si legge ⚠️  {errore}")
        connessione.close()
        return []

    trovati = []
    for sigla, numero, titolo in cursore:
        numero_testo = str(numero or "")
        # otto cifre con due zeri finali -> sei: vedi la spiegazione in cima
        numero_server = numero_testo[:6] if len(numero_testo) == 8 else numero_testo
        trovati.append({
            "sigla": sigla,
            "numero": numero_server,
            "numero_catalogo": numero_testo,
            "titolo": titolo or sigla,
        })
    connessione.close()

    _TITOLI_NUMERI.clear()
    for voce in trovati:
        _TITOLI_NUMERI[(voce["sigla"], lingua)] = voce["titolo"]
    return trovati


def int_lingua(lingua: str = "I") -> int:
    """Il codice lingua del programma come numero del catalogo.

    Accetta due cose: un NUMERO gia' pronto (`"4"`, che era quello che
    passavano i controlli dei pacchetti) o un SIMBOLO (`"I"`).  Il numero si
    prova per primo e passa com'e', senza cercarlo nella tabella: e' gia' un
    numero del catalogo e ripercorrere la tabella per un numero che c'e' gia'
    dentro aggiungerebbe un modo per sbagliare.

    Solo il simbolo passa da `Lingua.da_simbolo()`, che e' l'unico posto dove
    la traduzione e' scritta.  Qui prima c'era `{0: "E", 4: "I"}`, cioe' la
    decima copia dello stesso dizionario di due voci che c'era anche in
    `Copertine`, `Preferiti`, `MediaView` e altrove: con la lingua nuova quel
    dizionario non rispondeva piu' a nulla, perche' le lingue sono 874 e non
    due.
    """
    try:
        return int(lingua)
    except (TypeError, ValueError):
        pass
    from Utility import Lingua
    return Lingua.da_simbolo(lingua)


def da_controllare(lingue: tuple = ("I",)) -> list:
    """Tutto quello che si controlla a ogni avvio: le fisse e i periodici.

    Le pubblicazioni fisse sono quattro e non cambiano.  I periodici si
    rileggono dal catalogo, perche' il numero da chiedere cambia ogni mese e
    una lista scritta a mano smetterebbe di funzionare senza dire niente.

    Si controlla **solo l'ultimo numero** di ogni periodico, non tutti: gli
    altri numeri sono gia' usciti e chi li vuole li trova nella sezione
    Pubblicazioni.  Controllarli tutti sarebbero 1.620 richieste per `w` solo.
    """
    fisse = ("nwtsty", "ypq", "sn", "lff")
    lista: list = []
    for lingua in lingue:
        for sigla in fisse:
            lista.append((sigla, lingua))
        for voce in periodici(lingua):
            lista.append((voce["sigla"], lingua))
    return lista


def numero_di(sigla: str, lingua: str = "I") -> str:
    """L'ultimo numero di un periodico, o "" se non e' un periodico.

    Se il numero e' gia' stato letto si puo' passarlo: `periodici()` apre e
    legge il catalogo, e chiamarla una volta per ogni pubblicazione durante
    un controllo significa aprire il database sei volte per la stessa
    domanda.  Chi controlla tutto legge i periodici una volta e poi passa
    qui i numeri gia' trovati.
    """
    for voce in periodici(lingua):
        if voce["sigla"] == sigla:
            return voce["numero"]
    return ""


#: I titoli dei numeri, per (sigla, lingua).  Li riempie `periodici()` e li
#: usa `cosa_c_e_sul_server`, cosi' il catalogo viene aperto una volta sola
#: per controllo e non una per pubblicazione.
#:
#: E' un dato che cambia, quindi non e' una cache da tenere: si scrive ogni
#: volta che `periodici()` legge davvero il catalogo, e resta indietro solo
#: se la lettura fallisce — nel qual caso il nome manca e la scheda mostra
#: il titolo del pacchetto, che e' comunque vero.
_TITOLI_NUMERI: dict = {}


def _numero_gia_letto(sigla: str, numero: str | None, lingua: str) -> str:
    """Il numero da usare: quello passato, o quello cercato adesso."""
    if numero:
        return numero
    return numero_di(sigla, lingua)


def riassunto() -> str:
    """Una riga per la Home: che novita' ci sono.

    Se non c'e' niente da dire si dice che non c'e' niente.  Una riga che
    promette sempre qualcosa e poi non trova niente fa smettere di leggere
    quella riga, e quando c'e' davvero qualcosa non la si guarda piu'.
    """
    dati = leggi()
    if not dati.get("controllato"):
        return ""
    pezzi = []
    if dati.get("catalogo_vecchio"):
        pezzi.append("il catalogo da aggiornare")
    aggiornati = len(dati.get("aggiornati") or [])
    mancanti = len(dati.get("mancanti") or [])
    if aggiornati:
        pezzi.append(f"{aggiornati} {'aggiornata' if aggiornati == 1 else 'aggiornate'}")
    if mancanti:
        pezzi.append(f"{mancanti} {'disponibile' if mancanti == 1 else 'disponibili'}")
    if not pezzi:
        return "Tutto aggiornato."
    return "Ci sono novita': " + ", ".join(pezzi) + "."

# ---------------------------------------------------------------------------
# CHE COSA TI MANCA DAVVERO
# ---------------------------------------------------------------------------
#
# TRE COSE DA NON CONFONDERE
# --------------------------
# "Non scaricata" e "aggiornata" sembrano la stessa domanda e non lo sono:
#
#   NON SCARICATA   il pacchetto non e' sul disco.  Lo si vede guardando il
#                  disco: la cartella c'e' o non c'e'.  E' un fatto, e lo e'
#                  da subito, senza aspettare niente.
#
#   AGGIORNATA      il pacchetto c'e' ma e' di una versione vecchia.  Per
#                  saperlo serve il checksum di quello che hai, e il tuo non
#                  e' scritto da nessuna parte: il `.jwpub` viene cancellato
#                  dopo la scompatta.
#
#   LO SO DOPO     dall'istante in cui l'app registra il checksum a ogni
#                  scaricamento, il confronto si puo' fare.  Prima di allora
#                  no, e la risposta e' "non lo so", non "cambiato".
#
# FRA "CAMBIATO" E "NON LO SO"
# -----------------------------
# La differenza e' un download da 161 MB.  Diresti che c'e' un aggiornamento
# e non ci sarebbe: peggio che non dirlo.
#
# PERCHE' SI REGISTRA IL CHECKSUM E NON LA DATA
# --------------------------------------------
# La data del file sul server c'e' (`modifiedDatetime`, misurato: 2024-02-03
# per `sn`) e si potrebbe confrontare con la data di scaricamento.  Ma la
# data di scaricamento la conosciamo solo per i pacchetti scaricati da
# questa app: un pacchetto messo a mano col copia e incolla non ce l'ha, e
# dire "e' vecchio" perche' l'hai copiato ieri sarebbe falso.
#
# Il checksum e' diverso: e' una/impronta del contenuto.  Se non lo si
# conosce, non si conclude niente — che e' la cosa giusta.


def _percorso_scaricati() -> Path:
    from Utility.Structures.Paths import Paths

    return Paths.user_data_path / "scaricati.json"


def scaricati_leggi() -> dict:
    """I checksum registrati, o un dizionario vuoto."""
    try:
        percorso = _percorso_scaricati()
        if not percorso.is_file():
            return {}
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError):
        return {}


def scaricati_scrivi(dati: dict) -> None:
    try:
        percorso = _percorso_scaricati()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
    except OSError as errore:
        print(f"Non registro il checksum scaricato ⚠️  {errore}")


def segna_scaricato(sigla: str, lingua: str = "I", checksum: str | None = None,
                     quando: float | None = None) -> None:
    """Segna che questo pacchetto e' adesso sul disco, con questo checksum.

    Va chiamato DOPO che la scompatta e' finita, non prima: prima il pacchetto
    non c'e' ancora, e un download interrotto a meta' lascerebbe scritto che
    l'hai scaricato.

    Un checksum vuoto si registra lo stesso.  Il pacchetto c'e', e questo si
    sa; non si sa solo di che versione e'.  Meglio un record con un buco che
    nessun record: altrimenti la sezione dei scaricati non lo elencerebbe
    come scaricato, e continuerebbe a chiederlo di scaricare.
    """
    chiave = f"{sigla}_{lingua}"
    dati = scaricati_leggi()
    dati[chiave] = {"checksum": (checksum or ""),
                    "quando": quando or time.time()}
    scaricati_scrivi(dati)


def checksum_scaricato(sigla: str, lingua: str = "I") -> str | None:
    """Il checksum registrato di questo pacchetto, o None."""
    record = scaricati_leggi().get(f"{sigla}_{lingua}")
    if not isinstance(record, dict):
        return None
    return record.get("checksum") or None


def _chiave(voce: dict) -> str:
    """La chiave con cui una voce si riconosce fra un controllo e l'altro."""
    return f"{voce.get('sigla', '')}/{voce.get('lingua', '')}"


def spiegazione(voce: dict, prima: dict) -> str:
    """La riga che dice **perche'** questa scheda e' qui.

    PERCHE' UNA FRASE E NON UN ETICHETTA
    -----------------------------------
    Il pulsante dice "Scarica" e il dettaglio dice "122 MB · JWPUB".  Entrambi
    dicono come si scarica, non **perche'** quella scheda e' in elenco: senza
    questa riga una sezione che elenca quattro pubblicazioni e' indistinguibile
    da una sezione che ne elenca quattro perche' sono appena uscite.  Dopo due
    controlli l'utente smette di guardarla, ed e' proprio quando qualcosa e'
    cambiato che deve guardare.

    LE TRE FRASI, E DA DOVE VENGONO
    -------------------------------
    Tre informazioni, e ognuna viene da un fatto:

        NOVITÀ        il checksum del pacchetto e' diverso da quello del
                     controllo precedente.  E' il fatto che dice che il
                     server ha cambiato il file.

        AGGIORNATA    il checksum e' lo stesso ma il titolo e' diverso: il
                     server ha cambiato il titolo senza toccare il testo —
                     una ristampa cambia la copertina e non le pagine.

        (nessuna)     il checksum e' uguale: la scheda era gia' li' al
                     controllo prima e non e' successo niente.  Allora si
                     scrive **niente**, e non "nessuna novita'": una riga
                     che dice che non c'e' niente e' rumore, ed e' rumore in
                     un posto dove l'utente cerca cose nuove.

    LA PRIMA VOLTA NON SI DICE NULLA
    ---------------------------------
    Senza un controllo precedente non c'e' niente da confrontare, e "nuovo"
    richiederebbe di stabilire che una cosa e' nuova rispetto a **qualcosa**.
    Dire "novita'" alla prima apertura sarebbe dire che tutto e' nuovo,
    perchè tutto e' appena stato visto.  La prima volta la sezione dice solo
    che cosa manca, e la parola "novita'" compare dalla seconda.
    """
    if not prima:
        return ""
    vecchia = prima.get(_chiave(voce))
    if not isinstance(vecchia, dict):
        return ""

    mio = ((voce.get("pacchetto") or {}).get("checksum") or "").lower()
    suo = ((vecchia.get("pacchetto") or {}).get("checksum") or "").lower()
    if not mio or not suo or mio == suo:
        # nessun checksum da confrontare: fra "uguale" e "non lo so" la
        # differenza e' un download inutile, quindi si dice niente
        return ""
    return "Nuovo sul server: il file e' cambiato."

