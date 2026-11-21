"""Aprire una pubblicazione dal sito, senza scaricarla.

L'indirizzo si chiede ai «finder» del sito, che da sigla e lingua portano alla
pagina giusta:

  * libri, opuscoli, Bibbia...: WOL (wol.jw.org), che ha l'indice con i
    capitoli e il testo da leggere;
  * periodici (Torre di Guardia, Svegliatevi, guida delle adunanze): la pagina
    del numero su jw.org, che elenca gli articoli (WOL non cerca per numero).

Il testo si mostra poi con `NotiziaView`, cioe' nello stile dell'app.
Regola: quello che e' gia' scaricato si apre dal disco, mai da qui.
"""
from __future__ import annotations

from urllib.parse import quote

WOL = "https://wol.jw.org/wol/finder"
JW = "https://www.jw.org/finder"


def _numero(pub) -> str:
    """Il numero del periodico come lo vuole il sito: AAAAMM (20261200 -> 202612)."""
    n = int(getattr(pub, "issueTagNumber", 0) or 0)
    return str(n // 100 if n > 999999 else n) if n else ""


def url_pub(pub) -> str:
    """L'indirizzo web di una pubblicazione.  Vuoto se non si puo'."""
    from Utility import Preferiti
    sigla = getattr(pub, "keySymbol", "") or ""
    if not sigla:
        return ""
    lingua = quote(Preferiti._lingua(pub) or "I")
    numero = _numero(pub)
    if numero:
        return f"{JW}?srcid=jwlshare&wtlocale={lingua}&pub={quote(sigla)}&issue={numero}"
    return f"{WOL}?wtlocale={lingua}&pub={quote(sigla)}"


def url_documento(docid, lingua: str = "I") -> str:
    """L'indirizzo web di un documento (MepsDocumentId)."""
    return f"{WOL}?wtlocale={quote(lingua)}&docid={int(docid)}" if docid else ""


def e_scaricata(pub) -> bool:
    """True se il pacchetto e' gia' sul disco (allora si apre da li')."""
    from Utility import Copertine
    return bool(Copertine.pacchetto_locale(pub))
