#
#  HomeView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""La Home: il testo del giorno, i Preferiti, Novita' e aggiornamenti.

LA STRUTTURA E' QUELLA DELLA APP PRECEDENTE
--------------------------------------------
Tre pezzi, in quest'ordine, e non e' una scelta:

    1. il testo del giorno, in cima, centrato
    2. Preferiti, in griglia di card quadrate
    3. Novita' e aggiornamenti, in fila orizzontale

La griglia e' a cinque colonne e la fila e' a scorrimento.  La differenza
non e' un caso: i Preferiti sono scelti dall'utente e sono pochi, quindi
stanno in fila e si vedono tutti; Novita' e' un elenco che cresce
ogni settimana, quindi sta in fila e scorre, e non spinge la pagina.

LE MISURE NON SONO UNDICATE
----------------------------
Vengono dalla specifica della app precedente, che le dichiara:

    testo del giorno   pannello, bordo 1, raggio 4, padding 14 28, min 380
    la data             15 px, grassetto 600
    la riga sotto       12 px, colore secondario
    titolo di sezione   13 px, grassetto 600, margine sotto 9
    griglia             5 colonne, vuoto 10, margine sotto 18
    la card             quadrata, bordo 1, raggio 4
    il titolo della card 12 px, grassetto 600, margine sopra 6
    la fila Novita'      card larghe 128, vuoto 10

IL VUOTO SI DICE
---------------
Se non ci sono Preferiti, la sezione resta e dice che non ce ne sono.  Una
sezione che sparisce sembra un difetto; una sezione vuota con scritto
"nessun preferito" dice la verita' e lascia capire dove metterli.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal as Signal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from Utility import Aggiornamenti, Argomento, Notizie, Preferiti, tema
from Utility.Stuff import icon

# Le colonne della griglia, per larghezza di finestra.  Cinque com'e' nella
# app precedente, poi quattro, tre, due: la regola e' che la card non
# diventa piu' piccola di una larghezza che la rende illeggibile.
#: L'altezza della striscia dei Preferiti: l'anteprima quadrata (124) + il
#: titolo su due righe + il sottotitolo, piu' un margine.
#:
#: Prima c'era anche la riga dei tre puntini (22 pixel): adesso i due bottoni
#: stanno **dentro** la miniatura, quindi la riga non c'e' piu' e l'altezza
#: scende di 22.
#:
#: Con 200 il sottotitolo — la sigla sotto il titolo — veniva tagliato:
#: la card c'e' intera ma la sua ultima riga no, e una riga tagliata a
#: meta' sembra un difetto della finestra e non della misura.
#:
#: Fissa e non calcolata: una striscia che cambia altezza mentre si aggiunge
#: un Preferito sposta tutto quello che sta sotto, e sotto c'e' la sezione
#: Novita'.  Meglio un pezzo di vuoto che un salto a ogni Preferito.
ALTEZZA_STRISCIA = 202

#: La larghezza di una card dei Preferiti.  Fissa perche' in orizzontale le
#: card si sommano: se la larghezza la prendesse dal titolo, una card con un
#: titolo su due righe sarebbe larga piu' di una con il titolo su una, e la
#: striscia verrebbe storta.
#:
#: 140 e non 170: un filo piu' piccole, come chiesto.  Non molto piu' piccole
#: perche' sotto i 130 la copertina non si distingue piu' e il titolo va su
#: tre righe, e allora la card e' alta e stretta e sembra una lista.
LARGHEZZA_CARD = 140

#: Il lato dell'anteprima quadrata dentro la card.
LATO_ANTEPRIMA = 124

#: L'altezza della striscia delle Notizie.  Piu' alta dei Preferiti perche'
#: i titoli di una notizia sono lunghi: a 140 pixel "Una storica decisione
#: sull'obiezione di coscienza in Svezia" va su tre righe, e sotto ci sono
#: ancora la sezione e la data.  Con l'altezza dei Preferiti (224) la riga
#: della sezione finiva tagliata: la card c'era intera, l'ultima riga no, e
#: una riga tagliata a meta' sembra un difetto della finestra e non della
#: misura.
#:
#: Le due strisce hanno la stessa larghezza di card e la stessa anteprima
#: quadrata, quindi prendono la stessa aria: cambia solo quanto in basso
#: arriva il testo, e quello e' un fatto dei titoli.
#:
#: Il caso piu' alto che si e' misurato sulle 19 notizie del 2 ottobre 2026 e'
#: "Concerto biblico | 'Se possibile (...) i state pacifici con tutti'",
#: che fa tre righe di titolo e tre di sezione.  Con 268 finiva tagliato
#: l'anno.  Non si accorcia il testo per farlo entrare — il titolo e' del
#: sito e la sezione dice da dove viene — quindi la striscia e' alta quanto
#: serve.
ALTEZZA_STRISCIA_NOTIZIE = 306

#: Ogni quanto si rilegge l'argomento principale della home, in secondi.
#:
#: Mezz'ora e' una misura grossolana e va bene: l'argomento del sito
#: cambia una volta alla settimana, e nessuno guarda l'orologio per il
#: tempo che passa fra un controllo e l'altro.  Quel che conta e' che non
#: sia a ogni apertura del programma.
RICONTROLLO_ARGOMENTO = 30 * 60

#: Non si chiede la home se l'ultima richiesta e' stata meno di un quarto
#: d'ora fa.  Il timer passa ogni mezzora e la Home compare ogni volta che
#: l'utente ci va: senza questo, ogni andata e ritorno sarebbe una
#: richiesta, e aprire il programma la mattina e leggerlo la sera farebbe
#: una dozzina di richieste per la stessa pagina.
MINIMO_ARGOMENTO = 15 * 60

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì",
          "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


class _RiquadroGiorno(QWidget):
    """La data di oggi e il versetto del giorno, o il tasto per scaricarlo.

    COSA C'E' DENTRO, E PERCHE' NON C'E' PIU' «APRI IL VERSETTO»
    -------------------------------------------------------------
    Prima c'era la data e sotto la scritta «Apri il versetto di oggi dalla
    Bibbia».  Quella scritta e' sparita perche' era una promessa: non si
    poteva aprire niente.  Al suo posto c'e' **il testo vero**, letto dal
    pacchetto scaricato, e una riga sola:

        Geova e' colui che esamina i cuori (Prov. 17:3)

    Il commento che segue quella riga dentro il pacchetto non si prende: sono
    righe e righe, e qui ci sta una riga da leggere.  Il primo pezzo e' il
    versetto; se un giorno volessi anche il commento, e' un'altra riga e un
    altro pezzo — non e' che questo sia troppo corto.

    IL RIQUADRO SI PREME, E APRE TUTTO IL GIORNO
    --------------------------------------------
    Premendolo si apre la pagina del giorno nel capitolo del mese, sul
    paragrafo di oggi.  Tutto: versetto, commento e titoli.  Qui dentro si
    vede solo il primo pezzo, perche' il resto non ci starebbe e non e' quello
    che si legge a colpo d'occhio.

    E' la promessa che faceva la scritta di prima, resa vera.  Il capitolo e il
    paragrafo sono quelli del pacchetto, non una ricerca: vedi
    `JWPubManager.pagina_del_giorno`, che li legge dalla stessa riga da cui si
    legge il testo qui, quindi non possono dire cose diverse.

    IL TESTO E' COME NELLA PAGINA, MA NON E' UN COLLEGAMENTO
    -------------------------------------------------------
    Nel pacchetto il riferimento bibrico fra parentesi e' un collegamento, e
    nella sezione Articolo e' blu e si preme.  Qui non e' blu e non si preme,
    perche' questo riquadro non apre niente da solo — si preme il riquadro, non
    la parola.  Un colore che dicesse «cliccami» su una cosa che non si preme
    e' una promessa falsa.  Il testo e' pero' quello intero, riferimento
    compreso, perche' senza il riferimento non si sa di che si parla.
    """

    #: L'utente ha premuto il tasto: (sigla della pubblicazione da scaricare)
    scaricaRichiesta = Signal(object)
    #: L'utente ha premuto «Annulla» durante lo scaricamento
    annullaRichiesta = Signal()
    #: Il riquadro e' stato premuto: (la pagina di oggi)
    #:
    #: La pagina e' un dizionario di `JWPubManager.pagina_del_giorno`, cioe' il
    #: capitolo del mese e l'`id` del paragrafo di oggi.  Non si manda «apri il
    #: pacchetto»: per questa pubblicazione il pacchetto e' l'elenco dei
    #: dodici mesi, e senza il paragrafo si aprirebbe il primo giorno del mese
    #: con la data di oggi scritta sopra.
    aperta = Signal(object)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self._in_corso = False
        # Il cursore a mano e' quello che dice «qui si puo' premere».  Senza, un
        # riquadro che si preme sembra un riquadro che si guarda.
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._costruisci()

    # ------------------------------------------------------------------

    def _costruisci(self) -> None:
        """Il riquadro, con quello che c'e' da mostrare adesso.

        I widget vecchi si buttano con `deleteLater()` e non con
        `setParent(None)`: staccarli li trasformerebbe in finestre a se', e
        quando Python li butterebbe fuori Qt li distruggerebbe una seconda
        volta.  Misurato: `abort()` senza nessuna riga di traceback.  E'
        `deleteLater()` che usano anche `DownloadsView` e `UpdatesView`.
        """
        # Il layout di dentro, quello che si svuota.  Quello di `self` non si
        # tocca: e' il contenitore fisso, e rifarlo a ogni lettura significherebbe
        # ricreare il riquadro intero dalla finestra che lo contiene.
        if not hasattr(self, "_scatola") or self._scatola is None:
            # `tema.sfondo` **restituisce lo stesso widget** che riceve, quindi
            # qui dentro va un `QWidget` nuovo e non `self`.
            #
            # Passando `self` il riquadro diventava il contenitore stesso, e
            # quindi prendeva due layout — uno per la scatola e uno per il
            # testo — e Qt lo diceva:
            #
            #     QLayout: Cannot add parent widget _RiquadroGiorno/testoGiorno
            #              to its child layout QVBoxLayout/
            #     QLayout: Attempting to add QLayout "" to _RiquadroGiorno
            #              "testoGiorno", which already has a layout
            #
            # e il riquadro spariva del tutto: costruito, con i suoi due
            # layout, e senza niente dentro.
            #
            # La scatola e' quindi un figlio vero, e il layout di fuori sta su
            # `self`.  Come faceva il pezzo di prima, che creava il suo
            # `QWidget(padre)`.
            self._scatola = tema.sfondo(QWidget(self), "testoGiorno")
            esterno = QVBoxLayout(self)
            esterno.setContentsMargins(0, 0, 0, 0)
            esterno.addWidget(self._scatola)
            self._dentro = QVBoxLayout(self._scatola)
            self._dentro.setContentsMargins(28, 16, 28, 18)
            self._dentro.setSpacing(6)
        else:
            while self._dentro.count():
                elemento = self._dentro.takeAt(0)
                widget = elemento.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

        from Utility import JWPubManager

        ora = time.localtime()
        # tm_wday e' 0 il lunedi', ma la lista comincia dal lunedi' quindi
        # l'indice e' gia' quello giusto.
        data = QLabel(f"{GIORNI[ora.tm_wday]}, {ora.tm_mday} "
                      f"{MESI[ora.tm_mon - 1]}", self._scatola)
        data.setObjectName("giorno")
        data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dentro.addWidget(data)

        # Il versetto si legge **una** volta e si tiene in mano.
        #
        # Prima veniva chiesto due volte, una per decidere e una per il testo.
        # Funzionava, ma rileggeva il pacchetto due volte a ogni costruzione
        # del riquadro, e la seconda lettura poteva dare un testo diverso dalla
        # prima: se la mezzanotte passa fra le due, la riga del giorno
        # precedente finirebbe sotto la data di quello nuovo.  Non e' un
        # difetto che si vede spesso, e proprio per questo e' peggiore.
        versetto = JWPubManager.versetto_del_giorno()
        if versetto:
            corpo = QLabel(versetto, self._scatola)
            corpo.setObjectName("versettoGiorno")
            corpo.setWordWrap(True)
            corpo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dentro.addWidget(corpo)
        else:
            self._dentro.addWidget(self._tasto_scarica())

    def rileggi(self) -> None:
        """Un pacchetto e' arrivato: si rilegge tutto il riquadro.

        Si rilegge **tutto** e non si cambia una riga: il testo, il tasto e la
        data stanno nello stesso posto e con gli stessi nomi, e l'unica cosa
        che cambia e' quale dei due si vede.  E non si rilegge a ogni avvio: il
        riquadro nasce gia' con la data e il versetto del giorno giusti.

        `_in_corso` torna a `False` anche quando il pacchetto **non** e'
        arrivato.  Il tasto che dice «Sto scaricando...» deve poter tornare a
        dire «Scarica»: se il download fallisce e il tasto resta li' in quelle
        parole per sempre, l'utente non ha piu' modo di riprovare senza
        chiudere e riaprire il programma.
        """
        self._in_corso = False
        self._fatti = self._totale = 0
        self._costruisci()

    # ------------------------------------------------------------------
    # LA BARRA DEL DOWNLOAD
    # ------------------------------------------------------------------

    def _barra_viva(self):
        """La barra se c'e' ancora, altrimenti None (il riquadro si rifa)."""
        from PyQt6 import sip
        barra = getattr(self, "_barra", None)
        if barra is None or sip.isdeleted(barra):
            return None
        return barra

    def _disegna_barra(self) -> None:
        barra = self._barra_viva()
        if barra is None:
            return
        fatti = getattr(self, "_fatti", 0)
        totale = getattr(self, "_totale", 0)
        if totale > 0:
            barra.setRange(0, totale)
            barra.setValue(min(fatti, totale))
            barra.setFormat(f"Scarico… {min(fatti, totale) * 100 // totale}%")
        else:
            barra.setRange(0, 0)       # non si sa ancora quanto: barra che scorre
            barra.setFormat("Scarico…")

    def scarico_inizia(self, totale: int = 0) -> None:
        """Un pezzo del download comincia (pacchetto o capitoli)."""
        self._fatti, self._totale = 0, totale
        if not self._in_corso:
            self._in_corso = True
            self._costruisci()
        else:
            self._disegna_barra()

    def scarico_avanza(self, fatti: int, totale: int) -> None:
        self._fatti, self._totale = fatti, totale
        if self._in_corso:
            self._disegna_barra()

    def _tasto_scarica(self) -> QWidget:
        """Il tasto che scarica la pubblicazione dell'anno, o la frase che
        spiega perche' non si puo'."""
        from Utility import JWPubManager

        sigla = JWPubManager.sigla_del_giorno()
        riga = QWidget(self._scatola)
        riga.setObjectName("rigaTastoGiorno")
        disposizione = QHBoxLayout(riga)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.addStretch(1)

        if not sigla:
            # La sigla viene dal catalogo, quindi "" vuol dire due cose diverse:
            # il catalogo non c'e' (primo avvio senza rete), o c'e' e l'edizione
            # di quest'anno non e' ancora uscita.  Prima si diceva sempre la
            # seconda, e con la cartella dati vuota era falso.  In nessuno dei
            # due casi si mette un tasto: la sigla non si indovina.
            from Utility import Aggiornamenti
            if Aggiornamenti._file_catalogo() is None:
                testo = ("Per le Scritture del giorno serve il catalogo: "
                         "premi Aggiorna in alto per scaricarlo.")
            else:
                testo = ("Sul server non c'e' ancora l'edizione di quest'anno "
                         "per le Scritture del giorno.")
            nota = QLabel(testo, riga)
            nota.setObjectName("nota")
            nota.setWordWrap(True)
            disposizione.addWidget(nota)
        else:
            if self._in_corso:
                # Al posto del tasto, nello stesso punto, la barra viola come
                # nel resto dell'app: si vede che scende e quanto manca.
                from PyQt6.QtWidgets import QProgressBar
                barra = QProgressBar(riga)
                barra.setObjectName("barraGiorno")
                barra.setTextVisible(True)
                barra.setAlignment(Qt.AlignmentFlag.AlignCenter)
                barra.setFixedSize(300, 22)
                barra.setStyleSheet(
                    "QProgressBar { background: #444444; color: #ffffff;"
                    " border: none; border-radius: 6px; font-size: 12px; }"
                    f" QProgressBar::chunk {{ background: {tema.ACCENTO};"
                    " border-radius: 6px; }")
                self._barra = barra
                self._disegna_barra()
                disposizione.addWidget(barra)
                annulla = QPushButton("Annulla", riga)
                annulla.setObjectName("tastoGiorno")
                annulla.setToolTip("Annulla scaricamento")

                def annullato() -> None:
                    annulla.setEnabled(False)
                    annulla.setText("Annullo…")
                    self.annullaRichiesta.emit()

                annulla.clicked.connect(annullato)
                disposizione.addWidget(annulla)
            else:
                self._barra = None
                tasto = QPushButton("Scarica le Scritture del giorno", riga)
                tasto.setObjectName("tastoGiorno")
                tasto.clicked.connect(self._premuto)
                disposizione.addWidget(tasto)

        disposizione.addStretch(1)
        return riga

    def _premuto(self) -> None:
        """Il tasto e' stato premuto: si chiede il pacchetto e si dice che si
        sta scaricando."""
        from Utility import JWPubManager
        from Utility import Lingua

        sigla = JWPubManager.sigla_del_giorno()
        if not sigla:
            return
        self._in_corso = True
        # La voce e' un dizionario e non un oggetto `Publication`: e' la forma
        # che `SidebarView._scarica_da_home` sa ricevere, e che usa gia' la
        # sezione Novita'.  Non se ne scrive una copia perche' li' la riga
        # vera si cerca nel catalogo, e qui si puo' fare lo stesso.
        self.scaricaRichiesta.emit({"sigla": sigla,
                                    "lingua": Lingua.corrente_simbolo(),
                                    "titolo": sigla,
                                    "pacchetto": True})
        # Il riquadro si rifa **dopo**, con un rinvio di zero millisecondi, e
        # non qui dentro: il click del bottone chiama questo, e se il bottone
        # venisse distrutto mentre il click e' ancora in corso Qt chiuderebbe la
        # finestra senza lasciare una riga di traceback.  Vedi
        # `WebBrowserArticleView` per lo stesso tipo di problema.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._costruisci)

    def mousePressEvent(self, evento) -> None:
        """Il riquadro premuto: si apre la pagina del giorno, per intero.

        Si preme solo se il pacchetto e' scaricato: senza, non c'e' niente da
        aprire, e li' c'e' il tasto per scaricare, che basta e avanza.
        """
        if evento.button() == Qt.MouseButton.LeftButton:
            from Utility import JWPubManager

            pagina = JWPubManager.pagina_del_giorno()
            if pagina:
                evento.accept()
                self.aperta.emit(pagina)
                return
        super().mousePressEvent(evento)


