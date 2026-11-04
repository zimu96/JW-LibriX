"""La finestra dello schermo secondario: video e figure, e niente'altro.

QUANDO ESISTE
-------------
Solo se nelle impostazioni e' stato scelto uno schero.  Con «dove sta la
finestra» questa finestra non viene creata e tutto va come prima: il video a
tutto schermo parte quando lo si preme, sullo schermo dove sta l'app.

PERCHE' STA APERTA, E NON SI CHIUDE
----------------------------------
Il video ci va da solo, appena parte: non si preme nessun tasto.  E quando il
video finisce — l'utente esce dalla sezione, o sceglie un altro video — lo
schermo secondario non resta nero a caso, torna a mostrare la Scrittura
dell'anno.

Quindi la finestra non si chiude mai.  Se si chiudesse, al video successivo
non ci sarebbe piu' niente su cui mostrarlo, e servirebbe un tasto per
riaprirla: e' esattamente il tasto che si voleva evitare.

Per questo non ha comandi e non si chiude con nessun clic: non c'e' niente da
controllare qui dentro, e un clic che chiude sarebbe solo un modo per
ritrovarsi con lo schermo spento e il video che continua senza comparire da
nessuna parte.

I DUE CONTENUTI
---------------
Video e figure non possono stare insieme: il player e' uno solo in tutto il
programma e ha **una** uscita video.  Quindi chi riceve l'uno esce dal campo
all'altro.  La pila (`QStackedWidget`) e' il posto giusto per dirlo al
programma: una pagina per volta, e non si deve ricordare quale fosse.

LA SCRITTURA DELL'ANNO QUANDO NON C'E' NIENTE
----------------------------------------------
Uno schermo acceso e vuoto e' uno schermo che non serve a niente: si vede
che e' acceso e basta.

Qui dentro c'era il **verso del giorno**, cioe' la data.  Adesso c'e' la
**Scrittura dell'anno**: la frase che sta sulla pagina degli editori di
«Esaminiamo le Scritture ogni giorno del <anno>», presa dal pacchetto
scaricato.

La differenza non e' cosmetica.  La data la dice anche il programma, e non da
niente; e sul monitor secondario si guarda a un braccio e mezzo, dove 15
pixel non si leggono.  La Scrittura dell'anno e' l'unica riga che si puo'
leggere da lontano, e cambia una volta all'anno invece che ogni giorno — quindi
non invecchia.

E quando la pubblicazione non e' scaricata, la finestra **lo dice**, con il
nome della pubblicazione da cercare: uno schermo che dice «non hai scaricato
questa cosa» e' un invito a premere il tasto di Scaricati, e uno schermo vuoto
no.  Vedi `HomeView.scrittura_dell_anno`.
"""

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtSignal as Signal,
)
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from SubViews.LettoreView import SpecchioVideo, _Bottone

from PyQt6.QtGui import QGuiApplication
from Utility import Schermi

#: L'unica finestra dello schermo secondario, o None se non ce n'e' bisogno.
_istanza = None

#: Le finestre dei **duplicati**, per nome di schermo.
#:
#: E' un dizionario e non una lista perche' la chiave e' il nome dello
#: schermo: e' l'unica cosa che si sa prima di aprire la finestra, ed e' la
#: stessa cosa con cui si decide se la finestra c'e' gia'.  Con una lista
#: ogni controllo dovrebbe cercare il nome dentro, e una ricerca fatta a
#: mano sbaglia prima o poi.
_duplicati: dict = {}


def finestre(finestra_app=None) -> list:
    """Tutte le finestre che devono mostrare il video: la secondaria e i duplicati.

    L'ORDINE E' QUELLO DEL SISTEMA
    -----------------------------
    Prima la secondaria, poi i duplicati nell'ordine in cui il sistema li
    elenca.  Non e' una questione di cameindietro: e' l'ordine in cui
    l'utente li ha scelti, e metterli in un ordine diverso farebbe apparire
    una finestra nell'ordine sbagliato.

    PERCHE' UNA LISTA E NON UN PEZZO SINGOLO
    ---------------------------------------
    Prima questo posto restituiva una finestra sola e ogni chiamante decideva
    «c'e' o non c'e'».  Con la duplicazione la domanda non e' piu' quella: e'
    «**quante** ce ne sono», e puo' essere nessuna, una, cinque.  Un posto
    che restituisce sempre la lista e lascia che siano i chiamanti a chiederne
    la lunghezza non ha piu' il caso speciale da ricordare.

    Crea i duplicati che mancano e butta via quelli che non servono piu'.
    E' il posto dove «l'utente ha spuntato tre caselle» diventa «ci sono tre
    finestre aperte», e non un'altra funzione a meta'.

    LE FINESTRE SONO N, MA IL PEZZO DI CODICE E' UNO
    ------------------------------------------------
    Il lettore chiama questa e collega i fotogrammi a tutto quello che
    esce.  Non deve sapere se sono una o cinque, e non deve chiedere il
    numero: prendere la lista e collegarla e' il lavoro di un solo pezzo di
    codice per qualunque numero di schermi, e se domani un domani gli altri
    perche' la lista non ha una forma particolare.
    """
    fuori = []
    if _istanza is not None:
        fuori.append(_istanza)
    # I duplicati si creano **qui** e non altrove: e' questa la funzione che
    # il lettore chiama quando parte un video.  Se le finestre le creasse
    # solo `duplicati_di_video` — che nessuno chiamerebbe — le caselle
    # spuntate sarebbero un'impostazione che non accade niente.
    try:
        fuori += duplicati_di_video(finestra_app)
    except Exception:  # noqa: BLE001 - un duplicato rotto non ferma gli altri
        pass
    return fuori


def duplicati_di_video(finestra_app=None) -> list:
    """Le finestre dei duplicati, aperte se servono.

    E' il posto che trasforma gli schermi spuntati in finestre vere.  Ogni
    schermo spuntato ha una finestra; uno schermo non piu' collegato non ha
    piu' niente e la sua finestra viene chiusa e dimenticata.

    LA FINESTRA NASCE SENZA IL VERSO
    --------------------------------
    Una finestra di duplicazione che nasce col verso del giorno e' una
    finestra che mostra una riga di testo su un monitor che l'utente ha scelto
    per il video.  Ma il verso del giorno sta gia' sullo schermo secondario,
    che e' il suo posto: metterlo anche sui duplicati vuol dire la stessa
    riga su tre monitor, e l'utente che ne ha uno davanti agli occhi pensa
    che sia un'altra cosa.

    Quindi un duplicato e' **solo video**: nasce vuoto e non ha niente da
    dire finche' non parte un video.  Quando parte, si riempie; quando il
    brano finisce, resta nero — che e' la verita' su uno schermo che non
    e' quello principale.

    PERCHE' UNA FINESTRA PER SCHERMO E NON UNA PER TUTTI
    ---------------------------------------------------
    Perche' una finestra sta su **uno** schermo.  Tre finestre a tutto
    schermo su tre schermi diversi si vedono tutte; una sola finestra si
    mette su uno schermo solo, e gli altri due resterebbero neri — che
    sembrerebbe un video che non arriva, ed e' proprio la cosa che l'utente
    sta segnalando.
    """
    global _duplicati
    scelti = Schermi.tema_duplicati()
    secondario = Schermi.secondario_per_video(finestra_app)
    dove_sta = Schermi.schermo_dove_sta(finestra_app)

    # Gli schermi che ci devono essere: quelli spuntati, ancora collegati,
    # diversi dal secondario e da quello dove sta la finestra.
    voluti = []
    for schermo in QGuiApplication.screens():
        nome = schermo.name()
        if nome not in scelti:
            continue
        if secondario is not None and nome == secondario.name():
            continue
        if dove_sta is not None and nome == dove_sta.name():
            continue
        voluti.append(schermo)

    # Le finestre che non servono piu' chiudono: uno schermo staccato non
    # deve lasciare una finestra a tutto schermo accesa su niente.
    for nome in list(_duplicati):
        if nome not in [s.name() for s in voluti]:
            finestra = _duplicati.pop(nome)
            try:
                finestra.close()
            except RuntimeError:
                pass

    fuori = []
    for schermo in voluti:
        finestra = _duplicati.get(schermo.name())
        nuova = finestra is None
        if nuova:
            finestra = SchermoEsterno(schermo=schermo)
            finestra.setObjectName("schermo")
            # Un duplicato non ha un'uscita video propria: un programma ne ha
            # una sola, e quella e' gia' del secondo schermo.  Quindi riceve i
            # fotogrammi in copia.  Vedi `accendi_video`.
            finestra.riceve_copia = True
            _duplicati[schermo.name()] = finestra
            finestra.rimetti_a_schermo_intero()
            finestra.mostra_verso()
        # IL DUPLICATO SI TOCCA SOLO SE E' NUOVO
        # --------------------------------------
        # Una finestra gia' esistente non viene rimessa a schermo intero ne'
        # ricacciata al verso.  Il perche' e' il difetto che e' stato
        # segnalato, e vale la pena scriverlo per intero perche' e' sottile:
        #
        # `finestre()` viene chiamata a **ogni** video — dal lettore, per
        # collegare la copia dei fotogrammi.  Se qui il verso venisse rimesso
        # a ogni chiamata, la sequenza sarebbe questa: il lettore mette tutte
        # le finestre a video, poi chiama `finestre()` per i fotogrammi, e
        # quella rimetterebbe il verso ai duplicati.  Il terzo schermo
        # mostrerebbe la Scrittura dell'anno mentre il secondo mostra il
        # video, e la copia non si vedrebbe piu'.
        #
        # In parole povere: **`finestre()` crea, non decide**.  Se decidesse
        # anche che cosa si vede, ogni chiamata dimenticherebbe il video.
        #
        # Qui dentro si vede il verso del giorno, come nel secondo schermo:
        # un duplicato che partisse «sul video» avrebbe un riquadro video
        # senza fotogrammi — cioe' **nero** — ed e' cosi' che il terzo
        # schermo e' stato nero.

        fuori.append(finestra)
    return fuori


