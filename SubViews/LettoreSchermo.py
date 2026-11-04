#
#  SubViews/LettoreSchermo.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il video a tutto schermo, sopra tutto.

PERCHE' UNA FINESTRA E NON UN RECTANGOLO SOPRA LA FINESTRA
--------------------------------------------------------
Un rettangolo nero che copre tutto schermo sembra la cosa giusta e non lo e':
occupa 100x100 con i bordi dello schermo, si muove male quando cambiano i
monitor e non si chiude con la Escape in un modo che l'utente si aspetta.

Una finestra senza cornice e senza barra e' quello che il sistema gia' sa
fare: si posiziona sullo schermo che contiene la finestra principale, si
mette sopra tutto e prende la Escape da solo.

CHE COSA FA IL PROGRAMMA, E COSA FA IL LETTORE
----------------------------------------------
Qui non c'e' nessun player.  Il player e' uno solo e sta in
`Utility/Lettore.py`; questa finestra e' **dove va il video**, e cambiare
dove non cambia nulla di quello che sta suonando.

E' il motivo per cui il passaggio a schermo intero non ferma niente: si
sposta il widget, non il playback.

I COLORI
--------
Vengono da `tema`, non da qui.  Il nero di fondo non e' una scelta: e' il
colore che serve per guardare un video, e mettergli sopra il fondo della
finestra farebbe vedere i bordi del video.  Tutto il resto — i comandi, la
barra in basso — prende il tema come il resto dell'app.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
# `QShortcut` sta in **QtGui**, non in QtCore.  In QtCore si importava e si
# otteneva:
#
#     ImportError: cannot import name 'QShortcut' from 'PyQt6.QtCore'
#
# e il sintomo era il peggiore possibile: il pulsante dello schermo intero
# c'era, si premeva, e **non succedeva niente**.  Perche' l'import e' dentro
# `_schermo_intero` e dentro il `try` che avvolge il clic, quindi l'errore
# diventava una riga di traceback in mezzo ai messaggi e la finestra sembrava
# semplicemente un pulsante rotto.
#
# Il traceback era la prova che il modulo non entrava, e pero' arrivava
# tardi e in mezzo al rumore.  Per questo l'import di un modulo che serve per
# un comando deve stare in cima al file, dove un errore si vede subito e non
# ha bisogno di essere interpretato.
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from SubViews.LettoreView import (
    _Bottone,
    _Cursore,
    _TastoRisoluzione,
    tempo_corto,
)
from Utility import tema
from Utility.Stuff import icon


