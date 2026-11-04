#
#  ButtonStyle.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Gli stili dei pulsanti.

In Swift sono ``ButtonStyle``, cioe' un protocollo che riscrive il
pulsante a ogni pressione.  In Qt lo stesso risultato si ottiene con i
fogli di stile: ``QPushButton:pressed`` ridisegna da solo quando il
pulsante viene premuto, quindi non serve nessun codice che intercetti il
mouse.  Il colore premuto resta esattamente quello che Swift calcolava con
``color.lighter(by: 30)``.
"""

from PyQt6.QtWidgets import QPushButton

from Utility.Extensions.Ext_Color import lighter

FONT_COLOR = "#ffffff"


def _qss(background: str, pressed: str | None = None) -> str:
    """Un foglio di stile per un pulsante con sfondo pieno e angoli tondi."""
    testo = (
        f"QPushButton {{\n"
        f"    background-color: {background};\n"
        f"    color: {FONT_COLOR};\n"
        f"    border: none;\n"
        f"    border-radius: 6px;\n"
        f"    padding: 2px 10px;\n"
        f"}}\n"
        f"QPushButton:disabled {{\n"
        f"    background-color: {background};\n"
        f"    color: #888888;\n"
        f"}}\n"
    )
    if pressed is not None:
        testo += (
            f"QPushButton:pressed {{\n"
            f"    background-color: {pressed};\n"
            f"}}\n"
        )
    return testo


class BibleButtonStyle:
    """Il pulsante dei libri della Bibbia: sfondo pieno, testo bianco."""

    def __init__(self, color) -> None:
        self.color = color

    def qss(self) -> str:
        return _qss(self.color.name(), lighter(self.color, 30).name())

    def apply(self, button: QPushButton) -> QPushButton:
        button.setStyleSheet(self.qss())
        button.setCursor(button.cursor())
        return button


class TransparentButtonStyle:
    """Come sopra ma senza lo stato premuto piu' chiaro."""

    def __init__(self, color) -> None:
        self.color = color

    def qss(self) -> str:
        return _qss(self.color.name())

    def apply(self, button: QPushButton) -> QPushButton:
        button.setStyleSheet(self.qss())
        return button


def bible_button(label: str, color) -> QPushButton:
    """Costruisce il pulsante di un libro o di un capitolo, gia' colorato."""
    button = QPushButton(label)
    BibleButtonStyle(color).apply(button)
    return button

