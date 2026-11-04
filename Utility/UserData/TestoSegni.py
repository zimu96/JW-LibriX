#
#  TestoSegni.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il titolo e il testo vero di sottolineature, segnalibri e appunti.

Un backup di JW Library dice *dove* sta una sottolineatura (documento,
paragrafo, prima e ultima parola) ma non *che cosa* c'e' scritto.  Qui il testo
si ricostruisce dai documenti che sono gia' sul disco:

    pubblicazioni   ``Documents_<lingua>/<DocumentId>.html``
    Bibbia          ``<cartella Bibbia>/<libro>/<capitolo>.html``

Le parole si contano **come le conta ``Files/script.js``**, perche' le
sottolineature si disegnano con quella stessa regola: una parola, o un segno di
punteggiatura, e' un pezzo.

NIENTE RETE
-----------
Se il documento non e' sul disco non si va a cercarlo: si dice che non e'
scaricato.  Il titolo, in quel caso, e' quello della pubblicazione preso dal
catalogo (che e' locale).  Scaricarla e' una scelta dell'utente.

Quello che si ricostruisce si salva in ``BlockRange.Snippet``/``Title``: la
volta dopo la risposta e' immediata.
"""
from __future__ import annotations

import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path

from Utility.Structures.Paths import Paths

_PAROLA = re.compile(
    r"[\b\wàèìòùÀÈÌÒÙáéíóúýÁÉÍÓÚÝâêîôûÂÊÎÔÛãñõÃÑÕäëïöüÿÄËÏÖÜŸçÇßØøÅåÆæœ’:-]*"
    r"[^:\-.,;!?“”()‘’\s]+")
_PUNT_1 = re.compile(r"[:|\-|’](?=[\s|.|,])")
_PUNT_2 = re.compile(r"[.|,|;|!|?|“|”|(|)|‘]")

LIBRI_IT = [
    "Genesi", "Esodo", "Levitico", "Numeri", "Deuteronomio", "Giosuè", "Giudici", "Rut",
    "1 Samuele", "2 Samuele", "1 Re", "2 Re", "1 Cronache", "2 Cronache", "Esdra",
    "Neemia", "Ester", "Giobbe", "Salmi", "Proverbi", "Ecclesiaste", "Cantico dei Cantici",
    "Isaia", "Geremia", "Lamentazioni", "Ezechiele", "Daniele", "Osea", "Gioele", "Amos",
    "Abdia", "Giona", "Michea", "Naum", "Abacuc", "Sofonia", "Aggeo", "Zaccaria", "Malachia",
    "Matteo", "Marco", "Luca", "Giovanni", "Atti", "Romani", "1 Corinti", "2 Corinti",
    "Galati", "Efesini", "Filippesi", "Colossesi", "1 Tessalonicesi", "2 Tessalonicesi",
    "1 Timoteo", "2 Timoteo", "Tito", "Filemone", "Ebrei", "Giacomo", "1 Pietro", "2 Pietro",
    "1 Giovanni", "2 Giovanni", "3 Giovanni", "Giuda", "Rivelazione"]


def _token(testo: str) -> list[tuple[int, int]]:
    """Le posizioni (inizio, fine) dei pezzi di un testo, nell'ordine."""
    pezzi = [m.span() for m in _PAROLA.finditer(testo)]
    occupato = [False] * len(testo)
    for a, b in pezzi:
        for i in range(a, b):
            occupato[i] = True
    for m in list(_PUNT_1.finditer(testo)) + list(_PUNT_2.finditer(testo)):
        if not occupato[m.start()]:
            occupato[m.start()] = True
            pezzi.append(m.span())
    pezzi.sort()
    return pezzi


class _Estrattore(HTMLParser):
    """Raccoglie i testi dentro gli elementi cercati e il titolo del documento."""

    def __init__(self, scelto) -> None:
        super().__init__(convert_charrefs=True)
        self.scelto = scelto          # funzione(tag, attrs) -> True se e' l'elemento cercato
        self.nodi: list[str] = []
        self.titolo = ""
        self._pila: list[tuple[str, bool]] = []
        self._dentro = 0
        self._in_h1 = False
        self._ultimo_tag = ""
        self._ultimo_attrs: dict = {}
        self._pre_strong_verso = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1" and not self.titolo:
            self._in_h1 = True
        if tag in ("br", "img", "hr", "meta", "link", "input"):
            return
        e_cercato = self.scelto(tag, attrs) if self._dentro == 0 else False
        self._pila.append((tag, e_cercato))
        if e_cercato or self._dentro:
            self._dentro += 1
        self._pre_strong_verso = (tag == "strong" and self._ultimo_tag == "a"
                                  and "cl vx vp" in (self._ultimo_attrs.get("class") or ""))
        self._ultimo_tag, self._ultimo_attrs = tag, attrs

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False
        while self._pila:
            nome, _ = self._pila.pop()
            if self._dentro:
                self._dentro -= 1
            if nome == tag:
                break
        self._ultimo_tag, self._ultimo_attrs = "/" + tag, {}

    def handle_data(self, dati):
        if self._in_h1:
            self.titolo += dati
        if not self._dentro:
            return
        # le stesse esclusioni di script.js
        senza_token = (self._ultimo_tag == "sup"
                       or (self._ultimo_tag == "a" and "vl vx vp" in (self._ultimo_attrs.get("class") or ""))
                       or self._pre_strong_verso
                       or (self._ultimo_tag == "a" and "cl vx vp" in (self._ultimo_attrs.get("class") or "")))
        pulito = dati.strip()
        if pulito in ("+", "*"):        # richiami a note e riferimenti: non sono testo
            return
        if senza_token or not (len(pulito) > 1 or pulito in (";", ".")):
            self.nodi.append(("\0", dati))      # testo che non conta come pezzo
        else:
            self.nodi.append(("", dati))


def _frase(nodi, inizio: int, fine: int) -> str:
    """Il testo dal pezzo ``inizio`` al pezzo ``fine`` (compresi)."""
    totale = ""
    spazi: list[tuple[int, int]] = []
    for marca, dati in nodi:
        a = len(totale)
        totale += dati
        if marca == "":
            spazi.append((a, len(totale)))
    pezzi: list[tuple[int, int]] = []
    for a, b in spazi:
        for x, y in _token(totale[a:b]):
            pezzi.append((a + x, a + y))
    if not pezzi:
        return ""
    inizio = max(0, min(inizio, len(pezzi) - 1))
    fine = max(inizio, min(fine, len(pezzi) - 1))
    return " ".join(totale[pezzi[inizio][0]:pezzi[fine][1]].split())


def _leggi(percorso: Path) -> str:
    try:
        return percorso.read_text(encoding="utf-8")
    except OSError:
        return ""


def _cartella_documenti(lingua: str) -> Path:
    return Paths.root / f"Documents_{lingua}"


_catalogo_cache: dict[tuple, tuple[str, str]] = {}


def titolo_pubblicazione(sigla: str, issue: int, meps: int) -> tuple[str, str]:
    """(titolo, titolo del fascicolo) dal catalogo locale.  Vuoti se non c'e'."""
    chiave = (sigla, issue, meps)
    if chiave in _catalogo_cache:
        return _catalogo_cache[chiave]
    risultato = ("", "")
    try:
        catalogo = Paths.root / "catalog.db"
        if catalogo.is_file():
            c = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True)
            try:
                r = c.execute(
                    "SELECT Title, IssueTitle FROM Publication WHERE KeySymbol=? AND "
                    "IssueTagNumber=? AND MepsLanguageId=?", (sigla, issue, meps)).fetchone()
                if r:
                    risultato = (r[0] or "", r[1] or "")
            finally:
                c.close()
    except sqlite3.Error:
        pass
    _catalogo_cache[chiave] = risultato
    return risultato


