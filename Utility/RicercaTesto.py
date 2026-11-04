#
#  RicercaTesto.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La ricerca dentro il testo: pubblicazioni scaricate e Bibbia.

Un indice di ricerca (SQLite FTS5) in ``userData/ricerca.db``, costruito dai
testi che sono sul disco:

  - ``Documents_I/<MepsDocumentId>.html``: i capitoli e gli articoli scaricati;
  - la Bibbia scaricata, **un versetto per riga**, cosi' un risultato apre
    proprio quel versetto.

L'indice si aggiorna da solo: un file nuovo o cambiato si legge, uno sparito si
toglie, gli altri non si toccano.  Va chiamato da un thread: la prima volta
legge qualche decina di megabyte di testo.
"""

from __future__ import annotations

import html
import re
import sqlite3
from pathlib import Path

from Utility import JWPubManager as _jwpub
from Utility.Extensions.Ext_FileManager import get_documents_directory

INIZIO, FINE = "\x02", "\x03"
_RE_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_SPAZI = re.compile(r"\s+")
_RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
_RE_P = re.compile(r"<p\b[^>]*>.*?</p>", re.S | re.I)


def _percorso() -> Path:
    return get_documents_directory() / "userData" / "ricerca.db"


def _apri() -> sqlite3.Connection:
    percorso = _percorso()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(percorso), timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS doc (id INTEGER PRIMARY KEY, chiave TEXT UNIQUE,"
              " tipo TEXT, titolo TEXT, sigla TEXT, meps INTEGER, libro INTEGER,"
              " cap INTEGER, verso INTEGER, mtime REAL, origine TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS doc_origine ON doc (origine)")
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS testo USING fts5("
              "corpo, tokenize='unicode61 remove_diacritics 2')")
    return c


def _pulisci(frammento: str) -> str:
    frammento = _RE_SCRIPT.sub(" ", frammento)
    return _RE_SPAZI.sub(" ", html.unescape(_RE_TAG.sub(" ", frammento))).strip()


def _titoli_dei_documenti() -> dict[int, tuple[str, str]]:
    """MepsDocumentId -> (sigla, titolo), letto dai pacchetti scaricati."""
    titoli: dict[int, tuple[str, str]] = {}
    for cartella in _jwpub.scaricate():
        sigla = cartella.name.split("_", 1)[0]
        for db in (cartella / "contents").glob("*.db"):
            try:
                c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                try:
                    for meps, titolo in c.execute(
                            "SELECT MepsDocumentId, Title FROM Document"):
                        titoli[int(meps)] = (sigla, titolo or "")
                finally:
                    c.close()
            except sqlite3.Error:
                continue
    return titoli


def aggiorna_indice(progresso=None) -> int:
    """Mette l'indice in pari con il disco.  Ritorna quanti documenti ha letto."""
    c = _apri()
    letti = 0
    try:
        noti = {r[0]: r[1] for r in c.execute("SELECT origine, MAX(mtime) FROM doc GROUP BY origine")}
        visti: set[str] = set()
        lavoro: list[tuple] = []

        cartella_doc = get_documents_directory() / "Documents_I"
        if cartella_doc.is_dir():
            titoli = _titoli_dei_documenti()
            for file in cartella_doc.glob("*.html"):
                if not file.stem.isdigit():
                    continue
                chiave = f"d:{file.stem}"
                visti.add(chiave)
                mtime = file.stat().st_mtime
                if noti.get(chiave) == mtime:
                    continue
                lavoro.append(("d", chiave, file, mtime, titoli.get(int(file.stem))))

        bibbia = _jwpub.bible_package()
        if bibbia is not None:
            for file in bibbia.glob("*/*.html"):
                if not (file.parent.name.isdigit() and file.stem.isdigit()):
                    continue
                chiave = f"b:{file.parent.name}:{file.stem}"
                visti.add(chiave)
                mtime = file.stat().st_mtime
                if noti.get(chiave) == mtime:
                    continue
                lavoro.append(("b", chiave, file, mtime, None))

        for origine in noti:
            if origine not in visti:
                _togli(c, origine)

        for i, (tipo, chiave, file, mtime, info) in enumerate(lavoro):
            if progresso:
                progresso(i, len(lavoro))
            try:
                grezzo = file.read_text(encoding="utf-8")
            except OSError:
                continue
            _togli(c, chiave)
            if tipo == "d":
                _inserisci_documento(c, chiave, file, grezzo, mtime, info)
            else:
                _inserisci_capitolo_biblico(c, file, grezzo, mtime)
            letti += 1
            if i % 40 == 0:
                c.commit()
        c.commit()
    finally:
        c.close()
    return letti


