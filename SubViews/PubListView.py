#
#  PubListView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 20/08/21.
#

"""L'elenco delle pubblicazioni, raggruppate per tipo.

Cinque gruppi, ognuno dentro una scatola che si apre e si chiude:

    Libri                 publicationTypeId  2
    Opuscoli              publicationTypeId  4
    Torre di Guardia     publicationTypeId 14
    Svegliatevi!          publicationTypeId 13
    Guida per l'adunanza  publicationTypeId 30

PERCHE' UNA TABELLA E NON UNA RIGA DI WIDGET PER VOLTA
------------------------------------------------------
La prima versione creava un ``RigaPubblicazione`` — un QWidget con dentro
tre figli — per ogni pubblicazione.  Il catalogo ne ha 3.741, quindi la
finestra costruiva **15.466 widget** e il tempo di costruzione misurato era
**1.147 millisecondi**.  Non e' un po' lento: congelava tutto, e la ricerca
non si poteva usare perche' ogni lettera scritta faceva congelare la
finestra per un secondo e un quarto.

Un widget Qt non e' una riga di una tabella: e' un oggetto con una finestra,
un layout, una geometria e un evento di disegno.  Millemila di quelli sono
un costo che non si vede finche' non si misura.

Il modo che Qt offre per questo e' la coppia modello/vista:

    QAbstractTableModel   i dati, in una lista.  Non disegna niente e non
                          crea niente: 3.741 righe sono 3.741 voci Python.
    QTableView            il disegno.  Crea un delegates SOLO per le righe
                          che si vedono, cioe' una quindicina.

Il risultato si misura: da 15.466 widget a zero, e da 1.147 ms a poco.

I TRE NUMERI DIVERSI, E LA RAGIONE
----------------------------------
``PublicationTypeId`` dice il tipo, ``IssueTagNumber`` dice il numero, e sono
due cose diverse.  Per libri e opuscoli il numero non esiste (valgono 0) e si
ordina per titolo; per i tre periodici il numero c'e' e si ordina dal piu'
recente al piu' vecchio.  Per questo i tre gruppi periodici usano
``reverse=True`` e gli altri due no.

IL PERCHE' DI UN ELENCO DI NOMI
------------------------------
I cinque gruppi sono scritti uno per uno e non generati da una tabella,
perche' i tre periodici hanno il titolo dell'uscita (``issueTitle``) e gli
altri due no.  E un elenco di nomi e' una rete con i buchi: se un giorno
c'e' un sesto tipo, non compare in nessuna parte e la sezione e' semplicemente
vuota, senza errore e senza avviso.  E' una delle trappole elencate in
COME-FUNZIONA.txt sezione 14, quindi la tabella qui sotto e' l'unico posto
da cui guardare quando manca una sezione.

COME SCENDERE ALLA SCELTA
-------------------------
Due icone per ogni pubblicazione: il cestino se il pacchetto c'e' gia' e
il pallino di download se non c'e' (o comunque per riaverlo).  Il testo
del titolo si puo' cliccare solo se il pacchetto c'e' gia': senza il testo
scaricato aprire il libro non mostrerebbe niente, quindi si lascia il titolo
in grigio e si lascia capire che manca il passo prima.
"""
from __future__ import annotations

from PyQt6.QtCore import (QAbstractTableModel, QModelIndex, QPoint, QRect, Qt,
                            QTimer, pyqtSignal as Signal)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Utility import CaricaCopertine, tema
from Utility.Extensions.Ext_FileManager import extracted_jwpub_exist, get_documents_directory
from Utility.JWPubManager import JWPubManager, pub_dir_name
from Utility.Stuff import icon

# I cinque gruppi: (tipo, etichetta, ordina per anno?)
GRUPPI = [
    (2, "Libri", False),
    (4, "Opuscoli", False),
    (14, "Torre di Guardia", True),
    (13, "Svegliatevi!", True),
    (30, "Guida per l'adunanza", True),
]

#: Il nome e l'ordinamento di **tutti** i tipi del catalogo, non solo dei cinque
#: sopra.  Serve quando l'elenco mostra una categoria sola: l'utente ha premuto
#: «Trattati» e si aspetta di vedere i trattati, ma i cinque gruppi di GRUPPI
#: non hanno una casella per il tipo 7, quindi senza questa tabella la schermata
#: mostrerebbe cinque titoli vuoti — sembrerebbe che il catalogo non abbia
#: niente, mentre ne ha 552.
#:
#: Il secondo valore dice se l'ordinamento e' per anno decrescente: e' vero
#: per i periodici e per i programmi, che sono tanti pezzi tutti dello stesso
#: nome e si distinguono per la data, e falso per tutto il resto, che si
#: ordina per titolo.
#:
#: I numeri sono quelli del catalogo di jw.org (gli stessi usati da
#: `FILTRO_CATEGORIA` in `MediaView`).  Le due tabelle dicono la stessa cosa
#: da due lati: qui come si chiama un tipo, li' a quale categoria appartiene.
TIPI = {
    1: ("Bibbie", False),
    2: ("Libri", False),
    4: ("Brochure e opuscoletti", False),
    6: ("Manuali e indici", False),
    7: ("Trattati", False),
    10: ("Materiali di insegnamento", False),
    13: ("Svegliatevi!", True),
    14: ("La Torre di Guardia", True),
    17: ("Appunti per la riunione", False),
    22: ("Approfondimenti", False),
    30: ("Guida per l'adunanza", True),
    31: ("Programmi", True),
}

# L'altezza massima della lista dentro ogni gruppo, come nell'originale
# (frame(maxHeight: 300)).
ALTEZZA_MAX = 300

LARGHEZZA_ICONA = 30
#: la colonna della copertina: quadrata, e quadrata resta
LARGHEZZA_COPERTINA = 32
ALTEZZA_RIGA = 34    # sta alla copertina, non al titolo


