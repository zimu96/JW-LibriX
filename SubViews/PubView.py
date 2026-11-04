#
#  PubView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 13/01/21.
#

"""La sezione Pubblicazioni: il catalogo, e tutto quello che segue.

IL CATALOGO E' IL MENU, I PACCHETTI SONO I LIBRI
------------------------------------------------
``catalog.db`` non e' dentro nessun pacchetto: e' l'elenco di tutto quello
che si puo' scaricare.  Senza di lui la sezione e' vuota anche se sul disco
ci sono venti pubblicazioni gia' scompattate.  Quindi si scarica per primo,
come la Bibbia scarica il suo pacchetto prima di poter leggere i libri.

IL MANIFESTO
------------
L'API vuole sapere *quale* versione del catalogo si vuole, e quella versione
non e' un numero ma una data dentro ``manifest.json``.  Il manifest dice
``current``, e quella data va nel percorso di ``catalog.db.gz``.  Per questo
sono due richieste e non una, e la seconda ha senso solo dopo la prima.

PERCHE' IL CATALOGO VIENE DECOMPRESSO E IL .GZ CANCELLATO
---------------------------------------------------------
Arriva come ``catalog.db.gz``.  Il database vero e' dentro, e il database
vero e' quello che va interrogato con SQLite.  Si scrive il ``.gz``, si
tira fuori il ``.db`` e il ``.gz`` si butta: tenere due copie dello stesso
catalogo occuperebbe spazio per niente e, peggio, fa pensare che una delle
due sia quella giusta.
"""

# `Qt` viene da QtCore, non da QtWidgets, e si usa qui solo per gli
# allineamenti.  Prima non era importato, e `_mostra_catalogo_mancante` —
# che chiama `Qt.AlignmentFlag` tre volte — finiva con
# `NameError: name 'Qt' is not defined`.
#
# Il difetto si vedeva SOLO senza `catalog.db`: con il catalogo presente
# quella funzione non viene chiamata, quindi il programma partiva e la riga
# rotta restava dormiente.  E' il difetto che `JWLibraryApp.py --verifica`
# non trova, perche' anche lui costruisce le schermate con i dati di
# un'installazione vera.
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from SubViews.ArticleView import ArticleView
from SubViews.PubDocumentView import PubDocumentView
from SubViews.PubListView import PubListView, scarica_pub_url
from Utility.DBManager import DBManager
from Utility.Extensions.Ext_DispatchQueue import background
from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility.FileDownloader import FileDownloader
from Utility.JWPubManager import JWPubManager
from Utility.Structures.Generals import Document
from Utility import Lingua
from Utility.Stuff import CATALOG_BASE, Stuff, icon, CHIARO

CATALOG_DB = get_documents_directory() / "catalog.db"