class LettoreSchermo(QWidget):
    """Il video grande, a tutto schermo."""

    chiuso = Signal()
    #: Il video e' tornato dentro l'app: chi ascoltava rimette il widget
    #: dove stava prima
    rientrato = Signal()

    def __init__(self, padre=None) -> None:
        super().__init__(padre, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.Window)
        self.setWindowTitle("")
        self.setObjectName("schermo")
        self.setAutoFillBackground(True)
        # Lo schermo e' stato scelto a mano nelle impostazioni?  Se si', il
        # video va su quello e non su quello dove sta la finestra, e i
        # comandi non si vedono.  Vedi `_comandi_utili`.
        # La finestra da cui si e' partiti, per mettere a tutto schermo lo
        # schermo di quella e non il primario.  `guarda()` la riempe.
        self._finestra_app = None
        # Il conto alla rovescia che nasconde la riga quando il mouse si
        # ferma.  Nasce `None` e non un `QTimer` gia' pronto: il timer si crea
        # la prima volta che serve, e cosi' una finestra che non e' mai stata
        # mostrata non ha un timer che gira senza motivo.  Vedi
        # `_riaccendi_la_pausa`.
        self._timer_comandi = None
        # Il nero pieno: e' il colore che serve per guardare un video, e non
        # il fondo della finestra perche' con quello si vedrebbe la finestra
        # stessa intorno al video.
        paletta = self.palette()
        paletta.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(paletta)

        self.video = QVideoWidget(self)
        # `Qt.AspectRatioMode` e NON `QVideoWidget.AspectRatioMode`: in PyQt6 il primo
        # esiste e il secondo no — misurato, `hasattr` restituisce False.  Con
        # il secondo la sezione non si costruisce e la finestra non parte, che
        # e' il modo piu' rumoroso di sbagliare una riga.
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video.setObjectName("videoSchermo")

        # La riga sotto: quando il mouse si ferma sopra compare, quando va
        # via sparisce.  Sempre visibile sarebbe un bianco sopra il video per
        # tutto il tempo, e su un video scuro copre quello che si sta
        # guardando.
        self._comandi = QWidget(self)
        self._comandi.setObjectName("comandiSchermo")
        self._comandi.setVisible(False)
        disposizione = QVBoxLayout(self._comandi)
        disposizione.setContentsMargins(16, 10, 16, 16)
        disposizione.setSpacing(0)
        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(10)

        self.nome = QLabel("", self._comandi)
        self.nome.setObjectName("titolo")
        riga.addWidget(self.nome, 1)

        # I PULSANTI, CHE PRIMA NON C'ERANO
        # -----------------------------------
        # Qui c'era un contenitore `pulsanti` **vuoto**: nessun pulsante
        # dentro.  Quindi a schermo intero si vedeva il video e una riga con
        # il titolo e nient'altro - e senza nessun modo di tornare indietro
        # con il mouse.  La `Esc` funzionava, ma e' una scorciatoia: se il
        # video e' a schermo intero e il mouse non si muove, non c'e' niente
        # da premere.
        #
        # La riga di comando e' la stessa del lettore dentro l'app - play,
        # il tempo, chiudi - e non una versione ridotta: due elenchi di
        # comandi che non coincidono sono due cose che divergono.
        self.pulsante_play = _Bottone("play.fill", "Riproduci o ferma",
                                      self._comandi)
        self.pulsante_play.premuto.connect(self._commuta)
        riga.addWidget(self.pulsante_play, 0)

        # La risoluzione e il volume, anche qui.
        # -----------------------------------------
        # Sono gli stessi due pezzi che stanno nella barra del lettore dentro
        # l'app, presi dagli stessi posti: `_TastoRisoluzione` e `_Cursore` non
        # sono copie, e per questo il tasto si comporta uguale nelle due
        # finestre senza che nessuno debba ricordarselo.
        #
        # Prima qui non c'era niente di tutto questo: a schermo intero si
        # avevano play, il tempo e l'uscita, e nient'altro.  Ma a schermo
        # intero si guarda un video, e la risoluzione e il volume sono
        # esattamente le due cose che si cambiano mentre si guarda.
        self.pulsante_risoluzione = _TastoRisoluzione(self._comandi)
        self.pulsante_risoluzione.setVisible(False)
        self.pulsante_risoluzione.scelta.connect(self._cambiata_risoluzione)
        riga.addWidget(self.pulsante_risoluzione, 0)

        self.giacche = QLabel(self._comandi)
        self.giacche.setPixmap(icon("headphones", "#ffffff", 18).pixmap(18, 18))
        self.giacche.setFixedSize(22, 22)
        riga.addWidget(self.giacche, 0)

        self.volume = _Cursore(self._comandi)
        self.volume.setObjectName("volumeLettore")
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setMaximumWidth(90)
        self.volume.valueChanged.connect(self._volume)
        riga.addWidget(self.volume, 0)

        # `_Cursore` e non `QSlider`: anche qui il cursore si clicca e si
        # trascina, come in quello dentro l'app.
        self.posizione = _Cursore(self._comandi)
        # Lo stesso nome di oggetto del cursore del lettore dentro l'app:
        # una sola regola nel foglio di stile per tutti, e il colore non puo'
        # essere diverso da quello che l'utente vede due secondi prima.
        self.posizione.setObjectName("barraLettore")
        self.posizione.setRange(0, 0)
        riga.addWidget(self.posizione, 1)

        self.durata = QLabel("0:00", self._comandi)
        self.durata.setObjectName("nota")
        riga.addWidget(self.durata, 0)

        # IL TASTO PER USCIRE, E DEVE ESSERE CHIARO
        # -----------------------------------------
        # Era un `stop.fill`, che e' una X piccola e sta in fondo a destra:
        # presente, ma non si capiva che cosa fosse.  A schermo intero e' il
        # comando piu' importante che c'e' — e' l'unico modo di tornare
        # dentro l'app senza la tastiera — quindi non puo' essere un glifo
        # che si confonde con una decorazione.
        #
        # Il pulsante e' piu' grande degli altri, e porta lo stesso simbolo
        # di quello che ha fatto entrare: e' l'unico file che c'e'
        # (`fullscreen.svg`, dato dall'utente), e il simbolo di macOS per le
        # frecce verso l'interno non ha un file disegnato.  Inventarne uno
        # avrebbe significato un'icona diversa dal resto del programma, e in
        # questo progetto le icone non si inventano — quindi e' lo stesso
        # glifo, e la differenza la fa la misura e la scritta che spiega
        # che cosa fa.
        #
        # La X diceva "chiudi", che a schermo intero non e' quello che sta
        # succedendo: il video continua, si esce dalla modalita'.  Per questo
        # il simbolo non puo' essere una X.
        self.pulsante_chiudi = _Bottone(
            "arrow.up.left.and.arrow.down.right",
            "Torna dentro l'app", self._comandi, lato=32)
        self.pulsante_chiudi.premuto.connect(self.chiudi)
        riga.addWidget(self.pulsante_chiudi, 0)

        disposizione.addLayout(riga)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.setSpacing(0)
        esterno.addWidget(self.video, 1)
        esterno.addWidget(self._comandi, 0)

        # Il mouse fermo: dopo un po' che non si muove, i comandi spariscono.
        # Non e' una comodita', e' la ragione per cui si guarda un video
        # intero: con i comandi sempre addosso coprono quello che si sta
        # guardando.
        # I COMANDI VENGONO COLLEGATI AL MOTORE
        # ---------------------------------------
        # Qui sotto c'era tutto pronto e **collegato a niente**: la funzione
        # `_collega_motore` esisteva ma nessuno la chiamava.  Quindi la riga
        # di comando mostrava il video e non piu' niente che cambiasse: il
        # tempo fermo a 0:00, il cursore fermo a sinistra e il pulsante che
        # mostrava sempre la freccia di play mentre il video andava.
        #
        # E' il terzo difetto dello stesso genere in una sessione — dopo
        # `setIcon` su una classe che non lo ha e il collegamento del
        # segnale nella sezione sbagliata.  Il motivo e' sempre lo stesso: una
        # funzione nuova che scrive e non viene chiamata **non da' nessun
        # errore**, e il sintomo e' "qualcosa non si aggiorna" senza che
        # nessuno dica dove.
        #
        # Percio' qui la chiamata c'e' subito, e `controllo.py` controlla che
        # i metodi scritti vengano usati.
        self._collega_motore()

        self._tasto_chiusura = QShortcut(QKeySequence("Esc"), self,
                                         activated=self.chiudi)
        self._tasto_spazio = QShortcut(QKeySequence("Space"), self,
                                       activated=self._commuta)
        self._tasto_f = QShortcut(QKeySequence("F"), self,
                                  activated=self._commuta_schermo)
        self._tasto_sinistra = QShortcut(QKeySequence("Left"), self,
                                         activated=self._indietro)
        self._tasto_destra = QShortcut(QKeySequence("Right"), self,
                                        activated=self._avanti)

    def _collega_motore(self) -> None:
        """I comandi ascoltano lo stesso motore del lettore dentro l'app.

        E' l'unico player di tutta l'app, quindi qui non se ne crea un altro:
        si ascolta quello.  Se i due ascoltassero cose diverse, il play
        dello schermo intero e quello della sezione sarebbero due comandi
        che dicono cose diverse sullo stesso video.
        """
        from Utility.Lettore import motore as il_motore

        self.motore = il_motore()
        self.motore.mosso.connect(self._mosso)
        self.motore.stato.connect(self._stato)
        self.posizione.sliderMoved.connect(self._spostato)

    def _mosso(self, posizione: int, durata: int) -> None:
        self.posizione.setRange(0, durata // 1000 if durata > 0 else 0)
        self.posizione.blockSignals(True)
        self.posizione.setValue(posizione // 1000)
        self.posizione.blockSignals(False)
        self.durata.setText(tempo_corto(posizione, durata))

    def _stato(self, suona: bool, c_e_video: bool) -> None:
        self.pulsante_play.set_glifo("pause.fill" if suona else "play.fill", 20)
        self.pulsante_play.setToolTip("Ferma" if suona else "Riproduci")
        # Il tasto della risoluzione c'e' solo se c'e' un video, come nella
        # barra dentro l'app.  La giacca e' l'audio, quindi sparisce quando
        # c'e' il video: e' la stessa regola, detta al contrario.
        self.pulsante_risoluzione.setVisible(c_e_video)
        self.giacche.setVisible(not c_e_video)

    def _volume(self, valore: int) -> None:
        self.motore.volume(valore / 100.0)

    def _cambiata_risoluzione(self, scelta: str) -> None:
        """Il cambio lo fa il motore, che sa la posizione e lo stato.

        Poi il tasto si rimette a posto con quello che il motore ha potuto
        usare davvero, che non e' sempre quello che e' stato chiesto: vedi
        `_TastoRisoluzione` e `Lettore.cambla_risoluzione`.
        """
        self.motore.cambla_risoluzione(scelta)
        self.pulsante_risoluzione.metti_voce(self.motore.voce())

    def _spostato(self, posizione: int) -> None:
        """Come dentro l'app: il cursore da' i secondi, il motore i
        millisecondi.  Senza la conversione trascinando si tornava sempre
        all'inizio."""
        self.motore.volta_alla_posizione(posizione * 1000)

    # ------------------------------------------------------------------

    def guarda(self, motore, finestra_app=None) -> None:
        """Accendi questo video e mettilo davanti a tutto.

        `finestra_app` e' la finestra da cui si e' partiti.  Serve per due
        cose, e senza si sbaglia: per mettere a tutto schermo **lo** schermo
        di quella finestra (prima si metteva sempre il primario, misurato),
        e per capire se il video e' su uno schermo diverso dal suo — dal
        quale dipende se i comandi si vedono o no.  Vedi `_comandi_utili`.
        """
        self.video.setParent(self)
        self.nome.setText(motore.titolo())
        motore.al_video(self.video)
        # Il tasto della risoluzione ha bisogno della voce di quello che sta
        # suonando, e si riempie qui e non in `_stato`: `_stato` arriva anche
        # quando cambia solo lo stato, e li' la voce non e' ancora quella
        # giusta.  Se si riempisse li', il menu offrirebbe le risoluzioni del
        # video precedente.
        self.pulsante_risoluzione.metti_voce(motore.voce())
        self._finestra_app = finestra_app
        # LA FINESTRA NASCE DOPO, E QUINDI NON SENTIRA' `stato`
        # -----------------------------------------------------------
        # Questa finestra viene creata quando l'utente preme il tasto del tutto
        # schermo, e cioe' **dopo** che il video e' partito.  Il motore ha
        # gia' emesso `stato` a quel punto, e non lo riemette: quindi questa
        # finestra, che si collega al segnale dopo, non lo riceve **mai**.
        #
        # Il costo non era che mancasse un tasto: era che la faccia dei comandi
        # era quella di prima.  Misurato: con il video che suonava, il tasto
        # della risoluzione era invisibile e a geometria (0, 0, 28, 28), cioe'
        # mai messo in fila, e il pulsante play mostrava la freccia di play con
        # la scritta «Riproduci» mentre il video andava.
        #
        # Quindi qui si chiede lo stato **al motore**, una volta, e si applica:
        # e' l'unico modo che ha una finestra nata tardi di essere giusta al
        # primo frame, senza aspettare che succeda qualcosa.
        self._stato(motore.sta_suonando(), motore.e_video())
        self._sul_monitor_giusto(finestra_app)
        # I comandi appaiono subito, e non al primo movimento del mouse: se
        # aspettassero il mouse, chi ha aperto il video con la tastiera o con
        # un telecomando resterebbe senza comandi e dovrebbe muovere il
        # mouse per trovarli.  E se la finestra dell'app sta su un altro
        # schermo, la riga non si mostra: sarebbe dall'altra parte del tavolo.
        #
        # La domanda «stanno sullo schermo che guardo?» la fa `_comandi_utili`,
        # confrontando le due finestre.  Non c'e' piu' nessun `_schermo_fisso`:
        # rispondeva a un'altra domanda, e la risposta era sbagliata.
        self._comandi.setVisible(self._comandi_utili())
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    # Qui prima c'era anche `_schermo_dalle_impostazioni`, che leggeva lo
    # schermo salvato nelle impostazioni e lo confrontava con i nomi dei
    # schermi.  Era una **copia** di quello che fa `Utility/Schermi`, che e'
    # il posto unico: due copie di «quale schermo hai scelto» divergono, e
    # quando divergono la finestra va a schermo intero dove non deve.
    #
    # Non l'ho tenuto perche' era diventato inutile: serviva solo per il
    # `_schermo_fisso`, e `_schermo_fisso` e' sparito con `_comandi_utili`,
    # che ora confronta le due finestre e non ha bisogno di sapere cosa e'
    # stato impostato.  `controllo.py` lo segnalava come «scritto ma nessuno
    # lo chiama», che e' esattamente il caso.

    def _comandi_utili(self) -> bool:
        """I comandi sono sullo schermo che si sta guardando?

        LA DOMANDA VERA, E NON QUELLA CHE SI FACEVA PRIMA
        -------------------------------------------------
        Prima la risposta era «no se nelle impostazioni c'e' uno schermo
        scelto», e la domanda vera era un'altra: «questa finestra e la finestra
        dell'app sono sullo stesso schermo?».

        Sono due cose diverse, e con un solo schermo scelto la prima risposta
        era sbagliata **sempre**: scegliere lo schermo secondario non vuol dire
        che questa finestra sia su quello.  Dopo che il tasto del tutto schermo
        riporta il video dentro l'app, questa finestra si apre sullo **stesso**
        schermo dell'app — quindi la riga dei comandi e' proprio dove l'utente
        sta guardando, e nasconderla non aveva nessuna logica.

        Il costo era che la riga non compariva mai, e con lei il tasto della
        risoluzione: il tasto c'era, era costruito, era collegato, e non si
        vedeva.

        PERCHE' SI CONFRONTANO I DUE SCHERMI E NON UN SEGNO
        ----------------------------------------------------
        Prima la risposta veniva da `_schermo_fisso`, che stava per «e' stato
        scelto uno schermo»: un fatto impostato, non una posizione.  Qui si chiede a Qt «dove sta questa finestra» e
        «dove sta quella», e si confrontano: e' il posto dove si guarda.  Se
        un domani la finestra dell'app viene spostata sull'altro schermo, la
        risposta cambia da sola e non c'e' nessun segno da tenere allineato a
        mano.

        E se non si puo' rispondere — non c'e' piu' finestra dell'app, perche'
        e' stata chiusa — i comandi si mostrano.  Meglio una riga in piu' che
        un controllo che non c'e': senza finestra dell'app non c'e' nemmeno
        l'altro schermo da guardare.
        """
        app = getattr(self, "_finestra_app", None)
        if app is None:
            return True
        try:
            qui = self.window().screen()
            li = app.window().screen()
        except (AttributeError, RuntimeError):
            return True
        if qui is None or li is None:
            return True
        return qui == li

    def _scegli_schermo(self, finestra_app=None):
        """Lo schermo su cui mettere la finestra a tutto schermo.

        Non sta qui: e' in `Utility/Schermi`, perche' anche le immagini hanno
        bisogno di questa scelta e la logica deve essere una sola.  Vedi la
        nota di quel modulo, che spiega anche il difetto che c'era prima: il
        tutto schermo finiva sempre sullo schermo principale, anche quando la
        finestra dell'app era sull'altro.
        """
        from Utility import Schermi

        return Schermi.per_il_video(finestra_app)

    def _sul_monitor_giusto(self, finestra_app=None) -> None:
        """Mette la finestra a **vero** schermo intero sullo schermo scelto.

        TRE COSE SERVONO, E DA SOLA UNA NON BASTA
        -----------------------------------------
        1.  `windowHandle().setScreen(...)`: e' questo, in Qt, il modo per
            dire a una finestra «vai su quello schermo».  Senza, Qt la mette
            sullo schermo principale e basta: `setGeometry` da solo sposta un
            rettangolo, non cambia schermo, e con due monitor la finestra
            finisce a schermo intero sul primario anche se il rettangolo dice
            un'altra cosa.
        2.  `schermo.geometry()` e NON `availableGeometry()`: un vero schermo
            intero e' tutto il monitor.  `availableGeometry()` si ferma dove
            finisce la barra dei menu o il pannello, quindi la finestra
            sembrerebbe a schermo intero senza esserlo, e con una barra in
            alto resta una striscia grigia sopra il video.
        3.  Rimettere il tutto **dopo** `showFullScreen()`: la finestra deve
            gia' esistere per avere un handle, e `showFullScreen()` rimette il
            proprio schermo.  Quindi si richiama dopo, con un rinvio di zero
            millisecondi.

        La terza e' la cosa che si vede: senza, la finestra appare sul
        primario per un attimo e poi salta sull'altro schermo.
        """
        from PyQt6.QtCore import QTimer

        schermo = self._scegli_schermo(finestra_app)
        if schermo is None:
            return
        self._schermo_apertura = schermo
        # `winId()` crea la finestra, quindi l'handle: senza, `windowHandle()`
        # restituisce None e `setScreen` non viene chiamato.  Una richiesta
        # sola, non un costo.
        self.winId()
        maniglia = self.windowHandle()
        if maniglia is not None:
            maniglia.setScreen(schermo)
        self.setGeometry(schermo.geometry())
        QTimer.singleShot(0, lambda s=schermo: self._rimetti_a_intero(s))

    def _rimetti_a_intero(self, schermo) -> None:
        """La finestra e' a schermo intero: si rimette sullo schermo giusto."""
        try:
            if not (self.isFullScreen() or self.isVisible()):
                return
            maniglia = self.windowHandle()
            if maniglia is not None:
                maniglia.setScreen(schermo)
            if self.geometry() != schermo.geometry():
                self.setGeometry(schermo.geometry())
        except RuntimeError:
            # Finestra distrutta nel frattempo: non c'e' piu' niente da mettere
            # sullo schermo, e non e' un errore.
            return

    def chiudi(self) -> None:
        """Torna dentro l'app."""
        self._comandi.setVisible(False)
        self.close()

    def _commuta(self) -> None:
        """Play e pausa, sullo stesso pulsante.

        IL PERCHE' DELLA VARIABILE `m`
        ------------------------------
        Nella prima versione, dopo che la funzione era stata rinominata da
        `Lettore` a `motore`, questa scriveva:

            m = motore()                              # l'oggetto
            if motore.player.playbackState() ...       # la FUNZIONE
            motore.sospendi()                         # la FUNZIONE

        cioe' tre righe su quattro usavano il nome della funzione invece
        dell'oggetto.  E non dava un errore appena si schiacciava il pulsante:
        dava `AttributeError: 'function' object has no attribute 'player'`
        dentro un segnale di Qt, quindi dentro C++, quindi la finestra
        chiudeva senza una riga di traceback.

        Il sintomo era "il play non funziona" e nient'altro.  Quattro nomi
        uguali — la classe, la funzione, il modulo e l'attributo — e la
        riga sbagliata non si vede leggendo.

        Percio' qui il motore si prende **una volta sola** in `m` e tutte le
        righe seguenti usano `m`.  Un nome non si riusa.
        """
        from PyQt6.QtMultimedia import QMediaPlayer

        from Utility.Lettore import motore

        m = motore()
        if m.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            m.sospendi()
        else:
            m.continua()

    def _commuta_schermo(self) -> None:
        """Schermo intero oppure la finestra, sulla stessa finestra."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _indietro(self) -> None:
        from Utility.Lettore import motore

        motore().volta_alla_posizione(motore().player.position() - 10000)

    def _avanti(self) -> None:
        from Utility.Lettore import motore

        motore().volta_alla_posizione(motore().player.position() + 10000)

    # QUANTO TEMPO IL MOUSE PUO' RESTARE FERMO PRIMA CHE LA RIGA SPARISCA
    # -------------------------------------------------------------------
    # Due secondi.  Erano tre e mezzo e la riga restava troppo addosso al
    # video: segnalato come «sparisce troppo lentamente».
    #
    # Il punto e' che adesso il tempo **non decide piu'** se si puo' cliccare:
    # la riga non sparisce comunque mentre il mouse e' sopra di lei, e li' il
    # conto non riparte nemmeno.  Quindi questo numero puo' essere breve senza
    # che torni il difetto di prima, che era un conto di un secondo e mezzo che
    # partiva dal clic e nascondeva la riga mentre il mouse ci andava sopra.
    #
    # La differenza rispetto a prima e' tutta qui: 1,5 s **senza** protezione
    # non permetteva di premere niente, 3,5 s **con** protezione era lenta.
    # Con la protezione, due secondi tengono le due richieste insieme: la riga
    # si vede abbastanza da leggere cosa c'e' scritto, e sparisce presto
    # quando il mouse non la sta cercando.
    PAUSA_MOUSE = 2000

    def event(self, evento) -> bool:
        """Il mouse: la riga compare, e sparisce quando il mouse si ferma.

        LA RIGA NON SPARISCE MENTRE IL MOUSE E' SU DI LEI
        --------------------------------------------------
        Prima spariva un secondo e mezzo dopo aver premuto qualcosa, e non
        guardava dove fosse il mouse.  Il risultato era che la riga dei
        comandi era **impossibile da usare**: si muoveva il mouse per farla
        comparire, si partiva verso il bottone, e al momento di arrivare la riga
        era gia' sparita — e se si premeva, spariva mentre il mouse era ancora
        sopra.

        Ora la riga si nasconde **solo se il mouse non e' sopra di lei**.  Il
        posto del mouse si chiede a Qt con `mapFromGlobal`, e non con gli
        eventi di entrata e uscita: quelli arrivano a raffica e in ritardo, e
        decidere con quelli e' quello che faceva sparire la riga mentre il
        mouse ci stava sopra.

        E ogni movimento del mouse **riaccende** il conto alla rovescia, che
        e' la cosa che l'utente chiedeva esplicitamente: la riga segue il
        mouse, e quando il mouse riparte la riga resta.
        """
        from PyQt6.QtCore import QEvent

        if evento.type() == QEvent.Type.MouseMove:
            if self._comandi_utili():
                self._comandi.setVisible(True)
                self._riaccendi_la_pausa()
        elif evento.type() in (QEvent.Type.MouseButtonPress,
                               QEvent.Type.Wheel):
            if self._comandi_utili():
                self._comandi.setVisible(True)
                self._riaccendi_la_pausa()
        elif evento.type() == QEvent.Type.MouseButtonRelease:
            # Dopo la pressione la riga non sparisce subito: l'utente sta
            # ancora guardando dove ha premuto, e sparisirgliela subito sotto
            # gli occhi sembrerebbe che il programma abbia chiuso qualcosa.
            if self._comandi_utili():
                self._riaccendi_la_pausa()
        return super().event(evento)

    def _riaccendi_la_pausa(self) -> None:
        """Ricomincia il conto prima che la riga sparisca.

        Il conto non riparte da capo se il mouse e' sopra la riga: in quel caso
        la riga non sparisce affatto, e ripartire da capo ogni volta significherebbe
        che basta un movimento di un millimetro sopra un bottone per nasconderlo
        mentre lo si sta per premere.
        """
        from PyQt6.QtCore import QTimer

        if self._timer_comandi is None:
            self._timer_comandi = QTimer(self)
            self._timer_comandi.setSingleShot(True)
            self._timer_comandi.timeout.connect(self._nascondi_se_il_mouse_e_fuori)
        self._timer_comandi.start(self.PAUSA_MOUSE)

    def _nascondi_se_il_mouse_e_fuori(self) -> None:
        """Sparisce solo se il mouse non e' sopra la riga.

        IL PUNTO DEL MOUSE VA CONFRONTATO CON `rect()`, NON CON `geometry()`
        --------------------------------------------------------------
        Qui c'era un difetto, e la riga spariva **anche con il mouse sopra**.
        Motivo: `mapFromGlobal` su un widget **figlio** traduce la posizione
        dello schermo in coordinate **del figlio**, non della finestra.

        Misurato: mouse a 600, 665 sullo schermo, la riga che sta da y=642 —
        `mapFromGlobal` dava `600, 23` (dentro la riga, che e' 58 alta) e
        `geometry()` dava `0, 642, 1200, 58`.  Il confronto era fra due
        sistemi di coordinate diversi, e dava sempre falso: la riga spariva
        sempre, come prima.

        Il confronto giusto e' con `rect()`, che e' la riga nelle sue coordinate
        — cioe' da 0,0 — ed e' quello che `mapFromGlobal` produce.

        Non si usa `underMouse()` perche' risponde a events come il ratto: se la
        riga fosse una finestra a parte, il mouse puo' essere sopra di lei e
        `underMouse()` dire di no.
        """
        from PyQt6.QtGui import QCursor

        if not self._comandi_utili():
            return
        if self.isVisible() and self._comandi.isVisible():
            if self._comandi.rect().contains(
                    self._comandi.mapFromGlobal(QCursor.pos())):
                # Il mouse e' sulla riga: la riga resta.  E il conto non
                # riparte, cosi' non si mette a correre mentre il mouse e' li'.
                return
        self._comandi.setVisible(False)

    def closeEvent(self, evento) -> None:
        # Chiudere la finestra non ferma l'audio: l'utente puo' voler chiudere
        # il video e tenere la musica.  Il video pero' torna indietro, perche'
        # un widget che resta attaccato a una finestra nascosta non si vede
        # piu' e non lo si puo' rimettere dentro.
        self._comandi.setVisible(False)
        self.rientrato.emit()
        super().closeEvent(evento)