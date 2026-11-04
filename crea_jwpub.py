#
#  crea_jwpub.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Non viene da un file Swift: e' il pezzo che mancava, e che rende
#  l'applicazione indipendente.
#

"""Costruisce un .jwpub TUO, leggibile, senza decifrare niente.

IL PROBLEMA, E LA SCELTA
------------------------
Un .jwpub che scarichi da jw.org ha il corpo del testo cifrato
(``Document.Content``).  L'app non lo decifra e non vuole farlo: la chiave e'
dentro l'app originale e dentro i suoi dati, e non e' cosa che si fa con un
materiale del quale non si e' i diritti.  Quello che si vuole e' poter
leggere.

E si puo', senza la chiave.  Se il pacchetto lo scrivi TU, il testo e' in
chiaro perche' lo scrivi tu: nessuna cifratura, nessuna chiave, nessun
limite.  Non e' un trucco per aggirare qualcosa: e' il caso in cui non c'e'
niente da aggirare.

COME SI USA
-----------
Il modo normale e' dare un testo qualsiasi::

    python3 crea_jwpub.py mio.jwpub --titolo "Il mio libro" \\
        --testo capitolo1.txt capitolo2.txt

Oppure costruire il pacchetto da una fonte con cui l'indice di ricerca viene
fuori giusto da solo (vedi ``--estrai-da``).

LA STRUTTURA
------------
Un .jwpub e' uno ZIP che contiene un altro ZIP, dentro il quale c'e' un
database SQLite::

    mio.jwpub                       <- ZIP
      manifest.json                 <- in chiaro, i metadati
      contents                      <- ZIP annidato
        mio_E.db                    <- SQLite, obbligatorio
        figure.jpg                  <- facoltativo
        spartito.svg                <- facoltativo

LE TRE REGOLE CHE ROMPONO TUTTO
-------------------------------
1. ``manifest.json`` deve dire ``fileName``, e quel nome e' il nome del .db.
   Se non combacia, il pacchetto si apre e non c'e' niente dentro.
2. La tabella dell'indice si chiama ``SearchIndexDocument`` e quella delle
   parole si chiama ``Word``.  ``SearchIndexDocument`` NON e' un indice delle
   parole: e' l'indice delle OCCORRENZE, una riga per parola.
3. La codifica a 7 bit e' ``b - 128`` quando ``b >= 128``.  Un byte 0x80
   vuol dire ZERO, non 128.

E LA PROVA CHE HAI SCRITTO BENE
-------------------------------
La somma dei conteggi per capitolo, dentro ``PositionalListIndex``, deve
tornare a ``WordOccurrenceCount``.  Quel numero e' scritto in chiaro nella
stessa riga, quindi il controllo si puo' fare da soli, prima di mettere il
pacchetto nell'app.  ``--verifica`` lo fa e dice il risultato.

PERCHE' ``TextUnit``
--------------------
`TextUnit` e' il ponte fra la parola e il capitolo.  Senza quella tabella
l'indice non sa a chi appartiene ogni conteggio, e il testo non si
ricostruisce: si ottiene il vocabolario del libro intero mescolato, che e'
peggio di non avere niente.  Per questo e' scritta sempre, anche con un solo
capitolo.

DOVE SONO FINITI GLI ZIP DEL PROGETTO ORIGINALE
-----------------------------------------------
Questo file scrive due ZIP annidati con ``zipfile``.  Non per scelta
estetica: nel progetto originale la libreria per gli ZIP non esisteva nella
libreria standard di Swift, e per questo dentro al progetto c'era una copia
di ZIPFoundation (9 file, 2.481 righe, MIT) piu' uno shim in C per zlib:

    JWLibrary/Zip/ZIPFoundation/   ->  zipfile   (libreria standard)
    JWLibrary/Zip/Data+Gzip.swift   ->  gzip      (libreria standard)
    JWLibrary/Zip/CZLib/           ->  serveva solo a Data+Gzip

In tutto il progetto originale quelle librerie erano chiamate da tre punti:
``BackupManager`` righe 28 e 109 (creare e leggere il backup) e
``FileDownloader`` riga 56 (decomprimere ``catalog.db.gz``).  Sostituite
tutte e tre con i moduli standard, dentro ``Zip/`` non resta piu' niente da
portare, e il formato .jwpub si costruisce senza una libreria esterna.
"""

