#
#  GemmaRicerche.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La gemma: per un versetto, le pubblicazioni che lo citano.

I dati stanno nel pacchetto «Guida alle ricerche» (``rsg``), che l'utente
deve avere scaricato.  Il percorso e' sempre lo stesso:

  versetto  ->  ``VerseCommentaryMap``  ->  ``VerseCommentary``
            ->  documento + paragrafi    ->  ``DocumentExtract``
            ->  ``Extract.Caption``      (sigla e titolo, in chiaro)

Le didascalie non sono cifrate, quindi non serve decifrare niente.
Il numero del versetto (``BibleVerseId``) e' lo stesso nella Bibbia e nella
Guida: si ricava da ``BibleChapter.FirstVerseId`` del pacchetto della Bibbia.
"""

from __future__ import annotations

import html
import re
import sqlite3
from pathlib import Path

from Utility.Extensions.Ext_FileManager import get_documents_directory

SIMBOLO = "rsg"
_RE_TAG = re.compile(r"<[^>]+>")


def percorso_db() -> Path | None:
    """Il database della Guida alle ricerche, o None se non e' scaricata."""
    from Utility import Lingua
    nome = f"{SIMBOLO}_{Lingua.bibbia_simbolo()}"
    db = get_documents_directory() / nome / "contents" / f"{nome}.db"
    return db if db.is_file() else None


