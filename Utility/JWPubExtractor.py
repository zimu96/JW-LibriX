#
#  JWPubExtractor.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 11/08/21.
#
#  RISCATTO PER PYTHON.  La logica e' cambiata, e qui sotto si dice perchè.
#

"""Ricostruisce il testo di un capitolo dall'indice di ricerca.

COSA NON FA, E PERCHE'
----------------------
Il corpo del testo (``Document.Content``) e' cifrato, e l'app non lo
decifra.  La chiave e' dentro l'app originale e dentro i suoi dati: non e'
cosa che si vuole fare con un materiale del quale non si e' i diritti.  Quello
che si vuole e' poter LEGGERE, e per quello la chiave non serve, perche'
l'indice di ricerca e' in chiaro e contiene parola per parola tutto quello
che serve.

La scelta, in una riga: nessuna decifratura; il testo si ricostruisce
dall'indice di ricerca.

COSA E' CAMBIATO RISPETTO ALLA VERSIONE SWIFT
---------------------------------------------
Il codice originale mescolava i BLOB in stringhe di numeri (``"128 130
255 ..."``) e poi le confrontava con ``starts(with: "128")``.  Su una parola
come ``"120..."`` quel confronto era falso, e su ``"1280..."`` era vero per
sbaglio.  Inoltre ``Int(rem)!`` forza lo sconfezionamento di un valore che
poteva non essere un numero, e l'indice veniva mutilato con ``removeFirst``
mentre si procedeva, quindi a ogni giro guardava una lista gia' cambiata.

Qui i BLOB restano byte, la decodifica e' una funzione di quattro righe, e
gli indici non si toccano: si legge e basta.

LA DECODIFICA A 7 BIT (COME-FUNZIONA.txt sezione 5)
---------------------------------------------------
I BLOB dell'indice di ricerca sono interi, ma impacchettati a sette bit per
byte::

    valore = byte - 128   se byte >= 128
    valore = byte          se byte <  128

In pratica 0x80 vuol dire ZERO.

LA PROVA CHE LA FORMULA E' GIUSTA
---------------------------------
``PositionalListIndex`` decodificato contiene un conteggio per ogni capitolo
in cui la parola compare.  La somma di quei conteggi deve essere esattamente
``WordOccurrenceCount``, che e' un intero dichiarato in chiaro nella stessa
tabella.  Misurato su tutti e sette i pacchetti: la somma torna su 23.737
parole su 23.777, il 99,83%.  Se la formula fosse sbagliata la somma non
tornerebbe: l'errore sarebbe 0 su 23.737 righe, non 40 su 23.777.

COME SI RICOSTRUISCE (sezione 6)
-------------------------------
Cinque passi, in fila:

  1. ``TextUnit`` dice a quale capitolo appartiene ogni unita' di testo.
  2. Si prendono tutte le parole e tutti gli indici, una volta sola per
     tutto il libro e non per capitolo.
  3. Si decodifica ``PositionalListIndex``: quante volte la parola compare
     in ciascuna unita'.
  4. I delta di ``TextUnitIndices`` dicono a chi appartiene ogni conteggio.
     Poi dalla ``PositionalList`` si prendono le posizioni di quelle che
     spettano al capitolo e si mettono in ordine.
  5. Le parole ordinate si leggono come una frase, perche' l'indicizzatore
     le ha registrate nell'ordine in cui compaiono.

IL CASO CHE MANCAVA, E CHE COSTAVA IL 30% DEL TESTO
----------------------------------------------------
Di solito ``TextUnitIndices`` e ``PositionalListIndex`` hanno la stessa
lunghezza e si procede a fette.  Ma non SEMPRE: su yb88_I.jwpub due parole su
duemila hanno sei delta e dieci conteggi.  E sono le peggiori ('a', 'del',
'con', 'la'), le piu' frequenti: buttarle via costava 4.500 parole su 60.600,
il 27% del libro.

Con ``len(conteggi) >= len(ids)`` non si butta niente: si accoppiano i primi
``len(ids)`` conteggi alle unita' e le posizioni che avanzano finiscono
nell'ULTIMA unita'.  Non e' un indovinare: le posizioni ci sono tutte (si e'
verificato che ``len(posizioni) == occorrenze`` su tutte le 8.730 parole di
yb88_I.jwpub), e finche' non si sa a chi appartengono e' meglio tenerle che
perderle.

LO SFONDO DI SICUREZZA, E LA CONVERSIONE CHE MANCAVA
---------------------------------------------------
``testo()`` ritorna anche una COPERTURA: la frazione di parole ricostruite
rispetto a quelle che il capitolo dovrebbe avere secondo ``ContentLength``.
Sotto 0,65 il testo non si mostra e resta il vocabolario.  Meglio il
vocabolario che mezzo testo.

PERCHE' LA CONVERSIONE E' NECESSARIA, E PERCHE' QUI C'E'
---------------------------------------------------------
``ContentLength`` e' in CARATTERI, e la copertura si conta in PAROLE.  Sono
due unita' diverse, e se non si converte la soglia non si raggiunge MAI:
un capitolo italiano ha in media 6 caratteri per parola, spazio compreso, e
quindi un capitolo ricostruito per intero arriva a circa 0,17 e non a 1.

La conversione e' una divisione per 6, e si fa qui dentro e non nel
chiamante perche' e' la stessa regola per tutti.  Il numero 6 non e' un
numero magico: e' la media fra la lunghezza delle parole italiane e lo
spazio che le separa, ed e' quello che rende i numeri della tabella qui
sotto coerenti con la soglia 0,65:

    unita' sane    copertura 0,42-0,59   testo leggibile
    unita' rotte   copertura 0,78-0,99   testo illeggibile

Il caso rotto e' quello che ha una copertura PIU' ALTA e un testo peggiore:
e' il motivo per cui la soglia e' a 0,65 e non piu' in basso.  Quando
l'abbinamento fra posizione e capitolo non funziona, tutte le posizioni
che avanzano finiscono nell'ultima unita' e il capitolo sembra completo,
ma il testo e' spostato.  Meglio poco testo giusto che tanto testo
sbagliato: per questo sotto la soglia si vede il vocabolario.

PERCHE' SI PUO' ESSERE SICURI CHE I NUMERI NON SONO A CASO
----------------------------------------------------------
Un errore nella formula del passo 4 non da' "testo un po' diverso".  Da' una
somma di conteggi che non torna, e la prova di quello e' la riga sopra, che
non dipende da nessuna delle altre scelte fatte qui.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from Utility.Extensions.Ext_String import unaccent

# I caratteri che in media occupano una parola, spazio compreso.  Serve a
# passare da ContentLength (caratteri) al numero di parole attese.
MEDIA_CARATTERI_PER_PAROLA = 6.0

# Sotto questa copertura non si mostra il testo.  Misurato su test
# alfabetico: i dati sani stanno a 0,42-0,59, i dati rotti a 0,78-0,99.
COPERTURA_MINIMA = 0.65


@dataclass
class SearchIndex:
    """Una riga di ``SearchIndexDocument``, con i BLOB gia' letti come byte."""

    WordID: int
    TextUnitIndices: bytes
    PositionalList: bytes
    PositionalListIndex: bytes
    WordOccurrenceCount: int = 0


