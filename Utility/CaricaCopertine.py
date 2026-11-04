#
#  Utility/CaricaCopertine.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Le copertine, scaricate in un thread e disegnate sul main.

IL BLOCCO, E LA SUA CAUSA
-------------------------
La prima versione chiedeva la copertina dentro ``data()`` del modello, e
``data()`` viene chiamato mentre Qt sta **disegnando**.  Il risultato era
quello che si vede: la finestra si blocca, poi riparte, poi si blocca di
nuovo, e le copertine arrivano una alla volta.

Perche' succede: in quel punto la rete e' sul **main thread**, che e' lo
stesso thread che riceve i clic e ridisegna.  Un'attesa di rete li' non e'
uno slo', e' una pausa della finestra.  Con 3.741 righe e una copertina
per riga sono 3.741 pause.

IL CONFINE, E PERCHE' STA ESATTAMENTE DOVE STA
----------------------------------------------
    il thread scarica i BYTE
    il main thread fa il PIXMAP

``QPixmap`` e' un oggetto grafico e va creato dove c'e' la
``QApplication``.  Crearlo in un thread secondario e' una delle cose che
non funziona e che non lo dice.  Per questo ``Copertine.dati_copertina``
non tocca Qt e ``Copertine.pixmap_da_dati`` non tocca la rete: sono due
funzioni con un confine netto in mezzo, e ognuna si puo' chiamare solo
dove e' lecito.

PERCHE' UNA CODA E NON UN THREAD PER COPERTINA
---------------------------------------------
Trecento thread che scaricano insieme non sono piu' veloci di uno: si
contendono la connessione e il server risponde 429.  Un thread solo che
va in fila e' piu' veloce e non rischia di essere bloccato.

E non si scarica tutto: si scarica quello che si vede, e poi il resto
piano piano.  Un utente che guarda le prime trenta righe non ha bisogno
delle trecento della copertina.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, QTimer, pyqtSignal as Signal


class CaricaCopertine(QObject):
    """Scarica le copertine in fila e le consegna sul main thread.

    TRE LAVORATORI, NON UNO
    ------------------------
    Con un solo lavoratore la misura era di **due copertine al secondo**:
    ogni richiesta ci mette mezzo secondo di attesa, e mezzo secondo di
    attesa con un solo filo di esecuzione significa mezzo secondo per
    immagine.  Non e' un problema della rete, e' un problema di quante
    richieste si tengono aperte insieme.

    Tre e' un numero scelto, non casuale: abbastanza da non aspettare, e
    abbastanza pochi da non sembrare un attacco al server.  Con cento
    richieste aperte insieme il server risponde 429 e si blocca tutto, e
    il risultato e' **peggio** di uno alla volta, perche' gli errori non
    si possono distinguere dalle immagini che non esistono.

    ``caricata`` arriva sul main thread perche' e' un segnale Qt, e un
    segnale emesso da un thread estraneo finisce *di sicuro* accodato al
    thread che ha creato la QObject.  Non serve fare nient'altro.
    """

    #: (chiave della pubblicazione, indice di riga, byte dell'immagine)
    caricata = Signal(str, int, object)

    LAVORATORI = 3

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self._coda: list = []
        self._per_chiave: dict = {}
        self._thread: threading.Thread | None = None
        self._fermo = False
        self._lavoratori = 0
        # Quante copertine si scaricano prima di lasciare respirare la
        # finestra.  Un'immagine per volta e' il caso peggiore: si sente
        # ogni singola pausa.  Un blocchetto di venti e' indistinguibile.
        self._BRUZZO = 8

    # ------------------------------------------------------------------

    def metti(self, chiave: str, indice: int, pub, taglia: str = "xs") -> None:
        """Mette in coda una copertina da prendere.

        :param chiave: il nome con cui riconoscere la pubblicazione
        :param indice: il numero di riga nel modello, per sapere dove mettere
            l'immagine quando arriva
        """
        if chiave in self._per_chiave:
            return
        voce = (chiave, indice, pub, taglia)
        self._per_chiave[chiave] = voce
        self._coda.append(voce)

    def parti(self) -> None:
        """Fai partire i lavoratori, se non stanno gia' girando.

        Si avviano fino al massimo e non uno di piu': se la coda e' corta
        non serve aprire tre fili per due immagini.
        """
        if self._fermo or not self._coda:
            return
        quanti = min(self.LAVORATORI - self._lavoratori, len(self._coda))
        for _ in range(quanti):
            self._lavoratori += 1
            threading.Thread(target=self._lavora, daemon=True).start()

    def dimentica(self) -> None:
        """Scorda tutto quello che ha gia' consegnato.

        Serve quando l'elenco cambia di forma e le copertine sono state
        buttate via: senza, il caricatore crede di aver gia' fatto il
        lavoro e non consegna piu' niente, e la griglia resta coi glifi
        per sempre.
        """
        self._per_chiave = {}

    def ferma(self) -> None:
        """Non prendere piu' niente.

        Si chiama quando la sezione non e' piu' visibile.  Non serve
        uccidere i thread: quando arrivano al prossimo elemento vedono la
        bandierina e escono.  Terminare un thread a meta' lascia la
        connessione a meta' e puo' far restare un file di cache scritto
        per meta'.
        """
        self._fermo = True
        self._coda = []

    # ------------------------------------------------------------------

    def _lavora(self) -> None:
        """Il thread: prende dalla coda e consegna.

        Tutto quello che tocca Qt e' dentro l'emissione del segnale, che
        viene consegnata sul main thread.  Qui fuori non si crea nessun
        ``QPixmap``: solo byte e un segnale.

        La coda si legge con un blocco per volta e si rimette indietro
        subito: due lavoratori che leggono la stessa lista si pesterebbero
        i piedi e scaricherebbero la stessa copertina due volte.
        """
        from Utility import Copertine

        while not self._fermo:
            with self._coda_lock():
                if not self._coda:
                    break
                blocco = self._coda[:self._BRUZZO]
                self._coda = self._coda[self._BRUZZO:]
            for chiave, indice, pub, taglia in blocco:
                if self._fermo:
                    self._lavoratori -= 1
                    return
                try:
                    dati = Copertine.dati_copertina(pub, taglia)
                except Exception:  # noqa: BLE001
                    # Una copertina che non si prende non ferma le altre:
                    # si consegna None e la riga mostra il glifo.
                    dati = None
                # LA FINESTRA PUO' ESSERSI CHIUSA MENTRE SI LAVORA
                # --------------------------------------------------
                # `_fermo` dice al lavoratore di fermarsi, ma controlla **un
                # attributo di Python**: il widget Qt e' gia' stato liberato
                # quando il programma esce, e `emit` su un oggetto C++ distrutto
                # solleva «wrapped C/C++ object of type CaricaCopertine has
                # been deleted».
                #
                # Il sintomo è una raffica di traceback **all'avvio e all'uscita**,
                # mentre la finestra è già aperta: sembra un crash del programma
                # quando invece è un thread che ha finito il suo lavoro dopo che
                # nessuno lo ascolta più.  Non fa perdere niente — le copertine
                # che non arrivano sono di pezzi che non le avevano — ma
                # riempie il terminale di errori che non sono errori.
                try:
                    self.caricata.emit(chiave, indice, dati)
                except RuntimeError:
                    # Il widget non c'è più: non c'è nessuno a cui consegnare
                    # la copertina, e nessuno che la chieda.  Si smette.
                    return
        self._lavoratori -= 1

    def _coda_lock(self):
        """Il blocco sulla coda, creato una volta sola.

        Senza, tre lavoratori che leggono e scrivono la stessa lista
        mentre il main thread aggiunge righe possono vedere lo stesso
        elemento due volte o perdere un elemento.  E' la classica
        corruzione di lista e il sintomo e' "manca una copertina", che non
        fa pensare a niente.
        """
        if not hasattr(self, "_lock"):
            self._lock = threading.Lock()
        return self._lock


