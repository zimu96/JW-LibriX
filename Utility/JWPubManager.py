#
#  JWPubManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""Apre i .jwpub e legge quello che c'e' dentro.

Il formato non e' nostro: e' uno ZIP che contiene un altro ZIP, dentro il
quale c'e' un database SQLite.  Le quattro cose da sapere (COME-FUNZIONA.txt
sezione 2):

  a) SQLite non sa leggere da dentro uno ZIP: per aprire il .db bisogna
     tirarlo fuori.  Qui per il .db non serve, perche' il pacchetto viene
     scompattato tutto e poi si legge il file per esteso.

  b) Non si scompatta tutto per mostrare una figura.  Qui pero' si scompatta
     tutto, ed e' una scelta: tutto il resto dell'app (JWPubManager,
     FileDownloader) lavora su cartelle, non su ZIP.

  c) DocumentId (0, 1, 2) e' locale; MepsDocumentId (1102016770) e' stabile
     ed e' quello della URL su wol.jw.org.  Non si confondono.

  d) Multimedia.FilePath pieno vuol dire che il file e' dentro il pacchetto;
     vuoto vuol dire che e' un video sul CDN e il pacchetto dice quale,
     con KeySymbol e Track.

IL NOME DELLA CARTELLA
----------------------
Il nome del pacchetto si costruisce sempre uguale e lo fa una funzione sola,
``pub_dir_name``.  In Swift la stessa espressione compariva in sei punti
diversi: il giorno che la regola
cambia, cinque punti restavano indietro e la sezione semplicemente spariva
(e' successo, e' nella lista delle trappole).
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import time
import urllib.parse
from pathlib import Path

from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility.Structures.Generals import Document, Publication

# I documenti HTML che si scaricano da wol.jw.org per le pubblicazioni.
ARTICLES_DIR = "Documents_I"
ARTICLES_URL = "https://wol.jw.org/it/wol/d/r6/lp-i/"

# L'indirizzo dei documenti dipende dalla lingua: vedi `Utility.WolLingua.url_documento`.



def pub_dir_name(pub: Publication) -> str:
    """Il nome della cartella di una pubblicazione.

    ``w_I_202110`` per la Torre di Guardia di ottobre 2021, ``sjj_I`` per il
    Canzoniere.  La regola dell'ultimo pezzo e' la stessa del progetto
    originale: un IssueTagNumber che finisce con "00" si divide per 100
    (202110 -> 2021), altrimenti resta com'e'.

    Attenzione: 202100 finisce con "00" e diventerebbe 2021, che e' un anno
    e non un mese.  Il divisore e' quello che ha scritto l'originale e si
    lascia stare: i numeri che arrivano dal catalogo sono 20YYMM o 20YY0.
    """
    # Il pezzo di lingua e' quello della pubblicazione: la stessa pubblicazione
    # in inglese e in italiano sono due cartelle (``w_E_202610``, ``w_I_202610``).
    from Utility import Lingua
    lingua = Lingua.da_numero(pub.mepsLanguageId)
    if pub.issueTagNumber == 0:
        return f"{pub.keySymbol}_{lingua}"
    testo = str(pub.issueTagNumber)
    finale = testo[:-2] if testo.endswith("00") else testo
    return f"{pub.keySymbol}_{lingua}_{finale}"


def pub_dir(pub: Publication) -> Path:
    """La cartella della pubblicazione, gia' scompattata."""
    return get_documents_directory() / pub_dir_name(pub)


def pub_db_path(pub: Publication) -> Path:
    """Il percorso del .db dentro il pacchetto scompattato."""
    nome = pub_dir_name(pub)
    return get_documents_directory() / nome / "contents" / f"{nome}.db"


# LA BIBBIA: COME SI CHIAMA, E COME SI TROVA
# ------------------------------------------
# Il progetto originale scriveva "nwt_I" in tre posti: il pacchetto, la
# cartella, e il database.  Funzionava nel 2021 perche' la Bibbia si chiamava
# nwt_I.jwpub.  Oggi l'edizione per lo studio si chiama nwtsty_I.jwpub, e
# quindi la cartella si chiama nwtsty_I e il database nwtsty_I.db.
#
# Con "nwt_I" scritto fisso, la sezione Bibbia dice "0 libri" e la sezione
# delle citazioni dice "Non ci sono contenuti aggiuntivi", senza dare nessun
# errore: si sta leggendo un percorso che non esiste, e la differenza fra
# "non c'e' niente" e "non so dove sia" non la fa nessuno.
#
# Il nome quindi si cerca, e si cerca guardando il database: una cartella di
# una Bibbia e' quella che ha dentro un .db con la tabella BibleBook.  Non e'
# un indovinare: e' un controllo.
#
# E LA LINGUA ENTRA NELLA RICERCA
# -------------------------------
# Prima si cercava fra tutte le cartelle `nwt*` e si prendeva la prima, che e'
# quella che viene prima per nome: `nwtsty_E` prima di `nwtsty_I`.  Con una
# sola Bibbia scaricata andava bene perche' non c'era scelta; con il menu della
# lingua era sbagliato, perche' cambiando lingua si continuava a leggere la
# Bibbia di prima senza dire niente — testo italiano sotto un'app in spagnolo.
#
# Quindi si cerca solo la cartella della lingua scelta.  Se non c'e', non si
# ripiega su quella di un'altra lingua: un ripiego silenzioso mostra il testo
# sbagliato, e la sezione Bibbia che da' il libro con la parola sbagliata e'
# peggio di una sezione che dice che il pacchetto non c'e'.
def _e_bible(cartella: Path) -> bool:
    """Questa cartella e' un pacchetto della Bibbia?

    Il controllo e' la tabella ``BibleBook`` dentro un .db in ``contents/``:
    e' un fatto, non un nome indovinato.
    """
    if not cartella.is_dir():
        return False
    for db in sorted((cartella / "contents").glob("*.db")):
        try:
            connessione = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            riga = connessione.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='BibleBook';"
            ).fetchone()
        finally:
            connessione.close()
        if riga:
            return True
    return False


def bible_package(lingua: str | None = None) -> Path | None:
    """La cartella del pacchetto della Bibbia **nella lingua scelta**, o None.

    Si guarda solo fra le cartelle che finiscono con ``_<simbolo>``, percio'
    funzionano sia i nomi nuovi (`nwtsty_I`) sia quelli vecchi (`nwt_I`):
    quello che conta e' il pezzo di lingua in fondo, non l'edizione.

    Senza `lingua` si usa quella scelta dall'utente.  Il default non puo'
    essere la lettera "I" perche' un valore predefinito viene calcolato
    quando il modulo viene importato, quindi significherebbe "Bibbia italiana
    per sempre" e la sezione non cambierebbe mai.
    """
    if not lingua:
        from Utility import Lingua
        lingua = Lingua.bibbia_simbolo()
    radice = get_documents_directory()
    for cartella in sorted(radice.glob(f"nwt*_{lingua}")):
        if _e_bible(cartella):
            return cartella
    return None


def bible_package_di_qualunque_lingua() -> Path | None:
    """Una Bibbia qualsiasi sul disco, o None se non ce n'e' nessuna.

    Serve a una cosa sola: capire se la Bibbia manca perche' non e' mai stata
    scaricata oppure perche' c'e' ma in un'altra lingua.  Sono due situazioni
    diverse e vanno trattate in modo diverso — vedi `BibleView._comincia` — e
    per distinguerle serve sapere se sul disco c'e' qualcosa.
    """
    radice = get_documents_directory()
    for cartella in sorted(radice.glob("nwt*")):
        if _e_bible(cartella):
            return cartella
    return None


def bible_db_path() -> Path | None:
    """Il percorso del database della Bibbia, o None se non c'e'."""
    cartella = bible_package()
    if cartella is None:
        return None
    return next((cartella / "contents").glob("*.db"), None)


def _connect_bible() -> sqlite3.Connection | None:
    """Apre il database della Bibbia, ovunque sia."""
    percorso = bible_db_path()
    if percorso is None:
        print("Non trovo il pacchetto della Bibbia ⚠️")
        return None
    try:
        return sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


