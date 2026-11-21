"""La ricerca di jw.org, la stessa del sito (b.jw-cdn.org/apis/search).

Il sito la chiama cosi' (visto nel log di rete esportato da Chrome):
  1. un token da  https://b.jw-cdn.org/tokens/jworg.jwt
  2. https://b.jw-cdn.org/apis/search/results/<LINGUA>/all?q=<testo>
     con l'intestazione  Authorization: Bearer <token>.
Le schede del sito (publications, videos, audio, bible) sono lo stesso indirizzo
con quel nome al posto di «all».

Funzioni di rete: da un thread, mai dal main thread.  Senza internet, o con un
errore, si restituisce una lista vuota: la ricerca locale resta quella che e'.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

_TOKEN_URL = "https://b.jw-cdn.org/tokens/jworg.jwt"
_API = "https://b.jw-cdn.org/apis/search/results/{lingua}/{scheda}?q={q}"
_AGENTE = {"User-Agent": "Mozilla/5.0"}
_token = ["", 0.0]          # (token, quando e' stato preso)
_VALIDO = 30 * 60           # un token si riusa mezz'ora


def _prendi_token() -> str:
    if _token[0] and time.time() - _token[1] < _VALIDO:
        return _token[0]
    with urllib.request.urlopen(
            urllib.request.Request(_TOKEN_URL, headers=_AGENTE), timeout=8) as r:
        _token[0], _token[1] = r.read().decode().strip(), time.time()
    return _token[0]


def _appiattisci(elementi: list) -> list[dict]:
    """I risultati arrivano a gruppi: si tolgono i gruppi e restano le voci."""
    fuori: list[dict] = []
    for e in elementi or []:
        if e.get("type") == "group":
            fuori.extend(_appiattisci(e.get("results") or []))
        elif e.get("type") == "item":
            fuori.append(e)
    return fuori


def _voce(e: dict) -> dict | None:
    sottotipo = e.get("subtype") or ""
    if sottotipo in ("language", "alert"):
        return None
    lank = e.get("lank") or ""
    link = e.get("links") or {}
    docid = int(lank[3:]) if lank.startswith("pa-") and lank[3:].isdigit() else 0
    # La sigla c'e' solo per le PUBBLICAZIONI (lank «pub-lffi»): video e audio hanno
    # un lank «pub-xxx_NN_VIDEO» che e' una traccia, non una pubblicazione.
    sigla = lank[4:] if lank.startswith("pub-") and sottotipo == "publication" else ""
    if not docid:
        m = re.search(r"docid=(\d+)", link.get("jw.org", "") + link.get("wol", ""))
        docid = int(m.group(1)) if m and sottotipo not in ("video", "audio") else 0
    edizione = ""
    if sottotipo == "periodical":
        # «pi-w_201812»: la rivista w, numero dicembre 2018
        m = re.match(r"pi-(.+?)_(\d{6,8})$", lank)
        if m:
            sigla, edizione = m.group(1), m.group(2)
    if not sigla and sottotipo == "publication":
        sigla = e.get("printReference") or ""
    if not (sigla or docid or lank):
        return None
    titolo = re.sub(r"<[^>]+>", "", (e.get("title") or "").replace("&nbsp;", " "))
    return {"tipo": "web", "titolo": titolo,
            "contesto": e.get("context") or "", "sottotipo": sottotipo,
            "sigla": sigla, "edizione": edizione, "docid": docid, "lank": lank,
            "durata": e.get("duration") or "",
            "immagine": (e.get("image") or {}).get("url", ""),
            "anteprima": (e.get("snippet") or "").replace("<strong>", "<b>")
                                                 .replace("</strong>", "</b>"),
            "wol": link.get("wol", ""), "jw": link.get("jw.org", "")}


def _chiedi(percorso: str) -> dict:
    richiesta = urllib.request.Request(
        "https://b.jw-cdn.org" + percorso,
        headers={**_AGENTE, "Authorization": f"Bearer {_prendi_token()}"})
    with urllib.request.urlopen(richiesta, timeout=15) as r:
        return json.load(r)


#: Le schede e gli ordinamenti del sito: (chiave nell'indirizzo, etichetta)
FILTRI = (("all", "Tutto"), ("publications", "Pubblicazioni"), ("videos", "Video"),
          ("audio", "Audio"), ("bible", "Bibbia"))
ORDINI = (("rel", "Rilevanza"), ("newest", "Dal più recente"), ("oldest", "Dal meno recente"))
PER_PAGINA = 12


def pagina(domanda: str, lingua: str = "I", filtro: str = "all", ordine: str = "rel",
           offset: int = 0) -> dict:
    """Una pagina di risultati, come la pagina di ricerca del sito.

    {"sezioni": [{"titolo": str, "voci": [voce, ...]}], "etichetta": "Risultati 1 - 12 di 834",
     "pagine": [{"tipo", "label", "offset", "selezionata"}], "errore": bool}
    """
    vuoto = {"sezioni": [], "etichetta": "", "pagine": [], "errore": False}
    domanda = (domanda or "").strip()
    if len(domanda) < 2:
        return vuoto
    try:
        d = _chiedi(f"/apis/search/results/{urllib.parse.quote(lingua)}/{filtro}"
                    f"?sort={ordine}&offset={int(offset)}&limit={PER_PAGINA}"
                    f"&q={urllib.parse.quote(domanda)}")
    except Exception:  # noqa: BLE001
        _token[0] = ""
        return {**vuoto, "errore": True}
    sezioni = []
    elementi = d.get("results") or []
    for e in elementi:
        if e.get("type") == "group":
            voci = [v for v in map(_voce, _appiattisci(e.get("results") or [])) if v]
            etichetta = re.sub(r"<[^>]+>", "", e.get("label") or "")
            if voci:
                sezioni.append({"titolo": etichetta, "voci": voci})
        elif e.get("type") == "item":
            v = _voce(e)
            if v:
                sezioni.append({"titolo": "", "voci": [v]})
    pag = d.get("pagination") or {}
    pagine = []
    for l in pag.get("links") or []:
        m = re.search(r"offset=(\d+)", l.get("link", ""))
        pagine.append({"tipo": l.get("type", ""), "label": l.get("label", ""),
                       "offset": int(m.group(1)) if m else 0,
                       "selezionata": bool(l.get("selected"))})
    return {"sezioni": sezioni, "etichetta": pag.get("label", ""), "pagine": pagine,
            "errore": False}


def url_media(lank: str, lingua: str = "I") -> str:
    """L'indirizzo del file di un video/audio dal suo «lank» (es. pub-nwtsv_420_VIDEO)."""
    m = re.match(r"pub-(.+?)_(\d+)_(VIDEO|AUDIO)$", lank or "")
    if not m:
        return ""
    sigla, traccia, tipo = m.group(1), m.group(2), m.group(3)
    formato = "MP4" if tipo == "VIDEO" else "MP3"
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS?output=json"
                f"&pub={urllib.parse.quote(sigla)}&track={traccia}&fileformat={formato}"
                f"&langwritten={urllib.parse.quote(lingua)}&alllangs=0",
                headers=_AGENTE), timeout=15) as r:
            dati = json.load(r)
        voci = ((dati.get("files") or {}).get(lingua) or {}).get(formato) or []
        if tipo == "VIDEO":     # la piu' grande fra le 720p o meno
            voci = sorted(voci, key=lambda v: (int((v.get("label") or "0p")[:-1] or 0) > 720,
                                               -int((v.get("label") or "0p")[:-1] or 0)))
        return voci[0]["file"]["url"] if voci else ""
    except Exception:  # noqa: BLE001
        return ""


def cerca(domanda: str, lingua: str = "I", scheda: str = "all",
          limite: int = 8) -> list[dict]:
    """I risultati del sito per `domanda`.  [] se non c'e' rete o non risponde."""
    domanda = (domanda or "").strip()
    if len(domanda) < 2:
        return []
    try:
        url = _API.format(lingua=urllib.parse.quote(lingua), scheda=scheda,
                          q=urllib.parse.quote(domanda))
        richiesta = urllib.request.Request(
            url, headers={**_AGENTE, "Authorization": f"Bearer {_prendi_token()}"})
        with urllib.request.urlopen(richiesta, timeout=10) as r:
            dati = json.load(r)
    except Exception:  # noqa: BLE001 - offline, token scaduto, sito che non risponde
        _token[0] = ""
        return []
    voci = [v for v in map(_voce, _appiattisci(dati.get("results"))) if v]
    return voci[:limite]