def scarica_pub_url(pub) -> str:
    """L'indirizzo dell'API che dice dove si scarica un .jwpub.

    La richiesta porta tre cose che devono combaciare con la riga del
    catalogo: il numero (``issue``), il simbolo (``pub``) e la lingua scritta
    (``langwritten=I``).  Se una delle tre non combacia, l'API risponde senza
    ``JWPUB`` e non si scarica niente: e' successo, ed e' la ragione per cui
    il simbolo e la lingua sono letti dalla riga del catalogo e non scritti
    a mano.
    """
    return ("https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"
            f"?issue={pub.issueTagNumber}&output=json&pub={pub.keySymbol}"
            "&fileformat=jwpub&alllangs=0&langwritten=I")


def esiste_il_pacchetto(pub) -> bool:
    """Il pacchetto e' gia' scompattato?

    Si guarda la cartella col nome del pacchetto, non il file .jwpub: il
    .jwpub viene cancellato dopo la scompatta, quindi la sua assenza non
    vuol dire niente.
    """
    return extracted_jwpub_exist(
        url=get_documents_directory() / pub_dir_name(pub)
    )


class ModelloPubblicazioni(QAbstractTableModel):
    """I dati dell'elenco: non disegna e non crea widget.

    Le tre colonne sono il titolo, il download e il cestino.  Non si mette
    un pulsante dentro una cella: un pulsante dentro una cella e' un widget
    per cella, e il problema verrebbe spostato e non risolto.  Il disegno e
    il clic li fa il delegato sotto.
    """

    COPERTINA, TITOLO, SCARICA, CANCELLA = range(4)

    #: La pubblicazione della riga.  Va in un ruolo e non in un widget,
    #: cosi' chi riceve il segnale sa di che pubblicazione si tratta senza
    #: dover cercare l'indice.
    @staticmethod
    def chiave_di(pub) -> str:
        """L'identita' di una pubblicazione, per tutto quello che si tiene
        in memoria per lei.

        PERCHE' NON IL NUMERO DI RIGA
        ------------------------------
        Prima la copertina era tenuta in un dizionario indicizzato dal
        numero di riga, e il numero di riga cambia ogni volta che si
        filtra.  Il sintomo era esattamente questo: le copertine
        comparivano, poi **altre spariscono**, poi ricompaiano a caso, e
        non tornano piu'.

        Non era un problema di disegno: era la cache che associava
        l'immagine di una pubblicazione a una posizione che, dopo una
        ricerca, conteneva un'altra pubblicazione.  Tre filtri e la
        griglia mostrava copertine sbagliate.

        La chiave mette dentro tutto quello che distingue due righe:
        sigla, lingua, anno e numero dell'uscita.  Con la sola sigla i
        periodici si confonderebbero, perche' `w` ha una riga al mese.
        """
        return (f"{getattr(pub, 'keySymbol', '')}|"
                f"{getattr(pub, 'mepsLanguageId', '')}|"
                f"{getattr(pub, 'year', '')}|"
                f"{getattr(pub, 'issueTagNumber', '')}")

    def ha_copertina(self, chiave: str) -> bool:
        """Questa copertina e' gia' in cache?

        Serve per non chiederla due volte.  Si controlla la CHIAVE e non
        la riga, e per lo stesso motivo di `chiave_di`.
        """
        return chiave in self._copertine

    RUOLO_PUB = int(Qt.ItemDataRole.UserRole) + 1
    RUOLO_ESISTE = int(Qt.ItemDataRole.UserRole) + 2
    RUOLO_COPERTINA = int(Qt.ItemDataRole.UserRole) + 3
    #: Questa pubblicazione e' fra i Preferiti?
    #:
    #: Un ruolo suo e non una colonna, perche' non e' una colonna: e' un
    #: segno accanto al titolo, e una colonna per un segno sposterebbe i
    #: titoli di due caratteri per dire una cosa che si può dire in un segno.
    #:
    #: Il delegato lo chiede qui, e non chiama `Preferiti.c_e_` per ogni riga:
    #: con 3.741 righe quello sarebbe 3.741 letture di un file, dentro il
    #: disegno.  Qui si legge una volta sola, in `reset`, e il risultato sta in
    #: una lista come quella degli esistenti.
    RUOLO_PREFERITO = int(Qt.ItemDataRole.UserRole) + 4

    def __init__(self, pubblicazioni: list, padre=None) -> None:
        super().__init__(padre)
        self.pubblicazioni = list(pubblicazioni)
        self.esistono = [esiste_il_pacchetto(p) for p in self.pubblicazioni]
        self.preferiti: list[bool] = []
        # Quali sono fra i Preferiti.  Si legge UNA volta qui, non nel `data()`
        # che il delegato chiama per ogni cella.
        #
        # Il motivo e' il numero: sono 3.741 righe, e `data()` viene chiamato
        # molte volte anche per le righe che non si vedono.  Leggere il file
        # dei Preferiti li' dentro significa 3.741 aperture di file dentro il
        # disegno, e il risultato e' una finestra che si blocca.
        self.preferiti = [self._e_preferito(p) for p in self.pubblicazioni]
        # Le copertine gia' chieste, per non chiederle due volte alla
        # stessa pubblicazione.  Il ``data()`` del modello viene chiamato
        # molte volte per ogni cella, anche per una che non si vede: senza
        # questa cache ogni ridisegno riscaricherebbe la stessa immagine.
        # Le copertine in cache, per CHIAVE DI PUBBLICAZIONE e non per
        # numero di riga.  Vedi `chiave_di` perche' la differenza si vede.
        self._copertine: dict[str, object] = {}

    @staticmethod
    def _e_preferito(pub) -> bool:
        """Questa pubblicazione e' fra i Preferiti?

        Va chiamata una volta per pubblicazione, non per ogni disegno: vedi
        la nota sopra `self.preferiti`.

        Se il file dei Preferiti non si puo' leggere la risposta e' False.
        Non e' un caso da nascondere: una stella che c'e' quando non dovrebbe
        fare piu' danno di una stella che manca, e il rovescio e' il caso
        peggiore perche' un Preferito che non si vede non si vede da nessuna
        parte — e la Home, che e' l'altro posto dove si vedono, direbbe che
        non c'e'.
        """
        from Utility import Preferiti

        try:
            return Preferiti.c_e_(pub.keySymbol, Preferiti._lingua(pub))
        except Exception:  # noqa: BLE001
            return False

    # -- il numero di righe e colonne ------------------------------------

    def rowCount(self, padre=QModelIndex()) -> int:
        return 0 if padre.isValid() else len(self.pubblicazioni)

    def columnCount(self, padre=QModelIndex()) -> int:
        return 0 if padre.isValid() else 4

    # -- il contenuto ----------------------------------------------------

    def headerData(self, sezione, orientamento, ruolo=Qt.ItemDataRole.DisplayRole):
        if ruolo != Qt.ItemDataRole.DisplayRole:
            return None
        # L'intestazione della colonna del titolo non serve: e' il nome del
        # gruppo, scritto sopra, e due righe di intestazione sembrano un
        # errore.
        if orientamento == Qt.Orientation.Horizontal:
            return None
        return None

    def data(self, indice: QModelIndex, ruolo=Qt.ItemDataRole.DisplayRole):
        if not indice.isValid():
            return None
        riga, colonna = indice.row(), indice.column()
        if not 0 <= riga < len(self.pubblicazioni):
            return None
        pub = self.pubblicazioni[riga]

        if ruolo == self.RUOLO_PUB:
            return pub
        if ruolo == self.RUOLO_COPERTINA:
            # QUI NON SI SCARICA NESSUNA COPERTINA.
            #
            # `data()` viene chiamato mentre Qt sta disegnando, e il
            # disegno gira sul main thread.  Scaricare una copertina qui
            # dentro blocca la finestra per tutta la durata della
            # richiesta: con 3.741 righe la finestra si blocca, riparte, si
            # blocca di nuovo, ed e' la ragione per cui le copertine
            # arrivavano una alla volta.
            #
            # Qui si restituisce solo quello che e' gia' in cache.  Se non
            # c'e' si restituisce None, la riga mostra il glifo, e il
            # caricatore porta l'immagine quando arriva chiamando
            # `metti_copertina`, che ridisegna SOLO quella riga.
            #
            # Non e' una colonna visibile di per se': e' il ruolo che il
            # delegato usa per la miniatura nella prima colonna.
            return self._copertine.get(self.chiave_di(pub))
        if ruolo == self.RUOLO_ESISTE:
            return self.esistono[riga]
        if ruolo == self.RUOLO_PREFERITO:
            return self.preferiti[riga]

        if ruolo == Qt.ItemDataRole.DisplayRole and colonna == self.TITOLO:
            return pub.displayTitle

        if ruolo == Qt.ItemDataRole.DecorationRole and colonna == self.COPERTINA:
            # La copertina come icona: e' il ruolo che Qt disegna da solo,
            # e cosi' il delegato non deve dipingere immagini a mano.
            copertina = self.data(indice, self.RUOLO_COPERTINA)
            if copertina is None or copertina.isNull():
                return None
            from PyQt6.QtGui import QIcon
            return QIcon(copertina)

        if ruolo == Qt.ItemDataRole.DecorationRole:
            if colonna == self.SCARICA:
                return icon("icloud.and.arrow.down",
                            tema.colori(True)["testo"], 18)
            if colonna == self.CANCELLA and self.esistono[riga]:
                return icon("trash", tema.colori(True)["testo"], 18)
            return None

        if ruolo == Qt.ItemDataRole.TextAlignmentRole and colonna == self.TITOLO:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    # -- la riga come si comporta ----------------------------------------

    def flags(self, indice: QModelIndex):
        if not indice.isValid():
            return Qt.ItemFlag.NoItemFlags
        # Niente ItemIsEditable: le celle non si scrivono.  Niente
        # ItemIsSelectable sulla colonna del titolo quando il pacchetto non
        # c'e': un titolo non cliccabile che sembra cliccabile e' la cosa
        # peggiore, perche' l'utente clicca e non capisce perche' non
        # succede niente.
        if indice.column() in (self.TITOLO, self.COPERTINA) \
                and not self.esistono[indice.row()]:
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def segna_i_preferiti_uno(self) -> None:
        """Rilegge le stelle di QUESTA tabella.  Vedi `PubListView.segna_i_preferiti`,
        che spiega perche' una tabella sola non basta e chi la chiama."""
        for riga, pub in enumerate(self.pubblicazioni):
            nuovo = self._e_preferito(pub)
            if nuovo == self.preferiti[riga]:
                continue
            self.preferiti[riga] = nuovo
            indice = self.index(riga, self.TITOLO)
            if indice.isValid():
                self.dataChanged.emit(indice, indice, [self.RUOLO_PREFERITO])

    def metti_copertina(self, chiave: str, immagine) -> None:
        """Mette la copertina di una pubblicazione, quando e' arrivata.

        Si avvisano **solo le righe di quella pubblicazione**.  Avvisare
        tutto il modello ridipingerebbe 3.741 righe per un'immagine: e' la
        differenza fra una copertina che arriva e una griglia che si
        blocca.

        Tutte le righe, e non una: uno stesso titolo puo' comparire in due
        gruppi — per esempio l'indice e l'edizione di uno stesso periodico —
        e se se ne ridipingesse una sola l'altra resterebbe col glifo
        per sempre, senza che si capisca il perche'.
        """
        self._copertine[chiave] = immagine
        for riga, pub in enumerate(self.pubblicazioni):
            if self.chiave_di(pub) != chiave:
                continue
            indice = self.index(riga, self.COPERTINA)
            if indice.isValid():
                self.dataChanged.emit(indice, indice,
                                      [Qt.ItemDataRole.DecorationRole])

    # -- cambiarne il contenuto ------------------------------------------

    def imposta(self, pubblicazioni: list) -> None:
        """Cambia l'elenco.  Lo usa la ricerca.

        Si avvisa che TUTTO il modello e' cambiato, e non riga per riga:
        con 3.741 righe la differenza si sente, e in questo caso le righe
        sono diverse da tutte a tutte, quindi avvisare riga per riga non
        avrebbe senso.
        """
        self.beginResetModel()
        self.pubblicazioni = list(pubblicazioni)
        self.esistono = [esiste_il_pacchetto(p) for p in self.pubblicazioni]
        # Anche i Preferiti vanno riletti, e per lo stesso motivo degli
        # esistenti: la lista e' lunga quanto le pubblicazioni, quindi se le
        # righe cambiano e la lista no, `data()` chiede la riga 400 a una lista
        # di 12 e solleva:
        #
        #     IndexError: list index out of range
        #
        # dentro il disegno, che e' l'ultimo posto dove un errore di indici si
        # vede per quello che e'.  Dopo una ricerca la tabella mostrava la
        # griglia vuota e un messaggio su stderr che non spiegava niente.
        self.preferiti = [self._e_preferito(p) for p in self.pubblicazioni]
        # LE COPERTINE NON SI BUTTANO VIA.
        #
        # Prima qui c'era `self._copertine = {}`, e il risultato era che
        # dopo ogni ricerca la griglia perdeva tutte le immagini e
        # ricominciava a scaricarle.  Ma il caricatore si ricordava
        # quali aveva gia' consegnate, e non le consegnava piu': la
        # griglia restava coi glifi per sempre.  Il sintomo era "le
        # copertine spariscono e non tornano piu'".
        #
        # La cache e' per chiave di pubblicazione, quindi un filtro non la
        # invalida: sono le stesse immagini, solo elencate diversamente.
        self.endResetModel()


