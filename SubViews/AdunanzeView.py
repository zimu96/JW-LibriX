#
#  AdunanzeView.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""La sezione Adunanze: la settimana in corso, e le pubblicazioni dell'adunanza.

Come nell'applicazione originale: una riga con la settimana ("19-25 ottobre"),
due card — Vita cristiana e ministero (dalla Guida ``mwb``) e Studio della
Torre di Guardia (dall'edizione per lo studio ``w``) — e sotto le altre
pubblicazioni dell'adunanza.

DA DOVE VIENE OGNI COSA
-----------------------
- Le settimane si leggono dai pacchetti ``mwb`` scaricati: le date stanno nel
  titolo ("2-8 novembre", "30 novembre – 6 dicembre").
- L'articolo di studio della settimana sta in un pacchetto ``w`` scaricato: ogni
  articolo ha come titolo di contesto la sua settimana ("19-25 OTTOBRE 2026").
- Una settimana che comincia nel mese M sta nel numero ``w`` di M-2: il 19
  ottobre e' in agosto, il 2 novembre e' in settembre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Utility import Copertine, Lingua
from Utility import JWPubManager as _jwpub
from Utility.DBManager import DBManager
from Utility.Extensions.Ext_DispatchQueue import background
from Utility.Extensions.Ext_FileManager import get_documents_directory
from Utility.JWPubManager import JWPubManager, pub_dir_name
from Utility.Structures.Generals import Document, Publication
from SubViews.HomeView import _barra_scaricamento

SIGLA = "mwb"
SIGLA_STUDIO = "w"
#: Le altre pubblicazioni dell'adunanza che non hanno un numero:
#: Cantiamo a Geova con gioia, Ama le persone, Applicati alla lettura,
#: Istruzioni per l'adunanza.
ALTRE_SIGLE = ("sjj", "lmd", "th", "S-38")

LATO_MINIATURA = 63
LARGHEZZA_COLONNA = 782

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
    "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
    "novembre": 11, "dicembre": 12,
}
NOMI_MESI = {numero: nome for nome, numero in MESI.items()}

_RE_MESE = re.compile(r"\b(" + "|".join(MESI) + r")\b", re.IGNORECASE)
_RE_ANNO = re.compile(r"\b(20\d\d)\b")
_RE_GIORNO = re.compile(r"\b(\d{1,2})\b")


def inizio_settimana(titolo: str, anno_numero: int, mese_numero: int) -> date | None:
    """La data del primo giorno di una settimana, dal suo titolo.

    ``anno_numero`` e ``mese_numero`` sono quelli del numero (20261100 ->
    2026, 11) e servono quando il titolo non dice l'anno.
    """
    testo = titolo.replace("\u2013", "–")
    if "–" in testo:
        primo, secondo = (p.strip() for p in testo.split("–", 1))
    else:
        primo, _, secondo = (p.strip() for p in testo.partition("-"))
    giorno = _RE_GIORNO.search(primo)
    if not giorno:
        return None
    mese = _RE_MESE.search(primo) or _RE_MESE.search(secondo)
    if not mese:
        return None
    numero_mese = MESI[mese.group(1).lower()]
    anno = _RE_ANNO.search(primo)
    if anno:
        numero_anno = int(anno.group(1))
    elif "–" not in testo and _RE_ANNO.search(secondo):
        numero_anno = int(_RE_ANNO.search(secondo).group(1))
    else:
        numero_anno = anno_numero + (1 if numero_mese < mese_numero else 0)
    try:
        return date(numero_anno, numero_mese, int(giorno.group(1)))
    except ValueError:
        return None


def _anno_mese(pub: Publication) -> tuple[int, int]:
    testo = str(pub.issueTagNumber or 0).ljust(8, "0")
    return int(testo[:4]), int(testo[4:6])


def _giorno_mese(giorno: date) -> str:
    primo = "1º" if giorno.day == 1 else str(giorno.day)
    return f"{primo} {NOMI_MESI[giorno.month]}"


