"""I segnalibri del documento che si sta leggendo, per mostrarli dove servono.

Serve a due posti, e vale uguale per la lettura dal disco e per quella dal
sito (le due usano lo stesso ``MepsDocumentId``, quindi gli stessi segni):

  * la **pagina**: accanto al paragrafo (o al versetto) segnato compare un
    piccolo segnalibro del colore scelto, cosi' si vede dove e';
  * la **fascia viola**: il tasto dei segnalibri si colora con il colore
    dell'ultimo segnalibro messo in questo documento.
"""
from __future__ import annotations

import json

from Utility.Stuff import HIGHLIGHT_HEX
from Utility.UserData.BookmarkManager import BookmarkManager


def colore_hex(indice: int) -> str:
    """Il colore del segnalibro numero ``indice`` (1..6) come ``#rrggbb``."""
    if 1 <= int(indice or 0) <= len(HIGHLIGHT_HEX):
        return f"#{HIGHLIGHT_HEX[int(indice) - 1]:06x}"
    return f"#{HIGHLIGHT_HEX[0]:06x}"


#: I nomi dei sei colori, nell'ordine di ``HIGHLIGHT_HEX``: sono gli stessi
#: delle sottolineature, e si usano anche per i segnalibri.
NOMI_COLORI = ("Giallo", "Verde", "Blu", "Rosa", "Arancione", "Viola")


def icona_colore(indice: int):
    """Un pallino pieno del colore numero ``indice`` (per i menu)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    pittore = QPainter(pix)
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    pittore.setPen(QColor(0, 0, 0, 90))
    pittore.setBrush(QColor(colore_hex(indice)))
    pittore.drawEllipse(3, 3, 26, 26)
    pittore.end()
    return QIcon(pix)


def riempi_menu_colori(menu, su_scelta, attuale: int = 0) -> None:
    """Mette nel ``menu`` i sei colori; ``su_scelta(indice)`` quando se ne preme uno.

    ``attuale`` (1..6) e' il colore che ha gia' il segnalibro: compare con la
    spunta, cosi' cambiando colore si vede qual e' quello di adesso.
    """
    for indice, nome in enumerate(NOMI_COLORI, start=1):
        azione = menu.addAction(icona_colore(indice), nome)
        if attuale:
            azione.setCheckable(True)
            azione.setChecked(indice == int(attuale))
        azione.triggered.connect(lambda _=False, c=indice: su_scelta(c))


def chiedi_colore(padre, punto, su_scelta) -> None:
    """Prima di mettere un segnalibro si chiede il colore: un menu' con i sei."""
    from PyQt6.QtWidgets import QMenu
    menu = QMenu(padre)
    titolo = menu.addAction("Colore del segnalibro")
    titolo.setEnabled(False)
    menu.addSeparator()
    riempi_menu_colori(menu, su_scelta)
    menu.exec(punto)


def segnalibri_del_documento(pub, document_id: int) -> list:
    """I segnalibri di questo documento (o di questo capitolo della Bibbia)."""
    if pub is None or isinstance(pub, dict):
        return []
    try:
        tutti = BookmarkManager.get_bookmarks(pub)
    except Exception:  # noqa: BLE001 - un database che non risponde non e' un guasto qui
        return []
    if getattr(pub, "isBible", False):
        libro = int(getattr(pub, "book", 0) or 0)
        capitolo = int(getattr(pub, "chapter", 0) or 0)
        return [s for s in tutti
                if s.bookNumber == libro and s.chapterNumber == capitolo]
    documento = int(document_id or 0)
    if not documento:
        return []
    return [s for s in tutti if s.documentId == documento]


def colore_ultimo(pub, document_id: int) -> str:
    """Il colore dell'ultimo segnalibro del documento, o "" se non ce ne sono."""
    segni = segnalibri_del_documento(pub, document_id)
    # get_bookmarks li ordina dal piu' recente.
    return colore_hex(segni[0].color) if segni else ""


# IL SEGNO NELLA PAGINA
# ---------------------
# Un piccolo segnalibro (la sagoma con la coda a V) all'inizio del paragrafo.
# Non e' una <selectable>: le sottolineature contano solo quelle, quindi il
# segno non sposta i conteggi delle parole.  Prima di rimetterli si tolgono
# quelli vecchi, cosi' ridisegnando non si raddoppiano.
_FUNZIONE_JS = """
window.__jwlSegnaSegnalibri = function (elenco, isBible) {
  var vecchi = document.querySelectorAll('.jwl-segno');
  for (var k = 0; k < vecchi.length; k++) { vecchi[k].remove(); }
  for (var i = 0; i < elenco.length; i++) {
    var segno = elenco[i];
    var nodo = null;
    if (isBible) {
      var versi = document.querySelectorAll("span[id^='v']");
      for (var j = 0; j < versi.length; j++) {
        if (Number(String(versi[j].id).split('-')[2]) === segno.id) { nodo = versi[j]; break; }
      }
    } else {
      nodo = document.querySelector('[data-pid="' + segno.id + '"]');
    }
    if (!nodo || nodo.querySelector('.jwl-segno')) { continue; }
    var m = document.createElement('span');
    m.className = 'jwl-segno';
    m.title = 'Segnalibro';
    m.setAttribute('contenteditable', 'false');
    m.style.cssText = 'display:inline-block;width:0.72em;height:1.05em;margin-right:0.4em;'
      + 'vertical-align:-0.15em;background:' + segno.colore + ';'
      + 'clip-path:polygon(0 0,100% 0,100% 100%,50% 74%,0 100%);'
      + '-webkit-user-select:none;user-select:none;pointer-events:none;';
    nodo.insertBefore(m, nodo.firstChild);
  }
};
"""


def js_segna(pub, document_id: int) -> str:
    """Il JavaScript che mette (o toglie) i segni dei segnalibri nella pagina."""
    elenco = []
    visti = set()
    for s in segnalibri_del_documento(pub, document_id):
        if s.identifier <= 0 or s.identifier in visti:
            continue
        visti.add(s.identifier)
        elenco.append({"id": int(s.identifier), "colore": colore_hex(s.color)})
        # Il primo per paragrafo e' il piu' recente: e' quel colore che si vede.
    bibbia = "true" if getattr(pub, "isBible", False) else "false"
    return (_FUNZIONE_JS + "\nwindow.__jwlSegnaSegnalibri("
            + json.dumps(elenco) + ", " + bibbia + ");")