def scarica_jwpub(key_symbol: str, issue_tag: int, lingua: str | None = None,
                  completion=None, on_progress=None) -> None:
    """Scarica un .jwpub chiedendo prima all'API dove si trova.

    PERCHE' L'URL NON E' SCRITTO A MANO
    ------------------------------------
    Il progetto originale aveva l'indirizzo del pacchetto scritto dentro il
    codice, uno per pacchetto:

        SubViews/BibleView.swift:
        let bibleURL = URL(string:
            "https://download-a.akamaihd.net/files/media_publication/c1/nwt_I.jwpub")!

    Quell'indirizzo oggi risponde 404.  Non e' un problema dell'app: e' che
    jw.org ha cambiato CDN, e gli indirizzi diretti hanno dentro un percorso
    con un numero che cambia:

        https://cfp2.jw-cdn.org/a/221701/8/o/nwtsty_I.jwpub
                                      ^^^^^^ ^

    Scritto a mano diventa rotto senza che nessuno abbia toccato niente, e
    l'unico sintomo e' "HTTP Error 404" in mezzo a un sacco di messaggi.

    L'unico indirizzo che non cambia e' quello dell'API, che ogni volta
    restituisce quello giusto.  Per questo qui si chiede, e non si indovina.
    La stessa identica domanda che fa gia' ``PubListView`` per le
    pubblicazioni: un posto solo, due usi.

    Il callback arriva sul main thread, perche' costruisce schermate.

    LA LINGUA
    ---------
    `langwritten` era scritto `I` fisso, quindi scaricava la Bibbia italiana
    anche con lo spagnolo scelto: 122 MB di un'altra lingua, e il nome della
    cartella che ne esce (`nwtsty_I`) che `bible_package()` poi non
    riconosce come Bibbia della lingua corrente.  Il pacchetto e la cartella
    devono parlare la stessa lingua di quella che si sta leggendo, quindi la
    lingua arriva da `Lingua`, che e' il posto unico in cui sta.
    """
    from Utility.Extensions.Ext_DispatchQueue import background
    from Utility.FileDownloader import FileDownloader
    from Utility.Stuff import Stuff

    if not lingua:
        from Utility import Lingua
        lingua = Lingua.corrente_simbolo()

    api = ("https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"
           f"?issue={issue_tag}&output=json&pub={key_symbol}"
           f"&fileformat=jwpub&alllangs=0&langwritten={urllib.parse.quote(lingua)}")

    def chiedi_url() -> None:
        url = Stuff.get_jwpub_url(api_link=api)
        if not url:
            if completion is not None:
                completion(None, OSError(
                    f"L'API non sa dove sia il pacchetto {key_symbol}"))
            return
        FileDownloader.load_file_async(url=url, completion=completion,
                                       on_progress=on_progress)

    background(chiedi_url)


def _connect(pub: Publication) -> sqlite3.Connection | None:
    """Il database del pacchetto, o None.

    NON SCARICATO E' UNA FINE, NON UN ERRORE
    ----------------------------------------
    Qui prima finivano due righe:

        Errore apertura database ⚠️  unable to open database file
        Errore apertura database ⚠️  sjj_I

    per ogni pubblicazione che l'utente non aveva ancora scaricato, e una
    delle due righe e' un messaggio di SQLite che non dice niente — dice
    solo che un file non c'e', cosa che il pulsante «Scarica» sa gia'.

    Il caso di cui vale la pena parlare e' l'altro: il pacchetto c'e' e il
    database non si apre.  Quello e' un difetto vero e resta scritto, con il
    nome del pacchetto accanto.
    """
    percorso = pub_db_path(pub)
    if not percorso.parent.parent.exists():
        return None            # non scaricato: lo dice la sezione, non qui
    connessione = _connect_path(percorso)
    if connessione is None:
        print(f"Errore apertura database ⚠️  {pub_dir_name(pub)}")
    return connessione


def _connect_path(path: Path) -> sqlite3.Connection | None:
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


