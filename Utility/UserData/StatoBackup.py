#
#  StatoBackup.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Quali file di backup ha creato l'app, e cosa farne.

Si ricordano due percorsi in ``impostazioni.json``:

    backup_esportato   l'ultimo file scelto con «Esporta» (in qualunque cartella)
    backup_condiviso   la copia fatta per inviarla (Bluetooth, KDE Connect, ...)

Regole:
- un backup nuovo **sostituisce** il precedente dello stesso tipo: il vecchio si
  elimina, senza scelta, perche' il nuovo contiene gia' tutto quello che aveva;
- dopo un invio riuscito si elimina la copia dal computer, se l'utente non ha
  tolto la spunta;
- «Elimina» cancella i file ricordati; se uno non c'e' piu' lo dice.

Si eliminano solo file che l'app ha creato e di cui ha ricordato il percorso.
"""
from __future__ import annotations

import json
from pathlib import Path

CH_ESPORTATO = "backup_esportato"
CH_CONDIVISO = "backup_condiviso"
CH_ELIMINA_DOPO = "backup_elimina_dopo_invio"


def _file() -> Path:
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "userData" / "impostazioni.json"


def _leggi() -> dict:
    try:
        percorso = _file()
        if percorso.is_file():
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def _scrivi(chiave: str, valore) -> None:
    try:
        percorso = _file()
        percorso.parent.mkdir(parents=True, exist_ok=True)
        dati = _leggi()
        dati[chiave] = valore
        percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
    except OSError as errore:
        print(f"Non riesco a salvare {chiave} ⚠️  {errore}")


def elimina_dopo_invio() -> bool:
    return bool(_leggi().get(CH_ELIMINA_DOPO, True))


def imposta_elimina_dopo_invio(valore: bool) -> None:
    _scrivi(CH_ELIMINA_DOPO, bool(valore))


def _registra(chiave: str, nuovo: Path | None) -> None:
    """Ricorda il nuovo file e butta il precedente (se e' un altro)."""
    vecchio = _leggi().get(chiave)
    if vecchio and (nuovo is None or Path(vecchio) != Path(nuovo)):
        try:
            Path(vecchio).unlink(missing_ok=True)
            print(f"Backup precedente eliminato [{vecchio}] 🗑️")
        except OSError as errore:
            print(f"Non riesco a eliminare il backup precedente ⚠️  {errore}")
    _scrivi(chiave, str(nuovo) if nuovo else None)


def registra_esportato(percorso) -> None:
    _registra(CH_ESPORTATO, Path(percorso))


def registra_condiviso(percorso) -> None:
    _registra(CH_CONDIVISO, Path(percorso))


def dimentica_condiviso_eliminando() -> None:
    """Dopo un invio riuscito: via la copia dal computer."""
    _registra(CH_CONDIVISO, None)


def ricordati() -> list[Path]:
    dati = _leggi()
    return [Path(dati[c]) for c in (CH_ESPORTATO, CH_CONDIVISO) if dati.get(c)]


def elimina_tutti() -> tuple[list[Path], list[Path]]:
    """Elimina i file ricordati.  Ritorna (eliminati, non_trovati)."""
    eliminati, mancanti = [], []
    for percorso in ricordati():
        try:
            if percorso.is_file():
                percorso.unlink()
                eliminati.append(percorso)
            else:
                mancanti.append(percorso)
        except OSError as errore:
            print(f"Non riesco a eliminare {percorso} ⚠️  {errore}")
            mancanti.append(percorso)
    _scrivi(CH_ESPORTATO, None)
    _scrivi(CH_CONDIVISO, None)
    return eliminati, mancanti
