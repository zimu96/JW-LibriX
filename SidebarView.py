#
#  SidebarView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 31/12/20.
#

"""La finestra: rail a sinistra, fascia in alto, contenuto, mini-player.

In Swift ``SidebarView`` non era una schermata ma la cosa che veniva messa
dentro ``WindowGroup``, cioe' la finestra intera.  Qui e' una ``QMainWindow``.

LA CORNICE
----------
Quattro pezzi, e sono le misure della specifica, non misure dedotte da uno
screenshot:

    rail 48 px   la colonna stretta delle icone, a sinistra
    alto 32 px   la fascia viola in alto
    contenuto    tutto il resto
    mini-player  la striscia in fondo, larga quanto la finestra

LA RAIL STA DENTRO LA FASCIA
-----------------------------
La rail comincia dal bordo superiore della finestra, e la fascia sta alla
sua destra.  Percio' la finestra non e' una colonna con la fascia in cima e
la rail sotto: e' una RIGA, con la rail come prima colonna e il resto come
seconda.  Se la fascia stesse in cima, la rail comincerebbe 32 pixel piu'
in basso, e le due cose non sembrerebbero piu' una fascia sola.

IL VIOOLA E' UNO SOLO
---------------------
La fascia e la rail sono viola in chiaro e in scuro.  Il tema cambia lo
sfondo, il testo e i bordi del contenuto: non tocca la fascia, che e' un
pezzo dell'app.  Vedi ``Utility/tema.py`` per il perche'.

LA PILA DELLE SCHERMATE
-----------------------
In Swift la navigazione era una ``NavigationView`` con sei sezioni.  Qui e'
una ``QStackedWidget`` con tutte le schermate dentro, e un elenco di indici
che dice qual e' la schermata di sotto.

Con sei pile, andare avanti e indietro fra due sezioni diverse fa perdere di
vista dove si era.  Con una sola pila e un indice di sezione, l'indietro
riporta sempre alla schermata da cui si e' partiti, che e' quello che ci si
aspetta da un pulsante con una freccia.
"""

import time

from SubViews.Conferma import ConfermaApp
from Utility import WolLingua
from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QProgressBar,
    QHBoxLayout,
    QMenu,
    QSlider,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ContentView import ContentView
from SubViews.BibleView import BibleView
from SubViews.DownloadsView import DownloadsView
from SubViews.HomeView import HomeView, _barra_scaricamento
from SubViews.LinguaMenu import LinguaMenu
from SubViews.MediaView import MediaView
from SubViews.NotiziaView import NotiziaView
from SubViews.SettingsView import SettingsView
from SubViews.UpdatesView import UpdatesView
from SplashScreen import _SplashScreen  # noqa: F401  (esportata: la usa JWLibraryApp)
from SubViews.PubView import PubView
from SubViews.PersonalStudyView import PersonalStudyView
from SubViews.AdunanzeView import AdunanzeView
from SubViews.PlaylistView import PlaylistView
from Utility import Aggiornamenti, CatalogoMedia, JWPubManager, Lingua, Rete, tema
from Utility.JWPubManager import pub_dir_name
from Utility.Structures.Generals import Document, Publication
from Utility import Plugin
from Utility.Stuff import icon, icona_tabler

# Le sezioni della rail: (titolo, simbolo del progetto originale).
#
# Il secondo nome e' quello che arriva dal progetto originale ("house.fill"),
# non il nome del file Tabler ("home").  `icon()` cerca il primo nella tabella
# e trova il secondo: i due nomi si somigliano ma sono diversi, e sbagliando
# si ottiene un pulsante vuoto senza nessun avviso.
#
# "Scaricati" STA DOPO "Pubblicazioni" E NON IN FONDO
# ---------------------------------------------------
# `jwl/DESIGN-SYSTEM.txt` 6.15 mette `Library` — che e' «cosa hai scaricato» —
# al terzo posto per importanza, subito dopo il catalogo.  Il motivo e' che le
# due sezioni sono le due metà della stessa domanda: `Pubblicazioni` dice cosa
# c'e' da prendere, `Scaricati` dice cosa hai gia' preso.  Mettendole agli
# estremi opposti della rail si costringe a passare da cinque icone per
# confrontarle.
#
# E "Novita'" resta in fondo, che e' la sua posizione: e' la sezione che si
# apre quando non si sa cosa fare, non quella che si apre per lavorare.
SEZIONI = [
    ("Home", "house.fill"),
    ("Bibbia", "book.fill"),
    ("Biblioteca Digitale", "library.fill"),
    ("Scaricati", "arrow.down.doc"),
    ("Adunanze", "calendar"),
    ("Ricerche", "bookmark.fill"),
    ("Impostazioni", "gearshape"),
]

# "SCARICATI" NON E' PIU' UNA VOCE DELLA RAIL
# =========================================
# `SEZIONI` elenca le sezioni che **esistono** e le costruisce tutte: «Scaricati»
# resta in quella lista e la sua schermata continua a esistere, perche' da li'
# arrivano cose — la spunta sul pacchetto appena scaricato, il conto di quello
# che sta scendendo, il rimando alla Home quando un video parte da li'.  Se
# sparisse dalla lista, tutte quei chiamanti avrebbero `sezioni.get(...)` a `None`
# e la sezione si romperebbe per un motivo che non c'entra con la rail.
#
# Quello che e' sparito e' il **pulsante**: la sezione si apre dalla tab
# «Scaricati» dentro «Biblioteca Digitale», che e' gia' li' accanto alle altre
# tre.  Con il pulsante in rail la stessa schermata si apriva in due posti, e
# due ingressi per una cosa sola sono quello che non si sa quale usare — peggio,
# la rail e' sempre visibile mentre la tab si vede solo quando quella sezione e'
# aperta, quindi il pulsante era l'unico dei due che si trova subito.
#
# `NELLA_RAIL` e' quindi la lista dei **pulsanti**, non delle sezioni.  Se un
# giorno un'altra sezione smette di stare in rail, si toglie di qui e non da
# `SEZIONI`, e la sezione continua a esistere.
NELLA_RAIL = [
    ("Home", "house.fill"),
    ("Bibbia", "book.fill"),
    ("Biblioteca Digitale", "library.fill"),
    ("Adunanze", "calendar"),
    ("Ricerche", "bookmark.fill"),
    ("Impostazioni", "gearshape"),
]

# Gli strumenti a destra nella fascia: (chiave, simbolo, tooltip).
#
# Il secondo nome e' quello del PROGETTO ORIGINALE ("magnifyingglass"), non
# il nome del file Tabler ("search").  `icon()` cerca il primo nella tabella
# e usa il secondo per trovare il file: se si da il nome del file la ricerca
# non trova niente e il pulsante resta vuoto senza dire niente.
#
# QUI CI SONO CINQUE PULSANTI E NON SETTE
# ---------------------------------------
# Tolti dalla fascia due, perche' erano di troppo:
#
#   l'ingranaggio   la sezione Impostazioni e' gia' nella rail, quindi
#                   l'icona era la stessa cosa in due posti.  Con due
#                   ingressi per la stessa schermata, uno dei due
#                   inevitablemente non la usa mai, e non si sa quale.
#
#   la luna e il sole  il tema si cambia nelle Impostazioni, nella scheda
#                   Aspetto.  In fascia era un secondo posto dove
#                   cambiarlo, e il secondo posto e' quello che si
#                   dimentica.
#
# NESSUNA FUNZIONALITA' PERSA
# ---------------------------
# Il tema non e' sparito: e' nella casella "Tema" delle Impostazioni, che
# scrive il file e fa riapplicare il foglio di stile a tutta l'app
# (`_tema_richiesto`).  Le Impostazioni non sono sparite: sono la sezione
# con l'ingranaggio nella rail.
#
# E LA LINGUA E' IL PRIMO STRUMENTO, E NON L'ULTIMO
# -------------------------------------------------
# Perche' e' la prima cosa che cambia tutto il resto: catalogo, copertine,
# categorie dei media e notizie parlano tutti la lingua scelta.  Sta a
# sinistra degli altri perche' e' l'unico strumento che non guarda una
# sezione: gli altri quattro portano da qualche parte, questo apre un menu.
# I SEGNALIBRI SONO L'ULTIMO, E VANNO TRA L'AGGIORNAMENTO E I TRE PUNTINI
# ---------------------------------------------------------------------
# Il segnalibro e' un comando che vale mentre si legge: segna il punto
# dove si e' arrivati, e mostra quelli gia' segnati.  Per questo sta nella
# fascia, che e' la parte della finestra che c'e' in tutte le schermate, e
# sta **dopo** l'aggiornamento e **prima** dei tre puntini: la parte alta a
# destra e' quella dei comandi, e i tre puntini (la dimensione del testo)
# chiudono la fascia perche' guardano il testo, non il capitolo.
STRUMENTI = [
    ("lingua", "globe", "Lingua"),
    ("cerca", "magnifyingglass", "Cerca"),
    ("audio", "headphones", "Ascolta"),
    ("aggiorna", "arrow.clockwise", "Aggiorna"),
    ("segnalibri", "bookmark.fill", "Segnalibri"),
]

# LA DIMENSIONE DEL TESTO
# -----------------------
# Il cursore e' una percentuale, non un numero di pixel: 100 e' la misura
# normale, sotto si legge piu' piccolo e sopra si ingrandisce.  Il minimo non
# e' zero: a zero il testo sparisce e non c'e' piu' niente da leggere, quindi
# non sarebbe un comando ma un modo per perdere l'articolo.  Il massimo e'
# 200%, che e' il doppio della misura normale ed e' gia' un ingrandimento
# notevole senza rendere la pagina illeggibile per righe troppo lunghe.
DIMENSIONE_TESTO_MIN = tema.DIMENSIONE_TESTO_MIN
DIMENSIONE_TESTO_MAX = tema.DIMENSIONE_TESTO_MAX
DIMENSIONE_TESTO_DEFAULT = tema.DIMENSIONE_TESTO_DEFAULT
DIMENSIONE_TESTO_CHIAVE = tema.DIMENSIONE_TESTO_CHIAVE


def _si_sta_leggendo(schermata) -> bool:
    """La schermata che si sta guardando e' un capitolo che si legge?

    Serve alla fascia: mentre si legge ci sono due strumenti in piu' — i
    segnalibri e le cuffie — e non ci sono nelle altre schermate.

    L'import e' dentro la funzione perche' `ArticleView` tira dentro il
    motore di Chromium, e il modulo non serve a tutto il programma: lo
    importa solo quando la domanda e' stata posta.
    """
    try:
        from SubViews.ArticleView import ArticleView
    except Exception:  # noqa: BLE001 - se il modulo non c'e', non si legge
        return False
    return isinstance(schermata, ArticleView)


def _traccia_della_pagina(titolo_traccia: str, documento) -> bool:
    """La traccia audio e' quella della pagina aperta?  Si confrontano i titoli.

    Il titolo del documento deve stare in quello della traccia (o viceversa),
    oppure il numero di «Lezione N» / «Capitolo N» deve coincidere.
    """
    import re

    def norm(testo) -> str:
        return " ".join(re.sub(r"[\W_]+", " ", str(testo or "").replace("\xa0", " ")
                               .replace("\u200b", "")).lower().split())

    if documento is None:
        return False
    traccia = norm(titolo_traccia)
    for candidato in (getattr(documento, "title", ""),):
        c = norm(candidato)
        if len(c) > 3 and (c in traccia or traccia in c):
            return True
    contesto = norm(getattr(documento, "contextTitle", ""))
    m1 = re.match(r"(lezione|capitolo|appendice)\s*0*(\w+)", contesto)
    m2 = re.match(r"(lezione|capitolo|appendice)\s*0*(\w+)", traccia)
    return bool(m1 and m2 and m1.groups() == m2.groups())


def _peso_del_file(voce: dict) -> int:
    """I byte del file di una voce di media, o 0 se il server non li manda.

    Serve alla barra di scaricamento: senza il totale la barra resta in
    indeterminate, si muove e non dice quanto manca.  Il campo e' `filesize`
    (tutto minuscolo) nella risposta dell'API, e non va inventato un numero
    quando manca: zero e' il valore che `_Scaricamento` gia' sa leggere come
    "non si sa".
    """
    try:
        return int(voce.get("filesize") or 0)
    except (TypeError, ValueError):
        return 0


def _altezza_risoluzione(nome: str) -> int:
    """I pixel di altezza di un nome di risoluzione come «720p».

    Serve solo per ordinare il menu' dalla piu' alta alla piu' bassa.  Il
    numero si prende dall'altezza, e non dalla larghezza, perche' e' l'altezza
    quella che dice la risoluzione: «720p» e non «1280p», e un video
    verticale ha una larghezza piccola e un'altezza grande.
    """
    cifre = "".join(c for c in nome if c.isdigit())
    return int(cifre) if cifre else 0


def _del_formato(voce: dict, formato: str) -> bool:
    """La voce del server e' un file del formato chiesto?

    Il server, per una traccia, manda tutto insieme: i video MP4, l'MP3 e i
    sottotitoli (AIVTT, un file di testo).  MP3 e sottotitoli non hanno
    altezza e il server li chiama «0p»: nel menu' delle risoluzioni
    comparivano due voci «0p», e sceglierle scaricava l'audio o il testo al
    posto del video.  Qui si tengono solo i file del tipo giusto.
    """
    mime = str(voce.get("mimetype") or "").lower()
    formato = str(formato or "").upper()
    if formato in ("AUDIO", "MP3"):
        return mime.startswith("audio/")
    if formato in ("VIDEO", "MP4"):
        return mime.startswith("video/")
    return mime.startswith(("audio/", "video/"))


def _per_altezza(scelte: list, altezza: int):
    """La scelta che ha la risoluzione voluta, o la piu' vicina da sotto.

    `scelte` e' ordinata dalla piu' alta; il primo elemento di ogni voce e'
    il nome («720p»).  Con `altezza` 0 (o None) si prende la piu' alta.  Se
    quella voluta non c'e' per quel video si prende la migliore che sta sotto,
    e se sono tutte piu' alte la piu' bassa: meglio un video un po' piu'
    piccolo di un video che non scende.
    """
    if not altezza:
        return scelte[0]
    for voce in scelte:
        if _altezza_risoluzione(voce[0]) <= int(altezza):
            return voce
    return scelte[-1]


def _nome_risoluzione(voce: dict) -> str:
    """Il nome della risoluzione di una voce di media, per il menu'.

    Si legge `frameHeight` e si scrive come lo scrive la televisione, «720p»:
    e' il numero che l'utente cerca, e non la formula del file
    («1280x720»), che nessuno conosce.

    Il `label` del server viene usato solo quando non c'e' l'altezza: il
    server lo chiama «240p» anche per un 320x180, e mettere «240p» accanto a
    «720p» nel menu' fa pensare che la lista sia sbagliata.  Fallo comparire
    solo quando non c'e' nient'altro da dire.
    """
    altezza = voce.get("frameHeight")
    if altezza:
        return f"{int(altezza)}p"
    etichetta = str(voce.get("label") or "").strip()
    return etichetta or "video"


class _Toast(QWidget):
    """Una notifica che appare al centro, senza cornice, e sparisce da sola.

    SERVE PER DIRE COSE BREVI SENZA BLOCCARE
    --------------------------------------
    Non e' una finestra modale: si vede, si legge, e va via.
    Perfetta per "Controllo aggiornamenti...", "Tutto aggiornato",
    "Trovati 3 aggiornamenti", ecc.

    POSIZIONE: AL CENTRO, FUORI DAL LAYOUT
    --------------------------------------
    Un popup in mezzo alla finestra, senza barra del titolo: sta sopra il
    contenuto e non sposta niente.  In cima alla finestra non compare mai
    niente.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("toast")
        self.setVisible(False)

        riga = QHBoxLayout(self)
        riga.setContentsMargins(16, 10, 16, 10)
        riga.setSpacing(10)

        self.icona = QLabel(self)
        self.icona.setFixedSize(20, 20)
        riga.addWidget(self.icona, 0)

        self.testo = QLabel("", self)
        self.testo.setObjectName("toastTesto")
        self.testo.setWordWrap(True)
        riga.addWidget(self.testo, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._nascondi)

    def mostra(self, messaggio: str, tipo: str = "info", durata_ms: int = 4000) -> None:
        """Mostra il toast.
        :param tipo: "info" (viola), "success" (viola chiaro), "warning" (arancio), "error" (rosso)
        """
        # Colori tema app: viola per success/info, arancio/rossi per warning/error
        colori = {
            "info": ("#a855f7", "info.circle"),
            "success": ("#c084fc", "check.circle"),
            "warning": ("#f39c12", "alert.circle"),
            "error": ("#e74c3c", "x.circle"),
        }
        colore, simbolo = colori.get(tipo, colori["info"])
        self.icona.setPixmap(icon(simbolo, colore, 20).pixmap(20, 20))
        self.testo.setText(messaggio)
        self.testo.setStyleSheet(f"color: {colore}; font-size: 13px;")

        chiaro = tema.tema_attivo()
        c = tema.colori(chiaro)
        self.setStyleSheet(
            f"#toast {{ background-color: {c['pannello']}; "
            f"border: 1px solid {colore}; border-radius: 8px; }}"
            " #toast QLabel { background: transparent; }")
        padre = self.parentWidget()
        larghezza = min(460, (padre.width() if padre else 600) - 80)
        self.setFixedWidth(max(240, larghezza))
        self.adjustSize()
        self.setVisible(True)
        self._al_centro()
        self.raise_()
        self._timer.start(durata_ms)

    def _al_centro(self) -> None:
        padre = self.parentWidget()
        if padre is not None:
            self.move((padre.width() - self.width()) // 2,
                      (padre.height() - self.height()) // 2)

    def _nascondi(self) -> None:
        self.setVisible(False)


class _Scaricamento(QWidget):
    """La riga che dice che cosa si sta scaricando e quanto manca.

    PERCHE' ESISTE, E DOVE NON SI METTE
    ---------------------------------
    Prima c'era una riga di tre pixel appoggiata al bordo inferiore della
    fascia viola.  Tre pixel sono troppo pochi per dire due cose che servono
    entrambe — *che cosa* e *quanto manca* — e la fascia viola e' il bordo
    della finestra: un bordo non e' il posto dove si guarda mentre si aspetta.

    Adesso la riga e' **dentro** la finestra, sopra la pila delle schermate.

    E PERCHE' ESISTE ANCORA, SE I PACCHETTI HANNO LA BARRA SULLA LORO SCHEDA
    --------------------------------------------------------------------------
    Perche' qui ci sono due scaricamenti che **non hanno una scheda**:
    il catalogo delle pubblicazioni e il catalogo dei media.  Non sono una
    pubblicazione, quindi non c'e' nessuna copertina su cui mettere una barra,
    e senza questa riga non si saprebbe che il programma sta lavorando.  Un
    pacchetto scaricato dalla sezione Novita' mostra invece il progresso sulla
    sua propia scheda, che e' il posto dove l'utente sta guardando.

    IL TEMPO CHE MANCA, E PERCHE' E' UNA STIMA
    -------------------------------------------
    Il tempo che manca si calcola da quello che e' passato e da quanto
    manca: se ne sono fatti 40 su 150 in un minuto, e gli altri 110 costeranno
    circa tre quarti di quel minuto.  E' una stima e viene scritta «circa»,
    perche' non puo' essere diversamente: la rete cambia velocita' e un file
    grosso e' piu' lento di dieci piccoli.

    Con zero file fatti non si stima niente: il primo capitolo puo' durare
    piu' di tutti gli altri messi insieme, e una stima fatta sul primo file
    sbaglia di un ordine di grandezza.  Il contatore «40 su 150» dice la
    stessa cosa in un numero, e un numero non mente.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("scaricamento")
        self._quando_inizio = 0.0

        riga = QHBoxLayout(self)
        riga.setContentsMargins(10, 5, 10, 5)
        riga.setSpacing(10)

        self.icona = QLabel(self)
        # Il grigio e' quello delle altre icone del programma, per coerenza:
        # le icone non cambiano con il tema, e un grigio diverso qui e uno
        # diverso in `HomeView` si vedono uno accanto all'altro.
        self.icona.setPixmap(icon("arrow.down.doc", "#8a8a8a", 18).pixmap(18, 18))
        self.icona.setFixedSize(18, 18)
        riga.addWidget(self.icona, 0)

        self.nome = QLabel("", self)
        self.nome.setObjectName("scaricaNome")
        riga.addWidget(self.nome, 0)

        self.barra = QProgressBar(self)
        self.barra.setObjectName("scaricaBarra")
        self.barra.setTextVisible(False)
        self.barra.setRange(0, 0)          # 0,0 = non si sa ancora
        self.barra.setFixedHeight(6)
        riga.addWidget(self.barra, 1)

        self.conto = QLabel("", self)
        self.conto.setObjectName("scaricaConto")
        riga.addWidget(self.conto, 0)

        self.setVisible(False)

    def comincia(self, nome: str, totale: int = 0) -> None:
        """Uno scaricamento parte: la riga si vede e riparte da capo."""
        self.nome.setText(nome)
        self.conto.setText("")
        if totale > 0:
            self.barra.setRange(0, totale)
        else:
            self.barra.setRange(0, 0)      # non si sa: si muove e basta
        self.barra.setValue(0)
        self._quando_inizio = time.time()
        self.setVisible(True)

    def avanza(self, scritti: int, totale: int) -> None:
        """Lo scaricamento e' a meta'."""
        if self.isHidden():
            return
        if totale > 0 and self.barra.maximum() != totale:
            self.barra.setRange(0, totale)
        self.barra.setValue(scritti)
        self.conto.setText(self._testo(scritti, totale))

    def _testo(self, scritti: int, totale: int) -> str:
        """«147 su 150» — solo il conteggio, senza stime di tempo."""
        if totale <= 0:
            return ""
        return f"{scritti} su {totale}"

    def finito(self) -> None:
        """Lo scaricamento e' finito: la riga sparisce."""
        self.setVisible(False)
        self.conto.setText("")
        self.nome.setText("")


class _PulsanteIcona(QWidget):
    """Un pulsante di sola icona, delle misure della specifica.

    Serve perche' la fascia e la rail hanno due misure diverse e non si puo'
    usare lo stesso widget per le due: nella fascia la casella e' 32x32, nella
    rail 36x34.  E' un contenitore invece di un QToolButton perche' l'icona
    va centrata esattamente, e il padding di un QToolButton sposta tutto di
    qualche pixel.

    IL SEGNALE E' UN ATTRIBUTO DI CLASSE, NON DI ISTANZA
    ----------------------------------------------------
    In PyQt6 ``self.clic = Signal()`` dentro ``__init__`` non funziona.  Il
    descrittore del segnale viene costruito quando la CLASSE viene creata,
    quindi un segnale creato per ogni istanza non viene registrato, e
    ``connect`` su di esso non esiste.

    Il sintomo arriva quando si collega e non quando si dichiara, ed e' la
    parte che fa perdere tempo:

        pulsante.clic.connect(...)  ->  AttributeError: 'pyqtSignal' object
                                       has no attribute 'connect'
    """
    clic = Signal()

    def __init__(self, simbolo: str, lato: int, tooltip: str = "", attivo: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(lato, lato)
        self.setToolTip(tooltip)
        self._simbolo = simbolo
        self._attivo = attivo
        self._dimensione_icona = 20
        self._pixmap = None
        self._aggiorna_icona()

    def _aggiorna_icona(self) -> None:
        """Il glifo, del colore giusto per il viola.

        Sopra il viola il bianco si legge sempre, quindi l'icona e' chiara.
        Non "il colore del tema": quello cambierebbe in scuro e sopra il viola
        le icone sparirebbero.

        Sta in un attributo e non in un QLabel figlio perche' l'icona va
        centrata al pixel nella casella: un QLabel aggiunge i suoi margini e
        sposta tutto di qualche pixel, e in una fascia di 32 px quei pixel si
        vedono.
        """
        chiaro = "#ffffff" if self._attivo else "#d2c6e0"
        icona = icon(self._simbolo, chiaro, self._dimensione_icona)
        self._pixmap = icona.pixmap(self._dimensione_icona, self._dimensione_icona)
        self.update()

    def cambia_simbolo(self, simbolo: str) -> None:
        """Scambia il glifo.

        Serve al pulsante del tema, che mostra la luna in chiaro e il sole
        in scuro.  Il glifo sta in un attributo e non in un QLabel figlio,
        quindi si cambia ridisegnando: niente da ricreare.
        """
        if simbolo != self._simbolo:
            self._simbolo = simbolo
            self._aggiorna_icona()

    def impostato(self, attivo: bool) -> None:
        if attivo != self._attivo:
            self._attivo = attivo
            self._aggiorna_icona()
            self.update()

    def mousePressEvent(self, evento) -> None:
        self.clic.emit()

    def paintEvent(self, evento) -> None:
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QColor, QPainter

        pittore = QPainter(self)
        pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
        pittore.setPen(Qt.PenStyle.NoPen)

        # Il fondo: bianco al 22% sulla voce attiva, al 16% sotto il
        # puntatore.  Due livelli e non uno, cosi' la sezione aperta si vede
        # anche con il puntatore sopra.
        if self._attivo:
            pittore.setBrush(QColor(255, 255, 255, 56))
        elif self.underMouse():
            pittore.setBrush(QColor(255, 255, 255, 41))
        else:
            pittore.setBrush(Qt.GlobalColor.transparent)
        pittore.drawRoundedRect(QRectF(0, 0, self.width(), self.height()),
                                tema.RAGGIO, tema.RAGGIO)

        if self._pixmap is not None:
            x = (self.width() - self._pixmap.width()) // 2
            y = (self.height() - self._pixmap.height()) // 2
            pittore.drawPixmap(x, y, self._pixmap)
        pittore.end()

    def entraEvent(self, evento) -> None:
        self.update()

    def esciEvent(self, evento) -> None:
        self.update()


class SidebarView(QMainWindow):
    """La finestra principale."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("")  # vuoto: il sistema mostra solo il nome dell'app

        # IL MOTORE WEB NASCE PRIMA DELLA FINESTRA
        # ----------------------------------------
        # Il primo `QWebEngineView` creato dentro una finestra gia' mostrata
        # costringe Qt a ricrearla (Hide, WinIdChange, Show): l'utente vedeva
        # sparire e ricomparire tutta la finestra per un secondo, la prima
        # volta che apriva un testo.  Con un riquadro da un pixel gia' qui,
        # la finestra nasce col tipo giusto e non si ricrea piu'.
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        self._motore_web_acceso = QWebEngineView(self)
        self._motore_web_acceso.setGeometry(0, 0, 1, 1)
        self._motore_web_acceso.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._motore_web_acceso.show()

        # I tasti laterali del mouse (indietro e avanti), se il mouse li ha.
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

        # «RESTA SOPRA», COME LA FINESTRA DELLO SCHERMO SECONDARIO
        # --------------------------------------------------------
        # Entrambe le finestre del programma hanno questo segno, e serve
        # perche' stiano **nello stesso strato**: e' li' dentro che l'ordine
        # si decide con l'ultima finestra alzata, e quindi questa finestra
        # puo' andare davanti alla finestra del video quando serve.
        #
        # Senza, il video starebbe sempre davanti a tutto — anche alla
        # finestra del programma — e quando il mouse e' sullo schermo del
        # video, all'apertura, il programma si troverebbe sotto una finestra a
        # tutto schermo da cui non si puo' uscire.  Con il segno su entrambe,
        # le due finestre si passano davanti a vicenda e le **altre
        # applicazioni** restano sotto, che e' quello che si voleva.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        #: La cronologia, **per widget** e non per indice.
        #:
        #: Prima qui c'era `list[int]`: gli indici delle schermate nella pila.  E'
        #: fragile perche' `go_back` toglie una schermata dalla pila quando non e'
        #: permanente, e togliere un elemento da una lista sposta tutti gli
        #: indici dopo di lui di uno.  Quindi ogni indice gia' salvato passava a
        #: puntare alla schermata successiva — e l'indietro, un giro dopo, tornava
        #: nella sezione sbagliata senza dire niente.
        #:
        #: Il sintomo e'最难: funziona la prima volta, e la seconda porta nel
        #: posto sbagliato.  Un widget non si sposta mai quando cambia il numero
        #: di quelli intorno, quindi qui non c'e' niente che possa andare storto.
        self._schermate: list = []
        #: Le schermate da cui si e' tornati indietro, e da cui si puo' tornare
        #: avanti.  Cresce a ogni `go_back` e si svuota a ogni navigazione nuova.
        self._avanti: list = []
        self.sezioni: dict[str, QWidget] = {}
        self.strumenti: dict[str, list] = {}
        self.pulsanti_sezione: dict[str, _PulsanteIcona] = {}
        # Qui sotto c'era un secondo `self._avanti: list = []`, **morto**: non
        # lo leggeva e non lo scriveva nessuno, e sopraviveva dal tempo in cui
        # la cronologia avanti era un'altra cosa.  Tolto quando la cronologia
        # avanti e' diventata una lista vera e si e' dovuta dichiarare.
        #
        # Una dichiarazione morta e' pericolosa per una ragione sola: se il
        # nome torna in uso, la seconda dichiarazione **nasconde** la prima e il
        # programma funziona con la lista vuota, senza dire niente.
        self._schermo_corrente = None
        #: Il segnalibro da aprire appena finisce il download che l'utente ha
        #: accettato.  Vedi `_chiedi_download_segno` e `_riprendi_posizione`.
        self._posizione_in_attesa = None
        # Da dove si e' entrati nella sezione "Biblioteca Digitale" per far partire un
        # video o un audio, e dove tornare quando quel media si chiude o
        # finisce.  Vedi `_vai_a_multimedia` e `_torna_da_dove_sono_partito`.
        self._sezione_attiva: str | None = None
        self._ritorno: str | None = None
        #: Quando l'audio parte da una schermata che non e' una sezione — la
        #: notizia — la promessa della X non puo' essere un nome di sezione.
        #: Qui si tiene la schermata vera da ripristinare.  Vedi
        #: `_torna_da_dove_sono_partito` e `_torna_alla_schermata`.
        self._ritorno_schermata = None
        #: La dimensione del testo scelta dall'utente, in percentuale.  Si
        #: legge dal file e si applica alla schermata che si sta guardando.
        self._dimensione_testo = self._dimensione_testo_salvata()
        # DA DOVE STA PARTENDO IL MEDIA, E NON DOVE TORNA
        # ------------------------------------------------------
        # `_provenienza` e' il posto **da cui l'utente e' partito** per
        # far partire un media: lo mette `_vai_a_multimedia`, che e' il
        # momento in cui il programma porta se stesso nei Media perche'
        # l'utente ha premuto un video da un'altra sezione.
        #
        # `_ritorno` e' la **promessa**: da dove riportare l'utente quando
        # il media finisce o viene chiuso.  Sono due cose diverse perche' il
        # momento in cui si sa quale e' l'una o l'altra non coincide: la
        # provenienza si sa prima che il media parta (l'ha premuto l'utente),
        # il ritorno solo quando il media parte davvero.
        #
        # Senza i due campi, un media partito dalla Home che arriva tardi
        # (la lista dei media viene dalla rete) viene scambiato per uno
        # partito dalla lista dei Media, e la X porta l'utente nel posto
        # sbagliato.
        self._provenienza: str | None = None
        #: L'articolo da cui e' partito un video: la X ci riporta li'.
        self._articolo_di_partenza = None
        # IL LETTORE GRANDE NASCONDE LA STRISCIA IN FONDO
        # -------------------------------------------------
        # `_lettore_grande_visibile` dice se in questo momento il lettore
        # grande dentro la sezione "Biblioteca Digitale" e' aperto: e' l'unica cosa che
        # fa sparire la striscia mentre un media sta suonando.
        #
        # Non e' una cosa che segue lo stato della riproduzione, e non e'
        # neppure un interruttore che l'utente deve ricordare: e' quello
        # che si vede.  Con il lettore grande aperto ci sarebbero **due**
        # lettori per lo stesso video, e quello in fondo e' una seconda
        # barra di comandi con lo stesso play premuto in due posti.
        #
        # La regola e' quella detta da `_mini_stato`: striscia accesa
        # quando qualcosa suona e il lettore grande non si vede.  Quando
        # l'utente preme la freccia giu' il lettore si abbassa e la striscia
        # torna; quando cambia sezione il lettore si abbassa e la striscia
        # torna; quando dalla striscia si torna al lettore grande, la
        # striscia sparisce.  Senza che nessuno debba premere niente due
        # volte per gli stessi due gesti.
        self._lettore_grande_visibile = False

        self._costruisci_rail()
        self._costruisci_fascia()
        self._costruisci_contenuto()
        self._costruisci_mini()
        self._monta()

        # Uno schermo che compare dopo l'avvio va acceso come gli altri.  Va
        # collegato qui, e non dentro `_prepara_lo_schermo_esterno`: quel pezzo
        # gira una volta sola e una volta sola accenderebbe uno schermo che
        # arriva dopo — mentre il collegamento resta per tutta la vita della
        # finestra.
        self._ascolta_gli_schermi()

        # I tasti che fanno le stesse cose dei pulsanti.  Un pulsante senza
        # il suo tasto e' un pulsante che funziona una volta su due.
        self._scorciatoie()

        # Il tema: letto dal file, non indovinato.
        self._chiaro = tema.tema_salvato()
        self._applica_tema()

        self._costruisci_sezioni()
        if Plugin.visibile("timer") and Plugin.schermo("timer"):
            QTimer.singleShot(1500, self._schermo_timer_richiesto)
        self._seleziona(0)
        QTimer.singleShot(0, self._crea_icona_sfondo)

        # IL CONTROLLO ALL'APERTURA NON E' PIU' QUI
        # -------------------------------------------
        # Prima stava in questo punto: `if Aggiornamenti.automatici():` partiva
        # un controllo dei cataloghi mentre la finestra era gia' sullo schermo,
        # e i 58 megabyte del catalogo scendevano davanti agli occhi
        # dell'utente, accendendo la riga di scaricamento in fondo alla
        # finestra.
        #
        # La riga in fondo e' fatta per quello che l'utente ha premuto: li'
        # l'occhio e' gia' sul pezzo che si sta prendendo, e la barra e' sotto
        # quello che sta guardando.  All'avvio non c'e' nessun pezzo da
        # guardare — la finestra si sta ancora aprendo — quindi la barra
        # raccontava uno scaricamento che l'utente non aveva chiesto e non
        # poteva fermare.
        #
        # Ora il controllo e' dentro la splash, che e' il posto giusto: li' la
        # finestra non c'e' ancora, quindi nessuna barra, e quello che si vede
        # e' il logo con la sua barra — non una riga in fondo a una schermata
        # vuota.  La casella «Controlla da solo all'apertura» comanda sempre
        # la stessa cosa, solo che la comanda la splash: accesa si controlla e
        # si prende, spenta non si chiede niente e l'unico modo resta il tasto
        # in alto — che funziona in entrambi i casi.
        self._cataloghi_in_corso = 0
        # Il menu' delle risoluzioni, tenuto finche' e' aperto.
        #
        # Va dichiarato qui e non quando si apre: `_menu_aperto` si usa per
        # **tenerlo** (il menu' ha `self` come padre, e Qt lo libera quando
        # l'ultimo riferimento Python sparisce, cioe' finito il metodo che lo ha
        # costruito).  Se l'attributo esistesse solo da quando si apre un menu',
        # il primo accesso a un attributo inesistente dentro un segnale sarebbe
        # un `AttributeError` in mezzo a un richiamo Qt — e cioe' un `abort()`
        # senza traceback, che e' la cosa peggiore da cui diagnosticare.
        self._menu_aperto = None

    def moveEvent(self, evento) -> None:
        """La finestra si e' mossa: decidere chi sta davanti.

        PERCHE' NON SI SPOSTA LA FINESTRA
        --------------------------------
        Prima, se la finestra finiva sullo schermo del video, il programma la
        **spostava** da se' su un altro schermo.  E' stato tolto perche'
        non funziona: il gestore di finestre mette la finestra dove gli
        pare, e correggerlo mentre decide porta a due program's outcome — la
        finestra finisce nel posto sbagliato e l'utente non ha toccato
        niente.  E' capitato: l'app si apriva fuori dal monitor scelto senza
        che nessuno l'avesse spostata.

        Adesso il programma non tocca la posizione e decide solo **chi sta
        davanti**:

        - finestra del programma **fuori** dallo schermo del video → la
          finestra del video sta **sopra**, e il video si vede;
        - finestra del programma **dentro** lo schermo del video → la
          finestra del programma sta **sopra**, e l'utente la vede e la
          sposta lui, dove vuole.

        Il secondo caso e' quello che prima ti lasciava il programma sotto una
        finestra a tutto schermo, senza modo di afferrarla per spostarla.
        """
        super().moveEvent(evento)
        self._decide_chi_sta_sopra()

    def resizeEvent(self, evento) -> None:
        """La finestra e' cambiata di size: stessa decisione di `moveEvent`."""
        super().resizeEvent(evento)
        self._decide_chi_sta_sopra()

    def _schermo_video_richiesto(self) -> None:
        """Cambiato lo schermo del video: la finestra secondaria si sposta.

        SENZA RIAVVIARE IL PROGRAMMA
        -----------------------------
        Il video va sullo schermo scelto **subito**.  Prima la scelta valeva
        per il prossimo avvio: si cambiava lo schermo nelle impostazioni, si
        chiudeva il programma, si riapriva, e fino ad allora il video andava
        ancora sul vecchio.  Un'impostazione che si vede al prossimo avvio non
        e' un'impostazione.

        LE DUE FINESTRE SI SCAMBIANO DA SOLE, POI
        -------------------------------------------
        La finestra secondaria appena nata e' a tutto schermo e passa davanti.
        Se la finestra del programma restasse sotto, sarebbe di nuovo il caso
        da cui siamo partiti: una finestra a tutto schermo davanti a quella
        del programma, senza modo di afferrarla.

        Quindi appena la nuova finestra e' a posto, si alza **questa**, che e'
        il pezzo di «le altre applicazioni restano sotto»: l'utente vede
        subito il programma, e il verso del giorno si vede lo stesso appena
        l'utente torna a guardare l'altro monitor.

        Perche' non appena si cambia ma un istante dopo: la finestra che si
        sposta ha bisogno di un momento per arrivare sullo schermo nuovo, e se
        la finestra del programma sale subito la copre per un attimo e poi la
        copre lo schermo intero — che e' il lampo che si voleva evitare.  Il
        rinvio e' di zero millisecondi, quindi l'attesa e' di un giro di
        eventi, non di un secondo.
        """
        from PyQt6.QtCore import QTimer

        try:
            from SubViews import SchermoEsterno
        except ImportError:
            return

        # La vecchia finestra va chiusa: se resta, si ritroverebbero due
        # finestre a tutto schermo, e quella vecchia sullo schermo di prima
        # non si chiuderebbe piu' perche' nessuno la comanda.
        SchermoEsterno.chiudi_se_ce_n_e()
        QTimer.singleShot(0, lambda: self._alzati_alla_fine())

    def _alzati_alla_fine(self) -> None:
        """Le finestre degli schermi esterni sono nuove: si accendono tutte.

        NON SOLO LA SECONDARIA
        ----------------------
        Qui si chiamava `istanza()`, che crea **una** finestra.  Con la
        duplicazione le finestre sono N: chiamando solo `istanza()` si
        ricreerebbe il secondo schermo e si lascerebbero fuori i duplicati
        appena spuntati, che l'utente ha scelto un secondo fa e si
        ritroverebbe spenti fino al prossimo video.

        Si chiama quindi lo stesso pezzo di `_prepara_lo_schermo_esterno`, che
        chiama `finestre()`: crea quello che manca, chiude quello che non serve
        piu' e restituisce tutto quello che c'e'.  Con una finestra sola fa
        esattamente quello che faceva `istanza()`.

        E NON SI ALZA PIU' NIENTE
        ------------------------
        Qui finiva con `self.raise_()`, per mettere la finestra del programma
        davanti a quella del video.  Non serve piu': la finestra del video non
        ha piu' il «resta sempre sopra» e sta su un altro schermo, quindi non
        copre questa e non c'e' niente da mettere davanti.  Alzare una
        finestra a tutto schermo davanti al desktop coprirebbe anche le altre
        applicazioni, per niente.

        Quindi qui si creano le finestre e basta.  Il nome del metodo e' rimasto
        perche' e' il posto giusto da cui farlo e cambiare il nome romperebbe
        i due posti che lo chiamano; quello che fa e' spiegato sopra.
        """
        self._accendi_gli_schermi_esteri()

    def _decide_chi_sta_sopra(self) -> None:
        """Chi si alza: la finestra del programma o quella del video.

        LE DUE REGOLE, E SONO IN DUE POSTI DIVERSI
        ------------------------------------------
        «Resta sopra» e' acceso su **entrambe** le finestre: cosi' stanno
        nello stesso strato e l'ultima che viene alzata va davanti, e le altre
        applicazioni restano sotto — che e' quello che si voleva.

        Poi si decide solo quale delle due alzare:

        - il programma e' su un altro schermo → si alza il **video**, perche'
          e' li' che l'utente sta guardando;
        - il programma e' finito sullo schermo del video → si alza la
          **finestra del programma**, cosi' l'utente la vede e la sposta lui.
          Prima non si vedeva niente e non c'era modo di afferrarla.

        Se non c'e' schermo secondario non c'e' niente da decidere: si esce,
        perche' il metodo viene comunque da `moveEvent` e da `resizeEvent`,
        anche quando l'opzione e' «dove sta la finestra».
        """
        from Utility import Schermi

        if not getattr(self, "_a_posto", False):
            # Prima che la finestra sia comparsa non si decide niente: il
            # gestore di finestre sta ancora mettendola a posto.  Vedi
            # `showEvent`.
            return

        try:
            from SubViews.SchermoEsterno import istanza
        except ImportError:
            return
        esterno = istanza()
        if esterno is None:
            return

        # NON SI ALZA PIU' NIENTE
        # ----------------------
        # Prima qui si sceglieva quale delle due finestre alzare davanti a
        # tutte, e la scelta dipendeva da quale schermo fosse la finestra del
        # programma.  La ragione era che **entrambe** avevano il «resta
        # sempre sopra»: stando nello stesso strato, l'ultima alzata finiva
        # davanti, e senza scegliere qualcosa una delle due finestre restava
        # sotto.
        #
        # Adesso la finestra del video **non ha piu'** il «resta sempre
        # sopra» (vedi `SchermoEsterno.__init__`) e non viene piu' alzata.
        # Quindi non c'e' piu' nulla da scegliere: sono su due schermi
        # diversi, l'una non copre l'altra, e alzare una finestra a tutto
        # schermo davanti al desktop non serve a niente e copre tutto il
        # resto.
        #
        # Quindi qui non si fa niente, e il metodo resta perche' e' chiamato
        # da `moveEvent` e da `resizeEvent`: toglierlo richiederebbe
        # cambiare quei due posti, e lascerlo vuoto spiega da solo che e'
        # voluto.
        _ = Schermi
        return

    def activateEvent(self, evento) -> None:
        """La finestra e' stata attivata: alzala sopra la finestra del video.

        Sono nello stesso strato perche' entrambe hanno «resta sopra», quindi
        l'ordine dipende dall'ultima che e' stata alzata.  Dopo un click su un
       'altra applicazione l'utente torna qui e si aspetta di trovare la
        finestra del programma davanti, non dietro: senza questa riga il
        video la coprirebbe di nuovo.
        """
        super().activateEvent(evento)
        self._decide_chi_sta_sopra()

    def showEvent(self, evento) -> None:
        """La finestra e' comparsa: adesso puo' nascere lo schermo secondario.

        PERCHE' QUI E NON NEL COSTRUTTORE
        ---------------------------------
        Lo schermo secondario si accendeva in `__init__`, cioe' **prima** che
        questa finestra fosse mai comparsa.  Il risultato era che la finestra a
        tutto schermo si apriva per prima e restava davanti, e la finestra del
        programma finiva o coperta o di traverso: l'utente apriva il programma
        e non lo vedeva.

        Due finestre che nascono insieme sono una gara che non si vince: la
        seconda che si apre prende il davanti, e non importa quale sia.  Quindi
        prima nasce la finestra del programma — il gestore di finestre la
        mette dove vuole lui — e **poi**, a evento di finestra gia' avvenuto,
        nasce l'altra.

        Il rinvio di zero millisecondi serve perche' `showEvent` arriva
        mentre la finestra si sta ancora sistemando: farlo subito richiama
        `moveEvent` prima che il gestore di finestre abbia detto la sua, e si
        lotteggiano.
        """
        super().showEvent(evento)
        # Da qui in poi la finestra e' sullo schermo, e il trascinamento
        # dell'utente va corretto se finisce su quello del video.
        #
        # Finche' non e' comparsa, no: il gestore di finestre sta decidendo
        # dove metterla e correggerlo significa correggerlo mentre decide, e il
        # risultato e' una finestra nel posto sbagliato con l'utente che non ha
        # ancora toccato niente.  Misurato prima di questo: all'avvio l'app
        # finiva fuori dal monitor scelto senza che nessuno l'avesse spostata.
        self._a_posto = True
        self._dopo_la_prima_apertura()

    def _dopo_la_prima_apertura(self) -> None:
        """Una volta sola, alla prima apertura: accende lo schermo secondario."""
        if getattr(self, "_schermo_esterno_preparato", False):
            return
        self._schermo_esterno_preparato = True
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._prepara_lo_schermo_esterno)
        # La domanda sulla cartella dati compare SUBITO (primo avvio, app
        # offline, Home vuota): ogni attimo di attesa e' un attimo con una
        # finestra vuota davanti.  Il backup puo' aspettare un momento.
        from SubViews import SceltaCartellaDati
        QTimer.singleShot(0 if SceltaCartellaDati.serve() else 700,
                          self._proponi_backup_iniziale)

    def _proponi_backup_iniziale(self) -> None:
        """Il riquadro «importare il backup?», se l'utente non l'ha nascosto.

        PRIMA LA CARTELLA DATI, POI IL BACKUP
        -------------------------------------
        Al primo avvio si chiede prima dove salvare i dati: il backup
        importato finisce proprio li', quindi la domanda sul backup arriva
        solo dopo la risposta.
        """
        from SubViews import SceltaCartellaDati
        if SceltaCartellaDati.serve():
            SceltaCartellaDati.SceltaCartellaDati(self, self._cartella_dati_scelta)
            return
        from SubViews.BackupIniziale import BackupIniziale
        BackupIniziale.mostra_se_serve(self, self._importa_backup_scelto)

    def _cartella_dati_scelta(self, cartella) -> None:
        """Risposta a «Dove salvo i dati?»: si salva e l'app si riavvia.

        L'ordine del primo avvio e': cartella, catalogo, backup.  Fino a
        qui non si e' scaricato niente.  Si riavvia SEMPRE, anche se la
        scelta e' la cartella predefinita, cosi' la strada e' una sola: al
        riavvio la schermata di avvio scarica il catalogo nella cartella
        scelta, e poi la Home chiede del backup.
        """
        from Utility.Structures import Paths as modulo_paths
        modulo_paths.segna_scelta_fatta()
        modulo_paths.salva_cartella(cartella)
        from SubViews.SettingsView import riavvia_app
        riavvia_app()

    def _importa_backup_scelto(self) -> None:
        """Sceglie un file .jwlibrary, lo importa e rinfresca le schermate."""
        from Utility.UserData.BackupManager import BackupManager
        def fine(riepilogo, errore):
            if riepilogo:
                self._backup_importato(BackupManager.testo_riepilogo(riepilogo))
        BackupManager.restore_backup(parent=self, su_fine=fine)

    def _backup_importato(self, testo: str) -> None:
        """Dopo un import: le schermate leggono di nuovo preferiti e segni."""
        from PyQt6.QtCore import QTimer
        self.mostra_toast(testo, "success", 8000)
        QTimer.singleShot(0, self._ricrea_tutte_sezioni)

    def _prepara_lo_schermo_esterno(self) -> None:
        """Accende gli schermi esterni, se e' stato scelto uno schermo.

        PERCHE' QUI E NON QUANDO SERVE
        ------------------------------
        Lo schermo secondario deve essere **gia' acceso** all'avvio, con il
        verso del giorno dentro: e' il suo stato quando non c'e' un video o
        una figura da mostrare.  Se la finestra nascesse al primo video, per
        tutto il resto del tempo quello schermo resterebbe spento — e uno
        schermo spento sembra spento, quindi sembrerebbe un monitor rotto,
        mentre invece e' semplicemente vuoto.

        Se invece non e' stato scelto nessuno schermo, non si crea niente:
        `istanza()` restituisce None, ed e' il segnale che alle sezioni serve
        per capire che il video deve restare nel riquadro dentro l'app.

        Non viene costruita se lo schermo salvato non e' piu' collegato: uno
        staccato non si puo' mostrare, e aprire una finestra a schermo intero
        sul primario quando si voleva il terzo schermo coprirebbe l'app.

        E SI ACCENDONO TUTTE, DUPLICATI COMPRESI
        ------------------------------------------
        Qui si chiamava **solo** `istanza()`, che crea **una** finestra: quella
        dello schermo secondario multimediale.  I duplicati non nascevano, e il
        difetto era che con tre monitor e due caselle spuntate «duplica», il
        programma all'avvio ne accendeva uno solo.

        Il sintomo e' uguale in ogni forma: l'utente apre il programma, due
        monitor si accendono e il terzo resta spento, e nelle impostazioni la
        casella **e' gia' spuntata** — non c'e' niente da correggere li'.  Per
        farlo comparire bisognava andare nelle impostazioni, togliere la spunta
        e rimetterla; e funzionava, perche' quella strada chiude e riapre tutte
        le finestre.

        Il motivo e' che le due strade facevano cose diverse: `_alzati_alla_fine`,
        quella delle impostazioni, chiama `finestre()` — che crea quello che
        manca e chiude quello che non serve piu' — mentre qui si chiamava
        `istanza()`.  Due strade per accendere le finestre esterne che non
        fanno lo stesso lavoro sono il modo piu' semplice di avere un programma
        che funziona dopo che l'hai sistemato e non funziona al riavvio.

        Quindi qui si chiama il pezzo unico, `_accendi_gli_schermi_esteri`, che
        fa esattamente quello che fanno le impostazioni: al primo giro di
        eventi **tutte** le finestre sono accese, insieme, senza che l'utente
        debba toccare niente.

        UN MONITOR VERO E UNO VIRTUALE SONO LA STESSA COSA
        ---------------------------------------------------
        Qui dentro non si distingue, e non si deve distinguere: il codice non
        chiede «e' vero o virtuale?», chiede «l'hai scelto?».  Uno schermo che
        il sistema non ha ancora messo a disposizione non viene acceso — non
        perche' e' virtuale, ma perche' **non c'e'**: e quando compare,
        `_ascolta_gli_schermi` lo accende con la stessa regola degli altri.

        La regola e' una sola e vale per tutti: **uno schermo acceso al primo
        colpo**.
        """
        self._accendi_gli_schermi_esteri()

    def _ascolta_gli_schermi(self) -> None:
        """Un monitor che compare dopo l'avvio va acceso come gli altri.

        LO SCHERMO CHE ARRIVA DOPO
        -------------------------
        C'e' un momento in cui il sistema ha gia' fatto partire il programma ma
        i monitor non sono ancora tutti quelli che saranno: un portatile che
        si sveglia, una docking station che si annuncia, uno schermo che il
        compositor mette a disposizione con qualche secondo di ritardo.  E' la
        strada che prende uno schermo virtuale.

        Prima questo non lo sapeva nessuno: le finestre degli schermi esterni
        nascevano una volta sola, all'avvio, e uno schermo comparito dopo non
        aveva nessuna finestra — restava spento fino a che l'utente non
        andava nelle impostazioni a togliere e rimettere la spunta.

        IL PEZZO E' LO STESSO, NON UNO NUOVO
        ------------------------------------
        Qui si chiama esattamente quello che si chiama all'avvio, e per lo
        stesso motivo: due strade per accendere gli schermi esterni che fanno
        cose diverse divergono, e la prima divergenza si vede subito.

        E NON SI ACCENDE UNO SCHERMO CHE L'UTENTE NON HA SCELTO
        ------------------------------------------------------
        Il pezzo crea finestre solo per gli schermi spuntati nelle impostazioni
        e per quello che porta il video.  Quindi qui non si accende nulla di
        nuovo: si accendono **gli stessi schermi** di prima, e se uno di quelli
        non era ancora comparito lo si accende ora.  Un terzo monitor che
        l'utente non ha spuntato resta spento, come deve: accenderlo sarebbe
        inventing cose che l'utente non ha chiesto.
        """
        try:
            from PyQt6.QtGui import QGuiApplication

            applicazione = QGuiApplication.instance()
            if applicazione is not None:
                applicazione.screenAdded.connect(self._schermo_aggiunto)
        except (AttributeError, TypeError):
            # Senza questo collegamento il programma funziona lo stesso:
            # semplicemente uno schermo che compare dopo non si accende.
            pass

    def _schermo_aggiunto(self, _schermo=None) -> None:
        """E' comparso uno schermo: si riapplica la regola degli schermi."""
        from PyQt6.QtCore import QTimer

        # Un giro di eventi, non subito: mentre il sistema sta ancora
        # annunciando lo schermo, `screenshot` puo' restare vuoto e il pezzo
        # dei duplicati non avrebbe niente su cui lavorare.  E' lo stesso
        # rinvio di zero millisecondi che usa gia' il resto di questa finestra.
        QTimer.singleShot(0, self._accendi_gli_schermi_esteri)

    def _accendi_gli_schermi_esteri(self) -> None:
        """Il pezzo unico: accendi le finestre degli schermi che servono.

        Lo chiamano tre posti — l'avvio, uno schermo che compare, e le
        impostazioni quando l'utente cambia qualcosa — e perche' sia uno solo
        e' l'unico modo che i tre non possano divergere.  Sta dentro un `try`
        perche' senza schermi esterni il programma parte lo stesso: e' un
        monitor in piu', non una schermata.
        """
        try:
            from SubViews.SchermoEsterno import finestre, istanza

            istanza()
            finestre(self.window())
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # LA CORNICE
    # ------------------------------------------------------------------

    def _monta(self) -> None:
        """Mette i quattro pezzi dentro la finestra.

        LA RIGA, NON LA COLONNA
        ----------------------
        La rail comincia dal bordo superiore della finestra e la fascia sta
        alla sua destra, quindi la finestra e' una RIGA: la rail e' la prima
        colonna, e alla sua destra c'e' una colonna con la fascia in cima, il
        contenuto e il mini-player in fondo.

        Se la fascia stesse in cima e la rail sotto, la rail comincerebbe 32
        pixel piu' in basso e le due cose non sembrerebbero piu' una fascia
        sola: il viola si vedrebbe a due altezze diverse.

        Senza questa funzione i quattro pezzi esistono ma non sono figli di
        nessun layout: Qt li disegna tutti in alto a sinistra, l'uno sopra
        l'altro, e la finestra sembra vuota.  E' successo: la cornice era
        completa e lo schermata mostrava solo il nome dell'app.
        """
        self.setObjectName("finestra")

        # TOAST: popup al centro, sopra tutto, fuori dal layout
        self.toast = _Toast(self)

        # la colonna a destra della rail: fascia, toast, contenuto, mini-player
        self._colonna = tema.sfondo(QWidget(), "colonna")
        colonna = QVBoxLayout(self._colonna)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(0)
        colonna.addWidget(self.fascia)
        colonna.addWidget(self._contenitore, 1)
        # il mini-player e' l'ultimo, e sta in fondo perche' e' un elemento
        # a parte: quando compare spinge il contenuto in alto e non lo
        # copre.
        colonna.addWidget(self.mini)

        riga = tema.sfondo(QWidget(), "riga")
        disposizione_riga = QHBoxLayout(riga)
        disposizione_riga.setContentsMargins(0, 0, 0, 0)
        disposizione_riga.setSpacing(0)
        disposizione_riga.addWidget(self.rail)
        disposizione_riga.addWidget(self._colonna, 1)

        # CENTRAL WIDGET, NON setLayout
        # ----------------------------
        # QMainWindow ha gia' un layout suo, quello delle aree ancorabili e
        # del menastro.  Chiamare setLayout su una QMainWindow mette la
        # disposizione in un posto che Qt riordina: il risultato e' una
        # finestra con la cornice pigiata nell'angolo in alto a sinistra,
        # delle dimensioni minime, e il resto bianco.
        #
        # Il modo e' mettere la disposizione su un QWidget e consegnarlo con
        # setCentralWidget: e' l'unico modo che QMainWidget accetta.
        self.setCentralWidget(riga)
        self._riga = riga

    def _costruisci_rail(self) -> None:
        """La colonna stretta delle icone, a sinistra, tutta viola."""
        self.rail = QWidget()
        self.rail.setObjectName("rail")
        self.rail.setFixedWidth(tema.RAIL)
        disposizione = QVBoxLayout(self.rail)
        disposizione.setContentsMargins(6, 4, 6, 8)
        disposizione.setSpacing(1)

        # `NELLA_RAIL` e non `SEZIONI`: le sezioni sono sette, i pulsanti sei.
        for titolo, simbolo in NELLA_RAIL:
            pulsante = _PulsanteIcona(simbolo, tema.ICONA_RAIL, titolo)
            pulsante.clic.connect(lambda t=titolo: self._sceglie_una_sezione(t))
            disposizione.addWidget(pulsante, 0, Qt.AlignmentFlag.AlignHCenter)
            self.pulsanti_sezione[titolo] = pulsante
        # Plugin Timer: il tasto esiste sempre ma si vede solo se il plugin
        # e' installato e acceso.  Non e' in NELLA_RAIL: gli indici di quella
        # lista sono usati dalle scorciatoie.
        self._rail_layout = disposizione
        tasto_timer = _PulsanteIcona("timer", tema.ICONA_RAIL, "Timer")
        tasto_timer.clic.connect(lambda: self._apri_timer())
        disposizione.addWidget(tasto_timer, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pulsanti_sezione["Timer"] = tasto_timer
        tasto_timer.setVisible(Plugin.visibile("timer"))
        disposizione.addStretch(1)

    def _costruisci_fascia(self) -> None:
        """La fascia viola in alto: indietro, avanti, il nome, gli strumenti."""
        self.fascia = QWidget()
        self.fascia.setObjectName("fascia")
        self.fascia.setFixedHeight(tema.ALTO)
        disposizione = QHBoxLayout(self.fascia)
        disposizione.setContentsMargins(4, 0, 4, 0)
        disposizione.setSpacing(2)

        self._indietro = _PulsanteIcona("chevron.left", tema.ICONA_ALTO, "Indietro")
        self._indietro.clic.connect(self._torna_indietro)
        # `_avanti_btn` e non `_avanti`: la cronologia avanti e' una lista e il
        # pulsante e' un tasto.  Con lo stesso nome, il primo a essere stato
        # scritto (la lista) avrebbe coperto il pulsante, e `clic.connect` su una
        # lista avrebbe detto soltanto che le liste non si premono — ma solo
        # quando qualcuno ci passava vicino.
        self._avanti_btn = _PulsanteIcona("chevron.right", tema.ICONA_ALTO, "Avanti")
        self._avanti_btn.clic.connect(self.go_forward)
        disposizione.addWidget(self._indietro)
        disposizione.addWidget(self._avanti_btn)

        self.nome = QLabel("", self.fascia)
        self.nome.setStyleSheet(
            "color: #ffffff; font-weight: 600; font-size: 15px; padding: 0 6px;")
        disposizione.addWidget(self.nome, 1)

        # LA BARRA SULLA FASCIA: NON C'E' PIU'
        # -------------------------------------
        # Qui c'era una riga di tre pixel appoggiata al bordo inferiore della
        # fascia viola.  Non c'e' piu' perche' era nel posto sbagliato: la
        # fascia e' il bordo della finestra, e un bordo non e' il posto dove
        # si guarda mentre si aspetta.  Tre pixel non bastano a dire *che
        # cosa* si sta prendendo e *quanto manca*, che sono le due cose che
        # servono.
        #
        # Adesso c'e' `_Scaricamento`: dentro la finestra e **in fondo**.  La
        # vedi in `_costruisci_contenuto`, e i tre metodi
        # `_scaricamento_inizia`, `_scaricamento_avanza` e
        # `_scaricamento_finito` parlano con quella e non piu' con questa.
        self.barra = None
        # Il viola della fascia e' l'unico colore che non cambia con il tema,
        # e la barra ci sta sopra: senza un colore suo sarebbe bianca in scuro
        # e invisibile sul viola in chiaro.  Il riempiento e' il viola
        # schiarito, non il bianco: il bianco su una riga di 3 pixel si legge
        # come un errore di disegno, non come una percentuale.
        # I due colori vengono da `tema` e non sono scritti qui: il
        # fondo e' il viola della fascia, il riempimento e' il suo
        # schiarito.  Il perche' di quei colori e' scritto accanto a
        # `tema.AVANZAMENTO`.
        #
        # Copiarli qui avrebbe fatto di questo un secondo posto dove
        # cambiare un colore, che e' il modo tipico di ritrovarsi la barra
        # di un colore in una schermata e di un altro in un'altra.
        self.casella_strumenti = QWidget(self.fascia)
        disposizione_strumenti = QHBoxLayout(self.casella_strumenti)
        disposizione_strumenti.setContentsMargins(0, 0, 0, 0)
        disposizione_strumenti.setSpacing(2)
        for chiave, simbolo, tooltip in STRUMENTI:
            pulsante = _PulsanteIcona(simbolo, tema.ICONA_ALTO, tooltip)
            # Il pulsante passa con se': il menu' delle cuffie si apre **sotto di
            # lui**, e non dove sta il puntatore.  Con la mano ferma sulla fascia
            # un menu' che compare sotto il mouse si apre dove l'utente non sta
            # guardando.
            pulsante.clic.connect(lambda c=chiave, p=pulsante: self._strumento(c, p))
            disposizione_strumenti.addWidget(pulsante)
            self.strumenti.setdefault(chiave, []).append(pulsante)
        disposizione.addWidget(self.casella_strumenti)

        # Nella sezione Timer gli strumenti della fascia (lingua, cerca, cuffie,
        # aggiorna) non servono: al loro posto ci sono i due menu del timer,
        # File e Visualizza, come pulsanti della fascia.
        self._casella_timer = QWidget(self.fascia)
        riga_timer = QHBoxLayout(self._casella_timer)
        riga_timer.setContentsMargins(0, 0, 0, 0)
        riga_timer.setSpacing(2)
        # Un solo pulsante, i tre puntini: dentro ci sono i menu del timer.
        altro = _PulsanteIcona("ellipsis.circle", tema.ICONA_ALTO, "Menu del timer")
        altro.clic.connect(lambda p=altro: self._menu_del_timer("Altro", p))
        riga_timer.addWidget(altro)
        self._casella_timer.setVisible(False)
        disposizione.addWidget(self._casella_timer)

        # I TRE PUNTINI DELLA DIMENSIONE DEL TESTO
        # ----------------------------------------
        # Stanno fuori da `STRUMENTI` perche' non sono uno strumento di una
        # sezione: servono mentre si legge, anche nella notizia, e devono
        # esserci sempre.  Se stessero dentro `STRUMENTI`, la regola della Home
        # — che nasconde tutto tranne Aggiorna — li nasconderebbe proprio dove
        # il comando serve di piu'.
        self._pulsante_testo = _PulsanteIcona(
            "ellipsis.circle", tema.ICONA_ALTO, "Dimensione del testo")
        self._pulsante_testo.clic.connect(self._apri_menu_testo)
        disposizione.addWidget(self._pulsante_testo)
        #: Il menu' aperto, se c'e'.  Serve a chiuderlo e a non aprirne due.
        self._menu_testo = None

    # LA RIGA DEI SCARICAMENTI IN FONDO NON C'E' PIU'
    # ====================================================
    # Prima qui c'era `_Scaricamento`: una riga in fondo alla finestra con il
    # nome di quello che stava scendendo e una barra.  Ora non c'e' piu', e il
    # progresso si vede **dentro la card** di quello che si sta scaricando.
    #
    # LA RIGA IN FONDO ERA SBAGLIATA, E IL MOTIVO E' UNO SOLO
    # -------------------------------------------------------
    # Una riga sola puo' dire una cosa sola: "qualcosa sta scendendo".  In una
    # griglia di trecento pubblicazioni non dice **quale**, e l'utente che ha
    # appena premuto una card sta guardando quella card, non il fondo della
    # finestra.  Doveva stare li', accanto a quello che ha premuto.
    #
    # E' sparita del tutto, non nascosta: un widget non aggiunto al layout non
    # occupa spazio e non si vede, ma lasciarlo costruito e' codice che nessuno
    # usa e che un giorno qualcuno riattaccherebbe perche' "era li' prima".
    # I tre metodi qui sotto restano perche' sono i segnali a cui si collegano
    # le sezioni, e non fanno piu' niente.

    def _scaricamento_inizia(self, nome: str, totale: int) -> None:
        """Uno scaricamento comincia: la barra e' gia' accesa sulla card.

        Il metodo resta perche' `PubView` e le altre sezioni emettono questo
        segnale e non devono sapere che la riga in fondo non esiste piu'.  Il
        posto dove il progresso si vede lo mette `_catalogo`, che accende la
        barra sulla card giusta.
        """
        return

    def _scaricamento_avanza(self, scritti: int, totale: int) -> None:
        """Uno scaricamento e' a meta'.

        Lo stesso: il segnale resta, il disegno lo fa la barra sulla card.
        """
        return

    def _scaricamento_finito(self) -> None:
        """Uno scaricamento e' finito: la card lo sa gia' da se'."""
        return

    def mostra_toast(self, messaggio: str, tipo: str = "info", durata_ms: int = 4000) -> None:
        """Mostra una notifica toast in alto.
        :param tipo: "info" (blu), "success" (verde), "warning" (arancio), "error" (rosso)
        """
        self.toast.mostra(messaggio, tipo, durata_ms)

    def _costruisci_contenuto(self) -> None:
        """Il contenuto, che sta fra la fascia e il mini-player."""
        self.pila = QStackedWidget()
        self.pila.setObjectName("centro")
        self.titolo_barra = QLabel("")
        self.titolo_barra.setObjectName("titoloPagina")
        self.titolo_barra.setVisible(False)

        # LA BARRA DELLA SCHERMATA, FRA IL TITOLO E LA PILA
        # ------------------------------------------------
        # Le schermate che si aprono dentro un'altra — l'elenco dei capitoli
        # di una pubblicazione, quello dei capitoli di un libro della Bibbia —
        # hanno un metodo `toolbar()` che restituisce la barra con il pulsante
        # «indietro» e il nome.  Quel metodo **non era chiamato da nessuna
        # parte**: esisteva, e i controlli lo provavano, ma l'applicazione no.
        #
        # Il risultato era che quelle schermate si aprivano spoglie: nessun
        # titolo, nessun pulsante per tornare indietro, e capitoli disegnati
        # come pulsanti piatti senza colore.  Erano l'unica schermata del
        # programma che non sembrava dello stesso programma.
        #
        # Qui c'e' il posto dove metterla, e `_metti_la_barra` la mette.  Il
        # contenitore resta nascosto quando la schermata non ha una barra sua:
        # le sezioni principali hanno gia' la fascia viola e i loro titoli, e
        # una barra in piu' sopra la pila sarebbe un titolo in due posti.
        self._barra_schermata = QWidget()
        self._riga_barra = QHBoxLayout(self._barra_schermata)
        self._riga_barra.setContentsMargins(0, 0, 0, 0)
        self._riga_barra.setSpacing(0)
        self._barra_schermata.setVisible(False)

        self._contenitore = tema.sfondo(QWidget(), "contenitore")
        disposizione = QVBoxLayout(self._contenitore)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)
        disposizione.addWidget(self.titolo_barra)
        disposizione.addWidget(self._barra_schermata)
        # Qui sopra la schermata corrente compare il lettore quando un video parte
        # da una sezione che non e' la Biblioteca: vedi `_entra_in_multimedia`.
        self._ospite_lettore = QWidget()
        QVBoxLayout(self._ospite_lettore).setContentsMargins(0, 0, 0, 0)
        self._ospite_lettore.setVisible(False)
        self._lettore_collegato = False
        disposizione.addWidget(self._ospite_lettore, 1)
        # La stessa maniglia della Biblioteca: trascinandola si decide quanto spazio
        # prende il lettore e quanto la schermata sotto (posti 2 e 4 del layout).
        from SubViews.MediaView import _HandleRidimensiona
        self._maniglia_lettore = _HandleRidimensiona(
            self._ospite_lettore, self.pila, disposizione, 2, 4, self._contenitore)
        self._maniglia_lettore.setVisible(False)
        disposizione.addWidget(self._maniglia_lettore, 0)
        disposizione.addWidget(self.pila, 1)

        # NELLA FINESTRA NON C'E' PIU' NESSUNA RIGA DI SCARICAMENTO
        # ------------------------------------------------------------
        # Qui prima c'era `_Scaricamento`, una riga in fondo alla finestra con
        # il nome di quello che stava scendendo.  Non c'e' piu'.
        #
        # Il posto del progresso e' **la card** di quello che si scarica: e' li'
        # che l'utente ha premuto, e li' che sta guardando mentre aspetta.  Una
        # riga sola in fondo alla finestra poteva dire «qualcosa sta
        # scendendo» e non quale, e in una griglia di trecento pubblicazioni
        # quella informazione non serve a niente.
        #
        # Non si toglie il widget dalla classe `_Scaricamento` perche' la
        # finestra non lo costruisce piu': la classe resta nel file perche'
        # `tema.py` ha ancora le sue regole e perche' toglierla sarebbe
        # mettere mano a cose che non c'entrano.  Ma qui non se ne crea, e non
        # se ne vede.


    def _costruisci_mini(self) -> None:
        """La striscia del lettore in fondo, larga quanto la finestra.

        NASCOSTA FINCHE' NON SUONA.  Una striscia vuota in fondo a una
        finestra e' spazio buttato via, e nell'app precedente c'era anche
        quello: un lettore con niente dentro occupava 40 pixel e non
        spiegava niente.
        """
        from PyQt6.QtWidgets import QSlider

        self.mini = QWidget()
        self.mini.setObjectName("mini")
        self.mini.setFixedHeight(44)
        self.mini.setVisible(False)

        disposizione = QHBoxLayout(self.mini)
        disposizione.setContentsMargins(12, 0, 8, 0)
        disposizione.setSpacing(10)

        # LA COPERTINA, A SINISTRA DEL TESTO
        # -----------------------------------
        # Un quadrato con l'anteprima: la copertina della canzone se e' un
        # audio, l'immagine del video se e' un video.  Sta **prima** del titolo
        # perche' e' la cosa che si riconosce a colpo d'occhio: dieci righe di
        # testo e un nome che non si ricorda, e la copertina dice subito di
        # che media si tratta senza leggere niente.
        #
        # Quando non c'e' — il media non ha miniatura, o non e' ancora
        # arrivata — resta un quadrato scuro vuoto invece di sparire: se il
        # widget scomparisse, il titolo si sposterebbe ogni volta che arriva
        # un'immagine, e la striscia sembrerebbe che si muove da sola.
        self.mini_anteprima = QLabel(self.mini)
        self.mini_anteprima.setObjectName("miniAnteprima")
        self.mini_anteprima.setFixedSize(32, 32)
        self.mini_anteprima.setScaledContents(True)
        disposizione.addWidget(self.mini_anteprima, 0)

        self.mini_titolo = QLabel("", self.mini)
        self.mini_titolo.setObjectName("titolo")
        self.mini_stato = QLabel("", self.mini)
        self.mini_stato.setObjectName("stato")
        colonna = QVBoxLayout()
        colonna.setSpacing(0)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.addWidget(self.mini_titolo)
        colonna.addWidget(self.mini_stato)
        # La parte del titolo non cresce oltre il 38%: altrimenti con un
        # titolo lungo schiaccia il lettore e il testo non si vede piu'.
        contenitore_info = QWidget()
        contenitore_info.setMaximumWidth(360)
        contenitore_info.setLayout(colonna)
        disposizione.addWidget(contenitore_info)

        self.mini_slider = QSlider(Qt.Orientation.Horizontal, self.mini)
        # Lo stesso nome di oggetto del cursore del lettore grande, e non un
        # nome suo.
        #
        # Il perche' e' una correzione vera e non una scioltezza: il nome
        # era "lettore", che non corrispondeva a nessuna regola del foglio di
        # stile, quindi i due cursori della striscia restavano con il
        # disegno di default di Qt — azzurro — mentre quelli del lettore
        # grande erano viola.  Due cursori nella stessa finestra con due
        # colori diversi, e quello che l'utente correggeva era solo uno dei
        # due.
        #
        # Dare a un widget **lo stesso nome** del suo gemello e' il modo che
        # funziona: il foglio di stile ha una regola sola e vale per tutti e
        # due.  Copiare le regole una volta per posto e' il modo che non
        # funziona: il giorno che se ne cambia una, l'altra resta vecchia e
        # non si sa quale.
        self.mini_slider.setObjectName("barraLettore")
        disposizione.addWidget(self.mini_slider, 1)

        # IL PULSANTE DI PLAY E PAUSA
        # ----------------------------
        # Sta per primo e c'e' anche quando non suona niente: e' il comando
        # che l'utente cerca quando qualcosa e' partito, e se comparisse
        # solo mentre suona potrebbe non trovarlo proprio quando gli serve.
        #
        # Un pulsante che cambia faccia e non due pulsanti con uno spento:
        # l'utente preme quello spento, non succede niente, e sembra rotto.
        self.mini_play = _PulsanteIcona("play.fill", tema.ICONA_ALTO,
                                        "Riproduci o ferma")
        self.mini_play.clic.connect(self._mini_commuta)
        disposizione.addWidget(self.mini_play)

        # IL VOLUME
        # ---------
        # Anche questo c'e' sempre, per lo stesso motivo: il volume si
        # abbassa mentre si guarda, e cercarlo e accorgersi che non c'e'
        # peggio che trovarlo gia' li'.
        self.mini_volume = QSlider(Qt.Orientation.Horizontal, self.mini)
        # Stesso nome del volume del lettore grande: vedi sopra.
        self.mini_volume.setObjectName("volumeLettore")
        self.mini_volume.setRange(0, 100)
        self.mini_volume.setValue(100)
        self.mini_volume.setMaximumWidth(90)
        self.mini_volume.setToolTip("Volume")
        self.mini_volume.valueChanged.connect(self._mini_volume)
        disposizione.addWidget(self.mini_volume, 0)
        self.mini_read = _PulsanteIcona("speaker.fill", tema.ICONA_ALTO,
                                           "Leggi")
        self.mini_read.clic.connect(self._mini_read)
        disposizione.addWidget(self.mini_read)

        # LA FRECCIA IN SU', SUBITO A SINISTRA DELLA X
        # -------------------------------------------
        # Il gemello di quella che sta nella schermata grande: qui riporta al
        # lettore grande, li' torna alla striscia piccola.  Stanno nelle due
        # facce della stessa cosa, quindi nella stessa posizione — la penultima
        # — cosi' l'occhio impara il posto una volta sola.
        #
        # Serve perche' dalla striscia non si arriva al lettore grande in
        # nessun altro modo: senza questo tasto passare dal mini al grande
        # significherebbe andare a cercare la sezione Media nella rail, e per
        # un video che si sta guardando e' un giro che non ha senso fare.
        self.mini_espandi = _PulsanteIcona("chevron.up", tema.ICONA_ALTO,
                                            "Torna al lettore grande")
        self.mini_espandi.clic.connect(self._mini_espandi)
        disposizione.addWidget(self.mini_espandi, 0)

        self.mini_chiudi = _PulsanteIcona("xmark", tema.ICONA_ALTO,
                                          "Ferma e chiudi")
        # IL PULSANTE DI FERMA E' IL COMANDO CHE MANCAVA
        # -----------------------------------------------
        # Prima questo era "nascondi la striscia", e il nome diceva gia' il
        # difetto: nascondevano la striscia **lasciando suonare**.  Il
        # programma continuava a riprodurre un brano che l'utente aveva
        # chiuso, e senza nessun comando a portata di mano per fermarlo:
        # bisognava tornare nella sezione Media sperando che il lettore
        # fosse ancora li'.
        #
        # Adesso ferma davvero, e la striscia sparisce dopo.  E' la cosa che
        # l'utente si aspetta da una X: non "non lo vedo piu'", ma "non
        # suona piu'".
        self.mini_chiudi.clic.connect(self._mini_ferma)
        disposizione.addWidget(self.mini_chiudi)

        self._collega_mini_al_motore()

    def _collega_mini_al_motore(self) -> None:
        """La striscia ascolta il motore, e il motore sa quando tornare qui.

        LA STRISCIA E' L'ULTIMO POSTO DOVE IL VIDEO PUO' STARE
        -------------------------------------------------------
        Senza questo, uscendo dalla sezione Media il widget video veniva
        distrutto e il player restava attaccato a un widget morto: il video
        spariva e **dopo qualche secondo il playback si fermava da solo**.

        Il sintomo e' il peggiore: non c'era nessun errore, nessun messaggio,
        e il programma sembrava decidere da se' di smettere.  Il motivo e'
        che la catena era rotta in un punto di cui nessuno sapeva niente: il
        player era di un pezzo di interfaccia che veniva buttato via, e non
        era detto a nessuno che quel pezzo era il suo schermo.

        Qui si dice.  Quando la sezione Media chiude il lettore, il video
        torna qui dentro, che e' un posto che vive quanto la finestra.
        """
        # `from Utility import Lettore` e NON `from Utility.Lettore import
        # Lettore`: il secondo porta dentro **la classe** (che si chiama
        # Lettore), e `Lettore.motore()` su una classe cerca un attributo di
        # classe, che non esiste:
        #
        #     AttributeError: type object 'Lettore' has no attribute 'motore'
        #
        # Il primo porta il **modulo**, e li' `motore` e' la funzione.  Il
        # nome del modulo e quello della classe coincidono, quindi i due
        # import dicono la stessa parola e portano cose diverse: e' il motivo
        # per cui questo si scrive per esteso e non si "semplifica".
        from Utility import Lettore

        self._motore = Lettore.motore()
        # Il video e' a schermo intero?  La striscia sparisce in quel caso, e
        # torna quando rientra.  Va tenuto qui e non dedotto ogni volta dal
        # lettore, perche' la finestra a schermo intero e' viva anche quando
        # lo stato del player non cambia: premendo "torna indietro" lo stato
        # non cambia, ma la striscia deve tornare.
        self._a_schermo_intero_attivo = False
        self._motore.stato.connect(self._mini_stato)
        self._motore.mosso.connect(self._mini_mosso)
        self._motore.vuoto.connect(self._nascondi_mini)
        self._motore.problema.connect(self._mostra_messaggio)

    def _mini_stato(self, suona: bool, c_e_video: bool) -> None:
        """Cambia la faccia del play e mostra o nascondi la striscia."""
        # `cambia_simbolo`, NON `setIcon`.  `_PulsanteIcona` non e' una
        # `QPushButton`: e' un `QWidget` che si disegna da solo in
        # `paintEvent`, quindi `setIcon` non esiste e si ottiene:
        #
        #     AttributeError: '_PulsanteIcona' object has no attribute 'setIcon'
        #
        # E il metore giusto c'era gia' da prima, perche' la stessa classe e'
        # quella che disegna i pulsanti della fascia e della rail, e quelli
        # cambiano glifo con `cambia_simbolo`.  Non serve un metodo nuovo: e'
        # che si e' scritto `setIcon` per abitudine invece di guardare la
        # classe.
        self.mini_play.cambia_simbolo("pause.fill" if suona else "play.fill")
        # LA STRISCIA IN FONDO
        # -------------------
        # La striscia e' il lettore di quando **non** c'e' il lettore grande:
        # l'utente e' in un'altra sezione, o ha premuto la freccia giu', e il
        # brano continua.  Senza la striscia un brano continuerebbe a
        # suonare senza comando, e un video andrebbe avanti senza che si
        # possa toccare.
        #
        # Con il lettore grande aperto e' invece un **secondo** lettore per
        # lo stesso media: due play, due barre, e quello che si vede in
        # basso e' un pezzo di finestra sopra il contenuto che si voleva
        # guardare.  Per questo la regola non distingue l'audio dal video:
        # distingue **dove si guarda**.
        # TRE COSE NASCONDONO LA STRISCIA, E SONO TRE FATTI
        # -------------------------------------------------
        #   niente che suoni     non c'e' da fermare niente
        #   lettore grande       l'utente sta guardando il video nel suo
        #                       riquadro, con i suoi comandi: la striscia
        #                       sarebbe un secondo lettore per lo stesso video
        #   schermo intero vero tutto lo schermo e' del video, e sotto una
        #                       striscia col titolo c'e' un pezzo di finestra
        #                       sopra il contenuto che si voleva vedere
        #
        # Il lettore grande e' quello dentro l'app, quello che si vede
        # accanto alla lista dei media.  Non e' quello a tutto schermo: e'
        # `_a_schermo_intero_attivo`, e va contato da parte perche' quando
        # il video torna dentro l'app dal tutto schermo il lettore grande
        # riappare e va contato di nuovo.
        #
        # NIENT'ALTRO NASCONDE LA STRISCIA
        # ---------------------------------
        # Non c'e' piu' un interruttore che l'utente deve ricordare di
        # aver messo a posto: la striscia segue quello che si vede.  Il
        # lettore grande si abbassa quando l'utente preme la freccia giu' e
        # quando cambia sezione, quindi nei due modi in cui si esce dal
        # lettore grande la striscia c'e' gia', senza che nessuno debba
        # premere niente.
        if (not self._motore.sorgente()
                or self._a_schermo_intero_attivo
                or self._lettore_grande_visibile):
            self.mini.setVisible(False)
            return
        self.mini_titolo.setText(self._motore.titolo())
        self.mostra_anteprima_mini()
        self.mini.setVisible(True)

    def _mini_mosso(self, posizione: int, durata: int) -> None:
        self.mini_slider.setRange(0, durata // 1000)
        self.mini_slider.blockSignals(True)
        self.mini_slider.setValue(posizione // 1000)
        self.mini_slider.blockSignals(False)
        minuti = posizione // 60000
        secondi = posizione // 1000 % 60
        if durata > 0:
            self.mini_stato.setText(
                f"{minuti}:{secondi:02d} / {durata // 60000}:"
                f"{durata // 1000 % 60:02d}")
        else:
            self.mini_stato.setText(f"{minuti}:{secondi:02d}")

    def _a_schermo_intero(self, aperto: bool) -> None:
        """Il video e' andato (o e' tornato) a tutto schermo.

        La striscia in fondo sparisce comunque, anche se per un audio non ha
        senso: se il video prende tutto lo schermo, sotto non ci sta niente.
        Serve perche' `_mini_stato` decide sul tipo di file, e un video puo'
        essere gia' a schermo intero quando lo stato cambia.
        """
        self._a_schermo_intero_attivo = aperto
        self._mini_stato(self._motore.player.playbackState() == 1,
                         self._motore.e_video())

    def _lettore_grande_cambiato(self, visibile: bool) -> None:
        """Il lettore grande dentro la sezione Media e' comparso o sparito.

        E' l'altra metta' della regola di `_mini_stato`: il lettore grande e'
        aperto, la striscia si spegne; il lettore grande e' sparito, la
        striscia torna **se c'e' ancora qualcosa che suoni**.

        Si chiama anche quando non suona niente, e in quel caso `_mini_stato`
        nasconde e basta: il segnale non decide, dice com'e' andata.

        Non tocca niente del motore e niente degli schermi esterni: qui si
        guarda solo se la striscia in fondo si vede.  Il video che gira su
        un secondo monitor non e' un motivo per muovere nientiqui, e non
        viene toccato niente in questa parte.
        """
        if bool(visibile) == self._lettore_grande_visibile:
            return
        self._lettore_grande_visibile = bool(visibile)
        try:
            self._mini_stato(*self._stato_del_motore())
        except (AttributeError, RuntimeError):
            # La finestra puo' essere gia' stata smontata quando arriva
            # l'ultimo segnale: non vale la pena far cadere la finestra
            # per una striscia che comunque non si piuo' vedere.
            pass

    def _mini_commuta(self) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer

        if (self._motore.player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState):
            self._motore.sospendi()
        else:
            self._motore.continua()

    def _mini_volume(self, valore: int) -> None:
        self._motore.volume(valore / 100.0)

    # ------------------------------------------------------------------
    # DAL LETTORE GRANDE ALLA STRISCIA, E DI NUOVO
    # ------------------------------------------------------------------

    def _mini_ripiccola(self) -> None:
        """La freccia gi' del lettore grande: si torna alla striscia piccola.

        IL LETTORE GRANDE SI NASCONDE
        -----------------------------
        Non basta accendere la striscia: se il lettore grande resta aperto
        sotto, l'utente vede **due** lettori per lo stesso brano, e quello in
        fondo e' una seconda barra di comandi con lo stesso play.  Premere
        play su uno e play sull'altro e' il modo piu' rapido per metterli fuori
        sincrono.

        Quindi il lettore grande si chiude davvero, e il brano continua a
        suonare: `_nascondi_lettore_grande` chiude solo l'interfaccia, non il
        motore.

        E SI TORNA DOVE SI ERA PARTITI
        --------------------------------
        La striscia serve per una cosa sola: poter girare per l'app.  Se dopo
        averla premuta l'utente restasse sulla sezione Media, la striscia si
        spegnerebbe subito — perche' li' il lettore grande e' il suo posto —
        e la freccia gi' sembrerebbe rotta.

        Quindi si torna alla sezione da cui il media era partito, che e' gia'
        segnata da `_vai_a_multimedia`.  Se non c'e' nessuna, si va alla Home:
        e' la sezione in cui si parte e in cui si torna, e non richiede
        indovinare.
        """
        # IL LETTORE GRANDE SI ABBASSA, E QUELLO FA COMPARIRE LA STRISCIA
        # -------------------------------------------------------------
        # Il gesto e' `_attiva_il_mini_player`, non un interruttore da
        # accendere: e' la stessa cosa che fa il cambio sezione, e quindi
        # non c'e' piu' un posto dove la striscia si accende «a mano» e un
        # altro dove si accende da sola — con la parte difficile in un posto
        # e la regola in un altro.
        self._attiva_il_mini_player()
        if self._lettore_e_qui():
            return          # il lettore era sopra questa schermata: si resta dove si e'
        # Se il media e' partito da una notizia, si torna li' e non alla
        # Home: la promessa della X e' la stessa anche per la freccia giu'.
        if self._torna_alla_schermata(self._ritorno_schermata):
            return
        if self._ritorno and self._ritorno in self.sezioni:
            self._seleziona_nome(self._ritorno)
        else:
            self._seleziona_nome("Home")

    # ------------------------------------------------------------------
    # LA STESSA COSA DELLA FRECCIA GIU', DOVE LA SI RICHIEDE
    # ------------------------------------------------------------------

    def _attiva_il_mini_player(self) -> None:
        """«Porta il lettore in striscia piccola»: il gesto della freccia giu'.

        IL GESTE, SENZA LA DESTINAZIONE
        #-----------------------------
        La freccia giu' e' due cose insieme: mette in striscia il media che
        sta suonando, e poi porta l'utente nella sezione da cui quel media
        era partito.  Qui c'e' la **prima** parte, e non c'e' la seconda:
        chi chiama questa funzione ha gia' deciso dove andare — il cambio
        sezione va dove l'utente ha premuto, non dove il media era partito.

        E' perche' le due meta' sono in due funzioni: quando erano una sola
        si chiamavano a vicenda e l'ultima delle due a entrare vinceva, e
        il cambio sezione finiva nella sezione sbagliata.

        Non c'e' nessuna condizione dentro: se non sta suonando niente,
        abbassare il lettore e ridipingere la striscia non fanno danno, ma
        non si fa neppure — la domanda «c'e' qualcosa da mettere nella
        striscia?» la fa `_mini_stato`, che e' l'unico posto dove la
        visibilita' si decide.
        """
        self._nascondi_lettore_grande()
        self._mini_stato(*self._stato_del_motore())

    def _sta_suonando_qualcosa(self) -> bool:
        """C'e' un media avviato, o un lettore grande aperto, o un video a
        tutto schermo?

        Sono tre domande e una sola: **l'utente ha qualcosa che continua e
        che non vede piu' nella schermata in cui sta andando**.  La terza
        conta anche quando il motore non ha niente: la finestra a tutto
        schermo e' aperta fino a quando l'utente non la chiude, e in quel
        momento non si vede piu' niente della finestra sotto.
        """
        try:
            if self._motore.sorgente():
                return True
        except (AttributeError, RuntimeError):
            pass
        return bool(self._lettore_grande_visibile
                    or self._a_schermo_intero_attivo)

    def _mini_espandi(self) -> None:
        """La freccia su' della striscia: si torna al lettore grande.

        Va nella sezione Media e basta.  Il lettore grande si riapre da solo
        appena la sezione riceve il media: `MediaView` riprende la traccia
        corrente, quindi non c'e' niente da dire «riaprititi» — e dirlo
        sarebbe anche sbagliato, perche' si farebbe partire una seconda volta
        quello che sta gia' suonando.

        LA PROMESSA DELLA X, ANCHE QUI
        ------------------------------
        Qui prima c'era `self._ritorno = None`, e la ragione era che, salendo
        nel lettore grande, non aveva piu' senso tornare indietro.  Adesso la
        regola e' un'altra, ed e' quella che vale dappertutto: **la X riporta
        dove il media e' partito**.

        Quindi salire nel lettore grande non cancella la promessa, la lascia
        stare: se il video era partito dalla Home, chiudendolo dalla X si
        torna alla Home anche se nel frattempo si era passati dal mini
        player.  E se invece il video e' partito dentro la sezione Media,
        `_ritorno` era gia' `None` e questa riga non cambierebbe niente.

        Per il resto la freccia su' non tocca il segnaposto: ne' la
        provenienza, perche' qui non parte nessun media e quindi non c'e'
        niente di cui ricordare da dove arriva.
        """
        # `ricorda=True` solo quando si torna da una notizia: senza, la
        # cronologia verrebbe svuotata e la notizia distrutta, e la X non
        # avrebbe piu' un posto dove tornare.  Per i media normali resta il
        # comportamento di sempre.
        sezione = self.sezioni.get("Biblioteca Digitale")
        if self._lettore_e_qui():
            # Il lettore e' sopra la schermata in cui si e': basta rialzarlo.
            sezione._lettore.alza()
        else:
            self._seleziona_nome("Biblioteca Digitale",
                                 ricorda=bool(self._ritorno_schermata))
            if sezione is not None and hasattr(sezione, "riapre_il_lettore"):
                sezione.riapre_il_lettore()
        # Si ridipinge **dopo**, non prima: se il lettore grande e' salito,
        # il segnale ha gia' nascosto la striscia; se non e' salito — non
        # suona piu' niente, e `riapre_il_lettore` non fa niente — questa
        # chiamata la nasconde perche' non c'e' niente da metterci dentro.
        # Nasconderla a mano, prima di sapere se il lettore e' salito,
        # lascerebbe una striscia accesa o spenta per meta' caso.
        self._mini_stato(*self._stato_del_motore())

    def _stato_del_motore(self) -> tuple:
        """`(suona, c_e_video)` come li chiama il segnale `stato`.

        Serve perche' `_mini_stato` e' costruito per il segnale, che porta due
        valori, e chiamarlo a mano con due valori inventati sarebbe un modo
        per sbagliare.  Qui si legge il motore, che e' la fonte vera.
        """
        return (bool(self._motore.sta_suonando()), bool(self._motore.e_video()))

    def _nascondi_lettore_grande(self) -> None:
        """Chiude il lettore grande senza fermare il brano.

        Non chiama `_motore.ferma()`: e' il punto di tutta la freccia gi'.  Il
        brano continua, e quello che sparisce e' solo la sua cornice.  Chiama
        `LettoreView.abbassa` e non `chiudi` per la stessa ragione: `chiudi`
        chiama `motore.ferma()`, e la freccia gi' deve fare esattamente il
        contrario.
        """
        sezione = self.sezioni.get("Biblioteca Digitale")
        if sezione is None:
            return
        lettore = getattr(sezione, "_lettore", None)
        if lettore is not None and hasattr(lettore, "abbassa"):
            lettore.abbassa()

    def mostra_anteprima_mini(self) -> None:
        """La copertina della canzone (o l'anteprima del video) nella striscia.

        Va presa dalla stessa miniatura che usa la lista dei media, cosi' che la
        copertina che si vede in fondo e quella della riga da cui si e' partiti
        siano **la stessa immagine**.  Con due ricerche diverse, la copertina
        della striscia arriva prima o dopo e una volta resta quella di un altro
        brano — ed e' il caso peggiore, perche' un'immagine sbagliata accanto
        a un titolo giusto non si nota subito.

        QUI PRIMA NON FUNZIONAVA CON NESSUNA VOCE
        -----------------------------------------
        Due difetti, e insieme facevano sparire la copertina sempre:

        1. si chiedeva `pubSymbol`, che il mediator non scrive: tutte le
           categorie di Video e Audio finivano li' con «non c'e' nessuna
           sigla» e la striscia restava pulita;

        2. quello che tornava era un **indirizzo web**, e veniva controllato
           con `Path(indirizzo).is_file()`: con `https://...` la risposta e'
           sempre falsa.  Quindi anche per le voci che avevano la sigla il
           controllo diceva «non c'e'» e la copertina non finiva li'.

        Ora la domanda la fa `Copertine.locandina_del_media`, che e' la stessa
        che fanno la griglia e il player grande: un posto solo, e la striscia
        mostra quello che mostra la card da cui si e' partiti.
        """
        voce = self._motore.voce()
        if not isinstance(voce, dict) or not voce:
            self.mini_anteprima.clear()
            return

        def lavoro() -> bytes | None:
            from Utility import Copertine
            # Solo la cache: la striscia si ridisegna subito e non puo'
            # aspettare la rete.  Se l'immagine non e' ancora scesa arriva
            # con `mostra_anteprima_mini` richiamata, e nel frattempo c'e'
            # il glifo, che e' meglio di un riquadro nero.
            return Copertine.locandina_del_media(voce, solo_cache=True)

        try:
            dati = lavoro()
        except Exception:  # noqa: BLE001 - una copertina mancante non e' un guasto
            dati = None
        if not dati:
            self.mini_anteprima.clear()
            # LA CACHE NON C'E': LA SI VA A PRENDERE
            # -------------------------------------
            # Prima qui si finiva, e la striscia restava senza immagine per
            # tutta la canzone: nessuno prometteva che `lavoro` fosse stato
            # chiamato prima con la rete, e se la card non l'aveva ancora
            # messa in cache (una voce partita dagli Scaricati, o dalla
            # striscia in fondo senza passare per la griglia) il mini player
            # non la vedeva **mai** — mentre sulla card la copertina c'e'.
            #
            # La rete si chiede in sottofondo e si mette solo se, quando
            # arriva, sta ancora suonando la stessa cosa: un'immagine di un
            # brano vecchio accanto al titolo di uno nuovo e' il peggior
            # guasto che ci sia, perche' un'immagine sbagliata accanto a un
            # titolo giusto non si nota subito.
            self._scarica_l_anteprima_mini(voce)
            return

        from PyQt6.QtGui import QPixmap
        from Utility.Copertine import pixmap_da_dati

        immagine = pixmap_da_dati(dati)
        if immagine is None or immagine.isNull():
            self.mini_anteprima.clear()
            return
        self.mini_anteprima.setPixmap(immagine)

    def _scarica_l_anteprima_mini(self, voce: dict) -> None:
        """La locandina che manca alla striscia, chiesta in sottofondo.

        E' il seguito di `mostra_anteprima_mini`: quella guarda la cache e,
        se la cache non ha niente, chiama qui.  Senza questo pezzo la
        striscia restava senza immagine per tutta la canzone, perche' niente
        prometteva che l'immagine fosse gia' in cache — e sulle voci partite
        dagli Scaricati o dalla striscia in fondo, che non passano per la
        griglia, non lo era di sicuro.

        DUE CONFRONTI PRIMA DI METTERE QUALSIASI COSA
        ---------------------------------------------
        1. `sip.isdeleted`: la striscia puo' essere stata distrutta — il
           cambio lingua rifarebbe le sezioni — e mettere una pixmap dentro
           un widget morto fa `abort()` senza un solo messaggio;
        2. il **titolo**: il lavoro arriva un secondo dopo, e in un secondo
           l'utente puo' aver passato un altro brano.  Un'immagine di un
           brano vecchio accanto al titolo di uno nuovo e' il guasto peggiore
           che ci sia, perche' un'immagine sbagliata accanto a un titolo
           giusto non si nota subito.

        Il glifo resta fino all'arrivo: e' meglio di un riquadro nero.
        """
        titolo = self._motore.titolo() if hasattr(self._motore, "titolo") else ""

        portato: dict = {"dati": None}

        def lavoro() -> None:
            from Utility import Copertine
            # Tutte le misure, non solo la prima: una puo' rispondere 403
            # mentre un'altra della stessa immagine c'e', e allora la
            # striscia resterebbe senza immagine per un brano che il
            # programma sapeva quale fosse.
            #
            # I byte finiscono in `portato` e non nel valore di ritorno: il
            # `completion` di `background` viene chiamato **senza argomenti**,
            # quindi un `def arrivati(dati)` non riceve mai niente e va a
            # finire in un `TypeError` in stderr che nessuno legge.
            dati = Copertine.locandina_del_media(voce)
            if dati:
                portato["dati"] = dati

        def arrivati() -> None:
            from PyQt6 import sip
            from PyQt6.QtGui import QPixmap
            from Utility.Copertine import pixmap_da_dati
            dati = portato["dati"]
            if sip.isdeleted(self.mini_anteprima):
                return
            if not dati:
                return
            if hasattr(self._motore, "titolo") and self._motore.titolo() != titolo:
                return
            if not self.mini.isVisible():
                return
            immagine = pixmap_da_dati(dati)
            if immagine is None or immagine.isNull():
                return
            self.mini_anteprima.setPixmap(immagine)

        try:
            from Utility.Extensions.Ext_DispatchQueue import background
            background(lavoro, completion=arrivati)
        except Exception:  # noqa: BLE001 - una copertina mancante non e' un guasto
            pass

    def _mini_read(self) -> None:
        """Il tasto «Leggi»: qui non c'e' niente da leggere ad alta voce.

        IL PROGRAMMA NON HA LA LETTURA AD ALTA VOCE
        ---------------------------------------------
        Nella finestra grande c'e' la stessa cuffia, ma e' un'icona e non un
        tasto: e' un'etichetta che dice «questo e' audio», non un comando.
        Nella striscia piccola era un tasto — e un tasto che non fa niente e'
        la cosa peggiore che ci sia, perche' sembra rotto invece che non
        costruito.

        Quindi qui si **dice** che non c'e'.  Un avviso in fondo e' una riga e
        sparisce; un tasto premuto e che non succede niente resta li' e
        l'utente lo preme ancora.

        Se un giorno la lettura ad alta voce ci sara', e' qui che va chiamata,
        e non va rimesso un tasto che sembra funzionare: il programma non ha
        nessun motore di sintesi, e collegarlo a un tasto senza motore e' il
        difetto che questo avviso sostituisce.
        """
        self.mostra_toast("La lettura ad alta voce non è ancora disponibile.",
                          "info", 4000)

    def _mini_ferma(self) -> None:
        """Ferma tutto e nascondi la striscia, poi torna dove si era partiti.

        E' il comando che l'utente preme quando non vuole piu' sentire.  Se
        fermasse e lasciasse la striscia, l'utente dovrebbe premere due
        volte per liberarsi dello spazio: una per il suono e una per la
        striscia, e la seconda sembrerebbe non funzionare perche' non
        cambia niente.

        DEVE ANCHE TORNARE ALLA SEZIONE DI PROVENIENZA
        ----------------------------------------------
        Come per il player grande: chi ha avviato il media da un'altra sezione
        deve ritrovarsi li' quando chiude (o finisce) il media.
        """
        self._motore.ferma()
        # Qui basta `motore.ferma()`: il motore dice «non c'e' piu' niente»
        # e la striscia si nasconde da sola.  Non c'e' nessun interruttore
        # da spegnere — e non deve esserci: il prossimo media che parte
        # deve avere la sua striscia come tutti gli altri, perche' l'utente
        # non sta guardando nessun lettore grande in quel momento.
        self._nascondi_mini()
        self._torna_da_dove_sono_partito()

    def _scorciatoie(self) -> None:
        """I tasti che fanno le stesse cose dei pulsanti."""
        for tasti, funzione in (("Ctrl+Left", self.go_back),
                                ("Ctrl+Right", self.go_forward),
                                ("F5", self._aggiorna_schermata)):
            QShortcut(QKeySequence(tasti), self, activated=funzione)

    # ------------------------------------------------------------------
    # IL TEMA
    # ------------------------------------------------------------------

    def _applica_tema(self) -> None:
        """Riapplica il foglio di stile del tema.

        Si riapplica tutto invece di cambiare i colori ai singoli widget:
        cosi' una schermata nuova e' gia' nel tema giusto, e non c'e' nessun
        pezzo che puo' restare del colore vecchio.

        Non c'e' piu' nessuna icona del tema da aggiornare.  Prima la fascia
        aveva la luna e il sole, e qui si cambiava il loro glifo secondo il
        tema in uso.  Tolti dalla fascia, non c'e' piu' niente da
        aggiornare: il tema si cambia dalla casella nelle Impostazioni, e
        li' la casella mostra gia' la scelta attuale.

        IL TEMA VIENE COMUNICATO ANCHE A `tema`
        ---------------------------------------
        Il foglio di stile sa da solo quale dei due temi sta a schermo, ma
        i pezzi che disegnano senza foglio di stile — un pixmap, il colore di
        un'icona — no.  Qui si dice a `tema` quale dei due e', ed e' l'unico
        posto in cui si dice: la stessa riga coprirebbe anche l'avvio e il
        cambio tema, che passano entrambi di qui.

        Sta **prima** di `setStyleSheet` perche' il foglio di stile non crea
        widget: puo' solo colorare quelli che gia' ci sono.  Quindi nessuna
        delle due righe puo' stare nell'altra, e questa va prima perche' se il
        foglio sbaglia un colore la cella non puo' accorgersene.
        """
        tema.imposta_tema_attivo(self._chiaro)
        from PyQt6.QtWidgets import QApplication
        applicazione = QApplication.instance()
        if applicazione is not None:
            applicazione.setStyleSheet(tema.foglio_stile(self._chiaro))
        Plugin.tema_cambiato("timer", self.sezioni.get("Timer"), self._chiaro)

    def _tema_richiesto(self, chiaro: bool) -> None:
        """Le Impostazioni hanno chiesto di cambiare il tema.

        Si rispetta la richiesta anche se il tema e' gia' quello: cosi' la
        schermata che ha fatto la richiesta e' sempre quella che si vede,
        e non dipende da che tema c'era quando e' stata costruita.

        IL CAPITOLO SI RICARICA
        -----------------------
        Il capitolo e' una pagina web, e i suoi colori sono nel foglio di
        stile **dentro** la pagina: non cambiano da soli quando cambia il
        tema della finestra.  Un capitolo aperto mentre si cambia tema
        resterebbe col testo del tema vecchio — nero su scuro, il difetto
        che e' gia' stato corretto altrove.
        """
        self._chiaro = chiaro
        self._applica_tema()
        try:
            corrente = self.pila.currentWidget()
        except (AttributeError, RuntimeError):
            return
        ricarica = getattr(corrente, "ricarica", None)
        if callable(ricarica):
            ricarica()
        tema.salva_tema(chiaro)

    # ------------------------------------------------------------------
    # LA NAVIGAZIONE
    # ------------------------------------------------------------------

    def navigate(self, schermata) -> None:
        """Apre una schermata sopra quella di adesso.

        Ogni schermata chiama questo invece di aggiungere qualcosa a uno
        stack proprio: cosi' il pulsante indietro funziona sempre e non si
        finisce con due navigazioni diverse che non si parlano.
        """
        self.pila.addWidget(schermata)
        self._schermate.append(schermata)
        self.pila.setCurrentWidget(schermata)
        if hasattr(schermata, "goBack"):
            schermata.goBack.connect(self.go_back)
        # Un segnalibro scelto o una sottolineatura premuta devono portare al
        # punto del testo, e non solo nel capitolo giusto: lo schermo che li
        # mostra manda qui il segno, e qui si apre l'articolo con l'ancora.
        if hasattr(schermata, "posizioneScelta"):
            schermata.posizioneScelta.connect(self._apri_posizione)
        # Un segno aggiunto o tolto cambia l'elenco delle Ricerche.  Si
        # rilegge subito, anche se in quel momento la sezione non si vede:
        # quando l'utente ci torna, la trova gia' aggiornata.
        if hasattr(schermata, "segniCambiati"):
            schermata.segniCambiati.connect(self._aggiorna_ricerche)
        if hasattr(schermata, "avviso"):
            schermata.avviso.connect(self._avviso_schermata)
        if hasattr(schermata, "pacchettoScaricato"):
            schermata.pacchettoScaricato.connect(self._scaricata_qualcosa)
        if hasattr(schermata, "riferimentoDaAprire"):
            schermata.riferimentoDaAprire.connect(self._apri_riferimento_completo)
        if hasattr(schermata, "videoDaProporre"):
            schermata.videoDaProporre.connect(self._proponi_video)
        if hasattr(schermata, "contenutiDaAprire"):
            schermata.contenutiDaAprire.connect(self._apri_contenuti)
        if hasattr(schermata, "mediaRichiesto"):
            schermata.mediaRichiesto.connect(self._contenuto_apri)
        if hasattr(schermata, "scaricaRichiesta"):
            schermata.scaricaRichiesta.connect(self._contenuto_scarica)
        self._schermo_corrente = schermata
        self.nome.setText("")
        # La schermata che si sta aprendo ha la sua barra, o non ce l'ha.  Si
        # chiede a lei e non si deduce dal nome: una schermata che non ha
        # `toolbar` semplicemente non prende niente e la barra sparisce, e una
        # che ce l'ha la prende senza che qui se ne sappia il nome.
        self._metti_la_barra(schermata)
        # La schermata nuova nasce alla misura del testo scelta, e la fascia
        # sa se questa schermata e' una notizia con audio: senza queste due
        # righe la misura resterebbe quella di quando l'app e' partita, e le
        # cuffie non comparirebbero mai sulla notizia.
        self._applica_dimensione_testo(schermata)
        self._aggiorna_strumenti_per_schermata()
        self._aggiorna_frecce()

    def _metti_la_barra(self, schermata) -> None:
        """Mette in alto la barra della schermata, se ne ha una.

        CHIEDE, NON DEDUCE
        ------------------
        Il nome del metodo `toolbar` dice «questa schermata vuole una barra» e
        nient'altro: non dice quale, ne' che cosa c'e' dentro.  Ogni schermata
        costruisce la sua perche' dentro ci sono i suoi bottoni, e qui non si
        saprebbe scriverli senza riscrivere ogni schermata in un posto solo.

        UNA BARRA VECCHIA VA RIMOSSA, NON COPERTA
        -----------------------------------------
        Navigando avanti e indietro le barre si accumulerebbero una sopra
        l'altra nella stessa riga, e la schermata sotto mostrerebbe il nome
        della pubblicazione precedente.  Percio' si svuota la riga ogni volta:
        il widget viene sganciato e distrutto, non nascosto.

        La riga e' senza spaziature e senza margini perche' a sistemare la
        spaziatura di una barra che non conosciamo la fa il suo costruttore:
        qui si aggiunge solo il contenitore.
        """
        # SVUOTA
        while self._riga_barra.count():
            pezzo = self._riga_barra.takeAt(0)
            widget = pezzo.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        costruisci = getattr(schermata, "toolbar", None)
        if costruisci is None:
            self._barra_schermata.setVisible(False)
            return
        try:
            pezzi = costruisci()
        except Exception:  # noqa: BLE001
            # Una barra rotta non deve impedire di vedere la schermata: il
            # contenuto e' la cosa che l'utente ha chiesto, la barra e' un
            # aiuto a orientarsi.  Senza questo `try` una barra che solleva
            # un'eccezione chiuderebbe il programma senza lasciare traccia.
            import traceback
            print(f"Finestra: barra rotta su {schermata.__class__.__name__} ⚠️")
            traceback.print_exc()
            self._barra_schermata.setVisible(False)
            return

        if not pezzi:
            self._barra_schermata.setVisible(False)
            return

        # UNA BARRA O PIU' DI UNA, E NON SI SA PRIMA
        # --------------------------------------------
        # `toolbar()` restituisce una lista in due schermate e la barra
        # **singola** in una terza.  Il motivo e' storico e non lo si tocca: il
        # chiamante non deve accorgersene.
        #
        # Prima qui si faceva `for pezzo in pezzi` e basta, e la schermata che
        # restituiva una `QToolBar` sola faceva crashare il programma:
        # «'QToolBar' object is not iterable».  Non un avviso: la finestra
        # sparisce, e il nome dell'errore non dice nulla di una lista che
        # qualcuno ha cambiato.
        #
        # Si mette dentro una lista quello che non lo e' gia'.  Una `QToolBar`
        # non e' un `Iterable` di widget ma si puo' mettere in un layout come
        # qualsiasi altro widget, quindi la lista non sta a guardare il tipo.
        if not isinstance(pezzi, (list, tuple)):
            pezzi = [pezzi]

        for pezzo in pezzi:
            self._riga_barra.addWidget(pezzo)
        self._riga_barra.addStretch(1)
        self._barra_schermata.setVisible(True)

    def _se_permanente(self, schermata) -> bool:
        """Questa schermata si tiene anche quando l'utente torna indietro?

        DUE POSTI DIVERSI, E PERCHE' SERVE UNA DOMANDA E NON UN `if` A PEZZI
        ---------------------------------------------------------------------
        TORNARE INDIETRO DISTRUGGE
        -----------------------
        `go_back` e `_seleziona_nome` tolgono dalla pila la schermata che si
        sta lasciando e la chiamano `deleteLater()`.  Per una schermata che si
        riapre da capo ogni volta e' la cosa giusta: chi esce dalla sezione non
        la riaperra' e buttarla via non costa niente.

        IL CATALOGO NO
        --------------
        Il catalogo delle pubblicazioni e' l'unica schermata che **si riusa**:
        `_catalogo` lo costruisce una volta e lo tiene, perche' rileggere
        `catalog.db` — 3.745 righe — a ogni categoria premuta si sente come
        un'esitazione dell'app.

        Se `go_back` lo distruggesse, la volta dopo `self.sezioni["Pubblicazioni"]`
        terrebbe un involucro Python il cui oggetto C++ e' gia' stato liberato:
        chiamare un metodo su quello e' leggere memoria scaricata, e il
        programma termina senza dire perche'.  E' la classica morte per
        puntatore pendente, la piu' difficile da vedere perche' il difetto e'
        a tre funzioni di distanza dal posto in cui si preme.

        Per questo la domanda e' una e le risponde `_se_permanente`, e la
        chiamano **entrambi** i posti che tolgono schermate dalla pila: se solo
        uno dei due guardasse, il difetto si vedrebbe solo andando indietro con
        la freccia e non cambiando sezione con la rail — cioe' metà delle volte,
        e mai nella stessa prova.
        """
        if id(schermata) in getattr(self, "_permanenti", ()):
            return True
        # Le sezioni ricreate (lingua, Aggiorna) non passano da
        # `_costruisci_sezioni`: restano permanenti comunque.
        return any(schermata is s for s in self.sezioni.values())

    def _segna_permanente(self, schermata) -> None:
        """Dichiara che questa schermata non va distrutta uscendo.

        Si chiama una volta sola, quando la schermata viene costruita.  Il
        confronto e' per **identita'** e non per nome: due schermate con lo
        stesso nome sono due oggetti diversi, e quella che si tiene deve essere
        esattamente quella che c'e' nella pila.
        """
        permanenti = getattr(self, "_permanenti", None)
        if permanenti is None:
            permanenti = set()
            self._permanenti = permanenti
        permanenti.add(id(schermata))

    def _c_e_qualcosa_da_chiudere(self) -> bool:
        """Questa sezione ha qualcosa di suo da chiudere prima di uscire?

        Oggi l'unica cosa e' «Biblioteca Digitale» con una categoria aperta: la
        freccia torna alle dieci categorie.  E' una domanda e non un `if` sul
        nome della sezione perche' la risposta la sa la sezione — e quando
        comparirà un secondo caso (un video a tutto schermo, una ricerca) si
        aggiunge li', senza che qui si debba ricordare di cambiare.

        Non guarda il nome della sezione ma **chiede**: un controllo sul nome
        qui significa che ogni sezione nuova che ha qualcosa da chiudere
        dimenticata di registrare, e il sintomo e' una freccia spenta che
        dovrebbe essere accesa.
        """
        schermata = self.pila.currentWidget()
        if schermata is None:
            return False
        if getattr(schermata, "torna_alle_categorie", None) is None:
            return False
        # DUE CAMPI, PERCHE' LE CATEGORIE STANNO IN DUE POSTI DIVERSI
        # -------------------------------------------------------
        # `_categoria_aperta` sono le dodici categorie delle pubblicazioni,
        # `_categoria` sono le categorie di Video e Audio.  Guardando solo il
        # primo, dentro una categoria di un media la risposta era "no": la freccia
        # non chiedeva alla sezione e andava a `go_back()`, che con una sola
        # schermata nella pila non toglie niente.  Il sintomo era una freccia che
        # non faceva niente dentro Video e Audio, e funzionava dentro
        # Pubblicazioni — con lo stesso premuto e nella stessa schermata.
        #
        # Si chiede con `getattr` anche perche' non tutte le sezioni hanno i due
        # campi, e il metodo e' dichiarato anche in altri pezzi che non sono
        #sezioni: una domanda che vale per tutte non puo' presumerne uno.
        return bool(getattr(schermata, "_categoria_aperta", "")
                    or getattr(schermata, "_categoria", ""))

    def _torna_indietro(self) -> None:
        """La freccia indietro della fascia: prima dentro la sezione, poi fuori.

        LA SEZIONE CHIEDE PRIMA DI ESSERE LASCIATA
        --------------------------------------------
        Dentro «Biblioteca Digitale», sulla tab delle pubblicazioni, l'utente
        puo' essere dentro una categoria.  La freccia lo riporta alle dieci
        categorie, che sono la schermata di prima: e' esattamente quello che
        aspetta, ed e' dentro la sezione che sta guardando.

        Prima, per tornare alle categorie, c'era un bottone **dentro** la pagina,
        con una freccia sua.  Due frecce indietro a schermo — una nella fascia
        e una dentro il contenuto — dicono due cose diverse e non si sa quale
        premere: quella in fascia sembra portare via dalla sezione, quella
        dentro no.  Il peggio e' che la freccia della fascia era **spenta** in
        quel momento, perche' la pila aveva una schermata sola: il segnale che
        c'era un ritorno possibile era solo quello del bottone nuovo, e le due
        cose non potevano stare insieme.

        Perche' non si fa salire una schermata finta nella pila
        ------------------------------------------------------
        Si potrebbe: mettere le categorie «sotto» le pubblicazioni e accendere
        la freccia.  Ma allora la pila conterrebbe la stessa sezione due volte,
        e `go_back` distruggerebbe la prima — che e' la sezione, non una copia.
        Il contenuto si perderebbe e la sezione ricomincerebbe da capo a ogni
        categoria aperta.

        Qui si chiede prima alla sezione, e solo se non ha niente da fare si
        comporta come prima.  E' la stessa regola che gia' vale per il video a
        tutto schermo: chi ha qualcosa da chiudere, chiude; altrimenti la
        freccia torna nella schermata precedente.
        """
        schermata = self.pila.currentWidget()
        if self._c_e_qualcosa_da_chiudere():
            schermata.torna_alle_categorie()
            self._aggiorna_frecce()
            return
        self.go_back()

    def go_back(self) -> None:
        """Torna alla schermata di sotto, o alla sezione se non c'e' piu'.

        SI TORNA ALL'INDICE SCRITTO, NON A QUELLO CHE SCEGLIE QT
        -------------------------------------------------------
        Prima qui finiva cosi':

            self.pila.removeWidget(corrente)
            corrente.deleteLater()
            precedente = self.pila.currentWidget()      # <- Qt decide

        cioe' si chiedeva a Qt quale schermata avesse scelto di lasciare senza
        corrente dopo aver tolto quella corrente.  La scelta di `QStackedWidget`
        non e' «la precedente»: e' la prima rimasta, e quindi dipende da quante
        schermate ci sono e da quale era l'indice.

        Con il catalogo dentro la sezione e' successo: la pila delle sezioni ha
        sette schermate, il catalogo e' l'ottava, e dopo aver tolto il catalogo
        Qt ha lasciato corrente «Impostazioni» — l'ultima sezione — invece che
        «Biblioteca Digitale».  Il ritorno portava nella sezione sbagliata, e
        senza nessun errore: la freccia faceva qualcosa, solo non quello.

        `_schermate` sa gia' l'indice di sotto: e' stato scritto quando la
        schermata e' stata aperta.  Ci si va esattamente li'.
        """
        if len(self._schermate) <= 1:
            return
        # LA FRECCIA AVANTI: QUI NASCE
        # --------------------------
        # Prima di lasciare questa schermata si scrive dove si sta andando.  E' il
        # posto giusto perche' e' l'unico momento in cui la schermata e' ancora
        # viva e nota: dopo, o e' stata distrutta o non si sa piu' quale era.
        #
        # Senza questa riga la freccia avanti non si accende mai, e il motivo non
        # e' che «non c'e' niente avanti»: e' che nessuno scriveva mai **cosa**.
        corrente = self.pila.currentWidget()
        if corrente is not None:
            self._avanti.append(corrente)
        self._schermate.pop()
        if corrente is not None and not self._se_permanente(corrente):
            self.pila.removeWidget(corrente)
            corrente.deleteLater()
        # Si va **per widget**, non per indice: togliere una schermata dalla
        # pila sposta tutti gli indici dopo di lei, e tornare per indice
        # significava tornare nella schermata successiva a quella giusta.
        sotto = self._schermate[-1]
        if sotto is not None:
            self.pila.setCurrentWidget(sotto)
            self._schermo_corrente = sotto
            # Tornando indietro si torna a una schermata che potrebbe avere la
            # sua barra — per esempio da un capitolo si torna all'elenco dei
            # capitoli, che ha la sua.  Senza questa riga la barra resterebbe
            # quella di dove si sta venendo, e nomerebbe il pezzo sbagliato.
            self._metti_la_barra(self._schermo_corrente)
            self._applica_dimensione_testo(self._schermo_corrente)
            self._aggiorna_strumenti_per_schermata()
        self._aggiorna_frecce()

    def eventFilter(self, oggetto, evento) -> bool:
        """I tasti laterali del mouse fanno indietro e avanti, ovunque nella finestra.

        Si ascolta l'intera applicazione perche' la pagina web (Chromium) si
        prende il mouse e non lo passa alla finestra.  Se il mouse non ha i
        tasti laterali questi eventi non arrivano mai.
        """
        tipo = evento.type()
        if tipo in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            tasto = evento.button()
            if tasto in (Qt.MouseButton.BackButton, Qt.MouseButton.ForwardButton):
                if self.isActiveWindow():
                    if tipo == QEvent.Type.MouseButtonPress:
                        if tasto == Qt.MouseButton.BackButton:
                            # Prima si chiude l'immagine o il documento aperto
                            # sopra la schermata; solo dopo si torna indietro.
                            if self._chiudi_il_visore_aperto():
                                return True
                            if self._indietro.isEnabled():
                                self._torna_indietro()
                        elif self._avanti_btn.isEnabled():
                            self.go_forward()
                    return True
        return super().eventFilter(oggetto, evento)

    def _chiudi_il_visore_aperto(self) -> bool:
        """Chiude l'immagine o il documento aperto sopra la schermata, se c'e'."""
        from SubViews.VisoreDocumento import VisoreDocumento
        for visore in self.findChildren(VisoreDocumento):
            if visore.isVisible():
                visore.chiudi()
                return True
        return False

    def go_forward(self) -> None:
        """Avanti: verso una schermata che si e' appena lasciata.

        IL DIFETTO CHE C'ERA, E DOVE STAVA
        -----------------------------------
        Qui sotto c'era `self._avanti_pendenti`, e quel nome compariva in tre
        posti: letto qui, azzerato qui, e letto in `_aggiorna_frecce` per decidere
        se accendere la freccia.  **Non compariva in nessun altro posto.**

        E il posto in cui avrebbe dovuto essere scritto — cioe' `go_back`, quando
        si lascia una schermata — non lo faceva.  Quindi la variabile era sempre
        `None`: la freccia avanti non si accendeva mai e, se accesa a forza,
        `go_forward` usciva alla prima riga.  Non era una freccia lenta, era una
        freccia **spenta e ferma**, e il sintomo e' esattamente «non funziona».

        Adesso e' una **lista** (`_avanti`), non una variabile: si puo' tornare
        indietro due volte e poi andare avanti due volte, come in un browser.
        Con una variabile sola si poteva tornare indietro di una schermata sola,
        e ogni `go_forward` la cancellava: il secondo «avanti» non faceva niente
        e non si capiva perche'.
        """
        if not self._avanti:
            return
        schermata = self._avanti.pop()
        # La schermata puo' gia' essere nella pila — e' il caso normale, perche'
        # le sezioni non vengono mai tolte.  `addWidget` su un widget che c'e'
        # gia' lo **sposta in fondo** alla pila, e allora l'indietro successivo
        # non tornerebbe dove deve: per questo si controlla prima, e si rimette
        # dentro solo se non c'era piu'.
        if self.pila.indexOf(schermata) < 0:
            self.pila.addWidget(schermata)
        self._schermate.append(schermata)
        self.pila.setCurrentWidget(schermata)
        self._schermo_corrente = schermata
        # Avanti riapre una schermata che era stata lasciata e che ha ancora la
        # sua barra: senza rimetterla, la barra mostrerebbe il nome di dove si
        # era andati invece che di dove si e' tornati.
        self._metti_la_barra(schermata)
        self._applica_dimensione_testo(schermata)
        self._aggiorna_strumenti_per_schermata()
        self._aggiorna_frecce()

    def _aggiorna_frecce(self) -> None:
        """La freccia indietro si accende solo se c'e' qualcosa da tornare.

        E ADESSI ANCHE SE C'E' UNA CATEGORIA APERTA
        --------------------------------------------
        Dentro «Biblioteca Digitale» la freccia torna alle dieci categorie
        anche quando la pila ha una schermata sola, e quindi `len(self._schermate)
        > 1` e' falso.  Senza questa riga la freccia resterebbe spenta proprio
        mentre c'e' qualcosa da tornare: un tasto spento accanto a una schermata
        dalla quale si puo' tornare indietro e' la cosa piu' falsa che ci sia in
        una fascia.

        Il caso e' domandato alla sezione e non dedotto dal nome: sta in
        `_torna_indietro` la stessa domanda, e i due posti devono dire la stessa
        cosa — se lo chiedono in due modi diversi, una volta accende e una no.
        """
        self._indietro.setEnabled(len(self._schermate) > 1
                                 or self._c_e_qualcosa_da_chiudere())
        self._avanti_btn.setEnabled(bool(self._avanti))

    def set_titolo(self, titolo: str) -> None:
        """Il nome dello schermo, nella fascia viola."""
        self.nome.setText(titolo or "")

    # ------------------------------------------------------------------
    # LE SEZIONI
    # ------------------------------------------------------------------

    def _costruisci_sezioni(self) -> None:
        """Costruisce le sezioni e le infila nello stack.

        LE SETTE SEZIONI SONO PERMANENTI, E SOLO LORO
        ---------------------------------------------
        `_segna_permanente` finora veniva chiamata per il catalogo e per nient'
        altro, e le sette sezioni della rail non erano fra quelle.  Finche' la
        cronologia aveva una schermata sola — cioe' sempre, perche' la rail la
        azzerava — nessuno le incontrava e il difetto non si vedeva.

        Adesso che la rail **spinge** sulla cronologia, tornare indietro dalla
        Bibbia arriva davvero alla Home, e arrivandoci chiama `go_back`, che
        toglie dalla pila la schermata che si sta lasciando.  Bibbia non era
        permanente: veniva distrutta, e `self.sezioni["Bibbia"]` restava
        un involucro Python il cui oggetto C++ era gia' stato liberato.  Il
        click successivo su Bibbia leggeva memoria scaricata e il programma
        moriva senza dire perche'.

        E' la stessa morte per puntatore pendente che `_se_permanente` descrive
        per il catalogo, e per lo stesso motivo: una schermata che si riusa non
        si puo' distruggere uscendo.  Le sette sezioni si riusano sempre — sono
        la struttura dell'applicazione, non una schermata — quindi sono
        permanenti per definizione, e si dichiarano qui una volta sola.
        """
        for titolo, _simbolo in SEZIONI:
            schermata = self._crea_sezione(titolo)
            self._segna_permanente(schermata)
            self.sezioni[titolo] = schermata
            self.pila.addWidget(schermata)
            self._collega(schermata)

    def _crea_sezione(self, titolo: str) -> QWidget:
        """La schermata di una sezione.

        ``BibleView`` e ``PubView`` si costruiscono col loro nome: sono le due
        che scaricano, e costruirle tutte e due al primo avvio fa partire
        due scaricamenti insieme.
        """
        if titolo == "Bibbia":
            schermata = BibleView()
            schermata.documentoScelto.connect(self._apri_documento_bibbia)
            return schermata
        if titolo == "Pubblicazioni":
            schermata = PubView()
            # Una pubblicazione scelta qui mette in moto i media.  Senza
            # questo la sezione Media si apre e resta vuota, e sembra che
            # il server non risponda: ma non e' un errore del server, non
            # gli e' stato mai chiesto niente.
            schermata.pubblicazioneScelta.connect(self._media_per)
            # La barra di avanzamento.  `busyChanged` da solo non bastava:
            # dice solo che si sta scaricando, non quanto manca, e un'attesa
            # senza percentuale su un pacchetto da 122 MB sembra un
            # programma fermo.
            schermata.scaricamentoInizia.connect(self._scaricamento_inizia)
            schermata.scaricamentoAvanza.connect(self._scaricamento_avanza)
            # Un pacchetto e' arrivato sul disco: la sezione Scaricati va
            # riletta subito, senza aspettare che l'utente torni indietro o
            # prema Aggiorna.  Non si ricrea la sezione — si rifa solo la
            # lista, cosi' la posizione nella pila e quello che l'utente
            # stava leggendo restano dove erano.
            schermata.scaricata.connect(self._scaricata_qualcosa)
            # Mettersi un Preferito da questa sezione deve farlo vedere
            # subito nella Home, senza passare dal pulsante Aggiorna.
            schermata.preferitiCambiati.connect(self._aggiorna_preferiti)
            return schermata
        if titolo == "Ricerche":
            schermata = PersonalStudyView()
            # Cliccando una sottolineatura o un segnalibro si torna al punto
            # esatto.  La schermata non sa aprire gli articoli, e non deve
            # saperlo: manda il segno e la finestra fa il resto.
            schermata.posizioneScelta.connect(self._apri_posizione)
            schermata.playlistRichieste.connect(self._apri_playlist)
            return schermata
        if titolo == "Adunanze":
            # `navigate`, `goBack` e `messaggio` li collega `_collega`.
            schermata = AdunanzeView()
            schermata.scaricaRichiesta.connect(self._scarica_una_pubblicazione)
            schermata.pubblicazioneRichiesta.connect(self._apri_pubblicazione_scelta)
            return schermata
        if titolo == "Scaricati":
            # La sezione che guarda il disco.  Una riga premuta apre la
            # pubblicazione, o la scheda dei media se quella pubblicazione ha
            # tracce audio o video: la decisione la prende la riga, che ha
            # guardato dentro il pacchetto, e qui si esegue.
            schermata = DownloadsView()
            schermata.aperta.connect(self._aperta_da_scaricati)
            # Un video sciolto (file sul disco senza pacchetto) si suona nella
            # sezione Multimedia, che e' quella che ha il lettore con i
            # comandi: altro che un motore usa-e-getta che nessuno ascolta.
            schermata.mediaAperto.connect(self._apre_un_media_scaricato)
            # Una cancellazione cambia quello che c'e' sul disco, e quindi
            # anche quello che le altre sezioni possono mostrare: la Home non
            # si tocca, ma la lista dei Preferiti si rilegge.
            schermata.eliminata.connect(self._aggiorna_preferiti)
            # Un pacchetto tolto da qui deve sparire anche da Adunanze, dalla
            # griglia della Biblioteca e dal riquadro del giorno: un solo
            # posto da cui togliere, e tutti gli altri lo sanno.
            def _tolto_dagli_scaricati() -> None:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: (self._pacchetto_tolto(None),
                                              self._scaricata_qualcosa()))
            schermata.eliminata.connect(_tolto_dagli_scaricati)
            return schermata
        if titolo == "Home":
            # Una card dei Preferiti premuta apre la pubblicazione, o la
            # scheda dei media se quella pubblicazione ha tracce audio o video.
            schermata = HomeView()
            schermata.aperta.connect(self._aperta_da_preferito)
            # Una card di un video (le due strisce dei media) porta la sua
            # traccia: se e' gia' sul disco si suona subito, altrimenti si
            # apre la scheda dei media.  Vedi `HomeView.mediaAperta`.
            schermata.mediaAperta.connect(self._apre_una_card_media)
            # Dentro la Home c'e' la sezione Novita': e' lei che chiede al
            # server e che ha il pulsante "Scarica" (o "Aggiorna" per
            # pubblicazioni gia' scaricate con versione nuova).  La finestra
            # la raggiunge attraverso i segnali che la Home rilancia.
            schermata.cambiato.connect(self._aggiornamento_arrivato)
            schermata.scaricaRichiesta.connect(self._scarica_da_home)
            schermata.annullaRichiesta.connect(self._annulla_scarico)
            schermata.aggiorna.connect(self._scarica_da_home)
            # La nuvoletta sulle card: per un video apre il menu' delle
            # risoluzioni, per una pubblicazione scarica il JWPUB.
            schermata.scaricoChiesto.connect(self._scarica_da_card)
            # Il riquadro del giorno premuto: si apre la pagina di oggi.
            if hasattr(schermata, "giornoAperto"):
                schermata.giornoAperto.connect(self._aperta_il_giorno)
            # Una card delle notizie premuta: esce dalla Home come indirizzo e
            # qui diventa una schermata.  La Home non ha la pila, quindi se
            # aprisse la pagina da sola non potrebbe tornare indietro.
            schermata.notiziaAperta.connect(self._aperta_notizia)
            return schermata
        if titolo == "Biblioteca Digitale":
            # La sezione Media parte vuota e dice cosa fare: la
            # pubblicazione la sceglie l'utente nelle Pubblicazioni, e
            # invented qui un elenco di pubblicazioni sarebbe una seconda
            # copia di quello che sta nell'altra sezione, che prima o poi
            # dice una cosa diversa.
            schermata = MediaView()
            schermata.messaggio.connect(self._mostra_messaggio)
            schermata.testoScelto.connect(self._apri_risultato_ricerca)
            # Il lettore si chiude (o il brano finisce): se il media era stato
            # avviato da un'altra sezione, si riporta l'utente li'.  E' la
            # stessa cosa che `_apre_una_card_media` e gli Scaricati
            # preparano con `_vai_a_multimedia`.
            # Il segnale arriva dal thread del player: si rimette nel main.
            from Utility.Extensions.Ext_DispatchQueue import on_main
            schermata.lettoreChiuso.connect(lambda: on_main(self._torna_da_dove_sono_partito))
            schermata.staPerSuonare.connect(
                lambda: self._attesa_video and self._entra_in_multimedia())
            # La freccia gi' del lettore grande: e' un comando della **finestra**,
            # perche' la striscia piccola e il ritorno alla sezione di prima
            # stanno li'.  Media non puo' farlo: non vede la striscia e non sa
            # da dove si e' partiti.
            schermata.ripiccolato.connect(self._mini_ripiccola)
            # Il video a tutto schermo: sotto non ci sta niente, quindi la
            # striscia in fondo sparisce.
            #
            # Sta qui e NON dentro `PubView`, dove l'avevo collegata per
            # sbaglio: il segnale `schermoIntero` ce l'ha il **lettore**, e il
            # lettore sta dentro la sezione Media.  Collegandolo a
            # `PubView` non dava nessun errore — `getattr` con un valore di
            # riserva restituisce `None` e il `if` non entrava — quindi il
            # collegamento semplicemente non esisteva, e la striscia restava
            # in fondo a schermo intero.
            #
            # E' la stessa lezione di `setIcon` che non esisteva: quando una
            # cosa si collega con `getattr` e un `if`, un collegamento sbagliato
            # non si vede.  Meglio `getattr` senza riserva e fallire che
            # passare in silenzio.
            lettore_media = getattr(schermata, "_lettore", None)
            if lettore_media is not None and hasattr(lettore_media, "schermoIntero"):
                lettore_media.schermoIntero.connect(self._a_schermo_intero)
            # IL LETTORE GRANDE E' APERTO O CHIUSO: LA STRISCIA SEGUI
            # ------------------------------------------------------------
            # Il lettore grande sta dentro la sezione Media e la striscia in
            # fondo sta dentro la finestra: sono due pezzi in due posti
            # diversi, e nessuno dei due vede l'altro.  Qui la finestra
            # ascolta il lettore, cosi' la striscia c'e' quando lui non c'e'.
            #
            # Sta dalla parte del segnale `visibilitaCambiata`, **non**
            # sovrascrivendo `imposta_callback_visibilita`: quel callback e'
            # gia' di MediaView e regola il tasto della freccia giu', e
            # sostituirlo sembrerebbe funzionare — `getattr` con una riserva
            # non dà errori, semplicemente non collega niente — mentre
            # lascerebbe il tasto senza comando.  La stessa lezione del
            # collegamento a `PubView` che non esisteva.
            if lettore_media is not None and hasattr(lettore_media,
                                                     "visibilitaCambiata"):
                lettore_media.visibilitaCambiata.connect(
                    self._lettore_grande_cambiato)
            # UN MEDIA E' PARTITO: DA DOVE TORNERE ALLA X
            # ----------------------------------------------------
            # Lo dice il lettore, perche' e' lui che fa partire il media e la
            # finestra da sola non lo saprebbe: il media parte anche quando la
            # lista arriva dalla rete, e magari nel frattempo l'utente ha
            # cambiato sezione.  Vedi `_media_partito`.
            if lettore_media is not None and hasattr(lettore_media, "aperto"):
                lettore_media.aperto.connect(self._media_partito)

            # LE DUE TAB NUOVE DELLA BIBLIOTECA
            # ----------------------------------
            # «Publicazioni» e «Scaricati» dentro la sezione Media.
            #
            # Uno scaricato premuto nella griglia va allo stesso posto di uno
            # premuto nella sezione Scaricati: `_aperta_da_scaricati` e' gia'
            # scritto, fa gia' il caso giusto, e rifarlo qui sarebbe un secondo
            # posto con la stessa regola — il giorno che la regola cambia,
            # cambia uno solo e l'altro apre la cosa sbagliata.  Percio' qui si
            # **collega** e non si riscrive.
            #
            # Una categoria di pubblicazioni premuta va alla sezione
            # Pubblicazioni: dentro questa sezione non c'e' un elenco di libri,
            # e costruirlo qui sarebbe una seconda copia del catalogo che dice
            # una cosa diversa quando il catalogo cambia.
            schermata.scaricatoAperto.connect(self._aperta_da_scaricati)

            # Una categoria premuta **dentro questa sezione**: la sezione
            # cambia tab e si riempie di pubblicazioni.  Non e' una navigazione
            # della finestra e non tocca la pila: si sta guardando dentro
            # «Biblioteca Digitale», e il ritorno alle dieci categorie e' un
            # tasto dentro la sezione (`MediaView.torna_alle_categorie`).
            #
            # Prima questo segnale portava alla sezione «Pubblicazioni» della
            # rail, che e' stata unita a questa e non esiste piu': il collegamento
            # e' stato rifatto sul percorso vero, e non su uno nuovo.
            schermata.apriPubblicazioni.connect(schermata.apri_una_categoria)

            # LA VOCE «PREFERITI» DEL MENU' DELLA CARD
            # ----------------------------------------
            # I Preferiti sono una striscia **nella Home**, quindi la sezione
            # non puo' accenderli da sola: dice «voglio andare alla Home» e
            # ci va questa finestra, che e' l'unica che sa cosa sono le
            # sezioni e come si aprono.
            #
            # Il segnale porta il **nome** e non un indice perche' gli indici
            # delle sezioni cambiano se ne aggiunge una, e un menu' che punta a
            # un indice apre la sezione sbagliata senza dare nessun errore.
            schermata.vaiAllaSezione.connect(self._sceglie_una_sezione)

            # UN MEDIA DA SCARICARE: LA STESSA STRADA DELLA HOME
            # ---------------------------------------------------
            # La nuvoletta di una card di Video o Audio e' la stessa nuvoletta
            # che c'e' nella Home, e deve andare negli stessi posti: si chiede
            # al server la lista delle risoluzioni di quella traccia e si fa
            # scegliere all'utente, che e' l'unica cosa che puo' scegliere
            # perche' la scelta e' sua.
            #
            # Non si riscrive qui: `_scegli_la_risoluzione` e' gia' scritto,
            # provato, e dentro ha anche la regola del prefisso con la traccia a
            # due cifre.  Una seconda copia comincerebbe a divergere dalla prima
            # volta che il nome di un file cambia.
            schermata.mediaScaricata.connect(self._scarica_un_media_da_card)

            # La freccia indietro della fascia va riaccesa quando dentro la
            # sezione si e' entrati in una categoria, e spenta quando se ne
            # esce.  Senza questo la freccia direbbe una cosa diversa da quello
            # che fa, e il sintomo e' una freccia spenta accanto a una
            # schermata dalla quale si torna indietro con un tasto.
            schermata.frecciaCambiata.connect(self._aggiorna_frecce)
            # LA nuvoletta E IL REFRESH DI UNA CARD
            # --------------------------------------
            # Vanno al **download gia' scritto e provato**:
            # `_scarica_una_pubblicazione`, che e' lo stesso metodo che usa la
            # nuvoletta della Home e quello della sezione Scaricati.  Non se ne
            # scrive un secondo: scaricare e' una cosa sola in questa
            # applicazione, e due copie cominciano a divergere dalla prima
            # modifica — tipicamente quando l'indirizzo del pacchetto cambia
            # dal server, che cambia senza avviso.
            #
            # Il dizionario che manda la cella ha la chiave «sigla» e
            # «lingua»: e' il contratto che `_scarica_una_pubblicazione` ha
            # gia' da prima e che non si e' toccato.
            def _scarica_da_card(pub, _vista=schermata):
                from Utility import Lingua
                # Si ricorda **quale** pubblicazione sta scendendo: e' la
                # sola cosa che permette di mettere la barra sulla card
                # giusta fra le trecento che si vedono scorrendo.  Il segnale
                # che arriva piu' avanti dal catalogo porta solo i numeri dei
                # capitoli, e non dice a chi si riferiscono.
                self._pub_in_scarico = pub
                self._scarica_una_pubblicazione({
                    "sigla": getattr(pub, "keySymbol", "") or "",
                    "lingua": Lingua.da_numero(
                        getattr(pub, "mepsLanguageId", 0) or 0),
                })

            schermata.scaricaRichiesta.connect(_scarica_da_card)

            # Un pacchetto tolto dal disco e i Preferiti cambiati rimbalzano
            # sugli stessi metodi di prima, che gia' sanno cosa rileggere:
            # `_scaricata_qualcosa` per tutto cio' che guarda il disco,
            # `_aggiorna_preferiti` per la striscia della Home.
            schermata.pacchettoRimossa.connect(
                self._pacchetto_tolto)
            # Senza questo la sezione Scaricati continuerebbe a mostrare una
            # riga per un pacchetto che non c'e' piu'.
            schermata.pacchettoRimossa.connect(
                lambda _pub: self._scaricata_qualcosa())
            schermata.preferitiCambiati.connect(self._aggiorna_preferiti)
            return schermata
        if titolo == "Impostazioni":
            schermata = SettingsView()
            # Il tema non si cambia dentro la schermata che lo mostra:
            # e' un'informazione che riguarda tutta l'app, quindi la
            # riapplica la finestra, che ne e' la responsabile.
            schermata.temaCambiato.connect(self._tema_richiesto)
            schermata.backupImportato.connect(self._backup_importato)
            # Come il tema, anche lo schermo del video non e' una cosa della
            # schermata che lo mostra: la finestra secondaria e' della
            # finestra.  Quindi qui si dice «e' cambiato» e la finestra
            # ricostruisce lei.
            schermata.schermoCambiato.connect(self._schermo_video_richiesto)
            schermata.pluginCambiati.connect(self._plugin_cambiati)
            return schermata
        return ContentView()

    def _menu_del_timer(self, nome: str, pulsante) -> None:
        """I tre puntini del timer: il menu File, poi Visualizza come sottomenu.

        Le voci sono quelle del timer (non copie), quindi Impostazioni compare
        una volta sola, dentro File.
        """
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QMenu
        finestra = self.sezioni.get("Timer")
        barra = getattr(finestra, "menuBar", None)
        if barra is None:
            return
        menu_file = menu_visualizza = None
        for azione in barra().actions():
            titolo = azione.text().replace("&", "")
            if azione.menu() is not None and titolo == "File":
                menu_file = azione.menu()
            elif azione.menu() is not None and titolo == "Visualizza":
                menu_visualizza = azione.menu()
        if getattr(self, "_menu_timer_unico", None) is None:
            unico = QMenu(self)
            for voce in (menu_file.actions() if menu_file else []):
                if voce.menu() is not None:
                    unico.addMenu(voce.menu())
                else:
                    unico.addAction(voce)
            if menu_visualizza is not None:
                ultima = unico.actions()[-1] if unico.actions() else None
                if ultima is not None and not ultima.isSeparator():
                    unico.addSeparator()
                unico.addMenu(menu_visualizza)
            self._menu_timer_unico = unico
        self._menu_timer_unico.popup(pulsante.mapToGlobal(QPoint(0, pulsante.height())))

    def _plugin_cambiati(self) -> None:
        """Il plugin e' stato acceso o spento nelle impostazioni."""
        visibile = Plugin.visibile("timer")
        self.pulsanti_sezione["Timer"].setVisible(visibile)
        if not visibile and self._sezione_dove_sei() == "Timer":
            self._seleziona_nome("Home")
        self._schermo_timer_richiesto()

    def _crea_timer(self) -> None:
        """Crea la schermata del plugin la prima volta, poi la riusa."""
        if "Timer" in self.sezioni:
            return
        schermata, errore = Plugin.crea_schermata("timer")
        if schermata is None:
            schermata = ContentView()
            print(f"Plugin timer non si apre ⚠️  {errore}")
        else:
            Plugin.modulo("timer").al_chiudere_il_monitor(self._monitor_timer_chiuso)
            # I contenuti del timer si riproducono e si scaricano come quelli
            # della schermata Contenuti: stessa riproduzione, stesso monitor.
            if hasattr(schermata, "mediaRichiesto"):
                schermata.mediaRichiesto.connect(self._contenuto_apri)
            if hasattr(schermata, "scaricaRichiesta"):
                schermata.scaricaRichiesta.connect(self._contenuto_scarica)
            # scaricare la Guida o lo studio della settimana, come in Adunanze
            if hasattr(schermata, "pubblicazioneRichiesta"):
                schermata.pubblicazioneRichiesta.connect(self._scarica_una_pubblicazione)
        self._segna_permanente(schermata)
        self.sezioni["Timer"] = schermata
        self.pila.addWidget(schermata)
        self._collega(schermata)

    def _apri_timer(self) -> None:
        self._crea_timer()
        self._sceglie_una_sezione("Timer")

    def _schermo_timer_richiesto(self) -> None:
        """Nelle impostazioni e' cambiato lo schermo del monitor del timer."""
        nome = Plugin.schermo("timer") if Plugin.visibile("timer") else ""
        if nome:
            self._crea_timer()
        modulo = Plugin.modulo("timer")
        finestra = self.sezioni.get("Timer")
        if modulo is not None and hasattr(finestra, "settings_controller"):
            modulo.applica_schermo(finestra, nome or None)

    def _monitor_timer_chiuso(self) -> None:
        """L'utente ha chiuso il monitor con la X: l'impostazione si spegne."""
        Plugin.imposta_schermo("timer", "")

    def _collega(self, schermata) -> None:
        """Collega una sezione alla finestra, se ha qualcosa da dire."""
        if hasattr(schermata, "navigate"):
            schermata.navigate.connect(self.navigate)
        if hasattr(schermata, "goBack"):
            schermata.goBack.connect(self.go_back)
        if hasattr(schermata, "messaggio"):
            schermata.messaggio.connect(self._mostra_messaggio)
        if hasattr(schermata, "pacchettoScaricato"):
            schermata.pacchettoScaricato.connect(self._scaricata_qualcosa)
        if hasattr(schermata, "busyChanged"):
            schermata.busyChanged.connect(self._mostra_attesa)
        if hasattr(schermata, "linguaCambiata"):
            # Una sezione puo' cambiare la lingua dell'app: e' la Bibbia a
            # farlo, quando la lingua scelta non ha il testo scaricabile e
            # l'utente preme «Passa all'italiano».  La sezione sa che cosa
            # va rifatto (tutte le schermate leggono la lingua), quindi lo
            # dice alla finestra, che e' l'unica che le ha.
            schermata.linguaCambiata.connect(self._ricrea_tutte_sezioni)
        if hasattr(schermata, "catalogoRichiesto"):
            # Le Impostazioni chiedono di aggiornare il catalogo adesso.
            # Il download e' cosa della finestra: sa la barra, sa il riepilogo
            # e sa che cosa rileggere quando il catalogo e' arrivato.
            schermata.catalogoRichiesto.connect(
                lambda: self._controlla_aggiornamenti(forzato=True))

    def _seleziona(self, indice: int) -> None:
        """Una voce della rail e' stata scelta, per indice."""
        # L'indice e' quello di un **pulsante** della rail, quindi si legge in
        # `NELLA_RAIL`.  Con `SEZIONI` le due liste comincierebbero a divergere
        # al primo pulsante tolto, e un indice che punta a una sezione sbagliata
        # non da nessun errore: porta da un'altra parte e sembra funzionare.
        if not 0 <= indice < len(NELLA_RAIL):
            return
        self._sceglie_una_sezione(NELLA_RAIL[indice][0])

    def _sceglie_una_sezione(self, titolo: str) -> None:
        """L'utente ha premuto una voce del **menu laterale**: vai li'.

        PRIMA DI ANDARE DAVANTI: IL MINI PLAYER
        -------------------------------------
        Se c'e' un video avviato, o un lettore grande aperto, o un video a
        tutto schermo, **prima** di cambiare sezione si mette in striscia il
        player: e' lo stesso gesto della freccia giu', fatto dalla stessa
        funzione — `_attiva_il_mini_player`.

        Il motivo e' che l'utente non sta cambiando idea sul video: sta
        andando a guardare un'altra cosa.  Se la striscia non accompagna il
        cambio di sezione, il video continua in una schermata dove non si
        vede e dove non si puo' fermare, e l'unica salita e' tornare
        indietro e cercarlo.  Il pulsante della rail e' la stessa intenzione
        della freccia giu', detta in un altro modo.

        Non e' «se la striscia non c'e', accendila»: e' il gesto intero, e il
        lettore grande si abbassa davvero.  Senza fermare niente, pero':
        `_nascondi_lettore_grande` chiude l'interfaccia e lascia il motore
        acceso.

        Poi, e **solo dopo**, si va nella sezione che l'utente ha premuto.
        Il contrario non funziona: la freccia giu' riporta dove il media era
        partito, e se girasse per prima si arriverebbe li' invece che dove si
        voleva andare — ed e' il difetto per cui il cambio sezione sembrava
        non funzionare.

        Se non c'e' niente che suoni non si tocca niente: la striscia
        accenderebbe e spegnerebbe da sola mentre l'utente sta solo
        spostandosi per l'app.

        PERCHE' UN METODO PER LA RAIL E NON DENTRO `_seleziona_nome`
        -----------------------------------------------------------
        `_seleziona_nome` e' anche il modo con cui il programma porta se stesso
        in una sezione: quando parte un video dalla Home va nei Multimedia
        **per mostrare il video grande**, quando la freccia su' torna al
        lettore, quando il brano finisce si torna dove si era partiti.  Se il
        mini player fosse dentro `_seleziona_nome`, partirebbe anche in quei
        casi — e il video partirebbe gia' ripiccolato.

        Quindi il gesto sta **qui**, dove c'e' la mano dell'utente, e non
        dentro il metodo che naviga: e' l'unico modo per dire «l'ha chiesto
        lui» senza un interruttore.
        """
        if self._sta_suonando_qualcosa():
            self._attiva_il_mini_player()
        # LA PROVENIENZA, QUANDO LA SCEGLIE L'UTENTE
        # --------------------------------------------
        # `_provenienza` e' il posto da cui partira' il prossimo media, e la
        # mette il programma quando porta se stesso nei Media perche' l'utente
        # ha premuto un video.  Se invece e' l'utente a scegliere una sezione
        # dalla rail, quel video non e' piu' quello che aveva premesso: la
        # provenienza si azzera.
        #
        # `_ritorno` invece non si tocca: quello e' la promessa della X, e una
        # promessa non si cancella perche' l'utente e' passato di qui.
        self._attesa_video = False
        self._provenienza = None
        self._articolo_di_partenza = None
        # `ricorda=True`: questo e' il gesto dell'utente, quindi va nella
        # cronologia e la freccia indietro deve poterlo riprendere.
        self._seleziona_nome(titolo, ricorda=True)

    def _seleziona_nome(self, titolo: str, ricorda: bool = False) -> None:
        """Vai nella sezione `titolo`.

        `ricorda` dice **chi** ha deciso di andarci, e cambia il comportamento in
        modo che si vede.

        IL PULSANTE DELLA RAIL SPINGE, IL PROGRAMMA NO
        -------------------------------------------------
        Prima, in ogni caso, la cronologia finiva a una schermata sola
        (`self._schermate = [indice]`) e tutte le schermate di mezzo venivano
        distrutte.  Il programma doveva fare cosi': quando parte un video e poi
        finisce, la X deve riportare dove il video era partito, e una cronologia
        che cresce farebbe tornare alla schermata sbagliata.

        Ma la stessa regola applicata al **gesto** dell'utente vuota la freccia
        indietro: si preme Bibbia dalla Home, la cronologia diventa `[Bibbia]`, e
        la freccia non ha piu' niente su cui tornare.  E' quello che e' stato
        segnalato: dalla casetta, indietro e avanti non facevano niente — non
        perche' fossero lente, ma perche' la cronologia non esisteva piu' nel
        momento in cui le guardava.

        Con `ricorda` la rail **spinge** e il programma continua a ripartire da
        capo.  Il posto che distingue i due e' questo, e non un `if` sparso
        dentro il ciclo: e' l'unico punto in cui la differenza si vede.

        UN TETTO, PERCHE' LE SCHERMATE NON SONO GRATIS
        ------------------------------------------------
        Ogni schermata spinta resta viva, perche' avanti deve poterla rimettere.
        Senza un tetto un utente che passa fra le sezioni per un'ora accumula
        lettori aperti, e la memoria cresce senza che nessuno se ne accorga: il
        sintomo e' che il programma diventa lento dopo un po', e non si collega
        a niente di quello che e' successo.
        """
        schermata = self.sezioni.get(titolo)
        if schermata is None:
            return
        indice = self.pila.indexOf(schermata)
        # Spingere solo se si va davvero **da un'altra parte**: ripremere la
        # sezione in cui siamo gia' non e' una navigazione, e senza questa riga
        # ogni tocco sulla rail attuale accenderebbe l'indietro su se' stessa.
        spingere = ricorda and self._sezione_dove_sei() != titolo

        if spingere:
            self._schermate.append(schermata)
            # Una navigazione nuova rende inutile andare avanti: come in un
            # browser, il ritorno indietro scarta quello che c'era dopo.
            self._avanti.clear()
            self._dimentica_le_troppe()
            self.pila.setCurrentWidget(schermata)
            self._schermo_corrente = schermata
            self.nome.setText("")
            self._metti_la_barra(None)
            self._evidenzia_rail(titolo)
            self._sezione_attiva = titolo
            self._applica_dimensione_testo(schermata)
            self._aggiorna_strumenti_per_schermata()
            self._aggiorna_frecce()
            # Lasciare che Qt ridisegni prima di tornare: senza questo, il cambio
            # di sezione sembrava a scatti perche' il repaint restava in coda
            # mentre il metodo finiva e tornava.
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().processEvents()
            return
        while len(self._schermate) > 1:
            corrente = self.pila.currentWidget()
            # Il catalogo si tiene anche cambiando sezione: e' lo stesso
            # ragione di `go_back`, e per la stessa ragione questa riga e' qui
            # e non solo li'.  Senza, il catalogo verrebbe distrutto uscendo
            # dalla Biblioteca Digitale e `self.sezioni["Pubblicazioni"]`
            # terrebbe un involucro morto — vedi `_se_permanente`.
            #
            # Il controllo sta **prima** del `pop` perche' il ciclo serve a
            # buttare via gli indici delle schermate che sono state distrutte,
            # e la schermata permanente non e' stata distrutta: il suo indice
            # non c'e' piu' niente da tenere.  Dopo il ciclo, comunque,
            # `_schermate` viene riscritta a `[indice]`, quindi qui si pulisce
            # e basta.
            if corrente is not None and self._se_permanente(corrente):
                break
            self._schermate.pop()
            self.pila.removeWidget(corrente)
            corrente.deleteLater()
        self._schermate = [schermata]
        self._avanti.clear()
        self.pila.setCurrentWidget(schermata)
        self._schermo_corrente = schermata
        self.nome.setText("")
        # Le sezioni principali non hanno una barra loro: hanno gia' la fascia
        # e i loro titoli.  Se la barra di una schermata aperta prima restasse
        # in alto qui, il nome della pubblicazione appena lasciata
        # continuerebbe a stare sopra la sezione.
        self._metti_la_barra(None)
        self._evidenzia_rail(titolo)
        self._aggiorna_frecce()
        # La sezione attiva serve a `_vai_a_multimedia`, che da li' ricava
        # dove riportare l'utente.
        #
        # `_ritorno` NON SI TOCCA QUI
        # --------------------------
        # Prima questo blocco lo azzerava a ogni sezione diversa da
        # Multimedia, e sembrava ragionevole: se l'utente sceglie una sezione
        # a mano, il posto da cui tornare non e' piu' quello.
        #
        # Non e' cosi'.  `_ritorno` e' la promessa della X, e la promessa e'
        # «da dove e' partito il media», non «dove stavi due secondi fa».
        # Con l'azzeramento qui, partendo un video dalla Home e tornando poi
        # nei Media a mano, la X non riportava piu' alla Home: e il posto da
        # cui era partito il video era sparito solo perche' l'utente era
        # passato di li'.
        #
        # Quello che si azzera quando l'utente sceglie a mano e'
        # `_provenienza`, in `_sceglie_una_sezione`: quella e' la provenienza
        # di un media che sta ancora per partire, e scegliere una sezione a
        # mano significa che quel video non e' piu' quello che l'utente
        # aveva premesso.
        self._sezione_attiva = titolo
        self._applica_dimensione_testo(schermata)
        self._aggiorna_strumenti_per_schermata()
        # LA STRISCIA VIENE RICHIAMATA A OGNI CAMBIO SEZIONE
        # ---------------------------------------------------
        # Perche' qui e non da nessuna parte: la striscia puo' essere stata
        # nascosta da un evento che non c'entra con l'utente — il motore che
        # segnala «non c'e' niente», una schermata che si ricostruisce, un
        # segnale che passa di qui senza volerlo — e in tutti quei casi
        # l'utente che l'ha aperta con la freccia giu' si ritrova senza
        # niente in fondo, senza aver premuto niente per perderla.
        #
        # Qui si rimette tutto com'era e si lascia che sia `_mini_stato` a
        # decidere: se l'utente l'ha aperta e c'e' qualcosa che suona, torna;
        # se non l'ha aperta, o non suona niente, resta nascosta.  Il cambio
        # di sezione non decide niente, **rimette** quello che era.
        try:
            self._mini_stato(*self._stato_del_motore())
        except (AttributeError, RuntimeError):
            pass
        # Lasciare che Qt ridisegni prima di tornare: senza questo, il cambio
        # di sezione sembrava a scatti perche' il repaint restava in coda
        # mentre il metodo finiva.
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().processEvents()

    def _dimensione_testo_salvata(self) -> int:
        """La dimensione del testo scritta nelle impostazioni, gia' limitata.

        Il valore torna anche dentro `tema`, cosi' le schermate che nascono
        lontano dalla finestra — un capitolo, un pannello — partono gia' alla
        misura scelta e non a quella di prima.
        """
        return tema.carica_dimensione_testo()

    def _salva_dimensione_testo(self) -> None:
        """Scrive la scelta nel file, senza interrompere la lettura."""
        try:
            tema.salva_impostazione(DIMENSIONE_TESTO_CHIAVE,
                                    int(self._dimensione_testo))
        except (OSError, TypeError, ValueError):
            # Un file di impostazioni che non si puo' scrivere non deve
            # impedire di leggere: la misura resta valida per questa sessione.
            pass

    def _applica_dimensione_testo(self, schermata=None) -> None:
        """Applica la percentuale alla schermata che si sta guardando."""
        if schermata is None:
            try:
                schermata = self.pila.currentWidget()
            except (AttributeError, RuntimeError):
                return
        metodo = getattr(schermata, "imposta_dimensione_testo", None)
        if not callable(metodo):
            return
        try:
            metodo(self._dimensione_testo)
        except (AttributeError, RuntimeError, TypeError):
            # Una schermata che non sa ancora disegnarsi non deve far cadere
            # la finestra: la misura verra' applicata quando sara' pronta.
            pass

    def _dimensione_testo_cambiata(self, valore: int) -> None:
        """Il cursore si e' mosso: il testo cambia subito, non al rilascio."""
        # La misura entra in `tema` subito: e' il posto unico, e cosi' anche
        # le schermate aperte dopo la vedono senza dover chiedere.
        self._dimensione_testo = tema.imposta_dimensione_testo(valore)
        etichetta = getattr(self, "_testo_percentuale", None)
        if etichetta is not None:
            try:
                etichetta.setText(f"{self._dimensione_testo}%")
            except RuntimeError:
                pass
        self._applica_dimensione_testo()

    def _apri_menu_testo(self) -> None:
        """I tre puntini: un cursore per la dimensione del testo.

        Il cursore e' lo stesso delle barre del lettore — `barraTesto` ha in
        `tema.py` le stesse regole di `barraLettore` — cosi' si trascina con
        lo stesso gesto e con lo stesso aspetto.  Il valore si vede in
        percentuale e si applica mentre si trascina: l'utente vede subito
        l'effetto sull'articolo, senza chiudere il menu e senza ricaricare.
        """
        if self._menu_testo is not None and self._menu_testo.isVisible():
            return

        menu = QMenu(self)
        menu.setObjectName("menuTesto")

        contenitore = QWidgetAction(menu)
        pannello = QWidget(menu)
        disposizione = QVBoxLayout(pannello)
        disposizione.setContentsMargins(14, 10, 14, 10)
        disposizione.setSpacing(8)

        titolo = QLabel("Dimensione del testo", pannello)
        titolo.setStyleSheet("font-weight: 600;")
        disposizione.addWidget(titolo)

        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(8)

        colore_icona = tema.colori(tema.tema_attivo()).get("testo", "#1a1a1a")

        meno = QPushButton(pannello)
        meno.setIcon(icona_tabler("minus", colore_icona, 14))
        meno.setFixedSize(26, 26)
        meno.setFlat(True)
        meno.setToolTip("Testo piu' piccolo")
        riga.addWidget(meno)

        cursore = QSlider(Qt.Orientation.Horizontal, pannello)
        cursore.setObjectName("barraTesto")
        cursore.setRange(DIMENSIONE_TESTO_MIN, DIMENSIONE_TESTO_MAX)
        cursore.setSingleStep(5)
        cursore.setPageStep(10)
        cursore.setTracking(True)
        cursore.setMinimumWidth(190)
        cursore.setValue(self._dimensione_testo)
        cursore.setToolTip("Dimensione del testo")
        cursore.valueChanged.connect(self._dimensione_testo_cambiata)
        cursore.sliderReleased.connect(self._salva_dimensione_testo)
        riga.addWidget(cursore, 1)

        piu = QPushButton(pannello)
        piu.setIcon(icona_tabler("plus", colore_icona, 14))
        piu.setFixedSize(26, 26)
        piu.setFlat(True)
        piu.setToolTip("Testo piu' grande")
        riga.addWidget(piu)

        meno.clicked.connect(lambda _=False: cursore.setValue(cursore.value() - 5))
        piu.clicked.connect(lambda _=False: cursore.setValue(cursore.value() + 5))

        disposizione.addLayout(riga)

        percentuale = QLabel(f"{self._dimensione_testo}%", pannello)
        percentuale.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disposizione.addWidget(percentuale)

        self._cursore_testo = cursore
        self._testo_percentuale = percentuale

        contenitore.setDefaultWidget(pannello)
        menu.addAction(contenitore)
        corrente = self.pila.currentWidget()
        if hasattr(corrente, "ha_spartito") and corrente.ha_spartito():
            menu.addSeparator()
            for testo, spartito in (("Modalità digitale (solo testo)", False), ("Modalità stampata (con spartito)", True)):
                voce = menu.addAction(testo)
                voce.setCheckable(True)
                voce.setChecked(corrente.spartito_attivo() == spartito)
                voce.triggered.connect(
                    lambda _=False, a=corrente, s=spartito: a.mostra_spartito(s))
        if hasattr(corrente, "ha_contenuti") and corrente.ha_contenuti():
            menu.addSeparator()
            galleria = menu.addAction("Contenuti multimediali…")
            galleria.triggered.connect(lambda _=False, a=corrente: a.apri_galleria())
        self._menu_testo = menu
        menu.aboutToHide.connect(self._salva_dimensione_testo)
        menu.aboutToHide.connect(self._menu_testo_chiuso)
        punto = self._pulsante_testo.mapToGlobal(
            QPoint(0, self._pulsante_testo.height()))
        # `popup` e non `exec`: il menu' non deve fermare il ciclo degli
        # eventi.  Mentre si trascina il cursore la pagina deve poter
        # ricevere il nuovo `font-size` e ridisegnarsi; con `exec` il ciclo
        # annidato del menu' tiene fermo il motore della pagina, e il testo
        # cambierebbe solo alla chiusura.  Il menu' resta aperto lo stesso
        # finche' non si clicca fuori, perche' e' una finestra `Qt.Popup`.
        menu.popup(punto)

    def _menu_testo_chiuso(self) -> None:
        """Il menu' e' stato chiuso: si puo' buttare, e si salva la misura."""
        menu = self._menu_testo
        self._menu_testo = None
        if menu is not None:
            menu.deleteLater()

    def _aggiorna_strumenti(self, titolo: str | None) -> None:
        """Quali strumenti della fascia servono nella sezione che si sta guardando.

        LA HOME HA UN SOLO STRUMENTO
        -----------------------------
        Nella Home restano **solo Aggiorna**.  Le cuffie non ci sono perche'
        nella Home non c'e' una pubblicazione: ci sono Preferiti, notizie e
        video recenti, e ognuno di quei pezzi si preme da per se'.  Un menu'
        delle cuffie li' direbbe «scegli una pubblicazione» quando l'utente ha
        gia' premuto la card che voleva, e la lente porterebbe
        via da una schermata che l'utente non voleva lasciare.

        Nelle altre sezioni ci sono tutti e quattro, perche' li' c'e' una
        pubblicazione o un elenco e gli strumenti hanno su cosa lavorare.

        PERCHE' NASCONDERE E NON TOGLIERE
        --------------------------------
        I pulsanti sono gli stessi per tutte le sezioni, quindi qui si
        nascondono e non si ricostruisce la fascia a ogni cambio.  Ricostruirla
        ogni volta cambierebbe l'ordine dei pulsanti — che l'utente impara a
        riconoscere a memoria — e costerebbe un layout a ogni click sulla rail.

        La regola e' un `if` e non una tabella: due sezioni con regole diverse
        sono un `if` che diventa due, e la tabella la si scrive quando la terza
        sezione chiede qualcosa di diverso.
        """
        solo_aggiorna = (titolo == "Home")
        for chiave, pulsanti in self.strumenti.items():
            if chiave == "segnalibri":
                # I segnalibri si vedono **mentre si legge**: e' li' che si
                # segna un punto e si rivedono quelli gia' segnati.  Nelle
                # sezioni l'elenco e' gia' nella rail (Ricerche), e un
                # pulsante che porta li' dove si va con l'icona e' la stessa
                # cosa in due posti.
                visibile = False
            else:
                visibile = (chiave == "aggiorna") if solo_aggiorna else True
            for pulsante in pulsanti:
                pulsante.setVisible(visibile)

    def _aggiorna_strumenti_per_schermata(self) -> None:
        """Gli strumenti seguono la schermata, non solo la sezione.

        LA NOTIZIA NON E' UNA SEZIONE
        -----------------------------
        `_sezione_attiva` dice dove si era prima di aprire l'articolo, e non
        dove si e' adesso.  Se la fascia si regolasse solo su quel nome, la
        notizia mostrerebbe gli strumenti della Home — cioe' soltanto
        Aggiorna — e le cuffie non comparirebbero mai.

        Qui la domanda si fa alla schermata corrente: se e' una notizia, la
        fascia mostra **solo le cuffie**, e solo quando l'audio e' stato
        trovato davvero.  Negli altri casi vale la regola della sezione, che
        resta quella di prima.
        """
        try:
            corrente = self.pila.currentWidget()
        except (AttributeError, RuntimeError):
            corrente = None

        # Sezione Timer: via gli strumenti della fascia, al loro posto i menu.
        in_timer = corrente is not None and corrente is self.sezioni.get("Timer")
        self._casella_timer.setVisible(in_timer)
        self.casella_strumenti.setVisible(not in_timer)
        if in_timer:
            self._pulsante_testo.setVisible(False)
            return

        # I tre puntini (dimensione del testo) servono solo dove c'e' del testo
        # da ingrandire: le schermate che sanno farlo, cioe' quelle che hanno
        # `imposta_dimensione_testo` (libri, pubblicazioni, articoli dal sito).
        self._pulsante_testo.setVisible(
            hasattr(corrente, "imposta_dimensione_testo"))

        if isinstance(corrente, NotiziaView):
            ha_audio = bool(getattr(corrente, "audio_url", ""))
            for chiave, pulsanti in self.strumenti.items():
                visibile = (chiave == "audio") and ha_audio
                for pulsante in pulsanti:
                    pulsante.setVisible(visibile)
                    if chiave == "audio":
                        pulsante.setToolTip("Ascolta questo articolo")
            return

        for pulsante in self.strumenti.get("audio", []):
            pulsante.setToolTip("Ascolta")
        self._aggiorna_strumenti(self._sezione_attiva)

        # Nei contenuti multimediali ogni voce ha i suoi tasti: le cuffie
        # della fascia non servono e porterebbero fuori dalla pagina.
        if corrente.__class__.__name__ == "ContenutiView":
            for pulsante in self.strumenti.get("audio", []):
                pulsante.setVisible(False)
            return

        # LA SCHERMATA DI LETTURA
        # -----------------------
        # Mentre si legge una pubblicazione ci sono due strumenti in piu':
        # i **segnalibri** (per segnare il punto dove si e' arrivati) e le
        # **cuffie** (per ascoltare l'audio di quella pubblicazione, in
        # streaming o scaricato per l'uso senza rete).
        #
        # Prima non c'erano: i segnalibri stavano nella barra del capitolo e
        # le cuffie comparivano solo nelle sezioni.  La fascia e' la parte
        # della finestra che c'e' in tutte le schermate, e li' ci stanno
        # entrambi: e' il posto dei comandi, e sono due comandi che valgono
        # mentre si legge.
        #
        # Le cuffie compaiono **solo** se l'audio c'e' davvero: un tasto che
        # apre un menu' vuoto e' un tasto rotto, e non si sa se e' rotto o
        # se non c'e' niente da ascoltare.
        if _si_sta_leggendo(corrente):
            for pulsante in self.strumenti.get("segnalibri", []):
                pulsante.setVisible(True)
                pulsante.setToolTip("Segnalibri di questa pubblicazione")
            voci = (self._voci_cuffie_della_schermata(corrente)
                    if getattr(corrente, "pub", None) is not None else [])
            for pulsante in self.strumenti.get("audio", []):
                pulsante.setVisible(bool(voci))
                pulsante.setToolTip("Ascolta l'audio di questa pubblicazione")

    def _evidenzia_rail(self, titolo: str) -> None:
        """La sezione attiva ha il fondo acceso."""
        for nome, pulsante in self.pulsanti_sezione.items():
            pulsante.impostato(nome == titolo)
            pulsante.update()

    def _strumento(self, chiave: str, pulsante=None) -> None:
        """Un pulsante della fascia.

        Ogni pulsante va a una sezione vera.  Un pulsante che mette solo il
        titolo e non cambia niente e' la cosa peggiore che si possa fare:
        sembra che faccia qualcosa, e l'utente prova tre volte prima di
        capire che e' rotto.

        `pulsante` serve al menu' delle cuffie, che si apre sotto il pulsante
        premuto.  Va passato perche' il menu' non ha un padre che lo tenga vivo
        e deve sapere dove cadere: vedi `_apri_menu_cuffie`.
        """
        if chiave == "lingua":
            # La lingua non porta da nessuna parte: apre un menu.  E' l'unico
            # strumento che fa cosi' ed e' per questo che il ramo e' qui e non
            # in una sezione: se la finestra aprisse il menu, il pulsante
            # diventerebbe un interruttore che cambia una schermata, e il
            # menu sparirebbe al primo clic.
            self._apri_menu_lingua()
            return

        if chiave == "cerca":
            # Dentro una pubblicazione (o la Bibbia) la lente cerca LI': un campo
            # sotto la lente, senza cambiare schermata.
            corrente = self.pila.currentWidget()
            if hasattr(corrente, "immagini_della_pagina") and getattr(corrente, "pub", None):
                self._apri_ricerca_locale(corrente, pulsante)
                return
            # Altrove la lente accende la barra di ricerca della Biblioteca
            # Digitale: una sola, che filtra le pubblicazioni e cerca nel testo.
            self._seleziona_nome("Biblioteca Digitale")
            sezione = self.sezioni.get("Biblioteca Digitale")
            if hasattr(sezione, "cerca_e_vai"):
                sezione.cerca_e_vai()
            else:
                self.set_titolo("Cerca")
            return

        if chiave == "aggiorna":
            # L'AGGIORNAMENTO DEL CATALOGO STA SOLO NELLA HOME E NELLE IMPOSTAZIONI
            # -----------------------------------------------------------------
            # Il tasto della fascia e' un aggiornamento **manuale**: ricarica
            # quello che si sta guardando, e nient'altro.
            #
            # Il database — il catalogo delle pubblicazioni — non si tocca
            # qui.  Sta nella Home e nelle Impostazioni, e in nessun'altra
            # parte: sono 210 megabyte, e scaricarli mentre si sta leggendo
            # un capitolo e' una cosa che l'utente non ha chiesto in quel
            # momento.  Un pulsante che scarica mezzo gigabyte senza che
            # nessuno lo sappia e' un pulsante che non si preme piu'.
            #
            # Nella Home il tasto e' l'unico che c'e', e li' l'aggiornamento
            # del catalogo e' quello che ci si aspetta: il catalogo e' l'elenco
            # di tutto quello che si puo' scaricare.
            try:
                corrente = self.pila.currentWidget()
            except (AttributeError, RuntimeError):
                corrente = None
            if isinstance(corrente, HomeView):
                self._controlla_aggiornamenti(forzato=True)
            self._aggiorna_schermata()
            return

        if chiave == "segnalibri":
            self._apri_menu_segnalibri(pulsante)
            return

        if chiave == "audio":
            # DENTRO UNA NOTIZIA LE CUFFIE SONO L'ARTICOLO
            # --------------------------------------------
            # La notizia non ha una pubblicazione di sotto: le cuffie non
            # devono aprire il menu' delle pubblicazioni, devono far partire
            # l'audio di **questo** articolo.  Il tasto compare solo quando
            # l'audio esiste (vedi `_aggiorna_strumenti_per_schermata`), ma
            # qui si ricontrolla lo stesso: un segnale puo' arrivare mentre
            # la schermata sta cambiando.
            try:
                corrente = self.pila.currentWidget()
            except (AttributeError, RuntimeError):
                corrente = None
            if isinstance(corrente, NotiziaView):
                url = getattr(corrente, "audio_url", "")
                if url:
                    if self._motore.sorgente() == url:
                        # Secondo clic sullo stesso articolo: e' un play/pausa,
                        # come il tasto della striscia.  Non si fa ripartire
                        # il brano dall'inizio.
                        from PyQt6.QtMultimedia import QMediaPlayer
                        if (self._motore.player.playbackState()
                                == QMediaPlayer.PlaybackState.PlayingState):
                            self._motore.sospendi()
                        else:
                            self._motore.continua()
                    else:
                        self._audio_notizia_richiesto(url)
                return

            # Le cuffie non portano da nessuna parte: **aprono un menu'**.
            #
            # Prima andavano dritte alla sezione Multimedia, che e' una cosa
            # sola e non e' quello che l'utente sta chiedendo.  Premendo le
            # cuffie dentro una pubblicazione di video l'utente non vuole
            # "andare nei multimedia": vuole sapere se c'e' qualcosa da
            # ascoltare o da prendere, **di questa pubblicazione**.
            #
            # Il menu' si costruisce ogni volta, con quello che c'e' davvero:
            # vedi `_apri_menu_cuffie`.
            self._apri_menu_cuffie(pulsante)
            return

        # Non c'e' piu' il ramo "tema" ne' il ramo "impostazioni": quei due
        # pulsanti sono stati tolti dalla fascia.  Il tema si cambia dalla
        # casella nelle Impostazioni e le Impostazioni si aprono dalla
        # sezione con l'ingranaggio nella rail.
        #
        # I rami sono rimossi e non lasciati inerti, perche' un ramo che non
        # viene mai preso e' codice che sembra funzionante e non lo e': il
        # giorno che qualcuno rimette il pulsante, il ramo c'e' gia' e fa
        # quello che sembra, senza che nessuno lo controlli.

    def _controlla_aggiornamenti(self, forzato: bool = False) -> None:
        """Chiede al server se c'e' qualcosa di nuovo, e non blocca.

        Sono due domande, e vanno fatte entrambe: «c'e' un pacchetto
        aggiornato o che non ho?» e «c'e' un catalogo piu' nuovo?».  Sono
        domande diverse, con risposte diverse, e una delle due riguarda il
        programma intero: senza un catalogo nuovo le pubblicazioni appena
        uscite non esistono, neppure per chiederne il checksum.

        Se la sezione Novita' non e' ancora stata costruita non la
        costruisce apposta per controllare: creare una schermata intera
        per una domanda che si puo' fare a mano sarebbe costoso.  In quel
        caso il controllo parte dalla sezione, e basta.
        """
        if forzato:
            self.mostra_toast("Controllo aggiornamenti...", "info", 3000)
        self._controlla_catalogo(forzato=forzato)

        # La sezione Novita' non e' piu' una sezione: e' dentro la Home, sotto
        # i Preferiti.  Il pulsante Aggiorna della fascia continua a chiedere
        # al server, quindi parla con quella.
        home = self.sezioni.get("Home")
        if home is None:
            return
        novita = getattr(home, "_novita", None)
        if novita is not None and hasattr(novita, "controlla"):
            novita.controlla(forzato=forzato)

    def _controlla_catalogo(self, forzato: bool = False) -> None:
        """C'e' un catalogo piu' nuovo sul server? Se si', lo prende.

        **Non blocca**: il confronto col server avviene in un thread, perche'
        `Aggiornamenti.catalogo_vecchio` fa due richieste e un programma
        fermo due secondi sembra piantato.

        QUANDO PARTE SENZA CHE GLI SI CHIEDA
        -------------------------------------
        Solo all'apertura e solo se la casella «Controlla da solo
        all'apertura» e' accesa, e solo entro un'ora dall'ultimo tentativo:
        senza questo, ogni apertura del programma chiederebbe il manifest, e
        la casella accesa o spenta finirebbero per fare lo stesso, che era
        il difetto.

        Con `forzato` — cioe' il tasto di aggiornamento in alto — parte
        sempre, accesa o spenta la casella: e' quello che l'utente ha
        premuto, e premere un tasto e non veder succedere niente e' la cosa
        peggiore che possa fare un pulsante.
        """
        if getattr(self, "_cataloghi_in_corso", 0) > 0:
            # Due controlli insieme non danno due catalogo: danno la stessa
            # risposta due volte, e gli stessi megabyte scaricati due.
            return
        if not forzato:
            if not Aggiornamenti.automatici():
                return
            if not Aggiornamenti.scaduto():
                return

        self._catalogo_chiesto = forzato

        def deciso(vecchio: bool, media_vecchio: bool) -> None:
            """Il server e' stato guardato: c'e' qualcosa di nuovo?

            Sono due cataloghi e due domande: quello delle pubblicazioni e
            quello dei media.  Vanno tenuti separati perche' uno puo'
            cambiare senza che l'altro cambi, e ognuno scarica nel suo posto.

            Nessuno dei due e' obbligatorio per far funzionare il programma,
            quindi se non c'e' niente da prendere non si fa niente e non si
            dice niente: il tasto che non trova novita' e' una cosa diversa
            dal tasto rotto, e l'utente deve poter capire quale sia.

            PERCHE' UN CONTATORE E NON UN SI' O NO
            --------------------------------------
            I due scaricamenti possono partire insieme, e quello dei media
            finisce prima perche' e' molto piu' piccolo.  Con una bandierina
            sola, il primo che arriva la abbassa e il secondo rimane a
            scaricare senza che nessuno lo stia aspettando: e se l'utente
            preme il tasto in quel momento partono due download sullo stesso
            file.  Il contatore sale a due e scende a uno a uno.
            """
            if not vecchio and not media_vecchio:
                if self._catalogo_chiesto:
                    self.mostra_toast("Tutto aggiornato", "success", 3000)
                return
            # TOAST: TROVATI AGGIORNAMENTI
            if self._catalogo_chiesto:
                parti = []
                if vecchio:
                    parti.append("catalogo")
                if media_vecchio:
                    parti.append("media")
                self.mostra_toast(f"Aggiornamenti trovati: {', '.join(parti)}", "info", 4000)
            # NESSUNA FINESTRA MESSAGGIO QUI
            # -------------------------------
            # `_mostra_messaggio` e' una finestra modale: si apre e non
            # lascia continuare finche' non la chiudi.  Dirigere "sto
            # scaricando" e poi "ho finito" da li' vuol dire due finestre da
            # chiudere a ogni aggiornamento, e per un lavoro che l'utente ha
            # chiesto lui e di cui ha gia' visto partire la riga sotto la
            # fascia.
            #
            # Il lavoro in corso si dice con la riga di avanzamento, che c'e'
            # gia' e sta appoggiata al bordo della fascia.  Il risultato si
            # vede dalla schermata, che viene riletta.
            if vecchio:
                self._cataloghi_in_corso += 1
                self._scaricamento_inizia("Catalogo", 0)
                Aggiornamenti.scarica_catalogo(
                    completion=self._catalogo_preso,
                    on_progress=self._scaricamento_avanza,
                )
            if media_vecchio:
                self._cataloghi_in_corso += 1
                self._scaricamento_inizia("Catalogo dei media", 0)
                CatalogoMedia.scarica(
                    Lingua.corrente_simbolo(),
                    completion=self._media_preso,
                )

        # IL CONFRONTO VIENE DA UN THREAD, LA RISPOSTA NO
        # ------------------------------------------------
        # `catalogo_vecchio` chiede due volte al server e blocca, quindi va
        # in background.  Ma la risposta arriva a `deciso`, che scrive
        # messaggi e muove la barra: quello e' roba di finestra e va fatta
        # sul main thread.  Senza il passaggio si ottiene un `abort()` senza
        # spiegazione, perche' Qt non accetta che un thread secondario tocchi
        # i widget.
        from Utility.Extensions.Ext_DispatchQueue import background, on_main

        lingua = Lingua.corrente_simbolo()

        def lavoro() -> None:
            vecchio = Aggiornamenti.catalogo_vecchio()
            media_vecchio = CatalogoMedia.da_aggiornare(lingua)
            on_main(lambda: deciso(vecchio, media_vecchio))

        background(lavoro)

    def _media_preso(self, percorso: str, errore: str) -> None:
        """Il catalogo dei media e' arrivato, o non e' arrivato.

        Quando finisce anche questo, la riga di avanzamento sparisce e la
        schermata viene riletta: e' cosi' che le sezioni che mostrano le
        novita' sui video e sull'audio si vedono senza dover cambiare sezione.
        """
        if getattr(self, "_cataloghi_in_corso", 0) > 0:
            self._cataloghi_in_corso -= 1
        if getattr(self, "_cataloghi_in_corso", 0) > 0:
            # L'altro catalogo sta ancora scendendo: la barra resta, e non
            # si rilgge la schermata perche' il catalogo dei media da solo
            # non basta a cambiarla.
            return
        self._scaricamento_finito()
        if errore:
            if getattr(self, "_catalogo_chiesto", False):
                self.mostra_toast(f"Errore aggiornamento media: {errore}", "error", 5000)
            return
        if self._catalogo_chiesto:
            self.mostra_toast("Elenco video/audio aggiornato", "success", 3000)
        self._aggiorna_schermata()

    def _catalogo_preso(self, versione: str, errore: str) -> None:
        """Il catalogo e' arrivato, o non e' arrivato.

        Se e' andato bene, le sezioni che leggono il catalogo vanno
        rilette: senza questo la Home continuerebbe a mostrare la lista di
        prima per tutta la sessione, e l'utente avrebbe scaricato 58
        megabyte per non vedere niente di nuovo.  E' anche l'unico riscontro
        che l'utente ha: il pulsante e' premuto, la riga e' passata, e la
        schermata davanti cambia.  Per questo l'esito buono non apre una
        finestra: si vede.

        L'errore invece parla, ma solo se il giro e' partito da un tasto
        premuto.  All'apertura una finestra di errore non la chiede nessuno,
        non la puo' chiudere nessuno, e nasconde il programma per un
        download che si puo' ripetere quando si vuole.
        """
        if getattr(self, "_cataloghi_in_corso", 0) > 0:
            self._cataloghi_in_corso -= 1
        if getattr(self, "_cataloghi_in_corso", 0) > 0:
            # L'altro catalogo sta ancora scendendo: la barra resta.
            return
        self._scaricamento_finito()
        if errore:
            if getattr(self, "_catalogo_chiesto", False):
                self.mostra_toast(f"Errore aggiornamento catalogo: {errore}", "error", 5000)
            return
        if self._catalogo_chiesto:
            self.mostra_toast("Catalogo aggiornato", "success", 3000)
        self._aggiorna_schermata()

    def _aggiorna_preferiti(self) -> None:
        """I Preferiti sono cambiati: si rilegge la griglia della Home.

        NON RILEGGE IL CATALOGO E NON CHIEDE NIENTE AL SERVER
        ----------------------------------------------------
        Il file dei Preferiti e' gia' scritto: qui si tratta di rileggerlo e
        ridisegnare quattro card.  Il pulsante Aggiorna fa tre cose diverse —
        interroga il server, rilegge il catalogo, ricrea le sezioni — e
        nessuna delle tre e' questa.  Collegarle faceva dipendere una stella
        da quattro richieste di rete, e ricreava la Home mentre l'utente la
        stava guardando.

        La Home si tocca anche se non e' quella che si sta guardando? No: la
        si tocca sempre, perche' il lavoro e' una griglia di quattro nomi e
        non ricreare niente.  Se non e' la sezione corrente nessuno la vede,
        e quando l'utente ci tornera' sara' gia' a posto.  Il caso contrario
        — rimandare il lavoro a quando si apre la sezione — e' il modo per
        dimenticarsi di farlo.
        """
        sezione = self.sezioni.get("Home")
        if sezione is not None and hasattr(sezione, "aggiorna_preferiti"):
            sezione.aggiorna_preferiti()

        # Anche le nuvolette: un Preferito che e' stato scaricato o tolto
        # cambia la risposta a «lo devo ancora scaricare?».  Va detto qui e non
        # dentro `aggiorna_preferiti` perche' quella non sa niente dei pezzi
        # di media: qui la finestra ha gia' fatto il lavoro di chiudere i
        # pacchetti, ed e' l'unico posto che sa che il disco e' cambiato.
        if sezione is not None and hasattr(sezione, "aggiorna_scaricature"):
            sezione.aggiorna_scaricature()

    def _apre_una_card_media(self, sigla: str, lingua: str, traccia) -> None:
        """Una card di un video e' stata premuta: suona quel video.

        PRIMA SI CERCA IL FILE, E SOLO DOPO LA RETE
        --------------------------------------------
        Una card della striscia e' una **traccia** precisa, e la traccia e'
        il dato che la distingue dalle altre della stessa pubblicazione:
        `MediaScaricati.file_di` dice se quella traccia e' gia' sul disco, e
        se c'e' si suona quella senza passare dalla scheda dei media.

        Era il difetto che si vedeva come «i video non partono quando li
        cliccio»: il video era scaricato, ma il clic apriva la pubblicazione e
        la traccia bisognava ritrovarla e ripremerla.  Il file c'era: si
        guardava nel posto sbagliato.

        SENZA IL FILE SI SUONA LO STESSO, IN STREAMING
        ----------------------------------------------
        Prima qui si apriva la lista dei media e si lasciava l'utente a
        ripremere la traccia.  Ma la regola e' una e vale dappertutto:
        **premendo un video parte il video** — dal disco se c'e', dalla rete
        se non c'e'.  Si apre quindi la sezione Multimedia sulla scheda giusta
        e le si chiede di far partire quella traccia: l'indirizzo lo dà il
        server quando la lista arriva, e di quello si occupa `MediaView`.
        Vedi `MediaView.apri_e_suona`.

        UNA CARD DI PUBBLICAZIONE NON E' UNA TRACCIA
        --------------------------------------------
        Le card di `sjj`, `lmd`, `th`, `lff` sono pubblicazioni intere, e la
        traccia e' vuota.  Per quelle la domanda giusta e' «che cosa apre?»
        — testo, audio o video — e la risposta la dà `che_cosa_apre` con il
        catalogo, esattamente come per un Preferito: la stessa sigla apre la
        stessa cosa da qualunque parte la si prema.
        """
        numero = CatalogoMedia.numero_traccia(traccia)
        if numero is None:
            self._aperta_da_preferito(sigla, lingua)
            return

        from Utility import MediaScaricati

        try:
            file = MediaScaricati.file_di(sigla, lingua, numero)
        except Exception:  # noqa: BLE001
            file = None

        if file is not None:
            # Si va diritti al lettore con il file: e' lo stesso gesto di
            # «Apri» nella sezione Scaricati.
            titolo = ""
            try:
                voce = CatalogoMedia.voce_di(sigla, lingua, numero)
                titolo = (voce or {}).get("title") or ""
            except Exception:  # noqa: BLE001
                titolo = ""
            self._apre_un_media_scaricato(file, titolo or str(file.name))
            return

        self._apre_media_e_suona(sigla, lingua, numero,
                                 self._scheda_di_traccia(sigla, lingua, numero))

    def _scheda_di_traccia(self, sigla: str, lingua: str, traccia) -> int:
        """La scheda di Multimedia per una traccia: 0 audio, 1 video.

        Il formato sta nel catalogo, e il video e' il ripiego: e' quello che
        si guarda, e aprire la scheda Video per un audio e' meno sbagliato che
        il contrario, perche' l'utente sta cercando qualcosa da vedere.
        """
        if CatalogoMedia.formato_di_traccia(sigla, lingua, traccia) == "AUDIO":
            return 0
        return 1

    def _catalogo(self):
        """Il catalogo delle pubblicazioni, costruito se non c'e' ancora.

        IL PERCHE' DI UN METODO E NON `sezioni.get("Pubblicazioni")`
        -------------------------------------------------------------
        Il catalogo sta in `self.sezioni` sotto il nome «Pubblicazioni», che e'
        il nome con cui sei pezzi di questo file lo cercano gia' — il download
        dalla Home, «apri il giorno», la ricerca per sigla, l'apertura di una
        pubblicazione da una card.  Ma `sezioni.get` **non crea niente**:
        prima che l'utente prema una categoria del catalogo, la chiave non
        c'e' e quei sei posti ricevono `None` e ritornano in silenzio.

        Il difetto e' che quei posti si raggiungono **senza passare dal
        catalogo**: una card della Home si preme andando avanti, senza aver mai
        visto le dodici categorie.  Il pulsante sembrava premuto e non
        succedeva niente — lo stesso sintomo del collegamento rotto, e per la
        stessa ragione: un nome che non c'e' e un `if` che zittisce.

        Qui il catalato viene costruito al primo bisogno e messo nella pila
        senza mostrarlo: costruirlo non scarica niente (il catalogo e' gia' sul
        disco, e quando non c'e' `PubView` mostra un pulsante invece di
        scaricare da solo — vedi `PubView.__init__`), quindi non costa un
        download all'avvio ne' blocca l'apertura della finestra.

        Non e' un singleton per vezzo: e' perche' un oggetto costruito due
        volte perde quello che aveva gia' dentro.  Il catalogo tiene l'elenco
        letto dal disco, e due copie avrebbero due elenchi distinti: quello
        mostrato dalla Home e quello mostrato dalle categorie potrebbero
        elencare pubblicazioni diverse nello stesso momento.
        """
        catalogo = self.sezioni.get("Pubblicazioni")
        if catalogo is None:
            catalogo = self._crea_sezione("Pubblicazioni")
            self.sezioni["Pubblicazioni"] = catalogo
            self.pila.addWidget(catalogo)
            self._collega(catalogo)
            # Non viene distrutto tornando indietro ne' cambiando sezione:
            # e' l'unica schermata che si riusa, perche' rileggere il
            # catalogo a ogni categoria premuta si sente.  Vedi
            # `_se_permanente` perche' succede e cosa succederebbe senza.
            self._segna_permanente(catalogo)

            # LA BARRA DEL DOWNLOAD VA **SULLA CARD**, NON SOLO IN FONDO
            # ------------------------------------------------------------
            # Il catalogo scarica e dice quanto e' andato avanti, ma lo dice
            # con una riga sola in fondo alla finestra.  Con trecento pubblicazioni
            # in griglia quella riga parla di un pezzo che non si vede: dice
            # «qualcosa sta scendendo» e non quale.
            #
            # Qui quegli stessi segnali arrivano anche alla card giusta, che e'
            # l'unica cosa che l'utente sta guardando mentre aspetta.  La
            # riga in fondo **resta**: ci sono scaricamenti senza card (i
            # cataloghi, i capitoli), e toglierla farebbe sparire il progresso
            # di quelli.
            catalogo.scaricamentoInizia.connect(
                self._scarica_comincia_sulla_card)
            catalogo.scaricamentoAvanza.connect(
                self._scarica_avanza_sulla_card)
            catalogo.scaricata.connect(self._scarica_finita_sulla_card)
        return catalogo

    # ------------------------------------------------------------------
    # IL PROGRESSO SULLA CARD CHE L'UTENTE HA PREMUTO
    # ------------------------------------------------------------------

    def _card_del_pezzo_in_scarico(self):
        """La card della pubblicazione che sta scendendo, o ``None``.

        Cerca nella sezione Biblioteca Digitale per delega: e' li' che la
        griglia delle pubblicazioni sta, ed e' li' che c'e' il metodo `card_di`.
        Questa finestra non sa come sono fatte le card — e non deve saperlo:
        chiede «mi dai la card di questo pezzo?» e usa la risposta.
        """
        pub = getattr(self, "_pub_in_scarico", None)
        if pub is None:
            return None
        # Prima la sezione che si sta guardando: la barra deve comparire dove
        # l'utente ha premuto, non su una card della Biblioteca che non vede.
        for sezione in (self.pila.currentWidget(), self.sezioni.get("Adunanze"),
                        self.sezioni.get("Biblioteca Digitale")):
            if sezione is not None and hasattr(sezione, "card_di"):
                card = sezione.card_di(pub)
                if card is not None:
                    return card
        return None

    def _home_giorno(self, metodo: str, *args) -> None:
        """Gira alla Home l'avanzamento, se il pezzo che scende e' quello del
        riquadro del giorno: la barra viola sta al posto del tasto Scarica."""
        pub = getattr(self, "_pub_in_scarico", None)
        home = self.sezioni.get("Home")
        if pub is None or home is None or not hasattr(home, metodo):
            return
        try:
            from Utility import JWPubManager
            if getattr(pub, "keySymbol", None) == JWPubManager.sigla_del_giorno():
                getattr(home, metodo)(*args)
        except Exception:  # noqa: BLE001
            pass

    def _scarica_comincia_sulla_card(self, *_a) -> None:
        """Il download del catalogo comincia: la barra si accende sulla card."""
        self._home_giorno("scarico_giorno_inizia",
                          _a[1] if len(_a) > 1 else 0)
        card = self._card_del_pezzo_in_scarico()
        if card is not None:
            card._scarica_comincia(0)

    def _scarica_avanza_sulla_card(self, fatti: int, totale: int) -> None:
        """Un capitolo e' scritto: la barra della card si muove."""
        self._home_giorno("scarico_giorno_avanza", fatti, totale)
        card = self._card_del_pezzo_in_scarico()
        if card is not None:
            card._scarica_avanza(fatti, totale)

    def _scarica_finita_sulla_card(self) -> None:
        """Il download e' finito: la barra sparisce e la nuvoletta torna.

        Il pacchetto adesso c'e': la nuvoletta della card che l'utente sta
        guardando deve sparire subito, senza aspettare il giro completo delle
        card — altrimenti sembrerebbe che il download non sia andato, e
        l'utente lo rifarebbe.
        """
        card = self._card_del_pezzo_in_scarico()
        if card is not None:
            card._scarica_finita()
            if hasattr(card, "_scarica"):
                card._scarica.setVisible(False)
        self._pub_in_scarico = None

    def _nome_categoria(self, chiave: str) -> str:
        """Il nome leggibile di una categoria, o la stringa vuota se non c'e'.

        Il nome e' quello scritto in `MediaView.CATEGORIE_PUB`, perche' e' li'
        che l'utente ha premuto e che ha gia' letto: scriverlo anche qui
        sarebbe una seconda copia, e il giorno che le dodici categorie
        cambiano nome la schermata del catalogo direbbe una parola e la
        griglia un'altra.

        Se la chiave non e' nella tabella si restituisce la stringa vuota
        invece di far fallire tutto: una categoria nuova senza nome non
        impedisce di vedere le sue pubblicazioni, e mostrare un numero
        (`Tipo 7`) al posto del nome e' comunque piu' utile di niente.
        """
        from SubViews.MediaView import CATEGORIE_PUB

        for chiave_categoria, nome, _icona in CATEGORIE_PUB:
            if chiave_categoria == chiave:
                return nome
        return ""

    def _vai_a_multimedia(self, navigare: bool = False) -> None:
        """Apre la sezione Multimedia ricordando da dove si e' entrati.

        IL RITORNO E' UNA COSA CHE L'UTENTE NON DEVE CHIEDERE
        ------------------------------------------------------
        Il lettore — play, pausa, posizione — vive nella sezione Multimedia.
        Chi preme un video nella Home o una riga negli Scaricati vuole **vedere
        quel video**, non «finire nei Multimedia»: quando poi lo chiude, o lui
        finisce, deve ritrovarsi dove era.  Qui si segna il posto, e
        `_torna_da_dove_sono_partito` ce lo riporta.

        ADESSO LA PROVENIENZA E' UN CAMPO SUO
        --------------------------------------
        Qui si scrive `_provenienza` e non `_ritorno`: il ritorno non lo si
        puo' scrivere adesso, perche' **non lo si sa ancora**.  L'utente ha
        premuto un video e il programma va nei Media, ma il media parte
        davvero solo quando la lista e' arrivata — e a quel punto l'utente
        potrebbe essere gia' passato da un'altra parte.

        Per questo la provenienza vive finche' il media non parte
        (`_media_partito`), e li' diventa il ritorno, che e' una promessa e
        resta fino a che il media non finisce o non viene chiuso.
        """
        # Se il video parte da una schermata che non e' una sezione (un articolo,
        # un elenco di capitoli, una pagina qualunque) la si ricorda e la si tiene
        # viva: `_seleziona_nome` senza `ricorda` distrugge le schermate temporanee,
        # e la X non avrebbe piu' nulla a cui tornare.
        self._segna_la_partenza()
        self._entra_in_multimedia(navigare)

    def _segna_la_partenza(self) -> None:
        """Ricorda da dove parte il video, senza cambiare schermata."""
        corrente = self._schermo_corrente
        if corrente is not None and not self._se_permanente(corrente):
            self._articolo_di_partenza = corrente
        self._provenienza = self._sezione_dove_sei()

    def _entra_in_multimedia(self, navigare: bool = False) -> None:
        """Fa vedere il lettore (una volta sola per richiesta).

        Il lettore e' uno solo e vive nella Biblioteca.  Se il video parte da
        un'altra sezione **non si cambia sezione**: il lettore si mette sopra la
        schermata in cui si e' e, chiuso, la schermata resta com'era (niente da
        riportare).  Con ``navigare`` invece si va davvero nella Biblioteca, per
        chi ha chiesto di vedere la lista dei media.
        """
        self._attesa_video = False
        sezione = self.sezioni.get("Biblioteca Digitale")
        if self.pila.currentWidget() is sezione:
            return
        if navigare or sezione is None or not hasattr(sezione, "cedi_il_lettore"):
            self._seleziona_nome("Biblioteca Digitale",
                                 ricorda=self._articolo_di_partenza is not None)
            return
        self._provenienza = None
        self._articolo_di_partenza = None
        lettore = sezione.cedi_il_lettore(self._ospite_lettore.layout())
        if not self._lettore_collegato:
            self._lettore_collegato = True
            lettore.visibilitaCambiata.connect(self._lettore_ospite_visibile)
        self._mostra_ospite(lettore.isVisible())
        self._contenitore.layout().activate()

    def _lettore_ospite_visibile(self, visibile: bool) -> None:
        """Il contenitore del lettore segue il lettore, se questo e' li' dentro."""
        self._mostra_ospite(bool(visibile) and self._lettore_e_qui())

    def _mostra_ospite(self, visibile: bool) -> None:
        """Mostra o nasconde il contenitore del lettore e la sua maniglia insieme."""
        self._ospite_lettore.setVisible(visibile)
        self._maniglia_lettore.setVisible(visibile)

    def _lettore_e_qui(self) -> bool:
        """Il lettore sta sopra la schermata corrente (e non nella Biblioteca)?"""
        return bool(getattr(self.sezioni.get("Biblioteca Digitale"), "lettore_fuori", False))

    def _attendi_il_video(self) -> None:
        """Un video da rete sta per partire: si resta dove si e' fino a quando e' pronto.

        La lista dei media arriva dal server in qualche istante: prima si
        passava subito alla Biblioteca e si vedeva la lista vuota per qualche
        secondo.  Ora si resta sulla schermata corrente (senza scritte: coprirebbero il lettore), e si
        passa al lettore solo quando il video parte (`staPerSuonare`); se non
        arriva niente in 12 secondi si va comunque alla Biblioteca a vedere cosa e' successo.
        """
        self._segna_la_partenza()
        self._attesa_video = True
        QTimer.singleShot(12000, lambda: self._attesa_video and self._entra_in_multimedia())

    def _media_partito(self) -> None:
        """Un media e' partito: adesso si sa da dove.

        LA PROMESSA DELLA X
        -------------------
        `_ritorno` e' la sezione da cui riportare l'utente quando il media
        finisce o viene chiuso.  E' una sola regola, senza eccezioni:

        - il media e' partito da un'altra sezione -> la X ci riporta li';
        - il media e' partito **dentro** la sezione Multimedia -> la X lascia
          l'utente li' dove e'.

        Il secondo caso non e' un caso speciale: e' quello di prima con
        `_ritorno` a `None`, perche' «torna dove sei partito» e «resti nei
        Media» sono la stessa cosa.

        PERCHE' DUE CAMPI E NON UNO
        --------------------------
        Il media parte **asincrono**: quando l'utente preme una card, la
        sezione Media non ha ancora la lista e il media non e' partito.  Se
        il ritorno si scrivesse al momento del clic, e nel frattempo
        l'utente scegliesse un'altra sezione dalla rail, al momento in cui il
        media parte davvero non si saprebbe piu' da dove e' partito — e la X
        manderebbe l'utente nel posto sbagliato.

        `_provenienza` vale solo per il media che sta per partire, e si
        azzera qui: se il media parte **senza** che nessuno abbia cambiato
        sezione — cioe' premendo una riga della lista dei Media — il ritorno
        vale `None`, e l'utente resta qui, che e' quello che chiedeva
        quella riga.
        """
        if self._lettore_e_qui():
            self._provenienza = self._articolo_di_partenza = None
            self._ritorno = self._ritorno_schermata = None
            return
        provenienza = self._provenienza
        self._provenienza = None
        # Un media normale non torna a una schermata interna: la sua promessa
        # e' una sezione.  Solo un video aperto da un articolo (popup) porta
        # con se' l'articolo, e la X ci riporta li'.
        self._ritorno_schermata = self._articolo_di_partenza
        self._articolo_di_partenza = None
        if provenienza and provenienza != "Biblioteca Digitale":
            self._ritorno = provenienza
        else:
            self._ritorno = None

    #: Quante schermate la cronologia tiene.  Non e' un numero magico: e' il
    #: punto in cui il ritorno indietro comincia a essere inutile, e oltre il
    #: quale le schermate vive cominciano a pesare sulla memoria.
    _SCHERMATE_MAX = 24

    def _dimentica_le_troppe(self) -> None:
        """Tronca la cronologia dalla parte piu' vecchia, distruggendo cio' che si puo'.

        Si butta via la piu' vecchia **non permanente**: le sette sezioni stanno
        sempre nella pila e non si buttano mai, quindi la loro presenza nella
        cronologia non e' un problema — e buttarle fuori lascerebbe la pila senza
        la Home, che e' la schermata di partenza.
        """
        while len(self._schermate) > self._SCHERMATE_MAX:
            vecchia = self._schermate.pop(0)
            if vecchia is None or self._se_permanente(vecchia):
                # Si rimette dentro e si smette: le permanenti non si buttano, e
                # continuare a togliere da una cronologia che non si accorcia
                # porterebbe a mangiare tutta la cronologia.
                self._schermate.insert(0, vecchia)
                break
            self.pila.removeWidget(vecchia)
            vecchia.deleteLater()

    def _sezione_dove_sei(self) -> str | None:
        """Il nome della sezione che si sta guardando adesso, o None.

        PERCHE' NON BASTA `self._sezione_attiva`
        --------------------------------------
        `_sezione_attiva` e' un campo che si aggiorna quando l'utente sceglie
        una sezione.  Ma all'avvio **non e' mai stato scelto niente**: la Home
        e' la schermata di partenza e non passa da nessuna scelta, quindi il
        campo vale ancora `None`.

        E il difetto segnalato e' esattamente questo: partendo un video dalla
        Home e chiudendolo con la X, la prima volta non tornava alla Home ma
        restava nei Multimedia.  Non per caso: la provenienza era `None`,
        quindi il segnaposto non era stato messo e non c'era niente da
        consumare.  **La seconda volta funzionava** perche' nel frattempo
        l'utente aveva premuto qualcosa nella fascia, e quello aveva riempito
        il campo.

        Un campo che si ricorda di quello che e' successo e' la risposta
        sbagliata a «dove sto guardando adesso»: la risposta ce l'ha gia' la
        pila, che e' la cosa che decide cosa si vede.  Qui si legge da li', e
        il campo resta quello che e': un aiuto per i pezzi che non hanno la
        pila sotto gli occhi.
        """
        corrente = None
        try:
            corrente = self.pila.currentWidget()
        except (AttributeError, RuntimeError):
            corrente = None
        if corrente is None:
            return self._sezione_attiva
        for nome, schermata in self.sezioni.items():
            if schermata is corrente:
                return nome
        return self._sezione_attiva

    def _torna_alla_schermata(self, schermata) -> bool:
        """Torna a una schermata interna, per esempio a una notizia.

        LA NOTIZIA NON E' UNA SEZIONE
        -----------------------------
        La promessa della X era un nome di sezione, e per una notizia non
        basta: la notizia non sta in `self.sezioni`, quindi il nome non
        esisteva e la X ripiegava sulla Home.  Qui si riporta l'utente alla
        schermata vera, se e' ancora viva e se e' ancora nella cronologia.

        LA CRONOLOGIA SI TRONCA, NON SI SPOSTA
        --------------------------------------
        Se mentre l'audio suonava l'utente e' passato a un'altra sezione, la
        cronologia ha la notizia sotto e la sezione sopra.  Per tornare alla
        notizia si tolgono le schermate sopra di lei — quelle non permanenti
        vengono distrutte, le sezioni restano vive ma escono dalla cronologia.
        Cosi' la freccia indietro successiva riparte dalla notizia, e non
        dalla sezione che l'utente aveva aperto nel frattempo.
        """
        if schermata is None:
            return False
        try:
            if self.pila.indexOf(schermata) < 0:
                return False
            if schermata not in self._schermate:
                return False
        except (AttributeError, RuntimeError, ValueError):
            return False

        while self._schermate and self._schermate[-1] is not schermata:
            sopra = self._schermate.pop()
            if sopra is None or sopra is schermata:
                continue
            if self._se_permanente(sopra):
                continue
            try:
                self.pila.removeWidget(sopra)
                sopra.deleteLater()
            except (AttributeError, RuntimeError):
                pass

        # La freccia avanti appartiene alla cronologia che si e' appena
        # troncata: quello che c'era dopo non e' piu' raggiungibile.
        self._avanti.clear()

        self.pila.setCurrentWidget(schermata)
        self._schermo_corrente = schermata
        self.nome.setText("")
        self._metti_la_barra(schermata)
        self.set_titolo(getattr(schermata, "titolo", "") or "")

        # La rail deve indicare la sezione da cui la notizia e' stata aperta,
        # non quella in cui l'utente si era spostato mentre ascoltava.
        try:
            posizione = self._schermate.index(schermata)
        except ValueError:
            posizione = len(self._schermate)
        for sotto in reversed(self._schermate[:posizione]):
            trovata = False
            for nome, sezione in self.sezioni.items():
                if sezione is sotto:
                    self._sezione_attiva = nome
                    self._evidenzia_rail(nome)
                    trovata = True
                    break
            if trovata:
                break

        self._applica_dimensione_testo(schermata)
        self._aggiorna_strumenti_per_schermata()
        self._aggiorna_frecce()
        return True

    def _torna_da_dove_sono_partito(self) -> None:
        """Il lettore si e' chiuso o il brano e' finito: si torna da dove si era.

        IL SEGNAPOSTO SI CONSUMA SEMPRE
        --------------------------------
        Anche se la sezione non c'e' piu' (o non c'e' mai stato un ritorno da
        fare) si azzera lo stesso.  Un segnaposto lasciato in giro farebbe
        tornare a una sezione di due clic fa la prossima volta che si chiude un
        media, che e' un posto dove l'utente non era.

        PRIMA LA SCHERMATA, POI LA SEZIONE
        ----------------------------------
        Un audio partito da una notizia ha come promessa la notizia, non la
        sezione che c'era sotto.  Si prova prima quella; solo se non esiste
        piu' si usa il nome di sezione, che resta la strada dei media normali.
        """
        schermata = self._ritorno_schermata
        destinazione = self._ritorno
        self._ritorno_schermata = None
        self._ritorno = None
        if self._torna_alla_schermata(schermata):
            return
        if not destinazione or destinazione == "Biblioteca Digitale":
            return
        if destinazione not in self.sezioni:
            return
        self._seleziona_nome(destinazione)

    def _apre_media_e_suona(self, sigla: str, lingua: str, traccia=None,
                            scheda: int = 1) -> None:
        """Apre Multimedia e fa partire una traccia, dal disco o dalla rete.

        Si sceglie la sezione prima e si da' la richiesta alla sezione: e' lei
        che sa quando la lista dei media e' arrivata, e quindi quando la
        traccia si puo' far partire.  Qui non si aspetta niente e non si
        costruisce nessun lettore — vedi `MediaView.apri_e_suona`.
        """
        sezione = self.sezioni.get("Biblioteca Digitale")
        if sezione is None or not hasattr(sezione, "apri_e_suona"):
            # Una sezione che non sa ancora suonare non deve far cadere il
            # clic: si ricade sul comportamento di sempre, che apre la lista.
            sezione = self.sezioni.get("Biblioteca Digitale")
            if sezione is None:
                return
            numero = Lingua.da_simbolo(lingua)
            pub = Publication(ID=0, keySymbol=sigla, year=0,
                              mepsLanguageId=numero, publicationTypeId=0,
                              issueTagNumber=0, title=sigla)
            self._apre_media(pub, scheda)
            return
        numero = Lingua.da_simbolo(lingua)
        pub = Publication(ID=0, keySymbol=sigla, year=0,
                          mepsLanguageId=numero, publicationTypeId=0,
                          issueTagNumber=0, title=sigla)
        try:
            self._attendi_il_video()
            sezione.apri_e_suona(pub, traccia, scheda)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Media: non riesco a far partire {sigla} ⚠️")
            traceback.print_exc()

    def _aperta_da_preferito(self, sigla: str, lingua: str) -> None:
        """Una card dei Preferiti e' stata premuta.

        STESSA REGOLA DELLA SEZIONE SCARICATI
        --------------------------------------
        Solo testo -> il pacchetto, audio -> la scheda Audio, video -> la
        scheda Video.  La domanda la fa `JWPubManager.che_cosa_apre`, che e'
        l'unico posto dove la regola e' scritta: la sezione Scaricati chiama
        la stessa, e cosi' lo stesso Preferito apre la stessa cosa da
        qualunque parte lo si prema.

        La `Publication` qui e' costruita e non presa dal catalogo: un
        Preferito e' una sigla e una lingua, e sono gia' quello che serve per
        aprire.  Cercarla fra le 3.741 righe del database aggiungerebbe una
        ricerca a ogni clic per un oggetto che si puo' scrivere in tre righe.

        Se la pubblicazione non ha il pacchetto si apre lo stesso: la sezione
        Pubblicazioni funziona anche per una non scaricata, e li dice lei cosa
        non trova.  Non si rimane a non fare niente.

        IL CATALOGO COPRE QUELLO CHE IL DISCO NON SA
        --------------------------------------------
        `che_cosa_apre` guarda solo il disco: una pubblicazione di video non
        ancora scaricata le risulta «pubblicazione», e il clic finiva in
        Pubblicazioni invece che in Multimedia, che dice «non e' scaricato»
        mentre il video si potrebbe vedere subito.  Se il catalogo conosce una
        traccia di quella sigla, la pubblicazione e' di media: si apre
        Multimedia e si fa partire la prima, in streaming.  Vedi
        `CatalogoMedia.e_di_media`.
        """
        apri = JWPubManager.che_cosa_apre(sigla, lingua)
        if apri in ("audio", "video"):
            # Audio/video: parte subito, con la prima traccia della scheda,
            # dal disco se c'e' e dalla rete se non c'e'.
            self._apre_media_e_suona(sigla, lingua, None,
                                     0 if apri == "audio" else 1)
            return

        if CatalogoMedia.e_di_media(sigla, lingua):
            numero, formato = CatalogoMedia.prima_traccia_di(sigla, lingua)
            self._apre_media_e_suona(sigla, lingua, numero,
                                     0 if formato == "AUDIO" else 1)
            return

        numero = Lingua.da_simbolo(lingua)
        pub = Publication(ID=0, keySymbol=sigla, year=0,
                          mepsLanguageId=numero, publicationTypeId=0,
                          issueTagNumber=0, title=sigla)
        sezione = self._catalogo()
        if sezione is None or not hasattr(sezione, "apri_pubblicazione"):
            return
        try:
            sezione.apri_pubblicazione(pub)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Preferiti: non riesco ad aprire {sigla} ⚠️")
            traceback.print_exc()

    def _aperta_notizia(self, indirizzo: str) -> None:
        """Una card delle notizie e' stata premuta: la pagina si apre qui.

        DENTRO L'APP, NON NEL BROWSER
        -----------------------------
        `QDesktopServices.openUrl` aprirebbe il browser della macchina: una
        finestra nuova, fuori da questa, e il pulsante indietro di questa
        finestra continuerebbe a portare dove stava prima.  Tornando indietro
        nel browser e poi in avanti si ritrovava nella pagina giusta, quindi
        sembrava funzionare — ma non si e' piu' nel programma, e la pila delle
        schermate non registra niente.

        Qui si usa `NotiziaView`, che riusa il motore che mostra i capitoli
        della Bibbia.  E una schermata come tutte le altre: entra nella pila,
        il pulsante indietro torna alla Home, e il nome nella fascia diventa
        quello dell'articolo.

        IL TITOLO VIENE DALLA VOCE DELLA CARD
        ---------------------------------------
        Non si rilegge la pagina per prendere il titolo: si usa quello che la
        card aveva gia', che e' il titolo scritto dal sito.  Rileggere la
        pagina per un titolo significa due richieste per una cosa che si ha
        gia' in mano, e un titolo che cambia fra le due non si capisce quale
        delle due sia giusto.
        """
        try:
            titolo = self._titolo_notizia(indirizzo)
            schermata = NotiziaView(indirizzo, titolo)
            # I link e l'audio restano nell'app, non nel sito.  I collegamenti
            # si fanno **prima** di `carica`: una pagina puo' finire di
            # caricarsi mentre la finestra sta ancora sistemando la schermata,
            # e un segnale emesso in quel momento non troverebbe nessuno.
            schermata.linkPremuto.connect(self._link_notizia_premuto)
            # La notizia non manda piu' un comando «suona»: dice solo se
            # l'audio c'e'.  Il tasto e' nella barra viola, e lo mostra
            # `_aggiorna_strumenti_per_schermata`.
            schermata.audioTrovato.connect(
                lambda _url: self._aggiorna_strumenti_per_schermata())
            schermata.audioAssente.connect(
                self._aggiorna_strumenti_per_schermata)
            schermata.carica()
            self.navigate(schermata)
            self.set_titolo(titolo)
        except Exception:  # noqa: BLE001
            import traceback
            print("Notizie: non riesco ad aprire la pagina ⚠️")
            traceback.print_exc()
            self._mostra_messaggio("Non riesco ad aprire la notizia.")

    def _link_notizia_premuto(self, href: str) -> None:
        """Un link dentro la notizia e' stato premuto.

        I link che portano a jw.org si aprono come nuova notizia dentro
        l'app.  Quelli che portano a un versetto della Bibbia aprono la
        Bibbia.  Gli altri si ignorano: il sito ha link che qui non
        portano da nessuna parte (menu', home, ecc.) e che sono gia' stati
        tolti dal testo, ma per prudenza non si apre mai un browser
        esterno.
        """
        if not href or not isinstance(href, str):
            return
        # VERSI DELLA BIBBIA: si apre la Bibbia.
        # jw.org usa URL come .../bible/... o .../bibbia/...
        if "/bible/" in href or "/bibbia/" in href:
            self._apri_bibbia_da_link(href)
            return
        if "jw.org" in href or "jw-cdn" in href:
            # Notizia: si apre dentro l'app, come un'altra pagina.
            self._aperta_notizia(href)
            return
        # Altri link: si ignorano.

    def _apri_bibbia_da_link(self, href: str) -> None:
        """Apre la Bibbia dal link di una notizia.

        Si cerca di capire da quale libro e capitolo si parte.  jw.org usa
        URL come ``.../bible/study-bible/books/GEN/1/`` o
        ``.../bible/nwt/books/GEN/1/``.  Se non si riesce a capire, si apre
        la Bibbia e basta: l'utente la trova da solo.
        """
        import re

        # jw.org: /books/GEN/1/  o  /libri/GEN/1/
        match = re.search(r"/(?:books|libri)/([A-Z]{2,4})/(\d+)", href)
        if match:
            sigla = match.group(1).upper()
            try:
                capitolo = int(match.group(2))
            except (ValueError, TypeError):
                capitolo = 1
            # Si apre la Bibbia e si naviga al capitolo.
            self._sceglie_una_sezione("Bibbia")
            bible = self.sezioni.get("Bibbia")
            if bible is not None and hasattr(bible, "bible_books"):
                # Si cerca il libro per sigla.
                for indice, libro in enumerate(bible.bible_books):
                    if getattr(libro, "keySymbol", "") == sigla or \
                       getattr(libro, "shortName", "").upper() == sigla:
                        bible.bible_book_index = indice
                        capitoli = bible._capitolo_scelto if hasattr(bible, "_capitolo_scelto") else None
                        if capitoli is not None:
                            try:
                                capitoli(capitolo)
                            except Exception:  # noqa: BLE001
                                pass
                        return
            return
        # Non si è capito il libro: si apre la Bibbia e basta.
        self._sceglie_una_sezione("Bibbia")
        self._mostra_messaggio("Il versetto si apre nella Bibbia.")

    def _audio_notizia_richiesto(self, url: str) -> None:
        """L'audio della notizia va suonato nell'app, non nel sito.

        MINI PLAYER, NON LETTORE GRANDE
        -------------------------------
        Una notizia non e' un media da guardare: si ascolta mentre si legge, e
        il lettore grande coprirebbe l'articolo.  Si usa quindi direttamente
        il motore che alimenta la striscia in fondo alla finestra.  La
        striscia compare da sola quando il motore dice che sta suonando.
        """
        if not url:
            return
        # Il titolo e la copertina sono quelli dell'articolo aperto, non
        # quelli dell'indirizzo dell'mp3.
        titolo = "Audio"
        immagine = ""
        corrente = None
        try:
            corrente = self.pila.currentWidget()
            if isinstance(corrente, NotiziaView):
                titolo = corrente.titolo or titolo
                immagine = corrente.immagine_articolo or ""
        except (AttributeError, RuntimeError):
            pass
        # LA X DI QUESTO AUDIO RIPORTA ALL'ARTICOLO
        # -----------------------------------------
        # L'audio parte dalla notizia, che non e' una sezione: se il ritorno
        # restasse un nome di sezione, la X riporterebbe alla Home — che e'
        # il difetto segnalato.  Si segna la schermata vera.  La promessa
        # della X resta valida anche se l'utente passa a un'altra sezione
        # mentre ascolta.
        self._ritorno = None
        self._provenienza = None
        self._ritorno_schermata = (corrente
                                   if isinstance(corrente, NotiziaView) else None)
        # Si costruisce una voce minima per il lettore dell'app.  `trackImage`
        # e' lo stesso campo che usano le voci dei media: cosi' la striscia e
        # il lettore grande mostrano la copertina dell'articolo senza una
        # ricerca separata.
        voce = {
            "url": url,
            "title": titolo,
            "formato": "AUDIO",
            "tipo": "audio",
            "mimetype": "audio/mpeg",
        }
        if immagine:
            voce["trackImage"] = {"url": immagine}
        try:
            self._motore.suona(voce)
        except Exception:  # noqa: BLE001
            import traceback
            print("Notizie: errore nel suonare l'audio ⚠️")
            traceback.print_exc()

    def _titolo_notizia(self, indirizzo: str) -> str:
        """Il titolo dell'articolo, da quello che la card aveva gia'.

        Se non c'e' — il collegamento e' arrivato da un'altra parte — si
        ricade sul pezzo finale dell'indirizzo, che e' la parte con il
        titolo nella forma con cui il sito lo scrive.  Non e' un titolo
        composto: e' il titolo del sito con i trattini al posto degli
        spazi, ed e' quello che c'e'.  Meglio una cosa imperfetta e vera
        che una scritta a mano.
        """
        sezione = self.sezioni.get("Home")
        titolo = getattr(sezione, "_titolo_notizia", None)
        if callable(titolo):
            try:
                trovato = titolo(indirizzo)
            except Exception:  # noqa: BLE001
                trovato = ""
            if trovato:
                return trovato
        pezzo = indirizzo.rstrip("/").rsplit("/", 1)[-1]
        return pezzo.replace("-", " ").replace("%20", " ").strip()

    def _aperta_da_scaricati(self, pub, apri: str) -> None:
        """Una riga di Scaricati e' stata premuta.

        Tre strade, e una sola regola che vale anche per i Preferiti della
        Home: solo testo -> il pacchetto, audio -> la scheda Audio, video ->
        la scheda Video.

        LA SCELTA LA FA LA RIGA, NON QUI
        ---------------------------------
        La riga ha guardato dentro il pacchetto e sa cosa c'e'.  Qui si
        esegue, e non si decide: se qui si ricontasse, due posti
        conterrebbero la stessa regola e il giorno che cambiasse una, quella
        che non cambiava diventerebbe quella giusta solo per meta'.

        IL PACCHETTO PRIMA, PERCHE' E' QUELLO CHE C'E' DI CERTO
        ---------------------------------------------------------
        Per aprire la pubblicazione non serve che il pacchetto sia sul disco:
        la sezione Pubblicazioni funziona anche per una pubblicazione non
        scaricata.  Quindi se il pacchetto manca, o non si riesce ad aprirlo,
        si apre la sezione e si lascia che dica lei cosa non trova, invece
        di restare li' a non fare niente.
        """
        if apri in ("audio", "video"):
            self._apre_media(pub, scheda=0 if apri == "audio" else 1)
            return

        sezione = self._catalogo()
        if sezione is None or not hasattr(sezione, "apri_pubblicazione"):
            return
        try:
            sezione.apri_pubblicazione(pub)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Scaricati: non riesco ad aprire {pub} ⚠️")
            traceback.print_exc()

    def _apre_un_media_scaricato(self, percorso, titolo: str) -> None:
        """Un video sciolto scaricato si suona nella sezione Multimedia.

        PERCHE' PROPRIO MULTIMEDIA, E NON QUI
        ---------------------------------------
        Il lettore vero — con play, pausa e posizione — sta nella sezione
        Multimedia, sopra la lista.  Qui non c'e' un lettore, e crearne uno
        coi comandi in una sezione che non ha la sua lista sarebbe
        ricostruire la sezione a meta'.

        Prima questo gesto chiamava `Lettore().suona(...)`: un motore nuovo
        di zecca, con la sua porta audio, il suo decoder e **nessuno** che lo
        guardasse.  Il video partiva in quel motore invisibile, e quando la
        funzione tornava l'oggetto veniva buttato via mentre suonava — la
        sezione non mostrava niente e il programma poteva sparire senza
        messaggio (un `QMediaPlayer` distrutto mentre decodifica fa
        ``abort()`` in Qt).
        """
        sezione = self.sezioni.get("Biblioteca Digitale")
        if sezione is None or not hasattr(sezione, "suona_un_file"):
            return
        try:
            self._vai_a_multimedia()
            sezione.suona_un_file(percorso, titolo)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Media: non riesco a suonare il file {percorso} ⚠️")
            traceback.print_exc()

    def _apre_media(self, pub, scheda: int = 0) -> None:
        """Apre la sezione Multimedia sulla scheda giusta, con la pubblicazione.

        Si cambia sezione, e qui a differenza di `_media_per` e' voluto: l'utente
        ha premuto una riga che diceva «apri l'audio», quindi l'audio e' quello
        che vuole vedere adesso.  `_media_per` non cambia sezione perche' li
        l'utente sta leggendo e una sezione che sparisce gli nasconderebbe il
        testo: sono due momenti diversi e la regola cambia di conseguenza.

        La scheda si sceglie DOPO aver preparato la sezione: `carica()` parte
        il caricamento e `_ricostruisci()` ridipinge, quindi scegliere la scheda
        prima verrebbe perso al primo ridisegno.
        """
        sezione = self.sezioni.get("Biblioteca Digitale")
        if sezione is None or not hasattr(sezione, "apri_pubblicazione"):
            return
        try:
            self._vai_a_multimedia(navigare=True)
            sezione.apri_pubblicazione(pub, scheda)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Media: non riesco ad aprire i media di {pub} ⚠️")
            traceback.print_exc()

    def _media_per(self, pub) -> None:
        """Una pubblicazione e' stata scelta: i suoi media.

        Non si costruisce qui la sezione Media se non c'e'.  La finestra
        costruisce tutte le sezioni all'avvio, quindi di solito c'e'; ma se
        un domani la sezione venisse costruita piu' tardi, questa chiamata
        deve essere una nozione e non un altro modo di crashare.

        Non si cambia sezione: l'utente sta leggendo una pubblicazione e
        telo nasconderebbe.  I media si vedono quando l'utente li chiede,
        andando nella sezione Media, che a quel punto sa gia' cosa
        caricare.
        """
        sezione = self.sezioni.get("Biblioteca Digitale")
        if sezione is None or not hasattr(sezione, "carica"):
            return
        try:
            sezione.imposta_pubblicazione(pub)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Media: non riesco a preparare {pub} ⚠️")
            traceback.print_exc()

    def _annulla_scarico(self) -> None:
        """«Annulla scaricamento»: ferma il download in corso e ripulisce."""
        from Utility.FileDownloader import FileDownloader
        FileDownloader.annulla()
        self.mostra_toast("Annullo lo scaricamento…", "info")
        # Rete di sicurezza: se nessun download era davvero in corso, il segnale
        # non deve restare alzato e bloccare i prossimi.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(60000, FileDownloader.riparti)

    def _scarica_da_home(self, voce: dict) -> None:
        """Un "Scarica" e' stato premuto nella sezione Novita' dentro la Home.

        IL PULSANTE NON FACEVA NIENTE
        ------------------------------
        `UpdatesView.scaricaRichiesta` emetteva e nessuno lo ascoltava: il
        pulsante "Scarica" della sezione Novita' non scaricava niente, e
        apparentemente funzionava perche' premendolo non succedeva niente e
        un pulsante che non da' segni sembra un pulsante che non ha ancora
        finito.

        Qui si chiama il download vero, quello di `PubView._scarica_pub`, che
        scarica il .jwpub e poi i testi dei capitoli.  Non se ne scrive una
        copia: sono due richieste in sequenza e il testo si sa dove metterlo
        solo dopo che il pacchetto c'e'.

        LA VOCE CHE ARRIVA
        -----------------
        `Novita'` manda un dizionario — sigla, lingua, titolo, pacchetto — e
        non un oggetto `Publication`.  Qui si cerca la riga vera nel
        catalogo: il download ha bisogno del numero del pacchetto e dell'anno,
        e nel dizionario non ci sono.  Se la riga non c'e' non si scarica
        niente e si dice: scaricare al buio sarebbe scaricare la cosa
        sbagliata.
        """
        if not isinstance(voce, dict):
            return
        self._scarica_una_pubblicazione(voce)

    def _proponi_video(self, indirizzo: str, testo: str = "") -> None:
        """Un video nel testo e' stato premuto: popup al centro, senza cornice.

        Riprodurlo (dal disco se c'e', altrimenti in streaming) o scaricarlo,
        scegliendo la risoluzione.  Se e' gia' scaricato si offre solo di
        riprodurlo.  Alla chiusura del video la X riporta all'articolo.
        """
        from urllib.parse import parse_qs, urlsplit

        from PyQt6.QtGui import QCursor

        from Utility import MediaScaricati

        dati = parse_qs(urlsplit(indirizzo).query)
        sigla = (dati.get("pub") or [""])[0]
        traccia = (dati.get("track") or [""])[0]
        lingua = (dati.get("langwritten") or [Lingua.corrente_simbolo()])[0]
        if not sigla or not traccia.isdigit():
            self._mostra_messaggio("Non riesco a capire quale video aprire.")
            return
        traccia = int(traccia)

        titolo = ""
        try:
            voce = CatalogoMedia.voce_di(sigla, lingua, traccia)
            titolo = (voce or {}).get("title") or ""
        except Exception:  # noqa: BLE001
            titolo = ""
        testo_utile = testo if len(testo) > 12 else ""
        titolo = titolo or testo_utile or f"Video {sigla}, traccia {traccia}"
        try:
            scaricato = MediaScaricati.file_di(sigla, lingua, traccia, "VIDEO")
        except Exception:  # noqa: BLE001
            scaricato = None

        scelta = self._popup_video(
            titolo,
            "E' gia' scaricato." if scaricato else "Vuoi riprodurlo o scaricarlo?",
            "Riproduci" if scaricato else "Riproduci in streaming",
            None if scaricato else "Scarica…")
        if scelta == "riproduci":
            self._apre_una_card_media(sigla, lingua, traccia)
        elif scelta == "scarica":
            self._scegli_la_risoluzione(
                {"sigla": sigla, "lingua": lingua, "traccia": traccia,
                 "titolo": titolo}, QCursor.pos())

    def _popup_video(self, titolo: str, domanda: str, riproduci: str,
                     scarica: str | None) -> str:
        """Popup nei colori del tema: testi interi, solo i tasti sono viola."""
        from PyQt6.QtWidgets import QDialog

        c = tema.colori(tema.tema_attivo())
        dialogo = QDialog(self)
        dialogo.setObjectName("popupVideo")
        dialogo.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialogo.setStyleSheet(
            f"#popupVideo {{ background-color: {c['pannello']};"
            f" border: 1px solid {c['bordo']}; border-radius: 8px; }}"
            f" QLabel {{ background: transparent; color: {c['testo']}; font-size: 13px; }}"
            " QPushButton { background-color: #64398b; color: white; border: none;"
            " border-radius: 4px; padding: 7px 16px; font-size: 13px; }"
            " QPushButton:hover { background-color: #a77fd4; }"
            f" QPushButton#annulla {{ background: transparent; color: {c['testo']};"
            f" border: 1px solid {c['bordo']}; }}"
            f" QPushButton#annulla:hover {{ border-color: {c['testo']}; }}")
        colonna = QVBoxLayout(dialogo)
        colonna.setContentsMargins(22, 18, 22, 16)
        colonna.setSpacing(10)
        t = QLabel(titolo, dialogo)
        t.setWordWrap(True)
        t.setStyleSheet("font-weight: 600; font-size: 14px;")
        colonna.addWidget(t)
        colonna.addWidget(QLabel(domanda, dialogo))
        righe = QHBoxLayout()
        righe.setSpacing(8)
        esito = {"v": ""}

        def aggiungi(testo: str, valore: str, nome: str = "") -> None:
            b = QPushButton(testo, dialogo)
            if nome:
                b.setObjectName(nome)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda: (esito.update(v=valore), dialogo.accept()))
            righe.addWidget(b)

        aggiungi(riproduci, "riproduci")
        if scarica:
            aggiungi(scarica, "scarica")
        righe.addStretch(1)
        aggiungi("Annulla", "", "annulla")
        colonna.addLayout(righe)
        dialogo.setMinimumWidth(380)
        dialogo.setMaximumWidth(560)
        dialogo.adjustSize()
        dialogo.move(self.mapToGlobal(self.rect().center()) - dialogo.rect().center())
        dialogo.exec()
        return esito["v"]

    def prepara_in_anticipo(self) -> None:
        """Dopo l'apertura della finestra, prepara quello che il primo clic pagherebbe.

        - una pagina web vuota: avvia il processo che disegna le pagine, che
          altrimenti parte alla prima apertura di un articolo;
        - il catalogo delle pubblicazioni: costruirlo costa ~0,25 s, una volta.

        Si chiama a finestra gia' mostrata e con la grafica libera: non allunga
        l'avvio, e il primo articolo si apre come tutti gli altri.
        """
        try:
            from WebBrowserView import WebView
            self._web_caldo = WebView()
            self._web_caldo.setHtml("<html><body></body></html>")
            QTimer.singleShot(400, self._catalogo)
            QTimer.singleShot(2500, self._indicizza_il_testo)
            self._controlla_la_rete()
            self._timer_rete = QTimer(self)
            self._timer_rete.timeout.connect(self._controlla_la_rete)
            self._timer_rete.start(60_000)
        except Exception:  # noqa: BLE001 - e' solo una preparazione
            pass

    # ------------------------------------------------------------------
    # LE CUFFIE DENTRO UNA PUBBLICAZIONE
    # ------------------------------------------------------------------

    def _voci_cuffie_della_schermata(self, schermata) -> list:
        """Audio e video della pubblicazione che si legge, adattati a cio' che c'e'.

        Vuota = niente da mostrare (il pulsante sparisce).  Senza internet restano
        solo i file gia' scaricati: streaming, scarico e cambio lingua si tolgono.
        """
        pub = getattr(schermata, "pub", None)
        if pub is None:
            return []
        try:
            if getattr(pub, "isBible", False):
                voci = self._voci_cuffie_bibbia(pub)
            else:
                sigla = getattr(pub, "keySymbol", "") or ""
                lingua = Lingua.da_numero(getattr(pub, "mepsLanguageId", Lingua.PREDEFINITA))
                voci = None
                if sigla == "sjj":
                    voci = self._voci_cuffie_cantico(getattr(schermata, "document", None), lingua)
                voci = self._voci_audio_della_pub(schermata, pub, sigla, lingua)
                if not voci:
                    voci = self._voci_del_menu_cuffie((sigla, lingua), True) if sigla else []
        except Exception:  # noqa: BLE001 - un menu che non si costruisce non ferma la lettura
            return []
        return voci if Rete.noto() else self._senza_rete(voci)

    def _suona_video_veloce(self, sigla: str, lingua: str, traccia: int, formato: str) -> None:
        """Un video di una pagina parte chiedendo al server solo la sua traccia.

        Per l'audio e per ogni imprevisto resta la strada di sempre (`_ascolta_media`).
        """
        sezione = self.sezioni.get("Biblioteca Digitale")
        ripiego = lambda: self._ascolta_media(sigla, lingua, traccia, formato)  # noqa: E731
        if formato != "VIDEO" or not hasattr(sezione, "suona_traccia"):
            ripiego()
            return
        try:
            self._attendi_il_video()
            sezione.suona_traccia(sigla, lingua, traccia, 1, ripiego)
        except Exception:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            ripiego()

    def _media_del_documento(self, sigla: str, lingua: str, numero: int, traccia: int,
                             formato: str, titolo: str, scarica: bool,
                             chiave=None, automatico: bool = False,
                             altezza: int = 0) -> None:
        """Streaming o scaricamento di un media citato; chiede il file al server."""
        if not numero:
            if scarica:
                self._scarica_media_dal_server(sigla, lingua, traccia, formato,
                                               chiave=chiave, automatico=automatico,
                                               altezza=altezza)
            else:
                self._suona_video_veloce(sigla, lingua, traccia, formato)
            return
        from Utility import MepsAPI
        from Utility.Extensions.Ext_DispatchQueue import background

        scelte: list = []

        def lavoro() -> None:
            try:
                voci = MepsAPI.media(sigla, lingua, str(numero))
            except Exception:  # noqa: BLE001 - senza rete: nessuna scelta
                voci = []
            for voce in voci:
                if MepsAPI.traccia_numero(voce) != traccia or not _del_formato(voce, formato):
                    continue
                url = (voce.get("file") or {}).get("url") or ""
                if url:
                    scelte.append((_nome_risoluzione(voce), url, _peso_del_file(voce),
                                   voce.get("title") or ""))
            scelte.sort(key=lambda x: _altezza_risoluzione(x[0]), reverse=True)

        def arrivati() -> None:
            if not scelte:
                self.mostra_toast(f"Il server non ha un file per «{titolo}»",
                                  "warning", 5000)
                if scarica and chiave is not None:
                    from Utility import AvanzamentoMedia
                    AvanzamentoMedia.canale().finito.emit(chiave, "errore")
                return
            if scarica and len(scelte) > 1 and formato != "AUDIO" \
                    and not automatico and not altezza:
                # Una scelta sola (non «Scarica tutti»): l'utente sceglie la
                # risoluzione, come in tutto il resto dell'app.
                menu = QMenu(self)
                menu.setObjectName("menuRisoluzioni")
                for n, u, pe, nv in scelte:
                    menu.addAction(n).triggered.connect(
                        lambda _c=False, u=u, pe=pe, nv=nv:
                        self._scarica_un_video(u, nv or titolo, pe, None, formato,
                                               chiave=chiave))
                self._menu_aperto = menu
                if menu.exec(QCursor.pos()) is None and chiave is not None:
                    from Utility import AvanzamentoMedia
                    AvanzamentoMedia.canale().finito.emit(chiave, "annullato")
                return
            _nome, url, peso, nome_vero = _per_altezza(scelte, altezza if scarica else 0)
            nome = nome_vero or titolo
            if scarica:
                self._scarica_un_video(url, nome, peso, None, formato, chiave=chiave)
            elif formato == "AUDIO":
                self._suona_audio_in_striscia(url, nome)
            else:
                self._apre_un_media_scaricato(url, nome)

        background(lavoro, completion=arrivati)

    def _voci_audio_della_pub(self, schermata, pub, sigla: str, lingua: str) -> list:
        """Ascolto (streaming o scaricato) di QUALUNQUE pubblicazione che ha audio.

        L'elenco viene dal server (una volta, poi si ricorda).  Mentre arriva
        non si mostra niente; quando e' pronto la fascia si aggiorna da sola.
        Per un numero con una traccia per settimana si offre quella della
        pagina aperta, altrimenti tutte le tracce.
        """
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        tag = str(int(getattr(pub, "issueTagNumber", 0) or 0))
        numero = "" if tag == "0" else (tag[:-2] if tag.endswith("00") else tag)
        chiave = (sigla, lingua, numero)
        cache = self.__dict__.setdefault("_audio_pub", {})
        if chiave not in cache:
            if not Rete.noto():
                return []
            cache[chiave] = None
            self._cerca_audio_pub(chiave)
            return []
        tracce = cache[chiave] or []
        documento = getattr(schermata, "document", None)
        tracce = [t for t in tracce if _traccia_della_pagina(t[1], documento)]
        radice = get_documents_directory()
        voci: list = []
        for traccia, titolo, url, peso in tracce:
            file = radice / url.rsplit("/", 1)[-1]
            if file.is_file():
                voci.append(("riga", f"Ascolta «{titolo}»",
                             self._richiamo(self._suona_audio_in_striscia, str(file), titolo)))
                continue
            voci.append(("sotto", titolo, [
                ("Ascolta in streaming",
                 self._richiamo(self._suona_audio_in_striscia, url, titolo)),
                ("Scarica l'audio",
                 self._richiamo(self._scarica_un_video, url, titolo, peso, None, "AUDIO")),
            ]))
        return voci

    def _cerca_audio_pub(self, chiave: tuple) -> None:
        from Utility import MepsAPI
        from Utility.Extensions.Ext_DispatchQueue import background

        sigla, lingua, numero = chiave
        trovate: list = []

        def lavoro() -> None:
            try:
                voci = MepsAPI.media(sigla, lingua, numero or None)
            except Exception:  # noqa: BLE001
                voci = []
            for voce in voci:
                if not str(voce.get("mimetype") or "").startswith("audio/"):
                    continue
                url = (voce.get("file") or {}).get("url") or ""
                if url:
                    titolo = " ".join(str(voce.get("title") or "").replace("\u200b", "").split())
                    trovate.append((MepsAPI.traccia_numero(voce), titolo or sigla,
                                    url, _peso_del_file(voce)))
            trovate.sort(key=lambda t: t[0])

        def finito() -> None:
            self.__dict__["_audio_pub"][chiave] = trovate
            try:
                self._aggiorna_strumenti_per_schermata()
            except RuntimeError:
                pass

        background(lavoro, completion=finito)

    def _apri_contenuti(self, vista) -> None:
        """La schermata dei contenuti multimediali, sopra la pagina."""
        self.navigate(vista)

    def _contenuto_apri(self, v: dict) -> None:
        """Riproduce un video o un audio dell'elenco: dal disco, o in streaming."""
        titolo = v.get("titolo") or ""
        if v.get("file"):
            azione = (self._suona_audio_in_striscia if v["tipo"] == "audio"
                      else self._apre_un_media_scaricato)
            azione(v["file"], titolo)
            return
        self._media_del_documento(v["sigla"], v["lingua"], v["numero"], v["traccia"],
                                  v["formato"], titolo, False)

    def _contenuto_scarica(self, v: dict) -> None:
        """Scarica un media di un elenco di contenuti (pagina o timer).

        `automatico` (lo mette «Scarica tutti» del timer) prende da solo la
        risoluzione piu' alta: con dieci video non si aprono dieci menu'.
        L'avanzamento va anche al canale di `AvanzamentoMedia`, cosi' chi ha
        la riga di quel media (il timer) ci mette la barra.
        """
        from Utility import AvanzamentoMedia
        self._media_del_documento(v["sigla"], v["lingua"], v["numero"], v["traccia"],
                                  v["formato"], v.get("titolo") or "", True,
                                  chiave=AvanzamentoMedia.chiave_di(v),
                                  automatico=bool(v.get("automatico")),
                                  altezza=int(v.get("altezza") or 0))

    def _voci_cuffie_cantico(self, documento, lingua: str):
        """Audio e video del cantico che si legge, o None se la pagina non e' un cantico.

        Nel catalogo i media dei cantici stanno sotto «sjjm», con traccia uguale al
        numero del cantico; il numero si ricava dal documento (1102016800 + N).
        """
        from Utility import MediaScaricati
        if documento is None:
            return None
        numero = int(getattr(documento, "documentId", 0) or 0) - 1102016800
        if not 1 <= numero <= 200:
            return None
        esistono = {formato for n, formato in CatalogoMedia.tracce_di("sjjm", lingua)
                    if n == numero}
        if not esistono:
            return None
        titolo = ((CatalogoMedia.voce_di("sjjm", lingua, numero) or {}).get("title")
                  or f"Cantico {numero}")
        voci: list = []
        scaricare: list = []
        for formato, verbo in (("AUDIO", "Ascolta"),):
            if formato not in esistono:
                continue
            file = MediaScaricati.file_di("sjjm", lingua, numero, formato)
            if file is not None:
                azione = (self._suona_audio_in_striscia if formato == "AUDIO"
                          else self._apre_un_media_scaricato)
                voci.append(("riga", f"{verbo} «{titolo}»",
                             self._richiamo(azione, str(file), titolo)))
                continue
            voci.append(("riga", f"{verbo} «{titolo}» in streaming",
                         self._richiamo(self._ascolta_media, "sjjm", lingua, numero, formato),
                         True))
            scaricare.append(("riga", f"Scarica {'l\'audio' if formato == 'AUDIO' else 'il video'}"
                                      f" del cantico {numero}",
                              self._richiamo(self._scarica_media_dal_server,
                                             "sjjm", lingua, numero, formato), True))
        if scaricare:
            voci.append(None)
            voci.extend(scaricare)
        return voci

    @staticmethod
    def _senza_rete(voci: list) -> list:
        tenute = [v for v in voci
                  if v is None or (v[0] == "riga" and not (len(v) > 3 and v[3]))]
        pulite: list = []
        for v in tenute:
            if v is None and (not pulite or pulite[-1] is None):
                continue
            pulite.append(v)
        while pulite and pulite[-1] is None:
            pulite.pop()
        return pulite

    def _nome_libro_bibbia(self, libro: int) -> str:
        nomi = self.__dict__.setdefault("_nomi_libri_bibbia", {})
        if libro not in nomi:
            import re as _re
            nome = f"Libro {libro}"
            cartella = JWPubManager.bible_package()
            try:
                testo = (cartella / str(libro) / "1.html").read_text(encoding="utf-8")
                trovato = _re.search(r"<h1[^>]*>(.*?)</h1>", testo, _re.S)
                if trovato:
                    nome = _re.sub(r"<[^>]+>", "", trovato.group(1)).strip() or nome
            except (OSError, AttributeError):
                pass
            nomi[libro] = nome
        return nomi[libro]

    def _voci_cuffie_bibbia(self, pub) -> list:
        """Audio del capitolo che si legge e video introduttivo del libro."""
        from Utility import MediaScaricati
        libro, capitolo = int(pub.book or 0), int(pub.chapter or 0)
        if not libro or not capitolo:
            return []
        lingua = Lingua.da_numero(getattr(pub, "mepsLanguageId", 0) or Lingua.corrente_id())
        nome = self._nome_libro_bibbia(libro)
        titolo = f"{nome} {capitolo}"
        voci: list = []
        scaricare: list = []

        file = MediaScaricati.file_di("nwt", lingua, [libro, capitolo], "AUDIO")
        if file is not None:
            voci.append(("riga", f"Ascolta {titolo}",
                         self._richiamo(self._suona_audio_in_striscia, str(file), titolo)))
        else:
            voci.append(("riga", f"Ascolta {titolo} in streaming",
                         self._richiamo(self._audio_bibbia, libro, capitolo, lingua, False, titolo),
                         True))
            scaricare.append(("riga", f"Scarica l'audio di {titolo}",
                              self._richiamo(self._audio_bibbia, libro, capitolo, lingua, True, titolo),
                              True))

        introduzione = self._video_introduttivo(libro, lingua)
        if introduzione is not None:
            traccia, titolo_video = introduzione
            video = MediaScaricati.file_di("nwtsv", lingua, traccia, "VIDEO")
            if video is not None:
                voci.append(("riga", f"Guarda «{titolo_video}»",
                             self._richiamo(self._apre_un_media_scaricato, str(video), titolo_video)))
            else:
                voci.append(("riga", f"Guarda «{titolo_video}» in streaming",
                             self._richiamo(self._ascolta_media, "nwtsv", lingua, traccia, "VIDEO"),
                             True))
                scaricare.append(("riga", f"Scarica «{titolo_video}»",
                                  self._richiamo(self._scarica_media_dal_server,
                                                 "nwtsv", lingua, traccia, "VIDEO"), True))
        if scaricare:
            voci.append(None)
            voci.extend(scaricare)
        return voci

    @staticmethod
    def _video_introduttivo(libro: int, lingua: str):
        """(traccia, titolo) del video «Introduzione a <libro>», o None.

        Si abbina per **numero**, non per nome: i video hanno come traccia il
        numero del libro per dieci (Genesi 10, Geremia 240, Matteo 400,
        Rivelazione 660), piu' cinque per la versione con audiodescrizione.  I
        nomi non combaciano («Vangelo secondo Matteo» e «Matteo»).
        """
        candidati = sorted((n for n, formato in CatalogoMedia.tracce_di("nwtsv", lingua)
                            if formato == "VIDEO" and n >= 10 and n // 10 == libro),
                           key=lambda n: n % 10)
        if not candidati:
            return None
        numero = candidati[0]
        titolo = (CatalogoMedia.voce_di("nwtsv", lingua, numero) or {}).get("title") \
            or f"Introduzione al libro {libro}"
        return numero, titolo

    def _audio_bibbia(self, libro: int, capitolo: int, lingua: str,
                      solo_scarica: bool, titolo: str) -> None:
        """Trova l'MP3 del capitolo sul server e lo suona o lo scarica."""
        from Utility import MepsAPI
        from Utility.Extensions.Ext_DispatchQueue import background
        trovato: dict = {}

        def lavoro() -> None:
            try:
                for voce in MepsAPI.capitolo("nwt", libro, capitolo, lingua):
                    if (MepsAPI._formato(voce) == "MP3"
                            and MepsAPI.traccia_numero(voce) == capitolo):
                        trovato.update(url=(voce.get("file") or {}).get("url") or "",
                                       peso=int(voce.get("filesize") or 0))
                        break
            except Exception:  # noqa: BLE001
                pass

        def fatto() -> None:
            if not trovato.get("url"):
                self._mostra_messaggio("Non riesco a raggiungere l'audio: controlla la connessione.")
            elif solo_scarica:
                self._scarica_un_video(trovato["url"], titolo, trovato.get("peso", 0), None, "mp3")
            else:
                self._suona_audio_in_striscia(trovato["url"], titolo)

        background(lavoro, completion=fatto)

    def _ascolta_audio_qui(self, sigla: str, lingua: str, traccia) -> None:
        """Un audio di una pubblicazione si ascolta dalla striscia, senza lasciare la pagina."""
        from Utility import MediaScaricati, MepsAPI
        from Utility.Extensions.Ext_DispatchQueue import background
        titolo = ((CatalogoMedia.voce_di(sigla, lingua, traccia) or {}).get("title")
                  or f"{sigla} (traccia {traccia})")
        file = MediaScaricati.file_di(sigla, lingua, traccia, "AUDIO")
        if file is not None:
            self._suona_audio_in_striscia(str(file), titolo)
            return
        url: list = []

        def lavoro() -> None:
            try:
                for voce in MepsAPI.media(sigla, lingua):
                    if (MepsAPI._formato(voce) == "MP3"
                            and MepsAPI.traccia_numero(voce) == int(traccia)):
                        url.append((voce.get("file") or {}).get("url") or "")
                        break
            except Exception:  # noqa: BLE001
                pass

        def fatto() -> None:
            if url and url[0]:
                self._suona_audio_in_striscia(url[0], titolo)
            else:
                self._mostra_messaggio("Non riesco a raggiungere l'audio: controlla la connessione.")

        background(lavoro, completion=fatto)

    def _suona_audio_in_striscia(self, sorgente: str, titolo: str) -> None:
        """Fa partire un audio (indirizzo o file) nella striscia in fondo.

        Non cambia sezione e non apre il lettore grande: chiudendo l'audio si
        resta nella pubblicazione.
        """
        corrente = self.pila.currentWidget()
        self._ritorno = None
        self._provenienza = None
        self._ritorno_schermata = corrente
        voce = {"title": titolo, "formato": "AUDIO", "tipo": "audio",
                "mimetype": "audio/mpeg"}
        voce["url" if str(sorgente).startswith(("http://", "https://")) else "percorso"] = sorgente
        try:
            self._motore.suona(voce)
        except Exception:  # noqa: BLE001
            import traceback
            print("Audio: errore nel suonare ⚠️")
            traceback.print_exc()

    def _apri_ricerca_locale(self, articolo, pulsante=None) -> None:
        """Il campo di ricerca sotto la lente, per la pubblicazione che si legge."""
        from SubViews.RicercaLocale import RicercaLocale
        pub = articolo.pub
        sigla = getattr(pub, "keySymbol", "") or ""
        nome = ("la Bibbia" if getattr(pub, "isBible", False)
                else (getattr(pub, "title", "") or getattr(pub, "issueTitle", "") or sigla))
        vecchia = getattr(self, "_ricerca_locale", None)
        if vecchia is not None:
            try:
                vecchia.chiudi()
                vecchia.deleteLater()
            except RuntimeError:
                pass
        ricerca = self._ricerca_locale = RicercaLocale(self, sigla, nome)
        ricerca.scelto.connect(self._apri_risultato_ricerca)
        if pulsante is not None:
            punto = pulsante.mapTo(self, QPoint(pulsante.width(), pulsante.height() + 4))
        else:
            punto = QPoint(self.width() - 20, 100)
        ricerca.apri(punto)

    def _controlla_la_rete(self) -> None:
        """Aggiorna in secondo piano «c'e' internet?»; le cuffie la seguono."""
        from Utility.Extensions.Ext_DispatchQueue import background
        prima = Rete.noto()

        def dopo() -> None:
            if Rete.noto() != prima:
                try:
                    self._aggiorna_strumenti_per_schermata()
                except RuntimeError:
                    pass

        background(Rete.controlla, completion=dopo)

    def _indicizza_il_testo(self) -> None:
        """Tiene pronto l'indice della ricerca nel testo, in secondo piano."""
        from Utility import RicercaTesto
        from Utility.Extensions.Ext_DispatchQueue import background
        background(RicercaTesto.aggiorna_indice)

    def _apri_playlist(self) -> None:
        """Il pulsante Playlist di «Ricerche»: l'elenco delle playlist."""
        vista = PlaylistView()
        vista.riproduciRichiesto.connect(self._riproduci_playlist)
        self.navigate(vista)

    def _riproduci_playlist(self, elementi: list, indice: int) -> None:
        """Suona una playlist da un elemento, rispettando il taglio di ognuno."""
        from Utility.CodaPlaylist import CodaPlaylist
        coda = getattr(self, "_coda_playlist", None)
        if coda is None:
            coda = self._coda_playlist = CodaPlaylist(self._apre_un_media_scaricato, self)
        if not coda.parti(elementi, indice):
            self._mostra_messaggio("I file di questa playlist non ci sono piu' sul disco.")

    def _apri_documento_bibbia(self, meps: int, titolo: str) -> None:
        """Una voce di Introduzione, Indice o Appendici della Bibbia.

        Se la pagina e' gia' scaricata si apre subito; altrimenti la si scarica
        (azione esplicita dell'utente, quindi anche con "Offline" attivo) e poi
        si apre.
        """
        from Utility.Extensions.Ext_DispatchQueue import background
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        from Utility.FileDownloader import FileDownloader
        from Utility.JWPubManager import ARTICLES_DIR
        from Utility.WolLingua import url_documento
        def apri() -> None:
            if not self._apri_documento_locale(meps, "nwtsty", "Bibbia", titolo):
                self._mostra_messaggio("Non riesco a scaricare questa pagina.")
        if (get_documents_directory() / ARTICLES_DIR / f"{meps}.html").is_file():
            apri()
            return
        if not Rete.noto():
            self._mostra_messaggio("Serve internet per scaricare questa pagina.")
            return
        self._mostra_messaggio("Scarico la pagina…")
        def lavoro() -> None:
            url = url_documento(meps)
            if url:
                FileDownloader.download_article(
                    url=url, path=f"{ARTICLES_DIR}/{meps}.html")
        background(lavoro, completion=apri)

    def _apri_documento_locale(self, meps: int, sigla: str, nome: str,
                               titolo: str) -> bool:
        """Apre a schermo intero un documento scaricato.  False se non c'e'."""
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        if not meps or not (get_documents_directory() / "Documents_I"
                            / f"{meps}.html").is_file():
            return False
        pub = Publication(
            ID=0, keySymbol=sigla, year=0, mepsLanguageId=Lingua.corrente_id(),
            publicationTypeId=0, issueTagNumber=0, title=nome)
        self._apri_articolo(
            pub=pub, file_path=f"Documents_I/{meps}.html",
            prev_text=self._etichetta_indietro(),
            document=Document(ID=0, documentId=meps, title=titolo, contextTitle=None),
            ancora="")
        return True

    def _apri_risultato_ricerca(self, r: dict) -> None:
        """Un risultato della ricerca nel testo: un versetto o un documento."""
        from types import SimpleNamespace
        if r.get("tipo") == "b":
            self._apri_posizione_bibbia(
                SimpleNamespace(mepsLanguageId=Lingua.corrente_id(),
                                identifier=int(r.get("verso") or 0)),
                int(r["libro"]), int(r["cap"]))
        elif not self._apri_documento_locale(int(r.get("meps") or 0),
                                             r.get("sigla") or "", r.get("titolo") or "",
                                             r.get("titolo") or ""):
            self._mostra_messaggio("Questo testo non e' piu' scaricato.")

    def _apri_riferimento_completo(self, voce) -> None:
        """La barra del riquadro dei riferimenti: apre la pubblicazione intera.

        - un versetto apre la Bibbia al capitolo, sul versetto;
        - un documento gia' scaricato si apre a schermo intero;
        - una pubblicazione non scaricata chiede se scaricarla: si legge solo
          scaricata, non in linea.
        """
        from types import SimpleNamespace

        from Utility import Copertine

        if voce.libro and voce.capitolo:
            self._apri_posizione_bibbia(
                SimpleNamespace(mepsLanguageId=Lingua.corrente_id(),
                                identifier=voce.versetto),
                voce.libro, voce.capitolo)
            return

        sigla = voce.simbolo
        nome = voce.pubblicazione or sigla
        if self._apri_documento_locale(voce.documento, sigla, nome, voce.titolo):
            return

        trovata = self._cerca_pubblicazione(sigla, Lingua.corrente_id(), "")
        senza_numero = [p for p in getattr(self._catalogo(), "_tutto", []) or []
                        if p.keySymbol == sigla and p.issueTagNumber == 0]
        if trovata is None or not senza_numero:
            self._mostra_messaggio(
                f"«{nome}» non si puo' scaricare da qui: cercala nella Biblioteca.")
            return
        if Copertine.pacchetto_locale(trovata):
            self._apri_pubblicazione_scelta(trovata)
            return

        ConfermaApp.chiedi(
            self, "Pubblicazione non scaricata",
            f"«{nome}» non è scaricata.\n\nVuoi scaricarla adesso?", "Scarica",
            lambda: self._scarica_una_pubblicazione({
                "sigla": sigla, "lingua": Lingua.corrente_simbolo(),
                "numero": "", "titolo": nome, "apri": True}))

    def _apri_pubblicazione_scelta(self, pub) -> None:
        """Apre l'elenco dei capitoli di una pubblicazione gia' scaricata."""
        sezione = self._catalogo()
        if sezione is not None:
            sezione.apri_pubblicazione(pub)

    def _scarica_una_pubblicazione(self, voce: dict) -> None:
        """Scarica il JWPUB di una voce, e nient'altro.

        Il pezzo di `_scarica_da_home` che cerca la riga nel catalogo e chiama
        `PubView.scarica`.  E' qui, e non dentro `_scarica_da_home`, perche' la
        nuvoletta delle card delle pubblicazioni fa **esattamente** la stessa
        cosa: scaricare al buio sarebbe scaricare la cosa sbagliata.
        """
        sigla = voce.get("sigla") or ""
        lingua = voce.get("lingua") or Lingua.corrente_simbolo()
        numero = Lingua.da_simbolo(lingua)

        # Il numero del numero, se la voce ce l'ha.  Per un periodico e' la
        # cosa che distingue "dicembre 2026" da "marzo 2026", e senza questa
        # riga sotto la ricerca prenderebbe il primo numero della pila:
        # scaricare "La Torre di Guardia, dicembre 2026" porterebbe via un
        # numero diverso, dentro la cartella di quel numero, e la sezione
        # Scaricati mostrerebbe una cosa che l'utente non ha chiesto.
        numero_edizione = voce.get("numero") or ""

        pub = self._cerca_pubblicazione(sigla, numero, numero_edizione)
        if pub is None:
            self._mostra_messaggio(
                f"Non trovo «{voce.get('titolo') or sigla}» nel catalogo, "
                f"quindi non so dove scaricarlo.")
            return

        sezione = self._catalogo()
        if sezione is None or not hasattr(sezione, "scarica"):
            return
        # Si ricorda quale pubblicazione scende, per accendere la barra sulla card.
        self._pub_in_scarico = pub
        sezione.scarica(pub, apri=bool(voce.get("apri", True)))

    # ------------------------------------------------------------------
    # LE CARD, PER CHI SCARICA
    # ------------------------------------------------------------------

    def _card_del_video(self, voce):
        """La card che mostra quella voce, o None.

        Serve per mettere la barra di scaricamento **sulla card giusta**: un
        video scaricato e' uno fra i venti che si vedono scorrendo, e senza
        questo la barra finirebbe su quella sbagliata o su nessuna.

        TRE POSTI, E L'ORDINE E' QUELLO DI UNA PERSONA
        -----------------------------------------------
        Prima la sezione **che si sta guardando** — la persona che ha premuto
        «Scarica» e' li', e la barra deve comparire sotto i suoi occhi.  Poi
        la Biblioteca Digitale, che e' dove stanno le card di Video e Audio,
        e infine la Home, che ha le card dei media e dei Preferiti.

        Prima guardava la Home **sola**: le pubblicazioni avevano la loro
        barra e i media no, perche' `_card_del_video` non sapeva che le card
        di una categoria stanno in un'altra sezione.  L'utente premeva
        «Scarica» su un video e non vedeva cambiare niente — nemmeno una riga,
        perche' la riga in fondo alla finestra non esiste piu'.

        La ricerca e' delegata a `card_di_media` (griglia della sezione Media)
        e a `card_di` (Home e Preferiti), che sono i posti che sanno dove
        stanno le loro card: qui si sa solo che esistono queste sezioni.
        """
        cercate = []
        attuale = getattr(self, "_schermo_corrente", None)
        if attuale is not None:
            cercate.append(attuale)
        for nome in ("Biblioteca Digitale", "Home"):
            sezione = self.sezioni.get(nome)
            if sezione is not None and sezione not in cercate:
                cercate.append(sezione)

        for sezione in cercate:
            # Un media: la card della griglia di Video o Audio.
            if hasattr(sezione, "card_di_media"):
                card = sezione.card_di_media(voce)
                if card is not None:
                    return card
            # Una pubblicazione o un media fra i Preferiti della Home.
            if hasattr(sezione, "card_di"):
                card = sezione.card_di(voce)
                if card is not None:
                    return card
        return None

    def _aggiorna_scaricature(self) -> None:
        """Un pacchetto e' arrivato o e' stato tolto: le nuvolette cambiano.

        Chiama `HomeView.aggiorna_scaricature`, che mostra la nuvoletta solo
        dove il pezzo non e' ancora sul disco.  Serve in due momenti:

            dopo uno scaricamento finito   la nuvoletta sparisce
            dopo un'eliminazione           la nuvoletta ricompare

        Senza la seconda, la nuvoletta resterebbe sparita su un pezzo che non
        c'e' piu': l'utente non avrebbe piu' modo di ricaricarlo dalla card, e
        dovrebbe andare a cercarlo nella sezione Pubblicazioni.
        """
        home = self.sezioni.get("Home")
        if home is not None and hasattr(home, "aggiorna_scaricature"):
            home.aggiorna_scaricature()

    def _scarica_sulla_card(self, card, nome: str, totale: int) -> None:
        """Accende la barra dentro la card, se la card c'e'."""
        if card is not None and hasattr(card, "_scarica_comincia"):
            card._scarica_comincia(totale)

    # ------------------------------------------------------------------
    # IL MENU' DELLE CUFFIE
    # ------------------------------------------------------------------

    def _pub_delle_cuffie(self) -> tuple | None:
        """La pubblicazione di cui si occupano le cuffie, o ``None``.

        (sigla, lingua) della schermata che si sta guardando.

        DOVE SI VEDE
        ------------
        Ogni sezione tiene la pubblicazione con un nome suo, e sono tre nomi:
        `PubView.pub`, `MediaView._pub` e — per le righe degli Scaricati — un
        oggetto che arriva al momento del clic.  Non si cerca un nome unico
        perche' non esiste: si chiede alla schermata e si accetta il primo
        attributo che c'e'.  Aggiungere una quarta sezione significa
        aggiungere una riga qui, e non riscrivere le altre tre.

        SE NON C'E' NESSUNA
        --------------------
        Home, Bibbia, Adunanze, Ricerche e Impostazioni non hanno una
        pubblicazione: non c'e' niente di cui le cuffie possano occuparsi e chi
        lo chiama ricade sulla sezione Multimedia, che e' la risposta vera per
        «voglio sentire qualcosa» senza sapere che cosa.
        """
        schermata = self._schermo_corrente
        for nome in ("pub", "_pub"):
            pub = getattr(schermata, nome, None)
            sigla = getattr(pub, "keySymbol", "") or ""
            if sigla:
                lingua = Lingua.da_numero(getattr(pub, "mepsLanguageId",
                                                 Lingua.PREDEFINITA))
                return (sigla, lingua)
        return None

    def _apri_menu_segnalibri(self, pulsante=None) -> None:
        """Il tasto dei segnalibri della fascia.

        SE SI STA LEGGENDO UNA PUBBLICAZIONE
        -------------------------------------
        Il menu' e' quello della schermata: i segnalibri di quel libro, il
        comando per metterne uno qui e quello per toglierne uno.  Il menu'
        sa di quale pubblicazione si tratta, quindi lo chiede a lei.

        SE NON SI STA LEGGENDO NULLA
        ---------------------------
        L'elenco globale, che sta nella sezione Ricerche: e' la risposta
        vera per «dove sono i miei segnalibri» quando non c'e' un libro sotto.

        DOVE SI APRE
        -------------
        Sotto il pulsante premuto, non dove sta il mouse: la mano e' ferma
        sulla fascia e li' e' dove l'utente sta guardando.
        """
        try:
            corrente = self.pila.currentWidget()
        except (AttributeError, RuntimeError):
            corrente = None
        apri = getattr(corrente, "menu_segnalibri", None)
        if callable(apri):
            punto = None
            if pulsante is not None:
                punto = pulsante.mapToGlobal(QPoint(0, pulsante.height()))
            apri(punto)
            return
        self._seleziona_nome("Ricerche")

    def _apri_menu_cuffie(self, pulsante=None) -> None:
        """Le cuffie: un menu' con quello che c'e' davvero, nient'altro.

        ADATTIVO
        --------
        Ogni voce compare **solo se serve**, e le tre regole sono:

            streaming    solo se la traccia non e' sul disco (a che pro
                         streamare un file che c'e' gia'?)
            scarica      solo se la traccia non e' sul disco
            lingua       solo se quell'altra lingua esiste davvero, cioe' se
                         il suo catalogo e' gia' scaricato: promettere una
                         lingua che poi non c'e' e' una voce che non funziona

        Un menu' con dentro «Scarica l'audio» per una pubblicazione che ha
        solo il video e' una promessa falsa: l'utente preme, non si apre niente,
        e il giorno dopo smette di fidarsi del menu'.  Quindi il menu' dice
        quello che c'e'.

        DOVE SI APRE
        -------------
        Sotto il pulsante premuto, non dove sta il mouse: la mano e' ferma
        sulla fascia e li' e' dove l'utente sta guardando.

        SE IL MENU' RESTA VUOTO
        ------------------------
        Non si apre niente e si va alla sezione Multimedia, che e' quello che
        faceva il pulsante prima: e' la risposta giusta per «voglio sentire
        qualcosa» quando non c'e' una pubblicazione di sotto.
        """
        corrente = self._schermo_corrente
        dentro = (hasattr(corrente, "immagini_della_pagina")
                  and getattr(corrente, "pub", None) is not None)
        if dentro:
            voci = self._voci_cuffie_della_schermata(corrente)
        else:
            contesto = self._pub_delle_cuffie()
            voci = self._voci_del_menu_cuffie(contesto) if contesto else []
        if not voci:
            if dentro:
                # Si resta dove si e': nessun salto alla Biblioteca.
                self.mostra_toast("Per questa pubblicazione non c'e' audio ne' video"
                                  + ("" if Rete.noto() else " scaricato"), "info", 3000)
                return
            self._seleziona_nome("Biblioteca Digitale")
            sezione = self.sezioni.get("Biblioteca Digitale")
            if sezione is not None and hasattr(sezione, "ricarica_se_serve"):
                sezione.ricarica_se_serve()
            return
        menu = QMenu(self)
        menu.setObjectName("menuCuffie")
        for voce in voci:
            if voce is None:  # un separatore
                menu.addSeparator()
                continue
            if voce[0] == "sotto":
                sotto = menu.addMenu(voce[1])
                for etichetta, azione in voce[2]:
                    riga = sotto.addAction(etichetta)
                    riga.triggered.connect(azione)
                continue
            riga = menu.addAction(voce[1])
            riga.triggered.connect(voce[2])

        # Tenuto qui finche' non si sceglie: senza questo attributo Qt libera
        # il menu' quando questo metodo finisce, mentre e' ancora aperto.
        self._menu_aperto = menu
        if pulsante is not None:
            punto = pulsante.mapToGlobal(QPoint(0, pulsante.height()))
        else:
            punto = QCursor.pos()
        menu.exec(punto)

    def _voci_del_menu_cuffie(self, contesto: tuple, solo_audio: bool = False) -> list:
        """Le voci del menu' delle cuffie, gia' decise.

        Ogni voce e' ``("riga", etichetta, cosa_fare)``, un sotto-menu' e'
        ``("sotto", titolo, [(etichetta, cosa_fare), ...])``, e un separatore
        e' ``None``.  La terza parte e' **la funzione da chiamare**, non un
        nome di azione da interpretare: con un nome, ogni voce del menu'
        aveva bisogno del suo ``if`` e la stessa azione finiva scritta due
        volte — una per lo streaming e una per lo scaricamento — e il giorno
        che una delle due avesse cambiato, l'altra avrebbe continuato a fare
        la cosa vecchia senza che nessuno lo vedesse.

        LA REGOLA DELLE DUE TASSE
        -------------------------
        Non si fa una voce per ogni traccia: `wsb` ha 165 tracce e un menu' con
        165 righe non e' un menu', e' un elenco travestito.  Si prende **la
        prima** traccia di ogni formato — video e audio — perche' e' la stessa
        regola che gia' governa le card dei Preferiti (`prima_traccia_di`) e le
        strisce della Home: la prima e' quella che si pigia senza leggere.

        Il numero della traccia c'e' scritto nella voce, perche' «Streaming
        video» senza dire **quale** video e' una voce che non basta a sapere se
        e' quello che si vuole.
        """
        from Utility import MediaScaricati

        sigla, lingua = contesto
        voci: list = []
        scaricare: list = []
        fatti: set[str] = set()

        # IL PACCHETTO .JWPUB PRIMA DI TUTTO
        # -----------------------------------
        # Il libro e' stato scaricato in formato .jwpub, e dentro c'e' la
        # tabella `Multimedia` con quello che contiene: gli audio e i
        # video, con la loro traccia e con il loro file (quando il file
        # c'e').  Il libro sa da se' cosa contiene, e quindi la sua
        # risposta viene prima di ogni altra.
        for traccia in self._tracce_del_pacchetto(sigla, lingua):
            formato = traccia["formato"]
            if solo_audio and formato != "AUDIO":
                continue
            if formato in fatti:
                # Un formato per volta: la prima traccia del formato basta.
                continue
            fatti.add(formato)
            numero = int(traccia.get("traccia") or 0)
            nome = "video" if formato == "VIDEO" else "audio"
            if traccia.get("on_disk"):
                # Il file e' dentro il pacchetto: e' gia' offline, e si
                # parte da li'.  Non si scarica niente.
                etichetta = ("Guarda il video" if formato == "VIDEO"
                             else "Ascolta l'audio")
                if numero:
                    etichetta += f" (traccia {numero})"
                voci.append(("riga", etichetta,
                             self._richiamo(
                                 self._apre_un_media_scaricato,
                                 str(traccia.get("file") or ""),
                                 str(traccia.get("titolo")
                                     or f"{sigla} (traccia {numero})"))))
                continue
            # Il file non e' nel pacchetto: la traccia e' sul server.  Si
            # streama, e si puo' scaricare per averla anche senza rete.
            if not numero:
                continue
            voci.append(("riga", f"Streaming {nome} (traccia {numero})",
                         self._richiamo(self._ascolta_media,
                                         sigla, lingua, numero, formato), True))
            scaricare.append(
                ("riga", f"Scarica {nome} (traccia {numero})",
                 self._richiamo(self._scarica_media_dal_server,
                                 sigla, lingua, numero, formato), True))

        # IL CATALOGO DEI MEDIA, PER QUELLO CHE IL PACCHETTO NON HA
        # ----------------------------------------------------------
        # I periodici e i video non stanno dentro il libro: stanno nel
        # catalogo dei media, e li' c'e' tutto quello che si puo'
        # streamare e scaricare.
        tracce = CatalogoMedia.tracce_di(sigla, lingua)
        # La prima traccia di ogni formato.  `_tracce_di` mette il video prima
        # dell'audio a pari numero, quindi tiene il primo che trova.
        per_formato: dict[str, int] = {}
        for numero, formato in tracce:
            if formato not in per_formato:
                per_formato[formato] = numero

        for formato in (("AUDIO",) if solo_audio else ("VIDEO", "AUDIO")):
            traccia = per_formato.get(formato)
            if traccia is None:
                # Non c'e' un video: non si scrive «Streaming video».
                continue
            if formato in fatti:
                # Il pacchetto ha gia' dato la prima traccia di questo
                # formato: quella e' la sua, e non se ne cerca un'altra.
                continue
            fatti.add(formato)
            nome = "video" if formato == "VIDEO" else "audio"
            # IL FORMATTO CONTA NEL CONFRONTO CON IL DISCO
            # ---------------------------------------------
            # Lo stesso programma esce in due formati, e sul disco puo'
            # esserci uno solo dei due: la Torre di Guardia ha l'audio
            # scaricato e il video no.  Senza dire quale formato si cerca,
            # «Guarda il video» poteva trovarsi l'audio, e la voce suonava
            # al posto delle immagini.
            sul_disco = (MediaScaricati.file_di(sigla, lingua, traccia, formato)
                         is not None)

            # Sul disco non si scarica e non si streamerebbe: si parte.  Il
            # lettore prende il file che c'e' e, se per caso non ci fosse,
            # prende dalla rete — quindi la voce non puo' mentire.
            etichetta = ("Guarda il video" if formato == "VIDEO"
                         else "Ascolta l'audio")
            if not sul_disco:
                etichetta = f"Streaming {nome}"
            voci.append(("riga", f"{etichetta} (traccia {traccia})",
                         self._richiamo(self._ascolta_media,
                                         sigla, lingua, traccia, formato),
                         not sul_disco))

            if not sul_disco:
                scaricare.append(
                    ("riga", f"Scarica {nome} (traccia {traccia})",
                     self._richiamo(self._scarica_media_dal_server,
                                     sigla, lingua, traccia, formato), True))

        lingue = self._lingue_del_menu_cuffie(sigla, lingua)
        if scaricare:
            voci.append(None)
            voci.extend(scaricare)
        if lingue:
            voci.append(None)
            voci.append(("sotto", "Cambia lingua", lingue))
        return voci

    def _tracce_del_pacchetto(self, sigla: str, lingua: str) -> list:
        """I media che il pacchetto .jwpub della pubblicazione dichiara.

        IL PACCHETTO E' LA RISPOSTA PRIMA
        ----------------------------------
        Il libro e' stato scaricato in formato .jwpub, e il suo database
        (la tabella `Multimedia`) sa quali tracce ha: l'audio, il video,
        e se il file e' dentro il pacchetto o se sta sul server.

        Quindi la lista delle tracce la dice **il libro**, e non il
        catalogo dei media.  Il catalogo serve per quello che nel libro
        non c'e': i periodici, i video.

        DALL'ONLINE SOLO IL FILE
        ------------------------
        Una traccia con il `FilePath` vuoto sta sul server: si streama, e
        si scarica per averla anche senza rete.  Una traccia con il file
        dentro il pacchetto e' gia' offline, e si parte da li'.
        """
        return JWPubManager.media_nel_pacchetto(sigla, lingua)

    @staticmethod
    def _richiamo(azione, *dati):
        """Una funzione che chiama `azione` con `dati`, e basta.

        Serve perche' i dati del ciclo — sigla, traccia, formato — cambiano a
        ogni giro e la closure li catturerebbe tutti all'ultimo valore: tutte le
        voci del menu' farebbero la prima.  Qui il richiamo e' costruito sul
        momento e i suoi valori sono gia' quelli giusti quando il menu' viene
        premuto, che e' molto dopo.
        """
        return lambda: azione(*dati)

    def _lingue_del_menu_cuffie(self, sigla: str, lingua: str) -> list:
        """Le altre lingue in cui questa pubblicazione esiste, se esistono.

        SI GUARDA SOLO NEI CATALOGHI GIA' SCARICATI
        ---------------------------------------------
        Un sotto-menu' che promette «Italiano» e poi non trova nulla e' peggio
        di un menu' senza la voce: l'utente lo prova, non funziona, e non
        distingue «non c'e'» da «rotto».

        Quindi si guarda **solo quello che c'e' sul disco**: si controlla ogni
        lingua il cui catalogo e' gia' scaricato.  Sono una manciata di file
        da 7 megabyte e sono gia' in memoria dopo la prima lettura (`_leggi`
        tiene la cache), quindi il costo e' nullo e il risultato e' vero per
        costruzione.

        Se un domani si vuole anche la lingua che si puo' scaricare, e' un
        altro lavoro — e va detto all'utente che il catalogo non c'e' ancora,
        non mostrata una voce che non funziona.
        """
        voci: list = []
        for simbolo in Lingua.simboli():
            if simbolo == lingua:
                continue
            if not CatalogoMedia.c_e_file(simbolo):
                continue
            if not CatalogoMedia.tracce_di(sigla, simbolo):
                continue
            voce = Lingua.per_simbolo(simbolo) or {}
            numero = voce.get("id")
            if numero is None:
                continue
            titolo = Lingua.titolo(voce) or simbolo
            voci.append((titolo, self._richiamo(self._lingua_scelta, numero)))
        return voci

    def _ascolta_media(self, sigla: str, lingua: str, traccia, formato: str) -> None:
        """Fa partire una traccia, dalla rete o dal disco.

        Non si distingue qui: `Lettore.suona` guarda da solo se il file c'e' e,
        se non c'e', lo prende dalla rete.  La regola «scaricato = dal disco,
        non scaricato = dalla rete» sta in un posto solo, e questo non e' quel
        posto.

        Va pero' segnato da dove si parte: `_vai_a_multimedia` mette il
        segnaposto, cosi' chiudendo il lettore l'utente torna dove era e non
        resta nella sezione Multimedia.
        """
        if formato != "VIDEO" and hasattr(self._schermo_corrente, "immagini_della_pagina"):
            self._ascolta_audio_qui(sigla, lingua, traccia)
            return
        self._apre_media_e_suona(sigla, lingua, traccia,
                                 1 if formato == "VIDEO" else 0)
    def _scarica_media_dal_server(self, sigla: str, lingua: str, traccia,
                                  formato: str, chiave=None,
                                  automatico: bool = False, altezza: int = 0) -> None:
        """Scarica una traccia chiedendo il file al server.

        IL PERCHE' NON SI SCRIVE L'URL QUI
        -----------------------------------
        L'indirizzo del file cambia a ogni versione del server e dipende dalla
        risoluzione scelta, quindi non puo' essere una riga di codice: lo
        chiede `MepsAPI.media`, e se per quella traccia ci sono piu' file si
        lascia scegliere la risoluzione con lo stesso menu' che usa la nuvoletta
        delle card.

        Il nome del file sul disco lo mette `FileDownloader` prendendolo
        dall'indirizzo, quindi non c'e' niente da nominare qui: e il lettore lo
        ritrova con `MediaScaricati.file_di`.
        """
        from Utility.Extensions.Ext_DispatchQueue import background
        from Utility import AvanzamentoMedia, MepsAPI

        def annullato(esito: str) -> None:
            if chiave is not None:
                AvanzamentoMedia.canale().finito.emit(chiave, esito)

        try:
            numero = int(traccia)
        except (TypeError, ValueError):
            annullato("errore")
            return
        titolo = self._titolo_del_media(sigla, lingua, numero, formato)

        scelte: list[tuple[str, str, int]] = []

        def lavoro() -> None:
            try:
                voci = MepsAPI.media(sigla, lingua, traccia=numero)
            except Exception:  # noqa: BLE001 - senza rete: nessuna scelta
                voci = []
            for voce_media in voci:
                if (MepsAPI.traccia_numero(voce_media) != numero
                        or not _del_formato(voce_media, formato)):
                    continue
                url = (voce_media.get("file") or {}).get("url") or ""
                if not url:
                    continue
                scelte.append((_nome_risoluzione(voce_media), url,
                               _peso_del_file(voce_media)))
            scelte.sort(key=lambda s: _altezza_risoluzione(s[0]), reverse=True)

        def arrivati() -> None:
            if not scelte:
                self.mostra_toast(
                    f"Per «{titolo}» il server non ha nessun file da scaricare",
                    "warning", 5000)
                annullato("errore")
                return
            if len(scelte) == 1 or automatico or altezza:
                # Un file solo, o «Scarica tutti»: non si fa scegliere.  Si
                # prende la risoluzione voluta (o la piu' alta).
                nome, url, peso = _per_altezza(scelte, altezza)
                self._scarica_un_video(url, titolo, peso, None, formato, chiave=chiave)
                return
            menu = QMenu(self)
            menu.setObjectName("menuRisoluzioni")
            for nome, url, peso in scelte:
                azione = menu.addAction(nome)
                azione.triggered.connect(
                    lambda _c=False, u=url, p=peso, f=formato:
                    self._scarica_un_video(u, titolo, p, None, f, chiave=chiave))
            self._menu_aperto = menu
            if menu.exec(QCursor.pos()) is None:
                annullato("annullato")

        background(lavoro, completion=arrivati)

    def _titolo_del_media(self, sigla: str, lingua: str, traccia: int,
                          formato: str) -> str:
        """Il titolo di una traccia, per la riga di scaricamento.

        Se il catalogo non lo sa si usa la sigla: una riga che dice «Scarica
        · wsb (traccia 2)» e' meno bella di una che dice il titolo, ma e'
        vera, e una riga con un titolo inventato sarebbe falsa.
        """
        voce = CatalogoMedia.voce_di(sigla, lingua, traccia)
        titolo = (voce.get("title") if isinstance(voce, dict) else "") or ""
        if titolo:
            return titolo
        return f"{sigla} (traccia {traccia})"

    # ------------------------------------------------------------------
    # LA NUVOLETTA DELLE CARD
    # ------------------------------------------------------------------

    def _scarica_da_card(self, voce, punto) -> None:
        """La nuvoletta di una card e' stata premuta: (voce, dove).

        LA DOMANDA CHE DECIDE TUTTO
        ---------------------------
        Un **video** e' la stessa cosa in piu' risoluzioni, e l'utente sceglie
        quale prendere: quindi si apre un menu' con le risoluzioni che il
        server ha, dalla piu' alta alla piu' bassa.  Una **pubblicazione** e'
        un pacchetto solo, il JWPUB: non c'e' niente da scegliere, e premere
        la nuvoletta scarica e basta.

        Non si chiede alla card se e' un video o una pubblicazione: lo dice la
        voce.  Una voce con una traccia e formato ``VIDEO`` e' un video; tutto
        il resto e' una pubblicazione.
        """
        if not isinstance(voce, dict):
            return
        traccia = voce.get("traccia")
        formato = str(voce.get("formato") or "").upper()
        if traccia and formato == "VIDEO":
            self._scegli_la_risoluzione(voce, punto)
            return
        self._scarica_una_pubblicazione(voce)

    def _scarica_un_media_da_card(self, voce: dict, punto=None) -> None:
        """La nuvoletta di una card di Video o Audio.

        IL VIDEO CHIEDE QUALE, L'AUDIO SCARICA E BASTA
        ------------------------------------------------
        Un video ha piu' file — una risoluzione ciascuno, e fino a quattro —
        e la scelta e' dell'utente: la nuvoletta apre il menu' con le
        risoluzioni, come fa la Home.  La lista non si chiede al server: la
        voce del mediator porta **gia'** `risoluzioni`, con tutti gli
        indirizzi veri di quel video, quindi il menu' si apre al primo colpo
        e senza una seconda attesa.

        Un audio ha un file solo: non c'e' niente da scegliere, e un menu'
        con una riga sola sarebbe un clic che chiede cosa scegliere quando
        la risposta e' gia' decisa.  Scarica, come prima.

        DUE VOCI ALTRE, CHE RESTANO COME SONO
        --------------------------------------
        Una voce **senza** lista e **con** `url` — un video con una risoluzione
        sola, o un brano — scarica subito.

        Una voce senza niente dell'una e dell'altro — quelle della Home, che
        portano sigla e traccia e nient'altro — passa a
        `_scegli_la_risoluzione`, che le chiede al server.  E' la strada di
        prima, e non si tocca: e' quella provata.

        `punto` e' dove aprire il menu', in coordinate di schermo: arriva dalla
        card che ha premuto (vedi `MediaView._scarica_una_cella`).  Senza, si
        usa il centro della schermata, che e' comunque visibile.
        """
        if not isinstance(voce, dict):
            return

        titolo = voce.get("title") or voce.get("label") or "un media"
        risoluzioni = [r for r in (voce.get("risoluzioni") or [])
                       if isinstance(r, dict) and (r.get("url") or "")]
        video = (str(voce.get("formato") or "").upper() == "VIDEO"
                 or str(voce.get("tipo") or "").lower() == "video")

        if video and len(risoluzioni) > 1:
            # Dall'alta in giu': e' l'ordine con cui si sceglie e con cui si
            # guarda.  Si ordina sui numeri e non sulle etichette, perche'
            # una voce puo' non avere la risoluzione scritta.
            scelte = [(str(r.get("label") or ""), r.get("url") or "",
                       int(r.get("filesize") or 0)) for r in risoluzioni]
            scelte.sort(key=lambda s: _altezza_risoluzione(s[0]), reverse=True)
            self._apri_il_menu_delle_risoluzioni(scelte, titolo, voce, punto)
            return

        url = voce.get("url") or ""
        peso = int(voce.get("filesize") or 0)
        if not url and risoluzioni:
            url = risoluzioni[0].get("url") or ""
            peso = int(risoluzioni[0].get("filesize") or 0)
        if url:
            self._scarica_un_video(
                url, titolo, peso, voce,
                str(voce.get("mimetype") or "").split("/")[-1])
            return

        # Nessun indirizzo: e' una voce della Home, e quella lo chiede al
        # server — la strada di prima, che resta com'era.
        if punto is None:
            punto = self.pila.mapToGlobal(self.pila.rect().center())
        self._scegli_la_risoluzione(voce, punto)

    def _apri_il_menu_delle_risoluzioni(self, scelte, titolo: str,
                                        voce: dict, punto=None) -> None:
        """Apre il menu' delle risoluzioni con le scelte che ci sono gia'.

        IL POSTO DELL'APERTURA
        -----------------------
        `punto` e' un punto globale — lo schermo, non la finestra — e viene da
        chi ha premuto: la nuvoletta della card o la voce «Scarica» del menu'
        «...».  Senza punto si usa il centro della schermata, che e' comunque
        visibile, invece del `QPoint(200, 200)` di prima, che era la posizione
        della finestra quando il programma era stato scritto su un altro
        schermo e oggi puo' cadere fuori.

        `menu` resta tenuto in `self._menu_aperto` finche' non si sceglie: e'
        una variabile locale di questo metodo, e senza quell'attributo Qt lo
        libera appena il metodo finisce — mentre il menu' e' ancora aperto.
        """
        if not scelte:
            self._mostra_messaggio(
                f"Per «{titolo}» il server non ha nessun video da "
                f"scaricare.")
            return
        menu = QMenu(self)
        menu.setObjectName("menuRisoluzioni")
        for nome, url, peso in scelte:
            azione = menu.addAction(nome)
            azione.triggered.connect(
                lambda _controllato=False, u=url, p=peso:
                self._scarica_un_video(u, titolo, p, voce))
        self._menu_aperto = menu
        if not isinstance(punto, QPoint):
            punto = self.pila.mapToGlobal(self.pila.rect().center())
        menu.exec(punto)

    def _scegli_la_risoluzione(self, voce: dict, punto) -> None:
        """Chiede al server le risoluzioni di quella traccia e apre il menu'.

        LE RISOLUZIONI NON SONO SCRITTE QUI
        ------------------------------------
        Non c'e' nessuna lista nel codice.  Quelle che il menu' mostra sono
        **quelle che il server ha risposto**: si deducono dalle voci, e
        `MepsAPI.risoluzioni` le ordina dalla piu' alta in giu'.  Una lista
        scritta a mano prometterebbe formati che quel video non ha, e
        l'utente che sceglie "480p" si troverebbe un scaricamento che non
        parte.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        sigla = voce.get("sigla") or ""
        lingua = voce.get("lingua") or Lingua.corrente_simbolo()
        try:
            traccia = int(voce.get("traccia"))
        except (TypeError, ValueError):
            traccia = 0
        titolo = voce.get("titolo") or sigla

        # Le scelte stanno qui fuori e non sono un argomento di `arrivati`.
        # `background` chiama il `completion` **senza passargli niente**: il
        # segnale `run` porta due cose — il richiamo e la pausa — e i dati se li
        # prende il richiamo dalla lista che il lavoro ha riempito.  Un
        # `arrivati(scelte)` qui moriva con «missing 1 required positional
        # argument» e il menu' non si apriva mai.  E' la stessa forma di
        # `risultati` in `_immagini`, che per quello funziona.
        # (nome, indirizzo, peso in byte)
        scelte: list[tuple[str, str, int]] = []

        def lavoro() -> None:
            # Se la voce ha gia' un URL diretto (viene dal mediator), usalo:
            # non serve chiedere al server le risoluzioni.
            voce_url = voce.get("url") or ""
            if voce_url:
                scelte.append((_nome_risoluzione(voce), voce_url,
                               int(voce.get("filesize") or 0)))
                return
            # Altrimenti cerca sul server le risoluzioni della traccia.
            from Utility import MepsAPI

            voci = MepsAPI.media(sigla, lingua)
            for voce_media in voci:
                if (MepsAPI.traccia_numero(voce_media) != traccia
                        or not _del_formato(voce_media, "VIDEO")):
                    continue
                url = (voce_media.get("file") or {}).get("url") or ""
                if not url:
                    continue
                scelte.append((_nome_risoluzione(voce_media), url,
                               _peso_del_file(voce_media)))

            # Dalla piu' alta in giu': e' l'ordine con cui si sceglie e quello
            # con cui si guarda, e la prima voce e' quella che si pigia senza
            # leggere.  Si ordina sui numeri delle scelte, non sulle voci
            # intere, perche' una voce puo' non avere la risoluzione e il suo
            # `label` non e' un numero.
            scelte.sort(key=lambda s: _altezza_risoluzione(s[0]), reverse=True)

        def arrivati() -> None:
            # Il menu' e' uno solo, ed e' quello della scelta: si chiama la
            # stessa funzione che apre il menu' della nuvoletta di una card,
            # perche' un menu' delle risoluzioni non puo' essere due.  Solo
            # che qui le scelte vengono dal server, e lì sono poche per
            # costruzione: una traccia di una pubblicazione.
            self._apri_il_menu_delle_risoluzioni(scelte, titolo, voce, punto)

        background(lavoro, completion=arrivati)

    def _scarica_un_video(self, url: str, titolo: str, peso: int = 0,
                           voce: dict | None = None,
                           formato: str = "Video", chiave=None) -> None:
        """Scarica un file di media, e dice com'e' andata.

        Non passa da `PubView.scarica`: quello scarica un pacchetto e poi i
        testi dei capitoli, e qui c'e' gia' un solo file — il video — senza
        capitoli da cui prendere nulla.  La riga di scaricamento e' la stessa
        di quella degli altri pacchetti, quindi l'utente vede il progresso dove
        lo vede sempre.

        LA RIGA DICE COSA STA SCARICANDO
        ---------------------------------
        Il nome della riga e' «Video · <titolo>» e non solo il titolo: la
        stessa pubblicazione si scarica come pacchetto e come video, e una riga
        che dice solo «Perché studiare la Bibbia?» non dice quale delle due
        cose sta andando a prendere.

        Il totale (`peso`) viene da `filesize` della voce del server, e serve
        perche' senza la barra resta in indeterminate: si muove, ma non dice
        quanto manca, e «manca una percentuale» e' un'informazione che non
        c'e'.  Se il server non manda la misura si passa zero, che e' previsto.

        LA BARRA E' SU DUE POSTI
        -----------------------
        Sulla card di questa voce — perche' e' l'unica cosa che l'utente sta
        guardando — e nella riga in fondo, che resta per gli scaricamenti
        senza card (i cataloghi, i capitoli di un pacchetto).  Sulla card non
        basta la riga: con venti video in striscia, una riga in fondo dice
        «qualcosa sta scendendo» ma non quale.
        """
        from Utility.Extensions.Ext_DispatchQueue import on_main
        from Utility.FileDownloader import FileDownloader
        from Utility import AvanzamentoMedia

        card = self._card_del_video(voce) if voce else None
        canale = AvanzamentoMedia.canale() if chiave is not None else None

        def avanzo(scritti: int, totale: int) -> None:
            if canale is not None:
                canale.avanza.emit(chiave, int(scritti), int(totale or peso or 0))
            # L'avanzamento arriva dal thread del download e la card e' un
            # widget: va toccata sul main thread, altrimenti Qt avvisa che si
            # sta toccando un widget da fuori e la barra non si muove.
            if card is not None:
                on_main(lambda: card._scarica_avanza(scritti, totale))

        def finito(percorso, errore) -> None:
            if card is not None:
                card._scarica_finita()
                # Il file e' adesso sul disco: la nuvoletta di questa card
                # sparisce, senza aspettare il giro completo delle card.
                card._scarica.setVisible(False)
            self._scaricamento_finito()
            if FileDownloader.annullato():
                FileDownloader.riparti()
                if canale is not None:
                    canale.finito.emit(chiave, "annullato")
                self._mostra_messaggio(f"Scaricamento di «{titolo}» annullato")
                if card is not None:
                    card._scarica.setVisible(True)
                return
            if errore is not None or not percorso:
                if canale is not None:
                    canale.finito.emit(chiave, "errore")
                self._mostra_messaggio(
                    f"Non sono riuscito a scaricare «{titolo}» ⚠️")
                return
            if canale is not None:
                canale.finito.emit(chiave, "ok")
            self._scaricata_qualcosa()
            self._aggiorna_scaricature()

        FileDownloader.riparti()
        self._scaricamento_inizia(f"{formato} · {titolo}", peso)
        self._scarica_sulla_card(card, f"{formato} · {titolo}", peso)
        if canale is not None:
            canale.iniziato.emit(chiave, int(peso or 0))
        FileDownloader.load_file_async(url=url, completion=finito,
                                       on_progress=avanzo)

    def _cerca_pubblicazione(self, sigla: str, numero_lingua: int,
                             numero_edizione: str = ""):
        """La riga del catalogo con questa sigla — e questo numero, se c'e'.

        Si legge tutto l'elenco e si sceglie la riga: sono 3.741 righe e la
        lettura e' un attimo.  Una ricerca per simbolo nel database sarebbe
        piu' veloce, ma non esiste e scriverla adesso e' un'altra cosa da
        tenere aggiornata.

        IL NUMERO E' OBBLIGATORIO QUANDO C'E'
        --------------------------------------
        Senza `numero_edizione` si prende **la prima riga** che ha quella
        sigla, e per un periodico quella riga e' un numero a caso fra gli
        ultimi anni.  La sezione Novita' offre "La Torre di Guardia,
        dicembre 2026" e il pulsante scaricherebbe il primo numero
        incontrato, mettendolo nella cartella di **quello**: la riga mostrata
        e' una, il file scaricato e' un altro, e non c'e' nessun errore.  E'
        il difetto peggiore, perche' sembra funzionare.

        Il confronto passa da `pub_dir_name`, che e' l'unico posto dove la
        regola del numero e' scritta — `20261200` diventa `202612`.  Se qui si
        dividesse per 100 un secondo posto, e un domani la regola cambiasse,
        i due posti direbbero cose diverse e la cartella cercherebbe un nome
        che nessuno usa.

        Se il numero richiesto non c'e' nel catalogo si restituisce None e
        chi chiama dice che non lo trova: scaricare al buio sarebbe scaricare
        la cosa sbagliata.
        """
        sezione = self._catalogo()
        if sezione is None:
            return None
        for pub in getattr(sezione, "_tutto", []) or []:
            if pub.keySymbol != sigla:
                continue
            if getattr(pub, "mepsLanguageId", 4) not in (numero_lingua, 0):
                continue
            if numero_edizione and not pub_dir_name(pub).endswith(
                    f"_{numero_edizione}"):
                continue
            return pub
        return None

    def _ricrea_sezione(self, titolo: str) -> None:
        """Rifa una sola sezione (restando dove si e'), leggendo il disco da capo."""
        vecchia = self.sezioni.get(titolo)
        if vecchia is None:
            return
        era_corrente = self.pila.currentWidget() is vecchia
        nuovo = self._crea_sezione(titolo)
        self.sezioni[titolo] = nuovo
        self._segna_permanente(nuovo)
        self.pila.addWidget(nuovo)
        self._collega(nuovo)
        self._sostituisci_nella_cronologia(vecchia, nuovo)
        self._schermate = [nuovo if w is vecchia else w for w in self._schermate]
        self._avanti = [nuovo if w is vecchia else w for w in self._avanti]
        if era_corrente:
            self.pila.setCurrentWidget(nuovo)
        self.pila.removeWidget(vecchia)
        vecchia.deleteLater()

    def _bibbia_tolta_dal_disco(self) -> None:
        """La Bibbia e' stata eliminata: la sezione Bibbia smette di mostrare
        l'elenco dei libri e torna a dire «non e' scaricata»."""
        bibbia = self.sezioni.get("Bibbia")
        if bibbia is None or not getattr(bibbia, "_scaricato", False):
            return
        try:
            from Utility import BibbiaOnline, Lingua
            from Utility.JWPubManager import bible_package
            simbolo = Lingua.bibbia_simbolo()
            if bible_package() is None and BibbiaOnline.capitoli_su_disco(simbolo) == 0:
                self._ricrea_sezione("Bibbia")
        except Exception:  # noqa: BLE001
            import traceback
            traceback.print_exc()

    def _pacchetto_tolto(self, _pub=None) -> None:
        """Un pacchetto e' stato tolto dal disco: la sezione che lo mostrava.

        Va detto **a chi mostrava** il pacchetto, e non solo «rileggi tutto»:
        la sezione che ha la card sa di cambiare una nuvoletta; quella che non
        la conosce riceverebbe una lista da rileggere e non avrebbe niente da
        fare con un tasto.

        `_scaricata_qualcosa` fa il resto — Scaricati e il riquadro del giorno —
        e i due si sommano, non si sostituiscono.
        """
        self._bibbia_tolta_dal_disco()
        sezione = self.sezioni.get("Biblioteca Digitale")
        if sezione is None or not hasattr(sezione, "reletti_la_griglia"):
            return
        try:
            sezione.reletti_la_griglia(_pub)
        except Exception:  # noqa: BLE001
            import traceback
            print("Biblioteca: errore dopo aver tolto il pacchetto ⚠️")
            traceback.print_exc()

    def _scaricata_qualcosa(self) -> None:
        """Un pacchetto e' arrivato: si rileggono le sezioni che guardano il disco.

        CHI SI RILEGGE, E CHI NO
        -----------------------
        Si rileggono **due** pezzi, e sono due motivi diversi:

        - **Scaricati**, che **guarda** il disco e quindi ha una riga in piu':

          e' il comportamento di sempre.

        - **Il riquadro del giorno in cima alla Home**, che mostra il versetto
          di oggi letto **dal pacchetto scaricato**: senza il pacchetto non c'e'
          e c'e' un tasto, e con il pacchetto c'e' il versetto e il tasto
          sparisce.  Quindi la Home, in questo punto, cambia davvero.

        La nota qui sotto diceva il contrario, e aveva ragione **allora**: la
        Home mostrava i Preferiti, e un Preferito c'era prima del download e
        c'era anche dopo, quindi rileggerli costava una striscia di card
        ricostruita per ottenere la stessa cosa.  Il Preferiti **non** si
        rilegge qui, e non e' cambiato niente.

        PERCHE' SOLO QUEI DUE PEZZI, E NON LA SEZIONE
        ----------------------------------------------
        Non si ricostruisce la sezione: `ricostruisci()` svuota la colonna e la
        riempie dal disco.  Ricreare il widget la toglierebbe dalla pila e
        perderebbe la posizione, che e' cioe' dove l'utente si trova.  E il
        riquadro del giorno si aggiorna da solo, senza ricostruire niente: e'
        un riquadro dentro la Home, e la Home resta dov'e'.
        """
        adunanze = self.sezioni.get("Adunanze")
        if adunanze is not None:
            adunanze.aggiorna()

        scaricati = self.sezioni.get("Scaricati")
        if scaricati is not None:
            try:
                scaricati.ricostruisci()
            except Exception:  # noqa: BLE001
                import traceback
                print("Scaricati: errore nel rileggere il disco ⚠️")
                traceback.print_exc()

        home = self.sezioni.get("Home")
        if home is not None:
            try:
                home.rileggi_il_giorno()
            except Exception:  # noqa: BLE001
                import traceback
                print("Home: errore nel rileggere il versetto del giorno ⚠️")
                traceback.print_exc()

        biblioteca = self.sezioni.get("Biblioteca Digitale")
        if biblioteca is not None:
            try:
                biblioteca.pacchettoArrivato()
            except Exception:  # noqa: BLE001
                import traceback
                print("Biblioteca: errore nel rileggere la griglia ⚠️")
                traceback.print_exc()

        # Se un segnalibro stava aspettando proprio questo download, adesso
        # il suo file c'e': si apre, ma dopo che `PubView` ha finito di
        # mettere la sua schermata (vedi `_riprendi_posizione_in_attesa`).
        self._riprendi_posizione_in_attesa()

    # ------------------------------------------------------------------
    # I SEGNALIBRI E LE SOTTOLINEATURE
    # ------------------------------------------------------------------

    def _aggiorna_ricerche(self) -> None:
        """Rilegge la sezione Ricerche dopo un segno aggiunto o tolto."""
        sezione = self.sezioni.get("Ricerche")
        if sezione is None or not hasattr(sezione, "aggiorna"):
            return
        try:
            sezione.aggiorna()
        except Exception:  # noqa: BLE001
            import traceback
            print("Ricerche: errore nel rileggere i segni ⚠️")
            traceback.print_exc()

    def _avviso_schermata(self, testo: str) -> None:
        """Un messaggio breve arrivato da una schermata aperta."""
        if testo:
            self.mostra_toast(testo, "info", 3000)

    def _apri_articolo(self, pub: Publication, file_path: str, prev_text: str,
                       document: Document | None = None,
                       ancora: str = "") -> None:
        """Apre un articolo al punto indicato, sopra la schermata di adesso."""
        from SubViews.ArticleView import ArticleView

        articolo = ArticleView(
            pub=pub,
            file_path=file_path,
            prev_text=prev_text,
            document=document,
            ancora=ancora,
        )
        # `navigate` collega anche `goBack`, `posizioneScelta`, `avviso` e
        # `segniCambiati`: non si ricollegano qui, altrimenti il pulsante
        # indietro tornerebbe di due passi a ogni clic.
        self.navigate(articolo)

    def _etichetta_indietro(self) -> str:
        """Il nome da mettere accanto alla freccia indietro.

        Il segnalibro si puo' aprire da due posti: dall'elenco globale delle
        Ricerche, e dal menu' della barra dell'articolo che si sta leggendo.
        La freccia deve dire dove si torna davvero, non il titolo del segno:
        «Ricerche» nel primo caso, il documento di prima nel secondo.
        """
        corrente = getattr(self, "_schermo_corrente", None)
        if corrente is None:
            return "Indietro"
        if corrente.__class__.__name__ == "PersonalStudyView":
            return "Ricerche"
        titolo_documento = getattr(corrente, "_titolo_documento", None)
        if callable(titolo_documento):
            try:
                titolo = titolo_documento()
            except Exception:  # noqa: BLE001
                titolo = ""
            if titolo:
                return str(titolo)
        return "Indietro"

    def _apri_posizione(self, segno) -> None:
        """Apre il punto di una sottolineatura o di un segnalibro.

        Il segno porta con se' la pubblicazione, il documento (o libro e
        capitolo della Bibbia) e il paragrafo.  Non serve il file per sapere
        **dove** si trova: serve solo per poterlo mostrare, ed e' per questo
        che qui si controlla se c'e' e, se non c'e', si chiede.
        """
        if segno is None:
            return
        libro = int(getattr(segno, "bookNumber", 0) or 0)
        capitolo = int(getattr(segno, "chapterNumber", 0) or 0)
        if libro > 0 and capitolo > 0:
            self._apri_posizione_bibbia(segno, libro, capitolo)
            return
        self._apri_posizione_pubblicazione(segno)

    def _apri_posizione_bibbia(self, segno, libro: int, capitolo: int) -> None:
        lingua_bibbia = Lingua.da_numero(
            int(getattr(segno, "mepsLanguageId", 0) or Lingua.corrente_id()))
        cartella = JWPubManager.bible_package(lingua_bibbia) or JWPubManager.bible_package()
        percorso = cartella / str(libro) / f"{capitolo}.html" if cartella else None
        if percorso is None or not percorso.is_file():
            # Non si apre niente da internet: si chiede se scaricare la Bibbia.
            sigla = str(getattr(segno, "keySymbol", "") or "nwtsty")
            pub_da_scaricare = Publication(
                ID=0, keySymbol=sigla, year=0,
                mepsLanguageId=int(getattr(segno, "mepsLanguageId", 0) or Lingua.corrente_id()),
                publicationTypeId=1, issueTagNumber=0, title="Bibbia")
            self._chiedi_download_segno(segno, pub_da_scaricare)
            return

        from SubViews.BibleView import BIBLE_KEY_SYMBOL, BIBLE_TITLE

        pub = Publication(
            ID=0, keySymbol=BIBLE_KEY_SYMBOL, year=2021,
            mepsLanguageId=int(getattr(segno, "mepsLanguageId", 0)
                               or Lingua.corrente_id()),
            publicationTypeId=1, issueTagNumber=0, title=BIBLE_TITLE,
            isBible=True, book=libro, chapter=capitolo,
        )
        versetto = int(getattr(segno, "identifier", 0) or 0)
        ancora = f"v:{libro}:{capitolo}:{versetto}" if versetto > 0 else ""
        self._apri_articolo(
            pub=pub,
            file_path=f"{cartella.name}/{libro}/{capitolo}.html",
            prev_text=self._etichetta_indietro(),
            document=None,
            ancora=ancora,
        )

    def _apri_posizione_pubblicazione(self, segno) -> None:
        documento_id = int(getattr(segno, "documentId", 0) or 0)
        sigla = str(getattr(segno, "keySymbol", "") or "")
        if documento_id <= 0 or not sigla:
            self._mostra_messaggio(
                "Questo segno non ha un punto a cui tornare.")
            return

        titolo = str(getattr(segno, "title", "") or sigla)
        pub = Publication(
            ID=0, keySymbol=sigla, year=0,
            mepsLanguageId=int(getattr(segno, "mepsLanguageId", 0)
                               or Lingua.corrente_id()),
            publicationTypeId=0,
            issueTagNumber=int(getattr(segno, "issueTagNumber", 0) or 0),
            title=titolo,
        )
        # I documenti di una pubblicazione stanno tutti in `Documents_I`, non
        # nella cartella del pacchetto: `pub_dir` serve ai media, non al testo.
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        lingua_doc = Lingua.da_numero(
            int(getattr(segno, "mepsLanguageId", 0) or Lingua.corrente_id()))
        percorso = (get_documents_directory()
                    / f"Documents_{lingua_doc}" / f"{documento_id}.html")
        if not percorso.is_file():
            self._chiedi_download_segno(segno, pub)
            return

        documento = Document(ID=0, documentId=documento_id, title=titolo)
        paragrafo = int(getattr(segno, "identifier", 0) or 0)
        ancora = f"pid:{paragrafo}" if paragrafo > 0 else ""
        self._apri_articolo(
            pub=pub,
            file_path=f"Documents_{lingua_doc}/{documento_id}.html",
            prev_text=self._etichetta_indietro(),
            document=documento,
            ancora=ancora,
        )

    def _chiedi_download_segno(self, segno, pub: Publication) -> None:
        """La pubblicazione non c'e' piu': si chiede se scaricarla.

        Il segno resta nel database anche se il pacchetto e' stato tolto, ed
        e' voluto: cancellare un download non deve cancellare quello che
        l'utente ha segnato.  Ma senza file non c'e' niente da mostrare, e
        fingere che il segnalibro sia rotto sarebbe peggio che dirlo.
        """
        titolo = pub.displayTitle or getattr(segno, "title", "") or pub.keySymbol
        # La conferma e' una finestra senza bordi, in stile app: niente X,
        # niente barra del titolo, solo il testo e i due pulsanti.
        ConfermaApp.chiedi(
            self, "Pubblicazione non scaricata",
            f"«{titolo}» non e' scaricata.\n\nVuoi scaricarla adesso?",
            "Scarica", lambda: self._scarica_segno(segno, pub, titolo))

    def _scarica_segno(self, segno, pub: Publication, titolo: str) -> None:
        numero = ""
        numero_edizione = int(getattr(segno, "issueTagNumber", 0) or 0)
        if numero_edizione:
            numero = str(numero_edizione)
        trovata = self._cerca_pubblicazione(
            pub.keySymbol,
            int(getattr(segno, "mepsLanguageId", 0)
                or pub.mepsLanguageId or Lingua.corrente_id()),
            numero,
        )
        if trovata is None:
            self._mostra_messaggio(
                f"Non trovo «{titolo}» nel catalogo: non posso scaricarla.")
            return

        catalogo = self._catalogo()
        if catalogo is None or not hasattr(catalogo, "scarica"):
            return
        # Il segno si riprende quando il pacchetto e' davvero completo:
        # `PubView.scaricata` arriva dopo i capitoli, non dopo il solo
        # pacchetto.  Vedi `_riprendi_posizione_in_attesa`.
        self._posizione_in_attesa = segno
        catalogo.scarica(trovata)
        self.mostra_toast(
            f"Scaricamento avviato: {trovata.displayTitle}", "info", 4000)

    def _riprendi_posizione_in_attesa(self) -> None:
        """Apre il segnalibro che aspettava il download appena finito."""
        segno = self._posizione_in_attesa
        if segno is None:
            return

        documento_id = int(getattr(segno, "documentId", 0) or 0)
        sigla = str(getattr(segno, "keySymbol", "") or "")
        if documento_id <= 0 or not sigla:
            self._posizione_in_attesa = None
            return
        pub = Publication(
            ID=0, keySymbol=sigla, year=0,
            mepsLanguageId=int(getattr(segno, "mepsLanguageId", 0) or 0),
            publicationTypeId=0,
            issueTagNumber=int(getattr(segno, "issueTagNumber", 0) or 0),
            title=str(getattr(segno, "title", "") or sigla),
        )
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        percorso = (get_documents_directory()
                    / f"Documents_{Lingua.da_numero(int(getattr(segno, 'mepsLanguageId', 0) or Lingua.corrente_id()))}" / f"{documento_id}.html")
        if not percorso.is_file():
            # Non e' ancora arrivato, o il download e' di un'altra cosa.
            return

        self._posizione_in_attesa = None
        # Un giro di eventi dopo: `PubView` apre la sua schermata dei
        # capitoli subito dopo aver emesso `scaricata`, e senza questo rinvio
        # l'articolo del segnalibro finirebbe **sotto** quella schermata.
        QTimer.singleShot(0, lambda: self._apri_posizione(segno))

    def _aperta_il_giorno(self, pagina: dict) -> None:
        """Il riquadro del giorno e' stato premuto: si apre la pagina di oggi.

        LA STESSA STRADA DI QUALUNQUE PUBBLICAZIONE
        -------------------------------------------
        Non si apre niente di nuovo: si prende la sezione Pubblicazioni — che
        e' quella che sa aprire le pubblicazioni, e l'unica che lo sa —, si
        imposta la pubblicazione e si le dice quale capitolo aprire.  Il
        capitolo e l'`id` del paragrafo vengono dal pacchetto, non da una
        ricerca fra le righe del catalogo.

        Il perche' e' in `PubView.apri_il_giorno`: per questa pubblicazione il
        pacchetto e' l'elenco dei dodici mesi, quindi aprire il pacchetto
        senza il paragrafo aprirebbe il primo giorno del mese con la data di
        oggi scritta sopra — la pagina sbagliata con la data giusta, che e' il
        modo peggiore di sbagliare.
        """
        sezione = self._catalogo()
        if sezione is None or not hasattr(sezione, "apri_il_giorno"):
            return
        from Utility import JWPubManager

        sigla = JWPubManager.sigla_del_giorno()
        if not sigla:
            self._mostra_messaggio(
                "Le Scritture del giorno non sono scaricate:Aprilo prima.")
            return
        numero = Lingua.da_simbolo(Lingua.corrente_simbolo())
        pub = Publication(ID=0, keySymbol=sigla, year=0, mepsLanguageId=numero,
                          publicationTypeId=0, issueTagNumber=0, title=sigla)
        sezione.apri_il_giorno(pub, pagina if isinstance(pagina, dict) else {})

    def _aggiornamento_arrivato(self) -> None:
        """Il controllo e' finito: la Home mostra il riepilogo.

        Non si tocca la Home se non e' quella che si sta guardando:
        riaprirla mentre l'utente e' su un capitolo nasconderebbe quello
        che sta leggendo.
        """
        corrente = self.pila.currentWidget()
        if isinstance(corrente, HomeView):
            corrente.aggiorna_riepilogo()

    def _aggiorna_schermata(self) -> None:
        """Il pulsante di aggiornamento: riapre quello che si sta guardando.

        UNA SEZIONE, O UN CAPITOLO
        -------------------------
        Una sezione si riapre ricreandola: e' il modo che c'e' da quando le
        sezioni esistono, e rilegge il catalogo, le card e le liste.

        Un capitolo non e' una sezione: e' una schermata sopra un'altra, e
        non si ricrea — si **ricarica**.  Senza questo, il pulsante
        dell'aggiornamento mentre si legge non faceva niente, che e' la cosa
        peggiore che possa fare un pulsante.
        """
        corrente = self.pila.currentWidget()
        ricarica = getattr(corrente, "ricarica", None)
        if callable(ricarica):
            ricarica()
            return
        for titolo, seziona in self.sezioni.items():
            if seziona is corrente:
                nuovo = self._crea_sezione(titolo)
                self.sezioni[titolo] = nuovo
                self._segna_permanente(nuovo)
                self.pila.addWidget(nuovo)
                self._collega(nuovo)
                vecchia = self.pila.currentWidget()
                self.pila.setCurrentWidget(nuovo)
                self.pila.removeWidget(vecchia)
                self._sostituisci_nella_cronologia(vecchia, nuovo)
                vecchia.deleteLater()
                # Quello che si riapre e' una **sezione**, e le sezioni non
                # hanno una barra loro.  Se ne restasse una di una schermata
                # aperta prima, starebbe lì sopra la sezione nuova, con il
                # nome di un pezzo che non c'è più.
                self._metti_la_barra(None)
                return

    def _apri_menu_lingua(self) -> None:
        """Apre il menu della lingua sotto al pulsante.

        `popup()` e non `exec()`: `exec()` parte con un ciclo di eventi che
        blocca questa funzione fino a quando il menu non si chiude, e
        `_strumento` resterebbe dentro `exec` per tutto il tempo in cui
        l'utente guarda il menu.  Non succede niente di male, ma il codice
        sembra bloccato e il pulsante resta premuto a vista.

        Il menu si costruisce qui e non una volta sola perche' deve mostrare
        la lingua di adesso: una lingua cambiata in un'altra finestra (o
        scritta a mano nel file delle impostazioni) deve comparire con la
        spunta giusta, e un menu costruito all'avvio mostrerebbe quella di
        allora.
        """
        # Nella Bibbia lo stesso pulsante cambia la lingua della Bibbia, non
        # quella di tutta l'app.
        corrente = self.pila.currentWidget()
        if corrente.__class__.__name__ == "BibleView":
            corrente.apri_selettore_lingua()
            return
        menu = LinguaMenu(self)
        menu.scelta.connect(self._lingua_scelta)
        # Il menu non ha un genitore che lo tenga vivo: senza questa riga
        # verrebbe liberato appena questo metodo finisce, mentre e' aperto.
        self._menu_lingua = menu
        menu.popup(QCursor.pos())

    def _lingua_scelta(self, numero: int) -> None:
        """Una lingua e' stata scelta: si cambia e si rilegge tutto.

        PERCHE' SI RILEGGONO TUTTE LE SEZIONI E NON SOLO QUELLA CORRENTE
        ---------------------------------------------------------------
        `_aggiorna_schermata` rilegge solo quello che si sta guardando, e va
        bene per il pulsante Aggiorna: il resto dell'app non e' cambiato.  La
        lingua invece cambia il catalogo, le copertine, le categorie dei media
        e le notizie, quindi tutto.  Rileggere solo la sezione corrente
        lascerebbe la Home con i Preferiti in italiano sopra un catalogo
        spagnolo, e si scopre solo andando in un'altra sezione e tornando.

        PERCHE' IL PULSANTE "AGGIOORNA" NON SERVE
        -----------------------------------------
        Perche' `Lingua.imposta` scrive gia' il file delle impostazioni.  Il
        pulsante serve per controllare il server; qui il server e' gia' stato
        chiesto e ha risposto, e rifarlo sarebbe una richiesta di troppo.
        """
        aperta = self._pub_aperta_adesso()
        voce_lingua = Lingua.per_id(numero) or {}
        if not WolLingua.supportata(voce_lingua.get("simbolo", "")):
            ConfermaApp.chiedi(
                self, "Cambio lingua",
                f"Il sito non ha il testo in {voce_lingua.get('nome_vernacolare') or 'questa lingua'}.\n\n"
                "Potrai usare catalogo, audio e video, ma non leggere i capitoli.\n\n"
                "Vuoi cambiare lingua comunque?", "Cambia",
                lambda: self._cambia_lingua_ora(numero, aperta))
            return
        self._cambia_lingua_ora(numero, aperta)

    def _cambia_lingua_ora(self, numero, aperta) -> None:
        self.mostra_toast("Cambio lingua…", "info", 2500)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        if not Lingua.imposta(numero):
            return
        self._ricrea_tutte_sezioni()
        self.set_titolo(self.nome.text())
        if aperta is not None:
            QTimer.singleShot(0, lambda: self._riapri_nella_lingua(aperta))

    def _pub_aperta_adesso(self):
        """(sigla, numero edizione, titolo) della pubblicazione aperta, o None."""
        corrente = self.pila.currentWidget()
        pub = getattr(corrente, "pub", None) or getattr(corrente, "_pub", None)
        if pub is None or getattr(pub, "isBible", False):
            return None
        sigla = getattr(pub, "keySymbol", "")
        if not sigla:
            return None
        tag = int(getattr(pub, "issueTagNumber", 0) or 0)
        testo = str(tag)
        edizione = "" if not tag else (testo[:-2] if testo.endswith("00") else testo)
        titolo = (getattr(pub, "displayTitle", "") or getattr(pub, "title", "")
                  or sigla)
        return sigla, edizione, titolo

    def _riapri_nella_lingua(self, aperta) -> None:
        """Dopo il cambio lingua riapre la stessa pubblicazione, o propone di scaricarla."""
        from Utility import Copertine

        sigla, edizione, titolo = aperta
        pub = self._cerca_pubblicazione(sigla, Lingua.corrente_id(), edizione)
        if pub is None:
            self._mostra_messaggio(
                f"«{titolo}» non \u00e8 disponibile in questa lingua.")
            return
        if Copertine.pacchetto_locale(pub):
            self._apri_pubblicazione_scelta(pub)
            return
        messaggio = QMessageBox(self)
        messaggio.setWindowTitle("Pubblicazione non scaricata")
        messaggio.setText(
            f"«{pub.displayTitle or titolo}» non \u00e8 scaricata in questa lingua."
            "\n\nVuoi scaricarla adesso?")
        messaggio.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        messaggio.setDefaultButton(QMessageBox.StandardButton.Yes)
        messaggio.setWindowFlags(Qt.WindowType.FramelessWindowHint
                                 | Qt.WindowType.Dialog)
        if messaggio.exec() == QMessageBox.StandardButton.Yes:
            self._scarica_una_pubblicazione({
                "sigla": sigla, "lingua": Lingua.corrente_simbolo(),
                "numero": edizione, "titolo": titolo, "apri": True})

    def _sostituisci_nella_cronologia(self, vecchia, nuova) -> None:
        """Nella cronologia al posto della sezione distrutta mette quella nuova."""
        self._schermate = [nuova if w is vecchia else w for w in self._schermate]
        self._avanti = [nuova if w is vecchia else w for w in self._avanti]
        if getattr(self, "_schermo_corrente", None) is vecchia:
            self._schermo_corrente = nuova

    def _ricrea_tutte_sezioni(self) -> None:
        """Ricrea tutte le sezioni, restando sulla stessa sezione.

        La sezione da cui si e' partiti e' quella che torna: cambiare lingua
        non e' un atto di navigazione, e spostare l'utente sulla Home
        sarebbe fargli perdere quello che stava leggendo.

        PERCHE' NON SI SEMPLICEMENTE SOSTITUISCE LA PILA
        ------------------------------------------------
        La finestra tiene la sezione corrente in `self.sezioni`, per titolo, e
        la pila contiene anche le schermate aperte dentro una sezione (un
        capitolo, un articolo).  Se si sostituissero le voci di `self.sezioni`
        e basta, la schermata aperta dentro la sezione resterebbe quella
        vecchia, in italiano, sopra una sezione nuova in italiano: si
        vedrebbe una sola schermata cambiata e le altre no.

        Quindi si rifanno tutte le voci, si rimette dentro la pila la
        schermata giusta e poi si richiama `_seleziona_nome`, che e' il
        posto unico dove si sceglie la sezione e che azzera anche la pila
        delle schermate aperte.
        """
        corrente = self.pila.currentWidget()
        titolo_corrente = ""
        for titolo, schermata in self.sezioni.items():
            if schermata is corrente:
                titolo_corrente = titolo
                break
        # Dentro una pubblicazione aperta la schermata corrente non e' una
        # sezione: si resta nella sezione da cui si era partiti, non nella prima.
        if not titolo_corrente:
            titolo_corrente = self._sezione_attiva or self._sezione_dove_sei() or ""

        vecchie = []
        for titolo, _simbolo in SEZIONI:
            vecchia = self.sezioni.get(titolo)
            if vecchia is None:
                continue
            nuovo = self._crea_sezione(titolo)
            self.sezioni[titolo] = nuovo
            self._segna_permanente(nuovo)
            self.pila.addWidget(nuovo)
            self._collega(nuovo)
            self._sostituisci_nella_cronologia(vecchia, nuovo)
            vecchie.append(vecchia)

        # Le schermate aperte dentro le sezioni (capitoli, articoli) sono nella
        # lingua vecchia: si chiudono, insieme alla cronologia che le citava.
        nuove = set(id(w) for w in self.sezioni.values())
        for i in range(self.pila.count() - 1, -1, -1):
            w = self.pila.widget(i)
            if w is None or id(w) in nuove or w in vecchie:
                continue
            if self._se_permanente(w):
                continue
            self.pila.removeWidget(w)
            w.deleteLater()
        for vecchia in vecchie:
            self.pila.removeWidget(vecchia)
            vecchia.deleteLater()
        self._schermate = [w for w in self._schermate if w is not None and id(w) in nuove]
        self._avanti = [w for w in self._avanti if w is not None and id(w) in nuove]
        if not self._schermate:
            self._schermate = [self.sezioni[SEZIONI[0][0]]]

        # IL LETTORE GRANDE NUOVO E' CHIUSO
        # ----------------------------------
        # La sezione Media e' stata rifatta da capo, e quella nuova ha un
        # lettore grande che non si e' ancora visto: quello di prima e' stato
        # cancellato.  Senza questa riga la finestra continuerebbe a dire
        # «il lettore grande e' aperto» guardando un lettore che non esiste
        # piu', e la striscia in fondo resterebbe spenta anche se un brano
        # continua a suonare.
        #
        # Non si rimette su per forza: se suona ancora qualcosa, e' `_mini_stato`
        # — che `_seleziona_nome` chiama subito sotto — a rimetterla.
        self._lettore_grande_visibile = False

        self._seleziona_nome(titolo_corrente or SEZIONI[0][0])

    def _nascondi_mini(self) -> None:
        """La striscia si nasconde.  E basta.

        Qui, prima, c'era anche un interruttore che diceva «l'utente non la vuole
        piu'», ed e' stato tolto perche' non e' mai stato quello il problema:
        la striscia spariva **da sola** appena si usciva dalla sezione Media,
        e non tornava piu'.

        Il motivo e' che questa funzione e' collegata al segnale `vuoto` del
        motore, e quel segnale non vuol dire «l'utente non la vuole piu'»:
        vuol dire «adesso non c'e' niente da mettere nella striscia».  Sono
        due domande diverse, e la seconda la risponde solo quello che si
        vede: col lettore grande aperto la striscia non c'e', in ogni altra
        sezione c'e'.

        Quindi qui si nasconde e basta, e `vuoto` torna a rimetterla su da
        solo appena il motore ha di nuovo qualcosa da dire.
        """
        self.mini.setVisible(False)

    def _mostra_attesa(self, occupato: bool) -> None:
        # La barra sparisce quando `busyChanged` torna a False, e non prima:
        # fra il pacchetto e i testi dei capitoli c'e' un momento in cui non
        # si scarica piu' niente ma il lavoro non e' finito, e una barra che
        # sparisce li' direbbe "pronto" mentre il programpo scrive ancora.
        if not occupato:
            self._scaricamento_finito()

    def _mostra_messaggio(self, testo: str) -> None:
        """Mostra un messaggio. Per errori critici usa modal, per info usa toast."""
        # Parole chiave che indicano un errore critico -> modal
        error_keywords = ("errore", "non riesco", "impossibile", "fallito", 
                          "non trovato", "non valido", "cancellare", "eliminare")
        testo_lower = testo.lower()
        
        # Se contiene parole di errore -> QMessageBox (modal)
        if any(kw in testo_lower for kw in error_keywords):
            popup = QMessageBox(self)
            popup.setIcon(QMessageBox.Icon.Warning)
            popup.setText(testo)
            popup.setStandardButtons(QMessageBox.StandardButton.Ok)
            popup.setWindowFlags(Qt.WindowType.FramelessWindowHint
                                 | Qt.WindowType.Dialog)
            popup.exec()
        else:
            # Altrimenti -> toast non bloccante
            self.mostra_toast(testo, "info", 4000)

    # ------------------------------------------------------------------
    # SECONDO PIANO
    # ------------------------------------------------------------------
    # La X della finestra principale, se un video suona o un timer e' in
    # corso, non chiude il programma: nasconde la finestra e mette un'icona
    # nell'area di notifica.  Un clic (o «Apri») la riporta.  I monitor
    # esterni non si toccano: restano accesi, perche' sono loro che stanno
    # mostrando il video o il timer.  Con tutto fermo la X chiude come sempre.

    def _cosa_e_in_corso(self) -> bool:
        """Suona un video o un audio, o il timer e' partito?"""
        try:
            from Utility import Lettore
            if Lettore.motore().sta_suonando():
                return True
        except Exception:  # noqa: BLE001
            pass
        try:
            finestra = self.sezioni.get("Timer")
            controllo = getattr(finestra, "timer_controller", None)
            if controllo is not None:
                from src.models.timer import TimerState
                return controllo.timer.state != TimerState.STOPPED
        except Exception:  # noqa: BLE001
            pass
        return False

    def _crea_icona_sfondo(self) -> None:
        """L'icona nell'area di notifica: c'e' fin dall'avvio."""
        from PyQt6.QtWidgets import QMenu, QSystemTrayIcon
        if getattr(self, "_icona_sfondo", None) is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        # L'icona dell'applicazione: quella della finestra, a questo punto, puo'
        # essere ancora vuota (la riga che la mette arriva dopo la costruzione),
        # e un'icona vuota nell'area di notifica non si vede.
        grafica = self.windowIcon()
        if grafica.isNull():
            from PyQt6.QtGui import QGuiApplication
            grafica = QGuiApplication.windowIcon()
        if grafica.isNull():
            from pathlib import Path
            from PyQt6.QtGui import QIcon
            grafica = QIcon(str(Path(__file__).resolve().parent / "Files" / "icons" / "64.png"))
        icona = QSystemTrayIcon(grafica, self)
        icona.setToolTip("JW LibriX")
        menu = QMenu(self)
        menu.addAction("Apri JW LibriX", self._torna_in_primo_piano)
        menu.addSeparator()
        menu.addAction("Esci", self._esci_davvero)
        icona.setContextMenu(menu)
        icona.activated.connect(self._icona_sfondo_cliccata)
        self._icona_sfondo = icona
        self._menu_sfondo = menu
        icona.show()

    def _vai_in_secondo_piano(self) -> bool:
        """Nasconde la finestra; l'icona resta.  False se non si puo'."""
        self._crea_icona_sfondo()
        if getattr(self, "_icona_sfondo", None) is None:
            return False
        # Senza questo Qt chiude il programma appena l'ultima finestra
        # visibile si nasconde: e' la ragione per cui un clic sull'icona
        # trovava gia' tutto chiuso.
        from PyQt6.QtWidgets import QApplication
        QApplication.setQuitOnLastWindowClosed(False)
        self.hide()
        return True

    def _icona_sfondo_cliccata(self, motivo) -> None:
        from PyQt6.QtWidgets import QSystemTrayIcon
        # Il tasto destro apre il menu da solo: qui solo clic e doppio clic.
        if motivo in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._torna_in_primo_piano()

    def _torna_in_primo_piano(self) -> None:
        from PyQt6.QtWidgets import QApplication
        QApplication.setQuitOnLastWindowClosed(True)
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _esci_davvero(self) -> None:
        self._uscita_vera = True
        from PyQt6.QtWidgets import QApplication
        QApplication.setQuitOnLastWindowClosed(True)
        icona = getattr(self, "_icona_sfondo", None)
        if icona is not None:
            icona.hide()
        self.show()
        self.close()

    def closeEvent(self, evento) -> None:
        if (not getattr(self, "_uscita_vera", False)
                and self._cosa_e_in_corso() and self._vai_in_secondo_piano()):
            evento.ignore()
            return
        # LA FINESTRA DELLO SCHERMO SECONDARIO, PRIMA DI TUTTO
        # -------------------------------------------------------
        # Quella finestra e' a tutto schermo, senza bordo e senza comandi, e
        # per costruzione non si chiude da se': sta accesa apposta.  Quindi se
        # il programma finisce e lei resta, l'utente si ritrova il monitor
        # secondario acceso con dentro il verso del giorno e nessun
        # programma che lo governi — e senza modo di chiuderlo, perche' non
        # c'e' niente da premere.
        #
        # Va chiusa per prima, prima ancora di fermare l'audio: e' una
        # finestra senza bordi, quindi chiudere il programma non la chiude da
        # solo, e aspettare che Qt lo faccia lascia un attimo in cui il
        # monitor e' ancora acceso e non c'e' piu' niente che lo controlli.
        try:
            from SubViews.SchermoEsterno import chiudi_se_ce_n_e
            # `permanente=True`: il programma sta chiudendo, quindi la
            # finestra **non** rimette il video dentro l'app.  Emettere
            # `annullata` qui faceva ricollegare il video e riaccendere lo
            # specchio dentro una finestra che si stava chiudendo — ed e' la
            # causa del blocco segnalato: il programma non rispondeva, il video
            # restava fermo e il secondo schermo restava acceso.  Vedi la nota
            # di `chiudi_se_ce_n_e`.
            chiudi_se_ce_n_e(permanente=True)
        except Exception:  # noqa: BLE001 - non si deve impedire la chiusura
            pass
        # Si ferma anche l'audio.  Chiudere la finestra con un video che
        # suona e' la cosa piu' normale del mondo: l'utente chiude il
        # programma e il video continua.  Il backend di riproduzione vive
        # piu' a lungo della finestra, quindi senza questa riga l'audio
        # continua finche' non si chiude l'applicazione da un'altra parte.
        try:
            from Utility import Lettore
            Lettore.motore().ferma()
        except Exception:  # noqa: BLE001 - non si deve impedire la chiusura
            pass
        from Utility.UserData.BackupManager import BackupManager
        BackupManager.store_data_in_db()
        self._arma_uscita_di_sicurezza()
        super().closeEvent(evento)

    def _arma_uscita_di_sicurezza(self) -> None:
        """Se il programma non esce entro poco, esce comunque.

        IL PERCHE' DELL'USCITA FORZATA
        ------------------------------
        Un programma con un video che suona ha dentro un motore di
        riproduzione che parla con una libreria esterna, e quella libreria
        piu' volte non si accorge che il programma sta morendo.  Il
        risultato e' una finestra chiusa con dentro un programma che non esce
        piu': la X non serve piu' a niente e l'unica cosa che resta e'
        terminarlo a mano dal gestore dei processi.

        E' successo: chiudere il programma con un video sul secondo schermo
        richiedeva di premere Alt+F4 sul monitor secondario, poi Alt+F4
        ancora, e solo dopo la finestra si chiudeva.

        Qui non si corregge il motore — quello sta dentro Qt e non e' nostro —
        ma si mette un limite: se tra poco non e' successo niente, si esce.
        Un programma che si chiude un istante **meglio tardi** e' sempre
        preferibile a un programma che non si chiude piu'.

        PERCHE' IL TEMPO E' DI DUE SECONDI
        ----------------------------------
        Deve essere abbastanza lungo da non interrompere una chiusura che
        funziona, e abbastanza corto da non lasciare l'utente davanti a una
        finestra che non reagisce.  Il salvataggio e' gia' fatto a questo
        punto, quindi non si perde niente: due secondi servono solo a dare
        tempo al motore di chiudersi con le sue maniere.
        """
        import os

        from PyQt6.QtCore import QTimer

        # Il timer e' figlio di questa finestra: se il programma esce come si
        # deve, il timer muore con lui e non arriva mai a sparare.
        salvatore = QTimer(self)
        salvatore.setSingleShot(True)
        salvatore.timeout.connect(lambda: os._exit(0))
        salvatore.start(2000)
        self._salvatore_uscita = salvatore


