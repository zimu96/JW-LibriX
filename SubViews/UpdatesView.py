#
#  UpdatesView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Cosa c'e' sul server, e cosa puoi scaricare.  Tu scegli.

LA REGOLA, E NON E' UNA SCELTA DI STILE
----------------------------------------
**Niente si scarica da solo.**  Nessun download parte senza che l'utente
prema il pulsante di quella riga.

La ragione e' che un download automatico fa tre cose che non si possono
disfare:

    se la linea non regge si interrompe a meta' e lascia un file
    parziale dove l'app lo cerca come se fosse intero: il file c'e', la
    dimensione e' quasi giusta, e dentro non c'e' niente

    consuma traffico senza che nessuno lo abbia chiesto, e su una
    connessione lenta blocca la finestra per minuti

    se si scrive mentre qualcun altro sta leggendo, gli elenchi sono
    mezzo aggiornati e mezzo no

Quindi qui sotto ci sono tre cose e sono tre cose diverse:

    COSA C'E'         interroga il server, e basta.  Non scrive niente
    COSA HAI         quello che hai gia' scompattato sul disco
    COSA PUOI        la differenza: quello che hai e quello che c'e'

IL PULSANTE E' UNA RIGA, NON UN TUTTO
--------------------------------------
Non c'e' un "scarica tutto".  Ogni riga ha il suo pulsante, perche' una
riga sola puo' volerla e le altre no: un pulsante unico costringe a una
decisione che non e' quella giusta.

IL CONTROLLO ALL'AVVIO
----------------------
Non blocca la finestra e non scarica niente.  Parte in background e quando
arriva il risultato la schermata si aggiorna.  Un controllo che blocca
l'avvio fa aspettare l'utente prima di poter fare qualsiasi cosa, per
un'informazione che non serve subito.