class _Cliccabile(QLabel):
    """Un pezzo che si preme per aprire l'articolo: il titolo o la foto.

    Non e' un vero link: un link aprirebbe il browser della macchina, e
    l'articolo deve aprirsi **dentro l'app**, come le notizie.  Quindi e' una
    cosa che si preme, e il cursore a mano e' la parte che dice «qui si puo'
    premere».

    Ce n'e' uno solo per il titolo e per la foto perche' fanno la stessa
    cosa: due classi che fanno lo stesso lavoro sono due posti in cui
    cambiare una cosa e dimenticare l'altro.
    """

    premuto = Signal()

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.premuto.emit()
            evento.accept()
            return
        super().mousePressEvent(evento)


class _ArgomentoPrincipale(QWidget):
    """L'argomento principale della home di jw.org, sotto il testo del giorno.

    IL PEZZO CHE IL SITO METTE IN CIMA ALLA HOME
    --------------------------------------------
    Nella home del sito c'e' un riquadro con l'argomento del giorno: la
    foto, il titolo in grassetto, due righe di introduzione e il tasto
    «Trova la risposta».  Il titolo e il tasto portano allo stesso
    articolo.

    QUI IL TASTO NON C'E'
    --------------------
    Il tasto del sito e' sparito, e con lui una riga: in un riquadro largo
    diceva quello che il titolo diceva gia', e lo diceva peggio.  Si entra
    dal **titolo** o dalla **foto**, che sono i due pezzi che si premono
    guardando un riquadro.

    E' UNA CARD DELLE NOTIZIE, MA LARGHISSIMA
    ------------------------------------------
    Le notizie dell'app sono card: la foto quadrata, il titolo in grassetto
    e sotto la riga grigia.  Qui la stessa cosa, ma **di traverso**: la foto
    a sinistra e il testo a destra, perche' l'argomento sta in cima alla
    Home e non in una striscia di card strette.

    Per questo la foto e' la stessa miniatura delle card (`miniatura`) e i
    colori vengono dal tema come sempre.  Il titolo e' pero' piu' grande di
    quello di una card: a dodici pixel, in un riquadro largo, sembrerebbe
    una riga di testo e non un titolo.

    LA FOTO C'E', E IL PEZZO DEL SITO ANCHE
    ---------------------------------------
    Il sito mette la foto grande e l'introduzione, e qui ci sono tutte e
    due.  La foto arriva dopo, in sottofondo, e il riquadro intanto mostra
    gia' il titolo: nessuno aspetta la rete per leggere il titolo.

    PERCHE' E' UN PEZZO DELL'APP E NON UNA PAGINA
    ----------------------------------------------
    Un articolo si apre dentro l'app, e l'articolo di questo riquadro e'
    un articolo come gli altri: entra nella pila delle schermate, si torna
    indietro con la freccia, e si chiude tornando a dove si era partito.
    Non e' un caso: e' lo stesso segnale e quindi la stessa strada che
    usano le notizie.

    FINCHE' L'ARGOMENTO NON ARRIVA, IL RIQUADRO NON SI VEDE
    -------------------------------------------------------
    La Home non deve aspettare la rete per apparire, e un riquadro vuoto
    con scritto «argomento principale» sopra niente sembrerebbe un
    difetto.  Quindi il riquadro nasce nascosto e compare quando il
    contenuto e' arrivato.
    """

    #: L'argomento e' stato premuto: (l'indirizzo dell'articolo)
    aperto = Signal(str)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self._url = ""
        self._costruisci()
        # Finche' non c'e' un argomento, il riquadro non si vede: vedi la
        # docstring.
        self.setVisible(False)

    def _costruisci(self) -> None:
        """Il riquadro, vuoto ma pronto a ricevere il testo."""
        # LA FOTO, A SINISTRA
        # -------------------
        # La stessa miniatura quadrata delle card delle notizie, con lo
        # stesso segnaposto: il glifo del documento dice «qui ci sara' una
        # foto», e non e' un'icona che indica il tipo.
        #
        # Si preme come il titolo: e' la foto dell'articolo, e l'articolo
        # e' quello che si vuole aprire.
        self._miniatura = _Cliccabile(self)
        self._miniatura.setObjectName("miniatura")
        self._miniatura.setFixedSize(LATO_ANTEPRIMA, LATO_ANTEPRIMA)
        self._miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._miniatura.setPixmap(
            icon("doc.text.fill", "#8a8a8a", 44).pixmap(44, 44))
        self._miniatura.premuto.connect(self._premuto)

        # IL TITOLO, COME IL TITOLO DI UNA CARD
        # --------------------------------------
        self._titolo = _Cliccabile(self)
        self._titolo.setObjectName("argomentoTitolo")
        self._titolo.premuto.connect(self._premuto)

        # LA DESCRIZIONE, COME LA RIGA SOTTO IL TITOLO DI UNA CARD
        # ---------------------------------------------------------
        # Nelle card e' la sezione e la data; qui e' l'introduzione del
        # sito.  Stessa riga, stesso posto, stesso stile.
        self._sotto = QLabel("", self)
        self._sotto.setObjectName("argomentoSotto")
        self._sotto.setWordWrap(True)

        # IL TITOLO DELLA SEZIONE
        # -----------------------
        # «Argomento principale», come «Notizie» e «Preferiti».  Sta
        # **dentro** il riquadro e non accanto: se stasse fuori, e la home
        # non rispondesse, resterebbe la scritta senza niente sotto, e
        # sembrerebbe un difetto.  Cosi' l'etichetta sparisce con il
        # riquadro, che e' quello che deve fare.
        self._etichetta = _TitoloSezione("Argomento principale", self)

        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(12)
        riga.addWidget(self._miniatura, 0, Qt.AlignmentFlag.AlignTop)

        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(4)
        colonna.addWidget(self._titolo)
        colonna.addWidget(self._sotto)

        riga.addLayout(colonna, 1)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.setSpacing(6)
        esterno.addWidget(self._etichetta)
        esterno.addLayout(riga)

    def mostra(self, voce: dict) -> None:
        """L'argomento e' arrivato: si mostra.

        Un dizionario vuoto non cancella quello che c'era: se la rete
        fallisce, il riquadro resta com'era.  Sarebbe strano perdere un
        pezzo buono per un errore di rete.
        """
        if not voce or not voce.get("url"):
            return
        self._url = voce["url"]
        self._titolo.setText(voce.get("titolo", ""))
        descrizione = voce.get("descrizione", "")
        self._sotto.setText(descrizione)
        self._sotto.setVisible(bool(descrizione))
        self.setVisible(True)
        self._scarica_la_foto(voce.get("immagine", ""))

    def _scarica_la_foto(self, indirizzo: str) -> None:
        """La foto dell'argomento, in sottofondo, come per le notizie.

        La foto arriva dopo e non blocca niente: il riquadro e' gia' a
        schermo con il titolo, e la foto ci finisce sopra quando arriva.
        """
        if not indirizzo:
            return
        from Utility.Extensions.Ext_DispatchQueue import background

        portata: dict = {"dati": None}

        def lavoro() -> None:
            from Utility import Copertine
            try:
                portata["dati"] = Copertine.scarica(indirizzo)
            except Exception:  # noqa: BLE001 - una foto mancante non e' un guasto
                portata["dati"] = None

        background(lavoro,
                   completion=lambda: self._foto_arrivata(portata["dati"]))

    def _foto_arrivata(self, dati) -> None:
        """La foto e' arrivata: va sulla miniatura."""
        from PyQt6 import sip
        from Utility import CaricaCopertine, Copertine

        if sip.isdeleted(self) or not dati:
            return
        try:
            immagine = CaricaCopertine.pixmap_pronta(dati)
            if immagine is None or immagine.isNull():
                return
            quadrata = Copertine.pixmap_quadrata(immagine, LATO_ANTEPRIMA)
            if quadrata is not None and not quadrata.isNull():
                self._miniatura.setPixmap(quadrata)
        except Exception:  # noqa: BLE001
            import traceback
            print("Home: errore nel mettere la foto dell'argomento ⚠️")
            traceback.print_exc()

    def _premuto(self) -> None:
        """Il titolo o la foto premuti: si apre l'articolo.

        Il tasto «Trova la risposta» del sito e' sparito: in un riquadro
        largo era una riga in piu' che diceva la stessa cosa del titolo, e
        la stessa cosa del titolo la diceva **meglio**: il titolo e' il
        pezzo che si preme, e si preme anche la foto.
        """
        if self._url:
            self.aperto.emit(self._url)

    @property
    def url(self) -> str:
        """L'indirizzo dell'articolo, o "" se non c'e' ancora."""
        return self._url

    @property
    def titolo(self) -> str:
        """Il titolo dell'argomento, o "" se non c'e' ancora."""
        return self._titolo.text()


def _larghezza_per_lo_schermo(padre, parte: float) -> int:
    """Quanto e' larga una parte di schermo, in pixel, per il widget `padre`.

    `parte` e' la frazione: 0,92 e' il 92% della larghezza dello schermo.

    PERCHE' SI CHIEDE A Qt E NON SI SCRIVE UN NUMERO
    ------------------------------------------------
    Un numero scritto qui — 1180, 1340 — va bene su uno schermo e male
    sull'altro: su 1366 esce di bordo, su un 4K resta un terzo.  E il punto
    del monitor secondario e' proprio che schermo non e' quello su cui il
    programma si trova: e' l'altro, e puo' essere fatto in modo diverso.

    La domanda «di che schermo e' questa finestra?» la sa gia' Qt, e la fa
    `screen()`.  Se non si puo' rispondere — la finestra non e' ancora stata
    creata — si usa lo schermo principale, che e' l'unico di cui il sistema ha
    detto con certezza dove parte tutto.

    Non si divide per i pixel per device: `availableGeometry()` e' gia' in
    pixel di Qt, quindi e' gia' quello che lo schervo usa, e su uno schermo
    con scalatura la finestra viene ridimensionata da Qt dopo.
    """
    schermo = None
    if padre is not None:
        try:
            schermo = padre.screen()
        except (AttributeError, RuntimeError):
            schermo = None
    if schermo is None:
        schermo = QApplication.primaryScreen()
    if schermo is None:
        return 1200
    try:
        return int(schermo.availableGeometry().width() * parte)
    except (AttributeError, RuntimeError, ValueError):
        return 1200


def scrittura_dell_anno(padre=None, lontano: bool = False) -> QWidget:
    """La «Scrittura dell'anno», centrata, e dove andarla a prendere.

    E' la riga che sta sulla pagina degli editori di «Esaminiamo le Scritture
    ogni giorno del <anno>», e solo la parte dopo i due punti:

        “Felici quelli che sono consapevoli del loro bisogno spirituale”
        (Matteo 5:3)

    La parola «Scrittura dell'anno» non si mostra: e' un'etichetta, e su uno
    schermo che si guarda da lontano un'etichetta e' solo rumore.  Il
    riferimento bibrico **si** mostra, perche' senza non si sa di che si
    parla.

    `lontano=True` e' per lo schermo secondario: stesso testo, corpo molto
    piu' grande.  E' la stessa voce, non un'altra — quindi le parole sono quelle
    e basta, e cambia solo la misura.  I nomi dei colori e le misure stanno
    nel foglio di stile (`tema.py`), come tutto il resto.

    SE LA PUBBLICAZIONE NON C'E'
    ---------------------------
    Nello schermo secondario si dice che non l'hai scaricata, e con il nome
    della pubblicazione, perche' l'utente ha cosi' la riga da cercare senza
    dover ricordare come si chiama.  Nella Home la frase e' piu' breve: li' il
    nome ce l'ha gia' davanti, e ripeterlo due volte nella stessa schermata e'
    rumore.

    IL RIQUADRO E' QUASI TUTTO LO SCHERMO, E IL CONTORNO NON SI VEDE
    -----------------------------------------------------------------
    Il riquadro prende il 92% della larghezza dello schermo: «tutto quello che
    c'e'», con un margine per lato che e' quello che fa leggere il riquadro come
    un riquadro e non come il bordo dello schermo.

    **Il contorno non si vede**, e non e' una dimenticanza: `tema.sfondo()` mette
    un bordo a tutti i riquadri, e qui il bordo e' dichiarato **uguale al
    fondo** perche' su uno schermo nero una cornice intorno al testo sembra una
    finestra dentro la finestra, e distrae proprio da quello che si sta
    leggendo.  Vedi la nota di `#scritturaAnnoLontano` in `tema.py`.

    PERCHE' IL TESTO PUO' ANDARE SU PIU' RIGHE
    ------------------------------------------
    Il riquadro e' largo ma il corpo e' grosso, e la frase piu' lunga che ho
    misurato sta su due righe su uno schermo 1920 e su piu' se lo schermo e'
    stretto.  Con `wordWrap` il testo va a capo da solo e il riquadro cresce: si
    vede tutto, e non si vede un pezzo tagliato — che sarebbe il caso peggiore,
    perche' una citazione troncata sembra sbagliata.
    """
    from Utility import JWPubManager

    testo = JWPubManager.scrittura_dell_anno()
    cartella = JWPubManager.esaminiamo_il_pacchetto()

    # Il riquadro e' una `QWidget` con tema, e non una `QLabel`: la `QLabel`
    # non avrebbe il fondo che `tema.sfondo` mette, e su uno schermo nero il
    # testo ci starebbe sopra un rettangolo grigio che si vede.
    scatola = tema.sfondo(QWidget(padre),
                          "scritturaAnnoLontano" if lontano else "scritturaAnno")
    # Sullo schermo secondario la larghezza segue lo schermo, e non e' un
    # numero scritto qui.
    #
    # Il corpo e' di 70 pixel e la frase sta su due righe solo se il riquadro
    # e' largo: a 1180 pixel fissi andava su tre, e su uno schermo stretto
    # sarebbe uscito di bordo.  In percentuale la cosa si risolve da sola: il
    # riquadro si stringe con lo schermo e la frase va a capo di piu', e
    # comunque non viene tagliata — che e' il caso peggiore, perche' una
    # citazione troncata sembra sbagliata.
    if lontano:
        scatola.setFixedWidth(_larghezza_per_lo_schermo(padre, 0.92))
    else:
        scatola.setFixedWidth(520)
    disposizione = QVBoxLayout(scatola)
    disposizione.setContentsMargins(36, 20, 36, 20)
    disposizione.setSpacing(0)

    if testo:
        corpo = QLabel(testo, scatola)
    else:
        # La pubblicazione non c'e'.  Si dice quale, e in che sezione si trova,
        # cosi' l'utente non deve cercare il nome: vedi il nome che chiediamo
        # al pacchetto e non quello che scriviamo qui.
        if cartella is None:
            corpo = QLabel(
                "Non hai scaricato Esaminiamo le Scritture ogni giorno."
                if lontano else
                "Non hai scaricato Esaminiamo le Scritture ogni giorno: "
                "scaricala per vedere la Scrittura dell'anno.", scatola)
        else:
            corpo = QLabel(
                "Nella Scrittura dell'anno di quest'anno non c'e' nessuna riga."
                if lontano else
                "La Scrittura dell'anno di quest'anno non si trova dentro la "
                "pubblicazione che hai scaricato.", scatola)
    corpo.setObjectName("scritturaAnnoLontano" if lontano else "scritturaAnno")
    corpo.setWordWrap(True)
    corpo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    disposizione.addWidget(corpo, 1)

    # il riquadro e' centrato in alto e in basso, non solo a sinistra e a
    # destra: su uno schermo vuoto una riga attaccata in alto sembra un avviso
    # e una riga in fondo sembra una didascalia.  I due `addStretch` in alto e
    # in basso sono quello che lo tiene nel mezzo, e non uno solo in mezzo:
    # quello da solo spingerebbe il riquadro in alto e basta.
    riga = QHBoxLayout()
    riga.addStretch(1)
    riga.addWidget(scatola)
    riga.addStretch(1)
    contenitore = QVBoxLayout()
    contenitore.setContentsMargins(0, 0, 0, 0)
    contenitore.addStretch(1)
    contenitore.addLayout(riga)
    contenitore.addStretch(1)
    sola = QWidget(padre)
    sola.setLayout(contenitore)
    return sola