class DelegatoPubblicazione(QStyledItemDelegate):
    """Disegna la riga e gestisce i clic.

    Non crea widget: disegna con il pennello.  Un delegato che crea un
    widget per cella da' lo stesso problema che si voleva evitare, quindi
    qui dentro non c'e' nessun QWidget e non puo' esserci per costruzione.

    I TRE SEGNALI SONO A LIVELLO DI CLASSE
    ---------------------------------------
    ``self.scelto = Signal(object)`` dentro ``__init__`` non funziona: in
    PyQt6 il descrittore del segnale viene costruito quando la classe viene
    creata, quindi un segnale per ogni istanza non viene registrato.  Il
    sintomo e' ``'pyqtSignal' object has no attribute 'connect'``, e arriva
    al momento di collegare e non al momento di dichiarare.
    """
    scelto = Signal(object)
    scarica = Signal(object)
    cancella = Signal(object)
    #: Il tasto destro e' stato premuto su una riga: la lista chiede un
    #: menu a chi ascolta, che decide cosa mettere dentro.
    menuRichiesto = Signal(object, QPoint)

    def __init__(self, modello, padre=None) -> None:
        super().__init__(padre)
        self.modello = modello

    def paint(self, pittore: QPainter, opzione, indice: QModelIndex) -> None:
        # La riga della selezione, e cosa c'era di sbagliato
        # --------------------------------------------------
        # Qui sotto c'era:
        #
        #     if opzione.state & getattr(opzione, "State_Selected", 0):
        #         pittore.fillRect(opzione.rect, QColor(c["lavato"]))
        #
        # e faceva crashare il programma.  Il motivo e' che
        # ``State_Selected`` sta in ``QStyle.StateFlag``, non
        # nell'opzione.  ``opzione`` e' una ``QStyleOptionViewItem`` e non ha
        # quell'attributo: ``getattr`` con il ripiego restituiva 0 ogni
        # volta, e ``state & 0`` e' una combinazione di flag che Qt
        # considera inesistente, quindi si fermava con un ``abort()``.
        #
        # La riga non faceva niente, e non solo non faceva niente: faceva
        # cadere l'app.  E il sintomo non guardava ne' a questa riga ne' al
        # delegato: diceva ``QTableView::paintEvent``, che e' quattro
        # piani piu' in su, e il motivo vero era a sei righe da li'.
        #
        # E' la classe di errore piu' scomoda che ci sia: una riga che non
        # fa niente dovrebbe essere innocua, e invece uccide.  Il nome
        # giusto e' ``QStyle.StateFlag.State_Selected`` e si scrive
        # per esteso, perche' scritto ``State_Selected`` da solo dentro una
        # classe che non eredita da QStyle non si risolve e fallisce in
        # silenzio.
        from PyQt6.QtWidgets import QStyle

        pub = indice.data(ModelloPubblicazioni.RUOLO_PUB)
        esiste = indice.data(ModelloPubblicazioni.RUOLO_ESISTE)
        c = tema.colori(True)

        pittore.save()
        if opzione.state & QStyle.StateFlag.State_Selected:
            pittore.fillRect(opzione.rect, QColor(c["lavato"]))

        colonna = indice.column()
        if colonna == ModelloPubblicazioni.TITOLO:
            # Il titolo e' cliccabile solo se il pacchetto c'e'.  Se non
            # c'e' resta grigio: e' un avviso, non uno stile.
            colore = QColor(c["testo"] if esiste else c["grigio"])
            pittore.setPen(colore)

            # LA STELLA DEI PREFERITI, A SINISTRA DEL TITOLO
            # ---------------------------------------------------
            # Il motivo della stella e' che in una riga di 3.741 pubblicazioni
            # non c'e' nient'altro che dica se un titolo e' fra i Preferiti.  Il
            # menu con il tasto destro lo dice, ma per arrivarci bisogna
            # premere il tasto destro su quella riga, e nessuno fa cosi' per
            # guardare: si guarda e si vede.
            #
            # Sta a sinistra e non in fondo perche' a destra ci sono gia' i due
            # bottoni della riga: metterla li' la renderebbe un terzo bottone
            # che non si preme, che e' il modo peggiore per far capire che e'
            # un segno e non un'azione.
            #
            preferito = indice.data(ModelloPubblicazioni.RUOLO_PREFERITO)
            larghezza_stella = 0
            if preferito:
                LATO = 14
                larghezza_stella = LATO + 6
                y = opzione.rect.y() + (opzione.rect.height() - LATO) // 2
                x = opzione.rect.x() + 8
                pittore.drawPixmap(
                    QRect(x, y, LATO, LATO),
                    icon("star.fill", tema.ORO_PREFERITO, LATO).pixmap(LATO, LATO))

            testo = indice.data(Qt.ItemDataRole.DisplayRole) or ""
            # La stella ha preso 20 pixel, quindi il titolo parte piu' a
            # destra SOLO quando la stella c'e': senza, il titolo parte
            # dove parteva prima e non si vede nessuno spazio vuoto.
            pittore.drawText(opzione.rect.adjusted(8 + larghezza_stella, 0, -4, 0),
                             int(Qt.AlignmentFlag.AlignLeft
                                 | Qt.AlignmentFlag.AlignVCenter),
                             testo)

        elif colonna == ModelloPubblicazioni.COPERTINA:
            # LA COPERTINA SI DISEGNA QUI, NON DA QT
            # ---------------------------------------
            # Il delegato che si scrive da capo non chiama il metodo della
            # classe base, e quindi Qt non disegna nessun ruolo: ogni cosa
            # va dipinta a mano.  Prima questa colonna non veniva dipinta
            # affatto, perche' si contava sul fatto che Qt lo facesse da
            # solo, e la griglia mostrava il titolo con uno spazio vuoto
            # davanti senza spiegazione.
            glifo = indice.data(Qt.ItemDataRole.DecorationRole)
            if glifo is not None and not glifo.isNull():
                quadro = opzione.rect.adjusted(2, 2, -2, -2)
                # La miniatura e' quadrata per costruzione, ma il file
                # puo' non esserlo.  Si tiene il centro e si ritaglia
                # invece di deformare: una copertina stirata sembra
                # rotta, e una copertina tagliata sembra una miniatura.
                largo, alto = glifo.pixmap(LARGHEZZA_COPERTINA,
                                           LARGHEZZA_COPERTINA).width(), \
                              glifo.pixmap(LARGHEZZA_COPERTINA,
                                           LARGHEZZA_COPERTINA).height()
                if largo > 0 and alto > 0:
                    fattore = min(quadro.width() / largo, quadro.height() / alto)
                    larghezza, altezza = int(largo * fattore), int(alto * fattore)
                    x = quadro.x() + (quadro.width() - larghezza) // 2
                    y = quadro.y() + (quadro.height() - altezza) // 2
                    pittore.drawPixmap(QRect(x, y, larghezza, altezza),
                                       glifo.pixmap(LARGHEZZA_COPERTINA,
                                                    LARGHEZZA_COPERTINA))
        elif colonna in (ModelloPubblicazioni.SCARICA, ModelloPubblicazioni.CANCELLA):
            glifo = indice.data(Qt.ItemDataRole.DecorationRole)
            if glifo is not None and not glifo.isNull():
                x = opzione.rect.x() + (opzione.rect.width() - 18) // 2
                y = opzione.rect.y() + (opzione.rect.height() - 18) // 2
                pittore.drawPixmap(x, y, glifo.pixmap(18, 18))
        pittore.restore()

    def editorEvent(self, evento, modello, opzione, indice) -> bool:
        """Il clic su una cella.

        Si controlla il tipo di evento e la colonna: la colonna del titolo
        apre, le due icone fanno il loro mestiere.  Senza controllare la
        colonna, un clic sul cestino aprirebbe anche la pubblicazione.
        """
        from PyQt6.QtCore import QEvent

        # IL TASTO DESTRO
        # ---------------
        # Il destro apre il menu, il sinistro apre la pubblicazione.  Sono
        # due gesti diversi e non vanno mescolati: se il destro aprisse la
        # pubblicazione, l'utente che vuole togliere un Preferito
        # finirebbe dentro il libro.
        #
        # Il menu si chiede con un segnale e non si costruisce qui dentro:
        # il delegato non sa cosa si puo' fare con una pubblicazione, e se
        # lo sapesse ogni schermata che riusa la lista avrebbe il suo
        # menu dentro.
        if evento.type() == QEvent.Type.MouseButtonRelease and \
                evento.button() == Qt.MouseButton.RightButton:
            if pub := indice.data(ModelloPubblicazioni.RUOLO_PUB):
                self.menuRichiesto.emit(pub, evento.globalPosition().toPoint())
            return True

        if evento.type() != QEvent.Type.MouseButtonRelease:
            return False
        # Un click sulla copertina apre la pubblicazione come sul titolo.
        # Se non lo facesse, l'utente preme l'immagine e non succede
        # niente, e l'immagine sembra non essere un pulsante.
        if indice.column() == ModelloPubblicazioni.COPERTINA:
            if (pub := indice.data(ModelloPubblicazioni.RUOLO_PUB)) and \
                    indice.data(ModelloPubblicazioni.RUOLO_ESISTE):
                self.scelto.emit(pub)
            return True
        if pub := indice.data(ModelloPubblicazioni.RUOLO_PUB):
            colonna = indice.column()
            if colonna == ModelloPubblicazioni.TITOLO:
                if indice.data(ModelloPubblicazioni.RUOLO_ESISTE):
                    self.scelto.emit(pub)
                return True
            if colonna == ModelloPubblicazioni.SCARICA:
                self.scarica.emit(pub)
                return True
            if colonna == ModelloPubblicazioni.CANCELLA:
                self.cancella.emit(pub)
                return True
        return False


