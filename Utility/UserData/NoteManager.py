#
#  NoteManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Gli appunti.

Solo la lettura, come nell'originale: la schermata mostra quello che c'e'
nella tabella ``Note``.  Nell'app originale gli appunti si scrivono dal
telefono e arrivano nel backup, non si scrivono qui dentro.
"""
from __future__ import annotations

import sqlite3

from Utility.Structures.Generals import Note
from Utility.Structures.Paths import Paths


class NoteManager:

    @staticmethod
    def get_notes() -> list[Note]:
        """Tutti gli appunti, nell'ordine in cui il database li restituisce."""
        notes: list[Note] = []
        Paths.prepare()
        try:
            connessione = sqlite3.connect(f"file:{Paths.db_path}?mode=ro", uri=True)
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
            return notes
        try:
            # Dal piu' recente al piu' vecchio: la data e' quella dell'ultima modifica
            righe = connessione.execute(
                """
                SELECT Note.NoteId, Note.Title, Note.Content, Note.LastModified,
                       Location.KeySymbol, Location.MepsLanguage, Location.IssueTagNumber,
                       Location.DocumentId, Location.BookNumber, Location.ChapterNumber,
                       Note.BlockIdentifier
                FROM Note LEFT JOIN Location ON Location.LocationId = Note.LocationId
                ORDER BY Note.LastModified DESC, Note.NoteId DESC;
                """)
            for (note_id, titolo, contenuto, data, sigla, lingua, numero, documento,
                 libro, capitolo, blocco) in righe:
                notes.append(Note(ID=note_id, title=titolo or "",
                                  content=contenuto or "", date=data or "",
                                  keySymbol=sigla or "", mepsLanguageId=int(lingua or 0),
                                  issueTagNumber=int(numero or 0),
                                  documentId=int(documento or 0), bookNumber=int(libro or 0),
                                  chapterNumber=int(capitolo or 0),
                                  identifier=int(blocco or 0)))
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        # Non si stampa il numero: `get_notes()` la chiama ogni volta che una
        # sezione guarda gli appunti, e «Trovate 0 notes ✅» compariva tre
        # volte a ogni avvio.  Zero appunti e' la normalita' per quasi tutti
        # gli utenti, quindi la riga era rumore che sembrava una verifica.
        return notes
    # ------------------------------------------------------------------
    # SCRIVERE LE NOTE
    # ------------------------------------------------------------------
    # Le note che si scrivono qui sono «indipendenti»: non stanno in un punto di
    # una pubblicazione (LocationId vuoto), come quelle della pagina di studio
    # personale dell'originale.  Il formato e' quello del database utente, quindi
    # un backup le porta con se'.

    @staticmethod
    def _scrivibile() -> "sqlite3.Connection | None":
        Paths.prepare()
        try:
            connessione = sqlite3.connect(str(Paths.db_path), timeout=30)
            connessione.execute("PRAGMA foreign_keys = ON")
            return connessione
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
            return None

    @staticmethod
    def crea(titolo: str, contenuto: str) -> int | None:
        """Una nota nuova.  Ritorna il suo id."""
        import uuid

        connessione = NoteManager._scrivibile()
        if connessione is None:
            return None
        try:
            cur = connessione.execute(
                "INSERT INTO Note (Guid, Title, Content) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), titolo, contenuto))
            connessione.commit()
            return int(cur.lastrowid)
        except sqlite3.Error as errore:
            print(f"Errore scrittura nota ⚠️  {errore}")
            return None
        finally:
            connessione.close()

    @staticmethod
    def modifica(note_id: int, titolo: str, contenuto: str) -> None:
        connessione = NoteManager._scrivibile()
        if connessione is None:
            return
        try:
            connessione.execute(
                "UPDATE Note SET Title = ?, Content = ?, "
                "LastModified = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE NoteId = ?",
                (titolo, contenuto, note_id))
            connessione.commit()
        except sqlite3.Error as errore:
            print(f"Errore scrittura nota ⚠️  {errore}")
        finally:
            connessione.close()

    @staticmethod
    def elimina(note_id: int) -> None:
        """Toglie la nota e le sue etichette."""
        connessione = NoteManager._scrivibile()
        if connessione is None:
            return
        try:
            connessione.execute("DELETE FROM TagMap WHERE NoteId = ?", (note_id,))
            connessione.execute("DELETE FROM Note WHERE NoteId = ?", (note_id,))
            connessione.commit()
        except sqlite3.Error as errore:
            print(f"Errore scrittura nota ⚠️  {errore}")
        finally:
            connessione.close()
