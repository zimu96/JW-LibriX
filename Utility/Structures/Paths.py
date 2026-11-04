#
#  Paths.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Percorsi dei dati dell'utente.

La radice si calcola una volta sola all'import del modulo e non cambia
durante la vita del programma: per cambiarla si salva la scelta e si
riavvia l'app.

DOVE STA LA RADICE
------------------
FUORI dal programma, in una cartella che resta anche quando l'app si chiude,
si aggiorna o si cancella.  Dentro un'AppImage la cartella del programma e'
di sola lettura, quindi i dati accanto al programma non potrebbero esistere.

In ordine, vince la prima che c'e':

  1. ``JWL_HOME`` (variabile d'ambiente): per le prove e per due profili.
  2. La cartella scelta dall'utente nelle Impostazioni, salvata in
     ``~/.config/JW-LibriX/percorso_dati.json``.  Serve a chi vuole i dati
     su un altro disco (un secondo SSD, un disco dati).
  3. La predefinita: ``~/.local/share/JW-LibriX`` (``$XDG_DATA_HOME``).

La scelta sta in ``~/.config`` e non dentro la cartella dati: la cartella
dati e' proprio la cosa che si cambia, e non puo' dire dove si trova lei.

COSA C'E' DENTRO
----------------
Tutto quello che l'app scrive: catalogo, pubblicazioni, video, audio,
copertine, ``userData/`` (note, segnalibri, impostazioni, log) e
``plugin/``.  Il programma resta di sola lettura.

SPOSTARE O IMPORTARE I DATI
---------------------------
Copiare file mentre i database sono aperti li puo' rovinare.  Per questo
le Impostazioni non copiano niente subito: scrivono un'operazione in
sospeso (``copia_da``) e riavviano l'app; la copia la fa
`esegui_copia_in_sospeso` all'avvio, prima che qualcuno apra un database.
"""

import json
import os
import shutil
from pathlib import Path

# La cartella del programma: Utility/Structures/Paths.py sale di tre livelli
# (Paths.py -> Structures -> Utility) e arriva alla radice.
RADICE_PROGRAMMA = Path(__file__).resolve().parent.parent.parent

NOME_APP = "JW-LibriX"


def _xdg(variabile: str, ripiego: str) -> Path:
    scelta = os.environ.get(variabile)
    return Path(scelta).expanduser() if scelta else Path.home() / ripiego


#: Dove sta la piccola configurazione che dice dov'e' la cartella dati.
CARTELLA_CONFIG = _xdg("XDG_CONFIG_HOME", ".config") / NOME_APP
FILE_PERCORSO = CARTELLA_CONFIG / "percorso_dati.json"

#: La cartella dati se l'utente non ne ha scelta un'altra.
PREDEFINITA = _xdg("XDG_DATA_HOME", ".local/share") / NOME_APP

#: La vecchia cartella dentro il programma: da qui si possono importare i
#: dati delle versioni di prima.
VECCHIA_ACCANTO_AL_PROGRAMMA = RADICE_PROGRAMMA / "dati"


# ---------------------------------------------------------------------------
# LA SCELTA SALVATA
# ---------------------------------------------------------------------------

def _leggi_config() -> dict:
    try:
        dati = json.loads(FILE_PERCORSO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _scrivi_config(dati: dict) -> None:
    CARTELLA_CONFIG.mkdir(parents=True, exist_ok=True)
    temporaneo = FILE_PERCORSO.with_suffix(".tmp")
    temporaneo.write_text(json.dumps(dati, indent=2, ensure_ascii=False), encoding="utf-8")
    temporaneo.replace(FILE_PERCORSO)


def cartella_scelta() -> Path | None:
    """La cartella scelta nelle Impostazioni, o None se si usa la predefinita."""
    scelta = _leggi_config().get("cartella")
    return Path(scelta).expanduser() if scelta else None


def da_variabile() -> bool:
    """True se la cartella la decide ``JWL_HOME``: le Impostazioni non contano."""
    return bool(os.environ.get("JWL_HOME"))


def salva_cartella(nuova: Path | None, copia_da: Path | None = None,
                   sposta: bool = False) -> None:
    """Salva la cartella dati da usare dal prossimo avvio.

    ``nuova`` None vuol dire: torna alla predefinita.  ``copia_da``, se c'e',
    e' una cartella i cui file vanno copiati nella nuova all'avvio.
    """
    dati = _leggi_config()
    if nuova is None or Path(nuova).expanduser().resolve() == PREDEFINITA.resolve():
        dati.pop("cartella", None)
    else:
        dati["cartella"] = str(Path(nuova).expanduser().resolve())
    if copia_da is not None:
        dati["copia_da"] = str(Path(copia_da).expanduser().resolve())
        if sposta:
            dati["sposta"] = True
        else:
            dati.pop("sposta", None)
    else:
        dati.pop("copia_da", None)
        dati.pop("sposta", None)
    _scrivi_config(dati)


def importa_al_prossimo_avvio(sorgente: Path) -> None:
    """Copia i file di ``sorgente`` nella cartella dati attuale, al riavvio."""
    dati = _leggi_config()
    dati["copia_da"] = str(Path(sorgente).expanduser().resolve())
    dati.pop("sposta", None)
    _scrivi_config(dati)


def scelta_fatta() -> bool:
    """True se la domanda del primo avvio («Dove salvo i dati?») ha gia' risposta."""
    dati = _leggi_config()
    return bool(dati.get("scelta_fatta") or dati.get("cartella"))


def segna_scelta_fatta() -> None:
    dati = _leggi_config()
    dati["scelta_fatta"] = True
    dati.pop("da_chiedere", None)
    _scrivi_config(dati)


def da_chiedere() -> bool:
    """True finche' l'utente non ha risposto a «Dove salvo i dati?».

    LA DECISIONE SI PRENDE UNA VOLTA, ALL'INIZIO, E SI SALVA
    --------------------------------------------------------
    Va chiamata per la prima volta appena parte l'app, PRIMA che qualcuno
    scriva nella cartella dati: il primo avvio scarica il catalogo e apre il
    log, e dopo la cartella predefinita esiste gia'.  Se la domanda guardasse
    «c'e' gia' userData?» a quel punto, risponderebbe sempre «si'» e non
    verrebbe mai fatta.  Quindi la prima volta si scrive «da_chiedere» nella
    configurazione, e resta fino alla risposta: anche se l'app si chiude
    prima, al prossimo avvio la domanda c'e' ancora.
    """
    if da_variabile():
        return False
    dati = _leggi_config()
    if dati.get("scelta_fatta") or dati.get("cartella"):
        return False
    if dati.get("da_chiedere"):
        return True
    # Chi ha gia' i dati nella predefinita (versione di prima) non si disturba.
    if (PREDEFINITA / "userData").is_dir():
        segna_scelta_fatta()
        return False
    dati["da_chiedere"] = True
    _scrivi_config(dati)
    return True


def copia_in_sospeso() -> Path | None:
    origine = _leggi_config().get("copia_da")
    return Path(origine) if origine else None


def _root() -> Path:
    scelta = os.environ.get("JWL_HOME")
    if scelta:
        return Path(scelta).expanduser()
    return cartella_scelta() or PREDEFINITA


# ---------------------------------------------------------------------------
# LA COPIA ALL'AVVIO
# ---------------------------------------------------------------------------

def _file_da_copiare(origine: Path) -> list[Path]:
    return [p for p in origine.rglob("*") if p.is_file() and not p.is_symlink()]


def esegui_copia_in_sospeso(avanza=None) -> str:
    """Fa la copia chiesta dalle Impostazioni.  Ritorna '' o il motivo dell'errore.

    Va chiamata all'avvio PRIMA che si apra qualunque database.  I file con
    lo stesso nome vengono sostituiti: chi importa vuole i dati che ha scelto.
    ``avanza(fatti, totale)`` serve a mostrare il progresso.
    """
    origine = copia_in_sospeso()
    if origine is None:
        return ""
    # La richiesta si toglie subito: se la copia si rompe a meta', al
    # prossimo avvio l'app deve partire, non riprovare all'infinito.
    dati = _leggi_config()
    sposta = bool(dati.pop("sposta", False))
    dati.pop("copia_da", None)
    _scrivi_config(dati)

    destinazione = Paths.root
    try:
        if not origine.is_dir():
            return f"La cartella da copiare non c'e' piu': {origine}"
        if origine.resolve() == destinazione.resolve():
            return ""
        file = _file_da_copiare(origine)
        destinazione.mkdir(parents=True, exist_ok=True)
        for numero, sorgente in enumerate(file, 1):
            arrivo = destinazione / sorgente.relative_to(origine)
            arrivo.parent.mkdir(parents=True, exist_ok=True)
            if sposta:
                # Sullo stesso disco e' un cambio di nome, istantaneo; su un
                # altro disco shutil copia e poi cancella.
                shutil.move(str(sorgente), str(arrivo))
            else:
                shutil.copy2(sorgente, arrivo)
            if avanza is not None:
                avanza(numero, len(file))
        if sposta:
            # Restano le cartelle vuote: si tolgono dal fondo verso l'alto.
            for cartella in sorted((p for p in origine.rglob("*") if p.is_dir()),
                                   key=lambda p: len(p.parts), reverse=True):
                try:
                    cartella.rmdir()
                except OSError:
                    pass
            try:
                origine.rmdir()
            except OSError:
                pass
    except OSError as errore:
        return f"Copia non riuscita: {errore}"
    return ""


def spazio_occupato(cartella: Path) -> int:
    totale = 0
    try:
        for p in cartella.rglob("*"):
            try:
                if p.is_file() and not p.is_symlink():
                    totale += p.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return totale


class Paths:
    """Tutti i percorsi dell'app in un posto solo.

    Le lezioni su questo modulo sono in COME-FUNZIONA.txt sezione 10: se il
    percorso vecchio compariva in 17 punti su 12 file, il giorno che cambia
    la radice ne restavano due indietro.  Qui la radice e' scritta una volta
    e da li in poi tutti leggono ``Paths.<campo>``.
    """

    root = _root()

    db_path = root / "userData" / "user_data.db"
    user_data_path = root / "userData"
    db_path_shm = root / "userData" / "user_data.db-shm"
    db_path_wal = root / "userData" / "user_data.db-wal"
    json_path = root / "userData" / "manifest.json"
    json_def_path = root / "userData" / "manifestDefault.json"
    log_path = root / "userData" / "jwlibrary.log"
    plugin_path = root / "plugin"

    @classmethod
    def prepare(cls) -> None:
        """Crea la radice e la cartella userData se mancano.

        IL DATABASE VA MESSO QUI, PRIMA DI CHIUNQUE LO APRA
        ---------------------------------------------------
        Con la cartella dati vuota il primo gestore (note, segnalibri...)
        apriva ``user_data.db`` prima che `Stuff.add_base_files` ci copiasse
        il modello: SQLite crea un file da 0 byte, senza tabelle, e
        `add_base_files` lo trovava «gia' presente» e non lo toccava piu'.
        Il risultato era «no such table: Note» a ogni avvio.  Tutti i gestori
        passano da qui prima di aprire il database, quindi il modello si
        copia qui: se il file manca, o e' vuoto.
        """
        cls.user_data_path.mkdir(parents=True, exist_ok=True)
        modello = RADICE_PROGRAMMA / "Files" / "user_data.db"
        try:
            vuoto = not cls.db_path.exists() or cls.db_path.stat().st_size == 0
        except OSError:
            vuoto = False
        if vuoto and modello.is_file():
            # Un -wal o un -shm rimasti accanto a un database vuoto non sono
            # suoi: SQLite proverebbe a riapplicarli sul modello.
            for resto in (cls.db_path_wal, cls.db_path_shm):
                resto.unlink(missing_ok=True)
            shutil.copyfile(modello, cls.db_path)