def ascolta(chiamata):
    """Fai venire la finestra secondaria a `chiamata` quando si chiude.

    Serve al lettore dentro l'app, che e' l'unico che sa rimettere il video a
    posto: la finestra dice «e' finita» e non fa nient'altro.  Vedi
    `SchermoEsterno.riporta_nell_app`.
    """
    istanza()
    if _istanza is not None:
        _istanza.annullata.connect(chiamata)
        return True
    return False


def istanza(finestra_app=None):
    """La finestra dello schermo secondario, o None.

    None solo se c'e' un **solo** schermo: in quel caso non deve esistere,
    perche' una finestra a tutto schermo sopra l'unica cosa che l'utente sta
    guardando non e' una finestra, e' un intralcio.

    CON DUE SCHERMI ESISTE SEMPRE
    ----------------------------
    Prima esisteva solo se nelle impostazioni era stato scelto uno schermo
    con il suo nome.  Con «Segui la finestra» — che e' quella di partenza —
    non esisteva, il video usciva solo dentro l'app e il secondo schermo
    restava li' a far niente.  Non per un guasto: semplicemente la finestra
    non era mai stata creata, e tutto il resto lavorava con quel `None`.

    `finestra_app` serve a capire quale dei due schermi **non** e' quello
    dove l'utente sta guardando: e' quello li' che il video va in piu'.  Chi
    chiama ce l'ha sempre (`self.window()`).

    Il motivo per cui e' una sola e non una per schermo e' semplice: il
    programma sceglie **uno** schermo, e due finestre a tutto schermo sulla
    stessa figura o sullo stesso video non hanno senso.
    """
    global _istanza
    if _istanza is not None:
        return _istanza
    if Schermi.schermo_che_serve(finestra_app) is None:
        return None
    _istanza = SchermoEsterno()
    # PRIMA la finestra sullo schermo, POI il verso.  In questo ordine la
    # pagina della Scrittura dell'anno viene davvero messa in primo piano:
    # prima era il contrario, e la finestra si apriva con il riquadro del video
    # vuoto invece che con la pagina.  Vedi la nota di `__init__`.
    _istanza.rimetti_a_schermo_intero()
    _istanza.mostra_verso()
    return _istanza


def chiudi_se_ce_n_e(permanente: bool = False) -> None:
    """Butta via la finestra, se c'era.

    `permanente` vuol dire «il programma sta chiudendo» e cambia due cose.

    Serve quando l'impostazione cambia: se l'utente sceglie un altro schermo
    o torna a «dove sta la finestra», la finestra di prima non deve restare
    accesa su uno schermo che non e' piu' quello scelto.

    IL VIDEO SI STACCA PRIMA, E QUESTO E' IL DIFETTO CHE C'ERA
    -----------------------------------------------------------
    Qui si chiamava `close()` e basta.  Il video, pero', in quel momento
    era **attaccato al riquadro di questa finestra**: la chiama che lo attacca
    e' `Lettore.al_video`, e non c'era nessuno che lo staccasse.

    Chiudendo, la finestra distruggeva il suo `QVideoWidget` con il lettore
    ancora puntato dentro.  Il programma moriva: non rispondeva e KDE offriva
    di terminarlo.  Misurato tre volte su tre con un video che girava
    sull'altro schermo; con il video dentro l'app la chiusura passava in 0,02
    secondi.

    E il rimedio non e' una regola nuova: e' **la stessa che usa gia' la X** di
    questa finestra, che chiama `riporta_nell_app`, e che emette `annullata`
    **prima** di chiudere.  Il segnale lo ascolta il lettore, che riporta il
    video qui nell'app.  Quindi qui si fa esattamente lo stesso, e si riusa
    l'unica strada che rimette il video a posto — come dice la nota della X:
    due strade per rimetterlo sarebbero due regole che un giorno divergono.
    """
    global _istanza
    # I DUPLICATI VANO CHIUSI PRIMA
    # -------------------------------
    # Chiudere solo la secondaria lascerebbe N finestre a tutto schermo
    # accese su schermi che l'utente ha appena tolto dalla lista: schermi
    # neri, senza bordi, e niente che li governi — cioe' esattamente il caso
    # da cui siamo partiti.
    _chiudi_i_duplicati()

    if _istanza is None:
        return

    if permanente:
        # IL PROGRAMMA STA CHIUDENDO: NESSUN RIMETTIMENTO
        # -------------------------------------------------
        # Qui non si emette `annullata`, e la differenza non e' una questione
        # di ordine: e' la causa del blocco segnalato.
        #
        # `annullata` dice al lettore «rimetti il video nell'app», e il
        # lettore lo fa sul serio: ricollega il video al suo riquadro e
        # **riaccende lo specchio** — cioe' crea un widget video nuovo dentro
        # la finestra che si sta chiudendo, e gli riapre il riquadro.  Tutto
        # questo dentro una `closeEvent`, mentre Qt sta smontando le finestre:
        # il programma non risponde piu', il video resta fermo e la finestra
        # del secondo schermo resta accesa con dentro la Scrittura dell'anno,
        # senza piu' niente che la governi.  L'unica uscita era Alt+F4 con il
        # mouse sul monitor.
        #
        # Quando il programma chiude non c'e' niente da rimettere: si stacca
        # il video e basta, senza nessuno che lo voglia vedere.
        try:
            from Utility import Lettore
            Lettore.motore().al_video(None)
        except Exception:  # noqa: BLE001 - la chiusura non deve fallire qui
            pass
    else:
        try:
            # Prima di chiudere: il lettore riporta il video nell'app, e il
            # riquadro di questa finestra non viene piu' usato da nessuno.
            _istanza.annullata.emit()
        except RuntimeError:
            pass
    try:
        _istanza.close()
    except RuntimeError:
        pass
    _istanza = None


def _chiudi_i_duplicati() -> None:
    """Butta via tutte le finestre dei duplicati.

    Non riceve un flag «permanente» perche' qui la differenza non c'e': un
    duplicato non riceve il video, non ascolta nessun rimettimento e non ha
    niente da rimettere al suo posto.  Chiuderlo e' chiuderlo e basta, sia
    che stia chiudendo il programma sia che l'utente abbia tolto una spunta.
    """
    global _duplicati
    for nome in list(_duplicati):
        finestra = _duplicati.pop(nome)
        try:
            finestra.close()
        except RuntimeError:
            # La finestra e' gia' stata distrutta: non c'e' piu' niente da
            # chiudere, e questo non e' un errore da fermarsi.
            pass


