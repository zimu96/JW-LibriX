#
#  WebBrowserArticleView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""Il capitolo di una pubblicazione, dentro il motore.

Questa e' la schermata che si vede davvero quando si apre un articolo.  Il
suo compito e' mettere dentro la pagina quattro cose, in quest'ordine:

  1. il testo del capitolo, preso da ``Documents_I/<MepsDocumentId>.html``;
  2. le figure, che il capitolo non ha dentro (sono dentro il .jwpub) e
     quindi vengono iniettate come immagini in base64;
  3. ``initView()``, che mette il click sulle citazioni bibliche;
  4. ``generateSelectable()``, che divide il testo parola per parola.

PERCHE' LE FIGURE VANNO IN BASE64 E NON IN UN ``<img src>``
----------------------------------------------------------
Il capitolo scaricato da wol.jw.org e' un pezzo di HTML, non una pagina: non
ha una cartella accanto con cui risolvere i percorsi.  E le figure sono
dentro il pacchetto .jwpub, non accanto al file HTML.  Quindi non c'e' nessun
percorso che il motore possa aprire, e l'unica cosa che si puo' fare e'
mettere i byte dentro la pagina.  In Swift era ``base64EncodedString()``, e
qui e' la stessa cosa con ``base64``.

LE TRE MODALITA' DEL MESSAGGIO
-------------------------------
La pagina chiama ``postMessage`` con un campo ``mode``, e i tre numeri sono
tre cose diverse:

    0   ho colorato qualcosa         -> HighlightManager
    1   ho cliccato una figura       -> ArticleView la mostra a schermo intero
    3   ho selezionato del testo     -> il menu dei colori
    4   ho cliccato un riferimento   -> PannelloRiferimenti (versetto, cantico...)
    5   ho cliccato un video         -> il popup riproduci / scarica

Un numero che non e' nessuno di questi non e' un errore: e' una versione
vecchia della pagina, e si stampa e si va avanti.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal as Signal

from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility.JWPubManager import JWPubManager
from Utility.Structures.Generals import Document, Publication
from Utility.Stuff import leggi_utente
from Utility.UserData.HighlightManager import HighlightManager
from Utility.UserData.LocationManager import LocationManager
from WebBrowserView import WebView