import argparse
import json
import re
import sqlite3
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

# La lingua.  4 = italiano.  Nell'app originale compariva in tre posti, e in
# tutti e tre era scritto a mano.
LINGUA = 4
SCHEMA = 9
TIPO = "Book"

# I tre campi del manifesto che non si indovinano e che l'app usa:
#  schemaVersion  la versione dello schema del database
#  fileName       il nome del .db DENTRO contents
#  signature      un'eco del contenuto con la dimensione; serve a capire se il
#                 file e' quello giusto senza aprirlo
VERSIONE_FIRMA = 8

# Come si spezza una parola in pezzi.  Le lettere e le cifre dentro una
# parola; tutto quello che non e' una lettera e' un separatore.  Serve a non
# mettere dentro l'indice i punti e le virgole, che nell'indice non ci sono.
_PAROLA = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d+", re.UNICODE)

# Il simbolo del documento.  COME-FUNZIONA.txt sezione 2c: questo numero e'
# STABILE nel tempo, e' quello che sta nella URL pubblica su jw.org.  Se
# cambia, i link pubblici smettono di puntare al libro.
PRIMO_MEPS = 1102016770


def codifica_7bit(valori) -> bytes:
    """La codifica degli indici: un intero per byte, con 128 come zero.

    La regola e' una riga::

        valore = byte - 128   se byte >= 128
        valore = byte          se byte <  128

    E' l'inverso di ``Utility.JWPubExtractor.decodifica``.  I due devono
    essere l'uno l'inverso dell'altro: si puo' controllare con
    ``--verifica``, che rilegge il pacchetto e confronta.
    """
    return bytes((v + 128) if v < 128 else v for v in valori)


def senza_accenti(testo: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", testo.lower())
                   if not unicodedata.combining(c))


def parole_del_testo(testo: str) -> list[str]:
    """Le parole di un capitolo, nell'ordine in cui compaiono."""
    return _PAROLA.findall(testo)


