#
#  DownloadsView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Scaricati: cosa hai a terra, e come si toglie.

LA SEZIONE STA NELLA RAIL, NON DENTRO MEDIA
--------------------------------------------
`jwl/DESIGN-SYSTEM.txt` 6.15:

    Media risponde a «cosa c'e' da vedere», Download a «cosa ho scaricato»:
    sono due domande e una sezione che risponde a una delle due e fa finta
    dell'altra e' peggio di due sezioni.

Quindi questa e' una sezione per conto suo, accanto a Multimedia, e non una
scheda dentro Multimedia.  Se stesse dentro Media, Media risponderebbe a due
domande diverse e a meta' delle volte mostrerebbe la lista sbagliata.

LA LISTA VIENE DAL DISCO, NON DALL'INDICE
-----------------------------------------
Sempre 6.15:

    La lista viene dal DISCO, non da `library.db`.  L'indice sa che cosa si
    puo' scaricare; qui si vuole sapere che cosa c'e'.

Il motivo e' che un pacchetto messo a mano col copia e incolla e' scaricato
esattamente come uno preso dall'app, e una lista che guarda l'indice non lo
mostra.  Il nome della cartella lo da' il disco, e il titolo lo dice il .db
che sta dentro il pacchetto: non c'e' niente da indovinare.

IL PULSANTE TOGLIE IL FILE, NON LA RIGA
---------------------------------------
Di nuovo 6.15:

    `cancella()` cancella il FILE.  Se togliesse solo la riga dall'elenco,
    al riavvio la riga ricomparirebbe e sembrerebbe che il tasto non abbia
    fatto niente.

Quindi il cestino cancella la cartella del pacchetto dal disco, e poi la
riga sparisce perche' non c'e' piu' niente da guardare — non perche' qualcuno
l'ha tolta da una lista.

IL CESTINO CHIEDE CONFERMA
-------------------------
La specifica non ne parla, e qui chiede comunque.  Sono 160 MB e non tornano
indietro: il pulsante e' a due passi dalla riga, a mezza riga dalla seconda,
e un tasto che cancella mezzo gigabyte senza chiedere e' un tasto che un
giorno cancella il pacchetto sbagliato.  Il resto della sezione e' identico a
come lo descrive la specifica: cambia solo che qui, prima, si domanda.

APRIRE LA RIGA
--------------
Premere la riga apre la pubblicazione, come in tutte le altre sezioni.  Se ha
tracce audio o video, non parte il pacchetto: parte la scheda dei media,
perche' e' quello che l'utente voleva guardando una pubblicazione che sa di
avere dei media.  La regola e' una sola e vale anche per i Preferiti nella
Home: solo testo -> il pacchetto, audio -> la scheda Audio, video -> la scheda
Video.

I MEDIA SI CONTANO SUL DISCO, NON AL SERVER
--------------------------------------------
Dentro il pacchetto c'e' la tabella ``Multimedia`` col mimetype e il nome del
file di ogni traccia.  Chiedere al server significherebbe una richiesta per
ogni riga a ogni apertura della sezione, per sapere una cosa che e' gia'
scritta su disco.  E la risposta del server non cambierebbe: il pacchetto e'
quello che e' a terra, quindi i media che contiene sono quelli che ci sono.

E SI CONTANO I FILE, NON LE RIGHE DEL DATABASE
----------------------------------------------
La tabella ``Multimedia`` della Bibbia per lo studio elenca 105 video e il
pacchetto non contiene nessun ``.mp4``.  Contando le righe, la riga direbbe
«105 video, il clic apre il video» e il clic aprirebbe una scheda vuota.