class JWPubManager:

    @staticmethod
    def extract_pub(url) -> None:
        """Scompatta un .jwpub: fuori il primo ZIP, poi il secondo.

        La struttura e'::

            nwt_I.jwpub                <- ZIP
              manifest.json            <- in chiaro
              contents                 <- ZIP annidato
                nwt_I.db               <- SQLite

        ``contents`` dentro e' un *file*, non una cartella: per questo prima
        lo si rinomina in ``contentsFile``, poi si crea la cartella
        ``contents`` e la si scompatta dentro.  E' il trucco che rende
        leggibili i due ZIP con la stessa funzione di sistema.
        """
        import zipfile

        documents = get_documents_directory()
        source_url = documents / Path(str(url)).name
        destination_url = documents / source_url.name.replace(".jwpub", "")
        print(source_url)
        print(destination_url)

        try:
            if destination_url.exists():
                shutil.rmtree(destination_url)
            destination_url.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(source_url) as archivio:
                archivio.extractall(destination_url)
        except (OSError, zipfile.BadZipFile) as errore:
            print(f"Estrazione dell'archivio ZIP fallita con errore: {errore} ⚠️")
            return

        # ADESSO IL SECONDO ZIP, E L'ORDINE DEI TRE PASSI E' OBBLIGATO
        # -------------------------------------------------------------
        # Dopo il primo extractall, dentro la cartella c'e' una VOCE che si
        # chiama "contents", e non e' una cartella: e' il secondo ZIP, un
        # file.  Per aprirlo serve che al suo posto ci sia una cartella, e il
        # nome "contents" e' gia' preso.  Quindi il file va spostato via
        # PRIMA:
        #
        #     1. contents       -> contentsFile   (sposta il file)
        #     2. contents       -> cartella vuota (ora il nome e' libero)
        #     3. contentsFile   -> dentro contents (scompatta e cancella)
        #
        # Se si salta il passo 1 e si va dritti al 2, mkdir trova un file con
        # lo stesso nome, solleva FileExistsError, e la except se lo mangia.
        # Il risultato e' che il pacchetto sembra scompattato e dentro non c'e'
        # niente: la sezione pubblicazioni non mostra un capitolo, e non si
        # capisce perche'.
        #
        # Il progetto originale lo faceva con moveItem e poi createDirectory.
        # Qui si fa con rename e poi mkdir, che sono le due operazioni dello
        # stesso ordine.  Era questo il difetto: il passo 1 non c'era, e
        # nessuno se ne accorse perche' l'eccezione non rompeva niente.
        contents_file = destination_url / "contentsFile"
        contents_zip = destination_url / "contents"
        contents_folder = destination_url / "contents"

        print(contents_zip)
        print(contents_folder)
        JWPubManager.delete_file(filePath=source_url)

        # Se "contents" e' gia' una cartella il pacchetto e' stato gia'
        # scompattato: non si tocca niente.
        if contents_folder.is_dir():
            print("Il pacchetto e' gia' scompattato")
            return

        if not contents_zip.is_file():
            print(f"{contents_zip} non c'e', non c'e' il secondo ZIP ⚠️")
            return

        # 1. il file ZIP si sposta, e il nome "contents" si libera
        try:
            contents_zip.replace(contents_file)
        except OSError as errore:
            print(f"Non riesco a preparare il secondo ZIP ⚠️  {errore}")
            return

        # 2. e adesso al posto del nome c'e' una cartella
        try:
            contents_folder.mkdir(parents=True, exist_ok=False)
        except OSError as errore:
            print(f"Non riesco a creare {contents_folder} ⚠️  {errore}")
            return

        # 3. si scompatta dentro, e il ZIP compresso si butta
        try:
            with zipfile.ZipFile(contents_file) as archivio:
                archivio.extractall(contents_folder)
        except (OSError, zipfile.BadZipFile) as errore:
            print(f"Estrazione di contents fallita con errore: {errore} ⚠️")
            return
        JWPubManager.delete_file(filePath=contents_file)

        # 4. il controllo che dice se il pacchetto e' buono davvero.
        #    Un pacchetto scompattato senza il .db dentro non serve a niente,
        #    e senza questo controllo il difetto si vede solo molto dopo.
        if not any(contents_folder.glob("*.db")):
            print(f"ATTENZIONE: nessun .db dentro {contents_folder} ⚠️ "
                  f"il pacchetto non e' utilizzabile")
            return
        print(f"{destination_url.name} scompattato ✅")

    @staticmethod
    def delete_file(filePath) -> None:
        """Toglie un file, se c'e'."""
        try:
            Path(filePath).unlink()
            print("File cancellato ✅")
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            print("Errore ⚠️")

    @staticmethod
    def download_documents(pub: Publication, on_progress=None) -> None:
        """Scarica da wol.jw.org il testo di ogni capitolo della pubblicazione.

        Il .jwpub dice solo *quali* capitoli ci sono (MepsDocumentId, che e' in
        chiaro): il testo e' cifrato e non si decifra, quindi si va a prendere
        la versione pubblica dello stesso capitolo.  Il nome del file salvato e'
        il MepsDocumentId, cosi' ArticleView ritrova il file con lo stesso
        criterio con cui lo ha scritto.

        IL CHIAMANTE DEVE PASSARE UN `on_progress`, E CHIAMARLO DA UN THREAD
        ----------------------------------------------------------------
        Qui dentro ci sono **quindici richieste di rete una dopo l'altra** per
        una pubblicazione come «Altri argomenti», e milleottocentonovanta per
        la Bibbia.  Ogni richiesta aspetta la risposta, e l'attesa e' lavoro
        che blocca.

        Percio' questa funzione **non si puo' chiamare dal main thread**: la
        finestra resta ferma per tutto il download, e sembra piantata.  Il
        sintomo misurato: scaricando «Altri argomenti» la finestra non rispondeva
        e KDE offriva di terminarlo, poi si e' ripresa da sola quando il lavoro
        aveva finito.

        `on_progress(fatti, totale)` viene chiamato dopo ogni capitolo, dal
        thread di lavoro: chi ascolta lo rimette sul main thread con un
        segnale, che e' l'unico modo che Qt accetti.  I due numeri sono i
        capitoli **scritti** e quelli **da scrivere**, non l'id del capitolo e
        il totale come era prima: un'id non dice niente all'utente e non puo'
        far avanzare una barra.
        """
        from Utility.FileDownloader import FileDownloader  # ciclo: vedi sotto

        from Utility import Lingua, WolLingua
        simbolo = Lingua.da_numero(pub.mepsLanguageId) or Lingua.corrente_simbolo()
        if not WolLingua.supportata(simbolo):
            # Il sito non ha questa lingua: meglio nessun documento che testo
            # di un'altra lingua.
            return

        connessione = _connect(pub)
        if connessione is None:
            return
        try:
            righe = connessione.execute("SELECT MepsDocumentId FROM Document;").fetchall()
        except sqlite3.Error as errore:
            print(f"Errore lettura Document ⚠️  {errore}")
            return
        finally:
            connessione.close()

        totale = len(righe)
        fatti = 0
        for (meps_document_id,) in righe:
            if FileDownloader.annullato():
                return
            article_url = WolLingua.url_documento(meps_document_id, simbolo)
            if article_url:
                FileDownloader.download_article(
                    url=article_url,
                    path=f"{ARTICLES_DIR}/{meps_document_id}.html",
                )
            fatti += 1
            if on_progress is not None:
                on_progress(fatti, totale)

    @staticmethod
    def bible_sections() -> list[tuple[str, list[tuple[int, str, int]]]]:
        """Le schede della Bibbia, come le elenca il pacchetto.

        La vista «JW App Publication» ha sei voci di primo livello: Introduzione,
        Libri, Indice, Appendice A, B, C.  Per ognuna si danno i discendenti
        come ``(MepsDocumentId, titolo, livello)``; ``MepsDocumentId`` e' 0 per
        un titoletto che raggruppa (es. «CARTINE»).  Il testo e' cifrato nel
        pacchetto: si legge dalla pagina pubblica, scaricata a richiesta.
        """
        connessione = _connect_bible()
        if connessione is None:
            return []
        try:
            righe = connessione.execute(
                "SELECT i.PublicationViewItemId, i.ParentPublicationViewItemId, "
                "i.Title, d.MepsDocumentId FROM PublicationViewItem i "
                "LEFT JOIN Document d ON d.DocumentId = i.DefaultDocumentId "
                "WHERE i.PublicationViewId = 2 "
                "ORDER BY i.PublicationViewItemId;").fetchall()
        except sqlite3.Error as errore:
            print(f"Errore lettura schede Bibbia ⚠️  {errore}")
            return []
        finally:
            connessione.close()
        figli: dict[int, list] = {}
        for item_id, genitore, titolo, meps in righe:
            figli.setdefault(genitore, []).append((item_id, titolo, meps))
        primo_livello = figli.get(-1, [])
        if len(primo_livello) != 6:
            return []

        def scendi(item_id: int, livello: int, fuori: list) -> None:
            for figlio, titolo, meps in figli.get(item_id, []):
                fuori.append((int(meps or 0), titolo, livello))
                scendi(figlio, livello + 1, fuori)

        uscita = []
        for item_id, titolo, _meps in primo_livello:
            voci: list = []
            scendi(item_id, 0, voci)
            uscita.append((titolo, voci))
        return uscita

    @staticmethod
    def get_documents(pub: Publication) -> list[Document]:
        """I capitoli della pubblicazione, con titolo e titolo di contesto."""
        documents: list[Document] = []
        connessione = _connect(pub)
        if connessione is None:
            return documents
        try:
            righe = connessione.execute(
                """
                SELECT DocumentId, MepsDocumentId, Title, ContextTitle
                FROM Document;
                """
            )
            for doc_id, meps_document_id, titolo, contesto in righe:
                documents.append(
                    Document(
                        ID=doc_id,
                        documentId=meps_document_id,
                        title=titolo or "",
                        contextTitle=contesto,
                    )
                )
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return documents

    @staticmethod
    def get_document_media(pub: Publication, document_number: int) -> list[dict]:
        """Le figure che stanno dentro un capitolo.

        Ogni voce e' un dizionario:

            "percorso"   il file dentro il pacchetto
            "mime"       il tipo: "image/jpeg", "image/svg+xml", ...
            "larghezza"  i pixel, se il pacchetto li sa
            "altezza"    i pixel, se il pacchetto li sa

        LA QUERY ATTRAVERSA TRE TABELLE IN FILA
        ----------------------------------------
        Il capitolo, la figura che gli appartiene e il file della figura.  Si
        prendono solo le figure che hanno un paragrafo di inizio o di fine,
        perche' le altre non sono dentro il testo ma altrove (indice,
        copertina).

        Nota sul numero: qui ``document_number`` e' il MepsDocumentId, ed e'
        quello che passa ArticleView.

        L'ORDINE NON E' QUELLO DELLA PAGINA
        -----------------------------------
        L'ordine del database e' quello del pacchetto, e non quello in cui
        le figure compaiono nel capitolo: davanti c'e' la figura di apertura,
        e le miniature della «edizione stampata» vengono prima del testo.
        Chi usa questa lista deve abbinare le figure al testo **guardando le
        dimensioni**, e non contando: vedi `WebBrowserArticleView._metti_figure`.
        """
        media: list[dict] = []
        connessione = _connect(pub)
        if connessione is None:
            return media
        content_path = pub_dir(pub) / "contents"
        try:
            righe = connessione.execute(
                """
                SELECT DISTINCT Multimedia.MultimediaId, Multimedia.MimeType,
                       Multimedia.FilePath, Multimedia.Width, Multimedia.Height
                FROM DocumentMultimedia
                INNER JOIN Document ON Document.DocumentId = DocumentMultimedia.DocumentId
                INNER JOIN Multimedia ON Multimedia.MultimediaId = DocumentMultimedia.MultimediaId
                WHERE Document.MepsDocumentId = ?
                AND Multimedia.FilePath <> ''
                AND Multimedia.MimeType LIKE 'image/%'
                AND (BeginParagraphOrdinal IS NOT NULL OR EndParagraphOrdinal IS NOT NULL)
                ORDER BY Multimedia.MultimediaId;
                """,
                (document_number,),
            )
            dimensioni = JWPubManager._dimensioni_dei_media(connessione)
            for _multimedia_id, mime, file_name, larghezza, altezza in righe:
                img_path = content_path / str(file_name)
                if not img_path.is_file():
                    continue
                misure = dimensioni.get(str(file_name))
                if misure is not None:
                    larghezza = larghezza or misure[0]
                    altezza = altezza or misure[1]
                media.append({
                    "percorso": img_path,
                    "mime": str(mime or "image/jpeg"),
                    "larghezza": int(larghezza) if larghezza else None,
                    "altezza": int(altezza) if altezza else None,
                })
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return media

    @staticmethod
    def _dimensioni_dei_media(connessione) -> dict[str, tuple[int, int]]:
        """Le dimensioni dei file di media del pacchetto, per nome.

        PERCHE' SERVE UNA TABELLA E NON BASTA LA RIGA
        ---------------------------------------------
        La stessa figura compare piu' volte nella tabella `Multimedia` — una
        volta per ogni documento che la usa — e in una delle righe le
        dimensioni ci sono e in un'altra no.  Il nome del file e' la chiave,
        e la riga che ha le dimensioni e' quella giusta.

        Senza questa tabella la figura di apertura di un capitolo (che e'
        la stessa in tutti i capitoli) arrivava senza dimensioni, e senza
        dimensioni non si puo' capire a quale figura della pagina
        corrisponde: ogni immagine finiva sotto la didascalia sbagliata.
        """
        dimensioni: dict[str, tuple[int, int]] = {}
        try:
            righe = connessione.execute(
                """
                SELECT FilePath, Width, Height FROM Multimedia
                WHERE FilePath <> '' AND Width IS NOT NULL AND Height IS NOT NULL
                """
            )
            for file_name, larghezza, altezza in righe:
                try:
                    dimensioni[str(file_name)] = (int(larghezza), int(altezza))
                except (TypeError, ValueError):
                    continue
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        return dimensioni

    @staticmethod
    def article_url(meps_document_id: int) -> str:
        """La URL pubblica del capitolo, per il log e per i riferimenti."""
        from Utility.WolLingua import url_documento
        return urllib.parse.quote(url_documento(meps_document_id), safe=":/?&=")

# ---------------------------------------------------------------------------
# COSA C'E' SCARICATO: SI GUARDA IL DISCO
# ---------------------------------------------------------------------------
#
# `jwl/DESIGN-SYSTEM.txt` 6.15, "Download: cosa c'e' a terra, e come si toglie":
#
#     La lista viene dal DISCO, non da `library.db`.  L'indice sa che cosa
#     si puo' scaricare; qui si vuole sapere che cosa c'e'.  Un pacchetto
#     messo a mano col copia e incolla e' scaricato esattamente come uno
#     preso dall'app, e se la lista guardasse l'indice non lo mostrerebbe.
#
# E' la regola giusta per un motivo che si vede solo se si prova: interrogare
# l'indice richiede di sapere il nome della cartella, e il nome della cartella
# lo si sa solo se si conosce l'anno e il mese della pubblicazione.  Per una
# Torre di Guardia di marzo 2010 la cartella e' `w_I_201003` e per quella di
# ottobre e' `w_I_201010`: la differenza la fa solo l'ultimo numero, e un
# indice riportato indietro di un mese non la fa indovinare.
#
# Qui invece si guarda cosa c'e' nella cartella.  Il nome lo da' il disco, e il
# titolo lo dice il .db che sta dentro il pacchetto.

def peso(cartella: Path) -> int:
    """I byte che occupa una cartella, contati uno per uno.

    Non la dimensione dichiarata dal sito: quello che occupa e' quello che
    c'e'.  Un pacchetto scaricato a meta' e' meta' di quello che dovrebbe
    essere, e mostrarlo come intero e' l'unico modo di non accorgersene.
    """
    totale = 0
    try:
        for cosa in cartella.rglob("*"):
            if cosa.is_file():
                try:
                    totale += cosa.stat().st_size
                except OSError:
                    continue          # sparito mentre si contava
    except OSError:
        return 0
    return totale


