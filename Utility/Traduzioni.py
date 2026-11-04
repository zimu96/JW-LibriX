#
#  Traduzioni.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Lo stesso versetto in altre lingue, e le Bibbie scaricate in quelle lingue.

Il testo viene da wol.jw.org: ogni lingua ha un suo indirizzo (``r4/lp-s`` per
lo spagnolo) che si scopre una volta sola chiedendo ``wol.jw.org/<iso>`` e si
ricorda.

POCHE CHIAMATE
--------------
- un capitolo si chiede una volta sola: poi resta su disco, compresso, in
  ``userData/traduzioni/<lingua>/``;
- le richieste chiedono la risposta compressa (gzip);
- l'italiano si legge dal pacchetto gia' scaricato, senza rete;
- si scarica **solo quello che serve** mentre si legge.  La Bibbia intera
  (1189 capitoli) parte solo se l'utente lo chiede, e riprende da dove era
  arrivata: i capitoli gia' presenti non si richiedono.

Tutto cio' che fa rete va chiamato da un thread, mai mentre si disegna.
"""

from __future__ import annotations

import gzip
import html
import json
import re
import shutil
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from Utility import Lingua
from Utility.FileDownloader import FileDownloader
from Utility import RiferimentiWol as _wol
from Utility import BibbiaOnline, WolLingua
from Utility.Extensions.Ext_FileManager import get_documents_directory

PREDEFINITE = ["I", "E", "S", "F"]
TIMEOUT = 20
OPERAI = 3
_AGENTE = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
_RE_TOKEN = re.compile(r"<span\b|</span>", re.I)
_RE_TAG = re.compile(r"<[^>]+>")
#: I capitoli di ognuno dei 66 libri (1189 in tutto)
CAPITOLI = [50, 40, 27, 36, 34, 24, 21, 4, 31, 24, 22, 25, 29, 36, 10, 13, 10, 42,
            150, 31, 12, 8, 66, 52, 5, 48, 12, 14, 3, 9, 1, 4, 7, 3, 3, 3, 2, 14, 4,
            28, 16, 24, 21, 28, 16, 16, 13, 6, 6, 4, 4, 5, 3, 6, 4, 3, 1, 13, 5, 5,
            3, 5, 1, 1, 1, 22]
TOTALE = sum(CAPITOLI)
#: Gli scaricamenti in corso: simbolo -> {"fatti", "ferma"}
_in_corso: dict[str, dict] = {}


def _radice():
    cartella = get_documents_directory() / "userData" / "traduzioni"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella


def _json(nome: str, predefinito):
    try:
        return json.loads((_radice() / nome).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return predefinito


def _scrivi(nome: str, dati) -> None:
    try:
        (_radice() / nome).write_text(json.dumps(dati), encoding="utf-8")
    except OSError:
        pass


# ----------------------------------------------------------------------
# LE LINGUE SCELTE, IN ORDINE DI PRIORITA'
# ----------------------------------------------------------------------

def scelte() -> list[str]:
    """I simboli delle lingue da mostrare, la prima e' quella che compare per prima."""
    return list(_json("scelte.json", PREDEFINITE))


def alterna(simbolo: str) -> None:
    elenco = scelte()
    if simbolo in elenco:
        elenco.remove(simbolo)
    else:
        elenco.append(simbolo)
    _scrivi("scelte.json", elenco)


def riordina(simboli: list[str]) -> None:
    """Salva il nuovo ordine, tenendo solo lingue gia' scelte."""
    attuali = scelte()
    nuovo = [s for s in simboli if s in attuali]
    nuovo += [s for s in attuali if s not in nuovo]
    _scrivi("scelte.json", nuovo)


# ----------------------------------------------------------------------
# I CAPITOLI SU DISCO
# ----------------------------------------------------------------------

def _file(simbolo: str, libro: int, capitolo: int):
    cartella = _radice() / simbolo
    cartella.mkdir(exist_ok=True)
    return cartella / f"{libro}_{capitolo}.html.gz"