IL CONTEGGIO E LA REGOLA STANNO IN UN POSTO SOLO
-------------------------------------------------
`JWPubManager.media_nella_cartella`, `JWPubManager.media_sul_disco` e
`JWPubManager.che_cosa_apre`.  Anche i Preferiti della Home usano quelle, e un
Preferito puo' essere la stessa pubblicazione che sta in questa lista: con due
copie della regola, la stessa pubblicazione aprirebbe una cosa qui e un'altra
li', senza che ci sia un modo di capire quale sia quella giusta.
"""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Utility import Copertine, JWPubManager, MediaScaricati, Preferiti, Traduzioni, tema
from Utility.Stuff import icon
from Utility.Structures.Generals import Publication

#: Il colore del cestino.  Il tema cambia il fondo, ma il viola resta quello.
CHIARO = "#f2f2f2"

# I GRUPPI, GLI STESSI DELLA SEZIONE PUBBLICAZIONI
# -------------------------------------------------
# Gli stessi cinque, con gli stessi numeri di `publicationTypeId`, perche' la
# sezione dei scaricati e' la stessa lista con dentro un'altra cosa: le opere
# che hai gia' invece di tutte.  Se i gruppi fossero diversi, un titolo
# passerebbe da "Libri" a "Altro" passando da una sezione all'altra, e non ci
# sarebbe un modo di capire se e' cambiato il gruppo o l'elenco.
GRUPPI = (
    (2, "Libri"),
    (4, "Opuscoli"),
    (14, "Torre di Guardia"),
    (13, "Svegliatevi!"),
    (30, "Guida per l'adunanza"),
)

#: Il tipo che NON c'e' in nessuno dei cinque gruppi.  La Bibbia per lo studio
#: e' tipo 1 e non sta da nessuna parte: e' l'unico pacchetto scaricato che
#: finirebbe in "Altro".  Non si aggiunge un sesto gruppo "Bibbia" perche' la
#: sezione Bibbia e' gia' un'altra cosa, e mettere qui la Bibbia ripeterebbe
#: quello che e' gia' nella rail.
GRUPPO_ALTRO = (0, "Altro")


def gruppo_di(sigla: str, cartella: Path) -> tuple[int, str]:
    """Il gruppo in cui mettere questa pubblicazione.

    PRIMA SI CHIEDE AL CATALOGO
    ---------------------------
    Il catalogo ha la colonna `publicationTypeId`, che e' esattamente il numero
    che `GRUPPI` usa, e la richiesta costa niente: c'e' un indice sulla tabella
    e la risposta arriva in 0,0 ms (misurato su tre simboli).

    IL CATALOGO PUO' NON ESSERCI
    ----------------------------
    Senza catalogo non c'e' l'elenco delle pubblicazioni, e questa sezione
    funziona lo stesso perche' guarda il disco.  In quel caso si legge il
    pacchetto, che ha `PublicationType` con una parola.

    I TRE TIPI DEL PACCHETTO SONO STATI MISURATI
    -------------------------------------------
    Nei pacchetti scaricati ci sono `Bible`, `Book` e `Brochure`.  Non ce ne
    sono altri da verificare, quindi gli altri non si traducono: finiscono in
    "Altro" e si dice che sono in "Altro".  Inventare una traduzione per una
    parola che non si e' mai vista e' scrivere una regola che sembra sapere
    cose che non sa.
    """
    # La CLASSE, non il modulo: `from Utility import DBManager` porta dentro
    # il modulo, e `DBManager.tipo_pubblicazione` su un modulo non esiste.  La
    # classe si importa dal modulo.
    from Utility.DBManager import DBManager as _Catalogo

    try:
        riga = _Catalogo.tipo_pubblicazione(sigla)
    except Exception:  # noqa: BLE001
        riga = None
    if riga:
        for numero, etichetta in GRUPPI + (GRUPPO_ALTRO,):
            if numero == riga:
                return numero, etichetta
        return GRUPPO_ALTRO

    # il pacchetto: la parola, se c'e' una corrispondenza verificata
    parola = JWPubManager.tipo_nel_pacchetto(cartella)
    tradotto = {"Bible": 1, "Book": 2, "Brochure": 4}.get(parola or "")
    if tradotto is not None:
        for numero, etichetta in GRUPPI + (GRUPPO_ALTRO,):
            if numero == tradotto:
                return numero, etichetta
    return GRUPPO_ALTRO


class _TitoloGruppo(QLabel):
    """Il nome di un gruppo, con quante pubblicazioni ha.

    Come i titoli dei gruppi della sezione Pubblicazioni: piccolo, grassetto,
    con il numero accanto, cosi' si vede subito se un gruppo e' vuoto prima
    ancora di leggerne il nome.
    """

    def __init__(self, testo: str, parent=None) -> None:
        super().__init__(testo, parent)
        self.setObjectName("titoloGruppo")
        self.setStyleSheet("font-size: 13px; font-weight: 600;")


def _copertina(pub: Publication):
    """La copertina che e' gia' sul disco o in cache, o None.  Mai la rete.

    Prima si chiedeva alla rete, una richiesta dopo l'altra, mentre la finestra
    si costruiva: 11 copertine mancanti erano 3,7 secondi di splash ferma.  Qui
    si legge solo quello che c'e'; le mancanti le scarica `_copertina_in_background`.

    La taglia e' ``xs`` e non ``sm``: il server risponde 403 su ``sm`` per i
    libri, quindi un ``sm`` qui sarebbe una richiesta che fallisce sempre.
    """
    try:
        dati = Copertine.dati_gia_in_cache(pub, "xs")
        return Copertine.pixmap_da_dati(dati) if dati else None
    except Exception:  # noqa: BLE001
        # Una copertina mancante non e' un motivo per far cadere la sezione:
        # si mostra la riga senza immagine.
        return None


def _copertina_in_background(miniatura: QLabel, pub: Publication) -> None:
    """Scarica la copertina mancante senza bloccare la finestra.

    Con la modalita' Offline accesa non si va in rete da soli.
    """
    from Utility import Aggiornamenti
    from Utility.Extensions.Ext_DispatchQueue import background

    if not Aggiornamenti.automatici():
        return
    tenuto: list = [None]

    def scarica() -> None:
        try:
            tenuto[0] = Copertine.dati_copertina(pub, "xs")
        except Exception:  # noqa: BLE001
            tenuto[0] = None

    def pronto() -> None:
        if not tenuto[0]:
            return
        pixmap = Copertine.pixmap_da_dati(tenuto[0])
        try:
            if pixmap is not None and not pixmap.isNull():
                miniatura.setPixmap(Copertine.pixmap_quadrata(pixmap, 44))
        except RuntimeError:
            pass  # la riga e' stata ricostruita nel frattempo

    background(scarica, completion=pronto)


# ---------------------------------------------------------------------------
# IL MENU' DEI TRE PUNTINI
# ---------------------------------------------------------------------------
#
# Sta qui e non in un modulo nuovo perche' e' il posto dove la riga e', e la
# Home lo importa.  Se fosse in un terzo file, i due posti che hanno le stesse
# voci avrebbero due costruzioni del menu' e due elenchi di azioni da
# aggiornare insieme: e' il modo piu' economico che ci sia perche' una voce
# finisca in una schermata e non nell'altra.
#
# L'ORDINE E' QUELLO CHIESTO
# ---------------------------
#     Metti / Rimuovi dai Preferiti
#     ---------
#     Condividi  ->  Condividi file
#                    Condividi URL
#     ---------
#     Elimina
#
# "Rimuovi dai Preferiti" e "Elimina" sono separati da "Condividi" e non
# stanno dentro il suo sotto-menu, perche' non hanno niente a che fare con la
# condivisione: togliere un Preferito non toglie il pacchetto dal disco, e
# cancellare il pacchetto non toglie il Preferito.  Sono tre cose diverse su
# tre righe diverse, e metterne due dentro un sotto-menu di una terza direbbe
# che appartengono a quella terza cosa.

def menu_operazione(padre, cartella: Path, sigla: str, lingua: str,
                    preferito: bool, eliminata, preferiti_cambiati, messaggio,
                    con_cestino: bool = True, traccia=None, formato: str = "",
                    titolo: str = "") -> None:
    """Apre il menu' delle tre voci sulla pubblicazione ``sigla``.

    :param cartella: la cartella del pacchetto sul disco
    :param preferito: se la pubblicazione e' gia' fra i Preferiti
    :param eliminata: da chiamare quando il pacchetto e' stato cancellato
    :param con_cestino: False toglie la voce "Elimina".  Serve per la Home,
        dove la card non ha un pacchetto proprio e la cancellazione viene
       Offerta solo per quello che e' scaricato.
    :param traccia: il numero della traccia per una card dei media, o None
        per la pubblicazione intera.  E' la voce che rende «questo video» un
        Preferito diverso da «questa pubblicazione».
    :param formato: ``"VIDEO"`` o ``"AUDIO"`` per una traccia
    :param titolo: il titolo da scrivere nel Preferito; per una traccia e'
        quello della traccia, che non e' il titolo della pubblicazione.

    ELIMINARE NON TOCCA I PREFERITI
    ------------------------------
    Sono due liste diverse: `Preferiti` e' un file di nomi, il pacchetto e'
    una cartella.  Cancellare il pacchetto lascia il nome nel file dei
    Preferiti, e la card resta nella Home con la copertina presa dal sito.
    Il contrario e' vero: togliere dai Preferiti lascia il pacchetto sul disco,
    e compare di nuovo nella sezione dei scaricati.
    """
    from PyQt6.QtGui import QCursor, QDesktopServices
    from PyQt6.QtWidgets import QMenu

    from Utility import Condivisione

    menu = QMenu(padre)

    # 1. i Preferiti
    if preferito:
        azione = menu.addAction("Rimuovi dai Preferiti")
        def _togli():
            if Preferiti.togli(sigla, lingua, traccia):
                messaggio("Togliuto dai Preferiti")
            preferiti_cambiati()
        azione.triggered.connect(_togli)
    else:
        azione = menu.addAction("Metti nei Preferiti")
        def _metti():
            Preferiti.aggiungi(_pub_da_sigla(sigla, lingua),
                               traccia=traccia, formato=formato, titolo=titolo)
            messaggio(f"«{titolo or sigla}» fra i Preferiti")
            preferiti_cambiati()
        azione.triggered.connect(_metti)

    if traccia and str(formato).upper() in ("VIDEO", "AUDIO"):
        _voce_playlist(menu, padre, sigla, lingua, traccia, formato, titolo, messaggio)

    menu.addSeparator()

    # 2. la condivisione
    condividi = menu.addMenu("Condividi")
    voce_file = condividi.addAction("Condividi file")
    voce_url = condividi.addAction("Condividi URL")

    def _file():
        fatto, testo = Condivisione.condividi_file(cartella, padre)
        messaggio(testo)
    voce_file.triggered.connect(_file)

    url = Condivisione.url_pubblicazione(cartella, sigla) if cartella else None
    voce_url.setEnabled(bool(url))
    if url:
        def _url():
            from PyQt6.QtCore import QUrl
            if QDesktopServices.openUrl(QUrl(url)):
                messaggio(f"Aperto nel sito: {url}")
            else:
                # Il browser c'e' ma non parte: si mette l'indirizzo sulla
                # lavagnetta, che e' l'unica cosa che si puo' fare.
                from PyQt6.QtWidgets import QApplication
                appoggio = QApplication.instance()
                if appoggio is not None:
                    appoggio.clipboard().setText(url)
                messaggio(f"Copiato l'indirizzo: {url}")
        voce_url.triggered.connect(_url)

    if con_cestino:
        menu.addSeparator()
        azione = menu.addAction("Elimina")
        def _elimina():
            _chiedi_elimina(padre, cartella, eliminata, messaggio)
        azione.triggered.connect(_elimina)

    # Il menu' appare dove sta il mouse, e non sotto il bottone: e' un
    # menu' di sistema e i programmi di finestre lo mettono cosi'.  Usare la
    # posizione del bottone funzionerebbe uguale, con un pezzo di codice in
    # piu' per calcolarla.
    menu.exec(QCursor.pos())


def _voce_playlist(menu, padre, sigla, lingua, traccia, formato, titolo, messaggio) -> None:
    """Il sottomenu «Aggiungi alla playlist»: le playlist che ci sono, e una nuova."""
    from Utility import MediaScaricati
    from Utility.UserData import PlaylistManager as PM

    sotto = menu.addMenu("Aggiungi alla playlist")

    def aggiungi(tag_id) -> None:
        file = MediaScaricati.file_di(sigla, lingua, traccia, formato)
        if file is None:
            messaggio("Scarica prima il file: una playlist suona quello che c'e'.")
            return
        tipo = PM.AUDIO if str(formato).upper() == "AUDIO" else PM.VIDEO
        if PM.aggiungi(tag_id, file, titolo or file.stem, tipo) is not None:
            messaggio("Aggiunto alla playlist")

    for p in PM.playlist():
        azione = sotto.addAction(p["nome"])
        azione.triggered.connect(lambda _=False, i=p["id"]: aggiungi(i))
    if sotto.actions():
        sotto.addSeparator()
    nuova = sotto.addAction("Nuova playlist…")

    def crea() -> None:
        from SubViews.PlaylistView import chiedi_testo
        nome = chiedi_testo(padre, "Nome della nuova playlist")
        tag_id = PM.crea(nome) if nome else None
        if tag_id is not None:
            aggiungi(tag_id)

    nuova.triggered.connect(crea)


def _pub_da_sigla(sigla: str, lingua: str):
    """Una ``Publication`` con la sigla e la lingua: basta per un Preferito."""
    from Utility import Lingua
    from Utility.Structures.Generals import Publication

    return Publication(ID=0, keySymbol=sigla, year=0,
                       mepsLanguageId=Lingua.da_simbolo(lingua),
                       publicationTypeId=0, issueTagNumber=0, title=sigla)


def _chiedi_elimina(padre, cartella: Path, eliminata, messaggio) -> None:
    """Chiede e poi cancella il pacchetto.  Non tocca i Preferiti."""
    peso = JWPubManager.peso(cartella) / (1024 * 1024)
    risposta = QMessageBox.question(
        padre, "Eliminare la pubblicazione?",
        f"Elimino «{cartella.name}» dal disco?\n\nSono {peso:.0f} MB.  "
        f"Il pacchetto si riscarica; il Preferito, se c'e', resta.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    if risposta != QMessageBox.StandardButton.Yes:
        return
    import shutil

    from Utility.Extensions.Ext_FileManager import get_documents_directory

    radice = str(get_documents_directory())
    if not str(cartella).startswith(radice):
        messaggio("Non elimino: e' fuori dalla cartella dei dati")
        return
    try:
        shutil.rmtree(cartella)
    except OSError as errore:
        QMessageBox.warning(padre, "Non riesco a eliminare",
                            f"Non riesco a togliere {cartella.name}:\n{errore}")
        return
    eliminata()


class _Riga(QWidget):
    """Una pubblicazione scaricata: copertina, nome, apri, menu', cestino."""

    #: Il clic sulla riga o il bottone "Apri".
    #: (Publication, "pubblicazione" | "audio" | "video")
    aperta = Signal(object, str)
    #: Il cestino ha tolto la cartella dal disco.
    eliminata = Signal()
    #: Il menu' ha messo o tolto un Preferito: la Home deve rileggere la
    #: sua griglia, altrimenti la stella compare qui e non li'.
    preferitiCambiati = Signal()
    #: Il menu' ha fatto qualcosa che va detto all'utente.
    messaggio = Signal(str)

    def __init__(self, cartella: Path, pub: Publication | None, apri: str,
                 preferito: bool, audio: int, video: int, padre=None) -> None:
        super().__init__(padre)
        tema.sfondo(self, "rigaAggiornamento")
        self.cartella = cartella
        self.pub = pub
        self._apri = apri

        nome_visuale = pub.title if (pub and pub.title) else cartella.name

        disposizione = QHBoxLayout(self)
        disposizione.setContentsMargins(12, 10, 12, 10)
        disposizione.setSpacing(12)

        if pub is not None:
            copertina = _copertina(pub)
            if copertina is not None:
                miniatura = QLabel(self)
                miniatura.setPixmap(Copertine.pixmap_quadrata(copertina, 44))
                miniatura.setFixedSize(44, 44)
                miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
                miniatura.setObjectName("miniatura")
                disposizione.addWidget(miniatura, 0)
            else:
                # la copertina arriva dopo, senza fermare la finestra
                miniatura = QLabel(self)
                miniatura.setFixedSize(44, 44)
                miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
                miniatura.setObjectName("miniatura")
                disposizione.addWidget(miniatura, 0)
                _copertina_in_background(miniatura, pub)

        testo = QWidget(self)
        colonna = QVBoxLayout(testo)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(2)

        # IL NOME, E LA STELLA DEI PREFERITI
        #
        # Nella lista delle scaricate non ci sono le righe da confrontare, e
        # quindi non si vede nulla che dica se un titolo e' fra i Preferiti o
        # no.  La stella dice solo quello.
        #
        # STA A SINISTRA DEL NOME, E NON DOPO
        # ------------------------------------
        # Prima stava in fondo alla riga del nome.  Il nome e' la prima riga
        # della colonna di testo e il dettaglio ne segue due, quindi la stella
        # in fondo restava a un terzo dell'altezza della riga: non allineata
        # col titolo e non col dettaglio, e in mezzo fra il nome e il cestino.
        # Sembrava un elemento messo li' per sbaglio.
        #
        # A sinistra del nome e' allineata con la prima riga, che e' quella
        # che si legge, ed e' dove la stella sta nella lista delle
        # pubblicazioni: due sezioni, due schemi diversi perche' le righe sono
        # diverse, ma la stessa parte della riga per il segno che e' la stessa
        # cosa.
        riga_nome = QHBoxLayout()
        riga_nome.setContentsMargins(0, 0, 0, 0)
        riga_nome.setSpacing(6)

        if preferito:
            stella = QLabel(testo)
            stella.setPixmap(icon("star.fill", tema.ORO_PREFERITO, 16).pixmap(16, 16))
            stella.setToolTip("Fra i Preferiti")
            stella.setFixedSize(16, 16)
            riga_nome.addWidget(stella, 0)

        nome = QLabel(nome_visuale, testo)
        nome.setObjectName("titoloRiga")
        nome.setWordWrap(True)
        riga_nome.addWidget(nome, 1)

        colonna.addLayout(riga_nome)

        sigla = QLabel(pub.keySymbol if pub else cartella.name, testo)
        sigla.setObjectName("nota")
        colonna.addWidget(sigla)

        dettaglio = QLabel(self._dettaglio(cartella, apri, audio, video), testo)
        dettaglio.setObjectName("nota")
        dettaglio.setWordWrap(True)
        colonna.addWidget(dettaglio)

        disposizione.addWidget(testo, 1)

        # IL BOTTONE CHE APRE
        #
        # Ce n'e' uno anche se la riga si puo' premere: la riga si preme per
        # aprire, ma e' lunga 1.400 pixel e il titolo sta in fondo a sinistra,
        # quindi premere "dove si apre" significa indovinare.  Il bottone lo dice.
        self.apri = QPushButton("Apri", self)
        self.apri.setFixedWidth(60)
        self.apri.setToolTip(f"Apre {nome_visuale}")
        self.apri.clicked.connect(self._apri_ora)
        disposizione.addWidget(self.apri, 0)

        # I TRE PUNTINI
        #
        # Stanno a destra di tutto e non al posto del cestino: il cestino
        # cancella il pacchetto e non fa nient'altro, e il menu' fa anche quello
        # piu' tutto il resto.  Sono due cose diverse e non si sostituiscono.
        self.punti = QPushButton(icon("ellipsis.circle", CHIARO), "", self)
        self.punti.setFixedWidth(34)
        self.punti.setToolTip("Altre azioni")
        self.punti.clicked.connect(self._apri_menu)
        disposizione.addWidget(self.punti, 0)

        self.cestino = QPushButton(icon("trash.fill", CHIARO), "", self)
        self.cestino.setFixedWidth(34)
        self.cestino.setToolTip(f"Elimina {cartella.name} dal disco")
        self.cestino.clicked.connect(self._chiedi_conferma)
        disposizione.addWidget(self.cestino, 0)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        testo.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------

    def _apri_ora(self) -> None:
        """Il bottone "Apri".  Stessa cosa che preme la riga."""
        if self.pub is not None:
            self.aperta.emit(self.pub, self._apri)

    def _apri_menu(self) -> None:
        """Il menu' dei tre puntini."""
        menu_operazione(
            self, self.cartella,
            self.pub.keySymbol if self.pub else self.cartella.name,
            Preferiti._lingua(self.pub) if self.pub else "I",
            preferito=self.pub is not None and Preferiti.c_e_(
                self.pub.keySymbol, Preferiti._lingua(self.pub)),
            eliminata=self.eliminata.emit,
            preferiti_cambiati=self.preferitiCambiati.emit,
            messaggio=self.messaggio.emit)

    # ------------------------------------------------------------------

    def _dettaglio(self, cartella: Path, apri: str,
                   audio: int, video: int) -> str:
        """I byte sul disco, quando, e che cosa apre il clic."""
        pezzi = [f"{JWPubManager.peso(cartella) / (1024 * 1024):.0f} MB sul disco"]
        try:
            quando = time.strftime("%d/%m/%Y",
                                   time.localtime(cartella.stat().st_mtime))
            pezzi.append(f"del {quando}")
        except OSError:
            pass
        if video:
            pezzi.append(f"{video} video")
        if audio:
            pezzi.append(f"{audio} audio")
        pezzi.append({"audio": "il clic apre l'audio",
                      "video": "il clic apre il video",
                      "pubblicazione": "il clic apre la pubblicazione"}[apri])
        return " · ".join(pezzi)

    def _chiedi_conferma(self) -> None:
        """Il cestino: chiede, poi cancella il pacchetto.

        NON TOCCA I PREFERITI
        ---------------------
        Sono due liste diverse e separate di proposito: `Preferiti` e' un file
        di nomi dentro la cartella dei dati, il pacchetto e' una cartella
        accanto.  Cancellare il pacchetto lascia il nome nel file dei
        Preferiti, e la card resta nella Home.  E il contrario: togliere dai
        Preferiti lascia il pacchetto sul disco, e la riga resta qui.

        Il perche' e' una cosa sola e non due: un Preferito che sparisce quando
        cancelli 161 MB per liberare spazio e' una cosa che l'utente cerca per
        un pezzo di ritorno e non piu'.  Il pacchetto si riscarica; la lista
        dei Preferiti no.

        IL TESTO UNICO DELLA CONFERMA
        ------------------------------
        La conferma e' quella di `_chiedi_elimina`, la stessa del menu' dei
        tre puntini.  Prima qui ce n'era una copia, e le due dicevano cose
        diverse: il cestino prometteva che i segnalibri restano, il menu' no.
        Due testi per la stessa cancellazione, e quello che si legge dipende da
        dove hai premuto.
        """
        _chiedi_elimina(self, self.cartella, self._cancellata, self.messaggio.emit)

    def _cancellata(self) -> None:
        """La cartella e' stata tolta: la riga sparisce e la lista si rifa."""
        self.deleteLater()
        self.eliminata.emit()

    def mousePressEvent(self, evento) -> None:
        """Il clic apre.  Solo il sinistro: il destro e' della lista."""
        if (evento.button() != Qt.MouseButton.LeftButton
                or self.pub is None):
            return super().mousePressEvent(evento)
        # Il cestino e' figlio di questa riga, quindi le sue coordinate sono
        # gia' nelle coordinate della riga.  Se il clic e' partito da li' il
        # bottone ha gia' fatto il suo lavoro e il testo non deve aprire niente.
        if self.cestino.geometry().contains(evento.position().toPoint()):
            return super().mousePressEvent(evento)
        self.aperta.emit(self.pub, self._apri)


