#
#  PersonalStudyView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Le Ricerche: sottolineature, segnalibri e appunti.

TRE COSE NELLO STESSO POSTO
---------------------------
Sono tutte cose che l'utente ha lasciato nel testo per ritrovarle: una
sottolineatura perche' quel passo gli interessa, un segnalibro perche' e'
arrivato fin li', un appunto perche' l'ha scritto.  Tenerle in tre schermate
diverse vorrebbe dire sapere in quale delle tre si trova una cosa, e
ricordarselo.

Le sottolineature e i segnalibri si leggono dal database e portano con se'
titolo e testo: restano nell'elenco anche quando la pubblicazione e' stata
cancellata dal disco.  Cliccandone uno si chiede alla finestra di aprire quel
punto; se il file non c'e' piu', e' la finestra a proporre di scaricarlo.

GLI APPUNTI SI LEGGONO, NON SI SCRIVONO
----------------------------------------
Arrivano dal telefono dentro ``user_data.db``.  L'app non ne ha uno di
scrittura, come nel progetto originale: i pulsanti per scriverli non c'erano
e non si inventano qui.

IL VELO
-------
Cliccando un appunto si apre sopra tutto, con il resto scurito.  Il velo e'
un riquadro nero semitrasparente che copre la griglia e si chiude con un
clic.
"""
from __future__ import annotations

from html import escape

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Utility.Structures.Generals import SavedItem
from Utility.Stuff import control_background_color, highlight_color
from Utility.UserData.BookmarkManager import BookmarkManager
from Utility.UserData.HighlightManager import HighlightManager
from Utility.UserData import TestoSegni
from Utility.UserData.NoteManager import NoteManager
from Utility.UserData import TagManager
from SubViews.DialoghiNote import DialogoEtichette, DialogoNota, menu_etichette_nota

# L'altezza fissa di ogni appunto nella griglia, come nell'originale
# (minHeight: 200, maxHeight: 200).
ALTEZZA_NOTA = 200
# Le sottolineature e i segnalibri sono piu' corti: c'e' un testo di
# anteprima, non un appunto intero.
ALTEZZA_SEGNO = 130
COLONNE = 2
SPAZIO = 10
#: Quante card si disegnano per gruppo; le altre si chiedono con «Mostra altre».
#: Un backup puo' avere ventimila sottolineature: disegnarle tutte blocca la finestra.
PAGINA = 30

MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _data(testo: str) -> tuple[str, str]:
    """(anno, «28 mag 2017») da una data ISO; vuoti se non si legge."""
    from datetime import datetime
    try:
        d = datetime.fromisoformat((testo or "").replace("Z", "+00:00"))
    except ValueError:
        return "", ""
    return str(d.year), f"{d.day} {MESI[d.month - 1]} {d.year}"


class PersonalStudyView(QWidget):
    """Sottolineature, segnalibri e appunti, in tre gruppi."""

    #: Un segno e' stato premuto: la finestra apra quel punto del testo.
    posizioneScelta = Signal(object)
    #: Il pulsante «Playlist» e' stato premuto
    playlistRichieste = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.notes = []
        self.show_note = False
        #: l'etichetta con cui si filtrano gli appunti, o None (tutti)
        self._filtro_tag: int | None = None
        self._nota_aperta = None
        self._visibili = {"Sottolineature": PAGINA, "Segnalibri": PAGINA, "Appunti": PAGINA}

        griglia_esterna = QVBoxLayout(self)
        griglia_esterna.setContentsMargins(0, 0, 0, 0)

        barra = QHBoxLayout()
        barra.setContentsMargins(18, 10, 18, 0)
        self.pulsante_playlist = QPushButton("Playlist", self)
        self.pulsante_playlist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pulsante_playlist.clicked.connect(lambda _=False: self.playlistRichieste.emit())
        barra.addWidget(self.pulsante_playlist)
        nuova_nota = QPushButton("Nuova nota", self)
        nuova_nota.setCursor(Qt.CursorShape.PointingHandCursor)
        nuova_nota.clicked.connect(lambda _=False: self._nuova_nota())
        barra.addWidget(nuova_nota)
        self.pulsante_etichette = QPushButton("Etichette", self)
        self.pulsante_etichette.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pulsante_etichette.clicked.connect(lambda _=False: self._menu_filtro())
        barra.addWidget(self.pulsante_etichette)
        barra.addStretch(1)
        griglia_esterna.addLayout(barra)

        self.scorribile = QScrollArea(self)
        self.scorribile.setWidgetResizable(True)
        griglia_esterna.addWidget(self.scorribile)

        # Il riquadro di lettura, sopra tutto, nascosto fino a un clic.
        self.velo = QWidget(self)
        self.velo.setStyleSheet("background-color: rgba(0, 0, 0, 128);")
        self.velo.setVisible(False)
        self.velo_layout = QHBoxLayout(self.velo)
        self.velo_layout.setContentsMargins(30, 30, 30, 30)
        self.contenuto_rosso = QWidget(self.velo)
        self.contenuto_rosso.setStyleSheet(
            f"background-color: {control_background_color(self).name()};"
            f" border-radius: 15px;"
        )
        rosso_layout = QVBoxLayout(self.contenuto_rosso)
        rosso_layout.setContentsMargins(30, 30, 30, 30)
        self.titolo_nota = QLabel("", self.contenuto_rosso)
        self.testo_nota = QLabel("", self.contenuto_rosso)
        for etichetta in (self.titolo_nota, self.testo_nota):
            etichetta.setWordWrap(True)
            etichetta.setAlignment(Qt.AlignmentFlag.AlignTop)
            rosso_layout.addWidget(etichetta)
        azioni = QHBoxLayout()
        self.pulsante_testo = QPushButton("Vai al testo", self.contenuto_rosso)
        self.pulsante_testo.clicked.connect(lambda _=False: self._vai_al_testo())
        azioni.addWidget(self.pulsante_testo)
        for testo, azione in (("Modifica", self._modifica_nota),
                              ("Etichette…", self._etichette_della_nota),
                              ("Elimina", self._elimina_nota)):
            pulsante = QPushButton(testo, self.contenuto_rosso)
            pulsante.clicked.connect(lambda _=False, a=azione: a())
            azioni.addWidget(pulsante)
        azioni.addStretch(1)
        rosso_layout.addLayout(azioni)
        rosso_layout.addStretch(1)
        self.velo_layout.addWidget(self.contenuto_rosso)
        self.velo.mousePressEvent = self._chiudi

        self.aggiorna()

    # ------------------------------------------------------------------
    # LA COSTRUZIONE
    # ------------------------------------------------------------------

    def aggiorna(self) -> None:
        """Rilegge tutto e rifa' i tre gruppi, tenendo la posizione di scorrimento.

        Si chiama quando si apre la sezione e dopo aver aggiunto un segno:
        cosi' una sottolineatura fatta un minuto fa si vede subito, senza
        chiudere e riaprire il programma.
        """
        posizione = self.scorribile.verticalScrollBar().value()
        self.notes = NoteManager.get_notes()
        sottolineature = HighlightManager.get_all_highlights()
        segnalibri = BookmarkManager.get_bookmarks()

        vecchio = self.scorribile.takeWidget()
        if vecchio is not None:
            vecchio.deleteLater()

        interno = QWidget()
        contenuto = QVBoxLayout(interno)
        contenuto.setContentsMargins(12, 12, 12, 12)
        contenuto.setSpacing(6)

        self._gruppo(contenuto, interno, "Sottolineature", sottolineature,
                     "Nessuna sottolineatura salvata.")
        self._gruppo(contenuto, interno, "Segnalibri", segnalibri,
                     "Nessun segnalibro salvato.")
        self._gruppo_appunti(contenuto, interno)

        contenuto.addStretch(1)
        self.scorribile.setWidget(interno)
        # il contenuto ha la sua altezza solo dopo il primo giro di eventi
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.scorribile.verticalScrollBar().setValue(posizione))

    def _altre(self, contenuto: QVBoxLayout, chiave: str, totale: int) -> None:
        """Il pulsante «Mostra altre» sotto un gruppo che non e' tutto visibile."""
        if totale <= self._visibili[chiave]:
            return
        resto = totale - self._visibili[chiave]
        pulsante = QPushButton(f"Mostra altre {min(PAGINA, resto)}  ({resto} nascoste)")
        pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
        pulsante.clicked.connect(lambda _=False: self._mostra_altre(chiave))
        contenuto.addWidget(pulsante)

    def _mostra_altre(self, chiave: str) -> None:
        self._visibili[chiave] += PAGINA
        self.aggiorna()

    def _intestazione(self, contenuto: QVBoxLayout, testo: str,
                      quante: int = 0) -> None:
        scritta = testo if not quante else f"{testo}  ({quante})"
        etichetta = QLabel(scritta)
        etichetta.setStyleSheet(
            "font-size: 13px; font-weight: 700; letter-spacing: 1px;"
            " padding-top: 14px; padding-bottom: 4px;")
        contenuto.addWidget(etichetta)

    def _gruppo(self, contenuto: QVBoxLayout, padre: QWidget, titolo: str,
                elementi: list[SavedItem], vuoto: str) -> None:
        self._intestazione(contenuto, titolo.upper(), len(elementi))
        if not elementi:
            avviso = QLabel(vuoto)
            avviso.setStyleSheet("padding: 8px;")
            contenuto.addWidget(avviso)
            return

        griglia = QGridLayout()
        griglia.setSpacing(SPAZIO)
        for posizione, elemento in enumerate(elementi[:self._visibili[titolo]]):
            TestoSegni.completa(elemento)
            scheda = self._scheda_segno(elemento, padre)
            griglia.addWidget(scheda, posizione // COLONNE,
                              posizione % COLONNE)
        griglia.setAlignment(Qt.AlignmentFlag.AlignTop)
        contenuto.addLayout(griglia)
        self._altre(contenuto, titolo, len(elementi))

    def _scheda_segno(self, elemento: SavedItem, padre: QWidget) -> QLabel:
        """La card di una sottolineatura o di un segnalibro.

        Il colore sta sul bordo sinistro e non su tutta la card: il testo deve
        restare leggibile, e una fila di riquadri pieni di colore diventa
        rumore.  Il bordo dice di che colore e' il segno senza nascondere le
        parole.  Se la pubblicazione non e' scaricata lo dice la card: aprirla
        chiede se scaricarla, non va in rete da sola.
        """
        scheda = QLabel(padre)
        scheda.setTextFormat(Qt.TextFormat.RichText)
        scheda.setWordWrap(True)
        scheda.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scheda.setFixedHeight(ALTEZZA_SEGNO)
        colore = highlight_color(elemento.color)
        sfondo = control_background_color(self)
        scheda.setStyleSheet(
            f"background-color: {sfondo.name()};"
            f" border-radius: 10px;"
            f" border-left: 6px solid {colore.name()};"
            f" padding: 10px;"
        )
        if elemento.snippet:
            testo = escape(elemento.snippet)
        elif elemento.scaricato:
            testo = "<i>Testo non trovato nel documento.</i>"
        else:
            testo = "<i>Pubblicazione non scaricata.</i>"
        sotto = (f"<br><span style='font-size:11px; color:#8a8a8a'>"
                 f"{escape(elemento.sottotitolo)}</span>") if elemento.sottotitolo else ""
        avviso = ("" if elemento.scaricato else
                  "<br><span style='font-size:11px; color:#a77bd0'>"
                  "\u2601 Non scaricata \u2014 premi per scaricarla</span>")
        scheda.setText(f"<b>{escape(elemento.title)}</b>{sotto}<br>{testo}{avviso}")
        scheda.setCursor(Qt.CursorShape.PointingHandCursor)
        scheda.mousePressEvent = (
            lambda _evento, segno=elemento: self.posizioneScelta.emit(segno))
        return scheda

    def _gruppo_appunti(self, contenuto: QVBoxLayout, padre: QWidget) -> None:
        note = self.notes
        if self._filtro_tag is not None:
            ammesse = TagManager.note_del_tag(self._filtro_tag)
            note = [n for n in note if n.ID in ammesse]
        etichette = TagManager.nomi_per_nota()
        self._intestazione(contenuto, "APPUNTI", len(note))
        if not note:
            avviso = QLabel("Nessun appunto salvato." if self._filtro_tag is None
                            else "Nessun appunto con questa etichetta.")
            avviso.setStyleSheet("padding: 8px;")
            contenuto.addWidget(avviso)
            return

        sfondo = control_background_color(self)
        griglia = None
        anno_corrente = None
        posizione = 0
        for nota in note[:self._visibili["Appunti"]]:
            anno, data = _data(nota.date)
            # un'intestazione per anno, dal piu' recente: l'ordine e' cronologico
            if griglia is None or anno != anno_corrente:
                if griglia is not None:
                    griglia.setAlignment(Qt.AlignmentFlag.AlignTop)
                    contenuto.addLayout(griglia)
                anno_corrente = anno
                if anno:
                    anno_label = QLabel(anno)
                    anno_label.setStyleSheet(
                        "font-size: 12px; font-weight: 700; color: #8a8a8a;"
                        " padding-top: 8px;")
                    contenuto.addWidget(anno_label)
                griglia = QGridLayout()
                griglia.setSpacing(SPAZIO)
                posizione = 0
            nomi = etichette.get(nota.ID)
            coda = f"<br><br>\U0001F3F7 {escape(', '.join(nomi))}" if nomi else ""
            contesto = self._contesto_nota(nota)
            riga_data = " \u00b7 ".join(x for x in (data, contesto) if x)
            intestazione = (f"<span style='font-size:11px; color:#8a8a8a'>{escape(riga_data)}"
                            "</span><br>") if riga_data else ""
            scheda = QLabel(padre)
            scheda.setTextFormat(Qt.TextFormat.RichText)
            scheda.setText(f"<b>{escape(nota.title)}</b><br>{intestazione}"
                           f"{escape(nota.content).replace(chr(10), '<br>')}{coda}")
            scheda.setWordWrap(True)
            scheda.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            scheda.setFixedHeight(ALTEZZA_NOTA)
            scheda.setStyleSheet(
                f"background-color: {sfondo.name()};"
                f" border-radius: 10px; padding: 10px;"
            )
            scheda.setCursor(Qt.CursorShape.PointingHandCursor)
            scheda.mousePressEvent = lambda _e, n=nota: self._apri(n)
            griglia.addWidget(scheda, posizione // COLONNE, posizione % COLONNE)
            posizione += 1
        if griglia is not None:
            griglia.setAlignment(Qt.AlignmentFlag.AlignTop)
            contenuto.addLayout(griglia)
        self._altre(contenuto, "Appunti", len(note))

    @staticmethod
    def _contesto_nota(nota) -> str:
        """Il documento a cui l'appunto e' attaccato, se si conosce senza rete."""
        if not (nota.documentId or (nota.bookNumber and nota.chapterNumber)):
            return ""
        r = TestoSegni.risolvi(nota.keySymbol, nota.mepsLanguageId, nota.issueTagNumber,
                               nota.documentId, nota.bookNumber, nota.chapterNumber, 0)
        return r["titolo"] if r["scaricato"] else (r["titolo"] + " (non scaricata)")

    # ------------------------------------------------------------------

    def _apri(self, nota) -> None:
        self._nota_aperta = nota
        self.pulsante_testo.setVisible(bool(nota.documentId or (nota.bookNumber and nota.chapterNumber)))
        _anno, data = _data(nota.date)
        self.titolo_nota.setText(f"{nota.title}\n{data}" if data else nota.title)
        self.testo_nota.setText(nota.content)
        self.velo.setGeometry(self.rect())
        self.velo.raise_()
        self.velo.setVisible(True)

    def _vai_al_testo(self) -> None:
        nota = self._nota_aperta
        if nota is None:
            return
        self._chiudi(None)
        self.posizioneScelta.emit(SavedItem(
            kind="appunto", ID=nota.ID, title=nota.title, snippet="", color=1,
            identifier=nota.identifier, keySymbol=nota.keySymbol,
            mepsLanguageId=nota.mepsLanguageId, issueTagNumber=nota.issueTagNumber,
            documentId=nota.documentId, bookNumber=nota.bookNumber,
            chapterNumber=nota.chapterNumber))

    def _chiudi(self, _evento) -> None:
        self.velo.setVisible(False)
        self.titolo_nota.setText("")
        self.testo_nota.setText("")

    # ------------------------------------------------------------------
    # SCRIVERE E ORGANIZZARE LE NOTE
    # ------------------------------------------------------------------

    def _nuova_nota(self) -> None:
        dialogo = DialogoNota(self)
        if dialogo.exec() and dialogo.risultato:
            NoteManager.crea(*dialogo.risultato)
            self.aggiorna()

    def _modifica_nota(self) -> None:
        nota = self._nota_aperta
        if nota is None:
            return
        dialogo = DialogoNota(self, nota.title, nota.content)
        if dialogo.exec() and dialogo.risultato:
            NoteManager.modifica(nota.ID, *dialogo.risultato)
            self._chiudi(None)
            self.aggiorna()

    def _etichette_della_nota(self) -> None:
        if self._nota_aperta is not None:
            menu_etichette_nota(self, self._nota_aperta.ID, self.aggiorna)

    def _elimina_nota(self) -> None:
        nota = self._nota_aperta
        if nota is None:
            return
        from PyQt6.QtWidgets import QMessageBox
        domanda = QMessageBox(self)
        domanda.setText(f"Elimino la nota «{nota.title}»?")
        domanda.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        domanda.setDefaultButton(QMessageBox.StandardButton.No)
        domanda.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        if domanda.exec() == QMessageBox.StandardButton.Yes:
            NoteManager.elimina(nota.ID)
            self._chiudi(None)
            self.aggiorna()

    def _menu_filtro(self) -> None:
        """Le etichette: filtra gli appunti, oppure gestiscile."""
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        tutte = menu.addAction("Tutti gli appunti")
        tutte.setCheckable(True)
        tutte.setChecked(self._filtro_tag is None)
        tutte.triggered.connect(lambda _=False: self._imposta_filtro(None))
        for e in TagManager.etichette():
            azione = menu.addAction(f"{e['nome']}  ({e['note']})")
            azione.setCheckable(True)
            azione.setChecked(self._filtro_tag == e["id"])
            azione.triggered.connect(lambda _=False, i=e["id"]: self._imposta_filtro(i))
        menu.addSeparator()
        gestisci = menu.addAction("Gestisci le etichette…")
        gestisci.triggered.connect(lambda _=False: self._gestisci_etichette())
        menu.exec(QCursor.pos())

    def _imposta_filtro(self, tag_id: int | None) -> None:
        self._filtro_tag = tag_id
        self.aggiorna()

    def _gestisci_etichette(self) -> None:
        DialogoEtichette(self).exec()
        if self._filtro_tag not in {e["id"] for e in TagManager.etichette()}:
            self._filtro_tag = None
        self.aggiorna()

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.velo.setGeometry(self.rect())
