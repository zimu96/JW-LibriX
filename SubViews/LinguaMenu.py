#
#  LinguaMenu.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 04/10/26.
#

"""Il menu della lingua: un campo di ricerca e le 874 lingue.

PERCHE' UN MENU E NON UN MENU A TENDINA
----------------------------------------
Le lingue sono 874, non due.  Un ``QComboBox`` con dentro 874 righe e' un
elenco che si deve scorrere centinaia di volte per arrivare a «Kongo», e
sulla fascia, che e' alta 32 pixel, non ci sta comunque.

Quindi e' un menu che si apre: la fascia ha il pulsante, il pulsante apre
il menu, e nel menu c'e' il campo dove si scrive.  E' quello che fa
l'app originale.

IL CAMPO DI RICERCA DENTRO UN QMenu
-----------------------------------
Un ``QMenu`` accetta un widget qualunque dentro una ``QWidgetAction``, e li'
dentro ci sta un ``QLineEdit``.  Il menu resta aperto mentre ci si scrive e le
voci sotto cambiano a ogni tasto.

La parte che va detta: il campo prende i tasti e il menu no.  Se il campo non
prendesse i tasti, scrivere «ita» farebbe muovere la voce evidenziata invece
di cercare, e la lista sembrerebbe non reagire.

LE TRE COSE CHE IL MENO FA BENE
-------------------------------
1.  La lingua scelta ha il segno di spunta accanto.  Senza, non si sa quale
    e' quella attuale, e in un elenco di 874 righe non si trova a occhio.

2.  Il nome e' quello nella propria lingua.  Chi cerca «Deutsch» lo cerca
    cosi', non come «German»: vedi `Lingua.titolo`.

3.  Il numero di pubblicazioni e' scritto accanto al nome, perche' due lingue
    vicine possono avere una differenza grande e scegliere quella sbagliata
    costa un download.  Il numero viene da `Files/lingue.json`, che e' la
    tabella dell'originale: non e' un conteggio fatto qui e non cambia se il
    catalogo non e' presente.

IL MENO NON SCRIVE NULLA DA SOLO
-------------------------------
Il menu sceglie e basta: emette `scelta` con il numero e chi ascolta fa il
resto.  Un menu che cambia la lingua da solo dovrebbe sapere quali schermate
ricreare, e quel gesto e' della finestra, che le ha costruite: vedi
`SidebarView._lingua_scelta`.
"""

from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtWidgets import QLineEdit, QMenu, QWidget, QWidgetAction

from Utility import Lingua

#: Quante voci si disegnano quando il campo e' vuoto.
#:
#: Non e' un limite di quanto si puo' scegliere: si puo' scegliere tutte le
#: 874 lingue, e `cerca()` le cerca tutte.  E' il numero di righe disegnate
#: sotto un campo vuoto.
#:
#: Il perche' e' 60 e non 874: un ``QMenu`` con 874 voci da' un elenco che
#: si deve scorrere di tre schermate per trovare la Spagnola, che e' la
#: quarta in ordine di pubblicazioni.  Con 60 righe le lingue grandi ci sono
#: tutte e il resto si trova scrivendo.  E' la stessa regola che usa un menu
#: di un sistema operativo: non si disegnano 874 voci per scegliere una
#: stampante.
VOCI_NEL_CAMPO_VUOTO = 60