def scaricate() -> list[Path]:
    """Le cartelle pacchetto che ci sono davvero sul disco.

    Il riconoscimento e' il ``.db`` dentro ``contents/``: e' lo stesso
    controllo che fa l'estrazione alla fine ("nessun .db dentro contents: il
    pacchetto non e' utilizzabile"), quindi la lista non puo' contenere una
    cartella che l'app saprebbe dichiarare non utilizzabile un secondo dopo.

    Sono esclusi ``Documents_I``, ``copertine``, ``userData`` e ``catalog.db``:
    non hanno un ``contents/*.db``, quindi non entrano da sole, e non viene
    scritto un elenco di eccezioni per tenerli fuori: un criterio che basta
    da solo e' meglio di un criterio con le sue eccezioni.
    """
    radice = get_documents_directory()
    trovate: list[Path] = []
    try:
        voci = sorted(radice.iterdir())
    except OSError:
        return []
    for cartella in voci:
        if not cartella.is_dir():
            continue
        try:
            if any((cartella / "contents").glob("*.db")):
                trovate.append(cartella)
        except OSError:
            continue
    return trovate


def leggi_pubblicazione(cartella: Path) -> Publication | None:
    """La pubblicazione descritta dal .db dentro il pacchetto, o None.

    Si legge la tabella ``Publication``.  Se non c'e', o non si legge, si
    restituisce None e chi chiama mostra la riga con quello che c'e' da
    mostrare: il nome della cartella.  Una riga senza titolo e' meno utile di
    una riga con il nome della cartella, che almeno e' vero.
    """
    nome = cartella.name
    database = cartella / "contents" / f"{nome}.db"
    if not database.is_file():
        # il nome della cartella puo' non coincidere con quello del .db
        # quando l'archivio e' stato spostato a mano
        try:
            candidati = sorted((cartella / "contents").glob("*.db"))
        except OSError:
            return None
        if not candidati:
            return None
        database = candidati[0]

    try:
        connessione = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        riga = connessione.execute(
            "SELECT Title, Symbol, IssueTagNumber, MepsLanguageIndex "
            "FROM Publication LIMIT 1").fetchone()
    except sqlite3.Error:
        return None
    finally:
        connessione.close()

    if not riga:
        return None
    titolo, simbolo, issue, lingua = riga
    # `issueTagNumber` e' dichiarato `int` e `Copertine` ci fa `// 100` per
    # ricavare l'anno.  SQLite lo restituisce come testo perche' nella tabella
    # e' una colonna dichiarata TEXT, e una stringa con `//` solleva:
    #
    #     TypeError: unsupported operand type(s) for //: 'str' and 'int'
    #
    # Il tipo giusto si mette qui, una volta sola, invece di stare attenti in
    # ogni chiamante: un campo che arriva dal database come testo e' la
    # regola, non l'eccezione.
    try:
        numero_issue = int(issue or 0)
    except (TypeError, ValueError):
        numero_issue = 0
    return Publication(
        ID=0,
        keySymbol=_sigla_base(nome, simbolo),
        year=0,
        mepsLanguageId=int(lingua or 4),
        publicationTypeId=0,
        issueTagNumber=numero_issue,
        title=titolo or nome,
    )


def _sigla_base(nome_cartella: str, simbolo) -> str:
    """La sigla con cui il catalogo conosce la pubblicazione.

    Nel database del pacchetto `Symbol` dei periodici e delle guide porta
    l'anno (`mwb26`), mentre il catalogo e il nome della cartella usano la
    sigla base (`mwb`, cartella `mwb_I_202611`).  Se si usasse `Symbol`, la
    card degli Scaricati cercherebbe la cartella `mwb26_I_...` che non
    esiste: nuvoletta al posto del pacchetto, «Non trovo mwb26 nel
    catalogo» e l'eliminazione che non trova niente da togliere.
    Il prefisso della cartella e' per costruzione `pub.keySymbol`
    (vedi `pub_dir_name`), quindi e' lui la sigla giusta.
    """
    prefisso = nome_cartella.split("_")[0] if "_" in nome_cartella else ""
    return str(prefisso or simbolo or nome_cartella)


#: I conteggi gia' fatti, per (cartella, data del database).  Vedi la
#: spiegazione in `media_nella_cartella`: la data sta nella chiave perche' il
#: pacchetto riscompattato e' un pacchetto diverso.
_MEDIA_GIA_CONTATI: dict = {}

#: Le chiavi per cui il messaggio e' gia' uscito.  Sono separate dai
#: conteggi perche' un conto puo' volerlo ricalcolare senza ristampare: e il
#: caso normale, perche' `media_nella_cartelle` viene chiamata di nuovo a ogni
#: ridisegno.
_DETTO: set = set()

#: Sopprime il messaggio "pacchetto scaricato senza media" (usato in --verifica).
_SILENZIOSO: bool = False

#: Pubblicazioni "testo-prima" dove i media sono opzionali/referenziati
#: e la loro assenza sul disco e' NORMALE, non un problema.
#: nwtsty = Cantiamo a Geova con gioia (canzoniere)
#: sjj    = Cantiamo a Geova con gioia (edizione precedente)
#: lmd    = Ama le persone. Fai discepoli
#: th     = Applicati alla lettura e all'insegnamento
#: lff    = Puoi vivere felice per sempre?
#: lffi   = Puoi vivere felice per sempre? (edizione precedente)
#: ypq    = Giovani: le domande
#: sn     = Studio biblico
#: esXX   = Esempi per l'insegnamento (es26, es27, ecc.)
#: hs     = La Bibbia per lo studio
#: mwb    = Guida per l'adunanza Vita e ministero (sezione Adunanze)
#: w      = La Torre di Guardia, edizione per lo studio (sezione Adunanze)
#: nwtsty_I ha 105 tracce video nel DB ma 0 file: e' un canzoniere, i video son separati
_PUBBLICAZIONI_TESTO_PRIMA: set[str] = {
    "nwtsty", "sjj", "lmd", "th", "lff", "lffi", "ypq", "sn", "hs", "mwb", "w"
}


def _e_testo_prima(sigla: str) -> bool:
    """True se la pubblicazione e' testo-prima (media opzionali)."""
    return sigla.lower() in _PUBBLICAZIONI_TESTO_PRIMA or sigla.lower().startswith("es")


def media_nella_cartella(cartella: Path) -> tuple[int, int]:
    """Quante tracce audio e video ci sono davvero dentro una cartella.

    Si contano i file che ci sono, non le righe che il database promette.  I
    due numeri sono diversi, ed e' stato misurato:

        nwtsty_I    105 video citati nella tabella ``Multimedia``, 0 file .mp4
        nwtsty_I    756 immagini citate, 756 file sul disco  (100%)

    Il pacchetto della Bibbia per lo studio elenca i suoi video e non li
    contiene.  Contando le righe si direbbe «105 video, il clic apre il
    video» e il clic aprirebbe una scheda vuota: un pulsante che non porta da
    nessuna parte e' peggio di un pulsante che porta al pacchetto, perche'
    fa pensare che sia il pacchetto a essere sbagliato.

    Il nome del file e' nella colonna ``FilePath`` e sta in ``contents/``,
    la stessa cartella dove finiscono le immagini, e quelle ci sono tutte.

    IL RISULTATO SI RICORDA, E PERCHE'
    -----------------------------------
    Questa funzione viene chiamata da quattro posti — la sezione Scaricati
    per ogni riga, la sezione Multimedia, il menu' di ogni riga, il controllo
    di `che_cosa_apre` — e all'avvio le sezioni sono tutte costruite, anche
    quelle che l'utente non apre.  Per la sola Bibbia la chiamata arrivava a
    una trentina di volte.

    Il conto, da solo, non e' il problema: sono 105 nomi e 105 controlli di
    esistenza, e ci mette poco.  Il problema e' il messaggio, che usciva una
    volta per chiamata: **la stessa riga trentacinque volte di fila**,
    prima di qualsiasi altra riga dello schermo.  Un avviso ripetuto non e'
    piu' un avviso, e' rumore che copre il resto — e nasconde anche i messaggi
    che servono davvero.

    Percio' il risultato viene ricordato per cartella, e con lui la
    decisione di averlo gia' detto.

    LA CHIAVE INCLUDE LA DATA DEL DATABASE, E NON SOLO LA CARTELLA
    ------------------------------------------------------------
    Una chiave fatta solo del percorso sbagliarebbe in un caso che capita
    subito: si scarica la Bibbia, il pacchetto viene riscompattato, e il
    risultato ricordato sarebbe quello di **prima** del download, cioe'
    "105 tracce citate, nessun file" — che e' falso da quel momento in poi.
    Senza accorgersene, la sezione Multimedia direbbe che la Bibbia non ha
    video anche dopo che sono arrivati.

    Mettere la data del database nella chiave risolve da sola: il file
    cambia quando il pacchetto viene riscompattato, quindi il risultato
    ricordato non e' piu' valido e viene ricalcolato.  Non serve nessuna
    chiamata per "dimenticare", che era il modo per sbagliare: basta che il
    dato su cui si e' deciso sia cambiato.

    Non e' una cache che si puo' dimenticare a mano, e questa e' la parte
    importante: una cache che si invalida da sola e' un fatto; una che
    qualcuno deve svuotare e' un peso, e prima o poi qualcuno non lo fa.
    """
    import sqlite3

    contenuti = cartella / "contents"
    database = contenuti / f"{cartella.name}.db"
    if not database.is_file():
        return 0, 0

    try:
        # `-1` su uno stat e' niente: si vuole la data piu' recente, cioe'
        # quella del file se c'e', e se il file non ci fosse non si arriva
        # qui.  Non si puo' pero' silenziare l'errore con `getattr`: se il
        # filesystem risponde ma non dà la data, si deve sapere che il
        # risultato e' rimasto indietro.
        momento = database.stat().st_mtime_ns
    except OSError as errore:
        print(f"{cartella.name}: non riesco a leggere il database ⚠️  {errore}")
        return 0, 0

    chiave = (str(cartella), momento)
    if chiave in _MEDIA_GIA_CONTATI:
        audio, video, citati = _MEDIA_GIA_CONTATI[chiave]
        _stampa_una_volta(chiave, cartella, citati)
        return audio, video

    try:
        connessione = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0, 0

    audio = video = citati = 0
    try:
        for mime, percorso in connessione.execute(
                "SELECT MimeType, FilePath FROM Multimedia "
                "WHERE MimeType LIKE 'audio/%' OR MimeType LIKE 'video/%'"):
            citati += 1
            if not (contenuti / str(percorso or "")).is_file():
                continue
            if str(mime).startswith("video/"):
                video += 1
            else:
                audio += 1
    except sqlite3.Error:
        return 0, 0
    finally:
        connessione.close()

    _MEDIA_GIA_CONTATI[chiave] = (audio, video, citati)
    _stampa_una_volta(chiave, cartella, citati)
    return audio, video


