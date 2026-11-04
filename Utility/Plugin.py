"""I plugin: pezzi dell'app che si scaricano a parte.

Il primo e' il `timer`.  L'app funziona identica con o senza.

DOVE STANNO
-----------
In `plugin/<nome>/` dentro la cartella DATI (vedi `Paths`), non dentro il
programma: l'AppImage e' di sola lettura, e un aggiornamento dell'app non
deve toccare i plugin.

COSA DEVE CONTENERE UN PLUGIN
-----------------------------
    plugin.json   {"nome": "timer", "versione": "1.0.0", "entrata": "plugin.py"}
    plugin.py     con la funzione  crea_schermata() -> QWidget

DUE COSE DIVERSE: INSTALLATO E ATTIVO
-------------------------------------
`installato`: i file ci sono.  `attivo`: l'utente l'ha acceso nelle
impostazioni.  Il tasto nella barra viola compare solo se **tutte e due**
(`visibile`).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from Utility import tema
from Utility.Structures.Paths import Paths

MANIFESTO = "plugin.json"

#: I moduli dei plugin gia' caricati, per nome.
_moduli: dict = {}


def cartella(nome: str) -> Path:
    return Paths.plugin_path / nome


def manifesto(nome: str) -> dict | None:
    base = cartella(nome)
    if not (base / MANIFESTO).is_file():
        return None
    try:
        dati = json.loads((base / MANIFESTO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dati if isinstance(dati, dict) else None


def installato(nome: str) -> bool:
    dati = manifesto(nome)
    if dati is None:
        return False
    return (cartella(nome) / str(dati.get("entrata") or "plugin.py")).is_file()


def indirizzo(nome: str) -> str:
    """Da dove si scarica il plugin (vuoto se non e' configurato)."""
    from Utility import Versione
    return Versione.url_zip_timer() if nome == "timer" else ""


def installa(nome: str, su_progresso=None) -> str:
    """Scarica il plugin da GitHub e lo mette nella cartella dati.

    Va chiamata **da un thread**, non dal main thread: scarica e scompatta.
    `su_progresso(letti, totale)` e' facoltativo.  Ritorna '' se e' andata
    bene, altrimenti il motivo dell'errore.

    Il plugin sta nella cartella dei dati (`plugin/<nome>/`), non dentro il
    programma: un aggiornamento dell'app non lo tocca, e un aggiornamento del
    plugin non tocca l'app.  Riscaricarlo lo aggiorna.
    """
    import io
    import shutil
    import tempfile
    import urllib.request
    import zipfile

    url = indirizzo(nome)
    if not url:
        return "L'indirizzo del plugin non e' ancora configurato."
    try:
        with urllib.request.urlopen(url, timeout=60) as risposta:
            totale = int(risposta.headers.get("Content-Length") or 0)
            pezzi, letti = [], 0
            while True:
                pezzo = risposta.read(65536)
                if not pezzo:
                    break
                pezzi.append(pezzo)
                letti += len(pezzo)
                if su_progresso is not None:
                    su_progresso(letti, totale)
        dati = b"".join(pezzi)
    except Exception as errore:  # noqa: BLE001 - rete assente, 404, timeout
        return f"Non riesco a scaricare il plugin ({type(errore).__name__}: {errore})"

    try:
        with tempfile.TemporaryDirectory() as temporanea:
            radice = Path(temporanea).resolve()
            with zipfile.ZipFile(io.BytesIO(dati)) as archivio:
                for voce in archivio.namelist():
                    if not (radice / voce).resolve().is_relative_to(radice):
                        return "Archivio non valido (percorso fuori dalla cartella)."
                archivio.extractall(radice)
            # GitHub mette tutto dentro una cartella (`nome-v1.0.0/`): si cerca
            # quella che contiene plugin.json.
            trovati = [m.parent for m in radice.rglob(MANIFESTO)]
            if not trovati:
                return "L'archivio non contiene un plugin (manca plugin.json)."
            sorgente = min(trovati, key=lambda p: len(p.parts))
            destinazione = cartella(nome)
            destinazione.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(sorgente, destinazione, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    except (OSError, zipfile.BadZipFile) as errore:
        return f"{type(errore).__name__}: {errore}"
    return "" if installato(nome) else "Installazione incompleta: manca plugin.json o plugin.py."


def versione(nome: str) -> str:
    return str((manifesto(nome) or {}).get("versione") or "")


def _chiave(nome: str) -> str:
    return f"plugin_{nome}_attivo"


def attivo(nome: str) -> bool:
    return bool(tema.impostazioni().get(_chiave(nome), False))


def imposta_attivo(nome: str, valore: bool) -> None:
    tema.salva_impostazione(_chiave(nome), bool(valore))


def visibile(nome: str) -> bool:
    return installato(nome) and attivo(nome)


def crea_schermata(nome: str):
    """La schermata del plugin, o `(None, motivo)` se non si riesce.

    Un plugin rotto non deve buttare giu' l'app: l'errore torna come testo
    e la finestra lo mostra al posto della schermata.
    """
    if not installato(nome):
        return None, "Plugin non installato."
    base = cartella(nome)
    entrata = base / str(manifesto(nome).get("entrata") or "plugin.py")
    try:
        nome_modulo = f"plugin_{nome}"
        specifica = importlib.util.spec_from_file_location(nome_modulo, entrata)
        modulo = importlib.util.module_from_spec(specifica)
        # i file del plugin si importano fra loro per nome
        if str(base) not in sys.path:
            sys.path.insert(0, str(base))
        sys.modules[nome_modulo] = modulo
        specifica.loader.exec_module(modulo)
        _moduli[nome] = modulo
        return modulo.crea_schermata(), ""
    except Exception as errore:  # noqa: BLE001 - un plugin non deve rompere l'app
        return None, f"{type(errore).__name__}: {errore}"


def modulo(nome: str):
    """Il modulo del plugin se e' gia' stato caricato, altrimenti None."""
    return _moduli.get(nome)


def schermo(nome: str) -> str:
    """Il nome dello schermo scelto per il monitor del plugin, o '' (spento)."""
    return str(tema.impostazioni().get(f"plugin_{nome}_schermo") or "")


def imposta_schermo(nome: str, schermo_scelto: str) -> None:
    tema.salva_impostazione(f"plugin_{nome}_schermo", schermo_scelto or "")


def tema_cambiato(nome: str, finestra, chiaro: bool) -> None:
    """L'app ha cambiato tema: il plugin riapplica i suoi colori."""
    m = _moduli.get(nome)
    if m is not None and finestra is not None and hasattr(m, "applica_tema"):
        try:
            m.applica_tema(finestra, chiaro)
        except Exception as errore:  # noqa: BLE001 - il tema non deve rompere l'app
            print(f"Plugin {nome}: tema non applicato ⚠️  {errore}")
