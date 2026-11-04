#
#  BibleView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""La sezione Bibbia: scarica il pacchetto, poi scarica il testo.

Ci sono due scaricamenti separati e non si possono confondere:

  1. ``nwt_I.jwpub``.  Un pacchetto da qualche parte centinaia di
     mega, serve per sapere i 66 libri e quanti capitoli ha ciascuno.  Senza
     questo non c'e' nemmeno la lista dei libri, quindi viene per primo.

  2. Il testo, capitolo per capitolo, da wol.jw.org.  Sono 1189 richieste e
     ci mette un bel po'.  Vengono scaricate in background e la finestra
     resta viva.

QUELLO CHE IN SWIFT ERA SBAGLIATO
--------------------------------
Il codice originale scriveva dentro ``downloadProgress`` da dentro il ciclo
che gira in background::

    DispatchQueue.background(background: {
        for book in bibleBooks {
            ...
            downloadProgress = op + " nwt_I/\\(book.ID)/\\(chapter)\\n" + downloadProgress
        }

In Swift quello e' una scrittura a una ``@State`` da un thread che non e'
quello della grafica.  Funziona finche' non va male, e quando va male
l'errore e' dentro un altro file e non dice niente.  In Python la cosa
analoga e' scrivere in un attributo di un QWidget da un thread estraneo, e
anche li' il sintomo e' una cosa che muore in un punto diverso da quello
giusto.

Per questo qui il lavoro gira in background e l'avanzamento torna con un
segnale.  Lo stesso lavoro, lo stesso ordine, la stessa quantita' di richieste,
senza la scrittura fuori posto.

PERCHE' LA BIBLIA E' UNA PUBBLICAZIONE SPECIALE
-----------------------------------------------
La Bibbia si registra come ``Publication`` con ``keySymbol = "nwtsty"``, ma il
suo pacchetto si chiama ``nwt_I`` e il suo database si chiama ``nwt_I.db``.
E il suo capitolo e' un libro (1-66) piu' un capitolo, non un
MepsDocumentId.  Per questo in questa sezione il ``Publication`` viene
costruito a mano con ``isBible=True`` e i due numeri dentro, invece di
cercarlo nel catalogo.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from SubViews.ArticleView import ArticleView
from SubViews.BibleBooksView import BibleBooksView
from SubViews.BibleChaptersView import BibleChaptersView
from Utility.DBManager import DBManager
from Utility.Extensions.Ext_DispatchQueue import background
from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility.FileDownloader import FileDownloader
from Utility.JWPubManager import scarica_jwpub
from Utility.Structures.Generals import Publication

# IL PACCHETTO DELLA BIBBIA NON HA UN INDIRIZZO FISSO.
# Il progetto originale ne aveva uno scritto a mano
# (".../download-a.akamaihd.net/files/media_publication/c1/nwt_I.jwpub"), e
# oggi risponde 404: jw.org ha cambiato CDN e gli indirizzi diretti hanno dentro
# un percorso con numeri che cambiano.  Per questo l'indirizzo si chiede
# all'API, che ogni volta restituisce quello giusto.  Vedi
# JWPubManager.scarica_jwpub, che spiega perche'.

# Il testo di ogni capitolo si scarica da wol.jw.org, con l'indirizzo della lingua
# scelta: vedi `Utility.WolLingua.url_capitolo`.

# Il simbolo con cui la Bibbia si registra come pubblicazione.  Non e' il
# nome del pacchetto: vedi la nota sopra.
BIBLE_KEY_SYMBOL = "nwtsty"

# La cartella del pacchetto scompattato.  Il nome non cambia mai, a
# differenza dell'indirizzo di scarica.
def _bible_dir():
    """La cartella del pacchetto della Bibbia **nella lingua scelta**.

    Non ha nome fisso, e non e' piu' "la prima che si trova": con il menu
    della lingua, «la prima» era quella che viene prima per nome, quindi
    cambiare lingua non cambiava niente e si continuava a leggere il testo
    di prima.  Il perche' e' scritto in `JWPubManager.bible_package`.
    """
    from Utility.JWPubManager import bible_package
    return bible_package()

BIBLE_TITLE = "Traduzione del Nuovo Mondo delle Sacre Scritture (edizione per lo studio)"


def _nome_lingua(simbolo: str) -> str:
    from Utility import Lingua

    voce = Lingua.per_simbolo(simbolo) or {}
    return voce.get("nome_vernacolare") or voce.get("nome") or simbolo


class BibleView(QWidget):
    """La sezione Bibbia: scarica, poi mostra libri, capitoli e testo."""

    #: Chiede di cambiare schermata (navigazione della finestra)
    navigate = Signal(object)
    #: Chiede di tornare indietro
    goBack = Signal()
    #: L'avanzamento del download, dal thread di lavoro
    _avanzamento = Signal(str)
    #: Lo stesso avanzamento in numeri (capitoli fatti, capitoli totali)
    _numeri = Signal(int, int)
    #: Il testo e' pronto, l'indice si puo' mostrare
    _pronto = Signal()

    #: La sezione ha cambiato la lingua dell'app e vuole essere rifatta.
    #:
    #: Serve per un caso solo: l'utente e' in una lingua senza Bibbia
    #: scaricabile e preme «Passa all'italiano».  E' la sezione che lo
    #: scopre, ma sono le schermate che vanno rifatte, e sono della
    #: finestra: quindi la sezione **dice** che e' successo e non le fa
    #: rifare da se'.  Vedi `SidebarView._collega`.
    linguaCambiata = Signal()
    #: Un messaggio breve per l'utente
    messaggio = Signal(str)
    #: E' stato scaricato o tolto qualcosa: Scaricati si rilegge
    pacchettoScaricato = Signal()
    #: Lo scaricamento della Bibbia in una lingua e' finito (simbolo)
    _scaricoFinito = Signal(str)
    #: Un documento di Introduzione / Indice / Appendici: (MepsDocumentId, titolo).
    documentoScelto = Signal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.bible_books: list = []
        self.bible_book_index: int = -1
        self.chapter: int = 0
        self._scaricato: bool = False

        self.pila = QStackedWidget(self)
        self.stato = QLabel("Scarico struttura...")
        self.stato.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stato.setWordWrap(True)
        self.pila.addWidget(self.stato)
        self._barra_stato = self._crea_barra_stato()

        disposizione = QVBoxLayout(self)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.addWidget(self.pila)

        self._selettore = None
        self._scaricoFinito.connect(self._scarico_finito)
        self._crea_striscia_scarico(disposizione)
        self._comincia()

    # ------------------------------------------------------------------
    # L'AVVIO
    # ------------------------------------------------------------------

    def _comincia(self) -> None:
        """C'e' la Bibbia di questa lingua?  Se no, si decide come ottenerla.

        QUATTRO CASI, E PERCHE' NON SONO DUE
        ------------------------------------
        1.  Il pacchetto della lingua scelta c'e': si legge, e basta.
        2.  Il testo di questa lingua non si puo' scaricare: si dice e si
            offre l'italiano.  Il sito ha la lingua? Lo dice `WolLingua.supportata`.
        3.  Il testo si puo' scaricare, il pacchetto no, ma sul disco c'e' una
            Bibbia in un'altra lingua: **non si scarica**.  Sono 122 MB e
            l'utente ha solo cambiato lingua per leggere l'indice; scaricargli
            una Bibbia intera senza chiedere e' la cosa che questo programma
            non fa da nessuna parte.  Si dice che manca e si mette un
            pulsante: la scelta e' sua.
        4.  Non c'e' nessuna Bibbia: si scarica, come e' sempre stato.

        I casi 2 e 3 sono nuovi.  Prima non esistevano perche' non c'era la
        scelta della lingua: o c'era una Bibbia e si leggeva, o non c'era e si
        scaricava.  Con il menu della lingua il caso 3 e' quello in cui si
        entra cambiando lingua dopo aver scaricato la Bibbia una volta, e
        senza questa distinzione ogni cambio di lingua avrebbe avviato un
        download da 122 MB.
        """
        if _bible_dir() is not None:
            self._leggi_libri("Controllo")
            return

        from Utility import Lingua, WolLingua
        if not WolLingua.supportata(Lingua.bibbia_simbolo()):
            self._bibbia_non_disponibile()
            return

        if Lingua.bibbia_simbolo() != "I":
            self._apri_online()
            return

        from Utility.JWPubManager import bible_package_di_qualunque_lingua
        if bible_package_di_qualunque_lingua() is not None:
            self._chiedi_la_bibbia()
            return

        # Nessuna Bibbia sul disco: non si scarica da sola.  Se l'hai appena
        # eliminata, entrare qui per sbaglio non deve rimettersi a scaricare:
        # c'e' il tasto «Scaricala adesso».
        self._chiedi_la_bibbia()

    def _bibbia_non_disponibile(self) -> None:
        """Questa Bibbia non si puo' scaricare: si offre l'italiano, che si puo'.

        Il pulsante non scarica niente: cambia la lingua dell'app in italiano
        e chiede alla finestra di rifare le sezioni.  Il download parte poi da
        solo, per la strada di sempre, con la lingua giusta — e la schermata si
        ricrea, quindi la Bibbia italiana viene cercata di nuovo e trovata.

        Perche' non si scarica direttamente il pacchetto in italiano tenendo la
        lingua scelta: perche' `_scarica_testo` usa la lingua scelta per
        l'indirizzo, e il risultato sarebbe il testo italiano in una cartella
        che si chiama `nwtsty_I` dentro un'app che dice «español» — cioe' il
        difetto che questo lavoro voleva togliere, fatto in un altro modo.
        """
        from Utility import Lingua

        scatola = QWidget()
        colonna = QVBoxLayout(scatola)
        colonna.setContentsMargins(30, 30, 30, 30)
        colonna.setSpacing(12)
        colonna.addStretch(1)

        nome = Lingua.titolo(Lingua.bibbia_voce()) or Lingua.bibbia_simbolo()
        titolo = QLabel(f"La Bibbia in {nome} non si puo' scaricare.")
        titolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titolo.setWordWrap(True)
        colonna.addWidget(titolo)

        sotto = QLabel("Il sito non ha il testo dei capitoli in questa lingua.",
                       scatola)
        sotto.setObjectName("nota")
        sotto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sotto.setWordWrap(True)
        colonna.addWidget(sotto)

        pulsante = QPushButton("Passa all'italiano", scatola)
        pulsante.setFixedWidth(240)
        pulsante.clicked.connect(self._passa_all_italiano)
        colonna.addWidget(pulsante, 0, Qt.AlignmentFlag.AlignHCenter)
        colonna.addStretch(1)

        self.pila.addWidget(scatola)
        self.pila.setCurrentWidget(scatola)

    def _passa_all_italiano(self) -> None:
        """Cambia la lingua in italiano e chiede alla finestra di rifare tutto."""
        from Utility import Lingua
        if not Lingua.imposta(Lingua.PREDEFINITA):
            return
        self.linguaCambiata.emit()

    def _chiedi_la_bibbia(self) -> None:
        """Manca la Bibbia di questa lingua: si dice e si lascia scegliere.

        Il testo dice **quale** lingua manca e **quanto** costa scaricarla,
        perche' la domanda «scaricare 122 MB?» non si puo' rispondere senza
        sapere di cosa si parla.  Il numero viene da `dati/`: la dimensione
        del pacchetto gia' scaricato e' la misura reale di quello che
        verrebbe scaricato, non un numero scritto qui.

        Il pulsante chiama la stessa `_scarica_pacchetto` del caso 3: un solo
        posto da cui parte il download, e quindi un solo posto in cui puo'
        andare storto.
        """
        from Utility import Lingua
        from Utility.JWPubManager import bible_package_di_qualunque_lingua

        nome = Lingua.titolo(Lingua.bibbia_voce()) or Lingua.bibbia_simbolo()
        altra = bible_package_di_qualunque_lingua()
        quanto = ""
        if altra is not None:
            megabyte = self._peso_pacchetto(altra)
            if megabyte:
                quanto = f"circa {megabyte} MB"

        scatola = QWidget()
        colonna = QVBoxLayout(scatola)
        colonna.setContentsMargins(30, 30, 30, 30)
        colonna.setSpacing(12)
        colonna.addStretch(1)

        titolo = QLabel(f"La Bibbia in {nome} non e' ancora scaricata.")
        titolo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titolo.setWordWrap(True)
        colonna.addWidget(titolo)

        if quanto:
            sotto = QLabel(f"E' un pacchetto di {quanto}.", scatola)
            sotto.setObjectName("nota")
            sotto.setAlignment(Qt.AlignmentFlag.AlignCenter)
            colonna.addWidget(sotto)

        pulsante = QPushButton("Scaricala adesso", scatola)
        pulsante.setFixedWidth(220)
        pulsante.clicked.connect(self._scarica_e_mostra_avanzamento)
        colonna.addWidget(pulsante, 0, Qt.AlignmentFlag.AlignHCenter)
        colonna.addStretch(1)

        # `self.stato` — l'etichetta di avanzamento — resta nella pila accanto
        # a questa schermata e non viene sostituita: quando il download parte
        # basta tornare a mostrare quella.  Ricreare l'etichetta qui vuol dire
        # che `_scarica_testo`, che scrive su `self.stato` piu' avanti, si
        # troverebbe un oggetto diverso da quello che l'utente sta guardando.
        self.pila.addWidget(scatola)
        self.pila.setCurrentWidget(scatola)

    def _scarica_e_mostra_avanzamento(self) -> None:
        """Il pulsante e' stato premuto: si scarica e si mostra l'avanzamento.

        Il testo va impostato **prima** di chiamare `_scarica_pacchetto`,
        perche' quella parte in background e il callback possono arrivare
        prima che la finestra abbia cambiato pagina: scrivere l'avanzamento
        su un'etichetta che non si vede fa perdere quello che sta succedendo.
        """
        FileDownloader.riparti()
        self._scarico_nuovo = True
        self.stato.setText("Scarico struttura...")
        self._barra_stato.setRange(0, 0)
        self._tasto_annulla.setEnabled(True)
        self._tasto_annulla.show()
        self.pila.setCurrentWidget(self.stato)
        self._scarica_pacchetto()

    @staticmethod
    def _peso_pacchetto(cartella) -> int:
        """Quanto pesa il pacchetto, in megabyte arrotondati.  0 se non si sa.

        Si sommano i file di `contents/`, che e' il pacchetto: il `.jwpub` non
        c'e' piu' dopo che e' stato scompattato.  Il numero serve solo per
        dire all'utente «quanto», quindi un errore di qualche megabyte non
        cambia niente e va restituito come 0 invece di far fallire tutto.
        """
        try:
            byte = sum(f.stat().st_size for f in (cartella / "contents").rglob("*")
                       if f.is_file())
        except OSError:
            return 0
        if byte <= 0:
            return 0
        return max(1, round(byte / (1024 * 1024)))

    def _scarica_pacchetto(self) -> None:
        def fatto(_percorso, errore) -> None:
            if FileDownloader.annullato():
                self._annullato()
                return
            if errore is not None:
                self._tasto_annulla.hide()
                # Senza il pacchetto non c'e' la lista dei libri, e senza la
                # lista dei libri non c'e' niente da mostrare.  Meglio una
                # riga che dice cosa non ha funzionato che un "unable to open
                # database file" che non spiega niente.
                self.stato.setText(
                    "Non riesco a scaricare la Bibbia.\n"
                    "Controlla la connessione e riavvia.")
                return
            self._leggi_libri("Scarico")

        scarica_jwpub(BIBLE_KEY_SYMBOL, 0, completion=fatto)

    def _leggi_libri(self, operazione: str) -> None:
        """Legge i libri dal database e poi scarica il testo in background."""
        self.bible_books = DBManager.get_bible_books()
        if not self.bible_books:
            # Il pacchetto c'e' ma il database non si apre: senza libri non
            # si puo' mostrare niente, e conviene dirlo.
            #
            # Il nome della cartella non e' scritto qui: prima diceva
            # «Prova a togliere la cartella nwtsty_I», e con la lingua scelta
            # che non e' l'italiano quella cartella non esiste e l'utente
            # cancellava una cartella che non aveva.  Il nome lo sa
            # `_bible_dir()`, che e' l'unico posto che sa come si chiama.
            cartella = _bible_dir()
            nome = cartella.name if cartella is not None else "quella del pacchetto"
            self.stato.setText(
                "Non riesco a leggere il pacchetto della Bibbia.\n"
                f"Prova a togliere la cartella {nome} e riavviare.")
            return
        self._scarica_testo(operazione)

    def _scarica_testo(self, operazione: str) -> None:
        """Scarica i 1189 capitoli, in background, con l'avanzamento in alto.

        Il lavoro gira in un thread e l'avanzamento torna con un segnale.
        L'indice dei libri appare quando il testo e' pronto, come nell'app
        originale: mentre si scarica non c'e' niente da mostrare, e mostrare
        una lista vuota sarebbe piu' fuorviante di una riga di stato.
        """
        # IL CONTROLLO PRIMA DI TUTTO
        # ----------------------------
        # `_comincia` non scarica mai in una lingua fuori da
        from Utility import Lingua, WolLingua
        simbolo = Lingua.bibbia_simbolo()
        if not WolLingua.supportata(simbolo):
            self._bibbia_non_disponibile()
            return

        self.stato.setText(f"{operazione} testo...")
        self._barra_stato.setRange(0, 0)
        # Il tasto Annulla c'e' sempre mentre si scarica o si controlla il testo,
        # anche quando il pacchetto era gia' sul disco («Controllo testo...»).
        FileDownloader.riparti()
        self._tasto_annulla.setEnabled(True)
        self._tasto_annulla.show()

        # LA SCHERMA PUO' SPARIRE IN QUALUNQUE MOMENTO
        # --------------------------------------------
        # Si cambia sezione, si chiude la finestra, si ricrea la sezione.
        # Quando sparisce, l'oggetto Python resta nel `self` ma quello di C++
        # no, e toccarlo fa:
        #
        #     RuntimeError: wrapped C/C++ object of type BibleView
        #     has been deleted
        #
        # e, se si tratta del segnale, fa anche una segfault, che e' peggio
        # perche' un'eccezione almeno si può leggere.
        #
        # `sip.isdeleted` e' l'unico modo onesto di chiederlo: `is None` non
        # serve, perche' l'oggetto non diventa None, esiste, e-mentre non
        # e' piu' nato dal lato di C++.  Provarlo a voce fa peggio.
        #
        # Questa funzione sta FUORI da `lavoro` e fuori da `arrivo` perche'
        # la usano entrambe: e' lo stesso problema in due momenti diversi,
        # prima e dopo il download.
        def ancora_qua() -> bool:
            from PyQt6 import sip
            return not sip.isdeleted(self)

        def lavoro() -> None:
            totale = sum(max(0, libro.chapters) for libro in self.bible_books)
            fatti = 0

            # Il nome della cartella e la lista dei libri si prendono una
            # volta sola, PRIMA del ciclo.
            #
            # Prima stavano dentro il ciclo, e ogni capitolo ricalcolava il
            # nome della cartella: sono 1189 capitoli, quindi 1189 costruzioni
            # di un Path per ricavare sempre la stessa stringa.
            #
            # E, piu' importante: dentro il ciclo `self` non serve piu'.  Il
            # ciclo cosi' non tocca la schermata, quindi non puo' rompersi
            # perche' la schermata e' stata cancellata.  L'unica cosa che
            # tocca `self` e' l'emissione dell'avanzamento, e quella e'
            # guardata.
            cartella = self._nome_cartella()
            libri = list(self.bible_books)

            # La lingua si prende UNA volta, prima del ciclo (`simbolo`): se
            # l'utente la cambiasse mentre si scarica, i capitoli verrebbero
            # presi da due lingue nella stessa cartella.
            for libro in libri:
                for capitolo in range(1, max(0, libro.chapters) + 1):
                    if FileDownloader.annullato():
                        return
                    url = WolLingua.url_capitolo(libro.ID, capitolo, simbolo)
                    if url:
                        FileDownloader.download_article(
                            url=url,
                            path=f"{cartella}/{libro.ID}/{capitolo}.html",
                        )
                    fatti += 1
                    if fatti % 10 == 0:
                        if not ancora_qua():
                            return
                        self._avanzamento.emit(f"{operazione} testo... "
                                              f"{fatti}/{totale}")
                        self._numeri.emit(fatti, totale)
            if ancora_qua():
                self._avanzamento.emit(f"{operazione} testo... "
                                       f"{fatti}/{totale} — finito ✅")

        self._avanzamento.connect(self._mostra_avanzamento, Qt.ConnectionType.QueuedConnection)
        self._pronto.connect(self._finito, Qt.ConnectionType.QueuedConnection)

        # completion gira sul main thread: e' il posto giusto da cui costruire
        # i widget, che in Qt si puo' fare solo da li'.
        #
        # QUI C'ERA `completion=self._pronto.emit`, E QUELLO E' UN SEGNALE NUDO
        # ----------------------------------------------------------------------
        # La differenza sembra una parentesi in piu' e invece e' una
        # ``segfault``.
        #
        # `self._pronto.emit` non e' una funzione: e' il metodo ``emit`` del
        # segnale, gia' legato a questa schermata.  Se la schermata e' stata
        # cancellata mentre il download andava, chiamarlo va a leggere
        # memoria gia' liberata e il processo muore:
        #
        #     Fatal Python error: Segmentation fault
        #       File ".../Ext_DispatchQueue.py", line 50, in _esegui
        #
        # e questa riga era lì da quando il porting era cominciato, quindi
        # non e' un difetto che ho fatto io adesso: e' un difetto che
        # aspetta che l'utente cambi sezione durante il download.  Il modo
        # piu' semplice per ritrovarsi un core dump e' esattamente quello che
        # si fa ordinarily: aprire la Bibbia e andarsene.
        #
        # Un ``try`` non serve a niente: non e' un'eccezione, e' un accesso
        # a memoria non piu' tua.  L'unica difesa e' non chiamarlo.
        #
        # Per questo il richiamo e' una funzione che guarda prima, e la
        # guardiglia e' la stessa di `lavoro`, perche' e' lo stesso
        # problema: la schermata puo' sparire in qualunque momento fra
        # l'avvio del download e la fine.
        def arrivo() -> None:
            if not ancora_qua():
                return
            if FileDownloader.annullato():
                self._annullato()
                return
            self._tasto_annulla.hide()
            self._scarico_nuovo = False
            self._pronto.emit()

        background(lavoro, completion=arrivo)

    def _crea_barra_stato(self):
        """La barra viola sotto la scritta di stato: mostra quanto manca."""
        from PyQt6.QtWidgets import QProgressBar
        from Utility import tema

        barra = QProgressBar(self.stato)
        barra.setTextVisible(True)
        barra.setAlignment(Qt.AlignmentFlag.AlignCenter)
        barra.setFixedSize(320, 22)
        barra.setRange(0, 0)      # non si sa ancora quanto: barra che scorre
        barra.setStyleSheet(
            "QProgressBar { background: #444444; color: #ffffff; border: none;"
            " border-radius: 6px; font-size: 12px; }"
            f" QProgressBar::chunk {{ background: {tema.ACCENTO};"
            " border-radius: 6px; }")
        colonna = QVBoxLayout(self.stato)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.addStretch(5)
        colonna.addWidget(barra, 0, Qt.AlignmentFlag.AlignHCenter)
        from PyQt6.QtWidgets import QPushButton
        annulla = QPushButton("Annulla scaricamento", self.stato)
        annulla.setFixedWidth(220)
        annulla.hide()
        annulla.clicked.connect(self._annulla_scaricamento)
        self._tasto_annulla = annulla
        colonna.addSpacing(10)
        colonna.addWidget(annulla, 0, Qt.AlignmentFlag.AlignHCenter)
        colonna.addStretch(3)
        self._numeri.connect(self._mostra_numeri, Qt.ConnectionType.QueuedConnection)
        return barra

    def _annulla_scaricamento(self) -> None:
        """«Annulla scaricamento»: ferma il download e toglie quello gia' scritto."""
        FileDownloader.annulla()
        self._tasto_annulla.setEnabled(False)
        self.stato.setText("Annullo lo scaricamento...")

    def _annullato(self) -> None:
        """Il download e' stato fermato: si torna a «La Bibbia non e' scaricata»."""
        import shutil

        self._tasto_annulla.hide()
        self._tasto_annulla.setEnabled(True)
        if getattr(self, "_scarico_nuovo", False):
            cartella = _bible_dir()
            if cartella is not None:
                shutil.rmtree(cartella, ignore_errors=True)
        nuovo = getattr(self, "_scarico_nuovo", False)
        self._scarico_nuovo = False
        FileDownloader.riparti()
        self.messaggio.emit("Scaricamento annullato")
        if not nuovo and self.bible_books:
            # Il pacchetto della Bibbia c'era gia': annullare il controllo del
            # testo non deve toglierla, si mostra l'elenco dei libri.
            self._finito()
            return
        self.bible_books = []
        self._chiedi_la_bibbia()

    def _mostra_numeri(self, fatti: int, totale: int) -> None:
        barra = self._barra_stato
        if totale > 0:
            barra.setRange(0, totale)
            barra.setValue(min(fatti, totale))
            barra.setFormat(f"{min(fatti, totale) * 100 // totale}%")
        else:
            barra.setRange(0, 0)

    def _mostra_avanzamento(self, testo: str) -> None:
        """L'avanzamento arriva qui gia' sul main thread."""
        self.stato.setText(testo)

    # ------------------------------------------------------------------
    # LA LINGUA DELLA BIBBIA
    # ------------------------------------------------------------------

    def _apri_online(self) -> None:
        """Una lingua senza pacchetto: i libri dal sito (una richiesta, poi in memoria)."""
        from PyQt6 import sip
        from Utility import BibbiaOnline, Lingua, Rete

        simbolo = Lingua.bibbia_simbolo()
        self.bible_books = BibbiaOnline.libri(simbolo, rete=False)
        if self.bible_books:
            self._finito()
            return
        if not Rete.noto():
            self.stato.setText("Per aprire questa lingua la prima volta serve internet.")
            return
        self.stato.setText("Carico i libri…")
        trovati: list = [[]]

        def lavoro() -> None:
            trovati[0] = BibbiaOnline.libri(simbolo)

        def pronto() -> None:
            if sip.isdeleted(self) or Lingua.bibbia_simbolo() != simbolo:
                return
            self.bible_books = trovati[0]
            if self.bible_books:
                self._finito()
            else:
                self.stato.setText("Non riesco a caricare i libri di questa lingua.")
    
        background(lavoro, completion=pronto)

    def _crea_striscia_scarico(self, disposizione) -> None:
        """La striscia in basso con l'avanzamento, visibile solo mentre si scarica."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QHBoxLayout, QProgressBar, QToolButton
        from Utility import tema
        from Utility.Stuff import icon

        self._striscia = QWidget(self)
        self._striscia.setStyleSheet("background: #2b2b2b;")
        riga = QHBoxLayout(self._striscia)
        riga.setContentsMargins(16, 8, 8, 8)
        self._testo_scarico = QLabel("", self._striscia)
        self._testo_scarico.setStyleSheet("color: #f2f2f2; background: transparent;")
        riga.addWidget(self._testo_scarico, 0)
        self._barra_scarico = QProgressBar(self._striscia)
        self._barra_scarico.setTextVisible(False)
        self._barra_scarico.setFixedHeight(8)
        self._barra_scarico.setStyleSheet(
            "QProgressBar { background: #444444; border: none; border-radius: 4px; }"
            f" QProgressBar::chunk {{ background: {tema.ACCENTO}; border-radius: 4px; }}")
        riga.addWidget(self._barra_scarico, 1)
        ferma = QToolButton(self._striscia)
        ferma.setIcon(icon("xmark", "#d0d0d0", 20))
        ferma.setToolTip("Ferma lo scaricamento")
        ferma.clicked.connect(self._ferma_scarichi)
        riga.addWidget(ferma)
        self._striscia.hide()
        disposizione.addWidget(self._striscia)
        self._timer_scarico = QTimer(self)
        self._timer_scarico.timeout.connect(self._aggiorna_striscia)
        self._timer_scarico.start(500)

    def _aggiorna_striscia(self) -> None:
        from Utility import Traduzioni

        attivi = Traduzioni.scaricamenti()
        self._striscia.setVisible(bool(attivi))
        if not attivi:
            return
        simbolo, fatti = next(iter(attivi.items()))
        self._barra_scarico.setRange(0, Traduzioni.TOTALE)
        self._barra_scarico.setValue(fatti)
        self._testo_scarico.setText(
            f"Scarico la Bibbia in {_nome_lingua(simbolo)}… "
            f"{fatti * 100 // Traduzioni.TOTALE}%")

    def _ferma_scarichi(self) -> None:
        from Utility import Traduzioni

        for simbolo in Traduzioni.scaricamenti():
            Traduzioni.ferma(simbolo)

    def apri_selettore_lingua(self) -> None:
        """Il menu delle lingue della Bibbia: lo apre il pulsante della barra viola."""
        self._apri_selettore()

    def _apri_selettore(self) -> None:
        from SubViews.SelettoreLinguaBibbia import SelettoreLinguaBibbia

        if self._selettore is not None:
            try:
                self._selettore.chiudi()
            except RuntimeError:
                pass
        self._selettore = SelettoreLinguaBibbia(self)
        self._selettore.linguaScelta.connect(self._lingua_scelta)
        self._selettore.scaricaRichiesta.connect(self._chiedi_scarica_lingua)
        self._selettore.eliminaRichiesta.connect(self._chiedi_elimina_lingua)
        self._selettore.fermaRichiesta.connect(self._ferma_lingua)

    def _lingua_scelta(self, numero: int) -> None:
        from Utility import BibbiaOnline, Lingua, Rete
        from Utility.JWPubManager import bible_package

        simbolo = (Lingua.per_id(numero) or {}).get("simbolo", "")
        disponibile = (bible_package(simbolo) is not None
                       or BibbiaOnline.libri(simbolo, rete=False))
        if not disponibile and not Rete.noto():
            self.messaggio.emit("Serve internet per aprire questa lingua la prima volta.")
            return
        if self._selettore is not None:
            self._selettore.chiudi()
        if Lingua.imposta_bibbia(numero):
            self._ricomincia()

    def _ricomincia(self) -> None:
        """Rilegge la Bibbia dopo un cambio di lingua."""
        for indice in reversed(range(self.pila.count())):
            pagina = self.pila.widget(indice)
            if pagina is not self.stato:
                self.pila.removeWidget(pagina)
                pagina.deleteLater()
        self.bible_books = []
        self.bible_book_index = -1
        self.chapter = 0
        self._scaricato = False
        self.stato.setText("Carico…")
        self.pila.setCurrentWidget(self.stato)
        self._comincia()

    def _chiedi_scarica_lingua(self, simbolo: str) -> None:
        from SubViews.Conferma import ConfermaApp
        from Utility import Traduzioni

        ConfermaApp.chiedi(
            self, "Scaricare la Bibbia?",
            f"Scarico la Bibbia in {_nome_lingua(simbolo)}: {Traduzioni.TOTALE} "
            "capitoli, circa 13 MB.\n\nDopo si legge anche senza internet.  "
            "Se non la scarichi, si legge online e i capitoli che apri restano "
            "sul disco.",
            "Scarica", lambda: self._scarica_lingua(simbolo))

    def _ferma_lingua(self, simbolo: str) -> None:
        from Utility import Traduzioni

        Traduzioni.ferma(simbolo)
        self.messaggio.emit("Scaricamento fermato: riprende da dove era quando lo rilanci")

    def _scarica_lingua(self, simbolo: str) -> None:
        from Utility import Traduzioni

        if Traduzioni.avvia_scaricamento(simbolo, self._scaricoFinito.emit):
            self.messaggio.emit(f"Scarico la Bibbia in {_nome_lingua(simbolo)}…")
        self._aggiorna_striscia()
        if self._selettore is not None:
            self._selettore.aggiorna()

    def _scarico_finito(self, simbolo: str) -> None:
        from Utility import BibbiaOnline, Traduzioni

        self.pacchettoScaricato.emit()
        completa = BibbiaOnline.capitoli_su_disco(simbolo) >= Traduzioni.TOTALE
        self.messaggio.emit(
            f"Bibbia in {_nome_lingua(simbolo)} scaricata" if completa
            else f"Scaricamento della Bibbia in {_nome_lingua(simbolo)} interrotto")
        if self._selettore is not None:
            try:
                self._selettore.aggiorna()
            except RuntimeError:
                self._selettore = None

    def _chiedi_elimina_lingua(self, simbolo: str) -> None:
        from SubViews.Conferma import ConfermaApp

        ConfermaApp.chiedi(
            self, "Eliminare la Bibbia?",
            f"Elimino dal disco la Bibbia in {_nome_lingua(simbolo)}.\n\n"
            "Si puo' leggere di nuovo online o riscaricare.",
            "Elimina", lambda: self._elimina_lingua(simbolo))

    def _elimina_lingua(self, simbolo: str) -> None:
        from Utility import Lingua, Traduzioni

        Traduzioni.elimina(simbolo)
        self.pacchettoScaricato.emit()
        if self._selettore is not None:
            self._selettore.aggiorna()
        if Lingua.bibbia_simbolo() == simbolo:
            self._ricomincia()

    def _finito(self) -> None:
        """Il testo e' pronto: compare la lista dei libri."""
        if self._scaricato or not self.bible_books:
            return
        self._scaricato = True
        from Utility.JWPubManager import JWPubManager
        from Utility import BibbiaOnline, Lingua
        libri = BibleBooksView(self.bible_books, self,
                               sezioni=JWPubManager.bible_sections(),
                               titoli=(BibbiaOnline.titoli(Lingua.bibbia_simbolo())
                                       if _bible_dir() is None else None))
        libri.bookChosen.connect(self._libro_scelto)
        libri.documentChosen.connect(self.documentoScelto.emit)
        self.pila.addWidget(libri)
        self.pila.setCurrentWidget(libri)

    # ------------------------------------------------------------------
    # LA NAVIGAZIONE
    # ------------------------------------------------------------------

    def _nome_cartella(self) -> str:
        """Il nome della cartella dei capitoli: quello del pacchetto, o ``nwtsty_<lingua>``."""
        from Utility import Lingua
        cartella = _bible_dir()
        return cartella.name if cartella is not None else f"nwtsty_{Lingua.bibbia_simbolo()}"

    def _libro_scelto(self, indice: int) -> None:
        """Un libro e' stato scelto: la finestra apre la griglia dei capitoli.

        Lo schermo non viene messo dentro ``self.pila``: la finestra ha una
        pila sua, e mettere uno schermo dentro due pile diverse vuol dire che
        il pulsante "indietro" non sa da dove tornare.
        """
        self.bible_book_index = indice
        libro = self.bible_books[indice]
        capitoli = BibleChaptersView(libro)
        capitoli.chapterChosen.connect(self._capitolo_scelto)
        self.navigate.emit(capitoli)

    def _capitolo_scelto(self, capitolo: int) -> None:
        """Un capitolo e' stato scelto: compare il testo."""
        # `mepsLanguageId` era 4 scritto fisso.  Il capitolo che si sta per
        # mostrare e' quello del pacchetto della lingua scelta, quindi la
        # `Publication` deve dirlo: e' da quel numero che gli altri schermati
        # ricavano il simbolo per chiedere copertine e citazioni, e con il 4
        # fisso una Bibbia spagnola si presentava come italiana.
        from Utility import Lingua
        self.chapter = capitolo
        libro = self.bible_books[self.bible_book_index]
        pub = Publication(
            ID=0, keySymbol=BIBLE_KEY_SYMBOL, year=2021,
            mepsLanguageId=Lingua.bibbia_id(),
            publicationTypeId=1, issueTagNumber=0, title=BIBLE_TITLE,
            isBible=True, book=self.bible_book_index + 1, chapter=capitolo,
        )
        # I capitoli dello stesso libro sono pagine dello stesso articolo:
        # le frecce nella barra passano al precedente e al successivo senza
        # creare una schermata nuova.  Ai due estremi la freccia che non
        # porta da nessuna parte sparisce.
        cartella = self._nome_cartella()
        pagine = [
            {"file_path": f"{cartella}/{self.bible_book_index + 1}/{n}.html",
             "document": None, "titolo": str(n), "capitolo": n}
            for n in range(1, max(0, libro.chapters or 0) + 1)
        ]
        articolo = ArticleView(
            pub=pub,
            file_path=f"{cartella}/{self.bible_book_index + 1}/{capitolo}.html",
            prev_text=libro.shortName,
            document=None,
            pagine=pagine,
            indice_pagina=capitolo - 1,
        )
        self.navigate.emit(articolo)

    def bible_db_path(self):
        """Il percorso del database della Bibbia, per chi lo cerca altrove."""
        from Utility.JWPubManager import bible_db_path as _p
        return _p()
