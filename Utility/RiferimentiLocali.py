#
#  RiferimentiLocali.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I riferimenti che si leggono dal disco, senza rete.

Il link di un testo scaricato da wol.jw.org e' ``/wol/<tipo>/r6/lp-i/<doc>/<P>/<Q>``,
dove ``<doc>`` e' il MepsDocumentId della pagina in cui il link sta.  Il pacchetto
della pubblicazione sa dove porta:

  bc   BibleCitation: ``BlockNumber = P + 1`` e ``ElementNumber = Q + 1`` danno
       il primo e l'ultimo versetto (numeri di posizione nella Bibbia).  Il
       testo si prende dal capitolo della Bibbia scaricata.
  pc   DocumentExtract: il rimando numero ``P`` (in ordine di ``SortPosition``)
       dice il documento citato.  Se quel documento e' scaricato, si legge da li'.

Se qualcosa manca — pacchetto, Bibbia, documento citato — si restituisce
``None`` e chi chiama passa alla cache o al sito.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from Utility import JWPubManager as _jwpub
from Utility import RiferimentiWol as _wol
from Utility.Extensions.Ext_FileManager import get_documents_directory

_RE = re.compile(r"/wol/(bc|pc)/r\d+/lp-[a-z]+/(\d+)/(\d+)/(\d+)$")
_RE_TAG = re.compile(r"<[^>]+>")
#: MepsDocumentId -> (file .db del pacchetto, DocumentId locale)
_DOCUMENTI: dict[int, tuple[Path, int] | None] = {}
MAX_CAPITOLI = 3


def _apri(db: Path) -> sqlite3.Connection | None:
    try:
        return sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def _pacchetto_del_documento(meps_id: int):
    """(file .db, DocumentId locale) del pacchetto scaricato che ha quel documento."""
    if meps_id in _DOCUMENTI and _DOCUMENTI[meps_id] is not None:
        return _DOCUMENTI[meps_id]
    trovato = None
    for cartella in _jwpub.scaricate():
        for db in sorted((cartella / "contents").glob("*.db")):
            connessione = _apri(db)
            if connessione is None:
                continue
            try:
                riga = connessione.execute(
                    "SELECT DocumentId FROM Document WHERE MepsDocumentId = ?",
                    (meps_id,)).fetchone()
            except sqlite3.Error:
                riga = None
            finally:
                connessione.close()
            if riga is not None:
                trovato = (db, int(riga[0]))
                break
        if trovato:
            break
    _DOCUMENTI[meps_id] = trovato
    return trovato


def risolvi(href: str) -> _wol.Riferimento | None:
    """Il riferimento letto dal disco, o None se non si puo'."""
    voce = _wol.percorso(href)
    corrisponde = _RE.search(voce or "")
    if not corrisponde:
        return None
    tipo, meps, primo, secondo = (corrisponde.group(1),
                                  int(corrisponde.group(2)),
                                  int(corrisponde.group(3)),
                                  int(corrisponde.group(4)))
    pacchetto = _pacchetto_del_documento(meps)
    if pacchetto is None:
        return None
    try:
        if tipo == "bc":
            return _citazione_biblica(pacchetto, primo + 1, secondo + 1)
        return _pubblicazione_citata(pacchetto, primo)
    except (sqlite3.Error, OSError):
        return None


def _testo(html: str) -> str:
    return re.sub(r"\s+", " ", _RE_TAG.sub("", html)).strip()


# ----------------------------------------------------------------------
# VERSETTI
# ----------------------------------------------------------------------

def _citazione_biblica(pacchetto, blocco: int, elemento: int):
    db, documento = pacchetto
    cartella = _jwpub.bible_package()
    if cartella is None:
        return None

    connessione = _apri(db)
    if connessione is None:
        return None
    try:
        riga = connessione.execute(
            "SELECT FirstBibleVerseId, LastBibleVerseId FROM BibleCitation "
            "WHERE DocumentId = ? AND BlockNumber = ? AND ElementNumber = ?",
            (documento, blocco, elemento)).fetchone()
    finally:
        connessione.close()
    if riga is None:
        return None

    bibbia = _jwpub._connect_bible()
    if bibbia is None:
        return None
    try:
        query = ("SELECT BookNumber, ChapterNumber, FirstVerseId FROM BibleChapter "
                 "WHERE ? BETWEEN FirstVerseId AND LastVerseId")
        inizio = bibbia.execute(query, (riga[0],)).fetchone()
        fine = bibbia.execute(query, (riga[1],)).fetchone()
        titolo_bibbia = bibbia.execute(
            "SELECT Title FROM Publication LIMIT 1").fetchone()
    except sqlite3.Error:
        return None
    finally:
        bibbia.close()
    if inizio is None or fine is None or inizio[0] != fine[0]:
        return None

    libro = int(inizio[0])
    cap_1, verso_1 = int(inizio[1]), riga[0] - inizio[2] + 1
    cap_2, verso_2 = int(fine[1]), riga[1] - fine[2] + 1
    if cap_2 - cap_1 + 1 > MAX_CAPITOLI:
        return None

    blocchi, nome_libro = [], ""
    for capitolo in range(cap_1, cap_2 + 1):
        file = cartella / str(libro) / f"{capitolo}.html"
        if not file.is_file():
            return None
        html = file.read_text(encoding="utf-8")
        nome = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        nome_libro = _testo(nome.group(1)) if nome else nome_libro
        da = verso_1 if capitolo == cap_1 else 1
        a = verso_2 if capitolo == cap_2 else 10 ** 6
        pezzi = _versetti(html, libro, capitolo, da, a)
        if not pezzi:
            return None
        if cap_2 > cap_1:
            blocchi.append(f"<h2>{nome_libro} {capitolo}</h2>")
        blocchi.extend(pezzi)

    if cap_1 == cap_2:
        intervallo = f"{verso_1}" if verso_1 == verso_2 else f"{verso_1}-{verso_2}"
        titolo = f"{nome_libro} {cap_1}:{intervallo}"
    else:
        titolo = f"{nome_libro} {cap_1}:{verso_1}-{cap_2}:{verso_2}"

    copertina = next(iter(sorted((cartella / "contents").glob("*_univ_sqr-120x120.jpg"))), None)
    return _wol.Riferimento(titolo=titolo, voci=[_wol.Voce(
        titolo=titolo,
        pubblicazione=titolo_bibbia[0] if titolo_bibbia else "Bibbia",
        immagine=str(copertina) if copertina else "",
        html="".join(blocchi),
        simbolo="nwtsty", libro=libro, capitolo=cap_1, versetto=verso_1)])


