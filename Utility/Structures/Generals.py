#
#  Generals.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""Le strutture dati dell'app.

Sono le stesse ``struct`` di Swift, una riga per una riga, e i campi
restano con lo stesso nome (camelCase incluso) perche' sono gli stessi dati
e devono continuare a essere leggibili nello stesso modo.

Una differenza che conta: in Swift il memberwise initializer da' ``nil`` a
un ``Optional`` che si salta.  Qui i ``dataclass`` danno ``None`` agli
``Optional`` col valore di default, quindi si puo' chiamare esattamente come
in Swift::

    Publication(ID=0, keySymbol="nwtsty", ..., title="...")   # issueTitle mancante
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class BibleBook:
    ID: int
    shortName: str
    fullName: str
    chapters: int


@dataclass
class UserMark:
    ID: int
    color: int


@dataclass
class BlockRange:
    identifier: int
    startToken: int
    endToken: int


@dataclass
class Highlight:
    userMark: UserMark
    blockRange: BlockRange


@dataclass
class Existing:
    userMarkId: int
    startToken: int
    endToken: int
    colorIndex: int


@dataclass
class Note:
    ID: int
    title: str
    content: str
    date: str = ""
    keySymbol: str = ""
    mepsLanguageId: int = 0
    issueTagNumber: int = 0
    documentId: int = 0
    bookNumber: int = 0
    chapterNumber: int = 0
    identifier: int = 0


@dataclass
class SavedItem:
    """Una sottolineatura o un segnalibro, con il posto in cui si trova.

    PERCHE' UNO SOLO E NON DUE
    ---------------------------
    Le due cose si mostrano nello stesso elenco, si aprono allo stesso modo e
    hanno bisogno degli stessi dati: titolo, testo, colore e il punto dentro la
    pubblicazione.  Tenerli in due classi quasi uguali vorrebbe dire scrivere
    due volte la griglia, il clic e il salto al punto, e il giorno che uno dei
    due cambia l'altro resterebbe indietro.

    ``kind`` vale ``"sottolineatura"`` o ``"segnalibro"``.  ``identifier`` e'
    il numero del paragrafo (``data-pid``) per le pubblicazioni e il numero del
    versetto per la Bibbia.
    """

    kind: str
    ID: int
    title: str
    snippet: str
    color: int
    identifier: int
    keySymbol: str = ""
    mepsLanguageId: int = 0
    issueTagNumber: int = 0
    documentId: int = 0
    bookNumber: int = 0
    chapterNumber: int = 0
    startToken: int = -1
    endToken: int = -1
    sottotitolo: str = ""
    scaricato: bool = True
    risolto: bool = False

    @property
    def is_bible(self) -> bool:
        return self.bookNumber > 0 and self.chapterNumber > 0


@dataclass
class Publication:
    """Una riga della tabella ``Publication`` del catalogo.

    ``issueTagNumber`` e' quello che distingue un numero della Torre di
    Guardia dagli altri: 0 per un libro, 202110 per il numero di ottobre
    2021.  Da lui dipende il nome della cartella (vedi JWPubManager).
    """
    ID: int
    keySymbol: str
    year: int
    mepsLanguageId: int
    publicationTypeId: int
    issueTagNumber: int
    title: str
    issueTitle: Optional[str] = None
    # Solo Bibbia
    isBible: bool = False
    book: Optional[int] = None
    chapter: Optional[int] = None

    @property
    def displayTitle(self) -> str:
        """Il titolo che finisce sulla barra.

        Swift lo scriveva nei tre punti dove serve
        (``[13, 14, 30].contains(pub.publicationTypeId) ? pub.issueTitle :
        pub.title``).  La regola e' una sola e sta qui dentro: i periodici
        (Svegliatevi 13, Torre di Guardia 14, guida per l'adunanza 30) hanno
        il titolo dell'uscita, tutto il resto ha il titolo della pubblicazione.
        """
        if self.publicationTypeId in (13, 14, 30):
            return self.issueTitle or ""
        return self.title


@dataclass
class Document:
    """Una riga della tabella ``Document`` dentro il .jwpub.

    Due identificatori che non coincidono mai (COME-FUNZIONA.txt sezione 2c):
    ``ID`` e' il DocumentId locale, vale dentro UN pacchetto e comincia da 0;
    ``documentId`` e' il MepsDocumentId, stabile, ed e' il numero che sta
    nella URL pubblica su wol.jw.org.  Per passare dal pacchetto al sito si
    usa ``documentId``.  Prendere l'altro e' il modo piu' veloce di sbagliare.
    """
    ID: int
    documentId: int
    title: str
    contextTitle: Optional[str] = None