class _TitoloSezione(QLabel):
    """Il titolo di una sezione della Home.

    IL PERCHE' USA `titoloPagina` E NON UNO STILE SUO
    --------------------------------------------------
    Prima qui c'era uno stile scritto a mano: 13 pixel, grassetto 600.  Il
    resto del programma — Impostazioni, Scaricati, Novita' e aggiornamenti —
    usa `titoloPagina`, che e' 20 pixel.  Il risultato si vedeva nella Home:
    «Preferiti» e «Notizie» piccole e «Novita' e aggiornamenti» grande, a
    due scale diverse nella stessa schermata, e nessuna delle due giuste.

    Il criterio e' che un titolo di sezione e' un titolo di sezione: se
    nella sezione dei download e' di 20 pixel, in Home e' di 20 pixel.  Il
    nome del file di stile lo dice da solo, quindi non qui dentro.
    """

    def __init__(self, testo: str, parent=None) -> None:
        super().__init__(testo, parent)
        self.setObjectName("titoloPagina")


#: Lato della miniatura di una riga di Novita'.
#:
#: 64 pixel.  Nella schermata dell'originale la miniatura di queste righe e'
#: un quadrato che sta accanto al titolo e non sopra: il titolo e' quello che
#: si legge, e la miniatura serve solo a riconoscerlo.  Quindi la riga e'
#: bassa, non quadrata.
LATO_NOVITA = 64

#: Lato della miniatura di una card con un video o un audio.
#:
#: 124 pixel, **lo stesso dei Preferiti e delle Notizie**, e non 112.
#:
#: Prima era 112 per farne stare cinque in fila, ma la striscia scorre in
#: orizzontale: il posto non si perde, si vede girando la rotella.  E il 112
#: lasciava 14 pixel vuoti per lato dentro una card larga 140, mentre sopra,
#: nella stessa schermata, Preferiti e Notizie avevano la miniatura a 124 con
#: 8 pixel per lato: tre sezioni con card diverse sulla stessa pagina, e le
#: miniatura del «Kit dell'insegnante» non si allineavano con quelle delle
#: sezioni di sopra.
#:
#: Ora e' la stessa misura e la stessa aria: le card del «Kit dell'insegnante»,
#: quelle delle «ultime novita'» e quelle dei Preferiti sono la stessa cosa a
#: poche righe di distanza.
LATO_ANTEPRIMA_MEDIA = 124


def _bottoni_dentro(miniatura, lato: int, su_menu, su_scarica) -> tuple:
    """I due bottoni **dentro** la miniatura di una card.

   Restituisce ``(tre_puntini, scarica)``, gia' posizionati.

    DOVE STANNO E PERCHE' NON SOPRA
    -------------------------------
    Prima stavano in una riga **sopra** la miniatura, a destra.  In una
    finestra con quattro strisce di fila sembravano quattro file di puntini
    sospesi sopra le card, e non si capiva a quale card appartenessero: il
    bottone di una card sembrava il titolo di quella accanto.

    Dentro la miniatura, ai due angoli, ognuno appartiene alla sua card: in
    alto a destra il menu, in basso a destra lo scaricare.

    PERCHE' DUE BOTTONI E NON UNO
    -----------------------------
    Dicono due cose diverse:

        «...»      questo pezzo ha un menu' (metti fra i Preferiti, elimina)
        nuvoletta  questo pezzo si puo' scaricare

    Con un solo bottone, uno dei due due significati non ci starebbe, e
    quello che si perde e' quello che non si vede subito.

    LA POSIZIONE E' A MANO
    ----------------------
    I due bottoni sono figli della miniatura ma **non** del suo layout: il
    layout della miniatura contiene solo la durata, e i due angoli sono posti
    con `setGeometry`.  E' l'unico modo per avere due bottoni in due angoli
    opposti di un quadrato.
    """
    tre_punti = QPushButton(icon("ellipsis.circle", "#ffffff", 16), "",
                            miniatura)
    tre_punti.setObjectName("bottoneCard")
    tre_punti.setFixedSize(20, 20)
    tre_punti.setToolTip("Altre azioni")
    tre_punti.setFlat(True)
    tre_punti.clicked.connect(su_menu)

    scarica = QPushButton(icon("cloud.download", "#ffffff", 16), "",
                          miniatura)
    scarica.setObjectName("bottoneCard")
    scarica.setFixedSize(20, 20)
    scarica.setToolTip("Scarica")
    scarica.setFlat(True)
    def _clic() -> None:
        # Mentre la card sta scaricando il tasto e' «Annulla scaricamento».
        if getattr(scarica, "_annulla_attivo", False):
            from Utility.FileDownloader import FileDownloader
            FileDownloader.annulla()
            scarica.setEnabled(False)
            return
        su_scarica()

    scarica.clicked.connect(_clic)
    miniatura._tasto_scarica = scarica

    # 4 pixel di bordo: i bottoni non toccano ne' il bordo ne' la durata, che
    # sta in alto a sinistra.
    tre_punti.setGeometry(lato - 24, 4, 20, 20)
    scarica.setGeometry(lato - 24, lato - 24, 20, 20)
    # Sopra la miniatura, che si disegna per ultima quando arriva l'immagine.
    tre_punti.raise_()
    scarica.raise_()
    return tre_punti, scarica


def _stato_nuvoletta(voce: dict, sigla: str, lingua: str) -> str:
        """Stato del pulsante nuvoletta per questa voce.

        Ritorna:
            "none"      gia' scaricato, nessuna novita'
            "download"  non scaricato -> mostra nuvoletta download
            "update"    scaricato ma versione nuova sul server -> mostra refresh
        """
        from Utility.Aggiornamenti import checksum_scaricato, leggi

        traccia = voce.get("traccia")
        formato = str(voce.get("formato") or "").upper()

        # VIDEO/AUDIO: per ora solo download (checksum per traccia non implementato)
        #
        # NON SOLO `formato`
        # ------------------
        # La regola era «una voce media ha **traccia e formato**» (nota in
        # `Preferiti.aggiungi`), ed e' giusta: una pubblicazione non ha la
        # traccia, un media sì.  Ma `formato` lo danno le voci che nascono
        # col file gia' scritto (`MediaScaricati`, `_voce_di_un_file`) o che
        # passano per `Preferiti`, e le voci del mediator non lo avevano:
        # cadevano nella ramo delle pubblicazioni — che cerca una cartella
        # `<sigla>_<lingua>_<anno>` che per `sjjm` non esiste — e la
        # nuvoletta restava accesa **anche con il file sul disco**.
        #
        # Ora `Mediator.voci` lo scrive.  `tipo` resta come secondo indizio
        # per le voci salvate sui dischi di chi ha passato la vecchia
        # `formato` vuoto: e' la chiave che il mediator mette e che una
        # pubblicazione non ha mai.  Serve ancora la traccia, per la stessa
        # ragione di prima — senza, un pacchetto JWPUB con dentro un file
        # che comincia colla sua sigla sembrerebbe scaricato.
        if traccia and (formato or voce.get("tipo")):
            # La domanda «il file c'e' gia'?» la fa `MediaScaricati.file_di`,
            # che e' il posto dove sta la regola del nome.  Qui prima c'era
            # un `glob` scritto di nuovo, identico ma non uguale:
            #
            #     radice.glob(f"{sigla}_{lingua}_{int(traccia):02d}_*")
            #
            # con l'underscore finale.  Sui video va bene, perche' il nome
            # continua con la risoluzione (`jwb-142_I_01_r720P.mp4`), ma
            # **sugli audio non c'e'**: un brano non ha risoluzioni, e il
            # file finisce sulla traccia (`iam-1_I_01.mp3`).  Con quel
            # `_*` la nuvoletta di ogni brano diceva «scarica» anche con il
            # file sul disco — e la sezione Scaricati non lo vedeva.
            #
            # Due copie della stessa regola divergono: e' successo.  Ora la
            # regola sta in un posto solo, che e' quello che ne conosce i
            # due nomi diversi.
            from Utility import MediaScaricati

            # TUTTI i numeri della traccia, e non il primo solo: un video di
            # «Adorazione mattutina» si chiama `jwb_I_202104_02_r240P.mp4` e
            # i suoi numeri sono due, mentre `traccia` contiene il primo
            # (202104).  `file_di` confronta i numeri **per intero**
            # (`_numeri(pezzi[1:]) != voci`), quindi col solo primo il
            # confronto non tornava mai e quella nuvoletta restava accesa
            # per sempre.  E' la stessa regola di `MediaView._media_sul_disco`
            # e di `Lettore._file_scaricato`: tre posti che davano tre
            # risposte diverse alla stessa domanda.
            try:
                scaricato = MediaScaricati.file_di(
                    sigla, lingua, voce.get("tracce") or int(traccia)
                ) is not None
            except Exception:  # noqa: BLE001 - un disco che non si legge non scaricato
                scaricato = False
            return "download" if not scaricato else "none"

        # PUBBLICAZIONE (JWPUB): controlla pacchetto e checksum
        cartella = HomeView._cartella_se_scaricata(
            sigla, lingua, voce.get("cartella"))
        if cartella is None:
            return "download"

        # Pacchetto scaricato: controlla se c'e' aggiornamento in cache
        mio = checksum_scaricato(sigla, lingua)
        if not mio:
            # Non abbiamo checksum locale -> non possiamo confrontare
            return "none"

        # Cerca in cache server (ultimo controllo)
        dati = leggi()
        server_voce = None
        for v in (dati.get("server") or []):
            if v.get("sigla") == sigla and not v.get("errore"):
                server_voce = v
                break

        if not server_voce:
            return "none"

        suo = (server_voce.get("pacchetto") or {}).get("checksum")
        if suo and str(mio).lower() != str(suo).lower():
            return "update"

        return "none"


def _nuvoletta_da_mostrare(voce: dict, sigla: str, lingua: str) -> bool:
        """Compatibilita': True = mostra nuvoletta download (vecchio comportamento)."""
        return _stato_nuvoletta(voce, sigla, lingua) == "download"


def _numero_traccia(traccia) -> int | None:
    """La traccia come numero, o None se la card non e' una traccia.

    La conversione vera sta in `CatalogoMedia.numero_traccia`, che e' la stessa
    che usano la barra laterale e il menu': questo e' solo il nome con cui la
    Home la chiama.
    """
    from Utility import CatalogoMedia

    return CatalogoMedia.numero_traccia(traccia)


def _barra_scaricamento(miniatura, lato: int):
    """La barra di scaricamento **dentro** la card, e i suoi tre metodi.

   Restituisce ``(barra, comincia, avanza, finito)``.

    PERCHE' DENTRO LA CARD E NON IN FONDO ALLA FINESTRA
    ---------------------------------------------------
    La riga in fondo dice che si sta scaricando qualcosa, ma non **cosa** ne
    dove: con quattro strisce di card in pagina, l'utente vede muovere una
    barra e non sa quale dei venti video sia quello.  La barra dentro la card
    e' sulla card giusta, e l'utente non deve cercare.

    La riga in fondo **resta**: ci sono scaricamenti che non hanno una card
    (i due cataloghi, i capitoli di un pacchetto), e senza quella riga
    non si saprebbe che il programma sta lavorando.

    DOVE STA, DENTRO LA MINiatura
    -----------------------------
    Lungo il bordo **in basso** della miniatura, sopra la figura.  In alto c'e'
    gia' la durata del video, e in basso a destra la nuvoletta: il bordo
    inferiore e' l'unico posto libero, ed e' quello dove un lettore mette la
    barra di avanzamento.

    E' una `QProgressBar` senza testo e senza bordo, alta 4 pixel: dentro una
    card larga 140 un riquadro con la percentuale scritta coprirebbe un terzo
    della miniatura.
    """
    from PyQt6.QtWidgets import QProgressBar

    barra = QProgressBar(miniatura)
    barra.setObjectName("scaricaBarra")
    barra.setTextVisible(False)
    barra.setRange(0, 0)          # 0,0 = non si sa ancora
    barra.setFixedHeight(4)
    barra.setGeometry(4, lato - 8, lato - 8, 4)
    barra.hide()

    # LA CARD PUO' NON ESSERCI PIU'
    # ----------------------------
    # Lo scaricamento gira in un altro thread e richiama queste tre funzioni
    # quando vuole.  Intanto la Home si puo' essere ricostruita (al primo
    # avvio succede appena arriva il catalogo) e la card con la sua barra
    # essere stata distrutta: toccare una barra distrutta manda Qt in
    # crash (SIGSEGV, senza messaggio).  Se non c'e' piu', non si fa niente.
    from PyQt6 import sip

    tasto = getattr(miniatura, "_tasto_scarica", None)

    def comincia(totale: int = 0) -> None:
        if sip.isdeleted(barra):
            return
        if tasto is not None and not sip.isdeleted(tasto):
            tasto._annulla_attivo = True
            tasto.setEnabled(True)
            tasto.setIcon(icon("xmark", "#ffffff", 16))
            tasto.setToolTip("Annulla scaricamento")
            tasto.show()
            tasto.raise_()
        if totale > 0:
            barra.setRange(0, totale)
        else:
            barra.setRange(0, 0)
        barra.setValue(0)
        barra.show()
        barra.raise_()

    def avanza(scritti: int, totale: int) -> None:
        if sip.isdeleted(barra) or not barra.isVisible():
            return
        if totale > 0 and barra.maximum() != totale:
            barra.setRange(0, totale)
        barra.setValue(scritti)
        barra.raise_()

    def finito() -> None:
        if tasto is not None and not sip.isdeleted(tasto):
            tasto._annulla_attivo = False
            tasto.setEnabled(True)
            tasto.setIcon(icon("cloud.download", "#ffffff", 16))
            tasto.setToolTip("Scarica")
        if not sip.isdeleted(barra):
            barra.hide()

    return barra, comincia, avanza, finito


