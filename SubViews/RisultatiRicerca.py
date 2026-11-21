"""La pagina dei risultati di ricerca, come quella di jw.org ma nello stile dell'app.

Si apre premendo Invio nella barra di ricerca della Biblioteca Digitale.
Due sezioni separate:
  * «Scaricati (offline)»: quello che si trova nel testo gia' sul disco;
  * «Online (jw.org)»: gli stessi risultati del sito, con le schede (Tutto,
    Pubblicazioni, Video, Audio, Bibbia), l'ordine (rilevanza, piu' recente,
    meno recente) e le pagine numerate.
Senza internet resta solo la parte offline.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget)

from SubViews.RisultatiTesto import RisultatiTesto, _Riga
from Utility import RicercaWeb, Rete
from Utility.Extensions.Ext_DispatchQueue import background

MAX_OFFLINE = 20


class RisultatiRicerca(QWidget):
    #: Impostate dalla finestra: dicono se un risultato online e' gia' scaricato / fra i Preferiti.
    verifica = None
    verifica_preferito = None
    pub_da_contesto = None   # (contesto) -> Publication del catalogo o None
    nel_catalogo = None      # (risultato) -> bool: e' una pubblicazione del catalogo JWPUB?

    #: Un risultato scelto (dizionario del risultato, locale o online)
    apri = Signal(dict)
    #: Tre puntini di un risultato online: ("apri"|"scarica", risultato)
    azione = Signal(str, dict)
    messaggio = Signal(str)

    def __init__(self, domanda: str = "", parent=None) -> None:
        super().__init__(parent)
        self._filtro = "all"
        self._ordine = "rel"
        self._offset = 0
        self._numero = 0                    # per scartare risposte vecchie
        colonna = QVBoxLayout(self)
        colonna.setContentsMargins(16, 12, 16, 8)
        colonna.setSpacing(8)

        riga = QHBoxLayout()
        self.campo = QLineEdit(self)
        self.campo.setObjectName("campoCerca")
        self.campo.setPlaceholderText("Cerca su jw.org e nel testo scaricato")
        self.campo.setClearButtonEnabled(True)
        self.campo.setText(domanda)
        self.campo.returnPressed.connect(self._invio)
        # I SUGGERIMENTI: scrivendo, senza Invio, si apre una tendina sotto la barra
        # (testo scaricato + sito).  Il testo scritto resta nel campo.
        self._popup = RisultatiTesto(self)
        self._popup.scelto.connect(self._suggerimento_scelto)
        self._popup.azioneWeb.connect(lambda a, r: (self._popup.hide(), self.azione.emit(a, r)))
        self._attesa = QTimer(self)
        self._attesa.setSingleShot(True)
        self._attesa.setInterval(300)
        self._attesa.timeout.connect(self._suggerisci)
        self._num_sugg = 0
        self.campo.textChanged.connect(self._testo_cambiato)
        self.campo.installEventFilter(self)
        cerca = QPushButton("Cerca", self)
        cerca.clicked.connect(self._nuova_ricerca)
        riga.addWidget(self.campo, 1)
        riga.addWidget(cerca)
        colonna.addLayout(riga)

        # Le due sezioni e i filtri compaiono solo dopo una ricerca.
        self._filtri = QWidget(self)
        cf = QVBoxLayout(self._filtri)
        cf.setContentsMargins(0, 0, 0, 0)
        cf.setSpacing(8)
        self._filtri.hide()
        colonna.addWidget(self._filtri)
        # Le due sezioni, separate: online (sito) e offline (scaricato)
        riga0 = QHBoxLayout()
        riga0.setSpacing(6)
        self._sez_bottoni = {}
        for chiave, etichetta in (("online", "Online (jw.org)"),
                                  ("offline", "Scaricati (offline)")):
            b = QPushButton(etichetta, self)
            b.setCheckable(True)
            b.setChecked(chiave == "online")
            b.clicked.connect(lambda _=False, k=chiave: self._scegli_sezione(k))
            self._sez_bottoni[chiave] = b
            riga0.addWidget(b)
        riga0.addStretch(1)
        cf.addLayout(riga0)
        self._sezione = "online"
        self._cont: dict = {}
        self._righe_web: list = []
        self._giro = QTimer(self)
        self._giro.setInterval(2500)
        self._giro.timeout.connect(self.aggiorna_stati)
        self._giro.start()

        # Le schede del sito e l'ordine
        riga2 = QHBoxLayout()
        riga2.setSpacing(6)
        self._bottoni = {}
        for chiave, etichetta in RicercaWeb.FILTRI:
            b = QPushButton(etichetta, self)
            b.setCheckable(True)
            b.setChecked(chiave == "all")
            b.clicked.connect(lambda _=False, k=chiave: self._scegli_filtro(k))
            self._bottoni[chiave] = b
            riga2.addWidget(b)
        riga2.addStretch(1)
        riga2.addWidget(QLabel("Ordina:", self))
        self.ordine = QComboBox(self)
        for chiave, etichetta in RicercaWeb.ORDINI:
            self.ordine.addItem(etichetta, chiave)
        self.ordine.currentIndexChanged.connect(self._ordine_cambiato)
        riga2.addWidget(self.ordine)
        cf.addLayout(riga2)

        self._scorri = QScrollArea(self)
        self._scorri.setWidgetResizable(True)
        self._scorri.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scorri.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        colonna.addWidget(self._scorri, 1)
        self._contenuto = None
        if domanda:
            self._nuova_ricerca()

    # ---- suggerimenti ------------------------------------------------

    def _invio(self) -> None:
        self._attesa.stop()
        self._num_sugg += 1
        self._popup.hide()
        self._nuova_ricerca()

    def _testo_cambiato(self, testo: str) -> None:
        self._num_sugg += 1
        if len(testo.strip()) < 2:
            self._attesa.stop()
            self._popup.hide()
        else:
            self._attesa.start()

    def _suggerisci(self) -> None:
        domanda = self.campo.text().strip()
        if len(domanda) < 2 or not self.campo.hasFocus():
            return
        self._num_sugg += 1
        numero = self._num_sugg
        locali: list = []
        web: list = []
        stato = {"mancano": 2}

        def lavoro_locale() -> None:
            from Utility import RicercaTesto
            locali.extend(RicercaTesto.cerca(domanda, 3))

        def lavoro_web() -> None:
            if Rete.noto():
                from Utility import Lingua
                web.extend(RicercaWeb.cerca(domanda, Lingua.corrente_simbolo(), limite=5))

        def fatto() -> None:
            stato["mancano"] -= 1
            if stato["mancano"] or numero != self._num_sugg or not self.campo.hasFocus():
                return
            if not locali and not web:
                self._popup.hide()
                return
            gia = {int(r.get("meps") or 0) for r in locali}
            nuovi = [w for w in web if not (w.get("docid") and w["docid"] in gia)]
            punto = self.campo.mapTo(self, QPoint(0, self.campo.height() + 2))
            self._popup.mostra(locali, punto, self.campo.width(), nuovi, "")
            self._popup.raise_()

        background(lavoro_locale, completion=fatto)
        background(lavoro_web, completion=fatto)

    def _suggerimento_scelto(self, r: dict) -> None:
        self._popup.hide()
        self.apri.emit(r)

    def eventFilter(self, oggetto, evento) -> bool:
        if oggetto is self.campo:
            if evento.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(200, lambda: None if self.campo.hasFocus()
                                  else self._popup.hide())
            elif (evento.type() == QEvent.Type.KeyPress
                  and evento.key() == Qt.Key.Key_Escape):
                self._popup.hide()
        return super().eventFilter(oggetto, evento)

    # ------------------------------------------------------------------

    def _scegli_filtro(self, chiave: str) -> None:
        self._filtro = chiave
        for k, b in self._bottoni.items():
            b.setChecked(k == chiave)
        self._offset = 0
        self._cerca()

    def _ordine_cambiato(self) -> None:
        self._ordine = self.ordine.currentData() or "rel"
        self._offset = 0
        self._cerca()

    def _scegli_sezione(self, chiave: str) -> None:
        self._sezione = chiave
        for k, b in self._sez_bottoni.items():
            b.setChecked(k == chiave)
        if chiave in self._cont:
            self._metti(self._cont[chiave])

    def _nuova_ricerca(self) -> None:
        self._offset = 0
        self._cerca()

    def _vai_pagina(self, offset: int) -> None:
        self._offset = offset
        self._cerca()
        self._scorri.verticalScrollBar().setValue(0)

    def _cerca(self) -> None:
        domanda = self.campo.text().strip()
        self._numero += 1
        numero = self._numero
        if len(domanda) < 2:
            self._filtri.hide()
            self._mostra([self._nota("Scrivi almeno due lettere.")] if domanda else [])
            return
        self._filtri.show()
        self._mostra([self._nota("Cerco…")])
        offline: list = []
        online: dict = {}
        stato = {"mancano": 2}

        def lavoro_offline() -> None:
            from Utility import RicercaTesto
            tutti = RicercaTesto.cerca(domanda, 60)
            if self._filtro == "bible":
                tutti = [r for r in tutti if r.get("tipo") == "b"]
            elif self._filtro in ("videos", "audio"):
                tutti = []
            elif self._filtro == "publications":
                tutti = [r for r in tutti if r.get("tipo") != "b"]
            offline.extend(tutti[:MAX_OFFLINE])

        def lavoro_online() -> None:
            if not Rete.noto():
                online["senza_rete"] = True
                return
            from Utility import Lingua
            online.update(RicercaWeb.pagina(domanda, Lingua.corrente_simbolo(),
                                            self._filtro, self._ordine, self._offset))

        def fatto() -> None:
            stato["mancano"] -= 1
            if stato["mancano"] == 0 and numero == self._numero:
                self._disegna(domanda, offline, online)

        background(lavoro_offline, completion=fatto)
        background(lavoro_online, completion=fatto)

    # ------------------------------------------------------------------

    def _nota(self, testo: str) -> QLabel:
        l = QLabel(testo, self)
        l.setObjectName("nota")
        l.setWordWrap(True)
        l.setContentsMargins(4, 6, 4, 6)
        return l

    def _titolo(self, testo: str) -> QLabel:
        l = QLabel(testo, self)
        l.setStyleSheet("font-weight: 600; font-size: 15px;")
        l.setContentsMargins(4, 10, 4, 2)
        return l

    def _contenitore(self, widget: list) -> QWidget:
        contenuto = QWidget()
        c = QVBoxLayout(contenuto)
        c.setContentsMargins(0, 0, 8, 8)
        c.setSpacing(2)
        for w in widget:
            c.addWidget(w)
        c.addStretch(1)
        return contenuto

    def _metti(self, contenuto: QWidget) -> None:
        """Mette un contenitore nello scorrimento SENZA distruggere quello che c'era
        se e' una delle due sezioni (altrimenti tornando indietro resterebbe vuoto)."""
        vecchio = self._scorri.takeWidget()
        if vecchio is not None and vecchio not in self._cont.values():
            vecchio.deleteLater()
        self._scorri.setWidget(contenuto)
        contenuto.show()

    def _mostra(self, widget: list) -> None:
        """Un messaggio di passaggio (cerco…, errori): le due sezioni si scartano."""
        for v in self._cont.values():
            v.deleteLater()
        self._cont = {}
        self._metti(self._contenitore(widget))

    def _riga(self, r: dict, con_menu: bool = False) -> _Riga:
        titolo = r["titolo"]
        if r.get("contesto"):
            titolo += f"  ·  {r['contesto']}"
        if r.get("durata"):
            titolo += f"  ·  {r['durata']}"
        originale = r
        sotto = r.get("sottotipo") or ""
        # Un articolo di una pubblicazione scaricabile (es. Perspicacia, Bibbia di studio):
        # scarica / Preferiti riguardano la PUBBLICAZIONE, «Apri subito» l'articolo.
        if sotto in ("article", "index") and r.get("contesto") and self.pub_da_contesto:
            try:
                pub = self.pub_da_contesto(r["contesto"])
            except Exception:  # noqa: BLE001
                pub = None
            if pub is not None:
                r = {**r, "sottotipo": "publication", "sigla": pub.keySymbol,
                     "edizione": "", "lank": f"pub-{pub.keySymbol}",
                     "titolo": getattr(pub, "title", "") or r["titolo"]}
                sotto = "publication"
        scaricabile = r.get("tipo") == "web" and (
            sotto in ("video", "audio")
            or (sotto in ("publication", "periodical") and bool(r.get("sigla"))))
        con_menu = con_menu or scaricabile
        try:
            pref = bool(scaricabile and self.verifica_preferito and self.verifica_preferito(r))
        except Exception:  # noqa: BLE001
            pref = False
        lank = r.get("lank") or ""
        # I versetti della Bibbia non hanno immagine sul sito: si mette la copertina della Bibbia.
        sigla_bibbia = lank.split("_", 1)[1] if lank.startswith("bv-") and "_" in lank else ""
        riga = _Riga(titolo, r.get("anteprima", ""), self, con_menu=con_menu,
                     miniatura=bool(r.get("immagine")), scaricabile=scaricabile,
                     preferito=pref)
        if scaricabile:
            self._righe_web.append((riga, r))
            self._stato_riga(riga, r)
            self._nascondi_se_non_scaricabile(riga, r)
        if sigla_bibbia:
            r = {**r, "sigla": sigla_bibbia, "immagine": ""}
        if r.get("immagine"):
            self._carica_immagine(riga, r["immagine"])
        elif r.get("sigla") and (r.get("tipo") != "web" or sigla_bibbia):
            # Risultato scaricato: la copertina della pubblicazione (prima dal disco).
            riga.miniatura = QLabel(riga)
            riga.miniatura.setFixedSize(54, 72)
            riga.miniatura.setStyleSheet(
                "background: rgba(128,128,128,0.15); border-radius: 4px;")
            riga.layout().insertWidget(0, riga.miniatura, 0, Qt.AlignmentFlag.AlignTop)
            self._carica_copertina(riga, r["sigla"])
        riga.premuta.connect(lambda o=originale: self.apri.emit(o))
        def _azione(a, r=r, o=originale, riga=riga):
            if a == "scarica" and not (r.get("sottotipo") in ("video", "audio")):
                riga.avvia_barra()
            self.azione.emit(a, o if a == "apri" else r)
        riga.azione.connect(_azione)
        return riga

    def _nascondi_se_non_scaricabile(self, riga, r: dict) -> None:
        """Una pubblicazione fuori catalogo senza nessun file sul sito non si puo' scaricare:
        il tasto non si mette."""
        if r.get("sottotipo") not in ("publication", "periodical") or not r.get("sigla"):
            return
        try:
            if self.nel_catalogo is None or self.nel_catalogo(r):
                return
        except Exception:  # noqa: BLE001
            return
        from Utility import FormatiSito, Lingua
        sigla, lingua = r["sigla"], Lingua.corrente_simbolo()
        trovati: list = []

        def lavoro() -> None:
            try:
                trovati.append(bool(FormatiSito.formati(sigla, lingua)))
            except Exception:  # noqa: BLE001
                trovati.append(True)        # nel dubbio il tasto resta

        def fatto() -> None:
            try:
                if trovati and not trovati[0]:
                    riga.scarica.hide()
            except RuntimeError:
                pass

        background(lavoro, completion=fatto)

    def _stato_riga(self, riga, r: dict) -> None:
        try:
            riga.imposta_stato(bool(self.verifica and self.verifica(r)))
        except Exception:  # noqa: BLE001
            pass

    def scarico_avviato(self, titolo: str) -> None:
        """Un video/audio ha cominciato a scaricarsi (dopo la scelta della risoluzione)."""
        for riga, r in self._righe_web:
            try:
                if (r.get("titolo") or "") == titolo:
                    riga.avvia_barra()
            except RuntimeError:
                pass

    def scarico_fallito(self, r: dict) -> None:
        """Lo scaricamento non e' partito: la barra si toglie e il tasto torna libero."""
        for riga, rr in self._righe_web:
            try:
                if rr is r or (rr.get("lank") == r.get("lank") and rr.get("sigla") == r.get("sigla")
                               and rr.get("edizione") == r.get("edizione")):
                    riga.ferma_barra()
                    riga.imposta_stato(False)
            except RuntimeError:
                pass

    def aggiorna_stati(self) -> None:
        """Dopo uno scaricamento la nuvoletta diventa una spunta (offline e online combaciano)."""
        if not self.isVisible():
            return
        vive = []
        for riga, r in self._righe_web:
            try:
                riga.isVisible()
            except RuntimeError:
                continue
            self._stato_riga(riga, r)
            vive.append((riga, r))
        self._righe_web = vive

    _cache_immagini: dict = {}

    def _carica_immagine(self, riga, url: str) -> None:
        import urllib.request
        from PyQt6.QtGui import QPixmap
        dati = self._cache_immagini
        if url in dati:
            if dati[url]:
                riga.imposta_immagine(dati[url])
            return
        grezzo: list = []

        def lavoro() -> None:
            try:
                with urllib.request.urlopen(urllib.request.Request(
                        url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10) as r:
                    grezzo.append(r.read())
            except Exception:  # noqa: BLE001
                pass

        def fatto() -> None:
            pm = QPixmap()
            if grezzo:
                pm.loadFromData(grezzo[0])
            dati[url] = pm
            try:
                riga.imposta_immagine(pm)
            except RuntimeError:     # la riga e' stata sostituita nel frattempo
                pass

        background(lavoro, completion=fatto)

    _cache_copertine: dict = {}

    def _carica_copertina(self, riga, sigla: str) -> None:
        from types import SimpleNamespace
        from PyQt6.QtGui import QPixmap
        from Utility import Copertine, Lingua
        dati = self._cache_copertine
        if sigla in dati:
            if dati[sigla]:
                riga.imposta_immagine(dati[sigla])
            return
        grezzo: list = []

        def lavoro() -> None:
            try:
                pub = SimpleNamespace(keySymbol=sigla, symbol=sigla, issueTagNumber=0,
                                      mepsLanguageId=Lingua.corrente_id())
                d = Copertine.dati_copertina(pub, "lg")
                if d:
                    grezzo.append(d)
            except Exception:  # noqa: BLE001
                pass

        def fatto() -> None:
            pm = QPixmap()
            if grezzo:
                pm.loadFromData(grezzo[0])
            dati[sigla] = pm
            try:
                riga.imposta_immagine(pm)
            except RuntimeError:
                pass

        background(lavoro, completion=fatto)

    def _disegna(self, domanda: str, offline: list, online: dict) -> None:
        self._righe_web = []
        # --- OFFLINE ---------------------------------------------------
        off: list = []
        if offline:
            off.extend(self._riga(r) for r in offline)
        else:
            off.append(self._nota(f"Niente per «{domanda}» nel testo scaricato."))
        # --- ONLINE ----------------------------------------------------
        on: list = []
        if online.get("senza_rete"):
            on.append(self._nota("Senza internet: qui compaiono solo i risultati scaricati."))
        elif online.get("errore"):
            on.append(self._nota("Il sito non risponde. Riprova tra poco."))
        elif not online.get("sezioni"):
            on.append(self._nota(f"Nessun risultato su jw.org per «{domanda}»."))
        else:
            if online.get("etichetta"):
                on.append(self._nota(online["etichetta"]))
            for sezione in online["sezioni"]:
                if sezione["titolo"]:
                    n = QLabel(sezione["titolo"], self)
                    n.setObjectName("nota")
                    n.setContentsMargins(4, 8, 4, 0)
                    on.append(n)
                for r in sezione["voci"]:
                    on.append(self._riga(r, con_menu=bool(r.get("sigla")
                                                          and not r.get("docid"))))
            on.append(self._barra_pagine(online.get("pagine") or []))
        for v in self._cont.values():
            v.deleteLater()
        self._cont = {"online": self._contenitore(on), "offline": self._contenitore(off)}
        self._sez_bottoni["offline"].setText(
            f"Scaricati (offline) — {len(offline)}" if offline else "Scaricati (offline)")
        # Senza internet si parte dall'offline; altrimenti dal sito.
        if online.get("senza_rete") and self._sezione == "online":
            self._sezione = "offline"
            for k, b in self._sez_bottoni.items():
                b.setChecked(k == "offline")
        self._metti(self._cont[self._sezione])

    def _barra_pagine(self, pagine: list) -> QWidget:
        """«1 2 3 4 5 … 834 >» come sul sito."""
        barra = QWidget(self)
        r = QHBoxLayout(barra)
        r.setContentsMargins(0, 10, 0, 10)
        r.setSpacing(4)
        r.addStretch(1)
        for p in pagine:
            if p["tipo"] == "spacer":
                r.addWidget(QLabel("…", barra))
                continue
            b = QPushButton(p["label"], barra)
            b.setMinimumWidth(36)
            if p["selezionata"]:
                b.setEnabled(False)
            else:
                b.clicked.connect(lambda _=False, o=p["offset"]: self._vai_pagina(o))
            r.addWidget(b)
        r.addStretch(1)
        return barra