def stato_lingua(simbolo: str) -> tuple[int, int]:
    """(capitoli su disco, byte): quelli letti come traduzione e quelli della Bibbia."""
    capitoli = peso = 0
    try:
        file = list((_radice() / simbolo).glob("*.html.gz"))
        capitoli += len(file)
        peso += sum(f.stat().st_size for f in file)
        bibbia = list(BibbiaOnline.cartella(simbolo).glob("*/*.html"))
        capitoli += len(bibbia)
        peso += sum(f.stat().st_size for f in bibbia)
    except OSError:
        pass
    return capitoli, peso


def scaricate() -> list[dict]:
    """Le lingue con capitoli su disco (senza i pacchetti, che sono pubblicazioni)."""
    from Utility.JWPubManager import bible_package

    simboli = {c.name for c in _radice().iterdir() if c.is_dir()}
    simboli |= {c.name.split("_", 1)[1] for c in get_documents_directory().glob("nwtsty_*")
                if c.is_dir()}
    trovate = []
    for simbolo in sorted(simboli):
        if bible_package(simbolo) is not None:
            continue
        capitoli, peso = stato_lingua(simbolo)
        if capitoli:
            voce = Lingua.per_simbolo(simbolo) or {}
            trovate.append({
                "simbolo": simbolo,
                "nome": voce.get("nome_vernacolare") or voce.get("nome") or simbolo,
                "capitoli": capitoli, "byte": peso})
    return trovate


def elimina(simbolo: str) -> None:
    """Toglie dal disco i capitoli di quella lingua (non il pacchetto, se c'e')."""
    from Utility.JWPubManager import bible_package

    ferma(simbolo)
    shutil.rmtree(_radice() / simbolo, ignore_errors=True)
    if bible_package(simbolo) is None:
        shutil.rmtree(BibbiaOnline.cartella(simbolo), ignore_errors=True)


def _dal_pacchetto(simbolo: str, libro: int, capitolo: int) -> str | None:
    """Il capitolo dalla Bibbia gia' presente nell'app (nessuna rete)."""
    try:
        return (BibbiaOnline.cartella(simbolo) / str(libro) / f"{capitolo}.html").read_text(
            encoding="utf-8")
    except OSError:
        return None


def _capitolo(simbolo: str, libro: int, capitolo: int) -> str | None:
    """L'html del capitolo: dal pacchetto, dal disco, e solo alla fine dalla rete."""
    locale = _dal_pacchetto(simbolo, libro, capitolo)
    if locale is not None:
        return locale
    file = _file(simbolo, libro, capitolo)
    try:
        return gzip.decompress(file.read_bytes()).decode("utf-8")
    except (OSError, ValueError):
        pass
    if WolLingua.codici(simbolo) is None:
        return None
    indirizzo = WolLingua.url_capitolo(libro, capitolo, simbolo)
    try:
        with urllib.request.urlopen(
                urllib.request.Request(indirizzo, headers=_AGENTE), timeout=TIMEOUT) as r:
            grezzo = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                grezzo = gzip.decompress(grezzo)
            pagina = grezzo.decode("utf-8")
    except (urllib.error.URLError, OSError, UnicodeDecodeError, ValueError):
        return None
    try:
        file.write_bytes(gzip.compress(pagina.encode("utf-8")))
    except OSError:
        pass
    return pagina


def _testo_versetto(pagina: str, libro: int, capitolo: int, verso: int) -> str:
    """Il testo del versetto (senza numero, note e rimandi)."""
    prefisso = f'id="v{libro}-{capitolo}-{verso}-'
    pezzi = []
    inizio = 0
    while (posizione := pagina.find(prefisso, inizio)) >= 0:
        apertura = pagina.rfind("<span", 0, posizione)
        profondita = 0
        fine = len(pagina)
        for token in _RE_TOKEN.finditer(pagina, apertura):
            profondita += -1 if token.group(0).startswith("</") else 1
            if profondita == 0:
                fine = token.end()
                break
        pezzi.append(pagina[apertura:fine])
        inizio = fine
    testo = " ".join(pezzi)
    testo = re.sub(r"<a\b[^>]*class=\"[^\"]*\b(?:vl|cl|b|fn)\b[^\"]*\"[^>]*>.*?</a>",
                   "", testo, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(_RE_TAG.sub("", testo))).strip()