def pacchetti_scaricati(sigla: str) -> list[Publication]:
    """I pacchetti di quella sigla che sono sul disco, dal piu' vecchio."""
    trovati = []
    for cartella in _jwpub.scaricate():
        if not cartella.name.startswith(f"{sigla}_"):
            continue
        pub = _jwpub.leggi_pubblicazione(cartella)
        if pub is not None:
            # dentro il pacchetto il simbolo e' "mwb26": la cartella e'
            # "mwb_I_...", e `pub_dir_name` vuole la sigla senza l'anno
            trovati.append(replace(pub, keySymbol=sigla))
    trovati.sort(key=lambda p: p.issueTagNumber)
    return trovati


@dataclass
class Settimana:
    inizio: date | None
    pub: Publication
    documento: Document

    @property
    def titolo(self) -> str:
        return self.documento.title

    def contiene(self, giorno: date) -> bool:
        return (self.inizio is not None
                and self.inizio <= giorno <= self.inizio + timedelta(days=6))


def tutte_le_settimane() -> list[Settimana]:
    """Le settimane di tutti i pacchetti mwb scaricati, per data."""
    risultato: list[Settimana] = []
    for pub in pacchetti_scaricati(SIGLA):
        anno, mese = _anno_mese(pub)
        for documento in JWPubManager.get_documents(pub):
            titolo = documento.title or ""
            if documento.ID == 0 or titolo.lower().startswith("guida"):
                continue
            risultato.append(Settimana(
                inizio_settimana(titolo, anno, mese), pub, documento))
    risultato.sort(key=lambda s: s.inizio or date.max)
    return risultato


def indice_iniziale(settimane: list[Settimana], oggi: date) -> int:
    """La settimana di oggi; se non c'e' la prossima; se non c'e' l'ultima."""
    for i, settimana in enumerate(settimane):
        if settimana.contiene(oggi):
            return i
    for i, settimana in enumerate(settimane):
        if settimana.inizio is not None and settimana.inizio > oggi:
            return i
    return max(0, len(settimane) - 1)


def articolo_di_studio(inizio: date | None):
    """(pub, documento) dell'articolo di studio di quella settimana, o None."""
    if inizio is None:
        return None
    for pub in pacchetti_scaricati(SIGLA_STUDIO):
        anno, mese = _anno_mese(pub)
        for documento in JWPubManager.get_documents(pub):
            if not documento.contextTitle:
                continue
            if inizio_settimana(documento.contextTitle, anno, mese) == inizio:
                return pub, documento
    return None


def numero_studio_da_scaricare(inizio: date | None):
    """La riga del catalogo del numero ``w`` che contiene quella settimana."""
    if inizio is None:
        return None
    mese = inizio.month - 2
    anno = inizio.year
    if mese < 1:
        mese += 12
        anno -= 1
    cercato = anno * 10000 + mese * 100
    for pub in DBManager.get_publications():
        if pub.keySymbol == SIGLA_STUDIO and pub.issueTagNumber == cercato:
            return pub
    return None


def numero_da_scaricare(oggi: date, lingua: int | None = None):
    """La riga del catalogo del numero mwb in corso, o None."""
    mese_oggi = oggi.year * 100 + oggi.month
    migliore = None
    for pub in DBManager.get_publications(lingua):
        if pub.keySymbol != SIGLA:
            continue
        anno, mese = _anno_mese(pub)
        inizio = anno * 100 + mese
        if inizio <= mese_oggi and (migliore is None or inizio > migliore[0]):
            migliore = (inizio, pub)
    return migliore[1] if migliore else None


def cantici_della_pagina(meps_id: int) -> list[int]:
    """I numeri dei cantici di una pagina scaricata, nell'ordine in cui compaiono.

    Nella Guida sono le righe «Cantico 44»; nell'articolo di studio la riga
    «CANTICO 106 …».  Una pagina non scaricata non ne ha: lista vuota.
    """
    file = get_documents_directory() / "Documents_I" / f"{meps_id}.html"
    try:
        testo = file.read_text(encoding="utf-8")
    except OSError:
        return []
    testo = re.sub(r"<[^>]+>", " ", testo)
    visti: list[int] = []
    for trovato in re.finditer(r"\bcantico\s+(\d{1,3})\b", testo, re.IGNORECASE):
        numero = int(trovato.group(1))
        if numero not in visti:
            visti.append(numero)
    return visti


def _testo_cantici(numeri: list[int]) -> str:
    if not numeri:
        return ""
    return ("Cantico " if len(numeri) == 1 else "Cantici ") + ", ".join(map(str, numeri))