def _apri(db: Path) -> sqlite3.Connection | None:
    try:
        return sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def _id_versetto(libro: int, capitolo: int, versetto: int) -> int | None:
    from Utility.JWPubManager import bible_db_path, bible_package_di_qualunque_lingua
    # Il numero del versetto e' lo stesso in tutte le lingue: va bene anche la
    # Bibbia scaricata in un'altra lingua.
    percorso = bible_db_path()
    if percorso is None:
        altra = bible_package_di_qualunque_lingua()
        percorso = next((altra / "contents").glob("*.db"), None) if altra else None
    if percorso is None:
        return None
    connessione = _apri(Path(percorso))
    if connessione is None:
        return None
    try:
        riga = connessione.execute(
            "SELECT FirstVerseId FROM BibleChapter"
            " WHERE BookNumber = ? AND ChapterNumber = ?",
            (libro, capitolo)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connessione.close()
    return None if riga is None else int(riga[0]) + max(versetto, 1) - 1


def _testo(frammento: str) -> str:
    return html.unescape(_RE_TAG.sub("", frammento or "")).strip()


def pubblicazioni(libro: int, capitolo: int, versetto: int) -> list[dict]:
    """Le pubblicazioni che citano il versetto.

    Ogni voce: sigla e titolo da mostrare, documento citato, paragrafi da
    ``inizio`` a ``fine``, simbolo e titolo breve della pubblicazione.
    """
    db = percorso_db()
    versetto_id = _id_versetto(libro, capitolo, versetto)
    if db is None or versetto_id is None:
        return []
    connessione = _apri(db)
    if connessione is None:
        return []
    voci: list[dict] = []
    try:
        commenti = connessione.execute(
            "SELECT vc.CommentaryMepsDocumentId, vc.BeginParagraphOrdinal,"
            " vc.EndParagraphOrdinal FROM VerseCommentaryMap m"
            " JOIN VerseCommentary vc USING (VerseCommentaryId)"
            " WHERE m.BibleVerseId = ?", (versetto_id,)).fetchall()
        for meps_id, inizio, fine in commenti:
            documento = connessione.execute(
                "SELECT DocumentId FROM Document WHERE MepsDocumentId = ?",
                (meps_id,)).fetchone()
            if documento is None:
                continue
            for riga in connessione.execute(
                    "SELECT x.Caption, x.RefMepsDocumentId,"
                    " x.RefBeginParagraphOrdinal, x.RefEndParagraphOrdinal,"
                    " rp.EnglishSymbol, rp.ShortTitle"
                    " FROM DocumentExtract de JOIN Extract x USING (ExtractId)"
                    " LEFT JOIN RefPublication rp"
                    " ON rp.RefPublicationId = x.RefPublicationId"
                    " WHERE de.DocumentId = ? AND de.BeginParagraphOrdinal"
                    " BETWEEN ? AND ? ORDER BY de.SortPosition",
                    (documento[0], inizio, fine)):
                caption = riga[0] or ""
                sigla = _testo(re.sub(r'(?s)^.*?class="eloc">(.*?)</span>.*$',
                                      r"\1", caption))
                titolo = _testo(re.sub(r'(?s)^.*?class="etitle">(.*?)</span>.*$',
                                       r"\1", caption))
                voci.append({
                    "sigla": sigla, "titolo": titolo if titolo != sigla else "",
                    "documento": int(riga[1] or 0), "inizio": riga[2], "fine": riga[3],
                    "simbolo": riga[4] or "", "breve": riga[5] or ""})
    except sqlite3.Error:
        return voci
    finally:
        connessione.close()
    return voci


def riferimento(nome: str, voci: list[dict]):
    """La lista della gemma come ``Riferimento``: ogni voce e' un link blu.

    I link sono ``jwl:pub/<posizione>``: il riquadro li passa a chi lo usa, che
    apre il brano e ricorda la pagina per i pulsanti avanti e indietro.
    """
    from Utility import RiferimentiWol as _wol

    if voci:
        righe = "".join(
            f"<li><a href='jwl:pub/{i}'><b>{html.escape(v['sigla'])}</b></a>"
            + (f"<span>{html.escape(v['titolo'])}</span>" if v["titolo"] else "")
            + "</li>" for i, v in enumerate(voci))
        corpo = (
            "<style>ul.gemma{list-style:none;padding:0;margin:0}"
            "ul.gemma li{padding:9px 0;border-bottom:1px solid rgba(128,128,128,.3)}"
            "ul.gemma span{display:block;opacity:.7;font-size:13px}</style>"
            f"<h1>{html.escape(nome)}</h1><ul class='gemma'>{righe}</ul>")
    else:
        corpo = (f"<h1>{html.escape(nome)}</h1><p style='opacity:.7'>"
                 "Nessuna pubblicazione collegata a questo versetto.</p>")
    return _wol.Riferimento(titolo="Guida alle ricerche", voci=[_wol.Voce(
        titolo="Guida alle ricerche", pubblicazione=nome, immagine="", html=corpo)])


def pagina_scarica(titolo: str, colori: dict, css_scheme: str, accento: str,
                   in_corso: bool = False, errore: str = "",
                   percentuale: int = -1) -> str:
    """La pagina del riquadro quando la Guida alle ricerche non e' scaricata."""
    if in_corso:
        testo = f"Scarico la Guida alle ricerche… {percentuale}%" if percentuale >= 0 \
            else "Scarico la Guida alle ricerche…"
        barra = (f"<div class='barra'><div style='width:{max(percentuale, 0)}%'></div></div>")
        corpo = f"<p class='msg'>{testo}</p>{barra}"
    else:
        avviso = f"<p class='err'>{html.escape(errore)}</p>" if errore else ""
        corpo = (
            "<p class='msg'>Per vedere le pubblicazioni collegate a questo versetto "
            "serve la <b>Guida alle ricerche</b> (circa 110 MB).</p>" + avviso
            + "<p><a class='btn' href='jwl:scarica-guida'>Scarica la Guida alle ricerche</a></p>")
    return (
        "<html><head><meta charset='UTF-8'><style>"
        f"body{{font-family:sans-serif;font-size:15px;margin:0;padding:10px 14px 24px;"
        f"background:{colori['sfondo']};color:{colori['testo']}}}"
        f":root{{color-scheme:{css_scheme}}}"
        f"h1{{font-size:17px;margin:6px 0 10px}}"
        f".msg{{color:{colori['grigio']};line-height:1.45}}"
        f".err{{color:#d9534f}}"
        f".barra{{height:8px;border-radius:4px;background:{colori['bordo']}}}"
        f".barra div{{height:8px;border-radius:4px;background:{accento}}}"
        f".btn{{display:inline-block;padding:9px 16px;border-radius:6px;"
        f"background:{accento};color:#fff;text-decoration:none;font-weight:600}}"
        f"</style></head><body><h1>{html.escape(titolo)}</h1>{corpo}</body></html>")
