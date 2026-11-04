"""Le pagine di un PDF come immagini, con il primo motore che c'e' sul computer.

Nessun motore e' obbligatorio: il programma non ha dipendenze da `pip`, quindi
si prova in ordine quello che l'utente ha gia' e, se non c'e' niente, si dice
cosa installare.

    1. PyMuPDF  (``pip install pymupdf``)       il piu' veloce, ovunque
    2. QtPdf    (pacchetto Qt del sistema)      se importa e funziona
    3. pdftoppm (poppler: ``poppler-utils``)    c'e' su quasi ogni Linux, e con
                                                ``brew install poppler`` su macOS
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtGui import QImage

SUGGERIMENTO = ("Per aprire i PDF serve uno di questi: PyMuPDF (pip install pymupdf), "
                "QtPdf (pacchetto Qt del sistema) oppure poppler "
                "(apt install poppler-utils / pacman -S poppler / brew install poppler).")


def _motore_pymupdf():
    try:
        import pymupdf
    except ImportError:
        return None
    return pymupdf


def _motore_qtpdf():
    try:
        from PyQt6.QtPdf import QPdfDocument
    except ImportError:
        return None
    return QPdfDocument


class Documento:
    """Un PDF aperto: quante pagine ha e l'immagine di ognuna."""

    def __init__(self, percorso) -> None:
        self.percorso = str(percorso)
        self._pymupdf = _motore_pymupdf()
        self._doc = None
        self._pagine = 0
        self._cartella = None
        self.motore = ""
        if self._pymupdf is not None:
            self._doc = self._pymupdf.open(self.percorso)
            self._pagine = self._doc.page_count
            self.motore = "pymupdf"
            return
        qtpdf = _motore_qtpdf()
        if qtpdf is not None:
            try:
                doc = qtpdf()
                doc.load(self.percorso)
                if doc.pageCount() > 0:
                    doc.render(0, doc.pagePointSize(0).toSize())
                    self._doc, self._pagine, self.motore = doc, doc.pageCount(), "qtpdf"
                    return
            except Exception:  # noqa: BLE001 - un QtPdf rotto si salta
                pass
        if shutil.which("pdftoppm") and shutil.which("pdfinfo"):
            self._pagine = self._pagine_con_poppler()
            self.motore = "poppler"
            self._cartella = tempfile.TemporaryDirectory(prefix="jwl_pdf_")
            return
        raise RuntimeError(SUGGERIMENTO)

    def _pagine_con_poppler(self) -> int:
        uscita = subprocess.run(["pdfinfo", self.percorso], capture_output=True,
                                text=True, timeout=30).stdout
        for riga in uscita.splitlines():
            if riga.startswith("Pages:"):
                return int(riga.split(":", 1)[1])
        return 0

    @property
    def pagine(self) -> int:
        return self._pagine

    def pagina(self, numero: int, scala: float = 2.0) -> QImage:
        """La pagina ``numero`` (da 0), a ``scala`` volte i 72 punti per pollice."""
        if self.motore == "pymupdf":
            pix = self._doc[numero].get_pixmap(matrix=self._pymupdf.Matrix(scala, scala),
                                               alpha=False)
            immagine = QImage(pix.samples, pix.width, pix.height, pix.stride,
                              QImage.Format.Format_RGB888)
            return immagine.copy()
        if self.motore == "qtpdf":
            punti = self._doc.pagePointSize(numero)
            return self._doc.render(numero, (punti * scala).toSize())
        base = Path(self._cartella.name) / f"p{numero}_{int(scala * 100)}"
        file = Path(str(base) + ".png")
        if not file.is_file():
            subprocess.run(["pdftoppm", "-png", "-singlefile", "-r", str(int(72 * scala)),
                            "-f", str(numero + 1), "-l", str(numero + 1),
                            self.percorso, str(base)], capture_output=True, timeout=120)
        return QImage(str(file))

    def chiudi(self) -> None:
        if self.motore == "pymupdf" and self._doc is not None:
            self._doc.close()
        if self._cartella is not None:
            self._cartella.cleanup()
        self._doc = None