def media_nel_pacchetto(sigla: str, lingua: str | None = None) -> list[dict]:
    """I media (audio e video) che il pacchetto .jwpub dichiara.

    Ogni voce e' un dizionario:

        "formato"  "AUDIO" o "VIDEO"
        "traccia"  il numero della traccia, se il pacchetto lo sa
        "file"     il percorso del file, quando c'e' dentro il pacchetto
        "titolo"   il titolo che il pacchetto scrive
        "on_disk"  True se il file c'e' davvero
        "mime"     il tipo del media

    PERCHE' IL PACCHETTO PRIMA DEL CATALOGO
    ----------------------------------------
    Il libro sa da se' che cosa contiene: e' il suo database, dentro il
    .jwpub.  Il catalogo dei media e' un'altra cosa, e serve per quello
    che nel pacchetto non c'e' — i periodici, i video.

    Un media con il `FilePath` vuoto non e' dentro il pacchetto: e' sul
    server, e si raggiunge con la traccia.  Uno con il file c'e' gia' sul
    disco: e' gia' offline, e si guarda (o si ascolta) da li'.

    Il pacchetto che non c'e' non e' un errore: e' una pubblicazione non
    scaricata, e la lista vuota e' la risposta giusta.
    """
    radice = get_documents_directory()
    cartella = radice / f"{sigla}{_lingua_cartella(lingua)}"
    database = cartella / "contents" / f"{cartella.name}.db"
    if not database.is_file():
        # I periodici stanno in una cartella con il numero (mwb_I_202609).
        candidate = sorted(radice.glob(f"{cartella.name}_*"))
        for altra in reversed(candidate):
            db = altra / "contents" / f"{altra.name}.db"
            if db.is_file():
                cartella, database = altra, db
                break
    if not database.is_file():
        return []
    try:
        connessione = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return []

    voci: list[dict] = []
    try:
        righe = connessione.execute(
            "SELECT MultimediaId, Track, FilePath, MimeType, Label "
            "FROM Multimedia "
            "WHERE MimeType LIKE 'audio/%' OR MimeType LIKE 'video/%' "
            "ORDER BY MultimediaId"
        )
        for _multimedia_id, traccia, percorso, mime, titolo in righe:
            file = None
            if percorso:
                file = cartella / "contents" / str(percorso)
            try:
                numero = int(traccia or 0)
            except (TypeError, ValueError):
                numero = 0
            formato = ("VIDEO" if str(mime or "").startswith("video/")
                       else "AUDIO")
            voci.append({
                "formato": formato,
                "traccia": numero,
                "file": file,
                "titolo": str(titolo or ""),
                "on_disk": bool(file is not None and file.is_file()),
                "mime": str(mime or ""),
            })
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return []
    finally:
        connessione.close()
    return voci


def contenuti_del_documento(pub: Publication, documento_locale: int) -> list[dict]:
    """Immagini, video e audio di UN documento, nell'ordine dei paragrafi.

    Ogni voce: ``tipo`` ("immagine"/"video"/"audio"), ``titolo``, ``file``
    (percorso dell'immagine, se c'e'), ``sigla``, ``traccia``, ``numero``.
    Le miniature quadrate e le testate (``_sqr``, ``_lsr``, ``_pnr``, ``_cvr``)
    non sono contenuti della pagina e si saltano.
    """
    connessione = _connect(pub)
    if connessione is None:
        return []
    try:
        return _contenuti(connessione, documento_locale, pub_dir(pub) / "contents")
    finally:
        connessione.close()


def _chiave_media(voce: dict):
    """Cosa rende «la stessa» una voce: il nome del file, o sigla+traccia+numero."""
    if voce["tipo"] == "immagine":
        return ("immagine", Path(voce["file"]).name)
    return (voce["sigla"], voce["traccia"], voce["numero"], voce["tipo"])


def _contenuti(connessione: sqlite3.Connection, documento_locale: int, contenuti: Path,
               visti: set | None = None) -> list[dict]:
    """Il lavoro di `contenuti_del_documento`, su una connessione gia' aperta.

    ``visti`` e' l'insieme delle voci gia' prese (si aggiorna): serve a non
    ripetere la stessa cosa fra documenti diversi.

    Le figure di tipo 3 (SVG con le pagine del libro impaginate e le diapositive
    con il solo titolo) non sono immagini da mostrare e si saltano.
    """
    visti = set() if visti is None else visti
    try:
        righe = connessione.execute(
            "SELECT m.MimeType, m.FilePath, m.KeySymbol, m.Track, m.IssueTagNumber, "
            "m.Label, m.Caption, dm.BeginParagraphOrdinal, m.MajorType "
            "FROM DocumentMultimedia dm JOIN Multimedia m USING (MultimediaId) "
            "WHERE dm.DocumentId = ? "
            "ORDER BY COALESCE(dm.BeginParagraphOrdinal, 0), m.MultimediaId",
            (documento_locale,)).fetchall()
    except sqlite3.Error:
        return []
    voci: list[dict] = []
    for mime, percorso, sigla, traccia, numero, etichetta, didascalia, _ordine, genere in righe:
        mime = str(mime or "")
        if mime.startswith("image/"):
            nome = str(percorso or "")
            if (not nome or genere == 3 or mime == "image/svg+xml"
                    or any(t in nome for t in ("_sqr", "_lsr", "_pnr", "_cvr"))):
                continue
            file = contenuti / nome
            if not file.is_file():
                continue
            voce = {"tipo": "immagine", "titolo": str(etichetta or didascalia or ""),
                    "file": str(file)}
        elif mime.startswith(("video/", "audio/")) and sigla:
            voce = {"tipo": "video" if mime.startswith("video/") else "audio",
                    "titolo": str(etichetta or ""), "sigla": str(sigla),
                    "traccia": int(traccia or 0), "numero": int(numero or 0)}
        else:
            continue
        chiave = _chiave_media(voce)
        if chiave not in visti:
            visti.add(chiave)
            voci.append(voce)
    return voci


_RE_CITATA = re.compile(r"^jwpub://p/[A-Za-z]+:(\d+)")


