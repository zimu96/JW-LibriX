#
#  WebBrowserView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""Il motore che mostra il testo, e il ponte fra il motore e Python.

COSA E' CAMBIATO, E PERCHE'
---------------------------
WKWebView e' WebKit, che e' di Apple.  Su Linux il WebKit di Apple non c'e',
e al suo posto c'e' Chromium, che Qt mette a disposizione come
``QWebEngineView``.  Non e' la stessa cosa ma e' la stessa posizione: un
motore di pagine web dentro la finestra, con la stessa interfaccia.

Tre cose hanno nomi diversi e vanno ricordate:

    WKWebView.loadHTMLString(page, baseURL: nil)  ->  view.setHtml(page)
    WKWebView.evaluateJavaScript(code) { ... }    ->  view.run(code, callback)
    webView(_:didFinish:)                         ->  page.loadFinished

IL PONTE
--------
In Swift la pagina mandava un messaggio cosi'::

    window.webkit.messageHandlers.toggleMessageHandler.postMessage({...})

Quel nome (``webkit``) e' di WebKit.  Su Chromium non esiste.  Qui si mette
un oggetto con lo stesso nome, iniettato prima di qualunque altra cosa, che
fa la stessa cosa: riceve un oggetto JavaScript e lo consegna a Python.

    Files/script.js  resta  IDENTICO, riga per riga.

Questo e' il punto di tutto il porting: il JavaScript che fa la parte
difficile (le sottolineature parola per parola) e' gia' scritto, e' provato,
e' stato usato sull'app originale.  Se lo si riscrivesse, si perderebbero
tutte le prove che l'app originale funziona.  Il porting tocca Python e
tocca il minimo possibile del JavaScript.

ATTENZIONE A ``WebBrowserView``
-------------------------------
Questa classe e' la VECCHIA visione del capitolo della Bibbia, e non e' piu'
usata da nessuna schermata: nell'app originale e' rimasta accanto a
``WebBrowserArticleView``, che la ha sostituita.  Si porta dietro due cose
che non funzionano piu' col ``script.js`` di oggi:

  1. chiama ``restoreHighlight()`` senza argomenti, mentre in ``script.js``
     la funzione ne chiede cinque (paragrafo, inizio, fine, colore, bibbia);
  2. usa ``defSpans`` e ``unwrap()``, che in ``script.js`` non ci sono piu'.

