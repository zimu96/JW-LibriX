"""Aggiornamento dell'app da GitHub.

Tutte le funzioni di rete vanno chiamate **da un thread**, mai dal main thread.

Due casi:
  * installazione da sorgenti (cartella con `jw.sh`): si scarica lo zip della
    versione nuova e si sovrascrivono i file del programma.  I dati
    (`dati/`, la cartella dati dell'utente) non si toccano: stanno altrove.
  * AppImage: la versione resta sempre «V1» (1.0.0), quindi il numero non dice
    se c'e' un file nuovo: si confronta l'impronta sha256 dell'AppImage in uso
    con quella dell'AppImage allegata alla release su GitHub.  Se differisce si
    scarica in `<AppImage>.part` (stessa cartella), si controlla dimensione e
    impronta, si sostituisce il vecchio file in un solo passaggio (`os.replace`)
    e l'app si riavvia dallo stesso percorso.  I dati stanno fuori.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import urllib.parse
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
        return "Da AppImage si usa aggiorna_appimage()."
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


# ---------------------------------------------------------------------------
# AppImage
# ---------------------------------------------------------------------------

def _sha256_file(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blocco)
    return h.hexdigest()


def appimage_nuova() -> tuple[dict | None, str]:
    """(asset_nuovo, errore).  asset = {url, size, sha256}; None = gia' aggiornata."""
    if not Versione.REPO_APP:
        return None, "L'indirizzo GitHub dell'app non e' configurato."
    url = f"https://api.github.com/repos/{Versione.REPO_APP}/releases/latest"
    try:
        richiesta = urllib.request.Request(url, headers={"User-Agent": "JW-LibriX"})
        with urllib.request.urlopen(richiesta, timeout=20) as r:
            dati = json.load(r)
        asset = next((a for a in dati.get("assets", [])
                      if str(a.get("name", "")).lower().endswith(".appimage")), None)
        if not asset:
            return None, "Nessuna AppImage nella versione su GitHub."
        remoto = str(asset.get("digest", "")).removeprefix("sha256:").lower()
        locale_p = Path(os.environ["APPIMAGE"])
        if remoto:
            if _sha256_file(locale_p) == remoto:
                return None, ""
        elif locale_p.stat().st_size == int(asset["size"]):
            return None, ""     # senza impronta, ci si fida della dimensione
        return {"url": asset["browser_download_url"], "size": int(asset["size"]),
                "sha256": remoto}, ""
    except Exception as errore:  # noqa: BLE001 - rete assente, limite, file non leggibile
        return None, f"Non riesco a controllare ({type(errore).__name__})"


def _aggiorna_voce_menu(appimage: Path) -> None:
    """Riscrive la voce di menu (stessa di AppRun) perche' punti al file nuovo."""
    dati = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    voce = dati / "applications" / "JWLibriX.desktop"
    if not voce.is_file():
        return
    testo = voce.read_text(encoding="utf-8")
    nuovo = re.sub(r'(?m)^Exec=.*$', lambda _: f'Exec="{appimage}"', testo)
    if nuovo != testo:
        voce.write_text(nuovo, encoding="utf-8")
        voce.chmod(0o755)
        os.system("update-desktop-database >/dev/null 2>&1")  # facoltativo


def aggiorna_appimage(asset: dict, avanzamento=None) -> str:
    """Scarica l'AppImage nuova e sostituisce quella in uso.  '' = fatto.

    Il nome del file puo' cambiare con la versione (V1 -> V1.0.1): il file nuovo
    prende il nome che ha su GitHub e il vecchio viene tolto: resta un solo file.
    La voce di menu (e con lei l'icona nella barra) viene riscritta subito e
    `APPIMAGE` punta al file nuovo (il riavvio parte da li').

    `avanzamento(percentuale)` (opzionale) viene chiamata dal thread di download.
    """
    vecchia = Path(os.environ["APPIMAGE"])
    attuale = vecchia.resolve()
    nome = Path(urllib.parse.unquote(urllib.parse.urlparse(asset["url"]).path)).name
    if not nome.lower().endswith(".appimage"):
        nome = attuale.name
    nuova = attuale.with_name(nome)
    if not os.access(attuale.parent, os.W_OK):
        return f"La cartella {attuale.parent} e' in sola lettura."
    parte = nuova.with_name(nuova.name + ".part")
    try:
        h = hashlib.sha256()
        totale = 0
        richiesta = urllib.request.Request(asset["url"], headers={"User-Agent": "JW-LibriX"})
        with urllib.request.urlopen(richiesta, timeout=60) as r, open(parte, "wb") as f:
            while blocco := r.read(1024 * 1024):
                f.write(blocco)
                h.update(blocco)
                totale += len(blocco)
                if avanzamento and asset["size"]:
                    avanzamento(min(99, totale * 100 // asset["size"]))
        if totale != asset["size"]:
            parte.unlink(missing_ok=True)
            return "Download incompleto: riprova."
        if asset["sha256"] and h.hexdigest() != asset["sha256"]:
            parte.unlink(missing_ok=True)
            return "Il file scaricato e' danneggiato: riprova."
        parte.chmod(0o755)
        os.replace(parte, nuova)        # un solo passaggio: o vecchio o nuovo
        if nuova != attuale:
            attuale.unlink(missing_ok=True)
        os.environ["APPIMAGE"] = str(nuova)
        _aggiorna_voce_menu(nuova)
    except Exception as errore:  # noqa: BLE001
        parte.unlink(missing_ok=True)
        return f"Non riesco ad aggiornare ({type(errore).__name__}: {errore})"
    return ""