def contenuti_citati(pub: Publication, documento_locale: int,
                     propri: list[dict] | None = None) -> list[dict]:
    """Immagini e video dei documenti citati dalla pagina, se il pacchetto e' scaricato.

    Si leggono i collegamenti ``jwpub://p/I:<MepsDocumentId>/...`` della
    pagina.  Per ogni documento citato che sta in un pacchetto sul disco si
    prendono i suoi media (tutti: il numero di paragrafo del link non coincide con
    la posizione dei media nel pacchetto).
    Ogni voce porta ``gruppo``: il titolo del documento da cui viene.
    Quelli non scaricati si saltano: non si va in rete per una lista.
    Quello che c'e' gia' in ``propri`` (o in un altro documento citato), anche con un
    altro nome di file ma con gli stessi byte, non si ripete.
    """
    from Utility import RiferimentiLocali

    connessione = _connect(pub)
    if connessione is None:
        return []
    try:
        proprio = connessione.execute(
            "SELECT MepsDocumentId FROM Document WHERE DocumentId = ?",
            (documento_locale,)).fetchone()
        collegamenti = connessione.execute(
            "SELECT h.Link FROM DocumentHyperlink dh JOIN Hyperlink h USING (HyperlinkId) "
            "WHERE dh.DocumentId = ? ORDER BY dh.DocumentHyperlinkId",
            (documento_locale,)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        connessione.close()

    citati: list[int] = []
    for (link,) in collegamenti:
        trovato = _RE_CITATA.match(str(link or ""))
        if not trovato:
            continue
        meps = int(trovato.group(1))
        if (not proprio or meps != proprio[0]) and meps not in citati:
            citati.append(meps)

    visti = {_chiave_media(v) for v in (propri or [])}
    impronte = {_impronta(v) for v in (propri or []) if v["tipo"] == "immagine"}
    voci: list[dict] = []
    for meps in citati:
        posto = RiferimentiLocali._pacchetto_del_documento(meps)
        if posto is None:
            continue
        db, locale = posto
        try:
            altra = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            titolo = altra.execute("SELECT Title FROM Document WHERE DocumentId = ?",
                                   (locale,)).fetchone()
            media = _contenuti(altra, locale, db.parent, visti)
        except sqlite3.Error:
            continue
        finally:
            altra.close()
        for voce in media:
            if voce["tipo"] == "immagine":
                impronta = _impronta(voce)
                if impronta in impronte:
                    continue
                impronte.add(impronta)
            voce["gruppo"] = (titolo[0] if titolo and titolo[0] else f"Documento {meps}")
            voci.append(voce)
    return voci


def _impronta(voce: dict) -> str:
    """L'impronta dei byte di un'immagine: due file con lo stesso contenuto coincidono."""
    import hashlib
    try:
        with open(voce["file"], "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return voce["file"]


def _stampa_una_volta(chiave, cartella: Path, citati: int) -> None:
    """Il messaggio del pacchetto senza media, **una volta sola**.

    Il "se gia' c'e' stato detto" sta dentro questa funzione e non nei
    chiamanti: e' l'unico posto dove si stampa, quindi e' l'unico posto dove
    si puo' ricordare di averlo fatto.  Se la condizione fosse stata scritta
    ai due posti che chiamano, i due avrebbero potuto dimenticarsene a turno e
    il messaggio sarebbe tornato a uscirsi ogni volta.
    """
    if not citati or chiave in _DETTO or _SILENZIOSO:
        return
    # La chiave e' una tupla (str(cartella), momento). Estrae la sigla dal nome cartella.
    # cartella.name = "nwtsty_I_2026" -> sigla = "nwtsty"
    nome_cartella = cartella.name
    sigla = nome_cartella.split("_", 1)[0] if "_" in nome_cartella else nome_cartella
    if _e_testo_prima(sigla):
        # Per pubblicazioni testo-prima (canzonieri, manuali) l'assenza media e' NORMALE
        _DETTO.add(chiave)
        return
    _DETTO.add(chiave)
    print(f"{cartella.name}: il database cita {citati} tracce e sul disco "
          f"non c'e' nessun file: il pacchetto e' scaricato senza i media ⚠️")


def media_sul_disco(sigla: str, lingua: str | None = None) -> tuple[int, int]:
    """Quante tracce audio e video ci sono davvero, se ci sono.

    Stessa regola di `DownloadsView._conta_media`, e stessa ragione: si
    contano i file che ci sono, non le righe che il database promette.

    Misurato, e la differenza non e' piccola:

        nwtsty_I   105 video citati nella tabella ``Multimedia``, 0 file .mp4
        nwtsty_I   756 immagini citate, 756 file sul disco

    Il pacchetto della Bibbia per lo studio elenca i suoi video e non li
    contiene.  Contando le righe si direbbe «105 video, il clic apre il
    video» e il clic aprirebbe una scheda vuota: un pulsante che porta da
    nessuna parte e' peggio di un pulsante che porta al pacchetto.

    E SI CONTANO ANCHE I FILE SCIOLTI
    ----------------------------------
    Un video preso dalla nuvoletta di una card e' un file ``wsb_I_02_r720P.mp4``
    in mezzo ai pacchetti: sulla radice dei dati, non dentro una cartella.
    Prima non si contava, e il clic su un video scaricato finiva nella
    Pubblicazioni che diceva «non e' scaricato» — mentre il file c'era, solo
    guardato nel posto sbagliato.  `media_sul_disco` risponde a una domanda
    sola («questo pezzo, c'e'?») e la risposta non cambia perche' il file e'
    sciolto.

    Se non c'e' niente restituisce (0, 0), e il chiamante apre il pacchetto,
    che e' l'unica azione possibile su una pubblicazione non scaricata.
    """
    audio, video = media_nella_cartella(
        get_documents_directory() / f"{sigla}{_lingua_cartella(lingua)}")

    # I file sciolti si contano per sigla e traccia, e una volta sola per
    # traccia: otto file della stessa traccia (tutte le risoluzioni) sono un
    # video, non otto.  `MediaScaricati.scaricati()` ha gia' separato ogni
    # file nei suoi pezzi; si prende l'insieme.
    try:
        from Utility import MediaScaricati

        visti: set[tuple[str, int]] = set()
        for voce in MediaScaricati.scaricati():
            chiave = (voce["sigla"], voce["traccia"])
            if chiave in visti:
                continue
            if voce["sigla"] != sigla:
                continue
            if lingua and voce["lingua"] != lingua:
                continue
            visti.add(chiave)
            if voce.get("formato") == "VIDEO":
                video += 1
            else:
                audio += 1
    except Exception:  # noqa: BLE001 - se i file sciolti non si leggono si
        pass            # resta il conteggio del pacchetto, che e' gia' giusto

    # L'ordine e' `(audio, video)`, come `media_nella_cartella`: i chiamanti
    # (`che_cosa_apre`, la sezione Scaricati) spacchettano cosi'.
    return audio, video


def _lingua_cartella(lingua: str | None) -> str:
    """Il pezzo di lingua del nome della cartella, cioe' `I` o cosi' via.

    Il nome della cartella e' `nwtsty_I`: il simbolo, non il codice ISO e non
    il numero.  Senza `lingua` si usa la scelta dell'utente.  Il default non
    puo' essere "I" perche' un valore predefinito viene calcolato quando il
    modulo viene importato, e questa funzione cerca una cartella: con "I"
    cercherebbe sempre la cartella italiana e quella spagnola sembrerebbe non
    scaricata.
    """
    if not lingua:
        from Utility import Lingua
        return "_" + Lingua.corrente_simbolo()
    return f"_{lingua}"


def che_cosa_apre(sigla: str, lingua: str | None = None) -> str:
    """Che cosa deve aprire il clic su questa pubblicazione.

    Tre risposte e una sola regola: se ha video si guarda, se ha audio si
    ascolta, altrimenti si apre il pacchetto.  Il pacchetto viene per ultimo
    perche' e' la risposta di ripiego: aprire il testo quando l'utente ha
    premuto una pubblicazione che sa di avere dei media e' come non averlo
    ascoltato.

    STA QUI E NON IN DUE SCHERMATE
    ------------------------------
    La usano sia la lista degli Scaricati sia i Preferiti della Home, e
    prima stava in entrambe.  Due copie di una regola che sceglie cosa mostrare
    all'utente sono due posti che possono divergere: la stessa pubblicazione
    nella sezione Scaricati apre una cosa e nei Preferiti un'altra, e non si
    capisce quale delle due sia quella giusta.

    Il nome del pacchetto e' costruito con la stessa regola di
    ``pub_dir_name``, quindi un libro (`sigla_I`) e un periodico
    (`sigla_I_202601`) si cercano come li cerca tutto il resto del programma.
    Un Preferito che e' un numero della Torre di Guardia non ha tracce: il
    pacchetto non c'e' con quel nome e si apre il testo, che e' la risposta
    giusta per un periodicolo.
    """
    # Si prova il nome semplice, `sigla_lingua`.  Un periodico ha l'anno nel
    # nome (`sigla_I_202601`) e non ha tracce dentro, quindi indovinarlo non
    # serve a niente: si cerca il libro e si risponde "pubblicazione".
    audio, video = media_sul_disco(sigla, lingua)
    if video:
        return "video"
    if audio:
        return "audio"
    return "pubblicazione"


def tipo_nel_pacchetto(cartella: Path) -> str | None:
    """La parola `PublicationType` del pacchetto, o None.

    Vale solo quando il catalogo non c'e': con il catalogo la sezione dei
    scaricati legge il `publicationTypeId` vero, che e' un numero e sa a che
    gruppo appartiene.  Qui si legge la parola, perche' e' tutto quello che il
    pacchetto sa dire.

    La parola e' grezza e va tradotta in un gruppo dal chiamante, e solo per
    le tre che sono state misurate: vedi `DownloadsView.gruppo_di`.
    """
    import sqlite3

    nome = cartella.name
    database = cartella / "contents" / f"{nome}.db"
    if not database.is_file():
        return None
    try:
        connessione = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        riga = connessione.execute(
            "SELECT PublicationType FROM Publication LIMIT 1").fetchone()
    except sqlite3.Error:
        return None
    finally:
        connessione.close()
    return str(riga[0]) if riga and riga[0] else None


#: Il simbolo della famiglia «Esaminiamo le Scritture ogni giorno».
#:
#: **Non e' un indovinare**: e' il campo `UndatedSymbol` del pacchetto
#: `es26_I`, misurato, e lo stesso pacchetto lo ripete in
#: `PublicationCategorySymbol`.  Entrambi valgono `es`, quindi la famiglia e'
#: nota senza scrivere la sigla di nessun anno.
#:
#: Serve perche' la sigla cambia ogni anno — `es26` nel 2026, e quella
#: dell'anno dopo non si sa quale e' — mentre la famiglia no.  E senza la
#: famiglia non c'e' modo di sapere quale delle pubblicazioni scaricate e' quella
#: giusta: sono tutte libri con un titolo che comincia uguale.
SIMBOLO_ESAMINIAMO = "es"

#: La parola che precede la scrittura dell'anno, in italiano.
#:
#: Il pacchetto scrive la riga cosi':
#:
#:     Scrittura dell'anno: “Felici quelli che sono consapevoli del loro
#:     bisogno spirituale” (Matteo 5:3)
#:
#: e si prende **solo quello che viene dopo i due punti**, che e' quello che
#: l'utente vuole vedere: la frase e il riferimento biblico.
#:
#: Le parole scritte sono l'apostrofo tipografico (`l’anno`, non `l'anno`) e le
#: virgolette caporali (`“…”`), quindi qui sono gli stessi caratteri: non si
#: scrive `Scrittura dell'anno` perche' quella spelled cosi' non esiste e la
#: ricerca non troverebbe niente — silenziosamente, che e' il modo peggiore.
ETICHETTA_ANNO = "Scrittura dell’anno:"


def _il_pacchetto_di_oggi(oggi: int) -> Path | None:
    """La cartella del pacchetto che copre il giorno `oggi`, o `None`.

    `oggi` e' la data come numero intero, `20261005`.

    IL COME' E' IL DATO, E NON UN CALCOLO
    -----------------------------------
    Il pacchetto scrive da solo da che data a che data copre, e sono due
    numeri:

        FirstDatedTextDateOffset  20260101
        LastDatedTextDateOffset   20261231

    Quindi non si indovina l'anno dalla sigla e non si cerca «un pacchetto che
    assomiglia a quello dell'anno scorso»: si chiede a ogni pacchetto
    scaricato se oggi e' nel suo intervallo, e l'unico che risponde di si' e'
    quello giusto.  E' l'unico modo che regge quando l'anno cambia, che e'
    esattamente il caso che e' stato chiesto.

    Il confronto e' fatto sui numeri e non sulle stringhe: `20261005` come
    intero si ordina come le date, e come testo si orderebbe per lo stesso
    motivo solo finche' tutte le date hanno le stesse cifre — che e' vero ma e'
    una coincidenza, non una regola.
    """
    from Utility import Lingua

    lingua = Lingua.corrente_simbolo()
    suffisso = f"_{lingua}"
    for cartella in scaricate():
        if not cartella.name.endswith(suffisso):
            continue
        connessione = _connect_path(cartella / "contents" / f"{cartella.name}.db")
        if connessione is None:
            continue
        try:
            riga = connessione.execute(
                "SELECT UndatedSymbol, FirstDatedTextDateOffset,"
                " LastDatedTextDateOffset FROM Publication LIMIT 1"
            ).fetchone()
        except sqlite3.Error:
            continue
        finally:
            connessione.close()
        if not riga:
            continue
        simbolo, primo, ultimo = riga
        if str(simbolo or "") != SIMBOLO_ESAMINIAMO:
            continue
        try:
            if int(primo) <= oggi <= int(ultimo):
                return cartella
        except (TypeError, ValueError):
            # Il pacchetto non dice le date: non si sceglie a caso, si lascia
            # che un altro pacchetto risponda.
            continue
    return None


def scrittura_dell_anno(oggi: int | None = None) -> str:
    """La «Scrittura dell'anno» di oggi, o "" se non c'e'.

    Vuota significa una delle due cose che possono mancare, e sono diverse:

    - la pubblicazione dell'anno non e' stata scaricata;
    - c'e', ma la riga dentro non si trova piu' (il pacchetto e' cambiato).

    Il chiamante distingue le due guardando se l'ha scaricata: vedi
    `esaminiamo_il_pacchetto`.
    """
    if oggi is None:
        oggi = time.strftime("%Y%m%d")
    cartella = _il_pacchetto_di_oggi(int(oggi))
    if cartella is None:
        return ""
    return _la_riga_nel_pacchetto(cartella)


def esaminiamo_il_pacchetto(oggi: int | None = None) -> Path | None:
    """La cartella del pacchetto «Esaminiamo» di oggi, o `None`.

    Serve al chiamante per dire all'utente la differenza fra «non l'hai
    scaricata» e «l'hai scaricata ma non c'e' la riga»: sono due problemi che
    si risolvono in due modi opposti, e la stessa frase per entrambi lascia
    l'utente a indovinare.
    """
    if oggi is None:
        oggi = time.strftime("%Y%m%d")
    return _il_pacchetto_di_oggi(int(oggi))


def _la_riga_nel_pacchetto(cartella: Path) -> str:
    """La riga della «Scrittura dell'anno» dentro il pacchetto, o "".

    PERCHE' SI LEGGE L'HTML E NON IL DATABASE
    -----------------------------------------
    Nel database ci sono la struttura e i numeri, non le parole: la tabella
    `DocumentParagraph` ha `ParagraphId, DocumentId, ParagraphIndex,
    ParagraphNumberLabel, BeginPosition, EndPosition` e basta.  Le parole sono
    negli HTML in `Documents_I/`, che e' anche da li' che la sezione Articolo
    prende il testo — quindi e' lo stesso dato che il programma mostra gia'.

    I documenti che si leggono sono i primi quattro, e non tutti: quello con
    la riga e' la pagina degli editori, che sta in fondo ai documenti di
    apertura.  Leggerne 122 a ogni avvio sarebbe spreco, e la riga non e'
    dentro i testi giornalieri.

    E non si cerca un numero di documento fisso: quello che la contiene oggi ha
    `DocumentId` 1, ma e' un numero che cambia da un anno all'altro, e un
    numero scritto a mano che smette di andare bene non se ne accorge.
    """
    try:
        connessione = _connect_path(cartella / "contents" / f"{cartella.name}.db")
    except (AttributeError, TypeError, ValueError):
        return ""
    if connessione is None:
        return ""
    try:
        righe = connessione.execute(
            "SELECT MepsDocumentId FROM Document ORDER BY DocumentId LIMIT 4"
        ).fetchall()
    except sqlite3.Error:
        return ""
    finally:
        connessione.close()

    for (meps_id,) in righe:
        testo = _la_riga_in_un_documento(cartella, int(meps_id or 0))
        if testo:
            return testo
    return ""


def _la_riga_in_un_documento(cartella: Path, meps_id: int) -> str:
    """Il testo dopo «Scrittura dell'anno:» dentro un documento, o ""."""
    if meps_id <= 0:
        return ""
    # La cartella dei documenti segue la lingua scelta dall'utente, e non e'
    # quella scritta a mano in `ARTICLES_DIR`: con la lingua spagnola il
    # pacchetto e' `es26_S` e i documenti stanno in `Documents_S`.  Usando la
    # constante, il lettore andrebbe a leggere i documenti italiani anche per
    # il pacchetto spagnolo, e troverebbero la pagina degli editori di un anno
    # sbagliato senza dire niente.
    cartella_documenti = "Documents" + _lingua_cartella(None)
    percorso = (get_documents_directory() / cartella_documenti
                / f"{meps_id}.html")
    try:
        grezzo = percorso.read_text(encoding="utf-8")
    except OSError:
        return ""
    posizione = grezzo.find(ETICHETTA_ANNO)
    if posizione < 0:
        return ""
    # Il pezzo dopo i due punti, fino alla fine del paragrafo.  Si prende il
    # paragrafo e non il resto del file perche' la pagina degli editori
    # contiene anche la nota sul dono, la copyright e il traduttore: prese
    # tutte, finirebbero nella finestra del monitor secondario.
    fine = grezzo.find("</p>", posizione)
    if fine < 0:
        fine = len(grezzo)
    pezzo = grezzo[posizione + len(ETICHETTA_ANNO):fine]
    return _solo_testo(pezzo).strip()


def _solo_testo(html: str) -> str:
    """Il testo di un pezzo di HTML, con gli spazi ricostruiti.

    Il pezzo contiene un collegamento al versetto:

        “Felici quelli che sono consapevoli del loro bisogno spirituale”
        (<a href="…" class="b">Matteo 5:3</a>)

    Il collegamento si tiene, e si tiene **senza** il trattino: il trattino
    dentro le parentesi e' nel collegamento e verrebbe fuori cosi'
    `-Matteo 5:3`.  Quindi i due spazi che stanno intorno al trattino vengono
    tolti via per primi, quando il pezzo e' gia' diventato testo.
    """
    senza = re.sub(r"<[^>]+>", "", html)
    senza = (senza.replace("&amp;", "&").replace("&lt;", "<")
             .replace("&gt;", ">").replace("&quot;", '"')
             .replace("&#39;", "'").replace("&nbsp;", " "))
    # I due spazi intorno al trattino del collegamento: via per primi, perche'
    # poi `split` metterebbe li' uno spazio che non si vuole.
    senza = re.sub(r"\s*-\s*", " ", senza)
    return " ".join(senza.split())


def _il_documento_del_giorno(oggi: int) -> tuple[Path, int] | None:
    """Il documento del mese che contiene il testo di `oggi`, e il suo numero.

    Ritorna `(cartella del pacchetto, MepsDocumentId)` o `None`.

    LA TABELLA `DatedText` E' IL MAPPETTO DEI GIORNI
    ----------------------------------------------
    Un pacchetto di «Esaminiamo le Scritture ogni giorno» ha una riga per ogni
    giorno dell'anno — 365 righe misurate — e ognuna dice quale documento
    contiene quel giorno:

        Link                   'p/I:1102026209/14-16'
        FirstDateOffset        20261005
        LastDateOffset         20261005

    Il `Link` contiene il `MepsDocumentId` del documento del mese (quindi
    Ottobre, che e' `1102026209`) e gli ordinali dei paragrafi.

    PERCHE' GLI ORDINALI NON SERVONO
    --------------------------------
    Sono la cosa che sembra giusta e non lo e'.  Misurato: per il 5 di ottobre
    la riga dice `14-16`, e il paragrafo **14** e' meta' della frase
    «Geova è colui che esamina i cuori»: i due numeri sono di due conteggi
    diversi e tagliando l'HTML a quegli offset viene fuori un pezzo mozzato.
    Per questo il documento si cerca e dentro si prende il paragrafo giusto,
    che si riconosce da solo — vedi `versetto_del_giorno`.
    """
    cartella = _il_pacchetto_di_oggi(oggi)
    if cartella is None:
        return None
    connessione = _connect_path(cartella / "contents" / f"{cartella.name}.db")
    if connessione is None:
        return None
    try:
        riga = connessione.execute(
            "SELECT Link FROM DatedText WHERE FirstDateOffset <= ? "
            "AND LastDateOffset >= ? LIMIT 1", (oggi, oggi)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connessione.close()
    if not riga:
        return None
    # 'p/I:1102026209/14-16' -> '1102026209'.  Con `split` e non con una
    # espressione regolare: dentro puo' esserci un ':' nella lingua, e il
    # numero che serve e' quello dopo l'ultimo ':' prima della '/'.
    pezzo = str(riga[0] or "")
    numero = ""
    for parte in pezzo.split("/"):
        if ":" in parte:
            numero = parte.rsplit(":", 1)[-1]
            break
    try:
        return cartella, int(numero)
    except ValueError:
        return None


def pagina_del_giorno(oggi: int | None = None) -> dict:
    """Tutto quello che serve per aprire la pagina di oggi, in un dizionario.

    Ritorna `{}` se la pubblicazione non e' scaricata, e altrimenti:

        {"documentId": 1102026209, "ancora": "p15", "titolo": "Ottobre"}

    PERCHE' SERVE ANCHE L'ANCORA E NON BASTA IL DOCUMENTO
    ------------------------------------------------------
    Il documento del mese contiene **tutti** i giorni del mese: Ottobre ha 31
    paragrafi `themeScrp`, uno per giorno.  Aprendo il documento si comincia
    dal primo giorno, non da oggi — e allora si aprirebbe la pagina sbagliata
    con la data giusta sopra, che e' il modo peggiore di sbagliare.

    L'ancora e' l'`id` HTML del paragrafo di oggi, cioe' `p15` per il 5 di
    ottobre.  Non e' un numero calcolato: e' l'`id` che c'era gia' nel file e
    che si legge insieme al testo, quindi non puo' sbagliare numero rispetto a
    quello che si sta mostrando.
    """
    if oggi is None:
        oggi = time.strftime("%Y%m%d")
    trovato = _il_documento_del_giorno(int(oggi))
    if trovato is None:
        return {}
    cartella, meps_id = trovato
    ancore = _le_ancore_del_mese(cartella, meps_id)
    try:
        giorno = int(str(oggi)[6:8])
    except ValueError:
        return {}
    if not 1 <= giorno <= len(ancore):
        return {}
    return {"documentId": int(meps_id), "ancora": ancore[giorno - 1],
            "titolo": _titolo_del_documento(cartella, meps_id)}


def _le_ancore_del_mese(cartella: Path, meps_id: int) -> list:
    """Gli `id` dei paragrafi del versetto, in ordine di giorno."""
    testo = _il_documento_html(cartella, meps_id)
    if not testo:
        return []
    return re.findall(r'<p id="(p\d+)"[^>]*class="themeScrp"', testo)


def _il_documento_html(cartella: Path, meps_id: int) -> str:
    """L'HTML di un documento del pacchetto, o "".

    Il pacchetto serve per scegliere la lingua della cartella dei documenti:
    `Documents_I` sta accanto a `es26_I`, e con la lingua sbagliata non
    esiste.
    """
    cartella_documenti = "Documents" + _lingua_cartella(None)
    try:
        return (get_documents_directory() / cartella_documenti
                / f"{meps_id}.html").read_text(encoding="utf-8")
    except OSError:
        return ""


def _titolo_del_documento(cartella: Path, meps_id: int) -> str:
    """Il titolo del documento, o ""."""
    connessione = _connect_path(cartella / "contents" / f"{cartella.name}.db")
    if connessione is None:
        return ""
    try:
        riga = connessione.execute(
            "SELECT Title FROM Document WHERE MepsDocumentId = ? LIMIT 1",
            (meps_id,)).fetchone()
    except sqlite3.Error:
        return ""
    finally:
        connessione.close()
    return str(riga[0]) if riga and riga[0] else ""


def versetto_del_giorno(oggi: int | None = None) -> str:
    """Il versetto di oggi, cioe' la prima riga della pagina del giorno.

    Ogni giorno del mese ha due paragrafi: uno con classe `themeScrp`, che e' il
    **versetto** con il riferimento bibrico fra parentesi, e uno con classe
    `sb`, che e' il commento.  Qui si prende solo il versetto, perche' e' la
    riga breve che si legge; il commento sono righe e righe e non starebbe
    li'.

    MISURATO SU UN MESE INTERO
    --------------------------
    Il riconoscimento non e' «il paragrafo numero 5 del documento»: e' «il
    quinto paragrafo di classe `themeScrp`».  Funziona per tutti i giorni
    provati, e sono stati sei, compresi gli ultimi del mese:

        1 ottobre   ->  'Starò di vedetta in attesa di Geova (Mic. 7:7)'
        2 ottobre   ->  'Dio rivela i segreti (Dan. 2:28)'
        4 ottobre   ->  'Tengo di continuo Geova davanti a me. Non sarò mai
                         scosso, perché egli è alla mia destra (Sal. 16:8)'
        5 ottobre   ->  'Geova è colui che esamina i cuori (Prov. 17:3)'
        31 ottobre  ->  'Geova richiede devozione esclusiva (…)'
        14 febbraio ->  'Pensateci voi a dar loro qualcosa (…)'

    Il numero del giorno serve come indice fra questi paragrafi, e non come
    indice fra tutti: nel documento del mese ci sono anche i titoli, i numeri
    di pagina e i paragrafi del commento, e il quinto paragrafo **del mese** non
    e' il quinto paragrafo del file.
    """
    if oggi is None:
        oggi = time.strftime("%Y%m%d")
    trovato = _il_documento_del_giorno(int(oggi))
    if trovato is None:
        return ""
    cartella, meps_id = trovato
    cartella_documenti = "Documents" + _lingua_cartella(None)
    try:
        grezzo = (get_documents_directory() / cartella_documenti
                  / f"{meps_id}.html").read_text(encoding="utf-8")
    except OSError:
        return ""
    # Solo i paragrafi con classe `themeScrp`, nel loro ordine: e' l'ordine dei
    # giorni.  La classe e' un attributo suo e significa «scr.itura del
    # d[i]», quindi non e' una convenzione di questo programma: e' il pacchetto
    # che dice quale dei suoi paragrafi e' il versetto del giorno.
    righe = re.findall(
        r'<p id="p\d+"[^>]*class="themeScrp"[^>]*>(.*?)</p>', grezzo, re.S)
    try:
        giorno = int(str(oggi)[6:8])
    except ValueError:
        return ""
    if not 1 <= giorno <= len(righe):
        return ""
    return _solo_testo(righe[giorno - 1]).strip()


def sigla_del_giorno(anno: int | None = None) -> str:
    """La sigla del pacchetto «Esaminiamo» dell'anno, o "".

    Serve al tasto che scarica: senza la sigla non si sa cosa scaricare.

    LA RICERCA E' SUL CATALOGO, E NON SULL'ANNO NEL TITOLO
    -------------------------------------------------------
    Il catalogo ha la tabella `PublicationRootKey`, che mappa la sigla
    all'anno.  Misurato:

        es20  2019        es23  2022
        es21  2020        es24  2023
        es22  2021        es25  2024
                           es26  2025

    L'anno e' quello **precedente** a quello del titolo — `es26` e' l'edizione
    del 2026 e porta `RootYear` 2025 — quindi per il 2026 si cerca `2025`.  E'
    un fatto del pacchetto, non una convenzione: `JWPubManager.leggi_pubblicazione`
    lo legge anche lei, e i due posti non possono dire cose diverse.

    `Language` e' zero su tutte le righe, quindi la sigla non dipende dalla
    lingua e non si cerca un numero di lingua che non c'e'.

    Se l'edizione di quell'anno non e' ancora nel catalogo si restituisce "",
    e il chiamante lo dice all'utente.  **Non** si indovina la sigla mettendo
    `es` davanti all'anno: e' cosi' che funziona oggi, e se un domani la sigla
    non seguisse piu' quella regola si scaricherebbe la pubblicazione sbagliata
    senza che nessuno lo dica.
    """
    if anno is None:
        anno = time.localtime().tm_year
    database = get_documents_directory() / "catalog.db"
    if not database.is_file():
        return ""
    try:
        connessione = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return ""
    try:
        riga = connessione.execute(
            "SELECT Symbol FROM PublicationRootKey "
            "WHERE Symbol GLOB ? AND Year = ? LIMIT 1",
            (SIMBOLO_ESAMINIAMO + "[0-9][0-9]", int(anno) - 1)).fetchone()
    except sqlite3.Error:
        return ""
    finally:
        connessione.close()
    return str(riga[0]) if riga and riga[0] else ""