class _CardMedia(QLabel):
    """La card di un video o di un pezzo di audio: miniatura, durata, titolo.

    E' la stessa forma delle card dei Preferiti, con una cosa in piu': la
    **durata** nell'angolo della miniatura.  Nella schermata dell'originale
    c'e' anche un triangolino prima dei minuti, e serve: distingue il video da
    quello che si ascolta senza guardare, e su una striscia di miniature
    tutte quadrate e' l'unico segnale.

    LA DURATA VIENE DAL CATALOGO, NON E' UN CALCOLO
    -------------------------------------------------
    `duration` e' un numero di secondi scritto dal server accanto al titolo.
    Non si riconverte: si arrotonda e si scrive, e il nome della pubblicazione
    resta accanto al numero come sta li'.

    IL CLIC PORTA LA TRACCIA, NON SOLO LA PUBBLICAZIONE
    ---------------------------------------------------
    Una voce del catalogo dei media e' «la traccia 126 di osg»: la traccia e'
    il dato che la card ha in mano, ed e' **la** cosa che la distingue dalle
    altre card della stessa pubblicazione.  Percio' il clic la porta con se'
    (sigla, lingua, traccia): la finestra, se quella traccia e' gia' sul
    disco, la suona subito — che e' quello che l'utente si aspetta premendo
    il video che ha scaricato.

    Se la traccia non e' scaricata si apre la scheda dei media come prima:
    li' il file lo si chiede al server aprendo la pubblicazione, e quella
    strada e' gia' fatta e collaudata dalla sezione Multimedia.  Il clic non
    cambia significato fra una card scaricata e una no: la prima suona il
    file che c'e', la seconda apre la lista da cui prenderlo.
    """

    #: La card e' stata premuta: (sigla, lingua, traccia).  La traccia e' None
    #: per una card che non ne ha una (non dovrebbe succedere: le voci del
    #: catalogo dei media sono tracce).
    aperta = Signal(str, str, object)
    #: I tre puntini sono stati premuti: (voce).
    #:
    #: La voce intera e non solo la sigla: il menu' condiviso deve sapere
    #: **quale traccia** aggiungere ai Preferiti, e la traccia e' il dato che
    #: distingue due card della stessa pubblicazione.  E' la stessa forma di
    #: `scaricaChiesto`, che gia' porta la voce per lo stesso motivo.
    menuChiesto = Signal(object)
    #: La nuvoletta e' stata premuta: (voce, dove premere)
    #:
    #: La voce e' il dizionario del catalogo, cosi' chi riceve non deve
    #: cercare niente e scarica esattamente quello che si vede nella card.  Il
    #: punto serve per aprire il menu' delle risoluzioni **dove** e' stato
    #: premuto il bottone, e non al centro dello schermo.
    scaricaChiesto = Signal(object, object)
    #: La nuvoletta "aggiorna" (refresh) e' stata premuta: (voce, dove premere).
    #: Stesso payload di scaricaChiesto, ma per aggiornamento invece di download.
    aggiornaChiesto = Signal(object, object)

    def __init__(self, voce: dict, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("card")
        self.voce = voce
        self._sigla = voce.get("sigla", "")
        self._lingua = voce.get("lingua", "I")

        contenitore = QWidget(self)
        disposizione = QVBoxLayout(contenitore)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)

        # I DUE BOTTONI STANNO DENTRO LA MINIATURA
        # Li mette `_bottoni_dentro`, che li posiziona: tre puntini in alto a
        # destra, nuvoletta in basso a destra.  Prima i tre puntini erano in
        # una riga sopra la card, e sembravano sospesi fra una card e l'altra.

        # LA MINIATURA CON LA DURATA
        # --------------------------
        # La durata sta in un riquadro sopra l'angolo in alto a sinistra
        # della miniatura: sopra e non dentro, perche' dentro coprirebbe la
        # figura, e la figura e' la cosa che fa riconoscere il video.
        self._miniatura = QLabel(contenitore)
        self._miniatura.setPixmap(icon("film", "#f2f2f2", LATO_ANTEPRIMA_MEDIA)
                                   .pixmap(LATO_ANTEPRIMA_MEDIA, LATO_ANTEPRIMA_MEDIA))
        self._miniatura.setFixedSize(LATO_ANTEPRIMA_MEDIA, LATO_ANTEPRIMA_MEDIA)
        self._miniatura.setObjectName("miniatura")

        # LA DURATA, DENTRO LA MINIATURA
        # ------------------------------
        # Dentro e non sopra: un riquadro che sta *sop* l'immagine e' una
        # finestra a parte, e una finestra a parte davanti a un'immagine
        # finisce o davanti a tutto il resto o dietro, secondo l'ordine in cui
        # Qt le ha costruite.  Qui invece la durata e' un figlio della
        # miniatura, e un figlio si disegna **sopra** il contenuto del padre:
        # quindi sta sull'angolo in alto a sinistra e la copertina si vede
        # tutta.  Provato: mettendola in un layout della scatola, la
        # miniatura la copriva e la durata non si vedeva.
        sopra = QHBoxLayout(self._miniatura)
        sopra.setContentsMargins(3, 3, 0, 0)
        sopra.setSpacing(0)
        durata = voce.get("durata") or ""
        if durata:
            self._durata = QLabel(f"▶ {durata}", self._miniatura)
            self._durata.setObjectName("durataMedia")
            sopra.addWidget(self._durata, 0, Qt.AlignmentFlag.AlignTop
                            | Qt.AlignmentFlag.AlignLeft)
        else:
            sopra.addStretch(1)
        sopra.addStretch(1)

        disposizione.addWidget(self._miniatura, 0,
                               Qt.AlignmentFlag.AlignHCenter)

        # I DUE BOTTONI DENTRO LA MINIATURA
        # ----------------------------------
        self.punti, self._scarica = _bottoni_dentro(
            self._miniatura, LATO_ANTEPRIMA_MEDIA,
            lambda: self.menuChiesto.emit(self.voce),
            self._premuto_scarica)

        # E LA BARRA DI SCARICAMENTO, ANCORA DENTRO LA MINIATURA
        self._barra, self._scarica_comincia, self._scarica_avanza, \
            self._scarica_finita = _barra_scaricamento(
                self._miniatura, LATO_ANTEPRIMA_MEDIA)

        # STATO NUVOLLETTA: download / update / none
        # -------------------------------------------
        # Per le pubblicazioni (JWPUB) gia' scaricate controlliamo se c'e'
        # una versione nuova sul server (via cache). Se si, mostriamo l'icona
        # refresh invece della nuvoletta download.
        self._stato_nuvoletta = _stato_nuvoletta(voce, self._sigla, self._lingua)
        if self._stato_nuvoletta == "update":
            self._scarica.setIcon(icon("arrow.clockwise", "#ffffff", 16))
            self._scarica.setToolTip("Aggiorna: scarica la versione nuova")
        elif self._stato_nuvoletta == "download":
            self._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
            self._scarica.setToolTip("Scarica")
        else:
            self._scarica.setVisible(False)

        self.titolo = QLabel(voce.get("titolo") or "", contenitore)
        self.titolo.setObjectName("titoloCard")
        self.titolo.setWordWrap(True)
        disposizione.addWidget(self.titolo)
        disposizione.addStretch(1)

        # LA LAYOUT DELLA CARD, O QUEL DENTRO NON HA LA MISURA GIUSTA
        # ------------------------------------------------------------
        # Senza questa il widget `contenitore` non viene ridimensionato alla
        # larghezza della card: resta largo quanto basta per non andare a
        # capo, e va fino a 280 pixel dentro una card larga 140.  Il titolo,
        # non andando a capo, esce dalla card e si stende **sopra la card
        # accanto**: due card sovrapposte in orizzontale, e solo con i titoli
        # lunghi — quindi sembrava che qualcuna fosse messa storta e non che
        # mancasse un pezzo.
        #
        # Con la layout il widget dentro prende i 140 pixel della card, il
        # titolo va a capo come deve e ogni card resta al suo posto.  E' la
        # stessa riga che c'e' in `_Card`, che non ha il difetto.
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(contenitore)

        self.setFixedWidth(LARGHEZZA_CARD)
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._sigla
                       else Qt.CursorShape.ArrowCursor)

    def _premuto_scarica(self) -> None:
        """La nuvoletta e' stata premuta: esce la richiesta.

        Il punto e' quello del bottone premuto, non quello della card: il
        menu' delle risoluzioni deve aprirsi sotto il dito, e sotto la card
        finisce sopra la card successiva.
        """
        punto = self._scarica.mapToGlobal(
            QPoint(10, self._scarica.height()))
        if self._stato_nuvoletta == "update":
            self.aggiornaChiesto.emit(self.voce, punto)
        else:
            self.scaricaChiesto.emit(self.voce, punto)

    def metti_immagine(self, immagine) -> None:
        """Mette la miniatura del catalogo, quando arriva.

        I due bottoni vengono risollevati: l'immagine arriva dopo che i
        bottoni sono stati messi, e senza questo il pixmap li coprirebbe.
        """
        if immagine is None:
            return
        from Utility import Copertine

        quadrata = Copertine.pixmap_quadrata(
            immagine, LATO_ANTEPRIMA_MEDIA)
        if quadrata is None or quadrata.isNull():
            return
        self._miniatura.setPixmap(quadrata)
        self.punti.raise_()
        self._scarica.raise_()

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and self._sigla:
            self.aperta.emit(self._sigla, self._lingua,
                             self.voce.get("traccia"))
        super().mousePressEvent(evento)


class _SezioneMedia(QWidget):
    """Una striscia di video o di audio: titolo, lingua, e le card in fila.

    E' la forma che ha nella schermata dell'originale la sezione dei video da
    usare per insegnare e quella delle ultime novita': il titolo grande a
    sinistra, la lingua a destra sulla stessa riga, e sotto le card in fila
    orizzontale con la durata sulla miniatura.

    LE MINIATURE ARRIVANO DOPO, DA UN THREAD
    ----------------------------------------
    Il catalogo dei media scrive dentro ogni voce l'indirizzo della
    miniatura, ma l'indirizzo è un indirizzo: per vedere l'immagine bisogna
    andarlo a prendere.  Quindi la card si costruisce col glifo del film, che
    è sempre lì, e l'immagine la sostituisce quando arriva.  Il confine è
    quello di sempre: i byte li prende il thread, il `QPixmap` lo fa il main.
    """

    def __init__(self, titolo: str, voci: list, padre=None) -> None:
        super().__init__(padre)

        scatola = QVBoxLayout(self)
        scatola.setContentsMargins(0, 0, 0, 0)
        scatola.setSpacing(4)

        riga_titolo = QHBoxLayout()
        riga_titolo.setContentsMargins(0, 0, 0, 0)
        riga_titolo.setSpacing(8)
        riga_titolo.addWidget(_TitoloSezione(titolo, self))
        lingua = QLabel("", self)
        lingua.setObjectName("linguaSezione")
        # Il nome della lingua che si sta guardando, non il suo codice: e' la
        # stessa riga e la stessa forma delle altre sezioni, e «I» in un
        # angolo non dice niente a nessuno.
        from Utility import Lingua

        voce_lingua = Lingua.corrente_voce()
        if voce_lingua:
            lingua.setText(Lingua.titolo(voce_lingua))
        riga_titolo.addStretch(1)
        riga_titolo.addWidget(lingua, 0, Qt.AlignmentFlag.AlignBottom)
        scatola.addLayout(riga_titolo)

        # LA STRISCIA
        # -----------
        # Orizzontale e scorrevole, come i Preferiti e come nell'originale.  Il
        # widget dentro si allarga a riempire ma non si restringe sotto la
        # somma delle card: e' quello che fa comparire la rotella solo quando
        # le card non ci stanno.
        self.contenitore = QScrollArea(self)
        self.contenitore.setWidgetResizable(True)
        self.contenitore.setFrameShape(QFrame.Shape.NoFrame)
        self.contenitore.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.contenitore.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # La rotella gira questa striscia in orizzontale invece di alzare la
        # pagina: e' una striscia, e su una striscia la rotella gira per
        # scalare.  Vedi `Ext_ScrollRuota`.
        from Utility.Extensions.Ext_ScrollRuota import ruota_orizzontale

        ruota_orizzontale(self.contenitore)

        self._pagina = QWidget()
        self._colonna = QHBoxLayout(self._pagina)
        self._colonna.setContentsMargins(0, 0, 0, 0)
        # 3 pixel, come la striscia dei Preferiti e quella delle Notizie: le
        # tre sezioni hanno card della stessa larghezza e la stessa aria, e se
        # una sola avesse il vuoto diverso si vedrebbe che le card non sono
        # la stessa cosa.  La larghezza resta quella che e': fissa, cosi' la
        # posizione delle card non cambia da una card all'altra e la striscia
        # non viene storta.
        self._colonna.setSpacing(3)
        self.contenitore.setWidget(self._pagina)
        # L'ALTEZZA: 124 + 68 + 6 = 198
        # ---------------------------------
        #   124  la miniatura quadrata, `LATO_ANTEPRIMA_MEDIA`
        #   68   il titolo su quattro righe (17 pixel l'una)
        #    6   il respiro sotto l'ultima riga
        #
        # I due bottoni stanno dentro la miniatura, quindi non c'e' piu' la
        # riga dei tre puntini: l'altezza scende di 22 rispetto a prima.
        #
        # Le quattro righe servono davvero: il titolo piu' lungo che si e' visto
        # sulle 16 card delle «ultime novita'» e' «Troy Snyder. Nelle tragedie,
        # Geova ascolta il nostro grido d'aiuto (Sal. 18:6)», che va su quattro
        # righe a 140 pixel.  Con l'altezza di prima (il conto su 112 e tre
        # righe, 204 pixel) quella riga restava tagliata a meta', e un titolo
        # tagliato sembra un difetto della finestra e non della misura.
        self.contenitore.setFixedHeight(LATO_ANTEPRIMA_MEDIA + 68 + 6)
        scatola.addWidget(self.contenitore)

        self._cards: dict = {}
        for voce in voci:
            card = _CardMedia(voce, self._pagina)
            self._colonna.addWidget(card)
            self._cards[(voce.get("sigla", ""), voce.get("chiave", ""))] = card
        # Lo spazio avanza resta a destra: due card in una finestra larga
        # devono stare a sinistra e non spargersi per tutta la pagina.
        self._colonna.addStretch(1)

        if not voci:
            # Il catalogo dei media non c'e' o non ha nulla in questa
            # lista.  Si dice, con le parole giuste: non e' un errore e non
            # e' un guasto, e' che il catalogo non e' ancora stato preso.
            vuoto = QLabel(
                "Non c'è ancora l'elenco. Si prende con il tasto di "
                "aggiornamento in alto.", self._pagina)
            vuoto.setObjectName("nota")
            self._colonna.addWidget(vuoto)

        self._immagini(voci)

    def _immagini(self, voci: list) -> None:
        """Le immagini delle card, in un thread.

        DUE POSTI DA PRENDERE L'IMMAGINE
        #--------------------------------
        Il video ha l'indirizzo della miniatura **scritto dentro la voce** del
        catalogo dei media, e si scarica da li'.

        La pubblicazione non ce l'ha: il catalogo dei media contiene solo
        VIDEO e AUDIO, quindi di una pubblicazione in quella sezione non c'e'
        nessun indirizzo.  La copertina si chiede al server come per i
        Preferiti, dalla sigla, e `Copertine` guarda prima sul disco: se la
        pubblicazione e' gia' scaricata non chiede niente a nessuno.

        Il thread porta via i byte e il main thread fa il `QPixmap`.
        """
        con_indirizzo = [v for v in voci if v.get("miniatura")]
        solo_pubblicazioni = [v for v in voci
                              if not v.get("miniatura") and v.get("sigla")]
        if not con_indirizzo and not solo_pubblicazioni:
            return

        from Utility.Extensions.Ext_DispatchQueue import background

        risultati: list = []

        def lavoro() -> None:
            from Utility import Copertine
            from Utility.Structures.Generals import Publication
            from Utility import Lingua

            for voce in con_indirizzo:
                risultati.append((voce, Copertine.scarica(voce["miniatura"])))
            for voce in solo_pubblicazioni:
                pub = Publication(
                    ID=0, keySymbol=voce["sigla"], year=0,
                    mepsLanguageId=Lingua.da_simbolo(voce.get("lingua", "I")),
                    publicationTypeId=0, issueTagNumber=0,
                    title=voce["sigla"])
                risultati.append((voce, Copertine.dati_copertina(pub, "md")))

        def arrivati() -> None:
            from PyQt6 import sip
            from Utility.Copertine import pixmap_da_dati

            for voce, dati in risultati:
                card = self._cards.get((voce.get("sigla", ""),
                                        voce.get("chiave", "")))
                if card is None or sip.isdeleted(card) or not dati:
                    continue
                card.metti_immagine(pixmap_da_dati(dati))

        background(lavoro, completion=arrivati)


class _Card(QLabel):
    """Una card quadrata: la miniatura sopra, il titolo sotto.

    E' una QLabel e non un pulsante perche' le card della Home sono un
    elenco di collegamenti: se non c'e' niente da aprire non c'e' nemmeno
    bisogno che sembrino premibili.  Un bottone che non fa niente e' peggio
    di un'etichetta che non sembra un bottone.

    IL SEGNALE E' A LIVELLO DI CLASSE
    ---------------------------------
    ``clic = Signal()`` dentro ``__init__`` non funziona in PyQt6: il
    descrittore viene costruito quando la classe viene creata, e un
    segnale per ogni istanza non viene registrato.  Il sintomo arriva al
    ``connect``, con ``'pyqtSignal' object has no attribute 'connect'``.
    """

    aperta = Signal(str, str)   # sigla, lingua
    #: I tre puntini sono stati premuti: (sigla, lingua)
    #:
    #: Il menu' NON si costruisce qui.  Il menu' e' lo stesso delle righe
    #: della sezione Scaricati, e costruirlo qui sarebbe una seconda copia:
    #: le voci le si aggiornerebbero in un posto solo, e la Home mostrerebbe
    #: un menu' con una voce in piu' o in meno' rispetto a quello delle righe.
    #: Chi ascolta chiama il menu' di `DownloadsView`.
    menuChiesto = Signal(str, str)
    #: La nuvoletta e' stata premuta: (voce, dove premere)
    #:
    #: Come in `_CardMedia`: la voce e' un dizionario fatto qui, e non un
    #: oggetto `Publication`, perche' chi riceve non deve cercare niente e
    #: scarica esattamente la pubblicazione che si vede nella card.
    scaricaChiesto = Signal(object, object)
    #: La nuvoletta "aggiorna" (refresh) e' stata premuta: (voce, dove premere).
    aggiornaChiesto = Signal(object, object)

    def __init__(self, titolo: str, sottotitolo: str = "", simbolo: str = "",
                 etichetta: str = "", sigla: str = "", lingua: str = "I",
                 voce: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._sigla, self._lingua = sigla, lingua
        self._titolo = titolo
        # LA VOCE DELLA CARD, NON SOLO SIGLA E LINGUA
        # -------------------------------------------
        # Una card dei Preferiti puo' essere **una traccia** di una
        # pubblicazione di media, e allora la nuvoletta e il menu' devono
        # sapere quale traccia: con la sola sigla la nuvoletta restava accesa
        # su un video gia' scaricato («nei Preferiti non vede che era
        # scaricato») e il menu' toglieva la pubblicazione invece della
        # traccia.  Chi ha la voce la passa; chi non ce l'ha ricade su sigla e
        # lingua, che e' quello che basta per una pubblicazione intera.
        self.voce = dict(voce) if voce else {"sigla": sigla, "lingua": lingua}
        contenitore = QWidget(self)
        disposizione = QVBoxLayout(contenitore)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)

        # la miniatura: quadrata per costruzione, con il glifo al centro
        miniatura = QLabel(contenitore)
        miniatura.setObjectName("miniatura")
        miniatura.setFixedSize(LATO_ANTEPRIMA, LATO_ANTEPRIMA)
        miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # La miniatura si tiene: `metti_copertina` la riempie piu' tardi, quando
        # i byte dell'immagine arrivano dal thread che li ha scaricati.
        self._miniatura = miniatura
        if simbolo:
            miniatura.setPixmap(icon(simbolo, "#ffffff", 44).pixmap(44, 44))
        if etichetta:
            # L'etichetta sta in basso a sinistra dentro la miniatura, come
            # nella app precedente: e' il nome della pubblicazione.
            targhetta = QLabel(etichetta, miniatura)
            targhetta.setObjectName("targhetta")
            targhetta.setAlignment(Qt.AlignmentFlag.AlignLeft)
            targhetta.adjustSize()
        disposizione.addWidget(miniatura)

        # I DUE BOTTONI DENTRO LA MINiatura: tre puntini in alto a destra,
        # nuvoletta in basso a destra.  Prima i tre puntini erano in una riga
        # sopra la card e sembravano sospesi fra una card e l'altra; vedi
        # `_bottoni_dentro`.
        self.punti, self._scarica = _bottoni_dentro(
            miniatura, LATO_ANTEPRIMA, self._menu, self._premuto_scarica)

        # E LA BARRA DI SCARICAMENTO, SU QUESTA CARD
        self._barra, self._scarica_comincia, self._scarica_avanza, \
            self._scarica_finita = _barra_scaricamento(
                miniatura, LATO_ANTEPRIMA)

        # STATO NUVOLLETTA: download / update / none
        self._stato_nuvoletta = _stato_nuvoletta(self.voce, sigla, lingua)
        if self._stato_nuvoletta == "update":
            self._scarica.setIcon(icon("arrow.clockwise", "#ffffff", 16))
            self._scarica.setToolTip("Aggiorna: scarica la versione nuova")
        elif self._stato_nuvoletta == "download":
            self._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
            self._scarica.setToolTip("Scarica")
        else:
            self._scarica.setVisible(False)

        nome = QLabel(titolo, contenitore)
        nome.setObjectName("titoloCard")
        nome.setWordWrap(True)
        disposizione.addWidget(nome)

        if sottotitolo:
            sotto = QLabel(sottotitolo, contenitore)
            sotto.setObjectName("sottoCard")
            sotto.setWordWrap(True)
            disposizione.addWidget(sotto)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(contenitore)

        # La larghezza e' fissa perche' in orizzontale le card si sommano: se
        # la prende dal titolo, una card con un titolo su due righe e' larga
        # piu' di una con il titolo su una, e la striscia viene storta.
        self.setFixedWidth(LARGHEZZA_CARD)

        # IL CLIC
        # -------
        # La card e' una QLabel e non un pulsante (vedi sopra), quindi il
        # clic si intercetta a mano.  Senza, una QLabel non cliccabile
        # sembra una miniatura e basta, e non c'e' modo di aprirla.
        self.setCursor(Qt.CursorShape.PointingHandCursor if sigla
                       else Qt.CursorShape.ArrowCursor)

    def metti_copertina(self, immagine) -> None:
        """Mette la copertina al posto del glifo, quando arriva.

        La copertina arriva dopo: si scarica in un thread, perche' chiedere
        un'immagine al server dal main thread blocca la finestra.  Quindi la
        card si costruisce col glifo del libro, che e' sempre li', e l'immagine
        la sostituisce quando c'e'.

        IL PERCHE' DEL QUADRATO
        ----------------------
        La casella e' 150x150 e le copertine sono a perte: `ypq` e' 599x771.
        Un `QPixmap` piu' grande della `QLabel` non viene ridotto, viene
        **tagliato**: la copertina si vede zoomata tre volte e sembra
        un'immagine sbagliata.

        `setScaledContents(True)` non va bene perche' riduce davvero, ma
        schiaccia: 599x771 in un quadrato diventa larga e bassa.  Qui si passa
        da `Copertine.pixmap_quadrata`, che riduce tenendo le proporzioni e
        ritaglia il centro, e il risultato arriva gia' della misura giusta.

        Il glifo non resta sotto: con `setPixmap` il primo setter vince, e il
        glifo continuerebbe a occupare memoria senza piu' servire.
        """
        if immagine is None:
            return
        from Utility import Copertine

        quadrata = Copertine.pixmap_quadrata(
            immagine, min(self._miniatura.width(), self._miniatura.height()))
        if quadrata is None or quadrata.isNull():
            return
        self._miniatura.setPixmap(quadrata)
        # La copertina arriva dopo i bottoni: senza questo il pixmap li
        # coprirebbe, e i due bottoni diventerebbero visibili solo finche' la
        # copertina non arriva.
        self.punti.raise_()
        self._scarica.raise_()

    def _premuto_scarica(self) -> None:
        """La nuvoletta e' stata premuta: esce la richiesta.

        Una card dei Preferiti di una pubblicazione non ha risoluzioni da
        scegliere: chi riceve scarica il JWPUB e basta.  Una card di una
        **traccia** invece le risoluzioni le ha, ed e' la stessa richiesta di
        una card dei media: la voce che esce porta sigla, lingua e traccia, e
        chi riceve sa gia' cosa fare.  Il punto serve per aprire il menu' dove
        e' stato premuto.
        """
        voce = dict(self.voce)
        voce.setdefault("sigla", self._sigla)
        voce.setdefault("lingua", self._lingua)
        voce.setdefault("titolo", self._titolo)
        voce.setdefault("formato", "")
        voce.setdefault("traccia", "")
        voce.setdefault("durata", "")
        voce.setdefault("numero", "")
        punto = self._scarica.mapToGlobal(QPoint(10, self._scarica.height()))
        if self._stato_nuvoletta == "update":
            self.aggiornaChiesto.emit(voce, punto)
        else:
            self.scaricaChiesto.emit(voce, punto)

    def _menu(self) -> None:
        """I tre puntini: avvisano che il menu' e' stato premuto."""
        if self._sigla:
            self.menuChiesto.emit(self._sigla, self._lingua)

    def mousePressEvent(self, evento) -> None:
        # Solo il tasto sinistro apre.  Il destro e' quello che toglie il
        # Preferito, e mescolare i due significa che l'utente che vuole
        # togliere un Preferito finisce con quello aperto.
        if evento.button() == Qt.MouseButton.LeftButton and self._sigla:
            self.aperta.emit(self._sigla, self._lingua)
        super().mousePressEvent(evento)


