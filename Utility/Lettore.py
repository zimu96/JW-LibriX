#
#  Utility/Lettore.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il motore di riproduzione: UN player per tutta l'app.

PERCHE' UN SOLO PLAYER E NON UNO PER SCHERMATA
-----------------------------------------------
Il lettore piccolo in fondo e il lettore grande dentro la sezione Media
mostrano la stessa cosa: se avessero due `QMediaPlayer`, passare dall'uno
all'altro cambierebbe quello che sta suonando, e per sapere "che cosa sta
suonando adesso" servirebbero due stati da tenere allineati a mano.

Qui c'e' un player solo.  Il video e' un `QVideoWidget` che **si sposta** da
un widget all'altro — dentro la sezione Media, dentro la finestra a tutto
schermo, dentro la striscia in fondo — senza che il playback si interrompa.
`QVideoWidget` si puo' cambiare genitore mentre suona: e' quello che rende
possibile il passaggio a schermo intero senza fermare e ripartire da capo.

QUANDO IL PLAYER E' STATO CREATO
--------------------------------
`Lettore()` va chiamato **dopo** che esiste la `QApplication`, e il primo
uso lo crea.  Perche' non in cima al file: `QMediaPlayer` e' un oggetto con
un backend che va inizializzato, e costruirlo all'import del modulo
significherebbe che basta importarlo per far fallire l'avvio — che e' esattamente
la trappola che `WebBrowserView.py` ha gia' scritto per `QtWebEngine`.

PERCHE' GLI STREAMING SONO FILE COMUNI
--------------------------------------
Un video in streaming e' un file .mp4 con un indirizzo.  Il server non
invia "streaming" in un modo particolare: `progressiveDownloadURL` da' un
.mp4 che si puo' scaricare intero, e quindi si puo' anche suonare
dall'indirizzo.  Percio' qui non si distingue fra streaming e file: si
distingue solo fra **indirizzo di rete** e **percorso sul disco**, e il
motore mette dentro `QUrl` l'uno o l'altro.  Un lettore che facesse paging o
buffering per l'uno e non per l'altro sarebbe due lettori.

PERCHE' IL VOLUME STA SU `QAudioOutput`
---------------------------------------
In Qt 6 il volume non e' del player: e' dell'uscita audio.  Cercarlo su
`QMediaPlayer` non da' niente — misurato: `QMediaPlayer.setVolume` non
esiste — e il sintomo sarebbe un cursore che si muove e un volume che non
cambia.  Per lo stesso motivo il mute sta li'.

I SOTTOTITOLI: QUELLO CHE C'E' E QUELLO CHE NON C'E'
----------------------------------------------------
`QMediaPlayer` conosce i sottotitoli **dentro** il file (`subtitleTracks()` e
`setActiveSubtitleTrack(indice)`), e non sa caricare un file .vtt a parte.

Il mediator manda i sottotitoli come indirizzo separato — misurato, il
campo `subtitles` dentro ogni risoluzione — quindi **non** si possono
aggiungere a un mp4 con questa API.  Non si finge: il pulsante dei
sottotitoli esiste e funziona quando il file li ha dentro, e quando non li
ha resta spento e il tooltip lo dice.  Un pulsante che si preme e non
succede niente e' peggio di un pulsante che non c'e'.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QObject, QUrl, pyqtSignal as Signal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

#: L'unico motore di tutta l'app.  Non e' un modulo con una variabile: e' un
#: oggetto, perche' un `QMediaPlayer` costruito e abbandonato lascia il
#: backend attaccato, e crearne uno nuovo per ogni chiamata aprirebbe una
#: porta di uscita audio nuova ogni volta.
_motore: Lettore | None = None