class PubView(QWidget):
    """La sezione Pubblicazioni."""

    #: Chiede di cambiare schermata
    navigate = Signal(object)
    #: Chiede di tornare indietro
    goBack = Signal()
    #: Uno scaricamento e' cominciato o finito: la finestra fa girare la rotella
    busyChanged = Signal(bool)
    #: Una pubblicazione e' stata scelta.  Passa l'oggetto Publication.
    #:
    #: Serve alla sezione Media, che altrimenti non avrebbe modo di sapere
    #: di cosa chiedere i media al server.  Senza questo segnale la sezione
    #: Media si apre e resta vuota, e sembra che il server non risponda.
    #:
    #: Si passa l'oggetto intero e non la sigla perche' la sigla da sola
    #: non distingue l'italiano dall'inglese: la sezione Media deve
    #: chiedere `pub_media(lff, 'I')` e non `pub_media(lff, ?)`.
    pubblicazioneScelta = Signal(object)
    #: I Preferiti sono stati messi o tolti da questa sezione.
    #:
    #: Va alla finestra, che rilige la griglia della Home.  Non passa dal
    #: pulsante Aggiorna e non chiede niente al server: il file dei Preferiti e'
    #: gia' stato scritto sul disco e l'unica cosa che manca e' rileggerlo,
    #: quindi un aggiornamento completo sarebbe il modo piu' lento di
    #: aggiornare una lista di quattro nomi.
    preferitiCambiati = Signal()
    #: Il download e' cominciato: (nome della pubblicazione, byte attesi)
    #:
    #: Sono due segnali e non uno perche' la barra ha bisogno di sapere
    #: **quanto** deve essere lunga prima di muoversi, e quel numero arriva
    #: una volta sola, quando l'API ha detto il pacchetto.  Con un segnale
    #: solo che portasse i byte letti, la barra saprebbe il totale solo al
    #: primo pezzo — e a quel punto e' gia' dentro, quindi si muoverebbe di
    #: colpo o resterebbe ferma con la divisione sbagliata.
    scaricamentoInizia = Signal(str, int)
    #: (byte scritti, byte attesi)
    scaricamentoAvanza = Signal(int, int)
    #: Il pacchetto e' scompattato e sul disco
    #:
    #: NON ERA COLLEGATO A NESSUNA PARTE, E IL SINTOMO E' CHE IL PROGRAMMA
    #: SEMBRA FINITO PRESTO
    #: ----------------------------------------------------
    #: Prima l'unico avviso era `busyChanged`, che dice "sto scaricando" e
    #: basta.  Ma `busyChanged` va a False **subito dopo** il pacchetto,
    #: mentre i testi dei capitoli vengono ancora scritti in sottofondo: chi
    #: aspetta quel segnale e rilettesse il disco troverebbe la cartella con
    #: il solo `manifest.json` e la sezione Scaricati mostrerebbe "Nessuna
    #: pubblicazione scaricata" per qualche secondo dopo un download
    #: riuscito — e l'utente che preme Aggiorna in quel momento vede una
    #: sezione vuota e pensa che sia andato storto.
    #:
    #: Per questo il segnale parte **dopo** `download_documents`, che e'
    #: quando tutto e' scritto, e non prima.
    scaricata = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.publications: list = []
        self.pub = None
        self.document = None
        self._occupato = False
        self._tutto = []
        self._elenco = None
        self._sta_cercando = False

        # IL CAMPO DI RICERCA
        #
        # Sta SOPRA l'elenco, non dentro.  Si cerca in tutta la
        # pubblicazione e dentro un capitolo non ha senso: e' un campo che
        # appartiene a un elenco di 3.741 righe, quindi sta dove sta
        # l'elenco.
        self.cerca = QLineEdit(self)
        self.cerca.setObjectName("campoCerca")
        self.cerca.setPlaceholderText("Cerca fra le pubblicazioni")
        self.cerca.setClearButtonEnabled(True)
        self.cerca.textChanged.connect(self._cerca_cambiata)

        self.conteggio = QLabel("", self)
        self.conteggio.setObjectName("nota")

        riga_cerca = QHBoxLayout()
        riga_cerca.setContentsMargins(8, 6, 8, 6)
        riga_cerca.setSpacing(8)
        riga_cerca.addWidget(self.cerca, 1)
        riga_cerca.addWidget(self.conteggio, 0)
        self._riga_cerca = riga_cerca

        self.pila = QStackedWidget(self)
        self.stato = QLabel("")
        self.stato.setWordWrap(True)
        self.pila.addWidget(self.stato)

        disposizione = QVBoxLayout(self)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.addLayout(riga_cerca)
        disposizione.addWidget(self.pila)
        self._pila = self.pila

        # NESSUN DOWNLOAD ALL'AVVIO
        #
        # Prima qui c'era:
        #
        #     if not CATALOG_DB.exists():
        #         self._scarica_catalogo()      <- partiva da solo
        #
        # e la ragione per cui va tolto e' seria.  Un download che parte
        # senza che nessuno l'abbia chiesto:
        #
        #   * si interrompe a meta' se la linea non regge, e lascia un
        #     file parziale dove l'app lo cerca come se fosse intero
        #   * consuma traffico senza che l'utente lo sappia
        #   * su una linea lenta blocca la finestra per minuti
        #   * e se il catalogo si scrive mentre si legge, gli elenchi sono
        #     mezzo aggiornati e mezzo no
        #
        # Se il catalogo non c'e' si dice che non c'e' e si lascia un
        # pulsante.  Il pulsante e' la differenza fra un programma che
        # scarica e un programma che chiede.
        if not CATALOG_DB.exists():
            self._mostra_catalogo_mancante()
        else:
            self._mostra_pubblicazioni()

    def _mostra_catalogo_mancante(self) -> None:
        """Il catalogo non c'e': si dice e si lascia scegliere."""
        scatola = QWidget(self)
        riga = QVBoxLayout(scatola)
        riga.setContentsMargins(40, 40, 40, 40)
        riga.setSpacing(12)
        riga.addStretch(1)

        testo = QLabel("Il catalogo delle pubblicazioni non e' stato "
                       "scaricato.", scatola)
        testo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        testo.setWordWrap(True)
        riga.addWidget(testo)

        sotto = QLabel("Senza il catalogo non c'e' l'elenco delle "
                       "pubblicazioni.  Il download parte solo se lo "
                       "chiedi tu.", scatola)
        sotto.setObjectName("nota")
        sotto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sotto.setWordWrap(True)
        riga.addWidget(sotto)

        pulsante = QPushButton("Scarica il catalogo", scatola)
        pulsante.setFixedWidth(220)
        pulsante.clicked.connect(self._scarica_catalogo)
        riga.addWidget(pulsante, 0, Qt.AlignmentFlag.AlignHCenter)
        riga.addStretch(1)

        self.pila.addWidget(scatola)
        self.pila.setCurrentWidget(scatola)

    # ------------------------------------------------------------------
    # LA RICERCA
    # ------------------------------------------------------------------

    def _cerca_cambiata(self, testo: str) -> None:
        """Ogni lettera rilancia la ricerca.

        Si fa cosi' e non con un tasto, perche' il campo risponde in 24 ms
        e rimandare non serve a niente: l'utente sta scrivendo e vuole
        vedere.

        La ricerca gira nel filo del discorso, ma non blocca: e' una
        domanda a un indice e non un lavoro lungo.  Se un domani il
        catalogo diventasse tanto grande da far accorgere il ritardo, il
        posto giusto per spostarla e' un ``QThread``, e non un
        ``QTimer`` che rimanda: rimandare fa sembrare veloce una ricerca
        che non e' veloce, e l'utente vede i risultati vecchi senza
        capire perche'.
        """
        if self._sta_cercando:
            return
        self._sta_cercando = True
        try:
            if not testo.strip():
                self._elenco.filtra(self._tutto)
                self.conteggio.setText(f"{len(self._tutto)} pubblicazioni")
                return
            trovate = DBManager.cerca_pubblicazioni(testo)
            self._elenco.filtra(trovate)
            quante = len(trovate)
            self.conteggio.setText(
                f"{quante} {'pubblicazione' if quante == 1 else 'pubblicazioni'}"
                if quante else "nessuna pubblicazione")
        finally:
            self._sta_cercando = False

    def cerca_e_vai(self) -> None:
        """Mette il cursore nel campo di ricerca.

        Lo chiama la lente della fascia.  Non va sulla sezione
        Pubblicazioni perche' l'utente potrebbe essere su un'altra: andare
        e basta gli nasconderebbe quello che sta guardando.
        """
        self.cerca.setFocus()
        self.cerca.selectAll()

    # ------------------------------------------------------------------
    # IL CATALOGO
    # ------------------------------------------------------------------

    def _scarica_catalogo(self) -> None:
        """Due richieste: il manifest, poi il catalogo di quella versione."""
        self.stato.setText("Cerco il catalogo...")
        self.busyChanged.emit(True)

        def chiedi_manifest() -> None:
            manifest = Stuff.get_manifest()
            if not manifest:
                self.busyChanged.emit(False)
                self.stato.setText("Non riesco a raggiungere il catalogo.\n"
                                   "Controlla la connessione e riprova.")
                return
            url = CATALOG_BASE + manifest + "/catalog.db.gz"
            FileDownloader.load_file_async(url=url, completion=self._catalogo_arrivato)

        background(chiedi_manifest)

    def _catalogo_arrivato(self, _percorso, _errore) -> None:
        self.busyChanged.emit(False)
        self._mostra_pubblicazioni()

    def _mostra_pubblicazioni(self) -> None:
        """Legge il catalogo e mette su l'elenco."""
        self.publications = DBManager.get_publications()
        self._tutto = list(self.publications)
        elenco = PubListView(self.publications, self)
        elenco.publicationChosen.connect(self._pub_scelta)
        elenco.downloadRequested.connect(self._scarica_pub)
        elenco.deleteRequested.connect(self._cancella_pub)
        # Il segnale dei Preferiti esce da questa sezione insieme agli altri,
        # e non si chiama nessuno da qui: la finestra e' quella che sa
        # cos'e' la Home e come si rilige quella griglia.  Se qui si chiamasse
        # `HomeView.aggiorna_preferiti()` direttamente, la sezione Pubblicazioni
        # saprebbe della Home, che e' una cosa che non sa e non deve sapere:
        # i due non hanno un'altra ragione per conoscersi.
        elenco.preferitiCambiati.connect(self.preferitiCambiati.emit)
        # La lista rilesse le sue stelle da sola, e poi avvisa fuori.  Le due
        # cose non sono la stessa: senza la prima, la riga dove l'utente ha
        # premuto il tasto destro mostrerebbe la stella vecchia; senza la
        # seconda, la Home non saprebbe che il file dei Preferiti e' cambiato.
        elenco.preferitiCambiati.connect(elenco.segna_i_preferiti)
        self._elenco = elenco
        self.conteggio.setText(f"{len(self.publications)} pubblicazioni")
        self.pila.addWidget(elenco)
        self.pila.setCurrentWidget(elenco)

    # ------------------------------------------------------------------
    # SCARICARE UNA PUBBLICAZIONE
    # ------------------------------------------------------------------

    def scarica(self, pub, apri: bool = True) -> None:
        """Scarica una pubblicazione scelta da un'altra sezione.

        Il metodo pubblico per la sezione Novita' dentro la Home, che ha il
        suo bottone "Scarica" e manda qui la richiesta.

        Fa esattamente quello che fa il bottone della riga dell'elenco, e non
        reimplementa niente: `_scarica_pub` scarica il .jwpub e poi i testi
        dei capitoli, ed e' l'unico posto in cui lo fa.  Se qui si scrivesse di
        nuovo, il giorno che l'indirizzo del pacchetto cambiasse — e cambia,
        perche' l'API risponde e il pacchetto si sposta — qui resterebbe
        quello vecchio e la sezione Pubblicazioni scaricherebbe quella giusta
        mentre la Home scaricherebbe una pagina che non e' un pacchetto.
        """
        self._scarica_pub(pub, apri)

    def _avanza_capitoli(self, fatti: int, totale: int) -> None:
        """Un capitolo e' stato scritto: la riga in fondo si muove.

        Chiama dal main thread una volta per capitolo, e **emette il segnale**
        invece di chiamare la finestra: `_scaricamento_avanza` e' un metodo di
        `SidebarView`, e questa classe non lo ha.

        Il sintomo di averlo scritto male e' un `AttributeError` dentro un
        segnale Qt, e quindi un `abort()` senza traceback — la trappola numero
        sette di `COME-FUNZIONA.txt`.
        """
        self.scaricamentoAvanza.emit(fatti, totale)

    def _scarica_pub(self, pub, apri: bool = True) -> None:
        """Scarica il .jwpub e poi il testo dei suoi capitoli.

        I due scaricamenti sono in sequenza e non si possono fare insieme:
        il testo si sa dove metterlo solo dopo che il pacchetto c'e', e la sua
        lista di capitoli e' dentro il pacchetto.
        """
        self.busyChanged.emit(True)
        FileDownloader.riparti()
        self.stato.setText(f"Scarico {pub.displayTitle}...")

        def scarica_articoli(_percorso, _errore) -> None:
            if FileDownloader.annullato():
                # Annullato durante il pacchetto: niente e' stato scritto.
                self.busyChanged.emit(False)
                self.stato.setText("Scaricamento annullato.")
                FileDownloader.riparti()
                self.scaricata.emit()
                return
            # I CAPITOLI VANNO SCARICATI IN UN THREAD
            # ----------------------------------------
            # Qui ci sono **150 richieste** per una pubblicazione come «Altri
            # argomenti» e **1.189** per la Bibbia, e ogni richiesta aspetta la
            # risposta.  Questa funzione e' la `completion` del download del
            # pacchetto, e le callback di `FileDownloader` arrivano sul **main
            # thread**: a chiamare da qui `download_documents` la finestra
            # restava ferma per tutto il lavoro e sembrava piantata.  Misurato
            # su «Altri argomenti»: la finestra non rispondeva e KDE offriva di
            # terminarlo, poi si e' ripresa da sola quando aveva finito.
            #
            # Quindi il ciclo dei capitoli va in background, e l'avanzamento
            # torna indietro con un segnale: il main thread non aspetta, e la
            # riga in fondo alla finestra si muove col conto e col tempo che
            # manca.
            from Utility import Aggiornamenti
            from Utility.Extensions.Ext_DispatchQueue import background, on_main

            # IL CRONOMETRO RIPARTE, PERCHE' SI CONTA UNA COSA DIVERSA
            # ---------------------------------------------------------
            # Fino a un momento fa la riga contava i **byte** del pacchetto.
            # Adesso conta i **capitoli**, e sono un'altra unita': se il
            # cronometro non ripartisse, il tempo che manca sarebbe calcolato
            # su un numero di byte e detto in capitoli — e direbbe «manca un'ora»
            # per un lavoro di trenta secondi.
            #
            # Il totale dei capitoli si sa solo dopo che il thread ha aperto
            # il database del pacchetto, quindi qui si parte senza totale: la
            # riga si mette in indeterminate e la prima chiamata di `capitolo`
            # le allinea sul numero vero.
            from Utility.Extensions.Ext_DispatchQueue import on_main
            on_main(lambda: self.scaricamentoInizia.emit(
                f"{pub.displayTitle} — i capitoli", 0))

            def capitolo(fatti: int, totale: int) -> None:
                """Il thread ha scritto un capitolo: la riga si muove."""
                on_main(lambda: self._avanza_capitoli(fatti, totale))

            def finito() -> None:
                """Tutti i capitoli sono scritti: si registra e si apre.

                IL CHECKSUM SI REGISTRA QUI E NON PRIMA
                ------------------------------------------
                Il pacchetto e' scompattato e i file ci sono.  Prima di adesso
                il tuo checksum non era scritto da nessuna parte, quindi la
                sezione delle novita' non poteva dire se un pacchetto era
                vecchio: sapeva solo che esisteva.

                Si registra **dopo** e non prima perche' un download
                interrotto a meta' lascerebbe scritto «scaricato» senza che lo
                sia, e da quel momento in poi l'app non lo chiederebbe piu'.

                Il checksum viene dall'API, ed e' quello che il server ha
                adesso.  Se fra un mese il server cambia il pacchetto, il
                confronto lo vede: il tuo dice 2026-09 e il suo dice 2026-10.
                """
                if FileDownloader.annullato():
                    # Annullato durante i capitoli: si toglie quello che c'e',
                    # cosi' non resta un pacchetto a meta' segnato come scaricato.
                    PubListView.delete_pub(pub)
                    self.busyChanged.emit(False)
                    self.stato.setText("Scaricamento annullato.")
                    FileDownloader.riparti()
                    self.scaricata.emit()
                    return
                Aggiornamenti.segna_scaricato(
                    pub.keySymbol,
                    Lingua.da_numero(pub.mepsLanguageId),
                    checksum=dopo_url_tenuta[0])
                self.busyChanged.emit(False)
                # Ora il disco e' davvero completo: il pacchetto e' scompattato
                # e i testi scritti.  Solo adesso la sezione Scaricati ha
                # qualcosa da rileggere.
                self.scaricata.emit()
                if apri:
                    self._pub_scelta(pub)

            background(lambda: JWPubManager.download_documents(pub, capitolo),
                       completion=finito)

        # Il checksum del pacchetto, tenuto per la registrazione dopo, e la sua
        # dimensione in byte per la barra che deve sapere quanto e' lunga
        # **prima** di muoversi.  Due liste e non due variabili perche'
        # `dopo_url` e' chiamata dentro `chiedi_url`, che gira in un thread:
        # chiudere una variabile da li' e scriverla da un altro thread e' il
        # modo di avere metta della metta None.
        dopo_url_tenuta = [None]
        dimensione_tenuta = [0]

        def dopo_url(url: str | None) -> None:
            # QUESTA FUNZIONE GIRA IN UN THREAD, E IL SUO LAVORO E' DI RETE
            # --------------------------------------------------------------
            # `chiedi_url` chiama `Stuff.get_jwpub_url` dentro `background()`,
            # quindi tutto quello che segue e' rete: va bene qui.
            #
            # Quello che NON va bene qui e' toccare i widget.  `dopo_url`
            # accendeva la riga di scaricamento e scriveva l'etichetta di
            # stato direttamente, e i segnali sono collegati in modo diretto:
            # quindi `_scaricamento_inizia` e `_mostra_attesa` venivano
            # eseguiti **in questo thread**, non in quello della finestra.
            #
            # Il sintomo sono due cose diverse e dipendono da dove si guarda.
            # In una finestra vera, Qt si arrabbia e basta: la riga resta
            # com'era e lo scaricamento sembra partire a caso.  Con il
            # terminale si vede la parte vera: toccare un widget fuori dal suo
            # thread porta a `abort()`, e la traccia sparisce.
            #
            # Il rimedio e' quello che il resto del programma usa gia': la
            # parte di finestra passa da `on_main`, che rimette tutto sul
            # main thread attraverso un segnale.
            from Utility.Extensions.Ext_DispatchQueue import on_main

            def in_finestra(azione) -> None:
                """Il pezzo che tocca la finestra, sul main thread."""
                on_main(azione)

            if not url:
                def non_trovo() -> None:
                    self.busyChanged.emit(False)
                    self.stato.setText(
                        f"Non trovo dove scaricare {pub.displayTitle}.")

                in_finestra(non_trovo)
                return
            # Il checksum **e la dimensione** li chiede `controlla_una_pubblicazione`,
            # che e' la funzione che gia' esiste e che restituisce entrambi.
            # Non ne ho inventata un'altra: due modi di prendere lo stesso
            # numero dal server sono due modi che possono dare due numeri
            # diversi.
            #
            # LA RIGA CHE C'ERA PRIMA, E PERCHE' IL DOWNLOAD NON PARTIVA
            # ----------------------------------------------------------
            # Qui c'era `int(pub.filesize or 0)`, e `Publication` **non ha un
            # attributo `filesize`**: e' un dataclass con ID, keySymbol, year,
            # mepsLanguageId, publicationTypeId, issueTagNumber, title,
            # issueTitle, isBible, book, chapter.  Quindi la riga sollevava
            #
            #     AttributeError: 'Publication' object has no attribute 'filesize'
            #
            # dentro il thread di sfondo, il download del pacchetto non
            # partiva — e infatti la riga successiva, quella che avvia davvero
            # `FileDownloader`, non veniva mai raggiunta.  Il sintomo in finestra
            # era solo «Non riesco a togliere .../es26_I: File o directory non
            # esistente», e in terminale venti traceback identici.
            #
            # La dimensione non la si va a cercare da un'altra parte: e' gia'
            # nella risposta che questa funzione sta gia' facendo, accanto al
            # checksum.  `Aggiornamenti.controlla_una_pubblicazione` mette
            # `filesize` in ogni sua risposta, e qui si buttava via.
            #
            # E se il server non la manda?  Vale zero, e zero e' un valore
            # previsto: `SidebarView._scaricamento_inizia` mette la barra in
            # indeterminate quando il totale e' zero, e la prima chiamata di
            # `avanzamento` la riallinea con il `Content-Length` vero.  Quindi
            # qui non si indovina e non si blocca: si passa quello che si sa.
            try:
                from Utility import Aggiornamenti as _Agg
                voce = _Agg.controlla_una_pubblicazione(
                    pub.keySymbol,
                    Lingua.da_numero(pub.mepsLanguageId))
                dopo_url_tenuta[0] = voce.get("checksum")
                try:
                    dimensione_tenuta[0] = int(voce.get("filesize") or 0)
                except (TypeError, ValueError):
                    dimensione_tenuta[0] = 0
            except Exception:  # noqa: BLE001
                dopo_url_tenuta[0] = None
                dimensione_tenuta[0] = 0
            # L'avanzamento viene dal thread che scarica, e i widget si
            # toccano solo dal main thread: `on_main` e' il ponte, ed e'
            # gia' usato dal resto del programma per questo.  Senza, dentro
            # il callback Qt la finestra andrebbe in `abort()` dalla parte di
            # C++ senza lasciare nessuna riga di traceback.
            def avanzamento(scritti: int, totale: int) -> None:
                in_finestra(lambda: self.scaricamentoAvanza.emit(scritti, totale))

            # Il totale viene dall'API, accanto al checksum, e non da
            # `pub.filesize` — attributo che `Publication` non ha (vedi sopra).
            # Se il server non lo manda vale zero, e zero e' previsto: la barra
            # va in indeterminate e la prima `avanzamento` la riallinea con il
            # `Content-Length` vero, che arriva con i byte letti.  Meglio una
            # barra che si muove senza dire quanto che una percentuale inventata.
            def accendi_la_riga() -> None:
                self.scaricamentoInizia.emit(pub.displayTitle,
                                             dimensione_tenuta[0])

            in_finestra(accendi_la_riga)
            FileDownloader.load_file_async(url=url, completion=scarica_articoli,
                                           on_progress=avanzamento)

        def chiedi_url() -> None:
            dopo_url(Stuff.get_jwpub_url(api_link=scarica_pub_url(pub)))

        background(chiedi_url)

    def _cancella_pub(self, pub) -> None:
        """Toglie il pacchetto e i suoi testi, poi aggiorna l'elenco."""
        self.busyChanged.emit(True)
        PubListView.delete_pub(pub)
        self.busyChanged.emit(False)
        self._mostra_pubblicazioni()

    # ------------------------------------------------------------------
    # LA NAVIGAZIONE
    # ------------------------------------------------------------------

    def apri_pubblicazione(self, pub) -> None:
        """Apri una pubblicazione scelta da un'altra sezione.

        Il metodo pubblico per i Preferiti della Home e per la lista degli
        Scaricati, che scelgono una pubblicazione senza passare da qui.

        Fa esattamente quello che fa la riga dell'elenco quando la premi, e
        non reimplementa niente: ``_pub_scelta`` costruisce i capitoli e
        avvisa la sezione Media, ed e' l'unico posto in cui lo fa.  Se qui
        si scrivesse di nuovo, un cambiamento in `_pub_scelta` — per esempio
        il nome della cartella — lascerebbe fuori queste due sezioni, e
        sembrerebbe che certe pubblicazioni si aprano e altre no.
        """
        self._pub_scelta(pub)

    def _pub_scelta(self, pub) -> None:
        """Una pubblicazione e' stata scelta: si aprono i suoi capitoli."""
        self.pub = pub
        # Si dice anche quale e'.  E' quello che mette in moto la sezione
        # Media: senza, non c'e' modo di sapere di cosa chiedere i media
        # al server, e la sezione si apre e resta vuota.
        self.pubblicazioneScelta.emit(pub)
        documenti = PubDocumentView(pub)
        # L'elenco serve anche all'articolo: con le frecce si passa da un
        # capitolo all'altro senza tornare qui.  Si tiene la stessa lista che
        # PubDocumentView ha appena letto, non una seconda lettura del DB.
        self._documenti = documenti.documents
        documenti.documentChosen.connect(self._document_scelto)
        self.navigate.emit(documenti)

    def _document_scelto(self, documento, ancora: str = "",
                         a_un_giorno: bool = False) -> None:
        """Un capitolo e' stato scelto: si apre l'articolo.

        Il capitolo si cerca con ``documento.documentId``, che e' il
        MepsDocumentId: il nome del file HTML e' quel numero.

        `ancora` e' l'`id` del paragrafo da cui partire.  Vuota quando la
        pagina si apre dall'inizio, che e' il caso di tutte le righe
        dell'elenco.  Non e' un modo per aprire un pezzo a caso: l'`id` e'
        quello del paragrafo, e senza quel capitolo l'ancora non porta
        niente — quindi chi la passa deve sapere che il capitolo e' quello giusto.

        `a_un_giorno` serve solo alle Scritture del giorno: il documento del
        mese contiene tutti i giorni, e la schermata ne mostra uno per volta.
        """
        self.document = documento
        pagine = None
        indice_pagina = -1
        if not a_un_giorno:
            documenti = getattr(self, "_documenti", None)
            if not documenti:
                documenti = JWPubManager.get_documents(pub=self.pub)
                self._documenti = documenti
            if documenti:
                pagine = [
                    {"file_path": f"Documents_I/{d.documentId}.html",
                     "document": d, "titolo": d.title}
                    for d in documenti
                ]
                indice_pagina = next(
                    (i for i, d in enumerate(documenti)
                     if d.documentId == documento.documentId), -1)
                if indice_pagina < 0:
                    # Il documento non e' nell'elenco (per esempio un file
                    # aperto da un collegamento): meglio nessuna freccia che
                    # frecce che portano a un'altra pagina.
                    pagine = None
        articolo = ArticleView(
            pub=self.pub,
            file_path=f"Documents_I/{documento.documentId}.html",
            prev_text=self.pub.displayTitle,
            document=documento,
            ancora=ancora,
            a_un_giorno=a_un_giorno,
            pagine=pagine,
            indice_pagina=indice_pagina,
        )
        self.navigate.emit(articolo)

    def apri_il_giorno(self, pub: Publication, pagina: dict) -> None:
        """Apre il capitolo di una pagina, sul paragrafo giusto.

        PERCHE' ESISTE E BASTAVA `apri_pubblicazione`
        --------------------------------------------
        Perche' `apri_pubblicazione` apre il **pacchetto**, che per questa
        pubblicazione non e' un testo da leggere: e' l'elenco dei dodici
        mesi.  Per il verso del giorno serve il mese di oggi, e sul paragrafo
        di oggi dentro quel mese.

        PERCHE' LA PUBBLICAZIONE LA PRENDE E NON LA TROVA GIA' PRONTA
        -----------------------------------------------------------
        Il chiamante non deve venire a mettere `self.pub` a mano prima di
        chiamare.  Prima era cosi', e dipendeva da un accordo che stava fuori
        dalla porta: se il chiamante si dimenticava, `_document_scelto`
        leggeva `self.pub.displayTitle` con `self.pub` a `None` e moriva con

            AttributeError: 'NoneType' object has no attribute 'displayTitle'

        La pubblicazione e' un argomento, quindi l'ordine e' dentro il metodo
        e non e' una promessa.

        Il documento e' costruito qui e non cercato fra le righe del catalogo:
        un `documentId` e un titolo sono gia' tutto quello che `ArticleView`
        usa, e cercarli aggiungerebbe una lettura del database a ogni clic per
        roba che si puo' scrivere in tre righe.  E' la stessa scelta di
        `_aperta_da_preferito`, per lo stesso motivo.

        Se la pagina non dice niente — non e' scaricata, o il giorno non c'e'
        nel mese — non si apre niente e si dice perche': aprire un mese a caso
        mostrerebbe il giorno sbagliato sotto la data giusta.
        """
        documento_id = pagina.get("documentId") if isinstance(pagina, dict) else 0
        if not documento_id or pub is None:
            self.messaggio.emit(
                "Le Scritture del giorno non sono scaricate: aprile prima.")
            return
        self.pub = pub
        documento = Document(ID=0, documentId=int(documento_id),
                             title=str(pagina.get("titolo") or ""))
        self._document_scelto(documento,
                             ancora=str(pagina.get("ancora") or ""),
                             a_un_giorno=True)
