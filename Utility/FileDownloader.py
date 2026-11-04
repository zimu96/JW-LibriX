#
#  FileDownloader.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""Scaricare tre cose: i .jwpub, il catalogo, e il testo dei capitoli.

In Swift c'erano due strade: ``NSData(contentsOf:)`` che e' sincrona e blocca,
e ``URLSession`` che e' asincrona e dà un callback.  Qui c'e' una strada sola,
``urlopen`` in un thread, e la consegna del risultato avviene con una funzione
di callback che il chiamante decide.

PERCHE' UNA FUNZIONE E NON UN SEGNALE QUI
-----------------------------------------
Le altre classi di questa app sono QObject e possono emettere segnali.  Questa
no, e va bene cosi': il chiamante (BibleView, PubListView) le passa una
funzione, e quella funzione e' gia' un segnale collegato alla GUI.  Cosi' un
modulo che scarica non ha bisogno di sapere se il destinatario e' una finestra
o uno script, e resta usabile da riga di comando.
"""
from __future__ import annotations

import gzip
import threading
import urllib.error
import urllib.request
from pathlib import Path

from Utility.Extensions.Ext_FileManager import article_exist, get_documents_directory
from Utility.JWPubManager import JWPubManager

# Quanto si legge per volta dalla rete, quando si vuole mostrare l'avanzamento.
_CHUNK = 64 * 1024

# I due segnali che si cercano dentro una pagina di wol.jw.org.  Il primo
# segna l'inizio del contenuto, il secondo la fine.  Fra i due c'e' tutto
# quello che si vuole tenere; fuori, no.
ARTICLE_START = '<div class="scalableui">'
ARTICLE_END = "<!-- Root element of lightbox -->"


#: IL CONTO DEI CAPITOLI SALTATI NON ESISTE PIU'
#:
#: Prima si stampava una riga per capitolo, poi un contatore ogni cento.  La
#: seconda versione era gia' meglio della prima, ma continuava a uscire a
#: ogni avvio, e non serve a niente:
#:
#:     100 capitoli gia' scaricati
#:     200 capitoli gia' scaricati
#:     ... dodici righe ...
#:
#: Un capitolo che c'e' gia' e' il caso **normale**, non un evento.  Il
#: programma non sta facendo niente di particolare: sta dicendo che non ha
#: niente da fare, dodici volte, prima ancora di mostrare la finestra.  E
#: quello che viene scritto dopo — un errore, un avviso, una domanda — finisce
#: sotto e l'utente non lo vede piu'.
#:
#: Se un giorno si vuole sapere quanto ha fatto un download, il numero vero
#: lo da' `JWPubManager.download_documents`, che conta i documenti e dice
#: quanti ne ha scritti.  Un numero e' utile; dodici righe che dicono "non ho
#: fatto niente" sono rumore.


#: Quante volte si ritenta una pagina che ha risposto «non disponibile».
#:
#: Tre, e non uno: il 503 di wol.jw.org e' quello di un server **occupato**, non
#: di un indirizzo sbagliato.  Un indirizzo sbagliato risponde 404 e ritentare
#: non serve a niente; un 503 passa da solo dopo qualche secondo.
TENTATIVI = 3

#: Quanto si aspetta prima del secondo tentativo, e quanto raddoppia ogni volta.
#:
#: Un secondo, due, quattro.  Sono voluti lunghi: la richiesta dopo un 503
#: arriva subito, e arrive subito e di nuovo si viene rifiutati perche' il
#: motore che rispondeva non ha ancora finito quello che stava facendo.
ATTESA_PRIMO = 1.0


def _prendi_la_pagina(url: str) -> str | None:
    """Prende la pagina, ritentando quando il server dice «non disponibile».

    PERCHE' RITENTARE, E NON RINUNCIARE AL PRIMO ERRORE
    ----------------------------------------------------
    Un download di capitoli fa **centinaia** di richieste di fila: 146 per
    «Altri argomenti», 1.189 per la Bibbia.  A quel ritmo wol.jw.org risponde
    «503 Service Temporarily Unavailable» a una fetta delle richieste, e prima
    qui quel 503 finiva in un `return`: il capitolo non veniva scritto e non
    c'era modo di riprenderlo, perche' il file non esisteva e quindi alla
    richiesta dopo il programma non lo sapeva.

    Il sintomo era il peggiore possibile: il download diceva **finito**, la
    barra arrivava a capo, e poi aprendo la pubblicazione metà dei capitoli
    erano vuoti.  Non c'era nessun errore a schermo — solo una riga nel
    terminale — e l'utente non aveva modo di sapere quale metà.

    ADESSI IL 503 SI RITENTA, E IL 404 NO
    --------------------------------------
    Il 503 e' transitorio e il 404 no.  Su un 404 ritentare significa
    aspettare quattro secondi per scoprire che la risposta era la stessa: si
    distingue perche' il codice lo dice, e non perche' «e' un errore».

    Anche i 429 — «troppe richieste» — si ritentano, perche' dicono la stessa
    cosa del 503 con parole diverse.
    """
    import time

    attesa = ATTESA_PRIMO
    for tentativo in range(TENTATIVI):
        try:
            richiesta = urllib.request.Request(
                url, headers={"User-Agent": "JWLibrary"})
            with urllib.request.urlopen(richiesta, timeout=60) as risposta:
                return risposta.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as errore:
            # Solo i codici che passano: gli altri non si ritentano.
            if errore.code not in (429, 500, 502, 503, 504):
                print(f"Non riesco a prendere un capitolo ⚠️  {errore}")
                return None
            if tentativo < TENTATIVI - 1:
                time.sleep(attesa)
                attesa *= 2
                continue
            print(f"Non riesco a prendere un capitolo ⚠️  {errore}")
            return None
        except (urllib.error.URLError, OSError, TimeoutError) as errore:
            if tentativo < TENTATIVI - 1:
                time.sleep(attesa)
                attesa *= 2
                continue
            print(f"Non riesco a prendere un capitolo ⚠️  {errore}")
            return None
    return None


#: Alzato quando l'utente preme «Annulla scaricamento»: tutti i cicli di
#: download lo guardano e si fermano, senza lasciare file a meta'.
_ANNULLA = threading.Event()


class FileDownloader:

    @staticmethod
    def annulla() -> None:
        """Ferma i download in corso (si fermano al prossimo pezzo)."""
        _ANNULLA.set()

    @staticmethod
    def riparti() -> None:
        """Da chiamare quando l'utente avvia un nuovo scaricamento."""
        _ANNULLA.clear()

    @staticmethod
    def annullato() -> bool:
        return _ANNULLA.is_set()

    @staticmethod
    def _scrivi(path: Path, dati: bytes, on_progress=None, totale: int = 0) -> None:
        """Scrive un file a pezzi, e avvisa mentre scrive."""
        path.parent.mkdir(parents=True, exist_ok=True)
        scritti = 0
        with path.open("wb") as maniglia:
            for inizio in range(0, len(dati), _CHUNK):
                pezzo = dati[inizio:inizio + _CHUNK]
                maniglia.write(pezzo)
                scritti += len(pezzo)
                if on_progress is not None:
                    on_progress(scritti, totale or len(dati))

    @staticmethod
    def _scarica(url: str, on_progress=None) -> bytes | None:
        """I byte di un indirizzo, oppure None."""
        try:
            with urllib.request.urlopen(url, timeout=60) as risposta:
                totale = int(risposta.headers.get("Content-Length") or 0)
                chunks = []
                letti = 0
                while True:
                    if _ANNULLA.is_set():
                        return None
                    pezzo = risposta.read(_CHUNK)
                    if not pezzo:
                        break
                    chunks.append(pezzo)
                    letti += len(pezzo)
                    if on_progress is not None:
                        on_progress(letti, totale)
                return b"".join(chunks)
        except (urllib.error.URLError, OSError, TimeoutError) as errore:
            print(f"Errore download {url} ⚠️  {errore}")
            return None

    @staticmethod
    def load_file_async(url: str, completion=None, on_progress=None):
        """Scarica un file in background e richiama ``completion`` alla fine.

        ``completion(path, errore)``.  Non blocca: il chiamante non deve
        fare nient'altro e la GUI resta viva.

        IL CALLBACK ARRIVA SEMPRE SUL MAIN THREAD.  E' la parte importante di
        questa funzione, e non e' una cortesia.

        Il lavoro gira in un thread, e li' i widget non si possono creare: Qt
        si rifiuta e scrive ``QObject::setParent: Cannot set parent, new
        parent is in a different thread``.  E' la trappola numero 7 di
        COME-FUNZIONA.txt, quella elencata per prima, e non e' un avviso
        innocuo: e' Qt che dice di no a una operazione che poi va storta
       altrove, in un file che non c'entra.

        Chi chiama questa funzione costruisce schermate: liste, bottoni,
        griglie.  Per questo ``completion`` viene consegnato dal main thread
        e non da quello del lavoro.  Il chiamante non deve accorgersene, e non
        deve neanche potersene accorgere.

        In Swift era diverso: la ``URLSession`` consegnava il callback su una
        coda di servizio, e il codice originale costruiva li' i widget.  Li'
        funzionava finche' non andava male.

        Tre casi, come nel progetto originale: ``.jwpub`` si scompatta dopo
        averlo scritto, ``.gz`` si decomprime e si cancella il compresso,
        tutto il resto si scrive e basta.
        """
        from Utility.Extensions.Ext_DispatchQueue import background, on_main

        def lavoro() -> None:
            documents = get_documents_directory()
            destination = documents / Path(url).name

            if destination.exists():
                print(f"Il file esista gia' [{destination}]")
                if completion is not None:
                    on_main(lambda: completion(str(destination), None))
                return

            dati = FileDownloader._scarica(url, on_progress)
            if dati is None:
                if completion is not None:
                    on_main(lambda: completion(
                        str(destination), OSError(f"Errore download ({url})")))
                return

            try:
                if url.endswith("jwpub"):
                    FileDownloader._scrivi(destination, dati, on_progress)
                    JWPubManager.extract_pub(url=url)
                elif url.endswith("gz"):
                    # Il .gz si scrive, poi si scompatta e il .gz si cancella:
                    # quello che si usa e' il file senza il suffisso.
                    FileDownloader._scrivi(destination, dati, on_progress)
                    nuovo = Path(str(destination).replace(".gz", ""))
                    nuovo.write_bytes(gzip.decompress(dati))
                    JWPubManager.delete_file(filePath=destination)
                else:
                    FileDownloader._scrivi(destination, dati, on_progress)
            except (OSError, EOFError, gzip.BadGzipFile) as errore:
                if completion is not None:
                    on_main(lambda: completion(str(destination), errore))
                return

            if completion is not None:
                on_main(lambda: completion(str(destination), None))

        background(lavoro)
        return None

    @staticmethod
    def download_article(url: str, path: str) -> None:
        """Scarica il testo di un capitolo e lo pulisce dall'HTML di contorno.

        wol.jw.org restituisce una pagina intera con la testata, il menu e i
        collegamenti.  Si tiene solo quello che sta fra ``scalableui`` e il
        commento del lightbox, e si butta via il resto.

        Se il file c'e' gia' non lo riscarica: sono 1189 capitoli della
        Bibbia, e riscaricarli a ogni avvio e' spreco di banda.
        """
        if _ANNULLA.is_set():
            return
        if article_exist(path=path):
            # NON STAMPA NIENTE
            # -----------------
            # Prima scriveva `Salto percorso ✅` per ogni capitolo gia'
            # scaricato.  Sono **1.189 capitoli** della Bibbia: a ogni
            # avvio il terminale si riempiva di 1.189 righe, e finivano
            # sopra la finestra che stava per aprirsi, cosi' l'utente le
            # vedeva scorrere e non poteva ne' copiarle ne' arrivare in fondo.
            #
            # Non e' un semplice disturbo: e' un'uscita che **copre
            # l'avvio**.  E un capitolo che c'e' gia' e' la cosa meno
            # importante che possa succedere — e' il caso normale, non un
            # evento.
            #
            # Se si vuole vedere quanto ha fatto il download, il numero
            # vero lo da' `download_documents`, che conta i documenti e dice
            # quanti ne ha scritti.  Una riga con un numero e' utile; 1.189
            # righe con un nome di file sono rumore.
            #
            # L'unica riga che resta e' **un contatore ogni 100 file**,
            # perche' con 1.189 file un lavoro che sembra fermo e' indistinguibile
            # da uno che e' fermo.
            return

        # NON STAMPA IL NOME DEL CAPITOLO
        # -------------------------------
        # Prima scriveva `Scarico 501100123.html ✅` per ogni capitolo.  Sono
        # **150 capitoli** per una pubblicazione e **1.189** per la Bibbia: il
        # terminale si riempiva di quelle righe mentre la finestra era ferma,
        # e la cosa che l'utente stava guardando — una barra che avanza — non
        # si vedeva da nessuna parte.
        #
        # Il nome del capitolo non serve a nessuno: l'utente non sa cosa sia
        # `501100123`, e il capitolo successivo non si distingue dal
        # precedente.  Quello che serve e' «quanti ne mancano», e quello lo
        # dice la barra dentro la finestra, che guarda `on_progress`.
        pagina = _prendi_la_pagina(url)
        if pagina is None:
            return

        # components(separatedBy:).last / .first: si prende l'ultima
        # occorrenza del segnale d'inizio e la prima del segnale di fine.
        # In Python: rfind e find, che danno esattamente quello.
        inizio = pagina.rfind(ARTICLE_START)
        if inizio == -1:
            print(f"Errore: inizio del capitolo non trovato in {url} ⚠️")
            return
        inizio += len(ARTICLE_START)
        fine = pagina.find(ARTICLE_END, inizio)
        articolo = pagina[inizio:fine] if fine != -1 else pagina[inizio:]

        if not articolo.strip():
            return

        destination = get_documents_directory() / path
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(articolo, encoding="utf-8")
        except OSError as errore:
            print(f"Errore: {errore} ⚠️")