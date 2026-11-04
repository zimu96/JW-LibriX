#
#  SubViews/MediaView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I media: l'audio e il video, con le locandine e il lettore.

PERCHE' UNA SEZIONE E NON DUE
-----------------------------
Audio e video stanno nella stessa sezione perche' vengono dalla stessa
domanda al server e perche' si scelgono insieme: l'utente che cerca un
video di una lezione vuole anche sentire l'audio, e viceversa.  Sono due
schede dentro una sezione, non due sezioni della rail: due sezioni
avrebbero due icone che dicono la stessa cosa.

LE COPERTINE SONO LE LOCANDINE, NON LE COPERTINE
-----------------------------------------------
Le immagini dei media si chiedono per ``docid`` e non per sigla.  Sono due
famiglie diverse con due identificatori diversi, e sbagliare porta a 403:

    libro      img/p/{chiave}/{lingua}/pt/...       per la sigla breve
    media      img/p/{docid}/univ/art/...          per il docid

Quindi qui non si riusa `pixmap_copertina`, che cerca il pacchetto di un
libro, e si usa `pixmap_locandina`.

IL LETTORE
----------
E' la parte che l'utente tocca.  I comandi sono quelli che ci sono, non
quelli che si potrebbero aggiungere:

    play e pausa     un pulsante che cambia faccia, non due pulsanti
    volume           un cursore e il glifo delle casse
    schermo intero   si espande e si rientra
    sottotitoli     ci sono o no, e lo dice il glifo
    chiudi           esce dal lettore e torna alla lista

PERCHE' IL PLAY E' UN PULSANTE SOLO
-----------------------------------
Due pulsanti, play e pausa, con uno dei due sempre spento, e' la cosa che
si vede in giro.  E non funziona: l'utente prema quello spento, non
succede niente, e sembra che il pulsante sia rotto.  Un pulsante che
cambia faccia e' un pulsante che e' sempre quello giusto.

I GLIFI DEI COMANDI
-------------------
Vengono dalla tabella dei nomi, non dai nomi dei file Tabler: `play.fill`,
`pause.fill`, `speaker.wave.2`, `stop.fill`.  E' la stessa regola del
resto del porting, e sbagliarla dà un pulsante con dentro il nulla senza
dire niente.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal as Signal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from Utility import Copertine, Lingua, MepsAPI, Mediator, tema
from Utility.Stuff import icon, icona_tabler
from Utility.Extensions import on_main

from SubViews.LettoreView import LettoreView

# NOTA SUL TITOLO DI GRUPPO
# --------------------------
# Nella sezione Scaricati c'e' gia' una classe `_TitoloGruppo`.  Qui non si
# importa e non si riusa direttamente, e il perche' e' una scelta: i due
# moduli non hanno un'altra ragione per conoscersi, e un import fra due
# sezioni per quattro righe crea un ordine d'importazione che prima o poi si
# rompe — e quando si rompe, per colpa di quattro righe che sembravano una
# cosa sola.
#
# Quindi la classe e' rifatta qui sotto.  Il perche' non si puo' fare il
# contrario, cioe' metterla in un posto solo e importarla, e' che quella
# cosa sola dovrebbe stare in `Utility`: e un widget con i suoi colori non ha
# niente a che fare con `JWPubManager` o con `Copertine`.  Se un domani i due
# titoli di gruppo dovessero davvero essere uguali, il posto giusto e' un
# modulo di widget comuni, non un import circolare.
#
# Quello che invece e' gia' uguale, e non e' una scelta ma una regola: il
# nome dell'oggetto e' `titoloGruppo` in tutti e due i posti, quindi
# prendono lo stesso stile dal foglio di tema.  `controllo.py` controlla gli
# oggetti di nome che non esistono, quindi se un domani i due nomi si
# dividessero, lo direbbe.

# Le schede della sezione: (titolo, simbolo del progetto originale)
SCHEDE = [("Audio", "headphones"), ("Video", "film")]

# I comandi del lettore: (nome, simbolo del progetto, tooltip)
#
# Solo quattro, e sono i quattro che ci sono.  Nelle 82 icone del progetto
# precedente non ci sono il glifo dello schermo intero ne' quello dei
# sottotitoli, e metterli avrebbe dato due pulsanti con dentro il nulla.
# Meglio quattro comandi che si vedono che sei con due che non si vedono.
COMANDI = [
    ("riproduci", "play.fill", "Riproduci o ferma"),
    ("indietro", "backward.fill", "Indietro"),
    ("avanti", "forward.fill", "Avanti"),
    ("volume", "speaker.wave.2", "Volume"),
    ("preferito", "star.fill", "Fra i Preferiti"),
    ("ferma", "stop.fill", "Chiudi"),
]

#: Quando si ricontrolla il server.  Un'ora, come per gli aggiornamenti.
VALE_PER = 3600


class _SchedaCliccabile(QLabel):
    """La scheda Audio / Video, che si preme.

    PERCHE' NON UNA QLabel CON clicked
    ---------------------------------
    ``QLabel`` non ha il segnale ``clicked``: lo danno i pulsanti e le
    caselle di spunta.  Aggiungerlo con ``QLabel.clicked.connect`` dà

        AttributeError: 'QLabel' object has no attribute 'clicked'

    e la scheda sembra una scritta che si può premere: si vede esattamente
    come un pulsante e non è un pulsante, e non si capisce perché non
    funziona.

    Qui si scrive una classe che lo aggiunge.  Il segnale è a livello di
    classe, per la ragione di sempre: dentro ``__init__`` un segnale
    PyQt6 non viene registrato e ``connect`` non esiste.
    """

    clic = Signal(int)

    def __init__(self, indice: int, testo: str, padre=None) -> None:
        super().__init__(testo, padre)
        self._indice = indice
        self.setObjectName("scheda")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self._indice)
        super().mousePressEvent(evento)


class _Tab(QLabel):
    """Una delle quattro tab della Biblioteca.

    PERCHE' UNA CLASSE E NON RIUSARE `_SchedaCliccabile`
    --------------------------------------------------
    `_SchedaCliccabile` si chiama cosi' perche' e' una **scheda a capsula**:
    il suo nome nel foglio di stile e' `#scheda`, che ha lo sfondo acceso e
    gli angoli tondi.  La tab della Biblioteca e' un pezzo diverso: sfondo
    trasparente e una **barra** viola di 3 pixel sotto, e il suo nome e'
    `#tab`.

    Con la stessa classe si sarebbe dovuto cambiare il nome dell'oggetto da
    una parte sola, e allora o le tab della Biblioteca avrebbero perso la
    barra, o le schede a capsula della sezione Impostazioni — che usano lo
    stesso `#scheda` — l'avrebbero presa.  Sono due pezzi che si somigliano e
    per questo hanno due classi.

    IL NOME DELL'OGGETTO DIPENDE DA SE' ATTIVA
    ------------------------------------------
    Non c'e' una regola `QSS` per lo stato attivo: si cambia il nome
    dell'oggetto.  In Qt il nome dell'oggetto e' l'unica cosa che distingue
    due stati di uno stesso widget, e qui i due stati sono davvero diversi:
    colore del testo e spessore del carattere.
    """

    clic = Signal(int)

    def __init__(self, indice: int, testo: str, attiva: bool = False,
                 padre=None) -> None:
        super().__init__(testo.upper(), padre)
        self._indice = indice
        self.setObjectName("tabAttiva" if attiva else "tab")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def attendi(self, attiva: bool) -> None:
        """Rende questa tab attiva o no, cambiandole il nome."""
        nome = "tabAttiva" if attiva else "tab"
        if self.objectName() != nome:
            self.setObjectName(nome)
            # Senza questo, il colore nuovo non arriva: in Qt un oggetto che
            # cambia nome ha bisogno di un avviso per ricalcolare lo stile,
            # e fino a quel momento resta con il colore vecchio.
            self.style().unpolish(self)
            self.style().polish(self)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clic.emit(self._indice)
        super().mousePressEvent(evento)


class _TitoloGruppo(QLabel):
    """Il nome di un gruppo di media, con quante voci ha.

    La stessa forma del titolo di gruppo della sezione Scaricati: piccolo,
    grassetto, con il numero accanto.  Si rifa qui e non si importa perche'
    `MediaView` e `DownloadsView` non hanno altra ragione di conoscersi, e un
    import fra due sezioni per quattro righe crea un ordine d'importazione
    che prima o poi si rompe.

    Se un domani il nome dell'oggetto di nome cambiasse in uno dei due
    posti, `controllo.py` lo segnala: controlla gli oggetti di nome che non
    esistono nel foglio di stile.
    """

    def __init__(self, testo: str, parent=None) -> None:
        super().__init__(testo, parent)
        self.setObjectName("titoloGruppo")


class _RigaMedia(QWidget):
    """Una riga: la locandina, il titolo, la durata, il pulsante."""

    scelto = Signal(dict)

    def __init__(self, voce: dict, padre=None) -> None:
        super().__init__(padre)
        from Utility import tema as _tema
        _tema.sfondo(self, "rigaMedia")
        self.voce = voce

        disposizione = QHBoxLayout(self)
        disposizione.setContentsMargins(8, 6, 8, 6)
        disposizione.setSpacing(10)

        self.miniatura = QLabel(self)
        self.miniatura.setObjectName("miniatura")
        self.miniatura.setFixedSize(56, 32)
        self.miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Prima l'anteprima, e solo se non c'e' il glifo.  Il glifo e' il
        # ripiego: se ci mettesse sopra l'immagine, un'immagine scaricata
        # sembrerebbe non esistere.
        anteprima = voce.get("_anteprima")
        if anteprima is not None and not anteprima.isNull():
            from Utility import Copertine
            self.miniatura.setPixmap(Copertine.pixmap_riempi(anteprima, 56, 32))
        else:
            self.miniatura.setPixmap(
                icon(_glifo_per(voce), "#ffffff", 18).pixmap(18, 18))
        disposizione.addWidget(self.miniatura)

        testo = QWidget(self)
        colonna = QVBoxLayout(testo)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)

        nome = QLabel(voce.get("title") or voce.get("label") or "?", testo)
        nome.setObjectName("titoloRiga")
        nome.setWordWrap(True)
        colonna.addWidget(nome)

        sotto = QLabel(_dettaglio(voce), testo)
        sotto.setObjectName("nota")
        colonna.addWidget(sotto)
        disposizione.addWidget(testo, 1)

        self.pulsante = QLabel(self)
        self.pulsante.setPixmap(icon("play.fill", tema.ACCENTO, 20).pixmap(20, 20))
        self.pulsante.setFixedSize(28, 28)
        self.pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
        disposizione.addWidget(self.pulsante, 0)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.scelto.emit(self.voce)
        super().mousePressEvent(evento)


def _descrizione_categoria(chiave: str) -> str:
    """La riga che spiega che cos'e' una categoria.

    Viene dalla tabella di `Mediator.CATEGORIE`, che e' una scritta del
    programma e non un dato del server: serve per il suggerimento che
    compare sopra la linguetta, e li' un'approssimazione e' accettabile
    perche' il nome e l'unica cosa che resta sempre giusta e viene dal
    server.  Se la chiave non e' nella tabella si restituisce la chiave
    stessa: meglio il nome tecnico che una descrizione inventata.
    """
    for chiave_Nota, _nome, descrizione in Mediator.CATEGORIE:
        if chiave_Nota == chiave:
            return descrizione
    return chiave


def _glifo_per(voce: dict) -> str:
    """Il glifo per un media che non ha anteprima."""
    return "film" if _e_video(voce) else "headphones"


def _e_audio(voce: dict) -> bool:
    """Questa voce e' un audio?

    TRE INDIZI, IN QUESTO ORDINE
    ---------------------------
    Il primo e' il campo `tipo`, che scrive il server accanto al file:
    misurato, vale `"audio"` o `"video"` e nient'altro.  E' la risposta piu'
    sicura perche' e' dichiarata da chi ha preparato il file.

    Poi il mimetype, che comincia con `audio/`, e infine l'assenza di
    risoluzione: un audio non ha larghezza ne' altezza.

    Il perche' dei tre: il mediator scrive `tipo` e il mimetype insieme, ma
    le voci che vengono da `MepsAPI` (i media dentro una pubblicazione) non
    hanno `tipo` e arrivano con il mimetype.  Senza gli indizi di sotto, una
    voce senza mimetype restava fuori da tutte e due le griglie: non
    compariva nella scheda Audio e non compariva nella scheda Video, e la
    cosa non diceva niente.

    IL MIME, E NON IL FORMATO
    -------------------------
    Nella risposta del server ogni voce ha un `format` — JWPUB, PDF, RTF, ZIP
    — e un `mimetype`.  Il `format` dice in che formato e' impacchettata una
    cosa, e quasi tutte le voci sono `JWPUB`: guardarlo non distingue un video
    da una copertina.

    Prima il filtro guardava solo se c'era un mimetype qualunque, e metteva
    dentro anche i 95 file che non sono media.  Il risultato era una scheda
    Audio con dentro dei PDF, e le anteprime mancavano perche' quei file non
    ne hanno: la riga giusta c'era, ma 30 righe prima c'erano le sbagliate.
    """
    if (voce.get("tipo") or "").strip().lower() == "audio":
        return True
    return (voce.get("mimetype") or "").lower().startswith("audio/")


def _e_video(voce: dict) -> bool:
    """Questa voce e' un video?

    Tre indizi, e vanno d'accordo: il `tipo` che scrive il server, il
    mimetype che comincia per ``video/`` oppure la risoluzione, perche' un
    video ha sempre larghezza e altezza e un audio non le ha mai.

    `tipo` viene prima perche' e' il dato piu' diretto; gli altri due sono
    cio' che si ricava quando `tipo` non c'e'.
    """
    if (voce.get("tipo") or "").strip().lower() == "video":
        return True
    if (voce.get("mimetype") or "").lower().startswith("video/"):
        return True
    return bool(voce.get("frameWidth") and voce.get("frameHeight"))


def _pixel(voce: dict) -> int:
    """I pixel di una voce, come numero per confrontare due risoluzioni."""
    return int(voce.get("frameWidth") or 0) * int(voce.get("frameHeight") or 0)


def _indirizzo(voce: dict) -> str:
    """L'indirizzo del file di una voce di `MepsAPI`, o stringa vuota.

    IL TRABATTO: L'INDIRIZZO STA DENTRO ``file``
    --------------------------------------------
    `MepsAPI.media` restituisce le voci come sono scritte nella risposta del
    server, e li' l'indirizzo non e' un campo della voce ma un oggetto dentro
    ``file``::

        voce["file"]["url"]

    `Lettore.suona` invece cerca ``voce["url"]``.  Senza questo passaggio la
    riga si preme, il lettore non trova nessun indirizzo e il video non parte:
    e' il difetto «non parte in streaming se non e' scaricato».  Mai piu' di
    una volta: la conversione si fa qui, in un posto solo.
    """
    file_voce = voce.get("file")
    if isinstance(file_voce, dict):
        return file_voce.get("url") or ""
    if isinstance(file_voce, str):
        return file_voce
    return ""


def _checksum(voce: dict) -> str:
    """Il checksum del file di una voce di `MepsAPI`."""
    file_voce = voce.get("file")
    if isinstance(file_voce, dict):
        return file_voce.get("checksum") or ""
    return ""


def _raggruppa_tracce(voci: list, sigla: str) -> list:
    """Una voce per traccia, con dentro tutte le sue risoluzioni.

    IL DIFETTO CHE RISOLVE
    ----------------------
    `MepsAPI.media` risponde una voce per **risoluzione**: `wsb` esce otto
    volte, due video per quattro risoluzioni.  Le risoluzioni sono alternative
    dello stesso file, non voci diverse: in elenco la stessa lezione compariva
    quattro volte, e — peggio — l'indirizzo in ognuna stava dentro ``file`` e
    non in ``url``, quindi premendo la riga il lettore diceva «non so dove sia
    questo file» e non partiva niente.

    Qui si tiene una voce per traccia e le risoluzioni vanno dentro
    ``risoluzioni``, che e' la forma che `Mediator.scegli_risoluzione` e il
    lettore gia' conoscono — la stessa di `Mediator.voci`, la stessa che fa
    funzionare le categorie.  E si scrive ``sigla``, cosi' `Lettore` riconosce
    il file gia' scaricato e suona quello invece dell'indirizzo.

    La voce della riga parte dalla risoluzione **piu' piccola**, come in
    `Mediator.voci`: l'alta la sceglie `scegli_risoluzione` misurando la
    casella, e su una macchina senza accelerazione partire a 720p la fa
    impiantare.

    Quello che non e' un media a tracce si tiene com'e': scartarlo qui
    sarebbe una decisione presa al posto sbagliato — la sezione sa gia' cosa
    mostrare.
    """
    gruppi: dict = {}
    ordine: list = []
    altri: list = []

    for voce in voci:
        if not isinstance(voce, dict):
            continue
        indirizzo = _indirizzo(voce)
        traccia = MepsAPI.traccia_numero(voce)
        if _e_video(voce):
            genere = "video"
        elif _e_audio(voce):
            genere = "audio"
        else:
            genere = ""

        if traccia <= 0 or not genere or not indirizzo:
            copia = dict(voce)
            if indirizzo and not copia.get("url"):
                copia["url"] = indirizzo
            altri.append(copia)
            continue

        identificatore = (traccia, genere)
        if identificatore not in gruppi:
            base = dict(voce)
            base["sigla"] = (base.get("sigla") or base.get("pub")
                             or base.get("pubSymbol") or sigla)
            base["url"] = indirizzo
            base["checksum"] = _checksum(voce)
            base["risoluzioni"] = []
            gruppi[identificatore] = base
            ordine.append(identificatore)

        base = gruppi[identificatore]
        base["risoluzioni"].append({
            "label": str(voce.get("label") or ""),
            "url": indirizzo,
            "checksum": _checksum(voce),
            "filesize": voce.get("filesize") or 0,
            "frameWidth": voce.get("frameWidth") or 0,
            "frameHeight": voce.get("frameHeight") or 0,
        })
        # La risoluzione piu' piccola diventa quella della riga.
        if _pixel(voce) and _pixel(voce) < _pixel(base):
            base["url"] = indirizzo
            base["checksum"] = _checksum(voce)
            base["frameWidth"] = voce.get("frameWidth") or 0
            base["frameHeight"] = voce.get("frameHeight") or 0
            base["label"] = voce.get("label") or ""

    return [gruppi[i] for i in ordine] + altri


def _dettaglio(voce: dict) -> str:
    """La riga sotto il titolo: durata, risoluzione, formato."""
    pezzi = []
    durata = voce.get("duration")
    if isinstance(durata, (int, float)) and durata > 0:
        secondi = int(durata) % 60
        minuti = int(durata) // 60
        pezzi.append(f"{minuti}:{secondi:02d}")
    if voce.get("frameWidth") and voce.get("frameHeight"):
        pezzi.append(f"{int(voce['frameWidth'])}x{int(voce['frameHeight'])}")
    if voce.get("bitRate"):
        # IL bitRate E' GIA' IN kbit/s
        #
        # Misurato su lff: 127.0 e 159.4.  Sono kilo, non bit.  Dividendo
        # per mille come se fossero bit si ottiene 0, e la riga mostrava
        # "0 kbit/s" sotto ogni traccia.
        #
        # La difesa non e' "se minore di 1000 allora sono kilo": se un
        # giorno il server mandasse i bit veri, quella prova darebbe kilo
        # dove servono i bit.  Si usa il numero come arriva e si cambia la
        # parola, perche' il dato del server e' il dato del server.
        bitrate = voce["bitRate"]
        pezzi.append(f"{bitrate:.0f} kbit/s" if bitrate >= 1
                     else f"{bitrate * 1000:.0f} bit/s")
    if voce.get("subtitled"):
        pezzi.append("sottotitoli")
    if voce.get("formatDescr"):
        pezzi.append(voce["formatDescr"])
    return " · ".join(pezzi) if pezzi else "—"


