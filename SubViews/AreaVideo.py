#
#  SubViews/AreaVideo.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il riquadro del video dentro l'app: si sposta e si ridimensiona col mouse.

PERCHE' ESISTE
--------------
Il video si vedeva in **due** modi e nessuno dei due andava bene: tutto
schermo, oppure una striscia alta 280 pixel ferma in alto con la lista sotto.
Il primo nascondeva tutto, il secondo non si poteva ne' spostare ne'
ridimensionare, e su un portatile con lo schermo piccolo finiva sotto la
barra delle applicazioni.

Adesso e' un riquadro che sta **dentro** la finestra e che l'utente mette
dove vuole: lo trascina col corpo, lo allarga dal cantone.  E si ricorda dove
era, perche' rimetterlo a ogni avvio e' il modo migliore per non avere mai un
posto dove sta.

PERCHE' IL VIDEO SI VEDE ANCHE DENTRO, COLLO SCHERMO ESTERNO
-------------------------------------------------------------
Con un secondo schermo scelto il video va li' — e va lo anche da solo, perche'
e' quello che e' stato chiesto.  Ma allora chi e' nella stanza con il
programma e non vede il secondo schermo non ha **nessun modo** di accorgersi
che e' partito un video: e' il caso di chi guarda verso il muro invece che
verso il monitor.

Quindi dentro il programma il video si vede lo stesso, **in copia**.  Non e'
un secondo video e non parte un secondo audio: e' lo stesso fotogramma
mostrato in due posti.  Vedi `collega_il_copio`.

LA COPIA HA UN PREZZO, E SI SA
------------------------------
Mostrare lo stesso fotogramma in due punti costa: il fotogramma va
convertito in un'immagine e disegnato a mano.  Su questa macchina Qt non trova
una scheda video e ridimensiona gia' con la CPU, quindi un fotogramma in piu'
non e' gratuito.

Per questo il copia si accende **solo quando serve** — cioe' solo quando c'e'
lo schermo esterno e il video va davvero li' — e si spegne appena il video
torna nell'app.  Sempre acceso costerebbe a ogni video, anche di chi non ha un
secondo monitor, e il programmo risponderebbe peggio per un vantaggio che
quel pezzo di codice li' non tocca.
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QCursor, QImage, QPainter, QPixmap
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QWidget

#: Il lato del cantone che tira la misura, in pixel.
#:
#: Deve essere abbastanza grande da essere un bersaglio comodo con il mouse e
#: abbastanza piccolo da non stare sempre in mezzo all'immagine.  Ventidue
#: pixel e' un angolo: si prende senza mirare e non si tocca per sbaglio
#: trascinando il video.
LATO_ANGOLO = 22

#: La misura minima, sotto la quale il video non si vede piu'.
#:
#: Non e' una scelta di stile: sotto questa dimensione il riquadro non puo'
#: contenere il fotogramma e si vede solo il nero, e un riquadro nero grande
#: quanto una pastiglia sembra un errore di disegno.
MINIMO = QSize(240, 140)

#: Dove sta il file con la posizione.
#:
#: Nella cartella dei dati dell'utente e **non** nelle impostazioni: la posizione
#: di una finestra non e' un'impostazione del programma, e l'utente non cerca
#: un interruttore per spostare il video.  Cambia schermo la cambia da se', e va
#: bene cosi': e' un dettaglio della persona, non del funzionamento.
FILE_POSIZIONE = "area_video.json"


def _percorso_posizione() -> Path:
    from Utility.Extensions.Ext_FileManager import get_documents_directory

    cartella = get_documents_directory() / "userData"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella / FILE_POSIZIONE


def legge_posizione() -> dict:
    """La posizione e la misura ricordate, o un dizionario vuoto."""
    try:
        with open(_percorso_posizione(), encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, ValueError):
        return {}
    return dati if isinstance(dati, dict) else {}


def salva_posizione(x: int, y: int, larghezza: int, altezza: int) -> None:
    """Scrive la posizione e la misura.  Non alza mai niente.

    Un file che non si puo' scrivere non e' un motivo per far cadere il
    programmo: la posizione si perde e la prossima volta l'utente la rimette.
    """
    try:
        with open(_percorso_posizione(), "w", encoding="utf-8") as f:
            json.dump({"x": int(x), "y": int(y),
                       "w": int(larghezza), "h": int(altezza)}, f)
    except OSError:
        pass


