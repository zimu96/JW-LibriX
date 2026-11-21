"""Un PDF letto dentro l'app, come una pagina qualsiasi (stessa schermata, stessa freccia indietro).

Serve solo per il materiale che sul sito esiste in PDF e basta (vedi
`Utility/FormatiSito.py`).  Usa il lettore PDF di Chromium, che c'e' gia' in
QtWebEngine: nessuna libreria in piu'.  E' una `NotiziaView`, cosi' il resto
della finestra (indietro, titolo, tasto del mouse) funziona senza eccezioni.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEngineSettings

from SubViews.NotiziaView import NotiziaView
from WebBrowserView import WebEnginePage


class PaginaPdf(WebEnginePage):
    """Pagina del PDF: i link verso il sito escono come `linkPremuto` (restano nell'app).

    I collegamenti DENTRO il PDF (a sezioni, a pagine) li gestisce il lettore
    e funzionano come sempre: non sono http.
    """

    def __init__(self, ponte, vista, quando_link, proprio: str = "") -> None:
        super().__init__(ponte, vista)
        self._quando_link = quando_link
        self._proprio = proprio     # l'indirizzo del PDF stesso (se e' online)

    def acceptNavigationRequest(self, url, tipo, principale) -> bool:
        if principale and url.scheme() in ("http", "https") \
                and url.toString() != self._proprio:
            self._quando_link(url.toString())
            return False
        return super().acceptNavigationRequest(url, tipo, principale)


class PdfView(NotiziaView):
    def __init__(self, percorso: str, titolo: str = "", parent=None) -> None:
        """`percorso` e' un file sul disco oppure l'indirizzo online del PDF."""
        online = percorso.startswith(("http://", "https://"))
        self._indirizzo = (QUrl(percorso) if online else QUrl.fromLocalFile(percorso))
        super().__init__(self._indirizzo.toString(), titolo, parent)
        self.percorso = percorso
        # Pagina che intercetta i link verso il sito (stessi collegamenti di una notizia).
        pagina = PaginaPdf(self.web.bridge, self.web, self.linkPremuto.emit,
                        self._indirizzo.toString() if online else "")
        self.web.setPage(pagina)
        pagina.loadFinished.connect(self._pagina_pronta)
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PluginsEnabled, True)

    def carica(self) -> None:
        self.web.setUrl(self._indirizzo)
        self._aggancia_filtro_tastiera()

    def _pagina_pronta(self, riuscito: bool = True) -> None:
        """Il PDF si mostra com'e': niente estrazione dell'articolo."""
        if not riuscito:
            self.web.setVisible(False)
            self._stato.setVisible(True)
            self._stato.setText("Non riesco ad aprire il PDF.")
            return
        self._stato.setVisible(False)
        self.web.setVisible(True)

    def imposta_dimensione_testo(self, percentuale: int) -> None:
        """Il PDF ha il suo zoom: i tre puntini non cambiano il testo."""
        return