class _HandleRidimensiona(QWidget):
    """Handle tra player e lista: drag fluido stile reference.

    COMPORTAMENTO REFERENCE:
    -----------------------
    - Hover sull'handle → cursore SplitVCursor (doppia freccia verticale)
    - Click + drag sull'handle → ridimensiona player vs lista fluidamente
    - Il blocco player (video + comandi) e la lista scalano insieme

    L'handle è una striscia sottile (8px) tra i due widget.
    """

    def __init__(self, player_widget, lista_widget, layout_padre, idx_player, idx_lista, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("handleRidimensiona")
        self.setFixedHeight(8)
        self.setCursor(Qt.CursorShape.SplitVCursor)  # Doppia freccia verticale
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setStyleSheet("""
            #handleRidimensiona {
                background-color: transparent;
                border-top: 1px solid #555;
                border-bottom: 1px solid #555;
            }
            #handleRidimensiona:hover {
                background-color: #3a3a3a;
            }
        """)

        self._player = player_widget
        self._lista = lista_widget
        self._layout = layout_padre
        self._idx_player = idx_player
        self._idx_lista = idx_lista
        self._trascinando = False
        self._pos_iniziale_y = 0
        self._altezza_totale_fissa = 0
        self._altezza_player_iniziale = 0

    def enterEvent(self, evento) -> None:
        """Hover: assicura cursore corretto."""
        if not self._trascinando:
            self.setCursor(Qt.CursorShape.SplitVCursor)
        super().enterEvent(evento)

    def leaveEvent(self, evento) -> None:
        """Esci hover: ripristina cursore se non si sta trascinando."""
        if not self._trascinando:
            self.setCursor(Qt.CursorShape.SplitVCursor)
        super().leaveEvent(evento)

    def mousePressEvent(self, evento) -> None:
        """Inizia drag: fissa geometria iniziale per calcolo fluido."""
        if evento.button() == Qt.MouseButton.LeftButton:
            self._trascinando = True
            self._pos_iniziale_y = evento.globalPosition().y()
            # Fissa altezza totale all'inizio (evita feedback loop durante drag)
            self._altezza_totale_fissa = self._player.height() + self._lista.height()
            self._altezza_player_iniziale = self._player.height()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            evento.accept()
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:
        """Drag fluido: calcola nuova altezza player in pixel, applica stretch."""
        if self._trascinando and self._altezza_totale_fissa > 0:
            delta_y = evento.globalPosition().y() - self._pos_iniziale_y
            # INTUITIVO: Mouse GIÙ (delta positivo) → player PIÙ GRANDE (tira giù)
            # Mouse SU (delta negativo) → player PIÙ PICCOLO (spinge su)
            nuova_altezza_player = self._altezza_player_iniziale + delta_y

            # Limiti in pixel (fluidi, niente scatti)
            min_player = 150   # video + comandi minimi
            max_player = self._altezza_totale_fissa - 100  # spazio minimo lista
            nuova_altezza_player = max(min_player, min(nuova_altezza_player, max_player))

            # Converti in stretch proporzionale (base 1000 per precisione)
            stretch_player = int(nuova_altezza_player * 1000 / self._altezza_totale_fissa)
            stretch_lista = 1000 - stretch_player
            self._layout.setStretch(self._idx_player, stretch_player)
            self._layout.setStretch(self._idx_lista, stretch_lista)
            evento.accept()
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:
        """Finisce drag."""
        if self._trascinando:
            self._trascinando = False
            self._altezza_totale_fissa = 0
            self._altezza_player_iniziale = 0
            self.setCursor(Qt.CursorShape.SplitVCursor)
            evento.accept()
        super().mouseReleaseEvent(evento)


# ---------------------------------------------------------------------------
# LE QUATTRO TAB DELLA BIBLIOTECA
# ---------------------------------------------------------------------------
#
# PERCHE' L'INDICE NON SEGUE L'ORDINE A SCHERMO
# ---------------------------------------------
# Nella finestra si legge, da sinistra: Pubblicazioni, Video, Audio, Scaricati.
#
# Ma l'indice che c'e' dentro `_scheda` e' un'altra cosa, e non puo' seguire
# quell'ordine perche' due pezzi di codice gia' lo usano con un numero
# fisso: `_quando_video` distingue con `self._scheda == 1`, e `SidebarView`
# chiama `apri_pubblicazione(pub, scheda)` con `0` per l'audio e `1` per il
# video.
#
# Se le quattro tab fossero state numerate nell'ordine in cui si vedono,
# l'audio sarebbe passato da 0 a 2 e `apri_pubblicazione(pub, 0)` avrebbe
# aperto il video.  Niente crash: si aprirebbe la scheda sbagliata, che e'
# il difetto piu' difficile da vedere.
#
# Quindi l'ordine a schermo e' una cosa e l'indice e' un'altra, e sono due
# tabelle.  La prima si legge, la seconda non si tocca senza leggere tutto
# il resto del file.

#: `(titolo, indice interno)` nell'ordine in cui si vedono.
#:
#: "Pubblicazioni" e non "Publicazioni": la **C** e' sbagliata.  La parola
#: italiana e' "pubblicazioni" (doppia b, niente c), ed e' il nome con cui la
#: sezione si chiama in tutta l'app.  Con la C l'utente non riconosceva la tab
#: e credeva che il catalogo fosse sparito dalla Biblioteca: la parola scritta
#: male sembrava una sezione diversa, quindi non era la sua.
TABS = [
    ("Pubblicazioni", 2),
    ("Video", 1),
    ("Audio", 0),
    ("Scaricati", 3),
]

#: L'indice di ogni tab per nome, per non scrivere numeri sparsi nel codice.
TAB_PUBBLICAZIONI = 2
TAB_VIDEO = 1
TAB_AUDIO = 0
TAB_SCARICATI = 3
#: Quanti passi di testo si mostrano sotto la barra
MAX_RISULTATI_TESTO = 6

#: La larghezza e l'altezza di una cella, misurate sulla schermata dell'app
#: originale a 1368 pixel di larghezza logica: tre colonne da 417 con 4 di
#: vuoto fra l'una e l'altra.
CELLA_LARGA = 417
CELLA_ALTA = 100

#: Le card delle pubblicazioni hanno le **stesse** misure di quelle delle
#: categorie: stessa larghezza, stessa altezza, stesso quadrato a sinistra.
#:
#: Non e' una scelta di comodita'.  Una card 460 per 130 accanto a una 417 per
#: 100 fa tre cose sbagliate insieme: le due file non hanno la stessa altezza e
#: quindi le card non si allineano, la piu' larga finisce per occupare uno spazio
#: che l'altra non ha e le righe diventano irregolari, e — quello che conta di
#: piu' — l'utente vede due pezzi diversi dove doveva vederne uno.
#:
#: Le pubblicazioni erano prima elencate in `PubListView`, con righe alte 34
#: pixel: da li' sembravano "troppo piccole".  Il salto vero e' da 34 a 100, e
#: non c'e' bisogno di un secondo formato per arrivarci.
CELLA_PUB_LARGA = CELLA_LARGA
CELLA_PUB_ALTA = CELLA_ALTA
#: Il quadrato della copertina: e' alto come tutta la cella.  Le pubblicazioni
#: ce l'hanno come le categorie — e' quello che tiene la copertina a sinistra e
#: il titolo a destra, ed e' la forma che e' gia' a schermo.
QUADRO_PUB = CELLA_ALTA

#: Quante card si disegnano in una pagina del catalogo.
#:
#: Il numero e' un compromesso fra due difetti: con tutte, «La Torre di Guardia»
#: (2.787 pubblicazioni) costruirebbe 2.787 widget e congelerebbe la finestra;
#: con poche, non si arriverebbe ai titoli in fondo senza un modo per cercarli.
#: 300 e' abbastanza da sfogliare e da non far sentire il passaggio, e la
#: ricerca trova comunque tutti i 3.745 titoli.
MASSIMO_CARTE = 300

#: L'icona che disegna una pubblicazione **senza copertina**.
#:
#: UN SEGNAPOSTO PER TUTTI, E NON UNO PER TIPO
#: -------------------------------------------
#: Prima ogni tipo aveva la sua icona — il libro per i libri, il documento per
#: le brochure, il calendario per i programmi.  Erano dodici glifi diversi in
#: una griglia che mostra pezzi tutti uguali: copertine che mancano.
#:
#: In una griglia di pubblicazioni quei segnaposto non dicevano niente: la
#: riga dice gia' il titolo, e il tipo lo dice la categoria in cui l'utente sta
#: guardando.  Un segnaposto unico, disegnato a **tracci**, dice invece la cosa
#: vera — «qui c'e' qualcosa che va scaricato» — e non occupa il posto di
#: un'immagine che l'utente sta aspettando di vedere arrivare.
#:
#: E' `document`, che e' uno dei glofi del progetto, a tracci come gli altri.
ICONA_SEGNAPOSTO = "document"


def _icona_del_tipo(tipo: int) -> str:
    """Il segnaposto di una pubblicazione: **uno solo**, qualunque tipo sia.

    Resta una funzione perche' il chiamante non deve sapere che la risposta
    non dipende dal tipo: se un domani si volessero di nuovo le icone per tipo,
    si cambia qui e in un posto solo, e le due tabelle non possono andare
    avanti in direzioni opposte.

    Il parametro non e' usato ed e' dichiarato ugualmente: e' la firma che
    chiamano i due posti che costruiscono le celle, e toglierlo significherebbe
    cambiare anche loro per un motivo che non c'e'.
    """
    return ICONA_SEGNAPOSTO


def _riga_sotto(pub) -> str:
    """La riga piccola sotto il titolo.  Per il catalogo e' quasi sempre vuota.

    IL TITOLO GIUSTO E' `displayTitle`, E CE L'HA GIA' SCRITTO
    -------------------------------------------------------
    Sui periodici — Torre di Guardia, Svegliatevi!, guida per l'adunanza — il
    titolo del catalogo e' sempre lo stesso («La Torre di Guardia annunciante il
    Regno di Geova») e quello che distingue un numero dall'altro e' la data.  Il
    campo `issueTitle` porta gia' la riga intera, data compresa:

        La Torre di Guardia, 1° gennaio 2015

    e `Publication.displayTitle` sceglie gia' il campo giusto: `issueTitle` per
    i periodici, `title` per tutto il resto.  E' la stessa regola che usa la
    barra in alto, scritta una volta sola.

    Prima qui si ricostruiva la data a mano da `issueTagNumber`, che e' un
    numero come 20150101 e non un mese: la riga sotto il titolo diceva «gennaio
    50101 2015» — o niente, se il mese non era fra 1 e 12.  Un campo che sembra
    un mese ma e' una data intera e' il tipo di cosa che fa scrivere numeri
    sbagliati senza dare errore.

    Sotto il titolo della scheda, quindi, non ci mettiamo niente: il titolo e'
    gia' tutto quello che c'e' da dire.  La riga resta per quello che serve
    davvero, e cioe' la lingua di uno scaricato.
    """
    return ""


def _tracce_di(voce) -> tuple:
    """I numeri della traccia di una voce, come tupla di interi.

    SERVE PER DIRE SE DUE VOCI SONO LA STESSA COSA
    -----------------------------------------------
    Le voci arrivano da tre posti e con tre forme diverse: il mediator
    scrive `tracce` (un elenco, perche' un video di «Adorazione mattutina»
    ha due numeri), la Home scrive `traccia` (uno solo) e `MepsAPI` scrive
    `track`.  Confrontare le forme originali direbbe che due card della
    stessa traccia sono diverse, e la barra di scaricamento andrebbe su
    nessuna card.

    I numeri che non si capiscono si butta via invece di far fallire il
    confronto: una traccia senza numero e' comunque quella traccia.
    """
    valori = (voce.get("tracce") or voce.get("traccia")
              or voce.get("track") or 0)
    if not isinstance(valori, (list, tuple)):
        valori = [valori]
    numeri = []
    for valore in valori:
        try:
            numeri.append(int(valore))
        except (TypeError, ValueError):
            continue
    return tuple(numeri)


def _media_sul_disco(voce):
    """Il file di quella traccia che e' gia' sul disco, o ``None``.

    Una riga sola che chiama `MediaScaricati.file_di`, perche' il nome del file
    ha dentro la regola che si dimentica sempre: la traccia a **due cifre** e
    il prefisso `<sigla>_<lingua>_`.  Il `glob` senza quella doppia cifra non
    trova niente e il programma dice «non scaricato» con il file sul disco.

    Non si riscrive qui: la stessa domanda la fa gia' la Home per le sue card,
    e due ricerche con due formati diversi darebbero due risposte diverse sulla
    stessa domanda.

    LE TRACCE SONO TUTTE, NON UNA
    ----------------------------
    Si passa `tracce` (l'elenco) quando c'e', e `traccia` (il numero) solo
    per le voci che ne hanno una.  Il motivo e' il nome del file: un video di
    «Adorazione mattutina» si chiama `jwb_I_202104_02_r240P.mp4` e i suoi
    numeri sono **due** — il mese e il giorno.  Passando il primo dei due, il
    confronto non tornava e quei video si scaricavano e risultavano sempre
    non scaricati: il file c'era, la nuvoletta restava, e l'utente li
    riscaricava per sempre.
    """
    try:
        from Utility import MediaScaricati

        return MediaScaricati.file_di(voce.get("sigla", ""),
                                      voce.get("lingua", "I"),
                                      voce.get("tracce")
                                      or voce.get("traccia") or 0)
    except Exception:  # noqa: BLE001 - un file che non si trova e' assente
        return None


def _stato_media(voce) -> str:
    """Lo stato della nuvoletta di un media: scarica, aggiorna, o niente.

    Non e' una funzione nuova: chiama `_stato_nuvoletta` di `HomeView`, che
    guarda gia' il caso dei video e dell'audio — cerca il file sul disco con il
    prefisso `<sigla>_<lingua>_<traccia>_` e, se c'e', va a vedere se il server
    ne ha uno piu' nuovo.

    Il perche' del wrapper e' una riga sola: la domanda «questo media e' gia'
    sul disco?» ha gia' una risposta scrita e provata nella Home, con dentro
    anche la regola delle due cifre della traccia, che senza non trova niente.
    Riscriverla qui sarebbe una seconda copia che comincerebbe a divergere
    dalla prima volta che il nome di un file cambia.
    """
    try:
        from SubViews.HomeView import _stato_nuvoletta
        from Utility import Lingua

        return _stato_nuvoletta(voce,
                                voce.get("sigla", ""),
                                voce.get("lingua")
                                or Lingua.corrente_simbolo())
    except Exception:  # noqa: BLE001 - una nuvoletta che non si sa e' nessuna
        return "none"


def _copertina_subito_media(voce):
    """L'anteprima di un media, se e' **gia' sul disco**.  None altrimenti.

    Come `_copertina_subito`, che guarda una pubblicazione: qui si guarda un
    media, e quindi non c'e' il pacchetto da aprire.  Quello che c'e' e' la
    cache delle anteprime — il file che il programma ha gia' scritto quando ha
    visto quella locandina — e si legge e basta.

    Non chiede niente a nessuno: risponde subito, e il `None` vuol dire «la
    chiederemo dopo, in background» e non «non esiste».

    IL RITORNO ALLA CACHE: PERCHE' IL `mepsDocumentId` NON BASTAVA
    --------------------------------------------------------------
    Qui prima si cercava solo il `mepsDocumentId` e, non trovandolo, si
    finiva li'.  Ma il mediator non scrive nessun `mepsDocumentId`: scrive
    l'indirizzo della locandina in `trackImage.url`, che e' un fatto, e lo
    scrive per tutte le voci.

    Quindi per tutte le categorie di Video e Audio la domanda finiva sempre
    con «non c'e' nessuna chiave» e la card restava con il glifo: la seconda
    volta che si apriva la sezione la locandina era gia' scaricata, in cache,
    sul disco — e non la si mostrava lo stesso.

    Ora la domanda la fa `Copertine.locandina_del_media`, che e' la stessa
    che fanno il player grande e la striscia in fondo: cosi' la card, il
    riquadro e la striscia mostrano la stessa immagine.

    IL RITORNO E' UNA `QPixmap`, NON DEI BYTE
    -----------------------------------------
    `_Cella` scrive `anteprima.isNull()` e poi `setPixmap(anteprima)`, quindi
    vuole un'immagine gia' costruita, non i byte.  `_copertina_subito`, quello
    delle pubblicazioni, fa la stessa cosa e per questo finisce con
    `pixmap_quadrata`.  Restituire qui dei byte sarebbe stato un tipo diverso
    dalla stessa parte, e il primo `.isNull()` avrebbe sollevato un
    `AttributeError` dentro il costruttore della card — dentro un ciclo di
    costruzione, quindi con la griglia a meta'.

    Il quadrato e' quello della cella, e il ritaglio parte dal centro: una
    locandina 16:9 di un video, stirata in un quadrato, sembrerebbe una
    copertina rotta invece di una miniatura.
    """
    try:
        from Utility import Copertine
        from Utility.Copertine import pixmap_da_dati, pixmap_quadrata

        # Prima il pixmap che il thread ha gia' portato: e' gia' in memoria,
        # e rileggerlo da un file sarebbe solo sprecare tempo.
        gia = voce.get("_anteprima")
        if gia is not None:
            return gia
        dati = Copertine.locandina_del_media(voce, solo_cache=True,
                                             pub=getattr(voce, "_pub", None))
        if not dati:
            return None
        immagine = pixmap_da_dati(dati)
        if immagine is None or immagine.isNull():
            return None
        return pixmap_quadrata(immagine, QUADRO_PUB)
    except Exception:  # noqa: BLE001 - un'immagine mancante non ferma nulla
        return None


def _copertina_subito(pub):
    """La copertina di una pubblicazione, se e' **gia' sul disco**.  None altrimenti.

    Non chiede niente a nessuno: legge il pacchetto se c'e', e sennò il file in
    cache delle copertine.  Quindi risponde subito e sempre, e il `None` vuol
    dire «la chiederemo dopo, in background» e non «non esiste».

    Serve perche' nella griglia la differenza si vede: con questa, la seconda
    volta che si apre una categoria le copertine sono gia' li' mentre la
    finestra si disegna; senza, ogni card mostrava l'icona finche' il thread non
    tornava — e su una categoria grande l'utente le guardava tutte cosi'.
    """
    from Utility.Copertine import dati_gia_in_cache, pixmap_da_dati, pixmap_quadrata

    try:
        dati = dati_gia_in_cache(pub, "md")
    except Exception:  # noqa: BLE001 - una copertina illeggibile non e' un guasto
        return None
    if not dati:
        return None
    immagine = pixmap_da_dati(dati)
    if immagine is None:
        return None
    return pixmap_quadrata(immagine, QUADRO_PUB)


def _titolo_visuale(pub) -> str:
    """Il titolo da mettere sulla card: quello giusto, con la caduta.

    `displayTitle` e' la regola del progetto originale e la usa gia' la barra in
    alto: per un periodico restituisce il titolo dell'uscita, per tutto il resto
    il titolo della pubblicazione.  Non se ne scrive una seconda copia qui.

    Se il catalogo non ha nessuno dei due — una riga senza titolo — si mostra la
    sigla: e' corta e riconoscibile, e una card con «?» accanto non dice nulla.
    """
    titolo = ""
    try:
        titolo = (pub.displayTitle or "").strip()
    except Exception:  # noqa: BLE001 - un oggetto senza displayTitle non e' un guasto
        titolo = ""
    if not titolo:
        titolo = (getattr(pub, "title", "") or "").strip()
    return titolo or (getattr(pub, "keySymbol", "") or "?")

#: Le dodici categorie di pubblicazioni, con l'icona che le disegna.
#:
#: I nomi sono quelli della schermata originale.  Le icone sono Tabler, come
#: tutte le altre del programma: i disegni `pub_type_*` dell'app per Windows
#: sono quadretti con dentro un glifo che occupa il 44% della casella, e a
#: 44 pixel di lato dentro una cella da 100 si vedono come un puntino.
#:
#: Il formato e' `(chiave, nome, icona Tabler)`.  La chiave e' quella che
#: `PubView` capisce; l'icona e' il nome del file in `Files/icons`.
#: Le dodici categorie di pubblicazioni, con l'icona che le disegna.
#:
#: I NOMI VENGONO DALL'APP ORIGINALE, NON DA QUI
#: -----------------------------------------------
#: Queste dodici sono le stesse dell'app per Windows, lette dagli asset del
#: suo pacchetto: dodici file `pub_type_*` nella cartella `Assets/Icons`, uno
#: per categoria, ognuno nella versione chiara, scura, grigia e grigia scura.
#: Sono elencati in `BIBLIOTECA-DIGITALE-GRAFICA.txt`, capitolo 6, e sono la
#: fonte di questa tabella.
#:
#: NON SONO LE STESSE CHE C'ERAVANO PRIMA, E TRE NOMI ERANO SBAGLIATI
#: ------------------------------------------------------------------
#: «La Torre di Guardia» e «Svegliatevi!» sono **due** categorie e non una:
#: sono due periodici, settimanale e mensile, con una copertina diversa e un
#: ritmo di uscita diverso.  Nell'app originale hanno due icone — `awake` e
#: `watchtower` — e qui erano finiti nella stessa voce, dove si contavano
#: 2.787 pubblicazioni sotto un nome solo.
#:
#: «Il ministero del Regno» è una categoria per conto suo (552 pubblicazioni,
#: una per ogni anno dal 1934) e stava dentro «Trattati», che non c'entra
#: niente: un trattato e il ministero del Regno sono due opere diverse.
#:
#: «Indice» e «Linee guida» erano diventati «Manuali e indici» e «Materiali di
#: insegnamento»: due coppie che non hanno niente in comune fra loro.
#:
#: La Bibbia non e' in elenco, e non per dimenticanza: nell'app originale ha la
#: sua sezione, e i tre documenti di tipo 1 del catalogo sono la traduzione
#: dell'NMW, non una pubblicazione della Biblioteca.
CATEGORIE_PUB = (
    ("libri", "Libri", "book"),
    ("brochure", "Brochure e opuscoletti", "document-text"),
    ("trattati", "Trattati e inviti", "quote-circle"),
    ("articoli", "Articoli in serie", "document-stack"),
    ("torre", "La Torre di Guardia", "bookmark"),
    ("awake", "Svegliatevi!", "clock"),
    ("appunti", "Appunti per la riunione", "list"),
    ("ministero", "Il ministero del Regno", "persons"),
    ("programmi", "Programmi", "calendar"),
    ("indice", "Indice", "magnifying-glass"),
    ("linee_guida", "Linee guida", "checklist"),
    ("congresso", "Pubblicazioni al congresso", "tag"),
)


def _del_tipo(*numeri):
    """Un test: questa pubblicazione e' di uno di questi `publicationTypeId`?

    I numeri sono quelli del catalogo di jw.org, non dei pezzi di questa app.
    Sono stati letti uno per uno guardando i titoli che ci stanno sotto:

        2   Cosa insegna realmente la Bibbia?, Avviciniamoci a Geova
        4   Dio ci da' una buona notizia, La vostra famiglia puo' essere felice
        6   Guida alle ricerche, La buona notizia secondo Gesu'
        7   Il ministero del Regno  (uno per anno)
        10  Come consideri la Bibbia?  (le linee guida del Corpo Governingo)
        13  Svegliatevi!  (il mensile)
        14  La Torre di Guardia  (il settimanale)
        17  Istruzioni per l'adunanza
        22  La Bibbia ha cambiato la loro vita, Imitiamo la loro fede
        30  Guida alle attivita' per l'adunanza
        31  Programma del congresso, Programma dell'assemblea di circoscrizione

    PERCHE' UN TEST E NON UN INSIEME DI NUMERI
    ------------------------------------------
    Il chiamante ha bisogno di una domanda, non di un numero: «questa
    pubblicazione e' di questa categoria?».  Per undici categorie la domanda si
    puo' fare coi numeri, e per una no — «Pubblicazioni al congresso» si
    riconosce dalla sigla.  Se undici ritornassero un insieme e una una
    funzione, il chiamante dovrebbe chiedere quale delle due cose ha ricevuto,
    e sbagliare il `in` su una funzione non da un errore ma una lista vuota.

    Quindi tutte e dodici rispondono alla stessa domanda nello stesso modo, e il
    chiamante non sa — e non deve sapere — come sono fatte dentro.
    """
    insieme = frozenset(numeri)

    def filtra(pub) -> bool:
        return getattr(pub, "publicationTypeId", 0) in insieme

    filtra.__doc__ = f"Le pubblicazioni dei tipi {sorted(insieme)}."
    return filtra


def _dal_prefisso(*prefissi):
    """Un test: la sigla di questa pubblicazione comincia con uno di questi?

    Serve per «Pubblicazioni al congresso», che non e' un tipo: e' un insieme
    di pubblicazioni che escono al congresso — inviti, richieste, rapporti,
    messaggi — e si riconoscono dalla sigla, che comincia con `CO-`.  Nell'app
    originale hanno un asset tutto loro, `pub_type_convention_releases`, perche'
    sono un gruppo e non un tipo di pubblicazione.

    I numeri di tipo non bastano: i programmi del congresso sono di tipo 31 e
    andrebbero anche loro, ma sono programmi e nell'app originale stanno sotto
    «Programs».  La sigla e' cio' che distingue le due cose, ed e' l'unica cosa
    che le distingue.

    E' la prova che `_del_tipo` non puo' fare, ed e' per questo che le due
    fabbriche esistono: non due modi di scrivere la stessa cosa, ma due modi di
    riconoscere una pubblicazione.
    """
    def filtra(pub) -> bool:
        sigla = (getattr(pub, "keySymbol", "") or "").upper()
        return any(sigla.startswith(p) for p in prefissi)

    filtra.__doc__ = f"Le pubblicazioni con sigla che comincia con {prefissi}."
    return filtra


#: Per ogni categoria, il filtro che sceglie le sue pubblicazioni.
#:
#: Due modi di scegliere, e serve una tabella e non un numero perche' non
#: basta il tipo: «Pubblicazioni al congresso» si riconosce dalla sigla e le
#: altre dal tipo.  Scrivere `tipi=(...)` accanto a `sigla=(...)` per tutte e
#: dodici avrebbe fatto sembrare che manchi un pezzo dove invece e' una scelta
#: diversa.
FILTRO_CATEGORIA = {
    "libri": _del_tipo(2),
    "brochure": _del_tipo(4),
    "trattati": _del_tipo(22),
    # Nell'app originale la categoria c'e' e ha la sua icona.  Qui non ha
    # pubblicazioni: sono gli articoli collegati a una Bibbia, che vengono
    # presi dalle pagine di jw.org — `biblioteca-digitale/articoli/`, la stessa
    # famiglia di indirizzi che `Utility/Notizie.py` gia' legge — e non sono
    # righe del catalogo.  La si lascia con la sua lista vuota **e la sua
    # icona**, perche' una categoria che nell'app c'e' e qui no si vede subito
    # che manca qualcosa, mentre una che non c'e' fa credere che sia stata
    # sbagliata la scelta di tenerla.
    "articoli": _del_tipo(),
    "torre": _del_tipo(14),
    "awake": _del_tipo(13),
    "appunti": _del_tipo(17, 30),
    "ministero": _del_tipo(7),
    "programmi": _del_tipo(12, 31),
    "indice": _del_tipo(6),
    "linee_guida": _del_tipo(10),
    "congresso": _dal_prefisso("CO-"),
}

#: Le `publicationTypeId` del catalogo che stanno dentro ciascuna categoria.
#:
#: IL NUMERO VIENE DAL CATALOGO, NON DA UN PENSIERO
#: ---------------------------------------------------
#: La colonna `Publication` del `catalog.db` si chiama `PublicationTypeId`, e i
#: numeri sono quelli del catalogo di jw.org.  Le dodici voci qui dentro sono
#: state lette dal catalogo italiano, non scelte: ogni numero e' stato
#: controllato guardando i titoli che ci stanno sotto.
#:
#:     1   Traduzione del Nuovo Mondo delle Sacre Scritture
#:     2   Cosa insegna realmente la Bibbia? / Avviciniamoci a Geova
#:     4   Dio ci da' una buona notizia
#:     6   Guida alle ricerche
#:     7   Il ministero del Regno
#:     10  Come consideri la Bibbia?
#:     12  Programma dell'assemblea di circoscrizione o di zona
#:     13  Svegliatevi!
#:     14  La Torre di Guardia annunciante il Regno di Geova
#:     17  Istruzioni per l'adunanza
#:     22  La Bibbia ha cambiato la loro vita
#:     30  Guida alle attivita' per l'adunanza
#:     31  Programma del congresso
#:
#: Cinque di questi sono gia' scritti in `PubListView`, che li aveva gia'
#: guardati: Libri 2, Opuscoli 4, Torre di Guardia 14, Svegliatevi! 13,
#: Guida per l'adunanza 30.
#:
#: PERCHE' UN NUMERO PUO' ESSERNE PIU' DI UNO
#: ---------------------------------------------
#: Le dieci voci non sono dieci numeri, e non e' un errore: «La Torre di
#: Guardia» e' il periodico settimanale (14) **e** «Svegliatevi!» il mensile
#: (13), e nella schermata originale sono la stessa categoria.  Stessa cosa per
#: «Appunti per la riunione», che riprende sia le istruzioni (17) sia la
#: guida per l'adunanza (30), e per «Programmi», che comprende il congresso
#: (31) e l'assemblea di circoscrizione (12).
#:
#: DUE CATEGORIE SONO STATE TOLTE, E NON E' UNA SCELTA ESTETICA
#: ------------------------------------------------------------
#: Erano dodici: **«Articoli in serie»** e **«La Proclamazione»** non sono
#: piu' qui, e la ragione e' che questo catalogo non le contiene — non che
#: mancasse il numero da metterci.
#:
#: «Articoli in serie» sono gli articoli collegati a una Bibbia: vengono
#: presi dalle pagine di jw.org — `biblioteca-digitale/articoli/`, che e'
#: esattamente la famiglia di indirizzi che `Utility/Notizie.py` gia' legge —
#: e non sono pubblicazioni del catalogo.  Cercare un `publicationTypeId` che
#: non c'e' produrrebbe una lista vuota con un nome sopra: peggio che non
#: averla, perche' sembrerebbe che il catalogo sia vuoto.
#:
#: «La Proclamazione» nel catalogo non c'e' in nessuna lingua: cercando in tutte
#: le lingue e in tutti i titoli non compare una sola volta.  E' un deplianto,
#: non una pubblicazione, quindi non entra nella tabella `Publication`.
#:
#: Erano due celle che non potevano mai funzionare.  Una categoria che non puo'
#: funzionare e' rumore nella griglia: l'utente la preme, non succede niente,
#: e non sa se ha sbagliato lui o se e' rotto.
FILTRO_CATEGORIA = {
    # Le dodici categorie di pubblicazioni nell'app originale per Windows.
    # Nomi e tipi presi da BIBLIOTECA-DIGITALE-GRAFICA.txt (asset pub_type_*).
    # Vedi la tabella CATEGORIE_PUB sopra per la mappa completa.
    #
    # Due categorie non sono un tipo di pubblicazione: «Pubblicazioni al congresso»
    # si riconosce dalla sigla che comincia con 'CO-', e «Articoli in serie' non ha
    # pubblicazioni nel catalogo italiano (sono articoli biblici non nel catalogo).
    # Le altre dieci sono tutte un numero di publicationTypeId (o un'insieme).
    "libri": _del_tipo(2),
    "brochure": _del_tipo(4),
    "trattati": _del_tipo(22),
    "articoli": _del_tipo(),    # nessuna pubblicazione italiana — lasciato per onestà,
                                # ha l'icona e un elenco vuoto
    "torre": _del_tipo(14),
    "awake": _del_tipo(13),
    "appunti": _del_tipo(17, 30),
    "ministero": _del_tipo(7),
    "programmi": _del_tipo(12, 31),
    "indice": _del_tipo(6),
    "linee_guida": _del_tipo(10),
    "congresso": _dal_prefisso("CO-"),
}


# ---------------------------------------------------------------------------
# IL LAYOUT A FLUSSO
# ---------------------------------------------------------------------------
#
# PERCHE' NON UNA QGridLayout
# --------------------------
# La griglia ha tre colonne quando la finestra e' larga e meno quando non lo
# e'.  Una `QGridLayout` con il numero di colonne deciso all'avvio non si
# ricompone da sola quando la finestra si allarga e si stringe: mettere le
# celle in fila da sinistra a destra dentro un contenitore che cresce e si
# stringe e' esattamente quello che fa un layout a flusso.
#
# Il codice e' l'esempio `FlowLayout` che Qt mette nella documentazione, con
# due ritocchi: la larghezza si calcola sul **minimo** delle celle, e non sul
# massimo, perche' le celle sono tutte uguali e il minimo e' l'unico numero
# che le fa stare in fila senza che una tiri la riga.

class _Flusso(QLayout):
    """Le celle in fila, andando a capo quando la larghezza finisce."""

    def __init__(self, padre=None, margine: int = 0, spazio: int = 4) -> None:
        super().__init__(padre)
        self._voci: list = []
        self.setContentsMargins(margine, margine, margine, margine)
        self.setSpacing(spazio)

    def addItem(self, voce) -> None:  # noqa: N802 - nome di Qt
        """Una cella in piu', e il layout **non e' piu' valido**.

        IL PERCHE' DI `invalidate`, CHE Sembra UN DETTAGLIO
        --------------------------------------------------
        Un layout personalizzato deve dire a Qt «ho cambiato, rifammi la
        geometria» ogni volta che un elemento entra.  Senza, Qt tiene la
        posizione che aveva calcolato e non ricalcola niente.

        Il sintomo era questo: si aggiungevano le tre card delle categorie
        Audio — «Melodie del Regno», «Brani biblici recitati», «Videoracconti»
        — e **la terza finiva a (0, 0)**, cioe' esattamente sopra la prima.
        Le due davanti si vedevano, la terza no, e la sezione diceva «3
        categorie»: un numero che non tornava con quello che si vedeva, e
        nessun errore.

        Il conto torna solo se si guarda: `count()` diceva 3, e tre card erano
        nella griglia.  Ma la terza era **sotto** la prima.  Ed e' per questo
        che «alcune categorie non vanno»: non andavano, erano coperte.

        Non e' un trucco: e' quello che `QLayout` documenta come obbligo di un
        layout fatto a mano, e qui mancava.
        """
        self._voci.append(voce)
        self.invalidate()

    def takeAt(self, indice):  # noqa: N802, A003 - nomi di Qt
        if 0 <= indice < len(self._voci):
            voce = self._voci.pop(indice)
            self.invalidate()
            return voce
        return None

    def count(self) -> int:  # noqa: A003 - nome di Qt
        return len(self._voci)

    def itemAt(self, indice):  # noqa: N802, A003 - nomi di Qt
        if 0 <= indice < len(self._voci):
            return self._voci[indice]
        return None


    def expandingDirections(self):  # noqa: N802 - nome di Qt
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - nome di Qt
        return True

    def heightForWidth(self, larghezza: int) -> int:  # noqa: N802 - nome di Qt
        """Quanto alta deve essere la pagina a questa larghezza."""
        utile = larghezza - self.contentsMargins().left() \
            - self.contentsMargins().right()
        x = 0
        y = self.contentsMargins().top()
        riga = 0
        for voce in self._voci:
            suggerita = voce.sizeHint()
            # IL CONFRONTO E' `x + larghezza > utile`, E NON COL BORDO DESTRO
            # -------------------------------------------------------------
            # Il conto e' fatto a coordinate **relative al contenitore**, non
            # con `QRect.right()`.  `right()` e' l'ultima colonna inclusa, e
            # una cella che finisce esattamente al bordo ci sta: confronto
            # `x + 417` con `right()` e la terza cella di una riga da 1259 non
            # ci stava, perche' finiva a 1259 e il bordo era 1258.
            #
            # Il numero che ne viene e' quello che conta: con 417 per cella e
            # 4 di vuoto, tre celle occupano 1251 e quindi in una riga da
            # 1259 ce ne stanno tre.  Misurato: se ne vedevano due.
            if x + suggerita.width() > utile and riga > 0:
                x = 0
                y = y + riga + self.spacing()
                riga = 0
            x = x + suggerita.width() + self.spacing()
            riga = max(riga, suggerita.height())
        return y + riga + self.contentsMargins().bottom()

    def setGeometry(self, rettangolo) -> None:  # noqa: N802 - nome di Qt
        """Mette le celle dove stanno, andando a capo a ogni riga piena."""
        super().setGeometry(rettangolo)
        sinistra = rettangolo.x() + self.contentsMargins().left()
        utile = rettangolo.width() - self.contentsMargins().left() \
            - self.contentsMargins().right()
        x = 0
        y = rettangolo.y() + self.contentsMargins().top()
        riga = 0
        for voce in self._voci:
            suggerita = voce.sizeHint()
            # Vedi la nota in `heightForWidth`: il confronto e' fra la
            # posizione relativa e la larghezza utile, non col bordo destro.
            if x + suggerita.width() > utile and riga > 0:
                x = 0
                y = y + riga + self.spacing()
                riga = 0
            voce.setGeometry(
                QRect(sinistra + x, y, suggerita.width(), suggerita.height())
            )
            x = x + suggerita.width() + self.spacing()
            riga = max(riga, suggerita.height())

    def sizeHint(self) -> QSize:  # noqa: N802 - nome di Qt
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - nome di Qt
        """La larghezza minima e' una cella, l'altezza e' quella di quante ce ne sono."""
        dimensione = QSize()
        larghezza_cella = 0
        altezza_cella = 0
        for voce in self._voci:
            suggerita = voce.sizeHint()
            larghezza_cella = max(larghezza_cella, suggerita.width())
            altezza_cella = max(altezza_cella, suggerita.height())
        dimensione.setWidth(larghezza_cella)
        dimensione.setHeight(self.heightForWidth(larghezza_cella))
        return dimensione


class _Griglia(QWidget):
    """L'area che contiene le celle e le tiene in tre colonne."""

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        from Utility import tema as _tema
        _tema.sfondo(self, "paginaGriglia")
        self._flusso = _Flusso(self, margine=0, spazio=4)
        #: Le card usate da una lista e rimaste in attesa di un'altra lista.
        self._in_attesa: list = []

    def aggiungi(self, cella) -> None:
        """Mette una cella nella griglia."""
        self._flusso.addWidget(cella)

    def cella_per(self, cosa: dict, modo: str, collegare) -> object:
        """Una card che mostra `cosa`, riusandone una se si puo'.

        IL RIUSO, E LA SUA REGOLA
        ------------------------
        Costruire 300 card costa circa 150 millisecondi, e si rifa a ogni cambio
        di tab e a ogni lettera della ricerca.  Il tempo non e' nella lettura dei
        dati: e' Qt che crea trecento widget con layout, sotto-widget e foglio di
        stile, e poi li distrugge per rifare gli stessi trecento.

        Una card riusata ha gia' tutto questo dentro, quindi cambiano solo quattro
        cose: il quadrato, il titolo, la riga sotto e il tasto dello scaricare —
        quattro scritture, contro trecento widget.

        LA REGOLA E' UNA SOLA: LA FORMA
        --------------------------------
        Il riuso si accetta solo quando la card ha la **stessa forma** di prima,
        e la forma la decide `modo` piu' il fatto che i due tasti ci siano o no.
        `modo` cambia perche' `video` disegna la foto a tutto riempimento e gli
        altri un quadrato con l'icona, e sono due costruzioni diverse.

        Quando la forma non combacia si costruisce una card nuova e le due cose
        non si sforzano di essere la stessa.  Una card che cambia forma e' una
        card che mostra il pezzo sbagliato, e quello non e' un difetto di velocita'.

        LE SEGNALI SI COLLEGANO UNA VOLTA SOLA
        ---------------------------------------
        `collegare` viene chiamata solo per le card **nuove**.  Collegarle anche
        per le riusate significa che una card usata quattro volte ha il click
        collegato quattro volte, e ogni click scarica quattro volte quello che
        si e' premuto — senza dare nessun errore, e senza che il pulsante sembri
        rotto: sembra solo lento.
        """
        for cella in self._in_attesa:
            if cella.aggiorna(cosa, modo):
                self._in_attesa.remove(cella)
                cella._in_uso = True
                cella.show()
                self.aggiungi(cella)
                return cella
        cella = _Cella(cosa, modo=modo, padre=self)
        cella._in_uso = True
        collegare(cella)
        self.aggiungi(cella)
        return cella

    def svuota(self) -> None:
        """Butta via tutte le celle.

        Non si rimuovono a mano una per una perche' `QLayout.takeAt` va
        chiamato finche' restituisce qualcosa:Fermarsi al primo ``None``
        lascia indietro mett' dei pezzi, che il giorno dopo sono icone
        duplicate nella stessa sezione.

        SI TOGLIE DALL'ULTIMA, NON DALLA PRIMA
        ----------------------------------------
        `takeAt(0)` e' quello che sembra giusto — si svuota dalla cima — ma
        `_Flusso.takeAt` fa `self._voci.pop(indice)` su una **lista di Python**, e
        togliere il primo elemento sposta tutti gli altri di uno.  Su una griglia
        da 300 card il ciclo fa 300 + 299 + 298 + ... rimovimenti: 45.150 passi
        per svuotare una griglia.

        Misurato prima e dopo, sul solo smontaggio delle 300 card: 74 ms con
        `takeAt(0)` contro 1 ms togliendo dall'ultima.  Non cambia l'ordine in cui
        le widget vengono distrutte — `deleteLater` lavora a fine giro di eventi, e
        in un giro vengono distrutte tutte, quindi l'ordine non si vede.

        Si continua a chiamare finche' `count()` dice che c'e' roba: fermarsi al
        primo ``None`` lascerebbe indietro mett' dei pezzi, che il giorno dopo
        sono icone duplicate nella stessa sezione.
        """
        while self._flusso.count():
            voce = self._flusso.takeAt(self._flusso.count() - 1)
            widget = voce.widget() if voce is not None else None
            if isinstance(widget, _Cella):
                # La card non muore: esce dal layout e aspetta la prossima
                # lista.  `hide()` perche' una card tolta dal layout ma ancora
                # figlia di questa griglia continua a disegnarsi nella posizione
                # in cui era, sopra le card nuove.
                widget._in_uso = False
                widget.hide()
                self._in_attesa.append(widget)
                continue
            if widget is not None:
                # `setParent(None)` PRIMA di `deleteLater`, E NON E' OPZIONALE
                # -------------------------------------------------------------
                # Costo: 71 ms per 300 card, quasi meta' dello smontaggio, e si
                # e' provato a toglierlo perche' il conto e' alto.
                #
                # Tolto, la ricostruzione scende a 98 ms — e la griglia resta con
                # **861 widget** invece di 300.  Il motivo e' che `takeAt` toglie
                # il widget dal layout ma non lo stacca dalla finestra: resta figlio
                # della griglia, e `deleteLater` rimanda la distruzione a fine giro
                # di eventi, quindi per un po' ci sono card vecchie e card nuove
                # insieme nello stesso contenitore.
                #
                # Due problemi, e il secondo e' quello serio.  Il primo e' che si
                # vedono disegnate: hanno ancora la geometria di prima e il layout
                # non le piu' muove.  Il secondo e' che `findChildren(_Cella)` le
                # trova: `card_di()` cerca la card di una pubblicazione e puo'
                # prendere una che sta per morire, e a quella ci attacca la barra
                # del download, che sparisce a meta' scaricamento.
                #
                # `setParent(None)` le stacca subito dalla finestra, e un widget
                # senza padre in Qt e' una finestra nascosta: non si vede piu' e non
                # e' piu' tra i figli.  Costa 71 ms e li toglie entrambi i problemi
                # alla radice, quindi resta.
                widget.setParent(None)
                widget.deleteLater()


# ---------------------------------------------------------------------------
# LA CELLA
# ---------------------------------------------------------------------------
#
# Tre forme della stessa cella, e sono tre modi di guardare la stessa cosa:
# la domanda «di cosa guardo i media» ha tre risposte diverse a seconda che
# si scelga una pubblicazione, un audio o un video.
#
#     "pub"     icona 100x100 a sinistra, titolo accanto
#     "audio"   miniatura quadrata 100x100 a filo, titolo accanto
#     "video"   foto a tutto riempimento e titolo bianco sopra una sfumata
#
# LA MISCELA TRA PUBLICAZIONI, AUDIO E VIDEO E' DELLA FINESTRA, NON DELLA CELLA
# ---------------------------------------------------------------------------
# La sfumata nera e' un **figlio** della cella, non il suo sfondo.  Il fondo
# della cella e' la foto; la sfumata e' un rettangolo sopra, e il titolo e'
# sopra la sfumata.  Con la sfumata come sfondo della cella la foto non si
# vedrebbe piu'.
#
# E la sfumata e' un `QLabel` e non un'immagine generata: in Qt il
# gradiente si scrive in una riga di foglio di stile (`#sfumaturaVideo`) e
# cosi' segue il tema da solo.

class _Cella(QWidget):
    """Una cella della griglia.  Si preme e restituisce quello che contiene."""

    scelto = Signal(object)
    #: L'utente ha premuto «...»: chiede il menu' della riga.  Il segnale porta
    #: il dizionario della cella e la posizione del clic, che il menu' usa per
    #: aprirsi sotto il bottone premuto e non nel mezzo della finestra.
    menuChiesto = Signal(object, object)
    #: L'utente ha premuto la nuvoletta o il refresh: scarica o aggiorna.
    scaricaChiesta = Signal(object)

    def __init__(self, cosa: dict, modo: str = "pub", padre=None) -> None:
        super().__init__(padre)
        from Utility import tema as _tema
        _tema.sfondo(self, "cella")
        self.cosa = cosa
        self.modo = modo
        #: Vero quando la card e' in una lista, falso quando e' in attesa nel
        #: pool di `_Griglia`.  Chi legge le card con `findChildren` deve
        #: controllare questo, perche' nel pool ci sono card vere: hanno solo
        #: smesso di mostrare qualcosa.
        self._in_uso = True
        # La card di una pubblicazione e' **identica** a quella di una
        # categoria: stessa misura, stesso quadrato a sinistra, stesso titolo a
        # destra.  Cambia solo che dentro il quadrato c'e' la copertina e ci
        # sono i due bottoni — le categorie hanno l'icona e niente bottoni,
        # perche' una categoria non si scarica e non ha un menu' suo.
        #
        # Il nome del segnale e' `pub` perche' e' la stessa cosa che c'era: una
        # pubblicazione.  Se e' una riga del catalogo o uno scaricato cambia
        # solo dove il file e' (il server o il disco), non il disegno.
        # I COMANDI CI SONO ANCHE PER I MEDIA
        # -----------------------------------
        # Prima i due tasti c'erano solo sulle pubblicazioni: una nuvoletta su
        # un video e' la stessa nuvoletta su un libro, e non averla significa
        # che l'unico modo di scaricare un video e' andare a cercarlo nella
        # sezione giusta.
        #
        # La nuvoletta di un media pero' non puo' chiedere il pacchetto: e'
        # un file, non una cartella.  Quindi il tasto c'e' ma porta la voce, e
        # chi ascolta decide — come fanno gia' i video nella Home.
        self.ha_comandi = self._comandi_per(cosa, modo)
        self.lato_icona = CELLA_ALTA
        self.setFixedSize(CELLA_LARGA, CELLA_ALTA)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if modo == "video":
            self._costruisci_video(cosa)
        else:
            self._costruisci_normale(cosa, modo)

    # ------------------------------------------------------------------
    # LA FORMA CON ICONA O MINLATURA A FILO
    # ------------------------------------------------------------------
    def _costruisci_normale(self, cosa: dict, modo: str) -> None:
        """Icona (pubblicazioni) o miniatura (audio), con il titolo accanto.

        I DUE MODI NON SONO LO STESSO DISEGNO
        -------------------------------------
        La miniatura dell'audio e' **a filo**: tocca il bordo sinistro della
        cella, come nella schermata originale, e con un margine sembrerebbe una
        foto appoggiata sopra un riquadro, che e' una cosa diversa.

        L'icona della pubblicazione invece ha **30 pixel** di vuoto a sinistra,
        misurati: nella schermata originale comincia a x=102 dentro una cella
        che parte da x=72.  La differenza si vede subito e non e' una
        distrazione: sono due cose disegnate in due modi.

        IL TITOLO E' CENTRATO, E COME
        -----------------------------
        Con uno `stretch` **prima** e uno dopo: il solo `stretch` finale
        spingeva il titolo in alto, e una cella alta 100 con il titolo a 15
        pixel dal bordo superiore sembra una riga che e' sfuggita in su invece
        di una cella con la sua etichetta.
        """
        riga = QHBoxLayout(self)
        # 30 pixel a sinistra come le pubblicazioni: i media ora sono la stessa
        # card, quindi devono avere lo stesso vuoto davanti al quadrato.
        #
        # E 28 a destra, **solo se ci sono i due tasti**.  I tasti stanno
        # agli angoli della card — il «...» a x=389 e lo scaricare poco sotto —
        # e il widget del testo arrivava fino a x=417: il titolo passava
        # **sotto** i tasti e finiva sotto il bottone.  Non si vedeva subito
        # perche' il bottone e' piccolo e rotondo, ma il titolo finiva a met'a
        # e sembrava troncato: «Famiglie, prendete l'abitudine di leggere la
        # Bibbia ogni giorno!» era illeggibile sull'ultima parola, e la parola
        # sotto il bottone era quella che si perdeva.
        #
        # 28 e' la misura che serve: il bottone e' di 20 e il vuoto dal bordo
        # e' 8.  Ed e' la stessa cifra che il menu' usa per il punto sotto al
        # bottone (`_menu` passa `CELLA_LARGA - 28`): il vuoto e la posizione
        # vengono dalla stessa parte.
        riga.setContentsMargins(30 if modo in ("pub", "media") else 0, 0,
                                28 if self.ha_comandi else 0, 0)
        riga.setSpacing(28)

        # Il quadrato 100x100: e' alto come tutta la cella, e quindi non ha
        # bisogno di essere centrato in verticale, sta li' per costruzione.
        lato = self.lato_icona
        quadro = QLabel(self)
        # Il quadrato si tiene per nome: quando arriva la copertina dal thread
        # va rimessa **in questo** widget.  Prima qui si cercava con
        # `findChildren` e un controllo sulla larghezza del pixmap
        # (`width() == 44`), che funziona finche' l'icona e' 44 pixel e
        # smette quando cambia la misura del glifo — e in quel caso la
        # copertina finisce dentro l'etichetta del titolo, che si vede come
        # un'immagine fuori posto e non come «la copertina non è arrivata».
        self._quadro = quadro
        quadro.setFixedSize(lato, lato)
        self._metti_il_quadro(cosa)
        riga.addWidget(quadro, 0)

        # I DUE BOTTONI DENTRO LA COPERTINA, E LA BARRA
        # ------------------------------------------------
        # Presi dalla Home, che e' il posto dove l'utente ha gia' visto che
        # cosa significano: nuvoletta = scarica, refresh = aggiorna, «...» =
        # altre azioni.  Stessi simboli, stesso significato, stesse posizioni:
        # sono gli stessi due angoli della Home — in alto a destra il menu', in
        # basso a destra lo scaricare — calcolati sulla misura di questo
        # quadrato, quindi si adattano da soli.
        #
        # Le categorie non li hanno: non si scaricano e non hanno un menu'.
        testo = QWidget(self)
        colonna = QVBoxLayout(testo)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(2)
        self._costruisci_il_testo(testo, colonna, cosa)
        riga.addWidget(testo, 1)

        # I COMANDI VENGONO **DOPO** IL TESTO, E NON PRIMA
        # -----------------------------------------------
        # Qui prima c'era `self._aggiungi_comandi(...)` tre righe prima di
        # costruire il widget del testo, e i due bottoni finivano **coperti**.
        #
        # I bottoni non stanno nel layout: sono figli della card messi a mano
        # con `setGeometry`, e il widget del testo e' invece un figlio del
        # layout.  Un figlio del layout viene messo in alto rispetto a un
        # figlio a mano, perche' il layout ridispone i suoi quando viene
        # ridisegnato — e cioe' **dopo**.
        #
        # Il risultato: il widget del testo copriva da x=158 a x=417, e i due
        # bottoni stanno a x=389.  Erano visibili (il `raise_` li tirava su),
        # ma il click non arrivava a loro: passava al widget sotto, che non
        # faceva niente.  Il pulsante sembrava morto e il menu' non si apriva
        # mai.
        #
        # Un tasto che si vede e non premete e' la cosa peggiore: non dice
        # niente, e l'utente prova tre volte e poi smette.
        if self.ha_comandi:
            self._aggiungi_comandi(quadro, lato, cosa)

    # ------------------------------------------------------------------
    # I PEZZI CHE CAMBIANO: UN METODO UNO, CHIAMATO DUE VOLTE
    # ------------------------------------------------------------------
    #
    # Qui sotto ci sono quattro metodi, e ognuno e' chiamato da **due** posti:
    # dal costruttore, quando la card e' nuova, e da `aggiorna`, quando la card
    # viene riusata.
    #
    # Il motivo e' il difetto piu' facile da mettere in questo tipo di codice.
    # Il quadrato e' stato per prima dentro il costruttore, poi si e' aggiunto il
    # riuso, e il riuso ha ricominciato a scrivere «icona, allineamento, pixmap»
    # per conto suo.  Due posti che scrivono la stessa cosa divergono alla prima
    # modifica — e il sintomo e' una card che mostra la copertina del pezzo
    # **precedente**, che e' la cosa peggiore che possa fare una lista: non
    # sembra rotta, sembra un'altra.
    #
    # Quindi la regola e' una sola: quando un pezzo cambia, sta in un metodo, e il
    # metodo si chiama.  Non «un pezzo qui e uno li'».

    @staticmethod
    def _comandi_per(cosa: dict, modo: str) -> bool:
        """Questa cella ha i due tasti, o no?

        Un posto solo, perche' la domanda la fanno due: quando la card nasce e
        quando viene riusata.  Se le due rispondessero in modo diverso, una card
        riusata avrebbe i tasti di una categoria e viceversa — e il difetto non
        si vede, perche' un tasto che c'e' dove non dovrebbe e' cliccabile e fa
        qualcosa di plausibile: scarica la categoria.

        Un tasto che appare e sparisce a ogni cambio di tab e' il peggiore dei
        due errori, perche' nessuno dei due si nota da solo.
        """
        return ((modo == "pub" and (cosa.get("pub") is not None
                                    or cosa.get("traduzione") is not None))
                or modo == "media")

    def _metti_il_quadro(self, cosa: dict) -> None:

        """Il quadrato a sinistra: la copertina se c'e', altrimenti il glifo.

        Tre casi, e sono tre modi di guardare la stessa cosa:

            la copertina   quando c'e' gia' sul disco o in cache
            il glifo       quando e' una categoria di pubblicazioni
            il simbolo     quando e' un media senza anteprima

        La copertina **non** viene stirata a 100 per 100: si mette ridimensionata
        in mezzo, altrimenti una copertina 300 per 450 diventerebbe un rettangolo
        schiacciato che non si riconosce, e il titolo accanto direbbe una cosa
        diversa dall'immagine.
        """
        quadro = self._quadro
        anteprima = cosa.get("_anteprima")
        if anteprima is not None and not anteprima.isNull():
            quadro.setObjectName("miniatura")
            quadro.setAlignment(Qt.AlignmentFlag.AlignCenter)
            quadro.setPixmap(anteprima)
        elif self.modo == "pub":
            # `icona_tabler` e non `icon`: qui i nomi sono i nomi dei FILE
            # (`book.svg`), non i nomi dei simboli di macOS.  Vedi la nota di
            # `icona_tabler` in `Stuff.py`: le icone delle categorie non hanno
            # un simbolo corrispondente e non si deve scriverne uno falso nella
            # tabella solo per far passare la chiamata.
            #
            # Il glifo e' di 44 come quello delle categorie, perche' la cella e'
            # quella delle categorie: un glifo piu' grande dentro un quadrato
            # piccolo sembrerebbe un'icona stirata male, non una copertina.
            quadro.setPixmap(icona_tabler(cosa.get("icona", "book"),
                                          _colore("icona"), 44).pixmap(44, 44))
        else:
            quadro.setObjectName("miniatura")
            quadro.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # IL GLIFO LO SA LA VOCE, E NON LA CARD
            # ----------------------------------------
            # Qui c'era `nome = "headphones" if self.modo == "audio" else
            # "film"`.  Ma `modo` vale `"media"` per **tutti** i media, audio e
            # video insieme: e' una sola forma di card, cosi' il riuso fra
            # l'una e l'altro funziona.  Quindi la condizione non era mai vera
            # e il glifo era **sempre** quello del film.
            #
            # Il sintomo: le card dei 13 «Videoracconti» — che sono audio, e lo
            # dice anche la scheda in cui sono — avevano l'icona del film.  Una
            # icona che contraddice quello che c'e' scritto accanto e' peggio
            # di nessuna icona, perche' fa leggere il brano come un video.
            #
            # Il glifo giusto e' gia' calcolato e messo dentro `cosa`: e'
            # `_glifo_per`, che guarda la voce.  Quindi si usa quello, e la
            # regola sul `modo` resta solo per una card che non abbia ancora un
            # glifo — cioe' nessuna, ma non si scrive una regola che vale per un
            # caso che non esiste.
            nome = (cosa.get("icona")
                    or ("headphones" if self.modo == "audio" else "film"))
            quadro.setPixmap(icon(nome, _colore("grigio", "#8e8e8e"),
                                  32).pixmap(32, 32))

    def aggiorna(self, cosa: dict, modo: str) -> bool:
        """Questa card mostra un altro pezzo.  True se ha potuto, False se va rifatta.

        QUANDO PUO' E QUANDO NO
        ------------------------
        Il riuso e' possibile solo quando la **forma** della card non cambia:

            stessa `modo`      perche' `pub`, `media`, `audio` e `video` costruiscono
                               cose diverse — `video` mette la foto a tutto
                               riempimento, gli altri un quadrato con l'icona
            stessi comandi     perche' i due tasti ci sono o non ci sono, e una
                               card che li ha e una che non li ha non hanno la
                               stessa identita'

        Quando la forma e' diversa si risponde `False` e chi chiama costruisce una
        card nuova.  La regola e' che **non si deve sforzare**: una card che
        cambia forma e' una card che si spacca, e il sintomo e' una lista che
        mostra pezzi sbagliati — mentre il riso non era un difetto ma un lusso.

        PERCHE' LA BARRA VA RIMETTA A ZERO
        ---------------------------------
        La barra del download appartiene alla card, e una card riusata viene da
        una lista dove poteva essere scaricamento in corso.  Senza rimetterla a
        zero, il pezzo nuovo mostrerebbe la percentuale del pezzo vecchio: una
        riga che mente su quello che sta scaricando, che e' l'unica cosa che la
        barra ha da dire.
        """
        if modo != self.modo:
            return False
        if self._comandi_per(cosa, modo) != self.ha_comandi:
            return False

        self.cosa = cosa
        self._metti_il_quadro(cosa)
        self._metti_il_testo(cosa)
        if self.ha_comandi:
            self._metti_la_nuvoletta(cosa)
            # Il download che stava andando era di **questo** pezzo prima, e
            # `SidebarView` lo segue chiamando `_scarica_finita` sulla card che
            # trova con `card_di`.  Quel pezzo non c'e' piu': la barra torna al
            # suo riposo e il nuovo comincia da capo.
            self._barra.setRange(0, 0)
            self._barra.setValue(0)
            self._barra.hide()
        # I due tasti vanno tirati su **solo se ci sono**.  Una card di categoria
        # non li ha: `raise_()` su un attributo che non e' mai stato creato
        # solleva `AttributeError` e porta via il programma.
        #
        # Il caso e' reale e non ipotetico: `ha_comandi` e' `False` per le
        # categorie, e una card riusata da una pubblicazione a una categoria si
        # trova con `ha_comandi` `False` e i due tasti **non** creati, perche'
        # vengono creati solo quando ci sono.  Il controllo su `ha_comandi` qui
        # sotto non e' una difesa: e' la condizione che rende vera la frase
        # «una card senza tasti non chiama i tasti».
        if self.ha_comandi:
            self._tre_punti.raise_()
            self._scarica.raise_()
        return True

    def _costruisci_il_testo(self, testo, colonna, cosa: dict) -> None:
        """La colonna del titolo, e la riga sotto.

        LA RIGA SOTTO NASCE SEMPRE, E SI MOSTRA SOLO SE C'E' QUALCOSA
        -----------------------------------------------------------
        Prima nasceva solo quando `cosa["sotto"]` aveva qualcosa.  Va bene per una
        card che esiste una volta sola, ma non per una che viene riusata: una
        card che aveva il sottotitolo e la successiva non ce l'ha resterebbe con
        la riga e il titolo schiacciati in mezzo, e non si capirebbe se e' un
        difetto o un vuoto.

        Quindi nasce sempre e si mostra solo quando serve.  Il vuoto che sembra
        sciupare spazio e' lo stesso di prima: quando non c'e' sottotitolo la
        riga non e' alta e non sposta niente.
        """
        self._nome = QLabel(cosa.get("titolo") or "?", testo)
        self._nome.setObjectName("titoloCella")
        self._nome.setWordWrap(True)
        colonna.addStretch(1)
        colonna.addWidget(self._nome)
        # Il sottotitolo c'e' solo se c'e' qualcosa da dire (la lingua di una
        # pubblicazione scaricata).  Una riga vuota dentro una cella alta 100
        # sposta il titolo di mezzo centimetro e basta spazio buttato.
        self._dettaglio = QLabel(cosa.get("sotto") or "", testo)
        self._dettaglio.setObjectName("sottoCella")
        self._dettaglio.setVisible(bool(cosa.get("sotto")))
        colonna.addWidget(self._dettaglio)
        colonna.addStretch(1)

    def _metti_il_testo(self, cosa: dict) -> None:
        """Titolo e sottotitolo nuovi.  Stessa coppia di `_costruisci_il_testo`."""
        self._nome.setText(cosa.get("titolo") or "?")
        sotto = cosa.get("sotto")
        self._dettaglio.setText(sotto or "")
        self._dettaglio.setVisible(bool(sotto))

    def _stato_del_pulsante(self, cosa: dict) -> str:
        """«download», «update» o «none»: che vuol dire il tasto per **questo** pezzo."""
        if cosa.get("pub") is not None:
            from SubViews.HomeView import _stato_nuvoletta
            pub = cosa["pub"]
            sigla = getattr(pub, "keySymbol", "") or ""
            # `_stato_nuvoletta` vuole il **simbolo** della lingua («I», non 4),
            # perche' confronta con i nomi delle cartelle sul disco, che sono
            # `<sigla>_<lingua>_<anno>`.  Passando il numero la cartella non
            # corrisponderebbe e ogni pubblicazione sembrerebbe da scaricare.
            lingua = Lingua.da_numero(getattr(pub, "mepsLanguageId", 0) or 0)
            from Utility.JWPubManager import pub_dir_name
            return _stato_nuvoletta({"cartella": pub_dir_name(pub)}, sigla, lingua)
        return _stato_media(cosa["voce"]) if (voce := cosa.get("voce")) else "none"

    def _metti_la_nuvoletta(self, cosa: dict) -> None:
        """Il tasto dello scaricare come merita **questo** pezzo, adesso.

        Tre stati, e il terzo e' quello in cui il tasto sparisce: non c'e' niente
        da scaricare perche' il file e' gia' sul disco.
        """
        stato = self._stato_del_pulsante(cosa)
        if stato == "download":
            self._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
            self._scarica.setToolTip("Scarica")
            self._scarica.show()
        elif stato == "update":
            self._scarica.setIcon(icon("arrow.clockwise", "#ffffff", 16))
            self._scarica.setToolTip("Aggiorna: c'e' una versione nuova")
            self._scarica.show()
        else:
            self._scarica.hide()

    # ------------------------------------------------------------------
    # I COMANDI DELLA CARD: «...», SCARICA O AGGIORNA, E LA BARRA
    # ------------------------------------------------------------------
    def _aggiungi_comandi(self, quadro, lato: int, cosa: dict) -> None:
        """I due tasti e la barra, **sulla card** e non sulla copertina.

        PERCHE' SONO SULLA CARD E NON DENTRO IL QUADRATO DELLA COPERTINA
        ---------------------------------------------------------------
        Nella Home la copertina e' quasi tutta la card: `LATO_ANTEPRIMA` e' 124
        dentro una card larga 140.  Quindi i due angoli della copertina sono
        anche, di fatto, gli angoli della card, e metterli li' funziona.

        Qui non e' cosi': il quadrato della copertina e' alto 100 dentro una
        card larga **417**, e il resto e' il titolo.  I tasti dentro il quadrato
        restavano a mezz'aria accanto all'icona, senza niente sopra e sotto:
        sembravano appesi nel vuoto e non appartenevano a nessuna card.  Per
        questo stanno sugli angoli della **card** — in alto a destra il «...»,
        in basso a destra lo scaricare — che e' l'unico posto dove due comandi
        hanno sopra e sotto qualcosa.

        LE STESSE SIMBOLI E LA STESSA REGOLA DELLA HOME
        -------------------------------------------------
        I glifi e' la nuvoletta che diventa refresh quando c'e' una versione
        nuova, e lo stato lo dice `_stato_nuvoletta`, che viene **chiamata** e
        non ricoppiata.  Copiarla sarebbe la cosa che si rompe senza errore:
        il giorno che la Home distingue i due casi con un colore diverso, qui
        resterebbe il vecchio e due tasti con lo stesso nome farebbero cose
        diverse nella stessa applicazione.

        LA BARRA E' SUL BORDO INFERIORE DELLA CARD, PER TUTTA LA LARGHEZZA
        ---------------------------------------------------------------
        Nella Home la barra e' dentro la miniatura perche' la miniatura e'
        quasi tutta la card.  Qui il posto libero e' il bordo in basso della
        card: una riga orizzontale che attraversa tutta la larghezza e dice che
        il pezzo e' quello che si sta scaricando.  Dentro il quadrato della
        copertina sarebbe una tacca di 92 pixel accanto all'icona, e con quattro
        card in fila non si saprebbe quale delle quattro sta scaricando.

        E' alta **3** pixel e non 4: dentro una cella alta 100, quattro pixel
        sono una striscia spessa quanto un quinto della cover.  Tre la si vede
        e non si distingue dall'icona.
        """
        from PyQt6.QtWidgets import QProgressBar, QPushButton

        # DUE COSE DIVERSE SOTTO LO STESSO TASTO
        # ---------------------------------------
        # Una pubblicazione si scarica chiedendo il pacchetto, e il suo stato
        # lo dice `_stato_nuvoletta` guardando la cartella sul disco.
        #
        # Un media e' un **file**, non una cartella: non c'e' nessun pacchetto da
        # chiedere e nessuna cartella da guardare.  Il suo stato lo dice
        # `MediaScaricati`, che sa se quel file c'e'.
        #
        # Qui si sceglie **quale** delle due domande fare, e non si riscrivono
        # i due modi: la nuvoletta e' un bottone solo e deve restare uno solo.
        # LE DUE CHIUSURE LEGGONO `self.cosa`, E NON UNA COPIA
        # ---------------------------------------------------
        # Qui dentro c'era `def _scarica(): self.scaricaChiesta.emit(cosa)`, con
        # `cosa` presa dal costruttore.  Su una card che vive per sempre va bene;
        # su una card **riusata** e' un calcio: la chiusura tiene il dizionario
        # del pezzo di **prima**, quindi scaricando la terza riga si scarica il
        # pezzo della prima, e il menu apre il menu del pezzo sbagliato.
        #
        # Il difetto non si vede subito: il click funziona, e funziona sul serio.
        # Lo si vede quando si scarica una cosa diversa da quella su cui si e'
        # premuto, e allora sembra che il programma abbia scaricato a caso.
        #
        # Per questo leggono `self.cosa` al momento del click.  La card e' quella
        # su cui si e' premuto, quindi `self.cosa` e' per definizione il pezzo
        # giusto: non c'e' niente da tenere allineato.
        def _scarica() -> None:
            # Mentre scarica, il tasto e' «Annulla scaricamento».
            if getattr(self, "_annulla_attivo", False):
                from Utility.FileDownloader import FileDownloader
                FileDownloader.annulla()
                self._scarica.setEnabled(False)
                return
            self.scaricaChiesta.emit(self.cosa)

        def _menu() -> None:
            # LA POSIZIONE E' DI QUESTA CARD, E NON DELLA PRIMA
            # -------------------------------------------------
            # Qui si mandava `(CELLA_LARGA - 28, 24)`, che sono le coordinate
            # del bottone **dentro una cella** — e chi le riceve le applicava
            # alla griglia.  Il risultato era che il menu' si apriva sempre
            # sotto il bottone della prima card in cima, qualsiasi «...» si
            # premesse: su una griglia di quaranta righe il menu' spariva
            # fuori dalla vista, e l'utente premeva un tasto e non vedeva
            # niente.
            #
            # Adesso la cella manda il punto **globale** del proprio bottone,
            # cioe' il punto sullo schermo: il menu' si apre li' dov'e' la
            # card che lo ha chiesto, una alla volta.
            from PyQt6.QtCore import QPoint
            punto = self._tre_punti.mapToGlobal(
                QPoint(0, self._tre_punti.height()))
            self.menuChiesto.emit(self.cosa, punto)

        # Gli stessi due tasti della Home — stesso oggetto `bottoneCard` del
        # foglio di stile, stessa misura 20 per 20 — ma figli della **card**,
        # perche' e' la card che e' larga 417.
        self._tre_punti = QPushButton(self)
        self._tre_punti.setObjectName("bottoneCard")
        self._tre_punti.setFixedSize(20, 20)
        self._tre_punti.setIcon(icon("ellipsis.circle", "#ffffff", 16))
        self._tre_punti.setToolTip("Altre azioni")
        self._tre_punti.setFlat(True)
        self._tre_punti.clicked.connect(_menu)
        self._tre_punti.setGeometry(CELLA_LARGA - 28, 6, 20, 20)

        self._scarica = QPushButton(self)
        self._scarica.setObjectName("bottoneCard")
        self._scarica.setFixedSize(20, 20)
        self._scarica.setFlat(True)
        self._scarica.clicked.connect(_scarica)
        # In basso a destra, ma **sopra** la barra: se stessero sulla stessa
        # riga, l'icona del download coprirebbe la barra per i suoi 20 pixel e
        # il progresso sembrerebbe fermo proprio dove si scarica.
        self._scarica.setGeometry(CELLA_LARGA - 28, CELLA_ALTA - 32, 20, 20)

        self._metti_la_nuvoletta(cosa)

        self._tre_punti.raise_()
        self._scarica.raise_()

        # LA BARRA, LUNGO TUTTO IL BORDO INFERIORE
        #
        # Il nome nel foglio di stile e' `scaricaBarraCard` e non
        # `scaricaBarra`: quello di casa e' alto 6 pixel, che dentro una card
        # larga 417 e alta 100 sono un sesto della copertina e si leggono come
        # un bordo colorato invece che come un progresso.  Sono due regole
        # diverse invece di una sola modificata, perche' la barra della Home
        # sta dentro una miniatura di 124 pixel dove 6 pixel vanno bene — e non
        # si tocca una cosa che gia' funziona per farne funzionare un'altra.
        self._barra = QProgressBar(self)
        self._barra.setObjectName("scaricaBarraCard")
        self._barra.setTextVisible(False)
        self._barra.setRange(0, 0)          # 0,0 = non si sa ancora
        self._barra.setFixedHeight(5)
        self._barra.setGeometry(0, CELLA_ALTA - 5, CELLA_LARGA, 5)
        self._barra.hide()

        def comincia(totale: int = 0) -> None:
            self._annulla_attivo = True
            self._scarica.setEnabled(True)
            self._scarica.setIcon(icon("xmark", "#ffffff", 16))
            self._scarica.setToolTip("Annulla scaricamento")
            self._scarica.show()
            self._scarica.raise_()
            self._barra.setRange(0, totale if totale > 0 else 0)
            self._barra.setValue(0)
            self._barra.show()
            self._barra.raise_()

        def avanza(scritti: int, totale: int) -> None:
            if not self._barra.isVisible():
                return
            if totale > 0 and self._barra.maximum() != totale:
                self._barra.setRange(0, totale)
            self._barra.setValue(scritti)

        def finito() -> None:
            self._annulla_attivo = False
            self._scarica.setEnabled(True)
            self._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
            self._scarica.setToolTip("Scarica")
            self._barra.hide()

        self._comincia, self._avanza, self._finito = comincia, avanza, finito

        # I TRE NOMI SONO QUELLI DELLA HOME, E NON UN DETTAGLIO
        # -----------------------------------------------------
        # La barra di questa cella si accende e si spegne da fuori, e chi la
        # accende non e' questa classe: e' `SidebarView`, che segue il
        # download e chiama la card giusta con tre nomi.  Quelle tre righe
        # sopra sono gli equivalenti interni, ma sono chiamati come si chiamava
        # questa cosa **prima** che la barra esistesse qui dentro.
        #
        # Il risultato era che la barra non si accendeva mai: `SidebarView`
        # cercava `_scarica_comincia` e non lo trovava, quindi non dava nessun
        # errore — semplicemente non guardava la cella.  Il progresso si
        # vedeva solo nella riga in fondo alla finestra, e quella riga parla
        # di un pezzo fra venti che si scorrono: non dice quale sta scendendo.
        #
        # I tre nomi sono un **contratto** con `SidebarView`, non una scelta:
        # si cambiano tutti e tre insieme, da un lato e dall'altro, e non uno
        # solo perche' «qui tanto non lo chiama nessuno».
        self._scarica_comincia, self._scarica_avanza, self._scarica_finita = (
            self._comincia, self._avanza, self._finito)

    def showEvent(self, evento) -> None:
        """La card appare: la nuvoletta si rimette come vuole il disco **adesso**.

        PERCHE' QUI E NON SOLO QUANDO NASCE LA CARD
        --------------------------------------------
        Prima la nuvoletta si decideva una volta sola, nel costruttore, e ogni
        altro cambiamento andava detto a mano.  E' fragile perche' il pacchetto
        può cambiare **fra** la costruzione e la mostra: un download che
        finisce, una cancellazione, un elimina.

        Il sintomo era mezzo fatto: la nuvoletta spenta con la scritta
        «Scarica» sotto, e il menu che diceva «Scarica» — tutto giusto tranne il
        tasto, che non si vedeva.  Il programma sapeva la verita' e non la
        mostrava.

        Qui la domanda si fa **quando la card compare**, che e' l'unico momento
        in cui si puo' rispondere senza indovinare: il disco e' gia' a posto e la
        card sta per essere vista.

        Non costa niente: una lettura di cartella per le venti card che si
        vedono, e nessuna per le altre — `showEvent` non viene chiamato su una
        card fuori schermo.
        """
        super().showEvent(evento)
        self._rivedi_la_nuvoletta()

    def _rivedi_la_nuvoletta(self) -> None:
        """La nuvoletta come merita il pacchetto adesso: scarica, aggiorna, o niente."""
        pub = self.cosa.get("pub")
        if pub is None:
            return
        if not self.ha_comandi:
            return
        try:
            from SubViews.PubListView import esiste_il_pacchetto
            from SubViews.HomeView import _stato_nuvoletta
            from Utility import Lingua

            # La stessa riga del costruttore, parola per parola: la lingua
            # e' il **simbolo** («I», non 4), perche' `_stato_nuvoletta`
            # confronta con i nomi delle cartelle sul disco, che sono
            # `<sigla>_<lingua>_<anno>`.  Passando il numero la cartella non
            # corrisponderebbe e ogni pubblicazione sembrerebbe da scaricare.
            lingua = Lingua.da_numero(
                getattr(pub, "mepsLanguageId", 0) or 0)
            sigla = getattr(pub, "keySymbol", "") or ""
            from Utility.JWPubManager import pub_dir_name
            stato = _stato_nuvoletta({"cartella": pub_dir_name(pub)}, sigla, lingua)
        except Exception:  # noqa: BLE001 - una nuvoletta non deve fermare nulla
            return

        if stato == "download":
            self._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
            self._scarica.setToolTip("Scarica")
            self._scarica.setVisible(True)
        elif stato == "update":
            self._scarica.setIcon(icon("arrow.clockwise", "#ffffff", 16))
            self._scarica.setToolTip("Aggiorna: c'e' una versione nuova")
            self._scarica.setVisible(True)
        else:
            self._scarica.setVisible(False)
            self._scarica.setIcon(QIcon())
            self._scarica.setToolTip("")
        self._scarica.raise_()

    def metti_immagine(self, immagine) -> None:
        """Mette la copertina al posto dell'icona, quando arriva dal thread.

        L'immagine arriva **dopo**: il catalogo si legge dal disco ma le
        copertine si chiedono al server, e chiederne 300 mentre si disegna
        bloccherebbe la finestra per minuti.  Il thread porta via i byte e il
        main thread fa il `QPixmap`, che non si puo' fare da un altro thread.

        La copertina e' **tagliata in quadrato**, non stirata: stirare una
        copertina 300 per 450 in un 100 per 100 la trasformerebbe in una
        striscia, e il titolo accanto direbbe una cosa diversa dall'immagine.
        E' quello che fa gia' `Copertine.pixmap_quadrata` anche nella Home, e
        per questo non si riscrive qui.

        Se la cella e' gia' stata distrutta — l'utente ha cambiato categoria
        mentre il thread lavorava — non si fa niente.  Scrivere in un widget
        distrutto e' il modo di far crashare il programma dopo che l'utente ha
        gia' fatto altro, e il difetto non si vede in nessuna prova perche'
        dipende da quanto ci si ferma.
        """
        from PyQt6 import sip
        from Utility.Copertine import pixmap_quadrata

        if immagine is None or sip.isdeleted(self):
            return
        quadro = getattr(self, "_quadro", None)
        if quadro is None or sip.isdeleted(quadro):
            return
        quadrata = pixmap_quadrata(immagine, self.lato_icona)
        if quadrata is None:
            return
        # Il quadrato della copertina e' senza bordo e senza sfondo: con
        # l'icona dentro era trasparente, e deve restarlo anche con la
        # copertina, altrimenti il rettangolo grigio del segnaposto coprirebbe
        # l'immagine appena arrivata.
        quadro.setObjectName("miniatura")
        quadro.setPixmap(quadrata)

    # ------------------------------------------------------------------
    # LA FORMA A FOTO CON IL TITOLO SOPRA
    # ------------------------------------------------------------------
    def _costruisci_video(self, cosa: dict) -> None:
        """Foto a tutto riempimento, sfumata nera e titolo bianco sopra.

        I TRE SI SOVRAPPONGONO, E COME
        -----------------------------
        Foto, sfumata e titolo occupano **la stessa cella** di una
        `QGridLayout`, tutti e tre in posizione (0, 0).  In Qt un
        `QGridLayout` mette nella stessa cella tanti widget quanti gliene
        diamo, e uno sopra l'altro: e' il modo di mettere qualcosa sopra
        qualcosa.

        La prima versione li impilava con una `QVBoxLayout`, cioe' uno sotto
        l'altro, e la sfumata aveva l'altezza **della cella intera**: la foto
        si trovava con zero pixel di altezza e non si vedeva, e la tile
        diventava un rettangolo nero con scritto il titolo.  Il sintomo e'
        quello che sembra un'immagine che non si scarica, e non un errore di
        layout.

        La sfumata infatti e' un rettangolo **senza** altezza fissa: prende
        tutta la cella come fa la foto, ed e' la sua trasparenza che fa
        scalare la foto sotto.  Se avesse un'altezza fissa prenderebbe posto
        a qualcun altro.
        """
        griglia = QGridLayout(self)
        griglia.setContentsMargins(0, 0, 0, 0)
        griglia.setSpacing(0)

        # La foto, sotto.
        foto = QLabel(self)
        foto.setObjectName("fotoCella")
        foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        anteprima = cosa.get("_anteprima")
        if anteprima is not None and not anteprima.isNull():
            foto.setPixmap(anteprima)
        else:
            # Senza foto c'e' il grigio del segnaposto.  E' il colore `img`
            # del tema: non e' un colore inventato qui, e in scuro viene
            # scuro da solo.
            foto.setStyleSheet(
                f"background-color: {_colore('img', '#e8e6e4')}; border: none;"
            )
        griglia.addWidget(foto, 0, 0)

        # La sfumata, sopra la foto e senza altezza fissa.
        sfumata = QLabel(self)
        sfumata.setObjectName("sfumaturaVideo")
        griglia.addWidget(sfumata, 0, 0)

        # Il titolo bianco sopra la sfumata.  Va dentro un contenitore suo
        # perche' ha 16 pixel di vuoto a sinistra e sta centrato in verticale:
        # metterlo direttamente nella cella della griglia lo incollerebbe a un
        # angolo.  Il contenitore e' trasparente, altrimenti coprirebbe la
        # sfumata che sta sotto.
        sopra = QWidget(self)
        sopra.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        pila = QVBoxLayout(sopra)
        pila.setContentsMargins(16, 0, 16, 0)
        titolo = QLabel(cosa.get("titolo") or "?", sopra)
        titolo.setObjectName("titoloVideo")
        titolo.setWordWrap(True)
        pila.addStretch(1)
        pila.addWidget(titolo, 0)
        pila.addStretch(1)
        griglia.addWidget(sopra, 0, 0)

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.scelto.emit(self.cosa)
        super().mousePressEvent(evento)


def _a_punto(posizione):
    """Un punto in coordinate di widget, da una tupla o da un `QPoint`.

    `QMenu.exec` accetta un `QPoint`, e la cella manda il punto come tupla
    `(x, y)` perche' e' la forma che `setGeometry` usa gia' per i due bottoni
    dentro la copertina.  Sono la stessa cosa a coordinate intere — un bottone
    sta su pixel interi, non su mezzo pixel — e convertire qui evita di
    ripetere la conversione in ogni chiamata.
    """
    from PyQt6.QtCore import QPoint

    if isinstance(posizione, QPoint):
        return posizione
    if isinstance(posizione, (tuple, list)):
        return QPoint(int(posizione[0]), int(posizione[1]))
    return QPoint(int(posizione.x()), int(posizione.y()))


def _colore(ruolo: str, ripiego: str = "#4f4f4f") -> str:
    """Un colore del tema che sta a schermo adesso.

    Serve per i pezzi che disegnano **senza foglio di stile**: il colore di
    un pixmap non lo legge nessuno, e il foglio di stile non lo governa.

    Il tema chiesto e' `tema.tema_attivo()`, non `tema.tema_salvato()`.  Il
    secondo legge il **file**, e il file cambia solo quando l'app viene
    chiusa: dentro la finestra, subito dopo aver premuto il tema scuro, il
    file direbbe ancora «chiaro» e le icone uscirebbero grigio scuro su fondo
    scuro, cioe' invisibili.  Sarebbe un difetto che si vede solo in scuro e
    solo dopo aver cambiato tema a mano, che e' il modo peggiore.

    Il ripiego c'e' per quando il tema attivo non e' ancora stato deciso
    (per esempio in un controllo che costruisce la sezione da solo): meglio
    un colore plausibile che un'eccezione che impedisce di aprire la
    finestra.
    """
    try:
        return tema.colori(tema.tema_attivo())[ruolo]
    except (KeyError, TypeError, AttributeError):
        return ripiego


def _tema_chiaro() -> bool:
    """Il tema che sta a schermo: chiaro o scuro."""
    try:
        return tema.tema_attivo()
    except (AttributeError, TypeError):
        return True


class MediaView(QWidget):
    """La sezione Media: audio e video."""

    messaggio = Signal(str)
    goBack = Signal()
    #: Il lettore si e' chiuso, o il brano/video e' finito.  Serve a chi ha
    #: aperto il media da un'altra sezione: quella sezione lo sa, e puo'
    #: riportare l'utente da dove era partito invece di lasciarlo qui.  Vedi
    #: `SidebarView._torna_da_dove_sono_partito`.
    lettoreChiuso = Signal()
    #: La lista e' arrivata e la traccia chiesta da una card sta per partire:
    #: e' il momento in cui la finestra porta qui l'utente (non prima).
    staPerSuonare = Signal()
    #: Un passo di testo trovato dalla barra di ricerca e' stato premuto
    testoScelto = Signal(dict)
    #: L'utente ha premuto la freccia gi' del lettore grande e vuole la
    #: striscia piccola, per poter girare per l'app mentre suona.
    #:
    #: Rilancato da `LettoreView.ripiccolato` perche' la finestra e' l'unica
    #: che sa cosa sia la striscia in fondo e come si torna alla sezione da cui
    #: si e' partiti.  Media non puo' farlo da sola: la striscia sta in un
    #:'altra parte della finestra e Media non la vede nemmeno.
    ripiccolato = Signal()
    #: L'utente ha premuto una categoria di pubblicazioni e vuole vederne le
    #: pubblicazioni.  Il segnale porta **la chiave della categoria** (quella
    #: di `CATEGORIE_PUB`), e non niente: senza, la finestra saprebbe che
    #: l'utente ha premuto una categoria ma non quale, e il catalogo si
    #: aprirebbe tutto — che e' la stessa cosa che non aprire niente, con
    #: quattrocento righe in piu'.
    #:
    #: Non porta la pubblicazione ne' il nome: la categoria e' l'unica cosa
    #: che la griglia sa e che la lista non puo' indovinare.
    apriPubblicazioni = Signal(str)
    #: Una pubblicazione scaricata da aprire.  Il secondo valore e' la stringa
    #: che dice **cosa** aprire, con lo stesso contratto che usa la sezione
    #: Scaricati: `""` per il pacchetto, `"audio"` o `"video"` per le tracce.
    #: Questa sezione manda sempre `""`: scegliere qui sarebbe un secondo
    #: posto con la stessa regola.
    scaricatoAperto = Signal(object, str)
    #: L'utente ha premuto la nuvoletta o il refresh su una card di una
    #: pubblicazione: scaricala o aggiornala.  Il segnale porta l'oggetto
    #: `Publication` e non il dizionario della cella, perche' chi scarica ha
    #: bisogno del pacchetto e non del disegno.
    #:
    #: Non viene da `scaricatoAperto`: quello apre un pacchetto **gia' sul
    #: disco**, e questo lo porta.  Sono due direzioni opposte e una sola
    #: simbolo per le due sarebbe stato comodo e sbagliato.
    scaricaRichiesta = Signal(object)
    #: Un pacchetto e' stato tolto dal disco.  Chi ascolta rilegge quello che
    #: guarda il disco: la griglia di questa sezione e quella degli Scaricati.
    pacchettoRimossa = Signal(object)
    #: I Preferiti sono cambiati sul disco.  La Home ha una striscia di
    #: Preferiti: senza dirle che il file e' cambiato continuerebbe a mostrare
    #: la stella come prima fino al prossimo avvio.
    preferitiCambiati = Signal()
    #: Un media (video o audio) da scaricare.  Il segnale porta la voce, che
    #: e' un oggetto — e non un dizionario di disegno come per le pubblicazioni —
    #: perche' a scaricare serve il file e il suo formato, non la card.
    #:
    #: Porta anche il **punto sullo schermo** da cui e' partita la richiesta —
    #: la nuvoletta premuta o la voce del menu' «...» — perche' il menu' delle
    #: risoluzioni deve aprirsi li', sulla card che lo ha chiesto.  Senza, si
    #: apriva nel mezzo della finestra e l'utente premeva «Scarica» su una riga
    #: e vedeva un menu' apparire da un'altra parte.  `None` quando il punto non
    #: si puo' sapere: in quel caso chi lo riceve usa il centro della schermata.
    mediaScaricata = Signal(object, object)
    #: Un media da eliminare dal disco.  Stessa voce, altra azione.
    mediaEliminata = Signal(object)
    #: Vuole andare a un'altra sezione, per nome.  Il nome e' quello della
    #: sezione — «Home», «Biblioteca Digitale», «Impostazioni» — e non un
    #: indice: gli indici cambiano se si aggiunge una sezione, e un menu' che
    #: punta a un indice apre la sezione sbagliata senza dire niente.
    #:
    #: Serve per la voce «Preferiti» del menu' della card: i Preferiti sono
    #: una striscia **nella Home**, e questa sezione non sa accenderla.  Il
    #: segnale porta il nome e chi ascolta fa il resto.
    vaiAllaSezione = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pubblicazione = ""
        self._caricata = ""
        # La lingua dei media di **questa sezione**.  Prima qui cominciava
        # `""`, e la sezione restava in quello stato finche' l'utente non
        # sceglieva una pubblicazione: aprendo Multimedia e premendo una
        # linguetta delle categorie, la richiesta partiva con la lingua
        # vuota e il server rispondeva 404.  Lo stesso per i nomi delle
        # linguette, che si chiedono all'avvio.
        #
        # Il nome della lingua lo sa gia' `Lingua`, e la sezione non ha
        # motivo di aspettare che qualcuno glielo dica: senza pubblicazione
        # scelta si mostrano i media della lingua in cui si sta leggendo.
        self._lingua = Lingua.corrente_simbolo()
        self._titolo_pubblicazione = ""
        self._voci: list[dict] = []
        # LA SEZIONE SI APRE SULLE PUBBLICAZIONI, NON SULL'AUDIO
        # -------------------------------------------------------
        # Qui era `0`, e `0` e' `TAB_AUDIO`: entering in «Biblioteca Digitale»
        # apriva i suoni invece del catalogo.
        #
        # Il numero e' copiato dal costrutto e non messo a mano perche' le
        # quattro tab non sono in ordine: sono Audio 0, Video 1,
        # Pubblicazioni 2, Scaricati 3.  Il nome dice «terzo» e il valore
        # dice «1», quindi un numero scritto a mano nella posizione sbagliata
        # non si nota fino a quando l'app non apre sulla tab sbagliata — che e'
        # esattamente quello che era successo.
        #
        # Perche' le pubblicazioni e non i media: e' la sezione che l'utente
        # entra per guardare, e il catalogo e' la cosa che c'e' da vedere in
        # una biblioteca.  Suona piu' semplice di quel che e', ma il difetto
        # che c'era — aprire su una lista di suoni quando l'utente e' venuto a
        # cercare un libro — non si vede da nessuna parte nel codice.
        self._scheda = TAB_PUBBLICAZIONI
        # LE PUBBLICAZIONE DEL CATALOGO, DUE POSTE
        # -----------------------------------------
        # `_catalogo` e' l'elenco letto da `catalog.db`, letto **una volta** e
        # tenuto: sono 3.745 righe, e rileggerle a ogni categoria premuta si
        # sente come un'esitazione dell'app.
        self._catalogo: list = []
        # `_tutte_le_categorie` tiene, per ogni chiave di categoria, **tutte**
        # le pubblicazioni — non le 300 che si disegnano.  Serve alla ricerca,
        # che altrimenti cercherebbe solo fra le prime 300 e direbbe che gli
        # altri titoli non esistono.
        self._tutte_le_categorie: dict[str, list] = {}
        # La categoria di cui si stanno vedendo le pubblicazioni, o "" se si
        # stanno ancora vedendo le dieci categorie.  E' il pezzo che fa il
        # ritorno: premendo il «torna alle categorie» torna a "", e la griglia
        # si riempie di categorie senza nessun altro stato da ricordare.
        self._categoria_aperta: str = ""
        #: Vero mentre un thread sta scaricando le copertine.  Serve a non
        #: partire una richiesta nuova a ogni lettera scritta nella ricerca:
        #: dieci thread in cerca di copertine mentre l'utente digita «gennaio»
        #: non aiutano nessuno e il server li vede tutti insieme.
        self._copertine_in_corso: bool = False
        #: Id delle voci di media di cui l'anteprima e' **gia' stata chiesta**
        #: in questa sessione.  Serve a due cose: non richiedere due volte la
        #: stessa locandina a ogni ridisegno, e far smettere il ciclo di
        #: `_chiedi_antprime` sulle voci che hanno gia' l'immagine anche se la
        #: loro card non e' piu' a schermo.  Si svuota cambiando sezione o
        #: categoria, come `_copertine_chieste`.
        self._antprime_fatte: set = set()
        #: Vero mentre un thread sta prendendo le locandine dei media.
        self._antprime_in_corso: bool = False
        #: Le chiavi di categoria di cui chiedere l'immagine, e se e' gia'
        #: arrivata.  Vedi `_chiedi_antprime_categorie`: una card di categoria
        #: non ha una voce, quindi ha bisogno di una strada sua, ma non di un
        #: punto di partenza suo.
        self._antprime_cat_chiavi: list = []
        self._antprime_cat_fatte: dict = {}
        self._antprime_cat_in_corso: bool = False
        #: Le pubblicazioni di cui chiedere la copertina **alla prossima**
        #: `_riempi_griglia`.  Lo mette `_celle_del_catalogo` e lo legge
        #: `_riempi_griglia`, che e' il posto dove le card sono davvero nella
        #: griglia: chiedere le copertine prima non trova nessuna card a cui
        #: attaccarle.
        self._copertine_da_chiedere: list = []
        #: Gli ID delle pubblicazioni di cui la copertina e' **gia' stata
        #: chiesta**.  Serve a non richiedere due volte le stesse copertine
        #: scorrendo: ogni richiesta che torna vuota viene ricordata da
        #: `Copertine` come «non esiste» e non si ripete, quindi chiedere
        #: ancora produrrebbe solo traffico sprecato.
        self._copertine_chieste: set = set()
        # La traccia che una card ha chiesto di far partire appena la lista
        # arriva.  E' ``(traccia, scheda)`` o ``None``: la usa `apri_e_suona`,
        # la consuma `_forse_suona`.  ``None`` vuol dire "nessuno ha chiesto
        # niente", che e' il caso normale.
        self._da_suonare = None
        # La categoria scelta nel mediator, o "" se si guarda la pubblicazione.
        # Non e' un semplice avanzamento delle schede: cambia **cosa** e' la
        # lista, e non c'e' nessuna pubblicazione dietro.  Per questo e' un
        # attributo tutto suo e non un valore delle due schede Audio/Video.
        self._categoria = ""
        # La parola cercata, in minuscolo e senza caratteri speciali.
        # Comincia qui e non la introduce `_cerca_cambiata`: quello parte da
        # un campo gia' scritto, e questa sezione si disegna anche senza che
        # nessuno scriva niente.
        self._testo_cercato = ""
        # TRE STATI, E PRIMA ERAVANO DUE
        # -------------------------------
        # La sezione sapeva solo una cosa: `_voci` vuota o non vuota.  E da
        # quello deduceva «questa categoria non ha media».  Ma una lista
        # vuota vuol dire tre cose diverse:
        #
        #   - la richiesta non e' ancora tornata  -> `_in_corso`
        #   - la richiesta e' FALLITA             -> `_errore`
        #   - la richiesta e' tornata e non c'e' niente -> nessuno dei due
        #
        # Il secondo caso e' quello che dava la bugia: senza rete, premendo
        # «Notizie dai rulli», la sezione scriveva ««Notizie dai rulli» non ha
        # media da mostrare».  Ne ha 79, misurati: sono video.  Il programma
        # stava dicendo una cosa falsa sui dati per coprire un problema di
        # rete, che e' il modo peggiore in cui si puo' sbagliare — l'utente
        # crede che il server non abbia quella categoria.
        self._in_corso = ""
        self._errore = ""
        # Le linguette delle categorie, per poterci rimettere dentro il nome
        # che il server scrive.  Vedi `_chiedi_nomi`, che e' il metodo: il
        # commento qui diceva `_chiedi_nomi_categorie`, un nome che non
        # esiste, quindi non si poteva cercare il posto giusto per capire
        # come i nomi arrivassero — e infatti nessuno lo aveva trovato.
        self._linguette: list = []
        #: Il nome vero di ogni categoria, quando il server l'ha mandato.
        #: Serve alle **card**: le linguette non ci sono piu' in alto, quindi il
        #: nome non ha piu' un widget in cui essere scritto.  Un dizionario e'
        #: il posto giusto perche' si cerca per chiave e non per posizione.
        self._nomi_categoria: dict = {}

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)

        pagina = QWidget()
        disposizione = QVBoxLayout(pagina)
        # I margini della PAGINA sono zero, e i 18 pixel li mette ogni riga.
        #
        # Non e' una scelta di gusto: la griglia delle celle deve partire dal
        # bordo sinistro, come nella schermata dell'app originale, e con 18 di
        # margine su tutta la pagina la prima cella avrebbe 18 pixel di
        # vuoto a sinistra mentre tutte le altre no.  Ogni riga sa quanto
        # vuole: la striscia delle tab 18, il campo 18, la griglia 0.
        disposizione.setContentsMargins(0, 0, 0, 0)
        disposizione.setSpacing(0)
        disposizione.setAlignment(Qt.AlignmentFlag.AlignTop)

        # IL CAMPO DI RICERCA
        # -------------------
        # Lo chiedi tu, e il motivo e' che senza non si capiva niente: la
        # sezione mostrava centinaia di righe di video senza modo di
        # arrivare a uno in particolare.  Con 424 discorsi e 315 notizie, la
        # lista e' piu' lunga di quanto si possa leggere scorrendo, e
        # l'unico modo per trovare "Amiamio le pecore smarite" era sapere
        # gia' che c'era.
        #
        # Sta SOPRA tutto e non dentro: e' un campo che appartiene alla
        # sezione, non a una scheda.
        #
        # Perche' `QLineEdit` e non la casella della fascia: la casella cerca
        # in tutta l'app e qui si cerca in questa lista.  Due campi con lo
        # stesso nome che cercano in posti diversi sono due cose che
        # l'utente non distingue, e il primo che prova fa a cercare la
        # Bibbia nella sezione Media.
        self.cerca = QLineEdit(pagina)
        self.cerca.setObjectName("campoCerca")
        self.cerca.setPlaceholderText("Cerca fra i media")
        self.cerca.setClearButtonEnabled(True)
        self.cerca.textChanged.connect(self._cerca_cambiata)
        # La stessa barra cerca anche nel testo: i passi trovati compaiono in un
        # elenco a tendina sotto la barra, non in un'altra schermata.
        from SubViews.RisultatiTesto import RisultatiTesto
        self._risultati_testo = RisultatiTesto(self)
        self._risultati_testo.scelto.connect(self.testoScelto.emit)
        self._attesa_testo = QTimer(self)
        self._attesa_testo.setSingleShot(True)
        self._attesa_testo.setInterval(300)
        self._attesa_testo.timeout.connect(self._cerca_nel_testo)
        self._numero_ricerca = 0
        self.cerca.installEventFilter(self)
        # Il contatore accanto al campo, **come nella sezione
        # Pubblicazioni**: stesso oggetto di nome, stesso modo di contare,
        # stesse parole.  E' la riga che dice se la ricerca ha trovato
        # qualcosa, e senza di quella un campo vuoto sembra una ricerca
        # fallita anche quando ha trovato venti righe.
        self.conteggio = QLabel("", pagina)
        self.conteggio.setObjectName("nota")
        # La riga che li tiene insieme viene costruita piu' sotto, con le tab:
        # sta sotto di loro e non sopra tutto.

        # LE CATEGORIE DEL MEDIATOR, SOPRA LE SCHEDE AUDIO/VIDEO
        # ---------------------------------------------------------
        # Lo hai deciso tu: dentro la sezione Multimedia, non in una sezione
        # nuova.  Sta sopra le due schede perche' risponde alla domanda
        # **prima**: "di cosa guardo i media".  Scelta la pubblicazione si
        # scelgono Audio o Video; scelta una categoria del mediator non si
        # sceglie, perche' quelle voci sono gia' tutte video e filtrarle fra
        # Audio e Video mostrerebbe una scheda vuota e una piena senza
        # motivo.
        #
        # La prima linguetta e' "Pubblicazione", e torna al comportamento di
        # prima.  Senza, una volta scelta una categoria non si tornava indietro
        # senza chiudere la sezione, e la scelta fatta a caso diventava
        # irreversibile per la sessione.
        # LE QUATTRO TAB DELLA BIBLIOTECA
        # -------------------------------
        # Vanno **sopra tutto**, anche sopra il campo di ricerca: sono la
        # domanda piu' grossa della sezione ("di cosa guardo i media") e
        # rispondono a quella, non a quello che si cerca dentro una lista.
        #
        # La striscia ha un contenitore suo perche' il campo di ricerca sotto
        # si nasconde nelle due tab che non cercano niente.  Una riga di
        # layout non si puo' nascondere: si nasconde il widget che la contiene,
        # quindi servono due contenitori e non uno.
        self._striscia = QWidget(pagina)
        tema.sfondo(self._striscia, "strisciaTab")
        riga_striscia = QHBoxLayout(self._striscia)
        riga_striscia.setContentsMargins(18, 0, 18, 0)
        riga_striscia.setSpacing(0)
        disposizione.addWidget(self._striscia)

        # `_tabs` e' la lista di tutte e quattro, perche' al cambio di tab
        # bisogna sapere quale era attiva: `attendi` si chiama su tutte e
        # quella con il numero giusto si accende.  Tenerle in una lista evita
        # di tenerle in un attributo per tab, che al quarto tab finisce in
        # quattro attributi.
        self._tabs: list[_Tab] = []
        for posizione, (titolo, indice) in enumerate(TABS):
            tab = _Tab(indice, titolo, attiva=(indice == self._scheda),
                       padre=self._striscia)
            tab.clic.connect(self._scegli_scheda)
            riga_striscia.addWidget(tab)
            self._tabs.append(tab)
        # La striscia e' alta 48 come nella schermata originale.  Fissarla
        # serve perche' con una tab sola la riga si stringerebbe a 20 pixel e
        # la barra viola sotto cadrebbe dove capita.
        self._striscia.setFixedHeight(48)
        riga_striscia.addStretch(1)
        self._pagina = pagina

        # IL CAMPO DI RICERCA, SOTTO LE TAB
        # ---------------------------------
        # Prima stava sopra tutto, e adesso sta sotto: le tab rispondono alla
        # domanda grossa e la ricerca sta dentro quello che le tab scelgono.
        # Nelle due tab che non hanno una lista da cercare il campo sparisce,
        # e con lui il contatore accanto.
        self._contenitore_cerca = QWidget(pagina)
        riga_cerca2 = QHBoxLayout(self._contenitore_cerca)
        riga_cerca2.setContentsMargins(18, 10, 18, 10)
        riga_cerca2.setSpacing(8)
        disposizione.addWidget(self._contenitore_cerca)
        riga_cerca2.addWidget(self.cerca, 1)
        riga_cerca2.addWidget(self.conteggio, 0)

        # LE CATEGORIE DEL MEDIATOR
        # -------------------------
        # Stanno sotto le tab e sopra il contenuto, e valgono solo per Audio e
        # Video: sono un sottoinsieme di quelle due.  Nelle altre due tab il
        # contenitore sparisce, e con lui le linguette.
        self._contenitore_categorie = QWidget(pagina)
        riga_scelta = QHBoxLayout(self._contenitore_categorie)
        riga_scelta.setContentsMargins(18, 0, 18, 10)
        riga_scelta.setSpacing(8)
        disposizione.addWidget(self._contenitore_categorie)
        self._contenitore_categorie.setVisible(False)

        self._costruisci_categorie(pagina, riga_scelta)

        # LE DUE SCHEDE AUDIO/VIDEO
        # --------------------------
        # Hanno il loro contenitore perche' spariscono quando si sceglie una
        # categoria del mediator, e una riga di layout non si puo' nascondere:
        # si nasconde il widget che la contiene.  Sta dentro un contenitore
        # suo perche' altrimenti il pezzetto nascosto sarebbe stato quello
        # delle categorie — le due righe sono una dopo l'altra e i nomi si
        # somigliano — e la sezione avrebbe mostrato le schede senza le
        # categorie, cioe' esattamente il contrario di quello che si voleva.
        self._contenitore_schede = QWidget(pagina)
        riga_scelta2 = QHBoxLayout(self._contenitore_schede)
        riga_scelta2.setContentsMargins(18, 0, 18, 10)
        riga_scelta2.setSpacing(8)
        disposizione.addWidget(self._contenitore_schede)
        for indice, (titolo, simbolo) in enumerate(SCHEDE):
            scheda = _SchedaCliccabile(indice, titolo, pagina)
            scheda.clic.connect(self._scegli_scheda)
            riga_scelta2.addWidget(scheda)
        self._schede = SCHEDE
        riga_scelta2.addStretch(1)
        # NASCOSTI PER DEFAULT: si vedono solo dopo `_visibilita()`.
        # Senza questa riga, mentre l'app si sta ancora aggiornando e l'utente
        # va veloce in Biblioteca Digitale, i due tasti «Audio» e «Video»
        # restano visibili perche' `_visibilita()` non ha ancora girato.
        self._contenitore_schede.setVisible(False)
        self._contenitore_categorie.setVisible(False)

        # LA GRIGLIA: LE CELLE LARGHE DA 417
        # ---------------------------------
        # Va dentro un contenitore tutto suo, e non dentro `pagina`
        # direttamente, perche' le due cose si nascondono a vicenda: nelle
        # due tab nuove si vede la griglia e la lista no, e viceversa.
        self._contenitore_griglia = QWidget(pagina)

        # IL RITORNO ALLE CATEGORIE NON E' UN BOTTONE
        # --------------------------------------------
        # Qui prima c'era un bottone «< Tutte le categorie» sopra la griglia, e
        # sembrava la cosa giusta da mettere.  Ma la finestra ha gia' una freccia
        # indietro nella fascia, e due frecce indietro a schermo non si capiscono:
        # quella in fascia sembra uscire dalla sezione, quella dentro no, e
        # quando la freccia della fascia e' spenta — perche' la pila ha una
        # schermata sola — l'unico modo di tornare indietro sembra essere il
        # bottone nuovo.  Due modi di tornare indietro che dicono cose diverse e'
        # peggio di uno solo che non dice niente.
        #
        # Il ritorno e' adesso quello che gia' c'era: la freccia della fascia.
        # `SidebarView._torna_indietro` chiede prima alla sezione, e solo se qui
        # non c'e' niente da chiudere torna nella schermata precedente.
        #
        # La riga vuota che c'era qui e' sparita: senza il bottone non serve un
        # contenitore per ospitarlo, e 8 pixel di vuoto in alto su una griglia
        # spingerebbero le card sotto senza guadagnare niente.
        disposizione.addWidget(self._contenitore_griglia)
        self._griglia = _Griglia(self._contenitore_griglia)
        self._griglia.setSizePolicy(
            self._griglia.sizePolicy().horizontalPolicy().Expanding,
            self._griglia.sizePolicy().verticalPolicy().Preferred,
        )
        layout_griglia = QVBoxLayout(self._contenitore_griglia)
        layout_griglia.setContentsMargins(0, 0, 0, 0)
        layout_griglia.addWidget(self._griglia)

        # LE COPERTINE ARRIVANO SCORRENDO
        # --------------------------------
        # Si chiedono solo quelle che si vedono — chiedere tutte insieme fa
        # scattare il limite del CDN e `Copertine` non riprova piu' per la
        # sessione (vedi `_chiedi_copertine`).  Ma allora, quando l'utente
        # scorre, devono arrivare le successive: e nessuno glielo dice, se non
        # si sta qui ad ascoltare.
        #
        # Si ascolta la barra di scorrimento e non la griglia perche' e' la
        # barra che l'utente muove.  `_chiedi_altre_copertine` non fa nulla se
        # una richiesta e' gia' in corso, quindi si puo' chiamarla a ogni
        # pixel di scorrimento senza aprire richieste a raffica.
        self._area_griglia = area
        barra = area.verticalScrollBar()
        barra.valueChanged.connect(self._chiedi_altre_copertine)

        # IL LETTORE, SOPRA LA LISTA
        # --------------------------
        # Sta sopra e non al posto della lista: sotto si vede ancora che cosa
        # hai scelto e si puo' scegliere altro senza chiudere niente, che e'
        # quello che serve in una sezione con 424 voci.
        #
        self._lettore = LettoreView(self)
        self._lettore.ripiccolato.connect(self.ripiccolato.emit)

        # Nascosto all'avvio: un lettore vuoto sopra una lista occuperebbe
        # metà schermo e non direbbe niente.  Compare quando parte qualcosa e
        # sparisce quando finisce o quando lo chiudi.

        # IL LETTORE NON STA DENTRO LA PAGINA CHE SCORRE, E QUESTA E' LA COSA
        # che conta per il difetto della fascia: il lettore e' aggiunto al
        # layout **esterno** della sezione, piu' in basso.  Vedi la nota lunga
        # li' sotto: dentro la pagina c'era un `QVideoWidget`, che e' una
        # superficie di disegno con una finestra propria, e quella finestra
        # finiva impilata sopra la fascia.
        self._lettore.ripiccolato.connect(self.ripiccolato.emit)
        # Il lettore si chiude (bottone "stop") o il brano finisce: chi ha
        # aperto il media da un'altra sezione ascolta questo segnale e riporta
        # l'utente la'.  Vedi `SidebarView._torna_da_dove_sono_partito`.
        self._lettore.chiuso.connect(self.lettoreChiuso.emit)

        # LA LISTA
        # Ha il suo contenitore perche' i 18 pixel di vuoto sono suoi e non
        # della pagina: la pagina non ha margini (vedi sopra), e senza un
        # contenitore suo le righe della lista toccherebbero la colonna delle
        # sezioni.
        self._contenitore_lista = QWidget(pagina)
        disposizione.addWidget(self._contenitore_lista)
        cornice_lista = QVBoxLayout(self._contenitore_lista)
        cornice_lista.setContentsMargins(18, 0, 18, 16)
        cornice_lista.setSpacing(0)
        self._lista = QWidget(self._contenitore_lista)
        self._colonna = QVBoxLayout(self._lista)
        self._colonna.setContentsMargins(0, 0, 0, 0)
        self._colonna.setSpacing(6)
        cornice_lista.addWidget(self._lista)

        area.setWidget(pagina)
        # IL LETTORE STA FUORI DALL'AREA CHE SCORRE
        # -------------------------------------------
        # Prima stava dentro `pagina`, cioe' dentro la `QScrollArea`.  E la
        # pagina finiva **sopra** la fascia viola invece che sotto, e passando
        # la rotella sembrava che fosse la fascia a spostarsi.
        #
        # Il motivo non e' che la pagina sia alta piu' del dovuto: la fascia e
        # un widget fratello del contenitore, e un layout non li fa sovrapporre.
        # Il motivo e' che dentro la pagina c'era il lettore, e dentro il
        # lettore c'e' il `QVideoWidget`.  Un `QVideoWidget` **non e' un
        # widget**: e' una superficie di disegno propria, e quando parte un
        # video Qt le da' una finestra del sistema.  Un pezzo con una finestra
        # propria dentro una pagina che scorre viene impilato dal gestore
        # finestre come se fosse una finestra a se', e puo' finire sopra un
        # widget che e' suo fratello — cioe' sopra la fascia.
        #
        # Il programma avvisa di questo, e l'avviso diceva proprio quale
        # widget:
        #
        #     QWidgetWindow(0x…, name="comandiLettoreWindow") must be a top
        #     level window.
        #
        # cioe' la barra dei comandi del lettore aveva una finestra propria
        # mentre non e' una finestra.  Non e' un problema di Wayland e non e' un
        # problema di X11: e' che dentro l'area che scorre c'era una superficie
        # di disegno.  Levarla da li' lo risolve su tutti e due.
        #
        # E il lettore **sta meglio** cosi': fermo sopra la lista, quindi i
        # comandi restano visibili mentre si scorre fra i video, che e' quello
        # che serve.  Sotto, prima, scorrendo la lista il lettore saliva via
        # con le righe.
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        esterno.setSpacing(0)
        # Il lettore (video + comandi) si espande per far vedere il video;
        # l'area della lista sta sotto e prende lo spazio che avanza.
        esterno.addWidget(self._lettore, 1)

        # HANDLE DI RIDIMENSIONAMENTO TRA PLAYER E LISTA
        # ------------------------------------------------
        # Stile reference: SplitVCursor sull'handle, drag fluido che ridimensiona
        # il blocco player (video+comandi) vs lista.  L'handle è la barra sottile
        # tra i due: si trascina per cambiare la proporzione.
        # Layout indices: 0=lettore, 1=handle (fixed), 2=area
        self._handle = _HandleRidimensiona(self._lettore, area, esterno, 0, 2, self)
        esterno.addWidget(self._handle, 0)

        esterno.addWidget(area, 1)
        self._lettore_fuori = False

        # NASCONDI MINI PLAYER QUANDO VA IN FULLSCREEN VERO (LettoreSchermo)
        # ----------------------------------------------------------------
        # Il segnale schermoIntero viene emesso da LettoreView quando apre/chiude
        # LettoreSchermo.  True = fullscreen aperto -> nascondi mini player.
        self._lettore.schermoIntero.connect(self._lettore.imposta_mini_player_visibile)

        # SINCRONIZZA TASTO MINI PLAYER (FRECCIA GIÙ) CON VISIBILITÀ LETTORE
        # ----------------------------------------------------------------
        # REGOLA FERREA:
        # - Player GRANDE (dentro finestra app) → tasto VISIBILE (serve per andare in mini)
        # - Player MINI (barra in fondo)     → N/A (widget nascosto, ha suo bottone)
        # - Fullscreen (LettoreSchermo)      → tasto NASCOSTO
        #
        # setVisible(True)  = torna grande → tasto VISIBILE
        # setVisible(False) = va in mini → tasto nascosto (ma widget nascosto comunque)
        self._lettore.imposta_callback_visibilita(
            lambda visibile: self._lettore.imposta_mini_player_visibile(visibile)
        )
        # Sincronizza stato iniziale: player parte LARGE -> tasto VISIBILE
        self._lettore.imposta_mini_player_visibile(False)

        # NON c'e' piu' un'etichetta di stato tenuta da parte.
        #
        # Prima `self.stato` era creata qui e messa nella colonna quando
        # non c'erano righe.  Ma `_ricostruisci` svuota la colonna e chiama
        # `deleteLater()` su tutto quello che c' trova, quindi la
        # cancellava e poi la riusava, e Qt rispondeva:
        #
        #     RuntimeError: wrapped C/C++ object of type QLabel
        #     has been deleted
        #
        # Il messaggio ora lo crea `_messaggio()` ogni volta che serve.
        # Niente da riciclare, niente che possa morire.

    # ------------------------------------------------------------------
    # LA RICERCA E LA SUDDIVISIONE
    # ------------------------------------------------------------------

    def _cerca_cambiata(self, testo: str) -> None:
        """Il campo e' stato scritto: si ridipinge la lista.

        STESSA CONVENZIONE DELLA SEZIONE PUBBLICAZIONI
        -------------------------------------------------
        Il campo risponde a ogni lettera e non c'e' un tasto: con 424 voci il
        lavoro e' una lista Python e dura meno di un millisecondo, e
        rimandarlo non serve a niente — l'utente sta scrivendo e vuole
        vedere.

        Il confronto e' quello di `DBManager.cerca_pubblicazioni`: contiene,
        non comincia.  Con "pecore" si devono trovare anche "Amiamio le pecore
        smarite", e non solo le righe che cominciano per "pecore".  Il campo
        mette gia' i caratteri speciali fuori, come fa il catalogo: `%` e `_`
        non sono jolly e non fanno fallire niente.
        """
        pulito = (testo or "").strip()
        for carattere in ("\\", "%", "_"):
            pulito = pulito.replace(carattere, "")
        self._testo_cercato = pulito.lower()
        on_main(self._ricostruisci)
        if len(pulito) >= 3 and self._scheda in (TAB_PUBBLICAZIONI, TAB_SCARICATI):
            self._attesa_testo.start()
        else:
            self._numero_ricerca += 1
            self._risultati_testo.hide()

    def _cerca_nel_testo(self) -> None:
        """Cerca le parole nel testo scaricato, in secondo piano, e apre l'elenco."""
        from Utility import RicercaTesto
        from Utility.Extensions.Ext_DispatchQueue import background

        domanda = self.cerca.text().strip()
        self._numero_ricerca += 1
        numero = self._numero_ricerca
        trovati: list = []

        def lavoro() -> None:
            trovati.extend(RicercaTesto.cerca(domanda, MAX_RISULTATI_TESTO))

        def fatto() -> None:
            if numero != self._numero_ricerca or not self.cerca.hasFocus():
                return
            try:
                punto = self.cerca.mapTo(self, QPoint(0, self.cerca.height() + 2))
                self._risultati_testo.mostra(trovati, punto, self.cerca.width())
            except RuntimeError:
                pass

        background(lavoro, completion=fatto)

    def eventFilter(self, oggetto, evento) -> bool:
        """L'elenco si chiude con Esc o quando la barra perde il cursore."""
        if oggetto is self.cerca:
            if evento.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(150, self._chiudi_se_fuori)
            elif (evento.type() == QEvent.Type.KeyPress
                  and evento.key() == Qt.Key.Key_Escape):
                self._risultati_testo.hide()
        return super().eventFilter(oggetto, evento)

    def _chiudi_se_fuori(self) -> None:
        try:
            if not self.cerca.hasFocus():
                self._risultati_testo.hide()
        except RuntimeError:
            pass

    def _aggiorna_conteggio(self, quante: int, quante_in_elenco: int) -> None:
        """La riga accanto al campo: quante voci ci sono e quante si vedono.

        Le parole sono quelle della sezione Pubblicazioni — "12 media",
        "nessun media" — perche' due sezioni che dicono la stessa cosa con due
        parole diverse fanno sembrare l'app piu' complicata di quanto sia.
        """
        if self._testo_cercato:
            if not quante:
                self.conteggio.setText("nessun media")
                return
            parola = "media" if quante == 1 else "media"
            self.conteggio.setText(f"{quante} {parola} su {quante_in_elenco}")
            return
        if not quante_in_elenco:
            self.conteggio.setText("")
            return
        # `_nome_categoria` e' una **property** e gia' restituisce la stringa:
        # quindi qui si scrive senza parentesi.  Con le parentesi sarebbe
        # "'str' object is not callable"; senza, il contatore scriveva
        # l'indirizzo del metodo invece del nome — che e' la riga con dentro
        # `<bound method MediaView._nome_categoria of ...>` che si vedeva
        # accanto al campo di ricerca.
        nome = (self._nome_categoria(self._categoria) if self._categoria
                else self._pubblicazione)
        self.conteggio.setText(
            f"{quante_in_elenco} voci" if not nome
            else f"{quante_in_elenco} voci in {nome}")

    def _passa(self, voce: dict) -> bool:
        """Questa voce passa il filtro del campo di ricerca?

        La ricerca guarda **dentro la parola**, non al suo inizio: con 424
        discorsi, "pecore" deve trovare "Amiamio le pecore smarite" e non
        solo le righe che cominciano per "pecore".

        Confronto senza accenti e senza maiuscole perche' i titoli sono
        scritti come vengono dal server: "Le pecore" e "le pecore" sono la
        stessa cosa e l'utente cerca in minuscolo per abitudine.
        """
        if not self._testo_cercato:
            return True
        titolo = (voce.get("title") or voce.get("label") or "").lower()
        # anche i gruppi: cercando "dicembre" devono restare visibili le
        # voci della rivista di dicembre, e il gruppo e' quello che dice il
        # mese.
        gruppo = (voce.get("gruppo") or "").lower()
        return self._testo_cercato in titolo or self._testo_cercato in gruppo

    def _quando_video(self, voci: list) -> list:
        """Le voci di questa scheda, gia' filtrate dalla ricerca.

        UN SOLO POSTO DOVE SI SCEGLIE COSA MOSTRARE
        --------------------------------------------
        La ricerca e la scheda Audio/Video si applicano insieme, e applicarle
        in due posti diversi vuol dire che il giorno che una delle due regole
        cambiasse, le due non andassero d'accordo — e una lista con dentro un
        video mentre la scheda dice "Audio" sembrerebbe un difetto dei dati.

        IL FILTRO VALE ANCHE CON UNA CATEGORIA SCELTA
        ----------------------------------------------
        Prima, scelta una categoria, il filtro non si applicava piu': il
        commento diceva che «quelle voci sono gia' tutte della stessa
        natura e non sono scelte dall'utente».  E' vero per tutte tranne una:
        `VOXDramaticBibleReading` ("Brani biblici recitati") ha 10 video e 7
        audio nella stessa risposta, e la stessa lettura esiste in due forme.
        Aprendola dalla scheda Audio si vedevano anche i 10 video: la scheda
        prometteva audio e la griglia mostrava immagini in movimento.

        Il filtro e' una riga e costa niente, quindi vale sempre.  La
        categoria dice *cosa* si sta guardando, la scheda dice *in che
        forma* lo si guarda, e le due domande non sono la stessa.
        """
        scelta = self._scheda == TAB_VIDEO
        return [v for v in voci
                if self._passa(v)
                and (_e_video(v) if scelta else _e_audio(v))]

    # ------------------------------------------------------------------
    # LE CATEGORIE DEL MEDIATOR
    # ------------------------------------------------------------------

    def _costruisci_categorie(self, pagina, riga) -> None:
        """La riga delle categorie, sotto la fascia del titolo.

        IL NOME DEL SERVER, NON QUELLO SCRITTO QUI
        -------------------------------------------
        Nella tabella di `Mediator.CATEGORIE` il nome e' quello che si
        crede, e sbaglia: misurati sul server, `StudioNewsReports` si chiama
        "News e annunci" e non "Notizie dai rulli", `StudioMonthlyPrograms`
        "Programmi mensili" e non "Programmi del mese".  Due di sei erano
        sbagliati.

        Per questo la tabella tiene **solo le chiavi**, che sono la cosa
        che deve restare giusta, e il nome lo chiede il server: `_chiedi_nomi`
        lo fa in un thread e rimette dentro le linguette.  Fino ad allora si
        vede il nome della tabella, che e' una scritta provvisoria e non un
        dato: se la richiesta non va, resta quello e non si inventa niente.

        `FeaturedLibraryLanding` non c'e' nella lista perche' il server gli
        dà lo stesso nome di `FeaturedLibraryVideos` — entrambi "In primo
        piano" — e due linguette con la stessa parola non si distinguono.
        Quello e' un punto di ingresso a una pagina, non un elenco di media.
        """
        for chiave, nome, _descrizione in Mediator.CATEGORIE:
            if chiave == "FeaturedLibraryLanding":
                continue
            linguetta = _SchedaCliccabile(-1, nome, pagina)
            # PERCHE' SERVE `hide()` E NON BASTA NON METTERLA NEL LAYOUT
            # --------------------------------------------------------
            # Il commento qui sotto diceva che «un widget senza parent e senza
            # layout non viene mai creato a schermo».  Il secondo pezzo e' falso:
            # in Qt un widget figlio **senza layout** viene mostrato lo stesso,
            # all'angolo (0, 0) del padre, con la sua dimensione minima.
            #
            # Il sintomo era una scritta a caso sopra le tab — «Video in
            # evidenza» tagliata a meta' — che non si sapeva da dove venisse e
            # non andava via: cinque linguette tutte a (0, 0) una sopra l'altra,
            # e si vede solo l'ultima disegnata.  La riga qui sotto le toglie dal
            # layout, e questa le dice di non mostrarsi.
            linguetta.hide()
            linguetta.setToolTip(f"{_descrizione_categoria(chiave)}")
            linguetta.clic.connect(self._scegli_categoria)
            # La chiave sta sulla linguetta e non in una lista parallela:
            # due liste che devono stare nello stesso ordine finiscono
            # disallineate alla prima voce saltata, e il nome premuto porta
            # a una categoria diversa da quella scritta.
            linguetta._chiave = chiave
            # LE LINGUETTE NON VANNO PIU' IN ALTO
            # ------------------------------------
            # Una riga di bottoni piccoli sopra l'elenco e' la quarta cosa che
            # cambia aspetto passando da una tab all'altra: le pubblicazioni non
            # ce l'hanno, e li' la scelta si fa con le card.
            #
            # La funzione resta, pero': `_scegli_categoria` continua a
            # esistere e a chiamare `carica_categoria`, e le card qui sotto
            # chiamano esattamente quella.  Cambia **dove** si sceglie, non
            # **cosa** succede quando si sceglie — e per questo le linguette
            # non si buttano via ma smettono solo di stare nella pagina.
            #
            # Non si mettono nel layout, e il `hide()` di prima le tiene fuori
            # schermo: la scelta si fa con le card.  Restano nella lista perche'
            # `_linguette` deve continuare a tenersi quelle che ha costruite e
            # non deve diventare una lista di widget distrutti.
            self._linguette.append(linguetta)
        riga.addStretch(1)

    def _scegli_categoria(self, _indice: int) -> None:
        """Una categoria e' stata premuta."""
        # `_SchedaCliccabile` passa l'indice, che qui non serve: il `-1` e'
        # il segno che la linguetta e' una categoria e non una scheda.  Il
        # mittente si trova dal `sender()`, che e' la linguetta premuta.
        from PyQt6.QtWidgets import QApplication

        premuta = QApplication.instance() and self.sender()
        chiave = getattr(premuta, "_chiave", "")
        if not chiave:
            return
        try:
            if chiave == self._categoria:
                return
            self._categoria = chiave
            # Le due schede Audio/Video **restano**.  Le avevo nascoste
            # dicendo che sono "la scelta dentro una pubblicazione", ma
            # sono anche l'unico modo di dire "adesso voglio sentire, adesso
            # voglio guardare", e quella domanda e' vera anche per le
            # categorie.  Toglierle lasciava la sezione senza maniglia con
            # 315 righe davanti e niente che dicesse cosa stai guardando.
            #
            # Se una categoria e' tutta video, la scheda Audio mostra che
            # non ce n'e': e' la verita', detta da un comando che funziona.
            self.carica_categoria(chiave)
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nel scegliere la categoria ⚠️")
            traceback.print_exc()

    def torna_alla_pubblicazione(self) -> None:
        """Torna ai media della pubblicazione scelta."""
        self._categoria = ""

    def carica_categoria(self, chiave: str) -> None:
        """Chiede al mediator i media di una categoria.

        Non blocca, come `carica()`: 424 voci per "Discorsi" sono qualche
        secondo di risposta, e aspettarli sul main thread vuol dire una
        finestra ferma con dentro la scritta "Aggiorna".

        MENTRE ASPETTA SI VEDE
        ----------------------
        La sezione mette subito «Sto chiedendo al server...».  Prima, durante
        quei secondi, restava la lista della categoria precedente: era
        possibile guardare 79 video di una categoria e, un secondo dopo,
        vederli sparire senza capire perche'.  Ora la lista dice che sta
        chiedendo, e quando arriva il risultato dice com'e' andata.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        risultato: list = []
        fallito: list = []

        self._categoria = chiave
        self._voci = []
        self._errore = ""
        self._in_corso = chiave
        on_main(self._ricostruisci)

        def lavoro() -> None:
            try:
                risultato.extend(Mediator.voci(chiave, self._lingua))
            except Exception as errore:  # noqa: BLE001
                fallito.append(str(errore))

        background(lavoro,
                   completion=lambda: self._categoria_arrivata(chiave, risultato, fallito))

    def _categoria_arrivata(self, chiave: str, voci: list, fallito: list) -> None:
        """Le voci della categoria sono arrivate, o non sono arrivate."""
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        # La lingua e la categoria possono essere cambiate mentre si
        # aspettava: senza questo controllo la lista mostrerebbe i media di
        # una categoria con il titolo di un'altra, che e' il difetto peggiore
        # perche' sembra tutto funzionare.
        if chiave != self._categoria:
            return
        # Se la sezione e' stata distrutta non si tocca niente, e non si
        # lascia `_in_corso` acceso: la sezione successiva ricomincia pulita.
        self._in_corso = ""
        try:
            if fallito:
                # NESSUN DIALOG
                # --------------
                # Qui prima c'era `self.messaggio.emit(...)`, e la finestra
                # ne mostrava uno per ogni categoria premuta.  Tre problemi,
                # tutti veri: blocca la finestra mentre l'utente sta solo
                # sfogliando le linguette; ripete lo stesso messaggio per
                # ogni linguetta; e dice «Controlla la connessione», che e'
                # una diagnosi inventata — puo' essere la rete, puo' essere il
                # server, e il programma non lo sa.
                #
                # Ora la sezione scrive il fatto dove l'utente ha premuto, e
                # basta: `_errore` finisce in `_ricostruisci`, che e' il posto
                # dove stanno gia' tutti gli altri messaggi.
                self._in_corso = ""
                self._errore = ("Non riesco a raggiungere il server. "
                                "I media di questa categoria si vedranno "
                                "quando la connessione torna.")
                self._voci = []
                self._ricostruisci()
                return
            self._in_corso = ""
            self._errore = ""
            self._voci = list(voci)
            # Le voci sono altre, quindi gli id che erano gia' passati non
            # dicono piu' niente: senza questo, `_chiedi_antprime` troverebbe
            # un id gia' segnato (perche' il nome dell'oggetto e' riusato da
            # una voce precedente) e non chiederebbe la locandina.
            self._antprime_fatte = set()
            self._ricostruisci()
            self._chiedi_antprime()
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nel mostrare una categoria del mediator ⚠️")
            traceback.print_exc()

    def _chiedi_nomi(self) -> None:
        """Il nome vero di ogni categoria, in un thread.

        Sei richieste piccole.  Non si fanno nel costruttore perche' la
        sezione si costruisce all'avvio e non deve aspettare la rete, e non
        si fanno una per volta quando si preme una linguetta perche' il
        nome deve essere gia' scritto **prima** che l'utente prema.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        chiavi = [c for c, _n, _d in Mediator.CATEGORIE
                  if c != "FeaturedLibraryLanding"]
        trovati: list = []

        def lavoro() -> None:
            for chiave in chiavi:
                try:
                    nome = Mediator.nome_categoria(chiave, self._lingua)
                except Exception:  # noqa: BLE001 - una categoria senza nome
                    continue    # resta quello della tabella, che e' scritto
                if nome:
                    trovati.append((chiave, nome))
            # e le immagini delle categorie, cosi' la griglia le trova senza rete
            Mediator.precarica_immagini(chiavi, self._lingua)

        background(lavoro, completion=lambda: self._nomi_arrivati(trovati))

    def _nomi_arrivati(self, trovati: list) -> None:
        """I nomi sono arrivati: si mettono nelle linguette."""
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        self._nomi_categoria.update({c: n for c, n in trovati})
        # Le card vanno rilette: senza questo i nomi arriverebbero ma resterebbero
        # quelli della tabella, e la sezione direbbe «Ultimi video» dove il
        # server ha scritto altro.
        self._ricostruisci()

    # ------------------------------------------------------------------

    def _scegli_scheda(self, indice: int) -> None:
        """Una scheda e' stata premuta.

        IL TRY/CATCH QUI NON E' COSA' COMUNE
        -----------------------------------
        Questo metodo viene chiamato da un clic, quindi dentro un segnale
        Qt.  Un'eccezione li' fa ``abort()`` e non lascia nessuna riga di
        traceback: la finestra sparisce e si crede che sia un crash di Qt.

        Il motivo piu' probabile di un crash cosi' e' un errore in una
        callback, e l'unico modo per vederlo e' scriverlo qui.  Si mette
        anche perche' un crash che chiude l'app mentre l'utente sta solo
        passando da Audio a Video e' la cosa peggiore: non ha nessun
        rapporto con quello che l'utente stava facendo, e non si puo'
        ricostruire.
        """
        try:
            # DUE COSE CHE VANNO INSIEME E NON SI POSSONO DIMENTICARE
            # ---------------------------------------------------------------
            # La tab cambia e la ricerca si svuota.  Senza la seconda, dopo
            # aver cercato «Dramma» nelle voci e poi premuto «Publicazioni»
            # e tornare a «Video», la lista si riaprirebbe gia' filtrata da una
            # ricerca fatta in un'altra tab: si vedrebbero tre voci e non si
            # saprebbe perche' mancano le altre trecento.
            #
            # Il segnale di cambio testo viene bloccato perche' altrimenti la
            # ricerca che si sta svuotando si metterebbe a chiedere al server
            # una volta sola per tab premuta.
            self.cerca.blockSignals(True)
            self.cerca.clear()
            self.cerca.blockSignals(False)
            self._testo_cercato = ""
            self._numero_ricerca += 1
            self._risultati_testo.hide()
            self._scheda = indice
            on_main(self._ricostruisci)
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Media: errore nel cambiare scheda ⚠️")
            traceback.print_exc()

    def apri_una_categoria(self, chiave: str) -> None:
        """Mostra le pubblicazioni di una categoria, dentro questa tab.
        LE PUBBLICAZIONI VENGONO NELLA STESSA TAB, NON IN UN'ALTRA SCHERMATA
        -------------------------------------------------------------------
        Prima le pubblicazioni di una categoria si aprivano in una schermata
        separata (`PubView`) con l'elenco a righe strette: schermo nuovo, stile
        diverso dal resto, e la tab da cui si era partiti spariva dal quadro.

        Ora restano nella tab da cui si e' partiti e si disegnano con la stessa
        cella delle categorie, quindi con lo stesso fondo, gli stessi titoli e la
        stessa copertina quadrata a sinistra.  Cambia **cosa** e' scritto nella
        tab, non **come** e' scritto.

        IL RITORNO E' UN BOTTONE, NON LA PILA DELLA FINESTRA
        ------------------------------------------------------
        Il ritorno alle dieci categorie e' un tasto in alto a sinistra, e non la
        freccia indietro della finestra: la freccia tornerebbe a un'altra
        sezione, che non e' quello che l'utente sta facendo.  Qui si sta
        guardando dentro la stessa sezione, e dentro la sezione il ritorno e'
        fra le sue schermate.
        """
        self._categoria_aperta = chiave or ""
        # Le copertine gia' chieste sono di **quella** categoria: cambiando
        # categoria si riparte da capo, altrimenti il nuovo elenco mostrerebbe
        # solo icone perche' gli ID gia' chiesti sono di un'altra lista.
        self._copertine_chieste = set()
        self._scegli_scheda(TAB_PUBBLICAZIONI)
        self._ricostruisci()
        # Adesso si puo' tornare indietro — alle categorie — e prima no.  La
        # finestra lo deve sapere, altrimenti la freccia resta spetta perche'
        # la pila ha una schermata sola, che e' vero ma non e' l'unica cosa
        # da cui si torna indietro.
        self.frecciaCambiata.emit()

    #: La finestra ha una freccia indietro che, dentro questa sezione, torna
    #: alle categorie invece di uscire.  Va avvisata quando cambia: senza,
    #: resterebbe accesa o spenta secondo come era prima, e la freccia direbbe
    #: una cosa diversa da quello che fa.  `_c_e_qualcosa_da_chiudere` e'
    #: l'altra meta' di questa stessa cosa.
    frecciaCambiata = Signal()

    def torna_alle_categorie(self) -> None:
        """Rimette le dodici categorie al posto delle pubblicazioni.

        IL RITORNO PASSA ANCHE PER LA TAB DELLE PUBBLICAZIONI
        ------------------------------------------------------
        Le dodici categorie stanno sulla tab «Pubblicazioni».  Prima questo
        metodo svuotava solo `_categoria_aperta` e lasciava la sezione sulla tab
        che si trovava: tornarando indietro si finiva su Video o su Audio, con
        la lista dei media, e non si vedeva nessuna categoria.

        Il caso non si vedeva subito perche' quando si entra in una categoria
        la tab viene cambiata e sembra che torni indietro anche lei.  Ma il
        ritorno e' una freccia della fascia, e la freccia non tocca la tab:
        senza questa riga la freccia portava da un'altra parte.

        Il campo di ricerca si svuota per lo stesso motivo: cercando «altri
        argomenti» e tornando alle categorie, il testo resta e la griglia
        mostra i risultati della ricerca, non le dodici categorie — quindi la
        freccia «indietro» sembra non aver fatto niente.
        """
        # LE CATEGORIE DEI MEDIA SI APRONO SU UN ALTRO CAMPO
        # ---------------------------------------------------
        # `_categoria_aperta` e' quello delle dodici categorie delle
        # pubblicazioni.  Le categorie di Video e Audio stanno su `_categoria`,
        # e il metodo ne svuotava una sola: tornando indietro da «Discorsi»
        # rimaneva la categoria scelta, la tab Audio restava accesa e la griglia
        # continuava a mostrare i suoi media — la freccia sembrava premuta e non
        # era successo niente.
        #
        # Il secondo caso e' anche quello che lasciava la freccia **spenta**:
        # `SidebarView._c_e_qualcosa_da_chiudere` chiede se c'e' qualcosa da
        # chiudere guardando `_categoria_aperta`, che dentro una categoria media
        # e' vuoto.  Con la risposta "no" la fascia non chiama questo metodo e
        # va a `go_back()`, che con una schermata sola nella pila non fa niente:
        # due indizi che dicevano la stessa cosa — niente da chiudere, niente da
        # tornare — e uno solo dei due vero.
        #
        # Nota la tab: se si rientra dalle pubblicazioni si torna alla tab
        # Pubblicazioni, se si rientra da un media si resta su quella da cui si
        # e' partiti.  Saltare sempre alle pubblicazioni da dentro l'Audio
        # cambiava sezione mentre l'utente creeva di tornare indietro di una.
        era_media = bool(self._categoria)
        self._categoria_aperta = ""
        self._categoria = ""
        self._voci = []
        self._errore = ""
        self._in_corso = ""
        self._testo_cercato = ""
        self.cerca.blockSignals(True)
        self.cerca.clear()
        self.cerca.blockSignals(False)
        if not era_media:
            self._scheda = TAB_PUBBLICAZIONI
        for tab in self._tabs:
            tab.attendi(tab._indice == self._scheda)
        self._ricostruisci()
        self.frecciaCambiata.emit()

    def _scarica_una_cella(self, cosa: dict, cella=None) -> None:
        """Il tasto nuvoletta o refresh di una card: scarica o aggiorna.

        LA POSIZIONE ARRIVA DALLA CARD STESSA
        --------------------------------------
        Il secondo argomento e' la card che ha premuto.  Serve per mandare a
        valle il **punto** della sua nuvoletta: il menu' delle risoluzioni di
        un video si apre sotto il bottone premuto, e non nel mezzo della
        finestra.  Prima il punto non c'era e il menu' appariva a centro
        schermo, lontano dalla riga che l'utente stava guardando.

        PERCHE' IL SEGnale ESCE E NON SI SCARICA QUI
        ---------------------------------------------
        Il download vero e' uno solo in tutta l'applicazione, e sta in
        `PubView._scarica_pub`: scende nell'API, scrive il `.jwpub`, poi i
        testi dei capitoli.  Scaricare da qui sarebbe una seconda copia di
        quella funzione, e le due copie comincerebbero a divergere dalla prima
        modifica — tipicamente quando l'indirizzo del pacchetto cambia, che
        cambia piu' spesso di quanto sembri.

        Qui si rimanda: la sezione dice **quale** pubblicazione e chi ascolta
        scarica.  Il pulsante che ha premuto l'utente resta acceso con la sua
        barra perche' la barra la disegna `HomeView._barra_scaricamento`, che e'
        gia' dentro la cella.
        """
        # UN MEDIA: IL SEGnale E' DIVERSO
        # -------------------------------
        # Una pubblicazione si scarica chiedendo il pacchetto, e lo sa fare
        # `PubView`.  Un video e' un **file**, e chiedere un pacchetto non
        # esiste: qui si esce con `mediaScaricata` e chi ascolta chiede al
        # server le risoluzioni di quella traccia.
        voce = cosa.get("voce")
        if voce is not None:
            # Il punto della nuvoletta premuta, in coordinate di schermo.
            from PyQt6.QtCore import QPoint

            punto = None
            bottone = getattr(cella, "_scarica", None) if cella else None
            if bottone is not None:
                punto = bottone.mapToGlobal(QPoint(0, bottone.height()))
            self.mediaScaricata.emit(voce, punto)
            return

        pub = cosa.get("pub")
        if pub is not None:
            self.scaricaRichiesta.emit(pub)

    def reletti_la_griglia(self, _pub=None) -> None:
        """Un pacchetto e' stato **toltto** dal disco: la griglia va rilegta.

        PERCHE' QUI SI RICOSTRUISCE E SOPRA NO
        ---------------------------------------
        «Un pacchetto e' arrivato» cambia solo la nuvoletta di qualche card, e
        non ricostruisce niente: sono 300 widget da rifare e la posizione dello
        scorrimento dipende da dove sono.

        Una cancellazione e' un'altra cosa.  L'utente ha premuto «Elimina» e si
        aspetta che la nuvoletta **torni**: senza, sembra che il programma abbia
        cancellato e basta, e la card resta con l'aspetto di prima.

        Il perche' non bastava cambiare la nuvoletta: dopo la cancellazione la
        sezione Scaricati si rilegge, e quella rilettura ricostruisce anche
        questa griglia.  Le card nuove vengono costruite **mentre** il pacchetto
        sta sparendo, e quelle che si costruiscono in quel momento si
        ricordano che era ancora sul disco — quindi la nuvoletta resta spenta
        su una card che non c'era un secondo prima.

        Qui si ricostruisce **dopo**, quando il disco e' a posto.  E' un'azione
        rara e voluta, quindi perdere la posizione dello scorrimento non costa
        niente: si sta guardando una griglia che l'utente ha appena modificata,
        non sfogliando un elenco.
        """
        # RICOSTRUISCE E RILEGGE, INSIEME E NEL GIRO DOPO
        # -------------------------------------------------
        # Le due cose devono stare **nello stesso giro del ciclo di eventi**, e
        # una dopo l'altra.
        #
        # Prima solo `on_main(self._ricostruisci)`: rimandava la ricostruzione,
        # ma la nuvoletta veniva riletta subito, quindi sulle card **vecchie** —
        # e quelle che la ricostruzione creava dopo decidevano da sole, mentre
        # il pacchetto era ancora mezzo sul disco.
        #
        # Poi solo `_ricostruisci()` e subito `pacchettoArrivato()`, in fila:
        # la nuvoletta veniva accesa, ma **prima** che Qt avesse fatto il giro
        # di layout sulle card nuove, quindi quelle card non erano ancora
        # visibili e `show()` non poteva accendersi.  Il tasto restava spento
        # con la scritta «Scarica» sopra — cioe' mezzo fatto.
        #
        # Insieme e nel giro dopo, la ricostruzione mette le card a schermo e
        # il giro di layout le rende visibili; solo **poi** si rilegge la
        # nuvoletta, e questa volta c'e' qualcosa su cui accendersi.
        def rilettura() -> None:
            self._ricostruisci()
            self.pacchettoArrivato()

        from Utility.Extensions.Ext_DispatchQueue import on_main

        on_main(rilettura)

    def pacchettoArrivato(self) -> None:
        """Un pacchetto e' arrivato o e' stato tolto: le card vanno rilette.

        LA NUVOLETTA DEVE ANDARSENE
        --------------------------
        Ogni card chiede al disco se il pacchetto c'e' **una volta sola**, quando
        viene costruita.  Quindi dopo un download la card mostra ancora la
        nuvoletta di una nuvoletta che non serve piu': il click la riscarica, il
        menu' offersce «Elimina» per una pubblicazione che l'utente sta ancora
        aspettando di vedere comparire.

        Il sintomo e' la nuvoletta che resta dopo un download finito, e la cosa
        peggiore in un programma che scarica: sembra che il download non sia
        andato, e l'utente lo rifa.

        PERCHE' LE CARD E NON LA GRIGLIA INTERA
        ---------------------------------------
        Rileggere tutte le card significa rifare 300 widget: la nuvoletta, la
        copertina, i due tasti — tutto, per un pacchetto.  E la posizione dello
        scorrimento dipende da dove sono i widget, quindi si perde.

        Qui si cambia **solo** quello che e' cambiato: la nuvoletta sparisce o
        compare, il suggerimento segue, e null'altro si muove.  Un elemento che
        cambia da solo e' l'unico modo per cambiare qualcosa senza far saltare
        quello che c'e' intorno.
        """
        # `esiste_il_pacchetto` sta in `PubListView`, non qui: si importa
        # dentro la funzione perche' a questo livello farebbe un giro solo per
        # un nome che serve in due metodi di questo file.
        from SubViews.PubListView import esiste_il_pacchetto

        for cella in self._griglia.findChildren(_Cella):
            # Solo le card in uso: nel pool ci sono card vere, nascoste, e
            # cambiarne la nuvoletta non cambierebbe niente.
            if not cella._in_uso:
                continue
            if not cella.ha_comandi:
                continue
            pub = cella.cosa.get("pub")
            if pub is None:
                continue
            sul_disco = esiste_il_pacchetto(pub)
            if sul_disco:
                # Scaricata: la nuvoletta sparisce, e con lei il tasto di
                # aggiornamento che stava al suo posto.
                cella._scarica.setVisible(False)
                cella._scarica.setIcon(QIcon())
                cella._scarica.setToolTip("")
            elif not cella._scarica.isVisible():
                cella._scarica.setIcon(icon("cloud.download", "#ffffff", 16))
                cella._scarica.setToolTip("Scarica")
                cella._scarica.show()
            cella._scarica.raise_()

    def card_di(self, pub):
        """La card che mostra quella pubblicazione, o ``None``.

        Serve alla finestra per mettere la barra di scaricamento **sulla card
        giusta**, ed e' la stessa domanda che fa `HomeView.card_di` per i
        video.  Senza, il progresso si vede solo nella riga in fondo alla
        finestra — e quella riga parla di un pezzo fra i trecento che si
        scorrono: dice che qualcosa sta scendendo, non quale.

        LA RICERCA E' PER NUMERO, NON PER INDICE
        -----------------------------------------
        Le card si ricostruiscono a ogni cambio di categoria e a ogni ricerca, e
        un indice salvato un attimo prima punta gia' a un'altra card.  Si cerca
        quindi per quello che distingue la pubblicazione, che e' la sigla **e
        il numero**: la sigla da sola non basta, perche' «La Torre di Guardia»
        e' lo stesso pezzo in tutti i suoi numeri, e la barra che andasse sul
        numero di gennaio mentre si scarica quello di marzo sarebbe una barra
        che mente.
        """
        if pub is None:
            return None
        sigla = getattr(pub, "keySymbol", "") or ""
        numero = getattr(pub, "issueNumber", 0) or 0
        for cella in self._griglia.findChildren(_Cella):
            # Una card nel pool mostra ancora il pezzo di prima: se `card_di`
            # la trovasse, la barra del download andrebbe su una card che non
            # e' nella lista, e il progresso sparisce a meta' senza che nessuno
            # abbia toccato niente.
            if not cella._in_uso:
                continue
            if not cella.ha_comandi:
                continue
            altra = cella.cosa.get("pub")
            if altra is None:
                continue
            if (getattr(altra, "keySymbol", "") or "") != sigla:
                continue
            if (getattr(altra, "issueNumber", 0) or 0) != numero:
                continue
            return cella
        return None

    def card_di_media(self, voce: dict):
        """La card che sta mostrando **questo media**, o ``None``.

        LA STESSA DOMANDA DI `HomeView.card_di`, SU UNA COSA DIVERSA
        -------------------------------------------------------------
        `card_di` cerca una pubblicazione per (sigla, numero): qui non c'e'
        nessun numero, e la cosa da trovare e' un file — un video o un brano
        di una categoria.  Serve a `SidebarView` per accendere la **barra di
        scaricamento sulla card giusta**: senza questo il download di un video
        o di un brano non si vedeva da nessuna parte, perche' `_card_del_video`
        guardava solo la Home e la Home queste card non le ha.  Le
        pubblicazioni la avevano, i media no, e l'utente premeva «Scarica» e
        non capiva se stava arrivando qualcosa.

        SIGLA, LINGUA, TRACCE E GENERE
        -------------------------------
        La sigla da sola non basta: «Adorazione mattutina» ha decine di video
        con la stessa sigla, e una barra sul numero sbagliato direbbe che sta
        scendendo un altro pezzo.  Il **genere** serve per la categoria mista:
        «Brani biblici recitati» sta sia in Video sia in Audio, e la stessa
        traccia c'e' due volte, una per scheda.  Il genere si legge con
        `_e_video`, perche' non tutte le voci hanno `formato`: quelle raggruppate
        dalla Home non ce l'hanno.

        SOLO LE CARD IN USO
        --------------------
        La griglia tiene un pool di card riusate: una card in attesa mostra
        ancora il pezzo di prima, e trovarla significherebbe accendere una
        barra su una card che non e' nella lista.
        """
        if not isinstance(voce, dict):
            return None
        sigla = str(voce.get("sigla") or "")
        if not sigla:
            return None
        lingua = str(voce.get("lingua") or "I")
        tracce = _tracce_di(voce)
        video = _e_video(voce)
        for cella in self._griglia.findChildren(_Cella):
            if not cella._in_uso:
                continue
            altra = cella.cosa.get("voce")
            if not isinstance(altra, dict):
                continue
            if str(altra.get("sigla") or "") != sigla:
                continue
            if str(altra.get("lingua") or "I") != lingua:
                continue
            if _tracce_di(altra) != tracce:
                continue
            if _e_video(altra) != video:
                continue
            return cella
        return None

    def _menu_una_cella(self, cosa: dict, posizione) -> None:
        """Il «...» di una card: le voci che ci sono in un menu' di pubblicazione.

        LE STESSE VOCI DELLA HOME E DELLA SEZIONE SCARICATI
        ---------------------------------------------------
        «Metti fra i Preferiti» e «Togli il pacchetto» sono le stesse voci che
        si trovano premendo «...» sulla card della Home e sulla riga degli
        Scaricati, e sono le stesse perche' fanno le stesse cose: mettere fra
        i Preferiti non cambia in base a dove la pubblicazione e' stata aperta,
        e neppure toglierla dal disco.

        Una voce che cambia da una sezione all'altra e' la cosa peggiore che
        possa succedere a un menu': l'utente preme «Togli il pacchetto» dove lo
        aveva fatto due volte prima e non succede niente, e non sa se il
        programma e' rotto o se ha sbagliato sezione.

        LE DUE AZIONI DIPENDONO L'UNA DALL'ALTRA
        -----------------------------------------
        «Togli dai Preferiti» c'e' solo se la pubblicazione c'e' gia' fra i
        Preferiti, «Metti fra i Preferiti» solo se non c'e'.  Mostrare entrambe
        vuol dire che una delle due non fa niente, e una voce che non fa niente
        in un menu' e' rumore che fa perdere tempo a leggerlo.

        Il Preferito si puo' mettere anche di una pubblicazione **non**
        scaricata: e' una nota sul cosa voglio, non il cosa ho.  «Apri» e
        «Togli il pacchetto» invece ci sono solo se il pacchetto c'e'.
        """
        if cosa.get("traduzione"):
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)
            elimina = menu.addAction("Elimina")
            elimina.triggered.connect(
                lambda: self._chiedi_elimina_bibbia(cosa["traduzione"]))
            menu.exec(posizione)
            return

        from PyQt6.QtGui import QCursor, QDesktopServices
        from PyQt6.QtWidgets import QMenu

        # `esiste_il_pacchetto` e' una funzione del modulo,
        # `delete_pub` e' un metodo statico di `PubListView`: due cose diverse
        # che stanno nello stesso file, e importarle entrambe come funzioni fa
        # fallire l'import **prima** di costruire il menu' — quindi l'utente
        # preme «...» e non vede niente, senza alcun errore a schermo.
        from SubViews.PubListView import PubListView, esiste_il_pacchetto
        from Utility import Condivisione, Preferiti

        # UN MEDIA HA UN MENU' DIVERSO, E NON PERCHE' SIA PIU' POVERO
        # ----------------------------------------------------------
        # Non c'e' nessun pacchetto da togliere e nessuna pubblicazione da
        # mettere fra i Preferiti: un video e' un file, e quello che si puo'
        # fare con un file e' scaricarlo, condividerlo e cancellarlo.
        #
        # E' un menu' diverso **perche' la cosa e' diversa**, non perche' si
        # sia scritto in fretta: metterci dentro «Metti nei Preferiti» per
        # uguagliare le pubblicazioni metterebbe una voce che non sa cosa
        # fare, e una voce che non sa cosa fare e' rumore.
        voce = cosa.get("voce")
        if voce is not None:
            # `posizione` arriva **gia' in coordinate globali** dalla cella che
            # ha premuto (vedi `_Cella._menu`): non si mappa di nuovo.
            self._menu_di_un_media(voce, _a_punto(posizione))
            return

        pub = cosa.get("pub")
        if pub is None:
            return

        sigla = getattr(pub, "keySymbol", "") or ""
        lingua = Preferiti._lingua(pub)
        sul_disco = bool(esiste_il_pacchetto(pub))
        cartella = Copertine.pacchetto_locale(pub) if sul_disco else None

        menu = QMenu(self)

        # LE VOCI, IN PIANO, NELL'ORDINE IN CUI SI CERCANO
        # -------------------------------------------------
        # Nessun sottomenu': un sottomenu' si apre passandoci sopra, e serve
        # un secondo gesto.  Il menu' di una card si apre con un click e si
        # sceglie con un altro: se anche la terza voce chiede di passarci
        # sopra, condividere costa tre gesti.

        # 1. METTI NEI PREFERITI — PRIMA VOCE
        # ----------------------------------
        # Il Preferito si puo' mettere anche di una pubblicazione non
        # scaricata: e' una nota sul cosa voglio, non il cosa ho.  Se e' gia'
        # fra i Preferiti la voce cambia e dice «Togli», perche' una voce che
        # dice «Metti» e poi toglie e' una voce che mente.
        if Preferiti.c_e_(sigla, lingua):
            azione = menu.addAction("Togli dai Preferiti")
            azione.triggered.connect(
                lambda: self._togli_preferito(sigla, lingua))
        else:
            azione = menu.addAction("Metti nei Preferiti")
            azione.triggered.connect(lambda: self._metti_preferito(pub))

        # 2. LA LISTA DEI PREFERITI
        # ------------------------
        # Voce a parte, e non la stessa di prima: una **aggiunge** un pezzo,
        # questa **apre** la lista.  La lista e' nella Home, quindi qui si
        # dice solo «ci voglio andare» e la finestra fa il resto.
        apri_preferiti = menu.addAction("Preferiti")
        apri_preferiti.triggered.connect(
            lambda: self.vaiAllaSezione.emit("Home"))

        menu.addSeparator()

        # 3. CONDIVIDI LINK
        # -----------------
        # Va sempre bene, scaricata o no: il link e' di chiunque, e serve
        # proprio a chi non ha ancora la pubblicazione.
        voce_url = menu.addAction("Condividi link")
        url = Condivisione.url_pubblicazione(cartella, sigla) if cartella else None
        voce_url.setEnabled(bool(url))
        if url:
            def _url():
                from PyQt6.QtCore import QUrl
                if QDesktopServices.openUrl(QUrl(url)):
                    self.messaggio.emit(f"Aperto nel sito: {url}")
                else:
                    # Il browser c'e' ma non parte: si mette l'indirizzo sulla
                    # lavagnetta, che e' l'unica cosa che si puo' fare.
                    from PyQt6.QtWidgets import QApplication
                    appoggio = QApplication.instance()
                    if appoggio is not None:
                        appoggio.clipboard().setText(url)
                    self.messaggio.emit(f"Copiato l'indirizzo: {url}")

            voce_url.triggered.connect(_url)

        # 4. CONDIVIDI FILE
        # -----------------
        # Mette sulla lavagnetta la cartella del pacchetto, quindi ha senso
        # solo se il pacchetto c'e'.
        #
        # **NON SPARE, E TI DICE PERCHE'** — e' la scelta che conta qui.  Una
        # voce grigia si puo' leggere come «rotta» e una voce assente non si
        # vede neppure: in entrambi i casi l'utente non impara che il motivo e'
        # che non l'ha scaricata.  Premendola, il messaggio spiega e finisce
        # li': si sa cosa fare, e senza perdere il menu' di sotto.
        voce_file = menu.addAction("Condividi file")
        if cartella:
            def _file():
                fatto, testo = Condivisione.condividi_file(cartella, self)
                self.messaggio.emit(testo)

            voce_file.triggered.connect(_file)
        else:
            def _file_mancante():
                nome = getattr(pub, "displayTitle", "") or sigla
                self.messaggio.emit(
                    f"«{nome}» non e' ancora sul disco: scaricalo e poi "
                    "il pacchetto si puo' condividere.")
                self.scaricaRichiesta.emit(pub)

            voce_file.triggered.connect(_file_mancante)

        menu.addSeparator()

        # 5. SCARICA, O ELIMINA
        # ---------------------
        # DUE VOCI AL massimo, E NON DI PIU'
        # --------------------------------
        # «Apri» e «Scarica di nuovo» sono state tolte: sono cio' che fa
        # gia' il resto della card.  Il click sulla card apre il pacchetto se
        # c'e', e la nuvoletta lo scarica: due tasti che ripetono quello che
        # si fa premendo la card sono rumore in un menu' che ha quattro voci.
        #
        # «Scarica di nuovo» era la peggiore: il pacchetto **e' gia' sul disco**,
        # quindi non scarica niente — riscrive quello che c'e'.  E un bottone
        # che dice «scarica» mentre non scarica e' peggio di un bottone che non
        # c'e'.
        #
        # «Elimina» al posto di «Togli il pacchetto»: e' la stessa azione —
        # `_togli_pacchetto`, che chiama `PubListView.delete_pub` — ma il nome
        # dice quello che succede.  «Togli» sembra levare dal posto, «Elimina»
        # dice che sparisce.
        if esiste_il_pacchetto(pub):
            elimina = menu.addAction("Elimina")
            elimina.triggered.connect(lambda: self._togli_pacchetto(pub))
        else:
            # Non scaricata non c'e' niente da eliminare, e la voce non c'e'.
            # «Elimina» qui sarebbe un tasto che cancella il vuoto: premuto
            # sembra aver fatto qualcosa e non ha fatto niente.
            scarica = menu.addAction("Scarica")
            scarica.triggered.connect(
                lambda: self.scaricaRichiesta.emit(pub))

        # Anche qui il punto arriva gia' globale dalla cella che ha premuto.
        menu.exec(_a_punto(posizione))

    def _menu_di_un_media(self, voce: dict, dove) -> None:
        """Il «...» di una card di video o audio: scarica, condividi, elimina.

        LE STESSE QUATTRO VOCI DEGLI SCARICATI
        --------------------------------------
        Sono le stesse della sezione Scaricati e della Home, e con lo stesso
        ordine, perche' fanno le stesse cose e su una cosa sola: un video e un
        file, e con un file si puo' condividere il collegamento, condividere il
        file, scaricarlo e toglierlo.

        «Condividi file» **non sparisce** quando il file non c'e': premendola
        dice il motivo e scarica.  Una voce grigia si legge come «rotta» e una
        voce assente non si vede neppure.
        """
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtWidgets import QMenu

        from Utility import Condivisione, Lingua

        menu = QMenu(self)
        file_sul_disco = _media_sul_disco(voce)
        sigla = voce.get("sigla", "")
        lingua = voce.get("lingua") or Lingua.corrente_simbolo()

        voce_url = menu.addAction("Condividi link")
        # `url_traccia` e' gia' scritta per le voci dei media: rimanda a None
        # quando non c'e' un `DocumentId`, e un indirizzo che porta alla pagina
        # sbagliata e' peggio di un indirizzo che non c'e' — l'utente lo apre e
        # vede che non e' la cosa che pensava.
        url = Condivisione.url_traccia(voce, sigla)
        voce_url.setEnabled(bool(url))
        if url:
            def _url():
                from PyQt6.QtCore import QUrl

                if QDesktopServices.openUrl(QUrl(url)):
                    self.messaggio.emit(f"Aperto nel sito: {url}")
                else:
                    from PyQt6.QtWidgets import QApplication

                    appoggio = QApplication.instance()
                    if appoggio is not None:
                        appoggio.clipboard().setText(url)
                    self.messaggio.emit(f"Copiato l'indirizzo: {url}")

            voce_url.triggered.connect(_url)

        voce_file = menu.addAction("Condividi file")
        if file_sul_disco is not None:
            def _file():
                fatto, testo = Condivisione.condividi_file(file_sul_disco,
                                                            self)
                self.messaggio.emit(testo)

            voce_file.triggered.connect(_file)
        else:
            def _file_mancante():
                self.messaggio.emit(
                    "Il file non e' ancora sul disco: scaricalo e poi "
                    "lo puoi condividere.")
                self.mediaScaricata.emit(voce, dove)

            voce_file.triggered.connect(_file_mancante)

        menu.addSeparator()
        if file_sul_disco is not None:
            scarica = menu.addAction("Scarica di nuovo")
            scarica.triggered.connect(
                lambda: self.mediaScaricata.emit(voce, dove))

            elimina = menu.addAction("Elimina")
            elimina.triggered.connect(
                lambda: self._elimina_un_media(voce))
        else:
            scarica = menu.addAction("Scarica")
            scarica.triggered.connect(
                lambda: self.mediaScaricata.emit(voce, dove))

        menu.exec(dove)

    def _elimina_un_media(self, voce: dict) -> None:
        """Togli il file di quella traccia dal disco.

        Non sono tre righe perche' e' una cosa sola: il file che c'e' e' il
        piu' grande fra le risoluzioni, e `MediaScaricati` sa dirlo.  Si chiama
        quella funzione e non se ne scrive un'altra, perche' il nome del file ha
        dentro la traccia a due cifre e senza quella il `glob` non trova niente
        — e un tasto che dice «Elimina» e non elimina niente e' la cosa peggiore
        che ci sia.
        """
        from Utility import MediaScaricati

        percorso = _media_sul_disco(voce)
        if percorso is None:
            return
        try:
            percorso.unlink()
        except OSError as errore:
            self.messaggio.emit(f"Non riesco a togliere il file ⚠️  {errore}")
            return
        self.messaggio.emit("File tolto dal disco")
        self._ricostruisci()

    def _metti_preferito(self, pub) -> None:
        """Mette una pubblicazione fra i Preferiti e avvisa la Home.

        Il segnale parte anche se non e' cambiato niente: costa rileggere un
        file di poche righe, mentre una stella che non compare quando doveva e'
        il difetto che l'utente nota subito.
        """
        from Utility import Preferiti

        if Preferiti.aggiungi(pub):
            self.messaggio.emit(f"«{pub.title or pub.keySymbol}» fra i Preferiti")
        else:
            self.messaggio.emit("C'era gia' fra i Preferiti")
        self.preferitiCambiati.emit()

    def _togli_preferito(self, sigla: str, lingua: str) -> None:
        from Utility import Preferiti

        Preferiti.togli(sigla, lingua)
        self.messaggio.emit("Tolta dai Preferiti")
        self.preferitiCambiati.emit()

    def _togli_pacchetto(self, pub) -> None:
        """Elimina il pacchetto e i testi HTML che aveva fatto scaricare.

        NON SI RISCrive LA CANCELLAZIONE
        ---------------------------------
        Il lavoro vero e' gia' scritto e **provato** in `PubListView.delete_pub`,
        e porta con se' una cosa che si dimentica sempre: i file HTML dei
        capitoli vanno tolti insieme al pacchetto.  Se restano, riaprendo la
        pubblicazione si vede il testo scaricato e sembra che il pacchetto ci
        sia ancora — cioe' un programma che ha cancellato e non ha cancellato.

        Qui si chiama quella funzione e non se ne scrive un'altra: due copie
        comincerebbero a divergere dalla prima modifica, ed e' esattamente la
        prima modifica che dimenticherebbe gli HTML.

        Dopo la cancellazione la griglia va riletta e la sezione Scaricati
        anche: entrambe guardano il disco, e senza rileggerle mostrerebbero
        ancora un pacchetto che non c'e' piu'.  Per questo il segnale esce
        invece di ridisegnare qui.
        """
        from SubViews.PubListView import PubListView

        PubListView.delete_pub(pub)
        self.pacchettoRimossa.emit(pub)

    def cerca_e_vai(self) -> None:
        """Mette il cursore nella ricerca, sulle voci di tutte e quattro le tab.

        Serve al tasto della lente nella fascia.  Nella versione con due sezioni
        la lente andava su «Pubblicazioni» e il campo che c'era li' accendeva
        il filtro.  Adesso che il catalogo e' una tab, il campo e' uno solo per
        tutte e quattro e basta accenderlo: cerca dove si cerca, e non in un
        posto che l'utente non ha scelto.

        Se la tab corrente non ha un campo da cercare (le due che non hanno
        una lista), si va sulle Pubblicazioni, che ce l'ha.
        """
        if not self.cerca.isVisible():
            self._scegli_scheda(TAB_PUBBLICAZIONI)
        self.cerca.setFocus()
        self.cerca.selectAll()

    # ------------------------------------------------------------------
    # LE QUATTRO TAB: COSA SI VEDE E COSA NO
    # ------------------------------------------------------------------
    #
    # PERCHE' UN METODO E NON TRE `setVisible` sparsi per `_ricostruisci`
    # ---------------------------------------------------------------
    # Le quattro tab non cambiano una cosa, ne cambiano tre: il campo di
    # ricerca, le categorie del mediator e la lista.  Sparse in tre posti
    # diversi, la prima tab che non nasconde una delle tre mostra due pezzi
    # insieme: un campo di ricerca sopra una griglia di categorie che non si
    # cerca, e una lista di 424 righe sotto una tab che non le contiene.
    #
    # Qui si dice tutto una volta sola, e `_ricostruisci` chiama questo e poi
    # esce.  Il nome e' `_visibilita` e non `_nascondi`: il metodo mostra
    # anche, e chiamarlo "nascondi" racconterebbe solo meta' di quello che fa.

    def _visibilita(self) -> None:
        """Mostra o nasconde i pezzi secondo la tab scelta."""
        # LA RICERCA E' ACCESA SU TRE TAB, E SU TRE PERCHE' SONO TRE LE LISTE
        # ---------------------------------------------------------------
        # Audio e Video hanno una lista di voci da cercare.  La tab delle
        # pubblicazioni l'aveva spenta perche' mostrava dieci categorie e non
        # c'era niente da cercare: ma adesso che la stessa tab mostra anche le
        # pubblicazioni di una categoria, e sono fino a 2.787, il campo e' il
        # modo per arrivare a quelle che non stanno nelle prime 300 card.
        #
        # Senza, la tab direbbe che «La Torre di Guardia» ha 2.787 numeri e ne
        # mostrerebbe 300: sembrerebbe che il catalogo sia sbagliato, non che la
        # lista sia lunga.  Un numero che mente e' peggio di nessun numero.
        con_ricerca = (self._scheda in (TAB_AUDIO, TAB_VIDEO)
                       or self._scheda == TAB_PUBBLICAZIONI)
        con_lista = self._scheda in (TAB_AUDIO, TAB_VIDEO)
        self._contenitore_cerca.setVisible(con_ricerca)
        # Le linguette non vanno piu' in alto: la scelta si fa con le card.
        # Il contenitore resta, vuoto e nascosto, perche' `_linguette` continua
        # a tenersi quelle che ha costruite e non deve diventare una lista di
        # widget distrutti.
        self._contenitore_categorie.setVisible(False)
        # I DUE TASTI «AUDIO» E «VIDEO» NON CI SONO PIU'
        # ------------------------------------------------
        # Sono la stessa scelta che fanno gia' le tab in alto: «VIDEO» e
        # «AUDIO» sono tab, e qui sotto c'erano due bottoni che facevano
        # esattamente lo stesso.  Due maniglie per una domanda sola sono una
        # contraddizione: se sono d'accordo e' una ripetizione, se non lo sono
        # non si sa quale vale.
        #
        # Tolti i tasti, resta la tabella che li teneva — i due tab della sezione
        # non sono quelli, sono le quattro in alto — quindi qui basta spegnere
        # il contenitore e la funzione resta sulle tab, che sono l'unico posto
        # in cui si sceglie.
        self._contenitore_schede.setVisible(False)
        # LA GRIGLLA E' L'UNICO ELENCO, SU TUTTE LE TAB
        # ---------------------------------------------------
        # Qui c'era `setVisible(not con_lista)`: su Audio e Video la griglia
        # veniva nascosta e restava la colonna di righe strette.  Adesso anche
        # Audio e Video sono griglia — sono le stesse card delle pubblicazioni —
        # quindi l'elenco vecchio non si usa piu' e la griglia e' sempre
        # quella che si vede.
        #
        # Il sintomo era una sezione vuota con il contatore pieno: «15 media»
        # accanto al campo e niente sotto, perche' le card erano state create
        # dentro un contenitore nascosto.  Due indizi che non puntano nella
        # stessa direzione, e il secondo e' quello che fa credere che il
        # caricamento sia fallito.
        self._contenitore_lista.setVisible(False)
        self._contenitore_griglia.setVisible(True)

        # IL CAMPO DICE DOVE STA CERCANDO
        # -------------------------------
        # «Cerca fra i media» sopra le pubblicazioni e' una frase falsa: li'
        # non ci sono media, ci sono pubblicazioni, e l'utente non cerca un
        # video quando preme il tasto per ritrovare un annuario.
        #
        # Il testo cambia con la tab e non al momento della ricerca: se
        # cambiasse mentre si scrive, il placeholder che descriveva il campo
        # sparisce sotto le dita e non si sa piu' che cosa si sta cercando.
        if self._scheda == TAB_PUBBLICAZIONI:
            self.cerca.setPlaceholderText("Cerca fra le pubblicazioni e nel testo")
        else:
            self.cerca.setPlaceholderText("Cerca fra i media")
        # IL FONDO DELLA PAGINA DIPENDE DALLA TAB
        # ---------------------------------------
        # Nelle due tab con la griglia il fondo della pagina e' quello fra le
        # celle, e senza questo le celle bianche su bianco non si vedono: il
        # vuoto di 4 pixel fra una cella e l'altra diventa invisibile e la
        # griglia sembra un unico rettangolo grande.
        #
        # Nelle due tab con la lista il fondo resta quello di prima.  Non per
        #che' sia sbagliato metterci quello grigio anche li' — l'app originale
        # ce l'ha — ma perche' quelle due schermate funzionano cosi' da prima e
        # cambiarne il fondo insieme alla griglia e' cambiare due cose quando
        # se ne voleva una.  Se un domani anche li' si vuole il fondo grigio,
        # si toglie questa riga e la griglia smette di essere un caso
        # speciale.
        if con_lista:
            self._pagina.setObjectName("")
        else:
            tema.sfondo(self._pagina, "paginaGriglia")
        for tab in self._tabs:
            tab.attendi(tab._indice == self._scheda)
        # Il campo di ricerca non ha niente da dire in una tab che non ha
        # lista: lasciare il numero di una ricerca che non esiste sarebbe un
        # numero bugiardo.  Nella tab delle pubblicazioni invece il numero c'e' e
        # dice quante pubblicazioni ci sono e quante se ne vedono — che e'
        # l'unico posto dove si capisce che le 300 card sono un limite di
        # schermo e non di catalogo.
        if self._scheda == TAB_PUBBLICAZIONI:
            pass    # il conteggio lo scrive `_celle_del_catalogo`
        elif not con_lista:
            self.conteggio.setText("")

    # ------------------------------------------------------------------
    # LA GRIGLIA: LE CELLE CHE NON SONO MEDIA
    # ------------------------------------------------------------------
    #
    # DUE TAB DIVERSE E UN METODO
    # ---------------------------
    # «Publicazioni» e «Scaricati» non hanno niente in comune: una chiede al
    # server le dodici categorie, l'altra guarda sul disco che cosa c'e'.  Ma
    # si disegnano allo stesso modo e per questo stanno nello stesso metodo,
    # con un `if` dentro.  Un metodo per tab avrebbe finito per essere lo
    # stesso metodo due volte, e le due copie avrebbero cominciato a
    # divergere dalla terza modifica.

    def _riempi_griglia(self) -> None:
        """Mette le celle della tab corrente dentro la griglia.

        TRE FORME, E IL TERMINE E' UNO SOLO
        -------------------------------------
        Nella tab delle pubblicazioni si puo' vedere una delle due cose, e
        basta scegliere quale:

            le dieci categorie   quando nessuna e' stata aperta
            le pubblicazioni     quando l'utente ne ha aperta una

        Il termine e' `_categoria_aperta`: se e' vuota si vedono le categorie,
        se no le pubblicazioni di quella categoria.  Non serve nessun altro
        stato — e il ritorno e' scrivere la stringa vuota, che e' anche l'unico
        modo per tornare alle categorie.

        Tutte e tre le liste passano dalla stessa griglia e dalla stessa classe
        `_Cella`: e' il motivo per cui le pubblicazioni del catalogo e gli
        scaricati si vedono uguali, e per cui l'utente non deve imparare un
        aspetto nuovo ogni volta che cambia di scheda.
        """
        self._griglia.svuota()
        # LA BARRA VERTICALE: SOLO DOVE SERVE
        # ------------------------------------
        # Quando si vedono le **categorie** (la pagina principale, prima di
        # aprire una lista) la griglia e' corta e la barra sarebbe solo
        # rumore: si nasconde.  Quando si apre una categoria o si cerca,
        # la lista puo' essere lunga e la barra torna (AsNeeded).
        # Il tema la fa 2 mm piu' spessa (11 px) perche' la maniglia da 3 px
        # era troppo sottile da afferrare.
        area = getattr(self, "_area_griglia", None)
        if area is not None:
            self._aggiorna_barra_scroll_adattiva(area)

        if self._scheda in (TAB_VIDEO, TAB_AUDIO):
            # VIDEO E AUDIO: LE STESSE CARD DELLE PUBBLICAZIONI
            # ------------------------------------------------------
            # Prima erano righe strette in `self._colonna`, disegnate a mano e
            # mosse da `_ricostruisci`.  Passando dalle pubblicazioni a Video
            # l'aspetto cambiava tutto: due modi di mostrare la stessa cosa
            # nella stessa sezione.
            #
            # Qui prendono le card come le pubblicazioni, e `_colonna` non
            # viene neanche toccata: resta per il lettore, che e' un'altra
            # cosa e ha bisogno della sua colonna.
            # SENZA CATEGORIA LE CARD SONO LE CATEGORIE
            # -------------------------------------------
            # Come nelle pubblicazioni: prima di scegliere cosa guardare si vede
            # **cosa c'e' da scegliere**.  Con una categoria scelta le card sono
            # i media di quella, e con un testo scritto sono i risultati della
            # ricerca.
            #
            # Il termine e' `self._categoria`: se e' vuota non si e' entrati
            # in nessuna lista, e mostrare una lista vuota sarebbe una schermata
            # senza niente e senza dire perche'.
            if self._testo_cercato:
                celle = self._celle_dei_media()
            elif self._categoria:
                celle = self._celle_dei_media()
            else:
                celle = self._celle_delle_categorie_media()
                self.conteggio.setText(
                    f"{len(celle)} categorie")
        elif self._scheda == TAB_PUBBLICAZIONI:
            # TRE CASI, E L'ORDINE E' QUELLO CHE CONTA
            # -------------------------------------------
            #   dentro una categoria   le pubblicazioni di quella
            #   pagina principale      le dodici categorie
            #   pagina principale con testo scritto   tutta la Biblioteca
            #
            # Il terzo viene **per ultimo** perche' e' l'unico in cui si
            # rinuncia a mostrare le dodici categorie.  Senza di lui il campo
            # di ricerca non faceva niente sulla pagina principale: si scriveva
            # un titolo, la griglia non cambiava, e il contatore accanto al
            # campo restava vuoto — che e' indistinguibile da «non c'e' nessun
            # pezzo con questo titolo».
            #
            # La ricerca viene **prima** delle categori e non dentro di loro:
            # dentro una categoria il campo continua a limitare a quella, che e'
            # quello che l'utente si aspetta avendo premuto la categoria.
            if self._categoria_aperta:
                celle = self._celle_del_catalogo(self._categoria_aperta)
            elif self._testo_cercato:
                celle = self._celle_della_ricerca()
            else:
                celle = self._celle_pubblicazioni()
        else:
            celle = self._celle_scaricati()

        # UNA GRIGLIA VUOTA DEVE DIRE PERCHE' E' VUOTA
        # -----------------------------------------------
        # Il sintomo era una sezione interamente spoglia con dentro solo il
        # contatore: su Audio e Video, aprendo una categoria senza media (o una
        # categoria la cui richiesta e' fallita) la griglia restava vuota e
        # non diceva niente.
        #
        # Il motivo e' che la spiegazione la scriveva `_messaggio`, che pero'
        # mette l'etichetta dentro `self._colonna` — e quella colone e' la vecchia
        # lista a righe strette, `_contenitore_lista`, che `_visibilita()` tiene
        # **nascosta** su tutte e quattro le tab.  La frase c'era, ma in un
        # contenitore invisibile: due indizi che non puntavano nella stessa
        # direzione, il primo dei quali diceva «non c'e' niente» e il secondo
        # «c'e' roba» (il contatore), quindi nessuno dei due era giusto.
        #
        # Qui la scritta va nella griglia, che e' quello che l'utente sta
        # guardando.  Il testo distingue i tre vuoti come distingue gia'
        # `_ricostruisci`: senza dire quale sia, l'utente non sa se ha
        # sbagliato a cercare.
        if not celle:
            self._griglia.aggiungi(self._vuoto_nella_griglia())

        def _collega(cella) -> None:
            cella.scelto.connect(self._cella_premuta)
            # La card passa **se stessa** oltre alla cosa da scaricare: il
            # menu' delle risoluzioni le serve il punto della sua nuvoletta.
            cella.scaricaChiesta.connect(
                lambda cosa, _c=cella: self._scarica_una_cella(cosa, _c))
            cella.menuChiesto.connect(self._menu_una_cella)

        for cosa, modo in celle:
            # Non `self._griglia.aggiungi(_Cella(...))`: il pezzo unico e' il
            # riuso, e sta dentro `cella_per`.  Qui si dice solo **che** cella
            # serve, e chi decide se e' nuova o riusata e' la griglia, che e'
            # l'unica che sa cosa sta tenendo in attesa.
            self._griglia.cella_per(cosa, modo, _collega)

        # LE COPERTINE SI CHIEDONO **DOPO** CHE LE CELLE SONO NELLA GRIGLIA
        # ---------------------------------------------------------------
        # `_chiedi_copertine` deve mettere ogni copertina sulla card giusta, e
        # per farlo deve vedere le card: quindi va chiamata da qui, non da
        # `_celle_del_catalogo`.
        #
        # Prima la si chiamava da li', e non trovava nessuna card perche' a quel
        # momento la griglia era stata svuotata e le celle non erano ancora
        # state create.  Non dava nessun errore — la funzione guardava, non
        # trovava niente e usciva — e l'unico sintomo era che le copertine non
        # arrivavano mai.  Il difetto peggiore: quando la condizione per
        # lavorare non si verifica, il codice che la verifica e' quello che
        # smette di funzionare, e non si accorge.
        # Prima qui la chiamata era dentro `if not self._copertine_in_corso and
        # self._copertine_da_chiedere:`, cioe' con un filtro **fuori**.  E il
        # filtro escludeva le card delle **categorie**, perche' quelle non
        # lasciano niente in `_copertine_da_chiedere` (quella lista e' di
        # pubblicazioni e di voci di media, non di scelte).  Quindi in Audio e
        # in Video, finche' non si entrava in una categoria, la richiesta non
        # partiva **mai**.
        #
        # Il sintomo era una card di categoria con il glifo per sempre, anche
        # per «Melodie del Regno», che e' l'unica che ha un'immagine.  E non e'
        # un difetto che si vede: il glifo e' un segnaposto che sembra voluto.
        #
        # Il filtro adesso sta **dentro** `_chiedi_altre_copertine`, che sa
        # cosa fare per ogni scheda e cosa non fare: due filtri per la stessa
        # condizione sono due posti che possono dire cose diverse.
        self._chiedi_altre_copertine()
        self._griglia.updateGeometry()
        # Dopo aver riempito la griglia, il layout ha una geometria valida:
        # qui si misura se il contenuto fuoriesce dal viewport.
        self._aggiorna_barra_scroll_adattiva()

    def _aggiorna_barra_scroll_adattiva(self, area=None) -> None:
        """Abilita la barra e lo scorrimento solo se il contenuto fuoriesce.

        MISURA REALE, NON CONDIZIONI FISE
        ---------------------------------
        Qui non si indovina in base a `_categoria` o `_testo_cercato`: si
        misura l'altezza del contenuto (`_griglia.heightForWidth`) e la si
        confronta con l'altezza del **viewport** dello scroll area.  Se il
        contenuto e' piu' alto del viewport (anche di un solo pixel), la barra
        si accende e lo scorrimento col mouse funziona.  Se sta dentro, la
        barra sparisce e lo scorrimento col mouse e' bloccato.

        Viene chiamato:
            - a ogni `_riempi_griglia` (contenuto cambiato)
            - nel `resizeEvent` (finestra ridimensionata)
        """
        if area is None:
            area = getattr(self, "_area_griglia", None)
        if area is None:
            return

        viewport = area.viewport()
        if viewport is None:
            return

        # Altezza del viewport (area visibile)
        h_viewport = viewport.height()
        if h_viewport <= 0:
            return

        # Altezza necessaria dal layout della griglia a questa larghezza
        larghezza_utile = viewport.width()
        if larghezza_utile <= 0:
            return

        h_contenuto = self._griglia.heightForWidth(larghezza_utile)

        barra = area.verticalScrollBar()
        serve = h_contenuto > h_viewport

        area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if serve
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        barra.setEnabled(serve)

        # Se lo scrolling non serve piu', riporta la vista in cima.
        # Altrimenti resterebbe scorruta come la lista precedente
        # (es. pubblicazioni) e le categorie sarebbero tagliate.
        if not serve:
            barra.setValue(0)

    def resizeEvent(self, evento) -> None:
        """Rimisura la barra quando la finestra cambia dimensione."""
        super().resizeEvent(evento)
        # Un resize cambia l'altezza del viewport: si rivaluta se serve scroll.
        # Un timer a 0 evita di farlo troppe volte durante un trascinamento.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._aggiorna_barra_scroll_adattiva)

    def _vuoto_nella_griglia(self) -> QLabel:
        """La scritta che spiega una griglia senza card.

        Figlia della **griglia**, non della colonna: la colonna e' la vecchia
        lista a righe strette e `_visibilita()` la tiene nascosta su tutte e
        quattro le tab, quindi una scritta messa li' non si vede mai — ed e'
        esattamente il posto dove finiva prima questa frase.
        """
        etichetta = QLabel(self._testo_vuoto(), self._griglia)
        etichetta.setObjectName("vuoto")
        etichetta.setWordWrap(True)
        return etichetta

    def _testo_vuoto(self) -> str:
        """Quale dei vuoti e' questo.

        L'ordine e' quello di `_ricostruisci`, che distingue gia' i casi: prima
        l'errore, perche' un guasto non e' un elenco vuoto e dirgli «non c'e'
        niente» nasconde l'unica cosa che l'utente puo' fare (riprovare o
        aspettare la connessione); poi la ricerca, perche' con un testo scritto
        e' l'utente che ha scelto il vuoto; poi la categoria.
        """
        if self._errore:
            return self._errore
        if self._testo_cercato:
            return f"Niente per \u00ab{self.cerca.text().strip()}\u00bb."
        if self._categoria_aperta:
            return "Nessuna pubblicazione in questa categoria."
        if self._categoria:
            # Il nome viene dalla stessa fonte delle card, non da
            # `_nome_categoria`: quella legge `CATEGORIE_PUB`, che sono le dieci
            # categorie delle pubblicazioni, e per una chiave del mediator
            # restituirebbe la stringa vuota — la frase diventerebbe
            # «\u00bb non ha media» con le virgolette sole.  Le due liste si
            # somigliano e non sono la stessa.
            nome = self._nomi_categoria.get(self._categoria) or self._nome_categoria(
                self._categoria)
            if nome:
                return f"\u00ab{nome}\u00bb non ha media da mostrare."
            return "Questa categoria non ha media da mostrare."
        return "Non c'e' niente da mostrare qui."

    def _voce_di_catalogo(self, pub) -> tuple:
        """La card di una pubblicazione del catalogo: il dizionario e la modalita'.

        UN POSTO SOLO, E NON DUE
        -------------------------
        Questo dizionario e' quello che `_Cella` legge: `titolo` per la riga
        scritta, `sotto` per la riga piccola, `pub` per sapere di chi si tratta,
        `icona` per il segnaposto, `_anteprima` per la copertina gia' in cache.

        Prima la stessa cosa era scritta dentro `_celle_del_catalogo`, e la
        ricerca ne faceva una copia con la sola chiave `pub`.  Il sintomo era
        che cercando una pubblicazione la griglia **trovava** la riga giusta e
        ci scriveva «?» al posto del titolo, senza copertina e senza icona: la
        card sapeva di quale pubblicazione si trattava — il click scaricava il
        pezzo giusto — ma non aveva il nome da mostrare.

        Una card senza il proprio dizionario sembra una card a posto: apre e
        scarica, quindi sembra funzionare, e quello che manca si nota solo
        guardando.  Percio' qui dentro c'e' tutto quello che la cella
        disegna, e le due liste — la categoria e la ricerca — non possono
        divergere.

        LA COPERTINA CHE E' GIA' SU DISCO, SUBITO E SENZA ASPETTARE NULLA
        -----------------------------------------------------------------
        Si legge dalla cache dei file, e **non** dalla rete:
        `dati_gia_in_cache` non chiede niente a nessuno e risponde subito, o
        con i byte o con «non c'e'».

        Prima qui c'era `pixmap_copertina` solo per i pacchetti scaricati, e
        **tutto il resto** passava dal thread di rete: la prima volta arrivava
        dopo mezzo secondo e la seconda pure, anche con la copertina gia'
        scaricata da giorni.  L'utente riapriva «Libri» e rivedeva le icone al
        posto delle copertine, ogni volta, per sempre.

        Il prezzo di questa riga e' una lettura di file per card, e sono ~30
        byte di indice piu' ~34 KB di immagine: si fa in meno di un
        millisecondo e decodifica sul main thread, che e' il posto dove un
        `QPixmap` puo' essere creato.
        """
        return ({"titolo": _titolo_visuale(pub),
                 "sotto": _riga_sotto(pub),
                 "pub": pub,
                 "icona": _icona_del_tipo(
                     getattr(pub, "publicationTypeId", 0)),
                 "_anteprima": _copertina_subito(pub)},
                "pub")


    def _celle_pubblicazioni(self) -> list:
        """Le dodici categorie di pubblicazioni.

        IL CONTATORE QUI E NON DALL'ALTRA PARTE
        ---------------------------------------
        Ogni altra cosa che finisce nella griglia scrive il proprio numero
        accanto al campo di ricerca, e questa no: il contatore restava quello
        della ricerca precedente.

        Il sintomo era che tornando alle categorie dopo aver cercato qualcosa,
        sotto al campo c'era ancora «1 pubblicazione per "altri"» mentre a
        schermo c'erano le dodici categorie.  Un contatore che parla di una
        griglia che non e' quella a schermo e' la cosa piu' falsa che ci sia in
        una barra di stato.

        Qui si dice quello che c'e' davvero: quante categorie e quante
        pubblicazioni in tutto.  Il numero del catalogo viene contato sul
        catalogo gia' letto, e non si rilegge il database solo per quello.
        """
        if not self._catalogo:
            try:
                from Utility.DBManager import DBManager
                self._catalogo = list(DBManager.get_publications())
            except Exception:  # noqa: BLE001 - il catalogo non e' un guasto
                self._catalogo = []
        totale = len(self._catalogo)
        categorie = len(CATEGORIE_PUB)
        if totale:
            self.conteggio.setText(
                f"{categorie} categorie — {totale} pubblicazioni")
        else:
            self.conteggio.setText(f"{categorie} categorie")
        return [({"titolo": nome, "icona": icona, "chiave": chiave}, "pub")
                for chiave, nome, icona in CATEGORIE_PUB]

    def _celle_del_catalogo(self, chiave: str) -> list:
        """Le card delle pubblicazioni di una categoria del catalogo.

        PERCHE' COME LE CATEGORIE E NON COME L'ELENCO DI `PubListView`
        -------------------------------------------------------------
        L'elenco vecchio — quello con le righe strette — e' quello che ha
        fatto notare che le pubblicazioni si vedevano "troppo piccole": e' una
        riga alta 34 pixel con il titolo e la nuvoletta a destra.  Serve per
        sfogliare diecimila titoli cercandone uno, e non per scegliere.

        Qui si sceglie.  Le pubblicazioni sono disegnate con la **stessa cella
        delle categorie** — stessa altezza, stesso fondo, stesso titolo — e con
        la copertina piu' grande, perche' la copertina e' la cosa che distingue
        un annuario da una brochure.  E dentro la copertina ci sono i due
        tasti della Home: «...» e scarica/aggiorna.

        Lo stile e' lo stesso in ogni sezione che mostra pubblicazioni — qui,
        negli Scaricati, nei Preferiti della Home — perche' e' la stessa classe
        `_Cella` che le disegna tutte.  Un pezzo che cambia faccia a seconda di
        dove si apre non e' uno stile: e' un'altra applicazione dentro la stessa.

        IL CATALOGO VIENE LETTO UNA VOLTA SOLA
        ---------------------------------------
        `self._catalogo` e' un dizionario vuoto e si riempie alla prima richiesta
        e resta li'.  Rileggere `catalog.db` — 3.745 righe — a ogni categoria
        premuta si sente come un'esitazione dell'app, e il lettore prova a
        ripremere.
        """
        if not self._catalogo:
            try:
                from Utility.DBManager import DBManager
                self._catalogo = list(DBManager.get_publications())
            except Exception as errore:  # noqa: BLE001 - il catalogo non e' un guasto
                print(f"Biblioteca: catalogo non leggibile ⚠️  {errore}")
                return []

        # LA DOMANDA, NON I NUMERI
        # -----------------------
        # `FILTRO_CATEGORIA` tiene per ogni categoria una **domanda** — «questa
        # pubblicazione e' di questa categoria?» — e non l'insieme dei numeri
        # che ci starebbero dentro.  Undici categorie si riconoscono dal tipo e
        # una dalla sigla, e mettere tutte e dodici nella stessa forma e'
        # l'unico modo che il chiamante non debba accorgersi della differenza.
        #
        # Il `if filtra is None` copre la chiave che non c'e' nella tabella: e'
        # un'istruzione che arriva da fuori (una sezione che chiede una
        # categoria inesistente), e senza questo controllo `filtra(...)` su
        # `None` romperebbe con un errore che non spiega niente.
        filtra = FILTRO_CATEGORIA.get(chiave)
        if filtra is None:
            self.conteggio.setText("")
            return []
        scelte = [p for p in self._catalogo if filtra(p)]
        self._tutte_le_categorie[chiave] = scelte

        # LA RICERCA CERCA IN TUTTE, NON NELLE PRIME 300
        # -------------------------------------------------
        # Il campo filta `scelte`, che e' l'elenco **intero** della categoria, e
        # il limite di 300 viene dopo.  Filtrando dopo, una ricerca su un titolo
        # che sta alla posizione 2.000 non troverebbe niente e l'utente
        # concluderebbe che quel titolo non e' in catalogo — che e' falso, e
        # proprio sulle categorie grandi dove serve di piu'.
        #
        # Confronta `_titolo_visuale`, che e' il titolo **mostrato**: sui
        # periodici e' `issueTitle`, e cercando «gennaio 2024» dentro
        # `pub.title` — che e' sempre «La Torre di Guardia annunciante il Regno
        # di Geova» — non si troverebbe mai un numero.  Un campo che cerca in un
        # testo diverso da quello a schermo sembra che non funzioni, e invece
        # funziona su un altro pezzo di testo: e' la cosa piu' difficile da
        # diagnosticare che ci sia.
        #
        # Il confronto **contiene** e non comincia, come in
        # `DBManager.cerca_pubblicazioni`: con «pecore» devono uscire anche
        # «Amiamio le pecore smarite».
        if self._testo_cercato:
            cercato = self._testo_cercato
            scelte = [p for p in scelte
                      if cercato in _titolo_visuale(p).lower()
                      or cercato in (getattr(p, "keySymbol", "") or "").lower()]

        quante = len(scelte)

        # NON TUTTE, E PERCHE' IL NUMERO E' LIMITATO
        # ------------------------------------------
        # «La Torre di Guardia» sono 2.787 pubblicazioni, e una card e' un
        # widget Qt con layout, geometria e disegno: 2.787 card sono 2.787
        # widget da costruire e ridisegnare a ogni scorrimento.  Questo programma
        # ha gia' pagato quel conto — vedi la nota in cima a `PubListView`, dove
        # 3.741 righe come widget costavano 1.147 millisecondi e congelavano
        # tutto.
        #
        # Non e' una scorciatoia e non si nasconde: il campo accanto dice
        # «2.787 pubblicazioni, prime 300», e la ricerca arriva a tutte.  Un
        # numero che mente sarebbe peggio — sembrerebbe che il catalogo finisca
        # a 300.
        viste = scelte[:MASSIMO_CARTE]

        celle = [self._voce_di_catalogo(pub) for pub in viste]

        # LE COPERTINE CHE NON CI SONO ANCORA
        # ------------------------------------
        # Quelle gia' sul disco si sono viste subito, perche' sono un file
        # locale e non costa niente.  Tutte le altre — cioe' quasi tutte — si
        # chiedono al server, e chiederne 300 **mentre si disegna** bloccherebbe
        # la finestra per minuti.  E' la ragione per cui
        # `Copertine.pixmap_copertina` avvisa espressamente di non essere chiamata
        # dal main thread in una griglia.
        #
        # Qui le copertine non si vedono: al loro posto c'e' l'icona del tipo,
        # che e' la riserva giusta — dice a quale gruppo appartiene la
        # pubblicazione anche senza copertina.
        #
        # Vengono chieste **in background**, e arrivate ognuna mette la propria
        # copertina al posto dell'icona.  Il thread porta via i byte e il main
        # thread fa il `QPixmap`: un `QPixmap` creato in un altro thread non e'
        # valido, e con sole schede fuori schermo non si vedrebbe nulla.
        #
        # Non le si chiede a tutte le 3.745 ma solo alle prime `MASSIMO_CARTE`
        # della categoria aperta: sono quelle che l'utente sta guardando.  La
        # ricerca cambia la lista e le richieste ricominciano, che e' il
        # comportamento giusto — si scaricano le copertine di quello che si
        # vede, non di quello che non si vede.
        self._copertine_da_chiedere = list(viste)

        # IL NUMERO ACCANTO AL CAMPO
        # ---------------------------
        # Dice tre cose quando servono e una sola quando non servono: quante
        # pubblicazioni ha la categoria, quante ne vede adesso, e — solo se il
        # limite di 300 e' stato toccato — che il limite c'e'.  Senza l'ultima
        # parte un utente che scorre la Torre di Guardia arriverebbe in fondo e
        # non saprebbe se ha finito o se ce n'e' ancora.
        nome = self._nome_categoria(chiave)
        # Il singolare e il plurale si contano, non si indovinano: «1
        # pubblicazioni» accanto a un solo risultato fa pensare che il filtro
        # abbia perso qualcosa, che e' esattamente il dubbio che il campo di
        # ricerca non deve lasciare.
        parola = "pubblicazione" if quante == 1 else "pubblicazioni"
        if self._testo_cercato:
            self.conteggio.setText(
                f"{quante} {parola} per «{self._testo_cercato}»")
        elif quante > len(viste):
            self.conteggio.setText(
                f"{nome} — {quante} pubblicazioni, prime {len(viste)}")
        elif quante:
            self.conteggio.setText(f"{nome} — {quante} {parola}")
        else:
            self.conteggio.setText(f"{nome} — nessuna pubblicazione")
        return celle

    def _celle_della_ricerca(self) -> list:
        """Le pubblicazioni di **tutto** il catalogo che contengono il testo.

        PERCHE' SERVE, E NON ERA
        -----------------------
        Il campo di ricerca c'era, e dentro una categoria funzionava.  Sulla
        pagina principale — dove si vedono le dodici categorie — non
        funzionava: `_cerca_cambiata` chiama `_ricostruisci`, e senza categoria
        aperta quella mostrava le dodici categorie e ignorava il testo.

        Il sintomo e' il peggiore che possa esserci: si scrive un titolo, la
        griglia non cambia, e non si capisce se il titolo non c'e' o se il
        campo non fa niente.  Il contatore accanto al campo restava vuoto, che
        e' la prova che nessuno aveva guardato niente.

        PERCHE' CERCA SU TUTTO E NON SOLO NELLA CATEGORIA APERTA
        -------------------------------------------------------
        Perche' quando non c'e' nessuna categoria aperta non c'e' niente da
        limitare: e' l'unico momento in cui l'utente puo' chiedere una
        pubblicazione **senza sapere in quale categoria sia**.  Cercare «altri
        argomenti» e dover prima sapere che sta sotto «Trattati e inviti» e'
        chiedere all'utente di conoscere una risposta che non gli si e' data.

        IL CONFRONTO E' SU QUELLO CHE SI VEDE
        -------------------------------------
        `_titolo_visuale`, non `title`: sui periodici il titolo e' sempre lo
        stesso («La Torre di Guardia…») e il numero del numero sta in
        `issueTitle`.  Cercando «marzo 2015» dentro `title` non si troverebbe
        mai niente — che e' la stessa cosa che renderebbe il campo muto.

        Anche la sigla, perche' «mrt» e' quello che c'e' scritto sul pacchetto
        scaricato e nella cartella: un utente che ha scaricato «Altri
        argomenti» una volta lo cerca cosi' la seconda.
        """
        cercato = self._testo_cercato
        if not self._catalogo:
            try:
                from Utility.DBManager import DBManager
                self._catalogo = list(DBManager.get_publications())
            except Exception as errore:  # noqa: BLE001 - il catalogo non e' un guasto
                print(f"Biblioteca: catalogo non leggibile ⚠️  {errore}")
                self.conteggio.setText("")
                return []

        scelte = [p for p in self._catalogo
                  if cercato in _titolo_visuale(p).lower()
                  or cercato in (getattr(p, "keySymbol", "") or "").lower()]
        quante = len(scelte)
        viste = scelte[:MASSIMO_CARTE]
        celle = [self._voce_di_catalogo(p) for p in viste]
        self._copertine_da_chiedere = list(viste)

        parola = "pubblicazione" if quante == 1 else "pubblicazioni"
        if not quante:
            self.conteggio.setText(f"nessuna pubblicazione per «{cercato}»")
        elif quante > len(viste):
            self.conteggio.setText(
                f"{quante} {parola} per «{cercato}», prime {len(viste)}")
        else:
            self.conteggio.setText(f"{quante} {parola} per «{cercato}»")
        return celle

    def _chiedi_altre_copertine(self, _posizione: int = 0) -> None:
        """Chiedi le copertine delle card che sono entrate a schermo.

        UN SOLO PUNTO DOVE SI PARTE
        --------------------------
        Chiamata sia da `_riempi_griglia` — quando la griglia si riempie — sia
        dalla barra di scorrimento.  Prima erano due posti, e quello dentro
        `_riempi_griglia` poteva saltare: `_ricostruisci` gira piu' volte, e se
        la richiesta era ancora in corso la seconda volta non faceva niente e
        **non riprovava dopo**.  Il pezzo rimaneva in `_copertine_da_chiedere`
        per sempre, e scorrendo la schermata non chiedeva piu' niente.

        Il difetto e' che la condizione per lavorare e' vera solo ogni tanto, e
        il codice che la verifica viene eseguito una volta sola: quando torna
        vero, non c'e' piu' niente che lo richiami.

        Non fa niente se una richiesta e' gia' in corso e non tocca le altre tre
        tab, che non hanno copertine da chiedere.

        ANCHE LE SCHEDE AUDIO E VIDEO
        ----------------------------
        Prima questo punto tornava subito se la scheda non era
        Pubblicazioni, quindi per Audio e Video non passava mai nessuno: le
        locandine dei media le chiedeva solo `_categoria_arrivata`, una volta,
        e per di piu' ne chiedeva 30 su 109 senza mai ripetere il pezzo.  Il
        risultato era «manca il riquadro di anteprima» su tutto quello che
        veniva dopo le prime trenta.

        Le due schede hanno una strada propria, `_chiedi_antprime`, perche' la
        domanda e' diversa: le voci non hanno un id di pubblicazione e quindi
        `pub.ID` non esiste, e la card si trova dalla voce.  Ma il punto da cui
        parte resta questo, cosi' anche scorrendo la griglia si chiede il pezzo
        nuovo — e come per le pubblicazioni la richiesta non parte se ce n'e'
        gia' una in corso.
        """
        if self._copertine_in_corso or self._antprime_in_corso:
            return
        if self._scheda in (TAB_AUDIO, TAB_VIDEO):
            self._chiedi_antprime_categorie()
            self._chiedi_antprime()
            return
        if self._scheda != TAB_PUBBLICAZIONI:
            return
        if not self._categoria_aperta:
            return

        # Si prende prima quello che `_celle_del_catalogo` ha messo da parte —
        # le card appena create — e se non c'e' niente, si prosegue con il
        # pezzo successivo della categoria, che e' quello che lo scorrimento ha
        # appena portato a schermo.
        da_chiedere = self._copertine_da_chiedere
        if not da_chiedere:
            chiave = self._categoria_aperta
            if chiave not in self._tutte_le_categorie:
                return
            da_chiedere = self._tutte_le_categorie[chiave]
        self._copertine_da_chiedere = []
        self._chiedi_copertine(da_chiedere)

    def _chiedi_copertine(self, pubblicazioni: list) -> None:
        """Scarica in background le copertine mancanti delle card a schermo.

        LE COPERTINE ARRIVANO A UNA CARD CHE PUO' NON ESSERE PIU' QUELLA
        ---------------------------------------------------------------
        Coprire le richieste tenendo il **widget** è il modo più corto e
        funziona finché la griglia non viene ricostruita. E invece viene
        ricostruita: `_ricostruisci` passa da `_griglia.svuota()`, che chiama
        `deleteLater()` su tutte le celle, e `apri_una_categoria` /
        `torna_alle_categorie` / la ricerca lo fanno spesso.

        Perciò la copertina che arriva dopo trenta secondi verrebbe cercata in
        un widget distrutto, `sip.isdeleted` direbbe di sì, e la copertina
        verrebbe buttata. Il sintomo è «le immagini non arrivano mai» e la
        causa è un riferimento tenuto troppo a lungo — la classe di difetto più
        difficile da trovare, perché non c'è nessun errore.

        Per questo il legame è fra la pubblicazione e la card **di adesso**:
        al momento di mettere la copertina si cerca fra le celle che sono
        davvero a schermo quella con quella pubblicazione. Se nel frattempo
        l'utente ha cambiato categoria, quella card non c'è più e la copertina
        viene scartata — il comportamento giusto, non perdere nulla.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        def _id_di(widget):
            pub = widget.cosa.get("pub") if hasattr(widget, "cosa") else None
            return getattr(pub, "ID", None)

        celle = {}
        for voce in self._griglia._flusso._voci:
            widget = voce.widget() if hasattr(voce, "widget") else None
            if isinstance(widget, _Cella) and widget.ha_comandi:
                chiave = _id_di(widget)
                if chiave is not None and widget.cosa.get("_anteprima") is None:
                    celle[chiave] = True

        mancanti = [p for p in pubblicazioni
                    if getattr(p, "ID", None) in celle]

        # SOLO QUELLE CHE SI VEDONO, E PERCHE' TUTTE FA MALE
        # ---------------------------------------------------
        # `Copertine` tiene una lista di indirizzi che non hanno risposto e non
        # li richiede piu' **per tutta la sessione**.  Chiedere 124 copertine
        # tutte insieme fa scattare il limite del CDN, il CDN risponde 403, e quei
        # 83 indirizzi finiscono nella lista come se non esistessero: la sezione
        # resta senza copertine per il resto della sessione, anche tornando
        # domani, e il difetto si vede come «il programma non le scarica» e non
        # come «abbiamo chiesto troppo in una volta».
        #
        # Nessuna di quelle copertine era assente: verificate a mano, arrivano
        # tutte.  Il problema non era la rete, era quanta ne chiedevamo insieme.
        #
        # Qui si chiede quello che si vede, e si conta dalla larghezza della
        # griglia: tre colonne per cinque righe, piu' una riga di margine per
        # quella che sta arrivando sotto.  Scorrendo si chiede il pezzo nuovo.
        larghezza = max(self._griglia.width(), CELLA_LARGA)
        colonne = max(1, larghezza // (CELLA_LARGA + 4))
        righe = 6
        quante = colonne * (righe + 1)

        # Solo quelle non ancora chieste: `Copertine` ricorda per tutta la
        # sessione gli indirizzi che non hanno risposto e non li ripete, quindi
        # chiedere di nuovo produrrebbe solo traffico sprecato.
        mancanti = [p for p in mancanti
                    if getattr(p, "ID", None) not in self._copertine_chieste]
        mancanti = mancanti[:quante]
        if not mancanti:
            return
        # Si segnano subito: sono in volo, e se tornassero a passarci un
        # altro scorrimento non li chiederebbe due volte.
        self._copertine_chieste |= {getattr(p, "ID", None) for p in mancanti}

        # Una richiesta sola per tutte: `background` parte un thread per ogni
        # chiamata, e 300 thread che chiedono 300 copertine contemporaneamente
        # aprirebbero 300 connessioni e il server risponderebbe piano o
        # chiuderebbe la connessione.
        self._copertine_in_corso = True
        risultati: list = []

        def lavoro() -> None:
            from concurrent.futures import ThreadPoolExecutor

            from Utility import Copertine

            def uno(pub):
                try:
                    return (getattr(pub, "ID", None),
                            Copertine.dati_copertina(pub, "md"))
                except Exception as errore:  # noqa: BLE001 - una copertina mancante non e' un guasto
                    # Una copertina che non si puo' chiedere non ferma le altre
                    # 123, ma **si dice**: altrimenti il difetto si vede come
                    # «le immagini non arrivano» e non come «una richiesta e'
                    # fallita», che sono due bug diversi.
                    print(f"Copertina {getattr(pub, 'keySymbol', '?')} non "
                          f"arriva ⚠️  {type(errore).__name__}: {errore}")
                    return (getattr(pub, "ID", None), None)

            # SEI THREAD, E NON DI PIU'
            # -----------------------
            # Una copertina ci mette circa 0,15 secondi e quelle sono richieste
            # di rete: in fila 124 copertine sono 19 secondi di attesa, e
            # l'utente che guarda le card le vede tutte senza immagine per
            # mezzo minuto, e poi tutte insieme.
            #
            # Sei thread portano a circa 3 secondi e tengono la connessione
            # sotto controllo.  Di piu' non serve: il collo di bottiglia non e'
            # la banda — sono i giri di andata e ritorno — e con 20 thread si
            # guadagna poco e si rischia che il server scarta qualcuna richiesta
            # perche' sono troppe connessioni aperte insieme.
            with ThreadPoolExecutor(max_workers=6) as piscina:
                for risultato in piscina.map(uno, mancanti):
                    risultati.append(risultato)

        def arrivati() -> None:
            from PyQt6 import sip
            from Utility.Copertine import pixmap_da_dati

            self._copertine_in_corso = False

            # Le card di **adesso**, non quelle di quando la richiesta e' partita:
            # la griglia e' stata ricostruita nel frattempo e quelle prime non
            # esistono piu'.  Vedi la nota del metodo.
            ora = {}
            for voce in self._griglia._flusso._voci:
                widget = voce.widget() if hasattr(voce, "widget") else None
                if isinstance(widget, _Cella) and widget.ha_comandi:
                    chiave = _id_di(widget)
                    if chiave is not None:
                        ora[chiave] = widget

            for chiave, dati in risultati:
                cella = ora.get(chiave)
                if cella is None or sip.isdeleted(cella) or not dati:
                    continue
                cella.metti_immagine(pixmap_da_dati(dati))

        background(lavoro, completion=arrivati)

    def _nome_categoria(self, chiave: str) -> str:
        """Il nome leggibile di una categoria, cercandolo dove e' scritto.

        DUE TABELLE, E NON UNA
        -----------------------
        Le pubblicazioni hanno le loro dodici (`CATEGORIE_PUB`) e i media hanno
        le loro (`Mediator.CATEGORIE`).  Sono due elenchi diversi perche' sono
        cose diverse: le prime vengono da MepsAPI con un `pubType` dentro,
        le seconde dal mediator con una chiave che finisce l'indirizzo.  Non
        si possono mettere insieme in una tabella sola senza aggiungere un
        campo che dica da dove viene ognuna.

        Prima ne guardava una sola, e per una categoria del mediator
        restituiva la stringa vuota: il contatore scriveva «media » con il
        nome mancante, e il messaggio di categoria vuota diceva «» non ha
        media da mostrare».  Il nome c'era, solo che si cercava nella tabella
        sbagliata.

        Una chiave sconosciuta dà la stringa vuota invece di far fallire tutto:
        mostrare «prima 300» senza nome e' comunque piu' utile che niente.
        """
        for chiave_categoria, nome, _icona in CATEGORIE_PUB:
            if chiave_categoria == chiave:
                return nome
        for chiave_categoria, nome, _descrizione in Mediator.CATEGORIE:
            if chiave_categoria == chiave:
                return nome
        return ""

    def _celle_delle_categorie_media(self) -> list:
        """Le categorie di Video e Audio, come card — non come linguette.

        LE STESSE CARD DELLE PUBBLICAZIONI
        ----------------------------------
        Prima erano sei bottoni piccoli in una riga sopra l'elenco.  Nella
        sezione Pubblicazioni la stessa scelta si fa con le card, e passare da
        una tab all'altra cambiava aspetto: due modi di scegliere la stessa
        cosa nella stessa sezione.

        Quindi anche qui si sceglie con le card: quadrato con l'icona a
        sinistra, il nome a destra.  Il risultato e' che le quattro tab si
        somigliano e l'occhio impara una volta sola.

        COSA C'E' DENTRO
        -----------------
        Solo la chiave e il nome.  Non un numero di voci: quello arriva dal
        server e metterlo qui vuol dire una richiesta per ogni categoria, cioe'
        sei richieste a ogni apertura della sezione per mettere un numero che
        l'utente non ha chiesto.  Il nome viene dal server quando arriva — e
        nel frattempo si vede quello della tabella, che e' una scritta
        provvisoria e non un dato inventato.

        «In primo piano» non c'e': `FeaturedLibraryLanding` e' una pagina, non
        un elenco, e il server gli da' lo stesso nome di `FeaturedLibraryVideos`.
        Due card con la stessa parola non si distinguono.
        """
        celle = []
        vuole_audio = self._scheda == TAB_AUDIO
        # LA LISTA VIENE DA `Mediator.categorie_di`, E NON DA UNA PROVA
        # -----------------------------------------------------------
        # Qui prima, per ogni categoria e ogni volta che la griglia si
        # ridisegnava, si chiedeva al server `Mediator.voci(chiave)[:3]`
        # per contare se dentro ci fosse un audio o un video.  Erano una
        # decina di richieste di rete **per disegnare**: la sezione
        # andava a scatti, e senza connessione restava il vuoto perche'
        # la griglia non riusciva a costruirsi.
        #
        # E la prova contava le prime tre voci, che in
        # `VOXDramaticBibleReading` sono tre video: la categoria che ha 7
        # audio spariva dalla scheda Audio.  E' la stessa categoria che si
        # stava cercando, e spariva perche' il test era fatto sul campione
        # invece che sulla categoria.
        #
        # Ora la domanda la risponde la tabella `Mediator.NATURA`, che
        # `python3 -m Utility.Mediator` confronta con quello che c'e' davvero
        # sul server e segnala se non tornano.
        for chiave, nome, _descrizione in Mediator.categorie_di(
                "audio" if vuole_audio else "video"):
            if chiave == "FeaturedLibraryLanding":
                continue
            # Il nome del server, se e' gia' arrivato: e' quello che ha scritto
            # lui, e non quello che era qui quando la finestra si e' aperta.
            scritto = self._nomi_categoria.get(chiave) or nome
            # L'ICONA SEGUE LA TAB
            # ---------------------
            # Cinque card e tutte col simbolo del film, anche su Audio: e' la
            # stessa icona per due cose diverse, e su una tabella audio un
            # pallino che dice «video» contraddice quello che c'e' scritto
            # accanto.
            #
            # Non e' un colore diverso perche' e' la stessa forma di informazione:
            # la tab dice gia' «Audio», quindi l'icona ripete.  Ma se la
            # ripete sbagliata, allora la cosa che doveva aiutare a orientarsi
            # dice il contrario.
            glifo = "headphones" if vuole_audio else "film"
            # L'IMMAGINE DELLA CATEGORIA, SE IL SERVER L'HA MANDATA
            # --------------------------------------------------------
            # Una categoria non ha una copertina, ma alcune ne hanno
            # un'immagine propria: `Mediator.immagini_categoria` la legge da
            # `category.images` e restituisce tutte le misure, cosi' che se
            # una non esiste sul CDN si prova la successiva.
            #
            # Si passa in `trackImage` perche' e' il campo che gia' conosce
            # `Copertine.locandina_del_media`: un campo nuovo avrebbe voluto
            # una seconda strada per la stessa domanda, e le due strade
            # avrebbero cominciato a dare risposte diverse.
            #
            # Misurato: delle diciannove categorie **una sola** ha
            # un'immagine.  Le altre diciotto continuano col glifo, che e'
            # la verita': non si inventa un'immagine dove il server non ha
            # pubblicato niente.
            immagini = Mediator.immagini_categoria_gia_note(chiave, self._lingua)
            track = ({"url": immagini[0], "alternative": immagini[1:]}
                     if immagini else {})
            cella = {"titolo": scritto,
                     "categoria_media": chiave,
                     "icona": glifo,
                     "trackImage": track}
            # Se l'immagine e' gia' in cache si mette subito: senza, la card
            # mostrava il glifo per mezzo secondo e poi l'immagine, e la
            # seconda volta che si apre la sezione non si aspettava piu'.
            if track:
                dati = Copertine.locandina_del_media(cella, solo_cache=True)
                if dati:
                    from Utility.Copertine import pixmap_da_dati, pixmap_quadrata
                    immagine = pixmap_da_dati(dati)
                    if immagine is not None and not immagine.isNull():
                        cella["_anteprima"] = pixmap_quadrata(immagine,
                                                             QUADRO_PUB)
            celle.append((cella, "pub"))
        # Le chiavi di cui l'immagine si puo' chiedere: solo quelle che ne
        # hanno una.  La lista la legge `_chiedi_antprime_categorie`, che e'
        # l'unico posto che la usa.
        self._antprime_cat_chiavi = [c[0]["categoria_media"]
                                     for c in celle if c[0].get("trackImage")]
        return celle

    def _celle_dei_media(self) -> list:
        """Le card dei media di questa scheda — Video o Audio.

        LE STESSE CARD DELLE PUBBLICAZIONI, NON UN ALTRO RITORNO
        -------------------------------------------------------
        Video e Audio erano righe strette: 34 pixel, miniatura piccola, titolo e
        un triangolino.  Funzionano per sfogliare, e sono cio' che c'era prima.

        Ma sono un **aspetto diverso** nella stessa sezione: passi dalle
        pubblicazioni a Video e le card diventano righe, e viceversa.  Due
        aspetti per la cosa stessa e' quello che fa sembrare un programma
        piu' complicato di quanto sia — e qui la sezione e' una sola, quindi il
        salto si vede a ogni cambio di tab.

        Quindi i media prendono la card delle pubblicazioni: quadrato a
        sinistra, titolo e riga sotto a destra, e i due tasti a destra.

        COSA C'E' DENTRO LA CARD
        ------------------------
        Sulla riga stretta la miniatura era 56x32, cioe' rettangolare e
        piccola.  Nella card e' un quadrato come quello delle copertine, perche'
        il posto e' quadrato: stirare dentro un quadrato una miniatura
        panoramica la fa sembrare una copertina, che e' una cosa diversa.

        IL LIMITE E' LO STESSO DELLE PUBBLICAZIONI
        ------------------------------------------
        300 card, non tutte.  Una card e' un widget con layout, geometria e
        disegno, e «Ultimi video» ne ha 15.000: costruirle tutte congela la
        finestra per minuti.  Il campo accanto al nome dice
        «N voci», quindi il numero che si vede e' quello vero.
        """
        voci = self._quando_video(self._voci)
        quante = len(voci)
        viste = voci[:MASSIMO_CARTE]

        # LE ANTEPRIME CHE SONO GIA' SU DISCO
        # -------------------------------------
        # Prima, come per le copertine: si legge il file e non si chiede niente
        # a nessuno, cosi' la seconda volta che si apre la sezione le
        # miniatura sono gia' li' mentre la finestra si disegna.
        anteprime = {}
        for voce in viste:
            try:
                dati = _copertina_subito_media(voce)
            except Exception:  # noqa: BLE001 - un'immagine mancante non ferma nulla
                dati = None
            if dati is not None:
                anteprime[id(voce)] = dati

        celle = []
        for voce in viste:
            celle.append(({"titolo": voce.get("title") or voce.get("label") or "?",
                           "sotto": _dettaglio(voce),
                           "voce": voce,
                           "icona": _glifo_per(voce),
                           "_anteprima": anteprime.get(id(voce))},
                          "media"))
        self._copertine_da_chiedere = list(viste)

        if not quante:
            self.conteggio.setText("nessun media")
        elif quante > len(viste):
            parola = "media" if quante == 1 else "media"
            nome = (self._nome_categoria(self._categoria)
                    if self._categoria else "")
            dove = f" in {nome}" if nome else ""
            self.conteggio.setText(
                f"{quante} {parola}{dove}, prime {len(viste)}")
        else:
            parola = "media" if quante == 1 else "media"
            nome = (self._nome_categoria(self._categoria)
                    if self._categoria else "")
            dove = f" in {nome}" if nome else ""
            self.conteggio.setText(f"{quante} {parola}{dove}")
        return celle

    def _celle_scaricati(self) -> list:
        """Le pubblicazioni che sono gia' sul disco.

        La lista viene da `JWPubManager.scaricate()`, che guarda i pacchetti
        con dentro un `.db`: e' lo stesso criterio con cui la sezione Scaricati
        dichiara una cartella utilizzabile, quindi qui non puo' comparire una
        cartella che un secondo dopo l'app direbbe non utilizzabile.

        Il titolo viene dal `.db` del pacchetto e non dal nome della cartella:
        `w_202310` dice il mese, non cosa sia.  Se il `.db` non si legge si
        mostra il nome della cartella, che almeno e' vero, e non si mette la
        cella fra le scaricate: una cartella di cui non si sa cosa sia non e'
        una pubblicazione, e metterla aprirebbe una schermata vuota.

        LA CELLA TIENE L'OGGETTO `pub`, E NON IL PERCORSO
        ---------------------------------------------------
        Perche' `apri_pubblicazione` vuole `pub` e non un percorso: rifare qui
        la lettura del `.db` e passare il risultato avrebbe due posti che
        leggono lo stesso pacchetto, e il giorno che uno dei due legge un
        campo in piu' l'altro aprirebbe una pubblicazione diversa.
        """
        from Utility import JWPubManager
        celle = []
        try:
            cartelle = JWPubManager.scaricate()
        except OSError as errore:
            print(f"Scaricati: non riesco a leggere i pacchetti ⚠️  {errore}")
            return celle
        for cartella in cartelle:
            pub = JWPubManager.leggi_pubblicazione(cartella)
            if pub is None:
                continue
            titolo = getattr(pub, "title", "") or cartella.name
            sotto = getattr(pub, "language", "") or ""
            # La stessa copertina, la stessa icona e gli stessi bottoni del
            # catalogo.  Uno scaricato e' la stessa pubblicazione che nella
            # tab Pubblicazioni: se le due liste avessero facce diverse,
            # l'utente cercherebbe il pezzo che ha gia' scaricato e non lo
            # riconoscerebbe.
            # Solo disco e cache, mai la rete: la copertina di un pacchetto
            # scaricato e' gia' dentro il pacchetto, e le mancanti arrivano dopo,
            # in secondo piano (`_chiedi_altre_copertine`).
            dati_copertina = Copertine.dati_gia_in_cache(pub, "md")
            celle.append(({"titolo": titolo, "sotto": sotto, "pub": pub,
                           "icona": _icona_del_tipo(
                               getattr(pub, "publicationTypeId", 0)),
                           "_anteprima": (Copertine.pixmap_da_dati(dati_copertina)
                                          if dati_copertina else None)},
                          "pub"))
        # Le Bibbie scaricate come testo (senza pacchetto): una cella ciascuna,
        # cosi' si vedono qui e si possono eliminare.
        try:
            from Utility import Traduzioni
            for voce in Traduzioni.scaricate():
                celle.append(({
                    "titolo": f"Bibbia — {voce['nome']}",
                    "sotto": f"{voce['capitoli']} capitoli · "
                             f"{voce['byte'] / (1024 * 1024):.1f} MB",
                    "icona": ICONA_SEGNAPOSTO,
                    "traduzione": voce}, "pub"))
        except Exception as errore:  # noqa: BLE001 - un disco illeggibile non ferma la griglia
            print(f"Scaricati: non riesco a leggere le Bibbie ⚠️  {errore}")
        return celle

    def _chiedi_elimina_bibbia(self, voce: dict) -> None:
        from SubViews.Conferma import ConfermaApp
        from Utility import Traduzioni

        def elimina() -> None:
            Traduzioni.elimina(voce["simbolo"])
            self.messaggio.emit(f"Bibbia in {voce['nome']} eliminata")
            # Stessa strada di un pacchetto tolto: griglia, Scaricati, Home.
            self.pacchettoRimossa.emit(None)

        ConfermaApp.chiedi(
            self.window(), "Eliminare la Bibbia?",
            f"Elimino dal disco la Bibbia in {voce['nome']} "
            f"({voce['capitoli']} capitoli).\n\nSi puo' riscaricare quando vuoi.",
            "Elimina", elimina)

    def _si_puo_scaricare(self) -> bool:
        """Si puo' andare in rete adesso, o l'utente ha chiesto il contrario?

        UN INTERRUTTORE SOLO, NON DUE
        ------------------------------
        Nelle impostazioni c'e' **una** casella, «Offline», e non ce n'e' una
        per gli aggiornamenti automatici e un'altra per la modalita' offline.
        Sarebbero due interruttori per la stessa domanda — «devo andare in
        rete?» — e possono trovarsi in due stati che si contraddicono senza
        che l'utente lo sappia.

        Quindi la casella si chiama «Offline» e il valore si chiama
        `aggiornamenti_automatici`: la stessa cosa detta al contrario.  Qui si
        legge il valore, che e' gia' nel suo ordine, e non si ragiona sul
        ribaltamento — quello e' un dettaglio delle impostazioni e sta li'.

        PERCHE' IL CLIC SULLA CARD LA CHIEDE E LA NUVOLETTA NO
        -----------------------------------------------------
        La nuvoletta e' un bottone con scritto «scarica»: premere un bottone
        con scritto «scarica» e' gia' dire «voglio andare a prendere quella
        cosa», e li' non si guarda l'impostazione.

        Il clic sulla card invece e' un gesto ambiguo, e la risposta non puo'
        mai essere «scarico».  Su una **pubblicazione** il file serve per
        leggere e il clic lo scarica, ma solo se il programma puo' andare in
        rete: in offline un giro di sfoglia riempirebbe il disco senza che
        nessuno l'abbia chiesto.  Su un **media** il clic si limita a
        **suonare** — dal disco se il file c'e', in streaming se non c'e' — e
        lo streaming e' andare in rete, quindi anche quello chiede
        l'impostazione: con Offline acceso non si parte, e lo si dice.
        """
        from Utility import Aggiornamenti

        return Aggiornamenti.automatici()

    def _cella_premuta(self, cosa: dict) -> None:
        """Una cella della griglia e' stata premuta."""
        if cosa.get("traduzione"):
            return          # si elimina solo dal menu «...», mai con un clic
        # UNA CARD-CATEGORIA APRE QUELLA LISTA
        # -------------------------------------
        # La chiave e' `categoria_media` e non `chiave` perche' quella gia'
        # parla delle dodici categorie delle pubblicazioni, e le due cose
        # finiscono nella stessa griglia: con la stessa chiave una card di
        # «Ultimi video» aprirebbe la categoria delle pubblicazioni che si
        # chiama uguale, e il sintomo sarebbe una sezione che si apre su
        # un'altra senza dire niente.
        categoria_media = cosa.get("categoria_media")
        if categoria_media:
            self.carica_categoria(categoria_media)
            return

        # UN MEDIA SI SUONA SUBITO, E NON SI SCARICA MAI
        # -----------------------------------------------
        # Su una pubblicazione il click apre il pacchetto o lo scarica, perche'
        # un libro non si guarda: si legge, e per leggerlo serve il pacchetto.
        #
        # Un video e un audio invece si **suonano**, e basta.  Se il file c'e'
        # sul disco si apre quello; se non c'e' si parte **in streaming**
        # dall'indirizzo che ha scritto il server nella voce.  Scaricare non e'
        # piu' una cosa che fa il click: lo fa solo la nuvoletta, che ha
        # scritto «scarica» ed e' quindi un assenso gia' detto.
        #
        # Prima il click scaricava il file quando non c'era, e con 705 brani
        # nella scheda Audio significava che un giro di sfoglia riempiva il
        # disco di cose non chieste — e intanto l'utente non sentiva niente,
        # perche' scaricare non e' ascoltare.
        #
        # L'impostazione Offline resta il solo interruttore: in offline non si
        # va in rete, e lo streaming e' andare in rete.  Quindi con Offline
        # acceso e il file non sul disco il click non puo' fare niente, e lo
        # si dice — con una frase che parla di **ascoltare**, perche' qui non
        # si sta scaricando niente.
        voce = cosa.get("voce")
        if voce is not None:
            from Utility import MediaScaricati

            if _media_sul_disco(voce) is not None:
                self._riproducci(voce)
                return

            if self._si_puo_scaricare():
                self._riproducci(voce)
                return

            self.messaggio.emit(
                "Modalita' offline: per ascoltare o guardare togli "
                "Offline in Impostazioni.")
            return

        pub = cosa.get("pub")
        if pub is not None:
            # IL PEZZO GIA' SUL DISCO SI APRE
            # --------------------------------
            # Qui non si scarica niente e non si chiede niente: il pacchetto e'
            # gia' qui, e aprirlo e' una cosa che funziona anche senza rete.
            from SubViews.PubListView import esiste_il_pacchetto
            if esiste_il_pacchetto(pub):
                self.scaricatoAperto.emit(pub, "")
                return

            # IL PEZZO NON C'E' E IL PROGRAMMA PUO' ANDARE IN RETE
            # ----------------------------------------------------
            # Stesso segnale del tasto nuvoletta: e' lo stesso download e non
            # una seconda copia.
            if self._si_puo_scaricare():
                self.scaricaRichiesta.emit(pub)
                return

            # MODALITA' OFFLINE: SI DICE PERCHE' NON SUCCEDE NIENTE
            # -----------------------------------------------------
            # Senza questa riga il programma non farebbe niente e sembrerebbe
            # rotto: l'utente preme una card, non si muove niente, e non sa se
            # ha sbagliato lui o se il programma e' piantato.
            #
            # Il messaggio dice **che cosa** fare per poterlo fare, e non solo
            # che non si puo': «accendi la casella» e' un'azione, mentre «non
            # puo'» e' solo la meta' di una frase.
            self.messaggio.emit(
                "Modalita' offline: per scaricare togli Offline in Impostazioni.")
            return
        # Una categoria di pubblicazioni: apre il catalogo **di quella
        # categoria**, dentro questa sezione.  Non c'e' una schermata per
        # «Libri» costruita qui: costruirla sarebbe una seconda copia del
        # catalogo, che dice una cosa diversa quando il catalogo cambia.
        #
        # La chiave viaggia nel segnale perche' e' l'unica cosa che la griglia
        # sa.  Senza, la finestra aprirebbe il catalogo intero — 3.741 righe —
        # mentre l'utente ne voleva le poche centinaia di una categoria, e il
        # catalogo sembrerebbe non obbedire.
        self.apriPubblicazioni.emit(cosa.get("chiave", ""))

    def _ricostruisci(self) -> None:
        """Le righe del media che ci sono, in questa scheda.

        IL CRASH CHE C'ERA
        ------------------
        Qui prima c'era un'etichetta fissa, ``self.stato``, che si metteva
        nella colonna quando la lista era vuota.  Ma questa funzione
        svuota la colonna e chiama ``deleteLater()`` su **tutto** quello
        che c' trova, e quindi cancellava anche quell'etichetta.  Al
        richiamo successivo la rimetteva, e Qt diceva:

            RuntimeError: wrapped C/C++ object of type QLabel
            has been deleted

        Il sintomo arrivava cambiando scheda con Audio o Video premendo e
        poi riaprendo la sezione, e sembrava un problema di Qt.

        La lezione e' che ``deleteLater()`` dentro un ciclo di svuotamento
        non deve mai essere applicato a un widget che qualcun altro
        continua a usare.  Qui la soluzione e' la piu' semplice: **ogni
        messaggio e' un'etichetta nuova**, costruita quando serve.  Non
        c'e' niente da riciclare e non c'e' niente che possa morire.
        """
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.deleteLater()

        # LE DUE TAB CHE NON HANNO UNA LISTA DI MEDIA
        # --------------------------------------------
        # Prima di tutto: chi si vede.  «Publicazioni» e «Scaricati» non
        # hanno voci da chiedere al server e non hanno una lista da costruire,
        # quindi per loro la funzione finisce qui: dice cosa si vede e riempie
        # la griglia.
        #
        # Il controllo sta **prima** del resto e non dentro `if not self._voci`:
        # nelle due tab nuove `_voci` e' sempre vuota, e senza questa riga
        # finirebbero nel ramo del «non c'e' niente» e direbbero «scegli una
        # pubblicazione dalla sezione Pubblicazioni», che in una sezione che
        # si chiama proprio Pubblicazioni e' una frase che si nega da sola.
        # VIDEO E AUDIO ANCHE, E NON SOLO LE PUBBLICAZIONI
        # --------------------------------------------------
        # Qui la lista era una **colonna** di righe strette, disegnata sotto, e
        # la griglia restava vuota.  Ora Video e Audio prendono le card come le
        # pubblicazioni, quindi anche loro finiscono in `_riempi_griglia` e
        # escono per questa porta.
        #
        # Senza questa riga le card non si costruivano: `_riempi_griglia`
        # riceveva una lista vuota e la griglia restava spoglia, senza dire
        # niente.  Il sintomo e' una sezione vuota con il contatore vuoto — due
        # indizi che puntano lontani l'uno dall'altro.
        if self._scheda in (TAB_PUBBLICAZIONI, TAB_SCARICATI,
                            TAB_VIDEO, TAB_AUDIO):
            self._visibilita()
            self._riempi_griglia()
            # Lasciare che Qt ridisegni prima di tornare: il riempimento della
            # griglia con centinaia di card e' il pezzo che sembrava a scatti.
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().processEvents()
            return

        self._visibilita()

        if not self._voci:
            self.conteggio.setText("")
            # I DUE STATI PRIMA DI «NON C'E' NIENTE»
            # -----------------------------------------
            # Senza rete la lista e' vuota, ma «non c'e' niente» e' una bugia:
            # e' una domanda senza risposta, non una risposta.  Quindi se la
            # richiesta e' in corso o e' fallita si dice quello che sta
            # succedendo, e la frase sulla categoria resta per quando la
            # risposta e' arrivata davvero ed era vuota.
            if self._in_corso:
                self._colonna.addWidget(self._messaggio(
                    "Sto chiedendo al server..."))
                return
            if self._errore:
                self._colonna.addWidget(self._messaggio(self._errore))
                return
            # Il messaggio dice sempre WHICH pubblicazione, se c'e'.  Un
            # "scegli una pubblicazione" quando la sezione ne sa gia' una
            # e' una richiesta che non si puo' fare, e sembra un errore.
            #
            # Con una categoria scelta il messaggio e' un altro: non e' che
            # manca una pubblicazione da scegliere, e dirlo sarebbe
            # sbagliato — l'utente ha premuto una linguetta e quella ha
            # funzionato.
            if self._categoria:
                self._colonna.addWidget(self._messaggio(
                    f"«{self._nome_categoria(self._categoria)}» non ha media da mostrare."))
                return
            if self._pubblicazione:
                testo = (f"Non ci sono media per "
                         f"{self._titolo_pubblicazione or self._pubblicazione}.")
            else:
                testo = ("Scegli una pubblicazione dalla sezione "
                         "Pubblicazioni: i suoi media si vedranno qui.")
            self._colonna.addWidget(self._messaggio(testo))
            return

        # CON UNA CATEGORIA DEL MEDIATOR SI FILTRA LO STESSO
        # -----------------------------------------------------
        # Qui il commento diceva che «le voci del mediator sono gia' tutte
        # video» e quindi che dividere per scheda le avrebbe svuotate: era
        # vero quando l'unica categoria audio era `KingdomMelodies` e le
        # altre sei erano video, ma non e' piu' vero da quando sono state
        # aggiunte `VOXDramaticBibleReading` e `VOXDramas`.
        #
        # Il filtro e` `_quando_video`, che e' il posto unico, e vale anche
        # con una categoria scelta: e' li' che la categoria mista mostra 7
        # audio su Audio e 10 video su Video.
        voci = self._quando_video(self._voci)
        # quante sono in tutto, per il contatore: senza questo si direbbe
        # "3 media su 3" anche quando in elenco ce ne sono 300, e i due
        # numeri non si capirebbero quale sia l'uno e quale l'altro.
        quante_in_elenco = len(self._voci)
        self._aggiorna_conteggio(len(voci), quante_in_elenco)

        if self._categoria:
            righe = 0
            for voce in voci:
                if not voce.get("title"):
                    continue
                riga = _RigaMedia(voce, self._lista)
                riga.scelto.connect(self._riproducci)
                self._colonna.addWidget(riga)
                righe += 1
            if righe == 0:
                # Si riusa `_messaggio`, che c'e' gia' in questa classe: un
                # secondo posto per l'etichetta "non c'e' niente" e' un
                # secondo posto dove i due messaggi divergono.
                #
                # Il testo distingue i due vuoti: la ricerca che non trova
                # niente e' una cosa diversa da una categoria senza media,
                # e senza dire quale delle due sia l'utente non sa se ha
                # sbagliato a scrivere.
                if self._testo_cercato:
                    testo = (f"Niente per «{self.cerca.text().strip()}» "
                             f"in questa categoria.")
                else:
                    testo = (f"«{self._nome_categoria(self._categoria)}» non ha media da mostrare.")
                self._colonna.addWidget(self._messaggio(testo))
            self._colonna.addStretch(1)
            return

        righe = 0
        gruppi: dict[str, list] = {}
        for voce in voci:
            # Solo i media veri.  Un PDF o un ZIP non sono un audio, e
            # metterli in elenco non e' "aumentare le voci": e' mettere
            # file che non si possono ascoltare dove l'utente cerca
            # cose da ascoltare.
            if not _e_video(voce) and not _e_audio(voce):
                continue
            chiave = voce.get("gruppo") or ""
            gruppi.setdefault(chiave, []).append(voce)

        # LA SUDDIVISIONE
        # ---------------
        # Le righe si mettono sotto un titolo, e il titolo e' quello che
        # dice **cosa** sono.  Su 424 discorsi senza titolo ogni riga diceva
        # solo il proprio nome e non si capiva niente di quale argomento
        # fosse; col titolo si vede che il gruppo e' per materia, per anno o
        # per numero della rivista, e si capisce dove guardare.
        #
        # Con una sola voce o un solo gruppo il titolo non si mette: e'
        # rumore sopra una lista che si capisce da sola.
        mostrare_titoli = len(gruppi) > 1
        for chiave in sorted(gruppi, key=lambda c: (c == "", c)):
            voci_del_gruppo = gruppi[chiave]
            if mostrare_titoli and chiave:
                self._colonna.addSpacing(6)
                titolo = _TitoloGruppo(f"{chiave} ({len(voci_del_gruppo)})")
                self._colonna.addWidget(titolo)
            for voce in voci_del_gruppo:
                riga = _RigaMedia(voce, self._lista)
                riga.scelto.connect(self._riproducci)
                self._colonna.addWidget(riga)
                righe += 1
        if righe == 0:
            nome = self._titolo_pubblicazione or self._pubblicazione
            if nome:
                testo = (f"{nome} non ha {SCHEDE[self._scheda][0].lower()} "
                         f"da ascoltare o da guardare. "
                         f"I suoi file sono dentro il pacchetto, che si "
                         f"apre dalla sezione Pubblicazioni.")
            else:
                testo = ("Scegli una pubblicazione dalla sezione "
                         "Pubblicazioni: i suoi media si vedranno qui.")
            self._colonna.addWidget(self._messaggio(testo))

    def _messaggio(self, testo: str) -> QLabel:
        """Un'etichetta nuova, ogni volta.

        Non una messa da parte e riusata: quella dopo un po' non esiste
        piu', e il riusarla e' il crash qui sopra.
        """
        etichetta = QLabel(testo, self._lista)
        etichetta.setObjectName("vuoto")
        etichetta.setWordWrap(True)
        return etichetta

    # ------------------------------------------------------------------

    def imposta_pubblicazione(self, pub) -> None:
        """Si ricorda di quale pubblicazione si tratta, senza caricare.

        Serve perche' la sezione si costruisce all'avvio, quando non si
        sa ancora quale pubblicazione l'utente aprire'.  Il caricamento
        parte dopo, quando si apre la sezione o quando l'utente preme le
        cuffie nella fascia.
        """
        # L'oggetto Publication intero, non solo la sigla: senza l'oggetto
        # non si puo' chiedere se il pacchetto e' scaricato, e quindi
        # l'anteprima andrebbe sempre a cercarla in rete anche quando
        # l'immagine e' gia' sul disco.
        self._pub = pub
        self._pubblicazione = getattr(pub, "keySymbol", "")
        self._lingua = Lingua.da_numero(getattr(pub, "mepsLanguageId",
                                              Lingua.PREDEFINITA))
        self._titolo_pubblicazione = getattr(pub, "title", "") or self._pubblicazione

    def apri_pubblicazione(self, pub, scheda: int = 0) -> None:
        """Prepara e mostra i media di una pubblicazione, sulla scheda data.

        E' il metodo pubblico per quando la scelta arriva da un'altra
        sezione — i Preferiti della Home, la lista degli Scaricati — e non da
        una scelta fatta qui dentro.

        Perche' un metodo solo, e non tre chiamate dal chiamante
        ---------------------------------------------------------
        La sezione tiene due cose che solo lei sa: la lingua della
        pubblicazione (``imposta_pubblicazione`` la calcola dal
        ``mepsLanguageId``) e la scheda corrente.  Se il chiamante le
        impostasse per conto suo dovrebbe conoscere entrambe, e conoscerle
        male e' il modo normale che una sezione mostri la scheda sbagliata.

        L'ordine dentro e' obbligato: prima si prepara la pubblicazione, poi
        si carica, e solo dopo si sceglie la scheda.  Il caricamento chiama
        `_ricostruisci()`, che ridipinge tutto, quindi una scheda cambiata
        prima verrebbe persa al primo ridisegno — e il sintomo sarebbe che la
        scheda torna su Audio ogni volta che arriva qualcosa dal server.

        Il ``try`` copre la chiamata al server perche' questa funzione gira
        dentro un segnale Qt (il clic sulla riga), dove un'eccezione fa
        ``abort()`` senza lasciare nessuna traccia.
        """
        try:
            # Se l'utente era su una categoria del mediator, la scelta della
            # pubblicazione riporta alle due schede.  Senza, `carica()`
            # riempirebbe la lista della categoria con i media della
            # pubblicazione e le due schede resterebbero nascoste: la lista
            # e' quella giusta e non si puo' tornare indietro.
            self.torna_alla_pubblicazione()
            self.imposta_pubblicazione(pub)
            self.carica(self._pubblicazione, self._lingua)
            self._scegli_scheda(scheda)
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nell'aprire i media di una pubblicazione ⚠️")
            traceback.print_exc()

    def apri_e_suona(self, pub, traccia=None, scheda: int = 1) -> None:
        """Mostra i media di una pubblicazione **e fa partire una traccia**.

        E' quello che serve a una card: premendo il video si vuole vederlo,
        non vedere un elenco da cui ripremerlo.  La card dice **quale**
        traccia (``traccia``) e in che scheda guardarla (``scheda``: 0 audio,
        1 video); qui si apre la pubblicazione come sempre e si ricorda la
        richiesta.

        PERCHE' NON PARTE SUBITO
        ------------------------
        La lista dei media arriva dal server in un thread: al momento del clic
        non c'e' ancora nessuna voce da far partire.  Si mette da parte la
        richiesta in ``_da_suonare`` e la si consuma in ``_arrivato``, quando
        la lista e' pronta — vedi `_forse_suona`.

        Con ``traccia`` ``None`` si fa partire la **prima** della scheda: e'
        il caso di un Preferito di una pubblicazione intera, dove una traccia
        precisa non c'e' ma il video si vuole lo stesso.

        IL FILE GIA' SCARICATO VINCE SEMPRE
        -----------------------------------
        Non si sceglie qui fra file e rete: si passa la voce al lettore, e
        `Lettore.suona` guarda da solo se c'e' il file di quella traccia e
        suona quello.  La regola «scaricato = dal disco, non scaricato = dalla
        rete» sta in un posto solo, e questo non e' quel posto.
        """
        self._da_suonare = None
        self.apri_pubblicazione(pub, scheda)
        # Dopo `apri_pubblicazione`, e non prima: quella chiama `carica()`,
        # che azzera la lista e fa partire la richiesta al server, ma non
        # tocca `_da_suonare`.  Metterlo prima funzionerebbe lo stesso; qui
        # si legge meglio perche' la richiesta e' l'ultima cosa decisa.
        self._da_suonare = (traccia, scheda)

    @staticmethod
    def _voce_di_un_file(percorso, titolo: str) -> dict:
        """La voce di un file sciolto sul disco, con quello che e'.

        Tre campi, non due: `url`, `title` e **il formato**.  Il terzo e'
        quello che mancava, ed e' il motivo per cui questa funzione esiste
        invece di essere una riga dentro `suona_un_file`.

        L'estensione e' un fatto — e' scritta nel nome — e `MediaScaricati`
        conosce gia' quali sono quelle dei media.  Si riusa quella lista
        invece di scriverne una seconda: due elenchi di estensioni divergono,
        e quello che resta fuori dal secondo viene suonato come un audio
        quando e' un video.

        Il `mimetype` non e' decorativo: e' il primo indizio che
        `LettoreView._e_video` guarda, e senza il `tipo` e il `mimetype` un
        video scaricato non aggancia nessun riquadro e si vede solo la
        copertina.
        """
        from Utility import MediaScaricati

        testo = str(percorso)
        estensione = testo.rsplit(".", 1)[-1].lower() if "." in testo else ""
        formato = ("VIDEO" if f".{estensione}" in MediaScaricati._VIDEO
                   else "AUDIO")
        mimetype = {
            "mp4": "video/mp4", "m4v": "video/x-m4v", "mov": "video/quicktime",
            "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac",
        }.get(estensione, "")
        return {
            "url": testo,
            "title": titolo or testo,
            "formato": formato,
            "mimetype": mimetype,
            "tipo": "video" if formato == "VIDEO" else "audio",
        }

    def suona_un_file(self, percorso, titolo: str) -> None:
        """Il lettore suona un file sciolto, senza la lista dei media.

        ARRIVA DALLA SEZIONE SCARICATI
        -------------------------------
        Un video scaricato dalla nuvoletta di una card e' un **file sciolto**
        (``wsb_I_02_r720P.mp4``): non ha un pacchetto con le 165 tracce, e
        chiedere al server la lista dei media di `wsb` per poi far premere la
        traccia giusta sarebbe un passaggio in piu' per un file che si ha
        gia' in mano.

        Si va dritti al lettore con una voce che dice **che cosa e'**, non solo
        dove sta.  `Lettore.suona` distingue un percorso da un indirizzo, e
        `LettoreView.mostra` ci sta: `Mediator.scegli_risoluzione` non tocca
        una voce senza `risoluzioni`, e `pulsante_risoluzione` si mette la voce
        del motore (che resta questa).

        PERCHE' LA VOCE DEVE DIRE `formato` E `mimetype`
        --------------------------------------------------
        Prima la voce era `{"url": percorso, "title": titolo}`: due campi, e
        niente che dicesse se quel file e' un video o un audio.

        `LettoreView._e_video` guarda il `mimetype` e la risoluzione, e con
        una voce cosi' rispondeva «non e' un video» per **tutti** i file
        sciolti.  Il lettore allora non agganciava nessun riquadro video,
        chiamava `al_video(None)` e accanto al brano mostrava la copertina: un
        video scaricato e premuto dalla sezione Scaricati partiva **senza
        immagine**, e il sintomo era un lettore che sembra acceso ma e' fermo
        sul primo fotogramma.

        Il formato si legge dall'estensione, che e' sul disco ed e' un fatto:
        il chiamante non deve passarlo e non puo' sbagliarlo.
        """
        try:
            from PyQt6 import sip

            if sip.isdeleted(self):
                return
            self._lettore.mostra(self._voce_di_un_file(percorso, titolo))
        except Exception:  # noqa: BLE001
            import traceback
            print(f"Media: errore nel suonare il file {percorso} ⚠️")
            traceback.print_exc()

    # ------------------------------------------------------------------
    # IL LETTORE PUO' STARE FUORI DA QUESTA SEZIONE
    # ------------------------------------------------------------------
    #
    # Quando un video parte da un'altra sezione la finestra non cambia sezione:
    # chiede il lettore (sempre lo stesso, mai un secondo) e lo mette sopra la
    # schermata in cui si e' (`cedi_il_lettore`).  Quando si apre questa sezione
    # il lettore torna al suo posto (`riprendi_il_lettore`, dal `showEvent`).

    @property
    def lettore_fuori(self) -> bool:
        return self._lettore_fuori

    def cedi_il_lettore(self, disposizione) -> LettoreView:
        """Mette il lettore in ``disposizione`` (di un'altra schermata) e lo restituisce."""
        if not self._lettore_fuori:
            self._lettore_fuori = True
            self._handle.hide()
            disposizione.addWidget(self._lettore, 1)
        return self._lettore

    def riprendi_il_lettore(self) -> None:
        """Rimette il lettore nel suo posto, sopra la lista."""
        if self._lettore_fuori:
            self._lettore_fuori = False
            self.layout().insertWidget(0, self._lettore, 1)
            self._handle.show()

    def showEvent(self, evento) -> None:
        """La sezione appare: si chiedono i nomi delle categorie.

        Una volta sola per questa sezione: sei richieste piccole non sono
        un peso, e rifarle a ogni sguardo e' traffico senza motivo, perche' il
        nome di una categoria non cambia mentre la finestra e' aperta.

        LA GRIGLIA SI RIFAZE SE IL TEMA E' CAMBIATO
        ------------------------------------------
        Il foglio di stile ricolora da solo tutto quello che ha un nome di
        oggetto: le tab, la sfumata, il fondo delle celle.  Ma le **icone**
        sono un pixmap, e un pixmap ha il suo colore dentro come un file ha i
        suoi pixel: riapplicare il foglio di stile non lo cambia.

        Quindi senza questo controllo, cambiando tema con la sezione aperta le
        icone delle pubblicazioni resterebbero grigio scuro su fondo scuro,
        cioe' invisibili: e sparirebbero solo in scuro, che e' il difetto
        peggiore da andare a cercare.

        Si riface la griglia e non tutte le icone della finestra perche' qui
        si puo': sono dodici e un'icona da rifare costa un pixmap.  Nelle
        liste lunghe il conto e' un altro, e li' la cosa giusta non e' rifare
        tutto, ma non dipingere l'icona col colore del tema.
        """
        super().showEvent(evento)
        self.riprendi_il_lettore()
        chiaro = _tema_chiaro()
        if getattr(self, "_tema_della_griglia", None) != chiaro:
            self._tema_della_griglia = chiaro
            if self._scheda in (TAB_PUBBLICAZIONI, TAB_SCARICATI):
                self._riempi_griglia()
        if not getattr(self, "_nomi_chiesti", False):
            self._nomi_chiesti = True
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._chiedi_nomi)

    def ricarica_se_serve(self) -> None:
        """Carica, se c'e' una pubblicazione e se non e' gia' caricata.

        Il nome dice "se serve" perche' non ricarica ogni volta: il server
        risponde in qualche decimo di secondo e una sezione che si
        ricarica a ogni sguardo fa traffico inutile.
        """
        if not self._pubblicazione:
            return
        if self._voci and self._caricata == self._pubblicazione:
            return
        self.carica(self._pubblicazione, self._lingua or Lingua.corrente_simbolo())

    def riapre_il_lettore(self) -> None:
        """La freccia su' della striscia: torna qui il lettore grande.

        NON RIPARTE NULLA E NON SI RICOLLEGA NULLA
        -------------------------------------------
        Il brano sta gia' suonando e il video e' rimasto agganciato al suo
        riquadro per tutto il tempo in cui il lettore era abbassato: qui basta
        **mostrarlo**.  Non si chiama `mostra`, non si chiama `carica`, e non si
        tocca il motore.

        E' la parte che rende possibile tutta la freccia gi'.  Se per riaprire
        si fosse richiamato `mostra`, il brano ripartirebbe da capo: un click,
        la posizione azzerata, e chi stava ascoltando da due minuti dovrebbe
        cercare di nuovo il punto in cui era.

        Se non c'e' niente che suoni — l'utente ha premuto la X un secondo fa —
        non si fa niente e la sezione resta com'e'.
        """
        if self._lettore is None:
            return
        from Utility import Lettore
        if not Lettore.motore().sorgente():
            return
        self._lettore.alza()

    def carica(self, sigla: str, lingua: str | None = None) -> None:
        """Chiede al server i media di una pubblicazione.

        Senza `lingua` si usa quella scelta dall'utente, e non la lettera "I":
        un valore predefinito viene calcolato quando il modulo viene importato,
        quindi "I" significherebbe "italiano per sempre".

        Non blocca: parte in background e la lista si riempie quando
        arrivano.  Una risposta con 165 tracce sono 128 KB, e aspettarli
        sul main thread significa una finestra ferma.
        """
        if not lingua:
            lingua = Lingua.corrente_simbolo()
        self._pubblicazione = sigla
        self._caricata = sigla
        self._voci = []
        self._righe_pronte: set[int] = set()
        self._errore = ""
        self._in_corso = sigla
        on_main(self._ricostruisci)

        from Utility.Extensions.Ext_DispatchQueue import background

        risultato: list = []
        fallito: list = []

        def lavoro() -> None:
            # NON PUO' RESTITUIRE: completion viene chiamata senza
            # argomenti, quindi il valore di ritorno di `lavoro` va da
            # nessuna parte e la lista resterebbe vuota.  Il risultato
            # passa per `risultato`, che il thread riempie e il main
            # thread legge: e' sicuro perche' fra le due c'e' il
            # segnale, che e' una coda.
            try:
                risultato.extend(MepsAPI.media(sigla, lingua))
            except Exception as errore:  # noqa: BLE001
                fallito.append(str(errore))

        background(lavoro, completion=lambda: self._arrivato(risultato, sigla,
                                                            fallito))

    def _arrivato(self, voci: list, sigla: str, fallito: list | None = None) -> None:
        """I media sono arrivati, o non sono arrivati niente.

        Due controlli, in quest'ordine, e sono entrambi necessari.

        Il primo: l'oggetto puo' non esistere piu'.  La risposta arriva in
        background e la sezione puo' essere stata distrutta nel frattempo
        — la finestra la distrugge quando si cambia sezione o si preme
        Aggiorna.  Toccarla allora da:

            RuntimeError: wrapped C/C++ object of type MediaView
            has been deleted

        Il secondo: mentre si aspettava, l'utente puo' aver scelto un'altra
        pubblicazione.  Se il risultato non viene buttato, la lista mostra
        i media di una pubblicazione mentre il titolo dice un'altra: e il
        peggiore dei difetti, perche' sembra tutto funzionare.
        """
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        if sigla != self._pubblicazione:
            return
        self._in_corso = ""
        try:
            if fallito:
                # Come per le categorie: il fatto si scrive nella lista, dove
                # l'utente ha guardato, e non in un dialog che blocca la
                # finestra.  Prima qui finiva solo in terminale
                # (`print`), quindi senza rete la sezione semplicemente
                # restava vuota e sembrava una pubblicazione senza media.
                self._errore = ("Non riesco a raggiungere il server. "
                                "I media si vedranno quando la connessione "
                                "torna.")
                self._voci = []
                on_main(self._ricostruisci)
                return
            self._errore = ""
            # Si tengono TUTTE le voci, non solo i media: la sezione
            # filtra quando disegna, e cosi' un file che domani verra'
            # classificato come media non ha bisogno di nessuna modifica
            # qui.  buttare via le altre sarebbe una decisione presa al
            # posto sbagliato.
            # Le tracce pero' si raggruppano: una voce per traccia con
            # dentro le sue risoluzioni, con l'indirizzo in `url` e la
            # `sigla`.  Senza, la stessa lezione compariva una volta per
            # risoluzione e nessuna riga partiva.  Vedi `_raggruppa_tracce`.
            self._voci = _raggruppa_tracce(voci, sigla)
            on_main(self._ricostruisci)
            self._chiedi_antprime()
            # Una card premuta ha chiesto una traccia precisa: ora che la
            # lista c'e' la si fa partire.  Su `on_main` come
            # `_ricostruisci`: questo metodo gira nel thread della risposta, e
            # far partire un video tocca i widget — che si toccano solo dal
            # thread principale.  Vedi `apri_e_suona`.
            on_main(self._forse_suona)
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nel mostrare i media ⚠️")
            traceback.print_exc()

    def _chiedi_antprime_categorie(self) -> None:
        """L'immagine delle **card di categoria**, in un thread.

        LE CARD DI CATEGORIA NON HANNO UNA VOCE
        ---------------------------------------
        `_chiedi_antprime` lavora sulle voci dei media, e una card di categoria
        non ne ha: e' una scelta, non un pezzo di contenuto.  Quindi senza
        questa funzione la sua immagine non sarebbe mai chiesta, e la card
        resterebbe col glifo per sempre — anche per «Melodie del Regno», che
        e' l'unica categoria con un'immagine sul server.

        Il posto e' lo stesso di `_chiedi_antprime` e non un altro, perche' il
        punto da cui parte la richiesta e' gia' `_chiedi_altre_copertine`:
        due punti significherebbero che la seconda meta' delle immagini non
        viene chiesto quando la griglia si ridisegna, ed e' gia' successo
        con le copertine delle pubblicazioni.

        Non si finge: se il server non ha un'immagine per quella categoria
        non viene chiesto niente e la card mostra il glifo, che e' la verita'.
        """
        if self._antprime_cat_in_corso:
            return
        mancanti = []
        for chiave in self._antprime_cat_chiavi:
            if self._antprime_cat_fatte.get(chiave):
                continue
            for indirizzo in Mediator.immagini_categoria_gia_note(chiave, self._lingua):
                if not Copertine.mancante(indirizzo):
                    mancanti.append((chiave, indirizzo))
                    break
        if not mancanti:
            return

        self._antprime_cat_in_corso = True
        risultato: list = []

        def lavoro() -> None:
            from concurrent.futures import ThreadPoolExecutor

            def uno(coppia):
                try:
                    return (coppia[0], Copertine.scarica(coppia[1]))
                except Exception:  # noqa: BLE001 - un'immagine mancante e' un glifo
                    return (coppia[0], None)
            with ThreadPoolExecutor(max_workers=6) as piscina:
                risultato.extend(piscina.map(uno, mancanti))

        def finito() -> None:
            self._antprime_cat_in_corso = False
            try:
                from PyQt6 import sip

                if sip.isdeleted(self):
                    return
                for chiave, dati in risultato:
                    # Si segna come fatta **anche** se non e' arrivata: e' il
                    # modo che ha il server di dire che quell'immagine non
                    # esiste, e senza questo si chiederebbe a ogni ridisegno.
                    self._antprime_cat_fatte[chiave] = bool(dati)
                if any(d for _c, d in risultato):
                    self._ricostruisci()
            except Exception:  # noqa: BLE001
                import traceback
                print("Media: errore nelle immagini delle categorie ⚠️")
                traceback.print_exc()

        from Utility.Extensions.Ext_DispatchQueue import background

        background(lavoro, completion=finito)

    def _chiedi_antprime(self) -> None:
        """Le anteprime dei media, in un thread, a pezzi.

        IL PACCHETTO PRIMA, SEMPRE
        --------------------------
        `Copertine.locandina_del_media` prova prima dentro il pacchetto
        scaricato e dalla rete solo dopo.  Non si duplica quella scelta
        qui: se la si riscrivesse, i due punti comincerebbero a dare
        risultati diversi e non si saprebbe quale ha ragione.

        A PEZZI, E NON TUTTE IN UNA VOLTA
        ---------------------------------
        Prima se ne chiedevano 30, una volta sola, quando la categoria
        arrivava.  Su «Melodie del Regno» sono 109: le prime 30 avevano la
        copertina e le altre 79 no, e **non le chiedeva piu' neppure
        scorrendo** — la griglia si riempiva di schede con il glifo, che e'
        il difetto segnalato come «manca il riquadro di anteprima».

        Il pezzo e' dimensionato come quello delle pubblicazioni: tre colonne
        per sette righe, calcolate sulla larghezza vera della griglia.  Il
        doppio di `righe + 1` di `_chiedi_copertine`, perche' qui un'immagine
        senza testo accanto non si legge come «non caricata»: e' un quadrato
        grigio accanto a un titolo che si vede benissimo, e si nota subito.

        E POI? SI RIPETE FINCHE' CE N'E' BISOGNO
        ----------------------------------------
        `_antprime_arrivate` non finisce: chiama di nuovo questa funzione
        per il pezzo dopo.  Il ciclo si ferma da solo perche' una voce che ha
        gia' l'immagine viene saltata, e una il cui indirizzo non esiste viene
        saltata perche' `Copertine.mancante` dice che ha gia' risposto no.

        Il risultato passa per una lista che il thread riempie e il main
        thread legge: e' sicuro perche' fra le due c'e' un segnale, che e'
        una coda.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        if self._antprime_in_corso:
            return
        # LE VOCI SONO QUELLE CHE SI VEDONO, E NON QUELLE CHE ESISTONO
        # ------------------------------------------------------------
        # `_quando_video` e' il posto unico in cui si decide cosa si vede:
        # dentro ci passa anche la ricerca.  Prima qui la scelta era riscritta,
        # e con una categoria scelta non si filtrava affatto — quindi su un
        # brano della scheda Audio si chiedevano immagini di video, che non
        # ci sono, e la card restava col glifo.
        voci = self._quando_video(self._voci)
        voci = [v for v in voci if self._manca_ancora(v)]
        if not voci:
            return
        pub = getattr(self, "_pub", None)
        # Il pezzo, dalla larghezza vera della griglia: come in
        # `_chiedi_copertine`, con due righe in piu' per quello che sta
        # arrivando sotto mentre il thread lavora.
        larghezza = max(self._griglia.width(), CELLA_LARGA)
        colonne = max(1, larghezza // (CELLA_LARGA + 4))
        prime = voci[:colonne * (7 + 1)]

        self._antprime_in_corso = True
        risultato: list = []

        def lavoro() -> None:
            from concurrent.futures import ThreadPoolExecutor

            def uno(voce):
                try:
                    return (id(voce),
                            Copertine.locandina_del_media(voce, pub=pub, rapida=True))
                except Exception:  # noqa: BLE001 - una locandina non e' un guasto
                    # Una locandina che non si puo' chiedere non ferma le altre,
                    # ma **si dice**: altrimenti il difetto si vede come «le
                    # immagini non arrivano» e non come «una richiesta e'
                    # fallita», che sono due bug diversi.
                    print(f"Locandina {voce.get('title', '?')[:40]!r} non "
                          f"arriva ⚠️")
                    return (id(voce), None)

            # Sei thread, come per le copertine: il collo di bottiglia non e'
            # la banda, sono i giri di andata e ritorno, e con venti thread si
            # guadagna poco e si rischia che il server scarti qualche richiesta
            # perche' sono troppe connessioni aperte insieme.
            from concurrent.futures import as_completed
            with ThreadPoolExecutor(max_workers=6) as piscina:
                for futuro in as_completed([piscina.submit(uno, v) for v in prime]):
                    riga = futuro.result()
                    risultato.append(riga)
                    # Una per una appena pronta: non si aspetta l'ultima del pezzo.
                    on_main(lambda r=riga: self._antprime_arrivate([r], continua=False))

        def finito() -> None:
            self._antprime_in_corso = False
            self._antprime_arrivate(risultato)

        background(lavoro, completion=finito)

    def _manca_ancora(self, voce: dict) -> bool:
        """Questa voce ha ancora bisogno dell'immagine?

        Tre no' in tre punti, e senza nessuno dei tre il ciclo continua
        perche': una voce che ha gia' l'immagine verrebbe richiesta di
        nuovo, e una il cui indirizzo non esiste verrebbe richiesta per
        sempre senza ricevere mai niente.

        1. ha gia' la pixmap, o e' gia' stata sistemata in questa sessione:
           non si cerca due volte la stessa cosa.  Il secondo caso serve per
           le voci **senza card a schermo**: l'immagine e' in cache, e senza
           questo segno il ciclo continuerebbe anche se non ha piu' niente
           su cui metterla;
        2. non ha nessun indirizzo: non c'e' niente da chiedere;
        3. l'indirizzo ha gia' risposto 403 o 404: `Copertine` se lo
           ricorda per tutta la sessione, e ripeterlo non cambierebbe.
        """
        if voce.get("_anteprima") is not None:
            return False
        if id(voce) in self._antprime_fatte:
            return False
        indirizzi = Copertine.indirizzi_del_media(voce)
        if not indirizzi:
            return False
        # Se sono tutte gia' segnate come inesistenti non c'e' niente da
        # chiedere: `Copertine` le ricorda per tutta la sessione, e senza
        # questo controllo il ciclo girerebbe per sempre su voci che non
        # avranno mai un'immagine.
        return any(not Copertine.mancante(i) for i in indirizzi)

    def _antprime_arrivate(self, trovate: list, continua: bool = True) -> None:
        """Le anteprime sono arrivate: vanno sulle card di adesso.

        SULLA CARD, E NON CON UN RIFACIMENTO DELLA GRIGLIA
        ---------------------------------------------------
        Prima scriveva l'immagine dentro la voce e chiamava `_ricostruisci`,
        cioe' buttava via tutte le card e le ricostruiva.  Su una categoria
        come «Melodie del Regno» — 109 card, 6 pezzi da 24 — ogni pezzo che
        arrivava rifaceva tutta la griglia: venti volte la costruzione di 109
        widget, mentre l'utente guarda.  La finestra andava a scatti proprio
        mentre le immagini arrivavano, cioe' nel momento in cui non deve.

        `_chiedi_copertine` mette l'immagine sulla card che c'e' adesso, e
        funziona: si prende la cella, si chiama `metti_immagine`, e la cella
        si ridisegna da sola.  Qui si fa lo stesso, cercando la card dalla
        **voce** invece che dall'id della pubblicazione.

        E POI SI CHIEDE IL PEZZO DOPO
        -----------------------------
        Senza, si avrebbero le prime 24 immagini e il resto glifi per sempre:
        il difetto segnalato come «manca il riquadro di anteprima».  Il ciclo
        si chiude da solo — vedi `_manca_ancora` — e si ferma anche se il
        widget non c'e' piu': in quel caso l'immagine e' comunque in cache e
        la prossima volta che la sezione si apre la card la trova subito.
        """
        from PyQt6 import sip
        from Utility.Copertine import pixmap_da_dati

        if sip.isdeleted(self):
            return
        try:
            per_id = {id(v): v for v in self._voci}
            # Le card di **adesso**: la griglia e' stata ricostruita nel
            # frattempo e quelle di quando la richiesta e' partita non
            # esistono piu'.  Lo stesso motivo di `_chiedi_copertine`.
            celle = {}
            for elemento in self._griglia._flusso._voci:
                widget = (elemento.widget() if hasattr(elemento, "widget")
                          else None)
                if not isinstance(widget, _Cella):
                    continue
                voce = widget.cosa.get("voce")
                if isinstance(voce, dict):
                    celle[id(voce)] = widget

            # La `QPixmap` si costruisce qui, non nel thread: e' un oggetto
            # grafico e va creato dove c'e' la `QApplication`.
            fatte = set()
            for identificatore, dati in trovate:
                if not dati or identificatore in self._antprime_fatte:
                    continue
                voce = per_id.get(identificatore)
                if voce is None:
                    continue
                # La voce conta come sistemata anche se la card non c'e' piu':
                # l'immagine e' in cache, e senza questo segno il ciclo
                # continuerebbe a chiederla per sempre anche quando non ha
                # piu' nessuna card a cui metterla.
                fatte.add(identificatore)
                cella = celle.get(identificatore)
                if cella is None or sip.isdeleted(cella):
                    continue
                immagine = pixmap_da_dati(dati)
                if immagine is None or immagine.isNull():
                    continue
                cella.metti_immagine(immagine)
            self._antprime_fatte |= fatte
            # Il pezzo dopo, e si ferma quando non manca piu' niente.
            if continua:
                self._chiedi_antprime()
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nel mettere le anteprime ⚠️")
            traceback.print_exc()

    def _riproducci(self, voce) -> None:
        """Fa partire la voce nel lettore.

        LA PRIMA VERSIONE
        -----------------
        La prima versione diceva solo "il lettore non e' ancora collegato", il
        che era giusto come metodo ma non come programma: un pulsante che si
        preme e dice che non fa niente e' il peggio che ci sia, perche'
        sembra rotto invece che non costruito.

        Adesso il lettore sta sopra la lista e la lista resta sotto.  Si vede
        che cosa hai scelto e si puo' scegliere altro senza chiudere niente,
        che e' quello che serve quando una sezione ha 424 voci.

        IL `try` PERCHE' IL CLICK E' UN SEGNALE QT
        -----------------------------------------
        Un'eccezione dentro un segnale Qt fa `abort()` e non lascia nessuna
        riga di traceback: la finestra sparisce.  Vale anche per i pulsanti
        del lettore, che sono segnali come gli altri.
        """
        try:
            self._lettore.mostra(voce)
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nel far partire un media ⚠️")
            traceback.print_exc()

    def suona_traccia(self, sigla: str, lingua: str, traccia: int, scheda: int,
                      ripiego) -> None:
        """Fa partire una traccia chiedendo al server **solo quella**.

        `apri_e_suona` carica la pubblicazione intera (su `sjjm` quasi 2.000 voci,
        5 secondi) per poi cercarci dentro una traccia.  Qui la risposta e' di
        poche voci.  Se non arriva niente (rete, traccia sconosciuta) si chiama
        ``ripiego``, che e' la strada lunga di sempre.
        """
        from Utility.Extensions.Ext_DispatchQueue import background

        trovate: list = []

        def lavoro() -> None:
            try:
                trovate.extend(_raggruppa_tracce(
                    MepsAPI.media(sigla, lingua, traccia=traccia), sigla))
            except Exception:  # noqa: BLE001
                pass

        def pronto() -> None:
            from PyQt6 import sip

            if sip.isdeleted(self):
                return
            voce = next((v for v in trovate
                         if MepsAPI.traccia_numero(v) == int(traccia)
                         and (_e_video(v) if scheda == 1 else _e_audio(v))), None)
            if voce is None:
                ripiego()
                return
            self.staPerSuonare.emit()
            QTimer.singleShot(0, lambda: None if sip.isdeleted(self) else self._riproducci(voce))

        background(lavoro, completion=pronto)

    def _voce_di_una_traccia(self, traccia, scheda: int):
        """La voce della traccia richiesta in questa scheda, o None.

        Con ``traccia`` ``None`` si prende la **prima** della scheda: e' il
        caso di un Preferito di una pubblicazione intera.

        A pari traccia la voce e' gia' una sola — `_raggruppa_tracce` mette le
        risoluzioni dentro la voce invece di fare piu' voci — ma fra video e
        audio della stessa traccia si sceglie guardando la scheda, non
        prendendo la prima che capita.  La scheda e' quello che l'utente sta
        guardando, ed e' l'unico indizio che dice cosa voleva.
        """
        vuole_video = scheda == 1
        candidate = [v for v in self._voci
                     if (_e_video(v) if vuole_video else _e_audio(v))]
        numero = None
        if traccia not in (None, "", 0):
            try:
                numero = int(traccia)
            except (TypeError, ValueError):
                numero = None
        if numero is not None:
            candidate = [v for v in candidate
                         if MepsAPI.traccia_numero(v) == numero]
        if not candidate:
            return None
        return candidate[0]

    def _forse_suona(self) -> None:
        """Se una card ha chiesto una traccia e la lista c'e', la fa partire.

        Si consuma la richiesta in ogni caso: se la traccia non c'e' — una
        voce diversa, un errore del server — non si riprova a ogni ridisegno,
        che farebbe ripartire il video da solo mentre l'utente legge.
        """
        from PyQt6 import sip

        # La risposta arriva quando la sezione puo' essere gia' stata
        # distrutta (si e' cambiata sezione mentre caricava): toccarla allora
        # da «wrapped C/C++ object ... has been deleted».  Come in
        # `_ricostruisci`, che si difende allo stesso modo.
        if sip.isdeleted(self):
            return
        richiesta = self._da_suonare
        if not richiesta:
            return
        self._da_suonare = None
        self.staPerSuonare.emit()
        # Con una categoria del mediator la lista non e' di una
        # pubblicazione, e la traccia non c'e': non si suona niente.
        if self._categoria or not self._voci:
            return
        try:
            traccia, scheda = richiesta
            voce = self._voce_di_una_traccia(traccia, scheda)
            if voce is not None:
                # Un giro di eventi dopo il cambio di sezione: cosi' il lettore
                # misura la casella gia' al suo posto e sceglie la risoluzione giusta.
                QTimer.singleShot(0, lambda v=voce: (
                    None if sip.isdeleted(self) else self._riproducci(v)))
        except Exception:  # noqa: BLE001
            import traceback
            print("Media: errore nel far partire la traccia della card ⚠️")
            traceback.print_exc()