class WebBrowserArticleView(QObject):
    """Il motore che mostra l'articolo di una pubblicazione o della Bibbia.

    Non e' un QWidget ma un QObject che COMANDa un ``WebView``.  Serve per
    una cosa sola: i messaggi che arrivano dalla pagina devono poter uscire
    e arrivare a ``ArticleView``, che sta in un'altra parte della finestra.
    Un segnale attraversa quella distanza; un valore di ritorno no.
    """

    #: La pagina ha colorato qualcosa: (paragrafo, inizio, fine, colore)
    highlightRequested = Signal(int, int, int, int)
    #: La pagina ha chiesto di mostrare una figura a schermo intero
    imageToShow = Signal(bytes)
    #: La pagina ha chiesto di aprire un riferimento: l'indirizzo del link
    riferimentoRichiesto = Signal(str)
    #: La pagina ha chiesto un video: (indirizzo ``webpubvid://...``, testo del link)
    videoRichiesto = Signal(str, str)
    #: C'e' una selezione di testo: posizione, testo, paragrafo, id e se tocca
    #: una sottolineatura gia' presente
    selectionMenuRequested = Signal(int, int, str, int, str, bool)
    #: E' stato premuto il numero di un versetto: posizione, numero, id, testo
    verseMenuRequested = Signal(int, int, int, str, str)
    #: La pagina e' pronta: ancore, figure e testo selezionabile sono a posto
    paginaPronta = Signal()

    def __init__(self, pub: Publication, file_path: str, document: Document | None = None,
                 parent=None, ancora: str = "") -> None:
        super().__init__(parent)
        self.pub = pub
        self.document = document
        self.file_path = file_path
        # Il punto della pagina da cui partire, cioe' l'`id` di un paragrafo.
        # Vuota perche' quasi tutte le pagine si aprono dall'inizio.
        self.ancora = ancora
        self.images: list[bytes] = []
        # Il testo del capitolo, come e' stato letto dal disco: serve a
        # contare le `<img>` e a sapere quanto sono larghe.  Vedi
        # `_immagini_della_pagina`.
        self._testo_html = ""
        # Le `<img>` del capitolo, con le loro dimensioni: si leggono una
        # volta sola e si tengono qui.
        self._immagini_html: list | None = None
        self.web = WebView()
        self.web.bridge.message.connect(self._messaggio)
        self.web.al_fine_del_caricamento(self._pagina_pronta)

    # ------------------------------------------------------------------
    # IL CARICAMENTO
    # ------------------------------------------------------------------

    def carica(self) -> None:
        """Mette dentro la pagina e comincia.

        L'HEADER NON SI TOGLIE QUI
        -------------------------
        Prima qui c'era `document.querySelector('header')?.remove()`: si
        toglieva il primo `<header>` della pagina.  Ma il comando partiva
        **prima** che la pagina fosse caricata, e quindi finiva sulla
        pagina di prima (o su quella vuota): una corsa, e il risultato
        era diverso da una volta all'altra.

        E non era quello che si voleva.  L'header della Bibbia e' il titolo
        del capitolo, e quello si toglie dopo il caricamento (vedi
        `_pagina_pronta`).  L'header di una pubblicazione e' la figura di
        apertura, e quella si vuole.

        Con il toglimento fatto a caso, la figura di apertura spariva a
        meta' delle volte, e — peggio — nella scrittura del giorno il
        primo header (che e' anche il primo giorno) veniva tolto: i giorni
        diventavano trenta e la giornata aperta non era piu' quella giusta.
        """
        if not self._vivo():
            return
        self._testo_html = leggi_utente(
            get_documents_directory() / self.file_path)
        if not self._testo_html.strip() and self._scarica_se_manca():
            return
        self._immagini_html = None
        # Le immagini sono quelle della pagina: ricaricando il capitolo
        # comincia un elenco nuovo, e quello vecchio non deve restare
        # sotto i piedi (l'indice che la pagina manda quando si clicca una
        # figura e' la posizione nella pagina, non nel capitolo).
        self.images = []
        self.web.carica(self._testo_html)

    def _scarica_se_manca(self) -> bool:
        """Il capitolo non e' sul disco (scaricamento saltato): lo si prende ora.

        Un 503 del server durante lo scaricamento lascia buchi nella
        pubblicazione; qui il buco si ripara alla prima apertura.  True se
        parte uno scaricamento (la pagina si ricarica da sola alla fine).
        """
        import re
        from Utility import Aggiornamenti, Rete
        from Utility.Extensions.Ext_DispatchQueue import background
        from Utility.FileDownloader import FileDownloader
        from Utility.WolLingua import supportata, url_capitolo, url_documento

        if getattr(self, "_gia_provato", False) or not Aggiornamenti.automatici():
            return False
        percorso = self.file_path or ""
        # Un capitolo della Bibbia e' ``nwtsty_<lingua>/<libro>/<capitolo>.html``:
        # si chiede per libro e capitolo.  Gli altri documenti sono
        # ``Documents_I/<MepsDocumentId>.html``.
        bibbia = re.search(r"^nwt\w*_([A-Za-z]+)/(\d+)/(\d+)\.html$", percorso)
        documento = re.search(r"(\d+)\.html$", percorso)
        if bibbia:
            simbolo = bibbia.group(1)
            def indirizzo() -> str:
                return url_capitolo(int(bibbia.group(2)), int(bibbia.group(3)), simbolo)
        elif documento:
            from Utility import Lingua
            simbolo = Lingua.corrente_simbolo()
            def indirizzo() -> str:
                return url_documento(int(documento.group(1)), simbolo)
        else:
            return False
        if not supportata(simbolo):
            return False
        self._gia_provato = True
        if not Rete.noto():
            self.web.carica("<html><body style='font-family:sans-serif;opacity:.6;"
                            "padding:24px'>Questo capitolo non e' scaricato e non c'e' "
                            "internet.<br>Riaprilo quando torna la connessione.</body></html>")
            return True
        self.web.carica("<html><body style='font-family:sans-serif;opacity:.6;"
                        "padding:24px'>Carico il testo…</body></html>")

        def scarica() -> None:
            url = indirizzo()
            if url:
                FileDownloader.download_article(url=url, path=self.file_path)

        def finito() -> None:
            if self._vivo():
                self.carica()

        background(scarica, completion=finito)
        return True

    def _va_all_ancora(self) -> None:
        """Porta la pagina al paragrafo dell'ancora, se c'e'.

        TRE FORME, PERCHE' CI SONO TRE MODI DI DIRE DOVE
        -------------------------------------------------
        - ``p15`` e' l'``id`` che c'e' gia' nel file, usato da «apri il
          giorno»: si cerca per id, come prima;
        - ``pid:15`` e' il numero del paragrafo di una pubblicazione, che non
          sempre ha un id uguale al ``data-pid``;
        - ``v:24:51:1`` e' libro, capitolo e versetto della Bibbia, dove il
          versetto e' diviso in piu' ``span`` con lo stesso prefisso.

        Il selettore si costruisce con ``json.dumps`` invece di incollare il
        testo fra virgolette: il valore viene dal database, e un carattere
        strano non deve poter rompere la pagina.
        """
        if not self.ancora:
            return

        import json

        ancora = str(self.ancora)
        if ancora.startswith("pid:"):
            numero = "".join(ch for ch in ancora[4:] if ch.isdigit()) or "0"
            # Prima il paragrafo, poi un contenitore qualsiasi con lo stesso
            # `data-pid`: nei file di alcune pubblicazioni il numero sta sia
            # sul `<div>` di sezione sia sul `<p>` del paragrafo, e il primo
            # porterebbe all'inizio della sezione invece che al punto.
            selettore_paragrafo = json.dumps(f'p[data-pid="{numero}"]')
            selettore_qualsiasi = json.dumps(f'[data-pid="{numero}"]')
            chiamata = ("(document.querySelector({}) || "
                        "document.querySelector({}))").format(
                            selettore_paragrafo, selettore_qualsiasi)
        elif ancora.startswith("v:"):
            pezzi = ancora[2:].split(":")
            if len(pezzi) != 3 or not all(p.isdigit() for p in pezzi):
                return
            libro, capitolo, versetto = pezzi
            selettore = 'span[id^="v{}-{}-{}-"]'.format(libro, capitolo, versetto)
            chiamata = "document.querySelector({})".format(json.dumps(selettore))
        else:
            chiamata = "document.getElementById({})".format(json.dumps(ancora))

        if not self._vivo():
            return
        self.web.run(chiamata + "?.scrollIntoView({block: 'center'});")

    def _pagina_pronta(self, _ok: bool = True) -> None:
        """Dopo il caricamento: figure, stile, parole selezionabili.

        UNA PAGINA CHE NON E' LA NOSTRA NON SI TOCCA
        --------------------------------------------
        `loadFinished` arriva anche per l'`about:blank` iniziale e per
        qualunque pagina in cui il motore navighi (un link esterno, per
        esempio).  Quelle pagine non hanno `script.js`, quindi `initView`,
        `generateSelectable` e `cleanBodyHighlight` non esistono: chiamarle
        riempiva il log di

            Uncaught ReferenceError: initView is not defined

        che sembra un difetto del programma e invece e' solo una pagina
        estranea.  Le nostre pagine sono sempre caricate con
        `setHtml(..., about:blank)` e quindi hanno questo indirizzo; tutto
        il resto si lascia stare.
        """
        if not self._vivo():
            return
        indirizzo = self.web.url().toString()
        if indirizzo not in ("", "about:blank"):
            return

        # L'ancora va messa **prima** di tutto il resto, e perche' il resto
        # ricostruisce il corpo della pagina: `generateSelectable()` rifa
        # gli elementi del testo, quindi uno scroll fatto prima si perde e la
        # pagina si riapre in alto.  Scrollare per primo e' anche quello che
        # si vede: si parte gia' sul giorno giusto e non si nota il salto.
        self._va_all_ancora()
        if self.pub.isBible:
            self.web.togli_header()
        else:
            self._metti_figure()

        # L'ordine conta: initView mette i click sulle citazioni, e solo dopo
        # si divide il testo in pezzi, perche' generateSelectable ricostruisce
        # il corpo della pagina e i click messi prima andrebbero persi.
        #
        # Il `typeof` non e' pignoleria: se lo script non c'e' — una pagina
        # caricata prima che il file fosse disponibile, o un motore che ha
        # rifiutato il contenuto — ogni chiamata sarebbe un errore in
        # console.  Chiedere prima se la funzione esiste costa niente e
        # lascia il log leggibile.
        def dopo_generate_selectable(_risultato=None) -> None:
            # Il capitolo puo' essere chiuso mentre la pagina si sta
            # caricando: e' quello che succede quando si torna indietro.
            # Il richiamo del JavaScript arriva lo stesso, e allora il
            # motore non c'e' piu': senza questo controllo il programma
            # stampa «wrapped C/C++ object of type WebView has been
            # deleted» e lascia credere che sia successo qualcosa di
            # grave, mentre e' solo una pagina arrivata tardi.
            if not self._vivo():
                return
            # Le sottolineature si ridisegnano solo dopo che `generateSelectable`
            # ha creato gli elementi `<selectable>`: prima non c'e' niente su
            # cui appoggiarle, e il passaggio silenzioso non lascerebbe traccia.
            document_id = self.document.documentId if self.document else 0
            LocationManager.add_location(pub=self.pub, document_id=document_id)
            self.ripristina_evidenziazioni()
            self.paginaPronta.emit()

        def dopo_init_view(_risultato=None) -> None:
            if not self._vivo():
                return
            self.web.run(
                "if (typeof generateSelectable === 'function') { generateSelectable(); }",
                dopo_generate_selectable)

        self.web.run(
            "if (typeof initView === 'function') {{ initView({}); }}".format(
                "true" if self.pub.isBible else "false"),
            dopo_init_view)

    def _vivo(self) -> bool:
        """Questa schermata esiste ancora?

        Il capitolo puo' essere chiuso mentre la pagina si sta caricando,
        e il richiamo del JavaScript arriva lo stesso.  Se il motore non
        c'e' piu', continuare a chiamarlo fa stampare un errore che sembra
        un guasto e non e' niente: e' una pagina arrivata tardi.
        """
        try:
            self.web  # noqa: B018 - se il C++ e' sparito, qui solleva
        except RuntimeError:
            return False
        return True

    def _metti_figure(self) -> None:
        """Mette le figure dentro la pagina, una alla volta.

        PERCHE' NON BASTA CONTARE
        -------------------------
        Il capitolo e' un pezzo di HTML che viene da wol.jw.org, e le sue
        ``<img>`` non hanno dentro se stesse il file: hanno un indirizzo
        (``/it/wol/mp/r6/lp-i/wcg/2025/63``) che il motore non puo' aprire.
        Le figure stanno dentro il pacchetto, e vanno abbinate a mano.

        Abbinare per ordine **non funziona**, e il motivo e' misurato sul
        capitolo «Non si guardo indietro» del libro *Cammina coraggiosamente
        con Dio*:

            la pagina      9 figure: la figura di apertura, le due miniature
                          della «edizione stampata», e sei foto del capitolo
            il pacchetto  11 righe, di cui 3 sono la stessa miniatura due
                          volte e una e' la copertina quadrata

        Con il conto le figure finivano sbagliate: la prima della pagina
        prendeva la miniatura, e le foto del capitolo prendevano un pezzo
        avanti.  E per quattro immagini su nove il risultato era un
        quadratino vuoto: i byte di una figura SVG (l'«edizione stampata»)
        venivano scritti dentro un ``data:image/jpeg``, e il motore non
        riusciva a disegnarli.

        COME SI ABBINA, ALLORA
        ----------------------
        Guardando le **dimensioni**: la pagina le scrive nell'``<img>``
        (``width="1200" height="674"``) e il pacchetto le sa nella tabella
        `Multimedia`.  Una figura che ha le stesse dimensioni e' quella
        giusta; le figure senza dimensioni (le miniature vettoriali) si
        abbinano a quelle che restano, nell'ordine del pacchetto.

        E IL TIPO GIUSTO
        ----------------
        Ogni figura viene scritta con il **suo** tipo: ``image/svg+xml``
        per i vettori, ``image/jpeg`` per le fotografie.  Con il tipo
        sbagliato il motore non la disegna, e quello che si vede e' un
        riquadro vuoto con il testo dell'immagine.
        """
        document_number = self.document.documentId if self.document else 0
        media = JWPubManager.get_document_media(pub=self.pub,
                                                document_number=document_number)
        if not media:
            return

        abbinate = self._abbina_le_figure(media)
        if not abbinate:
            return

        import base64

        for indice, figura in enumerate(abbinate):
            if figura is None:
                # Un posto vuoto, ma un posto: l'indice che la pagina manda
                # quando si clicca una figura e' la posizione nella pagina,
                # e la lista deve avere la stessa lunghezza.
                self.images.append(None)
                continue
            percorso = figura["percorso"]
            try:
                grezzi = percorso.read_bytes()
            except OSError:
                self.images.append(None)
                continue
            # L'elenco delle immagini e' quello della PAGINA: e' da li' che
            # viene l'indice che la pagina manda quando si clicca una figura.
            self.images.append(grezzi)
            codificato = base64.b64encode(grezzi).decode("ascii")
            mime = figura["mime"] or "image/jpeg"
            # IL BLOCO BIANCO DIETRO LE FIGURE VETTORIALI
            # --------------------------------------------
            # La «edizione stampata» e' un disegno (SVG) **senza fondo**:
            # il testo dentro e' nero, e su una pagina scura nero su nero
            # non si legge.  Il testo dentro un'immagine non si puo'
            # cambiare, ma il fondo intorno si': mettendo un blocco
            # bianco dietro la figura, della sua stessa misura, il testo
            # nero torna su un foglio bianco, come sulla pagina stampata.
            #
            # Le fotografie non hanno bisogno di questo: hanno il loro
            # fondo, e un rettangolo bianco sotto si vedrebbe.
            fondo = ""
            if mime == "image/svg+xml":
                fondo = "img.style.background = '#ffffff';"
            self.web.run(
                """
                (function () {{
                  var img = document.querySelectorAll('img')[{i}];
                  if (!img) {{ return; }}
                  img.src = 'data:{mime};base64,{dati}';
                  {fondo}
                  img.classList.remove("north_center");
                  img.setAttribute("onClick", "javascript: showImg({i});");
                  img.removeAttribute('data-img-small-src');
                }})();
                """.format(i=indice, mime=mime, dati=codificato, fondo=fondo)
            )

    def _abbina_le_figure(self, media: list[dict]) -> list:
        """Quale figura del pacchetto sta in ogni ``<img>`` del capitolo.

        La lista che esce ha un posto per ogni ``<img>`` della pagina, e
        ogni posto dice quale figura ci va (o `None`, se non c'e' niente).

        LA REGOLA
        ---------
        Prima si cerca la figura con le **stesse dimensioni** di quelle
        scritte nell'``<img>``: e' la prova che e' quella giusta.  Se
        l'``<img>`` non ha dimensioni (le miniature della «edizione
        stampata» sono vettoriali) si prende la prima figura rimasta che
        non le ha, e se non c'e' neanche quella, la prima rimasta.

        L'ordine e' quello del pacchetto, che e' l'ordine in cui le figure
        compaiono nel capitolo.
        """
        immagini = self._immagini_della_pagina()
        if not immagini:
            return []

        abbinate: list = []
        usati: set[int] = set()

        for larghezza, altezza in immagini:
            scelta = None
            if larghezza and altezza:
                for indice, figura in enumerate(media):
                    if indice in usati:
                        continue
                    if (figura["larghezza"] == larghezza
                            and figura["altezza"] == altezza):
                        scelta = indice
                        break
            if scelta is None:
                for indice, figura in enumerate(media):
                    if indice in usati:
                        continue
                    if not figura["larghezza"] or not figura["altezza"]:
                        scelta = indice
                        break
            if scelta is None:
                for indice, _figura in enumerate(media):
                    if indice not in usati:
                        scelta = indice
                        break
            if scelta is None:
                abbinate.append(None)
                continue
            usati.add(scelta)
            abbinate.append(media[scelta])
        return abbinate

    def _immagini_della_pagina(self) -> list:
        """Le ``<img>`` del capitolo, con le loro dimensioni.

        Si legge il **codice** del capitolo, non la pagina del motore: il
        capitolo e' il testo che e' stato caricato, e le sue ``<img>``
        sono quelle che il pacchetto deve riempiere.  La pagina del motore,
        dopo `generateSelectable`, ha dentro anche le ``<selectable>``: e'
        un'altra cosa, e contare quelle darebbe un numero sbagliato.
        """
        if self._immagini_html is not None:
            return self._immagini_html

        import re

        larghezze: list = []
        for tag in re.findall(r"<img[^>]*>", self._testo_html or "", re.IGNORECASE):
            larghezza = altezza = None
            for attributo, nome in (("width", "larghezza"), ("height", "altezza")):
                trovato = re.search(rf'{attributo}\s*=\s*"(\d+)"', tag, re.IGNORECASE)
                if trovato:
                    if nome == "larghezza":
                        larghezza = int(trovato.group(1))
                    else:
                        altezza = int(trovato.group(1))
            larghezze.append((larghezza, altezza))
        self._immagini_html = larghezze
        return larghezze

    # ------------------------------------------------------------------
    # LE SOTTOLINEATURE
    # ------------------------------------------------------------------

    def ripristina_evidenziazioni(self) -> None:
        """Ridisegna le sottolineature che gia' ci sono.

        Prima si toglie tutto quello che c'era (``cleanBodyHighlight``) e poi
        si rimette: senza il primo passo, ricaricando il capitolo due volte,
        ogni sottolineatura verrebbe disegnata sopra se stessa.
        """
        if not self._vivo():
            return
        document_id = self.document.documentId if self.document else 0

        def ridisegna(_risultato=None) -> None:
            if not self._vivo():
                return
            for evidenziazione in HighlightManager.get_highlight(
                    pub=self.pub, document_id=document_id):
                blocco = evidenziazione.blockRange
                if blocco.identifier == -1 or blocco.startToken == -1 or blocco.endToken == -1:
                    continue
                self.web.run(
                    "if (typeof restoreHighlight === 'function') {{"
                    " restoreHighlight({}, {}, {}, {}, {});"
                    " }}".format(
                        blocco.identifier, blocco.startToken, blocco.endToken,
                        evidenziazione.userMark.color,
                        "true" if self.pub.isBible else "false")
                )
            # Dopo aver rimesso le sottolineature si torna all'ancora: la
            # pagina e' stata ricostruita e le immagini possono aver cambiato
            # l'altezza, quindi lo scroll fatto all'apertura non basta piu'.
            self._va_all_ancora()

        self.web.run(
            "if (typeof cleanBodyHighlight === 'function'"
            " && typeof makeSelectable === 'function') {"
            " cleanBodyHighlight(); makeSelectable(); }",
            ridisegna)

    def evidenzia(self, colore: int) -> None:
        """Colorare la selezione, o toglierla con ``-1``."""
        if colore == 0:
            return
        self.web.run("addHighlight({}, {});".format(
            colore, "true" if self.pub.isBible else "false"))

    # ------------------------------------------------------------------
    # I MESSAGGI DALLA PAGINA
    # ------------------------------------------------------------------

    def _messaggio(self, messaggio: dict) -> None:
        modo = messaggio.get("mode")

        if modo == 0:
            print("addHighlight({}, {}, {});".format(
                messaggio["paragraph"], messaggio["startIndex"], messaggio["endIndex"]))
            self.highlightRequested.emit(messaggio["paragraph"],
                                         messaggio["startIndex"],
                                         messaggio["endIndex"],
                                         messaggio["color"])

        elif modo == 1:
            indice = messaggio.get("imgIndex", -1)
            print(f"Apro immagine {indice}...")
            if 0 <= indice < len(self.images) and self.images[indice]:
                self.imageToShow.emit(self.images[indice])

        elif modo == 4:
            self.riferimentoRichiesto.emit(str(messaggio.get("href", "")))

        elif modo == 5:
            self.videoRichiesto.emit(str(messaggio.get("video", "")),
                                     str(messaggio.get("testo", "")))

        elif modo == 6:
            self.verseMenuRequested.emit(
                int(messaggio.get("x", 0)), int(messaggio.get("y", 0)),
                int(messaggio.get("verso", 0) or 0),
                str(messaggio.get("ancora", "")), str(messaggio.get("testo", "")))

        elif modo == 3:
            # L'utente ha selezionato del testo e ha mollato il mouse: e' il
            # momento in cui deve comparire il menu dei colori.  Il segnale
            # porta la posizione e anche il testo scelto: il menu lo usa per
            # il segnalibro, e cosi' non serve rileggere la selezione dopo che
            # il menu ha preso il fuoco.
            x = int(messaggio.get("x", 0))
            y = int(messaggio.get("y", 0))
            testo = str(messaggio.get("testo", ""))
            paragrafo = int(messaggio.get("paragrafo", 0) or 0)
            ancora = str(messaggio.get("ancora", ""))
            evidenziata = bool(messaggio.get("evidenziata", False))
            self.selectionMenuRequested.emit(x, y, testo, paragrafo, ancora,
                                             evidenziata)

        else:
            print("Come ci sei arrivato qui?")
