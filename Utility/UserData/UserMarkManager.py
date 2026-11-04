#
#  UserMarkManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Gli ``UserMark``: il segno che una sottolineatura e' stata fatta.

Un ``UserMark`` e' (colore, location).  Il *dove* dentro il testo non e'
qui, sta in ``BlockRange``: questo e' solo il segnaposto, cosi' che due
sottolineature dello stesso capitolo abbiano due numeri diversi anche se hanno
lo stesso colore.

La guida e' un UUID, come nel progetto originale.  Serve a poter sincronizzare
due backup senza confondere i segnaposto che per caso hanno lo stesso numero.
"""
from __future__ import annotations

import uuid

import sqlite3

from Utility.Structures.Paths import Paths


def _connetti() -> sqlite3.Connection | None:
    Paths.prepare()
    try:
        return sqlite3.connect(str(Paths.db_path))
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


class UserMarkManager:

    @staticmethod
    def add_user_mark(color: int, location_id: int, lang: int = 4) -> int:
        """Crea un segnaposto e restituisce il suo ``UserMarkId``.  0 se fallisce."""
        mark_guid = str(uuid.uuid4())
        connessione = _connetti()
        if connessione is None:
            return 0
        last_id = 0
        try:
            cursore = connessione.execute(
                """
                INSERT INTO UserMark (ColorIndex, LocationId, StyleIndex,
                                      UserMarkGuid, Version)
                VALUES (?, ?, 0, ?, 1);
                """,
                (color, location_id, mark_guid),
            )
            connessione.commit()
            last_id = cursore.lastrowid or 0
        except sqlite3.Error as errore:
            print(f"Error: {errore} ⚠️")
        finally:
            connessione.close()
        return last_id

    @staticmethod
    def get_user_mark(location_id: int) -> list:
        """Tutti i segnaposto di una posizione."""
        from Utility.Structures.Generals import UserMark

        user_marks: list[UserMark] = []
        connessione = _connetti()
        if connessione is None:
            return user_marks
        try:
            righe = connessione.execute(
                "SELECT UserMarkId, ColorIndex FROM UserMark WHERE LocationId = ?;",
                (location_id,),
            )
            for mark_id, colore in righe:
                user_marks.append(UserMark(ID=mark_id, color=colore))
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return user_marks

    @staticmethod
    def remove_user_mark(user_mark_id: int) -> None:
        """Toglie un segnaposto.  Se non c'e', non succede niente."""
        connessione = _connetti()
        if connessione is None:
            return
        try:
            connessione.execute(
                "DELETE FROM UserMark WHERE UserMarkId = ?;", (user_mark_id,)
            )
            connessione.commit()
        except sqlite3.Error as errore:
            print(f"Error {errore} ⚠️")
        finally:
            connessione.close()