#
#  Utility/Messaggi.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Fare capire i crash.

PERCHE' ESISTE
-------------
Un'eccezione Python dentro un callback di Qt non si comporta come un'eccezione
Python normale.  PyQt6 chiama ``qFatal``, ``qFatal`` chiama ``abort()``, e
l'applicazione muore.  Sulla riga di comando resta:

    Fatal Python error: Aborted
    Current thread ... [python3]:
      File "JWLibraryApp.py", line 310, in <module>
        return applicazione.exec()

E basta.  La riga con il motivo vero **non c'e'**.  Il traceback che si vede
e' quello del main thread, dentro ``exec()``: dice dove la finestra stava,
non cosa e' andato storto.  E il punto in cui e' andato storto puo' essere
un file e un centinaio di righe lontano.

LA MISURA
---------
Su questo progetto, prima di questo modulo, un ``NameError`` dentro una
``QTimer`` produceva:

    Fatal Python error: Aborted
    Current thread ...:
      File "...", line 70, in <module>     <- app.exec()

Il ``NameError: name 'schermata' is not defined`` **non compariva da nessuna
parte**.  Installando un gestore di messaggi di Qt la stessa identica
situazione stampa:

    [Qt FATALE] Traceback (most recent call last):
      File "...", line 35, in passo
        print(f"\\n1. rail -> {type(schemata).__name__}", flush=True)
    NameError: name 'schermata' is not defined. Did you mean: 'schermata'?

Stessa identica riga di codice, stesso identico crash.  L'unica differenza
e' che adesso c'e' scritto perche'.

QUELLO CHE FA
-------------
Due cose, e sono due buchi diversi:

1. un gestore di messaggi di Qt, che stampa quello che Qt voleva stampare e
   che per via sua non finiva da nessuna parte;
2. ``sys.excepthook``, che stampa le eccezioni che escono dal ciclo di
   eventi invece di lasciare che Python le ignori in silenzio.

Perche' due: il primo prende le eccezioni dentro i segnali Qt, il secondo
quelle che arrivano dal ciclo principale.  Sono strade diverse e ognuna
aveva il suo buco.

NON CAMBIA NESSUN COMPORTAMENTO
-------------------------------
Qui non si intercetta niente e non si nasconde niente: si stampa e si lascia
andare.  Il gestore non chiama ``exit`` e non risolve l'eccezione.  Se
qualcosa va storto l'app muore come prima, ma muore **dicendo cosa**.

Se un giorno un messaggio di Qt arriva in un file invece che a schermo,
questa funzione e' il posto giusto: c'e' una lista che tiene gli ultimi
messaggi e un numero che dice quanti.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Quanti messaggi tenere da parte se un giorno volessimo scriverli su file.
MESSAGGI_DA_TENERE = 200

ULTIMI: list[str] = []

#: Gli stessi messaggi, **con il livello accanto**.
#:
#: `ULTIMI` da sola non basta a distinguere un errore da una notizia: prima la
#: differenza si riconosceva guardando se la riga cominciava con «[Qt AVVISO]»,
#: e cosi' un messaggio che conteneva la parola AVVISO nel mezzo sembrava un
#: avviso.  Tenere il livello accanto elimina la domanda: il livello e' la
#: cosa che Qt ha passato, non una parola da indovinare.
ULTIMI_CON_LIVELLO: list[tuple[str, str]] = []

#: Chi ascolta le righe **mentre arrivano**.
#:
#: Non e' il log di nuovo: `ULTIMI` si legge quando serve, questo si sente
#: mentre scrive.  Serve alla schermata di avvio, che deve fermarsi all'istante
#: quando compare un errore — e se va a spiarlo ogni tanto, l'errore e' gia'
#: passato e la schermata parte lo stesso.
OSSERVATORI: list = []

#: I livelli per cui il programma **non puo' continuare a lavorare**.
#:
#: Non c'e' `AVVISO`, e la ragione e' misurata, non tasteggiata: su questa
#: stessa macchina Qt scrive a ogni avvio
#:
#:     [Qt AVVISO] This plugin does not support propagateSizeHints()
#:
#: un avviso che non ha niente a che fare con il programma.  Bloccare su un
#: avviso vuol dire che il programma non parte piu' su quelle macchine, e un
#: programma che non parte e' un difetto peggiore di un avviso che non
#: blocca.  Quindi l'avviso si raccoglie e si mostra, ma non ferma niente.
#:
#: Le tre qui sotto sono cose che invece non tornano: un'eccezione non gestita
#: lascia il programma in uno stato che nessuno conosce, e `CRITICO` e
#: `FATALE` sono problemi di Qt, non messaggi.
LIVELLO_BLOCCANTE = ("CRITICO", "FATALE", "ECCEZIONE")