class _CardNotizia(QLabel):
    """La card di una notizia: la foto sopra, il titolo e la data sotto.

    PERCHE' NON SI RIUSA `_Card` DEI PREFERITI
    -------------------------------------------
    `_Card` parla in `(sigla, lingua)` e ha un menu' a tre puntini che serve
    a mettere o togliere un Preferito: nessuna delle due cose ha senso per
    una notizia, che non e' una pubblicazione e non si puo' mettere fra i
    Preferiti.  Per riusarla si dovrebbe aggiungere un modo "questa e' una
    notizia" con dentro tutti i campi vuoti, e una card con quattro campi
    che valgono "" e' piu' difficile da leggere di una card che sa che cosa
    e'.

    Quello che invece e' lo stesso, e viene preso, e' la misura: la stessa
    larghezza, lo stesso lato dell'anteprima quadrata e lo stesso
    `Copertine.pixmap_quadrata`, cosi' le due strisce hanno la stessa aria e
    non si vede che sono due sezioni.

    LA FOTO NON E' SEMPRE LA STESSA FORMA
    -------------------------------------
    Le foto delle notizie non sono quadrate: quella del regalo per i sordi e'
    un ritratto, quella di Ramapo e' una foto con del testo sopra.  Il
    ritaglio al centro e' quello che c'e' gia' in `pixmap_quadrata` e serve
    anche qui: senza, la `QLabel` taglia fuori e l'immagine si vede
    ingrandita tre volte, che e' il difetto descritto in `_Card`.
    """

    aperta = Signal(str)

    def __init__(self, titolo: str, sotto: str = "", url: str = "",
                 immagine: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._url = url
        self._immagine = immagine
        self.setFixedWidth(LARGHEZZA_CARD)
        # Il cursore a mano solo se c'e' qualcosa da aprire, come in `_Card`.
        self.setCursor(Qt.CursorShape.PointingHandCursor if url
                       else Qt.CursorShape.ArrowCursor)

        contenitore = QWidget(self)
        disposizione = QVBoxLayout(contenitore)
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)

        miniatura = QLabel(contenitore)
        miniatura.setObjectName("miniatura")
        miniatura.setFixedSize(LATO_ANTEPRIMA, LATO_ANTEPRIMA)
        miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # La foto arriva dopo, dal thread che la scarica: la card si
        # costruisce subito e l'immagine la mette quando c'e'.  Il glifo del
        # giornale e' un segnaposto, non un'icona che indica il tipo: e'
        # "qui ci sara' una foto", e il peccato sarebbe inventare un'immagine
        # per una notizia che non ce l'ha.
        # `doc.text.fill` e non "newspaper": il nome va nella tabella dei
        # simboli del progetto originale (`Utility.Stuff.SF_SYMBOLS`), e
        # "newspaper" non c'era.  Un nome che non c'e' nella tabella non da'
        # nessun errore — `icon()` restituisce un'QIcon vuota — quindi la
        # card mostrava un rettangolo scuro senza niente dentro, e sembrava
        # un'immagine rotta invece di un simbolo che non esiste.
        miniatura.setPixmap(icon("doc.text.fill", "#8a8a8a", 44).pixmap(44, 44))
        self._miniatura = miniatura
        disposizione.addWidget(miniatura)

        nome = QLabel(titolo, contenitore)
        nome.setObjectName("titoloCard")
        nome.setWordWrap(True)
        disposizione.addWidget(nome)

        if sotto:
            # La sezione e la data: "NEWS · 30 settembre 2026".  Una riga e
            # non due, perche' sotto la striscia c'e' la sezione Novita' e
            # l'altezza e' fissa.
            sotto_etichetta = QLabel(sotto, contenitore)
            sotto_etichetta.setObjectName("sottoCard")
            sotto_etichetta.setWordWrap(True)
            disposizione.addWidget(sotto_etichetta)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(contenitore)

    def metti_immagine(self, immagine) -> None:
        """Mette la foto al posto del glifo, quando arriva dal thread."""
        if immagine is None:
            return
        from Utility import Copertine

        quadrata = Copertine.pixmap_quadrata(
            immagine, min(self._miniatura.width(), self._miniatura.height()))
        if quadrata is None or quadrata.isNull():
            return
        self._miniatura.setPixmap(quadrata)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and self._url:
            self.aperta.emit(self._url)
        super().mousePressEvent(evento)


