"""Le schermate.

Una schermata e' un QWidget.  Non sa niente della finestra: se ha bisogno di
cambiare schermata emette un segnale, e la finestra fa il resto.  E' il motivo
per cui nessuno di questi file importa `SidebarView`.
"""
from __future__ import annotations