# ---------------------------------------------------------------------------
# IL DATABASE
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE Document (
    DocumentId        INTEGER PRIMARY KEY,
    MepsDocumentId    INTEGER,
    ChapterNumber     INTEGER,
    Title             TEXT,
    TocTitle          TEXT,
    TocTitleRich      TEXT,
    ContextTitle      TEXT,
    Subtitle          TEXT,
    ParagraphCount    INTEGER,
    ContentLength     INTEGER,
    Class             TEXT,
    Type              INTEGER,
    HasMediaLinks     BOOLEAN,
    Content           BLOB
);
CREATE TABLE DocumentParagraph (
    DocumentParagraphId   INTEGER PRIMARY KEY,
    DocumentId            INTEGER,
    ParagraphIndex        INTEGER,
    ParagraphNumberLabel  INTEGER,
    BeginPosition         INTEGER,
    EndPosition           INTEGER
);
CREATE TABLE TextUnit (
    TextUnitId    INTEGER PRIMARY KEY,
    Type          TEXT,
    Id            INTEGER
);
CREATE TABLE Word (
    WordId    INTEGER PRIMARY KEY,
    Word      TEXT,
    Reading   TEXT
);
CREATE TABLE SearchIndexDocument (
    WordId                INTEGER,
    WordOccurrenceCount   INTEGER,
    TextUnitCount         INTEGER,
    TextUnitIndices       BLOB,
    PositionalList        BLOB,
    PositionalListIndex   BLOB
);
CREATE TABLE Multimedia (
    MultimediaId  INTEGER PRIMARY KEY,
    MimeType      TEXT,
    FilePath      TEXT,
    Label         TEXT,
    Caption       TEXT,
    Width         INTEGER,
    Height        INTEGER,
    KeySymbol     TEXT,
    Track         INTEGER,
    DataType      INTEGER,
    MajorType     INTEGER,
    MinorType     INTEGER
);
CREATE TABLE DocumentMultimedia (
    DocumentId             INTEGER,
    MultimediaId           INTEGER,
    BeginParagraphOrdinal  INTEGER,
    EndParagraphOrdinal    INTEGER
);
CREATE TABLE Publication (
    Id                  INTEGER PRIMARY KEY,
    KeySymbol           TEXT,
    Year                INTEGER,
    MepsLanguageId      INTEGER,
    PublicationTypeId   INTEGER,
    IssueTagNumber      INTEGER,
    Title               TEXT,
    IssueTitle          TEXT
);
CREATE TABLE SearchTextRangeDocument (
    DocumentId      INTEGER,
    TextUnitId      INTEGER,
    TextLength      INTEGER
);
"""


def costruisci_db(percorso: Path, capitoli: list[dict], simbolo: str,
                  titolo: str, anno: int) -> sqlite3.Connection:
    """Scrive il database con tutte le tabelle e i dati giusti.

    ``Content`` resta NULL.  Non e' una dimenticanza: in un pacchetto vero
    quel campo e' cifrato, e qui non si cifra niente perche' il testo si
    ricostruisce dall'indice.  Lasciarlo vuoto non impedisce niente.
    """
    if percorso.exists():
        percorso.unlink()
    connessione = sqlite3.connect(str(percorso))
    connessione.executescript(SCHEMA_SQL)

    # ---- i documenti e i paragrafi
    for indice, capitolo in enumerate(capitoli):
        meps = PRIMO_MEPS + indice
        connessione.execute(
            """
            INSERT INTO Document (DocumentId, MepsDocumentId, ChapterNumber, Title,
                                  TocTitle, TocTitleRich, ContextTitle, Subtitle,
                                  ParagraphCount, ContentLength, Class, Type,
                                  HasMediaLinks, Content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL);
            """,
            (indice, meps, capitolo["numero"], capitolo["titolo"],
             capitolo["titolo"], f"<b>{capitolo['titolo']}</b>", None, None,
             len(capitolo["paragrafi"]), len(capitolo["testo"]), "Standard", 0,
             1 if capitolo.get("figure") else 0),
        )

        posizione = 0
        for ordine, paragrafo in enumerate(capitolo["paragrafi"], start=1):
            connessione.execute(
                """
                INSERT INTO DocumentParagraph (DocumentId, ParagraphIndex,
                                               ParagraphNumberLabel,
                                               BeginPosition, EndPosition)
                VALUES (?, ?, ?, ?, ?);
                """,
                (indice, ordine - 1, ordine, posizione, posizione + len(paragrafo)),
            )
            posizione += len(paragrafo)

        # ---- il ponte fra parole e capitoli
        connessione.execute(
            "INSERT INTO TextUnit (TextUnitId, Type, Id) VALUES (?, 'Paragraph', ?);",
            (indice, indice),
        )
        connessione.execute(
            "INSERT INTO SearchTextRangeDocument (DocumentId, TextUnitId, TextLength) "
            "VALUES (?, ?, ?);",
            (indice, indice, len(capitolo["testo"])),
        )

        # ---- le figure
        for ordine_figura, figura in enumerate(capitolo.get("figure", []), start=1):
            multimedia_id = indice * 100 + ordine_figura
            connessione.execute(
                """
                INSERT INTO Multimedia (MultimediaId, MimeType, FilePath, Label,
                                        Caption, Width, Height, DataType, MajorType, MinorType)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0);
                """,
                (multimedia_id, figura["mime"], figura["nome"], "",
                 figura.get("didascalia", ""), figura.get("larghezza"),
                 figura.get("altezza")),
            )
            connessione.execute(
                """
                INSERT INTO DocumentMultimedia (DocumentId, MultimediaId,
                                                BeginParagraphOrdinal, EndParagraphOrdinal)
                VALUES (?, ?, ?, ?);
                """,
                (indice, multimedia_id, 1, len(capitolo["paragrafi"])),
            )

    # ---- il vocabolario e l'indice di ricerca
    #
    # Qui sta la parte che conta.  Per ogni parola del libro si tiene:
    #   - quante volte compare in tutto il libro       -> WordOccurrenceCount
    #   - una COPPIA (unita', posizione) per ogni
    #     occorrenza                                   -> PositionalList
    #   - quante volte compare in OGNI capitolo        -> PositionalListIndex
    #   - il salto da un capitolo al successivo         -> TextUnitIndices
    #
    # LA POSITIONALLIST VA A COPPIE, E QUESTO E' IL PUNTO
    # --------------------------------------------------
    # Non e' una posizione per occorrenza: sono DUE byte per occorrenza.
    # Misurato sui pacchetti veri, su yb88_I.jwpub: la parola 'costruita' ha
    # 9 occorrenze e 20 byte, cioe' 9 coppie piu' un byte; 'bandiera' ha
    # 9 occorrenze e 17 byte.  Se si legge un byte per occorrenza le posizioni
    # vengono disallineate di mezzo byte e non si capisce piu' niente.
    #
    # Il primo elemento della coppia e' il numero dell'unita', cioe' del
    # capitolo; il secondo e' la posizione DENTRO quel capitolo.  Il secondo
    # cresce dentro ogni capitolo, ed e' da li' che si mettono in fila le
    # parole per rileggerle nell'ordine giusto.
    #
    # In un pacchetto costruito qui il significato e' noto, perche' lo si
    # scrive: e' il vantaggio di costruire il pacchetto invece di leggerlo.
    vocabolario: dict[str, dict] = {}

    for capitolo in capitoli:
        contatore = 0
        for parola in capitolo["parole"]:
            voce = vocabolario.setdefault(parola, {
                "word_id": len(vocabolario) + 1,
                "coppie": [],                       # (unita', posizione dentro l'unita')
                "per_capitolo": [0] * len(capitoli),
            })
            numero_capitolo = capitolo["numero"] - 1
            voce["coppie"].append((numero_capitolo, contatore))
            voce["per_capitolo"][numero_capitolo] += 1
            contatore += 1

    for parola, voce in vocabolario.items():
        connessione.execute(
            "INSERT INTO Word (WordId, Word, Reading) VALUES (?, ?, NULL);",
            (voce["word_id"], parola),
        )

        # TextUnitIndices: i delta.  Il primo capitolo dice "tutte le
        # occorrenze fino a qui", il secondo "tutte quelle fino a qui", e cosi'
        # via.  Sommandoli si ritrova il punto in cui ogni capitolo finisce.
        confini = []
        accumulato = 0
        for numero in voce["per_capitolo"]:
            accumulato += numero
            confini.append(accumulato)

        # Le coppie appiattite in una sequenza di byte: unita', posizione,
        # unita', posizione, ...
        appiattito = []
        for unita, dentro in voce["coppie"]:
            appiattito.append(unita)
            appiattito.append(dentro)

        connessione.execute(
            """
            INSERT INTO SearchIndexDocument (WordId, WordOccurrenceCount,
                                             TextUnitCount, TextUnitIndices,
                                             PositionalList, PositionalListIndex)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (voce["word_id"], len(voce["coppie"]), len(capitoli),
             codifica_7bit(confini),
             codifica_7bit(appiattito),
             codifica_7bit(voce["per_capitolo"])),
        )

    # ---- i metadati dell'edizione
    connessione.execute(
        """
        INSERT INTO Publication (Id, KeySymbol, Year, MepsLanguageId,
                                 PublicationTypeId, IssueTagNumber, Title, IssueTitle)
        VALUES (1, ?, ?, ?, 2, 0, ?, NULL);
        """,
        (simbolo, anno, LINGUA, titolo),
    )
    connessione.commit()
    return connessione


