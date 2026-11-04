#
#  Ext_Int.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Estensioni sugli interi.

In Swift erano ``extension Int``. Python non lascia aggiungere metodi ai
tipi incorporati, quindi qui sono funzioni: ``month_n(3)`` al posto di
``3.monthN()``.  Il nome e' lo stesso, quindi il posto dove si chiamano si
riconosce.
"""

MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


def leading_zero(value: int) -> str:
    """``String(format: "%02d", self)``."""
    return f"{value:02d}"


def month_n(value: int) -> str:
    """Il nome del mese, 1 -> Gennaio.  Fuori range: stringa vuota."""
    if 1 <= value <= 12:
        return MONTHS[value - 1]
    return ""