def _cartella_bibbia(lingua: str) -> Path | None:
    try:
        from Utility import JWPubManager as modulo
        return modulo.bible_package(lingua)
    except Exception:  # noqa: BLE001 - la Bibbia puo' non esserci
        return None


def risolvi(sigla: str, meps: int, issue: int, documento: int, libro: int,
            capitolo: int, identificatore: int, inizio: int | None = None,
            fine: int | None = None) -> dict:
    """Ricostruisce titolo, testo e stato di un segno.

    Ritorna ``{"titolo", "sottotitolo", "testo", "scaricato"}``.  ``testo`` e'
    vuoto se non si puo' ricostruire.  Non usa mai la rete.
    """
    from Utility import Lingua
    lingua = Lingua.da_numero(meps) if meps else Lingua.corrente_simbolo()
    nome_pub, titolo_numero = titolo_pubblicazione(sigla, issue, meps or 4)
    sottotitolo = titolo_numero or nome_pub or sigla

    if libro and capitolo:
        cartella = _cartella_bibbia(lingua)
        nome_libro = (LIBRI_IT[libro - 1] if lingua == "I" and 0 < libro <= len(LIBRI_IT)
                      else f"Libro {libro}")
        titolo = f"{nome_libro} {capitolo}" + (f":{identificatore}" if 0 < identificatore < 177 else "")
        percorso = cartella / str(libro) / f"{capitolo}.html" if cartella else None
        if not percorso or not percorso.is_file():
            return {"titolo": titolo, "sottotitolo": sottotitolo or "Bibbia",
                    "testo": "", "scaricato": False}
        html = _leggi(percorso)
        prefisso = f"v{libro}-{capitolo}-{identificatore}-"
        est = _Estrattore(lambda t, a: t == "span" and (a.get("id") or "").startswith(prefisso))
        est.feed(html)
        testo = _frase(est.nodi, inizio or 0, fine if fine is not None else 10**6) if est.nodi else ""
        if est.titolo.strip() and lingua != "I":
            titolo = f"{' '.join(est.titolo.split())} {capitolo}" + (
                f":{identificatore}" if 0 < identificatore < 177 else "")
        return {"titolo": titolo, "sottotitolo": sottotitolo or "Bibbia",
                "testo": testo, "scaricato": True}

    percorso = _cartella_documenti(lingua) / f"{documento}.html"
    if not documento or not percorso.is_file():
        return {"titolo": titolo_numero or nome_pub or sigla or "Pubblicazione",
                "sottotitolo": "", "testo": "", "scaricato": False}
    html = _leggi(percorso)
    est = _Estrattore(lambda t, a: (a.get("data-pid") or "") == str(identificatore))
    est.feed(html)
    titolo = " ".join(est.titolo.split()) or nome_pub or sigla
    testo = ""
    if identificatore and est.nodi:
        testo = _frase(est.nodi, inizio or 0, fine if fine is not None else 10**6)
    return {"titolo": titolo, "sottotitolo": sottotitolo if sottotitolo != titolo else "",
            "testo": testo, "scaricato": True}