def motore() -> Lettore:
    """Il motore unico, creato alla prima chiamata.

    IL NOME NON E' `Lettore` PER UN MOTIVO MISURATO
    ----------------------------------------------
    La prima versione si chiamava `Lettore`, come la classe.  Il risultato e'
    che `from Utility.Lettore import Lettore` porta dentro **la funzione**, e
    `Lettore()` costruisce un motore che sembra di essere `Lettore`:

        AttributeError: type object 'Lettore' has no attribute 'Lettore'

    Perche' e' successo tre volte in una sessione, sempre con lo stesso
    errore, e sempre in una riga di prova.  Due nomi uguali nello stesso
    file sono la trappola classica del Python: la classe viene dopo la
    funzione, quindi il nome `Lettore` nel file indica due cose diverse a
    seconda di dove lo si guarda.

    `motore()` e' anche il nome giusto per quello che e': e' il motore di
    riproduzione, e non "un lettore".
    """
    global _motore
    if _motore is None:
        _motore = Lettore()
    return _motore


class Lettore(QObject):
    """Un player, uno solo, che chiunque puo' guidare."""

    #: Il video e' partito da un file che si puo' mettere a schermo intero:
    #: (percorso o indirizzo)
    #: Vuoto quando non si sta guardando un video: e' la finestra a schermo
    #: intero che decide se ha senso, e senza video non avrebbe niente da
    #: mostrare.
    video = Signal(str)
    #: Non c'e' niente da mostrare: la finestra a schermo intero si chiude
    vuoto = Signal()
    #: Cambia la posizione, in millisecondi: (posizione, durata)
    #: La durata arriva -1 finche' il server non ha mandato il header, e va
    #: detto cosi': un cursore che parte da "0 secondi" e resta li' sembra
    #: un video fermo.
    mosso = Signal(int, int)
    #: Cambia lo stato: (sta_suonando, c'e'_un_video)
    stato = Signal(bool, bool)
    #: E' successo qualcosa che l'utente deve sapere
    problema = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.player = QMediaPlayer(self)
        self.uscita = QAudioOutput(self)
        self.uscita.setVolume(1.0)
        self.player.setAudioOutput(self.uscita)

        self._titolo = ""
        self._sorgente = ""
        self._sembra_video = False
        self._schermo_intero = False
        self._volume = 1.0
        self._taceto = False
        # La voce che sta suonando, e il riquadro che la mostra.  Servono al
        # cambio di risoluzione: per ricaricare a un'altra risoluzione si
        # riparte dalla stessa voce, e per la scelta automatica si misura il
        # riquadro dove il video sta davvero — che dentro l'app non e' quello
        # della finestra, e a schermo intero non e' nessuno dei due.
        self._voce: dict = {}
        self._dove_va_video = None
        # Dove tornare dopo un cambio di risoluzione, e se ripartire suonando.
        # Sono due numeri e non una posizione sola, perche' il ritorno al punto
        # avviene piu' tardi, quando Qt apre il file, e a quel momento il
        # player potrebbe gia' essere partito da solo.
        self._tornare_a = 0
        self._ripartire_suonando = False

        self.player.positionChanged.connect(self._mosso)
        self.player.durationChanged.connect(self._mosso)
        self.player.playbackStateChanged.connect(self._cambiato_stato)
        self.player.mediaStatusChanged.connect(self._stato_media)
        self.player.errorOccurred.connect(self._errore)

    # ------------------------------------------------------------------
    # COSA SUONARE
    # ------------------------------------------------------------------

    def suona(self, dove, titolo: str = "") -> None:
        """Metti dentro un file: un percorso sul disco o un indirizzo.

        :param dove: una voce con `url`, oppure un percorso, oppure un
            indirizzo.  Una voce del mediator o di `MepsAPI` ha `url` gia'
            pronto; per i file gia' scaricati si passa il percorso.

        LA SCELTA FRA FILE E INDIRIZZO
        ------------------------------
        `QUrl("percorso")` interpreta quello che ha scritto come un indirizzo,
        e `QUrl("a/b/c.mp4")` non trova niente perche' pensa che `a` sia il
        nome di un sito.  Per un file locale serve `fromLocalFile`, e per un
        indirizzo no.  La prova e' sul primo pezzo: `http` e `file` sono
        schemi, tutto il resto e' un percorso.

        IL FILE GIA' SCARICATO VINCE SEMPRE
        -------------------------------------
        Se di quella traccia c'e' un file sul disco, si suona **quello**, e non
        l'indirizzo che ha scritto il server.

        La ragione e' che l'utente l'ha scaricato: ha premuto la nuvoletta e
        si e' preso il file di proposito.  Ripartire dalla rete con lo stesso
        video sarebbe piu' lento, e su una connessione scarsa non partirebbe
        affatto.

        Prima succedeva il contrario, ed e' stato il difetto piu' fastidioso
        della sezione: il video scaricato si apriva, e il programma diceva
        che non era scaricato — perche' guardava solo se c'era il **pacchetto**
        della pubblicazione, e un video scaricato dalla nuvoletta e' un file
        sciolto (``wsb_I_02_r720P.mp4``), non un pacchetto.  Il file c'era,
        guardato nel posto sbagliato.

        Il cambio di risoluzione dal lettore continua a funzionare: quello
        cambia l'indirizzo e va in rete di proposito.
        """
        indirizzo = dove
        if isinstance(dove, dict):
            indirizzo = (dove.get("url") or dove.get("percorso") or "")
            titolo = titolo or dove.get("title") or ""
            locale = _file_scaricato(dove)
            if locale:
                indirizzo = locale
        if not indirizzo:
            self.problema.emit("Non so dove sia questo file.")
            return

        if str(indirizzo).startswith(("http://", "https://", "file://")):
            qurl = QUrl(str(indirizzo))
        else:
            # Un percorso che non esiste viene detto subito, invece di
            # partire e fermarsi con un codice che non spiega niente.
            if not os.path.isfile(str(indirizzo)):
                self.problema.emit(f"Il file non c'è: {indirizzo}")
                return
            qurl = QUrl.fromLocalFile(os.path.abspath(str(indirizzo)))

        self._titolo = titolo or Path_nome(indirizzo)
        self._sorgente = qurl.toString()
        # Se e' un video si decide **adesso**, dal file che l'utente ha
        # scelto, e non dopo.  Prima si chiedeva a `activeVideoTrack()`, che
        # vale 0 finche' il file non ha cominciato a girare: quindi il
        # pulsante dello schermo intero restava nascosto proprio quando
        # l'utente lo cercava, e compariva solo dopo qualche secondo.
        #
        # I due indizi sono i mimetype e la risoluzione, che sono gia' nella
        # voce: non si aspetta il server per dire se una cosa e' un video.
        # E se il pulsante sbaglia, la finestra a schermo intero si apre
        # nera — che e' peggio che non averlo.
        self._sembra_video = _sembra_video(dove)
        # La voce si ricorda **copiata**: quella che arriva da fuori e' la
        # stessa che sta sulla riga della lista, e il cambio di risoluzione ci
        # scrive dentro.  Senza la copia, scegliendo 720p cambierebbe anche la
        # riga da cui si e' partiti, e la lista mostrerebbe una risoluzione
        # diversa da quella che sta girando.
        self._voce = dict(dove) if isinstance(dove, dict) else {}
        self.player.setSource(qurl)
        self.player.play()
        # Lo stato si annuncia **subito**, senza aspettare che il player
        # apra il file.
        #
        # Prima si aspettava che lo emettesse `playbackStateChanged`, e il
        # player emette lo stato ma `videoTracks()` e' ancora vuoto: quindi il
        # lettore riceveva "non c'e' video" e il pulsante dello schermo
        # intero restava nascosto.  Il pulsante compariva solo dopo qualche
        # secondo, e solo se un'altra cosa faceva ridisegnare la riga.
        #
        # Il pulsante e' l'unico modo che l'utente ha di mettere a schermo
        # intero: se non c'e' quando serve, non c'e'.  Percio' si decide con
        # quello che si sa gia' del file scelto — mimetype, risoluzione,
        # estensione — che sono dati veri, e non con una domanda fatta al
        # player che risponde tardi.
        self.stato.emit(True, self._sembra_video or self._e_video())

    def ferma(self) -> None:
        """Ferma e svuota."""
        self.player.stop()
        self.player.setSource(QUrl())
        self._titolo = ""
        self._sorgente = ""
        # Anche la voce sparisce: se resta, il tasto della risoluzione
        # offrirebbe i file del video di prima mentre non e' suonando niente.
        self._voce = {}
        # E il punto a cui tornare sparisce con lei: se il video successivo
        # finisse quello che si stava guardando, ricomincerebbe da meta'.
        self._tornare_a = 0
        # Anche l'indizio del file sparisce: senza, il player si ricorda le
        # tracce del video di prima per qualche secondo e un brano che parte
        # subito dopo viene scambiato per un video.
        self._sembra_video = False
        self.stato.emit(False, False)
        self.vuoto.emit()

    def continua(self) -> None:
        self.player.play()

    def sospendi(self) -> None:
        self.player.pause()

    def volta_alla_posizione(self, posizione: int) -> None:
        self.player.setPosition(max(0, posizione))

    def al_video(self, widget) -> None:
        """Il video esce su questo widget.

        Chiamarlo quando il video sta gia' su un altro widget **sposta** il
        video: e' il meccanismo che fa andare e tornare dallo schermo
        intero senza fermare la riproduzione.
        """
        self._dove_va_video = widget
        if widget is None:
            self.player.setVideoOutput(None)
            return
        self.player.setVideoOutput(widget)
        if self._sorgente:
            self.video.emit(self._sorgente)

    # ------------------------------------------------------------------
    # IL CAMBIO DI RISOLUZIONE
    # ------------------------------------------------------------------

    def voce(self) -> dict:
        """La voce che sta suonando, con tutte le sue risoluzioni.

        Va restituita **copiata** perche' il chiamante ne fa il menu e la
        mette in una riga: se la cambiasse, cambierebbe anche quello che sta
        suonando.  Il menu non ha bisogno di scriverci, quindi una copia va
        bene, ed e' quella che protegge.
        """
        return dict(self._voce)

    def cambla_risoluzione(self, scelta: str) -> bool:
        """Riparti con il video a un'altra risoluzione.  True se e' partito.

        LA SCELTA SI RICORDA, E IL TASTO LA MOSTRA
        ------------------------------------------
        La scelta si scrive subito in `impostazioni.json`: e' quello che
        l'utente sta dicendo («i video guardali cosi'»), e deve valere anche
        per il prossimo video.  Senza, il tasto ripartirebbe da automatico ogni
        volta e la scelta sarebbe buona solo per un filmato.

        DOVE SI TORNA
        -------------
        Cambio di risoluzione vuol dire un file diverso, quindi `setSource` da
        capo: non si puo' cambiare risoluzione a meta'.  E meta' era un posto
        preciso, cosi' si torna a quel punto, e non all'inizio.  La posizione si
        legge **prima** di cambiare la sorgente, perche' dopo `setSource` non
        c'e' piu' niente da leggere.

        E si torna anche fermo o in riproduzione com'era: cambiare risoluzione
        mentre si guarda non e' mettere in pausa, e un video che riparte
        giocando quando era fermo fa pensare che il tasto sia un play.

        PERCHE' IL RITORNO VA RIMESSO DENTRO
        ---------------------------------------
        `setPosition` su un player che non ha ancora aperto il file viene
        ignorato da Qt, e il video riparte dall'inizio.  Quindi la posizione si
        rimette **quando il file e' aperto**, e non subito: lo dice
        `mediaStatus` con `LoadedMedia`, che e' il momento in cui Qt accetta la
        posizione.
        """
        if not self._voce:
            return False
        from Utility import tema
        tema.salva_risoluzione_video(scelta)

        larghezza = self._larghezza_del_riquadro()
        try:
            from Utility import Mediator
            nuova = Mediator.scegli_risoluzione(dict(self._voce),
                                                larghezza, scelta)
        except Exception:  # noqa: BLE001
            # Se la scelta non si puo' calcolare si lascia com'era: meglio il
            # video che si sta guardando che un errore e una finestra vuota.
            return False
        if nuova.get("url") == self._voce.get("url"):
            # Stesso file: non si tocca niente, e non si riparte da capo per
            # niente.  Scegliere la risoluzione che si sta gia' guardando
            # capita ogni volta, e deve sembrare quello che e': un tasto che
            # premuto non fa niente.
            return False

        posizione = self.player.position()
        suonava = (self.player.playbackState()
                   == QMediaPlayer.PlaybackState.PlayingState)
        # Il ritorno al punto lo rimette `_tornato_qui`, quando Qt apre il
        # file; qui si prepara e basta.
        self._tornare_a = posizione
        self._ripartire_suonando = suonava
        self._voce = nuova
        self.player.setSource(QUrl(str(nuova.get("url") or "")))
        if suonava:
            self.player.play()
        else:
            self.player.pause()
        # Il nuovo indirizzo e' noto: si annuncia, cosi' il tasto della
        # risoluzione mette la spunta su quello giusto senza aspettare.
        self.video.emit(self.player.source().toString())
        return True

    def _larghezza_del_riquadro(self) -> int:
        """Quanto e' largo il riquadro che mostra il video, in pixel.

        Se il riquadro non c'e' ancora — cioe' il video non e' ancora partito —
        si restituisce 0, e la scelta automatica prende la piu' piccola: il
        comportamento di quando non si sa ancora quanto sara' grande.
        """
        riquadro = self._dove_va_video
        if riquadro is None:
            return 0
        try:
            return int(riquadro.width())
        except (AttributeError, TypeError, ValueError):
            return 0

    def _tornato_qui(self) -> None:
        """Il file e' aperto: si torna al punto di prima, e si suona o no."""
        if not getattr(self, "_tornare_a", 0):
            return
        dove = self._tornare_a
        self._tornare_a = 0
        self.player.setPosition(dove)
        if not getattr(self, "_ripartire_suonando", False):
            self.player.pause()

    # ------------------------------------------------------------------
    # IL VOLUME
    # ------------------------------------------------------------------

    def volume(self, valore: float) -> None:
        """Il volume, da 0 a 1.

        Sta su `QAudioOutput` e non sul player: in Qt 6 il volume e' della
       uscita.  Cercarlo sul player non da' niente, misurato.
        """
        self._volume = max(0.0, min(1.0, valore))
        self.uscita.setVolume(self._volume)

    # ------------------------------------------------------------------
    # COSA C'E' DENTRO
    # ------------------------------------------------------------------

    def sta_suonando(self) -> bool:
        """In questo momento il player sta riproducendo?

        Serve a chi apre una finestra **dopo** che la riproduzione e' partita:
        il segnale `stato` e' gia' passato e non arriva a chi e' nato dopo, e
        senza chiedere qui una finestra appena aperta direbbe «Riproduci» con
        un video che invece sta andando.  Vedi `LettoreSchermo.guarda`.
        """
        return (self.player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState)

    def e_video(self) -> bool:
        """Il file corrente e' un video?

        MISURATO SU Qt 6.11.2
        ---------------------
        `activeVideoTrack()` resta a **0** anche mentre un video sta
        suonando, quindi non si puo' usare per decidere se mostrare il
        pulsante dello schermo intero: prima lo usavo e il pulsante non
        compariva mai, e perche' compariva non compariva.

        Quello che dice la verita' e' `videoTracks()`: con un video dentro
        restituisce una lista con un pezzo, con un brano solo audio una lista
        vuota.  Misurato su un video in riproduzione:

            activeVideoTrack:  0
            videoTracks():     [<QMediaMetaData ...>]      <- c'e' il video
            audioTracks():     1

        La terza fonte e' `_sembra_video`, che guarda il mimetype o la
        risoluzione della voce: utile **prima** che il file si apra, quando
        `videoTracks()` e' ancora vuoto e il pulsante deve gia' esserci.

        Un pulsante dello schermo intero che manca e' peggio di uno che
        sbaglia: quello che manca non si cerca e non si trova.
        """
        # Niente sorgente, niente video.  Il controllo c'e' perche' il player
        # continua a ricordare le tracce del file precedente per qualche
        # secondo dopo che gli e' stato dato un indirizzo vuoto: quindi un
        # brano avviato subito dopo un video si dichiarava un video, e la
        # striscia in fondo — che e' solo per l'audio — non compariva.
        #
        # Il sintomo era che la striscia restava nascosta e l'audio non si
        # poteva fermare: la riga c'era, il titolo c'era, e il pezzo che
        # dice "e' un video" si sbagliava.
        if not self._sorgente:
            return False
        if self.player.videoTracks():
            return True
        return self._sembra_video

    def _e_video(self) -> bool:
        return bool(self.player.activeVideoTrack())

    def titolo(self) -> str:
        return self._titolo

    def sorgente(self) -> str:
        return self._sorgente

    # ------------------------------------------------------------------
    # I SEGNALI
    # ------------------------------------------------------------------

    def _mosso(self, _valore=None) -> None:
        self.mosso.emit(self.player.position(), self.player.duration())

    def _cambiato_stato(self, _stato=None) -> None:
        """Il player e' cambiato stato: si rilava il pulsante dello schermo intero.

        QUI C'ERA IL DIFETTO, E L'HO MISURATO
        --------------------------------------
        Questo segnale emetteva `self._e_video()`, cioe' solo
        `activeVideoTrack()`, che su Qt 6.11.2 resta a **0** anche con un
        video che gira.  Quindi arrivava "non c'e' video" e il lettore
        nascondeva il pulsante dello schermo intero.

        Il sintomo era strano perche' andava e tornava: `suona()` lo mostrava
        subito, subito dopo questo segnale lo nascondeva, e due secondi dopo un
        altro segnale lo rimostrava.  Un pulsante che accende e spegne da
        solo sembra un programma che non sa se il video c'e'.

        Ora la domanda ha **un posto solo** dove e' scritta, `e_video()`, e
        tutti i segnali usano quella.  Il pulsante non può piu' dipendere da
        quale segnale e' arrivato per primo.
        """
        self.stato.emit(
            self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
            self.e_video())

    def _stato_media(self, stato) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer as _P

        if stato == _P.MediaStatus.LoadedMedia:
            # Il file e' aperto: e' l'unico momento in cui Qt accetta una
            # posizione.  Prima di questo, `setPosition` su un file che non e'
            # ancora aperto viene ignorato e il video riparte dall'inizio.
            # Vedi `cambla_risoluzione`.
            self._tornato_qui()
            return

        if stato == _P.MediaStatus.EndOfMedia:
            # A fine brano il motore si ferma e si svuota, come con la X:
            # in pausa all'inizio restava carico, e la striscia piccola
            # continuava a mostrare un brano che non suona piu'.
            self.ferma()

    def _errore(self, errore, testo=""):
        # Il testo che Qt da e' in inglese e dentro ce n'e' di tecnico.  Si
        # dice cosa e' successo in italiano e con il nome del file, che e'
        # l'unica cosa che all'utente serve per capire.
        del errore
        dove = self._titolo or self._sorgente or "quel file"
        if not testo:
            testo = "non si riesce a leggerlo"
        else:
            testo = str(testo)
            if ":" in testo:
                testo = testo.split(":", 1)[1].strip() or testo
        self.problema.emit(f"«{dove}»: {testo}.")


