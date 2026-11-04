"""La figura a schermo intero: dentro l'app e sullo schermo esterno.

E' il visore di tutto il programma (`VisoreDocumento`) usato per le figure di
capitoli, notizie e contenuti: stessi comandi (zoom, spostamento, adatta, Esc) e
stessa replica sullo schermo esterno, se c'e'.  Qui resta solo il nome con cui
le schermate lo chiamano.
"""

from SubViews.VisoreDocumento import VisoreDocumento


class VeloImmagine(VisoreDocumento):
    """La figura sopra tutto quello che c'e' sotto."""

    def mostra(self, pixmap) -> None:
        self.apri_pixmap(pixmap)