def testo(simbolo: str, libro: int, capitolo: int, verso: int) -> str | None:
    pagina = _capitolo(simbolo, libro, capitolo)
    if pagina is None:
        return None
    return _testo_versetto(pagina, libro, capitolo, verso) or None


# ----------------------------------------------------------------------
# LA BIBBIA INTERA, SE L'UTENTE LA VUOLE
# ----------------------------------------------------------------------

def in_corso(simbolo: str) -> int | None:
    """Quanti capitoli sono stati controllati, se c'e' uno scaricamento in corso."""
    voce = _in_corso.get(simbolo)
    return None if voce is None else voce["fatti"]


def scaricamenti() -> dict[str, int]:
    """Gli scaricamenti in corso: simbolo -> capitoli controllati (su 1189)."""
    return {s: v["fatti"] for s, v in list(_in_corso.items())}


def ferma(simbolo: str) -> None:
    if simbolo in _in_corso:
        _in_corso[simbolo]["ferma"] = True


def avvia_scaricamento(simbolo: str, finito=None) -> bool:
    """Scarica tutta la Bibbia in una lingua, in un thread.  Riprende da dov'era.

    I capitoli vanno nella cartella ``nwtsty_<lingua>``, la stessa che usa la
    sezione Bibbia: dopo si leggono senza internet.
    """
    if simbolo in _in_corso:
        return False
    voce = _in_corso[simbolo] = {"fatti": 0, "ferma": False}
    lavori = [(libro, capitolo) for libro, quanti in enumerate(CAPITOLI, 1)
              for capitolo in range(1, quanti + 1)]

    def uno(coppia) -> None:
        if voce["ferma"]:
            return
        libro, capitolo = coppia
        file = BibbiaOnline.cartella(simbolo) / str(libro) / f"{capitolo}.html"
        if not file.is_file():
            url = WolLingua.url_capitolo(libro, capitolo, simbolo)
            if url:
                FileDownloader.download_article(
                    url=url, path=f"nwtsty_{simbolo}/{libro}/{capitolo}.html")
            if not file.is_file():
                # Un errore di rete non deve far girare 1189 richieste a vuoto.
                voce["errori"] = voce.get("errori", 0) + 1
                if voce["errori"] >= 5:
                    voce["ferma"] = True
        voce["fatti"] += 1

    def corpo() -> None:
        try:
            with ThreadPoolExecutor(max_workers=OPERAI) as pool:
                list(pool.map(uno, lavori))
        finally:
            _in_corso.pop(simbolo, None)
            if finito is not None:
                finito(simbolo)

    threading.Thread(target=corpo, daemon=True).start()
    return True


# ----------------------------------------------------------------------
# LE PAGINE DEL RIQUADRO
# ----------------------------------------------------------------------

def _nome(simbolo: str) -> str:
    voce = Lingua.per_simbolo(simbolo) or {}
    return voce.get("nome_vernacolare") or voce.get("nome") or simbolo


def versetto(libro: int, capitolo: int, verso: int, nome: str) -> _wol.Riferimento:
    """Il versetto in tutte le lingue scelte, nell'ordine di priorita'."""
    lingue = scelte()
    with ThreadPoolExecutor(max_workers=max(1, len(lingue))) as pool:
        testi = list(pool.map(lambda s: testo(s, libro, capitolo, verso), lingue))
    voci = []
    for simbolo, contenuto in zip(lingue, testi):
        corpo = (f"<p>{html.escape(contenuto)}</p>" if contenuto else
                 "<p style='opacity:.6'>Non disponibile (controlla la connessione).</p>")
        voci.append(_wol.Voce(titolo=_nome(simbolo), pubblicazione=nome, immagine="",
                              html=corpo))
    collegamento = ("<p style='padding-top:10px'>"
                    "<a href='jwl:lingue'>Lingue e Bibbie scaricate…</a></p>")
    if voci:
        voci[-1].html += collegamento
    else:
        voci.append(_wol.Voce(titolo="Altre traduzioni", pubblicazione=nome,
                              immagine="", html="<p>Nessuna lingua scelta.</p>" + collegamento))
    return _wol.Riferimento(titolo="Altre traduzioni", voci=voci)