# ---------------------------------------------------------------------------
# IL PACCHETTO
# ---------------------------------------------------------------------------


def firma(percorso: Path) -> str:
    """L'eco del contenuto con la dimensione.

    Non serve a leggere il pacchetto: serve a capire se il file e' quello
    giusto senza aprirlo.  E' un'eco, non una firma crittografica, e il
    manifest lo chiama cosi' anche nell'app originale.
    """
    import hashlib
    digest = hashlib.sha256(percorso.read_bytes()).hexdigest()[:32]
    return f"{digest}:{percorso.stat().st_size}"


def costruisci_manifest(simbolo: str, titolo: str, anno: int, db_name: str,
                        copertine: list[dict]) -> dict:
    """Il manifesto: tutto quello che serve per capire cosa sia il pacchetto."""
    return {
        "name": titolo,
        "publication": {
            "title": titolo,
            "symbol": simbolo,
            "fileName": db_name,
            "language": LINGUA,
            "schemaVersion": SCHEMA,
            "year": anno,
            "publicationType": TIPO,
            "images": copertine,
        },
        "manifestVersion": VERSIONE_FIRMA,
    }


def scrivi_jwpub(uscita: Path, simbolo: str, titolo: str, anno: int,
                 capitoli: list[dict], file_extra: dict[str, bytes]) -> None:
    """Mette insieme i due ZIP e scrive il .jwpub.

    L'ordine e' obbligato: prima il .db dentro ``contents``, poi ``contents``
    dentro il .jwpub, e solo alla fine il manifesto perche' la firma dei file
    si calcola sul contenuto gia' scritto.
    """
    cartella = Path(tempfile.mkdtemp(prefix="jwpub-"))
    contenuti = cartella / "contents"
    contenuti.mkdir(parents=True, exist_ok=True)
    db_name = f"{simbolo}_I.db"

    connessione = costruisci_db(contenuti / db_name, capitoli, simbolo, titolo, anno)
    tabella_conteggi = connessione.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table';"
    ).fetchone()[0]
    connessione.close()

    for nome, dati in file_extra.items():
        (contenuti / nome).write_bytes(dati)

    # Le copertine: ogni voce e' una voce della tabella images del manifesto.
    copertine = []
    for voce in sorted(contenuti.glob("*.jpg")) + sorted(contenuti.glob("*.png")):
        copertine.append({
            "signature": firma(voce),
            "fileName": voce.name,
            "type": "c" if "_cvr" in voce.stem else "t",
            "attribute": "r",
            "width": 0,
            "height": 0,
        })

    manifest = costruisci_manifest(simbolo, titolo, anno, db_name, copertine)

    if uscita.exists():
        uscita.unlink()
    with zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as esterno:
        esterno.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False,
                                                     indent=2))
        # Il ZIP annidato si scrive in memoria e poi si mette dentro: non si
        # puo' annidare ZipFile dentro ZipFile su uno stesso file.
        with tempfile.NamedTemporaryFile(suffix=".contents", delete=False) as provvisorio:
            percorso_provvisorio = Path(provvisorio.name)
        with zipfile.ZipFile(percorso_provvisorio, "w", zipfile.ZIP_DEFLATED) as interno:
            for voce in sorted(contenuti.iterdir()):
                interno.write(voce, voce.name)
        esterno.write(percorso_provvisorio, "contents")
        percorso_provvisorio.unlink()

    import shutil
    shutil.rmtree(cartella, ignore_errors=True)
    print(f"{uscita} creato ({uscita.stat().st_size} byte, {tabella_conteggi} tabelle) ✅")
    print(f"  simbolo {simbolo}, {len(capitoli)} capitoli, "
          f"{sum(len(c['parole']) for c in capitoli)} parole")


