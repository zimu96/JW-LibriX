"""Le caselle «La tua risposta» di un documento: si salvano e si ritrovano.

Il documento (libro, opuscolo) ha delle caselle dove scrivere con la tastiera
(``<textarea id="tt11">``).  JW Library le salva nella tabella ``InputField``:
una riga per casella, con la ``Location`` del documento, il codice della
casella (``TextTag`` = l'``id``, per esempio ``tt11``) e il testo scritto.

Il codice della casella e' lo stesso nel pacchetto scaricato e sul sito, e la
``Location`` e' la stessa (sigla + ``MepsDocumentId``): una risposta scritta
leggendo online si ritrova offline e viceversa, ed entra nel backup
``.jwlibrary`` come quelle del telefono.
"""
from __future__ import annotations

import json
import sqlite3

from Utility.Structures.Paths import Paths
from Utility.UserData.LocationManager import LocationManager


def _connetti() -> sqlite3.Connection | None:
    Paths.prepare()
    try:
        return sqlite3.connect(str(Paths.db_path))
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


def _valida(pub, document_id) -> bool:
    return (pub is not None and not isinstance(pub, dict)
            and not getattr(pub, "isBible", False) and int(document_id or 0) > 0)


def leggi(pub, document_id: int) -> dict:
    """{codice casella: testo} delle risposte salvate per questo documento."""
    if not _valida(pub, document_id):
        return {}
    location_id = LocationManager.get_location(pub=pub, document_id=int(document_id))
    if not location_id:
        return {}
    connessione = _connetti()
    if connessione is None:
        return {}
    try:
        righe = connessione.execute(
            "SELECT TextTag, Value FROM InputField WHERE LocationId = ?;",
            (location_id,)).fetchall()
    except sqlite3.Error as errore:
        print(f"Errore lettura risposte ⚠️  {errore}")
        righe = []
    finally:
        connessione.close()
    return {str(tag): str(valore or "") for tag, valore in righe}


def salva(pub, document_id: int, tag: str, valore: str) -> bool:
    """Scrive (o toglie, se vuota) la risposta di una casella."""
    tag = str(tag or "").strip()
    if not tag or not _valida(pub, document_id):
        return False
    LocationManager.add_location(pub=pub, document_id=int(document_id))
    location_id = LocationManager.get_location(pub=pub, document_id=int(document_id))
    if not location_id:
        return False
    connessione = _connetti()
    if connessione is None:
        return False
    try:
        if str(valore or "").strip():
            connessione.execute(
                "INSERT OR REPLACE INTO InputField (LocationId, TextTag, Value)"
                " VALUES (?, ?, ?);", (location_id, tag, str(valore)))
        else:
            connessione.execute(
                "DELETE FROM InputField WHERE LocationId = ? AND TextTag = ?;",
                (location_id, tag))
        connessione.commit()
        return True
    except sqlite3.Error as errore:
        print(f"Errore salvataggio risposta ⚠️  {errore}")
        return False
    finally:
        connessione.close()


# Il JavaScript della pagina.
# ASCOLTA: un solo ascoltatore sul documento (non sulle caselle), perche' la
# pagina ricostruisce il corpo quando ridisegna le sottolineature e gli
# ascoltatori messi sulle caselle andrebbero persi.  Ogni tasto premuto manda
# il testo a Python, che lo scrive subito: cosi' non si perde niente anche se
# subito dopo la pagina si ricostruisce.
# RIMETTI: dopo ogni ricostruzione le caselle tornano vuote, e si riempiono
# con quello che e' salvato.
_ASCOLTA_JS = """
(function () {
  if (window.__jwlAscoltaRisposte) { return; }
  window.__jwlAscoltaRisposte = true;
  document.addEventListener('input', function (evento) {
    var t = evento.target;
    if (!t || t.tagName !== 'TEXTAREA' || !t.id) { return; }
    window.__jwlRisposte = window.__jwlRisposte || {};
    window.__jwlRisposte[t.id] = t.value;
    window.webkit.messageHandlers.toggleMessageHandler.postMessage(
      {"mode": 7, "tag": t.id, "valore": t.value});
  }, true);
})();
"""


def js_ripristina(pub, document_id: int) -> str:
    """Il JavaScript che rimette nelle caselle le risposte salvate (e le ascolta)."""
    if not _valida(pub, document_id):
        return ""
    risposte = leggi(pub, document_id)
    return (_ASCOLTA_JS + "\n(function () { var r = " + json.dumps(risposte) + ";"
            " window.__jwlRisposte = Object.assign(r, window.__jwlRisposte || {});"
            " for (var k in window.__jwlRisposte) {"
            "   var c = document.getElementById(k);"
            "   if (c && c.tagName === 'TEXTAREA' && c.value !== window.__jwlRisposte[k]) {"
            "     c.value = window.__jwlRisposte[k]; }"
            " } })();")