class LinguaMenu(QMenu):
    """Il menu della lingua."""

    #: Il numero (``LanguageId``) della lingua scelta.  Chi ascolta fa il resto.
    scelta = Signal(int)

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("menuLingua")
        self._costruisci_campo()
        self._costruisci_voci("")
        self._collegato_a_se_stesso()

    # ------------------------------------------------------------------
    # IL CAMPO
    # ------------------------------------------------------------------

    def _costruisci_campo(self) -> None:
        """Il campo di ricerca, in cima al menu."""
        self.campo = QLineEdit(self)
        self.campo.setObjectName("campoLingua")
        self.campo.setPlaceholderText("Cerca la lingua")
        self.campo.setClearButtonEnabled(True)
        self.campo.textChanged.connect(self._testo_cambiato)

        # Il widget va messo in un QWidgetAction perche' un QMenu accetta
        # solo azioni: senza questo non c'e' modo di metterci dentro un campo.
        contenitore = QWidgetAction(self)
        contenitore.setDefaultWidget(self.campo)
        # `addAction` e' l'unico modo: `setWidget` non esiste su un QMenu, e
        # provarlo e' l'errore che si fa subito.
        self.addAction(contenitore)
        self.addSeparator()

    def _testo_cambiato(self, testo: str) -> None:
        """Il campo e' cambiato: si rifanno le voci.

        Il blocco dei segnali serve perche' togliere e rimettere le azioni
        cambia `currentIndex` e `textChanged` senza che nessuno lo abbia
        scritto: senza il blocco, ricostruire la lista la ricostruirebbe due
        volte per ogni tasto, e con 874 lingure ogni tasto costerebbe il
        doppio.
        """
        self.blockSignals(True)
        try:
            self._costruisci_voci(testo)
        finally:
            self.blockSignals(False)

    # ------------------------------------------------------------------
    # LE VOCI
    # ------------------------------------------------------------------

    def _costruisci_voci(self, testo: str) -> None:
        """Le voci, per quello che c'è nel campo."""
        # Si tolgono TUTTE le azioni tranne quella che contiene il campo, e
        # si tolgono davvero (`removeAction`) invece di nasconderle: una voce
        # nascosta dentro un QMenu occupa ancora spazio e si puo' ancora
        # scegliere con i tasti della tastiera, e una voce invisibile che si
        # puo' scegliere e' il difetto piu' difficile da notare di tutti.
        for azione in list(self.actions()):
            if not isinstance(azione, QWidgetAction):
                self.removeAction(azione)

        corrente = Lingua.corrente_id()
        if not testo.strip():
            # Campo vuoto: le lingue con piu' pubblicazioni, e non tutte.
            # `cerca("")` restituisce comunque tutte le lingue: e' il numero
            # qui a capo che decide quante mostrarne, quindi la ricerca e'
            # sempre la stessa e non ci sono due strade diverse da mantenere.
            elenco = Lingua.cerca("")[:VOCI_NEL_CAMPO_VUOTO]
        else:
            elenco = Lingua.cerca(testo)

        for voce in elenco:
            numero = voce.get("id")
            if numero is None:
                continue
            azione = self.addAction(self._testo_voce(voce))
            azione.setCheckable(True)
            azione.setChecked(numero == corrente)
            # `triggered` passa un booleano: si scarta perche' la voce porta
            # gia' il numero dentro e il segnale non ne ha bisogno.
            azione.triggered.connect(lambda _stato, n=numero: self.scelta.emit(n))

        if not elenco:
            nessuna = self.addAction("Nessuna lingua con questo nome")
            nessuna.setEnabled(False)

    @staticmethod
    def _testo_voce(voce: dict) -> str:
        """La riga di una lingua: nome, e quante pubblicazioni ha.

        Il numero di pubblicazioni sta fra parentesi quadre e non dopo una
        lineetta: con 874 righe la colonna delle pubblicazioni deve stare
        stretta e non rubare il nome, che e' la cosa che si legge.
        """
        nome = Lingua.titolo(voce)
        quanti = voce.get("pubblicazioni") or 0
        if not quanti:
            return nome
        return f"{nome}  [{quanti}]"

    # ------------------------------------------------------------------
    # IL COLLEGAMENTO
    # ------------------------------------------------------------------

    def _collegato_a_se_stesso(self) -> None:
        """Il menu si collega da solo, e non e' un dettaglio.

        `QMenu` si chiude quando si sceglie una voce.  Senza questo passaggio,
        la `QWidgetAction` che contiene il campo verrebbe rimossa insieme al
        menu e il campo — e con lui il testo scritto — sparirebbe alla
        prima scelta.  Con questo collegamento la `QWidgetAction` resta vivo
        finche' il campo ha il focus, quindi si puo' scegliere una lingua,
        riaprire il menu e ritrovarsi il testo che si era scritto.
        """
        try:
            self.aboutToHide.connect(self._dimentica_se_non_ha_focus)
        except Exception:  # noqa: BLE001 - se il collegamento non c'e' il menu funziona lo stesso
            pass

    def _dimentica_se_non_ha_focus(self) -> None:
        """Il menu si chiude: se il campo non aveva il focus, si svuota.

        Chi scrive una lingua e poi sceglie una voce torna a riaprire il menu
        e vuole trovarla l'unica lingua che c'era, non quella che aveva
        scritto prima.  Ma chi sta ancora scrivendo non deve perdere il testo
        a meta' frase: e' per questo che si controlla il focus.
        """
        if self.campo.hasFocus():
            return
        if self.campo.text():
            self.campo.blockSignals(True)
            self.campo.clear()
            self.campo.blockSignals(False)
            self._costruisci_voci("")