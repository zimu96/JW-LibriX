"""I file esterni aggiunti a mano ai contenuti di una pagina di adunanza.

Si ricorda solo il percorso del file originale: niente copie, quindi niente
doppioni.  «Togli» dimentica il percorso e non tocca mai il file sul disco.

Documenti (PDF, Word, Excel, LibreOffice...): si mostrano come PDF.  I PDF
si aprono cosi' come sono; gli altri si convertono una volta con LibreOffice e
il risultato resta in una cartella di cache, legato al file e alla sua data.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

FILE_ESTERNI = "file_esterni.json"

IMMAGINI = {".jpg", ".jpeg", ".jfif", ".png", ".gif", ".bmp", ".webp", ".svg", ".svgz",
            ".avif", ".heic", ".heif", ".jxl", ".tif", ".tiff", ".ico", ".tga", ".jp2"}
VIDEO = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpg",
         ".mpeg", ".ts", ".m2ts", ".3gp", ".ogv", ".av1", ".ivf", ".hevc", ".h264"}
AUDIO = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma", ".mka"}
PDF = {".pdf"}
OFFICE = {".doc", ".docx", ".odt", ".rtf", ".txt", ".xls", ".xlsx", ".ods", ".csv",
          ".ppt", ".pptx", ".odp"}


def _percorso() -> Path:
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / FILE_ESTERNI


def chiave(pub, documento) -> str:
    """Una pagina di adunanza: la pubblicazione e il suo documento."""
    return f"{pub.keySymbol}:{documento.documentId}"


def tipo_di(percorso) -> str | None:
    """«immagine», «video», «audio», «documento», o None se non si sa aprire."""
    estensione = Path(percorso).suffix.lower()
    if estensione in IMMAGINI:
        return "immagine"
    if estensione in VIDEO:
        return "video"
    if estensione in AUDIO:
        return "audio"
    if estensione in PDF or estensione in OFFICE:
        return "documento"
    return None


def _leggi_tutto() -> dict:
    try:
        percorso = _percorso()
        if percorso.is_file():
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            if isinstance(dati, dict):
                return dati
    except (OSError, ValueError) as errore:
        print(f"File esterni illeggibili, uso un elenco vuoto ⚠️  {errore}")
    return {}


def _scrivi_tutto(dati: dict) -> None:
    try:
        percorso = _percorso()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a salvare i file esterni ⚠️  {errore}")


def leggi(chiave_pagina: str) -> list[str]:
    return [str(p) for p in _leggi_tutto().get(chiave_pagina, [])]


def aggiungi(chiave_pagina: str, percorsi) -> list[str]:
    """Aggiunge i file riconosciuti; restituisce quelli scartati."""
    dati = _leggi_tutto()
    elenco = dati.setdefault(chiave_pagina, [])
    scartati: list[str] = []
    for percorso in percorsi:
        percorso = str(percorso)
        if tipo_di(percorso) is None:
            scartati.append(percorso)
        elif percorso not in elenco:
            elenco.append(percorso)
    _scrivi_tutto(dati)
    return scartati


def togli(chiave_pagina: str, percorso: str) -> None:
    """Dimentica il file: sul disco non si tocca niente."""
    dati = _leggi_tutto()
    elenco = dati.get(chiave_pagina, [])
    if percorso in elenco:
        elenco.remove(percorso)
        if not elenco:
            dati.pop(chiave_pagina, None)
        _scrivi_tutto(dati)


# ----------------------------------------------------------------------
# I MEDIA DELL'APP AGGIUNTI A MANO
# ----------------------------------------------------------------------
#
# Un video o un audio del catalogo (non un file del computer) si ricorda come
# una piccola scheda: quale e' (sigla, traccia, numero, lingua) e il titolo.
# Il file vero lo scarica l'app come sempre.  Stanno nello stesso file dei
# file esterni, sotto la chiave «<pagina>#media», cosi' chi legge solo i
# percorsi non li vede.

_CAMPI_MEDIA = ("tipo", "sigla", "traccia", "numero", "lingua", "titolo")


def _chiave_media(chiave_pagina: str) -> str:
    return f"{chiave_pagina}#media"


def _stessa(a: dict, b: dict) -> bool:
    return (a.get("sigla"), int(a.get("traccia") or 0), int(a.get("numero") or 0),
            a.get("tipo")) == (b.get("sigla"), int(b.get("traccia") or 0),
                               int(b.get("numero") or 0), b.get("tipo"))


def leggi_media(chiave_pagina: str) -> list[dict]:
    elenco = _leggi_tutto().get(_chiave_media(chiave_pagina), [])
    return [dict(v) for v in elenco if isinstance(v, dict) and v.get("sigla")]


def aggiungi_media(chiave_pagina: str, voce_media: dict) -> bool:
    """Aggiunge un media dell'app; False se c'era gia'."""
    scheda = {c: voce_media.get(c) for c in _CAMPI_MEDIA}
    dati = _leggi_tutto()
    elenco = dati.setdefault(_chiave_media(chiave_pagina), [])
    if any(isinstance(v, dict) and _stessa(v, scheda) for v in elenco):
        return False
    elenco.append(scheda)
    _scrivi_tutto(dati)
    return True


