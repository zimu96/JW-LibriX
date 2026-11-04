#
#  PlaylistManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le playlist, nel formato dei backup di JW Library.

Nel database utente una playlist e' un ``Tag`` di tipo 2; i suoi elementi sono
righe di ``PlaylistItem`` collegate dal ``TagMap`` (con la ``Position``), e il
file di ogni elemento sta in ``PlaylistMedia``.  Il taglio di un elemento sono
due numeri in ``PlaylistItem``: ``StartTimeOffsetTicks`` e ``EndTimeOffsetTicks``
(un tick = 100 nanosecondi, quindi 10.000 tick sono un millisecondo).

Tenendo lo stesso formato, i backup che JW Library esporta e importa portano con
se' anche le playlist.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from Utility.Extensions.Ext_FileManager import get_documents_directory

TIPO_PLAYLIST = 2
TICK_PER_MS = 10_000
#: PlaylistMedia.MediaType
AUDIO, VIDEO, IMMAGINE = 1, 2, 3


def _apri() -> sqlite3.Connection | None:
    percorso = get_documents_directory() / "userData" / "user_data.db"
    if not percorso.is_file():
        return None
    try:
        c = sqlite3.connect(str(percorso), timeout=30)
        c.execute("PRAGMA foreign_keys = ON")
        return c
    except sqlite3.Error:
        return None


def _relativo(file: Path) -> str:
    radice = get_documents_directory()
    try:
        return str(Path(file).resolve().relative_to(radice.resolve()))
    except ValueError:
        return str(file)


def percorso_file(nome: str) -> Path:
    """Il percorso vero di un file di playlist (relativo ai dati o assoluto)."""
    p = Path(nome)
    return p if p.is_absolute() else get_documents_directory() / p


def playlist() -> list[dict]:
    """Le playlist, in ordine alfabetico, con quanti elementi hanno."""
    c = _apri()
    if c is None:
        return []
    try:
        return [{"id": i, "nome": n, "elementi": k} for i, n, k in c.execute(
            "SELECT t.TagId, t.Name, COUNT(tm.TagMapId) FROM Tag t "
            "LEFT JOIN TagMap tm ON tm.TagId = t.TagId WHERE t.Type = ? "
            "GROUP BY t.TagId ORDER BY t.Name COLLATE NOCASE", (TIPO_PLAYLIST,))]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def crea(nome: str) -> int | None:
    """Crea una playlist; se il nome c'e' gia' ritorna quella che c'e'."""
    nome = (nome or "").strip()
    c = _apri()
    if c is None or not nome:
        return None
    try:
        riga = c.execute("SELECT TagId FROM Tag WHERE Type = ? AND Name = ?",
                         (TIPO_PLAYLIST, nome)).fetchone()
        if riga:
            return int(riga[0])
        cur = c.execute("INSERT INTO Tag (Type, Name) VALUES (?, ?)", (TIPO_PLAYLIST, nome))
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
                  (nome, tag_id, TIPO_PLAYLIST))
        c.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        c.close()


def elimina(tag_id: int) -> None:
    """Toglie la playlist e gli elementi che non servono a nessun'altra."""
    c = _apri()
    if c is None:
        return
    try:
        c.execute("DELETE FROM TagMap WHERE TagId = ?", (tag_id,))
        c.execute("DELETE FROM Tag WHERE TagId = ? AND Type = ?", (tag_id, TIPO_PLAYLIST))
        _pulisci_orfani(c)
        c.commit()
    except sqlite3.Error:
        pass
    finally:
        c.close()


def _pulisci_orfani(c: sqlite3.Connection) -> None:
    c.execute("DELETE FROM PlaylistItemChild WHERE PlaylistItemId NOT IN "
              "(SELECT PlaylistItemId FROM TagMap WHERE PlaylistItemId IS NOT NULL)")
    c.execute("DELETE FROM PlaylistItem WHERE PlaylistItemId NOT IN "
              "(SELECT PlaylistItemId FROM TagMap WHERE PlaylistItemId IS NOT NULL)")
    c.execute("DELETE FROM PlaylistMedia WHERE PlaylistMediaId NOT IN "
              "(SELECT PlaylistMediaId FROM PlaylistItem)")


