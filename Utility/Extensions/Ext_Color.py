#
#  Ext_Color.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Estensioni sui colori.

In Swift ``extension Color`` con dentro un ``NSColor``.  Qui si lavora su
``QColor``: stessi tre canali, stesso alpha, stessa regola dei minimi a 1.0.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor


def adjust(color: QColor, percentage: float) -> QColor:
    """Sposta i tre canali di ``percentage``/100, senza passare da 1.0.

    Il segno lo mette il chiamante: ``lighter`` passa positivo, ``darker``
    negativo.  Swift prende ``abs(percentage)`` e poi moltiplica per -1,
    quindi il risultato e' lo stesso.

    I TRE CANALI VANNO DA 0 A 1, E SERVONO I FLOAT
    ----------------------------------------------
    In Swift sono ``CGFloat``, cioe' doppi da 0 a 1.  Il costruttore di
    ``QColor`` in PyQt6 accetta solo interi da 0 a 255, e passargli un ``float``
    non da' un colore sbagliato: da' un ``TypeError``.

    Il costruttore giusto e' ``QColor.fromRgbF``, che vuole esattamente
    quattro ``float`` da 0 a 1.  E' l'unico modo per non fare aritmetica a
    mano su 255.

    Questo difetto era invisibile: si vede solo quando si passa da un colore
    chiaro a uno piu' chiaro, e cioe' quando si preme un pulsante dei libri
    della Bibbia.
    """
    shift = percentage / 100.0
    return QColor.fromRgbF(
        min(color.redF() + shift, 1.0),
        min(color.greenF() + shift, 1.0),
        min(color.blueF() + shift, 1.0),
        color.alphaF(),
    )


def lighter(color: QColor, percentage: float) -> QColor:
    return adjust(color, abs(percentage))


def darker(color: QColor, percentage: float) -> QColor:
    return adjust(color, -abs(percentage))