class SchermoEsterno(QWidget):
    """Il monitor secondario: nero, e con dentro il contenuto da guardare."""

    #: La finestra e' stata chiusa dalla X: il video va rimesso nell'app.
    #:
    #: E' un segnale e non una chiamata diretta al lettore perche' la finestra
    #: non sa nulla del lettore, e cosi' puo' stare in un file senza dipendere
    #: da lui.  Chi ascolta e' il lettore, in `LettoreView`.
    annullata = Signal()

    def __init__(self, parent=None, schermo=None) -> None:
        """`schermo` su cui mettere questa finestra, o None per decidere da solo.

        Il parametro serve alla **duplicazione**: con piu' di due monitor non
        basta una finestra, ne serve una per ogni schermo in cui il video deve
        comparire, e ognuna sa **su quale** schermo sta.  Senza il parametro
        ogni finestra andrebbe a chiedere qual e' «il suo» schermo alle
        impostazioni, e tutte avrebbero la stessa risposta.

        Con `None` — cioe' quando non si e' ancora deciso niente — si usa la
        regola di sempre, che e' quella giusta per la finestra unica.
        """
        super().__init__(parent, Qt.WindowType.Window
                         # SEMPRE SOPRA, E NON SOLO SUL SUO SCHERMO
                         # -----------------------------------------
                         # Il commento di prima diceva che questa finestra
                         # non aveva bisogno di «resta sempre sopra» perche'
                         # stava su un monitor diverso da quello del programma
                         # e non si sovrapponeva.  Il ragionamento era giusto
                         # sulla sovrapposizione, ma sbagliato sulla conclusione:
                         #
                         #   1. quando la finestra principale prende il fuoco,
                         #      il gestore di finestre mette **tutte** le
                         #      finestre non attive in secondo piano, anche su
                         #      un altro monitor — e la finestra secondaria
                         #      finiva sotto altre applicazioni aperte per caso
                         #      su quel monitor;
                         #   2. l'utente ha scelto quel monitor **per il video**,
                         #      e il video deve restare visibile sempre, anche
                         #      se l'utente sta lavorando sulla finestra
                         #      principale su un altro schermo.
                         #
                         # Quindi «resta sempre sopra» torna, e va su **tutte**
                         # le finestre di questo tipo — la secondaria e i
                         # duplicati — perche' tutte hanno lo stesso problema.
                         #
                         # `WindowDoesNotAcceptFocus` resta: questa finestra non
                         # prende la tastiera, cosi' passando sopra la finestra
                         # principale non le ruba i tasti.
                         #
                         # `ShowWithoutActivating`: aprire questa finestra non
                         # porta il focus a lei, e cosi' il video che parte non
                         # fa perdere la tastiera alla finestra principale.
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setObjectName("schermo")
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # MAI DIMENTICATA DAL COMPOSITORE
        # -------------------------------
        # Su alcuni gestori di finestre, una finestra che non prende il
        # fuoco viene trattata come «non in uso» quando il fuoco va altrove:
        # il compositore smette di ridisegnarla e lo sfondo (qui nero) sparisce.
        # `WA_OpaquePaintEvent` dice al compositore che questa finestra e'
        # opaca: deve ridisegnarla sempre, e non puo' mostrarci niente dietro.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        # macOS: una finestra di questo tipo non si nasconde quando l'app
        # perde il fuoco.  Su Linux la stessa cosa la fa `WindowStaysOnTopHint`.
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        # Un clic non porta il fuoco qui dentro.  Non ci sono comandi da
        # usare, quindi il clic non ha niente su cui agire, e qui dentro il
        # posto del fuoco deve restare la finestra principale.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # LA FINESTRA HA TITOLO E BORDI, E LI PERDE DA SOLA A TUTTO SCHERMO
        # ------------------------------------------------------------------
        # Prima la finestra nascondeva i bordi con `FramelessWindowHint`, e per
        # passare alla piccola toglieva il segno.  Due problemi, entrambi
        # misurati:
        #
        # 1.  Cambiare quel segno a runtime **ricrea la finestra**, e il
        #     gestore di finestre ne approfittava per rimetterla quasi a tutto
        #     schermo: misurata a 1920x1018 su uno schermo di 1920x1080, cioe'
        #     non si era rimpicciolita affatto.
        # 2.  Una finestra senza bordo non si afferra, e l'utente non sapeva
        #     se si potesse spostare.
        #
        # Quindi i bordi **non si toccano piu'**: la finestra e' sempre una
        # finestra normale del desktop, con titolo e barra, e a tutto schermo e'
        # il gestore di finestre a nasconderli da solo — che e' il comportamento
        # normale di qualunque finestra che va a schermo intero, e quindi
        # uguale su qualunque desktop.
        #
        # Il nome della finestra non si scrive qui e non si cambia quando si
        # riduce: quello lo scrive `JWLibraryApp`, in un posto solo, e ridurre
        # la finestra non e' un programma diverso.
        # Il nero e' lo stesso di `LettoreSchermo`: il fondo di un video o di
        # una figura guardati da soli e' nero.  Con un fondo grigio si vede
        # la finestra invece del contenuto, che e' l'unica cosa da guardare.
        paletta = self.palette()
        paletta.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(paletta)

        self.pila = QStackedWidget(self)
        # IL VIDEO E' UN FIGLIO DIRETTO, NON UNA PAGINA DELLA PILA
        # --------------------------------------------------------
        # Prima il video era dentro la pila, insieme al verso e alla figura.
        # Non funziona: con il video in primo piano e poi la figura al suo
        # posto, Qt si aborta.  Quindi il video sta **fuori** dalla pila e si
        # mostra e si nasconde, come gia' fa `LettoreSchermo`.
        #
        # E' un `QVideoWidget` suo, non quello del lettore dentro l'app: il
        # player ha una sola uscita video, e due uscite significherebbe che una
        # delle due e' sempre nera.  Vedi `LettoreView.mostra`.
        #
        # E NON ESISTE FINCHE' NON C'E' UN VIDEO DA MOSTRARE
        # --------------------------------------------------
        # Qui non viene creato subito.  Un `QVideoWidget` vuoto — cioe' senza
        # nessun filmato collegato — e' una cosa che non ha senso: non mostra
        # niente e non serve a niente.  Peggio, su una macchina dove Qt non
        # trova una scheda video (misurato qui: `MESA-EGL: failed to create
        # dri2 screen`) mostrarlo fa **abortire** Qt.
        #
        # Quindi si crea quando arriva il primo video, e da li' in poi si
        # riusa.  Non e' una differenza da poco: e' la differenza fra una
        # finestra che al massimo puo' stare male e una che si chiude.
        self._video = None

        self.figura = QLabel(self.pila)
        self.figura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # La figura va messa nella pila **qui**: senza questa riga non e' di
        # nessuna pagina e `setCurrentWidget` avvisa «not contained in stack»
        # e non cambia niente — misurato.
        self.pila.addWidget(self.figura)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(self.pila)

        # I DUE TASTI, IN ALTO A DESTRA, SOLO COL MOUSE SOPRA
        # --------------------------------------------------
        # Compaiono quando il mouse passa sopra la finestra e spariscono quando
        # esce, con una dissolvenza.  Sono due e fanno due cose:
        #
        #   - la X chiude **questa** finestra e riporta il video nell'app
        #     principale; il programma resta aperto e si continua a lavorare;
        #   - l'altro riduce la finestra a una piccola, che si puo' afferrare e
        #     spostare col mouse, e che ripresa diventa di nuovo a tutto
        #     schermo sullo schermo scelto.
        #
        # Il secondo e' nato da un problema vero: se la finestra del programma
        # resta sotto quella a tutto schermo, non si vede piu' come si esce.  A
        #vere una finestra piccola che si sposta, l'utente la prende e la
        # toglie di mezzo, e vede di nuovo sotto.
        #
        # I due tasti compaiono **sopra** il video, non al suo posto: il video
        # resta a tutto schermo e non si sposta di un pixel quando compaiono.
        # Percio' stanno in un riquadro sovrapposto, in alto a destra, e non
        # nella colonna: se fossero nella colonna, comparendo allargherebbero
        # tutto e il video si muoverebbe sotto gli occhi di chi sta guardando.
        self._comandi = QWidget(self)
        self._comandi.setObjectName("comandiSchermoEsterno")
        # Nascosti fin da qui: `rimetti_a_schermo_intero` li nasconde di nuovo
        # quando la finestra si rimette, e non si deve dipendere dall'ordine in
        # cui le cose vengono costruite.
        self._comandi.setVisible(False)
        riga_comandi = QHBoxLayout(self._comandi)
        riga_comandi.setContentsMargins(0, 0, 0, 0)
        riga_comandi.setSpacing(6)
        riga_comandi.addStretch(1)

        # L'ORDINE DEI DUE: RIDUCI, POI LA X
        # -------------------------------------
        # Prima era il contrario: la X a sinistra e «riduci» a destra.  L'ordine
        # con cui si mettono e' quello con cui si leggono: il comando che
        # cambia la misura e' un'azione sul video, e sta prima; la X chiude e
        # sta per ultima, in fondo a destra, dove va la fine.
        #
        # Il riduci / ingrandisci usa lo stesso simbolo del tasto di tutto schermo
        # del lettore (`fullscreen.svg`, mappato sotto
        # `arrow.up.left.and.arrow.down.right`), e cambia solo la scritta: un
        # simbolo nuovo sarebbe un'icona diversa dal resto del programma, e in
        # questo progetto le icone non si inventano.
        self.pulsante_misura = _Bottone("arrow.up.left.and.arrow.down.right",
                                        "Riduci la finestra",
                                        self._comandi, lato=34, luce=True)
        self.pulsante_misura.premuto.connect(self._cambia_misura)
        riga_comandi.addWidget(self.pulsante_misura, 0)

        # La X: chiude questa finestra e basta.  Il simbolo e' `xmark`,
        # mappato su `close.svg` nella tabella dei simboli del progetto: non se
        # ne inventa uno nuovo.
        self.pulsante_chiudi = _Bottone("xmark", "Torna nell'app",
                                       self._comandi, lato=34, luce=True)
        self.pulsante_chiudi.premuto.connect(self.riporta_nell_app)
        riga_comandi.addWidget(self.pulsante_chiudi, 0)

        # La finestra piccola: 480x270 e' un sesto dello schermo, e ci sta un
        # video 16:9 intero.  Piu' piccola di cosi' il video si vede a pezzi, e
        # il punto e' poterla afferrare e spostare, non guardarla.
        self._misura_piccola = None
        self._piccola = False
        self._trascina = None
        # LA DISSOLVENZA E' SUL RIQUADRO DEI TASTI, NON SULLA FINESTRA
        # --------------------------------------------------------
        # Prima la finestra intera veniva resa trasparente con
        # `setWindowOpacity`, e **non funzionava**: il plugin della piattaforma
        # non lo supporta e lo diceva, una riga per frame:
        #
        #     [Qt AVVISO] This plugin does not support setting window opacity
        #
        # Sono state uscite duecento righe cosi'.  E il difetto vero era che
        # la dissolvenza non c'era: i tasti comparivano col mouse e non
        # sparivano piu', perche' l'unica cosa che doveva farli sparire non
        # arrivava a schermo.
        #
        # L'opacita' di un **widget** invece funziona, perche' e' Qt a
        # disegnarlo e non il gestore di finestre.  Quindi la dissolvenza e'
        # sul riquadro dei tasti, e la finestra resta piena: cioe' non si
        # sbiadisce mai il video, che e' quello che si vuole guardare.
        self._effetto = QGraphicsOpacityEffect(self._comandi)
        self._comandi.setGraphicsEffect(self._effetto)
        self._animazione = QPropertyAnimation(self._effetto, b"opacity", self)
        self._animazione.setDuration(180)
        self._animazione.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._effetto.setOpacity(0.0)

        # La colonna del layout mette i tasti in alto, e il riquadro e' senza
        # margini perche' la posizione la decide il rettangolo qui sotto, che
        # viene mosso a ogni cambio di misura della finestra.
        self._comandi.setFixedHeight(34)
        self.pila.setContentsMargins(0, 0, 0, 0)
        self._comandi.raise_()
        # LA FINESTRA PUO' DIVENTARE PICCOLA
        # ------------------------------
        # Il layout impose una misura minima, e senza questo la finestra
        # ridotta non scende sotto quella: misurata a 772 pixel invece dei 480
        # richiesti, e il motivo e' che la pila e i tasti hanno una minima
        # propria.  La finestra che si deve poter afferrare col mouse non puo'
        # avere una minima che glielo impedisce.
        self.pila.setMinimumSize(1, 1)
        self.setMinimumSize(1, 1)

        self._pagina_verso = None
        #
        # Prima si metteva in `rimetti_a_schermo_intero`, e cioe' **dopo**.
        # Il risultato era che `mostra_verso()`, chiamata prima, trovava
        # `_schermo` ancora vuoto e usciva subito: la finestra si apriva con
        # il riquadro del video vuoto invece che con la pagina.
        # Misurato: la pagina in primo piano era `QVideoWidget` e il verso non
        # era visibile.
        #
        # Ora e' noto dal momento in cui la finestra esiste, quindi la guardia
        # `schermo` ha la precedenza, ed e' quello che serve alla duplicazione:
        # con piu' di due monitor c'e' una finestra per ogni schermo duplicato
        # e ognuna deve sapere **su quale** sta.  Senza il parametro ognuna
        # chiederebbe alle impostazioni e tutte riceverebbero la stessa
        # risposta — cioe' tutte sulla stessa tastiera.
        self._schermo = (schermo if schermo is not None
                         else Schermi.secondario_per_video())

        #: Questa finestra e' un **duplicato** e non il secondo schermo?
        #:
        #: La differenza e' che sul secondo schermo c'e' la Scrittura
        #: dell'anno quando non c'e' niente da guardare, e cosi' va bene:
        #: e' il suo posto.  Su un duplicato invece quella riga metterebbe
        #: la stessa identica scritta su tre monitor, e chi ne ha uno davanti
        #: agli occhi penserebbe che sia un'altra cosa.  Quindi un
        #: duplicato e' solo video: nero quando non c'e' niente.
        #: Questa finestra riceve il video **in copia** invece che dal motore?
        #:
        #: `False` per la finestra del secondo schermo: il motore scarica il
        #: video nel suo riquadro di uscita.
        #:
        #: `True` per un duplicato: un programma ha una sola uscita video, e
        #: quella e' gia' del secondo schermo.  Quindi l'unico modo che ha un
        #: duplicato e' ricevere i **fotogrammi** in copia.  Vedi
        #: `accendi_video` e `uscita_video`.
        #:
        #: IL NOME NON E' «SOLO VIDEO» PERCHE' IL DUPLICATO NON E' «SOLO VIDEO»
        #: ------------------------------------------------------------------
        #: Prima questa finestra si chiamava `solo_video`, e i duplicati
        #: partivano con quel flag acceso: spegnevano la pila del verso e
        #: restavano **neri** quando non c'era un video da mostrare.
        #:
        #: E' la cosa sbagliata, perche' il duplicato deve mostrare **tutto**
        #: quello che mostra il secondo schermo: il video quando c'e' un video,
        #: e la Scrittura dell'anno quando non c'e'.  Un terzo monitor scuro
        #: mentre il secondo mostra la Scrittura non e' una copia, e sembra
        #: un monitor spento.
        self.riceve_copia = False

        #: Il `QVideoWidget` che riceve il video dal motore.  Solo nella
        #: finestra del secondo schermo: un duplicato riceve i fotogrammi
        #: in copia e non ha un'uscita propria.  Vedi `uscita_video`.
        self._uscita = None

    # ------------------------------------------------------------------
    # I DUE TASTI
    # ------------------------------------------------------------------

    def paintEvent(self, evento) -> None:
        """Il fondo e' **sempre** nero, anche quando la finestra perde il fuoco.

        `paintEvent` viene chiamato **sempre**, anche per una finestra non
        attiva, e qui si riempie tutto di nero a mano: il compositore non ha
        piu' niente da indovinare, e il nero resta li' finche' la finestra
        c'e'.  Vedi il commento in `__init__` per il bug che risolve.
        """
        from PyQt6.QtGui import QPainter
        from PyQt6.QtCore import Qt

        pittore = QPainter(self)
        pittore.fillRect(self.rect(), Qt.GlobalColor.black)
        pittore.end()
        super().paintEvent(evento)

    def enterEvent(self, evento) -> None:
        """Il mouse e' entrato nella finestra: i tasti compaiono."""
        self._comandi.setVisible(True)
        self._comandi_in_fronte()
        self._dissolvenza(1.0)
        super().enterEvent(evento)

    def _comandi_in_fronte(self) -> None:
        """I tasti sopra tutto, **anche sopra il video**.

        IL DIFETTO CHE C'ERA
        -------------------
        I tasti venivano alzati solo quando il mouse entrava nella finestra.
        Ma il video e la figura salgono **dopo**: il video parte, il suo
        riquadro si mette davanti a tutto, e i tasti gli finiscono sotto.

        Il sintomo era che con la pagina i tasti si vedevano, e con
        un video o una figura **non si vedevano piu'**: e' il difetto segnalato.
        Non era un problema di opacita' ne' di posizione — erano coperti.

        Per questo l'alzamento si fa qui, e si richiama da ogni posto che
        cambia quello che si vede: il video, la figura, il verso, e la finestra
        piccola.  Ogni volta che si mette qualcosa davanti, i tasti tornano
        davanti.
        """
        try:
            self._comandi.raise_()
        except RuntimeError:
            return

    def leaveEvent(self, evento) -> None:
        """Il mouse e' uscito dalla finestra: i tasti spariscono.

        Dopo la dissolvenza vengono **nascosti**, e non solo resi
        trasparenti.  Lasciarli visibili con l'opacita' a zero non costa niente
        in immagini, ma lascia un riquadro che intercetta il mouse sopra
        un'area vuota: se l'utente ci passa sopra non succede niente e sembra
        un pulsante morto.

        Si nascondono anche quando la finestra e' piccola: per premere un tasto
        il mouse deve essere li', quindi quando non c'e' non servono.
        """
        self._dissolvenza(0.0)
        QTimer.singleShot(220, self._nascondi_i_tasti)
        super().leaveEvent(evento)

    def _nascondi_i_tasti(self) -> None:
        """I tasti sono spariti: non intercettano piu' il mouse."""
        try:
            if self._effetto.opacity() <= 0.01:
                self._comandi.setVisible(False)
        except RuntimeError:
            return

    def _dissolvenza(self, valore: float) -> None:
        """Porta i tasti a quell'opacita', in dissolvenza."""
        try:
            self._animazione.stop()
            if abs(self._effetto.opacity() - valore) < 0.01:
                self._animazione.setEndValue(valore)
                self._effetto.setOpacity(valore)
                if valore <= 0.0:
                    self._comandi.setVisible(False)
                return
            self._animazione.setStartValue(self._effetto.opacity())
            self._animazione.setEndValue(valore)
            self._animazione.start()
            if valore > 0.0:
                self._comandi.setVisible(True)
        except RuntimeError:
            # La finestra e' stata distrutta nel frattempo: non c'e' piu' niente
            # di cui animare l'opacita'.
            return

    def _cambia_misura(self) -> None:
        """A tutto schermo <-> finestra piccola.

        La piccola si mette **al centro dello schermo scelto**, e non dove
        capita: una finestra piccola in un angolo si nasconde dietro il
        pannello o dietro un'altra finestra, e il suo compito e' proprio
        farsi trovare.
        """
        try:
            if self._piccola:
                self._diventa_grande()
            else:
                self._diventa_piccola()
        except RuntimeError:
            return

    def _diventa_piccola(self) -> None:
        """La finestra diventa una finestra NORMALE del desktop, piccola.

        UNA FINESTRA NORMALE, NON UN RIQUADRO
        ------------------------------------
        Prima era una finestra senza bordo con dentro il video: si riduceva, ma
        restava un rettangolo che galleggiava e sembrava un errore, e non si
        sapeva se si potesse spostare.  Perche' sembrava un errore: una
        finestra senza bordo non si afferra, e il desktop la fa sembrare parte
        dello sfondo.

        Qui si toglie il «senza bordo» e si restituisce la finestra al
        gestore di finestre: tornano il titolo e i bordi, e con loro la barra
        del titolo — che e' quello che si afferra per spostare, come in
        qualsiasi finestra di qualsiasi desktop.

        IL NOME DELLA FINESTRA NON SI TOCCA
        ------------------------------------
        Il testo del titolo non si scrive qui: quello che scrive la finestra
        e' gia' pronto in un posto solo, in `JWLibraryApp`, e rifarlo qui
        sarebbe una seconda copia che un giorno dice una cosa diversa.

        E non si cambia quando la finestra si rimpicciolisce: su un'altra
        macchina cambierebbe quello che c'e' scritto in alto a sinistra, e chi
        lo cerca non lo troverebbe piu'.  Ridurre la finestra non e' un
        programma diverso: e' lo stesso programma, piu' piccolo.

        IL BORDO E I TASTI DEL DESKTOP
        -------------------------------
        Riappare anche il bottone di chiusura del gestore di finestre.  Non e'
        un problema perche' fa la stessa cosa del nostro: chiude questa
        finestra e basta, e il lettore dentro l'app rimette il video a posto
        perche' `closeEvent` dice «annullata» anche quando a chiudere e' il
        desktop e non la nostra X.

        LA MISURA, IN PEZZI DI SCHERMO E NON IN CENTIMETRI
        --------------------------------------------------
        Un terzo della larghezza e un terzo dell'altezza dello schermo scelto.

        Non in centimetri, perche' i centimetri non esistono per uno schermo:
        dipendono dalla densita' dei pixel, che e' diversa su un portatile e
        su un monitor, e un valore in centimetri su una macchina e' piccolo e
        sull'altra enorme.  Su questa macchina (1920x1080) viene 640x360:
        poco piu' di un terzo della larghezza, quindi intorno restano circa
        640 pixel per lato, e la finestra si vede nettamente al centro invece
        che a tutto schermo.

        C'e' un minimo (240x135) perche' con uno schermo minuscolo la
        finestra non diventi piu' piccola di quanto si possa afferrare col
        mouse.
        """
        if self._schermo is None:
            return
        geometria = self._schermo.geometry()
        larghezza = max(240, geometria.width() // 3)
        altezza = max(135, geometria.height() // 3)
        x = geometria.x() + (geometria.width() - larghezza) // 2
        y = geometria.y() + (geometria.height() - altezza) // 2
        self._piccola = True
        self._misura_piccola = (x, y, larghezza, altezza)

        # Qui non si tocca nessun segno della finestra: e' gia' una finestra
        # normale del desktop, e «tornarle» non cambierebbe niente.
        # «Sta sopra» resta, altrimenti la finestra piccola andrebbe sotto
        # le altre applicazioni e non si troverebbe piu'.
        self.showNormal()
        self.winId()
        maniglia = self.windowHandle()
        if maniglia is not None:
            maniglia.setScreen(self._schermo)
        self.setGeometry(x, y, larghezza, altezza)
        # La misura si rimette **due** volte: una adesso e una dopo un giro di
        # eventi, perche' quando si esce da schermo intero il gestore di
        # finestre rimette la finestra a quasi tutto schermo e va rimessa la
        # misura piccola per ultima.  Senza il secondo passaggio la finestra non
        # scende — misurato: restava a 1920x1018 su uno schermo di 1920x1080.
        QTimer.singleShot(0, self._rimetti_la_misura_piccola)
        self.pulsante_misura.setToolTip("Ingrandisci a tutto schermo")

    def _rimetti_la_misura_piccola(self) -> None:
        """Dopo che il layout e il desktop hanno finito: ora si' piccola davvero."""
        if not self._piccola or self._misura_piccola is None:
            return
        x, y, larghezza, altezza = self._misura_piccola
        if self.geometry() != (x, y, larghezza, altezza):
            self.setGeometry(x, y, larghezza, altezza)
        # E i tasti vanno rimessi a destra: la posizione dipende dalla
        # larghezza della finestra, che adesso e' un'altra.
        self._metti_i_comandi_in_angolo()

    def _diventa_grande(self) -> None:
        """Tornata a tutto schermo sullo schermo scelto.

        Nessun segno da cambiare: la finestra e' sempre quella normale del
        desktop, e a tutto schermo e' il desktop a nascondere titolo e bordi.
        """
        self._piccola = False
        self._misura_piccola = None
        # Si rilavora da capo la messa a schermo intero: la finestra era una
        # finestra normale e aveva perso il suo schermo, quindi va rimessa.
        self.rimetti_a_schermo_intero()
        self.pulsante_misura.setToolTip("Riduci la finestra")

    def mousePressEvent(self, evento) -> None:
        """Il clic sul video non fa niente; quello sulla piccola la trascina.

        IL CLIC NON CHIUDE NULLA
        ----------------------
        Qui sotto c'era un secondo `mousePressEvent` — scritto quando la
        finestra non aveva tasti ne' trascinamento — che diceva solo «il clic
        non chiude niente».  Due metodi con lo stesso nome: vinceva il secondo
        e **il primo non veniva mai chiamato**, quindi la finestra piccola non
        si poteva spostare col mouse.  Misurato: la premuta non impiantava
        niente, con tutte le condizioni giuste.

        Non si lascia qui la riga finale «il clic non chiude niente» come
        sembrerebbe innocua: era appunto quella che cancellava il trascinamento.
        Il video, quando la finestra e' a tutto schermo, riceve il clic e non
        fa niente — ed e' il comportamento giusto, perche' chiudere la finestra
        col clic significherebbe che al video successivo lo schermo secondario
        resta spento e il video non si vede da nessuna parte.

        In finestra piccola la finestra non ha bordo, e senza bordo non c'e'
        niente da afferrare: si sposta col mouse **dentro** la finestra.  Il
        trucco e' banale e funziona: si ricorda dove si e' premuto rispetto al
        bordo, e a ogni movimento la finestra va di quella distanza.

        Sopra i due tasti non si trascina niente, perche' li' il clic e' un
        comando — e se trascinasse, premere la X sposterebbe la finestra invece
        di chiuderla.
        """
        if self._piccola and evento.button() == Qt.MouseButton.LeftButton:
            punto = evento.position().toPoint()
            if not self._comandi.geometry().contains(punto):
                self._trascina = (evento.globalPosition().toPoint()
                                  - self.frameGeometry().topLeft())
                return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:
        """Col trascinamento la finestra segue il mouse."""
        if self._piccola and getattr(self, "_trascina", None) is not None:
            self.move(evento.globalPosition().toPoint() - self._trascina)
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:
        """Finito il trascinamento."""
        self._trascina = None
        super().mouseReleaseEvent(evento)

    def _metti_i_comandi_in_angolo(self) -> None:
        """I tasti in alto a **destra**, con un piccolo distacco dal bordo.

        PERCHE' NON SI USA IL LAYOUT
        ---------------------------
        I tasti sono un riquadro sovrapposto e non una riga della colonna:
        devono stare sopra il video senza spostarlo, e una riga del layout
        allargherebbe la colonna quando compaiono — cioe' muoverebbe il video
        sotto gli occhi di chi sta guardando.

        Percio' la posizione la calcoliamo qui, e va ricalcolata **ogni volta
        che la finestra cambia misura**: nella larghezza c'e' dentro anche
        quella dei tasti, e se la finestra si stringe vanno tenuti dentro
        pure loro.

        IL PERCHE' DEL RITARDO
        -----------------------
        La prima volta che questa funzione e' stata chiamata la finestra
        aveva ancora larghezza zero — sta nascendo — e il calcolo dava
        `max(0, 0 - 100 - 16)` = `0`.  Risultato: i tasti in alto a
        **sinistra**, che e' esattamente il difetto segnalato.

        Quindi si rimanda di un giro di eventi, quando la finestra ha una
        misura vera, e si rimette ogni volta che la misura cambia.
        """
        larghezza = self._comandi.sizeHint().width()
        if larghezza <= 0:
            # Il layout non ha ancora misurato i tasti: si rimanda.
            QTimer.singleShot(0, self._metti_i_comandi_in_angolo)
            return
        larghezza = min(larghezza, max(1, self.width() - 32))
        self._comandi.setGeometry(
            max(0, self.width() - larghezza - 16), 16, larghezza, 34)

    def riporta_nell_app(self) -> None:
        """La X: chiude questa finestra e riporta il video nell'app principale.

        CHIUDE SOLO QUESTA FINESTRA
        --------------------------
        Il programma resta aperto e si continua a lavorare.  Non si chiude
        nient'altro, e soprattutto non si esce dal programma: la X di questa
        finestra e' «torna nell'app», non «esci».

        Il video torna nel riquadro del lettore dentro l'app, che e' l'unico
        posto dove si puo' tornare indietro: qui non ci sono comandi.

        E IL PROGRAMMA LO SA PERCHE' IL SEGNALE ESISTE
        ----------------------------------------------
        La finestra non chiama il lettore da se': dice «e' finita» e lascia
        che chi ascolta riporti il video.  Il motivo e' che la stessa richiesta
        arriva anche dal tasto di tutto schermo dentro l'app, e due strade per
        rimettere il video a posto sarebbero due regole che un giorno
        divergono.
        """
        self.annullata.emit()
        self.close()

    def closeEvent(self, evento) -> None:
        """Chiusa: il registro delle finestre deve restare vuoto.

        IL BUCO CHE QUA CHIUDE
        ---------------------
        La finestra chiusa **non** si cancella da sola.  `istanza()` continua a
        restituirla, e chi la usa — il lettore, per metterci dentro il video —
        scrive in una finestra che non si vede piu'.  Il video partirebbe e non
        si vedrebbe da nessuna parte, senza un messaggio: e' il difetto peggiore
        che ci sia, perche' sembra tutto funzionare.

        Prima di pensare a questo si poteva anche non accorgersene, perche'
        non c'era un modo di chiudere la finestra.  Ora c'e' la X, quindi il
        caso e' reale ed e' stato misurato.

        Qui si dice al registro che la finestra non c'e' piu'.  La prossima
        volta che serve, `istanza()` ne costruisce una nuova — ed e' quello che
        rende il tasto di tutto schermo dentro l'app il modo per ripristinare
        lo schermo secondario senza chiudere il programma.
        """
        global _istanza
        if _istanza is self:
            _istanza = None
        super().closeEvent(evento)

    # ------------------------------------------------------------------
    # DOVE STA
    # ------------------------------------------------------------------

    def rimetti_a_schermo_intero(self) -> None:
        """Metti la finestra a vero schermo intero sullo schermo scelto.

        Le stesse tre cose di `LettoreSchermo`, e per gli stessi motivi:
        `windowHandle().setScreen()` per cambiare schermo, `geometry()` e non
        `availableGeometry()` per coprire tutto il monitor, e il tutto rimesso
        dopo `showFullScreen()` perche' quello rimette il proprio schermo.
        """
        schermo = self._schermo
        if schermo is None:
            schermo = Schermi.schermo_che_serve()
        if schermo is None:
            return
        self._schermo = schermo
        self.winId()
        maniglia = self.windowHandle()
        if maniglia is not None:
            maniglia.setScreen(schermo)
        self.setGeometry(schermo.geometry())
        self.showFullScreen()
        self._comandi_in_fronte()
        # I tasti in alto a destra: si rimettono **dopo** che la finestra e'
        # a schermo intero, perche' e' solo adesso che la finestra ha una
        # larghezza vera.  Prima, il calcolo della posizione dava zero e i
        # tasti finivano a sinistra.
        self._metti_i_comandi_in_angolo()
        # E **nascosti**, che e' il loro stato di riposo.
        #
        # Non si nascondono da soli: `enterEvent` li fa comparire quando il
        # mouse passa sopra.  Ma all'avvio il mouse e' gia' dentro la finestra —
        # la finestra e' a tutto schermo, quindi il mouse e' per forza dentro —
        # e `enterEvent` su una finestra che compare sotto il mouse **non
        # parte**: aspetta che il mouse si muova.  Senza questa riga i tasti
        # restavano visibili per sempre, che e' esattamente cio' che e' stato
        # segnalato.
        self._comandi.setVisible(False)
        # Niente `raise_()` ne' `activateWindow()`: questa finestra ha
        # `WindowDoesNotAcceptFocus`, e chiederle di prendere il focus fa
        # scrivere a Qt un avviso — misurato:
        #
        #     requestActivate() called for QWidgetWindow ... which has
        #     Qt::WindowDoesNotAcceptFocus set
        #
        # E l'avviso dice la verita': qui il focus non lo si vuole.  Resta
        # quello della finestra principale, cosi' i tasti di play e di Esc
        # vanno dove c'e' roba da comandare.
        # FIX: sincrono, usa visibilita' reale
        self._rimetti(schermo, self.isVisible())

    def _rimetti(self, schermo, era_visibile: bool = True) -> None:
        try:
            if not self.isVisible() and not era_visibile:
                return
            maniglia = self.windowHandle()
            if maniglia is not None:
                maniglia.setScreen(schermo)
            if self.geometry() != schermo.geometry():
                self.setGeometry(schermo.geometry())
            if era_visibile:
                self.show()
        except RuntimeError:
            return

    # ------------------------------------------------------------------
    # COSA C'E' DA MOSTRARE
    # ------------------------------------------------------------------

    def _metti_il_verso(self) -> None:
        """La Scrittura dell'anno, costruita una volta sola.

        Si costruisce al primo uso e poi si riusa: la data non cambia mentre
        il programma e' aperto, e rifare il riquadro ogni volta che un video
        finisce cambierebbe il modo in cui e' fatto senza che nessuno lo
        chieda.

        La pagina viene messa in fondo alla pila con `insertWidget`, non con
        `addWidget`: cosi' l'indice 0 resta quello del video, e non si
        sbaglia a scrivere `setCurrentIndex` con un numero che dipende
        dall'ordine in cui sono state create le pagine.
        """
        if self._pagina_verso is None:
            # PRIMA C'ERA LA DATA, E ADESSO C'E' LA SCRITTURA DELL'ANNO
            # ------------------------------------------------------------
            # Qui stava `testo_del_giorno`, che sul monitor secondario mostrava
            # solo la data - «domenica, 5 ottobre» - e nella Home, sotto, la
            # scritta «Apri il versetto di oggi dalla Bibbia».  E' stato deciso
            # di mettere via quella riga e di mostrare invece la «Scrittura
            # dell'anno», cioe' la frase che sta sulla pagina degli editori di
            # «Esaminiamo le Scritture ogni giorno del <anno>», presa dal
            # pacchetto **scaricato**.
            #
            # Il motivo di fondo e' che la data la dice anche il programma e non
            # da niente, mentre la frase e' l'unica cosa che si puo' leggere a
            # un braccio e mezzo, e cambia una volta all'anno invece che ogni
            # giorno.
            from SubViews.HomeView import scrittura_dell_anno

            self._pagina_verso = scrittura_dell_anno(self, lontano=True)
            self.pila.insertWidget(0, self._pagina_verso)
        return self._pagina_verso

    def mostra_verso(self) -> None:
        """Non c'e' niente da mostrare: la Scrittura dell'anno."""
        if self._schermo is None:
            return
        # NASCONO ENTRAMBI I RIQUADRI, NON SOLO UNO
        # --------------------------------------------
        # `_video` e' lo specchio che riceve i fotogrammi in copia,
        # `_uscita` e' il riquadro su cui il motore scarica il video.  Sono
        # due pezzi diversi e chiudere solo uno lascierebbe l'altro acceso:
        # dopo che il video e' finito resterebbe un rettangolo nero a tutto
        # schermo su un monitor che dovrebbe mostrare il verso del giorno, e
        # sembrerebbe un video che non parte.
        if self._video is not None:
            self._video.accetta(False)
            self._video.setVisible(False)
        if self._uscita is not None:
            self._uscita.setVisible(False)
        # Ogni finestra mostra il verso: anche un duplicato.
        self.pila.setVisible(True)
        pagina = self._metti_il_verso()
        if pagina is not None:
            self.pila.setCurrentWidget(pagina)
        self._comandi_in_fronte()

    def accendi_video(self):
        """Il riquadro che mostra il video, e se questa finestra lo riceve in copia.

        DUE RUOLI, E NON SI CONFONDONO
        ------------------------------
        Il **secondario** riceve il video dal motore: e' l'uscita vera, e il
        suo riquadro e' un `QVideoWidget` agganciato con `setVideoOutput`.

        Un **duplicato** invece riceve i **fotogrammi** copiati dal secondario:
        e' uno `SpecchioVideo`.  Non puo' essere un `QVideoWidget` perche' un
        programma ne ha una sola uscita video, e quella e' gia' al secondario.

        PERCHE' LA FINESTRA E' UN `ANY`: IL PROGRAMMA CHIEDE, LA FINESTRA RIS PONDE
        -----------------------------------------------------------------------
        Il lettore chiama `accendi_video()` su ogni finestra e collega quello
        che riceve.  Non deve sapere quale delle due e': se il secondo schermo
        cambiasse da uscita vera a specchio — e un giorno potrebbe, se i
        duplicati venissero prima — il lettore continuerebbe a funzionare senza
        toccare niente.

        NON ESISTE SINO A CHE SERVE
        ---------------------------
        Come prima, non viene creato al costruttore: un riquadro video senza
        filmato non mostra niente e, dove Qt non trova una scheda video,
        mostrarlo fa abortire il programma.  Vedi la nota di `__init__`.
        Dopo la prima volta resta, e viene solo mostrato e nascosto.
        """
        if self._video is None:
            self._video = SpecchioVideo(self)
            self._video.setObjectName("videoSchermoEsterno")
            # Davanti alla pila: il video deve coprire il verso, non stare
            # sotto una pagina della pila.
            self.layout().insertWidget(0, self._video)
            self._video.setVisible(False)
        specchio = self._video
        # ACCETTA I FOTOGRAMMI SOLO SE IL DUPLICATO
        # --------------------------------------------
        # Qui c'era `accetta(not self.riceve_copia)`, cioe' la condizione
        # **invertita**, ed e' il difetto segnalato: il terzo schermo restava
        # nero e il video non compariva.
        #
        # Perche' era invertita: sembrava che «solo video» volesse dire «non
        # ricevere niente, perche' il video lo prende qualcun altro».  Ma il
        # contrario e' vero — e sta in `imposta_frame`, che restituisce subito
        # se lo specchio non accetta:
        #
        #   - il **secondario** riceve il video **dal motore**, sul suo
        #     riquadro di uscita.  Il suo specchio non serve e non deve
        #     accettare: riceverebbe gli stessi fotogrammi due volte.
        #   - un **duplicato** non ha un'uscita sua — un programma ne ha una
        #     sola — quindi l'unico modo che ha e' ricevere i fotogrammi
        #     **in copia**.
        #
        # Quindi `accetta` e' vero esattamente per i duplicati, che sono
        # `riceve_copia`.  Niente `not`: il valore coincide con la condizione.
        specchio.accetta(self.riceve_copia)
        specchio.setVisible(True)
        self.pila.setVisible(False)
        self._comandi_in_fronte()
        return specchio

    def uscita_video(self):
        """Il `QVideoWidget` su cui il motore scarica il video: solo qui.

        Esiste **solo** nella finestra del secondo schermo.  Un duplicato
        non ha un'uscita propria e non deve chiederne una: chiamare questo
        su un duplicato restituirebbe `None`, e il lettore — che collega
        quello che riceve — non avrebbe niente su cui agganciarsi.

        DOVE ESCE IL VIDEO, E DOVE SI VEDE
        ------------------------------------
        Qui e' **l'uscita vera**: il motore scarica il video in questo
        riquadro, e da qui i fotogrammi vengono copiati su tutti gli altri
        schermi — i duplicati e il player dentro l'app.

        Il player dentro l'app non e' un posto dove il video «va»: e' un
        posto dove il video **si vede**, in copia.  Il primo schermo mostra
        l'applicazione, e dentro l'applicazione c'e' anche il video: e' quello
        che rende utile avere due schermi invece di uno solo, e non un lusso
        da disattivare.

        Con un solo monitor questo `QVideoWidget` non serve e non viene
        creato: li' non c'e' nessun monitor esterno e il video esce
        direttamente nel player, che e' l'unico posto dove puo' stare.
        """
        if self.riceve_copia:
            # Un duplicato non e' l'uscita: vedi la nota sopra.
            return None
        if self._uscita is not None:
            self._uscita.setVisible(True)
            return self._uscita

        # IL RIQUADRO VA NEL LAYOUT, E QUESTO ERA IL DIFETTO
        # --------------------------------------------------
        # Qui prima il `QVideoWidget` veniva **creato** ma non **messo nel
        # layout**: si chiamava `setObjectName`, `setAspectRatioMode`,
        # `setSizePolicy` e basta.  Un widget che non e' in nessun layout
        # conserva la sua misura iniziale — che per Qt e' 100x30 — e li' resta
        # per sempre: un **puntino in alto a sinistra**, che e' esattamente
        # quello che e' stato segnalato sul secondo schermo.
        #
        # La misura non e' «piccola»: e' proprio quella di prima di essere
        # messo a posto, e non la cambia nessun `resizeEvent` perche' nessun
        # layout la governa.  Un video che si vede in un centesimo dello
        # schermo non e' un video ridimensionato male: e' un video a cui
        # nessuno ha detto quanto deve essere grande.
        #
        # Quindi: si crea, si mette nel layout **in prima posizione** — cosi'
        # sta davanti alla pila del verso — e solo dopo gli si da' la misura.
        self._uscita = QVideoWidget(self)
        self._uscita.setObjectName("videoUscitaSchermo")
        self._uscita.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._uscita.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding)
        self.layout().insertWidget(0, self._uscita)
        self._uscita.setVisible(True)
        return self._uscita


    def spegni_video(self) -> None:
        """Qui non si mostra piu' il video: resta il verso del giorno.

        Si svuota anche il fotogramma rimasto: uno schermo che continua a
        mostrare l'ultima immagine del video sembra un video fermo, e il
        programma non e' in grado di dirti il contrario.
        """
        if self._video is not None:
            self._video.accetta(False)
            self._video.setVisible(False)
        # Vedi la nota di `mostra_verso`: anche l'uscita va nascosta.
        if self._uscita is not None:
            self._uscita.setVisible(False)
        # IL DUPLICATO MOSTRA IL VERSO COME IL SECONDO
        # --------------------------------------------
        # Prima qui, quando la finestra riceveva il video in copia, c'era un
        # ramo che spegneva la pila del verso e usciva: il duplicato restava
        # **nero** quando non c'era un video da mostrare.

        # Era una scelta — «il verso sta gia' sul secondo schermo» — che pero'
        # rende il duplicato non una copia ma un pezzo a meta'.  Se l'utente ha
        # scritto che il video va anche sul terzo, sul terzo deve andare tutto
        # quello che va sul secondo: **il video quando c'e' un video, e la
        # Scrittura dell'anno quando non c'e'**.

        # Un terzo monitor scuro mentre il secondo mostra la Scrittura sembra
        # un monitor spento, e non e' quello che e' stato chiesto.

        # Ogni finestra mostra il verso: anche un duplicato.
        self.pila.setVisible(True)
        pagina = self._metti_il_verso()
        if pagina is not None:
            self.pila.setCurrentWidget(pagina)
        self._comandi_in_fronte()

    def mostra_video(self) -> None:
        """Il video e' in arrivo: mettilo qui dentro.

        Il video copre **tutto**: la Scrittura dell'anno sparisce, e non e' una
        scelta di stile.  Se la finestra mostrasse il verso insieme al video,
        chi guarda l'altro monitor vedrebbe il video con una riga di testo
        sopra — e quella riga e' li' per quando non c'e' niente da guardare,
        non per sovrapporla a quello che c'e'.
        """
        if self._schermo is None:
            return
        self.pila.setVisible(False)

        # DUE RUOLI, DUE RIQUADRI
        # -----------------------
        # Il **secondo schermo** mostra il video dal riquadro su cui il motore
        # scarica davvero (`_uscita`).  Un **duplicato** invece mostra lo
        # specchio che riceve i fotogrammi in copia (`_video`).
        #
        # Prima qui si mostrava sempre e solo lo specchio, anche sul secondo
        # schermo — e quello sul secondo schermo non riceve niente, perche'
        # la copia la si spedisce ai **duplicati**.  Il risultato era che il
        # secondo schermo non mostrava il video, e il riquadro del motore,
        # lasciato nel layout con la sua misura minima, si vedeva come un
        # puntino in alto a sinistra.
        #
        # E i due riquadri non devono stare visibili **insieme**: il layout li
        # dividerebbe a meta' e il video comparirebbe piccolo.  Per questo
        # l'uno nasconde l'altro, sempre.
        if self.riceve_copia:
            specchio = self.accendi_video()
            specchio.accetta(True)
            specchio.setVisible(True)
            if self._uscita is not None:
                self._uscita.setVisible(False)
        else:
            if self._video is not None:
                self._video.accetta(False)
                self._video.setVisible(False)
            # `uscita_video()` crea il riquadro se non c'e' e lo mostra: e'
            # il posto che sa dargli la misura giusta, perche' conosce il
            # layout della finestra.
            self.uscita_video()
        # Il riquadro del video e' stato messo davanti a tutto appena ora, e
        # i tasti gli andrebbero sotto: si rialzano.  Vedi `_comandi_in_fronte`.
        self._comandi_in_fronte()

    def mostra_immagine(self, pixmap) -> None:
        """Una figura: mettila qui dentro, tenendo le proporzioni."""
        if self._schermo is None:
            return
        if pixmap is None or pixmap.isNull():
            self.mostra_verso()
            return
        if self._video is not None:
            self._video.accetta(False)
            self._video.setVisible(False)
        self.figura.setPixmap(pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.pila.setVisible(True)
        self.pila.setCurrentWidget(self.figura)
        self._comandi_in_fronte()

    def toglie_figura(self) -> None:
        """La figura non c'e' piu': libera la memoria e torna al verso."""
        self.figura.clear()
        self.mostra_verso()

    def nome_schermo(self) -> str:
        """Il nome dello schermo, per dire all'utente dove sta andando il video.

        PERCHE' NON BASTA `self._schermo`
        --------------------------------
        `_schermo` e' lo schermo **deciso**: quello scelto nelle impostazioni
        o quello trovato per conto nostro.  Ma se non si e' ancora deciso — la
        finestra e' stata appena creata, o nessuno ha ancora scritto niente —
        il campo e' vuoto e il nome tornerebbe una stringa vuota.

        E una stringa vuota in un messaggio fa «Il video si vede su .», che
        non dice niente e sembra un programma rotto.  Meglio dire lo schermo su cui
        la finestra e' **realmente**, che e' un fatto che il sistema sa sempre:
        e' quello a cui la finestra appartiene.

        Quindi si prova `_schermo` e, se non c'e', si chiede alla finestra.  Un
        nome racconta sempre **dove** si sta guardando, che e' l'unica cosa
        che questo metodo deve dire.
        """
        if self._schermo is not None:
            return self._schermo.name()
        try:
            maniglia = self.windowHandle()
            schermo = maniglia.screen() if maniglia is not None else None
        except RuntimeError:
            schermo = None
        return schermo.name() if schermo is not None else ""

    def dove_si_vede(self) -> str:
        """Dove si vede il video, con la preposizione gia' messa.

        IL PERCHE' LA PREPOSIZIONE STA QUI
        ----------------------------------
        Il nome di uno schermo si mette con «su»: «si vede su DP-2».  Ma il
        ripiego «il secondo schermo» si mette con «**sul**», non con «su il»:

            Il video si vede su il secondo schermo.   <- sbagliato
            Il video si vede sul secondo schermo.     <- giusto

        Le due frasi sono diverse, e scegliere la preposizione fuori dal metodo
        significa sceglierla una volta sola e sbagliare nell'altra.  Qui viene
        gia' giusta, e chi scrive il messaggio la mette dove va senza pensarci.
        

        PERCHE' NON BASTA IL NOME
        ------------------------
        Il nome dello schermo (`HDMI-1`, `DP-2`) e' la cosa piu' precisa, ma
        non c'e' **sempre**: ci sono ambienti in cui il sistema non dà un nome
        allo schermo, e allora il nome e' una stringa vuota.

        E una stringa vuota dentro una frase non si vede che manca: produce

            Il video si vede su . Qui sotto i comandi.

        che e' un messaggio **sbagliato**: sembra scritto male, e l'utente
        cerca un nome che non c'e'.  Meglio dire «il secondo schermo», che e'
        vero, si capisce, e resta vero anche quando il nome c'e' — perche' il
        secondo schermo e' comunque quello.

        IL NOME SI USA COMUNQUE
        -----------------------
        Quando c'e', il nome viene prima: «DP-2» dice **esattamente** quale
        monitor, e su una macchina con cinque schermi la differenza e' tutta
        li'.  Il secondo schermo e' il ripiego per quando non si puo' fare
        meglio, non la regola.
        """
        nome = self.nome_schermo()
        if nome:
            return f"su {nome}"
        return "sul secondo schermo"

    def resizeEvent(self, evento) -> None:
        """La finestra e' cambiata di misura: due cose da rimettere a posto.

        UN SOLO `resizeEvent`, E PERCHE' PRIMA CE N'ERANO DUE
        ---------------------------------------------------
        Qui sotto c'era un secondo `resizeEvent`, scritto quando la finestra
        non aveva ancora i tasti: si occupava solo della figura.  Due metodi
        con lo stesso nome nella stessa classe non danno nessun avviso: il
        secondo copre il primo e il primo diventa codice morto che sembra
        funzionante.

        Il danno reale era che **i tasti non venivano piu' messi a destra**,
        perche' a vincere era la versione vecchia: e infatti, rimpicciolendo
        la finestra, i tasti restavano a sinistra invece di spostarsi a
        destra.  Non era un problema di calcolo: era un metodo che non
        veniva chiamato.

        E' la stessa cosa che e' capitata con `mousePressEvent` qui sotto, e
        anche li' il secondo faceva sparire il primo.
        """
        super().resizeEvent(evento)
        # I tasti in alto a destra: la loro posizione dipende dalla larghezza
        # della finestra, quindi va rimessa a ogni misura nuova.
        self._metti_i_comandi_in_angolo()
        # La figura si riduce con la finestra, altrimenti resta piccola
        # nell'angolo di uno schermo grande.
        if self.figura.pixmap() is not None and not self.figura.pixmap().isNull():
            self.figura.setPixmap(self.figura.pixmap().scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))