#
#  SettingsView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""Le Impostazioni: quattro schede, una sotto l'altra.

LE SCHEDE E IL LORO ORDINE
--------------------------
    Generale            la lingua del catalogo
    Ascolto e video     qualita' e scarica automatica
    Spazio              quanto e' occupato, e quando e' stato aggiornato
    Aspetto             il tema

L'ordine non e' quello in cui si usano.  Prima quello che si cambia una
volta e non si tocca piu' (la lingua), poi quello tecnico, e per ultimo l'aspetto, che si cambia
quando qualcosa non piace e basta.

LE MISURE NON SONO UNDICATE
----------------------------
    la colonna          larga al massimo 620
    fra le schede       14
    la scheda           pannello, bordo 1, raggio 8, padding 12 14
    il titolo           12 px, grassetto 600, MAIUSCULE, spaziatura .4
    la riga             alto 5 sopra e sotto, etichetta a sinistra
    il valore           12 px, colore secondario, a destra

IL TITOLO MAIUSCULE E' UNA SCELTA, NON UN DIMENTICATO
-------------------------------------------------------
``text-transform: uppercase`` nella app precedente.  In Qt il foglio di
stile non ha quell'opzione: si scrive il titolo gia' maiuscolo e si tiene
la letteratura della parola, altrimenti "ascolto e video" diventa
"ASCOLTO E VIDEO" che e' diverso e meno leggibile.