def _stato_testo(simbolo: str) -> str:
    fatti = in_corso(simbolo)
    if fatti is not None:
        return f"Scarico… {fatti}/{TOTALE} capitoli"
    capitoli, peso = stato_lingua(simbolo)
    if simbolo == "I" or (capitoli == 0 and _dal_pacchetto(simbolo, 1, 1)):
        return "Nell'app"
    if not capitoli:
        return "Si scarica mentre leggi"
    return f"{capitoli}/{TOTALE} capitoli · {peso / (1024 * 1024):.1f} MB"


_STILE = """<style>
ul.l{list-style:none;padding:0;margin:0}
ul.l li{padding:9px 6px;border-bottom:1px solid rgba(128,128,128,.3)}
ul.l li.tr{cursor:grab}
ul.l li.sopra{border-top:2px solid #64398b}
ul.l .n{font-weight:700}
ul.l .s{display:block;opacity:.65;font-size:12px;margin-top:2px}
ul.l .az{display:block;font-size:13px;margin-top:3px}
ul.l .az a{margin-right:14px}
h2{font-size:14px;margin:14px 0 4px;opacity:.8}
</style>"""

_SCRIPT = """<script>
var trascinato = null;
function ordine() {
  return Array.prototype.map.call(document.querySelectorAll('li.tr'),
    function (e) { return e.getAttribute('data-s'); }).join(',');
}
document.querySelectorAll('li.tr').forEach(function (li) {
  li.setAttribute('draggable', 'true');
  li.addEventListener('dragstart', function (e) {
    trascinato = li; e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', li.getAttribute('data-s'));
  });
  li.addEventListener('dragover', function (e) {
    e.preventDefault();
    if (!trascinato || trascinato === li) { return; }
    var r = li.getBoundingClientRect();
    li.parentNode.insertBefore(trascinato,
      (e.clientY < r.top + r.height / 2) ? li : li.nextSibling);
  });
  li.addEventListener('drop', function (e) { e.preventDefault(); });
  li.addEventListener('dragend', function () {
    trascinato = null;
    window.webkit.messageHandlers.toggleMessageHandler.postMessage(
      {"mode": 99, "azione": "jwl:ordine/" + ordine()});
  });
});
</script>"""


def elenco_lingue() -> _wol.Riferimento:
    """La pagina delle lingue: ordine di priorita' (si trascina) e scaricamenti."""
    scelte_ora = scelte()
    righe = ""
    for simbolo in scelte_ora:
        s = html.escape(simbolo)
        azioni = []
        if simbolo != "I":
            fermo = in_corso(simbolo) is not None
            azioni.append(f"<a href='jwl:ferma/{s}'>Ferma</a>" if fermo
                          else f"<a href='jwl:scarica/{s}'>Scarica la Bibbia intera</a>")
            if stato_lingua(simbolo)[0]:
                azioni.append(f"<a href='jwl:elimina/{s}'>Elimina</a>")
        azioni.append(f"<a href='jwl:lingua/{s}'>Togli dall'elenco</a>")
        righe += (f"<li class='tr' data-s='{s}'><span class='n'>≡ {html.escape(_nome(simbolo))}</span>"
                  f"<span class='s' data-stato='{s}'>{html.escape(_stato_testo(simbolo))}</span>"
                  f"<span class='az'>{''.join(azioni)}</span></li>")
    altre = sorted((v for v in Lingua.lingue() if v["simbolo"] not in scelte_ora),
                   key=lambda v: -int(v.get("pubblicazioni") or 0))
    aggiungi = "".join(
        f"<li><a href='jwl:lingua/{html.escape(v['simbolo'])}'>+ "
        f"{html.escape(v.get('nome_vernacolare') or v['nome'])}</a></li>" for v in altre)
    corpo = (_STILE
             + "<p><a href='jwl:traduzioni'><b>Fatto: mostra il versetto</b></a></p>"
             "<h2>In ordine di priorita' (trascina per cambiare)</h2>"
             f"<ul class='l'>{righe}</ul>"
             "<h2>Aggiungi una lingua</h2>"
             f"<ul class='l'>{aggiungi}</ul>" + _SCRIPT)
    return _wol.Riferimento(titolo="Lingue", voci=[_wol.Voce(
        titolo="Lingue", pubblicazione="La prima e' quella che compare per prima",
        immagine="", html=corpo)])