def salva_in_cache(user_mark_id: int, titolo: str, testo: str) -> None:
    """Ricorda titolo e testo di una sottolineatura, cosi' la prossima volta e' immediato."""
    try:
        c = sqlite3.connect(str(Paths.db_path), timeout=30)
        try:
            c.execute("UPDATE BlockRange SET Snippet=?, Title=? WHERE UserMarkId=?",
                      (testo, titolo, user_mark_id))
            c.commit()
        finally:
            c.close()
    except sqlite3.Error as errore:
        print(f"Non riesco a ricordare il testo ⚠️  {errore}")


def completa(item) -> None:
    """Riempie titolo, testo e stato di un ``SavedItem`` (una volta sola)."""
    if getattr(item, "risolto", False):
        return
    item.risolto = True
    inizio = item.startToken if item.startToken >= 0 else 0
    fine = item.endToken if item.endToken >= 0 else inizio + 24
    r = risolvi(item.keySymbol, item.mepsLanguageId, item.issueTagNumber, item.documentId,
                item.bookNumber, item.chapterNumber, item.identifier, inizio, fine)
    item.scaricato = r["scaricato"]
    item.sottotitolo = r["sottotitolo"]
    if item.kind == "sottolineatura":
        if r["scaricato"]:
            nuovo_titolo, nuovo_testo = r["titolo"], item.snippet or r["testo"]
            if (nuovo_titolo, nuovo_testo) != (item.title, item.snippet):
                item.title, item.snippet = nuovo_titolo, nuovo_testo
                salva_in_cache(item.ID, item.title, item.snippet)
        elif not item.title:
            item.title = r["titolo"]
    else:
        if not item.title:
            item.title = r["titolo"]
        if not item.snippet:
            item.snippet = r["testo"]