def _versetti(html: str, libro: int, capitolo: int, da: int, a: int) -> list[str]:
    modello = re.compile(r'id="v%d-%d-(\d+)-' % (libro, capitolo))
    versetto = re.compile(
        r'<span id="v%d-%d-(\d+)-\d+" class="v">.*?</span>' % (libro, capitolo), re.S)
    pezzi = []
    for paragrafo in re.finditer(r"<p\b([^>]*)>(.*?)</p>", html, re.S):
        numeri = {int(n) for n in modello.findall(paragrafo.group(0))}
        if not any(da <= n <= a for n in numeri):
            continue
        if all(da <= n <= a for n in numeri):
            pezzi.append(paragrafo.group(0))
            continue
        # il paragrafo ha anche versetti fuori dall'intervallo: si tengono solo i giusti
        dentro = [v.group(0) for v in versetto.finditer(paragrafo.group(2))
                  if da <= int(v.group(1)) <= a]
        pezzi.append(f"<p{paragrafo.group(1)}>{' '.join(dentro)}</p>" if dentro
                     else paragrafo.group(0))
    return pezzi


# ----------------------------------------------------------------------
# PUBBLICAZIONI CITATE
# ----------------------------------------------------------------------

def _pubblicazione_citata(pacchetto, posizione: int):
    db, documento = pacchetto
    connessione = _apri(db)
    if connessione is None:
        return None
    try:
        riga = connessione.execute(
            "SELECT e.Caption, e.RefMepsDocumentId, e.RefBeginParagraphOrdinal, "
            "e.RefEndParagraphOrdinal, rp.ShortTitle, rp.EnglishSymbol "
            "FROM DocumentExtract de JOIN Extract e USING (ExtractId) "
            "LEFT JOIN RefPublication rp ON rp.RefPublicationId = e.RefPublicationId "
            "WHERE de.DocumentId = ? ORDER BY de.SortPosition LIMIT 1 OFFSET ?",
            (documento, posizione)).fetchone()
    finally:
        connessione.close()
    if riga is None or not riga[1]:
        return None

    didascalia, citato, inizio, fine, breve, simbolo = riga
    titolo_html = re.search(r'class="etitle">(.*?)</span>', didascalia or "", re.S)
    luogo = re.search(r'class="eloc">(.*?)</span>', didascalia or "", re.S)
    titolo = _testo(titolo_html.group(1)) if titolo_html else (
        _testo(luogo.group(1)) if luogo else "")
    return estratto(int(citato), inizio, fine, titolo, breve or "", simbolo or "")


def estratto(citato: int, inizio, fine, titolo: str, breve: str, simbolo: str,
             lingua: str | None = None):
    """I paragrafi ``inizio``-``fine`` del documento ``citato``, o None se non si leggono.

    Si legge dal disco; se il documento manca si prova a scaricarlo.
    """
    file = get_documents_directory() / "Documents_I" / f"{citato}.html"
    if not file.is_file():
        # Il capitolo e' rimasto fuori dallo scaricamento: si prende adesso.
        try:
            from Utility import Aggiornamenti
            from Utility.FileDownloader import FileDownloader
            from Utility.WolLingua import url_documento
            url = url_documento(citato, lingua)
            if url and Aggiornamenti.automatici():
                FileDownloader.download_article(
                    url=url, path=f"Documents_I/{citato}.html")
        except Exception:  # noqa: BLE001
            pass
    if not file.is_file():
        return None
    html = file.read_text(encoding="utf-8")
    if inizio:
        pezzi = [p.group(0) for p in re.finditer(r"<p\b[^>]*>.*?</p>", html, re.S)
                 if inizio <= _data_pid(p.group(0)) <= (fine or inizio)]
        if pezzi:
            html = "".join(pezzi)
    html = re.sub(r"<img\b[^>]*>", "", html)

    return _wol.Riferimento(titolo=titolo, voci=[_wol.Voce(
        titolo=titolo, pubblicazione=breve,
        immagine=_copertina_di(citato, simbolo), html=html,
        simbolo=simbolo, documento=citato)])


def _copertina_di(citato: int, simbolo: str = "") -> str:
    """La copertina quadrata: dal pacchetto che ha il documento, altrimenti dal sito."""
    pacchetto = _pacchetto_del_documento(citato)
    if pacchetto is None:
        if not simbolo or any(c.isdigit() for c in simbolo[1:]):
            return ""
        from Utility import Copertine
        return Copertine.url_copertina(simbolo, taglia="sm")
    copertina = next(iter(sorted(pacchetto[0].parent.glob("*_univ_sqr-120x120.jpg"))), None)
    return str(copertina) if copertina else ""


def _data_pid(paragrafo: str) -> int:
    trovato = re.search(r'data-pid="(\d+)"', paragrafo)
    return int(trovato.group(1)) if trovato else -1
