"""Che formati ha una pubblicazione sul sito (API pub-media di jw-cdn).

REGOLA: il JWPUB e' sempre la prima scelta, e il suo scarico passa dal catalogo
(nessun altro formato compare nell'elenco delle pubblicazioni).  Gli altri
formati servono solo per materiale che sul sito esiste in quel formato e basta:
in quel caso si prende il PDF (EPUB non si legge nell'app: si apre la pagina web).
Da un thread.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

_API = ("https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS?output=json"
        "&pub={pub}&langwritten={lingua}&fileformat=JWPUB,PDF,EPUB&alllangs=0{extra}")


def formati(sigla: str, lingua: str = "I", numero: str = "") -> dict[str, str]:
    """{"JWPUB": url, "PDF": url, "EPUB": url} con quelli che esistono.  {} se non risponde."""
    if not sigla:
        return {}
    extra = f"&issue={urllib.parse.quote(numero)}" if numero else ""
    url = _API.format(pub=urllib.parse.quote(sigla), lingua=urllib.parse.quote(lingua), extra=extra)
    try:
        richiesta = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(richiesta, timeout=15) as r:
            dati = json.load(r)
        file = (dati.get("files") or {}).get(lingua) or {}
        return {fmt: voci[0]["file"]["url"] for fmt, voci in file.items() if voci}
    except Exception:  # noqa: BLE001 - offline, pubblicazione senza file, risposta strana
        return {}


def scegli(trovati: dict[str, str]) -> str:
    """Il formato da usare: JWPUB, poi PDF.  "" se non c'e' niente di leggibile qui."""
    for fmt in ("JWPUB", "PDF"):
        if fmt in trovati:
            return fmt
    return ""


def scarica_pdf(url: str, destinazione: Path) -> str:
    """Scarica il PDF in `destinazione` (via .part).  '' = fatto, altrimenti l'errore."""
    try:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        parziale = destinazione.with_suffix(".part")
        richiesta = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(richiesta, timeout=60) as r, open(parziale, "wb") as f:
            while blocco := r.read(1024 * 256):
                f.write(blocco)
        parziale.replace(destinazione)
        return ""
    except Exception as errore:  # noqa: BLE001
        return f"Non riesco a scaricare ({type(errore).__name__})"