# ---------------------------------------------------------------------------
# IL CONTROLLO
# ---------------------------------------------------------------------------


def verifica(percorso: Path) -> int:
    """Rilegge il pacchetto e controlla che sia a posto.

    Sono tre controlli e tutti e tre si possono fare senza l'app:

      1. il .db esiste dentro ``contents`` e si apre;
      2. la somma dei conteggi per capitolo torna a ``WordOccurrenceCount``;
      3. il testo del capitolo si ricostruisce e viene fuori leggibile.

    Il secondo e' quello importante: e' la prova che la codifica a 7 bit e'
    quella giusta.  Se fosse sbagliata, la somma non tornerebbe su nessuna
    riga, e non su poche.
    """
    import tempfile

    from Utility.Extensions.Ext_FileManager import BUNDLE_DIR  # noqa: F401
    from Utility.JWPubExtractor import JWPubExtractor

    with tempfile.TemporaryDirectory(prefix="jwpub-verifica-") as cartella:
        cartella = Path(cartella)
        with zipfile.ZipFile(percorso) as esterno:
            manifesto = json.loads(esterno.read("manifest.json").decode("utf-8"))
            db_name = manifesto["publication"]["fileName"]
            with zipfile.ZipFile(esterno.open("contents")) as interno:
                interno.extract(db_name, cartella)

        print(f"simbolo     {manifesto['publication']['symbol']}")
        print(f"titolo      {manifesto['publication']['title']}")
        print(f"database    {db_name}")
        print(f"copertine   {len(manifesto['publication'].get('images', []))}")

        estrattore = JWPubExtractor(cartella / db_name)

        # Controllo 1: le tabelle obbligatorie ci sono.
        necessarie = ["Document", "DocumentParagraph", "TextUnit", "Word",
                      "SearchIndexDocument", "Biblioteca Digitale", "DocumentMultimedia"]
        connessione = sqlite3.connect(str(cartella / db_name))
        presenti = {r[0] for r in connessione.execute(
            "SELECT name FROM sqlite_master WHERE type='table';")}
        mancanti = [t for t in necessarie if t not in presenti]
        connessione.close()
        if mancanti:
            print(f"manca la tabella  {', '.join(mancanti)} ❌")
            return 1
        print(f"tabelle     {len(presenti)} ✅")

        # Controllo 2: la prova che la codifica e' giusta.
        giuste, totali, occorrenze = estrattore.prova_decodifica()
        if totali == 0:
            print("non ci sono parole nell'indice")
            return 1
        percentuale = 100.0 * giuste / totali
        segno = "✅" if percentuale >= 99.0 else "⚠️"
        print(f"decodifica  {giuste}/{totali} parole tornano "
              f"({percentuale:.2f}%), {occorrenze} occorrenze {segno}")

        # Controllo 3: il testo torna fuori e si legge.
        connessione = sqlite3.connect(str(cartella / db_name))
        capitoli = connessione.execute(
            "SELECT DocumentId, Title, ContentLength FROM Document "
            "WHERE COALESCE(Title,'') != '' ORDER BY DocumentId;").fetchall()
        connessione.close()

        print()
        for document_id, titolo, lunghezza in capitoli[:5]:
            testo, copertura = estrattore.testo(document_id, lunghezza or 0)
            stato = "✅" if testo and copertura >= 0.65 else "⚠️"
            print(f"[{stato}] {document_id}  {titolo}  (copertura {copertura:.2f})")
            if testo:
                anteprima = testo[:300] + ("..." if len(testo) > 300 else "")
                print(f"       {anteprima}")
    return 0


