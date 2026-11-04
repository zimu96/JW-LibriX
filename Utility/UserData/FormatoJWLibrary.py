#
#  FormatoJWLibrary.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Il file ``.jwlibrary``: lo stesso di Android, Windows, iOS e iPadOS.

Un backup e' uno ZIP con tre voci:

    userData.db            il database, schema 16
    manifest.json          nome, data, dispositivo, sha256 del database
    default_thumbnail.png  la miniatura

NON SI CAMBIA NIENTE: il nome del file (``UserdataBackup_<data>_<dispositivo>
.jwlibrary``), il nome del database e lo schema sono quelli che le altre app
riconoscono.  Questo modulo non apre finestre: converte fra quel formato e il
database interno dell'app (``user_data.db``), che ha uno schema piu' semplice.

COSA CONTIENE
-------------
Preferiti, segnalibri, sottolineature, appunti, etichette e campi di testo.
Non contiene i pacchetti scaricati e non contiene le impostazioni.

I PREFERITI
-----------
Nel formato sono un'etichetta (``Tag`` di tipo 0, "Favorite") collegata a delle
``Location``.  L'app li tiene in ``preferiti.json``: all'import si convertono
in quel file, all'export si riconvertono.  Un preferito non scaricato resta un
preferito: la Home lo mostra con la nuvoletta per scaricarlo.

COSA NON PASSA
--------------
Le playlist: nel formato sono altre tabelle, che puntano a file media dentro
il backup, e l'app le tiene con uno schema suo.  Restano com'erano nell'app e
non finiscono nel file esportato.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import socket
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from Utility.Structures.Paths import Paths, RADICE_PROGRAMMA

SCHEMA_VERSION = 16
NOME_DB = "userData.db"
NOME_DB_VECCHIO = "user_data.db"
FILE_SCHEMA = RADICE_PROGRAMMA / "Files" / "userData_schema.sql"
FILE_MINIATURA = RADICE_PROGRAMMA / "Files" / "default_thumbnail.png"

TAG_PREFERITO = 0
TAG_ETICHETTA = 1
TAG_PLAYLIST = 2

LOC_PUBBLICAZIONE = 1
LOC_AUDIO = 2
LOC_VIDEO = 3


class ErroreBackup(Exception):
    """Un backup che non si puo' leggere o scrivere, con il motivo in italiano."""


# ----------------------------------------------------------------------
# NOMI
# ----------------------------------------------------------------------

def nome_dispositivo() -> str:
    try:
        nome = socket.gethostname()
    except OSError:
        nome = ""
    return (nome or "Linux").replace(" ", "_")


def nome_file(quando: datetime.datetime | None = None) -> str:
    """``UserdataBackup_2026-08-15_Realme_RMX3867.jwlibrary``."""
    quando = quando or datetime.datetime.now()
    return f"UserdataBackup_{quando:%Y-%m-%d}_{nome_dispositivo()}.jwlibrary"


# ----------------------------------------------------------------------
# SQLITE: PICCOLI AIUTI
# ----------------------------------------------------------------------

# Le colonne di ogni tabella, calcolate una volta per operazione
_colonne_tabella: dict[tuple[int, str], list[str]] = {}


def _inserisci(dst: sqlite3.Connection, tabella: str, riga: dict) -> int:
    """Inserisce una riga con le sole colonne che la tabella ha."""
    chiave = (id(dst), tabella)
    if chiave not in _colonne_tabella:
        _colonne_tabella[chiave] = [r[1] for r in dst.execute(f'PRAGMA table_info("{tabella}")')]
    colonne = [k for k in riga if k in _colonne_tabella[chiave]]
    cur = dst.execute(
        f'INSERT INTO "{tabella}" ({",".join(colonne)}) VALUES ({",".join("?" * len(colonne))})',
        [riga[k] for k in colonne])
    return cur.lastrowid


def _righe(c: sqlite3.Connection, tabella: str, ordine: str = "") -> list[dict]:
    esiste = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (tabella,)).fetchone()
    if not esiste:
        return []
    vecchia = c.row_factory
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(f'SELECT * FROM "{tabella}" {ordine}')]
    finally:
        c.row_factory = vecchia