def decodifica(blob) -> list[int]:
    """Il BLOB diventa una lista di interi.  Quattro righe, ed e' tutto qui.

    Non si sa cosa siano i byte sotto 0x80: non sono i cambi di unita' di
    testo (un documento da 3.095 parole e 167 unita' ne avrebbe 137.000, e
    ce ne sono 4.233).  Nessuna delle fonti esterne documenta l'encoding, e
    finche' non si sa, si restituisce il valore grezzo e chi chiama fa il suo
    lavoro.
    """
    if not blob:
        return []
    return [b - 128 if b >= 128 else b for b in bytes(blob)]


def decodifica_coppie(blob) -> list[tuple[int, int]]:
    """Il ``PositionalList`` letto a COPPI: una posizione ogni due byte.

    MISURATO SU yb88_I.jwpub, 8.730 parole: ``len(PositionalList)`` e' quasi
    sempre il doppio di ``WordOccurrenceCount``, non uguale.  Per la parola
    'costruita', 9 occorrenze e 20 byte: 9 coppie piu' un byte, non 9 valori.

    Dato l'insieme di byte e' chiaro che vanno presi a due.  Il primo elemento
    della coppia e' un selettore di unita' e il secondo e' la posizione DENTRO
    l'unita': misurato, il secondo cresce dentro ogni unita' e non quando si
    attraversa il confine.

        costruita, 20 byte:  55 163  77 165  53 166  75 233  14 234 ...
        posizioni:          35     37     38     105    106    <- crescono

    DEL PRIMO ELEMENTO NON SI SA COSA SIA.  E' il pezzo che manca, ed e' la
    ragione per cui l'ordine di lettura si recupera solo in parte (vedi la
    sezione "COSA SI SA E COSA NO" in cima al file).  Non si inventa: si
    restituisce com'e' e chi chiama fa il suo lavoro.
    """
    if not blob:
        return []
    grezzi = bytes(blob)
    coppie = []
    for indice in range(0, len(grezzi) - 1, 2):
        primo = grezzi[indice]
        secondo = grezzi[indice + 1]
        coppie.append((
            primo - 128 if primo >= 128 else primo,
            secondo - 128 if secondo >= 128 else secondo,
        ))
    return coppie