Per questo e' rimasta com'e', e non viene costruita da nessuna parte.  Il
posto dove il capitolo della Bibbia si mostra davvero e'
``SubViews/ArticleView.py``.  Qui sotto il trucco del ponte, pero', e' vivo
e serve agli altri due.
"""

from pathlib import Path

# QtWebEngineWidgets si importa QUI, in cima al file, e non piu' in fondo.
# Il motivo e' che deve entrare prima che qualcuno crei una QApplication:
# se arriva dopo, QtWebEngine non parte e si legge
#     "QtWebEngineWidgets must be imported ... before a QCoreApplication
#      instance is created"
# che non dice che il problema e' qui dentro.  Averlo in cima lo rende una
# cosa dichiarata invece di una cosa che dipende da chi importa che cosa.
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401  (ordine conta)
from PyQt6.QtCore import QFile, QIODevice, QObject, QUrl, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineScript
from PyQt6.QtWidgets import QVBoxLayout, QWidget

# ---------------------------------------------------------------------------
# IL PONTE
# ---------------------------------------------------------------------------

# Il nome con cui la pagina chiama il ponte.  In Files/script.js compare
# quattro volte e non si tocca, quindi questo nome e' un contratto.
BRIDGE_NAME = "jwlBridge"
MESSAGE_HANDLER_NAME = "toggleMessageHandler"

# Il codice che mette a posto il nome di WebKit, cosi' script.js resta
# identico.  Va iniettato PRIMA di qualunque altra cosa, e per questo vive
# in un QWebEngineScript con punto di iniezione DocumentCreation.
WEBKIT_SHIM = """
(function () {
  if (window.webkit && window.webkit.messageHandlers
      && window.webkit.messageHandlers.%(handler)s) { return; }
  window.webkit = window.webkit || {};
  window.webkit.messageHandlers = window.webkit.messageHandlers || {};
  window.webkit.messageHandlers.%(handler)s = {
    postMessage: function (payload) {
      if (window.%(bridge)s) {
        window.%(bridge)s.received(JSON.stringify(payload));
      }
    }
  };
})();
""" % {"handler": MESSAGE_HANDLER_NAME, "bridge": BRIDGE_NAME}

# Il collegamento fra la pagina e l'oggetto Python.  Va eseguito DOPO
# qwebchannel.js, e quindi viene inserito dopo di quello fra gli script
# della pagina: Qt li esegue nell'ordine in cui sono stati inseriti.
# NELLE STRINGHE DEL JAVASCRIPT NON CI VANNO GLI APOSTROFI.
# Sono delimitatori di stringa in JS, e il italiano li usa dappertutto: un
# messaggio con "non e' stato" chiude la stringa a meta' e il file intero
# diventa un SyntaxError.  E' successo qui, e il sintomo e' che il ponte non
# si collega e la pagina resta muta senza dire niente.  Per questo i messaggi
# di questo blocco sono senza apostrofi, e la spiegazione e' qui sopra.
CHANNEL_BOOTSTRAP = """
(function () {
  var tentativi = 0;
  function collega() {
    tentativi++;
    // Se manca il trasportatore, il canale non e stato agganciato alla
    // pagina: si aspetta un po e si riprova, ma non all infinito.
    if (typeof qt === "undefined" || !qt.webChannelTransport) {
      if (tentativi < 100) { setTimeout(collega, 20); }
      else { console.error("JWLibrary: qt.webChannelTransport mancante. Il canale non e stato agganciato alla pagina con setWebChannel."); }
      return;
    }
    if (typeof QWebChannel === "undefined") {
      if (tentativi < 100) { setTimeout(collega, 20); }
      else { console.error("JWLibrary: qwebchannel.js non e stato caricato."); }
      return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
      window.%(bridge)s = channel.objects.%(bridge)s;
      if (!window.%(bridge)s) {
        console.error("JWLibrary: oggetto %(bridge)s non trovato nel canale.");
      }
    });
  }
  collega();
})();
""" % {"bridge": BRIDGE_NAME}

# L'AVVISO DELLA SELEZIONE
# ------------------------
# Il menu dei colori non sta piu' nella fascia: compare dove si seleziona.
# Perche' compaia, la pagina deve dire a Python **quando** una selezione e'
# finita e **dove** e' successa; Python non puo' vederlo da solo, perche' la
# selezione vive dentro Chromium.
#
# QUESTO SCRIPT E' AGGIUNTO, NON SOSTITUITO
# -----------------------------------------
# ``Files/script.js`` resta identico al progetto originale e non si tocca:
# e' la parte difficile (le sottolineature parola per parola) ed e' quella
# provata.  Questo blocco e' un secondo script, accanto a quello, che fa una
# cosa sola: ascoltare il rilascio del mouse e mandare un messaggio.
#
# PERCHE' IL ``setTimeout``
# -------------------------
# ``makeSelectable()`` aggancia a ogni parola un ``mouseup`` che chiama
# ``coverAll()``: la selezione vera viene **allargata** in quel momento.
# Il nostro ascoltatore gira sullo stesso evento, e senza il ritardo
# leggerebbe la selezione di prima.  Dieci millisecondi sono il tempo di far
# finire i gestori della parola, e non si vedono.
#
# NIENTE APOSTROFI, come sopra: sono delimitatori di stringa in JS.
SELEZIONE_JS = """
(function () {
  if (window.__jwlAscoltaSelezione) { return; }
  window.__jwlAscoltaSelezione = true;

  // ------------------------------------------------------------------
  // IL DIFETTO DI CHROMIUM, E PERCHE' SI VEDE SOLO QUI
  // ------------------------------------------------------------------
  // `coverAll()` in `script.js` allarga la selezione alle parole intere.
  // In WebKit (l'app originale) l'ancora della selezione restava la parola;
  // in Chromium `measure` no: dopo `setStartBefore` l'ancora diventa il
  // **paragrafo**, e `parentElement` il suo contenitore.  `addHighlight`
  // cerca `selectionStart` fra le `selectable` del paragrafo, non lo trova,
  // e non manda nessun messaggio: la sottolineatura non viene salvata e non
  // si vede niente.  Non e' un errore che si legge in console: e' un
  // silenzio.
  //
  // Qui si rimette la selezione sui nodi di testo prima di chiamare
  // `addHighlight`, cosi' l'ancora torna a essere la parola.  `script.js`
  // resta identico al progetto originale: questo e' un secondo script
  // accanto, non una modifica al primo.
  function selectableDa(nodo, offset, versoAvanti) {
    if (!nodo) { return null; }
    if (nodo.nodeType === 3) {
      var padre = nodo.parentElement;
      return (padre && padre.tagName === "SELECTABLE") ? padre : null;
    }
    if (nodo.nodeType !== 1) { return null; }
    var figli = nodo.childNodes;
    var i = versoAvanti ? offset : offset - 1;
    while (i >= 0 && i < figli.length) {
      var figlio = figli[i];
      if (figlio.nodeType === 1) {
        if (figlio.tagName === "SELECTABLE") { return figlio; }
        var dentro = figlio.querySelector ? figlio.querySelector("selectable") : null;
        if (dentro) { return dentro; }
      }
      i += versoAvanti ? 1 : -1;
    }
    return null;
  }

  var addHighlightOriginale = window.addHighlight;
  if (typeof addHighlightOriginale === "function") {
    window.addHighlight = function (color, isBible) {
      var sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        var range = sel.getRangeAt(0);
        if (range.startContainer.nodeType === 1) {
          var inizio = selectableDa(range.startContainer, range.startOffset, true);
          var fine = selectableDa(range.endContainer, range.endOffset, false);
          if (inizio && fine && inizio.firstChild && fine.firstChild) {
            var nuovo = document.createRange();
            nuovo.setStart(inizio.firstChild, 0);
            var ultimo = fine.firstChild;
            nuovo.setEnd(ultimo, ultimo.nodeType === 3 ? ultimo.length : ultimo.childNodes.length);
            sel.removeAllRanges();
            sel.addRange(nuovo);
          }
        }
      }
      return addHighlightOriginale.call(this, color, isBible);
    };
  }

  // ------------------------------------------------------------------
  // DOVE SI E' ARRIVATI
  // ------------------------------------------------------------------
  // Un segnalibro non ha bisogno di una selezione: si mette sul paragrafo
  // che si sta guardando.  Queste due funzioni dicono a Python **quale**
  // paragrafo e' e **quale id** ha, cosi' riaprendo il segnalibro si torna
  // esattamente li'.
  function paragrafoDi(nodo) {
    var corrente = nodo;
    while (corrente) {
      if (corrente.nodeType === 1) {
        if (corrente.hasAttribute && corrente.hasAttribute("data-pid")) {
          return Number(corrente.getAttribute("data-pid")) || 0;
        }
        if (corrente.id && String(corrente.id).charAt(0) === "v") {
          var pezzi = String(corrente.id).split("-");
          if (pezzi.length > 2) { return Number(pezzi[2]) || 0; }
        }
      }
      corrente = corrente.parentNode;
    }
    return 0;
  }

  function ancoraDi(nodo) {
    var corrente = nodo;
    while (corrente) {
      if (corrente.nodeType === 1 && corrente.id) { return String(corrente.id); }
      corrente = corrente.parentNode;
    }
    return "";
  }

  window.__jwlPosizioneVisibile = function (isBible) {
    var selettore = isBible ? "span[id^='v']" : "p[data-pid]";
    var nodi = document.querySelectorAll(selettore);
    if (!nodi.length && !isBible) { nodi = document.querySelectorAll("[data-pid]"); }
    var scelto = null;
    for (var i = 0; i < nodi.length; i++) {
      var r = nodi[i].getBoundingClientRect();
      if (r.height > 0 && r.bottom > 8 && r.top < (window.innerHeight - 8)) {
        scelto = nodi[i];
        break;
      }
    }
    if (!scelto && nodi.length) { scelto = nodi[0]; }
    if (!scelto) { return {"paragrafo": 0, "ancora": "", "testo": ""}; }
    var testo = String(scelto.innerText || scelto.textContent || "");
    testo = testo.replace(/\\s+/g, " ").trim();
    if (testo.length > 300) { testo = testo.slice(0, 300); }
    return {
      "paragrafo": paragrafoDi(scelto),
      "ancora": ancoraDi(scelto),
      "testo": testo
    };
  };

  // ------------------------------------------------------------------
  // UN GIORNO PER PAGINA (SCRITTURE DEL GIORNO)
  // ------------------------------------------------------------------
  // I file mensili delle Scritture del giorno sono una sequenza piatta:
  //
  //   <header><h2>Giovedi 1 ottobre</h2></header>
  //   <p class="themeScrp">versetto</p>
  //   <div class="bodyTxt">commento</div>
  //
  // e cosi' via per ogni giorno.  Il primo header contiene anche il titolo
  // del mese (<h1>).  Queste funzioni nascondono tutto tranne un giorno,
  // cosi' la pagina si legge come una pagina sola; gli altri giorni restano
  // nel documento e tornano quando si cambia giorno, senza ricaricare il
  // file.  Se la pagina non ha questo formato non si tocca niente.
  function jwlGruppiGiorni() {
    var h2 = Array.prototype.slice.call(document.querySelectorAll("h2"));
    var theme = document.querySelectorAll("p.themeScrp");
    if (h2.length < 2 || theme.length < 2) { return []; }
    var gruppi = [];
    var contenitore = null;
    for (var i = 0; i < h2.length; i++) {
      var testa = h2[i].parentElement;
      if (!testa || testa.tagName !== "HEADER") { return []; }
      if (contenitore === null) { contenitore = testa.parentElement; }
      if (!contenitore || testa.parentElement !== contenitore) { return []; }
      gruppi.push({"testa": testa, "h2": h2[i]});
    }
    return gruppi;
  }

  function jwlNascondiGiorni(gruppi, scelto) {
    var contenitore = gruppi[0].testa.parentElement;
    if (!contenitore) { return; }
    var figli = Array.prototype.slice.call(contenitore.children);
    var indici = [];
    for (var i = 0; i < gruppi.length; i++) {
      indici.push(figli.indexOf(gruppi[i].testa));
    }
    for (var k = 0; k < figli.length; k++) {
      var figlio = figli[k];
      if (figlio.tagName === "SCRIPT" || figlio.tagName === "STYLE" ||
          figlio.tagName === "LINK" || figlio.tagName === "META") { continue; }
      var proprietario = -1;
      for (var g = 0; g < indici.length; g++) {
        if (indici[g] === k) { proprietario = g; break; }
      }
      if (proprietario >= 0) {
        if (proprietario === 0) {
          // Il primo header tiene il titolo del mese: resta sempre, ma il
          // suo <h2> si vede solo se il giorno scelto e' il primo.
          figlio.style.display = "";
          gruppi[0].h2.style.display = (scelto === 0) ? "" : "none";
        } else {
          figlio.style.display = (proprietario === scelto) ? "" : "none";
        }
        continue;
      }
      // Il contenuto appartiene all'ultimo header incontrato.
      var ultimo = -1;
      for (var g2 = 0; g2 < indici.length; g2++) {
        if (indici[g2] < k) { ultimo = g2; }
      }
      if (ultimo < 0) { continue; }
      figlio.style.display = (ultimo === scelto) ? "" : "none";
    }
  }

  window.__jwlMostraGiorno = function (indice) {
    var gruppi = jwlGruppiGiorni();
    if (!gruppi.length) { return null; }
    var scelto = Number(indice);
    if (!isFinite(scelto) || scelto < 0) { scelto = 0; }
    if (scelto >= gruppi.length) { scelto = gruppi.length - 1; }
    jwlNascondiGiorni(gruppi, scelto);
    window.scrollTo(0, 0);
    return {
      "indice": scelto,
      "totale": gruppi.length,
      "titolo": String(gruppi[scelto].h2.innerText ||
                       gruppi[scelto].h2.textContent || "")
                .replace(/\\s+/g, " ").trim(),
      "ancora": String(gruppi[scelto].h2.id || "")
    };
  };

  window.__jwlMostraGiornoDaAncora = function (ancora) {
    var gruppi = jwlGruppiGiorni();
    if (!gruppi.length) { return null; }
    var nodo = ancora ? document.getElementById(String(ancora)) : null;
    if (!nodo) { return window.__jwlMostraGiorno(0); }
    // Il giorno a cui appartiene il nodo: l'ultimo header che lo precede.
    var scelto = 0;
    for (var i = 0; i < gruppi.length; i++) {
      if (gruppi[i].testa.compareDocumentPosition(nodo) &
          Node.DOCUMENT_POSITION_FOLLOWING) {
        scelto = i;
      }
    }
    return window.__jwlMostraGiorno(scelto);
  };

  // Seleziona le parole di un versetto (per sottolinearlo tutto).
  window.__jwlSelezionaVersetto = function (id) {
    var radice = String(id).slice(0, String(id).lastIndexOf("-") + 1);
    var parole = Array.prototype.filter.call(
      document.querySelectorAll('span.v[id^="' + radice + '"] selectable'),
      function (e) { return !e.closest("a.vl, a.cl, a.b, a.fn"); });
    if (!parole.length) { return false; }
    var inizio = parole[0].firstChild;
    var fine = parole[parole.length - 1].lastChild;
    window.getSelection().setBaseAndExtent(inizio, 0, fine, (fine.length || 0));
    return true;
  };

  var jwlDownXY = null;
  document.addEventListener("mousedown", function (evento) {
    jwlDownXY = [evento.clientX, evento.clientY];
  }, true);

  document.addEventListener("mouseup", function (evento) {
    // Un clic semplice su un link apre il riferimento: niente menu colori.
    var el = evento.target;
    var linkCliccato = el && el.closest && el.closest("a");
    if (linkCliccato && jwlDownXY &&
        Math.abs(evento.clientX - jwlDownXY[0]) < 4 &&
        Math.abs(evento.clientY - jwlDownXY[1]) < 4) { return; }
    setTimeout(function () {
      var sel = window.getSelection();
      if (!sel || sel.rangeCount === 0 || sel.isCollapsed) { return; }
      var testo = String(sel);
      if (!testo || !testo.trim()) { return; }
      // Il menu va **sotto il testo selezionato**, non al punto in cui si e'
      // lasciato il mouse: trascinando, il rilascio puo' essere lontano
      // dalla selezione, e il menu comparirebbe altrove.
      var rettangolo = sel.getRangeAt(0).getBoundingClientRect();
      var x = rettangolo.left;
      var y = rettangolo.bottom;
      if (!x && typeof evento.clientX === "number") { x = evento.clientX; }
      if (!y && typeof evento.clientY === "number") { y = evento.clientY; }
      // Dopo `coverAll()` l'ancora puo' essere il paragrafo: le due funzioni
      // risalgono da li' fino a `data-pid` (o all'id `v...` della Bibbia).
      var nodo = sel.anchorNode || sel.getRangeAt(0).startContainer;
      var paragrafo = paragrafoDi(nodo);
      var ancora = ancoraDi(nodo);
      var evidenziata = false;
      var intervallo = sel.getRangeAt(0);
      var colorati = document.querySelectorAll("highlighting");
      for (var k = 0; k < colorati.length && !evidenziata; k++) {
        evidenziata = intervallo.intersectsNode(colorati[k]);
      }
      window.__jwlUltimaSelezione = {
        "testo": testo,
        "paragrafo": paragrafo,
        "ancora": ancora
      };
      window.webkit.messageHandlers.toggleMessageHandler.postMessage({
        "mode": 3,
        "x": Math.round(x),
        "y": Math.round(y),
        "testo": testo,
        "paragrafo": paragrafo,
        "ancora": ancora,
        "evidenziata": evidenziata
      });
    }, 10);
  });

  // I RIFERIMENTI: VERSETTI, CANTICI, PUBBLICAZIONI CITATE
  // In fase di cattura, cosi' la pagina non naviga: il programma apre il
  // riquadro di destra.  Sono i link /wol/bc/, /wol/pc/ e /wol/dx/.
  document.addEventListener("click", function (evento) {
    var nodo = evento.target;
    while (nodo && nodo.nodeType === 1 && nodo.tagName !== "A") {
      nodo = nodo.parentNode;
    }
    if (!nodo || nodo.nodeType !== 1) { return; }
    // Il numero di un versetto della Bibbia: non apre niente, chiede il menu
    // del versetto (gemma, nota, segnalibro...).
    if (nodo.classList && (nodo.classList.contains("vl") || nodo.classList.contains("cl"))) {
      var versetto = nodo.closest("span.v");
      if (versetto && versetto.id) {
        evento.preventDefault();
        evento.stopPropagation();
        var rett = nodo.getBoundingClientRect();
        var testoVersetto = "";
        var radice = versetto.id.slice(0, versetto.id.lastIndexOf("-") + 1);
        var parti = document.querySelectorAll('span.v[id^="' + radice + '"]');
        for (var q = 0; q < parti.length; q++) {
          var copia = parti[q].cloneNode(true);
          var tolti = copia.querySelectorAll("a.vl, a.cl, a.b, a.fn, sup");
          for (var w = 0; w < tolti.length; w++) { tolti[w].remove(); }
          testoVersetto += (copia.textContent || "") + " ";
        }
        window.webkit.messageHandlers.toggleMessageHandler.postMessage({
          "mode": 6,
          "x": Math.round(rett.left),
          "y": Math.round(rett.bottom),
          "verso": paragrafoDi(versetto),
          "ancora": versetto.id,
          "testo": testoVersetto.replace(/\\s+/g, " ").trim()
        });
        return;
      }
    }
    var video = nodo.getAttribute("data-video") || "";
    if (video) {
      evento.preventDefault();
      evento.stopPropagation();
      window.webkit.messageHandlers.toggleMessageHandler.postMessage({
        "mode": 5,
        "video": video,
        "testo": String(nodo.textContent || "").trim()
      });
      return;
    }
    var href = nodo.getAttribute("href") || "";
    if (href.indexOf("/wol/bc/") < 0 && href.indexOf("/wol/pc/") < 0 &&
        href.indexOf("/wol/dx/") < 0) { return; }
    evento.preventDefault();
    evento.stopPropagation();
    window.webkit.messageHandlers.toggleMessageHandler.postMessage({
      "mode": 4,
      "href": href
    });
  }, true);
})();
"""


class Bridge(QObject):
    """Il destinatario dei messaggi che manda la pagina.

    La pagina chiama ``window.webkit.messageHandlers.toggleMessageHandler``,
    lo shim trasforma l'oggetto in una stringa JSON e la consegna qui.
    Qui diventa un dizionario e viene emesso come segnale: chi ascolta non
    sa niente di JavaScript e chi scrive JavaScript non sa niente di Python.
    """

    message = Signal(object)

    @Slot(str)
    def received(self, grezzo: str) -> None:
        """Dalla pagina a Python.  ``grezzo`` e' la stringa JSON."""
        import json

        try:
            messaggio = json.loads(grezzo)
        except (ValueError, TypeError) as errore:
            print(f"Messaggio dalla pagina non leggibile: {errore} ⚠️  {grezzo[:200]}")
            return
        self.message.emit(messaggio)