IL TEMPO DI VALIDITA'
--------------------
Un'ora.  Non a ogni apertura e non ogni tre minuti: il server non cambia
cosi' spesso, e una richiesta che ritorna sempre uguale non aggiunge
niente.
"""
from __future__ import annotations

import time
from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Utility import Aggiornamenti, Copertine, tema
from Utility.Stuff import icon

# Le pubblicazioni fisse che si controllano.  Non sono tutte: sono quelle
# che valgono la pena controllare a ogni avvio, cioe' quelle grandi e quelle
# che l'utente legge.  Controllarle tutte sarebbe centinaia di richieste per
# un'informazione che non cambia mai.
#
# NON SONO TUTTE LE PUBBLICAZIONI, E NON SONO I PERIODICI
# ------------------------------------------------------
# I periodici non possono stare qui dentro: senza il numero del numero il
# server risponde errore 400, e il numero cambia ogni mese, quindi una lista
# scritta a mano smetterebbe di funzionare senza dire niente.  Li aggiunge
# `Aggiornamenti.da_controllare()`, che li rilegge dal catalogo a ogni
# controllo.
#
# Quindi `DA_CONTROLLARE` non e' la lista di quello che si controlla: e' la
# parte che non cambia.  Il nome e' questo perche' cambiarlo avrebbe fatto
# cercare in questo punto quello che si cerca davvero li', cioe' il
# controllo, e sta in `Aggiornamenti`.
DA_CONTROLLARE = [("nwtsty", "I"), ("ypq", "I"), ("sn", "I"), ("lff", "I")]

#: Le misure di una scheda di Novita'.  Come le card dei Preferiti nella Home,
#: e un filo piu' piccole: qui le voci sono di piu' e la striscia e' quella
#: sotto, quindi non devono rubare la larghezza a quelle.
LATO_ANTEPRIMA = 112
LARGHEZZA_SCHEDA = 128

#: L'altezza della striscia: la miniatura, il titolo su due righe e il
#: dettaglio sotto, piu' un margine e la rotella orizzontale.
ALTEZZA_SCHEDA = 224


class _Riga(QWidget):
    """Una riga: che cosa e' e il pulsante per prendersela.

    Due modalita':
      - "scarica":   pubblicazione nuova, pulsante "Scarica"
      - "aggiorna":  pubblicazione gia' scaricata con update, icona refresh
    """

    #: L'utente ha premuto Scarica.  Passa la riga.
    scarica = Signal(object)
    #: L'utente ha premuto Aggiorna (refresh).  Passa la riga.
    aggiorna = Signal(object)

    def __init__(self, voce: dict, padre=None, *, modalita: str = "scarica") -> None:
        """Crea la riga.
        :param modalita: "scarica" (default) o "aggiorna".
        """
        super().__init__(padre)
        tema.sfondo(self, "rigaAggiornamento")
        self.voce = voce
        self._modalita = modalita

        # UNA SCHEDA, NON UNA RIGA
        # -----------------------
        # Nella schermata dell'app originale le voci di questa sezione sono
        # schede: la miniatura sopra, il titolo sotto, in fila orizzontale.
        # Prima erano righe larghe a tutto schermo, che e' un elenco e non una
        # striscia: con quattro voci la pagina era quasi vuota e con
        # venticinque erano venticinque righe da girare.
        disposizione = QVBoxLayout(self)
        disposizione.setContentsMargins(4, 4, 4, 4)
        disposizione.setSpacing(4)

        # LA COLONNA DI SINISTRA: IL PULSANTE SOPRA, LA COPERTINA SOTTO
        #
        # Il bottone sta SOPRA la miniatura: e' subito sopra la cosa a cui
        # si riferisce, e si vede prima ancora di leggere il titolo.
        sinistra = QWidget(self)
        colonna_sinistra = QVBoxLayout(sinistra)
        colonna_sinistra.setContentsMargins(0, 0, 0, 0)
        colonna_sinistra.setSpacing(4)

        if modalita == "aggiorna":
            # MODALITA' AGGIORNAMENTO: icona refresh bianca, niente testo
            self.pulsante = QPushButton(sinistra)
            self.pulsante.setFixedSize(28, 28)
            self.pulsante.setIcon(icon("arrow.clockwise", "#ffffff", 20))
            self.pulsante.setToolTip("Aggiorna: scarica la versione nuova")
            self.pulsante.clicked.connect(lambda: self.aggiorna.emit(self.voce))
        else:
            # MODALITA' SCARICA: pulsante con testo "Scarica"
            self.pulsante = QPushButton("Scarica", sinistra)
            self.pulsante.setFixedWidth(88)
            self.pulsante.setFixedHeight(22)
            self.pulsante.setEnabled(_ha_pacchetto(voce))
            self.pulsante.setToolTip(
                "Scarica il pacchetto" if _ha_pacchetto(voce)
                else "Sul server non c'è un pacchetto per questa pubblicazione")
            self.pulsante.clicked.connect(lambda: self.scarica.emit(self.voce))
        colonna_sinistra.addWidget(self.pulsante, 0)

        # Si chiede al pacchetto per prima: se la pubblicazione e' gia'
        # scaricata la copertina e' sul disco e non costa niente.  Se non
        # e' scaricata va dalla rete, e li il glifo del libro sta sotto,
        # come in tutta la lista.
        # SENZA COPERTINA IL GLIFO DEL LIBRO, E IL BOTTOLO NON SALE A VAO
        # ----------------------------------------------------------------
        # La Bibbia per lo studio non ha una copertina che stia in una
        # miniatura quadrata, e senza immagine la scheda aveva solo il bottone
        # in alto e il titolo in fondo, con 200 pixel di vuoto in mezzo e il
        # bottolo che sembrava non collegato a niente.
        #
        # Il glifo c'e' gia' in tutto il resto del programma per questo caso,
        # quindi si usa quello e non si lascia il buco.
        copertina = self._copertina(voce)
        if copertina is None:
            miniatura = QLabel(sinistra)
            miniatura.setPixmap(
                icon("book.fill", "#f2f2f2", 44).pixmap(44, 44))
            miniatura.setFixedSize(LATO_ANTEPRIMA, LATO_ANTEPRIMA)
            miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
            miniatura.setObjectName("miniatura")
            riga = QHBoxLayout()
            riga.setContentsMargins(0, 0, 0, 0)
            riga.addStretch(1)
            riga.addWidget(miniatura, 0)
            riga.addStretch(1)
            colonna_sinistra.addLayout(riga)
        if copertina is not None:
            miniatura = QLabel(sinistra)
            miniatura.setPixmap(Copertine.pixmap_quadrata(
                copertina, LATO_ANTEPRIMA))
            miniatura.setFixedSize(LATO_ANTEPRIMA, LATO_ANTEPRIMA)
            miniatura.setObjectName("miniatura")
            riga_miniatura = QHBoxLayout()
            riga_miniatura.setContentsMargins(0, 0, 0, 0)
            riga_miniatura.addStretch(1)
            riga_miniatura.addWidget(miniatura, 0)
            riga_miniatura.addStretch(1)
            colonna_sinistra.addLayout(riga_miniatura)
        disposizione.addWidget(sinistra, 0)
        self.setFixedWidth(LARGHEZZA_SCHEDA)

        testo = QWidget(self)
        colonna = QVBoxLayout(testo)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(2)

        # LA RIGA CHE SPIEGA PERCHE' LA SCHEDA E' QUI
        # -------------------------------------------
        # Sta SOPRA il titolo e non sotto: e' la domanda a cui la scheda
        # risponde.  Sotto, dopo "122 MB · JWPUB", si legge come un'altra
        # informazione fra le altre e nessuno la guarda; sopra, e' la prima
        # cosa che si vede.
        #
        # E' vuota quando non c'e' niente di vero da dire — cioe' quasi
        # sempre, perche' una scheda che resta due controlli di fila con lo
        # stesso checksum non ha niente di nuovo.  Il vuoto non occupa
        # altezza: `addWidget` su un'etichetta vuota la lascia con zero
        # pixel, quindi la scheda senza la frase e' identica a quella prima
        # che la frase esisteva.  Se si nascondesse con `setVisible` il
        # risultato sarebbe lo stesso, ma con una riga in piu' di codice
        # che serve solo a nascondere.
        if voce.get("spiegazione"):
            frase = QLabel(voce["spiegazione"], testo)
            frase.setObjectName("spiegazione")
            frase.setWordWrap(True)
            # due righe: "Nuovo sul server: il file e' cambiato." sta in due
            # righe su 128 pixel, e la terza spingerebbe il titolo sotto il
            # bottone "Scarica" come gia' succedeva coi cinque pezzi del
            # dettaglio
            frase.setMaximumHeight(32)
            colonna.addWidget(frase)

        nome = QLabel(voce.get("titolo") or voce.get("sigla", "?"), testo)
        nome.setObjectName("titoloRiga")
        nome.setWordWrap(True)
        # Due righe e non tre: un titolo con dentro il nome di un libro e
        # dell'edizione non si legge oltre, e il terzo pezzo spingerebbe
        # fuori il bottone.
        nome.setMaximumHeight(34)
        colonna.addWidget(nome)

        # LA SIGLA SOTTO, NON COME TITOLO
        #
        # "nwtsty" non e' un nome, e' una chiave.  Ma senza la chiave
        # l'utente non puo' cercare quella pubblicazione da un'altra
        # parte, quindi sta li' sotto, piccola, dove non fa finta di essere
        # il titolo.
        # LA SIGLA NON C'E' PIU'
        # -----------------------
        # Era una riga sotto il titolo.  Ma dentro una scheda larga 128 pixel
        # il titolo va su tre righe e la sigla su una: la scheda misurava 301
        # pixel, la striscia ne concedeva 218, e il fondo della scheda — cioe'
        # dove finiscono i formati e il bottone — veniva tagliato.
        #
        # Il titolo dice gia' tutto quello che diceva la sigla: «Cantiamo a
        # Geova» e «sn» sono la stessa informazione, e con la copertina
        # accanto non serve il codice.

        dettaglio = QLabel(self._dettaglio(), testo)
        dettaglio.setObjectName("nota")
        dettaglio.setWordWrap(True)
        dettaglio.setMaximumHeight(32)
        colonna.addWidget(dettaglio)

        disposizione.addWidget(testo, 0)


    @staticmethod
    def _copertina(voce: dict):
        """La copertina della riga, o None.

        Serve costruire un oggetto Publication al posto giusto, perche'
        ``pixmap_copertina`` cerca la cartella del pacchetto e quella la
        ricava dal nome che segue il formato delle righe del catalogo.
        """
        from Utility import Lingua
        from Utility.Structures.Generals import Publication

        numero = Lingua.da_simbolo(voce.get("lingua") or Lingua.corrente_simbolo())
        pub = Publication(ID=0, keySymbol=voce.get("sigla", ""), year=0,
                          mepsLanguageId=numero, publicationTypeId=0,
                          issueTagNumber=0, title=voce.get("titolo") or "")
        try:
            return Copertine.pixmap_copertina(pub, "xs")
        except Exception:  # noqa: BLE001
            # Una copertina mancante non e' un motivo per far cadere la
            # sezione: si mostra la riga senza immagine.
            return None

    @staticmethod
    def _giorni_da(giorno: str) -> str:
        """Da quanti giorni la pubblicazione e' nel catalogo, in italiano.

        Il conteggio lo fa il programma e non il server, quindi puo' essere
        sbagliato di un giorno: e' il caso normale, perche' `CatalogedOn` e'
        l'ora in cui il server ha messo la riga dentro, e quel momento puo'
        essere la sera prima.  Per questo la parola e' «da», che resta vera
        anche quando il numero non torna esattamente.
        """
        try:
            # `date` e non `time`: il catalogo scrive una data, e la differenza
            # fra due date si fa fra due date.  Con `time` si dovrebbe passare
            # da una stringa a una struct a un numero e poi tornare indietro,
            # e a metà del passaggio c'è il fuso orario, che qui non c'entra e
            # può far uscire un giorno.
            giorni = date.today().toordinal() - date.fromisoformat(giorno).toordinal()
        except (TypeError, ValueError):
            return ""
        if giorni <= 0:
            return "oggi"
        if giorni == 1:
            return "ieri"
        if giorni < 14:
            return f"{giorni} giorni"
        if giorni < 60:
            return f"{int(giorni / 7)} settimane"
        return f"{int(giorni / 30)} mesi"

    def _dettaglio(self) -> str:
        """La riga sotto il nome: che cosa c'e' e in che formato.

        PRIMA QUI C'ERANO DUE `_dettaglio`
        ---------------------------------
        Il primo era un `@staticmethod` che usava `self.get(...)`, cioe' un
        metodo che non poteva funzionare: `self` dentro un metodo statico
        non esiste.  Il secondo, quello vero, era **sotto** e vinceva.

        Due metodi con lo stesso nome nella stessa classe non danno nessun
        avviso: il secondo copre il primo e il primo diventa codice morto
        che sembra funzionante.  Se il secondo fosse stato tolto per un
        refuso, il primo sarebbe entrato e avrebbe detto
        "AttributeError: 'staticmethod' object has no attribute 'get'" con
        un nome che non porta da nessuna parte al motivo.
        """
        # DUE PEZZI, E NON CINQUE
        # ----------------------
        # Il dettaglio sta sotto il titolo in una scheda larga 128 pixel, e
        # cinque pezzi facevano tre righe: l'ultima riga restava sotto il
        # bordo e si leggeva a meta'.  Due pezzi stanno in due righe e dicono
        # quello che serve: quanto costa e che cosa c'e' dentro.
        voci = []
        # LA RIGA CHE VIENE DAL CATALOGO
        # -------------------------------
        # Una riga presa dal catalogo non ha passato dal server, quindi non ha
        # né la dimensione del pacchetto né il numero dei video: su quella
        # riga non si puo' scrivere «niente sul server», che sarebbe falso —
        # sul server c'è, e anzi è il catalogo stesso a dirlo.  Si scrive la
        # data in cui è entrata nel catalogo, che è la cosa che la riga sa e
        # che all'utente serve sapere: «è uscita tre giorni fa».
        giorno = self.voce.get("giorno")
        if giorno:
            giorni = self._giorni_da(giorno)
            voci.append(f"nel catalogo da {giorni}" if giorni else "nuova")
        pacchetto = self.voce.get("pacchetto")
        if pacchetto:
            megabyte = (pacchetto.get("filesize") or 0) / (1024 * 1024)
            voci.append(f"{megabyte:.0f} MB")
        # Video e audio sono info delle categorie Media, non delle pubblicazioni:
        # qui non servono e confondono (prima apparivano in rosso come tasti).
        # if self.voce.get("video"):
        #     voci.append(f"{self.voce['video']} video")
        # elif self.voce.get("audio"):
        #     voci.append(f"{self.voce['audio']} audio")
        elif self.voce.get("formati"):
            voci.append(", ".join(self.voce["formati"][:3]))
        return " · ".join(voci) if voci else "niente sul server"


def _ha_pacchetto(voce: dict) -> bool:
    """C'è un pacchetto da scaricare per questa voce?

    Due modi di saperlo, e vengono da due posti diversi:

        ``pacchetto``     il server ha risposto, e nella risposta c'era
        ``scaricabile``   lo ha detto il catalogo: c'è una riga in
                          ``PublicationAsset`` con dentro un ``.jwpub``

    Non si tiene un conto per ogni modo e non si sceglie: una riga puo'
    venire dall'uno o dall'altro, e il pulsante deve accendersi in entrambi i
    casi.  Un pulsante che si accende e non scarica niente è la cosa peggiore
    che possa fare questa sezione.
    """
    if voce.get("pacchetto") is not None:
        return True
    return bool(voce.get("scaricabile"))


class UpdatesView(QWidget):
    """Cosa c'e' sul server e cosa puoi scaricare."""

    messaggio = Signal(str)
    #: Chiede alla finestra di aggiornare le sezioni che cambiano
    cambiato = Signal()
    #: L'utente ha premuto "Scarica" su una riga.  La finestra lo sa,
    #: perche' e' lei che sa scaricare e che ha il barra di stato.
    scaricaRichiesta = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._in_corso = False
        self._righe: list[_Riga] = []

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)

        pagina = QWidget()
        disposizione = QVBoxLayout(pagina)
        disposizione.setContentsMargins(18, 16, 18, 16)
        disposizione.setSpacing(0)
        disposizione.setAlignment(Qt.AlignmentFlag.AlignTop)

        # IL TITOLO: UNA SEZIONE SOLA
        # ----------------------------------
        # Prima qui c'era «Novita' e aggiornamenti», e nella Home sopra
        # c'era anche una sezione «Novita'». Due sezioni con lo stesso nome,
        # una sotto l'altra, che parlano di due cose diverse: due nomi simili
        # per due domande diverse, e chi cerca «le novita'» non sa quale
        # delle due sta guardando.
        #
        # Adesso c'e' **una** sezione, e dentro ci sono le due liste con un
        # nome ciascuna: `Novita'` e quello che resta da scaricare. Le due
        # liste fanno due lavori diversi e restano due pezzi, ma non sono
        # due categorie.
        titolo = QLabel("Novità", pagina)
        titolo.setObjectName("titoloPagina")
        disposizione.addWidget(titolo)

        self.lingua = QLabel("", pagina)
        self.lingua.setObjectName("linguaSezione")
        titolo_riga = QHBoxLayout()
        titolo_riga.setContentsMargins(0, 0, 0, 0)
        titolo_riga.addStretch(1)
        titolo_riga.addWidget(self.lingua, 0, Qt.AlignmentFlag.AlignBottom)
        disposizione.addLayout(titolo_riga)

        # IL POSTO DOVE FINISCE LA PARTE «CHE COSA E' USCITO»
        # ----------------------------------------------------
        # `aggiungi_parte` mette qui sotto quello che c'e' gia' costruito, e il
        # nome della sezione lo mette solo questa. Il pezzo che arriva non
        # porta un titolo perche' due titoli nella stessa colonna sembrano due
        # sezioni, che e' proprio quello che non volevamo.
        self._parti = QVBoxLayout()
        self._parti.setContentsMargins(0, 0, 0, 0)
        self._parti.setSpacing(8)
        disposizione.addLayout(self._parti)

        # LA SOTTOTITOLA E' LA REGOLA, SCRITTA
        #
        # Non e' una frase di cortesia: e' la spiegazione di perche' qui
        # non parte nessun download.  Se un giorno qualcuno mette un
        # download automatico, questa riga lo rende visibile invece che
        # nascosto.
        self.stato = QLabel("", pagina)
        self.stato.setObjectName("nota")
        self.stato.setWordWrap(True)
        disposizione.addWidget(self.stato)
        disposizione.addSpacing(16)

        # LA STRISCIA
        # -----------
        # Orizzontale e scorrevole, come nell'app originale.  Il widget dentro
        # si allarga fino a riempire (`setWidgetResizable(True)`) ma non si
        # restringe sotto la somma delle schede: e' quello che fa comparire
        # la rotella solo quando le schede non ci stanno, e non sempre.
        #
        # La rotella verticale e' spenta: in una striscia non serve, e due
        # rotelle su un riquadro di 220 pixel non ci stanno.
        self.contenitore = QScrollArea(self)
        self.contenitore.setWidgetResizable(True)
        self.contenitore.setFrameShape(QScrollArea.Shape.NoFrame)
        self.contenitore.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.contenitore.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._pagina = QWidget()
        self._colonna = QHBoxLayout(self._pagina)
        self._colonna.setContentsMargins(0, 0, 0, 0)
        # 3 come i Preferiti: le due strisce sono sulla stessa pagina e devono
        # avere lo stesso vuoto, altrimenti una sembra piu' stretta dell'altra
        # senza che nessuno sappia dire quale sia quella giusta.
        self._colonna.setSpacing(3)
        self.contenitore.setWidget(self._pagina)
        self.contenitore.setFixedHeight(ALTEZZA_SCHEDA + 18)
        disposizione.addWidget(self.contenitore)

        area.setWidget(pagina)
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(area)

        self.mostra_ultimo()

    # ------------------------------------------------------------------

    def aggiungi_parte(self, nome: str, widget) -> None:
        """Mette un pezzo sotto il titolo, con un nome suo.

        Serve alla Home per il pezzo «che cosa e' uscito»: quello e' un
        elenco di voci curate dal catalogo, e qui sotto c'e' l'elenco di
        quello che si puo' scaricare. Sono due lavori diversi dentro la
        stessa sezione, e ognuno ha un nome perche' senza nomi due elenchi
        uno sotto l'altro sembrano la stessa cosa due volte.

        Il nome e' una riga piccola e grigia, non un titolo di sezione: un
        titolo grosso dentro una sezione che ha gia' un titolo grosso fa
        pensare che la sezione sia un'altra.
        """
        etichetta = QLabel(nome, widget.parentWidget())
        etichetta.setObjectName("parteNovita")
        self._parti.addWidget(etichetta)
        self._parti.addWidget(widget)

    def _metti_la_lingua(self) -> None:
        """Il nome della lingua che si sta guardando, a destra del titolo.

        Non il suo codice: e' la stessa riga e la stessa forma delle altre
        sezioni della Home, e «I» in un angolo non dice niente a nessuno.
        """
        from Utility import Lingua

        voce = Lingua.corrente_voce()
        self.lingua.setText(Lingua.titolo(voce) if voce else "")

    def mostra_ultimo(self) -> None:
        """Le righe, senza chiedere niente a nessuno.

        LE RIGHE NON SONO TUTTE DAL SERVER
        ----------------------------------
        Le righe vengono da tre posti:

            il catalogo       le pubblicazioni nuove, con il giorno in cui sono
                              entrate.  Non costa niente: il catalogo e' gia'
                              sul disco, e non serve una richiesta.
            il server (cache) il conto dei video, dell'audio e dei formati di
                              quello che c'era all'ultimo controllo.
            aggiornamenti     pacchetti GIA' SCARICATI che sul server hanno
                              un checksum diverso: c'e' una versione nuova.

        Le nuove del catalogo stanno **prima** perche' sono le piu' recenti.
        Gli aggiornamenti stanno dopo: l'utente li ha gia', ma c'e' una versione
        piu' nuova.  La stessa pubblicazione non compare due volte.
        """
        # 1. Nuove dal catalogo (esclude quelle gia' scaricate)
        righe = Aggiornamenti.nuove_nel_catalogo("I")
        gia_viste = {r["sigla"] for r in righe}
        self._metti_la_lingua()

        # 2. Cache server: voci gia' controllate (nuove o aggiornate)
        dati = Aggiornamenti.leggi()
        for voce in (dati.get("server") or []):
            if voce.get("errore") or voce.get("sigla") in gia_viste:
                continue
            righe.append(voce)
            gia_viste.add(voce["sigla"])

        # 3. AGGIORNAMENTI: pacchetti installati con checksum diverso sul server
        #    Usiamo la cache se c'e', altrimenti li segnamo per controllo in background
        aggiornamenti_cache = self._aggiornamenti_da_cache(gia_viste)
        righe.extend(aggiornamenti_cache)

        if not dati.get("controllato"):
            self.stato.setText(
                "Quello che è nuovo lo dice il catalogo, e il catalogo è già "
                "sul disco. Per il resto — quanti video, quanti file, "
                "quanto costa — serve chiedere al server: premi il tasto "
                "di aggiornamento in alto.")
        else:
            quando = time.strftime("%d/%m alle %H:%M",
                                   time.localtime(dati.get("quando") or 0))
            catalogo = ("da aggiornare" if dati.get("catalogo_vecchio")
                        else "aggiornato")
            self.stato.setText(
                f"Ultimo controllo: {quando}.  Catalogo: {catalogo}.  "
                f"Questa schermata guarda e non scarica: il download parte "
                f"solo dal pulsante di ogni riga, e solo per quella riga.")

        # Avvia controllo in background per aggiornamenti non in cache
        self._controlla_aggiornamenti_in_background(gia_viste)

        # Le piu' nuove in cima.
        self._ricostruisci(righe)

    def _aggiornamenti_da_cache(self, gia_viste: set) -> list:
        """Restituisce le righe 'aggiorna' per pacchetti installati con checksum diverso in cache."""
        dati = Aggiornamenti.leggi()
        server_cache = {v["sigla"]: v for v in (dati.get("server") or []) if not v.get("errore")}
        if not server_cache:
            return []

        from Utility.JWPubManager import scaricate
        from Utility.Aggiornamenti import checksum_scaricato

        # Pacchetti installati (sigla_lingua)
        installati = set()
        for cartella in scaricate():
            parti = cartella.name.split("_")
            if len(parti) >= 2:
                installati.add(f"{parti[0]}_{parti[1]}")

        aggiornamenti = []
        for chiave in installati:
            if chiave in gia_viste:
                continue
            sigla, lingua = chiave.split("_", 1)
            mio = checksum_scaricato(sigla, lingua)
            server_voce = server_cache.get(sigla)
            if not mio or not server_voce:
                continue
            suo = (server_voce.get("pacchetto") or {}).get("checksum")
            if suo and str(mio).lower() != str(suo).lower():
                # C'e' un aggiornamento: costruiamo la voce per la riga
                voce = dict(server_voce)
                voce["_modalita"] = "aggiorna"
                aggiornamenti.append(voce)
                gia_viste.add(sigla)
        return aggiornamenti

    def _controlla_aggiornamenti_in_background(self, gia_viste: set) -> None:
        """Controlla in background i pacchetti installati non in cache per aggiornamenti."""
        from Utility.JWPubManager import scaricate
        from Utility.Aggiornamenti import checksum_scaricato, controlla_una_pubblicazione
        from Utility.Extensions.Ext_DispatchQueue import background, on_main

        dati = Aggiornamenti.leggi()
        server_cache = {v["sigla"]: v for v in (dati.get("server") or []) if not v.get("errore")}

        # Pacchetti installati non ancora controllati
        da_controllare = []
        for cartella in scaricate():
            parti = cartella.name.split("_")
            if len(parti) < 2:
                continue
            chiave = f"{parti[0]}_{parti[1]}"
            if chiave in gia_viste:
                continue
            sigla, lingua = parti[0], parti[1]
            if sigla in server_cache:
                continue  # gia' in cache, gestito da _aggiornamenti_da_cache
            mio = checksum_scaricato(sigla, lingua)
            if not mio:
                continue  # non abbiamo checksum locale, non possiamo confrontare
            da_controllare.append((sigla, lingua, mio))

        if not da_controllare:
            return

        def lavoro() -> list:
            trovati = []
            for sigla, lingua, mio in da_controllare:
                try:
                    server = controlla_una_pubblicazione(sigla, lingua)
                except Exception:
                    continue
                if server.get("errore"):
                    continue
                suo = (server.get("pacchetto") or {}).get("checksum")
                if suo and str(mio).lower() != str(suo).lower():
                    voce = dict(server)
                    voce["_modalita"] = "aggiorna"
                    trovati.append(voce)
            return trovati

        def finito(trovati: list) -> None:
            if not trovati:
                return
            # Ricostruiamo aggiungendo i nuovi aggiornamenti trovati
            righe_attuali = [r.voce for r in self._righe]
            sigle_attuali = {r.get("sigla") for r in righe_attuali}
            for voce in trovati:
                if voce["sigla"] not in sigle_attuali:
                    righe_attuali.append(voce)
            on_main(lambda: self._ricostruisci(righe_attuali))

        background(lavoro, completion=finito)

    def _ricostruisci(self, voci: list) -> None:
        """Le righe, da capo.  Sono quattro: il costo non si vede."""
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()
        self._righe = []

        if not voci:
            vuoto = QLabel("Niente da mostrare.", self.contenitore)
            vuoto.setObjectName("vuoto")
            self._colonna.addWidget(vuoto)
            return

        for voce in voci:
            riga = _Riga(voce, self.contenitore)
            riga.scarica.connect(self.scaricaRichiesta.emit)
            self._colonna.addWidget(riga)
            self._righe.append(riga)

    # ------------------------------------------------------------------

    def controlla(self, forzato: bool = False) -> None:
        """Chiede al server, in background.

        Non scarica niente: interroga e basta.

        Se il controllo e' gia' in corso non se ne avvia un secondo: due
        richieste insieme non danno due risposte, danno la stessa risposta
        due volte e il doppio lavoro.
        """
        if self._in_corso:
            return
        if not forzato and not Aggiornamenti.scaduto():
            self.mostra_ultimo()
            return
        self._in_corso = True
        self.stato.setText("Sto chiedendo al server. Non scarico niente.")
        self._lavora()

    def _lavora(self) -> None:
        """Interroga in background, e torna sul main thread a scrivere.

        DUE TRABATTI, E SONO ENTRAMBI NEL COLPO

        Uno: un thread secondario non puo' toccare i widget.  Non e' una
        raccomandazione di stile: Qt vuole che i widget siano creati e
        modificati dal thread che ha costruito la ``QApplication``, e
        farlo da un altro thread porta a un ``abort()`` senza
        spiegazione.

        Due: ``completion`` viene chiamata **senza argomenti**.  Dentro
        ``Ext_DispatchQueue`` c'e' ``func()``, e se la funzione ne vuole
        uno va in errore: di nuovo con ``abort()``, e di nuovo senza
        spiegazione.

        Il risultato passa per una lista che il thread secondario riempie
        e il main thread legge.  E' sicuro perche' fra le due c'e' il
        segnale, che e' una coda: quando la callback parte, il lavoro e'
        finito.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        risultato: list = []
        # LE DUE COSE CHE IL THREAD RIEMPIE STANNO **FUORI** DA `lavoro`
        # -----------------------------------------------------------
        # La `completion` di `background` viene chiamata dal main thread e
        # chiude la funzione che l'ha lanciata: vede quindi le variabili di
        # `_lavora`, e **non** quelle che sono nate dentro `lavoro`.
        #
        # Perche' e' successo: `catalogo` era dichiarata dentro `lavoro` e
        # la lambda la leggeva di fuori, quindi al richiamo:
        #
        #     NameError: name 'catalogo' is not defined
        #
        # e la sezione Novita' non mostrava niente, senza dire niente: la
        # traceback finiva in mezzo all'output di un thread.
        #
        # `risultato` sta fuori per la stessa ragione ed e' gia' cosi' da
        # prima: quindi le due liste stanno insieme e si leggono insieme.
        catalogo: list = []

        def lavoro() -> None:
            # Le fisse **e** i periodici letti dal catalogo.  Il catalogo si
            # apre una volta sola, fuori dal ciclo: `periodici()` fa una
            # query e aprire il database dentro il ciclo significherebbe
            # aprirlo una volta per ogni pubblicazione.
            # I periodici si leggono UNA volta: e' una query sul catalogo e
            # il numero va passato dentro, altrimenti ogni chiamata a
            # `cosa_c_e_sul_server` riaprirebbe il database per cercare lo
            # stesso numero che il chiamante ha gia' davanti.  I numeri letti
            # qui sono i veri: vengono dal catalogo che elenca i numeri di
            # ogni periodico, non sono calcolati.
            periodici = Aggiornamenti.periodici("I")
            for sigla, lingua in DA_CONTROLLARE:
                risultato.append(Aggiornamenti.cosa_c_e_sul_server(sigla, lingua))
            for voce in periodici:
                risultato.append(Aggiornamenti.cosa_c_e_sul_server(
                    voce["sigla"], "I", voce["numero"]))
            # LA DOMANDA SUL CATALOGO VIENE QUI E NON DOPO
            # ---------------------------------------------
            # `catalogo_vecchio` chiede il manifest al server e blocca, quindi
            # va fatto in questo thread.  Prima era chiamato in `_finito`,
            # che gira sul main thread: due richieste con la finestra ferma
            # nel mezzo di un controllo che l'utente ha avviato lui, e la
            # sensazione era che il programma si fosse impiantato.
            catalogo.append(Aggiornamenti.catalogo_vecchio())

        background(lavoro, completion=lambda: self._finito(risultato, catalogo))

    def _finito(self, righe: list, catalogo: list | None = None) -> None:
            """Il controllo e' arrivato: si scrive il fatto e si mostra.

            IL PRIMO CONTROLLO: L'OGGETTO PUO' NON ESISTERE PIU'
            --------------------------------------------------------
            Il controllo parte in background e torna quando torna.  Se nel
            frattempo la sezione e' stata distrutta — e la finestra lo fa quando
            si preme Aggiorna, o quando si cambia sezione — l'oggetto Python
            esiste ancora ma quello di C++ no, e toccarlo da:

                RuntimeError: wrapped C/C++ object of type UpdatesView
                has been deleted

            La finestra e' gia' sparita, quindi non c'e' nessuno a cui fare
            male: si controlla e si esce.

            ``sip.isdeleted`` e' l'unico modo onesto di chiederlo.  ``is None``
            non serve, perche' l'oggetto non diventa None: esiste, e-mentre non
            e' piu' nato dal lato di C++.  Provarlo a voce fa peggio.

            IL FILE PRIMA DI TUTTO
            ----------------------
            Il file si scrive PRIMA, fuori dal try, perche' e' la parte che
            conta: il risultato di quattro richieste di rete deve sopravvivere
            alla schermata, altrimenti si rifanno tutte alla prossima apertura.

            IL TRY/CATCH QUI NON E' COSA' COMUNE
            -----------------------------------
            Questa funzione gira dentro un segnale Qt.  Un'eccezione dentro un
            segnale Qt fa ``abort()`` e non lascia nessuna riga di traceback: la
            finestra sparisce e si crede che sia un crash di Qt.  Il motivo piu'
            probabile di un crash cosi' e' un errore in una callback, e l'unico
            modo per vederlo e' scriverlo qui.
            """
            self._in_corso = False

            # IL CONTROLLO PRECEDENTE, LETTO **PRIMA** DI SCRIVERE QUESTO
            # ----------------------------------------------------------
            # `scrivi()` sovrascrive il file con le righe di adesso.  Se si
            # leggesse dopo, `prima` sarebbe il controllo che si e' appena
            # fatto e il confronto darebbe sempre "uguale": la riga che
            # spiega il perche' non comparirebbe mai, e sembrerebbe che il
            # meccanismo non funzioni.
            #
            # Il file puo' anche non esserci: `leggi()` restituisce un
            # dizionario vuoto, e `spiegazione()` con un vuoto non scrive
            # niente.  E' la prima volta, e in quel caso non si sa cosa sia
            # nuovo.
            try:
                prima = {Aggiornamenti._chiave(v): v
                         for v in (Aggiornamenti.leggi().get("server") or [])
                         if isinstance(v, dict)}
            except Exception:  # noqa: BLE001 - senza il confronto la sezione
                prima = {}      # funziona lo stesso, solo senza la frase

            for voce in righe:
                if isinstance(voce, dict):
                    voce["spiegazione"] = Aggiornamenti.spiegazione(voce, prima)

            try:
                # `catalogo` e' la risposta del thread di lavoro.  Se non c'e'
                # — cioe' se il controllo e' cominciato prima che questa
                # domanda esistesse — non si rimette a True: dire "da
                # aggiornare" senza aver guardato e' la cosa che questo
                # controllo ha smesso di fare.
                vecchio = bool(catalogo and catalogo[0])
                Aggiornamenti.scrivi({
                    "quando": time.time(),
                    "controllato": True,
                    "catalogo_vecchio": vecchio,
                    "server": righe,
                })
            except Exception as errore:  # noqa: BLE001
                print(f"Aggiornamenti non salvati ⚠️  {errore}")

            try:
                from PyQt6 import sip
                if sip.isdeleted(self):
                    return
                self.cambiato.emit()
                self.mostra_ultimo()
            except Exception:  # noqa: BLE001
                import traceback
                print("Aggiornamenti: errore nel mostrare il risultato ⚠️")
                traceback.print_exc()