def _miniatura_del_pacchetto(pub: Publication, meps_id: int) -> QPixmap | None:
    percorso = (get_documents_directory() / pub_dir_name(pub) / "contents"
                / f"{meps_id}_univ_sqr.jpg")
    if not percorso.is_file():
        return None
    pixmap = QPixmap(str(percorso))
    return pixmap if not pixmap.isNull() else None


class _Card(QFrame):
    """Una riga cliccabile: miniatura a sinistra, titolo e sottotitolo."""

    clicked = Signal()

    def __init__(self, titolo: str, sottotitolo: str = "",
                 pixmap: QPixmap | None = None, parent=None,
                 chiave: tuple | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rigaPiatta")
        #: (sigla, numero) della pubblicazione che la card scarica, se ne scarica una
        self.chiave = chiave
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        riga = QHBoxLayout(self)
        riga.setContentsMargins(8, 8, 8, 8)
        riga.setSpacing(14)

        self.miniatura = QLabel(self)
        self.miniatura.setFixedSize(LATO_MINIATURA, LATO_MINIATURA)
        self.miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.miniatura.setObjectName("miniatura")
        riga.addWidget(self.miniatura, 0)
        self.imposta_miniatura(pixmap)
        # La barra di scaricamento sulla miniatura, come nella Biblioteca: la
        # finestra la accende con questi tre nomi.
        _, self._scarica_comincia, self._scarica_avanza, self._scarica_finita = (
            _barra_scaricamento(self.miniatura, LATO_MINIATURA))

        colonna = QVBoxLayout()
        colonna.setSpacing(2)
        colonna.addStretch(1)
        self.titolo = QLabel(titolo, self)
        self.titolo.setObjectName("titoloNovita")
        self.titolo.setWordWrap(True)
        colonna.addWidget(self.titolo)
        if sottotitolo:
            sotto = QLabel(sottotitolo, self)
            sotto.setObjectName("sottoCard")
            sotto.setWordWrap(True)
            colonna.addWidget(sotto)
        colonna.addStretch(1)
        riga.addLayout(colonna, 1)

    def imposta_miniatura(self, pixmap: QPixmap | None) -> None:
        if pixmap is None or pixmap.isNull():
            self.miniatura.clear()
            return
        from Utility import Copertine
        self.miniatura.setPixmap(Copertine.pixmap_quadrata(pixmap, LATO_MINIATURA))

    def mousePressEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class AdunanzeView(QWidget):
    """La settimana dell'adunanza e le sue pubblicazioni."""

    navigate = Signal(object)
    goBack = Signal()
    messaggio = Signal(str)
    #: Chiede di scaricare un pacchetto: stesso dizionario della Home, piu'
    #: ``apri`` (False = si resta in questa sezione).
    scaricaRichiesta = Signal(dict)
    #: Chiede di aprire l'elenco dei capitoli di una pubblicazione scaricata.
    pubblicazioneRichiesta = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settimane: list[Settimana] = []
        self._indice = 0
        self._inizio_scelto: date | None = None

        scorribile = QScrollArea(self)
        scorribile.setWidgetResizable(True)
        scorribile.setFrameShape(QScrollArea.Shape.NoFrame)

        pagina = QWidget()
        esterna = QHBoxLayout(pagina)
        esterna.setContentsMargins(18, 16, 18, 16)
        esterna.addStretch(1)

        self.contenitore = QWidget(pagina)
        self.contenitore.setMaximumWidth(LARGHEZZA_COLONNA)
        self._colonna = QVBoxLayout(self.contenitore)
        self._colonna.setContentsMargins(0, 0, 0, 0)
        self._colonna.setSpacing(6)
        self._colonna.setAlignment(Qt.AlignmentFlag.AlignTop)
        esterna.addWidget(self.contenitore, 100)
        esterna.addStretch(1)

        scorribile.setWidget(pagina)
        radice = QVBoxLayout(self)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.addWidget(scorribile)

        self.aggiorna()

    # ------------------------------------------------------------------
    # COSTRUZIONE
    # ------------------------------------------------------------------

    def aggiorna(self) -> None:
        """Rilegge il disco e ricostruisce la pagina."""
        while self._colonna.count():
            elemento = self._colonna.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().hide()
                elemento.widget().deleteLater()

        oggi = date.today()
        self._settimane = tutte_le_settimane()
        self._colonna.addWidget(self._etichetta("Adunanze", "titoloPagina"))
        voce = Lingua.corrente_voce()
        if voce:
            self._colonna.addWidget(
                self._etichetta(Lingua.titolo(voce), "linguaSezione"))

        if not self._settimane:
            self._mostra_vuoto(oggi)
            return

        if self._inizio_scelto is not None:
            self._indice = next(
                (i for i, s in enumerate(self._settimane)
                 if s.inizio == self._inizio_scelto),
                indice_iniziale(self._settimane, oggi))
        else:
            self._indice = indice_iniziale(self._settimane, oggi)
        settimana = self._settimane[self._indice]
        self._inizio_scelto = settimana.inizio

        self._colonna.addWidget(self._barra_settimana(settimana, oggi))
        self._colonna.addSpacing(8)

        self._colonna.addWidget(self._titolo_sezione("Vita cristiana e ministero"))
        self._colonna.addWidget(self._card_vita_ministero(settimana))
        self._colonna.addSpacing(14)

        self._colonna.addWidget(
            self._titolo_sezione("Studio della Torre di Guardia"))
        self._colonna.addWidget(self._card_studio(settimana))
        self._colonna.addSpacing(14)

        self._colonna.addWidget(
            self._titolo_sezione("Altre pubblicazioni per l'adunanza"))
        self._aggiungi_altre(settimana)

    def _etichetta(self, testo: str, nome: str) -> QLabel:
        etichetta = QLabel(testo, self.contenitore)
        etichetta.setObjectName(nome)
        return etichetta

    def _titolo_sezione(self, testo: str) -> QLabel:
        etichetta = QLabel(testo, self.contenitore)
        etichetta.setStyleSheet(
            "font-size: 18px; font-weight: 600; padding: 6px 8px 2px 8px;"
            " background: transparent;")
        return etichetta

    def _barra_settimana(self, settimana: Settimana, oggi: date) -> QWidget:
        """«19-25 ottobre · Questa settimana», viola, con le frecce accanto.

        Come nell'originale: un gruppo al centro della colonna, con le frecce
        vicine al testo e non ai due estremi della pagina.
        """
        # Un widget e non un layout: `aggiorna` cancella solo i widget, e i
        # pulsanti di un layout lasciato li' si sovrapponevano a ogni cambio
        # di settimana.
        contenitore = QWidget(self.contenitore)
        barra = QHBoxLayout(contenitore)
        barra.setContentsMargins(0, 6, 0, 6)
        barra.setSpacing(60)
        indietro = QPushButton("‹", self.contenitore)
        avanti = QPushButton("›", self.contenitore)
        for pulsante in (indietro, avanti):
            pulsante.setObjectName("frecciaSettimana")
            pulsante.setFixedWidth(32)
            pulsante.setFlat(True)
            pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
        indietro.setEnabled(self._indice > 0)
        avanti.setEnabled(self._indice < len(self._settimane) - 1)
        indietro.clicked.connect(lambda: self._cambia_settimana(-1))
        avanti.clicked.connect(lambda: self._cambia_settimana(1))

        testo = settimana.titolo
        if settimana.contiene(oggi):
            testo += "  ·  Questa settimana"
        etichetta = QLabel(testo, self.contenitore)
        etichetta.setObjectName("testoSettimana")
        etichetta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        barra.addStretch(1)
        barra.addWidget(indietro)
        barra.addWidget(etichetta)
        barra.addWidget(avanti)
        barra.addStretch(1)
        return contenitore

    def _cambia_settimana(self, passo: int) -> None:
        nuovo = self._indice + passo
        if 0 <= nuovo < len(self._settimane):
            self._inizio_scelto = self._settimane[nuovo].inizio
            self.aggiorna()

    def _mostra_vuoto(self, oggi: date) -> None:
        pub = numero_da_scaricare(oggi)
        testo = ("Non c'e' ancora nessuna Guida per l'adunanza scaricata."
                 if pub is not None else
                 "Non trovo la Guida per l'adunanza nel catalogo.")
        vuoto = QLabel(testo, self.contenitore)
        vuoto.setObjectName("vuoto")
        vuoto.setWordWrap(True)
        self._colonna.addWidget(vuoto)
        if pub is None:
            return
        nome = pub.issueTitle or pub.title
        pulsante = QPushButton(f"Scarica {nome}", self.contenitore)
        pulsante.setCursor(Qt.CursorShape.PointingHandCursor)
        pulsante.clicked.connect(lambda _=False, p=pub: self._scarica(p))
        self._colonna.addWidget(pulsante)

    # ------------------------------------------------------------------
    # LE DUE CARD
    # ------------------------------------------------------------------

    def _card_vita_ministero(self, settimana: Settimana) -> _Card:
        cantici = _testo_cantici(cantici_della_pagina(settimana.documento.documentId))
        sotto = "Adunanza infrasettimanale" + (f"  ·  {cantici}" if cantici else "")
        card = _Card(settimana.titolo, sotto,
                     _miniatura_del_pacchetto(settimana.pub,
                                              settimana.documento.documentId),
                     self.contenitore)
        card.clicked.connect(lambda: self._apri_settimana(settimana))
        return card

    def _card_studio(self, settimana: Settimana) -> _Card:
        trovato = articolo_di_studio(settimana.inizio)
        if trovato is not None:
            pub, documento = trovato
            cantici = _testo_cantici(cantici_della_pagina(documento.documentId))
            card = _Card(documento.title, "Articolo di studio · "
                         + (documento.contextTitle or "").capitalize()
                         + (f"  ·  {cantici}" if cantici else ""),
                         _miniatura_del_pacchetto(pub, documento.documentId),
                         self.contenitore)
            card.clicked.connect(lambda: self._apri_articolo(pub, documento))
            return card

        catalogo = numero_studio_da_scaricare(settimana.inizio)
        if catalogo is None:
            return _Card("Articolo di studio non disponibile",
                         "Non trovo il numero della Torre di Guardia nel catalogo.",
                         None, self.contenitore)
        nome = catalogo.issueTitle or catalogo.title
        card = _Card(f"Scarica {nome}",
                     "Contiene l'articolo di studio di questa settimana.",
                     None, self.contenitore,
                     chiave=(catalogo.keySymbol, catalogo.issueTagNumber))
        self._copertina_in_background(card, catalogo)
        card.clicked.connect(lambda: self._scarica(catalogo))
        return card

    # ------------------------------------------------------------------
    # ALTRE PUBBLICAZIONI
    # ------------------------------------------------------------------

    def _aggiungi_altre(self, settimana: Settimana) -> None:
        date_guida = [s.inizio for s in self._settimane
                      if s.pub.issueTagNumber == settimana.pub.issueTagNumber
                      and s.inizio is not None]
        sottotitolo = ""
        if date_guida:
            sottotitolo = (f"Adunanze dal {_giorno_mese(min(date_guida))} "
                           f"al {_giorno_mese(max(date_guida) + timedelta(days=6))}")
        guida = _Card(self._titolo_numero(settimana.pub, "Guida per l'adunanza"),
                      sottotitolo, None, self.contenitore)
        guida.imposta_miniatura(self._copertina_pacchetto(settimana.pub))
        guida.clicked.connect(
            lambda: self.pubblicazioneRichiesta.emit(settimana.pub))
        self._colonna.addWidget(guida)

        trovato = articolo_di_studio(settimana.inizio)
        if trovato is not None:
            pub = trovato[0]
            date_studio = []
            anno, mese = _anno_mese(pub)
            for documento in JWPubManager.get_documents(pub):
                inizio = inizio_settimana(documento.contextTitle or "", anno, mese)
                if inizio is not None and documento.contextTitle:
                    date_studio.append(inizio)
            sotto = ""
            if date_studio:
                sotto = (f"Articoli di studio dal {_giorno_mese(min(date_studio))} "
                         f"al {_giorno_mese(max(date_studio) + timedelta(days=6))}")
            studio = _Card(self._titolo_numero(pub, "La Torre di Guardia"), sotto,
                           self._copertina_pacchetto(pub), self.contenitore)
            studio.clicked.connect(lambda: self.pubblicazioneRichiesta.emit(pub))
            self._colonna.addWidget(studio)

        catalogo = {p.keySymbol: p for p in DBManager.get_publications()
                    if p.keySymbol in ALTRE_SIGLE and p.issueTagNumber == 0}
        for sigla in ALTRE_SIGLE:
            pub = catalogo.get(sigla)
            if pub is None:
                continue
            card = _Card(pub.title, "", self._copertina_pacchetto(pub),
                         self.contenitore, chiave=(pub.keySymbol, 0))
            if not Copertine.pacchetto_locale(pub):
                self._copertina_in_background(card, pub)
            card.clicked.connect(lambda p=pub: self._apri_altra(p))
            self._colonna.addWidget(card)

    @staticmethod
    def _titolo_numero(pub: Publication, predefinito: str) -> str:
        anno, mese = _anno_mese(pub)
        if pub.keySymbol == SIGLA:
            ultimo = mese + 1
            return (f"{predefinito}, {NOMI_MESI[mese]}-{NOMI_MESI[ultimo]} {anno}"
                    if 1 <= mese < 12 else f"{predefinito}, {anno}")
        return f"{predefinito}, {NOMI_MESI.get(mese, '')} {anno}".replace("  ", " ")

    @staticmethod
    def _copertina_pacchetto(pub: Publication) -> QPixmap | None:
        dati = Copertine.dati_gia_in_cache(pub, "sm")
        return Copertine.pixmap_da_dati(dati) if dati else None

    def _copertina_in_background(self, card: _Card, pub: Publication) -> None:
        if Copertine.dati_gia_in_cache(pub, "sm"):
            card.imposta_miniatura(self._copertina_pacchetto(pub))
            return
        tenuta: list = [None]

        def scarica() -> None:
            tenuta[0] = Copertine.dati_copertina(pub, "sm")

        def pronto() -> None:
            if not tenuta[0]:
                return
            try:
                card.imposta_miniatura(Copertine.pixmap_da_dati(tenuta[0]))
            except RuntimeError:
                pass

        background(scarica, completion=pronto)

    def card_di(self, pub) -> _Card | None:
        """La card che scarica quella pubblicazione, o None.

        Serve alla finestra per accendere la barra di scaricamento sulla card
        giusta: si cerca per (sigla, numero), non per posizione.
        """
        if pub is None:
            return None
        chiave = (getattr(pub, "keySymbol", ""), getattr(pub, "issueTagNumber", 0) or 0)
        return next((c for c in self.findChildren(_Card) if c.chiave == chiave), None)

    # ------------------------------------------------------------------
    # AZIONI
    # ------------------------------------------------------------------

    def _scarica(self, pub: Publication, apri: bool = False) -> None:
        self.scaricaRichiesta.emit({
            "sigla": pub.keySymbol,
            "lingua": Lingua.corrente_simbolo(),
            "numero": (pub_dir_name(pub).rsplit("_", 1)[-1]
                       if pub.issueTagNumber else ""),
            "titolo": pub.issueTitle or pub.title,
            "apri": apri,
        })

    def _apri_altra(self, pub: Publication) -> None:
        if Copertine.pacchetto_locale(pub):
            self.pubblicazioneRichiesta.emit(pub)
        else:
            self._scarica(pub, apri=True)

    def _apri_settimana(self, settimana: Settimana) -> None:
        elenco = [s for s in self._settimane
                  if s.pub.issueTagNumber == settimana.pub.issueTagNumber]
        pagine = [
            {"file_path": f"Documents_I/{s.documento.documentId}.html",
             "document": s.documento, "titolo": s.documento.title}
            for s in elenco
        ]
        indice = next((i for i, s in enumerate(elenco)
                       if s.documento.documentId == settimana.documento.documentId), -1)
        self._apri_articolo(settimana.pub, settimana.documento,
                            pagine if indice >= 0 else None, indice)

    def _apri_articolo(self, pub: Publication, documento: Document,
                       pagine: list | None = None, indice: int = -1) -> None:
        from SubViews.ArticleView import ArticleView

        file_path = f"Documents_I/{documento.documentId}.html"
        if not (get_documents_directory() / file_path).is_file():
            self.messaggio.emit(
                "Il testo di questa pagina non e' stato scaricato: "
                "riscarica la pubblicazione.")
            return
        articolo = ArticleView(
            pub=pub,
            file_path=file_path,
            prev_text="Adunanze",
            document=documento,
            pagine=pagine,
            indice_pagina=indice,
        )
        self.navigate.emit(articolo)