class Gruppo(QWidget):
    """Una scatola che si apre e si chiude, con la tabella dentro."""

    def __init__(self, titolo: str, padre=None) -> None:
        super().__init__(padre)
        self.aperta = True

        self.testo = QLabel(titolo)
        self.freccia = QToolButton()
        self.freccia.setText("▼")
        self.freccia.setAutoRaise(True)
        self.freccia.setFixedSize(16, 16)
        self.freccia.clicked.connect(self._ruota)

        intestazione = QHBoxLayout()
        intestazione.setSpacing(4)
        intestazione.addWidget(self.freccia)
        intestazione.addWidget(self.testo)
        intestazione.addStretch(1)

        # LA TABELLA
        self.modello = ModelloPubblicazioni([], self)
        self.delegato = DelegatoPubblicazione(self.modello, self)

        self.tabella = QTableView(self)
        self.tabella.setModel(self.modello)
        # Le copertine: un thread le scarica, il main le disegna.
        self.caricatore, self.pompa = CaricaCopertine.collega(self.modello, self)
        self.tabella.setItemDelegate(self.delegato)
        self.tabella.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabella.setShowGrid(False)
        self.tabella.setWordWrap(False)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.horizontalHeader().setVisible(False)
        # Nessuna riga fissa: con 3.741 righe non si può usare
        # setSectionResizeMode, che lavora solo su righe visibili.
        self.tabella.verticalHeader().setDefaultSectionSize(ALTEZZA_RIGA)
        self.tabella.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tabella.setColumnWidth(ModelloPubblicazioni.SCARICA, LARGHEZZA_ICONA)
        self.tabella.setColumnWidth(ModelloPubblicazioni.CANCELLA, LARGHEZZA_ICONA)
        self.tabella.setColumnWidth(ModelloPubblicazioni.COPERTINA, LARGHEZZA_COPERTINA)
        # Le due colonne delle icone non si allargano col resto.
        self.tabella.horizontalHeader().setSectionResizeMode(
            ModelloPubblicazioni.SCARICA, QHeaderView.ResizeMode.Fixed)
        self.tabella.horizontalHeader().setSectionResizeMode(
            ModelloPubblicazioni.CANCELLA, QHeaderView.ResizeMode.Fixed)
        # La colonna della copertina non si allarga col resto: e' una
        # miniatura quadrata e non ha senso che diventi rettangolare.
        self.tabella.horizontalHeader().setSectionResizeMode(
            ModelloPubblicazioni.COPERTINA, QHeaderView.ResizeMode.Fixed)

        # Si chiedono le copertine delle righe che si vedono.  Non di
        # tutte: 3.741 richieste per 30 righe guardate sarebbero 3.711
        # richieste buttate, e tenerebbe la connessione occupata mentre
        # l'utente legge.
        self._timer_visibilitye = QTimer(self)
        self._timer_visibilitye.setInterval(400)
        self._timer_visibilitye.timeout.connect(self._chiedi_visibili)
        self._timer_visibilitye.start()

        self.scorrimento = QScrollArea(self)
        self.scorrimento.setWidgetResizable(True)
        self.scorrimento.setWidget(self.tabella)
        self.scorrimento.setMaximumHeight(ALTEZZA_MAX)

        disposizione = QVBoxLayout(self)
        disposizione.setSpacing(2)
        disposizione.addLayout(intestazione)
        disposizione.addWidget(self.scorrimento)

    def _chiedi_visibili(self) -> None:
        """Mette in coda le copertine delle righe che si vedono, e un po' dopo.

        LE VISIBILI E POI QUALCHE ALTRA
        -------------------------------
        Solo le visibili e' gia' meglio di tutto, ma quando l'utente
        scorre vede arrivare le immagini con un ritardo che sembra un
        difetto.  Si aggiunge quindi un margine di due schermate sopra e
        due sotto: arriva prima che ci arrivi l'occhio, e lo scorrimento
        resta fluido.

        Il margine non e' tutto: 3.741 richieste sarebbero 3.741 immagini
        scaricate per quelle che l'utente forse guarda, con la connessione
        occupata mentre legge.

        LA CHIAVE HA L'ANNO E LA RIGA
        ------------------------------
        La sigla da sola non basta: ``w`` e' la Torre di Guardia e ha una
        riga per ogni mese, quindi la stessa sigla torna quattrocento
        volte e la coda — che tiene un elemento per chiave — ne terrebbe
        uno solo.  Con l'anno e la riga ogni riga ha la sua.

        Il taglia e' "xs" e NON "sm": i LIBRI hanno solo xs, md e lg.
        Chiedere "sm" dà 403 e la colonna resta vuota per tutte le righe,
        senza che si capisca il perche'.  Le "sm" esistono per le
        LOCANDINE, non per le copertine di libro: sono due famiglie diverse,
        anche per le taglie.
        """
        modello = self.tabella.model()
        quante = modello.rowCount()
        if quante == 0:
            return

        primo = self.tabella.indexAt(self.tabella.rect().topLeft()).row()
        ultimo = self.tabella.indexAt(self.tabella.rect().bottomLeft()).row()
        # Se la tabella non ha ancora disegnato nulla gli indici sono non
        # validi e `row()` restituisce -1.  Allora `range(-1, -1 + n)`
        # parte da -1 e mette in coda righe che non esistono: non e' una
        # difesa, e' il caso normale della prima esecuzione del timer.
        if primo < 0 or ultimo < 0:
            return

        margine = 2 * self._righe_visibili()
        alto = max(0, primo - margine)
        basso = min(quante - 1, ultimo + margine)

        for riga in range(alto, basso + 1):
            pub = modello.index(riga, 0).data(ModelloPubblicazioni.RUOLO_PUB)
            if pub is None:
                continue
            chiave = ModelloPubblicazioni.chiave_di(pub)
            if modello.ha_copertina(chiave):
                continue
            self.caricatore.metti(chiave, riga, pub, "xs")
        self.caricatore.parti()

    def _righe_visibili(self) -> int:
        """Quante righe si vedono, approssimativamente.

        Serve solo per il margine, quindi una stima va bene: se sbaglia di
        due righe la finestra funziona lo stesso.
        """
        altezza = self.tabella.viewport().height() or 1
        return max(1, altezza // ALTEZZA_RIGA)

    def _ruota(self) -> None:
        self.aperta = not self.aperta
        self.scorrimento.setVisible(self.aperta)
        self.freccia.setText("▼" if self.aperta else "▶")

    def metti(self, pubblicazioni: list) -> None:
        self.modello.imposta(pubblicazioni)
        # Il caricatore si ferma: se il gruppo e' vuoto non c'e' niente da
        # chiedere, e continuare a chiedere durante una ricerca scarica
        # copertine di pubblicazioni che non sono piu' in elenco.
        if hasattr(self, "caricatore"):
            self.caricatore.ferma() if not pubblicazioni \
                else self.caricatore.parti()
        nome = self.testo.text().split(" (")[0]
        self.testo.setText(f"{nome} ({len(pubblicazioni)})")

        # UN GRUPPO VUOTO SI CHIUDE DA SE'
        #
        # Durante una ricerca quasi sempre qualche gruppo non trova niente.
        # Lasciarlo aperto con dentro una scatola vuota alta 300 pixel fa
        # perdere metà schermo per quattro righe di risultato, e la
        # parte utile finisce sotto.
        #
        # Non si cancella il gruppo: si chiude.  Così il nome e il numero
        # restano visibili e si vede che quel tipo di pubblicazioni non ha
        # corrispondenze, che è una informazione, mentre una scatola vuota
        # non è niente.
        if pubblicazioni:
            self.aperta = True
            self.freccia.setText("▼")
            self.scorrimento.setVisible(True)
        else:
            self.aperta = False
            self.freccia.setText("▶")
            self.scorrimento.setVisible(False)


class PubListView(QWidget):
    """Le pubblicazioni, in cinque gruppi."""

    #: Una pubblicazione e' stata scelta
    publicationChosen = Signal(object)
    #: Chiede di scaricare una pubblicazione
    downloadRequested = Signal(object)
    #: Chiede di cancellare una pubblicazione
    deleteRequested = Signal(object)
    #: Dice qualcosa all'utente, per la barra di stato
    messaggio = Signal(str)
    #: I Preferiti sono cambiati: qualcuno li ha messi o tolti.
    #:
    #: IL SEGNALE ESISTE PERCHE' PRIMA NON C'ERA NESSUN AVVISO
    #: -------------------------------------------------------
    #: `_metti_preferito` scriveva il file e basta.  La Home costruiva i
    #: Preferiti una volta sola, all'avvio della sezione, e non sapeva che il
    #: file era cambiato: per vedere il Preferito appena messo bisognava
    #: chiudere e riaprire l'app, o premere il pulsante Aggiorna.
    #:
    #: Il pulsante Aggiorna pero' fa tre cose — controlla il server, rilegge
    #: il catalogo, ricrea le sezioni — e nessuna delle tre e' "ho messo un
    #: Preferito".  Collegare le due cose e' quello che rendeva l'aggiornamento
    #: necessario per vedere una stella.  Qui il segnale e' dedicato e la
    #: finestra rilige solo la griglia dei Preferiti.
    preferitiCambiati = Signal()

    def __init__(self, publications, parent=None) -> None:
        super().__init__(parent)
        self.publications = list(publications)
        self.gruppi: list[Gruppo] = []

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(4, 4, 4, 4)

        for tipo, etichetta, per_anno in GRUPPI:
            gruppo = Gruppo(etichetta, self)
            # Si collega il SEGNALE al segnale, non al suo `.emit`:
            # `emit` e' il modo per spararlo, non la lista di chi ascolta,
            # e `.connect` su di esso non esiste.  E' lo stesso errore di
            # `pyqtSignal has no attribute 'connect'` in un altro vestito.
            gruppo.delegato.scelto.connect(self.publicationChosen)
            gruppo.delegato.scarica.connect(self.downloadRequested)
            gruppo.delegato.cancella.connect(self.deleteRequested)
            gruppo.metti(self._ordinate(tipo, per_anno))
            gruppo.delegato.menuRichiesto.connect(self._menu_riga)
            esterno.addWidget(gruppo)
            self.gruppi.append(gruppo)

        esterno.addStretch(1)
        self.setLayout(esterno)

    # ------------------------------------------------------------------

    def _ordinate(self, tipo: int, per_anno: bool) -> list:
        """Le pubblicazioni di un tipo, nell'ordine giusto.

        Non e' un metodo statico perche' legge ``self.publications``: la
        lista corrente, che durante la ricerca non e' piu' quella di
        partenza.  Se fosse statico, durante la ricerca continuerebbe a
        ordinare la lista intera e il filtro non servirebbe a niente.
        """
        scelte = [p for p in self.publications if p.publicationTypeId == tipo]
        if per_anno:
            scelte.sort(key=lambda p: p.year, reverse=True)
        else:
            scelte.sort(key=lambda p: p.title)
        return scelte

    def _menu_riga(self, pub, posizione) -> None:
        """Il menu del tasto destro su una riga.

        DUE AZIONI, E UNA DIPENDE DALL'ALTRA
        --------------------------------------
        "Metti fra i Preferiti" c'e' solo se la pubblicazione non c'e' gia'
        fra i Preferiti, e "Togli dai Preferiti" solo se c'e'.  Mostrare
        entrambe sempre vuol dire che una delle due non fa niente, e una
        voce che non fa niente in un menu e' rumore che fa perdere tempo a
        leggerlo.

        Il Preferito si puo' mettere anche di una pubblicazione non
        scaricata: e' una nota sul cosa voglio, non il cosa ho.  E il
        titolo si puo' aprire solo se il pacchetto c'e', quindi quel voce
        appare solo in quel caso.
        """
        from PyQt6.QtWidgets import QMenu

        from Utility import Preferiti

        sigla, lingua = Preferiti._lingua(pub), Preferiti._lingua(pub)
        chiave = Preferiti.chiave(pub.keySymbol, Preferiti._lingua(pub))
        gia = Preferiti.c_e_(*(pub.keySymbol, Preferiti._lingua(pub)))

        menu = QMenu(self)
        if gia:
            azione = menu.addAction("Togli dai Preferiti")
            azione.triggered.connect(
                lambda: self._togli_preferito(pub.keySymbol,
                                              Preferiti._lingua(pub)))
        else:
            azione = menu.addAction("Metti fra i Preferiti")
            azione.triggered.connect(lambda: self._metti_preferito(pub))
        _ = (sigla, chiave)

        if esiste_il_pacchetto(pub):
            menu.addSeparator()
            apri = menu.addAction("Apri")
            apri.triggered.connect(lambda: self.publicationChosen.emit(pub))
        scarica = menu.addAction("Scarica il pacchetto")
        scarica.triggered.connect(lambda: self.downloadRequested.emit(pub))
        if esiste_il_pacchetto(pub):
            togli = menu.addAction("Togli il pacchetto")
            togli.triggered.connect(lambda: self.deleteRequested.emit(pub))

        menu.exec(posizione)

    def _metti_preferito(self, pub) -> None:
        from Utility import Preferiti

        if Preferiti.aggiungi(pub):
            self.messaggio.emit(f"«{pub.title or pub.keySymbol}» fra i Preferiti")
        else:
            self.messaggio.emit("C'era gia' fra i Preferiti")
        # Il segnale parte anche quando non e' cambiato niente: costa una
        # rilettura di un file di poche righe, e il caso "era gia' fra i
        # Preferiti" non e' distinguibile dal chiamante, che qui non ha
        # motivo di saperlo.  Meglio una rilettura inutile che una stella
        # che non compare quando doveva.
        self.preferitiCambiati.emit()

    def _togli_preferito(self, sigla: str, lingua: str) -> None:
        from Utility import Preferiti

        if Preferiti.togli(sigla, lingua):
            self.messaggio.emit("Togliuto dai Preferiti")
        self.preferitiCambiati.emit()

    def segna_i_preferiti(self) -> None:
        """Rilegge le stelle dei Preferiti, e ridipinge.

        Va chiamata quando un Preferito e' stato messo o tolto, da questa
        lista stessa o da un'altra sezione.

        STA SULLA LISTA E NON SUL MODELLO
        ---------------------------------
        I modelli sono uno per gruppo, e i gruppi li tiene la lista.  Quindi il
        metodo che deve aggiornarli sta qui: dentro il modello si aggiornerebbe
        una tabella e le altre cinque mostrerebbero ancora la stella vecchia,
        e non si capirebbe perche' la stessa pubblicazione ha la stella in un
        gruppo e non nell'altro.

        PERCHE' RILEGGE TUTTO E NON SOLO LA RIGA TOCCATA
        -------------------------------------------------
        Si potrebbe ridipingere solo la riga appena cambiata, e sarebbe piu'
        veloce.  Ma la stella e' una proprieta' della pubblicazione, e la
        stessa pubblicazione compare in piu' righe: l'indice e l'edizione, il
        libro e la sua versione stampata.  Se si ridipingesse una riga sola,
        l'altra mostrerebbe una stella che non c'e' piu' — o che non c'e'
        ancora.

        Il costo e' una rilettura di un file di poche righe piu' il ridisegno
        delle righe di QUELLA pubblicazione, non delle 3.741.
        """
        for gruppo in self.gruppi:
            modello = getattr(gruppo, "modello", None)
            if modello is None:
                continue
            modello.segna_i_preferiti_uno()

    def filtra(self, pubblicazioni: list) -> None:
        """Cambia l'elenco, mantenendo i cinque gruppi.

        Lo usa la ricerca: il filtraggio lo fa il database, e qui dentro
        si mette quello che e' tornato nei gruppi giusti.  I gruppi non si
        ricreano, si svuotano e si riempiono: ricrearli ogni volta
        costerebbe quanto ricrearli da capo, che e' il costo che si sta
        cercando di togliere.
        """
        self.publications = list(pubblicazioni)
        for (tipo, _etichetta, per_anno), gruppo in zip(GRUPPI, self.gruppi):
            gruppo.metti(self._ordinate(tipo, per_anno))

    def mostra_i_tipi(self, tipi, pubblicazioni: list) -> None:
        """Ricostruisce i gruppi sui tipi richiesti, e non sui cinque fissi.

        PERCHE' RICOSTRUISCE E NON NASCONDE
        ------------------------------------
        `filtra` riusa i cinque gruppi e svuota quelli che non servono: va
        bene finche' si cerca, perche' la ricerca non cambia **quali** tipi
        ci sono.  Premendo una categoria cambia invece proprio quello, e con i
        cinque gruppi fissi la categoria «Trattati» — che e' il tipo 7, e che
        nei cinque non c'e' — mostrerebbe cinque scatole vuote.

        I gruppi vecchi vengono tolti dal layout e distrutti, non nascosti: se
        restassero nel layout anche invisibili, ogni cambio categoria
        accumulerebbe cinque scatole finche' la finestra non si riempie.

        La lista delle pubblicazioni arriva gia' filtrata dal chiamante, che e'
        `PubView`: qui si ordina e si mette nei gruppi, e la decisione di
        **cosa** mostrare non si prende due volte.
        """
        self.publications = list(pubblicazioni)
        disposizione = self.layout()

        for gruppo in self.gruppi:
            disposizione.removeWidget(gruppo)
            gruppo.hide()
            gruppo.deleteLater()
        self.gruppi = []

        # L'ultimo elemento del layout e' il `addStretch(1)` di `__init__`, e i
        # gruppi nuovi vanno **prima** di quello: inseriti dopo, starebbero
        # sotto la parte vuota e non si vedrebbero.
        for posizione, tipo in enumerate(tipi):
            etichetta, per_anno = TIPI.get(tipo, (f"Tipo {tipo}", False))
            gruppo = Gruppo(etichetta, self)
            gruppo.delegato.scelto.connect(self.publicationChosen)
            gruppo.delegato.scarica.connect(self.downloadRequested)
            gruppo.delegato.cancella.connect(self.deleteRequested)
            gruppo.delegato.menuRichiesto.connect(self._menu_riga)
            gruppo.metti(self._ordinate(tipo, per_anno))
            disposizione.insertWidget(posizione, gruppo)
            self.gruppi.append(gruppo)

        # Senza gruppi non c'e' niente da mostrare e non c'e' nemmeno una
        # scatola che dica il perche'.  Il richiamo e' perche' l'elenco puo'
        # essere vuoto anche con i gruppi: una ricerca che non trova niente
        # e' la stessa cosa da guardare.
        if not self.gruppi:
            vuoto = QLabel("Nessuna pubblicazione in questa categoria.")
            vuoto.setObjectName("nota")
            vuoto.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vuoto.setWordWrap(True)
            disposizione.insertWidget(0, vuoto)
            self.gruppi.append(vuoto)

    # ------------------------------------------------------------------

    @staticmethod
    def delete_pub(pub) -> None:
        """Toglie il pacchetto e i testi HTML che aveva fatto scaricare.

        I file HTML vanno tolti insieme al pacchetto: se restano, riaprendo la
        pubblicazione si vede il testo scaricato e sembra che il pacchetto ci
        sia ancora.  E' la stessa cosa che faceva il progetto originale.
        """
        from Utility.Extensions.Ext_FileManager import get_documents_directory as _radice

        for documento in JWPubManager.get_documents(pub):
            percorso = _radice() / "Documents_I" / f"{documento.documentId}.html"
            print(f"Elimino... {percorso}")
            try:
                percorso.unlink(missing_ok=True)
            except OSError:
                pass

        import shutil
        cartella = _radice() / pub_dir_name(pub)
        try:
            shutil.rmtree(cartella)
            print(f"Eliminata {cartella}")
        except OSError as errore:
            print(f"Non riesco a togliere {cartella}: {errore} ⚠️")