def elementi(tag_id: int) -> list[dict]:
    """Gli elementi di una playlist, nell'ordine in cui si suonano."""
    c = _apri()
    if c is None:
        return []
    try:
        return [{"id": i, "titolo": l, "tipo": mt, "file": fn,
                 "inizio_ms": (s or 0) // TICK_PER_MS,
                 "fine_ms": (e // TICK_PER_MS) if e else None}
                for i, l, mt, fn, s, e in c.execute(
                    "SELECT pi.PlaylistItemId, pi.Label, pm.MediaType, pm.Filename,"
                    " pi.StartTimeOffsetTicks, pi.EndTimeOffsetTicks "
                    "FROM TagMap tm JOIN PlaylistItem pi ON pi.PlaylistItemId = tm.PlaylistItemId "
                    "JOIN PlaylistMedia pm ON pm.PlaylistMediaId = pi.PlaylistMediaId "
                    "WHERE tm.TagId = ? ORDER BY tm.Position", (tag_id,))]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def aggiungi(tag_id: int, file: Path, titolo: str, tipo: int = VIDEO) -> int | None:
    """Mette un file in fondo alla playlist.  Ritorna l'id dell'elemento."""
    c = _apri()
    if c is None:
        return None
    nome_file = _relativo(file)
    try:
        riga = c.execute("SELECT PlaylistMediaId FROM PlaylistMedia WHERE Filename = ?",
                         (nome_file,)).fetchone()
        if riga:
            media = int(riga[0])
        else:
            media = c.execute(
                "INSERT INTO PlaylistMedia (MediaType, Label, Filename) VALUES (?, ?, ?)",
                (tipo, titolo or Path(file).name, nome_file)).lastrowid
        item = c.execute(
            "INSERT INTO PlaylistItem (Label, AccuracyStatement, EndAction, PlaylistMediaId)"
            " VALUES (?, 0, 0, ?)", (titolo or Path(file).name, media)).lastrowid
        posizione = c.execute("SELECT COALESCE(MAX(Position), -1) + 1 FROM TagMap WHERE TagId = ?",
                              (tag_id,)).fetchone()[0]
        c.execute("INSERT INTO TagMap (PlaylistItemId, TagId, Position) VALUES (?, ?, ?)",
                  (item, tag_id, posizione))
        c.commit()
        return int(item)
    except sqlite3.Error:
        return None
    finally:
        c.close()


def rimuovi(tag_id: int, item_id: int) -> None:
    c = _apri()
    if c is None:
        return
    try:
        c.execute("DELETE FROM TagMap WHERE TagId = ? AND PlaylistItemId = ?", (tag_id, item_id))
        _pulisci_orfani(c)
        _rinumera(c, tag_id)
        c.commit()
    except sqlite3.Error:
        pass
    finally:
        c.close()


def _rinumera(c: sqlite3.Connection, tag_id: int) -> None:
    """Posizioni di nuovo 0, 1, 2...  (passando da numeri negativi: la coppia
    TagId+Position e' unica e uno scambio diretto la violerebbe)."""
    righe = [r[0] for r in c.execute(
        "SELECT TagMapId FROM TagMap WHERE TagId = ? ORDER BY Position", (tag_id,))]
    for n, tagmap in enumerate(righe):
        c.execute("UPDATE TagMap SET Position = ? WHERE TagMapId = ?", (-(n + 1), tagmap))
    for n, tagmap in enumerate(righe):
        c.execute("UPDATE TagMap SET Position = ? WHERE TagMapId = ?", (n, tagmap))


def sposta(tag_id: int, item_id: int, passo: int) -> None:
    """Sposta un elemento in su (-1) o in giu' (+1)."""
    c = _apri()
    if c is None:
        return
    try:
        righe = [r[0] for r in c.execute(
            "SELECT PlaylistItemId FROM TagMap WHERE TagId = ? ORDER BY Position", (tag_id,))]
        if item_id not in righe:
            return
        i = righe.index(item_id)
        j = i + passo
        if not 0 <= j < len(righe):
            return
        righe[i], righe[j] = righe[j], righe[i]
        for n, item in enumerate(righe):
            c.execute("UPDATE TagMap SET Position = ? WHERE TagId = ? AND PlaylistItemId = ?",
                      (-(n + 1), tag_id, item))
        for n, item in enumerate(righe):
            c.execute("UPDATE TagMap SET Position = ? WHERE TagId = ? AND PlaylistItemId = ?",
                      (n, tag_id, item))
        c.commit()
    except sqlite3.Error:
        pass
    finally:
        c.close()


def imposta_taglio(item_id: int, inizio_ms: int | None, fine_ms: int | None) -> None:
    """Il taglio di un elemento: da dove parte e dove si ferma (``None`` = nessun limite)."""
    c = _apri()
    if c is None:
        return
    inizio = int(inizio_ms) * TICK_PER_MS if inizio_ms else None
    fine = int(fine_ms) * TICK_PER_MS if fine_ms else None
    try:
        c.execute("UPDATE PlaylistItem SET StartTimeOffsetTicks = ?, EndTimeOffsetTicks = ?"
                  " WHERE PlaylistItemId = ?", (inizio, fine, item_id))
        c.commit()
    except sqlite3.Error:
        pass
    finally:
        c.close()
