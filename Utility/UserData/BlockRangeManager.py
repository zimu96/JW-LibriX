#
#  BlockRangeManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Gli ``BlockRange``: *dove* sta una sottolineatura, parola per parola.

``identifier`` e' il numero del paragrafo, ``startToken`` e ``endToken``
sono l'indice della prima e dell'ultima parola dentro quel paragrafo.  I
numeri sono indici di ``selectable``, cioe' di quei pezzi di testo che
``Files/script.js`` avvolge uno a uno.

``BlockType``: 1 per una pubblicazione, 2 per la Bibbia.  Il CHECK della
tabella obbliga il valore a essere 1 o 2, quindi non si puo' passare 0 e
aspettarsi che funzioni: fallisce e basta.

Le tre query di scrittura e le tre di lettura sono le stesse del progetto
originale, con i valori passati come parametri.
"""
from __future__ import annotations

import sqlite3

from Utility.Structures.Generals import BlockRange, Existing, Publication
from Utility.Structures.Paths import Paths


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
    """Aggiunge a ``BlockRange`` il testo e il titolo, se mancano.

    IL TESTO STA QUI, NON NEL FILE DELLA PUBBLICAZIONE
    ---------------------------------------------------
    L'elenco delle sottolineature deve restare leggibile anche dopo che la
    pubblicazione e' stata cancellata dal disco.  Rileggere il paragrafo dal
    file HTML funzionerebbe solo finche' il file c'e', e per la Bibbia
    vorrebbe dire rifare in Python la divisione in parole di ``script.js``:
    due copie della stessa regola, e la seconda sbagliata al primo caso
    strano.

    Percio' il testo si salva **quando si sottolinea**, che e' l'unico momento
    in cui e' gia' in mano a chi lo vede.  Le due colonne sono un'aggiunta:
    i database creati prima non le hanno, e ``ALTER TABLE`` le mette senza
    toccare le righe che ci sono gia'.
    """
    colonne = {riga[1] for riga in connessione.execute("PRAGMA table_info(BlockRange)")}
    if "Snippet" not in colonne:
        connessione.execute("ALTER TABLE BlockRange ADD COLUMN Snippet TEXT")
    if "Title" not in colonne:
        connessione.execute("ALTER TABLE BlockRange ADD COLUMN Title TEXT")
    connessione.commit()


class BlockRangeManager:

    @staticmethod
    def ensure_schema() -> None:
        """Prepara le colonne aggiunte, senza leggere ne' scrivere altro.

        Serve a chi legge le sottolineature **senza** passare da
        `add_block_range`: un database creato prima dell'anteprima non ha le
        colonne ``Snippet`` e ``Title``, e una lettura diretta fallirebbe
        prima che qualcuno abbia mai avuto modo di aggiungerle.
        """
        connessione = _connetti()
        if connessione is not None:
            connessione.close()

    @staticmethod
    def add_block_range(pub: Publication, identifier: int, start_token: int,
                        end_token: int, mark_id: int, snippet: str = "",
                        title: str = "") -> None:
        """Scrive una sottolineatura nuova.

        ``snippet`` e ``title`` sono il testo e il titolo del documento al
        momento della sottolineatura.  Restano nel database anche se poi la
        pubblicazione viene cancellata, cosi' l'elenco delle Ricerche continua
        a mostrare qualcosa di leggibile.
        """
        block_type = 2 if pub.isBible else 1
        connessione = _connetti()
        if connessione is None:
            return
        try:
            connessione.execute(
                """
                INSERT INTO BlockRange (BlockType, Identifier, StartToken,
                                        EndToken, UserMarkId, Snippet, Title)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (block_type, identifier, start_token, end_token, mark_id,
                 snippet or None, title or None),
            )
            connessione.commit()
        except sqlite3.Error as errore:
            print(f"Error: {errore} ⚠️")
        finally:
            connessione.close()

    @staticmethod
    def get_existing_block_range(block_range: BlockRange, location_id: int) -> list[Existing]:
        """Le sottolineature che toccano la stessa frase.

        La condizione e' "sovrappongono in qualche modo": una delle due estremita'
        cade dentro l'altra, oppure la nuova sta tutta dentro la vecchia.  Sono
        tre casi invece di uno perche' i due estremi devono stare in una sola
        riga WHERE, e senza la terza il caso "la nuova e' dentro la vecchia"
        non verrebbe mai trovato.
        """
        connessione = _connetti()
        if connessione is None:
            return []
        esistenti: list[Existing] = []
        try:
            righe = connessione.execute(
                """
                SELECT BlockRange.UserMarkId, BlockRange.StartToken,
                       BlockRange.EndToken, ColorIndex
                FROM BlockRange
                JOIN UserMark ON BlockRange.UserMarkId = UserMark.UserMarkId
                WHERE BlockRange.Identifier = ?
                AND UserMark.LocationId = ?
                AND ((EndToken BETWEEN ? AND ?)
                  OR (StartToken BETWEEN ? AND ?)
                  OR (StartToken >= ? AND EndToken <= ?));
                """,
                (block_range.identifier, location_id,
                 block_range.startToken, block_range.endToken,
                 block_range.startToken, block_range.endToken,
                 block_range.startToken, block_range.endToken),
            )
            for user_mark_id, start_token, end_token, color_index in righe:
                esistenti.append(Existing(userMarkId=user_mark_id,
                                          startToken=start_token,
                                          endToken=end_token,
                                          colorIndex=color_index))
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return esistenti

    @staticmethod
    def get_block_range(user_mark_id: int) -> BlockRange:
        """Il blocco di un segnaposto.  Se non c'e': (-1, -1, -1).

        I tre -1 sono il segnale "non c'e' niente qui".  Non sono un numero
        buono come indice, quindi chi non controlla ottiene un blocco vuoto e
        non disegna niente, invece di disegnare a caso.
        """
        connessione = _connetti()
        if connessione is None:
            return BlockRange(identifier=-1, startToken=-1, endToken=-1)
        block_range = BlockRange(identifier=-1, startToken=-1, endToken=-1)
        try:
            riga = connessione.execute(
                "SELECT Identifier, StartToken, EndToken FROM BlockRange WHERE UserMarkId = ?;",
                (user_mark_id,),
            ).fetchone()
            if riga is not None:
                block_range = BlockRange(identifier=riga[0], startToken=riga[1],
                                        endToken=riga[2])
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return block_range

    @staticmethod
    def remove_block_range(user_mark_id: int) -> None:
        """Toglie il blocco di un segnaposto."""
        connessione = _connetti()
        if connessione is None:
            return
        try:
            connessione.execute(
                "DELETE FROM BlockRange WHERE UserMarkId = ?;", (user_mark_id,)
            )
            connessione.commit()
        except sqlite3.Error as errore:
            print(f"Error {errore} ⚠️")
        finally:
            connessione.close()

    @staticmethod
    def update_block_range(existing: Existing) -> None:
        """Allunga o accorcia un blocco esistente, senza cambiarne il colore."""
        connessione = _connetti()
        if connessione is None:
            return
        try:
            connessione.execute(
                """
                UPDATE BlockRange SET StartToken = ?, EndToken = ?
                WHERE UserMarkId = ?;
                """,
                (existing.startToken, existing.endToken, existing.userMarkId),
            )
            connessione.commit()
            print("BlockRange updated ✅")
        except sqlite3.Error as errore:
            print(f"Error {errore} ⚠️")
        finally:
            connessione.close()