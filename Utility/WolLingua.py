#
#  WolLingua.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Gli indirizzi di wol.jw.org in ogni lingua.

Ogni lingua ha il suo indirizzo, con due codici che non si indovinano
(``r6/lp-i`` italiano, ``r1/lp-e`` inglese, ``r4/lp-s`` spagnolo).  Sbagliare
codice non da' errore: il sito risponde con il testo italiano.  Per questo il
codice si **chiede** al sito, una volta per lingua (``wol.jw.org/<iso>`` risponde
con un redirect che lo contiene) e si ricorda su disco.

Chi cerca testo in una lingua passa di qui, cosi' c'e' un posto solo che sa
come si costruisce l'indirizzo.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from Utility.Extensions.Ext_FileManager import get_documents_directory

BASE = "https://wol.jw.org"
TIMEOUT = 20
_AGENTE = {"User-Agent": "Mozilla/5.0"}
_RE_CODICI = re.compile(r"^/([^/]+)/wol/h/(r\d+)/(lp-[a-z]+)$")
_memoria: dict[str, list] = {}


class _SenzaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _file():
    cartella = get_documents_directory() / "userData"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella / "wol_codici.json"


def _carica() -> dict:
    if not _memoria:
        try:
            _memoria.update(json.loads(_file().read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return _memoria


def _salva(simbolo: str, valore: list) -> None:
    _memoria[simbolo] = valore
    try:
        _file().write_text(json.dumps(_memoria), encoding="utf-8")
    except OSError:
        pass


def _voce(simbolo: str) -> dict:
    from Utility import Lingua
    return Lingua.per_simbolo(simbolo) or {}


def _chiedi(simbolo: str):
    """[lingua, r, lp]; [] se il sito non ha quella lingua; None se non si e' potuto chiedere.

    Per una lingua che non conosce il sito risponde con l'inglese, senza errore:
    si accetta il risultato solo se il codice ``lp-`` e' quello del simbolo della
    lingua (``lp-x`` per il tedesco, ``X``), altrimenti sarebbe testo inglese.
    """
    iso = (_voce(simbolo).get("iso") or "").strip()
    if not iso:
        return []
    try:
        urllib.request.build_opener(_SenzaRedirect).open(
            urllib.request.Request(f"{BASE}/{iso}", headers=_AGENTE), timeout=TIMEOUT)
        return []
    except urllib.error.HTTPError as errore:
        percorso = urllib.parse.urlparse(errore.headers.get("Location", "")).path
        trovato = _RE_CODICI.match(percorso)
        if trovato and trovato.group(3) == f"lp-{simbolo.lower()}":
            return list(trovato.groups())
        return []
    except (urllib.error.URLError, OSError):
        return None


def codici(simbolo: str) -> tuple[str, str, str] | None:
    """(lingua, r, lp) della lingua nel sito, o None se non ci sono (o non si sa)."""
    noti = _carica()
    if simbolo not in noti:
        risposta = _chiedi(simbolo)
        if risposta is None:
            return None
        _salva(simbolo, risposta)
    return tuple(noti[simbolo]) if noti[simbolo] else None


def supportata(simbolo: str) -> bool:
    """Il sito ha il testo in questa lingua?  Senza rete si presume di si'."""
    return codici(simbolo) is not None or _carica().get(simbolo) != []


def _base(simbolo: str | None, tipo: str) -> str:
    if not simbolo:
        from Utility import Lingua
        simbolo = Lingua.corrente_simbolo()
    voce = codici(simbolo)
    if voce is None:
        # Mai un indirizzo di ripiego: un codice sbagliato da' testo di un'altra lingua.
        return ""
    return f"{BASE}/{voce[0]}/wol/{tipo}/{voce[1]}/{voce[2]}"


def url_documento(documento: int, simbolo: str | None = None) -> str:
    """L'indirizzo di un documento (``MepsDocumentId``) nella lingua, o "" se non c'e'."""
    base = _base(simbolo, "d")
    return f"{base}/{documento}" if base else ""


def url_capitolo(libro: int, capitolo: int, simbolo: str | None = None) -> str:
    """L'indirizzo di un capitolo della Bibbia di studio nella lingua."""
    base = _base(simbolo, "b")
    return f"{base}/nwtsty/{libro}/{capitolo}" if base else ""
