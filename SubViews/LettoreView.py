#
#  SubViews/LettoreView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il lettore grande, dentro la sezione Multimedia.

PERCHE' E' UN WIDGET E NON UN DIALOGO
--------------------------------------
Un video che si apre in una finestra a parte e' un video che copre la
finestra da cui lo hai aperto, e l'utente deve scegliere fra due finestre.
Qui il video sta **dentro** la sezione, sopra la lista: la lista resta
visibile sotto, si vede che cosa hai scelto e si puo' scegliere altro senza
chiudere niente.

Lo schermo intero è un'altra cosa e sta in `LettoreSchermo`: li' il video
prende **tutto** lo schermo del computer, che è quello che si chiede quando
si preme "schermo intero".  Sono due passaggi diversi e non si confondono.

I COMANDI SONO QUELLI CHE CI SONO
----------------------------------
    play e pausa     un pulsante che cambia faccia, non due pulsanti
    volume           un cursore e il glifo delle casse
    schermo intero   si espande e si rientra
    chiudi           esce dal lettore e torna alla lista

Due pulsanti, play e pausa, con uno dei due sempre spento, sono la cosa che
si vede in giro e non funziona: l'utente preme quello spento, non succede
niente, e sembra che il pulsante sia rotto.  Un pulsante che cambia faccia è
un pulsante che è sempre quello giusto.

I COLORI VENGONO DA `tema`
-------------------------
Nessun colore scritto qui.  Il lettore è dentro la finestra e deve sembrare
della finestra: un lettore con i propri colori è un programma dentro un
programma.  Gli oggetti di nome (`rigaLettore`, `titoloLettore`,
`comandiLettore`) prendono tutto dal foglio di tema, quindi il tema scuro e
quello chiaro funzionano senza che qui ci sia scritto niente.

LO STATO VIENE TUTTO DA `Lettore`
----------------------------------
Nessun timer qui.  Il widget ascolta il motore e si ridipinge: se tenesse
un proprio conto dei secondi, andrebbe avanti di un secondo rispetto al
suono e si sentirebbe che il video e l'audio non vanno d'accordo.
"""

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal as Signal
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QImage, QPainter, QPixmap

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QVBoxLayout,
    QWidget,
)

from Utility import Lettore
from Utility.Stuff import icon
from Utility.tema import AUTOMATICA, PER_TAGLIO

# Il modulo, non la classe: `Utility.Lettore.motore()` e' la funzione che
# dà il motore unico.  `from Utility.Lettore import Lettore` porta la classe,
# e su quella `motore` non esiste.


#: L'altezza della casella del video, in pixel.
#:
#: Non e' un numero preso a caso: e' mezzo schermo.  Piu' piccolo e il video si
#: vede male, e a schermo intero non serve perche' li' la finestra e' grande
#: quanto lo schermo.  Sopra, e la lista sotto sparisce — vedi il commento in
#: `__init__`.
ALTEZZA_VIDEO = 280

#: L'altezza della riga dei comandi: pulsanti da 28 pixel con 6 sopra e
#: sotto fanno 40, e i tasti hanno bordo.
ALTEZZA_COMANDI = 40


#: Se l'hai gia' detta una volta, non la ripeti.  Serve per gli avvertimenti
#: che sono un fatto, non un evento: dodici click sullo stesso tasto non
#: devono diventare dodici righe uguali.
_GIA_DETTO: set = set()


def _finestra_esterna(finestra_app=None):
    """La finestra dello schermo secondario, o `None` se non c'e'.

    `finestra_app` e' la finestra del programma: serve a capire quale dei
    due schermi e' «l'altro».  Chi chiama ce l'ha sempre (`self.window()`).

    PERCHE' L'IMPORT E' PROTETTO, E NON NELLA FUNZIONE GEMELLA
    ---------------------------------------------------------
    `_rientrato` gia' lo faceva, e `_schermo_intero` no.  La differenza si
    vedeva: il tasto del tutto schermo, quando la finestra secondaria non si
    poteva caricare, stampava un `ModuleNotFoundError` e **non faceva niente**:

        RuntimeError: wrapped C/C++ object of type _Bottone has been deleted

    Il primo errore e' la causa, il secondo e' la conseguenza: l'eccezione
    esce dal segnale di Qt dentro `mousePressEvent`, e quando torna indietro
    l'oggetto e' gia' stato distrutto.  Per questo la protezione sta qui, nel
    posto dove l'import e' fatto, e non ognuno dei due chiamanti.

    E SE NON SI PUO' CARICARE, IL PROGRAMMA CONTINUA
    ------------------------------------------------
    Perche' la finestra secondaria e' una cosa in piu', non una condizione per
    guardare un video: senza di lei il video va qui dentro l'app, e va benone.
    Quindi se il modulo non si carica si va avanti come se non ci fosse, e non
    si butta via il tasto.

    L'avvertimento si stampa **una volta sola** e in italiano, perche' e' un
    fatto e non un evento, e dodici click sullo stesso tasto non possono
    diventare dodici righe uguali.
    """
    try:
        from SubViews.SchermoEsterno import istanza

        return istanza(finestra_app)
    except ImportError as errore:
        if "SchermoEsterno" not in _GIA_DETTO:
            _GIA_DETTO.add("SchermoEsterno")
            print(f"Lo schermo secondario non si carica ({errore}). "
                  "Il video resta nella finestra del programma.")
        return None


def _e_video(voce: dict) -> bool:
    """Questa voce e' un video, o un audio?

    Due indizi che vanno d'accordo: il `mimetype` che comincia per `video/`
    oppure la risoluzione, perche' un video ha sempre larghezza e altezza e un
    audio non le ha mai.

    PERCHE' QUI E NON `MediaView._e_video`
    --------------------------------------
    `MediaView` usa gia' questo file (`LettoreView(self)` nella sua
    costruzione), quindi importarlo da qui chiuderebbe un cerchio: quando si
    costruisce la sezione Media si importerebbe il modulo che sta chiedendo
    esattamente quel modulo, e Python troverebbe mezzo `MediaView` gia' fatto.

    La regola e' scritta due volte, e questa e' la cosa che andrebbe cambiata
    per prima se domani il catalogo dicesse qualcos'altro.  Meglio due copie
    note che un import che non parte.
    """
    if not isinstance(voce, dict):
        return False
    if (voce.get("mimetype") or "").lower().startswith("video/"):
        return True
    return bool(voce.get("frameWidth") and voce.get("frameHeight"))


def tempo_corto(posizione: int, durata: int) -> str:
    """Il tempo in ``m:ss``, e con la durata dopo se c'e'.

    E' una funzione e non una riga dentro ogni schermata, perche' il tempo si
    mostra in tre posti — il lettore dentro l'app, quello a schermo intero e
    la striscia in fondo — e tre versioni della stessa formattazione
    divergono.  La prima divergenza e' invisibile ("0:14" e "00:14") e la
    seconda no.

    Senza durata si scrive solo la posizione: durante il caricamento il
    server non sa ancora quanto dura, e un "0:00 / --:--" sembrerebbe un
    video fermo invece che uno di cui non si sa la durata.
    """
    minuti, secondi = posizione // 60000, posizione // 1000 % 60
    testo = f"{minuti}:{secondi:02d}"
    if durata > 0:
        testo += f" / {durata // 60000}:{durata // 1000 % 60:02d}"
    return testo


class VideoWidget(QWidget):
    """Il riquadro del video **dentro l'app**: li' il video esce davvero.

    PERCHE' QUI DENTRO E NON SUL MONITOR ESTERNO
    ------------------------------------------
    Prima l'uscita del video la sceglieva il chiamante: se c'era il monitor
    esterno il video usciva li', se no usciva qui.  E il difetto e' stato
    proprio questo: con il monitor esterno aperto il video usciva sul
    `QVideoWidget` di quella finestra, e **nel player non si vedeva niente**.

    Il motivo e' che `setVideoOutput` e' una cosa sola: un solo riquadro puo'
    essere l'uscita.  Quindi «il video va sul monitor esterno **e anche** nel
    player» e' una richiesta che quell'uscita sola non puo' soddisfare, e
    ogni tentativo di accontentarla a sposta finisce con uno dei due posti
    nero.

    Qui la regola e' una e non si negozia: **il video esce sempre qui dentro**,
    perche' questo e' il riquadro che c'e' sicuramente ed e' sicuramente
    visibile.  Un secondo schermo, se c'e', non e' un posto dove il video
    "va": e' un posto dove il video si **vede in piu'**, e di quello se ne
    occupa `SpecchioVideo`, che riceve i fotogrammi da qui.

    Il vantaggio non e' solo che funziona: e' che il player **non puo'**
    diventare nero.  Se il secondo schermo manca, non parte; se c'e' ma non
    copia, il video si vede lo stesso.  Niente di quello che si rompe da solo.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("videoLettore")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(p)

        self._video_widget = QVideoWidget(self)
        self._video_widget.setObjectName("videoLettoreInterno")
        self._video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._video_widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Expanding)

        # LO SPECCHIO, PER QUANDO IL VIDEO ESCE SU UN MONITOR ESTERNO
        # ------------------------------------------------------------
        # Con un solo schermo il video esce qui dentro e basta: il
        # `QVideoWidget` mostra lui, e lo specchio resta spento.
        #
        # Con un monitor esterno scelto il video esce **li'**, e qui dentro si
        # vede una **copia**: non un secondo video e non un secondo audio, ma
        # lo stesso fotogramma mostrato in due posti.  E' la stessa cosa che
        # fanno i duplicati, quindi e' lo stesso pezzo di codice — ed e' un
        # `SpecchioVideo`, lo stesso.
        #
        # Perche' il video si vede anche dentro l'app: chi sta leggendo una
        # pubblicazione sul primo monitor e chi guarda il video sull'altro
        # sono due persone, spesso nella stessa stanza, e non per questo uno
        # dei due schermi deve restare spento.
        #
        # I due riquadri non stanno visibili insieme: quando arriva la copia
        # il `QVideoWidget` si nasconde, e quando il video torna dentro si
        # nasconde lo specchio.  Se stassero visibili entrambi si dividerebbero
        # il posto a meta' e il video si vedrebbe piccolo.
        self._specchio = SpecchioVideo(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)
        layout.addWidget(self._specchio)
        self._specchio.setVisible(False)
        self._in_copia = False

    def video_widget_diretto(self) -> QVideoWidget:
        """Il `QVideoWidget` su cui il video esce."""
        return self._video_widget

    def in_copia(self) -> bool:
        """`True` se qui dentro si vede la copia del video (monitor esterno)."""
        return self._in_copia

    def accetta_copia(self, accetta: bool) -> None:
        """Il player mostra il video in copia invece che direttamente?

        `True` quando il video esce su un monitor esterno e qui dentro si vede
        la sua copia.  `False` quando il video esce qui dentro, ed e' il caso
        di un solo schermo.

        I due riquadri si nascondono a vicenda perche' nel layout condividono
        lo stesso posto: visibili insieme, ognuno prenderebbe meta' casella e
        il video si vedrebbe piccolo — che e' esattamente il difetto che si
        era visto sui monitor esterni.
        """
        self._in_copia = bool(accetta)
        self._specchio.accetta(self._in_copia)
        self._specchio.setVisible(self._in_copia)
        self._video_widget.setVisible(not self._in_copia)

    def imposta_frame(self, frame) -> None:
        """Un fotogramma e' arrivato: tienilo e ridisegnati."""
        self._specchio.imposta_frame(frame)

    def svuota_copia(self) -> None:
        """Non c'e' piu' niente da mostrare qui dentro."""
        self._specchio.svuota()

    def sink(self):
        """Il `QVideoSink` da cui si prendono i fotogrammi per gli specchi.

        C'e' **sempre**, appena il widget esiste: e' quello che Qt crea per
        il riquadro e non dipende da nessuna impostazione, nessun timer e
        nessuna disponibilita'.  Per questo gli specchi si possono attaccare
        subito, e non c'e' il ritardo di qualche decimo di secondo in cui il
        video e' gia' partito ma lo specchio e' ancora nero — che era
        esattamente il difetto che si vedeva.
        """
        return self._video_widget.videoSink()

    def setAspectRatioMode(self, mode) -> None:
        """Delega al QVideoWidget interno."""
        self._video_widget.setAspectRatioMode(mode)