def pixmap_pronta(dati):
    """Dai byte a un QPixmap, sul main thread.

    E' lo stesso di ``Copertine.pixmap_da_dati`` e sta qui perche' chi
    scarica in un thread ha bisogno di due cose: ``dati_copertina`` per
    andare in rete e ``pixmap_pronta`` per tornare indietro.  Sono due
    funzioni e stanno nella stessa riga di un file, cosi' il confine fra
    "cosa si puo' fare in un thread" e "cosa no" si vede a colpo d'occhio.
    """
    from Utility import Copertine
    return Copertine.pixmap_da_dati(dati)


class PompaCopertine(QObject):
    """Fissa le copertine che arrivano, sul main thread.

    E' il secondo pezzo, e sta sul main thread di proposito: riceve i
    byte, li trasforma in ``QPixmap`` e dice al modello di ridisegnare
    quella riga.
    """

    #: (modello, chiave della pubblicazione, QPixmap o None)
    fissata = Signal(object, str, object)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)

    def prendi(self, chiave: str, _indice: int, dati: bytes) -> None:
        """Trasforma i byte in immagine e la consegna.

        La trasformazione avviene qui, non nel thread: ``QPixmap`` ha
        bisogno della ``QApplication``, e crearlo altrove e' una delle
        cose che funziona una volta e poi non piu'.

        Si passa la CHIAVE e non l'indice della riga, perche' fra la
        richiesta e la consegna l'elenco puo' essere stato filtrato, e
        l'indice di allora non indica piu' la stessa pubblicazione.
        """
        from PyQt6 import sip
        from Utility import Copertine

        if sip.isdeleted(self):
            return
        try:
            immagine = Copertine.pixmap_da_dati(dati)
            self.fissata.emit(None, chiave, immagine)
        except Exception:  # noqa: BLE001
            pass


def collega(modello, padre=None) -> tuple:
    """Il caricatore pronto all'uso per un modello di elenco.

    :returns: (caricatore, pompa).  Il caricatore si mette in coda, la
        pompa fissa sul modello.

    Qui dentro non si mette **tutto** in coda: si mette quello che si
    vede.  Mettere 3.741 richieste in coda significa scaricare 3.741
    copertine delle quali l'utente ne guarda forse trenta, e il resto
    tiene occupata la connessione mentre lui sta leggendo.
    """
    from PyQt6 import sip

    caricatore = CaricaCopertine(padre)
    pompa = PompaCopertine(padre)

    def fissa(_modello, chiave, immagine) -> None:
        # Il modello puo' essere stato buttato via mentre la rete
        # parlava: `dataChanged` su un oggetto morto e' un altro dei
        # modi per far crashare la finestra senza lasciare traccia.
        if sip.isdeleted(modello):
            return
        modello.metti_copertina(chiave, immagine)

    # IL COLLEGAMENTO CHE MANCAVA
    # --------------------------
    # Il thread consegna a `pompa.prendi`, la pompa consegna al modello.
    # Senza la riga qui sotto la catena si interrompe e le copertine
    # arrivano a nessuno: la griglia resta con i glifi e non si capisce
    # perche'.  E' il caso peggiore, perche' il codice sembra tutto
    # collegato e invece manca un pezzo in mezzo.
    caricatore.caricata.connect(pompa.prendi)
    pompa.fissata.connect(fissa)
    return caricatore, pompa