def _sembra_video(dove) -> bool:
    """Dalla voce o dal nome del file, questo e' un video?

    Tre indizi, in quest'ordine, e tutti gia' disponibili senza aspettare
    nessuno:

        il mimetype   `video/...` — il dato vero, quando c'e'
        la risoluzione `frameWidth` e `frameHeight` — un video ha sempre due
                      lati e un audio non li ha mai
        l'estensione  `.mp4`, `.webm`, `.mkv`, `.mov` — l'ultimo, e da solo

    L'estensione da sola non basta e non si usa da sola: un `.mp4` puo'
    contenere solo audio, e mostrare il pulsante dello schermo intero su un
    brano apre una finestra nera.
    """
    if isinstance(dove, dict):
        if (dove.get("mimetype") or "").lower().startswith("video/"):
            return True
        if dove.get("frameWidth") and dove.get("frameHeight"):
            return True
        return False
    return str(dove).lower().rsplit("?", 1)[0].endswith(
        (".mp4", ".webm", ".mkv", ".mov", ".m4v"))


def _file_scaricato(voce: dict) -> str:
    """Il file di quella traccia che e' sul disco, o stringa vuota.

    LA VOCE, E NON IL PERCORSO
    --------------------------
    Chi chiama `suona` con una voce ha gia' dentro l'indirizzo del server, e
    quasi sempre l'indirizzo c'e'.  Ma se il video e' stato scaricato con la
    nuvoletta della card, l'indirizzo c'e' **e** il file c'e', e la domanda
    giusta non e' «posso arrivare a questo file?» — arrivo, anche dalla rete —
    ma «ho gia' questo file qui?».

    TRE CAMPI E NON UNO
    -------------------
    Servono sigla, lingua e traccia perche' `sigla_I` puo' avere piu' tracce:
    `wsb_I_01` e `wsb_I_02` sono due video diversi della stessa pubblicazione,
    e senza la traccia partirebbe sempre il primo.

    La lingua e' il **simbolo** (`I`), non il numero: e' cosi' che i nomi dei
    file sono scritti.  Vedi la nota di `HomeView._nuvoletta_da_mostrare`, che
    aveva gia' dovuto accorgersene.

    STRINGA VUOTA SE NON SI SA
    --------------------------
    Se la voce non porta questi campi non si cerca niente e si va con
    l'indirizzo: e' il comportamento di sempre, e va bene per tutto cio' che
    non e' un media scaricato (un articolo, un capitolo, un brano in rete).
    """
    from Utility import MediaScaricati

    sigla = str(voce.get("sigla") or voce.get("pubSymbol") or "")
    traccia = voce.get("traccia", voce.get("track"))
    if not sigla or traccia in (None, "", 0):
        return ""

    lingua = voce.get("lingua") or voce.get("language") or ""
    # LE TRACCE SONO TUTTE, NON UNA
    # ------------------------------
    # Il nome del file porta **tutti** i numeri della traccia: un video di
    # «Adorazione mattutina» si chiama `jwb_I_202104_02_r240P.mp4`, cioe' il
    # mese e il giorno.  Passando il primo dei due, `file_di` non trovava
    # niente e il video ripartiva dalla rete anche con il file sul disco: si
    # vedeva ricaricare un video gia' scaricato, e l'attesa sembrava un
    # download che non finisce.
    #
    # E' la stessa domanda che fa la nuvoletta della card, e va fatta con la
    # stessa funzione: due ricerche con due formati diversi darebbero due
    # risposte diverse sulla stessa domanda.
    tracce = voce.get("tracce")
    if isinstance(tracce, (list, tuple)) and tracce:
        scelte = list(tracce)
    else:
        try:
            scelte = [int(traccia)]
        except (TypeError, ValueError):
            # Una traccia scritta in un modo che non e' un numero non si cerca:
            # il nome del file la vuole con le cifre, e indovinarla sarebbe un
            # file che non esiste detto con sicurezza.
            return ""

    file = MediaScaricati.file_di(sigla, str(lingua).upper(), scelte)
    return str(file) if file is not None else ""


def Path_nome(indirizzo) -> str:
    """Il nome del file, da un percorso o da un indirizzo.

    Serve al titolo quando la voce non ne ha uno: dal percorso si prende
    l'ultimo pezzo, dall'indirizzo quello dopo l'ultima barra.  Non si
    indovina niente, si legge quello che c'e'.
    """
    testo = str(indirizzo).rstrip("/")
    nome = testo.rsplit("/", 1)[-1]
    return nome or testo