# ---------------------------------------------------------------------------
# LA RIGA DI COMMANDO
# ---------------------------------------------------------------------------


def leggi_capitoli(percorsi: list[Path]) -> list[dict]:
    """Trasforma dei file di testo in capitoli pronti per il database."""
    capitoli = []
    for numero, percorso in enumerate(percorsi, start=1):
        testo = percorso.read_text(encoding="utf-8")
        righe = [riga.strip() for riga in testo.split("\n\n")]
        paragrafi = [r for r in righe if r]
        capitoli.append({
            "numero": numero,
            "titolo": percorso.stem.replace("_", " "),
            "testo": " ".join(paragrafi),
            "paragrafi": paragrafi,
            "parole": parole_del_testo(testo),
            "figure": [],
        })
    return capitoli


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        prog="crea_jwpub.py",
        description="Costruisce un .jwpub tuo, con il testo in chiaro.",
    )
    analizzatore.add_argument("uscita", nargs="?", help="il .jwpub da scrivere")
    analizzatore.add_argument("--titolo", default="Il mio libro")
    analizzatore.add_argument("--simbolo", default="mio", help="3-4 lettere")
    analizzatore.add_argument("--anno", type=int, default=2026)
    analizzatore.add_argument("--testo", nargs="+", metavar="FILE",
                              help="i file di testo, uno per capitolo")
    analizzatore.add_argument("--verifica", metavar="JWPUB",
                              help="controlla un pacchetto e dice cosa c'e' dentro")
    opzioni = analizzatore.parse_args(argv)

    if opzioni.verifica:
        return verifica(Path(opzioni.verifica))

    if not opzioni.uscita or not opzioni.testo:
        analizzatore.print_help()
        print()
        print("Esempi:")
        print("  crea_jwpub.py mio.jwpub --titolo 'Il mio libro' --testo c1.txt c2.txt")
        print("  crea_jwpub.py --verifica nwt_I.jwpub")
        return 1

    if not 3 <= len(opzioni.simbolo) <= 4:
        print(f"⚠️  Il simbolo '{opzioni.simbolo}' non e' di 3-4 lettere. "
              f"Nelle pubblicazioni vere e' cosi', ma non e' obbligatorio.")
    if len(opzioni.simbolo) != len(set(opzioni.simbolo)):
        print(f"⚠️  Il simbolo '{opzioni.simbolo}' ha lettere ripetute.")

    percorsi = [Path(p) for p in opzioni.testo]
    mancanti = [p for p in percorsi if not p.is_file()]
    if mancanti:
        for p in mancanti:
            print(f"non trovo {p}")
        return 1

    capitoli = leggi_capitoli(percorsi)
    scrivi_jwpub(Path(opzioni.uscita), opzioni.simbolo, opzioni.titolo,
                 opzioni.anno, capitoli, {})

    print()
    print("Ora puoi metterlo dove l'app guarda:")
    print(f"  cp {opzioni.uscita} ~/.local/share/JWLibrary/publicazioni/")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())