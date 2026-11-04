#
#  BookmarkManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 21/10/26.
#

"""I segnalibri: un posto nel testo a cui tornare.

UN SEGNALIBRO NON E' UNA SOTTOLINEATURA
----------------------------------------
La sottolineatura dice «questo testo mi interessa».  Il segnalibro dice
«sono arrivato qui, e voglio ritrovare il punto»: non ha bisogno di una
selezione, e infatti si mette anche solo stando fermi su un paragrafo.  Le
due cose convivono nella stessa tabella ``Bookmark`` del database originale,
che ha gia' tutto quello che serve: la posizione, il titolo, il testo di
anteprima e il paragrafo.

IL COLORE
---------
La tabella originale non ha un colore per il segnalibro.  Qui si aggiunge la
colonna ``ColorIndex`` con un ``ALTER TABLE``: i database creati prima non
l'hanno, e le righe che ci sono gia' prendono il colore 1.  Si fa **una volta
sola**, quando si apre il database: non e' una migrazione da lanciare a mano.
"""
from __future__ import annotations

import sqlite3

from Utility.Structures.Generals import Publication, SavedItem
from Utility.Structures.Paths import Paths
from Utility.UserData.LocationManager import LocationManager


def _connetti() -> sqlite3.Connection | None:
    Paths.prepare()
    try:
        connessione = sqlite3.connect(str(Paths.db_path))
        _assicura_colonne(connessione)
        return connessione
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


def _assicura_colonne(connessione: sqlite3.Connection) -> None:
    """Aggiunge ``ColorIndex`` a ``Bookmark`` se il database e' vecchio."""
    colonne = {riga[1] for riga in connessione.execute("PRAGMA table_info(Bookmark)")}
    if "ColorIndex" not in colonne:
        connessione.execute(
            "ALTER TABLE Bookmark ADD COLUMN ColorIndex INTEGER NOT NULL DEFAULT 1")
        connessione.commit()


def _titolo_di_riserva(sigla: str, documento: int, libro: int,
                       capitolo: int) -> str:
    """Un titolo leggibile quando la riga non ne ha uno salvato."""
    if libro and capitolo:
        return f"{sigla or 'Bibbia'} — libro {libro}, capitolo {capitolo}"
    return f"{sigla or 'Pubblicazione'} — documento {documento}"


class BookmarkManager:

    @staticmethod
    def add_bookmark(pub: Publication, document_id: int | None, identifier: int,
                     title: str, snippet: str = "", color: int = 1) -> int:
        """Scrive un segnalibro e restituisce il suo numero (0 se fallisce).

        ``identifier`` e' il paragrafo per una pubblicazione e il versetto per
        la Bibbia, cioe' la stessa cosa che ``BlockRange.Identifier`` dice per
        le sottolineature: aprendo il segnalibro si arriva allo stesso punto.

        ``PublicationLocationId`` e' messo uguale a ``LocationId``.  Il
        database originale lo usa per il segnalibro «di pubblicazione», ma
        qui non c'e' una riga separata per la pubblicazione intera: il
        segnalibro punta sempre a un punto preciso, che e' quello che serve.
        """
        LocationManager.add_location(pub=pub, document_id=document_id)
        location_id = LocationManager.get_location(pub=pub, document_id=document_id)
        if not location_id:
            print("Segnalibro non salvato: manca la Location ⚠️")
            return 0

        connessione = _connetti()
        if connessione is None:
            return 0
        try:
            slot = connessione.execute(
                "SELECT COALESCE(MAX(Slot), 0) + 1 FROM Bookmark"
                " WHERE PublicationLocationId = ?;", (location_id,)
            ).fetchone()[0]
            tipo = 2 if pub.isBible else 1
            cursore = connessione.execute(
                """
                INSERT INTO Bookmark (LocationId, PublicationLocationId, Slot,
                                      Title, Snippet, BlockType,
                                      BlockIdentifier, ColorIndex)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (location_id, location_id, slot,
                 title or "Segnalibro", snippet or None,
                 tipo, int(identifier or 0), max(1, int(color or 1))),
            )
            connessione.commit()
            print(f"Segnalibro aggiunto 🔖 ({title})")
            return int(cursore.lastrowid or 0)
        except sqlite3.Error as errore:
            print(f"Errore salvataggio segnalibro ⚠️  {errore}")
            return 0
        finally:
            connessione.close()

    @staticmethod
    def get_bookmarks(pub: Publication | None = None) -> list[SavedItem]:
        """Tutti i segnalibri, o solo quelli di una pubblicazione.

        Si legge la tabella e la ``Location``: il testo e il titolo sono nella
        riga del segnalibro, quindi l'elenco resta uguale anche se il
        pacchetto non e' piu' sul disco.
        """
        elementi: list[SavedItem] = []
        connessione = _connetti()
        if connessione is None:
            return elementi

        query = """
            SELECT Bookmark.BookmarkId, Bookmark.Title, Bookmark.Snippet,
                   Bookmark.ColorIndex, Bookmark.BlockIdentifier,
                   Location.KeySymbol, Location.MepsLanguage,
                   Location.IssueTagNumber, Location.DocumentId,
                   Location.BookNumber, Location.ChapterNumber
            FROM Bookmark
            JOIN Location ON Location.LocationId = Bookmark.LocationId
        """
        parametri: tuple = ()
        if pub is not None:
            query += """
                WHERE Location.KeySymbol = ? AND Location.MepsLanguage = ?
                  AND Location.IssueTagNumber = ?
            """
            parametri = (pub.keySymbol, pub.mepsLanguageId, pub.issueTagNumber)
        query += " ORDER BY Bookmark.BookmarkId DESC;"

        try:
            righe = connessione.execute(query, parametri).fetchall()
        except sqlite3.Error as errore:
            print(f"Errore lettura segnalibri ⚠️  {errore}")
            connessione.close()
            return elementi

        for (bookmark_id, titolo, snippet, colore, identifier, sigla, lingua,
             numero, documento, libro, capitolo) in righe:
            documento = int(documento or 0)
            libro = int(libro or 0)
            capitolo = int(capitolo or 0)
            elementi.append(SavedItem(
                kind="segnalibro",
                ID=int(bookmark_id),
                title=(titolo or _titolo_di_riserva(sigla or "", documento,
                                                    libro, capitolo)),
                snippet=(snippet or "").strip(),
                color=int(colore or 1),
                identifier=int(identifier or 0),
                keySymbol=sigla or "",
                mepsLanguageId=int(lingua or 0),
                issueTagNumber=int(numero or 0),
                documentId=documento,
                bookNumber=libro,
                chapterNumber=capitolo,
            ))
        connessione.close()
        return elementi

    @staticmethod
    def remove_bookmark(bookmark_id: int) -> None:
        """Toglie un segnalibro."""
        connessione = _connetti()
        if connessione is None:
            return
        try:
            connessione.execute("DELETE FROM Bookmark WHERE BookmarkId = ?;",
                                (int(bookmark_id),))
            connessione.commit()
            print("Segnalibro rimosso 🗑️")
        except sqlite3.Error as errore:
            print(f"Errore rimozione segnalibro ⚠️  {errore}")
        finally:
            connessione.close()