class SpecchioVideo(QWidget):
    """Una copia del video che si vede su un altro schermo.

    Non e' un `QVideoWidget`: non riceve il video da Qt, riceve i
    **fotogrammi** da un `SpecchioVideo` gemello e li ridipinge.  E' la
    differenza che serve per mostrare la stessa cosa in due posti — un solo
    `setVideoOutput` per programma, e un solo pezzo che puo' essere
    "l'uscita vera".

    LA COPIA SCORRE DI UN FOTOGRAMMA
    ---------------------------------
    Il fotogramma che si vede qui e' quello appena arrivato, non quello che
    sta davanti: la copia passa dal riquadro d'origine a questo in un
    paintEvent.  Su un video da 24 fotogrammi al secondo sono circa 40
    millisecondi, e non si vedono: quello che si vede e' il video.

    IL SENSO DELLA PAROLA "SPECCHIO"
    --------------------------------
    E' una metafora di programmazione (dal design pattern *observer*) messa
    qui perche' dice esattamente cosa fa: e' un secondo ascoltatore dello
    stesso fotogramma.  Non e' una copia del widget, e non decide nulla: se
    il riquadro d'origine smette di ricevere fotogrammi, questo mostra
    l'ultimo e basta, senza che nessuno se ne accorga in modo irreparabile.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(p)
        self._frame: QImage | None = None
        self._accetta = False

    def accetta(self, accetta: bool) -> True | None:
        """Accetta i fotogrammi, o smette e si svuota.

        Il nome e' volutamente diverso da `imposta_frame`: `imposta_frame`
        viene chiamata dal segnale di Qt e non deve mai fare nient'altro,
        mentre questo e' l'interruttore.  Sono due cose diverse anche se
        arrivano dallo stesso posto.

        Quando smette di accettare si svuota: uno specchio spento che
        continua a mostrare l'ultimo fotogramma sembra un video fermo, e il
        programma non e' in grado di dirti il contrario.
        """
        self._accetta = bool(accetta)
        if not self._accetta:
            self._frame = None
            self.update()
        return None

    def imposta_frame(self, frame) -> None:
        """Un fotogramma e' arrivato: tienilo e ridisegnati."""
        if not self._accetta or not self.isVisible():
            return
        try:
            if frame is None or not frame.isValid():
                return
            self._frame = frame.toImage()
        except Exception:  # noqa: BLE001 - un fotogramma perso non e' un guasto
            return
        self.update()

    def svuota(self) -> None:
        """Non c'e' piu' niente da mostrare qui: resta nero."""
        self._frame = None
        self.update()

    def paintEvent(self, evento) -> None:
        pittore = QPainter(self)
        pittore.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._frame is None or self._frame.isNull():
            return
        misura = self._frame.size()
        misura.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - misura.width()) // 2
        y = (self.height() - misura.height()) // 2
        pittore.drawImage(QRect(x, y, misura.width(), misura.height()), self._frame)


class CopertinaView(QWidget):
    """La copertina, o la miniatura del video, nel posto dove c'e' il video.

    PERCHE' NON UNA `QLabel`
    -----------------------
    Nella `QLabel` che c'era prima la copertina si metteva e **non si
    vedeva**: lo spazio c'era, giusto, e dentro non c'era niente.

    Il motivo sono due, ed e' per questo che qui non si usa piu' una `QLabel`:

    1.  `setPixmap` su una `QLabel` **non scala**.  La miniatura che arriva
        dal catalogo e' quadrata e grande — 600 pixel — e la casella del
        video puo' essere molto piu' piccola.  Una `QLabel` con dentro una
        pixmap piu' grande di lei la centra e la **taglia**: si vede un
        pezzo, e spesso il pezzo ritagliato e' un pezzo di cielo o di
        sfondo, cioe' apparentemente nero.

    2.  La `QLabel` non si rivede quando cambia la misura.  Ridimensionando
        il lettore — e il lettore si ridimensiona, e' il suo scopo — la
        pixmap restava quella di prima, fuori dai bordi.

    Qui l'immagine viene ridimensionata alla casella **tenendo le
    proporzioni**, e ridisegnata a ogni cambio di misura.  Il posto del video
    e' esattamente quello del video: stesso nero, stessa grandezza.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(p)
        self._pixmap = QPixmap()

    def metti(self, pixmap) -> None:
        """La copertina da mostrare.  Una pixmap nulla e' un rettangolo nero."""
        self._pixmap = pixmap if (pixmap is not None and not pixmap.isNull()) \
            else QPixmap()
        self.update()

    def pulito(self) -> None:
        """Non c'e' piu' copertina."""
        self.metti(None)

    def paintEvent(self, evento) -> None:
        pittore = QPainter(self)
        pittore.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._pixmap.isNull():
            return
        misura = self._pixmap.size()
        misura.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - misura.width()) // 2
        y = (self.height() - misura.height()) // 2
        pittore.drawPixmap(QRect(x, y, misura.width(), misura.height()),
                           self._pixmap)