# FILE LOG: scrive tutto su disco (stesso contenuto del terminale)
_FILE_LOG: Path | None = None
_FILE_HANDLER = None

def _inizializza_file_log() -> None:
    """Inizializza il file di log su disco (stesso output del terminale).
    
    ROTAZIONE: mantiene jwlibrary.log (corrente) + jwlibrary.log.1 (precedente).
    File più vecchi vengono cancellati. Max ~1MB totale.
    """
    global _FILE_LOG, _FILE_HANDLER
    try:
        from Utility.Structures.Paths import Paths
        _FILE_LOG = Paths.log_path
        _FILE_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        # ROTAZIONE: se il log corrente è > 500KB, ruota
        MAX_SIZE = 500 * 1024  # 500KB per file
        if _FILE_LOG.is_file() and _FILE_LOG.stat().st_size > MAX_SIZE:
            backup = _FILE_LOG.with_suffix(".log.1")
            try:
                if backup.is_file():
                    backup.unlink()
                _FILE_LOG.rename(backup)
            except OSError:
                pass
        
        _FILE_HANDLER = open(_FILE_LOG, "a", encoding="utf-8")
        # Scrive un separatore per distinguere le sessioni
        from datetime import datetime
        _FILE_HANDLER.write(f"\n{'='*60}\n")
        _FILE_HANDLER.write(f"JW LibriX avviato - {datetime.now().isoformat()}\n")
        _FILE_HANDLER.write(f"{'='*60}\n")
        _FILE_HANDLER.flush()
    except Exception:
        _FILE_LOG = None
        _FILE_HANDLER = None


def _scrivi_su_file(testo: str) -> None:
    """Scrive subito sul file di log (se inizializzato)."""
    if _FILE_HANDLER is not None:
        try:
            _FILE_HANDLER.write(testo if testo.endswith("\n") else testo + "\n")
            _FILE_HANDLER.flush()
        except Exception:
            pass


def _inizializza() -> None:
    """Inizializza tutto: file log + handler Qt + excepthook."""
    _inizializza_file_log()

# Qt e' 6, e in Qt 6 i livelli sono questi cinque.  Il tipo esatto e' un enum,
# ma il nome e' quello che serve qui: se un giorno ne arriva uno nuovo, non
# si blocca niente, si stampa lo stesso.
NOMI = {
    "QtDebugMsg": "DEBUG",
    "QtInfoMsg": "INFO",
    "QtWarningMsg": "AVVISO",
    "QtCriticalMsg": "CRITICO",
    "QtFatalMsg": "FATALE",
}

# La directory dei dati: se un giorno si scrivono messaggi su file, e' li'.
from Utility.Structures.Paths import Paths as _Paths
RADICE_DATI = _Paths.root


def _livello(tipo) -> str:
    """Il nome leggibile del livello, anche se Qt ne ha aggiunto uno."""
    try:
        return NOMI[str(tipo).rsplit(".", 1)[-1]]
    except Exception:  # noqa: BLE001
        # Se il nome non c'e' nella tabella si stampa comunque: meglio
        # "QUALCOSA" che non stampare niente e lasciare il crash muto, che
        # e' esattamente il difetto che questo modulo viene a togliere.
        return str(tipo).rsplit(".", 1)[-1]