class _RigaMedia(QWidget):
    """Un video o un audio scaricato: glifo, titolo, dettaglio, cestino.

    PERCHE' UNA RIGA DIVERSA E NON `_Riga` RIUSATA
    -----------------------------------------------
    `_Riga` mostra una pubblicazione scaricata, e una pubblicazione e' una
    cartella: il nome viene dal pacchetto, il peso e' la somma di tutto, e il
    cestino chiede prima di togliere una cartella con dentro i segnalibri.

    Un video scaricato e' un **file sciolto**.  Non c'e' una cartella da
    aprire, non ci sono segnalibri da proteggere, e il peso e' quello del
    file.  Riutilizzare `_Riga` avrebbe voluto dire far finta che sia un
    pacchetto: la riga avrebbe detto che il video si puo' toccare come un
    pacchetto, e la conferma avrebbe detto una cosa diversa da quello che il
    cestino fa.

    IL FILE PUO' ESSERE STATO MESSO LI' A MANO
    -------------------------------------------
    La sezione mostra quello che c'e' sul disco, da **qualunque parte** venga:
    la nuvoletta della Home, o un file copiato dentro la cartella dei dati da
    fuori.  Per l'utente e' la stessa cosa — l'ha scaricato lui — e dividerli
    sarebbe inventare due categorie che su un disco non hanno un segno per
    essere riconosciute.

    NIENTE PREFERITI E NIENTE MENU' DEI TRE PUNTINI
    -------------------------------------------------
    Un Preferito e' il nome di una **pubblicazione**, e un file sciolto non e'
    un pacchetto: la card della stessa pubblicazione e' gia' nella Home, con
    la sua nuvoletta.  Quindi qui non c'e' il menu', ma solo il cestino, che
    chiede e cancella il file.
    """

    #: Il clic sulla riga o il bottone "Apri": (percorso, titolo).
    aperto = Signal(object, str)
    #: Il cestino ha tolto il file dal disco.
    eliminato = Signal()
    #: Qualcosa che va detto all'utente.
    messaggio = Signal(str)

    def __init__(self, voce: dict, padre=None) -> None:
        super().__init__(padre)
        tema.sfondo(self, "rigaAggiornamento")
        self._voce = voce
        self._file: Path = voce["file"]
        self._titolo = voce.get("titolo") or self._file.name

        disposizione = QHBoxLayout(self)
        disposizione.setContentsMargins(12, 10, 12, 10)
        disposizione.setSpacing(12)

        # Il glifo dice che cosa si aprira': per un video il film, per un
        # audio una nota.  La miniatura vera non c'e': il file sciolto non ha
        # una copertina, e chiederla al catalogo vorrebbe dire che la riga ha
        # una rete a cui chiedere, che non e' detto.
        glifo = QLabel(self)
        nome_glifo = ("film" if voce.get("formato") == "VIDEO"
                      else "music.note")
        glifo.setPixmap(icon(nome_glifo, "#8a8a8a", 44).pixmap(44, 44))
        glifo.setFixedSize(44, 44)
        glifo.setObjectName("miniatura")
        disposizione.addWidget(glifo, 0)

        testo = QWidget(self)
        colonna = QVBoxLayout(testo)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(2)

        nome = QLabel(self._titolo, testo)
        nome.setObjectName("titoloRiga")
        nome.setWordWrap(True)
        colonna.addWidget(nome)

        dettaglio = QLabel(self._dettaglio(), testo)
        dettaglio.setObjectName("nota")
        dettaglio.setWordWrap(True)
        colonna.addWidget(dettaglio)

        disposizione.addWidget(testo, 1)

        self.apri = QPushButton("Apri", self)
        self.apri.setFixedWidth(60)
        self.apri.setToolTip(f"Suona {self._titolo}")
        self.apri.clicked.connect(self._apri_ora)
        disposizione.addWidget(self.apri, 0)

        self.cestino = QPushButton(icon("trash.fill", CHIARO), "", self)
        self.cestino.setFixedWidth(34)
        self.cestino.setToolTip(f"Elimina {self._file.name} dal disco")
        self.cestino.clicked.connect(self._chiedi_conferma)
        disposizione.addWidget(self.cestino, 0)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        testo.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------

    def _dettaglio(self) -> str:
        """La sigla, la risoluzione e il peso, che stanno nel nome del file."""
        pezzi = [self._voce["sigla"]]
        if self._voce.get("risoluzione"):
            pezzi.append(self._voce["risoluzione"])
        pezzi.append(f"{self._voce.get('peso', 0) / (1024 * 1024):.0f} MB")
        return " · ".join(pezzi)

    def _apri_ora(self) -> None:
        """Il bottone "Apri".  Stessa cosa che preme la riga."""
        self.aperto.emit(self._file, self._titolo)

    def _chiedi_conferma(self) -> None:
        """Il cestino: chiede, poi cancella il file sciolto."""
        risposta = QMessageBox.question(
            self, "Eliminare il video?",
            f"Elimino «{self._file.name}» dal disco?\n\n"
            f"Sono {self._voce.get('peso', 0) / (1024 * 1024):.0f} MB.  "
            f"Si riscarica con la nuvoletta della card.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if risposta != QMessageBox.StandardButton.Yes:
            return

        from Utility.Extensions.Ext_FileManager import get_documents_directory

        radice = str(get_documents_directory())
        if not str(self._file).startswith(radice):
            self.messaggio.emit("Non elimino: e' fuori dalla cartella dei dati")
            return
        try:
            self._file.unlink()
        except OSError as errore:
            QMessageBox.warning(self, "Non riesco a eliminare",
                                f"Non riesco a togliere {self._file.name}:\n"
                                f"{errore}")
            return
        self.eliminato.emit()

    def mousePressEvent(self, evento) -> None:
        """Il clic apre.  Il cestino ha gia' fatto il suo, se il clic l'ha
        toccato."""
        if evento.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(evento)
        if self.cestino.geometry().contains(evento.position().toPoint()):
            return super().mousePressEvent(evento)
        self.aperto.emit(self._file, self._titolo)


class _RigaTraduzione(QWidget):
    """Una Bibbia scaricata in un'altra lingua: nome, capitoli, peso e cestino."""

    eliminata = Signal()

    def __init__(self, voce: dict, padre=None) -> None:
        super().__init__(padre)
        tema.sfondo(self, "rigaAggiornamento")
        self._voce = voce
        disposizione = QHBoxLayout(self)
        disposizione.setContentsMargins(12, 10, 12, 10)
        disposizione.setSpacing(12)
        glifo = QLabel(self)
        glifo.setPixmap(icon("book", "#8a8a8a", 44).pixmap(44, 44))
        glifo.setFixedSize(44, 44)
        disposizione.addWidget(glifo, 0)
        colonna = QVBoxLayout()
        colonna.setSpacing(2)
        nome = QLabel(f"Bibbia — {voce['nome']}", self)
        nome.setObjectName("titoloRiga")
        dettaglio = QLabel(
            f"{voce['capitoli']} capitoli · {voce['byte'] / (1024 * 1024):.1f} MB", self)
        dettaglio.setObjectName("nota")
        colonna.addWidget(nome)
        colonna.addWidget(dettaglio)
        disposizione.addLayout(colonna, 1)
        cestino = QPushButton(icon("trash.fill", CHIARO), "", self)
        cestino.setFixedWidth(34)
        cestino.setToolTip(f"Elimina la Bibbia in {voce['nome']}")
        cestino.clicked.connect(self._chiedi)
        disposizione.addWidget(cestino, 0)

    def _chiedi(self) -> None:
        from SubViews.Conferma import ConfermaApp

        ConfermaApp.chiedi(
            self.window(), "Eliminare la Bibbia?",
            f"Elimino dal disco la Bibbia in {self._voce['nome']} "
            f"({self._voce['capitoli']} capitoli).\n\nSi puo' riscaricare quando vuoi.",
            "Elimina", self._elimina)

    def _elimina(self) -> None:
        from Utility import Traduzioni

        Traduzioni.elimina(self._voce["simbolo"])
        self.eliminata.emit()


class DownloadsView(QWidget):
    """Scaricati: cosa hai a terra."""

    messaggio = Signal(str)
    #: L'utente ha premuto una riga: (pubblicazione, che cosa aprire)
    aperta = Signal(object, str)
    #: Un video sciolto (file sul disco, senza pacchetto) si deve suonare:
    #: (percorso, titolo).  La sezione non ha un lettore suo, lo ha la
    #: sezione Multimedia, quindi qui si chiede.
    mediaAperto = Signal(object, str)
    #: Una riga e' stata eliminata dal disco
    eliminata = Signal()
    #: Un Preferito e' stato messo o tolto dal menu' dei tre puntini
    preferitiCambiati = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._righe: list[_Riga] = []

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)

        pagina = QWidget()
        disposizione = QVBoxLayout(pagina)
        disposizione.setContentsMargins(18, 16, 18, 16)
        disposizione.setSpacing(0)
        disposizione.setAlignment(Qt.AlignmentFlag.AlignTop)

        titolo = QLabel("Scaricati", pagina)
        titolo.setObjectName("titoloPagina")
        disposizione.addWidget(titolo)

        self.stato = QLabel("", pagina)
        self.stato.setObjectName("nota")
        self.stato.setWordWrap(True)
        disposizione.addWidget(self.stato)
        disposizione.addSpacing(16)

        self.contenitore = QWidget(pagina)
        self._colonna = QVBoxLayout(self.contenitore)
        self._colonna.setContentsMargins(0, 0, 0, 0)
        self._colonna.setSpacing(10)
        self._colonna.setAlignment(Qt.AlignmentFlag.AlignTop)
        disposizione.addWidget(self.contenitore)

        area.setWidget(pagina)
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.addWidget(area)

        self.ricostruisci()

    # ------------------------------------------------------------------

    def ricostruisci(self) -> None:
        """La lista, riletta da capo e RAGGRUPPATA per categoria.

        IL GRUPPO LO STESSO DELLA SEZIONE PUBBLICAZIONI
        ------------------------------------------------
        Gli stessi cinque gruppi e nello stesso ordine, con gli stessi numeri
        di `publicationTypeId`.  Non e' una scelta estetica: e' quello che
        permette di passare dalla sezione delle pubblicazioni a quella dei
        scaricati e ritrovare un titolo nello stesso posto.  Con gruppi
        diversi, «Cantiamo a Geova» starebbe sotto "Libri" da una parte e
        sotto "Altro" dall'altra, e non ci sarebbe modo di capire se e'
        cambiato il gruppo o l'elenco.

        LA BIBBIA FINISCE IN "ALTRO"
        -----------------------------
        Il pacchetto della Bibbia per lo studio e' tipo 1, e il tipo 1 non e'
        in nessuno dei cinque gruppi: nella sezione Pubblicazioni la Bibbia
        non c'e' perche' ha una sezione tutta sua.  Qui finisce in "Altro",
        che e' visibile e non mente.  Non si aggiunge un gruppo "Bibbia"
        perche' ripeterebbe nella lista dei scaricati quello che la rail gia'
        dice.

        LE RIGHE VENGONO DAL DISCO, I GRUPPI DAL CATALOGO
        --------------------------------------------------
        La lista e' quella che c'e' sul disco, e resta quella anche senza
        catalogo: e' `jwl/DESIGN-SYSTEM.txt` 6.15.  Il catalogo serve solo a
        sapere in che gruppo mettere una riga, e quando non c'e' si legge il
        pacchetto.  Un pacchetto scaricato a mano col copia e incolla viene
        comunque mostrato: al massimo finisce in "Altro".
        """
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()
        self._righe = []

        cartelle = JWPubManager.scaricate()
        traduzioni = Traduzioni.scaricate()
        if not cartelle and not MediaScaricati.scaricati() and not traduzioni:
            vuoto = QLabel(
                "Nessuna pubblicazione scaricata.\n\n"
                "Si scarica dalla Home, sotto Preferiti: il download parte "
                "solo dal pulsante di ogni riga, e solo per quella riga.",
                self.contenitore)
            vuoto.setObjectName("vuoto")
            vuoto.setWordWrap(True)
            self.stato.setText("Questa sezione guarda quello che c'e' sul "
                               "disco, e non chiede niente al server.")
            self._colonna.addWidget(vuoto)
            return

        if cartelle:
            peso = sum(JWPubManager.peso(c) for c in cartelle)
            self.stato.setText(
                f"{len(cartelle)} pubblicazioni, {peso / (1024 * 1024):.0f} MB sul "
                f"disco.  Il cestino e la voce Elimina tolgono il pacchetto: i "
                f"segnalibri, le note e i Preferiti restano.")
        else:
            self.stato.setText(
                "Questa sezione guarda quello che c'e' sul disco, e non "
                "chiede niente al server.")

        # una lista per gruppo, nell'ordine di GRUPPI, e in fondo gli altri
        per_gruppo: dict[int, list] = {}
        for cartella in cartelle:
            pub = JWPubManager.leggi_pubblicazione(cartella)
            sigla = pub.keySymbol if pub else cartella.name
            numero, _etichetta = gruppo_di(sigla, cartella)
            per_gruppo.setdefault(numero, []).append((cartella, pub))

        for numero, etichetta in list(GRUPPI) + [GRUPPO_ALTRO]:
            voci = per_gruppo.get(numero)
            if not voci:
                continue
            if len(list(GRUPPI)) > 1 or numero == GRUPPO_ALTRO[0]:
                self._colonna.addSpacing(6)
            titolo = _TitoloGruppo(f"{etichetta} ({len(voci)})")
            self._colonna.addWidget(titolo)
            for cartella, pub in voci:
                audio, video = JWPubManager.media_nella_cartella(cartella)
                preferito = (pub is not None
                             and Preferiti.c_e_(pub.keySymbol,
                                                Preferiti._lingua(pub)))
                apri = JWPubManager.che_cosa_apre(
                    pub.keySymbol if pub else cartella.name,
                    Preferiti._lingua(pub) if pub else "I")
                riga = _Riga(cartella, pub, apri, preferito,
                             audio, video, self.contenitore)
                riga.aperta.connect(self.aperta.emit)
                riga.eliminata.connect(self._riga_eliminata)
                riga.preferitiCambiati.connect(self.preferitiCambiati.emit)
                riga.messaggio.connect(self.messaggio.emit)
                self._colonna.addWidget(riga)
                self._righe.append(riga)

        # I media scaricati dalla nuvoletta di una card: file sciolti nella
        # radice dei dati, senza pacchetto.  `JWPubManager.scaricate()` non li
        # vede perche' guarda le cartelle con un `contents/*.db`; la rigorosa
        # regola della sezione e' «quello che c'e' sul disco», e questi sono su
        # disco quanto i pacchetti.
        righe_media = MediaScaricati.scaricati()
        if righe_media:
            self._colonna.addSpacing(6)
            self._colonna.addWidget(_TitoloGruppo(
                f"Video e audio scaricati ({len(righe_media)})"))
            for voce in righe_media:
                riga_media = _RigaMedia(voce, self.contenitore)
                riga_media.aperto.connect(self._media_aperto)
                riga_media.eliminato.connect(self._media_eliminato)
                riga_media.messaggio.connect(self.messaggio.emit)
                self._colonna.addWidget(riga_media)
                self._righe.append(riga_media)

        if traduzioni:
            self._colonna.addSpacing(6)
            self._colonna.addWidget(_TitoloGruppo(
                f"Bibbie in altre lingue ({len(traduzioni)})"))
            for voce in traduzioni:
                riga_lingua = _RigaTraduzione(voce, self.contenitore)
                riga_lingua.eliminata.connect(self.ricostruisci)
                riga_lingua.eliminata.connect(self.eliminata.emit)
                self._colonna.addWidget(riga_lingua)
                self._righe.append(riga_lingua)

    def _media_aperto(self, percorso, titolo: str) -> None:
        """Un video scaricato e' stato premuto: parte nel lettore.

        IL MOTORE UNICO, E NON UN MOTORE NUOVO
        -------------------------------------
        Qui prima c'era `Lettore().suona(percorso, titolo)`.  `Lettore` e' la
        **classe**, non il motore: costruendone una si faceva un secondo
        player, con la sua porta audio e il suo decoder, che non ha niente a
        che fare con la finestra del programma.

        Il sintomo era che il video **non partiva**: nessuno ascoltava quel
        player, quindi nessuno sapeva che stava suonando e nessuno mostrava
        niente.  E il player, essendo stato costruito dentro una funzione che
        subito dopo tornava, veniva buttato via **mentre suonava** — e un
        `QMediaPlayer` distrutto mentre decodifica fa abortire Qt.  Misurato
        qui come programma che sparisce senza messaggio.

        `motore()` e' l'unico motore di tutto il programma: e' quello a cui
        guarda la finestra e quello che i comandi di play e posizione
        governano.  Non se ne crea un secondo perche' un video scaricato e'
        un caso particolare: e' un video.

        IL LETTORE E' COMUNQUE QUELLO DELLA SEZIONE MULTIMEDIA
        ------------------------------------------------------
        Suonare il motore unico non basta a mostrare qualcosa: il video va
        attaccato a un riquadro.  Quindi si chiede alla sezione Multimedia di
        aprirlo, che e' dove sta il lettore con play e posizione — un video
        scaricato che si sente e non si vede, e che non si puo' fermare, non
        e' un video guardato.  Vedi `SidebarView._apre_un_media_scaricato`.
        """
        try:
            from Utility.Lettore import motore

            motore().suona(percorso, titolo)
        except Exception:  # noqa: BLE001 - dentro un segnale Qt un'eccezione
            # fa `abort()` e la finestra sparisce senza lasciare traccia.
            import traceback
            print(f"Scaricati: non riesco a suonare {percorso} ⚠️")
            traceback.print_exc()
            return
        self.mediaAperto.emit(percorso, titolo)

    def _media_eliminato(self) -> None:
        """Un file sciolto e' stato tolto: la lista si rifa da capo.

        E' la stessa regola di `_riga_eliminata`: la lista viene dal disco, e
        il disco ha appena perso un file.  Rileggerlo e' il modo di essere
        sicuri che quello che c'e' adesso e quello che si vede — e la
        nuvoletta della card, che guarda lo stesso disco, ricompare perche'
        il file non c'e' piu'.
        """
        self.ricostruisci()
        self.eliminata.emit()
        self.messaggio.emit("Video eliminato dal disco")

    def _riga_eliminata(self) -> None:
        """Una riga e' stata tolta: la lista si rifa.

        Si rifa e non si toglie a mano la riga sola: la lista viene dal disco,
        e il disco ha appena perso una cartella.  Rileggerlo e' il modo di
        essere sicuri che quello che c'e' adesso e quello che si vede.
        """
        self.ricostruisci()
        self.eliminata.emit()
        self.messaggio.emit("Publicazione eliminata dal disco")
