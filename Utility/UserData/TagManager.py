#
#  TagManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le etichette (tag) per organizzare le note.

Nel database utente un'etichetta e' un ``Tag`` di tipo 1; e' collegata a una nota
dal ``TagMap`` (``NoteId`` + ``Position``).  Le playlist sono tag di tipo 2 e i
Preferiti il tipo 0: qui si tocca solo il tipo 1.
"""

from __future__ import annotations

import sqlite3

from Utility.Structures.Paths import Paths

TIPO_ETICHETTA = 1


def _apri() -> sqlite3.Connection | None:
    Paths.prepare()
    try:
        c = sqlite3.connect(str(Paths.db_path), timeout=30)
        c.execute("PRAGMA foreign_keys = ON")
        return c
    except sqlite3.Error:
        return None


def etichette() -> list[dict]:
    """Le etichette in ordine alfabetico, con quante note hanno."""
    c = _apri()
    if c is None:
        return []
    try:
        return [{"id": i, "nome": n, "note": k} for i, n, k in c.execute(
            "SELECT t.TagId, t.Name, COUNT(tm.TagMapId) FROM Tag t "
            "LEFT JOIN TagMap tm ON tm.TagId = t.TagId AND tm.NoteId IS NOT NULL "
            "WHERE t.Type = ? GROUP BY t.TagId ORDER BY t.Name COLLATE NOCASE",
            (TIPO_ETICHETTA,))]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def crea(nome: str) -> int | None:
    nome = (nome or "").strip()
    c = _apri()
    if c is None or not nome:
        return None
    try:
        riga = c.execute("SELECT TagId FROM Tag WHERE Type = ? AND Name = ?",
                         (TIPO_ETICHETTA, nome)).fetchone()
        if riga:
            return int(riga[0])
        cur = c.execute("INSERT INTO Tag (Type, Name) VALUES (?, ?)", (TIPO_ETICHETTA, nome))
        c.commit()
        return int(cur.lastrowid)
    except sqlite3.Error:
        return None
    finally:
        c.close()


def rinomina(tag_id: int, nome: str) -> bool:
    nome = (nome or "").strip()
    c = _apri()
    if c is None or not nome:
        return False
    try:
        c.execute("UPDATE Tag SET Name = ? WHERE TagId = ? AND Type = ?",
                  (nome, tag_id, TIPO_ETICHETTA))
        c.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        c.close()


def elimina(tag_id: int) -> None:
    """Toglie l'etichetta da tutte le note e la cancella.  Le note restano."""
    c = _apri()
    if c is None:
        return
    try:
        c.execute("DELETE FROM TagMap WHERE TagId = ?", (tag_id,))
        c.execute("DELETE FROM Tag WHERE TagId = ? AND Type = ?", (tag_id, TIPO_ETICHETTA))
        c.commit()
    except sqlite3.Error:
        pass
    finally:
        c.close()


def della_nota(note_id: int) -> list[int]:
    """Gli id delle etichette di una nota."""
    c = _apri()
    if c is None:
        return []
    try:
        return [r[0] for r in c.execute(
            "SELECT tm.TagId FROM TagMap tm JOIN Tag t ON t.TagId = tm.TagId "
            "WHERE tm.NoteId = ? AND t.Type = ?", (note_id, TIPO_ETICHETTA))]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def nomi_per_nota() -> dict[int, list[str]]:
    """Per ogni nota con etichette, i loro nomi (per mostrarli sulle card)."""
    c = _apri()
    if c is None:
        return {}
    risultato: dict[int, list[str]] = {}
    try:
        for nota, nome in c.execute(
                "SELECT tm.NoteId, t.Name FROM TagMap tm JOIN Tag t ON t.TagId = tm.TagId "
                "WHERE tm.NoteId IS NOT NULL AND t.Type = ? ORDER BY t.Name COLLATE NOCASE",
                (TIPO_ETICHETTA,)):
            risultato.setdefault(int(nota), []).append(nome)
    except sqlite3.Error:
        pass
    finally:
        c.close()
    return risultato


def imposta(note_id: int, tag_id: int, attivo: bool) -> None:
    """Mette o toglie un'etichetta a una nota."""
    c = _apri()
    if c is None:
        return
    try:
        if attivo:
            esiste = c.execute("SELECT 1 FROM TagMap WHERE TagId = ? AND NoteId = ?",
                               (tag_id, note_id)).fetchone()
            if not esiste:
                posizione = c.execute(
                    "SELECT COALESCE(MAX(Position), -1) + 1 FROM TagMap WHERE TagId = ?",
                    (tag_id,)).fetchone()[0]
                c.execute("INSERT INTO TagMap (NoteId, TagId, Position) VALUES (?, ?, ?)",
                          (note_id, tag_id, posizione))
        else:
            c.execute("DELETE FROM TagMap WHERE TagId = ? AND NoteId = ?", (tag_id, note_id))
        c.commit()
    except sqlite3.Error:
        pass
    finally:
        c.close()


def note_del_tag(tag_id: int) -> set[int]:
    """Gli id delle note che hanno quell'etichetta."""
    c = _apri()
    if c is None:
        return set()
    try:
        return {r[0] for r in c.execute(
            "SELECT NoteId FROM TagMap WHERE TagId = ? AND NoteId IS NOT NULL", (tag_id,))}
    except sqlite3.Error:
        return set()
    finally:
        c.close()
