#
#  RiferimentiWol.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I riferimenti dentro un testo: versetti, cantici, altre pubblicazioni.

I testi scaricati da wol.jw.org hanno tre tipi di link che aprono un
riquadro e non una pagina:

    /wol/bc/...   citazione biblica   (Geremia 49:1-50:46)
    /wol/pc/...   pubblicazione citata (Cantico 44, un libro, una rivista)
    /wol/dx/...   rimandi              (lo stesso versetto in piu' traduzioni)

Chiesti senza ``/it`` nel percorso e con l'intestazione di una richiesta AJAX,
il sito risponde con un JSON: ``{"items": [{"title", "content", "imageUrl",
"publicationTitle", ...}], "title"}``.  E' lo stesso JSON che usa il riquadro
del sito, e ``content`` e' gia' il testo da mostrare.

L'ordine e': prima quello che e' scaricato (``RiferimentiLocali``), poi quello
letto in passato (``userData/riferimenti``), e solo alla fine il sito.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from Utility.Extensions.Ext_FileManager import get_documents_directory

BASE = "https://wol.jw.org"
TIPI = ("bc", "pc", "dx")
_RE = re.compile(r"^(?:/[a-z]{2})?(/wol/(?:%s)/r\d+/lp-[a-z]+/[^#?]+)" % "|".join(TIPI))
_INTESTAZIONI = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}
TIMEOUT = 20


@dataclass
class Voce:
    titolo: str
    pubblicazione: str
    immagine: str
    html: str
    #: sigla della pubblicazione ("nwtsty", "sjj"), per aprirla a schermo intero
    simbolo: str = ""
    #: per la Bibbia: libro, capitolo e primo versetto
    libro: int = 0
    capitolo: int = 0
    versetto: int = 0
    #: MepsDocumentId del documento citato, se si sa
    documento: int = 0


@dataclass
class Riferimento:
    titolo: str
    voci: list[Voce] = field(default_factory=list)

    @property
    def sottotitolo(self) -> str:
        return self.voci[0].pubblicazione if self.voci else ""

    @property
    def immagine(self) -> str:
        return next((v.immagine for v in self.voci if v.immagine), "")


def percorso(href: str) -> str | None:
    """Il percorso ``/wol/<tipo>/...`` di un link, o None se non e' un riferimento."""
    if not href:
        return None
    href = href.strip()
    if href.startswith(BASE):
        href = href[len(BASE):]
    corrisponde = _RE.match(href)
    return corrisponde.group(1) if corrisponde else None


def e_riferimento(href: str) -> bool:
    return percorso(href) is not None


def _cache(chiave: str) -> Path:
    cartella = get_documents_directory() / "userData" / "riferimenti"
    return cartella / (hashlib.sha1(chiave.encode()).hexdigest() + ".json")


def _leggi_rete(indirizzo: str) -> bytes | None:
    richiesta = urllib.request.Request(indirizzo, headers=_INTESTAZIONI)
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
            return risposta.read()
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _intero(valore) -> int:
    try:
        return int(valore)
    except (TypeError, ValueError):
        return 0


def _da_json(dati: dict) -> Riferimento | None:
    voci = []
    for voce in dati.get("items") or []:
        contenuto = voce.get("content") or ""
        if not contenuto.strip():
            continue
        immagine = voce.get("imageUrl") or ""
        documento = re.search(r"/wol/d/r\d+/lp-[a-z]+/(\d+)", voce.get("url") or "")
        voci.append(Voce(
            titolo=voce.get("title") or voce.get("caption") or "",
            pubblicazione=(voce.get("publicationTitle") or voce.get("source")
                           or ""),
            immagine=(BASE + immagine) if immagine.startswith("/") else immagine,
            html=contenuto,
            simbolo=str(voce.get("englishSymbol") or ""),
            libro=_intero(voce.get("book")),
            capitolo=_intero(voce.get("first_chapter")),
            versetto=_intero(voce.get("first_verse")),
            documento=int(documento.group(1)) if documento else 0,
        ))
    if not voci:
        return None
    return Riferimento(titolo=voci[0].titolo or dati.get("title") or "", voci=voci)