class _NotizieInHome(QWidget):
    """La striscia delle notizie vere, sopra Novita'.

    LE NOTIZIE VENGONO PRIMA DI NOVITA'
    ---------------------------------
    Non perche' siano piu' importanti, ma perche' rispondono a due domande
    diverse e in ordine diverso.  "Cosa c'e' di nuovo **da scaricare**" e'
    la domanda di chi ha il disco quasi pieno e deve scegliere; "cosa c'e'
    di nuovo **da leggere**" e' la domanda di chi apre il programma.  Le due
    sezioni insieme nella stessa riga si confonderebbero, e Novita' finirebbe
    sotto una striscia di articoli che non c'entrano.

    LA PAGINA SI LEGGE UNA VOLTA sola
    ---------------------------------
    Il programma non tiene le notizie da parte: le rilegge dalla pagina di
    jw.org quando vengono chieste.  Sono 19 articoli e una pagina sola, e
    rileggerli tiene due cose vere insieme — quello che c'era ieri e quello
    che c'e' adesso — senza dover inventare una cache che si invalida da
    sola.  Il prezzo e' che senza rete la striscia resta vuota, e in quel
    caso lo **dice**, invece di riempirsi di notizie vecchie senza avvisare.
    """

    #: Una card e' stata premuta: (indirizzo della pagina)
    #:
    #: La card ce l'ha gia', ma non si collega a `HomeView` direttamente: le
    #: carte vengono buttate via e rifatte a ogni caricamento, e un collegamento
    #: che punta alla cardvecchia lascerebbe una sezione che ascolta qualcosa
    #: che non esiste piu'.  Il segnale e' della sezione, che vive quanto
    #: lei, e le carte ci parlano solo passando da qui.
    aperta = Signal(str)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self._card: dict = {}
        # stessi nomi della `_NotizieInHome` che c'era in `UpdatesView`: i
        # titoli vivono qui dentro, non nella Home.  Vedi `_titolo_notizia`.
        self._titoli_notizie: dict = {}

        scatola = QVBoxLayout(self)
        scatola.setContentsMargins(0, 0, 0, 0)
        scatola.setSpacing(8)

        self.titolo = _TitoloSezione("Notizie", self)
        scatola.addWidget(self.titolo)

        self._vuoto = QLabel("", self)
        self._vuoto.setObjectName("vuoto")
        self._vuoto.setWordWrap(True)
        scatola.addWidget(self._vuoto)

        # LA ROTELLA GIRA LA STRISCIA, NON LA PAGINA
        # ------------------------------------------------
        # Questa sezione e' una striscia in orizzontale: senza questo, il mouse
        # sopra le card e la rotella alzava la pagina e la striscia restava
        # ferma.  Vedi `Ext_ScrollRuota`.
        from Utility.Extensions.Ext_ScrollRuota import ruota_orizzontale

        self.area = QScrollArea(self)
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setFixedHeight(ALTEZZA_STRISCIA_NOTIZIE)
        ruota_orizzontale(self.area)

        self.pagina = QWidget(self)
        self._fila = QHBoxLayout(self.pagina)
        # 3 pixel, come le due strisce sopra: il vuoto fra le card e' la
        # distanza che rende leggibile una striscia, non un'altra misura.
        self._fila.setContentsMargins(0, 0, 0, 0)
        self._fila.setSpacing(3)
        self.area.setWidget(self.pagina)
        scatola.addWidget(self.area)

    def _svuota(self) -> None:
        """Butta via le card precedenti, senza cancellare la `self` stessa."""
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        while self._fila.count():
            elemento = self._fila.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()
        self._card.clear()
        # Anche i titoli si svuotano: se restassero, un articolo che non e'
        # piu' in elenco aprirebbe con il titolo di quello che c'era prima, e
        # la fascia direbbe una cosa e la pagina un'altra.  Sono la stessa
        # lista, quindi si svuotano insieme.
        self._titoli_notizie.clear()

    def titolo_di(self, indirizzo: str) -> str:
        """Il titolo della notizia con quell'indirizzo, o "".

        Lo chiede `SidebarView._aperta_notizia` per il titolo da mettere
        nella fascia e per quello della schermata.

        Si prende il titolo che la card aveva gia', e non si rilegge la
        pagina: rileggerla vuol dire una seconda richiesta per una parola
        che si ha gia' in mano, e i due titoli possono non essere uguali —
        la pagina nel frattempo e' cambiata — e allora non si saprebbe quale
        dei due sia giusto.
        """
        return self._titoli_notizie.get(indirizzo, "")

    def mostra(self, voci: list) -> None:
        """Mette le notizie, o dice perche' non ce ne sono."""
        self._svuota()
        if not voci:
            self.titolo.setVisible(False)
            self.area.setVisible(False)
            self._vuoto.setVisible(True)
            self._vuoto.setText(
                "Le notizie non sono arrivate: controlla la connessione.")
            return

        self.titolo.setVisible(True)
        self.area.setVisible(True)
        self._vuoto.setVisible(False)

        for voce in voci:
            sotto = " · ".join(pezzo for pezzo in
                                (voce.get("sezione", ""),
                                 Notizie.data_in_italiano(voce.get("data", "")))
                                if pezzo)
            card = _CardNotizia(voce.get("titolo", ""), sotto,
                                voce.get("url", ""), voce.get("immagine", ""),
                                self.pagina)
            card.aperta.connect(self.aperta.emit)
            self._fila.addWidget(card)
            self._card[voce.get("url", "")] = card
            self._titoli_notizie[voce.get("url", "")] = voce.get("titolo", "")
        self._fila.addStretch(1)
        self._scarica_immagini(voci)

    def _scarica_immagini(self, voci: list) -> None:
        """Le foto, in un thread, e solo quelle che ci sono.

        `Copertine.scarica` tiene i file in una cartella di cache, quindi la
        seconda volta che la Home si apre le foto sono gia' sul disco e non
        si richiede niente al server.

        Non si scaricano tutte: una striscia lunga 19 card con 19 foto mette
        la connessione occupata mentre l'utente guarda la prima.  Si prendono
        le prime dodici, che sono le dodici che entrano in una finestra senza
        dover girare la rotella, e si prendono solo quelle che hanno un
        indirizzo: cinque delle 19 non hanno la foto e per quelle non c'e'
        niente da chiedere.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        prime = [v for v in voci if v.get("immagine")][:12]
        if not prime:
            return

        risultato: list = []

        def lavoro() -> None:
            from Utility import Copertine
            for voce in prime:
                try:
                    dati = Copertine.scarica(voce["immagine"])
                except Exception:  # noqa: BLE001 - una foto mancante non
                    dati = None    # deve far cadere la striscia intera
                if dati:
                    risultato.append((voce.get("url", ""), dati))

        background(lavoro, completion=lambda: self._immagini_arrivate(risultato))

    def _immagini_arrivate(self, trovate: list) -> None:
        """Le foto sono arrivate: vanno sulla card giusta."""
        from PyQt6 import sip
        from Utility import CaricaCopertine

        if sip.isdeleted(self):
            return
        try:
            for url, dati in trovate:
                card = self._card.get(url)
                if card is None:
                    continue
                immagine = CaricaCopertine.pixmap_pronta(dati)
                if immagine is not None and not immagine.isNull():
                    card.metti_immagine(immagine)
        except Exception:  # noqa: BLE001
            import traceback
            print("Home: errore nel mettere le foto delle notizie ⚠️")
            traceback.print_exc()


class HomeView(QWidget):
    """La schermata iniziale."""

    messaggio = Signal(str)
    navigate = Signal(object)
    goBack = Signal()
    #: La sezione e' stata costruita, la Home si aggiorni da sola
    aggiornamento_chiesto = Signal()
    #: I Preferiti sono stati messi o tolti dal menu' dei tre puntini
    preferiti_messi = Signal()
    #: Rilanciati da `UpdatesView`, che sta dentro questa sezione.  La
    #: finestra li ascolta qui e non sa che dentro la Home c'e' una sezione.
    cambiato = Signal()
    scaricaRichiesta = Signal(object)
    #: Aggiorna una pubblicazione già scaricata (stesso payload di scaricaRichiesta).
    aggiorna = Signal(object)
    #: «Annulla scaricamento» premuto nel riquadro del giorno
    annullaRichiesta = Signal()
    #: Il riquadro del giorno e' stato premuto: (la pagina di oggi)
    #:
    #: Va alla finestra, e non a `aperta`: `aperta` e' la promessa che si apre
    #: una **pubblicazione** — una Preferito, una riga degli Scaricati — e li'
    #: chi ascolta cerca una sigla nel catalogo e apre il pacchetto.  Qui
    #: invece si apre un capitolo preciso, e quella strada finirebbe
    #: all'elenco dei mesi.
    giornoAperto = Signal(object)
    #: Una card dei Preferiti e' stata premuta: (sigla, lingua)
    #:
    #: NON ERA COLLEGATO A NESSUNA PARTE
    #: -----------------------------------
    #: La card emetteva `aperta`, questa sezione lo rimetteva qui dentro, e
    #: di qui non usciva: nessuno ascoltava `HomeView.aperta`.  Il risultato
    #: era che premere un Preferito non faceva assolutamente niente — la
    #: card aveva il cursore a mano, si premeva, e la finestra restava li'.
    #:
    #: Il sintomo peggiore di questo difetto e' che sembra funzionante: la
    #: card c'ha il cursore a mano, e il collegamento c'era fino a due passi
    #: (card -> sezione), quindi a occhio sembrava tutto a posto.  Il terzo
    #: passo mancante non si vede da nessuna parte, e la prova e' premere.
    aperta = Signal(str, str)
    #: Una card di un **media** (le due strisce dei video) e' stata premuta:
    #: (sigla, lingua, traccia).  E' diversa da `aperta`, e non per caso.
    #:
    #: `aperta` promette che si apre una **pubblicazione**: chi la ascolta
    #: cerca la sigla e apre il pacchetto, o la scheda dei media.  Una card
    #: della striscia invece e' una **traccia** precisa, e la traccia e' il
    #: dato che la distingue dalle altre card della stessa pubblicazione:
    #: buttarla via per mandare solo la sigla vorrebbe dire che premere la
    #: traccia 2 scaricata apre la lista delle tracce, e non suona niente.
    #:
    #: Per questo il segnale e' un altro e porta la traccia: chi lo riceve
    #: controlla se quella traccia e' gia' sul disco e, se c'e', la suona.
    #: Se non c'e', apre la scheda dei media esattamente come `aperta`.
    mediaAperta = Signal(str, str, object)
    #: Una card delle notizie e' stata premuta: (indirizzo della pagina)
    #:
    #: Esce da qui perche' dentro la Home la card non puo' aprire niente
    #: da sola: non ha la pila delle schermate e non sa cosa fare di una
    #: pagina.  La finestra la riceve e ci mette dentro il motore che c'e'
    #: gia' - vedi `SubViews/NotiziaView.py`.
    notiziaAperta = Signal(str)
    #: La nuvoletta di una card e' stata premuta: (voce, dove premere)
    #:
    #: **IL SEGNALE ESCE DA QUI E NON SI SCARICA QUI**
    #: ------------------------------------------------------
    #: La Home non sa scaricare: non ha la pila delle schermate, non conosce
    #: la sezione Pubblicazioni e non ha la barra di stato.  Scaricare da
    #: qui sarebbe una terza strada per prendere un pacchetto, e le tre
    #: strade direbbero tre cose diverse quando una di loro sbaglia.
    #:
    #: Per un **video** la voce porta anche la traccia e il formato: chi
    #: riceve chiede al server le risoluzioni di quella traccia e apre il
    #: menu' dove e' stato premuto il bottone.  Per una **pubblicazione** non
    #: c'e' niente da scegliere e si scarica il JWPUB, come per i Preferiti.
    scaricoChiesto = Signal(object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Gli accoppiamenti (sigla, lingua, card) dei Preferiti.  Li tiene
        # `_preferiti()` e li usa `_copertine_dei_preferiti` per sapere a
        # quale card mettere quale copertina.
        #
        # Comincia come lista vuota e non come attributo che si crea quando
        # serve: senza questa riga, un richiamo di `_copertine_dei_preferiti`
        # prima del primo `_preferiti()` — cioe' se qualcuno la chiama da solo —
        # finisce con un attributo che non esiste, dentro un metodo che gira in
        # un thread.
        self._preferiti_accoppiati: list = []
        # Le card per (sigla, lingua): il menu' dei tre puntini deve sapere
        # quale card ha premuto l'utente, e dalla sigla sola non basta perche'
        # la stessa sigla in due lingue sono due card.
        self._card_per_sigla: dict = {}
        self._riepilogo = QLabel("", self)
        self._riepilogo.setObjectName("nota")
        self._riepilogo.setWordWrap(True)
        # L'ULTIMA VOLTA CHE L'ARGOMENTO E' STATO CHIESTO, in secondi
        # dalla mezzanotte.  Serve a non chiedere la home a ogni apertura
        # del programma: l'argomento cambia una volta alla settimana, e
        # rileggerlo ogni volta non trova niente di nuovo.
        self._argomento_chiesto = 0.0

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)

        pagina = QWidget()
        disposizione = QVBoxLayout(pagina)
        disposizione.setContentsMargins(18, 16, 18, 16)
        disposizione.setSpacing(0)
        disposizione.setAlignment(Qt.AlignmentFlag.AlignTop)

        disposizione.addWidget(self._testo_del_giorno())
        disposizione.addSpacing(18)

        # L'ARGOMENTO PRINCIPALE DELLA HOME
        # ---------------------------------
        # Il pezzo che il sito mette in cima alla sua home: il titolo
        # dell'argomento del giorno, due righe di introduzione e il tasto
        # «Trova la risposta».  Sta **sotto il testo del giorno**, perche'
        # e' la stessa domanda di chi apre il programma la mattina: di che
        # cosa parla oggi il sito.
        #
        # Il titolo e il tasto aprono l'articolo **dentro l'app**, come
        # fanno le notizie: e' lo stesso segnale, e quindi la stessa strada.
        self._argomento = _ArgomentoPrincipale()
        self._argomento.aperto.connect(self.notiziaAperta.emit)
        disposizione.addWidget(self._argomento)
        disposizione.addSpacing(18)

        # OGNI TANTO L'ARGOMENTO SI RILEGGE
        # ---------------------------------
        # Il sito cambia l'argomento principale una volta alla settimana, e
        # non ogni ora: rileggerlo spesso non serve a niente e mette la
        # rete in fila per niente.  Il timer passa ogni mezzora, e il
        # controllo dentro `_cerca_argomento` fa si' che non si chieda la
        # home piu' di una volta ogni quindici minuti.
        self._timer_argomento = QTimer(self)
        self._timer_argomento.setInterval(RICONTROLLO_ARGOMENTO)
        self._timer_argomento.timeout.connect(self._cerca_argomento)
        self._timer_argomento.start()

        # IL RIEPILOGO DELLE NOVITA'
        #
        # Va subito sotto la data, prima dei Preferiti.  Se ci sono
        # novita' e sono nascoste sotto due sezioni, l'utente non le vede
        # e il controllo all'avvio sembra non aver fatto niente.
        #
        # Se non c'e' niente la riga sparisce: una riga che dice "tutto
        # aggiornato" ogni volta che si apre l'app e' rumore, e dopo una
        # settimana non la si legge piu' nemmeno quando c'e' qualcosa.
        self._contenitore_riepilogo = QWidget(pagina)
        riga_riepilogo = QHBoxLayout(self._contenitore_riepilogo)
        riga_riepilogo.setContentsMargins(0, 0, 0, 0)
        riga_riepilogo.addWidget(self._riepilogo)
        disposizione.addWidget(self._contenitore_riepilogo)
        self.aggiorna_riepilogo()

        disposizione.addWidget(_TitoloSezione("Preferiti"))
        # Prima None, poi la griglia vera: `_preferiti()` la crea e la
        # restituisce, e dentro ci cerca `self._striscia_preferiti` per
        # riusarla.  Senza questa riga l'attributo non esiste ancora e il
        # primo richiamo va in errore.
        self._striscia_preferiti = None

        # LA STRISCIA DEI PREFERITI, IN ORIZZONTALE E SCORRIBILE
        # ------------------------------------------------------
        # Era una griglia a colonne, con il numero di colonne calcolato dalla
        # larghezza della finestra.  In una finestra larga la griglia metteva
        # cinque card e mezza pagina vuota: la larghezza che avanza andava
        # sprecata, e con quattro Preferiti la Home sembrava vuota perche'
        # quattro quadrati in fondo a sinistra non si vedono.
        #
        # In orizzontale la larghezza che avanza la usano le card, e quando i
        # Preferiti sono molti Compare la rotella.  Il widget dentro si
        # allarga fino a riempire (`setWidgetResizable(True)`) ma non si
        # restringe sotto la somma delle card: e' quello che fa comparire la
        # rotella solo quando serve, e non sempre.
        #
        # La rotella verticale e' spenta: in orizzontale non serve, e due
        # rotelle su un riquadro di 230 pixel non ci stanno.
        self._striscia_area = QScrollArea(self)
        self._striscia_area.setWidgetResizable(True)
        self._striscia_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._striscia_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._striscia_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._striscia_area.setFixedHeight(ALTEZZA_STRISCIA)
        # Anche questa e' una striscia: la rotella la gira in orizzontale
        # invece di alzare la pagina.  Vedi `Ext_ScrollRuota`.
        from Utility.Extensions.Ext_ScrollRuota import ruota_orizzontale

        ruota_orizzontale(self._striscia_area)

        pagina_striscia = QWidget()
        self._striscia_preferiti = self._preferiti()
        pagina_striscia.setLayout(self._striscia_preferiti)
        self._striscia_area.setWidget(pagina_striscia)
        disposizione.addWidget(self._striscia_area)
        # Le copertine partono DOPO che la griglia e' nel layout: se partissero
        # prima, le card sarebbero costruite ma non ancora collegate a nulla, e
        # un'immagine arrivata in quel momento andrebbe su una card che non e'
        # ancora quella che l'utente sta guardando.
        self._copertine_dei_preferiti()
        disposizione.addSpacing(18)

        # LE NOTIZIE SONO L'ULTIMA SEZIONE, IN FONDO
        # -------------------------------------------
        # Lo hai deciso tu, e il motivo e' l'ordine delle domande: prima si
        # guarda **cosa si usa** — il giorno, i Preferiti, i pezzi da
        # insegnare, le ultime novita' — e le notizie sono l'ultima cosa, non
        # la prima.
        #
        # Prima erano qui, sopra le strisce dei media, e finivano sotto una
        # striscia lunga di card: si leggevano per caso, scorrendo, e non per
        #che le si cercassero.  In fondo stanno dove le si cerca davvero.
        #
        #   notizie      "cosa c'e' di nuovo **da leggere**"  - si svuota
        #                leggendo, e non occupa disco
        #   novita'      "cosa c'e' di nuovo **da scaricare**" - occupa disco,
        #                e la scelta va fatta una volta sola
        #
        # Sono costruite vuote e si riempiono dopo: la Home non deve aspettare
        # la rete per apparire, e una finestra che non si apre perche' una
        # pagina esterna non risponde e' peggio di una finestra con la
        # striscia che si riempisce un secondo dopo.

        # «USCITE DI RECENTE» NON STA PIU' NELLA HOME
        # ---------------------------------------------
        # Era il riquadro circondato di rosso: il titolo, le cinque righe con
        # la copertina e sotto la riga «19 voci in tutto: 14 si vedono
        # scorrendo l'elenco».  Un riquadro che scorre in verticale dentro una
        # pagina che gia' scorre, e che ripeteva quello che diceva gia'
        # «Le ultime novita'» piu' sotto.
        #
        # Le voci sono ancora disponibili: sono il gruppo 2 di `CuratedAsset`,
        # cioe' la stessa lista dell'app originale sotto «What's New», e si
        # vedono dalla sezione «Le ultime novita'» e dai Preferiti.  Quello
        # che non sta piu' e' il riquadro con la rotella dentro.
        disposizione.addSpacing(18)


        # LE DUE STRISCE DI VIDEO E AUDIO
        # -------------------------------
        # Nella schermata dell'originale, sotto i Preferiti, ci sono due
        # sezioni: il «Kit dell'insegnante» e «Le ultime novita'».
        #
        # IL «KIT DELL'INSEGNANTE» HA DENTRO ANCHE LE PUBBLICAZIONI
        # ------------------------------------------------------
        # Nell'originale quella sezione non ha solo i video: accanto ai video
        # da usare per insegnare ci sono le pubblicazioni, cioe' gli opuscoli
        # e i trattati che si usano per lo stesso scopo.
        #
        # Il catalogo dei media — dove stanno i video — non le contiene: li ha
        # solo VIDEO e AUDIO, 4.910 voci e nessuna pubblicazione.  Le
        # pubblicazioni curate stanno nell'altro catalogo, nella tabella
        # `CuratedAsset`.
        #
        # In sezione vanno le tre che sono pezzi da insegnare (misurate il
        # 9 ottobre 2026):
        #
        #     sjj    Cantiamo a Geova con gioia
        #     lmd    Ama le persone. Fai discepoli
        #     th     Applicati alla lettura e all'insegnamento
        #
        # **NON** `S-38` «Istruzioni per l'adunanza», che era nella lista 0:
        # e' un'istruzione per chi organizza l'adunanza, non un pezzo da
        # insegnare, e in una sezione che si chiama «Kit dell'insegnante» non
        # c'entra.  Per questo si prende la lista 0 e si toglie quella voce,
        # invece di scrivere le tre sigle a mano: la lista e' quella decisa da
        # chi ha fatto il catalogo, e se domani dentro ci sara' un pezzo da
        # insegnare entra anche lui senza toccare niente.
        #
        # E poi il corso e il libro di «Puoi vivere felice per sempre?», che
        # sono i due pezzi che si usano insieme:
        #
        #     lff    Puoi vivere felice per sempre. Corso biblico interattivo
        #     lffi   Puoi vivere felice per sempre. Lezioni bibliche introduttive
        #
        # Il primo e' quello che si indica come «Puoi vivere felice per
        # sempre?», il secondo e' il libro che gli va dietro.  Le due sigle
        # sono scritte qui perche' sono scelte, non una lista del catalogo; il
        # **titolo** no: viene letto dal catalogo, cosi' se il server lo
        # cambia cambia anche qui.
        #
        # L'ordine e' quello deciso qui: prima i quattro video, poi le tre
        # pubblicazioni della lista 0, poi il corso e il libro.  Non si
        # mescola perche' non si sa quale dei due sia piu' recente, e una
        # lista di pezzi per insegnare con un ordine chiaro vale piu' di una
        # lista riordinata per data.
        #
        # Se il catalogo non c'e' la sezione mostra i soli quattro video, e va
        # bene cosi': non si scrive niente a mano.
        from Utility import Aggiornamenti, CatalogoMedia, Lingua

        lingua_corrente = Lingua.corrente_simbolo()
        voci_kit = list(CatalogoMedia.kit_insegnante(lingua_corrente))
        # Le pubblicazioni entrano con la stessa forma delle voci dei media,
        # cosi' `_CardMedia` le disegna senza sapere da dove vengono.  La
        # `miniatura` vuota e' quello che le distingue: la copertina non si
        # prende dal catalogo dei media perche' non c'e', quindi si chiede al
        # server come per i Preferiti.  Vedi `_immagini`.
        def pubblicazione(sigla: str, titolo: str) -> dict:
            return {"chiave": "", "titolo": titolo, "sigla": sigla,
                    "lingua": lingua_corrente, "docid": "", "traccia": "",
                    "formato": "", "numero": "", "durata": "",
                    "pubblicato": "", "miniatura": ""}

        # La lista 0 meno S-38, nell'ordine del catalogo.
        for voce in Aggiornamenti.novita_recenti(lingua_corrente,
                                                 Aggiornamenti.LISTA_IN_EVIDENZA):
            if voce.get("sigla", "").upper() == "S-38":
                continue
            voci_kit.append(pubblicazione(voce.get("sigla", ""),
                                          voce.get("titolo", "")))

        # Il corso e il libro di «Puoi vivere felice per sempre?».
        for sigla, titolo in Aggiornamenti.titoli_delle(["lff", "lffi"],
                                                         lingua_corrente).items():
            voci_kit.append(pubblicazione(sigla, titolo))

        self._kit_insegnante = _SezioneMedia(
            "Kit dell'insegnante", voci_kit, self)
        disposizione.addWidget(self._kit_insegnante)
        disposizione.addSpacing(18)

        self._ultime = _SezioneMedia(
            "Le ultime novità",
            CatalogoMedia.ultime(lingua_corrente), self)
        disposizione.addWidget(self._ultime)
        disposizione.addSpacing(18)

        # LE NOTIZIE, ULTIMA SEZIONE
        # ---------------------------
        # Dopo le due strisce dei media, e non prima: vedi la nota piu' su,
        # «LE NOTIZIE SONO L'ULTIMA SEZIONE, IN FONDO».
        self._notizie = _NotizieInHome(self)
        disposizione.addWidget(self._notizie)
        disposizione.addStretch(1)

        # Le card dei video portano la loro traccia (vedi `_CardMedia`): se la
        # traccia e' gia' sul disco la finestra la suona, altrimenti apre la
        # pubblicazione.  Il menu' dei tre puntini e' quello condiviso: le
        # stesse regole dei Preferiti, perche' il significato di una card non
        # dipenda da dove sta.
        for sezione in (self._kit_insegnante, self._ultime):
            for card in sezione.findChildren(_CardMedia):
                card.aperta.connect(
                    lambda s, l, t: self.mediaAperta.emit(s, l, t))
                card.menuChiesto.connect(self._menu_novita)
                card.scaricaChiesto.connect(self.scaricoChiesto.emit)
                card.aggiornaChiesto.connect(self.aggiorna.emit)

        # La card di una notizia esce come indirizzo, e la finestra ci mette
        # dentro il motore.  Qui dentro non si sa cosa sia una pagina, e una
        # segnale che portasse gia' la schermata costruita costringerebbe
        # questa sezione a dipendere dal motore: il verso della dipendenza che
        # si evita e' esattamente quello che ha fatto crescere `ArticleView`.
        self._notizie.aperta.connect(self.notiziaAperta)

        area.setWidget(pagina)
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(area)

        # Dopo che tutto e' costruito, e non prima: `_notizie_cercate` parte da
        # un thread e chiama `_mostra_notizie`, che tocca `self._notizie`.  Se
        # partisse durante `__init__` il widget non ci sarebbe ancora e il
        # risultato sarebbe una striscia che non si riempie e nessun avviso.
        self._notizie_cercate = False

    def card_di(self, voce: dict):
        """La card che mostra quella voce, o None.

        Serve alla finestra per mettere la barra di scaricamento **sulla card
        giusta**: il video scaricato e' uno fra i venti che si vedono
        scorrendo, e senza questo la barra andrebbe su quella sbagliata o su
        nessuna.

        La ricerca e' per `(sigla, chiave)` e non per indice: le card si
        ricostruiscono (un Preferito nuovo, la lingua cambiata) e un indice
        salvato un attimo prima punta gia' a un'altra card.

        Si cerca in tutte le sezioni che hanno card — Kit dell'insegnante, Le
        ultime novita' e i Preferiti — perche' la stessa pubblicazione puo'
        comparire in due sezioni (per esempio «Cantiamo a Geova con gioia» e'
        nel Kit e puo' essere un Preferito).  Va bene la prima: la barra dice
        «sto scaricando questo» e su entrambe le card dice la verita'.
        """
        if not isinstance(voce, dict):
            return None
        sigla = voce.get("sigla", "")
        chiave = voce.get("chiave", "")

        for sezione in (getattr(self, "_kit_insegnante", None),
                        getattr(self, "_ultime", None)):
            if sezione is None:
                continue
            card = sezione._cards.get((sigla, chiave))
            if card is not None:
                return card

        # I Preferiti hanno una card per (sigla, lingua, traccia) e non hanno
        # la `chiave`: sono pubblicazioni o tracce, e le distingue la lingua e
        # — per una traccia — il numero.  La traccia vuota e' `None`, come
        # nella costruzione, altrimenti la ricerca non troverebbe la card di
        # una pubblicazione intera.
        return getattr(self, "_card_per_sigla", {}).get(
            (sigla, voce.get("lingua", "I"),
             _numero_traccia(voce.get("traccia"))))

    def aggiorna_scaricature(self) -> None:
        """Rilegge tutte le card e mostra la nuvoletta/refresh solo dove serve.

        Si chiama quando qualcosa arriva sul disco o quando l'utente elimina
        qualcosa dalla sezione Scaricati: in entrambi i casi la risposta alla
        domanda «questa cosa la devo ancora scaricare/aggiornare?» e' cambiata,
        e senza questa rilettura la nuvoletta resterebbe quella di prima.

        Non si ricostruiscono le card: si cambia solo l'icona/visibilita' di un
        bottone.  Ricostruirle rifarebbe le copertine e riporterebbe le card
        nella posizione di prima, mentre l'utente sta guardando quella pagina.
        """
        for sezione in (getattr(self, "_kit_insegnante", None),
                        getattr(self, "_ultime", None)):
            if sezione is None:
                continue
            for card in sezione.findChildren(_CardMedia):
                stato = _stato_nuvoletta(card.voce, card._sigla, card._lingua)
                if stato == "update":
                    card._scarica.setIcon(icon("arrow.clockwise", "#ffffff", 16))
                    card._scarica.setToolTip("Aggiorna: scarica la versione nuova")
                    card._scarica.setVisible(True)
                elif stato == "download":
                    card._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
                    card._scarica.setToolTip("Scarica")
                    card._scarica.setVisible(True)
                else:
                    card._scarica.setVisible(False)
                card._stato_nuvoletta = stato

        for (sigla, lingua, _traccia), card in getattr(
                self, "_card_per_sigla", {}).items():
            # Le card qui sono _Card (non _CardMedia): usano la stessa logica
            # di stato per l'icona refresh/download.
            stato = _stato_nuvoletta(card.voce, sigla, lingua)
            if stato == "update":
                card._scarica.setIcon(icon("arrow.clockwise", "#ffffff", 16))
                card._scarica.setToolTip("Aggiorna: scarica la versione nuova")
                card._scarica.setVisible(True)
            elif stato == "download":
                card._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
                card._scarica.setToolTip("Scarica")
                card._scarica.setVisible(True)
            else:
                card._scarica.setVisible(False)
            card._stato_nuvoletta = stato

    # ------------------------------------------------------------------
    # LE NOTIZIE
    # ------------------------------------------------------------------

    def showEvent(self, evento) -> None:
        """La Home appare: si chiedono le notizie, se non sono gia' venute.

        PERCHE' QUI E NON NEL COSTRUTTORE
        ---------------------------------
        Nel costruttore la Home si costruisce tutte le sezioni, anche quelle
        che l'utente non apra' mai: e se chiedessero li', l'avvio del
        programma aspetterebbe una pagina di jw.org per una sezione che
        magari non vieneGuardata neanche una volta.

        `showEvent` arriva quando la sezione diventa visibile, quindi la
        richiesta parte quando l'utente la guarda.  E il controllo dentro
        `cerca_notizie` fa il resto: la seconda volta che si apre la Home le
        notizie sono gia' state prese e non si chiede niente.

        Il `super()` va chiamato per primo: senza, l'evento non viene
        inoltrato e la sezione resta con il disegno a meta'.
        """
        super().showEvent(evento)
        self.cerca_notizie()
        self._cerca_argomento()

    def _titolo_notizia(self, indirizzo: str) -> str:
        """Il titolo della notizia con quell'indirizzo.

        Lo chiede `SidebarView._aperta_notizia` per il titolo da mettere
        nella fascia e per quello della schermata.

        Si prende il titolo che la card aveva gia', e non si rilegge la
        pagina: rileggerla significa una seconda richiesta per una parola
        che si ha gia' in mano, e i due titoli possono non essere uguali —
        la pagina nel frattempo e' cambiata — e allora non si saprebbe quale
        dei due sia quello giusto.

        Se l'indirizzo non e' fra quelli mostrati si restituisce "" e chi
        chiama ricade sul pezzo finale dell'indirizzo, che e' comunque il
        titolo del sito e non una parola inventata qui.
        """
        # L'argomento principale ha il suo titolo, che non sta nella
        # striscia delle notizie: senza questo, la fascia direbbe l'ultimo
        # pezzo dell'indirizzo ("proteste-la-soluzione") invece di
        # «La soluzione e' la protesta?».
        argomento = getattr(self, "_argomento", None)
        if argomento is not None and argomento.url == indirizzo:
            return argomento.titolo
        return self._notizie.titolo_di(indirizzo)

    def cerca_notizie(self) -> None:
        """Chiede le notizie al server, una volta sola per questa Home.

        IL PERCHE' DEL SEGNALE DI "GIA' CHIESTO"
        ----------------------------------------
        Senza questo, ogni volta che la Home appare — cioe' a ogni avvio e
        ogni volta che l'utente torna su questa sezione — si rifarebbe la
        stessa richiesta e si aprirebbe un thread.  Il segnale e' una cosa
        sola e vive quanto questa sezione: le notizie del giorno sono le
        stesse per un giorno intero, e rileggerle non trova niente di nuovo
        e fa solo traffico.

        E IL PULSANTE "Aggiorna"?
        -------------------------
        Non c'e' niente da fare qui, e il motivo sta in come funziona quel
        pulsante: `SidebarView._aggiorna_schermata` **ricostruisce** la
        sezione da capo invece di ricaricarla.  La Home che si riapre e'
        un'altra, con il suo segnale a False, quindi le notizie vengono
        rilette davvero — senza che qui ci sia un caso "forzato" che nessuno
        chiama e che quindi nessuno saprebbe se funziona.

        PERCHE' LA CHIAMATA PARTE BENE, ANCHE SE IL RISULTATO ARRIVA TARDI
        -----------------------------------------------------------------
        `background` parte quando gira l'evento, e un widget non ha eventi
        finche' la finestra non parte: da qui il `QTimer.singleShot`.  Senza,
        la richiesta aspetterebbe un evento che arriva solo quando l'utente
        preme qualcosa, e la striscia resterebbe vuota fino ad allora — o
        per sempre, se l'utente non preme niente.
        """
        from PyQt6.QtCore import QTimer

        if getattr(self, "_notizie_cercate", False):
            return
        self._notizie_cercate = True
        QTimer.singleShot(0, self._cerca_notizie_ora)

    def _cerca_notizie_ora(self) -> None:
        """La richiesta vera, e in un thread."""
        from Utility.Extensions.Ext_DispatchQueue import background

        risultato: list = []
        fallito: list = []

        def lavoro() -> None:
            try:
                risultato.extend(Notizie.aggiorna())
            except Exception as errore:  # noqa: BLE001
                # La sezione deve dire che non ha potuto, non restare muta:
                # una striscia vuota senza parole sembra che non ci siano
                # notizie, che e' una cosa diversa dal non essere arrivate.
                fallito.append(str(errore))

        background(lavoro,
                   completion=lambda: self._notizie_arrivate(risultato, fallito))

    def _cerca_argomento(self) -> None:
        """L'argomento principale della home: si chiede al server.

        NON A OGNI APERTURA
        -------------------
        L'argomento cambia una volta alla settimana.  Rileggerlo a ogni
        apertura del programma significa una richiesta della home a ogni
        avvio, per trovare sempre la stessa cosa: e quando il programma
        resta aperto giorni, sono richieste inutili.

        Per questo c'e' un minimo: se l'ultima richiesta e' stata meno di
        un quarto d'ora fa, non si chiede niente.  Il timer passa ogni
        mezzora e quando la Home compare, e uno dei due trova il momento
        giusto.

        IL RITMO DEL PROGRAMMA
        ----------------------
        Come per le notizie, la richiesta parte in un thread: la Home non
        deve aspettare la rete per comparire, e un programma che si blocca
        mentre scarica una pagina e' un programma che sembra rotto.
        """
        adesso = time.time()
        if adesso - self._argomento_chiesto < MINIMO_ARGOMENTO:
            return
        self._argomento_chiesto = adesso

        from Utility.Extensions.Ext_DispatchQueue import background

        portata: dict = {"voce": {}}

        def lavoro() -> None:
            try:
                portata["voce"] = Argomento.aggiorna()
            except Exception:  # noqa: BLE001
                # Una home che non arriva non e' un guasto: il riquadro
                # semplicemente non cambia, e quello che c'era resta
                # vero.  Non si mostra un avviso perche' l'argomento e'
                # un di piu', e un avviso ogni volta che la rete e' debole
                # diventa un rumore che l'utente impara a ignorare.
                portata["voce"] = {}

        background(lavoro,
                   completion=lambda: self._argomento_arrivato(portata["voce"]))

    def _argomento_arrivato(self, voce: dict) -> None:
        """L'argomento e' arrivato (o non e' arrivato): si mette nel riquadro."""
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        try:
            self._argomento.mostra(voce)
        except Exception:  # noqa: BLE001
            import traceback
            print("Home: errore nel mostrare l'argomento principale ⚠️")
            traceback.print_exc()

    def _notizie_arrivate(self, voci: list, fallito: list) -> None:
        """Le notizie sono arrivate, o non sono arrivate.

        Il controllo `sip.isdeleted` non e' paranoia: il risultato arriva in
        background e nel frattempo la finestra puo' essere stata distrutta.
        Toccarla allora da `RuntimeError: wrapped C/C++ object of type HomeView
        has been deleted`, e dentro un callback di Qt quello finisce in
        `abort()` senza lasciare nessuna riga di traceback.
        """
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        try:
            if fallito:
                # Non si svuota la striscia: quello che c'era gia' e' vero e
                # si lascia stare.  Non si finge che sia la notizia di oggi.
                self.messaggio.emit(
                    "Le notizie non sono arrivate: controlla la connessione.")
                if not voci:
                    self._notizie.mostra([])
                return
            self._notizie.mostra(voci)
        except Exception:  # noqa: BLE001
            import traceback
            print("Home: errore nel mostrare le notizie")
            traceback.print_exc()

    # ------------------------------------------------------------------

    def _testo_del_giorno(self) -> QWidget:
        """La data di oggi e il versetto del giorno, o il tasto per scaricarlo.

        Una funzione, non una classe, perche' non serve nient'altro: la Home
        costruisce il riquadro una volta e lo tiene.

        Il riquadro e' pero' una classe perche' lui deve poter emettere
        `scaricaRichiesta` — il tasto che c'e' dentro non potrebbe emettere un
        segnale della Home — e riedersi quando un pacchetto arriva.  Vedi
        `_RiquadroGiorno`.
        """
        self._giorno = _RiquadroGiorno(self)
        self._giorno.scaricaRichiesta.connect(self.scaricaRichiesta.emit)
        self._giorno.annullaRichiesta.connect(self.annullaRichiesta.emit)
        self._giorno.aperta.connect(self.giornoAperto.emit)
        return self._giorno

    def scarico_giorno_inizia(self, totale: int = 0) -> None:
        riquadro = getattr(self, "_giorno", None)
        if riquadro is not None:
            riquadro.scarico_inizia(totale)

    def scarico_giorno_avanza(self, fatti: int, totale: int) -> None:
        riquadro = getattr(self, "_giorno", None)
        if riquadro is not None:
            riquadro.scarico_avanza(fatti, totale)

    def rileggi_il_giorno(self) -> None:
        """Un pacchetto e' arrivato sul disco: il riquadro si rifa.

        Lo chiama la finestra, perche' e' lei che guarda il disco e sa quando
        un pacchetto arriva.  Non si rilegge da soli a ogni avvio: il riquadro
        nasce gia' con la data e il versetto del giorno giusti, e rileggerlo due
        volte non cambia niente e fa due letture del pacchetto.
        """
        riquadro = getattr(self, "_giorno", None)
        if riquadro is not None:
            riquadro.rileggi()

    def aggiorna_riepilogo(self) -> None:
        """La riga delle novita', o niente.

        Si legge quello che l'ultimo controllo ha scritto.  Non si chiama il
        server da qui: la Home viene costruita all'avvio e non deve
        aspettare la rete per apparire.  Se non e' mai stato controllato,
        la riga non c'e' e basta.
        """
        testo = Aggiornamenti.riassunto()
        self._riepilogo.setText(testo)
        self._contenitore_riepilogo.setVisible(bool(testo))

    def _preferiti(self) -> QHBoxLayout:
        """I Preferiti, in griglia.

        Non se ne inventano: nell'app sono scelti dall'utente.  Se non ci
        sono, la sezione dice che non ce ne sono, cosi' si vede dove
        metterli.  Un preferito finto sarebbe peggio di uno spazio vuoto,
        perche' l'utente non saprebbe quale toccare per cambiarlo.

        LA GRIGLIA SI RI-COSTRUISCE
        ----------------------------
        Il numero dei Preferiti cambia quando l'utente ne aggiunge uno, e
        ogni volta cambia il numero di colonne.  Non si può tenere la
        griglia com'e' e riempirla: quando da tre colonne si passa a
        quattro, l'ultima cella deve spostarsi e la tabella non lo fa da
        sola.  Si butta via la griglia e si rifa: sono una decina di
        elementi, e il costo non si vede.

        LA GRIGLIA E' UN ATTRIBUTO
        --------------------------
        Perche' sta in ``self._striscia_preferiti`` e non in una variabile
        locale: il rifacimento serve anche quando l'utente aggiunge o
        toglie un Preferito, e quel e' un altro momento.  Una variabile
        locale muore con la funzione, e non c'e' nessun modo di richiamarla
        dopo.
        """
        disposizione = self._striscia_preferiti or QHBoxLayout()
        # 3 e non 10, e non 6 neppure.
        #
        # Le card sono quadrate e la copertina arriva al bordo della scheda:
        # con 10 pixel di vuoto due copertine sembrano due immagini sciolte,
        # con 6 sembrano due immagini vicine, e con 3 si vede che sono un
        # elenco.  Tre pixel e' la distanza a cui due copertine quadrate si
        # leggono come una striscia e non come due oggetti separati.
        disposizione.setSpacing(3)
        self._striscia_preferiti = disposizione

        while disposizione.count():
            elemento = disposizione.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()

        # Il riquadro sta nella PRIMA cella, non si stende su tutta la
        # larghezza.  Nella app precedente e' dentro la griglia a cinque
        # colonne, quindi occupa un quinto: stirato su tutta la pagina
        # sembra un errore di allineamento.
        voci = Preferiti.voci()
        if not voci:
            disposizione.addWidget(
                self._vuoto("Nessun preferito. Tasto destro su un titolo "
                            "per metterlo qui."))
            self._preferiti_accoppiati = []
            return disposizione

        # Gli accoppiamenti (sigla, lingua, traccia, card) servono a
        # `_copertine_dei_preferiti`, che viene chiamata subito dopo e deve
        # sapere a quale card mettere quale copertina.  Senza questo elenco la
        # copertina arriverebbe senza sapere a chi appartiene, e la prima card
        # prenderebbe tutte le immagini.
        #
        # La traccia sta nell'accoppiamento perche' due tracce della stessa
        # pubblicazione sono due card: con la sola sigla e lingua le due
        # avrebbero la stessa chiave e la copertina dell'una finirebbe
        # sull'altra.
        self._preferiti_accoppiati = []
        for voce in voci:
            sigla = voce.get("pubblicazione", "")
            lingua = voce.get("lingua", "I")
            titolo = voce.get("titolo") or sigla
            card = self._card_preferito(sigla, lingua, titolo,
                                        voce.get("traccia"),
                                        voce.get("formato", ""))
            disposizione.addWidget(card)
            self._preferiti_accoppiati.append(
                (sigla, lingua, voce.get("traccia"), card))
        # Lo spazio avanza resta a destra, non si spalma fra le card: due
        # Preferiti in una finestra larga devono stare a sinistra e non
        # spargersi per tutta la pagina.
        disposizione.addStretch(1)
        return disposizione

    def _card_preferito(self, sigla: str, lingua: str, titolo: str,
                        traccia=None, formato: str = "") -> _Card:
        """Una card dei Preferiti, con il tasto destro per toglierla.

        LA COPERTINA VERA, E NON IL GLIFO DEL LIBRO
        --------------------------------------------
        Prima qui c'era `simbolo="book"`: tutte le card avevano lo stesso
        glifo, e quattro Preferiti diversi sembravano la stessa immagine quattro
        volte.  Non si riconosceva nessuno.

        Adesso la copertina si chiede come in tutte le altre sezioni, e arriva
        dopo: la card si costruisce col glifo, che cosi' c'e' subito al primo
        sguardo, e quando i byte arrivano dal thread la copertina prende il
        suo posto.  Una copertina mancante lascia il glifo, che e' quello che
        si vuole vedere quando non c'e' niente.

        LA STELLA
        ---------
        Ogni card dei Preferiti è per definizione un Preferito, quindi la
        stella qui e' redundant: dice solo "questa è fra i Preferiti", e in
        questa sezione si sa gia'.  Non si mette.  Nelle altre sezioni, dove
        la stella accanto al titolo dice a una riga sola se quel titolo e' fra
        i Preferiti, quella dice una cosa che non si sa, e li' la stella sta.

        IL SOTTOTITOLO NON C'E' PIU'
        -------------------------
        Prima sotto il titolo c'era la sigla — «ypq», «es26» — e adesso non
        c'e' piu'.  Due ragioni, e la prima basta da sola: nella schermata
        dell'applicazione originale sotto la card dei Preferiti c'e' solo il
        titolo, e quello e' il riferimento; e la sigla non dice niente a chi
        guarda, perche' il nome e' gia' scritto due righe sopra.

        Il titolo resta, e resta anche la riga vuota che occupava: una card
        con il titolo su una riga sola e le altre su due righe hanno la stessa
        altezza, e una striscia di card tutte diverse sembra storta.

        IL CLIC
        -------
        Passa alla finestra la sigla e la lingua, e la finestra domanda a
        `JWPubManager.che_cosa_apre` che cosa aprire: il pacchetto, l'audio o
        il video.  La regola sta in un posto solo e non viene ricostruita
        qui: se la si ricostruisse, un Preferito aprirebbe una cosa e la stessa
        pubblicazione nella sezione Scaricati un'altra.

        IL GLIFO E' QUELLO CHE SI APRE
        ------------------------------
        Il glifo resta finche' non arriva la copertina — o per sempre, se non
        arriva (nessuna rete, o una pubblicazione che una copertina non ce
        l'ha).  Un glifo di libro su un video sarebbe la cosa sbagliata da
        guardare proprio nel momento in cui non c'e' altro da guardare, quindi
        lo decide la stessa regola che decide il clic: `che_cosa_apre`.
        Video -> il film, audio -> la nota, testo -> il libro.

        LA SIGLA VA PASSATA PER NOME
        ----------------------------
        Qui sotto c'era `_Card(titolo, sigla, simbolo="book", parent=self)`, e
        il secondo parametro posizionale di `_Card` non e' `sigla`: e'
        `sottotitolo`.  Quindi la sigla finiva sotto il titolo — e li si
        vedeva, quindi sembrava tutto a posto — mentre `sigla` restava la
        stringa vuota.

        E con la sigla vuota `_Card.mousePressEvent` non emette niente:

            if evento.button() == Qt.MouseButton.LeftButton and self._sigla:

        quindi premere un Preferito non apriva niente, e nemmeno il cursore
        diventava una mano.  Il sintomo non guardava ne' al collegamento dei
        segnali ne' alla finestra: guardava a questa riga, che passava un
        valore nel posto sbagliato e non lo diceva.

        Per questo `sigla` va passata per nome, e resta il posto suo: quello
        che dice alla card **che cosa aprire**, che e' un'altra cosa dal testo
        sotto il titolo e non va perso insieme a quello.
        """
        from Utility import CatalogoMedia, JWPubManager

        numero = _numero_traccia(traccia)
        formato = str(formato or "").upper()
        if numero is not None:
            # Una card di una traccia: la scheda la dice il formato salvato
            # insieme al Preferito.  Se manca — un Preferito scritto da una
            # versione che non lo salvava — si chiede al catalogo, che lo sa:
            # senza, la nuvoletta resterebbe accesa su un video gia' scaricato.
            if not formato:
                formato = CatalogoMedia.formato_di_traccia(sigla, lingua, numero)
            apri = "audio" if formato == "AUDIO" else "video"
        else:
            apri = JWPubManager.che_cosa_apre(sigla, lingua)
            if apri == "pubblicazione" and CatalogoMedia.e_di_media(sigla, lingua):
                # Una pubblicazione di media **non scaricata**: `che_cosa_apre`
                # guarda solo il disco e non la vede, ma il catalogo la
                # conosce.  Vedi `CatalogoMedia.e_di_media`.
                _numero, formato_catalogo = CatalogoMedia.prima_traccia_di(
                    sigla, lingua)
                apri = "audio" if formato_catalogo == "AUDIO" else "video"
        simbolo = {"video": "film", "audio": "music.note"}.get(apri, "book")

        # LA VOCE DELLA CARD, CON LA TRACCIA QUANDO C'E'
        # ---------------------------------------------
        # E' quella che rende la nuvoletta e il menu' capaci di parlare della
        # traccia giusta.  Per una pubblicazione intera la voce ha solo sigla
        # e lingua, ed e' quello che serve.
        voce_card = {"sigla": sigla, "lingua": lingua, "titolo": titolo,
                     "traccia": numero if numero is not None else "",
                     "formato": formato if numero is not None else "",
                     "durata": "", "numero": "", "miniatura": ""}
        card = _Card(titolo, sottotitolo="", sigla=sigla, lingua=lingua,
                     simbolo=simbolo, voce=voce_card, parent=self)
        card.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        azione = QAction(f"Togli «{titolo}» dai Preferiti", self)
        azione.triggered.connect(
            lambda: self._togli_preferito(sigla, lingua, numero))
        card.addAction(azione)
        if numero is not None:
            # Una traccia: si apre il lettore sulla traccia, come dalla card
            # dei media.  `mediaAperta` porta (sigla, lingua, traccia) e la
            # finestra fa partire proprio quella.
            card.aperta.connect(
                lambda _s, _l, s=sigla, lg=lingua, t=numero:
                    self.mediaAperta.emit(s, lg, t))
        else:
            card.aperta.connect(lambda _s, _l, s=sigla, lg=lingua:
                                self.aperta.emit(s, lg))
        # I tre puntini aprono il menu' condiviso, quello delle righe della
        # sezione Scaricati.  Qui non si sa se la pubblicazione e' scaricata,
        # quindi si passa `None` come cartella e il menu' toglie le voci che
        # non hanno un pacchetto: la voce "Elimina" c'e' solo se c'e' il
        # pacchetto, e non c'e' il caso di metterla per una pubblicazione che
        # non hai scaricato.
        card.menuChiesto.connect(
            lambda s, l, t=titolo, tr=numero, f=formato:
                self._menu_preferito(s, l, t, tr, f))
        # La nuvoletta: per una pubblicazione scarica il pacchetto, per una
        # traccia la risoluzione.  E' la stessa voce che va a chi scarica,
        # quindi non c'e' niente da decidere qui.
        card.scaricaChiesto.connect(self.scaricoChiesto.emit)
        card.aggiornaChiesto.connect(self.aggiorna.emit)
        self._card_per_sigla[(sigla, lingua, numero)] = card
        return card

    def _menu_novita(self, voce) -> None:
        """I tre puntini di una card di Novita' o del Kit.

        IL MENU' E' QUELLO DI `DownloadsView`, E LA VOCE DEI PREFERITI
        -------------------------------------------------------------
        Non se ne costruisce una copia: se un giorno quello ha una voce in
        piu', questa riga deve averla anche lei.

        Percio'`preferito` non e' True come per le card dei Preferiti, ma
        quello che e' davvero: la voce del menu' dice «Togli ... dai
        Preferiti» oppure «Aggiungi ... ai Preferiti», e su una riga che
        elenca le novita' direbbe «togli» a una pubblicazione che non e'
        mai stata messa fra i Preferiti.

        LA TRACCIA, NON SOLO LA SIGLA
        -----------------------------
        La card porta la sua voce, e la voce porta la traccia: aggiungere ai
        Preferiti «wsb traccia 2» e' un'altra cosa da «wsb traccia 1», e il
        menu' deve sapere quale delle due.  La stessa `preferito` chiede della
        traccia, non della pubblicazione: la stella della card dice se
        **questo video** e' fra i Preferiti.
        """
        from SubViews.DownloadsView import menu_operazione

        sigla = voce.get("sigla", "")
        lingua = voce.get("lingua", "I")
        traccia = voce.get("traccia")
        formato = voce.get("formato", "")
        titolo = voce.get("titolo", "")
        cartella = self._cartella_se_scaricata(sigla, lingua)
        menu_operazione(
            self, cartella, sigla, lingua,
            preferito=Preferiti.c_e_(sigla, lingua, traccia),
            eliminata=lambda: None,
            preferiti_cambiati=self._preferiti_mossi,
            messaggio=self.messaggio.emit,
            con_cestino=cartella is not None,
            traccia=traccia, formato=formato, titolo=titolo)

    def _menu_preferito(self, sigla: str, lingua: str, titolo: str,
                        traccia=None, formato: str = "") -> None:
        """Apre il menu' dei tre puntini su un Preferito della Home."""
        from SubViews.DownloadsView import menu_operazione

        cartella = self._cartella_se_scaricata(sigla, lingua)
        menu_operazione(
            self, cartella, sigla, lingua,
            preferito=True,                      # e' una card dei Preferiti
            eliminata=lambda: None,              # la lista la rileggera'
            preferiti_cambiati=self._preferiti_mossi,
            messaggio=self.messaggio.emit,
            con_cestino=cartella is not None,
            traccia=traccia, formato=formato, titolo=titolo)

    def _preferiti_mossi(self) -> None:
        """Un Preferito e' stato tolto dal menu': la griglia si rilegge."""
        self.aggiorna_preferiti()
        self.preferiti_messi.emit()

    @staticmethod
    def _cartella_se_scaricata(sigla: str, lingua: str, nome: str | None = None):
        """La cartella del pacchetto, o None se non e' scaricato.

        `nome` e' il nome esatto della cartella (`mwb_I_202611`): serve per
        le pubblicazioni con il numero, dove `<sigla>_<lingua>` da solo non
        esiste mai sul disco.
        """
        from Utility.Extensions.Ext_FileManager import get_documents_directory

        cartella = get_documents_directory() / (nome or f"{sigla}_{lingua}")
        return cartella if (cartella / "contents").is_dir() else None

    def _copertine_dei_preferiti(self) -> None:
        """Le copertine dei Preferiti, in un thread.

        IL PERCHE' DEL THREAD
        ---------------------
        `Copertine.pixmap_copertina` avvisa lei stessa: chiama la rete e non va
        chiamata dal main thread mentre si disegna.  Qui i Preferiti sono
        quattro, quindi l'attesa non si vedrebbe — ma l'attesa non e' il punto.
        Il punto e' che la Home si costruisce all'avvio, mentre la finestra si
        sta ancora piazzando, e quattro richieste in fila bloccano
        l'apertura.

        I TRE PEZZI DEL VIAGGIO
        -----------------------
        `dati_copertina` legge il pacchetto e la cache, e chiede al CDN se
        manca: gira nel thread e restituisce byte.  `pixmap_da_dati` costruisce
        il `QPixmap`, e quello va fatto sul main thread: costruire un
        `QPixmap` fuori dal main thread funziona una volta e poi dà
        `QPixmap: Must construct QPixmap before a QApplication`, o peggio,
        disegna a metà.

        `completion` gira sul main thread, quindi li' si mette il pixmap.
        """
        voci = list(self._preferiti_accoppiati)
        if not voci:
            return

        from Utility.Extensions.Ext_DispatchQueue import background

        risultati: list = []

        def lavoro() -> None:
            from Utility import Copertine, JWPubManager
            from Utility import CatalogoMedia

            for sigla, lingua, traccia, _card in voci:
                # LA COPERTINA DI UNA PUBBLICAZIONE DI MEDIA NON ESISTE
                # -----------------------------------------------------
                # Misurato: `dati_copertina("wsb", "I")` risponde **zero
                # byte**, e cosi' `whbs`.  Sono pubblicazioni fatte di video
                # e non hanno una copertina da chiedere: la card dei Preferiti
                # restava col glifo del libro, che per un video e' il glifo
                # sbagliato — ed e' il «non si vedono le icone di anteprima»
                # che si vedeva nella Home.
                #
                # La miniatura del video invece c'e', ed e' scritta nel
                # catalogo dei media: si prende da li'.  Vedi
                # `CatalogoMedia.miniatura_di`.
                #
                # La domanda «e' una pubblicazione di media?» la fa la regola
                # di sempre, `che_cosa_apre`, che e' anche quella che decide
                # cosa apre il clic: cosi' la card che apre un video e' anche
                # la card che **mostra** il video.  E per una **traccia** la
                # risposta la dà il catalogo anche senza il pacchetto, che e'
                # lo stesso caso di `_card_preferito`.
                consulta_catalogo = False
                if traccia not in (None, "", 0):
                    consulta_catalogo = True
                elif JWPubManager.che_cosa_apre(sigla, lingua) in ("video",
                                                                   "audio"):
                    consulta_catalogo = True
                elif CatalogoMedia.e_di_media(sigla, lingua):
                    consulta_catalogo = True

                dati = None
                if consulta_catalogo:
                    indirizzo = CatalogoMedia.miniatura_di(sigla, lingua)
                    if indirizzo:
                        dati = Copertine.scarica(indirizzo)
                if not dati:
                    pub = self._pubblicazione(sigla, lingua)
                    dati = Copertine.dati_copertina(pub, "md")
                risultati.append((sigla, lingua, traccia, dati))

        def arrivati() -> None:
            from PyQt6 import sip
            from Utility.Copertine import pixmap_da_dati

            # La chiave porta anche la traccia: due tracce della stessa
            # pubblicazione sono due card, e con la sola sigla e lingua la
            # copertina dell'una finirebbe sull'altra.
            accoppiati = {f"{s}_{l}_{t}": c for s, l, t, c in voci}
            for sigla, lingua, traccia, dati in risultati:
                card = accoppiati.get(f"{sigla}_{lingua}_{traccia}")
                # La scheda puo' essere stata distrutta mentre si scaricava:
                # l'utente ha tolto il Preferito, o ha cambiato sezione.
                if card is None or sip.isdeleted(card):
                    continue
                if dati:
                    card.metti_copertina(pixmap_da_dati(dati))

        background(lavoro, completion=arrivati)

    @staticmethod
    def _pubblicazione(sigla: str, lingua: str):
        """La ``Publication`` minima per chiedere una copertina.

        Serve solo il KeySymbol e la lingua: `Copertine` costruisce l'indirizzo
        con quelli.  Non si legge il catalogo perche' una copertina non vale una
        ricerca nel database da 3.741 righe, e il Preferito ce l'ha gia' scritto
        nella sigla.
        """
        from Utility import Lingua
        from Utility.Structures.Generals import Publication

        return Publication(
            ID=0, keySymbol=sigla, year=0,
            mepsLanguageId=Lingua.da_simbolo(lingua),
            publicationTypeId=0, issueTagNumber=0, title=sigla)

    def aggiorna_preferiti(self) -> None:
        """Rilegge la griglia dei Preferiti.  Solo quella.

        PERCHE' ESISTE UN METODO SOLO PER I PREFERITI
        ----------------------------------------------
        Prima, togliere un Preferito dalla Home emetteva
        ``aggiornamento_chiesto``, che e' lo stesso segnale del pulsante
        Aggiorna della fascia.  E il pulsante Aggiorna fa tre cose: interroga
        il server, rilegge il catalogo e ricrea le sezioni.

        Sono tre cose che non c'entrano niente con una stella che compare o
        scompare, e il prezzo si sentiva: quattro richieste di rete per
        rivedere una griglia di quattro nomi.  Peggio: la Home si ricreava da
        capo, quindi anche il testo del giorno tornava indietro, e se
        l'utente stava guardando la Home perdeva quello che stava leggendo.

        Qui il lavoro e' uno solo e finisce subito: rilegge il file dei
        Preferiti e ricarica le card.  Il server non viene toccato, e la
        sezione non viene ricreata.

        Chiama ``_preferiti()`` e basta.  Quel metodo prende la griglia che
        c'e' gia' (``self._striscia_preferiti``), la svuota, e la riempie: il
        numero di Preferiti cambia e con esso il numero di colonne, e una
        griglia non si riempie da sola.  RICHIAMARLO NON CREA UN NUOVO LAYOUT,
        e non si tocca il layout che lo contiene: rifare qui quello che
        ``_preferiti()`` gia' fa significherebbe due posti che svuotano la
        stessa griglia, e il secondo non si accorgerebbe che il primo ha
        gia' tolto tutto.

        E POI RILEGGE LE COPERTINE, perche' se ne aggiunge una nuova non ha
        immagine finche' qualcuno non passa di qui.
        """
        self._preferiti()
        self._copertine_dei_preferiti()

    def _togli_preferito(self, sigla: str, lingua: str, traccia=None) -> None:
        Preferiti.togli(sigla, lingua, traccia)
        # NON emette `aggiornamento_chiesto`: quello e' il pulsante Aggiorna,
        # e per togliere una stella non serve chiedere niente al server.
        self.aggiorna_preferiti()

    def _vuoto(self, testo: str) -> QLabel:
        """Il riquadro grigio di quando non c'e' niente."""
        etichetta = QLabel(testo, self)
        etichetta.setObjectName("vuoto")
        etichetta.setWordWrap(True)
        etichetta.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Minimum)
        return etichetta