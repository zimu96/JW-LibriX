"""Estensioni sui tipi che Python non lascia modificare.

In Swift erano `extension Int`, `extension String`, `extension Color`,
`extension FileManager` e `extension DispatchQueue`.  Python non permette di
aggiungere metodi a `int`, `str` o `FileManager`, quindi qui sono funzioni con
lo stesso nome in minuscolo e col nome che avevano: `month_n(3)` al posto di
`3.monthN()`.
"""
from __future__ import annotations

from .Ext_Int import *
from .Ext_String import *
from .Ext_FileManager import *
from .Ext_DispatchQueue import on_main, background
