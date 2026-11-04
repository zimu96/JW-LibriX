#
#  SplashScreen.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La schermata di avvio, spostata fuori da SidebarView.py.

`SidebarView` la importa con lo stesso nome (`_SplashScreen`), quindi
`from SidebarView import _SplashScreen` continua a funzionare.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from SubViews.HomeView import _barra_scaricamento
from Utility.Stuff import icon, icona_tabler


class _SplashScreen(QWidget):
    """La schermata di avvio: **un terminale con sopra il logo**.

    COSA FA, IN UNA FRASE
    ---------------------
    E' la finestra che si apre quando parte il programma, e fa **le cose che
    fa il terminale**: da' il benvenuto al log, lascia che il programma si
    costruisca, e prende i cataloghi se l'utente ha chiesto che siano presi
    da soli.  Poi si chiude e fa spazio alla finestra principale.

    LA X IN ALTO A DESTRA CHIUDE IL PROGRAMMA
    ------------------------------------------
    Non chiude la schermata: chiude **tutto**.  Il programma e' partito per
    caso e l'utente non lo voleva: la X e' l'unico modo per tornare indietro
    senza aspettare che finisca un download di 58 megabyte.

    Se chiudesse solo la schermata, il programma resterebbe vivo senza
    finestra e senza via d'uscita — dovrebbe chiuderlo dal gestore dei
    processi.  Quindi la X chiude il programma, ed e' anche il modo normale
    per interrompere un aggiornamento a meta'.

    PERCHE' NESSUN TEMPO MINIMO
    ---------------------------
    Prima c'era un secondo e poco: la schermata restava li' un secondo anche
    se non aveva niente da fare.  Non serve piu', perche' adesso la
    schermata non e' una pausa con dentro un logo: **e' il lavoro**.  Resta
    quanto basta per essere disegnata — una volta, senza orologio — e poi
    finisce quando ha finito.

    Un tempo minimo e' una promise falsa: dopo mezzo secondo l'utente vede
    che il logo e' sparito e non sa se il programma e' partito o no.  Meglio
    vederlo partire che vederlo trattenuto.

    IL LOG
    ------
    Il testo del terminale e' qui dentro, sotto il pannello nero con il logo.
    Non e' una decorazione: e' la stessa riga che va al terminale vero
    (`Messaggi.devia`), quindi l'utente che lancia da riga di comando vede i
    log come sempre, e quello che lancia dall'icona li vede qui e non da
    nessuna parte.

    Se qualcosa va storto, i warning e gli errori finiscono in una finestra
    con i dettagli e con «Salva log» in TXT o JSON — la stessa cosa che si
    fa dalle Impostazioni.
    """

    #: Emesso quando la schermata ha finito: (ok, righe di log con problemi)
    finito = Signal(bool, list)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("splashScreen")

        self._errori_log: list[str] = []
        self._auto_update_attivo = False
        self._cataloghi_in_corso = 0
        self._annullato = False
        #: Un errore ha fermato il programma: la schermata e' quella degli
        #: errori e la finestra principale non parte.  Vedi `_riga_di_log`.
        self._bloccata = False
        # Il segnale `finito` esce una volta sola: vedi `_finito`.
        self._finito_emesso = False

        # SENZA IL CONTORNO DELLA FINESTRA DI SISTEMA
        # --------------------------------------------
        # Il programma originale non ha cornici, e qui si e' deciso che non
        # le avesse nemmeno questa schermata: il nero arriva fino al bordo
        # dello schermo e la finestra non si staglia dal fondo.  Però la X
        # serve — vedi `_costruisci_chiudi` — e senza `FramelessWindowHint`
        # non ci sarebbe stato modo di metterla, perche' il bordo di sistema
        # non si tocca e quello di sistema porta gia' la sua X.
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("JW LibriX")
        self.setStyleSheet("background-color: #000000;")

        # IL TERMINALE
        # ------------
        # Il riquadro di testo che prende il log, sotto tutto il resto.  Non
        # si mette in un menu' e non si mostra a comando: sta qui perche' e'
        # quello che il programma sta dicendo, e il pannello con il logo ci
        # passa sopra.
        self.terminale = QPlainTextEdit(self)
        self.terminale.setReadOnly(True)
        self.terminale.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.terminale.setStyleSheet(
            "QPlainTextEdit { background-color: #000000; color: #cfcfcf;"
            " border: none; font-family: monospace; font-size: 11px; }")
        self.terminale.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                                    True)
        self.terminale.show()

        # IL PANELLO: L'IMMAGINE CHE NASCONDE IL LOG
        # ------------------------------------------
        # Un riquadro nero, sopra il terminale, con il logo e la barra.  E' il
        # pezzo che l'utente vede: il log c'e' dietro e non si vede, che e'
        # esattamente quello che e' successo nell'app originale quando la
        # schermata copriva il terminale.
        self.pannello = QWidget(self)
        self.pannello.setStyleSheet("background-color: #000000;")
        self.pannello.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                                   True)

        scatola = QVBoxLayout(self.pannello)
        scatola.setContentsMargins(40, 40, 40, 40)
        scatola.setSpacing(20)
        scatola.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo = self._costruisci_logo()
        scatola.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)

        self.barra, self._barra_inizia, self._barra_avanza, self._barra_finita = \
            _barra_scaricamento(self.pannello, 360)
        self.barra.setFixedWidth(360)
        self._barra_inizia(0)
        scatola.addWidget(self.barra, 0, Qt.AlignmentFlag.AlignHCenter)

        self.stato = QLabel("", self.pannello)
        self.stato.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stato.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        self.stato.setVisible(False)
        self.stato = QLabel("", self.pannello)
        self.stato.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stato.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        self.stato.setVisible(False)
        scatola.addWidget(self.stato, 0, Qt.AlignmentFlag.AlignHCenter)

        self._costruisci_errori()
        self._costruisci_chiudi()

        self.resize(760, 520)
        # `_rimetti` va chiamata **qui** e non solo da `resizeEvent`: il primo
        # `resize()` della vita di una finestra non passa da `resizeEvent`, e
        # senza questa riga la X resterebbe nell'angolo in alto a sinistra fino
        # alla prima ridimensionata della finestra.
        self._rimetti()

    # ------------------------------------------------------------------

    def _costruisci_errori(self) -> None:
        """La fascia degli errori, in fondo, che si vede solo se serve.

        LA SCHERMATA DEGLI ERRORI E' LA STESSA FINESTRA
        ------------------------------------------------
        Non e' una finestra di dialogo sopra: e' **questa** finestra che
        cambia faccia.  Il pannello col logo sparisce, il terminale si vede
        per intero — e cosi' l'utente legge tutto quello che il programma ha
        detto, non solo gli errori — e in fondo compaiono la frase e i bottoni.

        Perche' non una finestra a parte: chi non ha un terminale, aprendo un
       'altra finestra avrebbe il log nascosto dietro un riquadro di dialogo, e
        dovrebbe cliccare «Dettagli» per sapere cosa e' andato storto.  Qui il
        log e' gia' li', e si puo' anche selezionare e copiare.

        PERCHE' DUE BOTTONI E NON TRE
        -----------------------------
        «Salva con nome...» e «Esci».  Non c'e' «prova a partire» perche' la
        schermata si mostra solo quando il programma **non puo'** continuare:
        andare avanti a meta' di un crash vuol dire che il difetto si vede tre
        schermate dopo, quando non si sa piu' cosa l'ha causato.

        Il terzo bottone, «Ignora e parti», c'e' **solo** quando la schermata
        e' stata aperta per un avviso e non per un errore: li' il programma sa
        funzionare, e l'avviso e' roba che non c'entra.  Vedi `_mostra_errori`.
        """
        self.scatola_errori = QWidget(self)
        self.scatola_errori.setObjectName("erroriSplash")
        self.scatola_errori.setStyleSheet(
            "#erroriSplash { background-color: #1b1b1b;"
            " border-top: 1px solid #3a3a3a; }")
        self.scatola_errori.setVisible(False)

        dentro = QHBoxLayout(self.scatola_errori)
        dentro.setContentsMargins(20, 14, 20, 16)
        dentro.setSpacing(12)

        self.frase_errori = QLabel("", self.scatola_errori)
        self.frase_errori.setWordWrap(True)
        self.frase_errori.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        dentro.addWidget(self.frase_errori, 1)

        bottoni = QVBoxLayout()
        bottoni.setSpacing(6)

        self.pulsante_salva = QPushButton("Salva con nome...", self.scatola_errori)
        self.pulsante_salva.setObjectName("salvaLogSplash")
        self.pulsante_salva.setToolTip("Salva questo log dove vuoi")
        self.pulsante_salva.setStyleSheet(
            "QPushButton#salvaLogSplash { background-color: #64398b; color: white;"
            " border: none; border-radius: 4px; padding: 7px 14px; }"
            "QPushButton#salvaLogSplash:hover { background-color: #a77fd4; }")
        self.pulsante_salva.clicked.connect(self._salva_e_ferma)
        bottoni.addWidget(self.pulsante_salva)

        self.pulsante_ignora = QPushButton("Ignora e parti", self.scatola_errori)
        self.pulsante_ignora.setObjectName("ignoraSplash")
        self.pulsante_ignora.setStyleSheet(
            "QPushButton#ignoraSplash { background: transparent; color: #cfcfcf;"
            " border: 1px solid #5a5a5a; border-radius: 4px; padding: 6px 12px; }"
            "QPushButton#ignoraSplash:hover { border-color: #cfcfcf; }")
        self.pulsante_ignora.clicked.connect(self._ignora)
        bottoni.addWidget(self.pulsante_ignora)

        self.pulsante_esci = QPushButton("Esci", self.scatola_errori)
        self.pulsante_esci.setObjectName("esciSplash")
        self.pulsante_esci.setStyleSheet(
            "QPushButton#esciSplash { background: transparent; color: #cfcfcf;"
            " border: 1px solid #5a5a5a; border-radius: 4px; padding: 6px 12px; }"
            "QPushButton#esciSplash:hover { border-color: #cfcfcf; }")
        self.pulsante_esci.clicked.connect(self._annulla)
        bottoni.addWidget(self.pulsante_esci)

        dentro.addLayout(bottoni)
    # ------------------------------------------------------------------

    def _costruisci_logo(self) -> QLabel:
        """Il logo, centrato.

        `Files/JWLibrary.png` e' il file che c'e' sempre: e' quello che
        `installa.sh` mette anche nell'icona del menu'.  Il 1024 e' il ripiego,
        per quando il programma gira da una copia dove manca.
        """
        from pathlib import Path

        from PyQt6.QtGui import QPixmap

        radice = Path(__file__).resolve().parent
        for nome, via in (("Files/JWLibrary.png", "Files/JWLibrary.png"),
                          ("Files/icons/1024.png", "Files/icons/1024.png")):
            percorso = radice / via
            if not percorso.is_file():
                continue
            etichetta = QLabel(self.pannello)
            etichetta.setAlignment(Qt.AlignmentFlag.AlignCenter)
            etichetta.setPixmap(QPixmap(str(percorso)).scaled(
                128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            return etichetta
        etichetta = QLabel(self.pannello)
        etichetta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etichetta.setPixmap(icona_tabler("book", "#ffffff", 128).pixmap(128, 128))
        return etichetta

    def _costruisci_chiudi(self) -> None:
        """La X in alto a destra.

        Sta **dentro** la finestra senza bordi, perche' il bordo di sistema
        non c'e': senza questo pulsante la schermata non si chiuderebbe.

        Non e' un tasto della finestra di sistema, quindi non eredita niente da
        lei: disegna una X e basta, con lo stesso colore del pannello.
        """
        self.chiudi = QPushButton(self)
        self.chiudi.setObjectName("chiudiSplash")
        self.chiudi.setIcon(icon("xmark", "#cfcfcf", 16))
        self.chiudi.setIconSize(QSize(16, 16))
        self.chiudi.setFixedSize(30, 30)
        self.chiudi.setFlat(True)
        self.chiudi.setToolTip("Chiudi il programma")
        self.chiudi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chiudi.setStyleSheet(
            "QPushButton#chiudiSplash { background: transparent; border: none; }"
            "QPushButton#chiudiSplash:hover { background-color: #3a3a3a;"
            " border-radius: 4px; }")
        self.chiudi.clicked.connect(self._annulla)

    def resizeEvent(self, evento) -> None:
        """Il terminale e il pannello seguono la finestra."""
        super().resizeEvent(evento)
        self._rimetti()

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        self._rimetti()

    def _rimetti(self) -> None:
        """Mette i pezzi al loro posto, secondo la faccia che ha la finestra.

        Due facce, e `_mostra_errori` sceglie quale:

            lavoro   il pannello col logo davanti, il terminale dietro
            errori   il terminale davanti, a tutta altezza meno la fascia in
                     fondo, il pannello nascosto
        """
        area = self.rect()
        if self.scatola_errori.isVisible():
            fascia = self.scatola_errori.sizeHint().height()
            self.scatola_errori.setGeometry(0, area.height() - fascia,
                                            area.width(), fascia)
            self.terminale.setGeometry(area.adjusted(0, 0, 0, -fascia))
            self.terminale.show()
            self.terminale.raise_()
            self.scatola_errori.raise_()
        else:
            self.terminale.setGeometry(area)
            self.pannello.setGeometry(area)
            self.terminale.lower()
            # Dietro il logo il testo non lo vede nessuno: nascosto non si
            # disegna.  Si rimostra da solo quando serve (faccia degli errori).
            self.terminale.hide()
            self.pannello.raise_()
        # La X sta sopra tutto, altrimenti il pannello nero — che e' un widget
        # a tutto schermo — la coprirebbe e non si potrebbe premere.
        self.chiudi.move(area.width() - 38, 8)
        self.chiudi.raise_()

    # ------------------------------------------------------------------

    def scrivi(self, riga: str) -> None:
        """Una riga arriva dal terminale del programma.

        Sta **sotto** il pannello del logo, quindi non si vede mentre la
        schermata lavora.  Va messa lo stesso perche' e' la stessa riga che
        andrebbe a schermo, e quando la faccia diventa quella degli errori il
        terminale si vede: e non si vede **solo** la lista degli errori, si vede
        tutto, perche' a metà di un crash la riga che spiega il crash spesso
        arriva tre righe dopo di quella che l'ha causato.
        """
        self.terminale.appendPlainText(riga)

    def _riga_di_log(self, testo: str, livello: str) -> None:
        """Una riga di log e' arrivata **mentre** il programma scrive.

        E' l'orecchio della schermata: `Messaggi` la chiama per ogni messaggio,
        con il livello accanto, e qui si decide cosa farne.

        LA REGOLA, IN DUE TEMPI
        -----------------------
        Il testo va **sempre** nel terminale: sia l'avviso che l'errore.  Poi,
        solo se il livello e' di quelli che fermano, la schermata si blocca.

        «SOLO SE», E NON «SE E' UN AVVISO, NON SI FERMA MAI»
        ---------------------------------------------------
        La distinzione non e' fra parole: e' fra livelli.  Un avviso su questa
        macchina lo scrive Qt a ogni avvio — «This plugin does not support
        propagateSizeHints()» — e non ha niente a che fare con il programma.
        Bloccare su un avviso vuol dire che il programma non parte piu' su
        quelle macchine, e un programma che non parte e' un difetto peggiore di
        un avviso che si registra.

        Un'eccezione non gestita invece lascia il programma in uno stato che
        nessuno conosce: proseguire vuol dire che il difetto si vede tre
        schermate dopo, quando non si sa piu' cosa l'ha causato.  Per quello la
        schermata si ferma.

        `LIVELLO_BLOCCANTE` e' la lista, ed e' in `Messaggi`: la decisione e'
        sul livello che Qt ha dato, e metterla qui dentro significherebbe
        avere due elenchi che possono dire cose diverse.
        """
        from Utility import Messaggi

        self.scrivi(testo)
        if self._annullato or self._bloccata:
            return
        if livello not in Messaggi.LIVELLO_BLOCCANTE:
            return
        self._blocca(testo)

    def _blocca(self, prima_riga: str) -> None:
        """Un errore ha fermato il programma: la schermata si ferma con lui.

        SI FERMA «ALL'ISTANTE»
        ----------------------
        `_bloccata` viene messa **prima** di qualsiasi altra cosa, perche' da
        quel momento `_risposta` e `_concluso` smettono di fare il loro lavoro:
        se un download in corso richiamasse `_finito` dopo, aprirebbe la
        finestra principale sopra una schermata che dice che il programma e'
        rotto, e l'utente vedrebbe partire un programma che un secondo prima
        gli ha detto di non partire.

        Il lavoro che resta a meta' non si ferma — sono thread separati e non
        c'e' un modo onesto per interromperli — ma nessuno se ne accorge e il
        programma non parte, quindi non resta niente a meta'.  Quello che non
        arriva si rifinisce al giro dopo: `FileDownloader` lascia il `.part`.
        """
        if self._annullato or self._bloccata:
            return
        self._bloccata = True

        from Utility import Messaggi

        self._errori_log = Messaggi.problemi_bloccanti() or self._errori_log
        self._mostra_errori(bloccante=True)

    def _mostra_errori(self, bloccante: bool) -> None:
        """La finestra cambia faccia: via il logo, dentro il log, i bottoni.

        LA FRASE DIPENDE DA UN SOLO FATTO
        ---------------------------------
        Se `bloccante`, il programma non parte e c'e' una riga che dice
        perche'.  Se non lo e', il programma parte e i bottoni sono diversi.

        Il testo del terminale si vede **sempre**, anche quando l'errore non
        blocca: l'utente che l'ha letto vuole sapere cos'e' successo, e
        chiedergli di aprire un altro file per saperlo e' una richiesta che
        nessuno fa.

        NON SI MOSTRA UN LOG VUOTO
        --------------------------
        Se per un errore la lista e' vuota — un errore aggiunto a mano da
        `_avviso`, per esempio — si scrive il testo dell'errore ricevuto, cosi'
        la schermata non si presenta con «0 errori» mentre l'utente ha visto
        comparire la finestrella: e' l'unico caso in cui una schermata vuota
        fa piu' danno di una schermata che dice una cosa in piu'.
        """
        if not self._errori_log:
            self._errori_log = ["(il dettaglio dell'errore non e' stato "
                                "registrato)"]

        numero = len(self._errori_log)
        if bloccante:
            # «C'e' 1 errore» e «Ci sono 3 errori»: due forme diverse, e con
            # una sola si scrive «Ci sono 1 errore che impediscono», che fa
            # capire che la riga e' scritta da una macchina.  Il numero e'
            # contato perche' la frase dice anche quanti, e senza dire quanti
            # l'utente non sa se e' una cosa sola o un programma distrutto.
            if numero == 1:
                titolo = "C'e' 1 errore che impedisce al programma di partire."
            else:
                titolo = (f"Ci sono {numero} errori che impediscono al "
                          f"programma di partire.")
            self.frase_errori.setText(
                f"{titolo}\n"
                f"Sopra c'e' tutto quello che e' stato scritto. Salvalo e "
                f"mandalo a chi sviluppa il programma.")
            # Senza «Ignora e parti»: continuare sapendo che qualcosa e' rotto
            # e' la parte peggiore, perche' il difetto si vede molto piu' in
            # la' e non si sa piu' cosa l'ha causato.
            self.pulsante_ignora.setVisible(False)
        else:
            if numero == 1:
                titolo = "C'e' 1 messaggio con problemi, ma nessuno che fermi il programma."
            else:
                titolo = (f"{numero} messaggi con problemi, ma nessuno che "
                          f"fermi il programma.")
            self.frase_errori.setText(
                f"{titolo}\n"
                f"Sopra c'e' tutto quello che e' stato scritto.")
            self.pulsante_ignora.setVisible(True)
        # Il terminale smette di mangiare i clic: adesso l'utente deve poterlo
        # selezionare e copiare, e' il posto dove sta la risposta.
        self.terminale.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                                    False)
        self.terminale.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.pannello.hide()
        self.scatola_errori.show()
        self._rimetti()

        if bloccante:
            self._termina_lascolto()
        self._blocca_chiavi()

    def _blocca_chiavi(self) -> None:
        """Nella faccia degli errori la finestra va in primo piano.

        Senza, la schermata si ferma **sotto** un'altra finestra e l'utente non
        vede niente: sembra che il programma non sia partito, che e' la cosa
        peggiore quando invece si e' fermato per dirti che cosa e' successo.
        """
        try:
            self.show()
            self.raise_()
            self.activateWindow()
        except RuntimeError:
            pass

    def _termina_lascolto(self) -> None:
        """La finestra principale sta per aprirsi: la schermata smette di ascoltare.

        Senza, l'osservatore resta nella lista di `Messaggi` per tutta la
        sessione e ogni messaggio del programma continua a venire qui, dentro
        una schermata che e' stata distrutta: si accumula in un widget morto
        finche' la memoria va via, e ogni tanto butta fuori una riga.
        """
        from Utility import Messaggi
        Messaggi.non_guardare(self._riga_di_log)

    def _salva_e_ferma(self) -> None:
        """Il bottone «Salva con nome...».

        Dopo aver salvato la schermata **resta li'**.  Non si chiude e non
        parte: l'utente che ha salvato il log di solito vuole anche leggerlo o
        controllare che sia completo, e una finestra che sparisce appena si
        preme un bottone toglie il tempo per farlo.
        """
        self._salva_log()

    def _ignora(self) -> None:
        """Il bottone «Ignora e parti»: gli avvisi non fermano il programma.

        EMETTE DIRETTAMENTE, E NON ATTRAVERSA `_finito`
        -------------------------------------------------
        Perche' `_finito` e' gia' stata chiamata — e' lei che ha aperto questa
        schermata — quindi il suo fermo («una volta sola») la lascerebbe passare
        e non succederebbe niente.  Il bottone che riprende il programma non
        e' la fine del lavoro: e' una scelta dell'utente, e va detta per quello
        che e'.

        Non c'e' nessuna condizione nascosta: se il bottone non c'e' — cioe' se
        l'errore blocca davvero — premere un bottone che non esiste non fa
        partire un programma rotto.
        """
        if not self.pulsante_ignora.isVisible():
            return
        from Utility import Messaggi
        Messaggi.ripristina()
        self._termina_lascolto()
        self.finito.emit(True, self._errori_log)

    def imposta_stato(self, testo: str) -> None:
        """La scritta sotto la barra: «Sta succedendo questo».

        PUBBLICA, E CON UN NOME
        -----------------------
        Prima l'unico modo di scriverci era mettere le mani su `self.stato` da
        fuori.  Ora e' un metodo, perche' a scriverci e' anche il pezzo che
        mette in fila i controlli dell'avvio: senza un nome suo, quel pezzo
        avrebbe scritto `splash.stato.setText(...)` e i due posti che scrivono la
        stessa riga avrebbero cominciato a divergere alla prima modifica — che e'
        esattamente il difetto che questo metodo evita.

        Una riga vuota nasconde la scritta: senza, dopo il lavoro fatto la
        scritta resterebbe li' a dire «Sta scaricando» quando non sta
        scaricando piu' niente.
        """
        self.stato.setText(testo or "")
        self.stato.setVisible(bool(testo))

    def imposta_errori_log(self, errori: list[str]) -> None:
        """Le righe con problemi, catturate mentre il programma si costruiva."""
        self._errori_log = list(errori or [])
    def imposta_auto_update(self, attivo: bool) -> None:
        """Se prendere i cataloghi da soli all'avvio, se l'utente lo vuole."""
        self._auto_update_attivo = attivo

    # ------------------------------------------------------------------

    def start(self) -> None:
        """Parte: mostra, si mette in ascolto del terminale, e lavora.

        L'ORDINE E' OBBLIGATO
        ---------------------
        Prima si mostra e si disegna, poi si devia il terminale, poi si
        lavora.  Con l'ordine diverso il lavoro comincia prima che la
        finestra esista, e i primi secondi di log — che sono quelli
        interessanti, perche' sono i moduli che caricano — arrivano quando
        l'utente sta ancora guardando il vuoto.
        """
        from PyQt6.QtWidgets import QApplication

        from Utility import Messaggi

        self.show()
        # Un giro di eventi, non un'attesa: serve a far **disegnare** la
        # finestra, non a trattenerla.  E' l'unico momento in cui il tempo e'
        # di proposito.
        QApplication.processEvents()

        # QUELLO CHE E' SUCCESSO PRIMA
        # ---------------------------
        # Il terminale parte vuoto, ma il log no: fra l'avvio di Python e
        # questo momento i moduli sono entrati e qualcosa puo' essere andato
        # storto.  Quelle righe si mettono dentro adesso, altrimenti la
        # schermata degli errori direbbe «NameError» e mostrerebbe un terminale
        # vuoto — la cosa peggiore che possa fare una finestra che serve
        # proprio a far vedere l'errore.
        for riga in Messaggi.ULTIMI:
            self.terminale.appendPlainText(riga)

        # SE IL PROGRAMMA E' GIA' CRASHATO PRIMA DI ADESSO, SI FERMA QUI
        # -----------------------------------------------------------------
        # Tutto quello che c'e' fra l'avvio di Python e questo punto — gli
        # import, la costruzione della finestra — e' gia' passato, e un errore
        # li' e' gia' dentro `Messaggi`.  Se non si guarda adesso, la schermata
        # si mette in ascolto, trova il lavoro che deve fare, lo fa, e alla
        # fine apre la finestra principale: un programma che parte dopo aver
        # detto due volte che e' rotto.
        #
        # E' il caso piu' importante di tutti: il crash di cui l'utente si
        # accorgera' e' quasi sempre qui dentro, non mentre si scarica un
        # catalogo.
        if Messaggi.problemi_bloccanti():
            self._blocca("")
            return

        # Due ascolti, e non sono la stessa cosa:
        #
        #   `devia`   prende quello che il programma scrive con `print` e che
        #             andrebbe sul terminale.  Non ha un livello: e' testo.
        #   `osserva`  prende il log di Qt e delle eccezioni, **con il
        #             livello**.  E' da qui che si vede se quello che e'
        #             arrivato e' un errore che ferma il programma o un avviso
        #             che si registra e si lascia passare.
        #
        # L'ordine conta: `osserva` va montato per primo, cosi' anche un
        # errore scritto fra il primo giro di eventi e il lavoro non passa
        # inosservato.
        Messaggi.osserva(self._riga_di_log)
        Messaggi.devia(self.scrivi)

        # Il lavoro parte con `processEvents` gia' passato: la finestra e' a
        # schermo e non si rivede piu' il vuoto.
        QTimer.singleShot(0, self._lavoro)

    def _annulla(self) -> None:
        """La X: chiude il programma, anche a meta' di un download.

        Non si chiede conferma e non si prova a fermare i download: sono
        thread separati e non c'e' un modo onesto per fermarli a meta'.  Quello
        che non arriva si riconsiglia al giro dopo — `FileDownloader` lascia
        il `.part` e ricomincia.
        """
        self._annullato = True
        from Utility import Messaggi
        Messaggi.ripristina()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    # ------------------------------------------------------------------

    def _lavoro(self) -> None:
        """Il lavoro dell'avvio, tutto qui dentro.

        Sono tre cose, e sono nell'ordine in cui le fa il programma quando
        parte dal terminale:

            1. controllare i log diWARNING e ERROR raccolti fin qui
            2. se l'utente ha chiesto l'aggiornamento automatico, chiedere al
               server se c'e' un catalogo piu' nuovo e prenderlo
            3. chiudere la schermata e far partire la finestra

        Il controllo al server va in un thread: `catalogo_vecchio` fa due
        richieste e mezzo minuto di attesa sul main thread sembrerebbe un
        programma piantato, e qui la schermata **sarebbe** un programma
        piantato, perche' non c'e' nient'altro da premere.
        """
        from Utility.Extensions.Ext_DispatchQueue import background, on_main

        if self._auto_update_attivo:
            self.stato.setText("Controllo gli aggiornamenti...")
            self.stato.setVisible(True)
            self._barra_inizia(0)
        else:
            self.stato.setVisible(False)

        if not self._auto_update_attivo:
            self._finito(True)
            return

        def domanda() -> None:
            from Utility import Aggiornamenti, CatalogoMedia, Lingua
            lingua = Lingua.corrente_simbolo()
            try:
                catalogo = Aggiornamenti.catalogo_vecchio()
                media = CatalogoMedia.da_aggiornare(lingua)
            except Exception as errore:  # noqa: BLE001
                # Una domanda al server che va storta non e' un motivo per
                # non aprire il programma: si registra e si parte.  Il
                # programma senza catalogo mostra poco, ma si apre.
                motivo = str(errore)
                on_main(lambda: self._avviso(f"controllo non riuscito: {motivo}"))
                catalogo = media = False
            on_main(lambda: self._risposta(catalogo, media, lingua))

        background(domanda)

    def _risposta(self, catalogo_vecchio: bool, media_vecchio: bool,
                  lingua: str) -> None:
        """Il server ha risposto: si prende quello che c'e'.

        Sono due cataloghi e due domande, e possono partire **insieme**: il
        dei media finisce prima perche' e' molto piu' piccolo.  Con una
        bandierina sola il primo che arriva chiuderebbe la schermata e
        l'altro continuerebbe a scaricare senza che nessuno lo aspetti, e la
        finestra si aprirebbe su un catalogo vecchio.  Il contatore sale a
        due e scende a uno a uno.
        """
        if self._annullato or self._finito_emesso:
            return
        if not catalogo_vecchio and not media_vecchio:
            self.stato.setVisible(False)
            self._finito(True)
            return

        from Utility import Aggiornamenti, CatalogoMedia

        if catalogo_vecchio:
            self._cataloghi_in_corso += 1
            self.stato.setText("Scarico il catalogo delle pubblicazioni...")
            self._barra_inizia(0)
            Aggiornamenti.scarica_catalogo(
                completion=self._catalogo_preso,
                on_progress=self._avanza("catalogo delle pubblicazioni"),
            )
        if media_vecchio:
            self._cataloghi_in_corso += 1
            self.stato.setText("Scarico l'elenco dei video e dell'audio...")
            self._barra_inizia(0)
            CatalogoMedia.scarica(
                lingua,
                completion=self._media_preso,
                on_progress=self._avanza("elenco dei media"),
            )

    def _avanza(self, cosa: str):
        """Il callback dell'avanzamento, con la frase da scrivere sotto.

        Si chiama `on_progress` **gia' sul main thread** — e' `FileDownloader` e
        `Aggiornamenti` che lo rimettono li' appena — quindi qui non c'e' niente
        da spostare: mettere un `on_main` dentro sarebbe un doppio giro che
        ritarda la barra di un ciclo di eventi e non aggiunge niente.
        """
        def progresso(scritti: int, totale: int) -> None:
            if totale <= 0:
                # Totale zero: il server non ha detto quanto pesa.  La barra
                # resta indeterminata e la frase non promette un numero che
                # non si conosce.
                messaggio = f"Scarico {cosa}..."
            elif totale >= 1024 * 1024:
                messaggio = (f"Scarico {cosa}: "
                             f"{scritti // (1024 * 1024)} di "
                             f"{totale // (1024 * 1024)} MB")
            elif totale >= 1024:
                # Sotto il megabyte non si divide per il megabyte: si
                # arriverebbe a scrivere «0 di 0 MB», che e' una barra che
                # non dice niente proprio mentre l'utente la guarda.
                messaggio = (f"Scarico {cosa}: "
                             f"{scritti // 1024} di {totale // 1024} KB")
            else:
                # Sotto il chilobyte non si sa niente: si dice solo che si
                # sta scaricando.  Meglio una frase povera che una
                # percentuale che non c'e'.
                messaggio = f"Scarico {cosa}..."
            self.stato.setText(messaggio)
            if totale > 0:
                self._barra_avanza(scritti, totale)

        return progresso

    def _catalogo_preso(self, versione: str, errore: str) -> None:
        """Il catalogo delle pubblicazioni e' arrivato."""
        self._concluso("Catalogo delle pubblicazioni", errore)

    def _media_preso(self, percorso: str, errore: str) -> None:
        """L'elenco dei media e' arrivato."""
        self._concluso("Elenco dei media", errore)

    def _concluso(self, cosa: str, errore: str) -> None:
        """Un catalogo ha finito: se era l'ultimo, la schermata chiude."""
        if self._annullato:
            return
        self._cataloghi_in_corso = max(0, self._cataloghi_in_corso - 1)
        if errore:
            self._avviso(f"{cosa}: {errore}")
        if self._cataloghi_in_corso > 0:
            return
        self.stato.setVisible(False)
        self._finito(not self._errori_log)

    def _avviso(self, testo: str) -> None:
        """Una riga con un problema: va nel log e nella lista degli errori.

        Va in **entrambi**: la lista e' quella che la schermata elenca e che si
        puo' salvare, e il log e' quello che va a schermo e su file.  Scriverne
        uno solo dei due lascerebbe mezzo della storia da un lato.

        NOTA: questa e' una riga **che il programma stesso ha scritto**, non un
        errore di Qt.  Non passa per `Messaggi` e quindi non blocca: un
        download che non riesce e' una cosa che il programma sa gestire — la
        dice, e va avanti con quello che ha.  Se un giorno un guasto di rete
        dovesse rendere il programma inutilizzabile, il posto giusto non e' qui
        ma e' sollevare l'eccezione: li' si blocca perche' e' vero che si e'
        rotto.
        """
        self._errori_log.append(testo)
        self.scrivi(f"[AVVISO] {testo}")

    # ------------------------------------------------------------------

    def _finito(self, ok: bool) -> None:
        """La schermata ha fatto il suo lavoro.

        UNA VOLTA SOLO
        -------------
        Il segnale esce una volta e basta, e il fermo sta qui dentro e non in
        chi chiama.  `_finito` puo' essere chiamata da due strade diverse —
        «non c'e' niente da aggiornare» e «l'ultimo catalogo e' arrivato» — e se
        arrivassero insieme l'utente vedrebbe comparire la finestra principale
        e, subito dopo, il programma chiudersi perche' la X e' stata premuta:
        una finestra che si apre e si richiude da sola sembra un crash.

        TRE USCITE, E OGNUNA DIVERSA
        -----------------------------
            bloccata   un errore ha fermato il programma: la schermata degli
                       errori e' gia' aperta e non si tocca niente
            con avvisi  ci sono problemi ma nessuno che fermi: si mostra la
                       schermata e si aspetta che l'utente prema «Ignora e
                       parti» o «Esci»
            pulita     tutto bene: parte la finestra principale

        LA LISTA SI CHIEDE A `Messaggi`, NON SI USA QUELLA DI QUI
        ---------------------------------------------------------
        `_errori_log` tiene solo quello che la schermata ha scritto lei — un
        download che non e' riuscito, un errore bloccante.  Gli avvisi di Qt
        passano da `Messaggi` e non arrivano qui, quindi controllare la lista
        locale darebbe «nessun problema» su un avvio pieno di avvisi, e la
        finestra principale si aprirebbe come se niente fosse.

        E' l'unico posto dove si rilegge `Messaggi`, e si rilegge **qui** e
        non all'avvio: un avviso puo' arrivare mentre la schermata sta
        scaricando i cataloghi, e leggerlo solo all'avvio significa non
        accorgersi di quelli.
        """
        if self._annullato or self._finito_emesso:
            return
        self._finito_emesso = True
        from Utility import Messaggi
        Messaggi.ripristina()
        self._termina_lascolto()

        if self._bloccata:
            # Un errore ha gia' aperto la schermata degli errori: qui non si
            # fa niente, e soprattutto non si parte.
            return

        problemi = Messaggi.problemi()
        if self._errori_log or problemi:
            self._errori_log = self._errori_log + [r for r in problemi
                                                   if r not in self._errori_log]
            self._mostra_errori(bloccante=False)
            return
        self.finito.emit(bool(ok), self._errori_log)

    def _salva_log(self) -> bool:
        """Salva il log in un file scelto dall'utente.  True se e' andato.

        SI SALVA TUTTO, NON SOLO GLI ERRORI
        ------------------------------------
        Il file prende **tutto** quello che c'e' nella schermata: gli errori,
        gli avvisi e le righe che li precedono.  Il motivo e' che in un crash
        la causa non e' quasi mai l'ultima riga: e' il modulo che non entra,
        la riga quattro prima, e se il file contiene solo «NameError: nome non
        trovato» senza il percorso che ci porta, non serve a niente.

        Il formato lo decide l'estensione che l'utente scrive, e non una
        domanda: `QFileDialog` mette gia' il filtro, e chiedere un'altra
        domanda significa due decisioni per una cosa sola.

        IL FORMATO JSON
        ---------------
        C'e' anche li', perche' e' quello che serve quando il log lo legge una
        macchina e non una persona.  Dentro ci sono i messaggi **coi livelli**,
        non come stringhe: il file JSON serve proprio per separare un errore
        da un avviso, e scriverli tutti uguali renderebbe il file inutile.
        """
        from datetime import datetime
        import json

        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        percorso, _ = QFileDialog.getSaveFileName(
            self, "Salva il log di avvio",
            f"jwlibrary_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Testo (*.txt);;JSON (*.json);;Tutti i files (*)")
        if not percorso:
            return False

        testo = self.terminale.toPlainText()
        adesso = datetime.now().isoformat(timespec="seconds")
        try:
            if percorso.lower().endswith(".json"):
                from Utility import Messaggi
                with open(percorso, "w", encoding="utf-8") as f:
                    json.dump({
                        "programma": "JW LibriX",
                        "avvio": adesso,
                        "messaggi": [{"riga": r, "livello": lv}
                                     for r, lv in Messaggi.ULTIMI_CON_LIVELLO],
                        "testo": testo,
                    }, f, indent=2, ensure_ascii=False)
            else:
                with open(percorso, "w", encoding="utf-8") as f:
                    f.write(f"JW LibriX — log di avvio — {adesso}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(testo)
                    f.write("\n\n")
                    f.write(f"{'=' * 60}\n")
                    f.write(f"Problemi rilevati: {len(self._errori_log)}\n\n")
                    for numero, riga in enumerate(self._errori_log, 1):
                        f.write(f"[{numero}] {riga}\n\n")
            return True
        except OSError as errore:
            QMessageBox.warning(self, "Non riesco a salvare il log",
                                f"{errore}\n\nIl programma resta fermo: "
                                f"prova un'altra cartella.")
            return False

    def mostra_toast(self, messaggio: str, tipo: str = "info",
                     durata_ms: int = 4000) -> None:
        """Le finestra principale non esiste ancora: qui un toast non ha dove andare."""
        self.scrivi(messaggio)