def _togli(c: sqlite3.Connection, origine: str) -> None:
    """Toglie dall'indice tutto quello che veniva da un file."""
    for (id_doc,) in c.execute("SELECT id FROM doc WHERE origine = ?", (origine,)).fetchall():
        c.execute("DELETE FROM testo WHERE rowid = ?", (id_doc,))
    c.execute("DELETE FROM doc WHERE origine = ?", (origine,))


def _inserisci(c, chiave, origine, tipo, titolo, sigla, meps, libro, cap, verso, mtime, corpo) -> None:
    cur = c.execute("INSERT INTO doc (chiave, origine, tipo, titolo, sigla, meps, libro, cap, verso, mtime)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (chiave, origine, tipo, titolo, sigla, meps, libro, cap, verso, mtime))
    c.execute("INSERT INTO testo (rowid, corpo) VALUES (?, ?)", (cur.lastrowid, corpo))


def _inserisci_documento(c, chiave, file, grezzo, mtime, info) -> None:
    meps = int(file.stem)
    if info:
        sigla, titolo = info
    else:
        h1 = _RE_H1.search(grezzo)
        sigla, titolo = "", (_pulisci(h1.group(1)) if h1 else f"Documento {meps}")
    corpo = _pulisci(grezzo)
    if corpo:
        _inserisci(c, chiave, chiave, "d", titolo or f"Documento {meps}", sigla, meps,
                   0, 0, 0, mtime, corpo)


def _inserisci_capitolo_biblico(c, file, grezzo, mtime) -> None:
    libro, cap = int(file.parent.name), int(file.stem)
    h1 = _RE_H1.search(grezzo)
    nome = _pulisci(h1.group(1)) if h1 else f"Libro {libro}"
    versi: dict[int, list[str]] = {}
    modello = re.compile(r'id="v%d-%d-(\d+)-\d+"' % (libro, cap))
    for paragrafo in _RE_P.finditer(grezzo):
        testo_p = paragrafo.group(0)
        numeri = [int(n) for n in modello.findall(testo_p)]
        if not numeri:
            continue
        if len(set(numeri)) == 1:
            versi.setdefault(numeri[0], []).append(_pulisci(testo_p))
            continue
        # piu' versetti nello stesso paragrafo: si tagliano span per span
        for span in re.finditer(r'<span id="v%d-%d-(\d+)-\d+"[^>]*>.*?</span>' % (libro, cap),
                                testo_p, re.S):
            versi.setdefault(int(span.group(1)), []).append(_pulisci(span.group(0)))
    for verso, pezzi in versi.items():
        corpo = " ".join(pezzi)
        if corpo:
            _inserisci(c, f"b:{libro}:{cap}:{verso}", f"b:{libro}:{cap}", "b",
                       f"{nome} {cap}:{verso}", "nwtsty", 0, libro, cap, verso, mtime, corpo)


def indicizzato() -> bool:
    """C'e' qualcosa nell'indice?"""
    try:
        c = _apri()
        try:
            return c.execute("SELECT 1 FROM doc LIMIT 1").fetchone() is not None
        finally:
            c.close()
    except sqlite3.Error:
        return False


def cerca(domanda: str, limite: int = 80, sigla: str | None = None) -> list[dict]:
    """I risultati per una domanda: i termini insieme, l'ultimo anche a meta' parola.

    Con ``sigla`` si cerca solo dentro quella pubblicazione («nwtsty» e' la Bibbia).
    """
    termini = re.findall(r"\w+", domanda or "", re.UNICODE)
    if not termini:
        return []
    espressione = " ".join(f'"{t}"' for t in termini[:-1])
    espressione = (espressione + " " if espressione else "") + f'"{termini[-1]}"*'
    try:
        c = _apri()
    except sqlite3.Error:
        return []
    try:
        righe = c.execute(
            "SELECT d.tipo, d.titolo, d.sigla, d.meps, d.libro, d.cap, d.verso,"
            f" snippet(testo, 0, '{INIZIO}', '{FINE}', '…', 16) "
            "FROM testo JOIN doc d ON d.id = testo.rowid "
            "WHERE testo MATCH ? " + ("AND d.sigla = ? " if sigla else "")
            + "ORDER BY bm25(testo) LIMIT ?",
            (espressione, *((sigla,) if sigla else ()), limite)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        c.close()
    return [{"tipo": t, "titolo": titolo, "sigla": sigla, "meps": meps, "libro": libro,
             "cap": cap, "verso": verso, "anteprima": _in_html(snippet)}
            for t, titolo, sigla, meps, libro, cap, verso, snippet in righe]


def _in_html(snippet: str) -> str:
    """Lo snippet con le parole trovate in grassetto, il resto protetto."""
    protetto = html.escape(snippet or "")
    return protetto.replace(INIZIO, "<b>").replace(FINE, "</b>")