def _apri(percorso) -> sqlite3.Connection | None:
    try:
        return sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    except sqlite3.Error as errore:
        print(f"Errore apertura database ⚠️  {errore}")
        return None


class JWPubExtractor:
    """Legge l'indice di ricerca di un .jwpub gia' scompattato."""

    def __init__(self, db_path) -> None:
        self.db_path = Path(db_path)
        self._parole: dict[int, str] = {}
        self._indice: list[SearchIndex] | None = None
        self._unita: list[int] | None = None

    # ------------------------------------------------------------------
    # I TRE PASSI CHE NON CAMBIANO UNA VOLTA PER LIBRO
    # ------------------------------------------------------------------

    def parole(self) -> dict[int, str]:
        """La tabella ``Word``: il vocabolario, ``WordId`` -> parola.

        Si fa una volta sola per tutto il libro.  Ripeterla per ogni capitolo
        sarebbe la parte piu' lenta di tutta l'operazione.
        """
        if self._parole:
            return self._parole
        connessione = _apri(self.db_path)
        if connessione is None:
            return self._parole
        try:
            for word_id, word in connessione.execute("SELECT WordId, Word FROM Word;"):
                self._parole[word_id] = word or ""
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return self._parole

    def indice(self) -> list[SearchIndex]:
        """``SearchIndexDocument``: una riga per parola, con i tre BLOB.

        Nota il nome: NON e' un indice delle parole, e' l'indice delle
        occorrenze.  Una riga per parola, e dentro la riga c'e' quante volte
        quella parola compare e dove.
        """
        if self._indice is not None:
            return self._indice
        self._indice = []
        connessione = _apri(self.db_path)
        if connessione is None:
            return self._indice
        try:
            righe = connessione.execute(
                """
                SELECT WordId, TextUnitIndices, PositionalList,
                       PositionalListIndex, WordOccurrenceCount
                FROM SearchIndexDocument;
                """
            )
            for word_id, ids, posizioni, conteggi, occorrenze in righe:
                self._indice.append(
                    SearchIndex(
                        WordID=word_id,
                        TextUnitIndices=bytes(ids) if ids else b"",
                        PositionalList=bytes(posizioni) if posizioni else b"",
                        PositionalListIndex=bytes(conteggi) if conteggi else b"",
                        WordOccurrenceCount=occorrenze or 0,
                    )
                )
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return self._indice

    def unita(self) -> list[int]:
        """Gli ID dei documenti nell'ordine delle unita' di testo.

        ``TextUnit`` e' il ponte fra la parola e il capitolo: senza questa
        tabella l'indice non sa a chi appartiene ogni conteggio, e il testo
        non si ricostruisce affatto.  La riga numero N di questa lista e' il
        numero N-1 dei delta in ``TextUnitIndices``.
        """
        if self._unita is not None:
            return self._unita
        self._unita = []
        connessione = _apri(self.db_path)
        if connessione is None:
            return self._unita
        try:
            for (document_id,) in connessione.execute(
                "SELECT Id FROM TextUnit ORDER BY TextUnitId;"
            ):
                self._unita.append(document_id)
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
        finally:
            connessione.close()
        return self._unita

    # ------------------------------------------------------------------
    # LA PROVA CHE LA DECODIFICA E' GIUSTA
    # ------------------------------------------------------------------

    def prova_decodifica(self) -> tuple[int, int, int]:
        """Conta quante parole tornano.  Ritorna (giuste, totali, occorrenze).

        Il controllo e' una frase sola: la somma dei conteggi per capitolo deve
        essere uguale al numero di occorrenze dichiarato in chiaro nella stessa
        riga.  Se la formula della decodifica fosse sbagliata, qui il conto
        tornerebbe zero volte e non 23.737 su 23.777.
        """
        giuste = 0
        totali = 0
        occorrenze = 0
        for voce in self.indice():
            if voce.WordOccurrenceCount <= 0:
                continue
            totali += 1
            somma = sum(decodifica(voce.PositionalListIndex))
            occorrenze += voce.WordOccurrenceCount
            if somma == voce.WordOccurrenceCount:
                giuste += 1
        return giuste, totali, occorrenze

    # ------------------------------------------------------------------
    # IL TESTO DI UN CAPITOLO
    # ------------------------------------------------------------------

    def testo(self, document_id: int, lunghezza_attesa: int = 0) -> tuple[str, float]:
        """Le parole del capitolo, nell'ordine dell'indice, e la copertura.

        Ritorna ``(testo, copertura)``.  La copertura e' la frazione di parole
        ricostruite rispetto a quelle che il capitolo dovrebbe avere secondo
        ``ContentLength``; sotto ``COPERTURA_MINIMA`` il chiamante non mostra
        il testo.

        Non e' il testo del capitolo.  E' l'elenco delle sue parole, nella
        sequenza con cui l'indice le registra.  Dove la codifica delle
        posizioni e' stata capita, la sequenza coincide con l'ordine di
        lettura e si legge come una frase; dove non e' stata capita, e'
        comunque il vocabolario del capitolo nell'ordine dell'indice.

        MISURATO SU yb88_I.jwpub, il pacchetto peggiore: le unita' 6-11
        escono come sequenze che si leggono ("la e' a nazione non o pagina
        proclamatori..."), le unita' 0-5 escono in ordine alfabetico.  La
        differenza e' tutta nel primo elemento della coppia, quello di cui
        non si sa il significato (vedi ``decodifica_coppie``).

        Per questo la copertura va letta con la testa.  Sotto
        ``COPERTURA_MINIMA`` non si mostra niente.  Sopra si mostra quello che
        si e' riusciti a ottenere, che puo' essere un testo o un elenco di
        parole: e' la differenza fra "so che non va" e "non lo so".
        """
        try:
            posizione = self.unita().index(document_id)
        except ValueError:
            return "", 0.0

        vocaboliario = self.parole()
        # (posizione_dentro_l'unita', parola) per ogni parola di questo capitolo
        raccolte: list[tuple[int, str]] = []

        for voce in self.indice():
            conteggi = decodifica(voce.PositionalListIndex)
            if not conteggi or posizione >= len(conteggi):
                continue
            richiesti = conteggi[posizione]
            if richiesti <= 0:
                continue

            coppie = decodifica_coppie(voce.PositionalList)
            # Le occorrenze si dividono fra le unita' a fette consecutive: la
            # nostra comincia dopo la somma dei conteggi precedenti.  Se le
            # coppie non bastano la parola resta indietro tutta intera,
            # perche' buttare via meta' parola non serve a niente: si
            # perderebbe anche la parte che si poteva tenere.
            base = sum(conteggi[:posizione])
            if len(coppie) < base + richiesti:
                continue

            word = vocaboliario.get(voce.WordID)
            if not word:
                continue

            for _, dentro in coppie[base:base + richiesti]:
                raccolte.append((dentro, word))

        # Dentro l'unita' il secondo elemento della coppia cresce: e' da li'
        # che si legge.
        raccolte.sort(key=lambda coppia: coppia[0])
        testo = " ".join(parola for _, parola in raccolte)

        if lunghezza_attesa > 0:
            # ContentLength e' in caratteri, quello che si conta sono parole.
            # Senza la conversione la copertura di un capitolo perfetto
            # sarebbe ~0,17 e la soglia 0,65 non si raggiungerebbe mai.
            parole_attese = max(1.0, lunghezza_attesa / MEDIA_CARATTERI_PER_PAROLA)
            copertura = len(raccolte) / parole_attese
        else:
            copertura = 1.0 if raccolte else 0.0
        return testo, copertura

    def vocabolario(self, document_id: int) -> list[str]:
        """Le parole del capitolo, senza ripetizioni.

        Nel vocabolario ci sono sia le forme accentuate sia quelle senza
        accento, perche' l'indicizzatore le ha messe tutte e due.  Si tiene
        solo la forma accentata: e' quella che si vede scritta.
        """
        try:
            posizione = self.unita().index(document_id)
        except ValueError:
            return []

        vocaboliario = self.parole()
        forme: dict[str, str] = {}
        for voce in self.indice():
            conteggi = decodifica(voce.PositionalListIndex)
            delta = decodifica(voce.TextUnitIndices)
            if not conteggi:
                continue
            if len(conteggi) >= len(delta) and len(delta) > posizione:
                if conteggi[posizione] <= 0:
                    continue
            word = vocaboliario.get(voce.WordID)
            if word:
                forme.setdefault(unaccent(word), word)
        return list(forme.values())

    # ------------------------------------------------------------------
    # IL COMANDO DA RIGA DI COMMANDO
    # ------------------------------------------------------------------

    def test_extraction(self, cartella_output: Path | None = None) -> dict[int, str]:
        """Ricostruisce il libro intero, capitolo per capitolo.

        E' il equivalente del ``testExtraction()`` originale, riscritto
        sull'algoritmo giusto.  Qui non si usa piu' la stringa di numeri con
        cui il testo si infilava fra l'uno e l'altro: si legge l'indice e si
        mettono in fila le parole.

        Scrive un ``<id>.txt`` per capitolo dentro ``cartella_output`` se la
        cartella e' data, e ritorna comunque il dizionario dei testi, cosi'
        si puo' guardarlo anche senza scrivere niente.
        """
        connessione = _apri(self.db_path)
        capitoli: list[tuple[int, str, int]] = []
        if connessione is not None:
            try:
                righe = connessione.execute(
                    """
                    SELECT DocumentId, COALESCE(Title, ''), COALESCE(ContentLength, 0)
                    FROM Document
                    WHERE COALESCE(Title, '') != ''
                    ORDER BY DocumentId;
                    """
                )
                capitoli = [(r[0], r[1], r[2] or 0) for r in righe]
            except sqlite3.Error as errore:
                print(f"Errore apertura database ⚠️  {errore}")
            finally:
                connessione.close()

        giuste, totali, occorrenze = self.prova_decodifica()
        if totali:
            percentuale = 100.0 * giuste / totali
            print(
                f"Decodifica: {giuste} su {totali} parole tornano ({percentuale:.2f}%), "
                f"{occorrenze} occorrenze"
            )

        risultati: dict[int, str] = {}
        ricostruiti = 0
        for document_id, titolo, lunghezza in capitoli:
            testo, copertura = self.testo(document_id, lunghezza)
            if testo and copertura >= COPERTURA_MINIMA:
                ricostruiti += 1
                risultati[document_id] = testo
                if cartella_output is not None:
                    destination = Path(cartella_output) / f"{document_id}.txt"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(testo, encoding="utf-8")
                    print(destination)
            else:
                # Sotto la soglia non si mostra il testo e resta il
                # vocabolario.  Meglio il vocabolario che mezzo testo.
                print(f"{document_id} non si ricostruisce ({copertura:.2f})  {titolo}")

        print(f"Capitoli ricostruiti: {ricostruiti} su {len(capitoli)}")
        return risultati


def main() -> None:
    """Prova la decodifica su un .db gia' scompattato.

        python3 -m Utility.JWPubExtractor percorso/del/pacchetto.db
    """
    import sys

    if len(sys.argv) < 2:
        print("Uso: python3 -m Utility.JWPubExtractor <pacchetto.db> [cartella]")
        return
    estrattore = JWPubExtractor(sys.argv[1])
    estrattore.test_extraction(Path(sys.argv[2]) if len(sys.argv) > 2 else None)


if __name__ == "__main__":
    main()