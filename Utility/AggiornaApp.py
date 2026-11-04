"""Aggiornamento dell'app da GitHub.

Tutte le funzioni di rete vanno chiamate **da un thread**, mai dal main thread.

Due casi:
  * installazione da sorgenti (cartella con `jw.sh`): si scarica lo zip della
    versione nuova e si sovrascrivono i file del programma.  I dati
    (`dati/`, la cartella dati dell'utente) non si toccano: stanno altrove.
  * AppImage: il file e' in sola lettura, quindi l'app non puo' cambiarsi da
    sola; si manda l'utente alla pagina della versione nuova.
"""

import io
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from Utility import Versione

RADICE = Path(__file__).resolve().parent.parent


def e_appimage() -> bool:
    return bool(os.environ.get("APPIMAGE"))


def _numeri(versione: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", versione)[:3])


def ultima_versione() -> tuple[str, str]:
    """(versione_ultima, errore).  La versione e' senza la «v», es. '1.0.1'."""
    if not Versione.REPO_APP:
        return "", "L'indirizzo GitHub dell'app non e' configurato."
    url = f"https://api.github.com/repos/{Versione.REPO_APP}/releases/latest"
    try:
        richiesta = urllib.request.Request(url, headers={"User-Agent": "JW-LibriX"})
        with urllib.request.urlopen(richiesta, timeout=20) as r:
            dati = json.load(r)
        return str(dati.get("tag_name", "")).lstrip("vV"), ""
    except Exception as errore:  # noqa: BLE001 - rete assente, 404 (nessuna versione), limite
        return "", f"Non riesco a controllare ({type(errore).__name__})"


def e_piu_nuova(ultima: str) -> bool:
    try:
        return _numeri(ultima) > _numeri(Versione.VERSIONE_APP)
    except ValueError:
        return False


def aggiorna(versione: str) -> str:
    """Scarica la versione e sovrascrive il programma.  '' = fatto, altrimenti l'errore."""
    if e_appimage():
        return "Da AppImage non si aggiorna da sola: scarica il file nuovo dalla pagina delle versioni."
    if not os.access(RADICE, os.W_OK):
        return "La cartella del programma e' in sola lettura."
    url = f"https://github.com/{Versione.REPO_APP}/archive/refs/tags/v{versione}.zip"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            dati = r.read()
    except Exception as errore:  # noqa: BLE001
        return f"Non riesco a scaricare ({type(errore).__name__})"
    try:
        with tempfile.TemporaryDirectory() as temporanea:
            radice = Path(temporanea).resolve()
            with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
                for voce in archivio.namelist():
                    if not (radice / voce).resolve().is_relative_to(radice):
                        return "Archivio non valido."
                archivio.extractall(radice)
            trovati = [m.parent for m in radice.rglob("JWLibraryApp.py")]
            if not trovati:
                return "L'archivio non contiene l'app."
            sorgente = min(trovati, key=lambda p: len(p.parts))
            shutil.copytree(sorgente, RADICE, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "dati"))
    except (OSError, zipfile.BadZipFile) as errore:
        return f"{type(errore).__name__}: {errore}"
    return ""
