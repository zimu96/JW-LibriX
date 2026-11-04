#
#  DBManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""Le due query che danno il materiale alla schermata.

Da SQLite3/C a sqlite3: le query sono le stesse, ma i valori viaggiano
come parametri (``?``) e non dentro la stringa.  In Swift si faceva
``"... WHERE Document.MepsDocumentId = \\(documentNumber)"``: funziona finche'
``documentNumber`` e' un intero, e non appena qualcosa lo interrompe.  Qui
non si puo' sbagliare perche' il parametro non viene mai interpretato come SQL.

Un'altra differenza che conta: ogni funzione apre e chiude la sua connessione,
proprio come faceva ``sqlite3_open``/``sqlite3_close`` in Swift.  Non e' la
piu' veloce ma e' quella che non lascia file aperti e non si mette in mezzo
fra i thread.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility import Lingua
from Utility.Structures.Generals import BibleBook, Publication
from Utility.Stuff import Stuff

# La lingua, quando nessuno la dice.
#
# In Swift era scritta fisso 4 (= italiano) in tre posti; qui la chiede
# `Lingua`, che e' il posto unico in cui sta, e `lingua_scelta` sotto fa da
# ponte per chi non vuole saperne niente.
#
# PERCHE' LA FUNZIONE NON PUO' AVERE `4` COME VALORE PREDEFINITO
# ------------------------------------------------------------------
# Un valore predefinito in una firma viene calcolato una volta sola, quando
# il modulo viene importato.  Quindi `def get_publications(l=4)` non "usa la
# lingua scelta": usa la lingua che era scelta in quel momento, che e' sempre
# l'italiano perche' e' la prima lingua che l'app ha mai avuto.  Cambiare
# lingua dal menu non cambierebbe niente, e il difetto sarebbe invisibile:
# la funzione sembra che rispetti il default e non lo rispetta.
#
# Per questo il default e' `None` e la lingua si chiede DENTRO, al momento
# della chiamata.  `None` vuol dire "quella scelta dall'utente", e il
# ripiego (italiano, o la lingua che non c'e' piu' nel catalogo) e' gia'
# dentro `Lingua.corrente_id()`.
#
# `MEPS_LANGUAGE_ID` non c'e' piu'.  Era `4` e l'hanno letto sei file in una
# giornata; lasciare il nome con dentro un 4 fisso avrebbe tenuto vivo il
# numero che questo file voleva togliere, e il giorno della lingua nuova
# qualcuno lo avrebbe reimportato.
CATALOG_DB = "catalog.db"


def lingua_scelta(valore=None) -> int:
    """Il numero della lingua da usare: quello passato, o quello scelto."""
    if valore is None:
        return Lingua.corrente_id()
    try:
        return int(valore)
    except (TypeError, ValueError):
        return Lingua.corrente_id()


def _connect(path) -> sqlite3.Connection | None:
    """Apre il database, o None se il file non c'e' o e' illeggibile.

    IL FILE CHE MANCA NON E' UN ERRORE
    ----------------------------------
    `sqlite3.connect("file:...?mode=ro", uri=True)` non fallisce subito quando
    il file non c'e': solleva `OperationalError: unable to open database file`,
    e su un'installazione nuova — dove `catalog.db` non e' ancora scaricato —
    questo arriva come un errore.  Era il rumore che si vedeva a ogni primo
    avvio, tre volte, prima delle schermate.

    Non scaricato e' uno stato normale e la sezione lo dice gia': `PubView`
    mostra «Il catalogo delle pubblicazioni non e' stato scaricato» con il
    pulsante per scaricarlo.  Quindi qui, se il file non c'e', si esce in
    silenzio e si lascia parlare la schermata.

    Se invece il file c'e' e non si apre, quello e' un difetto vero — file
    corrotto, permessi, un'altra applicazione lo tiene — e resta scritto col
    nome del file, che serve a sapere *quale*.
    """
    try:
        esiste = Path(path).is_file()
    except (OSError, TypeError, ValueError):
        esiste = False
    if not esiste:
        return None
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {path}: {errore}")
        return None


