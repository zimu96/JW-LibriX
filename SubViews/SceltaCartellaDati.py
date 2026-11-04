#
#  SceltaCartellaDati.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Al primo avvio: «Dove salvo i dati?».

Compare UNA volta, dentro la finestra quando arriva la Home, PRIMA della
domanda sul backup (`BackupIniziale`), nello stesso stile.  Finche' non c'e'
risposta il primo avvio non scarica il catalogo: deve sapere dove metterlo.  Propone la cartella predefinita, qualche cartella candidata (la
home e gli altri dischi montati, con lo spazio libero) e «Scegli…».

Si puo' cambiare dopo da Impostazioni › Cartella dati.
"""

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QVBoxLayout)

from Utility import tema
from Utility.Structures import Paths as modulo_paths


def serve() -> bool:
    """True se bisogna chiedere dove salvare i dati (vedi `Paths.da_chiedere`)."""
    return modulo_paths.da_chiedere()


def _libero(cartella: Path) -> str:
    """Lo spazio libero sul disco della cartella (o del primo genitore che c'e')."""
    prova = cartella
    while not prova.exists() and prova != prova.parent:
        prova = prova.parent
    try:
        return f"{shutil.disk_usage(prova).free / (1024 ** 3):.0f} GB liberi"
    except OSError:
        return ""


def _scrivibile(cartella: Path) -> bool:
    return cartella.is_dir() and os.access(cartella, os.W_OK)


def candidate() -> list[tuple[str, Path]]:
    """Le cartelle proposte: (descrizione, percorso)."""
    nome = modulo_paths.NOME_APP
    voci = [("Predefinita (consigliata)", modulo_paths.PREDEFINITA),
            ("Nella cartella Home, visibile", Path.home() / nome)]
    # Gli altri dischi: dove le distribuzioni montano i dischi in piu'.
    utente = os.environ.get("USER") or Path.home().name
    radici = [Path("/run/media") / utente, Path("/media") / utente, Path("/mnt")]
    disco_home = _dispositivo(Path.home())
    visti = set()
    for radice in radici:
        try:
            dischi = sorted(p for p in radice.iterdir() if p.is_dir())
        except OSError:
            continue
        for disco in dischi:
            if not _scrivibile(disco) or disco in visti:
                continue
            # Lo stesso disco della home non e' «un altro disco».
            if _dispositivo(disco) == disco_home:
                continue
            visti.add(disco)
            voci.append((f"Altro disco: {disco.name}", disco / nome))
    return voci


def _dispositivo(cartella: Path):
    try:
        return cartella.stat().st_dev
    except OSError:
        return None


class SceltaCartellaDati(QFrame):
    """Il riquadro sopra la finestra, con il velo scuro dietro.

    ``su_scelta(cartella)`` riceve la cartella scelta (gia' provata in
    scrittura): cosa farne lo decide la finestra.
    """

    def eventFilter(self, oggetto, evento) -> bool:
        if evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def __init__(self, padre, su_scelta) -> None:
        super().__init__(padre)
        self._su_scelta = su_scelta
        self._altra: Path | None = None
        self.setObjectName("velo")

        scheda = QFrame(self)
        scheda.setObjectName("scheda")
        scheda.setFixedWidth(520)
        scheda.setStyleSheet(
            "#scheda { background-color: #2b2b2b; border-radius: 10px; }"
            " #scheda QLabel, #scheda QRadioButton { color: #f2f2f2; background: transparent; }"
            " QRadioButton { spacing: 8px; font-weight: 600; }"
            " QRadioButton::indicator { width: 12px; height: 12px; border-radius: 8px;"
            " border: 2px solid #8a8a8a; background: transparent; }"
            f" QRadioButton::indicator:checked {{ border-color: {tema.ACCENTO};"
            f" background-color: {tema.ACCENTO}; }}"
            " #scheda #nota { color: #a8a8a8; }"
            f" #testata {{ background-color: {tema.ACCENTO};"
            " border-top-left-radius: 10px; border-top-right-radius: 10px; }"
            " QPushButton { border: none; border-radius: 6px; padding: 9px 18px;"
            " font-weight: 700; color: #ffffff; }"
            f" #si {{ background-color: {tema.ACCENTO}; }}"
            " #si:hover { background-color: #7a49a6; }"
            " #no { background-color: #444444; } #no:hover { background-color: #555555; }")
        self.setStyleSheet("#velo { background-color: rgba(0, 0, 0, 150); }")
        self._scheda = scheda

        colonna = QVBoxLayout(scheda)
        colonna.setContentsMargins(0, 0, 0, 16)
        colonna.setSpacing(12)

        testata = QFrame(self)
        testata.setObjectName("testata")
        riga = QHBoxLayout(testata)
        riga.setContentsMargins(16, 12, 16, 12)
        titolo = QLabel("Dove salvo i dati?", testata)
        titolo.setStyleSheet("font-size: 15px; font-weight: 700;")
        riga.addWidget(titolo)
        colonna.addWidget(testata)

        corpo = QLabel(
            "Qui finiscono catalogo, pubblicazioni, video, audio, note, "
            "segnalibri, impostazioni e plugin. Restano anche quando l'app "
            "si chiude o si aggiorna. Le pubblicazioni e i video occupano "
            "molto: se hai un disco dati, sceglilo.", self)
        corpo.setWordWrap(True)
        corpo.setContentsMargins(16, 0, 16, 0)
        colonna.addWidget(corpo)

        self._gruppo = QButtonGroup(self)
        self._percorsi: dict[int, Path] = {}
        for numero, (descrizione, percorso) in enumerate(candidate()):
            self._aggiungi_voce(colonna, numero, descrizione, percorso)
        self._gruppo.button(0).setChecked(True)

        # «Scegli…»: una voce in piu' che si riempie con la finestra del sistema.
        riga_altra = QHBoxLayout()
        riga_altra.setContentsMargins(16, 0, 16, 0)
        self._voce_altra = QRadioButton("Un'altra cartella…", self)
        self._gruppo.addButton(self._voce_altra, 999)
        sfoglia = QPushButton("Scegli…", self)
        sfoglia.setObjectName("no")
        sfoglia.clicked.connect(self._sfoglia)
        riga_altra.addWidget(self._voce_altra)
        riga_altra.addStretch(1)
        riga_altra.addWidget(sfoglia)
        colonna.addLayout(riga_altra)
        self._nota_altra = QLabel("", self)
        self._nota_altra.setObjectName("nota")
        self._nota_altra.setContentsMargins(42, 0, 16, 0)
        self._nota_altra.setWordWrap(True)
        self._nota_altra.hide()
        colonna.addWidget(self._nota_altra)

        dopo = QLabel("La puoi cambiare quando vuoi da Impostazioni › Cartella dati.", self)
        dopo.setObjectName("nota")
        dopo.setContentsMargins(16, 4, 16, 0)
        dopo.setWordWrap(True)
        colonna.addWidget(dopo)

        pulsanti = QHBoxLayout()
        pulsanti.setContentsMargins(16, 0, 16, 0)
        pulsanti.addStretch(1)
        continua = QPushButton("Continua", self)
        continua.setObjectName("si")
        continua.setCursor(Qt.CursorShape.PointingHandCursor)
        continua.clicked.connect(self._continua)
        pulsanti.addWidget(continua)
        colonna.addLayout(pulsanti)

        esterno = QVBoxLayout(self)
        esterno.addWidget(scheda, 0, Qt.AlignmentFlag.AlignCenter)
        padre.installEventFilter(self)
        self.setGeometry(padre.rect())
        self.show()
        self.raise_()

    def _aggiungi_voce(self, colonna, numero: int, descrizione: str, percorso: Path) -> None:
        blocco = QVBoxLayout()
        blocco.setContentsMargins(16, 0, 16, 0)
        blocco.setSpacing(2)
        voce = QRadioButton(descrizione, self)
        self._gruppo.addButton(voce, numero)
        self._percorsi[numero] = percorso
        blocco.addWidget(voce)
        nota = QLabel(f"{percorso}   ·   {_libero(percorso)}", self)
        nota.setObjectName("nota")
        nota.setContentsMargins(26, 0, 0, 0)
        nota.setWordWrap(True)
        blocco.addWidget(nota)
        colonna.addLayout(blocco)

    def _sfoglia(self) -> None:
        scelta = QFileDialog.getExistingDirectory(self, "Scegli la cartella dati", str(Path.home()))
        if not scelta:
            return
        cartella = Path(scelta)
        # Una cartella piena di altre cose (la home, Documenti) non si
        # riempie di file dell'app: si usa una sottocartella JW-LibriX.
        try:
            piena = any(cartella.iterdir()) and not (cartella / "userData").is_dir()
        except OSError:
            piena = False
        if piena:
            cartella = cartella / modulo_paths.NOME_APP
        self._altra = cartella
        self._voce_altra.setChecked(True)
        self._nota_altra.setText(f"{cartella}   ·   {_libero(cartella)}")
        self._nota_altra.show()

    def _continua(self) -> None:
        numero = self._gruppo.checkedId()
        if numero == 999:
            if self._altra is None:
                self._sfoglia()
                if self._altra is None:
                    return
            scelta = self._altra
        else:
            scelta = self._percorsi.get(numero, modulo_paths.PREDEFINITA)
        try:
            scelta.mkdir(parents=True, exist_ok=True)
            prova = scelta / ".prova_scrittura"
            prova.write_text("ok")
            prova.unlink()
        except OSError as errore:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "JW LibriX", f"Non posso scrivere in {scelta}:\n{errore}")
            return
        self.parentWidget().removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self._su_scelta(scelta)
