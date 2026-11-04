#
#  SubViews/NotiziaView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Una pagina di jw.org aperta **dentro** l'app.

PERCHE' ESISTE E PERCHE' NON SI USA IL BROWSER DEL SISTEMA
--------------------------------------------------------
Una notizia e' una pagina web, e il modo piu' semplice di vederla sarebbe
`QDesktopServices.openUrl`, che apre il browser della macchina.  Ma allora
l'utente esce dall'app: un'altra finestra, un'altra barra degli indirizzi, un
altro pulsante indietro, e la pila delle schermate di questa app resta ferma
mentre lui legge.  Preme indietro e torna dove era, quindi sembra funzionare
— ma non si e' piu' dentro il programma.

Qui si riusa `WebView`, cioe' lo stesso motore che mostra il testo della
Bibbia (un `QWebEngineView`).  Non si scrive un motore nuovo: si carica un
indirizzo invece di un capitolo, e cosi' la finestra, la pila e il pulsante
indietro restano quelle che ci sono.

LA PAGINA SI FERMA E SCORRE
---------------------------
`setHtml` fa scattare di nuovo `loadFinished`.  Se quel segnale rifacesse
l'estrazione e richiamasse `setHtml`, la pagina si ricaricherebbe in un ciclo
infinito e tornerebbe in cima a ogni giro: l'articolo sembrerebbe non
scorrere.  Per questo `_articolo_mostrato` lascia passare il ciclo una volta
sola, e il CSS dichiara lo scorrimento verticale su `html`.

COSA SI MOSTRA, E COSA NO
------------------------
La pagina si spuglia di tutto quello che il sito mette **intorno**
all'articolo: menu', sidebar, breadcrumb, player audio, video, social
sharing.  Dell'articolo si tiene anche il suo `<header>`, perche' contiene
la foto di apertura e la didascalia: toglierlo portava via proprio
l'immagine che deve restare al suo posto.  Si lascia solo il titolo, il
testo, le immagini e i link, con lo stile dell'app e non quello del sito.

I LINK SONO CLICCABILI E RESTANO DENTRO L'APP
---------------------------------------------
Un link a un versetto o a un'altra notizia non apre il browser: resta dentro
l'app.  Se e' un versetto, si apre la Bibbia; se e' un'altra notizia, si
apre la notizia.  I link del sito che non hanno senso dentro l'app (Home,
menu', ecc.) sono gia' stati tolti insieme ai menu' e alle barre del sito.

L'AUDIO SI SENTE NELL'APP, NON NEL SITO
---------------------------------------
Il tasto per ascoltare l'articolo **non sta dentro la pagina**: sta nella
barra viola in alto, e compare solo se l'articolo ha davvero un audio.  La
pagina non disegna nessun bottone e non manda comandi al lettore: si limita a
dire alla finestra se l'audio esiste e qual e' il suo indirizzo.  Premendolo
parte l'audio **dentro l'app**, nella striscia in fondo alla finestra, non nel
lettore grande: una notizia si ascolta mentre si legge.

Il lettore del sito non contiene l'mp3, contiene un `data-jsonurl`:
l'indirizzo si risolve in background e il tasto compare solo se il file esiste
davvero.  La prima immagine dell'articolo viaggia insieme all'audio, cosi' la
striscia e il lettore grande mostrano la copertina giusta.

IL CARICAMENTO NON SI BLOCCA
-----------------------------
La pagina viene dal server e ci mette.  Mentre arriva c'e' un'etichetta che
lo dice e un pulsante "Indietro" che funziona gia': senza, la finestra
sembra bloccata e l'unica cosa che l'utente puo' fare e' chiuderla.