def _titolo_catalogo(sigla: str, issue: int, lingua: int) -> str:
    """Il titolo dal catalogo, se c'e'; altrimenti la sigla."""
    try:
        catalogo = Paths.root / "catalog.db"
        if catalogo.is_file():
            c = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True)
            try:
                r = c.execute(
                    'SELECT Title FROM Publication WHERE KeySymbol=? AND IssueTagNumber=? '
                    'AND MepsLanguageId=?', (sigla, issue, lingua)).fetchone()
                if r and r[0]:
                    return r[0]
            finally:
                c.close()
    except sqlite3.Error:
        pass
    return sigla


class _Avanzamento:
    """Comunica a che punto si e' (da 0 a 1) a chi disegna la barra."""

    TABELLE = ("Location", "UserMark", "BlockRange", "Note", "Bookmark", "InputField",
               "Tag", "TagMap")

    def __init__(self, callback, src: sqlite3.Connection | None, base: float = 0.0,
                 ampiezza: float = 1.0, extra: int = 0) -> None:
        self.cb = callback
        self.base, self.ampiezza = base, ampiezza
        self.fatti = 0
        self.totale = max(1, extra)
        if src is not None:
            for t in self.TABELLE:
                try:
                    self.totale += src.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                except sqlite3.Error:
                    pass
        self._ultimo = 0
        self._passo = max(1, self.totale // 300)

    def dici(self, frazione: float, testo: str) -> None:
        if self.cb:
            self.cb(min(1.0, self.base + self.ampiezza * frazione), testo)

    def itera(self, righe, testo: str):
        self.dici(self.fatti / self.totale, testo)
        for r in righe:
            yield r
            self.fatti += 1
            if self.fatti - self._ultimo >= self._passo:
                self._ultimo = self.fatti
                self.dici(self.fatti / self.totale, testo)


# ----------------------------------------------------------------------
# PREFERITI <-> LOCATION
# ----------------------------------------------------------------------

def _voce_in_location(voce: dict) -> dict:
    """Un preferito dell'app come riga di ``Location``."""
    from Utility import Lingua
    sigla = voce.get("pubblicazione", "")
    lingua = Lingua.da_simbolo(voce.get("lingua") or "I")
    issue = int(voce.get("issue") or 0)
    try:
        traccia = int(voce.get("traccia")) if voce.get("traccia") not in (None, "", 0) else None
    except (TypeError, ValueError):
        traccia = None
    if traccia is None:
        return {"KeySymbol": sigla, "IssueTagNumber": issue, "MepsLanguage": lingua,
                "Type": LOC_PUBBLICAZIONE}
    tipo = LOC_AUDIO if str(voce.get("formato", "")).upper() == "AUDIO" else LOC_VIDEO
    riga = {"IssueTagNumber": issue, "MepsLanguage": lingua, "Track": traccia, "Type": tipo}
    if sigla.startswith("docid-"):
        riga["KeySymbol"] = None
        riga["DocumentId"] = int(sigla[6:])
    else:
        riga["KeySymbol"] = sigla
        if voce.get("docid"):
            riga["DocumentId"] = int(voce["docid"])
    return riga


def _location_in_voce(loc: dict) -> dict | None:
    """Una ``Location`` dei preferiti come voce di ``preferiti.json``."""
    from Utility import Lingua
    tipo = loc.get("Type")
    if tipo not in (LOC_PUBBLICAZIONE, LOC_AUDIO, LOC_VIDEO):
        return None
    sigla = loc.get("KeySymbol") or ""
    if not sigla and loc.get("DocumentId"):
        sigla = f"docid-{loc['DocumentId']}"
    if not sigla:
        return None
    meps = loc.get("MepsLanguage")
    voce = {"pubblicazione": sigla,
            "lingua": Lingua.da_numero(meps) if meps is not None else "I"}
    issue = int(loc.get("IssueTagNumber") or 0)
    if tipo == LOC_PUBBLICAZIONE:
        voce["titolo"] = loc.get("Title") or _titolo_catalogo(sigla, issue, meps if meps is not None else 4)
    else:
        docid = loc.get("DocumentId")
        voce["titolo"] = loc.get("Title") or (
            f"Documento {docid} - traccia {loc.get('Track')}" if sigla.startswith("docid-")
            else f"{sigla} - traccia {loc.get('Track')}")
        voce["traccia"] = int(loc.get("Track") or 1)
        voce["formato"] = "AUDIO" if tipo == LOC_AUDIO else "VIDEO"
        if docid and not sigla.startswith("docid-"):
            voce["docid"] = int(docid)
    if issue:
        voce["issue"] = issue
    return voce


# ----------------------------------------------------------------------
# ESPORTARE
# ----------------------------------------------------------------------

def costruisci_database(destinazione: Path, origine: Path | None = None,
                        preferiti: list[dict] | None = None, progresso=None,
                        base: float = 0.0, ampiezza: float = 1.0) -> dict:
    """Scrive ``userData.db`` (schema 16) a partire dal database dell'app.

    Ritorna un riepilogo con i conteggi.
    """
    origine = origine or Paths.db_path
    if preferiti is None:
        from Utility import Preferiti
        preferiti = Preferiti.leggi()
    destinazione.unlink(missing_ok=True)
    _colonne_tabella.clear()

    dst = sqlite3.connect(str(destinazione))
    dst.executescript(FILE_SCHEMA.read_text(encoding="utf-8"))
    ora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dst.execute("INSERT INTO PlaylistItemAccuracy VALUES (1,'Accurate'),(2,'NeedsUserVerification')")
    dst.execute("INSERT INTO android_metadata VALUES ('it_IT')")
    # Il formato vieta INSERT in LastModified: la riga la mette lo schema
    # solo se la si inserisce prima dei trigger, quindi si toglie il trigger un attimo.
    dst.execute("DROP TRIGGER TR_Raise_Error_Before_Insert_LastModified")
    dst.execute("INSERT INTO LastModified VALUES (?)", (ora,))

    conteggi = {"preferiti": 0, "segnalibri": 0, "sottolineature": 0, "appunti": 0, "etichette": 0}
    src = sqlite3.connect(f"file:{origine}?mode=ro", uri=True) if origine.is_file() else None
    try:
        av = _Avanzamento(progresso, src, base, ampiezza, extra=len(preferiti))
        mappa_loc: dict[int, int] = {}
        mappa_mark: dict[int, int] = {}
        mappa_tag: dict[int, int] = {}
        mappa_nota: dict[int, int] = {}

        # Il tag dei preferiti c'e' sempre, e per primo
        tag_pref = _inserisci(dst, "Tag", {"Type": TAG_PREFERITO, "Name": "Favorite"})

        if src is not None:
            for r in av.itera(_righe(src, "Location", "ORDER BY LocationId"), "Preparo le posizioni"):
                try:
                    mappa_loc[r["LocationId"]] = _inserisci(dst, "Location", r)
                except sqlite3.IntegrityError as e:
                    print(f"Location {r['LocationId']} saltata nel backup: {e} ⚠️")
            for r in av.itera(_righe(src, "UserMark", "ORDER BY UserMarkId"), "Salvo le sottolineature"):
                if r["LocationId"] not in mappa_loc:
                    continue
                r["LocationId"] = mappa_loc[r["LocationId"]]
                mappa_mark[r["UserMarkId"]] = _inserisci(dst, "UserMark", r)
            conteggi["sottolineature"] = len(mappa_mark)
            for r in av.itera(_righe(src, "BlockRange"), "Salvo le sottolineature"):
                if r["UserMarkId"] in mappa_mark:
                    r["UserMarkId"] = mappa_mark[r["UserMarkId"]]
                    _inserisci(dst, "BlockRange", r)
            for r in av.itera(_righe(src, "Note", "ORDER BY NoteId"), "Salvo gli appunti"):
                r["UserMarkId"] = mappa_mark.get(r.get("UserMarkId"))
                r["LocationId"] = mappa_loc.get(r.get("LocationId"))
                r["Created"] = r.get("Created") or r.get("LastModified") or ora
                try:
                    mappa_nota[r["NoteId"]] = _inserisci(dst, "Note", r)
                except sqlite3.IntegrityError as e:
                    print(f"Appunto {r['NoteId']} saltato nel backup: {e} ⚠️")
            conteggi["appunti"] = len(mappa_nota)
            for r in av.itera(_righe(src, "Bookmark", "ORDER BY BookmarkId"), "Salvo i segnalibri"):
                if r["LocationId"] in mappa_loc and r["PublicationLocationId"] in mappa_loc:
                    r["LocationId"] = mappa_loc[r["LocationId"]]
                    r["PublicationLocationId"] = mappa_loc[r["PublicationLocationId"]]
                    _inserisci(dst, "Bookmark", r)
                    conteggi["segnalibri"] += 1
            for r in av.itera(_righe(src, "InputField"), "Salvo i campi di testo"):
                if r["LocationId"] in mappa_loc:
                    r["LocationId"] = mappa_loc[r["LocationId"]]
                    _inserisci(dst, "InputField", r)

            for r in av.itera(_righe(src, "Tag", "ORDER BY TagId"), "Salvo le etichette"):
                if r["Type"] == TAG_ETICHETTA:
                    mappa_tag[r["TagId"]] = _inserisci(dst, "Tag", r)
            conteggi["etichette"] = len(mappa_tag)
            for r in av.itera(_righe(src, "TagMap", "ORDER BY TagId, Position"), "Salvo le etichette"):
                if r["TagId"] in mappa_tag and r.get("NoteId") in mappa_nota:
                    r["TagId"] = mappa_tag[r["TagId"]]
                    r["NoteId"] = mappa_nota[r["NoteId"]]
                    r["PlaylistItemId"] = None
                    r["LocationId"] = None
                    _inserisci(dst, "TagMap", r)

        posizione = 0
        for voce in av.itera(list(preferiti), "Salvo i preferiti"):
            if not voce.get("pubblicazione"):
                continue
            try:
                loc = _voce_in_location(voce)
            except (TypeError, ValueError):
                continue
            where = " AND ".join(f"{k} IS ?" for k in loc)
            esistente = dst.execute(f"SELECT LocationId FROM Location WHERE {where}",
                                    list(loc.values())).fetchone()
            try:
                loc_id = esistente[0] if esistente else _inserisci(dst, "Location", loc)
                dst.execute("INSERT INTO TagMap (LocationId, TagId, Position) VALUES (?,?,?)",
                            (loc_id, tag_pref, posizione))
            except sqlite3.IntegrityError as e:
                print(f"Preferito {voce.get('pubblicazione')} saltato: {e} ⚠️")
                continue
            posizione += 1
            conteggi["preferiti"] += 1

        dst.execute("CREATE TRIGGER TR_Raise_Error_Before_Insert_LastModified BEFORE INSERT ON "
                    "LastModified BEGIN SELECT RAISE (FAIL, 'INSERT INTO LastModified not allowed'); END;")
        dst.commit()
    finally:
        if src is not None:
            src.close()
        dst.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
        dst.execute("PRAGMA journal_mode=DELETE")
        dst.commit()
        dst.close()
        _colonne_tabella.clear()
    return conteggi


def _sha256(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def crea_backup(destinazione: Path, origine: Path | None = None,
                preferiti: list[dict] | None = None, progresso=None) -> dict:
    """Scrive il file ``.jwlibrary`` in ``destinazione``.  Ritorna i conteggi."""
    destinazione = Path(destinazione)
    try:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ErroreBackup(f"Non riesco a scrivere il backup: {e}") from e
    with tempfile.TemporaryDirectory(prefix="jwl-backup-") as tmp:
        db = Path(tmp) / NOME_DB
        if progresso:
            progresso(0.0, "Leggo i dati")
        conteggi = costruisci_database(db, origine, preferiti, progresso, 0.0, 0.85)
        if progresso:
            progresso(0.88, "Calcolo l'impronta del file")
        adesso = datetime.datetime.now(datetime.timezone.utc)
        manifest = {
            "name": destinazione.name,
            "creationDate": datetime.datetime.now().strftime("%Y-%m-%d"),
            "version": 1,
            "type": 0,
            "userDataBackup": {
                "lastModifiedDate": adesso.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "deviceName": nome_dispositivo(),
                "databaseName": NOME_DB,
                "hash": _sha256(db),
                "schemaVersion": SCHEMA_VERSION,
            },
        }
        if progresso:
            progresso(0.92, "Comprimo il backup")
        temporaneo = destinazione.with_name(destinazione.name + ".parziale")
        try:
            with zipfile.ZipFile(temporaneo, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(db, NOME_DB)
                z.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
                if FILE_MINIATURA.is_file():
                    z.write(FILE_MINIATURA, "default_thumbnail.png")
            temporaneo.replace(destinazione)
        except OSError as e:
            temporaneo.unlink(missing_ok=True)
            raise ErroreBackup(f"Non riesco a scrivere il backup: {e}") from e
        if progresso:
            progresso(1.0, "Backup completato")
    return conteggi


# ----------------------------------------------------------------------
# IMPORTARE
# ----------------------------------------------------------------------

def leggi_manifest(percorso: Path) -> dict:
    """Il manifesto di un backup, o ``ErroreBackup`` se non e' un backup."""
    try:
        with zipfile.ZipFile(percorso) as z:
            voci = z.namelist()
            return json.loads(z.read("manifest.json")) if "manifest.json" in voci else {}
    except (OSError, zipfile.BadZipFile, ValueError) as e:
        raise ErroreBackup("Il file non e' un backup di JW Library valido.") from e


def _prepara_db_app() -> None:
    """Porta ``Location`` dell'app allo schema del formato.

    Servono le colonne in piu' e ``MepsLanguage`` che puo' mancare: cosi'
    l'app accetta le righe di qualunque backup.  Una copia del database
    com'era resta accanto, con il suffisso ``.prima-migrazione``.
    """
    Paths.prepare()
    if not Paths.db_path.is_file():
        shutil.copyfile(RADICE_PROGRAMMA / "Files" / "user_data.db", Paths.db_path)
    c = sqlite3.connect(str(Paths.db_path), timeout=30)
    try:
        if "Specialty" in [r[1] for r in c.execute("PRAGMA table_info(Location)")]:
            return
        schema = sqlite3.connect(":memory:")
        schema.executescript(FILE_SCHEMA.read_text(encoding="utf-8"))
        ddl = schema.execute("SELECT name, sql FROM sqlite_master WHERE tbl_name='Location' "
                             "AND sql IS NOT NULL ORDER BY type DESC").fetchall()
        schema.close()
        shutil.copyfile(Paths.db_path, Paths.db_path.with_name(NOME_DB_VECCHIO + ".prima-migrazione"))
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("BEGIN")
        vecchie = [r[1] for r in c.execute("PRAGMA table_info(Location)")]
        for nome, sql in ddl:
            if nome == "Location":
                c.execute(sql.replace('CREATE TABLE "Location"', "CREATE TABLE Location_nuova", 1))
        c.execute(f"INSERT INTO Location_nuova ({','.join(vecchie)}) "
                  f"SELECT {','.join(vecchie)} FROM Location")
        c.execute("DROP TABLE Location")
        c.execute("ALTER TABLE Location_nuova RENAME TO Location")
        for nome, sql in ddl:
            if nome != "Location":
                c.execute(sql)
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def importa_backup(percorso: Path, progresso=None) -> dict:
    """Mette il contenuto di un ``.jwlibrary`` dentro l'app.

    Sostituisce preferiti, segnalibri, sottolineature, appunti ed etichette.
    Prima di toccare qualcosa salva una copia di quello che c'era in
    ``userData/prima-dell-import``.
    """
    percorso = Path(percorso)
    if progresso:
        progresso(0.0, "Apro il backup")
    manifest = leggi_manifest(percorso)
    info = manifest.get("userDataBackup", {})
    nome_db = info.get("databaseName") or NOME_DB

    with tempfile.TemporaryDirectory(prefix="jwl-import-") as tmp:
        estratto = Path(tmp) / "sorgente.db"
        try:
            with zipfile.ZipFile(percorso) as z:
                voci = z.namelist()
                scelto = next((n for n in (nome_db, NOME_DB, NOME_DB_VECCHIO) if n in voci), None)
                if scelto is None:
                    raise ErroreBackup("Nel backup non c'e' il database (userData.db).")
                with z.open(scelto) as s, open(estratto, "wb") as d:
                    shutil.copyfileobj(s, d)
        except (OSError, zipfile.BadZipFile) as e:
            raise ErroreBackup(f"Non riesco a leggere il backup: {e}") from e

        if progresso:
            progresso(0.04, "Controllo il database")
        try:
            src = sqlite3.connect(str(estratto))
            if src.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                src.close()
                raise ErroreBackup("Il database del backup e' danneggiato.")
        except sqlite3.Error as e:
            raise ErroreBackup("Il database del backup non si apre.") from e

        try:
            if progresso:
                progresso(0.07, "Salvo una copia di sicurezza")
            _salva_copia_di_sicurezza()
            _prepara_db_app()
            return _importa(src, info.get("schemaVersion"), progresso)
        except sqlite3.Error as e:
            raise ErroreBackup(f"Errore nel database: {e}") from e
        finally:
            src.close()


def _salva_copia_di_sicurezza() -> None:
    from Utility import Preferiti
    cartella = Paths.user_data_path / "prima-dell-import"
    cartella.mkdir(parents=True, exist_ok=True)
    sigla = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if Paths.db_path.is_file():
        shutil.copyfile(Paths.db_path, cartella / f"user_data-{sigla}.db")
    pref = Preferiti._percorso()
    if pref.is_file():
        shutil.copyfile(pref, cartella / f"preferiti-{sigla}.json")
    for modello in ("user_data-*.db", "preferiti-*.json"):
        for vecchia in sorted(cartella.glob(modello))[:-5]:
            vecchia.unlink(missing_ok=True)


def _importa(src: sqlite3.Connection, versione, progresso=None) -> dict:
    conteggi = {"preferiti": 0, "segnalibri": 0, "sottolineature": 0, "appunti": 0,
                "etichette": 0, "playlist_saltate": 0,
                "versione_nuova": isinstance(versione, int) and versione > SCHEMA_VERSION}
    _colonne_tabella.clear()
    preferiti: list[dict] = []
    av = _Avanzamento(progresso, src, 0.10, 0.88)

    dst = sqlite3.connect(str(Paths.db_path), timeout=30)
    try:
        dst.execute("PRAGMA foreign_keys=OFF")
        dst.execute("BEGIN")
        # Via quello che si sostituisce.  Le Location usate dalle playlist
        # dell'app restano, perche' le playlist non si toccano.
        dst.execute("DELETE FROM BlockRange")
        dst.execute("DELETE FROM InputField")
        dst.execute("DELETE FROM TagMap WHERE PlaylistItemId IS NULL")
        dst.execute("DELETE FROM Bookmark")
        dst.execute("DELETE FROM Note")
        dst.execute("DELETE FROM UserMark")
        dst.execute("DELETE FROM Tag WHERE Type != ?", (TAG_PLAYLIST,))
        dst.execute("DELETE FROM Location WHERE LocationId NOT IN "
                    "(SELECT LocationId FROM PlaylistMedia WHERE LocationId IS NOT NULL)")

        mappa_loc: dict[int, int] = {}
        luoghi_src: dict[int, dict] = {}
        for r in av.itera(_righe(src, "Location", "ORDER BY LocationId"), "Importo le posizioni"):
            luoghi_src[r["LocationId"]] = dict(r)
            try:
                mappa_loc[r["LocationId"]] = _inserisci(dst, "Location", r)
            except sqlite3.IntegrityError:
                chiavi = [k for k in ("BookNumber", "ChapterNumber", "DocumentId", "Track",
                                      "IssueTagNumber", "KeySymbol", "MepsLanguage", "Type")
                          if k in r]
                esistente = dst.execute(
                    "SELECT LocationId FROM Location WHERE " + " AND ".join(f"{k} IS ?" for k in chiavi),
                    [r[k] for k in chiavi]).fetchone()
                if esistente:
                    mappa_loc[r["LocationId"]] = esistente[0]

        mappa_mark: dict[int, int] = {}
        for r in av.itera(_righe(src, "UserMark", "ORDER BY UserMarkId"), "Importo le sottolineature"):
            if r["LocationId"] not in mappa_loc:
                continue
            r["LocationId"] = mappa_loc[r["LocationId"]]
            try:
                mappa_mark[r["UserMarkId"]] = _inserisci(dst, "UserMark", r)
            except sqlite3.IntegrityError:
                pass
        conteggi["sottolineature"] = len(mappa_mark)
        for r in av.itera(_righe(src, "BlockRange"), "Importo le sottolineature"):
            if r["UserMarkId"] in mappa_mark:
                r["UserMarkId"] = mappa_mark[r["UserMarkId"]]
                _inserisci(dst, "BlockRange", r)

        mappa_nota: dict[int, int] = {}
        for r in av.itera(_righe(src, "Note", "ORDER BY NoteId"), "Importo gli appunti"):
            r["UserMarkId"] = mappa_mark.get(r.get("UserMarkId"))
            r["LocationId"] = mappa_loc.get(r.get("LocationId"))
            try:
                mappa_nota[r["NoteId"]] = _inserisci(dst, "Note", r)
            except sqlite3.IntegrityError:
                pass
        conteggi["appunti"] = len(mappa_nota)

        for r in av.itera(_righe(src, "Bookmark", "ORDER BY BookmarkId"), "Importo i segnalibri"):
            if r["LocationId"] in mappa_loc and r["PublicationLocationId"] in mappa_loc:
                r["LocationId"] = mappa_loc[r["LocationId"]]
                r["PublicationLocationId"] = mappa_loc[r["PublicationLocationId"]]
                try:
                    _inserisci(dst, "Bookmark", r)
                    conteggi["segnalibri"] += 1
                except sqlite3.IntegrityError:
                    pass
        for r in av.itera(_righe(src, "InputField"), "Importo i campi di testo"):
            if r["LocationId"] in mappa_loc:
                r["LocationId"] = mappa_loc[r["LocationId"]]
                try:
                    _inserisci(dst, "InputField", r)
                except sqlite3.IntegrityError:
                    pass

        # Le etichette (tipo 1) passano, i preferiti (tipo 0) diventano
        # preferiti.json, le playlist (tipo 2) non si importano.
        mappa_tag: dict[int, int] = {}
        tag_preferiti: set[int] = set()
        for r in av.itera(_righe(src, "Tag", "ORDER BY TagId"), "Importo le etichette"):
            if r["Type"] == TAG_ETICHETTA:
                try:
                    mappa_tag[r["TagId"]] = _inserisci(dst, "Tag", r)
                except sqlite3.IntegrityError:
                    pass
            elif r["Type"] == TAG_PREFERITO:
                tag_preferiti.add(r["TagId"])
        conteggi["etichette"] = len(mappa_tag)

        for r in av.itera(_righe(src, "TagMap", "ORDER BY TagId, Position"), "Importo preferiti ed etichette"):
            if r["TagId"] in mappa_tag and r.get("NoteId") in mappa_nota:
                r["TagId"] = mappa_tag[r["TagId"]]
                r["NoteId"] = mappa_nota[r["NoteId"]]
                r["PlaylistItemId"] = None
                r["LocationId"] = None
                try:
                    _inserisci(dst, "TagMap", r)
                except sqlite3.IntegrityError:
                    pass
            elif r["TagId"] in tag_preferiti and r.get("LocationId") in luoghi_src:
                voce = _location_in_voce(luoghi_src[r["LocationId"]])
                if voce:
                    preferiti.append(voce)
            elif r.get("PlaylistItemId") is not None:
                conteggi["playlist_saltate"] += 1
        conteggi["preferiti"] = len(preferiti)
        dst.commit()
    except Exception:
        dst.rollback()
        raise
    finally:
        _colonne_tabella.clear()
        try:
            dst.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        dst.close()

    if progresso:
        progresso(0.99, "Aggiorno i preferiti")
    from Utility import Preferiti
    Preferiti.scrivi(preferiti)
    if progresso:
        progresso(1.0, "Importazione completata")
    return conteggi