LA DIMENSIONE DEL TESTO NON STA QUI
-----------------------------------
Sta nel menu in alto, dove serve mentre si legge.  Qui starebbe una
seconda copia di uno cursore che si puo' muovere da due posti, e le due
copie non possono stare d'accordo.
"""
from __future__ import annotations

from datetime import datetime
import json

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from Utility import Aggiornamenti, Messaggi, Plugin, Schermi, tema
from Utility.tema import AUTOMATICA

LARGHEZZA_COLONNA = 620


def riavvia_app() -> None:
    """Chiude l'app e la riapre.  Dentro un'AppImage riparte l'AppImage.

    La nuova parte quando questa e' GIA' uscita (`atexit`), non prima: al
    riavvio si possono spostare o copiare i database, e la vecchia non deve
    stare ancora scrivendoci dentro.
    """
    import atexit
    import os
    import subprocess
    import sys
    from PyQt6.QtWidgets import QApplication
    appimage = os.environ.get("APPIMAGE")
    comando = [appimage, *sys.argv[1:]] if appimage else [sys.executable, *sys.argv]
    atexit.register(lambda: subprocess.Popen(comando, start_new_session=True))
    QApplication.quit()


class _Scheda(QWidget):
    """Una scheda: il titolo e le righe sotto."""

    def __init__(self, titolo: str, padre=None) -> None:
        super().__init__(padre)
        # vedi tema.sfondo(): su un QWidget puro il foglio di stile non
        # disegna fondo ne' bordo senza questo attributo
        tema.sfondo(self, "scheda")
        self._disposizione = QVBoxLayout(self)
        self._disposizione.setContentsMargins(14, 12, 14, 12)
        self._disposizione.setSpacing(0)

        intestazione = QLabel(titolo.upper(), self)
        intestazione.setObjectName("titoloScheda")
        self._disposizione.addWidget(intestazione)
        self._disposizione.addSpacing(9)

    def aggiungi(self, cosa) -> None:
        """Mette una riga sotto il titolo."""
        self._disposizione.addWidget(cosa)

    def nota(self, testo: str) -> None:
        """La riga piccola in grigio sotto una riga."""
        riga = QLabel(testo, self)
        riga.setObjectName("nota")
        riga.setWordWrap(True)
        self._disposizione.addWidget(riga)


class _Riga(QWidget):
    """Una riga: l'etichetta a sinistra, il controllo a destra."""

    def __init__(self, etichetta: str, controllo=None, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("riga")
        disposizione = QHBoxLayout(self)
        disposizione.setContentsMargins(0, 5, 0, 5)
        disposizione.setSpacing(12)

        testo = QLabel(etichetta, self)
        testo.setObjectName("etichetta")
        testo.setWordWrap(True)
        disposizione.addWidget(testo, 1)
        if controllo is not None:
            disposizione.addWidget(controllo, 0)


class _Valore(QLabel):
    """Il valore a destra della riga: spazio usato, data.

    Figurato: sono numeri e devono stare in colonna.  In Qt il monospace si
    chiede col nome della famiglia, non con ``font-family: monospace``.
    """

    def __init__(self, testo: str = "…", padre=None) -> None:
        super().__init__(testo, padre)
        self.setObjectName("valore")
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class SettingsView(QWidget):
    """Le impostazioni."""

    messaggio = Signal(str)

    #: Un backup e' stato importato: la finestra rifa' le schermate.
    #: Porta il testo del riepilogo.
    backupImportato = Signal(str)

    #: La finestra lo ascolta e riapplica il tema.  Il tema non si cambia
    #: dentro la schermata che lo mostra: e' un'informazione che riguarda
    #: tutta l'app, quindi la legge chi ne e' responsabile, che e' la
    #: finestra.  Qui dentro si dice solo "e' cambiato".
    temaCambiato = Signal(bool)

    #: Lo schermo per video e figure e' cambiato.
    #:
    #: Come il tema, e' una cosa che riguarda tutta l'app e non la schermata
    #: che la mostra: la finestra secondaria e' sua, e va spostata.  Quindi
    #: anche qui dentro si dice solo «e' cambiato» e non si ricostruisce
    #: niente.
    #:
    #: Senza questo la scelta vale per il prossimo avvio: l'utente cambiava
    #: lo schermo, chiudeva il programma, lo riapriva, e intanto il video
    #: andava ancora sul vecchio.  Un'impostazione che si vede solo al
    #: prossimo avvio non e' un'impostazione, e' una nota.
    schermoCambiato = Signal()

    #: L'utente ha chiesto di aggiornare il catalogo **adesso**.
    #:
    #: Il catalogo — il database delle pubblicazioni — si aggiorna dalla
    #: Home e da qui, e da nessun'altra parte: il tasto della fascia, quando
    #: si legge, ricarica quello che si sta guardando e non scarica duecento
    #: megabyte di nascosto.  Qui dentro il pulsante e' esplicito, e la
    #: finestra e' quella che sa come si fa (il download, la barra, il
    #: riepilogo).
    catalogoRichiesto = Signal()

    #: Un plugin e' stato acceso o spento: la finestra mostra o toglie il tasto.
    pluginCambiati = Signal()
    _appControllata = Signal(str, str)
    _appAggiornata = Signal(str)
    _installFinita = Signal(str)   # '' = ok, altrimenti l'errore (arriva dal thread)


    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # DOVE STA' LA FINESTRA DEL PROGRAMMA
        # ---------------------------------
        # Lo schermo su cui sta questa finestra non si chiede ogni volta: si
        # chiede qui e basta.  Serve al menu della duplicazione, che su quello
        # schermo **non puo'** offrire la duplicazione — li' il video si vede
        # gia' nel player, e una finestra a tutto schermo sopra coprirebbe
        # l'applicazione.
        #
        # Se non si trova — la finestra non e' ancora su schermo — resta
        # `None` e il menu mostra uno schermo in piu' invece di uno in meno.
        # Meglio un'offerta in piu' che si vede subito e si corregge da sola,
        # che un'offerta mancante che l'utente cerca e non trova.
        self._schermo_dove_sta = Schermi.schermo_dove_sta(self)

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)

        pagina = QWidget()
        disposizione = QVBoxLayout(pagina)
        disposizione.setContentsMargins(18, 16, 18, 16)
        disposizione.setSpacing(0)
        disposizione.setAlignment(Qt.AlignmentFlag.AlignTop)

        titolo = QLabel("Impostazioni", pagina)
        titolo.setObjectName("titoloPagina")
        disposizione.addWidget(titolo)
        disposizione.addSpacing(14)

        colonna = tema.sfondo(QWidget(pagina))
        colonna.setFixedWidth(LARGHEZZA_COLONNA)
        colonna.setSizePolicy(QSizePolicy.Policy.Fixed,
                              QSizePolicy.Policy.Preferred)
        schede = QVBoxLayout(colonna)
        schede.setContentsMargins(0, 0, 0, 0)
        schede.setSpacing(14)

        schede.addWidget(self._generale())
        schede.addWidget(self._ascolto())
        schede.addWidget(self._backup())
        schede.addWidget(self._spazio())
        schede.addWidget(self._cartella_dati())
        schede.addWidget(self._aggiornamenti())
        schede.addWidget(self._log())
        schede.addWidget(self._aspetto())
        schede.addWidget(self._plugin())
        schede.addWidget(self._informazioni())
        schede.addStretch(1)

        # allineata a sinistra, non centrata: una colonna di impostazioni
        # si legge dall'alto in basso e sta dove la si aspetta.
        contenitore = QHBoxLayout()
        contenitore.addWidget(colonna)
        contenitore.addStretch(1)
        pagina_larga = QWidget()
        pagina_larga.setLayout(contenitore)
        disposizione.addWidget(pagina_larga)

        chiusura = QLabel(
            "Le impostazioni si ricordano in un file solo. "
            "Cio' che cambia l'app scrive li' per primo, quindi quello che "
            "vedi qui vale fino a quando non lo cambi.", pagina)
        chiusura.setObjectName("nota")
        chiusura.setWordWrap(True)
        disposizione.addWidget(chiusura)
        disposizione.addSpacing(16)

        area.setWidget(pagina)
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(area)

    # ------------------------------------------------------------------
    # LE SCHEDE
    # ------------------------------------------------------------------

    def _generale(self) -> _Scheda:
        scheda = _Scheda("Generale", self)

        # La lingua viene dall'elenco del catalogo se c'e', e non da una
        # lista scritta a mano: sono 1446 lingue e quelle scritte a mano
        # sbagliano.  Se il catalogo non c'e' resta solo l'italiano, che e'
        # l'unica lingua di cui siamo sicuri.
        lingue = self._lingue()
        scelta = QComboBox(self)
        for nome, codice in lingue:
            scelta.addItem(nome, codice)
        scelta.setCurrentIndex(max(0, self._indice(lingue, self._lingua_salvata())))
        scelta.currentIndexChanged.connect(self._lingua_cambiata)

        scheda.aggiungi(_Riga("Lingua", scelta, self))
        # "1 lingue disponibili" e' sbagliato.  Una sezione che scrive
        # male quello che promette fa perdere fiducia in tutto il resto.
        quante = len(lingue)
        scheda.nota(f"{quante} {'lingua disponibile' if quante == 1 else 'lingue disponibili'}. "
                    "I numeri non sono in ordine: 0 e' l'inglese, 4 l'italiano.")
        return scheda

    def _ascolto(self) -> _Scheda:
        scheda = _Scheda("Ascolto e video", self)

        qualita = QComboBox(self)
        # Le quattro voci sono "Automatica", "Bassa", "Media", "Alta", e i
        # valori sono le tre posizioni nella lista delle risoluzioni, non delle
        # risoluzioni: "bassa" vuol dire la piu' piccola **di quel video**.
        # Non si scrivono qui "240p" e "720p" perche' non ci sono in tutti i
        # video, e una risoluzione proposta e poi non disponibile e' una voce
        # che non funziona.  Vedi `Mediator.scegli_risoluzione`.
        for testo, valore in (("Automatica", AUTOMATICA), ("Bassa", "bassa"),
                              ("Media", "media"), ("Alta", "alta")):
            qualita.addItem(testo, valore)
        # `findData` e non l'indice: l'indice dipende dall'ordine in cui sono
        # state scritte le voci qui sopra, e se un domani ne arriva una nuova
        # l'indice punta a un'altra cosa senza che nessuno se ne accorga.
        # `findData` cerca il valore, che e' quello che si salva.
        posizione = qualita.findData(tema.risoluzione_video())
        qualita.setCurrentIndex(posizione if posizione >= 0 else 0)
        # `activated` e non `currentIndexChanged`: come per lo schermo, cosi'
        # riselezionare la stessa voce agisce.  Vedi `_schermo_video`.
        qualita.activated.connect(
            lambda riga: self._qualita_salvata(qualita.itemData(riga)))

        scarica = QCheckBox("", self)
        scarica.setText("")

        schermo = self._schermo_video()

        scheda.aggiungi(_Riga("Qualita' streaming", qualita, self))
        scheda.aggiungi(_Riga("Scarica automaticamente in Wi-Fi", scarica, self))
        scheda.aggiungi(_Riga("Schermo per video e immagini", schermo, self))
        # LA DUPLICAZIONE SUGLI ALTRI SCHERMI
        # -------------------------------------
        # Sta **sotto** la scelta dello schermo secondario, e non e' una riga
        # messa li' per caso: e' la continuazione di quella.  Il primo dice
        # «dove va il video», il secondo dice «e in che altri posti lo voglio
        # vedere».  Messe separate, lontane, sembrerebbero due impostazioni
        # senza relazione, e l'utente non saprebbe che una vale solo se
        # l'altra e' scelta.
        scheda.aggiungi(_Riga("Duplicazione monitor", self._duplica(), self))
        scheda.nota(self._nota_duplica())
        scheda.nota(self._nota_schermi())
        scheda.nota("La risoluzione si cambia anche dal lettore, col tasto "
                    "accanto a play: li' si vedono solo le risoluzioni di quel "
                    "video, e il cambio e' immediato.")
        return scheda

    def _qualita_salvata(self, valore) -> None:
        """La qualita' scelta nelle impostazioni la scrive il tema.

        ERA UNA COMBO CHE NON FACEVA NIENTE
        ------------------------------------
        La combo c'era, con le sue quattro voci, e non era collegata a niente:
        si poteva scegliere «Alta» e non succedeva niente, e non si accorgeva
        niente.  Ora la scelta si scrive nell'impostazione, che e' lo stesso
        posto dove la legge il tasto del lettore: cosi' i due posti non dicono
        due cose diverse.

        Il video che sta suonando **non** viene ricaricato.  Cambiare
        risoluzione vuol dire ripartire da capo, e farlo mentre si guarda,
        mentre l'utente sta cambiando un'impostazione in un'altra schermata,
        fermerebbe il video di botto.  La scelta vale dal prossimo video, e il
        tasto del lettore la usa subito quando la si preme li'.
        """
        if valore:
            tema.salva_risoluzione_video(str(valore))

    def _schermo_video(self):
        """La scelta dello schermo per video e immagini a tutto schermo.

        IL NOME VIENE DA Qt, E NON E' UN NUMERO
        -----------------------------------------
        Le voci sono gli schermi che il sistema sta adesso usando, con il
        nome che ha dato lui (`HDMI-A-1`, `DP-1`, …) e la misura.  Non si
        scrivono due schermi a mano perche' su un portatile uno dei due puo'
        non esserci, e su un desktop con tre non ci starebbero.

        Non si salva un indice perche' gli indici cambiano: staccando il
        secondo schermo, quello che era «2» diventa «1» e la finestra andrebbe
        a schermo intero sullo schermo sbagliato senza dire niente.  Il nome
        o c'e' o non c'e', e si puo' controllare: per questo e' il nome a
        essere salvato (`tema.video_schermo`).

        «Disattivato» e' la prima voce perche' e' il comportamento di
        sempre e quello che si vuole quando c'e' un solo schermo: con un
        monitor solo scegliere uno schermo preciso non avrebbe senso, e questa
        voce dice esattamente cosa succede — niente schermo esterno.

        «Principale» e «secondario» sono le parole del **sistema**, e si
        usano quelle: sono le stesse che l'utente ha gia' letto nelle
        impostazioni del sistema.  E non si aggiunge «dove sta la finestra»
        perche' quello cambierebbe l'ordine delle voci, e una voce che
        cambia posto mentre la si guarda fa scegliere la schermata sbagliata.
        Vedi la nota di `Schermi.elenco`.
        """
        scelta = QComboBox(self)
        # LA PRIMA VOCE: DISATTIVATO
        # ----------------------------
        # Dice cosa **succede**, non da dove parte.  Il nome di prima era
        # «Dove sta la finestra», che si poteva leggere come «il video va
        # dove sta la finestra» — cioe' sul primo schermo, dentro l'app — e
        # non e' quello che questa voce fa: qui il video **resta** dentro
        # l'app perche' il monitor esterno e' spento, non perche' vada li'.
        #
        # Quindi la voce si chiama «Disattivato», che e' una parola sola con un
        # significato solo: niente schermo esterno.
        scelta.addItem("Disattivato", tema.SEGUI)

        # Nell'ordine in cui li da' il sistema, senza spostare niente.
        for voce in Schermi.elenco():
            scelta.addItem(voce["etichetta"], voce["nome"])

        salvato = tema.video_schermo()
        indice = scelta.findData(salvato)
        if indice < 0:
            # Lo schermo salvato non c'e' piu': si mette «dove sta la
            # finestra», che e' la scelta che vale comunque, e la nota sotto
            # la riga lo dice.
            indice = 0
        scelta.setCurrentIndex(indice)
        # Si collega con una lambda che chiude sopra la scelta, e non con un
        # metodo che poi va a cercare «la combo giusta» fra tutte: la riga
        # della scheda puo' essere ricostruita e un metodo che cerca per
        # indice trova quello sbagliato.  Qui la combo e' quella giusta per
        # costruzione, quindi non c'e' niente da cercare.
        # Solo `activated`, e NON anche `currentIndexChanged`.
        #
        # `currentIndexChanged` parte solo quando il valore **cambia**: se
        # l'utente sceglie di nuovo lo stesso schermo — cioe' quello che e'
        # gia' salvato — non parte niente e la voce sembra morta.  Misurato:
        # era esattamente il caso che non funzionava.
        #
        # `activated` parte anche quando la voce scelta e' gia' quella attiva,
        # perche' racconta un gesto dell'utente e non un cambio di stato.
        #
        # E si collega **solo** lui: collegando entrambi, un cambio vero
        # farebbe partire due volte la ricostruzione della finestra a tutto
        # schermo, che si chiuderebbe e si riaprirebbe di fila — e si vedrebbe.
        scelta.activated.connect(self._schermo_video_cambiato)
        # Si tiene qui la combo, e non la si va a cercare fra tutte quando
        # serve: `findChildren` su una scheda con piu' tendine restituirebbe
        # la prima, non quella giusta, e il valore salvato sarebbe quello di
        # un'altra voce.
        self._combo_schermo = scelta
        return scelta

    def _duplica(self):
        """Il pulsante che apre il menu a spunte degli altri schermi.

        PERCHE' UN PULSANTE CON UN MENU E NON UNA COMBO
        -----------------------------------------------
        Perche' la risposta e' «**zero**, uno o tre schermi», e una tendina
        puo' dire solo **uno** di tre: scegliendo «HDMI-1» e poi «HDMI-2» la
        prima scelta verrebbe cancellata, mentre l'utente le voleva entrambe.

        Il menu a spunte e' l'unico modo con cui si risponde a una domanda
        con piu' di una risposta.  E in un `QComboBox` di Qt le caselle si
        possono mettere, ma non si vedono e non si spuntano come uno si
        aspetta: si apre la tendina, si vede il segno di spunta, e non si
        capisce come si sia fatto a cambiarla.  Un menu che si apre e ha
        dentro le caselle da spuntare e' esattamente quello che l'utente
        cerca con il mouse.

        PERCHE' IL PULSANTE SCRIVE QUANTO HA SPUNTATO
        ----------------------------------------------
        Il pulsante non e' una tendina: mostra una riga di testo.  Se
        dicesse sempre «Duplica anche su», non si saprebbe se qualcosa e'
        stato scelto, e una scelta invisibile e' una scelta che non esiste.
        Quindi mostra quante spunte ci sono: «Nessuno», «uno schermo», «3
        schermi», coi nomi dentro quando sono pochi e sono leggibili.

        CHI NON COMPARE NEL MENU, E PERCHE'
        ------------------------------------
        -  **Il secondo schermo**: nella riga sopra e' gia' scelto.  Spuntarlo
           qui non aggiungerebbe niente — la finestra su quello schermo c'e'
           gia' — e se comparisse non spuntato sembrerebbe che si possa
           spegnere da li'.

        -  **Lo schermo dove sta la finestra**: il video li' si vede gia',
           nel player.  Coprirlo con una finestra a tutto schermo metterebbe
           l'applicazione sotto, e chi sta leggendo una pubblicazione si
           ritrova a non poterla piu' toccare.

        L'ORDINE E' QUELLO DEL SISTEMA
        ------------------------------
        Le voci sono nell'ordine in cui il sistema elenca gli schermi, senza
        spostarne nessuna: e' lo stesso ordine che si vede nelle impostazioni
        del sistema operativo, ed e' quello in cui l'utente li riconosce.

        QUANDO E' SPENTO, E PERCHE'
        ---------------------------
        Senza un secondo schermo scelto non ha senso duplicare niente — «dove
        va il video» non e' definito, quindi non c'e' niente da copiare.  E
        senza altri schermi non ci sarebbe niente da spuntare.

        Spenta e **visibile**, pero': una riga che compare e scompare a ogni
        montaggio di monitor e' una riga che l'utente cerca e non trova, e
        per un attimo pensa di aver toccato qualcosa.  Stare li' grigia dice
        invece, in un colpo solo, «questa cosa dipende da quella di sopra».
        """
        from PyQt6.QtWidgets import QMenu

        pulsante = QPushButton(self)
        pulsante.setObjectName("pulsanteDuplica")
        pulsante.setEnabled(bool(self._schermi_da_duplicare()))

        def apri_menu() -> None:
            # Il menu si ricrea a ogni apertura.  Riciclarlo sembrerebbe
            # piu' leggero, ma le spunte cambiano quando l'utente cambia i
            # monitor e un menu riciclato mostra le spunte di prima: si
            # spunta una casella e la finestra non si apre, e sembra rotto.
            menu = QMenu(pulsante)
            for voce in self._schermi_da_duplicare():
                nome = voce["nome"]
                azione = menu.addAction(voce["etichetta"])
                azione.setCheckable(True)
                azione.setChecked(nome in tema.video_schermi_duplica())
                azione.toggled.connect(
                    lambda segnato, n=nome: self._duplica_toccato(n, segnato))
            if menu.isEmpty():
                azione = menu.addAction("Nessun altro schermo collegato")
                azione.setEnabled(False)
            menu.exec(pulsante.mapToGlobal(
                pulsante.rect().bottomLeft()))

        pulsante.clicked.connect(apri_menu)
        self._pulsante_duplica = pulsante
        pulsante.setText(self._testo_duplica())
        return pulsante

    def _testo_duplica(self) -> str:
        """Che cosa scrive il pulsante dei duplicati.

        UN PULSANTE CHE MENTE E' PEGGIO DI UN PULSANTE SPENTO
        ------------------------------------------------------
        Il pulsante mostra **quanti** schermi sono spuntati, non i nomi di
        tutti: con cinque schermi i nomi non ci stanno e diventerebbero una
        riga illeggibile.  Con uno o due invece i nomi si leggono, e sono
        molto piu' utili di «2 schermi».

        PERCHE' UN NOME E NON UN NUMERO SEGUITO DAI NOMI
        -----------------------------------------------
        «3 schermi: DP-3, DP-4, HDMI-1» e' piu' completo ma occupa tre righe
        in un pulsante che ne ha una sola, e il pulsante si allarga fino a
        spostare tutto quello che c'e' sotto.  Con i nomi da soli la riga
        resta corta e resta leggibile.

        UN SCHERMO STACCATO NON SI CONTA
        --------------------------------
        Se l'utente aveva spuntato `HDMI-1` e poi l'ha staccato, quel nome
        e' ancora salvato ma non c'e' piu' nessuno schermo con quel nome.
        Contarlo sarebbe dire «3 schermi» per due schermi reali, e
        l'utente cercherebbe il terzo.  Per questo si contano solo quelli
        che sono **collegati adesso**.
        """
        scelti = tema.video_schermi_duplica()
        vivi = [v["nome"] for v in self._schermi_da_duplicare()]
        numeri = [n for n in scelti if n in vivi]
        if not numeri:
            return "Nessuno"
        if len(numeri) == 1:
            return numeri[0]
        return ", ".join(numeri)

    def _schermi_da_duplicare(self) -> list:
        """Gli schermi che si possono spuntare, nell'ordine del sistema.

        SERVE UN MONITOR SCELTO, E SI VEDE
        ----------------------------------
        Il pulsante si accende solo se nella riga sopra c'e' un monitor
        **scelto**.  Con «Disattivato» resta grigio, e la riga sotto lo dice:
        prima di scegliere il primo schermo non c'e' niente da copiare.

        Qui prima funzionava anche senza scegliere niente, perche' il programma
        sceglieva da solo «l'altro schermo».  Adesso non lo fa piu' — e il
        pulsante grigio e' la conseguenza giusta: senza un monitor esterno
        acceso non c'e' niente da duplicare, e una spunta che non porta da
        nessuna parte e' una spunta che mente.

        PERCHE' UN DOPPIO SCREEN VA ESCLUSO
        ----------------------------------
        Il secondo schermo non si duplica: e' gia' scelto nella riga sopra,
        e la sua finestra c'e' gia'.  Spuntarlo qui non aggiungerebbe niente
        e sembrerebbe che si possa spegnere da li'.

        E' la stessa regola dei tre filtri di `Schermi.duplicati`, che e'
        il posto dove la decisione viene presa davvero: qui si **mostra**
        quello che si puo' scegliere, e non si decide niente.
        """
        if tema.video_schermo() == tema.SEGUI:
            # Nessun monitor esterno scelto: non c'e' niente da copiare.  Con
            # un monitor solo la domanda non si pone, e porla sarebbe una voce
            # grigia che l'utente cerca e non capisce.  Con piu' monitor ma
            # senza scelta e' la stessa cosa: il monitor esterno e' spento,
            # quindi non c'e' niente da duplicare.
            return []

        secondo = Schermi.secondario_per_video(self)
        # LO SCHERMO DELLA FINESTRA SI RILEGGE QUI, NON SOLO ALL'AVVIO
        # -----------------------------------------------------------
        # Il campo era impostato una volta sola, in `__init__`, e li' la
        # finestra delle impostazioni poteva non essere ancora su schermo:
        # `_schermo_dove_sta` rispondeva `None`, e senza risposta il monitor
        # dove sta la finestra finiva fra i duplicabili.  E' il difetto
        # segnalato: nel menu c'era anche il primo schermo.
        #
        # Il menu si costruisce quando l'utente **apre** le impostazioni, e
        # in quel momento la finestra e' gia' stata spostata dove sta: e'
        # quindi il momento giusto per chiedere, ed e' il posto giusto perche'
        # e' l'unica volta in cui la risposta conta davvero.
        da_chiudere = Schermi.schermo_dove_sta(self) or self._schermo_dove_sta
        # `_schermo_dove_sta` e' un `QScreen` e le voci dell'elenco hanno il
        # **nome**: confrontare le due cose cosi' com'e' non trova mai niente,
        # e lo schermo della finestra compariva fra i duplicabili — che e'
        # esattamente il caso da cui ci si voleva tenere lontani.
        nome_finestra = da_chiudere.name() if da_chiudere is not None else None

        fuori = []
        for voce in Schermi.elenco():
            nome = voce["nome"]
            if secondo is not None and nome == secondo.name():
                continue                       # gia' scelto nella riga sopra
            if nome_finestra is not None and nome == nome_finestra:
                continue                       # li' il video non va: e' l'app
            fuori.append(voce)
        return fuori

    def _duplica_toccato(self, nome: str, segnato: bool) -> None:
        """Una casella e' stata spuntata o tolta: si salva e si avvisa.

        Si salva **prima** di avvisare, per la stessa ragione della riga
        sopra: se la finestra ricostruisse le schermi leggendo il file mentre
        la scrittura non e' ancora passata, rileverebbe la lista vecchia e
        l'utente vedrebbe la casella spuntata senza effetto — e penserebbe
        che sia rotta.  Vedi `_schermo_video_cambiato`.

        IL PULSANTE SI RILEGGE
        ----------------------
        Dopo aver salvato il testo del pulsante viene ricalcolato: mostra
        quanti schermi sono spuntati, quindi senza questo resta fermo su
        «Nessuno» mentre le casunte sono spuntate — e un pulsante che mente
        e' peggio di un pulsante spento.
        """
        scelti = list(tema.video_schermi_duplica())
        if segnato and nome not in scelti:
            scelti.append(nome)
        elif not segnato and nome in scelti:
            scelti.remove(nome)
        tema.salva_video_schermi_duplica(scelti)
        pulsante = getattr(self, "_pulsante_duplica", None)
        if pulsante is not None:
            pulsante.setText(self._testo_duplica())
        self.schermoCambiato.emit()

    def _schermo_video_cambiato(self) -> None:
        """Salva lo schermo scelto e dice alla finestra che e' cambiato.

        Il segnale parte **dopo** la scrittura, e l'ordine conta: se la
        finestra ricostruisse lo schermo secondario leggendo il file mentre la
        scrittura non e' ancora passata, rileverebbe il valore vecchio e
        sposterebbe la finestra sullo schermo di prima — e sembrerebbe che
        l'opzione non abbia fatto niente.
        """
        scelta = getattr(self, "_combo_schermo", None)
        if scelta is None:
            return
        tema.salva_video_schermo(str(scelta.currentData() or tema.SEGUI))
        # IL PULSANTE DEI DUPLICATI SI RICARICA ANCHE LUI
        # -------------------------------------------------
        # Cambiando il secondo schermo cambia **quali** schermi si possono
        # duplicare: il nuovo secondo esce dalla lista, e lo schermo che era
        # secondo rientra come duplicabile.  Senza questo, il pulsante
        # offrirebbe uno schermo che adesso e' il secondo — e l'utente
        # spunterebbe una casella che non serve.
        self._ricarica_i_duplicati()
        self.schermoCambiato.emit()

    def _ricarica_i_duplicati(self) -> None:
        """Rilegge il pulsante dei duplicati dopo che il secondo e' cambiato.

        Il pulsante non viene ricostruito — verrebbe perso il collegamento con
        il menu — ma si aggiornano il testo e lo stato spento/acceso, che
        dipendono entrambi dal secondo schermo scelto.
        """
        pulsante = getattr(self, "_pulsante_duplica", None)
        if pulsante is None:
            return
        pulsante.setEnabled(bool(self._schermi_da_duplicare()))
        pulsante.setText(self._testo_duplica())

    def _nota_duplica(self) -> str:
        """La riga che spiega la duplicazione sotto le tendine degli schermi.

        Dice le tre cose che l'utente non puo' indovinare: che il video va
        sul monitor **esterno** e non sul primo, che i duplicati scelti qui si
        aggiungono al secondo schermo e non lo sostituiscono, e che senza
        spunte si e' come prima — cioe' solo il secondo schermo.
        """
        vivi = self._schermi_da_duplicare()
        if not vivi:
            return ("Prima scegli il monitor esterno qui sopra: se e' "
                    "«Disattivato» non c'e' niente da copiare, perche' il "
                    "video resta dentro l'applicazione.")
        return ("Il video va sul monitor esterno, non sul primo: quello dove "
                "sta la finestra resta per l'applicazione. Quello che spunti "
                "qui ci mette una copia in piu'. Senza spunte e' come prima: "
                "solo il secondo schermo.")

    def _nota_schermi(self) -> str:
        """La riga che dice che cosa succede con lo schermo scelto qui sopra.

        TRE CASI, TRE FRASI DIVERSE
        ---------------------------
        Una frase sola per tutti i casi non serve a niente: quello che
        l'utente deve capire leggendo questa riga e' **dove finisce il video**,
        e la risposta e' diversa a seconda della scelta.

        - **un solo schermo**: non c'e' niente da scegliere, il video resta
          nell'app.  Meglio dirlo che lasciare una tendina con una voce sola.

        - **disattivato**: scelta esplicita dell'utente, il video resta
          nell'app.  Qui la frase e' importante perche' «disattivato» puo'
          voler dire due cose — «non voglio il video fuori» oppure «non
          funziona» — e l'utente deve sapere che e' la prima.

        - **uno schermo scelto**: il video va li'.  E si dice anche che i
          comandi restano nella finestra del programma, che e' la cosa che
          l'utente cerca di sapere quando vede il video su un altro monitor
          e non vede play ne' pausa da nessuna parte.
        """
        from PyQt6.QtGui import QGuiApplication

        quanti = len(QGuiApplication.screens())
        scelto = tema.video_schermo()

        if quanti < 2:
            return ("C'e' un solo schermo: il video resta dentro "
                    "l'applicazione, come prima.")
        if scelto == tema.SEGUI:
            return ("Disattivato: nessun monitor esterno. Il video resta "
                    "dentro l'applicazione, sullo schermo dove sta la "
                    "finestra — e li' la finestra continua a vedersi "
                    "come si deve.")
        return ("Il video va su " + scelto + ". I comandi restano nella "
                "finestra del programma: uscendo dalla sezione, o cambiando "
                "video, quello schermo torna come era.")


    def _backup(self) -> _Scheda:
        """Importare, esportare e condividere il backup (.jwlibrary).

        Il file e' quello di JW Library su Android, Windows, iOS e iPadOS: il
        nome lo decide il formato (data e dispositivo), non si sceglie.
        """
        scheda = _Scheda("Backup", self)

        importa = QPushButton("Importa\u2026", self)
        importa.clicked.connect(self._importa_backup)
        scheda.aggiungi(_Riga("Importa un backup (.jwlibrary)", importa, self))

        esporta = QPushButton("Esporta\u2026", self)
        esporta.clicked.connect(self._esporta_backup)
        scheda.aggiungi(_Riga("Esporta in una cartella a tua scelta", esporta, self))

        condividi = QPushButton("Condividi\u2026", self)
        self._menu_condividi = QMenu(self)
        self._menu_condividi.aboutToShow.connect(self._riempi_menu_condividi)
        condividi.setMenu(self._menu_condividi)
        scheda.aggiungi(_Riga("Condividi il backup", condividi, self))

        from SubViews import BackupIniziale
        domanda = QCheckBox("Chiedi se importare il backup all'avvio", self)
        domanda.setChecked(not BackupIniziale.nascosto())
        domanda.toggled.connect(lambda attivo: BackupIniziale.imposta_nascosto(not attivo))
        scheda.aggiungi(_Riga("", domanda, self))

        from Utility.UserData import StatoBackup
        elimina_dopo = QCheckBox("Dopo l'invio al telefono, elimina il file dal computer", self)
        elimina_dopo.setChecked(StatoBackup.elimina_dopo_invio())
        elimina_dopo.toggled.connect(StatoBackup.imposta_elimina_dopo_invio)
        scheda.aggiungi(_Riga("", elimina_dopo, self))

        elimina = QPushButton("Elimina\u2026", self)
        elimina.clicked.connect(self._elimina_backup)
        scheda.aggiungi(_Riga("Elimina il backup creato dal computer", elimina, self))

        scheda.nota("Il backup contiene preferiti, segnalibri, sottolineature e appunti. "
                    "Non contiene le pubblicazioni scaricate ne' le impostazioni. "
                    "Importando si sostituiscono i dati attuali (ne resta una copia in "
                    "userData/prima-dell-import). Le playlist non passano dal backup. "
                    "Ogni nuovo backup sostituisce il precedente, che viene eliminato.")
        return scheda

    def _elimina_backup(self) -> None:
        """Elimina i file di backup creati dall'app, dopo una conferma."""
        from SubViews.Conferma import ConfermaApp
        from Utility.UserData import StatoBackup
        ricordati = StatoBackup.ricordati()
        if not ricordati:
            self.messaggio.emit("Non c'e' nessun backup creato da eliminare")
            return
        if not any(p.is_file() for p in ricordati):
            StatoBackup.elimina_tutti()
            self.messaggio.emit("Non posso eliminarlo: il file non c'e' piu', "
                                "l'hai gia' eliminato a mano")
            return
        elenco = "\n".join(str(p) for p in ricordati if p.is_file())

        def elimina() -> None:
            eliminati, mancanti = StatoBackup.elimina_tutti()
            if eliminati and mancanti:
                self.messaggio.emit("Backup eliminato; un altro file non c'era piu' (eliminato a mano)")
            elif eliminati:
                self.messaggio.emit("Backup eliminato dal computer")
            else:
                self.messaggio.emit("Non posso eliminarlo: il file non c'e' piu'")

        ConfermaApp.chiedi(self.window(), "Eliminare il backup?",
                           f"Elimino dal computer:\n{elenco}\n\nI dati nell'app non cambiano.",
                           "Elimina", elimina)

    def _importa_backup(self) -> None:
        from Utility.UserData.BackupManager import BackupManager

        def fine(riepilogo, errore):
            if riepilogo:
                self.backupImportato.emit(BackupManager.testo_riepilogo(riepilogo))
        BackupManager.restore_backup(parent=self, su_fine=fine)

    def _esporta_backup(self) -> None:
        from Utility.UserData.BackupManager import BackupManager

        def fine(percorso, errore):
            if percorso:
                self.messaggio.emit(f"Backup salvato in {percorso}")
        BackupManager.create_backup(parent=self, su_fine=fine)

    def _riempi_menu_condividi(self) -> None:
        import shutil
        import subprocess
        menu = self._menu_condividi
        menu.clear()

        menu.addAction("Copia il file negli appunti").triggered.connect(self._copia_backup)
        menu.addAction("Mostra il file nella cartella").triggered.connect(self._apri_cartella_backup)
        menu.addSeparator()

        if shutil.which("kdeconnect-cli"):
            dispositivi = []
            try:
                fuori = subprocess.run(["kdeconnect-cli", "-a", "--id-name-only"],
                                       capture_output=True, text=True, timeout=5).stdout
                for riga in fuori.splitlines():
                    if " " in riga.strip():
                        id_, nome = riga.strip().split(" ", 1)
                        dispositivi.append((id_, nome.strip()))
            except (OSError, subprocess.SubprocessError):
                pass
            if dispositivi:
                for id_, nome in dispositivi:
                    menu.addAction(f"KDE Connect \u2192 {nome}").triggered.connect(
                        lambda _=False, i=id_, n=nome: self._invia_kde(i, n))
            else:
                menu.addAction("KDE Connect: nessun dispositivo raggiungibile").setEnabled(False)

        from Utility import BluetoothInvio
        if BluetoothInvio.disponibile():
            telefoni = BluetoothInvio.dispositivi()
            if telefoni:
                for indirizzo, nome in telefoni:
                    menu.addAction(f"Bluetooth \u2192 {nome}").triggered.connect(
                        lambda _=False, i=indirizzo, n=nome: self._invia_bluetooth_a(i, n))
            else:
                menu.addAction("Bluetooth: nessun telefono associato").setEnabled(False)
        else:
            # Senza il servizio OBEX di BlueZ, se c'e' un programma di invio del
            # desktop lo si usa; altrimenti il Bluetooth non si nomina.
            for programma in ("bluedevil-sendfile", "blueman-sendto", "bluetooth-sendto"):
                if shutil.which(programma):
                    menu.addAction("Bluetooth\u2026").triggered.connect(
                        lambda _=False, p=programma: self._invia_bluetooth(p))
                    break

    def _prepara_per_condividere(self, poi) -> None:
        """Scrive il backup da condividere (con la barra) e poi chiama ``poi(file)``."""
        from Utility.UserData.BackupManager import BackupManager

        def fine(file, errore):
            if file is not None:
                poi(file)
        BackupManager.crea_per_condividere(parent=self, su_fine=fine)

    def _invia_kde(self, id_: str, nome: str) -> None:
        from Utility import InvioKde
        from Utility.UserData.BackupManager import BackupManager
        BackupManager.condividi(
            self, "Invio il backup", lambda file, avanza: InvioKde.invia(file, id_, nome, avanza),
            self._fine_invio)

    def _invia_bluetooth_a(self, indirizzo: str, nome: str) -> None:
        """Manda il backup a un telefono associato, via BlueZ (OBEX)."""
        from Utility import BluetoothInvio
        from Utility.UserData.BackupManager import BackupManager
        BackupManager.condividi(
            self, "Invio il backup",
            lambda file, avanza: BluetoothInvio.invia(indirizzo, file, avanza),
            self._fine_invio)

    def _fine_invio(self, messaggio, errore) -> None:
        # gli errori li mostra gia' la barra, con il pulsante Chiudi
        if errore is None and messaggio:
            self.messaggio.emit(messaggio)

    def _invia_bluetooth(self, programma: str) -> None:
        def invia(file):
            import subprocess
            try:
                comando = [programma, "-f", str(file)] if programma == "bluedevil-sendfile" \
                    else [programma, str(file)]
                subprocess.Popen(comando)
            except OSError as errore:
                self.messaggio.emit(f"Bluetooth non disponibile: {errore}")
        self._prepara_per_condividere(invia)

    def _copia_backup(self) -> None:
        def copia(file):
            from PyQt6.QtCore import QMimeData, QUrl
            from PyQt6.QtWidgets import QApplication
            dati = QMimeData()
            dati.setUrls([QUrl.fromLocalFile(str(file))])
            dati.setText(str(file))
            QApplication.clipboard().setMimeData(dati)
            self.messaggio.emit("File del backup copiato negli appunti: incollalo dove vuoi")
        self._prepara_per_condividere(copia)

    def _apri_cartella_backup(self) -> None:
        def apri(file):
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file.parent)))
        self._prepara_per_condividere(apri)

    def _spazio(self) -> _Scheda:
        scheda = _Scheda("Spazio", self)
        scheda.aggiungi(_Riga("Usato", _Valore(self._spazio_usato(), self), self))
        scheda.aggiungi(_Riga("Ultimo aggiornamento",
                              _Valore(self._ultimo(), self), self))
        scheda.nota("I valori si riempiono quando la finestra chiede i "
                    "dati al server.")
        return scheda

    def _aggiornamenti(self) -> _Scheda:
        """Aggiornamenti automatici o manuali.

        UN INTERRUTTORE PER DUE DOMANDE
        --------------------------------
        La casella comanda il lavoro automatico all'apertura, e quel lavoro
        sono due domande diverse al server:

            il catalogo e' piu' nuovo?      e se si', lo prende
            un pacchetto e' cambiato?      e quali mi mancano

        Sono in una casella sola perche' una sola domanda all'utente e non
        due, e perche' accenderne una senza l'altra non ha senso: nessuno
        vuole un catalogo nuovo con dentro l'elenco delle pubblicazioni di
        tre settimane fa.

        IL PREDEFINITO E' MANUALE, E NON E' UNA SCELTA NEUTRA
        -----------------------------------------------------
        UN INTERRUTTORE, DUE EFFETTI, E NON UNA CASELLA DI PIU'
        -----------------------------------------------------
        La casella si chiama «Offline» perche' e' la domanda che l'utente si
        fa davvero: «adesso posso andare in rete?».  Un «modalita' offline» e
        un «aggiornamenti automatici» separati sarebbero due interruttori per
        la stessa domanda, e possono trovarsi in due stati che si
        contraddicono — «controlla da solo all'avvio: si», ma «modalita'
        offline: si» — e in quel caso non si sa quale dei due vale.

        Percio' qui dentro c'e' **un interruttore solo**, e quando e' acceso
        succedono due cose che prima erano due scelte:

            all'avvio il programma controlla e prende il catalogo nuovo
            premere una card del catalogo la scarica

        Spento, il programma non chiede niente a nessuno: ne' all'avvio, ne'
        quando l'utente preme una card che non ha ancora.

        PERCHE' IL PREDEFINITO E' SPENTO, E NON E' UNA SCELTA NEUTRA
        -----------------------------------------------------------
        Un download che parte senza che nessuno l'abbia chiesto consuma
        traffico e, su una linea che non regge, lascia file parziali dove
        l'app li cerca come se fossero interi.  Per questo la casella parte
        spenta e accenderla e' una scelta.

        IL DOWNLOAD CHIESTO CON IL DITTO ESISTE SEMPRE
        ------------------------------------------------
        La nuvoletta sulla card e' un bottone con scritto «scarica»: premere
        un bottone con scritto «scarica» e' gia' dire «voglio scaricare»,
        e quel gesto non viene negato da un interruttore.  L'interruttore
        riguarda quello che il programma farebbe **per conto suo** — il clic
        su una card e' un gesto che puo' voler dire tre cose diverse, e in
        modalita' offline non si puo' scegliere per l'utente.

        Non c'e' un pulsante "scarica tutto" da nessuna parte, per
        principio: una riga sola puo' volerla e le altre no.
        """
        scheda = _Scheda("Aggiornamenti", self)

        # LA CASELA E' AL ROVESCIO DEL VALORE SALVATO
        # ------------------------------------------
        # Il file si chiama «aggiornamenti_automatici» e vale `True` quando il
        # programma PUO' andare in rete.  La casella si chiama «Offline» e
        # quando e' accesa il programma NON ci va.  Sono la stessa cosa detta
        # al contrario, e senza questo ribaltamento una casella accesa
        # significa offline mentre il file dice online: l'utente accende
        # «Offline», vede la spunta, e il programma continua a scaricare.
        #
        # Il ribaltamento e' qui, in un posto solo, e non nei due metodi che
        # scrivono e leggono: rifarlo li' doppio vuol dire che i due posti
        # possono dimenticarsene uno.
        offline = QCheckBox("", self)
        offline.setChecked(not Aggiornamenti.automatici())
        offline.stateChanged.connect(self._offline_cambiata)

        scheda.aggiungi(_Riga("Offline", offline, self))

        # L'AGGIORNAMENTO DEL CATALOGO, ADESSO
        # --------------------------------------
        # Il catalogo e' il database delle pubblicazioni: sono circa 210
        # megabyte, e senza un catalogo nuovo le pubblicazioni appena uscite
        # semplicemente non esistono.
        #
        # Si aggiorna da qui e dalla Home, e da nessun'altra parte: il tasto
        # dell'aggiornamento nella fascia, quando si sta leggendo un capitolo,
        # ricarica il capitolo e non scarica niente.  Un pulsante che
        # scarica duecento megabyte mentre si legge e' una cosa che l'utente
        # non ha chiesto in quel momento.
        adesso = QPushButton("Aggiorna il catalogo adesso", self)
        adesso.clicked.connect(self.catalogoRichiesto.emit)
        scheda.aggiungi(_Riga("Catalogo", adesso, self))
        scheda.nota(
            "Controlla se il server ha un catalogo piu' nuovo e, se sì, lo "
            "prende. Sono circa 210 megabyte.")

        scheda.nota(
            "Spento: all'avvio il programma non chiede niente a nessuno, e "
            "premere una card del catalogo scarica quella pubblicazione.")
        scheda.nota(
            "Acceso: modalità offline. All'avvio non si controlla nulla, e "
            "una card del catalogo non si scarica con un clic. Quello che "
            "hai già scaricato si apre e si legge come sempre.")
        scheda.nota(
            "La nuvoletta sulla card scarica anche in modalità offline: un "
            "bottone con scritto «scarica» è già un richiesta, e non è il "
            "programma a deciderlo al posto tuo.")
        scheda.nota(
            "Il catalogo è l'elenco di tutto quello che si può scaricare: "
            "se non si aggiorna, le pubblicazioni nuove semplicemente "
            "non ci sono. Sono circa 210 megabyte.")
        return scheda

    def _log(self) -> _Scheda:
        """Visualizza e salva il log di avvio."""
        scheda = _Scheda("Log", self)

        scheda.nota(
            "Qui trovi gli errori e avvisi dell'ultimo avvio. "
            "Se l'app ha mostrato errori all'avvio puoi rivederli o salvarli.")

        # Pulsante per visualizzare il log
        btn_visualizza = QPushButton("Visualizza log", self)
        btn_visualizza.clicked.connect(self._visualizza_log)
        scheda.aggiungi(_Riga("Log avvio", btn_visualizza, self))

        # Pulsante per salvare il log
        btn_salva = QPushButton("Salva log...", self)
        btn_salva.clicked.connect(self._salva_log_impostazioni)
        scheda.aggiungi(_Riga("Salva log", btn_salva, self))

        return scheda

    def _visualizza_log(self) -> None:
        """Mostra il log in un dialog."""
        from PyQt6.QtWidgets import QMessageBox, QTextEdit
        from Utility import Messaggi

        # Recupera il log: chiama la funzione se è callable, altrimenti usa l'attributo
        ultimo_log = getattr(Messaggi, "ultimo_log", None)
        if callable(ultimo_log):
            log_testo = ultimo_log()
        else:
            log_testo = ultimo_log or "Nessun log disponibile."
        
        if not log_testo or log_testo == "Nessun log disponibile.":
            # Prova a leggere dal file di log se esiste
            try:
                from Utility.Extensions.Ext_FileManager import get_documents_directory
                log_file = get_documents_directory() / "userData" / "jwlibrary.log"
                if log_file.is_file():
                    log_testo = log_file.read_text(encoding="utf-8")
            except Exception:
                pass

        msg = QMessageBox(self)
        msg.setWindowTitle("Log di avvio")
        msg.setIcon(QMessageBox.Icon.Information)

        dettaglio = QTextEdit()
        dettaglio.setReadOnly(True)
        dettaglio.setPlainText(log_testo)
        dettaglio.setMinimumSize(600, 400)
        dettaglio.setStyleSheet("font-family: monospace; font-size: 11px;")
        msg.setText("Log di avvio (ultimi errori/avvisi):")
        msg.setDetailedText(log_testo)
        msg.setStandardButtons(QMessageBox.StandardButton.Close)
        msg.exec()

    def _salva_log_impostazioni(self) -> None:
        """Salva il log su file (da Impostazioni)."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime
        import json
        from Utility import Messaggi

        ultimo_log = getattr(Messaggi, "ultimo_log", None)
        if callable(ultimo_log):
            log_testo = ultimo_log()
        else:
            log_testo = ultimo_log or ""
        
        if not log_testo:
            try:
                from Utility.Extensions.Ext_FileManager import get_documents_directory
                log_file = get_documents_directory() / "userData" / "jwlibrary.log"
                if log_file.is_file():
                    log_testo = log_file.read_text(encoding="utf-8")
            except Exception:
                log_testo = "Nessun log disponibile."

        percorso, _ = QFileDialog.getSaveFileName(
            self, "Salva log", 
            f"jwlibrary_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Testo (*.txt);;JSON (*.json);;Tutti i file (*)")
        if not percorso:
            return
        try:
            if percorso.endswith(".json"):
                with open(percorso, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "log": log_testo
                    }, f, indent=2, ensure_ascii=False)
            else:
                with open(percorso, "w", encoding="utf-8") as f:
                    f.write(f"JW LibriX Log - {datetime.now().isoformat()}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(log_testo)
            self.mostra_toast(f"Log salvato in: {percorso}", "success", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Non riesco a salvare: {e}")

    def _offline_cambiata(self, stato: int = 0) -> None:
        """La casella Offline si e' mossa: la scelta si scrive subito.

        SI SCRIVE SUBITO, E NON ALL'USCITA
        ----------------------------------
        Se il programma viene chiuso in modo improvviso la scelta deve essere
        gia' dentro, altrimenti l'utente crede di averla cambiata e riapre
        l'app con la vecchia — e una casella che mostra una cosa e ne fa
        un'altra e' peggio di una casella che non c'e'.

        LA CASELLA E' AL ROVESCIO DEL FILE
        -----------------------------------
        La casella si chiama «Offline»: accesa vuol dire che il programma NON
        va in rete.  Il file si chiama «aggiornamenti_automatici» e vuol dire
        che il programma PUO' andare in rete.  Percio' quello che si scrive e'
        il contrario di quello che e' acceso.

        IL SEGNALE E' UN NUMERO DI Qt, NON UN SI' O UN NO
        -------------------------------------------------
        `stateChanged` manda lo stato del tasto: `0` spento, `2` acceso.  Il
        valore arriverebbe a schermo come `2` nella casella, che al prossimo
        avvio si leggerebbe come accesa anche se l'utente l'aveva spenta — e
        non si saprebbe piu' tornare indietro senza aprire le impostazioni a
        mano.  Percio' si passa da `bool(stato)`.

        Questo metodo sostituisce quello di prima, che andava a cercare la
        casella per il testo della riga.  Non serve piu': la casella e' gia'
        collegata qui, e cercarla fra le righe per nome significava che
        cambiando una parola dell'etichetta il salvataggio smetteva di
        funzionare senza dare nessun errore.
        """
        Aggiornamenti.salva_automatici(not bool(stato))

    def _aspetto(self) -> _Scheda:
        scheda = _Scheda("Aspetto", self)

        scelta = QComboBox(self)
        scelta.addItem("Chiaro", True)
        scelta.addItem("Scuro", False)
        scelta.setCurrentIndex(0 if tema.tema_salvato() else 1)
        # Non si scrive il file da qui: la finestra lo fa, perche' e' lei
        # che deve riapplicare il foglio di stile a tutta l'app.
        scelta.currentIndexChanged.connect(
            lambda: self.temaCambiato.emit(bool(scelta.currentData())))

        scheda.aggiungi(_Riga("Tema", scelta, self))
        scheda.nota("La scelta vale per tutta l'app e viene ricordata. "
                    "Il viola non cambia mai: e' lo stesso in chiaro e in scuro.")
        # LA DIMENSIONE DEL TESTO STA IN ALTO, NON QUI
        # -------------------------------------------------
        # Il comando e' nella fascia viola, nei tre puntini a destra: li' si
        # vede subito mentre si legge, che e' quando serve.  Qui si dice solo
        # dove si trova, perche' una cosa che si cerca e non si trova e' come
        # una cosa che non c'e'.
        scheda.nota("La dimensione del testo si cambia dai tre puntini in "
                    "alto, nella barra viola: vale per gli articoli, per la "
                    "Bibbia e per le pubblicazioni, e viene ricordata.")
        return scheda

    # ------------------------------------------------------------------
    # LA CARTELLA DATI
    # ------------------------------------------------------------------

    def _cartella_dati(self) -> _Scheda:
        """Dove l'app salva tutto: si vede, si cambia, si importa, si cancella.

        Ogni cambio vale dal prossimo avvio: i database sono aperti, e la
        copia la fa l'avvio prima di aprirli (vedi `Paths`).
        """
        from Utility.Structures import Paths as modulo_paths
        from Utility.Structures.Paths import Paths

        scheda = _Scheda("Cartella dati", self)

        attuale = _Valore(str(Paths.root), self)
        attuale.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        attuale.setWordWrap(True)
        scheda.aggiungi(_Riga("Cartella attuale", attuale, self))

        apri = QPushButton("Apri", self)
        apri.clicked.connect(self._apri_cartella_dati)
        scheda.aggiungi(_Riga("Mostra nel gestore file", apri, self))

        if modulo_paths.da_variabile():
            scheda.nota("La cartella e' decisa dalla variabile JWL_HOME: per "
                        "cambiarla togli la variabile e riavvia.")
            return scheda

        cambia = QPushButton("Cambia\u2026", self)
        cambia.clicked.connect(self._cambia_cartella_dati)
        scheda.aggiungi(_Riga("Usa un'altra cartella (anche su un altro disco)", cambia, self))

        predefinita = QPushButton("Ripristina", self)
        predefinita.setEnabled(modulo_paths.cartella_scelta() is not None)
        predefinita.clicked.connect(self._cartella_predefinita)
        scheda.aggiungi(_Riga("Torna alla cartella predefinita", predefinita, self))

        importa = QPushButton("Importa\u2026", self)
        importa.clicked.connect(self._importa_cartella_dati)
        scheda.aggiungi(_Riga("Importa i dati da un'altra cartella", importa, self))

        elimina = QPushButton("Elimina\u2026", self)
        elimina.clicked.connect(self._elimina_dati_app)
        scheda.aggiungi(_Riga("Elimina tutti i dati dell'app", elimina, self))

        scheda.nota(f"Predefinita: {modulo_paths.PREDEFINITA}. Qui stanno "
                    "catalogo, pubblicazioni, video, audio, note, impostazioni "
                    "e plugin, e restano anche quando l'app si chiude o si "
                    "aggiorna. Ogni cambio vale dopo il riavvio.")
        return scheda

    def _apri_cartella_dati(self) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from Utility.Structures.Paths import Paths
        Paths.root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Paths.root)))

    def _scegli_cartella(self, titolo: str):
        from pathlib import Path
        scelta = QFileDialog.getExistingDirectory(self, titolo, str(Path.home()))
        return Path(scelta) if scelta else None

    def _cambia_cartella_dati(self) -> None:
        from Utility.Structures import Paths as modulo_paths
        from Utility.Structures.Paths import Paths

        nuova = self._scegli_cartella("Scegli la nuova cartella dati")
        if nuova is None:
            return
        # Una cartella qualsiasi (la home, Documenti) si riempirebbe di file
        # dell'app: se non e' vuota e non e' gia' una cartella dati, si usa
        # una sottocartella JW-LibriX dentro.
        if (nuova.exists() and any(nuova.iterdir())
                and not (nuova / "userData").is_dir()):
            nuova = nuova / modulo_paths.NOME_APP
        if nuova.resolve() == Paths.root.resolve():
            self.messaggio.emit("E' gia' la cartella attuale")
            return
        try:
            nuova.mkdir(parents=True, exist_ok=True)
            prova = nuova / ".prova_scrittura"
            prova.write_text("ok")
            prova.unlink()
        except OSError as errore:
            QMessageBox.warning(self, "Cartella dati",
                                f"Non posso scrivere in {nuova}:\n{errore}")
            return

        domanda = QMessageBox(self)
        domanda.setWindowTitle("Cartella dati")
        domanda.setText(f"Nuova cartella dati:\n{nuova}")
        domanda.setInformativeText(
            "Copio i dati attuali nella nuova cartella? La vecchia cartella "
            "resta com'e': quando hai controllato puoi cancellarla tu.")
        copia = domanda.addButton("Copia i dati", QMessageBox.ButtonRole.AcceptRole)
        vuota = domanda.addButton("Inizia vuota", QMessageBox.ButtonRole.DestructiveRole)
        domanda.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
        domanda.exec()
        if domanda.clickedButton() is copia:
            modulo_paths.salva_cartella(nuova, copia_da=Paths.root)
        elif domanda.clickedButton() is vuota:
            modulo_paths.salva_cartella(nuova)
        else:
            return
        self._chiedi_riavvio()

    def _cartella_predefinita(self) -> None:
        from Utility.Structures import Paths as modulo_paths
        risposta = QMessageBox.question(
            self, "Cartella dati",
            f"Dal prossimo avvio uso la cartella predefinita:\n"
            f"{modulo_paths.PREDEFINITA}\n\nI dati della cartella attuale "
            "non vengono copiati ne' cancellati.")
        if risposta != QMessageBox.StandardButton.Yes:
            return
        modulo_paths.salva_cartella(None)
        self._chiedi_riavvio()

    def _importa_cartella_dati(self) -> None:
        from Utility.Structures import Paths as modulo_paths
        from Utility.Structures.Paths import Paths

        origine = self._scegli_cartella("Scegli la cartella da cui importare i dati")
        if origine is None:
            return
        if origine.resolve() == Paths.root.resolve():
            self.messaggio.emit("E' la cartella attuale: niente da importare")
            return
        if not ((origine / "userData").is_dir() or (origine / "catalog.db").is_file()):
            risposta = QMessageBox.question(
                self, "Importa dati",
                f"{origine}\nnon sembra una cartella dati di JW LibriX "
                "(manca userData/). Importo lo stesso?")
            if risposta != QMessageBox.StandardButton.Yes:
                return
        dimensione = modulo_paths.spazio_occupato(origine) / (1024 ** 2)
        risposta = QMessageBox.question(
            self, "Importa dati",
            f"Copio {dimensione:.0f} MB da\n{origine}\nin\n{Paths.root}\n\n"
            "I file con lo stesso nome vengono sostituiti (anche note e "
            "segnalibri). La copia si fa al riavvio.")
        if risposta != QMessageBox.StandardButton.Yes:
            return
        modulo_paths.importa_al_prossimo_avvio(origine)
        self._chiedi_riavvio()

    def _elimina_dati_app(self) -> None:
        from SubViews.Conferma import ConfermaApp
        from Utility.Structures import Paths as modulo_paths
        from Utility.Structures.Paths import Paths

        radice = Paths.root
        # Mai cancellare una cartella che non e' sicuramente dell'app.
        if (radice == radice.parent or radice.resolve() == modulo_paths.Path.home().resolve()
                or not (radice / "userData").is_dir()):
            QMessageBox.warning(self, "Elimina dati",
                                f"{radice}\nnon sembra una cartella dati di JW LibriX: "
                                "non la cancello.")
            return

        def elimina() -> None:
            import os
            import shutil
            try:
                shutil.rmtree(radice)
                modulo_paths.FILE_PERCORSO.unlink(missing_ok=True)
            except OSError as errore:
                QMessageBox.warning(self, "Elimina dati", f"Non riuscito: {errore}")
                return
            # Si esce subito: chi resta aperto riscriverebbe i file appena
            # cancellati (impostazioni, log, database).
            os._exit(0)

        ConfermaApp.chiedi(
            self.window(), "Eliminare tutti i dati?",
            f"Cancello {radice} con dentro catalogo, pubblicazioni, media, "
            "note, segnalibri, impostazioni e plugin. Non si puo' annullare: "
            "se ti servono, esporta prima il backup. L'app poi si chiude.",
            "Elimina tutto", elimina)

    def _chiedi_riavvio(self) -> None:
        risposta = QMessageBox.question(
            self, "Riavvio", "La modifica vale dal prossimo avvio. Riavvio adesso?")
        if risposta == QMessageBox.StandardButton.Yes:
            riavvia_app()
        else:
            self.messaggio.emit("La modifica vale dal prossimo avvio")

    def _plugin(self) -> _Scheda:
        scheda = _Scheda("Plugin", self)
        installato = Plugin.installato("timer")
        casella = QCheckBox("", self)
        casella.setChecked(installato and Plugin.attivo("timer"))
        casella.setEnabled(installato)

        def cambiata(stato: int) -> None:
            Plugin.imposta_attivo("timer", bool(stato))
            self.pluginCambiati.emit()

        casella.stateChanged.connect(cambiata)
        scheda.aggiungi(_Riga("Timer adunanze", casella, self))

        if installato:
            scheda.nota(f"Plugin installato (versione {Plugin.versione('timer')}). "
                        "Acceso: compare il tasto con l'orologio nella barra viola. "
                        "Il monitor del timer si sceglie dentro il timer, "
                        "in Impostazioni > Visualizzazione.")
        pulsante = QPushButton("Aggiorna" if installato else "Installa", self)
        pulsante.setEnabled(bool(Plugin.indirizzo("timer")))

        def finita(errore: str) -> None:
            pulsante.setEnabled(True)
            if errore:
                pulsante.setText("Aggiorna" if Plugin.installato("timer") else "Installa")
                self.messaggio.emit(f"Timer non installato: {errore}")
                return
            casella.setEnabled(True)
            pulsante.setText("Aggiorna")
            self.messaggio.emit("Timer installato: ora puoi accenderlo "
                                "(riavvia l'app se non compare il tasto)")
            self.pluginCambiati.emit()

        self._installFinita.connect(finita)

        def scarica_timer() -> None:
            import threading
            pulsante.setEnabled(False)
            pulsante.setText("Scarico…")
            threading.Thread(
                target=lambda: self._installFinita.emit(Plugin.installa("timer")),
                daemon=True).start()

        pulsante.clicked.connect(scarica_timer)
        scheda.aggiungi(_Riga("Scarica da GitHub", pulsante, self))
        if not installato:
            scheda.nota("Plugin non installato. Premi «Installa»: viene scaricato da "
                        f"GitHub e salvato in {Plugin.cartella('timer')}, accanto ai "
                        "tuoi dati (un aggiornamento dell'app non lo tocca).")
        if not Plugin.indirizzo("timer"):
            scheda.nota("L'indirizzo GitHub del timer non è ancora configurato.")
        return scheda

    def _informazioni(self) -> _Scheda:
        from Utility import AggiornaApp, Versione
        scheda = _Scheda("Informazioni", self)
        scheda.nota(f"JW-LibriX {Versione.ETICHETTA_APP} (versione {Versione.VERSIONE_APP})")

        pulsante = QPushButton("Controlla aggiornamenti", self)
        stato = {"ultima": ""}

        def risultato(ultima: str, errore: str) -> None:
            pulsante.setEnabled(True)
            if errore:
                pulsante.setText("Controlla aggiornamenti")
                self.messaggio.emit(errore)
            elif AggiornaApp.e_piu_nuova(ultima):
                stato["ultima"] = ultima
                pulsante.setText(f"Aggiorna alla {ultima}")
                self.messaggio.emit(f"Versione {ultima} disponibile")
            else:
                pulsante.setText("Controlla aggiornamenti")
                self.messaggio.emit("Hai gia' l'ultima versione")

        def fatto(errore: str) -> None:
            pulsante.setEnabled(True)
            if errore:
                self.messaggio.emit(errore)
                return
            pulsante.setText("Aggiornata: riavvia l'app")
            pulsante.setEnabled(False)
            self.messaggio.emit("App aggiornata: chiudi e riapri il programma")

        self._appControllata.connect(risultato)
        self._appAggiornata.connect(fatto)

        def clic() -> None:
            import threading
            pulsante.setEnabled(False)
            if stato["ultima"]:
                pulsante.setText("Scarico…")
                v = stato["ultima"]
                threading.Thread(target=lambda: self._appAggiornata.emit(AggiornaApp.aggiorna(v)),
                                 daemon=True).start()
            else:
                pulsante.setText("Controllo…")
                threading.Thread(target=lambda: self._appControllata.emit(*AggiornaApp.ultima_versione()),
                                 daemon=True).start()

        pulsante.clicked.connect(clic)
        scheda.aggiungi(_Riga("Aggiornamenti dell'app", pulsante, self))
        if Versione.url_app():
            scheda.nota(f"Codice e versioni: {Versione.url_app()}")
        return scheda

    # ------------------------------------------------------------------
    # I DATI
    # ------------------------------------------------------------------

    def _file(self, nome: str):
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        return get_documents_directory() / "userData" / nome

    def _leggi(self, nome: str, chiave: str, ripiego):
        """Un valore dalle impostazioni, o il ripiego."""
        import json
        try:
            percorso = self._file(nome)
            if not percorso.is_file():
                return ripiego
            return json.loads(percorso.read_text(encoding="utf-8")).get(chiave, ripiego)
        except (OSError, ValueError):
            return ripiego

    def _scrivi(self, nome: str, chiave: str, valore) -> None:
        """Scrive UN campo, senza toccare gli altri.

        Legge prima quello che c'e' e cambia un campo solo: cosi' un'altra
        impostazione messa in futuro non viene cancellata da un cambio di
        tema, o di lingua.
        """
        import json
        try:
            percorso = self._file(nome)
            percorso.parent.mkdir(parents=True, exist_ok=True)
            dati = {}
            if percorso.is_file():
                try:
                    dati = json.loads(percorso.read_text(encoding="utf-8"))
                except ValueError:
                    dati = {}
            dati[chiave] = valore
            percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
        except OSError as errore:
            print(f"Non riesco a salvare {chiave} ⚠️  {errore}")

    def _lingua_salvata(self) -> int:
        return int(self._leggi("impostazioni.json", "lingua", 4) or 4)

    def _lingua_cambiata(self, indice: int) -> None:
        scelta = self.findChildren(QComboBox)[0]
        codice = scelta.currentData()
        if codice is None:
            return
        self._scrivi("impostazioni.json", "lingua", int(codice))

    def _lingue(self) -> list[tuple[str, int]]:
        """Le lingue del catalogo, o almeno l'italiano."""
        try:
            from Utility.JWPubManager import lingue_catalogo
            trovate = lingue_catalogo()
            if trovate:
                return trovate
        except (ImportError, OSError):
            pass
        return [("Italiano", 4)]

    @staticmethod
    def _indice(lingue: list[tuple[str, int]], voluto: int) -> int:
        for posizione, (_nome, codice) in enumerate(lingue):
            if codice == voluto:
                return posizione
        return 0

    def _spazio_usato(self) -> str:
        """Quanto occupa la cartella dei dati.

        Si contano i file senza seguire i collegamenti: i pacchetti sono
        zip e dentro ci sono collegamenti simbolici, e seguirli fa contare
        lo stesso contenitore piu' volte.
        """
        try:
            from Utility.Structures.Paths import Paths
            totale = 0
            # `Paths.root` e' un ATTRIBUTO, non un metodo: chiamarlo
            # darebbe 'PosixPath' object is not callable.
            for percorso in Paths.root.rglob("*"):
                try:
                    if percorso.is_file() and not percorso.is_symlink():
                        totale += percorso.stat().st_size
                except OSError:
                    # un file che sparisce mentre si conta non e' un errore
                    continue
            if totale == 0:
                return "…"
            return f"{totale / (1024 ** 3):.1f} GB"
        except (ImportError, OSError):
            return "…"

    def _ultimo(self) -> str:
        """L'ultimo aggiornamento del catalogo."""
        from Utility import Aggiornamenti
        return Aggiornamenti.leggi_ultimo_aggiornamento()