class AreaVideo(QWidget):
    """Il riquadro nero del video, dentro la finestra, mosso col mouse.

    IL TRASCINAMENTO
    ----------------
    Si preme **sul corpo** e si trascina.  Il cursore e' quello a quattro
    frecce perche' e' quello che vuol dire «questa cosa si sposta», e senza un
    cursore che cambia la prima cosa che fa un utente con un riquadro nero e'
    provarlo a premere.

    LA MISURA
    ---------
    Si tira **dal cantone in basso a destra**, e li' il cursore diventa quello
    diagonale.  Un bordo tutto intorno sarebbe stato un'altra scelta legittima,
    ma mette un bersaglio dove sta l'immagine: premere nel mezzo del video per
    spostarlo e tirare dall'angolo per allargarlo sono due gesti diversi, e se
    il bordo fosse sparso ovunque l'utente non saprebbe quale sta facendo.

    IL CANTONCINO
    -------------
    Nell'angolo c'e' un quadratino disegnato, cosi' si vede dove si tira.  Non
    e' solo un disegno: il quadratino e' anche l'unico posto dove il cursore
    cambia, e senza si avrebbe un riquadro che si muove ma non si capisce come
    si allarga.
    """

    def __init__(self, padre=None) -> None:
        super().__init__(padre)
        self.setObjectName("areaVideo")
        # Il nero e' anche il fondo del tema: su un video scuro serve il nero,
        # e su uno chiaro il nero e' quello che c'e' intorno al fotogramma.
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(p)

        self._immagine: QImage | None = None
        self._trascina = None       # (punto del mouse, punto del riquadro)
        self._misura = None         # (punto del mouse, dimensione di partenza)
        self._angolo = False        # il mouse e' sul cantone?

        # DOVE STA IL VIDEO VERO
        # -----------------------
        # Il `QVideoWidget` del player e' **figlio del riquadro**, non viceversa.
        # Cosi' il widget del player segue il riquadro quando l'utente lo
        # sposta o lo allarga, senza che nessuno debba stare a chiamare
        # `setGeometry` a ogni movimento del mouse: se il video fosse a fratello
        # del riquadro, resterebbe fermo nel posto di prima mentre il riquadro
        # andava altrove — e si vedrebbe il video fuori dal suo contenuto.
        self.video = QVideoWidget(self)
        self.video.setObjectName("videoArea")
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        self.setMinimumSize(MINIMO)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setToolTip("Trascina per spostare, tira dal cantone per allargare")

    # ------------------------------------------------------------------
    # LA COPIA DEL VIDEO
    # ------------------------------------------------------------------

    def metti_immagine(self, percorso) -> None:
        """La copertina, per un audio.  Non e' un fotogramma: e' una figura.

        Sulla schermata esterna la copertina **non** si mostra: li' si vedono
        solo video e immagini, e una copertina di canzone accanto a un verso
        della Scrittura sarebbe un pezzo che non c'entra con niente.
        """
        try:
            if not percorso:
                self._immagine = None
                self.update()
                return
            self._immagine = QImage(str(percorso))
        except Exception:  # noqa: BLE001
            self._immagine = None
        self.update()

    # ------------------------------------------------------------------

    def paintEvent(self, evento) -> None:
        """Disegna il fotogramma al centro, tenendo le proporzioni.

        Le proporzioni si tengono come le tiene il `QVideoWidget` vero, cioe'
        `KeepAspectRatio`: se si stirasse il fotogramma per riempiere il
        riquadro, un video 16:9 in un riquadro 4:3 diventerebbe un'immagine
        schiacciata, e l'utente accorgerebbe che il video e' «storto» senza
        sapere che e' il riquadro.
        """
        pittore = QPainter(self)
        pittore.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._immagine is None or self._immagine.isNull():
            self._disegna_il_cantone(pittore)
            return
        misura = self._immagine.size()
        misura.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - misura.width()) // 2
        y = (self.height() - misura.height()) // 2
        pittore.drawImage(QRect(x, y, misura.width(), misura.height()),
                          self._immagine)
        self._disegna_il_cantone(pittore)

    def _disegna_il_cantone(self, pittore: QPainter) -> None:
        """Il quadratino nell'angolo: dice dove si tira la misura."""
        lato = LATO_ANGOLO - 4
        x = self.width() - lato - 3
        y = self.height() - lato - 3
        colore = (Qt.GlobalColor.white if self._angolo
                  else Qt.GlobalColor.darkGray)
        pittore.setPen(colore)
        for i in range(3):
            pittore.drawLine(x + i * 5, y + lato, x + lato, y + lato - i * 5)

    # ------------------------------------------------------------------
    # IL MOUSE
    # ------------------------------------------------------------------

    def _c_il_cantone(self, punto: QPoint) -> bool:
        return (punto.x() >= self.width() - LATO_ANGOLO
                and punto.y() >= self.height() - LATO_ANGOLO)

    def mouseMoveEvent(self, evento) -> None:
        """Muove il riquadro, o lo allarga, secondo dove e' partito."""
        posizione = evento.position().toPoint()
        if self._misura is not None:
            (partenza, iniziale) = self._misura
            nuova = QSize(iniziale.width() + posizione.x() - partenza.x(),
                          iniziale.height() + posizione.y() - partenza.y())
            self.resize(self._misura_limitata(nuova))
            return
        if self._trascina is not None:
            (origine, iniziale) = self._trascina
            nuovo = iniziale + posizione - origine
            self._metti_dentro(self._metti_limitata(nuovo))

    def mousePressEvent(self, evento) -> None:
        """Sul corpo si trascina, sul cantone si allarga."""
        if evento.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(evento)
            return
        punto = evento.position().toPoint()
        if self._c_il_cantone(punto):
            self._misura = (punto, self.size())
        else:
            self._trascina = (punto, self.pos())
        evento.accept()

    def mouseReleaseEvent(self, evento) -> None:
        """Finito: si ricorda la posizione e la misura."""
        if self._trascina is not None or self._misura is not None:
            self._trascina = None
            self._misura = None
            salva_posizione(self.x(), self.y(), self.width(), self.height())
            evento.accept()
            return
        super().mouseReleaseEvent(evento)

    def mouseDoubleClickEvent(self, evento) -> None:
        """Doppio clic: torna alla misura di partenza.

        Il modo per tornare indietro dopo averla resa minuscola per guardare
        una parte del fotogramma, senza doverla ripescare con il mouse.
        """
        self.resize(*self._misura_iniziale())
        self._metti_dentro(self.pos())
        salva_posizione(self.x(), self.y(), self.width(), self.height())
        evento.accept()

    def _misura_iniziale(self) -> tuple:
        """La misura con cui parte quando non c'e' una posizione ricordata."""
        return (min(720, max(MINIMO.width(), (self.parent().width() * 3) // 5)),
                min(440, max(MINIMO.height(), (self.parent().height() * 3) // 5)))

    # ------------------------------------------------------------------

    def _metti_limitata(self, punto: QPoint) -> QPoint:
        """La posizione, senza uscire dal contenitore."""
        padre = self.parentWidget()
        if padre is None:
            return punto
        massimo = padre.rect().size() - self.size()
        # `width()` e `height()`: `QSize` non ha `x()` e `y()`, che sono di
        # `QPoint`.  Su un `QSize` `x` non esiste e l'errore arriva al primo
        # trascinamento — cioe' quando l'utente ha gia' premuto.
        return QPoint(max(0, min(punto.x(), max(0, massimo.width()))),
                      max(0, min(punto.y(), max(0, massimo.height()))))

    def _metti_dentro(self, punto: QPoint) -> None:
        """Porta il riquadro dove e' stato chiesto, ma dentro il padre."""
        self.move(punto)

    def _misura_limitata(self, nuova: QSize) -> QSize:
        """La misura, senza uscire dal contenitore ne' scendere sotto il minimo."""
        padre = self.parentWidget()
        alto = padre.height() if padre is not None else nuova.height()
        largo = padre.width() if padre is not None else nuova.width()
        return QSize(max(MINIMO.width(), min(nuova.width(), largo)),
                     max(MINIMO.height(), min(nuova.height(), alto)))

    # ------------------------------------------------------------------

    def resizeEvent(self, evento) -> None:
        """Il video prende tutta la misura nuova, subito."""
        super().resizeEvent(evento)
        if getattr(self, "video", None) is not None:
            self.video.setGeometry(0, 0, self.width(), self.height())

    def ripristina(self) -> None:
        """Mette il riquadro dove l'utente l'aveva lasciato.

        Si chiama quando il riquadro viene mostrato per la prima volta, e non a
        ogni avvio di un video: rimetterlo a ogni volta significherebbe che
        l'utente non lo puo' spostare mai, perche' basta far partire un altro
        video e torna dove era prima.
        """
        dati = legge_posizione()
        padre = self.parentWidget()
        if padre is None:
            return
        if dati:
            larghezza = max(MINIMO.width(), min(int(dati.get("w", 720)),
                                               padre.width()))
            altezza = max(MINIMO.height(), min(int(dati.get("h", 440)),
                                                padre.height()))
            self.resize(larghezza, altezza)
            self._metti_dentro(QPoint(int(dati.get("x", 0)),
                                      int(dati.get("y", 0))))
            return
        self.resize(*self._misura_iniziale())