def togli_media(chiave_pagina: str, voce_media: dict) -> None:
    dati = _leggi_tutto()
    k = _chiave_media(chiave_pagina)
    elenco = [v for v in dati.get(k, []) if not (isinstance(v, dict) and _stessa(v, voce_media))]
    if elenco:
        dati[k] = elenco
    else:
        dati.pop(k, None)
    _scrivi_tutto(dati)


def voce(percorso: str) -> dict:
    """La voce per `ContenutiView`, con la stessa forma di quelle della pagina."""
    file = Path(percorso)
    tipo = tipo_di(file) or "documento"
    miniatura = None
    if tipo == "immagine" and file.is_file():
        from PyQt6.QtCore import QBuffer, QIODevice, Qt
        from PyQt6.QtGui import QImageReader
        lettore = QImageReader(str(file))
        lettore.setAutoTransform(True)
        dimensione = lettore.size()
        if dimensione.isValid():
            lettore.setScaledSize(dimensione.scaled(
                352, 198, Qt.AspectRatioMode.KeepAspectRatio))
        immagine = lettore.read()
        if not immagine.isNull():
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            immagine.save(buffer, "PNG")
            miniatura = bytes(buffer.data())
    return {"tipo": tipo, "titolo": file.stem, "file": str(file), "percorso": str(file),
            "esterno": True, "scaricato": True, "mancante": not file.is_file(),
            "miniatura": miniatura, "dati": None}


def _libreoffice() -> str | None:
    """Il programma LibreOffice, se c'e': nel PATH o nei posti usuali di macOS/Windows."""
    trovato = shutil.which("soffice") or shutil.which("libreoffice")
    if trovato:
        return trovato
    usuali = ["/Applications/LibreOffice.app/Contents/MacOS/soffice",
              r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"]
    return next((p for p in usuali if Path(p).is_file()), None)


def in_pdf(percorso: str) -> Path:
    """Il PDF da mostrare per quel file; converte con LibreOffice se serve.

    Blocca (anche decine di secondi per un file grande): da chiamare in un thread.
    """
    file = Path(percorso)
    if file.suffix.lower() in PDF:
        return file
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    firma = hashlib.sha1(f"{file}|{file.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    cartella = get_documents_directory() / "cache_documenti" / firma
    risultato = cartella / (file.stem + ".pdf")
    if risultato.is_file():
        return risultato
    programma = _libreoffice()
    if programma is None:
        raise RuntimeError("Per aprire Word, Excel e documenti LibreOffice serve LibreOffice "
                           "(libreoffice.org). I PDF si aprono anche senza.")
    cartella.mkdir(parents=True, exist_ok=True)
    esito = subprocess.run(
        [programma, "--headless", "--convert-to", "pdf", "--outdir", str(cartella), str(file)],
        capture_output=True, timeout=180)
    if not risultato.is_file():
        shutil.rmtree(cartella, ignore_errors=True)
        raise RuntimeError("Non riesco a convertire il documento: "
                           + esito.stderr.decode(errors="replace")[:200])
    return risultato
