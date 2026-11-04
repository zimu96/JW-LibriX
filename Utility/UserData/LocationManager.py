#
#  LocationManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Le ``Location``: dove si puo' scrivere qualcosa.

Una ``Location`` e' un capitolo (libro + capitolo, per la Bibbia) o un
documento di una pubblicazione.  E' il contenitore a cui agganciano
sottolineature e appunti, e il suo ``LocationId`` e' quello che va in
``UserMark.LocationId``.

PERCHE' C'E' IL ``WHERE NOT EXISTS``
------------------------------------
La tabella ha ``UNIQUE(BookNumber, ChapterNumber, KeySymbol, MepsLanguage,
Type)``, ma in SQLite un NULL non e' uguale a un NULL dentro un vincolo
UNIQUE.  Per il ramo delle pubblicazioni ``BookNumber`` e ``ChapterNumber``
restano NULL, quindi quel vincolo non blocca niente e due righe identiche
entrerebbero.  Il ``WHERE NOT EXISTS`` e' quello che tiene davvero uniqueness
la tabella, ed e' per questo che c'e'.

IL vincolo CHECK
----------------
Per ``Type = 0`` il database vuole o il capitolo della Bibbia (BookNumber e
ChapterNumber pieni, DocumentId NULL) o il documento di una pubblicazione
(DocumentId pieno, BookNumber e ChapterNumber NULL).  Le due colonne non
riempite devono restare NULL: non si scrive 0 al posto di "non c'e'", perche'
0 e' un numero valido e il vincolo lo accetterebbe.
"""

import sqlite3

from Utility.Structures.Generals import Publication
from Utility.Structures.Paths import Paths


def _connetti() -> sqlite3.Connection | None:
    Paths.prepare()
    try:
        return sqlite3.connect(str(Paths.db_path))
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


class LocationManager:

    @staticmethod
    def add_location(pub: Publication, document_id: int | None = None) -> None:
        """Crea la ``Location`` se non c'e' gia'.  Non fa niente se c'e'."""
        libro = pub.book or 0
        capitolo = pub.chapter or 0
        documento = document_id or 0
        connessione = _connetti()
        if connessione is None:
            return
        try:
            if pub.isBible:
                query = """
                    INSERT INTO Location (BookNumber, ChapterNumber, IssueTagNumber,
                                          KeySymbol, MepsLanguage, Type)
                    SELECT ?, ?, 0, ?, ?, 0
                    WHERE NOT EXISTS(SELECT * FROM Location
                                     WHERE BookNumber = ?
                                     AND ChapterNumber = ?
                                     AND KeySymbol = ?
                                     AND MepsLanguage = ?);
                """
                parametri = (libro, capitolo, pub.keySymbol, pub.mepsLanguageId,
                             libro, capitolo, pub.keySymbol, pub.mepsLanguageId)
            else:
                query = """
                    INSERT INTO Location (DocumentId, IssueTagNumber,
                                          KeySymbol, MepsLanguage, Type)
                    SELECT ?, ?, ?, ?, 0
                    WHERE NOT EXISTS(SELECT * FROM Location
                                     WHERE DocumentId = ?
                                     AND IssueTagNumber = ?
                                     AND KeySymbol = ?
                                     AND MepsLanguage = ?);
                """
                parametri = (documento, pub.issueTagNumber, pub.keySymbol,
                             pub.mepsLanguageId, documento, pub.issueTagNumber,
                             pub.keySymbol, pub.mepsLanguageId)

            connessione.execute(query, parametri)
            connessione.commit()
        except sqlite3.Error as errore:
            print(f"errore: {errore} ⚠️")
        finally:
            connessione.close()

    @staticmethod
    def get_location(pub: Publication, document_id: int | None = None) -> int:
        """Il ``LocationId`` di un capitolo o documento.  Se non esiste: 0.

        Il valore 0 non e' un posto buono: nessuna ``Location`` ha
        ``LocationId = 0``, quindi una sottolineatura con 0 semplicemente non
        viene trovata indietro.  Non e' una difesa, e' quello che faceva
        anche il codice originale.
        """
        connessione = _connetti()
        if connessione is None:
            return 0
        location = 0
        try:
            if pub.isBible:
                query = """
                    SELECT LocationId FROM Location
                    WHERE KeySymbol = ? AND BookNumber = ? AND ChapterNumber = ?
                    AND MepsLanguage = ?;
                """
                parametri = (pub.keySymbol, pub.book or 0, pub.chapter or 0,
                             pub.mepsLanguageId)
            else:
                query = """
                    SELECT LocationId FROM Location
                    WHERE KeySymbol = ? AND DocumentId = ? AND IssueTagNumber = ?
                    AND MepsLanguage = ?;
                """
                parametri = (pub.keySymbol, document_id or 0, pub.issueTagNumber,
                             pub.mepsLanguageId)

            riga = connessione.execute(query, parametri).fetchone()
            if riga is not None:
                location = riga[0]
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return location