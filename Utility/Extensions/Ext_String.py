#
#  Ext_String.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Estensioni sulle stringhe.

Stessa nota di Ext_Int: in Swift erano ``extension String``, qui sono
funzioni.  ``sha256`` non usa piu' CommonCrypto (che non esiste su Linux)
ma ``hashlib``, che e' nella libreria standard e fa la stessa cosa.
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata

_MONTHS_LOWER = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def deleting_prefix(text: str, prefix: str) -> str:
    """Togli il prefisso se c'e'.  Se non c'e', lascia la stringa come sta."""
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def sha256(text: str) -> str:
    """SHA-256 in esadecimale, minuscolo, 64 caratteri.

    Identico a CC_SHA256 + hexStringFromData: stesso hash, stessa stampa.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def month_n(text: str) -> int:
    """Il numero del mese (0 = gennaio).  Nome non riconosciuto: 0."""
    try:
        return _MONTHS_LOWER.index(text.lower())
    except ValueError:
        return 0


def unaccent(text: str) -> str:
    """Tolle i diacritici.

    Swift usava ``folding(options: .diacriticInsensitive)``.  L'equivalente
    su Linux e' scomporre in NFD e buttare i segni combinanti: e' quello che
    fa la specifica Unicode, e non dipende dalla lingua del sistema.
    """
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def pulito_html(segmento: str | None) -> str:
    """Il testo di un pezzo di HTML, senza tag e senza spazi doppi.

    Serve per le pagine di jw.org: dentro un titolo c'e' una ``<em>`` e
    dentro una descrizione c'e' una ``<p>``, e quello che si vuole leggere e'
    il **testo**, non il markup.

    Il tag diventa uno spazio e non una stringa vuota: ``<p>La</p><p>soluzione</p>``
    deve diventare «La soluzione» e non «Lasoluzione», che e' una parola che
    non esiste.  Poi gli spazi si accavallano e si lasccia uno solo.
    """
    if not segmento:
        return ""
    senza_tag = re.sub(r"<[^>]+>", " ", segmento)
    return re.sub(r"\s+", " ", html.unescape(senza_tag)).strip()