def _install_channel_scripts(profile) -> None:
    """Mette qwebchannel.js e i due script di collegamento nella pagina.

    Si fa una volta sola per ogni profilo, non per ogni pagina.  Se lo si
    facesse per ogni pagina, aprire il capitolo successivo aggiungerebbe gli
    script una seconda volta e ogni messaggio verrebbe recapitato due volte.
    """
    if getattr(profile, "_jwl_channel_installed", False):
        return

    # qwebchannel.js e' dentro Qt.  Non e' un file nostro e non lo troviamo
    # con un percorso: sta nelle risorse compilate dentro la libreria.
    handle = QFile(":/qtwebchannel/qwebchannel.js")
    script_channel = QWebEngineScript()
    script_channel.setName("qwebchannel.js")
    script_channel.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script_channel.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script_channel.setRunsOnSubFrames(False)
    if handle.open(QIODevice.OpenModeFlag.ReadOnly):
        script_channel.setSourceCode(bytes(handle.readAll()).decode("utf-8"))
        handle.close()
    else:
        # Senza qwebchannel.js il ponte non si collega: meglio accorgersene
        # subito che lasciare una pagina muta e non capire perche'.
        print("qwebchannel.js non trovato in Qt ⚠️")
        return
    profile.scripts().insert(script_channel)

    for nome, codice in (("jwl-channel", CHANNEL_BOOTSTRAP), ("jwl-shim", WEBKIT_SHIM)):
        script = QWebEngineScript()
        script.setName(nome)
        script.setSourceCode(codice)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        profile.scripts().insert(script)

    profile._jwl_channel_installed = True