Se il caricamento fallisce si dice cosa e' successo, e si lascia il pulsante
indietro comunque.  Una pagina bianca senza spiegazione sembra un difetto del
programma, mentre e' una rete che non ha risposto.
"""

from PyQt6.QtCore import QEvent, QTimer, Qt, QUrl, pyqtSignal as Signal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

import Utility.tema as _tema
from SubViews.VeloImmagine import VeloImmagine


#: Il codice che estrae l'articolo dalla pagina del sito.
#:
#: NON SI PRENDE IL TESTO E POI SI RIMONTA LA PAGINA
#: --------------------------------------------------
#: Prima si prendevano tre liste separate — paragrafi, immagini, link — e in
#: Python si rimontava tutto mettendo prima tutte le immagini e poi tutti i
#: paragrafi.  Cosi' una foto che nell'articolo sta in mezzo a due paragrafi
#: finiva in cima, e l'ordine dell'HTML non c'entrava piu' niente.
#:
#: Qui invece si **pulisce una copia dell'articolo** e si tiene il suo HTML,
#: con l'ordine vero.  Si tolgono solo i pezzi che non sono l'articolo
#: (script, menu', video, social, strumenti del sito), si assolutizzano le
#: immagini e si trasformano i link in link interni all'app.
EXTRACT_SCRIPT = """
  (function () {
    var risultato = { titolo: '', articolo_html: '', paragrafi: [], immagini: [],
                      immagine: '', principale: '', occhiello: '', link: [],
                      audio: [], audio_json: [] };
    var h1 = document.querySelector('h1');
    if (h1) risultato.titolo = h1.textContent.trim();

    function assoluto(valore) {
      if (!valore) return '';
      try { return new URL(valore, document.baseURI).href; } catch (e) { return ''; }
    }

    // LA COPERTINA DELL'ARTICOLO
    // ---------------------------
    // Serve al mini player e al lettore grande quando parte l'audio.  Si
    // preferisce `og:image`, che e' l'immagine scelta dal sito per questa
    // pagina; se non c'e', si prendera' la prima immagine dell'articolo dopo
    // la pulizia.  Non si usa `immagini[0]`: quella lista viene costruita
    // scorrendo i nodi al contrario per poterli togliere, quindi il suo primo
    // elemento e' l'ultima foto, non la prima.
    var metaImmagine = document.querySelector('meta[property="og:image"]') ||
                       document.querySelector('meta[name="twitter:image"]');
    if (metaImmagine) {
      risultato.immagine = assoluto(metaImmagine.getAttribute('content'));
    }

    // ---------------------------------------------------------------
    // L'AUDIO SI CERCA IN TUTTA LA PAGINA
    // ---------------------------------------------------------------
    // Non solo dentro l'articolo: il lettore del sito puo' stare in una
    // barra accanto.  Si accettano solo indirizzi che sembrano davvero un
    // file audio, per non scambiare per audio un link alla sezione «Audio».
    var audioTrovati = [];
    function aggiungiAudio(valore) {
      var u = assoluto(valore);
      if (!u || !/^https?:/i.test(u)) return;
      if (!/\\.(mp3|m4a|aac|ogg)([?#]|$)/i.test(u)) return;
      for (var i = 0; i < audioTrovati.length; i++) {
        if (audioTrovati[i] === u) return;
      }
      audioTrovati.push(u);
    }
    var elementiAudio = document.querySelectorAll(
      'audio, audio source, a[href], [data-audio-src], [data-audio-url],' +
      ' [data-mp3], [data-src]');
    for (var i = 0; i < elementiAudio.length; i++) {
      var el = elementiAudio[i];
      aggiungiAudio(el.getAttribute('src'));
      aggiungiAudio(el.getAttribute('href'));
      aggiungiAudio(el.getAttribute('data-audio-src'));
      aggiungiAudio(el.getAttribute('data-audio-url'));
      aggiungiAudio(el.getAttribute('data-mp3'));
      aggiungiAudio(el.getAttribute('data-src'));
    }
    var metaAudio = document.querySelectorAll(
      'meta[property="og:audio"], meta[property="og:audio:url"],' +
      ' link[rel="alternate"][type^="audio/"]');
    for (var i = 0; i < metaAudio.length; i++) {
      aggiungiAudio(metaAudio[i].getAttribute('content') ||
                    metaAudio[i].getAttribute('href'));
    }
    risultato.audio = audioTrovati;

    // IL LETTORE DEL SITO NON DICE L'MP3: DICE DOVE CHIEDERLO
    // Il player della pagina non contiene un <audio> con l'indirizzo del
    // file.  Contiene un `data-jsonurl`: un'API che restituisce l'elenco
    // dei file.  Si raccoglie quell'indirizzo, e Python lo interroga fuori
    // dal thread della finestra.  Se l'articolo non ha audio, l'API
    // risponde 404 e non compare nessun bottone.
    var jsonAudio = document.querySelectorAll('[data-jsonurl]');
    for (var i = 0; i < jsonAudio.length; i++) {
      var indirizzoJson = assoluto(jsonAudio[i].getAttribute('data-jsonurl'));
      if (!indirizzoJson || !/^https?:/i.test(indirizzoJson)) continue;
      var gia = false;
      for (var j = 0; j < risultato.audio_json.length; j++) {
        if (risultato.audio_json[j] === indirizzoJson) gia = true;
      }
      if (!gia) risultato.audio_json.push(indirizzoJson);
    }

    // ---------------------------------------------------------------
    // LA FOTO CHE STA PRIMA DEL TITOLO
    // ---------------------------------------------------------------
    // Sul sito l'articolo comincia con una figura — `articleTopRelatedImage`
    // — che sta **fuori** dall'<article>': e' la foto di apertura, e non
    // arriva mai nel testo che si estrae.  Senza di lei l'articolo
    // comincia dal titolo, e sembra una pagina senza foto.
    //
    // La si prende dal suo contenitore: il sito ci mette dentro uno
    // <span class="jsRespImg"> con le varie misure, e la piu' grande e'
    // quella giusta per la pagina larga.  Il <noscript> dentro ha un
    // <img> pronto, ma e' la misura piu' piccola: si usa solo se le altre
    // non ci sono.
    function baseDi(indirizzo) {
      // Il nome del file senza la misura: "102013244_univ_lsr_md.jpg" e
      // "102013244_univ_lsr_lg.jpg" sono la stessa foto, una piccola e una
      // grande.
      var nome = (indirizzo || '').split('?')[0].split('/').pop();
      return nome.replace(/_(xs|sm|md|lg|xl)\\.(jpg|jpeg|png|webp)$/i, '');
    }
    var figura = document.querySelector('#articleTopRelatedImage') ||
                 document.querySelector('figure.article-top-related-image');
    if (figura) {
      var contenitore = figura.querySelector('.jsRespImg');
      var misura = '';
      if (contenitore) {
        misura = contenitore.getAttribute('data-img-size-lg') ||
                 contenitore.getAttribute('data-zoom') ||
                 contenitore.getAttribute('data-img-size-md') ||
                 contenitore.getAttribute('data-img-size-sm') ||
                 contenitore.getAttribute('data-img-size-xs');
      }
      if (!misura) {
        var immagineFigura = figura.querySelector('img');
        if (immagineFigura) misura = immagineFigura.getAttribute('src') || '';
      }
      if (misura) {
        var scelta = assoluto(misura);
        // LA MISURA GRANDE
        // -----------------
        // Il sito, quando il suo JavaScript lavora, sostituisce lo
        // <span> con un <img> gia' pronto, e l'indirizzo che si legge e'
        // quello scelto per **la sua** finestra: piu' piccolo di quello
        // che serve qui.  L'`og:image` e' la stessa foto alla misura
        // grande, e si usa solo se e' davvero la stessa foto — il confronto
        // e' sul nome del file, perche' un'altra immagine messa li' farebbe
        // capire che qualcosa e' andato storto.
        if (risultato.immagine &&
            baseDi(risultato.immagine) === baseDi(scelta)) {
          scelta = risultato.immagine;
        }
        risultato.principale = scelta;
      }
    }

    // ---------------------------------------------------------------
    // L'ARTICOLO, NELL'ORDINE IN CUI E' SCRITTO
    // ---------------------------------------------------------------
    var corpo = document.querySelector('article') ||
                document.querySelector('main') ||
                document.querySelector('.article') ||
                document.querySelector('.content') ||
                document.body;
    if (!corpo) return JSON.stringify(risultato);

    var copia = corpo.cloneNode(true);

    // LE FOTO "RESPONSIVE" DEL SITO
    // Il sito non mette subito un <img>: mette uno <span class="jsRespImg">
    // con dentro le varie misure, e il suo JavaScript lo trasforma in
    // un'immagine dopo.  Se l'estrazione arriva prima di quel passaggio,
    // l'immagine sparisce.  Qui la si costruisce subito dalla misura media,
    // che e' quella giusta per la larghezza dell'articolo.
    var risposte = copia.querySelectorAll('.jsRespImg');
    for (var i = 0; i < risposte.length; i++) {
      var contenitore = risposte[i];
      var misura = contenitore.getAttribute('data-img-size-md') ||
                   contenitore.getAttribute('data-img-size-sm') ||
                   contenitore.getAttribute('data-img-size-xs') ||
                   contenitore.getAttribute('data-img-size-lg');
      if (misura && contenitore.parentNode) {
        var immagine = document.createElement('img');
        immagine.setAttribute('src', misura);
        immagine.setAttribute('alt', '');
        contenitore.parentNode.replaceChild(immagine, contenitore);
      }
    }

    // I PEZZI DEL SITO CHE NON SONO L'ARTICOLO
    //
    // `header` e `footer` NON si tolgono: l'articolo ha il suo <header> con
    // la foto di apertura e la didascalia.  Toglierlo portava via proprio
    // l'immagine che deve restare al suo posto.  Il whitelist qui sotto non
    // conosce HEADER e FOOTER, quindi li "scioglie" e tengono i figli.
    var daTogliere = copia.querySelectorAll(
      'script, style, noscript, iframe, video, audio, form, button, input,' +
      ' select, textarea, svg, canvas, nav, aside,' +
      ' .documentActions, .articleMeta, .share, .social, .related,' +
      ' .breadcrumb, .toolbar, .languageSelector, .publicationInfo, .nav, .meta,' +
      ' .jsAudioPlayer, #streamingAudio, .jsPinnedAudioPlayer,' +
      ' .jsPlayUppCaseLabel,' +
      // I pezzi che il sito NASCONDE: il titolo della pagina qui dentro
      // ("onPageTitle"), che sul sito si vede solo quando si salta a una
      // sezione, e che qui comparirebbe come un titolo ripetuto sotto
      // quello vero.
      ' .onPageTitle, .hideObj');
    for (var i = daTogliere.length - 1; i >= 0; i--) {
      if (daTogliere[i].parentNode) {
        daTogliere[i].parentNode.removeChild(daTogliere[i]);
      }
    }

    // Il titolo lo mostra gia' l'app: nell'articolo sarebbe il secondo.
    var h1Copia = copia.querySelector('h1');
    if (h1Copia && h1Copia.parentNode) h1Copia.parentNode.removeChild(h1Copia);

    // L'OCHIELLO
    // ----------
    // Il sito mette sopra il titolo una scritta che dice da dove viene
    // l'articolo ("IN COPERTINA").  Se la si lascia nel testo, nell'app
    // finisce **sotto** il titolo — il contrario del sito — e sembra un
    // pezzo fuori posto.  Quindi la si prende qui e la si rimette
    // davanti al titolo, dove il sito ce l'ha.
    var occhielloCopia = copia.querySelector('.contextTtl');
    if (occhielloCopia) {
      var testoOcchello = (occhielloCopia.textContent || '').replace(/\\s+/g, ' ').trim();
      if (testoOcchello) risultato.occhiello = testoOcchello;
      if (occhielloCopia.parentNode) {
        occhielloCopia.parentNode.removeChild(occhielloCopia);
      }
    }

    // SOLO I TAG CHE SONO CONTENUTO
    // Un DIV o uno SPAN del sito non servono: si tolgono e si tengono i
    // figli, cosi' il testo non sparisce.  Gli altri si buttano via.
    var consentiti = { P: 1, H2: 1, H3: 1, H4: 1, IMG: 1, A: 1, UL: 1, OL: 1,
                       LI: 1, BLOCKQUOTE: 1, STRONG: 1, EM: 1, B: 1, I: 1,
                       SUP: 1, SUB: 1, BR: 1, FIGURE: 1, FIGCAPTION: 1 };
    var nodi = copia.querySelectorAll('*');
    for (var i = nodi.length - 1; i >= 0; i--) {
      var nodo = nodi[i];
      if (!nodo.parentNode) continue;
      var tag = nodo.tagName;
      if (!consentiti[tag]) {
        var padre = nodo.parentNode;
        while (nodo.firstChild) padre.insertBefore(nodo.firstChild, nodo);
        padre.removeChild(nodo);
        continue;
      }
      // Si tengono solo gli attributi che servono, e si tolgono tutti gli
      // altri (classe, stile, gestori di eventi).
      var nomi = [];
      for (var j = 0; j < nodo.attributes.length; j++) {
        nomi.push(nodo.attributes[j].name);
      }
      for (var j = 0; j < nomi.length; j++) {
        var nome = nomi[j];
        if (tag === 'A' && nome === 'href') continue;
        if (tag === 'IMG' && (nome === 'src' || nome === 'data-src' ||
                              nome === 'alt')) continue;
        nodo.removeAttribute(nome);
      }
      if (tag === 'A') {
        var href = assoluto(nodo.getAttribute('href'));
        // Un link che punta a un'immagine (il «clicca per ingrandire» del
        // sito) non e' un articolo: si toglie il link e resta la foto.
        if (!href || !/^https?:/i.test(href) ||
            /\\.(jpe?g|png|gif|webp|svg)([?#]|$)/i.test(href)) {
          var padreA = nodo.parentNode;
          while (nodo.firstChild) padreA.insertBefore(nodo.firstChild, nodo);
          padreA.removeChild(nodo);
          continue;
        }
        nodo.setAttribute('href', '#');
        nodo.setAttribute('data-href', href);
        nodo.setAttribute('class', 'link-articolo');
        risultato.link.push({ href: href, testo: nodo.textContent.trim() });
      } else if (tag === 'IMG') {
        var src = assoluto(nodo.getAttribute('src') ||
                           nodo.getAttribute('data-src'));
        if (!src || !/^https?:/i.test(src)) {
          if (nodo.parentNode) nodo.parentNode.removeChild(nodo);
          continue;
        }
        var alt = nodo.getAttribute('alt') || '';
        nodo.setAttribute('src', src);
        nodo.setAttribute('alt', alt);
        nodo.setAttribute('loading', 'lazy');
        nodo.setAttribute('onerror', "this.style.display='none'");
        risultato.immagini.push({ src: src, alt: alt });
      }
    }

    // I paragrafi vuoti (spazi, niente immagini) non si vedono e creano
    // buchi: si tolgono.
    var vuoti = copia.querySelectorAll('p');
    for (var i = vuoti.length - 1; i >= 0; i--) {
      if (!vuoti[i].textContent.trim() && !vuoti[i].querySelector('img')) {
        if (vuoti[i].parentNode) vuoti[i].parentNode.removeChild(vuoti[i]);
      }
    }

    risultato.articolo_html = copia.innerHTML;

    // Se `og:image` non c'era, la copertina e' la prima foto rimasta
    // nell'articolo pulito.  Le immagini sono gia' state rese assolute.
    if (!risultato.immagine) {
      var primaImmagine = copia.querySelector('img');
      if (primaImmagine) {
        risultato.immagine = primaImmagine.getAttribute('src') || '';
      }
    }

    // I campi vecchi restano per sicurezza: se l'HTML pulito fosse vuoto,
    // Python sa ancora rimontare la pagina.
    var paragrafi = copia.querySelectorAll('p');
    for (var i = 0; i < paragrafi.length; i++) {
      var testo = paragrafi[i].textContent.trim();
      if (testo.length > 0) risultato.paragrafi.push(testo);
    }
    return JSON.stringify(risultato);
  })();
"""

def _colori_tema() -> dict:
    """I colori del tema attivo, per il template HTML."""
    chiaro = _tema.tema_attivo()
    accento = "#64398b"
    if chiaro:
        return {
            "sfondo": "#ffffff",
            "testo": "#1a1a1a",
            "titolo": "#000000",
            "grigio": "#666666",
            "link": "#0066cc",
            "link_hover": "#004499",
            "bordo": "#e3e3e3",
            "img": "#e8e6e4",
            "accento": accento,
        }
    else:
        return {
            "sfondo": "#1a1a1a",
            "testo": "#e0e0e0",
            "titolo": "#ffffff",
            "grigio": "#888888",
            "link": "#6ab0f3",
            "link_hover": "#9ccfff",
            "bordo": "#3d3d3d",
            "img": "#2b2b2b",
            "accento": accento,
        }


def _escape(testo: str) -> str:
    """Escapa i caratteri HTML per evitare XSS."""
    if not testo:
        return ""
    return (testo.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def _mp3_da_json(indirizzo: str, referer: str = "") -> str:
    """Chiede all'API del sito l'mp3 di un articolo.

    Il lettore della pagina non contiene il file: contiene un
    ``data-jsonurl`` che restituisce un JSON con, dentro, l'elenco dei
    formati.  Si cerca un indirizzo audio vero e si restituisce il primo.

    Restituisce ``""`` quando l'articolo non ha audio: in quel caso l'API
    risponde 404, e non si deve mostrare nessun bottone.
    """
    import json
    import re
    import urllib.error
    import urllib.request

    if not indirizzo:
        return ""
    intestazioni = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }
    if referer:
        intestazioni["Referer"] = referer
    try:
        richiesta = urllib.request.Request(indirizzo, headers=intestazioni)
        with urllib.request.urlopen(richiesta, timeout=10) as risposta:
            dati = json.load(risposta)
    except (urllib.error.URLError, ValueError, OSError, TimeoutError):
        return ""

    candidati = []

    def visita(valore) -> None:
        if isinstance(valore, dict):
            for chiave, figlio in valore.items():
                if (chiave in ("url", "stream") and isinstance(figlio, str)
                        and re.search(r"\.(mp3|m4a|aac|ogg)([?#]|$)",
                                      figlio, re.IGNORECASE)):
                    candidati.append((chiave, figlio))
                else:
                    visita(figlio)
        elif isinstance(valore, list):
            for figlio in valore:
                visita(figlio)

    visita(dati)
    # `stream` e' pensato per la riproduzione, `url` per il download:
    # per il mini player si preferisce il primo.
    for chiave, url in candidati:
        if chiave == "stream":
            return url
    return candidati[0][1] if candidati else ""


class NotiziaView(QWidget):
    """Una pagina di jw.org, letta dentro la finestra dell'app."""

    goBack = Signal()
    messaggio = Signal(str)
    #: L'articolo ha un audio vero: (url).  La barra viola mostra le cuffie.
    audioTrovato = Signal(str)
    #: L'articolo non ha audio: la barra viola nasconde le cuffie.
    audioAssente = Signal()
    #: Si e' premuto un link: (href)
    linkPremuto = Signal(str)

    def __init__(self, url: str, titolo: str = "", parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self.titolo = titolo
        #: L'audio risolto, e la copertina dell'articolo da passare al
        #: lettore quando si preme la cuffia nella barra viola.
        self.audio_url = ""
        self.immagine_articolo = ""
        #: La scala del testo in percentuale.  Si parte dalla misura scelta
        #: dall'utente — quella vale per tutta l'app — e la finestra puo'
        #: cambiarla con `imposta_dimensione_testo`; 100 e' la misura normale.
        self._dimensione_testo = _tema.dimensione_testo()
        self._audio_annunciato = False
        # L'articolo estratto si mostra UNA VOLTA SOLA.  `setHtml` fa scattare
        # di nuovo `loadFinished`, e senza questo lucchetto `_pagina_pronta`
        # rieseguiva l'estrazione e `_mostra_articolo` ricaricava la pagina:
        # un ciclo infinito che riportava la pagina in cima a ogni giro, e
        # quindi non si riusciva a scorrere.  Misurato: oltre 4.000
        # caricamenti in pochi secondi.
        self._articolo_mostrato = False
        #: Gli indirizzi `data-jsonurl` da risolvere quando la pagina pulita
        #: ha finito di caricarsi (vedi `_avvia_audio_pendente`).
        self._audio_json_pendente = []

        from WebBrowserView import WebView

        disposizione = QVBoxLayout(self)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)

        self._stato = QLabel("Carico la pagina...", self)
        self._stato.setObjectName("vuoto")
        self._stato.setWordWrap(True)
        self._stato.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disposizione.addWidget(self._stato)

        self.web = WebView(self)
        self.web.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # La cronologia del WebView e il suo menu' non devono portare alla
        # pagina del sito: l'utente resta nella notizia e torna con la freccia
        # dell'app.  Il tasto «indietro» del mouse e Alt+sinistra vengono
        # intercettati qui e diventano il `goBack` della schermata.
        self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.web.installEventFilter(self)
        disposizione.addWidget(self.web, 1)
        self.web.setVisible(False)

        self.web.bridge.message.connect(self._messaggio)
        self.web.al_fine_del_caricamento(self._pagina_pronta)

        # LA FIGURA A SCHERMO INTERO
        # ---------------------------
        # Cliccando una foto dell'articolo si apre a tutto schermo dentro
        # l'app, e va anche sullo schermo esterno: e' lo stesso velo delle
        # pubblicazioni, e quindi fa le stesse cose.
        self.velo = VeloImmagine(self)

    def carica(self) -> None:
        """Apre l'indirizzo."""
        self.web.setUrl(QUrl(self.url))
        self._aggancia_filtro_tastiera()

    def _aggancia_filtro_tastiera(self) -> None:
        """Mette il filtro anche sul widget interno di Chromium.

        Il tasto «indietro» del mouse e Alt+sinistra non arrivano sempre alla
        `QWebEngineView`: li riceve il widget che Chromium crea dentro di lei.
        Senza questo filtro, quel tasto faceva tornare il WebView alla pagina
        del sito — la «pagina come browser» che non deve esistere.
        """
        try:
            proxy = self.web.focusProxy()
        except (AttributeError, RuntimeError):
            proxy = None
        if proxy is not None:
            proxy.installEventFilter(self)

    def eventFilter(self, oggetto, evento) -> bool:
        """Il tasto indietro del mouse e Alt+sinistra tornano all'app."""
        try:
            interno = oggetto is self.web or oggetto is self.web.focusProxy()
        except (AttributeError, RuntimeError):
            interno = False
        if interno:
            if evento.type() == QEvent.Type.MouseButtonPress:
                try:
                    if evento.button() == Qt.MouseButton.BackButton:
                        self.goBack.emit()
                        return True
                except AttributeError:
                    pass
            elif evento.type() == QEvent.Type.KeyPress:
                try:
                    if evento.matches(QKeySequence.StandardKey.Back):
                        self.goBack.emit()
                        return True
                except (AttributeError, TypeError):
                    pass
        return super().eventFilter(oggetto, evento)

    def _pulisci_storia(self) -> None:
        """Toglie la pagina del sito dalla cronologia del WebView.

        `setUrl` mette la pagina del sito nella cronologia, e `setHtml` ne
        aggiunge una seconda.  La prima e' quella che compariva premendo
        «indietro»: una pagina del sito, con il suo aspetto da browser, dentro
        un'app che deve mostrare solo l'articolo.  Qui si svuota la
        cronologia, cosi' l'unico indietro possibile e' quello della pila
        delle schermate.
        """
        try:
            self.web.page().history().clear()
        except (AttributeError, RuntimeError):
            pass

    def _pagina_pronta(self, riuscito: bool = True) -> None:
        """La pagina e' arrivata, o non e' arrivata."""
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        self._aggancia_filtro_tastiera()
        # Il secondo `loadFinished` e' quello del nostro stesso `setHtml`:
        # non c'e' niente da estrarre, e rieseguire il ciclo riporterebbe la
        # pagina in cima (vedi `_articolo_mostrato`).
        if self._articolo_mostrato:
            self._pulisci_storia()
            # La pagina pulita ora c'e': si mostra **adesso**, non prima.
            # Mostrarla subito dopo `setHtml` poteva far vedere per un istante
            # la pagina del sito che stava ancora sotto, e l'utente avrebbe
            # visto un lampo di browser dentro l'app.
            self._stato.setVisible(False)
            self.web.setVisible(True)
            # E' anche il momento giusto per chiedere l'mp3 del lettore del
            # sito: prima `.articolo` non esiste ancora (vedi
            # `_mostra_articolo`).
            self._avvia_audio_pendente()
            return
        if riuscito:
            # La pagina del sito non deve restare nella cronologia: era lei a
            # comparire al primo «indietro», e sembrava un browser dentro
            # l'app.  Si toglie subito, prima ancora di estrarre l'articolo;
            # poi si toglie anche la pagina costruita da `setHtml`.
            self._pulisci_storia()
            # Un attimo per il JavaScript del sito: le foto «responsive» e il
            # lettore audio vengono costruiti dopo il caricamento.  Senza
            # questa attesa si estrae una pagina ancora senza immagini.
            QTimer.singleShot(500, self._estrai)
        else:
            self.web.setVisible(False)
            self._stato.setVisible(True)
            self._stato.setText(
                f"Non sono riuscito a aprire la pagina.\n\n{self.url}\n\n"
                "Controlla la connessione e riprova.")
            self.messaggio.emit("Pagina non aperta")

    def _estrai(self) -> None:
        """Esegue l'estrazione quando il JavaScript del sito ha finito."""
        from PyQt6 import sip

        if sip.isdeleted(self) or self._articolo_mostrato:
            return
        self.web.run(EXTRACT_SCRIPT, self._mostra_articolo)

    def _mostra_articolo(self, risultato: str) -> None:
        """Riceve il JSON estratto e costruisce la pagina con lo stile dell'app."""
        import json

        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        if self._articolo_mostrato:
            return
        self._articolo_mostrato = True
        try:
            dati = json.loads(risultato or "{}")
        except (json.JSONDecodeError, TypeError):
            dati = {}

        titolo = dati.get("titolo", "") or self.titolo or ""
        articolo_html = dati.get("articolo_html", "") or ""
        paragrafi = dati.get("paragrafi", []) or []
        immagini = dati.get("immagini", []) or []
        link = dati.get("link", []) or []
        audio = dati.get("audio", []) or []
        audio_json = dati.get("audio_json", []) or []
        self.immagine_articolo = (dati.get("immagine", "") or
                                  (immagini[0].get("src", "")
                                   if immagini and isinstance(immagini[0], dict)
                                   else ""))
        #: La foto che il sito mette **prima del titolo**: sta fuori
        #: dall'articolo, e senza di lei l'articolo comincia dal titolo.
        principale = dati.get("principale", "") or ""
        #: L'occhiello: la scritta che sul sito sta sopra il titolo e dice
        #: da dove viene l'articolo ("IN COPERTINA").
        occhiello = dati.get("occhiello", "") or ""

        colori = _colori_tema()

        # COSTRUISCE IL CORPO DELL'ARTICOLO
        #
        # LA FOTO PRIMA, POI IL TITOLO
        # -----------------------------
        # Come sul sito: la foto di apertura viene prima del titolo, e non
        # dentro il testo.  Il titolo lo mette l'app, e quindi l'ordine
        # dei due pezzi lo decide l'app.
        parti = []
        if principale:
            parti.append(f'<img class="principale" src="{_escape(principale)}" '
                         f'alt="">')
        if occhiello:
            parti.append(f'<p class="occhiello">{_escape(occhiello)}</p>')
        if titolo:
            parti.append(f"<h1>{_escape(titolo)}</h1>")

        if articolo_html:
            # L'HTML e' gia' nell'ordine dell'articolo: le foto restano dove
            # sono scritte, in mezzo ai paragrafi, e i link sono gia' stati
            # trasformati in link interni.
            parti.append(f'<div class="articolo">{articolo_html}</div>')
        else:
            # RISERVA: se l'HTML pulito non c'e', si rimonta dalle liste.
            # Le immagini non hanno piu' la loro posizione: e' il motivo per
            # cui questa strada si usa solo quando l'altra e' vuota.
            for img in immagini:
                src = img.get("src", "")
                alt = img.get("alt", "")
                if src:
                    parti.append(
                        f'<img src="{_escape(src)}" alt="{_escape(alt)}" '
                        f'onerror="this.style.display=\'none\'">')
                    if alt:
                        parti.append(
                            f'<p class="immagine-alt">{_escape(alt)}</p>')
            for p in paragrafi:
                parti.append(f"<p>{_escape(p)}</p>")
            if link:
                parti.append('<p style="margin-top: 16px; font-size: 0.875em;">')
                parti.append('<strong>Link:</strong><br>')
                for l in link:
                    href = l.get("href", "")
                    testo = l.get("testo", "")
                    if href and testo:
                        parti.append(
                            f'<a class="link-articolo" href="#" '
                            f'data-href="{_escape(href)}">'
                            f'{_escape(testo)}</a><br>')
                parti.append('</p>')

        if not parti or (len(parti) == 1 and titolo
                         and not articolo_html and not paragrafi
                         and not immagini):
            parti.append('<p class="caricamento">Nessun contenuto trovato.</p>')

        # COSTRUZIONE HTML CON CSS INLINE
        #
        # LE MISURE DEL TESTO SONO IN `em`
        # --------------------------------
        # La dimensione scelta dall'utente si applica al `body`, e tutto il
        # resto scala con lui.  Con le misure in pixel i titoli e le didascalie
        # resterebbero fermi mentre il corpo cambia, e l'articolo sembrerebbe
        # scritto con due mani diverse.  Le immagini non hanno misure in `em`:
        # la dimensione del testo non deve ingrandire le foto.
        dimensione_px = 16.0 * self._dimensione_testo / 100.0
        css = f"""
        html {{
          height: 100%;
          overflow-y: auto;
          overflow-x: hidden;
        }}
        body {{
          min-height: 100%;
          box-sizing: border-box;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: {dimensione_px:.2f}px;
          line-height: 1.6;
          color: {colori['testo']};
          background-color: {colori['sfondo']};
          margin: 0;
          padding: 20px;
          overflow: visible;
        }}
        h1 {{
          font-size: 1.5em;
          font-weight: 600;
          color: {colori['titolo']};
          margin-bottom: 16px;
          line-height: 1.3;
        }}
        p {{
          margin-bottom: 12px;
          text-align: justify;
        }}
        .articolo h2, .articolo h3, .articolo h4 {{
          color: {colori['titolo']};
          line-height: 1.3;
          margin-top: 22px;
          margin-bottom: 10px;
        }}
        .articolo h2 {{ font-size: 1.3125em; }}
        .articolo h3 {{ font-size: 1.125em; }}
        .articolo h4 {{ font-size: 1em; }}
        .articolo ul, .articolo ol {{
          margin: 0 0 14px 0;
          padding-left: 24px;
        }}
        .articolo li {{
          margin-bottom: 8px;
        }}
        .articolo blockquote {{
          margin: 16px 0;
          padding: 2px 0 2px 14px;
          border-left: 3px solid {colori['accento']};
          color: {colori['grigio']};
        }}
        .articolo figure {{
          margin: 18px 0;
        }}
        .articolo figure img {{
          margin: 0;
        }}
        .articolo figcaption {{
          font-size: 0.75em;
          color: {colori['grigio']};
          text-align: center;
          margin-top: 4px;
        }}
        .articolo figcaption p {{
          margin-bottom: 0;
        }}
        img {{
          max-width: 100%;
          height: auto;
          border-radius: 8px;
          margin: 12px 0;
          display: block;
        }}
        /* LA FOTO DI APERTURA
           -------------------
           La foto che il sito mette prima del titolo.  E' la stessa del
           sito, ma con i bordi dell'app: il bordo sottile e gli angoli
           arrotondati come le miniature delle card, e il fondo del tema
           dietro, cosi' che mentre l'immagine non e' ancora arrivata non
           si vede un buco bianco. */
        .principale {{
          max-width: 100%;
          height: auto;
          display: block;
          margin: 0 0 20px 0;
          border: 1px solid {colori['bordo']};
          border-radius: 8px;
          background-color: {colori['img']};
        }}
        /* L'OCHIELLO
           ----------
           La scritta che dice da dove viene l'articolo ("IN COPERTINA").
           Sul sito sta sopra il titolo, e qui sta sopra il titolo: e' un
           titolo di sezione, e un titolo di sezione sta prima del pezzo
           che descrive.  Piccolo e in grassetto, come gli occhielli del
           programma. */
        .occhiello {{
          font-size: 0.75em;
          font-weight: 600;
          color: {colori['grigio']};
          margin: 0 0 4px 0;
        }}
        .immagine-alt {{
          font-size: 0.75em;
          color: {colori['grigio']};
          text-align: center;
          margin-top: 4px;
          margin-bottom: 16px;
        }}
        .caricamento {{
          text-align: center;
          color: {colori['grigio']};
          margin-top: 40px;
        }}
        a.link-articolo {{
          color: {colori['link']};
          text-decoration: underline;
          cursor: pointer;
        }}
        a.link-articolo:hover {{
          color: {colori['link_hover']};
        }}
        ::-webkit-scrollbar {{
          width: 6px;
          background: transparent;
        }}
        ::-webkit-scrollbar-track {{
          background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
          background: {colori['accento']};
          border-radius: 1px;
          min-height: 30px;
        }}
        ::-webkit-scrollbar-button {{
          display: none;
          height: 0;
          width: 0;
        }}
        """
        js = """
        function inviaAlPonte(dati) {
          if (window.webkit && window.webkit.messageHandlers
              && window.webkit.messageHandlers.toggleMessageHandler) {
            window.webkit.messageHandlers.toggleMessageHandler.postMessage(dati);
            return true;
          }
          return false;
        }
        function apriLink(href) {
          inviaAlPonte({mode: 99, href: href});
          return false;
        }
        function apriImmagine(src) {
          inviaAlPonte({mode: 100, src: src});
          return false;
        }
        document.addEventListener('click', function (evento) {
          var bersaglio = evento.target;
          var link = bersaglio && bersaglio.closest
            ? bersaglio.closest('a[data-href]') : null;
          if (link) {
            evento.preventDefault();
            apriLink(link.getAttribute('data-href'));
            return;
          }
          // LA FOTO SI APRE A SCHERMO INTERO
          // --------------------------------
          // Come nelle pubblicazioni: la foto si guarda per bene, a tutto
          // schermo dentro l'app e sullo schermo esterno.  Una foto che si
          // preme e non fa niente e' la cosa peggiore che ci sia: si
          // preme, e sembra rotta.
          if (bersaglio && bersaglio.tagName === 'IMG') {
            evento.preventDefault();
            apriImmagine(bersaglio.getAttribute('src'));
          }
        });
        """
        html = f"<html><head><meta charset='UTF-8'><style>{css}</style><script>{js}</script></head><body>{'\n'.join(parti)}</body></html>"

        self._stato.setVisible(True)
        self._stato.setText("Preparo l'articolo...")
        self.web.setVisible(False)  # nascosto mentre si carica
        self.web.setHtml(html)
        # Si mostra in `_pagina_pronta`, quando la pagina pulita ha finito:
        # cosi' non si vede mai, nemmeno per un istante, la pagina del sito.
        # Se per qualche motivo quel segnale non arriva, si mostra comunque:
        # meglio un articolo senza un fotogramma che una scritta eterna.
        QTimer.singleShot(2500, self._assicura_articolo_visibile)

        # L'articolo si vede subito.  Se il lettore del sito ha un
        # `data-jsonurl`, si chiede l'mp3 in background e, solo se esiste, si
        # annuncia alla barra viola che le cuffie possono comparire.  Non si
        # ricarica la pagina: ricaricarla riporterebbe l'articolo in cima.
        self._audio_json_pendente = list(audio_json) if (audio_json and not audio) else []
        if audio:
            self._annuncia_audio(audio[0])
        elif not self._audio_json_pendente:
            self._annuncia_audio("")

    def _annuncia_audio(self, url: str) -> None:
        """Dice alla finestra se questo articolo ha un audio, una volta sola."""
        if self._audio_annunciato:
            return
        self._audio_annunciato = True
        self.audio_url = url or ""
        if self.audio_url:
            self.audioTrovato.emit(self.audio_url)
        else:
            self.audioAssente.emit()

    def _avvia_audio_pendente(self) -> None:
        """Avvia una sola volta la risoluzione dell'audio dell'articolo."""
        indirizzi = self._audio_json_pendente
        if not indirizzi:
            return
        self._audio_json_pendente = []
        self._cerca_audio_json(indirizzi)

    def _assicura_articolo_visibile(self) -> None:
        """Rete di sicurezza: la pagina pulita si vede anche senza segnale."""
        from PyQt6 import sip

        if sip.isdeleted(self) or not self._articolo_mostrato:
            return
        if not self.web.isVisible():
            self._stato.setVisible(False)
            self.web.setVisible(True)

    def _cerca_audio_json(self, indirizzi: list) -> None:
        """Risolve gli indirizzi ``data-jsonurl`` fuori dal thread grafico."""
        from Utility.Extensions.Ext_DispatchQueue import background

        trovato = {}

        def lavoro() -> None:
            for indirizzo in indirizzi:
                url = _mp3_da_json(indirizzo, self.url)
                if url:
                    trovato["url"] = url
                    return

        def finito() -> None:
            from PyQt6 import sip

            if sip.isdeleted(self):
                return
            self._annuncia_audio(trovato.get("url", ""))

        background(lavoro, completion=finito)

    def imposta_dimensione_testo(self, percentuale: int) -> None:
        """Cambia la dimensione del testo senza toccare le immagini.

        La misura e' una percentuale: 100 e' il corpo normale.  Il valore si
        tiene anche prima che l'articolo sia costruito, cosi' la pagina nasce
        gia' alla misura scelta; se l'articolo e' gia' a schermo si cambia il
        `body` in JavaScript, senza ricaricare e senza perdere il punto di
        lettura.
        """
        try:
            valore = int(percentuale)
        except (TypeError, ValueError):
            valore = 100
        self._dimensione_testo = max(50, min(300, valore))
        if not self._articolo_mostrato:
            return
        dimensione_px = 16.0 * self._dimensione_testo / 100.0
        self.web.run(
            "document.body.style.fontSize = '%spx';" % f"{dimensione_px:.2f}")

    def _chiedi_immagine(self, indirizzo: str) -> None:
        """Una foto e' stata premuta: si prende e si mostra a schermo intero.

        La foto si **scarica**, e non si prende dalla pagina: nella pagina
        c'e' gia' dentro il motore, ma il motore non da' i byte, e senza
        byte non c'e' immagine da mostrare.  Lo scaricamento e' in un thread
        e la pagina resta scorrevole intanto.

        Il file finisce nella cache delle copertine, quindi la seconda volta
        che la stessa foto si preme non si chiede niente al server.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        portata: dict = {"dati": None}

        def lavoro() -> None:
            from Utility import Copertine
            try:
                portata["dati"] = Copertine.scarica(indirizzo)
            except Exception:  # noqa: BLE001 - una foto che non c'e' non e' un guasto
                portata["dati"] = None

        background(lavoro,
                   completion=lambda: self._mostra_immagine(portata["dati"]))

    def _mostra_immagine(self, grezzi) -> None:
        """I byte della foto sono arrivati: si aprono a schermo intero."""
        from PyQt6 import sip
        from PyQt6.QtGui import QPixmap

        if sip.isdeleted(self) or not grezzi:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(grezzi):
            return
        self.velo.mostra(pixmap)

    def _messaggio(self, messaggio: dict) -> None:
        """Gestisce i messaggi dal JavaScript della pagina."""
        if not isinstance(messaggio, dict):
            return
        mode = messaggio.get("mode")
        if mode == 99:
            href = messaggio.get("href", "")
            if href:
                self.linkPremuto.emit(href)
        elif mode == 100:
            # Una foto e' stata premuta: si apre a schermo intero, e va
            # anche sullo schermo esterno.  Come nelle pubblicazioni.
            src = messaggio.get("src", "")
            if src:
                self._chiedi_immagine(src)