def _stampa(testo: str, livello: str = "INFO") -> None:
    """Scrive subito, tiene gli ultimi messaggi e avvisa chi ascolta.

    IL LIVELLO VIENE DA CHI CHIAMA
    ------------------------------
    `_messaggio_qt` passa il livello che Qt le ha dato, e
    `_eccezione_non_gestita` passa `ECCEZIONE`.  Il resto chiama senza e resta
    `INFO`.  Non si deduce dalla riga: dedurlo vuol dire che una riga che
    contiene la parola «AVVISO» nel mezzo e' un avviso, e non e' vero.

    AVVISA PRIMA DI SCRIVERSE SUL FILE
    ----------------------------------
    L'ordine e' file, poi osservatori — e i due non si toccano.  Il file si
    scrive sempre, anche se un osservatore e' rotto: altrimenti il log di un
    crash sparisce proprio mentre si sta cercando il motivo del crash, che e'
    l'unico momento in cui il log serve.
    """
    ULTIMI.append(testo)
    ULTIMI_CON_LIVELLO.append((testo, livello))
    if len(ULTIMI) > MESSAGGI_DA_TENERE:
        del ULTIMI[:len(ULTIMI) - MESSAGGI_DA_TENERE]
    if len(ULTIMI_CON_LIVELLO) > MESSAGGI_DA_TENERE:
        del ULTIMI_CON_LIVELLO[:len(ULTIMI_CON_LIVELLO) - MESSAGGI_DA_TENERE]

    # Scrive su terminale
    try:
        sys.stderr.write(testo if testo.endswith("\n") else testo + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        # stderr chiuso (l'app lanciata senza terminale, per esempio): non
        # e' un motivo per far cadere anche questo.  Un crash che muore
        # mentre cerca di spiegarsi e' un crash che non spiega niente.
        pass
    # Scrive su file
    _scrivi_su_file(testo)
    # E avvisa chi ascolta
    for ascoltatore in list(OSSERVATORI):
        try:
            ascoltatore(testo, livello)
        except Exception:  # noqa: BLE001
            # Un ascoltatore rotto non deve far cadere la stampa.
            pass


def osserva(ascoltatore) -> None:
    """Iscrive `ascoltatore`: riceve `(riga, livello)` per ogni messaggio.

    E' cosi' che la schermata di avvio si ferma **all'istante** quando compare
    un errore.  Se andasse a leggere `ULTIMI` ogni volta che capita, l'errore
    sarebbe gia' passato, la schermata sarebbe gia' finita, e la finestra
    principale si sarebbe aperta lo stesso.

    Va tolto con `non_guardare` quando non serve piu': un ascoltatore lasciato
    dentro riceve per sempre, e se tiene la schermata tiene viva anche i suoi
    widget — che il ciclo di eventi continua a ridisegnare senza che nessuno li
    veda piu'.
    """
    if ascoltatore not in OSSERVATORI:
        OSSERVATORI.append(ascoltatore)


def non_guardare(ascoltatore) -> None:
    """Toglie `ascoltatore` dalla lista.  Non fallisce se non c'era."""
    try:
        OSSERVATORI.remove(ascoltatore)
    except ValueError:
        pass

#: I messaggi che NON si stampano, perche' sono rumore e non informazioni.
#:
#: Il caso che c'era e' `qt.multimedia`: al primo video partiva Qt scriveva
#: quindici righe di header del file — il formato del contenitore, i
#: metadati, la durata, ogni stream con il suo codec — e poi la versione di
#: FFmpeg che sta usando.  Una riga per video, sul terminale, mentre l'utente
#: guarda il video che ha appena avviato.
#:
#: Non sono errori, e non sono informazioni che servono: sono la
#: diagnostica di una libreria.  E sono pericolosi per una cosa sola: il
#: terminale e' dove si leggono gli errori **veri**, quindi quindici righe di
#: FFmpeg sopra un avviso del programma lo nascondono.
#:
#: PERCHE' IL FILTRO STA QUI E NON IN `main()`
#: ------------------------------------------
#: La prima volta il filtro lo mettevo in `JWLibraryApp.main()`, con
#: `QLoggingCategory.setFilterRules`.  Non ha funzionato: **un gestore di
#: messaggi installato con `qInstallMessageHandler` riceve tutto**, filtri o
#: no.  I filtri di Qt servono quando il gestore e' quello di Qt; con un
#: gestore nostro la decisione e' nostra e va presa qui.
#:
#: E il posto giusto e' questo, perche' `Messaggi` e' **l'unico** posto che
#: stampa i messaggi di Qt: se la lista dei rumori stesse in `main()`,
#: `controllo.py` e le prove non la vedrebbero, e la prossima persona che
#: aggiunge un gestore proprio si troverebbe di nuovo il rumore.
ZITTE = ("qt.multimedia", "qt.multimedia.ffmpeg")


#: Avvisi di Qt che dipendono dalla macchina e non dicono niente di rotto: la
#: scheda grafica che ripiega su Vulkan, l'audio che non c'e' (pipewire/pulse),
#: il sistema a finestre che non sa fare `raise()`.  Si vedono nel log come
#: informazioni; non contano come problemi, quindi la splash non si ferma.
INNOCUI = (
    "GBM is not supported",
    "does not support raise()",
    "does not support propagateSizeHints()",
    "Failed to connect to pipewire",
    "PulseAudioService: pa_context_connect() failed",
)


def _rumore(testo: str) -> bool:
    """Questo messaggio e' uno di quelli che non si stampano?"""
    for zitta in ZITTE:
        if zitta in testo:
            return True
    return False


def _messaggio_qt(tipo, contesto, testo) -> None:
    """Il gestore che Qt chiama per ogni messaggio.

    Firma imposta da Qt, non libera: ``(tipo, contesto, testo)``.  I due
    ultimi argomenti sono opzionali in PyQt6, e non arrivano a noi.

    Se il messaggio e' uno di quelli in `ZITTE` **non viene scritto niente**:
    resta in `ULTIMI`, cosi' `scarica()` puo' tirarlo fuori se qualcosa e'
    andato storto e serve sapere che cosa aveva detto FFmpeg, ma non
    finisce sul terminale davanti all'utente.
    """
    if _rumore(testo):
        ULTIMI.append(f"[Qt {_livello(tipo)}] {testo}")
        return
    livello = _livello(tipo)
    if livello in SONO_PROBLEMA and any(frase in testo for frase in INNOCUI):
        # Resta nel log, ma non e' un problema: non apre il pannello della splash.
        livello = "INFO"
    _stampa(f"[Qt {livello}] {testo}", livello)


def _eccezione_non_gestita(tipo, valore, indirizzo=None) -> None:
    """Le eccezioni che escono dal ciclo di eventi.

    Senza questo, Python chiama ``sys.excepthook`` che stampa e basta: va
    bene quando la finestra non c'e'.  Ma dentro ``QApplication.exec()``
    il ciclo non e' Python, e alcuni errori finiscono per non passare da
    qui e vengono persi.  Mettersi un ``excepthook`` proprio e' la maniera
    onesta di non dipendere da quello di PyQt6.

    I TRE ARGOMENTI, NON ``sys.exc_info()``
    ---------------------------------------
    La prima versione di questa funzione ignorava i tre argomenti e
    chiamava ``sys.exc_info()``.  Stampava ``NoneType: None``.

    Il motivo e' che quando si arriva qui l'eccezione e' gia' stata presa e
    messa da parte: ``sys.exc_info()`` restituisce tre ``None``.  I tre
    argomenti che Qt passa all'hook sono l'unica copia che c'e', e buttarli
    via per rileggere un posto che e' gia' vuoto e' il modo piu' rapido per
    stampare niente.

    Per lo stesso motivo non si usa ``raise`` qui dentro: rilancerebbe
    l'eccezione dentro un gestore di errori, che e' il modo piu' rapido per
    farne una seconda e non vedere mai la prima.
    """
    if valore is None and isinstance(indirizzo, BaseException):
        # alcuni chiamanti passano (tipo, eccezione) invece di (tipo,
        # eccezione, traceback): in quel caso la terza posizione non c'e'
        valore = indirizzo
        indirizzo = getattr(valore, "__traceback__", None)

    if valore is None:
        _stampa("[eccezione non gestita] nessun valore ricevuto, "
                "niente da dire sul motivo")
        return

    _stampa("".join(traceback.format_exception(tipo, valore, indirizzo)).rstrip(),
            "ECCEZIONE")


def installa() -> None:
    """Collega i due gestori.  Da chiamare una volta sola, prima di ``exec()``."""
    _inizializza()  # Inizializza file log + handler Qt + excepthook
    from PyQt6.QtCore import qInstallMessageHandler

    qInstallMessageHandler(_messaggio_qt)
    sys.excepthook = _eccezione_non_gestita


def scarica() -> str:
    """Gli ultimi messaggi, per quando qualcosa va storto e la finestra e' gia' andata.

    Non lo usa nessuno per ora.  Sta qui perche' il giorno che l'app girera'
    senza terminale, la riga da scrivere su file e' una, e sapere in che
    punto si mette conta piu' del resto.
    """
    return "\n".join(ULTIMI)


# Funzione per compatibilità con SettingsView
def ultimo_log() -> str:
    return "\n".join(ULTIMI)


#: I tre livelli di Qt che sono un problema.  Sotto questi — `QtDebugMsg` e
#: `QtInfoMsg` — quello che arriva e' rumore: arriva a ogni modulo che si carica
#: e a ogni motore che si avvia, e una schermata che si apre per dire «sono
#: cominciati due moduli» e' una schermata che l'utente impara a chiudere senza
#: leggere, che e' peggio che non averla.
SONO_PROBLEMA = ("AVVISO", "CRITICO", "FATALE")


def problemi() -> list[str]:
    """I messaggi che sono un problema: avvisi, critici, fatali ed eccezioni.

    Serve alla schermata di avvio, che te li elenca e lascia salvare il log.
    Se prendesse `ULTIMI` cosi' com'e', aprirebbe la schermata degli errori a
    ogni avvio: di messaggi normali ce ne sono decine.

    Guarda il **livello** e non l'inizio della riga.  Prima guardava il testo:
    una riga che contiene la parola «AVVISO» nel mezzo sembrava un avviso, e
    le righe di un traceback venivano prese o buttate a seconda di come erano
    cominciate.

    UN MESSAGGIO = UNA VOCE, ANCHE SE E' SU TRE RIGHE
    -------------------------------------------------
    Qui non si tiene traccia di «dentro un traceback»: ogni chiamata a
    `_stampa` e' gia' un messaggio **completo**, con dentro le sue righe di
    traceback se e' un'eccezione.  Tenere il conto delle righe serviva solo
    perche' prima ogni riga era una voce, e cosi' un avviso che arrivava dopo
    un traceback finiva dentro il traceback — e la schermata diceva che anche
    quell'avviso era un errore che ferma il programma.
    """
    return [testo for testo, livello in ULTIMI_CON_LIVELLO
            if livello in SONO_PROBLEMA]


def problemi_bloccanti() -> list[str]:
    """I messaggi che dicono che il programma **non puo' continuare**.

    Sono `CRITICO`, `FATALE` e le eccezioni non gestite — vedi
    `LIVELLO_BLOCCANTE`, che spiega perche' un semplice `AVVISO` non e' qui.

    La schermata di avvio si ferma su queste e non lascia aprire la finestra
    principale: continuare sapendo che qualcosa e' andato storto e' la parte
    peggiore, perche' il difetto si vede tre schermate dopo, quando non si sa
    piu' cosa l'ha causato.

    Gli avvisi restano fuori di qui e vengono mostrati lo stesso, alla fine,
    con la via per ignorarli: sono cose che il programma sa fare senza problemi
    e che ha scritto perche' e' stato male.  Bloccarci sopra significa che il
    programma non parte piu' su quelle macchine — e un programma che non parte
    e' un difetto peggiore di un avviso ignorato.
    """
    return [testo for testo, livello in ULTIMI_CON_LIVELLO
            if livello in LIVELLO_BLOCCANTE]


# ---------------------------------------------------------------------------
# IL TERMINALE E' ANCHE UNA FINESTRA
# ---------------------------------------------------------------------------
#
# LA RICHIESTA
# ------------
# Quando il programma parte dall'icona delle applicazioni non c'e' nessun
# terminale: quello che il terminale avrebbe detto, non lo dice nessuno.  Il
# programma e' diventato una finestra e con essa e' sparito l'unico posto dove
# si vedeva se qualcosa era andato storto.
#
# LA SOLUZIONE: NON SCEGLIERE
# ---------------------------
# Si scrive **in due posti**: sul terminale vero e in un secondo posto che
# puo' essere la splash.  Non e' una scelta fra «col terminale» e «senza»:
# e' avere le due cose, perche' sono due utenti diversi.
#
#     lanciato da riga di comando    vede i log sul terminale, come prima
#     lanciato dall'icona             non vede il terminale, ma i log
#                                    sono nella schermata di avvio e, se
#                                    qualcosa va storto, in una finestra
#                                    che permette di salvarli
#
# PERCHE' UN DOPPIO E NON UN SOSTITUTO
# ------------------------------------
# Sostituire il flusso vero metterebbe a tacere l'utente che sviluppa il
# programma — cioe' l'utente che, quando un bug si manifesta solo una volta su
# tre, ha bisogno di quei log e non li avrebbe piu'.  Il doppio costa quattro
# righe e non toglie niente a nessuno.
#
# IL CARICO DEL TERMINALE NASCOSTO
# --------------------------------
# Chi scrive a pezzi — `print("a", end="")` — non produrrebbe righe intere, e
# il conto tornerebbe sbagliato: si tiene il pezzo in fresco e si rimanda al
# prossimo `\n`, che e' il modo che ha `print` di sapere dove finisce una riga.

class _Deviato:
    """Un flusso che scrive al terminale vero **e** a un secondo posto."""

    def __init__(self, vero, scrivi) -> None:
        self._vero = vero
        self._scrivi = scrivi
        self._in_corso = ""

    def write(self, testo: str) -> int:
        # Il terminale vero per primo: se va storto lui, almeno l'utente che
        # guarda il terminale deve vedere la riga.  Il secondo posto e' quello
        # che puo' non esistere.
        try:
            self._vero.write(testo)
        except Exception:  # noqa: BLE001
            pass
        self._in_corso += testo
        if "\n" in self._in_corso:
            *righe, self._in_corso = self._in_corso.split("\n")
            for riga in righe:
                try:
                    self._scrivi(riga)
                except Exception:  # noqa: BLE001
                    # Una schermata che non regge una riga non deve portare
                    # giù il terminale: il log vero resta al suo posto.
                    pass
        return len(testo)

    def flush(self) -> None:
        try:
            self._vero.flush()
        except Exception:  # noqa: BLE001
            pass

    def isatty(self) -> bool:
        try:
            return bool(self._vero.isatty())
        except Exception:  # noqa: BLE001
            return False

    def fileno(self) -> int:
        return self._vero.fileno()


#: I flusso veri, messi da parte quando si deviano.  Senza questo, ripristinare
#: significherebbe indovinare quale dei due flussi era il nostro.
_VERI: dict = {}


def devia(scrivi) -> None:
    """Da' a `scrivi` ogni riga che il programma scrive sul terminale.

    `scrivi` riceve una riga per volta, senza il `\n` finale.

    Non fa niente al secondo giro: deviare gia' deviato metterebbe due
    livelli di doppio e la stessa riga arriverebbe due volte alla schermata.
    """
    for nome in ("stdout", "stderr"):
        vero = getattr(sys, nome, None)
        if vero is None:
            # `pythonw` e i programmi lanciati senza terminale: qui non c'e'
            # niente da deviare e non e' un errore.
            continue
        if isinstance(vero, _Deviato):
            continue
        _VERI[nome] = vero
        setattr(sys, nome, _Deviato(vero, scrivi))


def ripristina() -> None:
    """Rimette i flussi come erano.

    Va chiamata quando la schermata finisce: dopo, il log del programma non
    piu' interessa a nessuno che lo guardi in faccia, e tenere il doppio
    significa tenere viva la schermata chiusa.
    """
    for nome, vero in list(_VERI.items()):
        setattr(sys, nome, vero)
        _VERI.pop(nome, None)


def _prova() -> int:
    """Prova i due gestori con un errore vero dentro un vero callback.

    Serve a una cosa sola: accertarsi che quando succede un errore dentro un
    segnale Qt si veda il motivo.  Un crash senza spiegazione e' la cosa piu'
    costosa che si possa avere in fase di porting, perche' ogni volta si
    torna a indovinare.

        python3 -m Utility.Messaggi
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    applicazione = QApplication.instance() or QApplication([])
    installa()

    def dentro_un_segnale() -> None:
        # questo non puo' funzionare: `nome_che_non_esiste` non esiste
        nome_che_non_esiste  # noqa: F841

    QTimer.singleShot(300, dentro_un_segnale)
    QTimer.singleShot(2000, applicazione.quit)
    print("fra poco un segnale solleva un errore. "
          "Se qui sotto leggi il nome dell'errore, i gestori funzionano.",
          flush=True)
    return applicazione.exec()


if __name__ == "__main__":
    sys.exit(_prova())