class DBManager:

    @staticmethod
    def get_bible_books() -> list[BibleBook]:
        """I 66 libri, con il nome ripulito e il numero di capitoli.

        Il capitolo piu' alto dice quanti capitoli ha il libro: e' il modo piu'
        corto per ottenerlo e non richiede nessuna tabella dei numeri romani.
        """
        bible_books: list[BibleBook] = []
        # La cartella della Bibbia non ha nome fisso: era "nwt_I", oggi e'
        # "nwtsty_I".  Si cerca invece di indovinare.  Vedi
        # JWPubManager.bible_package.
        from Utility.JWPubManager import bible_db_path
        path = bible_db_path()
        if path is None:
            print("Non trovo il pacchetto della Bibbia ⚠️")
            return bible_books
        connessione = _connect(path)
        if connessione is None:
            return bible_books
        try:
            righe = connessione.execute(
                """
                SELECT BibleBook.BibleBookId, BibleBook.BookDisplayTitle,
                       MAX(BibleChapter.ChapterNumber)
                FROM BibleBook
                JOIN BibleChapter ON BibleBook.BibleBookId = BibleChapter.BookNumber
                GROUP BY BibleBook.BibleBookId;
                """
            )
            for book_id, full_name, chapters in righe:
                full_name = full_name or ""
                bible_books.append(
                    BibleBook(
                        ID=book_id,
                        shortName=Stuff.clear_bible_book_name(name=full_name),
                        fullName=full_name,
                        chapters=chapters,
                    )
                )
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return bible_books

    @staticmethod
    def get_publications(language_id: int | None = None) -> list[Publication]:
        """Tutte le pubblicazioni della lingua scelta, dal catalogo.

        Il catalogo non sta dentro i pacchetti: e' lo scaffale.  Un .jwpub e'
        un libro, catalog.db e' l'elenco dei libri.

        Senza `language_id` si usa la lingua scelta dall'utente: vedi
        `lingua_scelta` perche' il default non puo' essere una costante.
        """
        publications: list[Publication] = []
        language_id = lingua_scelta(language_id)
        path = get_documents_directory() / CATALOG_DB
        connessione = _connect(path)
        if connessione is None:
            return publications
        try:
            righe = connessione.execute(
                """
                SELECT Id, KeySymbol, Year, MepsLanguageId, PublicationTypeId,
                       IssueTagNumber, Title, IssueTitle
                FROM Publication
                WHERE MepsLanguageId = ?;
                """,
                (language_id,),
            )
            for (pub_id, key_symbol, year, lang, tipo, issue,
                 titolo, issue_title) in righe:
                publications.append(
                    Publication(
                        ID=pub_id,
                        keySymbol=key_symbol,
                        year=year,
                        mepsLanguageId=lang,
                        publicationTypeId=tipo,
                        issueTagNumber=issue,
                        title=titolo,
                        issueTitle=issue_title,
                    )
                )
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        # QUI NON SI STAMPA QUANTE SONO
        # --------------------------------
        # Prima c'era `print(f"{len(publications)} pubblicazioni trovate ✅")`.
        # La funzione non si chiama una volta: la chiama ogni schermata che
        # apre lo scaffale, e in un avvio sono tre, quindi la riga compariva
        # tre volte senza dire niente di nuovo — e con il ✅ sembrava un
        # successo, quindi il numero si leggeva come una verifica.
        #
        # Non e' una verifica: e' una riga di `SELECT`.  Il numero, quando
        # serve, lo dice la sezione che mostra le pubblicazioni, che e' il
        # posto dove l'utente lo sta leggendo.
        return publications

    @staticmethod
    def tipo_pubblicazione(key_symbol: str,
                           language_id: int | None = None) -> int | None:
        """Il ``publicationTypeId`` di un simbolo, o None.

        Serve a mettere una pubblicazione nel gruppo giusto — Libri,
        Opuscoli, Torre di Guardia — senza caricare tutto l'elenco.

        PERCHE' UNA FUNZIONE E NON `get_publications`
        -------------------------------------------
        `get_publications` legge 3.741 righe e costruisce 3.741 oggetti per
        arrivare a un numero.  Per un pacchetto scaricato ne basta uno, e la
        richiesta diretta costa 0,01-0,12 ms (misurato su cinque simboli)
        perche' c'e' un indice sulla tabella.

        Con la lingua dentro la WHERE e non fuori
        ------------------------------------------
        Una sigla ha piu' righe, una per lingua.  Senza il `MepsLanguageId`
        nella richiesta, sqlite ne restituisce una a caso: `sn` in italiano e
        `sn` in inglese hanno lo stesso tipo, ma non e' garantito, e un tipo
        preso a caso mette un titolo nel gruppo sbagliato senza che nulla lo
        segnali.
        """
        path = get_documents_directory() / CATALOG_DB
        connessione = _connect(path)
        if connessione is None:
            return None
        try:
            riga = connessione.execute(
                "SELECT publicationTypeId FROM Publication "
                "WHERE KeySymbol = ? AND MepsLanguageId = ? LIMIT 1",
                (key_symbol, lingua_scelta(language_id))).fetchone()
        except sqlite3.Error:
            return None
        finally:
            connessione.close()
        return int(riga[0]) if riga and riga[0] is not None else None

    @staticmethod
    def cerca_pubblicazioni(testo: str,
                            language_id: int | None = None) -> list[Publication]:
        """Le pubblicazioni il cui titolo contiene ``testo``.

        LA RICERCA LA FA IL DATABASE, NON PYTHON
        ------------------------------------------
        Il catalogo ha 320.427 pubblicazioni.  Filtrare in Python vuol dire
        leggerle tutte dal database, costruire 320.427 oggetti e buttare
        via 319.000 di quelli: qualche decimo di secondo e una memoria che
        si vede.

        Qui la domanda va al database, che ha l'indice, e tornano solo
        quelle che tornano.  Il carattere speciale del LIKE viene messo
        fuori: se l'utente scrive ``%`` o ``_`` non deve diventare un
        jolly e non deve far fallire la domanda.
        """
        testo = (testo or "").strip()
        if not testo:
            return DBManager.get_publications(language_id)

        language_id = lingua_scelta(language_id)

        # SQLite non ha ILIKE: si usa LIKE e si mette il confronto in
        # minuscolo da entrambe le parti.  In italiano non ci sono
        # differenze di maiuscole e minuscole, ma il catalogo contiene
        # anche titoli in altre lingue e li' conta.
        for carattere in ("\\", "%", "_"):
            testo = testo.replace(carattere, "")
        criterio = f"%{testo.lower()}%"

        publications: list[Publication] = []
        path = get_documents_directory() / CATALOG_DB
        connessione = _connect(path)
        if connessione is None:
            return publications
        try:
            righe = connessione.execute(
                """
                SELECT Id, KeySymbol, Year, MepsLanguageId, PublicationTypeId,
                       IssueTagNumber, Title, IssueTitle
                FROM Publication
                WHERE MepsLanguageId = ?
                  AND (LOWER(Title) LIKE ?
                       OR LOWER(IFNULL(IssueTitle, '')) LIKE ?)
                ORDER BY Title;
                """,
                (language_id, criterio, criterio),
            )
            for (pub_id, key_symbol, year, lang, tipo, issue,
                 titolo, issue_title) in righe:
                publications.append(
                    Publication(
                        ID=pub_id,
                        keySymbol=key_symbol,
                        year=year,
                        mepsLanguageId=lang,
                        publicationTypeId=tipo,
                        issueTagNumber=issue,
                        title=titolo,
                        issueTitle=issue_title,
                    )
                )
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        # Come sopra: il numero e' un risultato, non un avviso.
        return publications