#
#  Ext_FileManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Estensioni su FileManager.

Su macOS ``FileManager.getDocumentsDirectory()`` restituiva il contenitore
sandbox dell'app.  Su Linux l'equivalente e' la cartella dati XDG, e la
calcola ``Paths.root``.  Qui si richiama ``Paths`` invece di rifare la
logica: vedi la lezione sulle estensioni in COME-FUNZIONA.txt sezione 10,
"UN posto solo dove stanno i dati".

In Swift erano metodi statici ed un metodo d'istanza su ``FileManager``.
Qui sono funzioni: ``get_documents_directory()``, ``article_exist(path)``,
``extracted_jwpub_exist(url)``, ``copyfile_to_user_document_directory(...)``.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from Utility.Structures.Paths import Paths

# La cartella "bundle" dell'app: dove sta il codice e la cartella Files/.
# In Swift era Bundle.main.path(forResource:ofType:).
BUNDLE_DIR = Path(__file__).resolve().parent.parent.parent


def get_documents_directory() -> Path:
    """La radice dei dati.  macOS: ~/Documents/JWLibrary.  Linux: ~/.local/share/JWLibrary."""
    return Paths.root


def bundle_path(file_name: str, file_ext: str) -> Path | None:
    """Dov'e' una risorsa nella cartella Files/, o None se non c'e'."""
    candidate = BUNDLE_DIR / "Files" / f"{file_name}.{file_ext}"
    return candidate if candidate.is_file() else None


def copyfile_to_user_document_directory(dest_path: Path) -> bool:
    """Copia da Files/ alla cartella dati, senza sovrascrivere.

    Swift separava il nome sul punto e chiedeva il bundle.  Qui il bundle e'
    una cartella vera (``Files/``) e la divisione la fa pathlib, quindi un
    nome con piu' punti non viene piu' tagliato a meta'.
    """
    dest_path = Path(dest_path)
    source = bundle_path(dest_path.stem, dest_path.suffix.lstrip("."))
    if source is None:
        return False
    if dest_path.exists():
        return False
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest_path)
    return True


def article_exist(path: str) -> bool:
    """Esiste gia' l'articolo scaricato?  Esempio: ``nwt_I/66/22.html``."""
    return (get_documents_directory() / path).exists()


def extracted_jwpub_exist(url) -> bool:
    """Il .jwpub e' gia' stato scompattato?

    In Swift si toglieva ".jwpub" dal nome e si chiedeva se esisteva la
    cartella.  Esempio: https://.../nwt_I.jwpub -> ~/.../nwt_I/ esiste.
    """
    name = Path(str(url)).name.replace(".jwpub", "")
    return (get_documents_directory() / name).exists()