def _chiama(funzione, risultato):
    """Chiama il callback passandogli il risultato solo se lo vuole.

    ``lambda: f()`` e ``lambda x: f(x)`` sono entrambi scritti spesso, e
    sbagliare il numero di argomenti dentro un callback di Qt costa la
    finestra.  Qui si prova con il risultato e, se il numero di argomenti non
    torna, si prova senza.  Non e' magico: e' il minimo che serve perche' i
    due stili convivano senza che nessuno dei due sia quello sbagliato.
    """
    import inspect
    try:
        segnatura = inspect.signature(funzione)
        quanti = len([p for p in segnatura.parameters.values()
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
        accetta_variadica = any(p.kind == p.VAR_POSITIONAL
                                for p in segnatura.parameters.values())
    except (TypeError, ValueError):
        accetta_variadica = False
        quanti = 1
    if accetta_variadica or quanti >= 1:
        return funzione(risultato)
    return funzione()


class WebEnginePage(QWebEnginePage):
    """Una pagina con il ponte gia' collegato.

    LA RIGA CHE FA TUTTO: ``setWebChannel``.
    -----------------------------------------
    Non basta creare il ``QWebChannel`` e registrarci dentro un oggetto.  Il
    trasportatore ``qt.webChannelTransport``, che Qt inietta dentro la pagina e
    senza il quale il JavaScript non ha modo di parlare con Python, esiste SOLO
    se il canale e' stato agganciato alla pagina con ``setWebChannel``.

    Senza quella riga: il JavaScript dentro la pagina vede ``typeof qt``
    uguale a ``undefined``, il collegamento non si fa, e la pagina resta
    muta.  Non c'e' nessun errore, nessun avviso, e non si capisce perche'
    niente succeda.  E' successo qui, ed e' per questo che la riga c'e' e ha
    un commento sopra.
    """

    def __init__(self, bridge: Bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        # qwebchannel.js e i due script di collegamento, una volta sola per
        # ogni profilo.
        _install_channel_scripts(self.profile())
        # Il canale, agganciato alla pagina: e' questo che fa esistere
        # qt.webChannelTransport dentro la pagina.
        self.canale = QWebChannel(self)
        self.canale.registerObject(BRIDGE_NAME, bridge)
        self.setWebChannel(self.canale)


class WebView(QWebEngineView):
    """Un motore di pagine con tre cose in piu': il ponte, la coda, il caricamento.

    LA COSTA
    --------
In Swift le chiamate JavaScript erano annidate una dentro l'altra::

    evaluateJavaScript(a) { evaluateJavaScript(b) { evaluateJavaScript(c) } }

e' l'unico modo che ha SwiftUI per dire "prima questo, poi quello".  Qui si
scrive una lista e la si svuota da sola, uno alla volta: ``run(a,
lambda: run(b, lambda: run(c)))`` diventa ``run(a); run(b); run(c)`` e fa la
stessa cosa.  Il vantaggio e' che non si puo' dimenticare di annidare una
chiamata e lasciare il pezzo successivo in un ordine sbagliato: e' una delle
trappole elencate in COME-FUNZIONA.txt sezione 14.

UNA TRAPPOLA CHE COSTA LA FINESTRA, E CHE E' STATA MISURATA
-----------------------------------------------------------
UNA ECCEZIONE IN UN CALLBACK UCCIDE IL PROGRAMMA.  Non la stampa: lo uccide.
``runJavaScript`` chiama il callback dal codice di Qt, in C++, e se quel
callback solleva una eccezione Python l'eccezione esce da uno slot chiamato
dal C++ e Qt fa ``abort()``.  La finestra sparisce e l'ultima riga che si
vede e' un errore che non c'entra niente.

E' successo qui ed e' stato misurato: una lambda che si aspettava il
risultato del JavaScript e non lo riceveva.  Non un dato sbagliato, non un
errore di logica: ``abort()``, e la ragione si vede a dieci righe di
distanza.

Per questo in ``run()`` il callback e' SEMPRE chiuso dentro un ``try`` e il
risultato passa sempre.  La regola e' una riga: dentro un callback che Qt
chiama, non lascia uscire niente.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.bridge = Bridge(self)
        self.setPage(WebEnginePage(self.bridge, self))
        self._coda: list[tuple[str, object]] = []

    # -- il codice della pagina -------------------------------------------

    def carica(self, articolo: str) -> None:
        """Mette dentro il capitolo, con il CSS e il JavaScript del programma.

        Lo stesso assemblaggio del progetto originale: meta, foglio di stile
        dentro la testa, corpo, e lo script dentro il corpo.  Lo script va
        dentro il corpo perche' ``generateSelectable()`` in ``script.js``
        toglie il tag ``script`` dal corpo e lo rimette in fondo: se lo
        script fosse fuori dal corpo, quella riga butterebbe via la pagina.

        IL CSS SEGUE IL TEMA DELL'APP
        ----------------------------
        Il foglio di stile del capitolo e' quello del progetto originale,
        e i suoi colori sono quelli del **sito**: grigi su bianco.  Ma la
        pagina vive dentro una finestra che puo' essere scura, e allora
        il grigio `#626262` su uno sfondo scuro non si legge.

        Per questo al foglio di stile si aggiunge un pezzo con i colori
        del tema: il testo del capitolo prende il colore del tema (in
        scuro e' bianco), i grigi intermedi diventano il grigio del tema,
        e le caselle che hanno uno sfondo chiaro — le pagine stampate —
        tengono il fondo chiaro con il testo scuro, perche' il testo
        nero su un foglio stampato e' l'unica cosa leggibile.
        """
        from Utility.Stuff import carica_script, carica_style

        meta = "<meta charset='UTF-8'>"
        stile = carica_style()
        script = carica_script()
        pagina = (
            "<html><head>" + meta + "<style>" + stile + "</style></head><body>"
            + articolo
            + "<script type=\"text/javascript\">" + script + "</script>"
            # Il secondo script e' l'ascoltatore della selezione: sta qui e
            # non dentro `script.js`, che deve restare identico al progetto
            # originale.  Viene eseguito dopo, quindi trova gia' il ponte e
            # le funzioni della pagina.
            + "<script type=\"text/javascript\">" + SELEZIONE_JS + "</script>"
            + "</body></html>"
        )
        self.setHtml(pagina, QUrl("about:blank"))

    # -- il JavaScript ----------------------------------------------------

    def run(self, script: str, on_done=None) -> None:
        """Esegue un pezzo di JavaScript, e poi il prossimo.

        Le chiamate si mettono in fila e vengono eseguite una alla volta, in
        ordine.  ``on_done`` riceve il risultato dell'espressione JavaScript e
        gira sul main thread, che in Qt e' gia' dove siamo.

        Si puo' passare anche una funzione che NON accetta argomenti: in quel
        caso viene chiamata senza.  Serve perche' altrimenti mettere
        ``lambda: ...`` in una catena e' un ``TypeError``, e un ``TypeError``
        dentro un callback di Qt uccide il programma (vedi sopra).
        """
        self._coda.append((script, on_done))
        self._svuota()

    def _svuota(self) -> None:
        if not self._coda:
            return
        script, on_done = self._coda.pop(0)

        def continua(risultato=None) -> None:
            # Il try non e' paranoia: senza, un'eccezione in un callback fa
            # abort() e la finestra sparisce senza spiegare niente.
            try:
                if on_done is not None:
                    _chiama(on_done, risultato)
            except Exception as errore:  # noqa: BLE001 - qui non si lascia passare nulla
                print(f"Errore nel callback del JavaScript ⚠️  {type(errore).__name__}: "
                      f"{errore}")
            finally:
                self._svuota()

        self.page().runJavaScript(script, continua)

    # -- il seguito della pagina -----------------------------------------

    def al_fine_del_caricamento(self, cosa_fare) -> None:
        """Registra una funzione da chiamare quando la pagina e' pronta."""
        self.page().loadFinished.connect(cosa_fare)

    def togli_header(self) -> None:
        """Togli il ``<header>`` se c'e'.

        Swift faceva ``document.querySelector('header').remove()``.  Se
        l'header non c'e', ``querySelector`` restituisce null e ``remove()``
        butta un errore: in Swift l'errore finiva in un callback che non lo
        guardava, in Chromium l'errore resta sulla console.  Il ``?.``
        fa la stessa cosa e non lascia un errore in giro.
        """
        self.run("document.querySelector('header')?.remove()")


# ---------------------------------------------------------------------------
# LA CLASSE DEL PROGETTO ORIGINALE
# ---------------------------------------------------------------------------


class WebBrowserView(QWidget):
    """Il capitolo della Bibbia, alla maniera vecchia.

    Non e' usata da nessuna schermata, e non viene costruita.  Resta perche'
    il porting e' file per file e questo file esiste; il commento in cima
    spiega perche' non funziona piu' col ``script.js`` di oggi.

    Se un giorno serve, il pezzo da sistemare e' ``ripristina_evidenziazioni``:
    deve chiamare ``restoreHighlight(identifier, startToken, endToken, color,
    isBible)`` e non ``restoreHighlight()`` a caso, e deve passare per
    ``cleanBodyHighlight()`` e ``makeSelectable()`` come fa l'altro.
    """

    def __init__(self, pubb: str = "", book: int = 0, chapter: int = 0,
                 parent=None) -> None:
        super().__init__(parent)
        self.pubb = pubb
        self.book = book
        self.chapter = chapter
        self.web = WebView(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.web.bridge.message.connect(self._messaggio)
        self.web.al_fine_del_caricamento(self._pagina_pronta)

    def carica(self) -> None:
        """Il capitolo, preso da ``<pubb>/<book>/<chapter>.html`` su disco."""
        from Utility.Stuff import leggi_utente

        articolo = leggi_utente(Path(self.pubb) / str(self.book) / f"{self.chapter}.html")
        self.web.bridge._bridge_pubb = self.pubb
        self.web.bridge._bridge_book = self.book
        self.web.bridge._bridge_chapter = self.chapter
        self.web.carica(articolo)

    def _pagina_pronta(self, _ok: bool = True) -> None:
        """Cosa fare appena la pagina e' a posto."""
        from Utility.UserData.LocationManager import LocationManager
        from Utility.UserData.HighlightManager import HighlightManager
        from Utility.Structures.Generals import Publication

        self.web.togli_header()
        pub = Publication(ID=0, keySymbol=self.pubb, year=0, mepsLanguageId=4,
                          publicationTypeId=1, issueTagNumber=0, title="",
                          isBible=True, book=self.book, chapter=self.chapter)
        LocationManager.add_location(pub=pub, document_id=None)

        def ripristina() -> None:
            for evidenziazione in HighlightManager.get_highlight(pub=pub, document_id=None):
                blocco = evidenziazione.blockRange
                if blocco.identifier == -1 or blocco.startToken == -1 or blocco.endToken == -1:
                    continue
                self.web.run(
                    "restoreHighlight({}, {}, {}, {}, true);".format(
                        blocco.identifier, blocco.startToken, blocco.endToken,
                        evidenziazione.userMark.color)
                )

        self.web.run("cleanBodyHighlight(); makeSelectable();", ripristina)

    def evidenzia(self, colore: int) -> None:
        """Colorare quello che e' selezionato, o toglierlo con -1."""
        from Utility.UserData.BackupManager import BackupManager

        if colore == 0:
            return
        BackupManager.store_data_in_db()
        self.web.run("addHighlight({}, true);".format(colore))
        self.web.run("clearSelection();")

    def _messaggio(self, messaggio: dict) -> None:
        """Dalla pagina: modo 0 vuol dire "aggiungi sottolineatura"."""
        if messaggio.get("mode") != 0:
            return
        from Utility.Structures.Generals import BlockRange, Publication
        from Utility.UserData.HighlightManager import HighlightManager

        pub = Publication(ID=0, keySymbol=self.pubb, year=0, mepsLanguageId=4,
                          publicationTypeId=1, issueTagNumber=0, title="",
                          isBible=True, book=self.book, chapter=self.chapter)
        blocco = BlockRange(identifier=messaggio["paragraph"],
                            startToken=messaggio["startIndex"],
                            endToken=messaggio["endIndex"])
        HighlightManager.add_highlight(color=messaggio["color"], new_block_range=blocco,
                                       pub=pub, document_id=None)
        # IL RICARICAMENTO ERA UN ARGOMENTO, NON UN CALLBACK
        # ---------------------------------------------------
        # Qui sotto c'era:
        #
        #     self.web.run("cleanBodyHighlight(); makeSelectable();",
        #                  self.web.run("location.reload()"))
        #
        # Il secondo `run` e' un ARGOMENTO, quindi viene ESEGUITO SUBITO e
        # non passato come cosa-da-fare.  Gli argomenti si valutano da
        # sinistra a destra, quindi l'ordine vero era:
        #
        #   1. la pagina si ricarica ADESSO
        #   2. `location.reload()` restituisce None
        #   3. None viene passato come callback del primo `run`
        #
        # Il risultato e' una pagina che si ricarica mentre le si sta
        # ordinando di ridisegnarsi.  Il contesto JavaScript viene buttato
        # via mentre c'e' del lavoro in coda, e il lavoro che arriva dopo si
        # ritrova in una pagina che non ha ancora eseguito `script.js`:
        # da li' viene
        #
        #     Uncaught ReferenceError: initView is not defined
        #
        # Per rimettere l'evidenziazione non serve ricaricare: si ridisegna,
        # che e' quello che fa la riga qui sotto.
        self.web.run("cleanBodyHighlight(); makeSelectable();")