def carica(href: str, rete: bool = True) -> Riferimento | None:
    """Il riferimento di un link: dal disco, dalla cache, e solo alla fine dal sito.

    Con ``rete=False`` (modalita' offline) il sito non si tocca mai.
    Fa I/O: va chiamata da un thread, mai mentre si disegna.
    """
    voce = percorso(href)
    if voce is None:
        return None

    from Utility import RiferimentiLocali
    try:
        locale = RiferimentiLocali.risolvi(href)
    except Exception:  # noqa: BLE001 - un riferimento rotto non deve fermare la lettura
        locale = None
    if locale is not None:
        return locale

    file = _cache(voce)
    if file.is_file():
        try:
            dati = json.loads(file.read_text(encoding="utf-8"))
            letto = _da_json(dati)
            if letto is not None:
                return letto
        except (OSError, ValueError):
            pass
    if not rete:
        return None

    grezzo = _leggi_rete(BASE + voce)
    if grezzo is None:
        return None
    try:
        letto = _da_json(json.loads(grezzo.decode("utf-8")))
    except (ValueError, UnicodeDecodeError):
        return None
    if letto is not None:
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(grezzo)
        except OSError:
            pass
    return letto


def scarica_immagine(indirizzo: str) -> bytes | None:
    """La miniatura della pubblicazione (il logo da mettere nella barra)."""
    if not indirizzo:
        return None
    if not indirizzo.startswith("http"):
        try:
            return Path(indirizzo).read_bytes()
        except OSError:
            return None
    file = _cache("img:" + indirizzo).with_suffix(".img")
    try:
        if file.is_file():
            return file.read_bytes()
    except OSError:
        pass
    dati = _leggi_rete(indirizzo)
    if dati:
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(dati)
        except OSError:
            pass
    return dati


def pagina_html(riferimento: Riferimento, colori: dict, css_scheme: str,
                accento: str) -> str:
    """La pagina del riquadro, con i colori del tema dell'app."""
    blocchi = []
    molti = len(riferimento.voci) > 1
    for voce in riferimento.voci:
        testa = ""
        if molti:
            testa = (f"<div class='testa'><b>{html.escape(voce.titolo)}</b>"
                     f"<span>{html.escape(voce.pubblicazione)}</span></div>")
        corpo = voce.html
        blocchi.append(f"<section>{testa}{corpo}</section>")
    stile = f"""
    body {{ font-family: sans-serif; font-size: 15px; line-height: 1.45;
            margin: 0; padding: 10px 14px 24px 14px;
            background: {colori['sfondo']}; color: {colori['testo']}; }}
    :root {{ color-scheme: {css_scheme}; }}
    section {{ padding: 6px 0 12px 0; border-bottom: 1px solid {colori['bordo']}; }}
    section:last-child {{ border-bottom: none; }}
    .testa {{ display: flex; flex-direction: column; margin-bottom: 6px; }}
    .testa span {{ font-size: 12px; color: {colori['grigio']}; }}
    a {{ color: #2878bb; text-decoration: none; border-bottom: none; }}
    a.vx, a.vp, a.vl {{ color: #2878bb; font-weight: 600; }}
    a.cl strong {{ color: #2878bb; }}
    h1, h2 {{ font-size: 17px; margin: 8px 0; }}
    img {{ max-width: 100%; height: auto; }}
    p {{ margin: 6px 0; }}
    ol.source {{ list-style: none; padding: 0; margin: 8px 0; }}
    ol.source li {{ margin: 0 0 12px 0; }}
    ol.source p {{ margin: 2px 0; }}
    .alternatePresentation {{ display: none; }}
    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: {accento}; border-radius: 3px; }}
    """
    return ("<html><head><meta charset='UTF-8'><style>" + stile
            + "</style></head><body>" + "".join(blocchi) + "</body></html>")


def pagina_messaggio(testo: str, colori: dict, css_scheme: str,
                     collegamento: tuple[str, str] | None = None) -> str:
    """Una pagina con una riga di testo e, se serve, un collegamento da premere."""
    link = ""
    if collegamento:
        indirizzo, etichetta = collegamento
        link = (f"<p><a href='{html.escape(indirizzo)}'>"
                f"{html.escape(etichetta)}</a></p>")
    return (
        "<html><head><meta charset='UTF-8'><style>"
        f"body{{font-family:sans-serif;padding:24px;text-align:center;"
        f"background:{colori['sfondo']};color:{colori['grigio']}}}"
        f"a{{color:{colori['testo']};font-weight:600}}"
        f":root{{color-scheme:{css_scheme};}}</style></head>"
        f"<body>{html.escape(testo)}{link}</body></html>")
