#
#  Ext_DispatchQueue.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Estensioni su DispatchQueue.

In Swift:

    DispatchQueue.background(delay: 0.0, background: nil, completion: nil)

lavoro in coda e il ``completion`` sul main thread, con ritardo.  Qui il
lavoro gira in un ``threading.Thread`` e il ``completion`` torna sul main
thread passando da un segnale Qt.

PERCHE' UN SEGNALE E NON UNA FUNZIONA
-------------------------------------
COME-FUNZIONA.txt sezione 14: "toccare la finestra da un thread che non e'
quello della grafica" e' una delle trappole che hanno rotto l'app piu' di
una volta.  In Python una chiamata diretta a un metodo di un QWidget da un
thread estraneo spesso funziona e poi rompe in un modo difficile da leggere.
Un segnale emesso da un thread estraneo e' sempre consegnato in coda al
thread che ha creato la QObject, quindi il callback finisce *di sicuro* sul
main thread.  E' la stessa garanzia che dava DispatchQueue.main.async.
"""

import sys
import threading
import traceback

from PyQt6 import sip
from PyQt6.QtCore import QObject, QTimer, pyqtSignal as Signal


class _MainQueue(QObject):
    """Il equivalente di DispatchQueue.main: consegna sul thread della GUI."""

    run = Signal(object, float)

    def __init__(self) -> None:
        super().__init__()
        # AutoConnection: emesso da un thread estraneo, finisce accodato al
        # main thread.  Emesso dal main thread, viene eseguito subito.
        self.run.connect(self._esegui)

    def _esegui(self, func, delay: float) -> None:
        """Esegue il richiamo sul main thread.

        UN ECCEZIONE QUI FA ``abort()``
        --------------------------------
        Questa funzione e' il corpo di un segnale Qt.  Un'eccezione
        Python dentro un segnale Qt non viene propagata: PyQt6 chiama
        ``qFatal`` e l'applicazione muore, senza che il chiamante possa
        fare niente.  Quindi il try e' qui dentro, non intorno a chi
        emette.

        Non e' una pignoleria.  Il caso reale: una schermata viene
        cancellata mentre un download e' in corso, e il richiamo tocca un
        oggetto che non esiste piu'.

        QUELLO CHE IL TRY NON PUO' FARE
        --------------------------------
        Non puo' salvare da una ``segfault``.  Emettere il segnale di un
        ``QObject`` distrutto non solleva un'eccezione Python: va a
        leggere memoria liberata e muore.  Il try non serve, non c'e' niente
        da catturare.

        Per questo il richiamo non deve mai essere un segnale nudo di una
        schermata: deve essere una funzione che prima controlla se la
        schermata esiste ancora (`sip.isdeleted`) e poi, solo se esiste,
        emette.  Il try qui e' la rete di sicurezza per gli altri errori;
        quella e' la difesa vera, e sta nei chiamanti.
        """
        try:
            if delay:
                QTimer.singleShot(int(delay * 1000), func)
            else:
                func()
        except Exception:  # noqa: BLE001
            sys.stderr.write(
                "\n[background] il richiamo sul main thread e' fallito:\n"
                + "".join(traceback.format_exc())
            )
            sys.stderr.flush()


_main_queue = _MainQueue()


def _emetti(func, delay: float) -> None:
    """Emette sul main thread, se `_main_queue` esiste ancora.

    ALLA CHIUSURA
    -------------
    Quando l'applicazione finisce, Python distrugge gli oggetti Qt mentre i
    thread in background possono non aver ancora finito.  Un thread che a
    quel punto emette il segnale di `_main_queue` la trova distrutta, e
    PyQt6 alza:

        RuntimeError: wrapped C/C++ object of type _MainQueue has been deleted

    La chiusura sta succedendo, e nessuna schermata puo' fare niente:
    l'unica cosa giusta e' non emettere.  `sip.isdeleted` lo vede e il
    thread passa oltre, come fanno gia' i chiamanti con `sip.isdeleted`
    prima di toccare una schermata.
    """
    if sip.isdeleted(_main_queue):
        return
    _main_queue.run.emit(func, delay)


def on_main(func, delay: float = 0.0) -> None:
    """Esegui ``func`` sul main thread, eventualmente dopo ``delay`` secondi."""
    _emetti(func, delay)


def background(func=None, *, delay: float = 0.0, completion=None):
    """Lancia ``func`` in background; ``completion`` sul main thread dopo ``delay``.

    Se ``func`` e' None si puo' usare solo come "mandaci questo al main
    thread".  Il thread non e' joinato e non blocca: come ``.async`` in
    Swift, non come ``.sync``.
    """

    def runner() -> None:
        # UN LAVORO CHE MUORE NON PUO' PORTARE VIA IL THREAD SENZA DIRE
        # ------------------------------------------------------
        # Prima questo era:
        #
        #     if func is not None:
        #         func()
        #     if completion is not None:
        #         _main_queue.run.emit(completion, delay)
        #
        # Se `func` sollevava, l'eccezione usciva da `runner`, Python
        # stampava una traceback e il thread moriva.  Non succedeva nient'altro,
        # e in particolare `completion` non veniva mai chiamato: la schermata
        # restava con la riga "sto scaricando" per sempre, e l'unica traccia
        # del motivo era una traceback in mezzo all'output di un thread, dove
        # nessuno la cerca.
        #
        # Il caso vero e' comparso con `BibleView`: la schermata veniva
        # cancellata mentre scaricava i capitoli, e a un certo punto il thread
        # provava a emettere l'avanzamento su una vista che non esisteva piu':
        #
        #     RuntimeError: wrapped C/C++ object of type BibleView
        #     has been deleted
        #
        # QUI SI MISURA IL CONTRATTO
        # -------------------------
        # Se il lavoro fallisce, `completion` NON viene chiamato.
        #
        # Sembra scortese, e lo e': chiamarlo sarebbe dire "finito" quando
        # non e' finito, e la schermata mostrerebbe una riga di stato che
        # promette un risultato che non c'e'.  Un lavoro fallito che non si
        # presenta come riuscito e' meglio di un lavoro fallito che lo fa.
        #
        # Il richiamo e' pero' in `stderr` e non perso: `Messaggi` adesso
        # stampa anche i messaggi di Qt, e qui sotto si scrive lo stesso.
        if func is not None:
            try:
                func()
            except Exception:  # noqa: BLE001
                sys.stderr.write(
                    "\n"
                    f"[background] il lavoro in background e' fallito: "
                    f"{getattr(func, '__name__', func)}\n"
                    + "".join(traceback.format_exc())
                )
                sys.stderr.flush()
                return
        if completion is not None:
            _emetti(completion, delay)

    threading.Thread(target=runner, daemon=True).start()