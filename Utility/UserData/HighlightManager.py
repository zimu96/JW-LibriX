#
#  HighlightManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Le sottolineature: metterle e toglierle.

Il caso difficile e' togliere.  Se la frase che vuoi togliere e' dentro una
sottolineatura piu' grande, non basta cancellare: la sottolineatura si
divide in due pezzi, e quello nuovo ha lo stesso colore del vecchio.
Togliere davvero tutto e' il caso in cui la nuova frase contiene del tutto
la vecchia: allora la vecchia sparisce.

I quattro casi, e sono tutti, perche' con due estremi ci sono solo quattro
disposizioni:

    1. la nuova dentro la vecchia, strettamente   -> si divide in due
    2. la nuova parte dal fondo della vecchia      -> si accorcia l'inizio
    3. la nuova parte dall'inizio della vecchia    -> si accorcia la fine
    4. la vecchia dentro la nuova                  -> si cancella

Il primo caso scrive due righe, gli altri una, e l'ultimo cancella.  E'
l'unico posto in cui si scrive piu' di una volta per operazione, quindi e'
l'unico dove un'istruzione sola non basta: per questo ``should_split`` e'
dentro il ciclo e non fuori.
"""

import sqlite3

from Utility.Structures.Generals import (
    BlockRange,
    Existing,
    Highlight,
    Publication,
    SavedItem,
)
from Utility.Structures.Paths import Paths
from Utility.UserData.BlockRangeManager import BlockRangeManager
from Utility.UserData.LocationManager import LocationManager
from Utility.UserData.UserMarkManager import UserMarkManager


def _riscrivi(esistente: Existing, start_token: int, end_token: int) -> None:
    """Allunga o accorcia un blocco esistente, tenendone il colore.

    Si rilegge ``BlockRange`` con due estremi nuovi: il colore non si tocca,
    perche' cambiare il colore senza chiederlo sarebbe una sorpresa.
    """
    BlockRangeManager.update_block_range(existing=Existing(
        userMarkId=esistente.userMarkId,
        startToken=start_token,
        endToken=end_token,
        colorIndex=esistente.colorIndex,
    ))


class HighlightManager:

    @staticmethod
    def add_highlight(color: int, new_block_range: BlockRange, pub: Publication,
                      document_id: int | None = None, snippet: str = "",
                      title: str = "") -> None:
        """Mette una sottolineatura (color > 0) o la toglie (color < 0).

        ``color == -1`` e' il cestino della barra: non un colore, un ordine.
        Per questo il segno e' controllato sul valore e non sul nome.

        ``snippet`` e ``title`` sono il testo selezionato e il titolo del
        documento: si salvano con la sottolineatura perche' l'elenco delle
        Ricerche li deve mostrare anche quando il file non c'e' piu'.
        """
        # La Location deve esserci prima del segnaposto: se manca,
        # `get_location` restituirebbe 0 e la sottolineatura finirebbe su una
        # posizione che non esiste, senza nessun errore.  Crearla qui rende
        # `add_highlight` indipendente dall'ordine di chiamata.
        LocationManager.add_location(pub=pub, document_id=document_id)
        location_id = LocationManager.get_location(pub=pub, document_id=document_id)
        esistenti = BlockRangeManager.get_existing_block_range(
            block_range=new_block_range, location_id=location_id
        )

        if color > 0:
            # Colorare allargando: se la nuova frase tocca una vecchia, le due
            # diventano una sola, dalla prima parola all'ultima.
            new_start_token = new_block_range.startToken
            new_end_token = new_block_range.endToken
            for esistente in esistenti:
                new_start_token = min(esistente.startToken, new_start_token)
                new_end_token = max(esistente.endToken, new_end_token)
                BlockRangeManager.remove_block_range(user_mark_id=esistente.userMarkId)
                UserMarkManager.remove_user_mark(user_mark_id=esistente.userMarkId)
            mark_id = UserMarkManager.add_user_mark(color=color, location_id=location_id)
            BlockRangeManager.add_block_range(pub=pub,
                                              identifier=new_block_range.identifier,
                                              start_token=new_start_token,
                                              end_token=new_end_token,
                                              mark_id=mark_id,
                                              snippet=snippet,
                                              title=title)
            print("Sottolineatura aggiunta ✍🏻")
        else:
            for esistente in esistenti:
                should_split = (esistente.startToken < new_block_range.startToken
                                and esistente.endToken > new_block_range.endToken)
                if should_split:
                    # Caso 1: la nuova sta dentro la vecchia.  Si tiene il pezzo
                    # di sinistra e si crea il pezzo di destra, stesso colore.
                    _riscrivi(esistente, esistente.startToken,
                               new_block_range.startToken - 1)
                    mark_id = UserMarkManager.add_user_mark(
                        color=esistente.colorIndex, location_id=location_id
                    )
                    BlockRangeManager.add_block_range(pub=pub,
                                                      identifier=new_block_range.identifier,
                                                      start_token=new_block_range.endToken + 1,
                                                      end_token=esistente.endToken,
                                                      mark_id=mark_id)
                elif (new_block_range.startToken <= esistente.startToken
                      and new_block_range.endToken >= esistente.startToken
                      and new_block_range.endToken < esistente.endToken):
                    # Caso 2: la nuova parte dalla fine della vecchia.
                    _riscrivi(esistente, new_block_range.endToken + 1,
                               esistente.endToken)
                elif (new_block_range.endToken >= esistente.endToken
                      and new_block_range.startToken <= esistente.endToken
                      and new_block_range.startToken > esistente.startToken):
                    # Caso 3: la nuova parte dall'inizio della vecchia.
                    _riscrivi(esistente, esistente.startToken,
                               new_block_range.startToken - 1)
                elif (esistente.startToken >= new_block_range.startToken
                      and esistente.endToken <= new_block_range.endToken):
                    # Caso 4: la vecchia e' tutta dentro la nuova.  Via.
                    BlockRangeManager.remove_block_range(user_mark_id=esistente.userMarkId)
                    UserMarkManager.remove_user_mark(user_mark_id=esistente.userMarkId)
            print("Sottolineatura rimossa 🚮")

        # Si scrive tutto su disco prima di tornare indietro: cosi' la finestra
        # puo' essere chiusa subito dopo senza perdere niente.
        from Utility.UserData.BackupManager import BackupManager
        BackupManager.store_data_in_db()

    @staticmethod
    def get_highlight(pub: Publication, document_id: int | None = None) -> list[Highlight]:
        """Tutte le sottolineature di un capitolo o documento."""
        highlights: list[Highlight] = []
        location_id = LocationManager.get_location(pub=pub, document_id=document_id)
        for user_mark in UserMarkManager.get_user_mark(location_id=location_id):
            block_range = BlockRangeManager.get_block_range(user_mark_id=user_mark.ID)
            highlights.append(Highlight(userMark=user_mark, blockRange=block_range))
        return highlights

    @staticmethod
    def get_all_highlights() -> list[SavedItem]:
        """Tutte le sottolineature di tutte le pubblicazioni.

        PERCHE' SI LEGGE IL DATABASE E NON I FILE
        -----------------------------------------
        La sezione Ricerche deve continuare a mostrare una sottolineatura
        anche dopo che la pubblicazione e' stata cancellata.  Il testo e il
        titolo sono salvati nella riga stessa (vedi ``BlockRangeManager``),
        quindi questa lettura non apre nessun HTML e non dipende dal disco.

        Le righe piu' vecchie, fatte prima che il testo venisse salvato, non
        hanno ``Snippet``: si mostrano lo stesso, con il titolo di riserva.
        E' meglio un elenco con qualche riga senza anteprima che un elenco
        che nasconde le sottolineature fatte ieri.
        """
        elementi: list[SavedItem] = []
        Paths.prepare()
        # Le colonne dell'anteprima possono non esserci in un database
        # vecchio: la lettura e' in sola lettura, quindi la migrazione va
        # fatta prima, da chi puo' scrivere.
        BlockRangeManager.ensure_schema()
        try:
            connessione = sqlite3.connect(f"file:{Paths.db_path}?mode=ro", uri=True)
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
            return elementi

        try:
            righe = connessione.execute(
                """
                SELECT UserMark.UserMarkId, UserMark.ColorIndex,
                       BlockRange.Identifier, BlockRange.StartToken,
                       BlockRange.EndToken, BlockRange.Snippet, BlockRange.Title,
                       Location.KeySymbol, Location.MepsLanguage,
                       Location.IssueTagNumber, Location.DocumentId,
                       Location.BookNumber, Location.ChapterNumber
                FROM UserMark
                JOIN BlockRange ON BlockRange.UserMarkId = UserMark.UserMarkId
                JOIN Location ON Location.LocationId = UserMark.LocationId
                WHERE BlockRange.StartToken >= 0 AND BlockRange.EndToken >= 0
                ORDER BY UserMark.UserMarkId DESC;
                """
            ).fetchall()
        except sqlite3.Error as errore:
            print(f"Errore lettura sottolineature ⚠️  {errore}")
            connessione.close()
            return elementi

        for (mark_id, colore, identifier, inizio, fine, snippet, titolo,
             sigla, lingua, numero, documento, libro, capitolo) in righe:
            libro = libro or 0
            capitolo = capitolo or 0
            documento = documento or 0
            # Senza titolo salvato resta vuoto: lo ricostruisce `TestoSegni.completa`
            # dal documento, se e' sul disco.
            elementi.append(SavedItem(
                kind="sottolineatura",
                ID=mark_id,
                startToken=int(inizio if inizio is not None else -1),
                endToken=int(fine if fine is not None else -1),
                title=str(titolo or ""),
                snippet=(snippet or "").strip(),
                color=int(colore or 1),
                identifier=int(identifier or 0),
                keySymbol=sigla or "",
                mepsLanguageId=int(lingua or 0),
                issueTagNumber=int(numero or 0),
                documentId=int(documento),
                bookNumber=int(libro),
                chapterNumber=int(capitolo),
            ))
        connessione.close()
        return elementi