class LettoreView(QWidget):
    """Il video con i suoi comandi, dentro la sezione."""

    chiuso = Signal()
    #: L'utente ha premuto play: chi ascolta decide se aprire la finestra
    #: grande o lasciare il video qui
    aperto = Signal()
    #: Il lettore ha cambiato qualcosa che la sezione deve ricalcolare
    #: (per esempio il video a schermo intero non e' piu' qui dentro)
    videoMoved = Signal()
    #: Il video e' andato a schermo intero, o e' tornato: (aperto)
    #:
    #: Serve per la striscia in fondo, che con un video a tutto schermo non
    #: deve stare li'.  La finestra lo ascolta e la nasconde.
    schermoIntero = Signal(bool)

    #: L'utente ha premuto la freccia giù: vuole la striscia piccola e
    #: poter girare per l'app mentre suona.
    #:
    #: Chi ascolta e' la finestra (`SidebarView`), perche' la sezione Media non
    #: sa cosa sia la striscia in fondo: sta in un'altra parte della finestra e
    #: non la vede nemmeno.  Come per `schermoIntero`, che pure e' una cosa
    #: della finestra e passa di qui.
    ripiccolato = Signal()

    #: Il lettore grande e' comparso o sparito: (visibile)
    #:
    #: Serve per la **striscia piccola in fondo alla finestra**: con il
    #: lettore grande aperto dentro l'app la striscia sparisce, perche' due
    #: lettori per lo stesso video sono due cose da guardare insieme.
    #:
    #: Chi ascolta e' la finestra (`SidebarView`), che e' l'unica che vede
    #: sia il lettore dentro la sezione Media sia la striscia in fondo: sono
    #: due pezzi in due posti diversi, e nessuno dei due sa dell'altro senza
    #: che qualcuno lo dica.
    visibilitaCambiata = Signal(bool)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("lettore")
        # Callback per visibilità mini player button
        self._on_visibilita_cambiata = None
        # Ultima visibilita' **richiesta** con `setVisible`, non quella che Qt
        # calcola: se la sezione Media non e' in primo piano il lettore e'
        # gia' "non visibile" per Qt, ma e' il lettore grande dell'utente e
        # la striscia in fondo deve restare accesa lo stesso.
        self._visibile_comandata = False

        # GLI SCHERMI ESTERNI, E LE LORO COPIE DEL VIDEO
        # ---------------------------------------------
        # `_esterno`   la prima finestra esterna (quella del secondario), o
        #              None.  Serve a chi ha bisogno di una finestra sola:
        #              il nome dello schermo, e nient'altro.
        #
        # `_esterni`   le coppie `(sink, specchio)` di **tutti** gli schermi
        #              esterni accesi: uno per finestra, perche' chiudere una
        #              finestra non deve spegnere le altre.
        #
        # Due campi e non uno perche' hanno vite diverse: la lista si
        # ricostruisce a ogni video, `_esterno` no.  E un campo solo
        # produrrebbe metodi che si tolgono da soli un pezzo di cui hanno
        # ancora bisogno.
        self._esterno = None
        # Il `sink` da cui arriva la copia mostrata **dentro l'app** quando il
        # video esce su un monitor esterno.  Va ricordato perche' il
        # collegamento si stacca da quello e da nessun altro: vedi
        # `_stacca_il_player_in_copia`.
        self._sink_copia_player = None

        # IL VIDEO IN ALTO, I COMANDI SOTTO
        # ---------------------------------
        # Il video si espande verticalmente (stretch=1), i comandi stanno
        # sotto con altezza fissa.  Il lettore ha altezza minima, non fissa:
        # cosi' l'utente puo' ridimensionare la finestra e il video si
        # adatta.  La lista sotto non viene schiacciata perche' il lettore
        # sta in una colonna che gli da' lo spazio che serve.
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Minimum)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.setSpacing(0)

        # IL VIDEO IN ALTO: SI ESPANDE VERTICALMENTE (stretch=1)
        # -------------------------------------------------------
        # VideoWidget custom: può fare output diretto O ricevere frame copiati
        self.video = VideoWidget(self)
        self.video.setObjectName("videoLettore")
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Expanding)
        self.video.setMinimumHeight(200)
        esterno.addWidget(self.video, 1)

        # LA COPERTINA, AL POSTO DEL VIDEO QUANDO C'E' UN AUDIO
        # ---------------------------------------------------------
        # Un audio non ha niente da mostrare nel riquadro grande: quello e' il
        # posto del video.  Ma un rettangolo nero vuoto sembra un video che
        # non parte, quindi qui ci va la copertina della canzone, prenduta
        # dalla stessa miniatura che usa la lista.
        #
        # Nascosta finche' non c'e' un audio: con un video e' il video che si
        # vede, e due immagini una sopra l'altra sarebbero un difetto.
        self.copertina = CopertinaView(self)
        self.copertina.setObjectName("copertinaLettore")
        self.copertina.setVisible(False)
        esterno.addWidget(self.copertina, 1)

        # L'AVVISO: QUANDO IL VIDEO VA SULLO SCHERMO ESTERNO
        # ----------------------------------------------------
        # Una riga sola, centrata, che dice dove sta andando il video.
        self.avviso = QLabel("", self)
        self.avviso.setObjectName("nota")
        self.avviso.setWordWrap(True)
        self.avviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avviso.setVisible(False)
        esterno.addWidget(self.avviso, 0)

        # I COMANDI SOTTO IL VIDEO (altezza fissa)
        # -----------------------------------------
        self.comandi = QWidget(self)
        self.comandi.setObjectName("comandiLettore")
        self.comandi.setFixedHeight(ALTEZZA_COMANDI)
        riga = QHBoxLayout(self.comandi)
        riga.setContentsMargins(8, 6, 8, 6)
        riga.setSpacing(8)

        self.pulsante_play = _Bottone("play.fill", "Riproduci o ferma")
        self.pulsante_play.premuto.connect(self._commuta)
        riga.addWidget(self.pulsante_play, 0)

        self.pulsante_schermo = _Bottone("arrow.up.left.and.arrow.down.right",
                                         "Schermo intero")
        self.pulsante_schermo.premuto.connect(self._schermo_intero)
        riga.addWidget(self.pulsante_schermo, 0)

        # Il tasto della risoluzione sta accanto a quello dello schermo
        # intero, perche' i due parlano di come si guarda il video.  Entra
        # **nascosto** e si vede solo se c'e' un video: su un brano non ci
        # sarebbe niente da scegliere, e un tasto che apre un menu con dentro
        # una voce sola sembra un comando rotto.  Vedi `_stato`.
        self.pulsante_risoluzione = _TastoRisoluzione(self.comandi)
        self.pulsante_risoluzione.setVisible(False)
        self.pulsante_risoluzione.scelta.connect(self._cambiata_risoluzione)
        riga.addWidget(self.pulsante_risoluzione, 0)

        # `_Cursore` e non `QSlider`: il cursore si clicca e si trascina.
        self.posizione = _Cursore(self.comandi)
        self.posizione.setObjectName("barraLettore")
        self.posizione.setRange(0, 0)
        riga.addWidget(self.posizione, 1)

        self.durata = QLabel("0:00", self.comandi)
        self.durata.setObjectName("nota")
        riga.addWidget(self.durata, 0)

        # La QLabel senza testo, col glifo messo dopo.
        self.giacche = QLabel(self.comandi)
        self.giacche.setPixmap(icon("headphones", "#ffffff", 18).pixmap(18, 18))
        self.giacche.setFixedSize(22, 22)
        riga.addWidget(self.giacche, 0)

        # Anche il volume su `_Cursore`: cliccando sulla barra si va al punto.
        self.volume = _Cursore(self.comandi)
        self.volume.setObjectName("volumeLettore")
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.setMaximumWidth(90)
        self.volume.valueChanged.connect(self._volume)
        riga.addWidget(self.volume, 0)

        # LA FRECCIA IN GIU', SUBITO A SINISTRA DELLA X
        # ------------------------------------------------
        # Sta li' e non altrove perche' e' la coppia di un tasto: la X chiude
        # tutto, la freccia lo rimpicciolisce.  Due tasti che si somigliano ma
        # fanno cose diverse, quindi vanno vicini: se la freccia stesse a
        # sinistra della barra, l'utente la premerebbe senza sapere che e'
        # quella giusta, perche' li' accanto ci sarebbe il cursore di posizione.
        #
        # E' bianca come tutti gli altri comandi: sopra il nero del video un
        # glifo grigio non si vede, e un tasto che non si vede e' un tasto che
        # non c'e'.
        self.pulsante_ripiccola = _Bottone("chevron.down",
                                           "Mini player: continua a suonare")
        self.pulsante_ripiccola.premuto.connect(self._ripiccolato)
        riga.addWidget(self.pulsante_ripiccola, 0)

        self.pulsante_chiudi = _Bottone("stop.fill", "Chiudi il lettore")
        self.pulsante_chiudi.premuto.connect(self.chiudi)
        riga.addWidget(self.pulsante_chiudi, 0)

        esterno.addWidget(self.comandi, 0)

        # L'attributo si chiama `motore` e la funzione pure: per questo la
        # funzione si chiama via il modulo e non in breve.
        self.motore = Lettore.motore()
        self.motore.mosso.connect(self._mosso)
        self.motore.stato.connect(self._stato)
        self.motore.video.connect(self._tasto_video)
        self.motore.vuoto.connect(self._vuoto)
        self.posizione.sliderMoved.connect(self._spostato)
        self.setVisible(False)
    # ------------------------------------------------------------------

    def mostra(self, voce: dict) -> None:
        """Fai partire questo media e mostrati.

        DOVE VA IL VIDEO, DIPENDE DA UN'IMPOSTAZIONE
        --------------------------------------------
        Con «dove sta la finestra» — cioe' senza schermo scelto — il video va
        nel riquadro qui dentro, e va a tutto schermo solo quando si preme il
        tasto.

        Se invece nelle impostazioni e' stato scelto uno schermo, il video va
        **subito** e **da solo** in quella finestra, senza aspettare nessun
        tasto.  E' quello che e' stato chiesto: con due monitor e la finestra
        sull'uno, il video grande sull'altro si mette appena lo si preme, e non
        dopo un tasto premuto a caso.

        La riga dei comandi resta qui nell'app: play, pausa e posizione si
        comandano da dove si guarda l'app.  Per questo il riquadro del video
        qui dentro viene nascosto e al suo posto c'e' una riga che dice dove
        sta andando il video: un riquadro nero senza spiegazione sembra un
        video rotto.

        L'ORDINE DEI DUE PASSI E' IL MOTORE DI TUTTO
        --------------------------------------------
        Prima si **collega** il video al widget che lo mostra, poi si fa
        partire.  Invertendoli si sente l'audio e non si vede niente, senza
        un solo messaggio.

        Il playback parte appena `setSource` viene chiamato, e se l'uscita
        video non e' ancora collegata il primo pezzo di video va in un buco
        nero.  Collegare prima e' l'unico ordine che non butta via nulla, e
        non costa niente.

        PERCHE' SI RICOLLEGA OGNI VOLTA E NON UNA VOLTA SOLA
        ---------------------------------------------------
        Perche' il video **sposta** il suo widget: quando parte lo schermo
        intero il video va in quella finestra, e quando si chiude torna qui.
        Ogni volta che questo lettore riappare deve riprendersi il video,
        altrimenti resta uno schermo nero dentro l'app mentre l'audio
        continua a suonare.
        """
        self.setVisible(True)
        # LA FINESTRA DEL SECONDO SCHERMO, O NULLA
        # ----------------------------------------
        # Prima si chiama e basta: adesso non decide piu' niente sul video.
        # Dice solo se c'e' un altro schermo su cui mostrare il video **in
        # piu'**, e di quello si occupa `_accendi_specchi`.
        self._prepara_dove_va_il_video(voce)

        # IL VIDEO ESCE QUI DENTRO, SEMPRE
        # ---------------------------------
        # Non c'e' un ramo in cui esce altrove.  Il `QVideoWidget` del player
        # e' l'unica uscita del programma: esiste sempre, e' visibile, e non
        # puo' fallire.  Un secondo schermo, se c'e', non e' un posto dove il
        # video "va": e' un posto dove il video si **vede in piu'**, e di
        # quello si occupa lo specchio.
        #
        # Prima l'uscita la sceglieva il chiamante, e con il secondo schermo
        # aperto il video usciva li': nel player diventava nero, e l'unico
        # modo di rivederlo era togliere il secondo schermo.  E' il difetto
        # segnalato, e nasceva dal fatto che `setVideoOutput` e' una cosa sola.
        # DOVE ESCE IL VIDEO: SUL MONITOR ESTERNO, MAI NEL PLAYER
        # -------------------------------------------------------
        # La regola e' una sola e non ha eccezioni: **il video esce sui
        # monitor esterni**.  Sul primo monitor — quello dove sta la finestra
        # del programma — il video non compare, e non ci va una copia.
        #
        # Non e' una scelta di comodo': e' quello che e' stato chiesto, ed e'
        # la ragione per cui esiste un secondo monitor.  Il primo schermo
        # mostra l'applicazione, gli altri mostrano il video, e ognuno guarda
        # quello che gli riguarda.  Copiare il video anche nel player
        # coprirebbe la finestra con una seconda cosa da guardare, e
        # costerebbe una copia in piu' che non serve a nessuno.
        #
        # UN AUDIO NON E' UN VIDEO
        # ------------------------
        # Un audio non ha niente da mostrare sui monitor esterni: li' tornano
        # al verso del giorno, e nel player c'e' la copertina.  Qui si esce
        # prima di toccare l'uscita video, perche' un audio **non** deve
        # avere un riquadro video agganciato — si vedrebbe un rettangolo
        # nero su un monitor che dovrebbe mostrare il verso.
        #
        # E non si tocca la copertina: l'ha gia' messa
        # `_prepara_dove_va_il_video`, e rimetterla qui significherebbe
        # nasconderla subito dopo averla mostrata.  Prima succedeva
        # esattamente questo, e per un audio nel player non si vedeva niente.
        esterno = getattr(self, "_esterno", None)
        if not _e_video(voce):
            self.motore.al_video(None)
            self._spegni_specchi()
            larghezza = 0
        else:
            riquadro = None
            if esterno is not None:
                try:
                    riquadro = esterno.uscita_video()
                except (AttributeError, RuntimeError):
                    riquadro = None

            if riquadro is None:
                # Nessun monitor esterno — un solo schermo, o scelta
                # «Disattivato»: il video esce **qui dentro**, per forza.
                #
                # Non e' un'eccezione alla regola, e' la regola su una macchina
                # senza monitor esterni.  E il player smette di essere una
                # copia: torna a mostrare il video dal riquadro diretto.
                # Senza questo, dopo un video con lo schermo esterno e poi uno
                # senza, il player mostrerebbe un riquadro nero — la copia non
                # arriverebbe piu' e il diretto resterebbe spento.
                #
                # E la copia di prima va staccata per davvero: senza questa
                # riga resterebbe collegata al fotogramma di uno schermo
                # esterno che non c'e' piu'.  Non si vede, ma e' un
                # collegamento che non dovrebbe esserci, e il giorno in cui
                # torna un monitor esterno si sommererebbe a quello nuovo.
                riquadro = self.video.video_widget_diretto()
                self._stacca_il_player_in_copia()
                self.video.accetta_copia(False)
                self.video.setVisible(True)
                self.copertina.setVisible(False)
                self.avviso.setVisible(False)
                self.avviso.clear()
            else:
                # C'e' il monitor esterno: li' il video esce.  Ma **qui
                # dentro si vede lo stesso video**, in copia — lo stesso
                # fotogramma, non un secondo video.  Il primo schermo mostra
                # l'applicazione, e dentro l'applicazione c'e' il video: e' il
                # motivo per cui il primo schermo serve.
                #
                # Sotto il video una riga dice **dove** si vede a schermo
                # intero, cosi' chi guarda il primo schermo sa che la finestra
                # grande e' sull'altro monitor e non pensa che sia sparito.
                self.video.setVisible(True)
                self.copertina.setVisible(False)
                # Qui il nome era solo quello del secondario: con i
                # duplicati accesi l'utente ne cercava uno che non
                # compariva.  `_dove_si_vede_il_video` elenca tutti.
                self.avviso.setText(
                    f"A schermo intero {self._dove_si_vede_il_video()}. "
                    "Qui sotto i comandi.")
                self.avviso.setVisible(True)

            self.motore.al_video(riquadro)
            # E SOLO ADESSO, e SOLO se il video e' uscito su un monitor
            # esterno, si accendono le copie.
            #
            # La chiamata sta **dentro** il ramo, e non dopo: prima stava
            # dopo, e accendeva la copia anche quando il video era uscito
            # qui dentro.  Il player si metteva in modalita' copia, si
            # nascondeva il riquadro diretto, e siccome la copia non arrivava
            # — l'uscita era il riquadro del player, non un monitor esterno —
            # restava **nero**.  Il video dentro l'app non si vedeva.
            if riquadro is not None and riquadro is not \
                    self.video.video_widget_diretto():
                self._accendi_specchi(riquadro)
            larghezza = self._larghezza_dove_si_vede()
        # La risoluzione si sceglie **misurando la casella**, e non prendendo
        # la piu' grande: su questa macchina Qt non trova una scheda video e
        # ridimensiona con la CPU sul filo del discorso, e con 1280x720 il
        # programma smette di rispondere.  Vedi `Mediator.scegli_risoluzione`.
        #
        # Si misura **la casella dove il video va davvero**.  Con un secondo
        # schermo acceso il video si vede li' a tutto schermo, quindi e' quella
        # casella che conta e non questa striscia: misurare 128 pixel
        # sceglierebbe una risoluzione minuscola per un video che si vedra' a
        # tutto schermo su 1920 pixel, e si vedrebbe sfocato per un motivo che
        # non ha niente a che fare col video.
        try:
            from Utility import Mediator
            from Utility import tema
            voci = Mediator.scegli_risoluzione(dict(voce), larghezza,
                                               tema.risoluzione_video())
        except Exception:  # noqa: BLE001 - se non si puo' scegliere si usa
            voci = voce     # quello che c'era, che e' comunque una versione
                            # che il server ha dichiarato
        self.motore.suona(voci)
        # Il tasto ha bisogno della voce **dopo** la scelta, non prima: e' in
        # `voci` che c'e' la risoluzione che e' partita davvero.  Con la voce
        # di prima la spunta del menu andrebbe sull'opzione sbagliata.
        self.pulsante_risoluzione.metti_voce(self.motore.voce())
        self.aperto.emit()

    def _prepara_dove_va_il_video(self, voce: dict | None = None) -> None:
        """C'è un secondo schermo? E che cosa ci deve mostrare?

        ADESSO NON SCEGLIE DOVE ESCE IL VIDEO
        ---------------------------------------
        Prima questo metodo decideva se il video usciva nel player o nella
        finestra dello schermo secondario, e la scelta era anche il motivo per
        cui il player diventava nero.  Adesso non decide piu' niente: il video
        esce **sempre** nel player (vedi `mostra`), e questo metodo fa due
        cose sole:

        1.  dice alla finestra del secondo schermo **che cosa mostrare** —
            il video, se e' un video, oppure il verso del giorno;
        2.  dice al player che cosa mettere al posto del video — la copertina
            se e' un audio, niente se e' un video.

        E' una divisione che torna: «dove esce il video» e «cosa si vede
        sull'altro schermo» non sono piu' la stessa domanda.

        LA FINESTRA SI RIACCENDE, E SI SPEGNE
        --------------------------------------
        Quando parte un video, `mostra_video` la accende e `_accendi_specchi`
        le attacca i fotogrammi.  Quando parte un audio, o quando il brano
        finisce, quella finestra torna al verso del giorno — un audio non ha
        niente da mostrare a schermo intero, e lasciare li' l'ultimo fotogramma
        di un video farebbe pensare che stia ancora suonando.
        """
        esterno = _finestra_esterna(self.window())

        # SENZA SECONDO SCHERMO: NESSUN SPECCHIO, MA LA COPERTINA SÌ
        # ----------------------------------------------------------
        # Il ramo dell'audio — quello che nasconde il riquadro video e chiama
        # `_metti_la_copertina` — stava **sotto**, dentro il caso «c'e' un
        # monitor esterno».  Senza monitor esterno qui si usciva subito, e
        # quel pezzo non correva mai: un brano nel player grande lasciava il
        # riquadro nero, e la copertina che si vedeva sulla card non
        # appariva da nessuna parte.  E' il difetto segnalato, e il motivo
        # per cui sembrava casuale: su una macchina con due monitor
        # funzionava, su una con uno solo no.
        #
        # Si fa quindi la stessa cosa prima di uscire.  Un video non tocca
        # niente: il riquadro video lo riaccende `mostra`, che dopo questo
        # metodo continua il suo lavoro.
        if esterno is None:
            self._esterno = None
            self._spegni_specchi()
            if not _e_video(voce):
                self.video.setVisible(False)
                self._metti_la_copertina(voce)
            return

        self._esterno = esterno
        # UNA VOLTA SOLA per tutta la vita di questo lettore: il segnale si
        # collega quando la finestra esiste, non a ogni video.
        if not getattr(self, "_collegato_all_esterno", False):
            try:
                from SubViews.SchermoEsterno import ascolta
                ascolta(self._rientrato)
                self._collegato_all_esterno = True
            except ImportError:
                # Senza quella finestra il video si vede lo stesso: qui dentro.
                # Non e' un errore, e' un monitor che non c'e'.
                self._collegato_all_esterno = False

        # UN AUDIO: LA COPERTINA QUI, IL VERSO SULL'ALTRO SCHERMO
        # ---------------------------------------------------------
        if not _e_video(voce):
            self._spegni_specchi()
            esterno.mostra_verso()
            self.video.setVisible(False)
            self._metti_la_copertina(voce)
            return

        # UN VIDEO: IL VIDEO SU TUTTI GLI SCHERMI ESTERNI
        # -------------------------------------------------
        # `mostra_video` va chiamata su **tutte** le finestre, non solo sulla
        # prima.  Prima qui si chiamava sul solo secondo schermo: i duplicati
        # restavano con quello che avevano prima, cioe' la Scrittura
        # dell'anno, mentre il secondo passava al video.
        #
        # Non e' una dimenticanza ma una conseguenza del pezzo di prima: i
        # duplicati erano finestre «solo video», senza verso, e quindi non
        # c'era niente da cambiare.  Adesso che sono copie vere — video **e**
        # verso — vanno avvertiti come il secondo, e il `for` e' l'unico modo
        # che non richiede di sapere quanti sono.
        self.copertina.setVisible(False)
        self.video.setVisible(True)
        for finestra in self._finestre_esterne():
            finestra.mostra_video()
        # La copia dei fotogrammi si accende in `_accendi_specchi`, che
        # `mostra` chiama **dopo** che l'uscita e' questa: i fotogrammi da
        # copiare devono venire dal riquadro che il motore sta riempiendo,
        # e se si accendesse prima si copierebbero da un riquadro vuoto.

    def _finestre_esterne(self) -> list:
        """Tutte le finestre degli schermi esterni, e se non c'e' nessuna, [].

        Il nome torna in italiano e vuol dire «esterne», non «esterne»
        e finale: due nomi che differiscono di una lettera e si confondono
        solo leggendo veloce.  Per questo il metodo si chiama come va scritto
        e non come suona.

        Vedi `SchermoEsterno.finestre`.
        """
        try:
            from SubViews import SchermoEsterno
        except ImportError:
            return []
        try:
            return SchermoEsterno.finestre(self.window())
        except RuntimeError:
            return []

    def _dove_si_vede_il_video(self) -> str:
        """«su DP-1», oppure «su DP-1, DP-2 e HDMI-1»: **tutti** gli schermi.

        PERCHE' TUTTI, E NON UNO
        -----------------------
        La riga sotto il video scriveva il nome di **uno** schermo solo, quello
        secondario.  Ma con la duplicazione l'utente ha spuntato piu'
        schermi, e sono accesi tutti: dirne uno solo fa pensare che gli altri
        siano spenti, e uno schermo che dovrebbe mostrare il video e resta nero
        sembra un monitor rotto.

        Quindi qui si dice dove si vede il video **davvero**, e non e' un
        elenco di giudizi presi uno per uno: si prende la stessa lista di
        finestre che il lettore usa per i fotogrammi — `_finestre_esterne` —
        cosi' la riga non puo' nominare uno schermo su cui il video non sta.

        L'ORDINE E' QUELLO DELL'UTENTE
        ------------------------------
        Prima la secondaria, poi i duplicati nell'ordine in cui il sistema li
        elenca, che e' quello in cui sono stati scelti.  L'ordine viene da
        `finestre()` e non e' deciso qui: due posti che decidono l'ordine
        divergono, e il primo che diverge e' quello che stampa la riga.

        IL RIPIEGO SENZA NOMI
        ---------------------
        Se il sistema non da' un nome a uno schermo non si inventa: si torna al
        «sul secondo schermo» di prima.  «Il video si vede su , e .» e' un
        messaggio sbagliato, e qui vale ancora piu' che con uno schermo solo,
        perche' la riga e' piu' lunga e la buca si vede di piu'.

        IL PERCHE' UN METODO E NON UNA RIGA NEI TRE POSTI
        -------------------------------------------------
        La stessa frase era scritta in tre punti — quando parte il video,
        quando torna dal tutto schermo, e quando il tasto spiega che il video
        e' gia' a schermo intero.  Tre punti, tre liste da tenere dritte
        insieme: il primo che resta indietro mostra uno schermo in meno e
        l'utente cerca perche' quel monitor non si accende.
        """
        try:
            finestre = self._finestre_esterne()
        except (AttributeError, RuntimeError):
            finestre = []
        nomi = []
        for finestra in finestre:
            try:
                nome = finestra.nome_schermo()
            except (AttributeError, RuntimeError):
                nome = ""
            if nome and nome not in nomi:
                nomi.append(nome)
        if len(nomi) > 1:
            return "su " + ", ".join(nomi[:-1]) + " e " + nomi[-1]
        if len(nomi) == 1:
            return f"su {nomi[0]}"
        esterno = getattr(self, "_esterno", None)
        if esterno is not None:
            return esterno.dove_si_vede()
        return "sul secondo schermo"


    def _larghezza_dove_si_vede(self) -> int:
        """La larghezza della casella piu' grande in cui il video si vedra'.

        Serve a scegliere la risoluzione: un video scelto per 1280 pixel e
        poi mostrato a tutto schermo su 1920 si vede sfocato, e si vede
        sfocato per un motivo che non ha niente a che fare col video.

        Con un secondo schermo acceso, quella casella e' la sua, perche' e'
        li' che il video sta a tutto schermo.  Senza, e' la casella del
        player.  Se nessuna delle due ha ancora una misura — la finestra e'
        appena stata creata — si usa la larghezza dello schermo: e' un fatto,
        e meglio un fatto che uno zero.
        """
        esterno = getattr(self, "_esterno", None)
        if esterno is not None:
            larghezza = esterno.width()
            if larghezza > 0:
                return larghezza
            schermo = getattr(esterno, "_schermo", None)
            if schermo is not None:
                return schermo.geometry().width()
        if self.video.width() > 0:
            return self.video.width()
        from Utility import Schermi
        schermo = Schermi.per_il_video(self.window())
        return schermo.geometry().width() if schermo is not None else 1920

    def _accendi_specchi(self, uscita=None) -> None:
        """I **duplicati** mostrano il video, copiandolo dal secondo schermo.

        CHI E' L'USCITA E CHI E' LA COPIA
        ---------------------------------
        Il video esce dal motore nel riquadro del **secondo schermo**: e'
        l'unica uscita che il programma ha.  I duplicati non possono averne una
        loro, quindi ricevono i **fotogrammi** del secondario e li ridipingono
        a mano: e' la stessa copia che si faceva prima per uno schermo solo,
        con dentro il numero di schermi che l'utente ha chiesto.

        Il player dentro l'app non e' niente di tutto questo: e' l'unico posto
        dove il video non va.

        LA COPIA PARTE DAL `sink` DELL'USCITA, E SI ACCENDE DOPO
        ------------------------------------------------------
        `QMediaPlayer` ha una sola uscita video e `QVideoWidget` ha un solo
        `videoSink`.  I fotogrammi da copiare sono quelli che passano da li', e
        li' devono **esistere**: collegare gli specchi prima che l'uscita sia
        agganciata significa guardare un segnale che non emette niente, e il
        duplicato resta nero senza che nessuno dica perche'.  Per questo qui
        si riceve l'uscita gia' collegata, e non si indovina.

        OGNI SPECCHIO HA IL SUO COLLEGAMENTO
        -----------------------------------
        Chiudere un duplicato non deve spegnere gli altri, quindi ogni
        collegamento si stacca da solo e per nome: `disconnect()` senza
        argomenti stacca **tutti** gli ascoltatori di un segnale, e su un
        segnale di Qt non si sa mai chi altro e' agganciato.
        """
        self._stacca_specchi()

        if uscita is None:
            return
        if getattr(self, "_esterno", None) is None:
            # Nessun monitor esterno: non c'e' niente da copiare.  Il video e'
            # gia' nel player, mostrato dal suo riquadro diretto, e metterlo
            # in copia vuol dire spegnere l'unico riquadro che riceve il
            # video — e lasciare il player nero.
            self.video.accetta_copia(False)
            return
        if uscita is self.video.video_widget_diretto():
            # L'uscita e' il riquadro del player: non e' un monitor esterno,
            # e copiere da se' stesso non ha senso.  Vedi la nota sopra.
            return

        try:
            from SubViews import SchermoEsterno
        except ImportError:
            return

        secondario = getattr(self, "_esterno", None)

        sink = uscita.videoSink() if hasattr(uscita, "videoSink") else None
        if sink is None:
            self._esterni = []
            self._stacca_il_player_in_copia()
            return

        # IL PLAYER E' UNA COPIA COME I DUPLICATI
        # ----------------------------------------
        # Il video esce sul monitor esterno, ma **qui dentro si vede lo
        # stesso video**.  Non e' un secondo video e non un secondo audio: e'
        # lo stesso fotogramma, mostrato in due posti, e arriva dallo stesso
        # sink — quindi non costa un secondo decodifica.
        #
        # Perche' si vede anche dentro: chi sta leggendo una pubblicazione sul
        # primo monitor e chi guarda il video sull'altro sono due persone,
        # spesso nella stessa stanza.  Il primo schermo mostra l'applicazione,
        # e l'applicazione mostra anche il video: e' quello che rende utile
        # avere due schermi invece di uno solo.
        #
        # PRIMA DI GUARDARE I DUPLICATI, E SENZA CONDIZIONI
        # -------------------------------------------------
        # Prima questo pezzo stava **dopo** `if not finestre: return`, e li'
        # il pensiero sembrava giusto: «se non ci sono duplicati, non c'e'
        # niente da copiare».  Ma il player dentro l'app non e' un duplicato:
        # e' uno schermo come gli altri, e spesso e' l'unico che mostra il
        # video.
        #
        # Il difetto e' stato proprio questo: con **un solo** monitor esterno,
        # cioe' senza duplicati, la funzione tornava indietro prima di
        # arrivare qui.  L'uscita del video era gia' puntata sul monitor
        # esterno, il riquadro diretto del player non riceveva niente, e
        # dentro l'app restava un rettangolo **nero** con l'audio che
        # continuava.  Con due schermi esterni, o con un duplicato, la copia
        # si accendeva e tutto funzionava: due schermi e il video si vede
        # anche qui, uno schermo e il video si vede solo li'.
        #
        # Il video era ed e' lo stesso: e' cambiato solo il posto in cui
        # questa funzione si fermava.
        try:
            sink.videoFrameChanged.connect(self.video.imposta_frame)
            self._sink_copia_player = sink
            self.video.accetta_copia(True)
        except (TypeError, RuntimeError):
            self._sink_copia_player = None

        finestre = [f for f in SchermoEsterno.finestre(self.window())
                    if f is not secondario]
        if not finestre:
            # Nessun duplicato: e va bene cosi'.  Il player dentro l'app e'
            # gia' collegato — e' la copia che non manca mai, ed e' per questo
            # che questo `return` non lascia niente indietro.
            self._esterni = []
            return

        collegati = []
        for finestra in finestre:
            try:
                specchio = finestra.accendi_video()
                sink.videoFrameChanged.connect(specchio.imposta_frame)
                collegati.append((sink, specchio))
            except (TypeError, RuntimeError):
                # Un duplicato che non si collega non deve impedire agli altri
                # di accendersi: meglio due schermi che si vedono e uno che
                # no, che tre schermi che sembrano rotti.
                continue

        self._esterni = collegati

    def _spegni_specchi(self) -> None:
        """Il video esce qui dentro e nessuno schermo esterno lo mostra.

        Anche il player smette di essere una copia: torna a mostrare il video
        dal suo riquadro diretto.  Senza questo, chiudendo un video e
        riaprendone un altro dentro l'app si troverebbe un riquadro nero,
        perche' la copia non arriverebbe piu' e il diretto resterebbe spento.
        """
        self._stacca_specchi()
        try:
            self.video.accetta_copia(False)
            self.video.svuota_copia()
        except (AttributeError, RuntimeError):
            pass
        try:
            from SubViews import SchermoEsterno
        except ImportError:
            return
        for finestra in SchermoEsterno.finestre(self.window()):
            try:
                finestra.spegni_video()
            except RuntimeError:
                continue

    def _stacca_specchi(self) -> None:
        """Scollega tutti i fotogrammi in copia, senza toccare il video."""
        for coppia in getattr(self, "_esterni", []) or []:
            sink, specchio = coppia
            try:
                sink.videoFrameChanged.disconnect(specchio.imposta_frame)
            except (TypeError, RuntimeError):
                pass
        self._esterni = []
        # Anche la copia del player dentro l'app va staccata, e non solo
        # quella dei duplicati: senza questo, ogni video ricollegherebbe la
        # stessa funzione un'altra volta e un fotogramma verrebbe ridisegnato
        # due, tre, quattro volte — e con tre schermi accesi il programma
        # lavorerebbe sempre piu' piano, che e' il modo piu' subdolo di
        # bloccare un video.
        self._stacca_il_player_in_copia()

    def _stacca_il_player_in_copia(self) -> None:
        """Scollega la copia che il player dentro l'app mostra.

        Si tiene il `sink` usato perche' il collegamento va staccato **da
        quello**: scollegare da un sink diverso non toglie niente e lascia
        il collegamento vecchio attaccato per sempre.
        """
        sink = getattr(self, "_sink_copia_player", None)
        if sink is None:
            return
        try:
            sink.videoFrameChanged.disconnect(self.video.imposta_frame)
        except (TypeError, RuntimeError):
            pass
        self._sink_copia_player = None


    def _metti_la_copertina(self, voce: dict) -> None:
        """Un audio: nel riquadro grande ci va la copertina della canzone.

        IL REQUADRO GRIGIO CHE C'ERA PRIMA
        -----------------------------------
        Nella sezione Media, su un brano, si vedeva un rettangolo grigio senza
        niente dentro: era il posto dove la copertina avrebbe dovuto stare e
        non c'era.  Sembrava un pezzo non finito, ed era un immagine che non
        arrivava.

        Qui si mette la copertina vera, presa dalla stessa miniatura che usa la
        lista: cosi' la copertina del riquadro e quella della riga da cui si e'
        partiti sono la stessa immagine.  Con due ricerche diverse, una delle
        due arriva prima e una volta resta quella di un altro brano — e
        un'immagine sbagliata accanto a un titolo giusto non si nota subito.

        SULLA SCHERMATA ESTERNO NO
        --------------------------
        Li' la copertina non si mostra: su quello schermo si vedono solo video
        e immagini.  Una copertina di canzone accanto alla Scrittura dell'anno
        sarebbe un pezzo che non c'entra con niente.
        """
        # Un audio: il video sparisce e al suo posto c'e' la copertina,
        # grande come il riquadro che occupava.
        self.video.setVisible(False)
        self.copertina.pulito()
        self.copertina.setVisible(True)
        self._scarica_la_copertina(voce)

    def _copertina_di(self, voce: dict):
        """L'indirizzo della copertina di questa voce, o None.

        Si passa dalla stessa voce che fa partire il brano, quindi la copertina
        e' quella giusta per costruzione e non una ricerca a parte che puo'
        sbagliare il titolo.

        E' un **indirizzo**, non un percorso: chi lo usa deve scaricarlo, e non
        aprirlo come un file.  Vedi `_scarica_la_copertina`, che e' l'unico
        posto che lo usa, e il posto in cui e' successo il guasto.

        PERCHE' ADESSO C'E' `trackImage` E PRIMA NO
        ------------------------------------------
        Qui si cercava `pubSymbol` e si chiedeva il catalogo dei media
        (`CatalogoMedia.miniatura_di`).  E funzionava solo per i media che
        vengono da una pubblicazione: il mediator non scrive `pubSymbol`, e
        per tutte le categorie di Audio e Video la domanda finiva con «non
        c'e' nessuna sigla».  Il riquadro grande restava nero su un brano.

        Il mediator scrive invece l'indirizzo della locandina in
        `trackImage.url`, che e' il dato vero e non una ricerca: e' esattamente
        l'immagine di quel brano.
        """
        try:
            from Utility import Copertine

            indirizzo = Copertine.url_anteprima(voce)
            if indirizzo:
                return indirizzo
            from Utility import CatalogoMedia
            sigla = voce.get("pubSymbol") or voce.get("keySymbol") or ""
            if not sigla:
                return None
            return CatalogoMedia.miniatura_di(sigla, voce.get("language") or "I")
        except Exception:  # noqa: BLE001
            # Una copertina che non si trova non e' un guasto: il riquadro
            # resta nero e il brano si sente lo stesso.
            return None

    def _scarica_la_copertina(self, voce: dict) -> None:
        """Prende la copertina e la mette, appena arriva.

        L'INDIRIZZO NON E' UN FILE
        --------------------------
        `CatalogoMedia.miniatura_di` restituisce un **indirizzo web**, non il
        percorso di un file sul disco.  Eppure prima qui si faceva:

            self.copertina.setPixmap(QPixmap(str(indirizzo)))

        `QPixmap` accetta un nome di file.  Con `https://...` non apre
        niente, **senza dire niente**: `QPixmap` su un indirizzo fallisce in
        silenzio e restituisce una pixmap vuota.  Il risultato era un
        riquadro nero con la forma giusta — esattamente quello che e' stato
        segnalato come «lo spazio c'e' ma l'immagine non si vede».

        Nella Home la stessa immagine si vedeva perche' li' il passaggio
        giusto c'era gia': `Copertine.scarica(indirizzo)` porta a terra i
        byte e `pixmap_da_dati` li trasforma in pixmap.  Qui si fa lo stesso,
        e **in sottofondo**, perche' la scaricata di una copertina non deve
        aspettare la fine per far partire il brano: il brano parte, e la
        copertina arriva un istante dopo.

        SE IL BRANO E' FINITO PRIMA, NESSUN PROBLEMA
        ----------------------------------------------
        Il lavoro in sottofondo puo' arrivare quando l'utente ha gia' chiuso
        il lettore o e' passato a un altro brano.  Per questo il confronto
        e' con il **titolo** di adesso: se non e' piu' quello che avevamo
        chiesto, l'immagine che e' arrivata si butta.
        """
        indirizzo = self._copertina_di(voce)
        # Non basta che `_copertina_di` dia qualcosa: le voci del mediator
        # possono avere piu' misure dentro `trackImage` e nessuna delle due
        # funzioni sa quale risponde.  Si parte quando c'e' almeno un
        # indirizzo **fra tutti quelli che si conoscono**.
        if not indirizzo:
            from Utility import Copertine

            if not Copertine.indirizzi_del_media(voce):
                return
        # IL TITOLO DI **QUESTA** VOCE, E NON QUELLO DEL MOTORE
        # -----------------------------------------------------
        # Qui prima si leggeva `self.motore.titolo()`, ma a questo punto il
        # motore non ha ancora ricevuto la voce: `mostra` chiama
        # `_prepara_dove_va_il_video` **prima** di `motore.suona(...)`.
        # Catturato cosi', il titolo era quello di prima — o il vuoto — e il
        # confronto con quello di adesso non tornava mai: l'immagine che
        # arrivava veniva buttata **sempre**, anche quando era la giusta.
        #
        # Si chiede alla voce che si sta per far partire: e' la stessa prima
        # e dopo la scelta della risoluzione, che cambia l'indirizzo e non
        # il titolo.
        titolo = str(voce.get("title") or "") if isinstance(voce, dict) else ""

        portato: dict = {"dati": None}

        def lavoro() -> None:
            from Utility import Copertine
            # TUTTE le misure, non solo la prima: una puo' rispondere 403
            # mentre un'altra della stessa immagine c'e' (misurato su 18 inni
            # su 109), e allora il riquadro grande restava nero per un
            # brano che ha un'immagine e che il programma sapeva quale fosse.
            #
            # I byte finiscono in `portato` e non nel valore di ritorno: il
            # `completion` di `background` viene chiamato **senza argomenti**
            # (`_emetti(completion, delay)` e basta), quindi un
            # `def arrivati(dati)` non riceve mai niente e va a finire in un
            # `TypeError` stampato in stderr, silenzioso per l'utente.  Era
            # esattamente questo: la copertina del player grande non arrivava
            # **mai** per questo motivo, e il riquadro restava nero.
            # Si prova **tutte** le misure e si tiene la piu' grande: la
            # prima che risponde non e' per forza la migliore — e' solo
            # quella che c'e'.  Una copertina media scalata nel riquadro
            # grande e' la causa dello «sgranato» che si vedeva.
            migliori: bytes | None = None
            for candidato in Copertine.indirizzi_del_media(voce):
                dati = Copertine.scarica(candidato)
                if dati and (migliori is None or len(dati) > len(migliori)):
                    migliori = dati
            if migliori is None and indirizzo:
                # Il ripiego: l'indirizzo del catalogo dei media, per le voci
                # che non hanno `trackImage` ma hanno una sigla.
                migliori = Copertine.scarica(indirizzo)
            portato["dati"] = migliori

        def arrivati() -> None:
            from PyQt6 import sip
            from Utility.Copertine import pixmap_da_dati
            dati = portato["dati"]
            if sip.isdeleted(self.copertina):
                return
            # Il brano e' cambiato nel frattempo: questa copertina non e' piu'
            # di nessuno.  Il motore si guarda **adesso**, quando l'immagine
            # arriva, perche' era li' il difetto: prima il titolo veniva
            # catturato prima che il brano partisse.
            #
            # Se uno dei due titoli e' vuoto non si butta niente: un titolo
            # che non si sa non e' un titolo diverso, e la regola serve solo
            # a non mostrare l'immagine di un brano sotto il titolo di un
            # altro.
            attuale = (self.motore.voce()
                       if hasattr(self.motore, "voce") else None)
            attuale_titolo = (str(attuale.get("title") or "")
                              if isinstance(attuale, dict) else "")
            if attuale_titolo and titolo and attuale_titolo != titolo:
                return
            if not dati:
                return
            self.copertina.metti(pixmap_da_dati(dati))

        from Utility.Extensions.Ext_DispatchQueue import background
        background(lavoro, completion=arrivati)

    def _ripiccolato(self) -> None:
        """La freccia giù: da schermata grande a striscia piccola.

        Qui non si fa niente: si dice solo che l'utente l'ha premuta.  Il
        lettore non sa cosa sia la striscia in fondo alla finestra ne' come si
        torna alla sezione di prima, e provare a indovinarlo qui vuol dire mettere
        dentro il lettore pezzi della finestra.

        E' la stessa regola di `schermoIntero`, che pure non tocca niente e si
        limita a segnalare.
        """
        self.ripiccolato.emit()

    def abbassa(self) -> None:
        """Nascondi il lettore grande, **senza fermare** il brano.

        E' quello che fa la freccia gi'.  Non e' `chiudi()`, che chiama
        `motore.ferma()`: la freccia gi' serve per continuare a sentire mentre
        si gira per l'app, e un `ferma()` la farebbe l'unica cosa che l'utente
        non voleva.

        Non si stacca niente dal motore: il video resta agganciato al suo
        riquadro e la posizione resta dov'e'.  Per questo riaprire e' una riga —
        vedi `alza` — e non un riavvio.

        Sullo schermo esterno non si tocca niente: un video che continua a
        suonare li' deve continuare a vedersi li', e un audio non ha niente da
        cambiare in ogni caso.
        """
        self.setVisible(False)

    def alza(self) -> None:
        """Ritira il lettore grande: e' quello che fa la freccia su'.

        Il brano non riparte e il video non si ricollega: sono rimasti attaccati
        per tutto il tempo in cui il lettore era abbassato, quindi qui basta
        mostrarlo.  E' il motivo per cui `abbassa` non stacca niente — staccarlo
        qui dentro costerebbe un riavvio del video per un gesto che non cambia
        niente di quello che si vede.

        LA COPERTINA SI RIMETTE, SE E' UN AUDIO
        ---------------------------------------
        Un audio partito da una notizia non passa da `mostra`: il motore parte
        direttamente, e il lettore grande potrebbe avere ancora la copertina
        del brano precedente.  Qui si riprende la voce che sta suonando e si
        rimette la sua copertina.  La chiamata e' sicura anche per un audio
        normale: la copertina e' gia' in cache e non riparte niente.
        """
        voce = self.motore.voce() if hasattr(self.motore, "voce") else None
        if isinstance(voce, dict) and voce and not _e_video(voce):
            self._metti_la_copertina(voce)
        self.setVisible(True)

    def chiudi(self) -> None:
        """Torna alla lista.

        IL VIDEO FERMA E LO SCHERMO SECONDARIO TORNA AL VERSETTO
        ---------------------------------------------------------
        Uscendo dalla sezione il video si ferma, e lo schermo secondario non
        resta nero a caso: torna a mostrare il verso del giorno.  E' il posto
        dove si trova la stessa voce della Home, quindi lo schermo non e'
        vuoto ne' spento.

        La finestra a tutto schermo dentro l'app invece si chiude come sempre,
        perche' quella la sta usando l'utente e ha i suoi comandi.
        """
        self._in_chiusura = True
        try:
            self.motore.ferma()
        finally:
            self._in_chiusura = False
        # IL SECONDO SCHERMO SMETTE DI MOSTRARE IL VIDEO, E TORNANO AL VERSO
        # ----------------------------------------------------------------
        # Prima si spegne la copia dei fotogrammi e poi si riaccende la
        # stacca: senza video che gira, uno specchio che continua a ricevere
        # fotogrammi mostrerebbe l'ultimo fotogramma e sembrerebbe un video
        # fermo.
        self._spegni_specchi()
        self.copertina.pulito()
        self.copertina.setVisible(False)
        self.avviso.setVisible(False)
        self.video.setVisible(True)
        finestra = getattr(self, "_finestra", None)
        if finestra is not None and not finestra._comandi_utili():
            finestra.chiudi()
        self.setVisible(False)
        self.chiuso.emit()

    def _commuta(self) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer

        suona = (self.motore.player.playbackState()
                 == QMediaPlayer.PlaybackState.PlayingState)
        if suona:
            self.motore.sospendi()
        else:
            self.motore.continua()

    def _volume(self, valore: int) -> None:
        self.motore.volume(valore / 100.0)

    def _spostato(self, posizione: int) -> None:
        """Il video va dove ha portato il mouse, in secondi.

        IL DIFETTO CHE C'ERA
        -------------------
        Il cursore ragiona in **secondi** (`setRange(0, durata // 1000)`),
        ma `volta_alla_posizione` vuoi i **millisecondi** di Qt: lo si vede
        dagli altri due chiamanti, che saltano di `±10000` per andare di
        dieci secondi.  Passando i secondi così come sono, trascinando il
        video finiva quasi sempre all'inizio: 200 secondi diventavano 200
        millisecondi, cioe' niente.  E' per questo che la barra «non
        andava avanti» anche trascinandola.

        Qui la conversione e' messa per nome, in un posto solo.
        """
        self.motore.volta_alla_posizione(posizione * 1000)

    def _schermo_intero(self) -> None:
        """Il tasto di tutto schermo, con e senza monitor esterni.

        CON UN MONITOR ESTERNO IL TASTO NON FA NULLA
        -------------------------------------------
        Il video e' gia' a tutto schermo sul monitor esterno: e' esattamente
        quello che il tasto chiederebbe.  Portarlo dentro l'app non e' quello
        che si puo' fare, perche' sul primo monitor il video non ci va e una
        finestra a tutto schermo li' coprirebbe l'applicazione.

        Quindi il tasto dice, in una riga, che il video e' gia' a schermo
        intero e su quale schermo.  Un tasto che premendo non cambia niente
        sembra rotto; se invece spiega perche', l'utente capisce e va a
        guardarlo.

        SENZA MONITOR ESTERNO: IL LAVORO DI SEMPRE
        -----------------------------------------
        Un solo schermo, quindi niente schermi esterni: il video e' dentro
        l'app e il tasto lo porta a tutto schermo in una finestra separata,
        come ha sempre fatto.  E se la finestra era aperta, la chiude:
        un tasto che torna su se' stesso e' un tasto che si capisce da solo.
        """

        # IL SECONDO SCHERMO, QUANDO C'E': IL TASTO NON FA NULLA
        # ------------------------------------------------------
        # Il video e' gia' **a tutto schermo** sul monitor esterno: e' quello
        # che e' stato premuto il tasto.  Non c'e' niente da ingrandire, e la
        # cosa da non fare e' portarlo dentro l'app — che sul primo monitor
        # il video non ci va, e una finestra a tutto schermo li' coprirebbe
        # proprio l'applicazione.
        #
        # Quindi con un monitor esterno il tasto non fa niente, e **dice**
        # che non fa niente.  Un tasto che premendo non cambia niente e non
        # spiega perche' sembra rotto; se invece spiega, l'utente capisce che
        # il video e' gia' a schermo intero e va a guardarlo.
        #
        # PRIMA QUI C'ERA UNA TRAPPOLA
        # ----------------------------
        # C'era un `_rientrato()` chiamato in ogni caso, che riportava il
        # video nel player.  Oltre a portare il video sul primo monitor — che
        # e' la cosa che non si deve fare — spegneva anche i duplicati, che
        # l'utente aveva spuntato un secondo prima nelle impostazioni.
        esterno = getattr(self, "_esterno", None)
        if esterno is None:
            esterno = _finestra_esterna(self.window())
        if esterno is not None:
            self.avviso.setText(
                f"Il video e' gia' a tutto schermo "
                f"{self._dove_si_vede_il_video()}.")
            self.avviso.setVisible(True)
            return

        # SENZA MONITOR ESTERNO: IL TASTO FA IL SUO LAVORO
        # -------------------------------------------------
        # Un solo schermo: il video e' dentro l'app, e il tasto lo porta a
        # tutto schermo come ha sempre fatto.
        from SubViews.LettoreSchermo import LettoreSchermo

        finestra = getattr(self, "_finestra", None)
        if finestra is None:
            finestra = LettoreSchermo()
            finestra.rientrato.connect(self._rientrato)
            self._finestra = finestra
        # La finestra da cui si parte serve al lettore per mettere il
        # video a tutto schermo sullo **stesso** schermo di questa
        # finestra: prima sceglieva sempre il primario, quindi con due
        # monitor il video finiva dove non stava l'app.  Vedi
        # `LettoreSchermo._scegli_schermo`.
        finestra.guarda(self.motore, self.window())
        self.schermoIntero.emit(True)

    def _rientrato(self) -> None:
        """Il video torna qui dentro l'app.

        Vale per due casi, ed e' la stessa cosa in entrambi: la finestra a
        tutto schermo si e' chiusa, oppure l'utente ha premuto il tasto di
        tutto schermo per riprendere il video vicino ai comandi.

        In entrambi i casi lo schermo secondario — se c'e' — torna a mostrare
        il verso del giorno, perche' il video non e' piu' li'.  Senza questo,
        lo schermo secondario resterebbe con l'ultimo fotogramma del video
        fermo: sembrerebbe che il video sia ancora in riproduzione, e la
        riga dei comandi dentro l'app direbbe che e' fermo.
        """
        esterno = getattr(self, "_esterno", None)
        if esterno is None:
            esterno = _finestra_esterna(self.window())
        if esterno is None:
            # UN SOLO MONITOR: IL VIDEO VA RIMESSO QUI DENTRO
            # ---------------------------------------------------
            # Qui il commento diceva «il video e' gia' dentro l'app e non
            # c'e' niente da rimettere», e l'affermazione era vera **prima**
            # che esistesse la finestra a tutto schermo.  Non e' piu' vera.
            #
            # `LettoreSchermo.guarda` chiama `motore.al_video(il proprio
            # widget)`: l'uscita video e' stata **spostata** sulla finestra a
            # tutto schermo, e quella finestra non sparisce — viene chiusa,
            # ma il widget dentro resta e resta collegato all'uscita.
            #
            # Quindi, senza queste righe, l'uscita resta su un widget che non
            # si vede piu': il player grande resta con l'ultimo fotogramma
            # (quello attaccato al file, l'immagine di copertina) e il video
            # e' fermo.  Il sintomo e' «l'ho chiuso a tutto schermo e ora
            # resta fermo con l'immagine del primo fotogramma», e la cosa che
            # lo rende difficile da vedere e' che **tornando a tutto schermo
            # funziona di nuovo**: la finestra riapre e riprende come prima, e
            # sembra che il difetto sia la finestra piccola invece che il
            # passaggio dall'una all'altra.
            #
            # Si rimette quindi l'uscita sul riquadro diretto e si stacca la
            # copia: e' la stessa operazione del ramo «un solo monitor» di
            # `_prepara_dove_va_il_video`, e non per caso — e' lo stesso fatto.
            riquadro = self.video.video_widget_diretto()
            self._stacca_il_player_in_copia()
            self.video.accetta_copia(False)
            self.video.setVisible(True)
            self.copertina.setVisible(False)
            self.avviso.setVisible(False)
            self.avviso.clear()
            self.motore.al_video(riquadro)
            self.setVisible(True)
            self.videoMoved.emit()
            self.schermoIntero.emit(False)
            return

        # IL VIDEO TORNA SUI MONITOR ESTERNI
        # -----------------------------------
        # «Rientrato» vuol dire che il video **torna fuori** dall'app: il
        # tasto di tutto schermo lo aveva portato dentro, e ora torna dov'era.
        # Quindi l'uscita e' di nuovo il riquadro del secondo schermo, e il
        # player torna a non mostrare il video.
        riquadro = esterno.uscita_video()
        self.motore.al_video(riquadro)
        # TUTTE le finestre vanno a video, non solo la prima: un duplicato che
        # restasse col verso mentre il secondo mostra il video non sarebbe una
        # copia del secondo, e uno schermo con la Scrittura dell'anno accanto
        # a un video e' una schermata sbagliata.
        for finestra in self._finestre_esterne():
            finestra.mostra_video()
        self._accendi_specchi(riquadro)
        self.video.setVisible(False)
        self.copertina.setVisible(False)
        self.avviso.setText(
            f"A schermo intero {self._dove_si_vede_il_video()}. "
            "Qui sotto i comandi.")
        self.avviso.setVisible(True)
        self.setVisible(True)
        self.videoMoved.emit()
        self.schermoIntero.emit(False)

    def _tasto_video(self, _sorgente: str) -> None:
        """C'e' un video da mettere in qualche parte."""
        self.setVisible(True)

    def _vuoto(self) -> None:
        """Non c'e' piu' niente da mostrare: il lettore si chiude del tutto.

        Il motore svuotato (fine del brano) chiude il lettore come la X.  Se la
        chiusura l'ha chiesta `chiudi()` stessa, ci pensa lei.
        """
        if not getattr(self, "_in_chiusura", False):
            self.chiudi()

    # ------------------------------------------------------------------

    def _mosso(self, posizione: int, durata: int) -> None:
        if durata > 0:
            self.posizione.setRange(0, durata // 1000)
        else:
            # Il server non ha ancora detto quanto dura.  Senza questo la
            # barra resterebbe con il massimo a zero e non si muoverebbe,
            # e sembrerebbe un video fermo invece che uno di cui non si sa
            # ancora la durata.
            self.posizione.setRange(0, 0)
        self.posizione.blockSignals(True)
        self.posizione.setValue(posizione // 1000)
        self.posizione.blockSignals(False)
        self.durata.setText(tempo_corto(posizione, durata))

    def _stato(self, suona: bool, c_e_video: bool) -> None:
        """Cambia la faccia del pulsante e dice se c'e' il pulsante schermo.

        Il pulsante dello schermo intero c'e' solo se c'e' un video: su un
        brano non ci sarebbe niente da espandere, e un pulsante che porta
        a una finestra nera sembra un difetto.  Lo stesso vale per il tasto
        della risoluzione, per lo stesso motivo e per lo stesso errore.
        """
        # Il `try` non e' paranoia: questo metodo viene chiamato dentro un
        # segnale di Qt, quindi dal codice di C++.  Un'eccezione qui dentro
        # fa `abort()` e la finestra sparisce senza lasciare nessuna riga di
        # traceback — e succedeva, per il `setIcon` che non esiste.
        try:
            nome = "pause.fill" if suona else "play.fill"
            self.pulsante_play.set_glifo(nome, 20)
            self.pulsante_play.setToolTip("Ferma" if suona else "Riproduci")
            self.pulsante_schermo.setVisible(c_e_video)
            self.pulsante_risoluzione.setVisible(c_e_video)
            self.giacche.setVisible(not c_e_video)
        except Exception:  # noqa: BLE001
            import traceback
            print("Lettore: errore nel cambiare i comandi ⚠️")
            traceback.print_exc()

    def imposta_callback_visibilita(self, callback) -> None:
        """Imposta callback chiamato quando il lettore viene mostrato/nascondo.

        Serve per sincronizzare il tasto mini player (freccia giù):
        - Lettore visibile (large) → tasto VISIBILE
        - Lettore nascosto (mini) → tasto NASCOSTO
        """
        self._on_visibilita_cambiata = callback

    def imposta_mini_player_visibile(self, visibile: bool) -> None:
        """Mostra/nasconde il tasto mini player (freccia giù).

        SERVE PER DUE CASI:
        -------------------
        1. Fullscreen vero (LettoreSchermo): quando il video va a tutto schermo
           in una finestra a parte, il mini player non ha senso.  Il segnale
           `schermoIntero` chiama questo metodo con False/True.
        2. Sync con visibilità lettore: MediaView imposta callback che chiama
           questo metodo quando il lettore viene mostrato/nascondo (mini↔large).
        """
        self.pulsante_ripiccola.setVisible(visibile)

    def setVisible(self, visibile: bool) -> None:
        """Mostra o nascondi il lettore, e **dillo** a chi ascolta.

        IL SEGNALE PARTE SOLO QUANDO CAMBIA
        -----------------------------------
        `setVisible` viene chiamato spesso anche per ridirlo com'era', e un
        segnale a ogni chiamata farebbe ridipingere la striscia in fondo
        senza motivo.  Si guarda la visibilita' richiesta in precedenza e si
        segnala solo il cambiamento vero.

        E si segnala **quello che e' stato chiesto**, non quello che Qt
        dice: quando l'utente e' in un'altra sezione il lettore non e'
        "visibile" per Qt, ma non e' per questo che la striscia in fondo
        debba spegnersi — l'utente non sta guardando il lettore perche'
        sta guardando un'altra sezione, e li' i comandi gli servono.
        """
        voluto = bool(visibile)
        cambia = voluto != bool(getattr(self, "_visibile_comandata", False))
        self._visibile_comandata = voluto
        super().setVisible(voluto)
        if self._on_visibilita_cambiata:
            self._on_visibilita_cambiata(voluto)
        if cambia:
            self.visibilitaCambiata.emit(voluto)

    def _cambiata_risoluzione(self, scelta: str) -> None:
        """Cambia la risoluzione, e il tasto mostra quella che e' in uso.

        Il cambio lo fa il motore, che e' l'unico che sa la posizione e lo
        stato: vedi `Lettore.cambla_risoluzione`.  Qui si rimette il tasto a
        posto perche' il motore ha riscritto la voce con la risoluzione che ha
        potuto usare davvero — che, se quella scelta non esisteva in questo
        video, non e' quella che e' stata chiesta.
        """
        self.motore.cambla_risoluzione(scelta)
        self.pulsante_risoluzione.metti_voce(self.motore.voce())


class _Cursore(QSlider):
    """Il cursore del tempo: si clicca e si trascina, come in ogni lettore.

    PERCHE' NON BASTA `QSlider`
    --------------------------
    Un `QSlider` di Qt ha due comportamenti che non sono quelli di un
    lettore, e sono entrambi sbagliati per un video:

    - **cliccando sulla barra** non porta a quel punto: fa un *passo di
      pagina*, cioe' avanza o indietregge di un pezzo fisso.  Cliccando al
      terzo del video non ci si va al terzo del video.
    - **trascinando** funziona solo se si prende la maniglia esatta; premendo
      sulla barra piena non si trascina niente.

    Qui il clic porta al punto premuto e il trascinamento parte da li', quindi
    il cursore si usa come in qualsiasi lettore: clic dove vuoi e il video
    va li', tieni premuto e porti dove vuoi.

    IL CALCOLO DEL PUNTO
    -------------------
    Non si fa con una divisione sul valore massimo, perche' la maniglia ha
    una larghezza: il centro del cursore va dal centro della maniglia a
    sinistra al centro della maniglia a destra, e non dagli estremi della
    barra.  Con la divisione sbagliata i primi e gli ultimi secondi sono
    irraggiungibili — e sono esattamente quelli dove serve andare.

    La posizione si chiede al **stile** che disegna il cursore
    (`subControlRect` della scanalatura e della maniglia): e' il posto che
    sa dove stanno, e funziona anche se il tema cambia la forma della
    maniglia o le margini della barra.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, padre)
        self._trascinando = False

    # -- la geometria vera della barra ---------------------------------

    def _scanalatura_e_maniglia(self) -> tuple:
        """Dove comincia e finisce la corsia, in pixel.

        Ritorna `(da, a)`: i due punti in cui puo' andare il **centro** della
        maniglia.  Se non si riesce a chiederlo allo stile, si usa tutta la
        larghezza: e' peggio di qualche pixel all'estremi, ma funziona, e
        una barra che non si muove e' molto peggio.
        """
        opzione = QStyleOptionSlider()
        self.initStyleOption(opzione)
        stile = self.style()
        scanalatura = stile.subControlRect(
            QStyle.ComplexControl.CC_Slider, opzione,
            QStyle.SubControl.SC_SliderGroove, self)
        maniglia = stile.subControlRect(
            QStyle.ComplexControl.CC_Slider, opzione,
            QStyle.SubControl.SC_SliderHandle, self)
        semi = max(1, maniglia.width() // 2)
        da = scanalatura.x() + semi
        a = scanalatura.x() + scanalatura.width() - semi
        if a <= da:
            da, a = 0, max(1, self.width())
        return da, a

    def _valore_da(self, x: int) -> int:
        """Il valore che corrisponde a quel punto della barra."""
        da, a = self._scanalatura_e_maniglia()
        corsia = a - da
        if corsia <= 0:
            return self.minimum()
        passi = (x - da) / corsia
        valore = self.minimum() + round(passi * (self.maximum() - self.minimum()))
        return max(self.minimum(), min(self.maximum(), valore))

    # -- il mouse -------------------------------------------------------

    def mousePressEvent(self, evento) -> None:
        """Clic: si va a quel punto e si comincia a trascinare da li'.

        Si va al punto subito, senza aspettare di muovere il mouse: cliccare
        e fermarsi deve gia' spostare il video, altrimenti sembra che il
        clic non sia registrato.
        """
        if evento.button() == Qt.MouseButton.LeftButton:
            self._trascinando = True
            self.setValue(self._valore_da(evento.position().x()))
            # Si avvisa con `sliderMoved` e non con `valueChanged`: e' il
            # segnale a cui il lettore e' collegato, e dice «l'utente sta
            # muovendo la posizione», che e' quello che e' successo.
            self.sliderMoved.emit(self.value())
            evento.accept()
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:
        """Trascinamento: il video segue il mouse."""
        if self._trascinando:
            self.setValue(self._valore_da(evento.position().x()))
            self.sliderMoved.emit(self.value())
            evento.accept()
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:
        """Finito il trascinamento: il video resta dove e' arrivato."""
        if self._trascinando:
            self._trascinando = False
            evento.accept()
            return
        super().mouseReleaseEvent(evento)

    def keyPressEvent(self, evento) -> None:
        """Le frecce e la spaziatura vanno sempre avanti e indietro."""
        super().keyPressEvent(evento)


class _Bottone(QLabel):
    """Un comando del lettore: un glifo che si preme.

    Una `QLabel` come `_Card` e `_SchedaCliccabile`, per lo stesso motivo:
    se non c'e' niente da premere non deve sembrare premibile.  Qui pero'
    c'e' sempre qualcosa da fare, e il pulsante e' una `QPushButton` solo
    per avere l'effetto di passaggio del mouse senza scriverlo a mano.
    """

    premuto = Signal()

    def __init__(self, simbolo: str, tooltip: str, padre=None,
                 lato: int = 28, luce: bool = False) -> None:
        super().__init__(padre)
        # Il glifo e' sempre un quarto del pulsante: con un pulsante da 32 il
        # glifo da 20 sembra piccolo dentro, e con uno da 28 va bene.  La
        # proporzione e' la regola, e la misura la sceglie chi costruisce.
        self.set_glifo(simbolo, max(16, lato - 8))
        self.setFixedSize(lato, lato)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # LA RETROILLUMINAZIONE, SOLO SE LA SI CHIEDE
        # --------------------------------------------
        # Il nome del foglio di stile e' quello che fa illuminare il pulsante
        # quando il mouse ci passa sopra: `:hover` lo mette nel foglio di
        # stile, e senza un nome non si puo' distinguere questo pulsante dagli
        # altri.
        #
        # Perche' dietro una scelta e non sempre: dentro l'app il lettore ha
        # gia' uno sfondo scuro tutto suo (`comandiLettore`), e aggiungere
        # un'illuminazione li' cambierebbe un pezzo di programma che non
        # c'entra.  Qui si accende solo dove serve, e si dichiara.
        if luce:
            self.setObjectName("bottoneLuce")

    def set_glifo(self, simbolo: str, lato: int = 20) -> None:
        """Cambia il disegno del pulsante.

        Si chiama `set_glifo` e non `setIcon` perche' `_Bottone` e' una
        `QLabel`, e `QLabel` non ha `setIcon`: chiamarlo dava

            AttributeError: '_Bottone' object has no attribute 'setIcon'

        dentro `_stato`, che e' un segnale di Qt, quindi dentro C++: la
        finestra chiude senza nessuna riga di traceback.  Il nome `set_glifo`
        e' diverso da quello di `QPushButton` **di proposito**: se un domani
        la classe cambiasse diventando un pulsante, `setIcon` funzionerebbe e
        `set_glifo` no, e si scopre subito invece di rompere in silenzio.
        """
        self.setPixmap(icon(simbolo, "#ffffff", lato).pixmap(lato, lato))

    def mousePressEvent(self, evento) -> None:
        """Il tasto sinistro emette `premuto` e basta.

        Dopo aver emesso **non** si passa il evento a `QLabel`, e la ragione
        e' un difetto misurato: se il gestore di `premuto` distrugge o
        ricostruisce qualcosa — e succede, per esempio quando il tasto apre una
        finestra — la riga `super().mousePressEvent(evento)` va a chiamare un
        metodo su un oggetto C++ gia' distrutto, e Qt butta giu' il programma
        con

            RuntimeError: wrapped C/C++ object of type _Bottone has been deleted

        dentro il ciclo di eventi, quindi senza poterlo fermare.  A una `QLabel`
        con dentro solo un disegno il click sinistro non serve a niente, quindi
        non si perde niente a non inoltrarlo.
        """
        if evento.button() == Qt.MouseButton.LeftButton:
            self.premuto.emit()
            evento.accept()
            return
        super().mousePressEvent(evento)


class _TastoRisoluzione(_Bottone):
    """Il tasto che apre l'elenco delle risoluzioni del video.

    IL MENU E' ADATTIVO, E NON UN ELENCO FISSO
    ------------------------------------------
    Le voci sono quelle che il server ha dato **per quel video**: se c'e' il
    1080p viene proposto, e se non c'e' non viene nemmeno scritto.  Non si
    scrive una lista fissa di "240p, 480p, 720p, 1080p" perche' sarebbe una
    promessa: il 1080p e' raro, e su un video che non ce l'ha la voce
    prometterebbe una risoluzione che non si puo' scegliere.

    La prima voce e' sempre «Automatica», che e' il default: la risoluzione si
    sceglie misurando la casella che mostra il video, ed e' quello che faceva
    il programma fin dall'inizio.

    LA SPIUNTA STA SU QUELLO CHE STA GIRANDO
    -----------------------------------------
    Non su quello che l'utente aveva chiesto.  Sono due cose diverse quando la
    scelta non e' applicabile a quel video: chi ha chiesto il 1080p e poi apre
    un video che arriva solo a 720p vede il 720p che gira e la spunta sul
    720p.  Una spunta sull'opzione non scelta sembrerebbe un tasto rotto.

    Percio' la spunta la decide `Mediator.scegli_risoluzione`, che e' l'unico
    posto che ha guardato tutte le risoluzioni e ha deciso quale si puo' usare.

    IL MENU SALE VERSO L'ALTO
    ------------------------
    Il tasto e' in fondo alla barra, e un menu che si aprirebbe in giu' uscirebbe
    dallo schermo.  Per questo il punto in cui compare si mette a mano, con
    `popup()` e non `exec()`: si dice «qui, e precisamente qui», invece di
    chiedere a Qt di aprirlo dove vuole lui.
    """

    #: La scelta, come si scrive: `""` per automatica, un'etichetta ("720p")
    #: o una posizione ("bassa", "media", "alta").
    scelta = Signal(str)

    def __init__(self, padre=None, lato: int = 28) -> None:
        super().__init__("change-video-resolution", "Risoluzione del video",
                         padre, lato)
        self._voce: dict = {}
        # Quello che sta girando davvero, che non e' sempre quello che e' stato
        # scelto.  Vedi la spunta, sopra.
        self._in_uso = ""
        # Il menu nasce qui e non a ogni apertura.
        #
        # Prima veniva costruito nuovo ogni volta, con il tasto come padre: e
        # un `QMenu` non si distrugge da solo, quindi dopo ogni video guardato
        # restava li' un menu che nessuno guardava piu'.  Dopo un'ora di
        # video, con venti video, sono venti menu e venti azioni ciascuno
        # ancora in memoria.  Nessuno se ne accorgerebbe — il programma non si
        # rompe — ma e' spazzatura che cresce e che si vede con il tempo.
        self._menu: QMenu | None = None

    def metti_voce(self, voce: dict) -> None:
        """Ricorda la voce che sta suonando: serve a costruire il menu."""
        self._voce = voce or {}
        self._in_uso = str(self._voce.get("risoluzioneInUso") or "")

    def mousePressEvent(self, evento) -> None:
        """Il tasto apre il menu, e non emette `premuto`.

        `_Bottone` emette `premuto`, che qui non serve a niente: e' il tasto
        della risoluzione, e l'unica cosa che fa e' aprire il menu.  Emettere
        anche `premuto` non romperebbe niente oggi, ma lascerebbe a un collega
        di domani un segnale che sembra dire «e' stato premuto il tasto» e che
        non ha nessun ascolto.
        """
        if evento.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(evento)
            return
        evento.accept()
        self._apri_il_menu()

    def _voci_in_scalata(self) -> list:
        """Le etichette di quel video, **dalla piu' grande alla piu' piccola**.

        L'ordine e' quello che si aspetta chi guarda: in cima la piu' nitida e in
        fondo la piu' leggera, che e' anche la piu' veloce.  Andare dal basso in
        alto metterebbe 240p per primo e 720p in fondo, e sembrerebbe che la
        qualita' diminuisca scendendo, che e' il contrario di quello che si
        sceglie.

        Si ordina sui **pixel** e non sull'etichetta: "720p" scritto nella sigla
        potrebbe essere un'etichetta e i pixel no.  E si tiene l'ordine del
        server per i pixel uguali, perche' non si inventa una differenza dove non
        c'e' — due file con la stessa larghezza sono la stessa risoluzione e
        l'ordine in cui il server li ha mandati non ha importanza.
        """
        voci = [str(r.get("label") or "")
                for r in self._voce.get("risoluzioni") or []
                if r.get("label")]
        larghezze = {}
        for r in self._voce.get("risoluzioni") or []:
            etichetta = str(r.get("label") or "")
            if etichetta and etichetta not in larghezze:
                try:
                    larghezze[etichetta] = int(r.get("frameWidth") or 0)
                except (TypeError, ValueError):
                    larghezze[etichetta] = 0
        voci.sort(key=lambda e: -larghezze.get(e, 0))
        return voci

    def _apri_il_menu(self) -> None:
        """Costruisce il menu di quel video e lo apre sopra il tasto."""
        voci = self._voci_in_scalata()
        if len(voci) < 2:
            # Un file solo, o nessuno: non c'e' niente da scegliere.  Un menu
            # con una voce sola sembra un comando che non funziona, quindi non
            # si apre e non si dice niente: il tasto semplicemente non fa niente.
            return

        # Quello che sta girando davvero decide la spunta, non quello che e'
        # stato chiesto.  Sono due cose diverse quando la scelta non e'
        # applicabile a questo video — il 1080p su un video che arriva a
        # 720p — e senza questa distinzione non si accenderebbe niente, e un
        # menu senza spunta sembra un tasto che non sa cosa sta facendo.
        #
        # Sulla spunta c'e' un patto con l'utente: quello che vede acceso e'
        # quello che sta girando.  Cambiare voce cambia il file, quindi la
        # spunta non mente mai.
        from Utility import tema
        salvata = tema.risoluzione_video()
        # Una posizione ("bassa", "media", "alta") non e' un'etichetta e quindi
        # non puo' accendersi: e' quello che si e' chiesto, ma il file vero
        # lo sceglie il motore e cambia da un video all'altro.  La spunta va
        # quindi su «Automatica», che e' la voce che descrive un video deciso
        # dal programma e non dall'utente voce per voce.
        if not salvata or salvata == AUTOMATICA or salvata in PER_TAGLIO:
            su_automatica, accesa = True, None
        elif salvata in voci:
            su_automatica, accesa = False, salvata
        else:
            # Scelta non applicabile a questo video: la spunta va su quello che
            # sta girando, che e' quello che l'utente sta guardando.
            su_automatica = False
            accesa = self._in_uso if self._in_uso in voci else None

        # Un menu solo, svuotato e rifatto: vedi `__init__` perche' non uno
        # nuovo ogni volta.
        if self._menu is None:
            self._menu = QMenu(self)
        menu = self._menu
        menu.clear()
        autom = menu.addAction("Automatica")
        autom.setCheckable(True)
        autom.setChecked(su_automatica)
        autom.triggered.connect(lambda: self.scelta.emit(""))
        for etichetta in voci:
            azione = menu.addAction(etichetta)
            azione.setCheckable(True)
            azione.setChecked(etichetta == accesa)
            scelta_reale = etichetta
            azione.triggered.connect(
                lambda _controllato=False, v=scelta_reale: self.scelta.emit(v))
        self._punta_su(menu)

    def _punta_su(self, menu) -> None:
        """Mette il menu sopra il tasto, e dentro lo schermo.

        Il punto si calcola a mano perche' il tasto sta in fondo alla barra: il
        menu di Qt si apre sotto il cursore, e sotto il cursore, in fondo alla
        finestra, non c'e' niente.  `popup()` e non `exec()`: `exec()` apre e
        **blocca** fino a quando non si sceglie, e serve quando si vuole
        aspettare la risposta; qui si sceglie e si torna, e bloccare sarebbe
        inutile.
        """
        alto = menu.sizeHint().height()
        largo = menu.sizeHint().width()
        angolo = self.mapToGlobal(QPoint(0, 0))
        # Centrato sul tasto e non allineato a sinistra: il tasto e' stretto e
        # il menu no, e con la sinistra allineata il menu penderebbe a destra.
        x = angolo.x() + self.width() // 2 - largo // 2
        y = angolo.y() - alto
        schermo = self.screen()
        if schermo is not None:
            area = schermo.availableGeometry()
            # Se non ci sta sopra — tasto in cima, o schermo basso — si apre
            # sotto.  Meglio un menu che copre il video che un menu fuori
            # dallo schermo, che non si vede e non si sa come sia chiuso.
            if y < area.top():
                y = angolo.y() + self.height()
            # E in orizzontale non si esce dal bordo destro, che e' dove il
            # tasto sta: e' la parte che si vede tagliata.
            x = max(area.left(), min(x, area.right() - largo))
        menu.popup(QPoint(int(x), int(y)))