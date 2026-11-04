#
#  BibbiaOnline.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La Bibbia in una lingua senza il pacchetto da 122 MB.

I nomi dei 66 libri si chiedono al sito con **una sola richiesta** (la pagina
dell'indice della Bibbia, circa 7 KB compressa) e si ricordano su disco.  I
capitoli si scaricano quando si leggono e restano nella cartella
``nwtsty_<lingua>``: quello che hai letto funziona anche senza internet.
"""

from __future__ import annotations

import gzip
import json
import re
import urllib.error
import urllib.request

from Utility import Lingua, WolLingua
from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility.Structures.Generals import BibleBook

_AGENTE = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
_RE_LIBRO = re.compile(
    r'data-bookid="(\d+)"[^>]*>.*?class="title ellipsized name">(.*?)</span>', re.S)


def cartella(simbolo: str):
    return get_documents_directory() / f"nwtsty_{simbolo}"


def capitoli_su_disco(simbolo: str) -> int:
    try:
        return sum(1 for _ in cartella(simbolo).glob("*/*.html"))
    except OSError:
        return 0


def _file():
    percorso = get_documents_directory() / "userData"
    percorso.mkdir(parents=True, exist_ok=True)
    return percorso / "bibbia_libri.json"


def _memoria() -> dict:
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _dal_sito(simbolo: str) -> list | None:
    codici = WolLingua.codici(simbolo)
    if codici is None:
        return None
    indirizzo = f"{WolLingua.BASE}/{codici[0]}/wol/binav/{codici[1]}/{codici[2]}/nwtsty"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(indirizzo, headers=_AGENTE), timeout=20) as r:
            grezzo = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                grezzo = gzip.decompress(grezzo)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    nomi = {}
    for numero, nome in _RE_LIBRO.findall(grezzo.decode("utf-8", "replace")):
        pulito = re.sub(r"<[^>]+>", "", nome).strip()
        if 1 <= int(numero) <= 66 and pulito:
            nomi.setdefault(int(numero), pulito)
    titoli = [re.sub(r"<[^>]+>", "", t).strip() for t in
              re.findall(r'class="group grid">(.*?)</div>', grezzo.decode("utf-8", "replace"))]
    if len(nomi) != 66:
        return None
    return {"libri": [[n, nomi[n]] for n in sorted(nomi)], "titoli": titoli[:2]}


def _voce(simbolo: str, rete: bool) -> dict | None:
    """I libri e i titoli dei due gruppi: dalla memoria, o dal sito."""
    noti = _memoria()
    voce = noti.get(simbolo)
    if not isinstance(voce, dict) and rete:
        voce = _dal_sito(simbolo)
        if voce is not None:
            noti[simbolo] = voce
            try:
                _file().write_text(json.dumps(noti), encoding="utf-8")
            except OSError:
                pass
    return voce if isinstance(voce, dict) else None


def titoli(simbolo: str) -> list[str] | None:
    """I nomi dei due gruppi (Scritture ebraiche e greche) nella lingua, se noti."""
    voce = _voce(simbolo, rete=False)
    elenco = voce.get("titoli") if voce else None
    return elenco if elenco and len(elenco) == 2 else None


def libri(simbolo: str, rete: bool = True) -> list[BibleBook]:
    """I 66 libri nella lingua, dalla memoria o dal sito.  Vuoto se non si sa."""
    from Utility.Traduzioni import CAPITOLI

    voce = _voce(simbolo, rete)
    elenco = voce.get("libri") if voce else None
    if not elenco:
        return []
    return [BibleBook(ID=n, shortName=nome, fullName=nome, chapters=CAPITOLI[n - 1])
            for n, nome in elenco]
