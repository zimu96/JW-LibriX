#
#  Stuff.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 02/01/21.
#

"""Utensili comuni: nomi dei libri, colori, icone, manifest, file di base.

ICONE
-----
Su macOS ``Image(systemName: "house.fill")`` disegnava un simbolo SF.
Su Linux quei simboli non esistono e non si possono installare: sono dentro
il sistema operativo, non dentro l'app.  Qui ogni nome SF e' associato a un
glifo che esiste in DejaVu Sans, il font che c'e' su ogni installazione di
Linux.  I nomi nella tabella sono quelli del progetto originale: se un
giorno i simboli diventano disponibili si cambia la tabella e non il resto.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

from Utility.Extensions.Ext_FileManager import (
    BUNDLE_DIR,
    copyfile_to_user_document_directory,
    get_documents_directory,
)
from Utility.Structures.Paths import Paths

# Il server dei cataloghi.  Stesso indirizzo del progetto originale.
CATALOG_BASE = "https://app.jw-cdn.org/catalogs/publications/v4/"
MANIFEST_URL = CATALOG_BASE + "manifest.json"

# LE ICONE
# ---------
# Il progetto originale usava i simboli di macOS ("house.fill", "book.fill").
# Sono dentro il sistema operativo: su Linux non esistono e non si possono
# installare.  Sostituirli con i glifi di una scrittura era una soluzione
# povera, e si vedeva.
#
# Qui si usano le icone Tabler, che sono disegni veri: SVG a tracci, con la
# licenza MIT che permette anche l'uso commerciale.  82 icone in
# Files/icons/, con dentro anche la nota di copyright.
#
# PERCHE' IL NOME DELL'ICONA E' UN PEZZO DI INFORMAZIONE
# -------------------------------------------------------
# I disegni di Tabler non si possono copiare, ma i NOMI si possono tradurre:
# "casa" in Tabler si chiama home, in Lucide si chiama house, in Material
# home.  Le chiavi della tabella sotto sono quindi i nomi del progetto
# originale, e i valori i nomi di Tabler.  Il codice che chiama le icone parla
# coi nomi del progetto originale, e non cambia.
#
# IL COLORE
# ---------
# Le icone Tabler sono disegnate con stroke="currentColor": il colore non e'
# scritto nel file e lo prende dal testo che le contiene.  Nella pagina web
# funziona da solo.  Nei pulsanti di Qt NON funziona, perche' li non c'e' un
# CSS: e' per questo che ``icon()`` sostituisce la parola con un colore
# concreto prima di disegnare.
#
# Le sei pastiglie (i colori delle sottolineature) stanno in una cartella
# a parte perche' il loro colore e' scelto, non quello del tema: la stessa
# tinta su fondo chiaro e su fondo scuro sarebbe illeggibile su uno dei due.

# I sei colori delle sottolineature.  Gli stessi numeri del progetto originale,
# e le stesse regole CSS corrispondenti in Files/style.css.
HIGHLIGHT_HEX = [0xFFEB3B, 0x9EF953, 0x29B6F6, 0xFFA1C8, 0xFFB976, 0xAF85FF]

# IL VIOLA DELL'APPLICAZIONE
# --------------------------
# Il campione viene dall'icona originale, Assets.xcassets/AppIcon.appiconset/
# Icon-1024.png, contando i pixel di ogni colore opaco: il viola e' 548.655
# pixel su 1.048.576 ed e' nettamente il primo.  Il risultato e' #64398b.
#
# NON E' #5b3c88.  La differenza e' piccola (rgb 100,57,139 contro 91,60,136)
# ma reale, e la regola scritta nei documenti del progetto e' proprio questa:
# il viola si campiona dagli asset originali, non si indovina.  Dagli asset
# originali esce #64398b.
#
# E L'ACCENTCOLOR DELL'ORIGINALE E' VUOTO:
#     Assets.xcassets/AccentColor.colorset/Contents.json
#     {"colors": [{"idiom": "universal"}], "info": {...}}
# dichiara un colore e non dice quale.  Quindi il viola non e' mai venuto da
# li', e chi lo prende da li' non trova niente.  (C'e' anche un "Contents 2.json"
# identico, un file duplicato per errore nell'originale.)
#
# STA FUORI DAI DUE TEMI, E QUESTO E' VOLUTO: in scuro un viola schiarito
# diventa un lilla' slavato, e sopra un lilla' le icone bianche spariscono.
ACCENTO = "#64398b"

# Il colore delle icone FUORI dal viola.  Sopra il viola il bianco si legge
# sempre; sotto, in un pannello chiaro, il bianco sparisce.  Per questo ci
# sono due colori e non uno che "si adatta da solo": e' una cosa che nella
# pagina web fa CSS, e nei pulsanti di Qt la fa nessuno.
CHIARO = "#3b3547"

# LA TABELLA DEI NOMI DELLE ICONE
# --------------------------------
SF_SYMBOLS = {
    # navigazione
    "house.fill": "home",
    "book.fill": "bible",
    "doc.text.fill": "document-text",
    "film": "film",
    "calendar": "calendar",
    "bookmark.fill": "bookmark-square",
    # La sezione "Biblioteca Digitale".  Il file e' `biblioteca.svg`, che
    # disegna il libro aperto, lo schermo video con il play e la doppia nota
    # musicale.  Il trucco e' `currentColor`, non un colore scritto: e' il
    # modo in cui tutti gli altri 83 file funzionano in chiaro e in scuro.
    "library.fill": "biblioteca",
    # `SidebarView.SEZIONI` aveva "library" e non "library.fill": la chiave
    # non esisteva, `icon()` restituiva una QIcon vuota e il pulsante della
    # rail restava un quadrato con dentro il nulla.  Questa riga tiene anche
    # il nome corto, cosi' non si rompe di nuovo.
    "library": "biblioteca",
    # La sezione Scaricati.  `folder.fill` e non `icloud.and.arrow.down`,
    # che e' gia' la freccia di Novita': due sezioni con la stessa icona nella
    # stessa rail non si distinguono, e le due sezioni fanno due domande diverse.
    "folder.fill": "folder",
    # azioni
    "sidebar.left": "list",
    "chevron.left": "chevron-left",
    "trash": "trash",
    "trash.fill": "trash",
    # Il bottone "..." delle card e delle righe, e le icone del menu.
    # `dots-vertical.svg` e' il Tabler dei tre puntini **in verticale**, che e'
    # quello che si intende: il bottone sta nell'angolo della card e i punti
    # devono stare incolonnati.  Prima era `list.svg`, che e' un elenco con i
    # punti a sinistra: disegnato piccolo sembrava una riga di tre trattini, non
    # tre puntini.
    "ellipsis.circle": "dots-vertical",
    # La nuvoletta con la freccia in giu': scaricare.  Sta sulla card, in
    # basso a destra, e dice una cosa sola — questo pezzo si puo' prendere —
    # mentre il bottone "..." accanto dice "questo pezzo ha un menu'".  Sono
    # due cose diverse e quindi due bottoni diversi.
    "cloud.download": "cloud-download",
    "square.and.arrow.up": "share",
    "square.and.arrow.up.fill": "share",
    "icloud.and.arrow.down": "download",
    "paintbrush.fill": "text-paintbrush",
    "arrow.clockwise": "refresh",
    # La lingua.  Il file e' `language.svg` del progetto originale, che e' un
    # glifo "parla" (unicode ebbe, i suoi tag sono tongue/speak/translate) e
    # non un mappamondo.  Il nome del progetto e' "globe" perche' e' il
    # simbolo che la fascia usa per il selettore della lingua.
    #
    # Non si disegna un mappamondo e non si prende un nome che descriva il
    # file: nella tabella i nomi sono quelli del progetto originale, e il file
    # e' quello che c'e'.  E' la stessa regola di `fullscreen.svg` mappato
    # sotto "arrow.up.left.and.arrow.down.right": il nome dice a cosa serve,
    # il file dice come e' fatto.
    "globe": "language",
    "plus": "plus",
    "xmark": "close",
    "magnifyingglass": "search",
    "gearshape": "settings",
    "timer": "clock",
    "timer.file": "folder-open",
    "timer.menu": "list",
    # la fascia in alto e la rail
    #
    # Queste sei sono state aggiunte quando la cornice e' diventata quella
    # della app precedente: senza, `icon("chevron.right")` restituiva
    # un'icona vuota e la freccia avanti non si vedeva.
    #
    # IL TRABATTO
    # ------------
    # `icon()` vuole il NOME DEL PROGETTO ORIGINALE ("chevron.right"), non
    # il nome del file Tabler ("chevron-right").  Sono due nomi diversi e
    # somigliano: il punto e' nel primo, il trattino nel secondo.
    #
    # Passando il nome del file, la ricerca nella tabella non trova niente e
    # `icon()` restituisce un'icona vuota: nessun errore, nessun messaggio,
    # e un pulsante con dentro il nulla.  Il sintomo e' una cornice della
    # finestra tutta viola e senza icone, che sembra un problema di colori.
    "chevron.right": "chevron-right",
    "chevron.left.forwardslash.chevron.right": "chevron-right",
    # le due frecce del lettore: «porta giù alla striscia» e «torna su».
    # Servono perch' `Files/icons/` le ha gia' — `chevron-down.svg` e
    # `chevron-up.svg` — ma senza questa riga `icon()` non le trova e il
    # pulsante resta con dentro il nulla: un tasto che c'e' e che non si vede.
    "chevron.down": "chevron-down",
    "chevron.up": "chevron-up",
    "line.3.horizontal": "list",
    "line.3.horizontal.decrease": "filter",
    "slider.horizontal.3": "filter",
    # il tema
    "sun.max": "sun",
    "moon": "moon",
    # media
    "headphones": "headphones",
    "play.fill": "play",
    "pause.fill": "pause",
    "speaker.wave.2": "sound",
    "stop.fill": "close",
    # Il tasto del cambio di risoluzione: due schermi, e dentro quello davanti
    # un triangolo.  Il file e' `change-video-resolution.svg`, **dato
    # dall'utente** come `fullscreen.svg`, e non una scelta mia.
    #
    # Qui la chiave e' il nome del file, e non un nome di simbolo di macOS
    # come tutte le altre: quello non e' scritto da nessuna parte, e
    # inventarselo sarebbe mettere un nome falso accanto a nomi veri.  Il
    # nome dice quello che il tasto fa, ed e' l'unico nome da ricordare.
    #
    # Il file e' **a tracci** come gli altri 83, e non pieno come lo ha dato
    # l'utente: nella barra del lettore le altre icone sono tutte a tracci
    # (play, volume, schermo intero) e una pesta li' accanto si vedrebbe come
    # un comando diverso dagli altri.  Il colore lo prende lo stesso da
    # `currentColor`, quindi e' bianco sul nero e scuro sul chiaro senza che
    # nessuno lo dica.
    "change-video-resolution": "change-video-resolution",
    # varie
    "square.grid.2x2": "grid",
    "list.bullet": "list",
    "info.circle": "information-circle",
    "questionmark.circle": "question-circle",
    "arrow.down.doc": "download",
    # il lettore: i comandi che si toccano mentre si ascolta o si guarda
    #
    # Solo le chiavi **il cui file esiste davvero**.  Le 82 icone del
    # progetto precedente sono state scelte per la navigazione e non
    # coprono i comandi del lettore: non ci sono il schermo intero, i
    # sottotitoli e il testo grande.
    #
    # Una chiave senza file e' la trappola peggiore che ci sia: `icon()`
    # restituisce un'icona vuota senza dire niente, e il pulsante resta
    # li' con dentro il nulla.  Meglio non scriverla: se un domani si
    # aggiunge il file, la chiave si aggiunge insieme, e si vede subito
    # che il pulsante e' comparso.
    #
    # "sound" e' il glifo del volume, "music" quello dell'audio e
    # "video-camera" quello del video: sono i tre che ci sono e sono
    # giusti per quello che indicano.
    # I COMANDI DEL LETTORE
    # ---------------------
    # "arrow.up.left.and.arrow.down.right" e' il simbolo di macOS per
    # schermo intero, e nelle 82 icone del progetto precedente **non c'e'**.
    # Il nome lo si scrive solo se il file c'e': `icon()` con un nome assente
    # restituisce un'icona vuota e senza dire niente, quindi il pulsante
    # sarebbe quadrato e nero — sembrerebbe spento, e non si capirebbe
    # perche'.
    #
    #
    # Il file e' `fullscreen.svg`, **dato dall'utente**, e non una scelta
    # mia: il simbolo di partenza (`outline`, un quadrato) non diceva
    # "schermo intero" e l'utente se n'e' accorto guardando il pulsante.
    # Sono quattro frecce verso gli angoli, che e' esattamente il gesto.
    #
    # Le quattro frecce si distinguono da una cornice semplice perche' il
    # pulsante ha accanto play e chiudi: un quadrato in mezzo a una freccia
    # di play sembra un quarto comando che non e' detto cosa faccia.
    "arrow.up.left.and.arrow.down.right": "fullscreen",
    "arrow.clockwise.circle": "refresh",
    "music.note": "music",
    "video": "video-camera",
    "star.fill": "star",
    "quote.opening": "quote-circle",
    "backward.fill": "audio",
    "forward.fill": "forward",
}

# Dove si cercano i file.  La radice e' la prima perche' e' la piu' grande e
# non ha sottocartelle; se un'icona finisce in colorate/ viene trovata li'.
# Si calcola da BUNDLE_DIR e non da bundle_file(), perche' bundle_file e'
# definito piu' in basso e questa riga gira all'import del modulo.
ICON_DIR = BUNDLE_DIR / "Files" / "icons"
ICON_DIRS = (ICON_DIR, ICON_DIR / "colorate")

#: Le icone gia' disegnate, per (file, colore, lato).
#:
#: Il motivo sta nella misura, non nell'ottimizzazione.  Una griglia da 300 card
#: chiama `icon()` **tre volte per card** — il glifo, la nuvoletta e i tre
#: puntini — quindi 900 volte per lo stesso schermo, con le stesse tre icone.
#: Prima ogni chiamata rileggeva l'SVG dal disco, ci faceva due espressioni
#: regolari sopra e lo **rasterizzava** in un pixmap: 272 ms per ricostruire la
#: griglia, di cui 120 in questo pezzo solo.
#:
#: Non cresce: `QIcon` e' condiviso in modo implicito, quindi restituire la
#: stessa istanza a centinaia di pulsanti e' esattamente per quello che Qt e'
#: fatto, e il costo di una copia e' un puntatore.
_cache_icone: dict = {}
_CACHE_ICONE_MAX = 512


def _trova_icona(nome: str) -> Path | None:
    """Il file SVG dell'icona, o None.

    Si cerca nella radice e poi nelle sottocartelle.  La radice viene prima
    perche' e' la piu' grande e non ha sottocartelle.

    Il risultato e' messo via: `_trova_icona` rispondeva con `is_file()` ogni
    volta, e quei `stat` erano 900 per schermo.  Il nome del file e' l'unica
    chiave possibile perche' i file non cambiano dentro un avvio dell'app.
    """
    già = _cache_percorso.get(nome)
    if già is not None:
        return già
    trovato = None
    for cartella in ICON_DIRS:
        candidato = cartella / f"{nome}.svg"
        if candidato.is_file():
            trovato = candidato
            break
    _cache_percorso[nome] = trovato
    return trovato


_cache_percorso: dict = {}


def svg_colorato(percorso: Path, colore: str, lato: int = 22) -> QIcon:
    """Disegna un SVG nel colore richiesto e ne fa una QIcon.

    PERCHE' SI SOSTITUISCE "currentColor"
    ------------------------------------
    Le icone Tabler sono disegnate a tracci con ``stroke="currentColor"``:
    il colore non e' scritto nel file e lo prende dal testo che le contiene.
    In una pagina web funziona da solo.

    In un pulsante di Qt NON funziona, perche' li non c'e' un foglio di stile
    e dentro un file SVG ``currentColor`` non vuol dire niente: chi lo
    interpreta e' il CSS, e il CSS non c'e'.  Il risultato sarebbe un'icona
    con il tracci di default, che e' nero, e nero su nero non si vede.

    Per questo la parola viene sostituita con il colore vero PRIMA di
    disegnare.  Non e' un trucco: e' quello che il modulo delle icone
    dell'app precedente fa con l'argomento ``color``, e funziona per lo
    stesso motivo.
    """
    chiave = (str(percorso), colore, lato)
    già_fatta = _cache_icone.get(chiave)
    if già_fatta is not None:
        return già_fatta

    try:
        grezzo = percorso.read_text(encoding="utf-8")
    except OSError:
        return QIcon()

    svg = re.sub(r"<!--.*?-->", "", grezzo, flags=re.S)
    svg = svg.replace("currentColor", colore)
    # Si toglie il colore fisso se l'icona lo avesse: cosi' il colore
    # richiesto vince sempre, e l'icona resta leggibile in ogni tema.
    svg = re.sub(r'(stroke|fill)="#[0-9a-fA-F]{3,8}"', rf'\1="{colore}"', svg)

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()

    # IL DIFETTO CHE C'ERA, MISURATO
    # ------------------------------
    # Prima il disegno veniva messo in un pixmap di 2*lato e poi ridotto a
    # mano in due pixmap, lato e 2*lato, aggiunti entrambi alla QIcon:
    #
    #     for misura in (lato, grande):
    #         ridotto = QPixmap(misura, misura)
    #         ridotto.drawPixmap(0, 0, pixmap)      <- riduce a mano
    #         icona.addPixmap(ridotto)
    #
    # sembra la cosa giusta e non lo e'.  `QIcon.pixmap(lato, lato)` cerca
    # il pezzo piu' vicino alla misura chiesta e, trovando il pixmap da
    # 2*lato, lo RITAGLIA a lato per lato invece di ridurlo.  Lo chiede
    # gia' pronto e non lo ridimensiona.
    #
    # Misurato, su home disegnata a 160:
    #
    #     render(pittore, rettangolo) 160   x[ 13..146]  <- giusto
    #     icon().pixmap(160, 160)           x[ 26..159]  <- tagliato a destra
    #
    # Il sintomo nella finestra e' una traccia che non somiglia a niente:
    # per la casa una diagonale, per le frecce un arco, per l'ingranaggio una
    # curva.  Casella giusta, colore giusto, disegno sbagliato, e sembrava
    # un difetto di stile invece che di dimensione.
    #
    # LA CORREZIONE
    # -------------
    # Un solo pixmap, a 2*lato, con dentro dichiarato che e' un'immagine
    # due volte piu' grande di un'icona di `lato`.  E' quello che Qt si
    # aspetta per uno schermo ad alta risoluzione, e Qt riduce da solo
    # quando si chiede una misura minore.
    grande = lato * 2
    pixmap = QPixmap(grande, grande)
    pixmap.fill(Qt.GlobalColor.transparent)
    pittore = QPainter(pixmap)
    pittore.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(pittore, QRectF(0.0, 0.0, float(grande), float(grande)))
    pittore.end()

    # QUESTA RIGA E' LA CORREZIONE.  Senza, il fattore di scala del
    # dispositivo resta 1 e Qt crede che il pixmap sia un'icona di 2*lato.
    pixmap.setDevicePixelRatio(2.0)
    icona = QIcon(pixmap)
    # Il colore fa parte della chiave, quindi un cambio di tema non serve
    # svuotare niente: sono chiavi diverse.  Il tetto c'e' per il caso in cui un
    # tema con molti colori e molte misure farebbe crescere il dizionario senza
    # fine, e a quel punto si preferisce ricominciare.
    if len(_cache_icone) >= _CACHE_ICONE_MAX:
        _cache_icone.clear()
    _cache_icone[chiave] = icona
    return icona


def icon(name: str, colore: str = "#ffffff", lato: int = 22) -> QIcon:
    """L'icona corrispondente a un nome del progetto originale.

    Il nome e' quello di macOS ("house.fill"), perche' e' il nome con cui
    chiamano le icone tutti i pezzi del porting.  Il file disegnato e' quello
    di Tabler che gli corrisponde.

    Se il nome non e' nella tabella si restituisce un'icona vuota: e' quello
    che faceva anche il progetto originale quando il simbolo non esisteva, e
    fa in modo che una riga nuova non butti giu' la barra.
    """
    nome_file = SF_SYMBOLS.get(name)
    if not nome_file:
        return QIcon()
    percorso = _trova_icona(nome_file)
    if percorso is None:
        print(f"icona {name} -> {nome_file}.svg non c'e' ⚠️")
        return QIcon()
    return svg_colorato(percorso, colore, lato)


def icona_tabler(nome: str, colore: str = "#ffffff", lato: int = 22) -> QIcon:
    """L'icona con dentro il **nome del file** Tabler, non quello del simbolo.

    PERCHE' ESISTE, E `icon` non BASTA
    ---------------------------------
    `icon()` vuole il nome con cui il progetto originale chiama le icone
    ("house.fill", "film") e cerca il file Tabler corrispondente nella tabella
    `SF_SYMBOLS`.  E' la regola giusta per tutto cio' che esisteva gia' nel
    progetto: il nome del simbolo e' il nome con cui il resto del porting chiama
    ogni icona, e la tabella tiene il ponte fra i due mondi.

    Ma le dodici icone delle **categorie di pubblicazioni** non hanno un
    simbolo corrispondente in macOS: nell'app per Windows sono disegni
    (`pub_type_book`, `pub_type_watchtower`) che non esistono da un'altra parte.
    Inventare un nome di simbolo per usarle con `icon()` sarebbe scrivere una
    riga falsa nella tabella per far passare una chiamata.

    Quindi qui si chiama il file per quello che e': `icona_tabler("book", ...)`
    disegna `Files/icons/book.svg`.  E la stessa funzione serve a tutto cio'
    che non viene da macOS.

    Se il nome non c'e' restituisce un'icona vuota, come `icon()`: una riga
    senza icona e' meno male di un programma che non si apre.
    """
    percorso = _trova_icona(nome)
    if percorso is None:
        print(f"icona Tabler {nome}.svg non c'e' ⚠️")
        return QIcon()
    return svg_colorato(percorso, colore, lato)


def highlight_color(index: int) -> QColor:
    """Il colore della sottolineatura numero ``index`` (1..6)."""
    if 1 <= index <= len(HIGHLIGHT_HEX):
        return QColor(f"#{HIGHLIGHT_HEX[index - 1]:06x}")
    return QColor("#ffffff")


class Stuff:
    """Metodi statici, come in Swift."""

    @staticmethod
    def clear_bible_book_name(name: str) -> str:
        """Ripulisce il nome lungo di un libro della Bibbia.

        La sostituzione e' fatta sempre nell'ordine in cui sta qui dentro, e
        non in un dizionario: l'ordine conta.  Per esempio "Seconda" va
        cancellata prima di "Prima"? No: i due non si pestano i piedi, ma
        "Terza" dopo "Seconda" si, se i numeri fossero romani.  La regola
        semplice e' che questo e' il posto dove si corregge, e si lascia
        com'e' finche' un nome non esce male.
        """
        clear_name = name
        for vecchio, nuovo in (
            ("Primo", "1"),
            ("Prima", "1"),
            ("Secondo", "2"),
            ("Seconda", "2"),
            ("Terza", "3"),
            ("libro di ", ""),
            ("libro dei ", ""),
            ("libro delle ", ""),
            (" (Qoèlet)", ""),
            ("Vangelo secondo ", ""),
            (" degli Apostoli", ""),
            ("Lettera ai ", ""),
            ("Lettera agli ", ""),
            ("Lettera a ", ""),
            ("lettera ai ", ""),
            ("lettera a ", ""),
            ("Lettera di ", ""),
            ("lettera di ", ""),
            (" a Giovanni (Apocalisse)", ""),
        ):
            clear_name = clear_name.replace(vecchio, nuovo)
        return clear_name

    @staticmethod
    def hex_color(hex_value: int) -> QColor:
        """Un colore da un intero 0xRRGGBB.  Stessi tre canali di ``hexColor``."""
        return QColor(
            (hex_value >> 16) & 0xFF,
            (hex_value >> 8) & 0xFF,
            hex_value & 0xFF,
        )

    @staticmethod
    def add_base_files() -> None:
        """Prepara la cartella dati e ci mette dentro i file che servono.

        swift-ui, script.js e i due file di userData/ arrivano dalla cartella
        Files/ del programma.  I primi due vengono tolti e rimessi a ogni
        avvio, cosi' una versione nuova del CSS si vede subito; il database e
        il manifesto di default no, perche' uno contiene quello che hai
        scritto tu.
        """
        Paths.prepare()
        user_data_folder = get_documents_directory() / "userData"
        user_data_folder.mkdir(parents=True, exist_ok=True)
        documents_folder = get_documents_directory() / "Documents_I"
        documents_folder.mkdir(parents=True, exist_ok=True)

        documents = get_documents_directory()
        files = [
            documents / "style.css",
            documents / "script.js",
            user_data_folder / "user_data.db",
            user_data_folder / "manifestDefault.json",
        ]

        # style.css e script.js: si rimettono sempre, e' quello che voleva
        # il codice originale con i due removeItem().
        for file in (files[0], files[1]):
            try:
                file.unlink()
            except FileNotFoundError:
                pass

        for file in files:
            if not file.exists():
                copyfile_to_user_document_directory(file)

    @staticmethod
    def get_mac_name() -> str:
        """Il nome della macchina.

        Il nome del metodo si conserva anche se non e' piu' un Mac: e' il
        nome che finisce nel manifest del backup, e i backup gia' fatti
        continuano a essere riconosciuti.  Su Linux il nome e' quello
        dell'host.  Se non si trova, "Mac" come nell'originale.
        """
        try:
            name = socket.gethostname()
        except OSError:
            return "Mac"
        return name or "Mac"

    @staticmethod
    def _get_json(url: str):
        """Scarica un JSON e lo restituisce.  None se non si puo'."""
        try:
            with urllib.request.urlopen(url, timeout=30) as risposta:
                return json.loads(risposta.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as errore:
            print(f"Errore {errore} ⚠️")
            return None

    @staticmethod
    def get_manifest() -> str | None:
        """Il nome della versione corrente del catalogo, es. una data.

        In Swift era URLSession + DispatchSemaphore.  Qui basta urlopen: la
        stessa chiamata, la stessa risposta.  Attenzione pero': blocca, e va
        chiamata fuori dal main thread.

        NON SCRIVE NIENTE A TERMINALE
        ------------------------------
        Prima qui c'era un `print` con il nome della versione.  Non c'e' piu'
        perche' questa funzione viene chiamata anche solo per capire se il
        catalogo e' da aggiornare, e cioe' a ogni apertura del programma: la
        riga compariva ogni volta, e un'informazione che serve al programma
        non ha bisogno di finire sul terminale.  Il nome viene ricordato in
        `Utility/Aggiornamenti.py`, dove serve davvero.
        """
        json_data = Stuff._get_json(MANIFEST_URL)
        if json_data is None:
            return None
        return json_data.get("current", "") or None

    @staticmethod
    def get_jwpub_url(api_link: str) -> str | None:
        """L'indirizzo del .jwpub dentro la risposta dell'API dei media.

        La risposta ha la forma files -> lingua -> JWPUB[0] -> file -> url.
        Si scende quella strada perche' e' l'unica che c'e': non si sceglie
        fra piu' link.
        """
        json_data = Stuff._get_json(api_link)
        try:
            url = json_data["files"]["I"]["JWPUB"][0]["file"]["url"]
        except (TypeError, KeyError, IndexError) as errore:
            print(f"Errore {errore} ⚠️")
            return None
        if url:
            print(f"Manifest: {url} ✅")
            return url
        return None


def bundle_file(name: str) -> Path:
    """Il percorso di un file dentro la cartella Files/ del programma."""
    from Utility.Extensions.Ext_FileManager import BUNDLE_DIR
    return BUNDLE_DIR / "Files" / name


def leggi_utente(percorso, default: str = "") -> str:
    """Legge un file dalla cartella dati dell'utente, o restituisce ``default``.

    Era ``try? String(contentsOf:) ?? ""`` in Swift: se il file non c'e' non
    e' un errore, e' un file che non e' stato ancora scaricato.  Sotto Linux
    e' una condizione normale, non un'eccezione.
    """
    try:
        return Path(percorso).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return default


def carica_style(chiaro: bool | None = None) -> str:
    """Il foglio di stile del capitolo, con i colori del tema.

    Si legge da ``userData`` e non dalla cartella del programma perche' e'
    ``Stuff.add_base_files()`` a copiare li' la versione buona, e li' un
    utente puo' correggersela.  Se non c'e' neanche li', si prende da
    ``Files/``: meglio il foglio di stile del programma che nessuno.

    I COLORI DEL TEMA VENGONO AGGIUNTI QUI
    --------------------------------------
    Il file `style.css` e' quello del progetto originale, e i suoi colori
    sono quelli del sito: testo nero, grigi `#626262`, caselle con fondo
    `#f1f1f1`.  Quelle regole vanno bene su un foglio bianco.

    Ma la pagina vive dentro una finestra che puo' essere **scura**, e
    allora succede quello che e' successo: il testo del capitolo restava
    nero su uno sfondo scuro, e non si leggeva niente.  Il pezzo che
    segue mette i colori del tema al posto di quelli del sito.

    LE TRE REGOLE
    -------------
    1. il testo del capitolo prende il colore del tema: in scuro e'
       bianco, e si legge;
    2. i grigi intermedi (`#626262`) diventano il grigio del tema, che in
       scuro e' piu' chiaro: sono le didascalie e i sottotitoli, e devono
       restare leggibili;
    3. le caselle con fondo chiaro — le pagine stampate — tengono il
       fondo chiaro e il testo **scuro**: un foglio stampato e' bianco,
       e il testo nero su bianco e' l'unica cosa che si legge.

    La barra dello scorrimento e'viola come quella delle altre sezioni:
    il motore di Chromium la disegna da solo, e senza questi comandi e'
    grigia, mentre in tutte le altre sezioni e' viola.
    """
    testo = leggi_utente(get_documents_directory() / "style.css")
    if not testo:
        try:
            testo = bundle_file("style.css").read_text(encoding="utf-8")
        except OSError:
            testo = ""
    if chiaro is None:
        from Utility import tema
        # Il tema **attivo**, non quello salvato: dentro la finestra il
        # file cambia solo quando il programma viene chiuso, e un capitolo
        # aperto dopo aver cambiato tema deve gia' essere scuro.
        chiaro = tema.tema_attivo()
    return testo + _colori_del_tema(chiaro)


def _colori_del_tema(chiaro: bool) -> str:
    """Il pezzo di foglio di stile con i colori del tema.

    Va **dopo** `style.css`, non prima: con la stessa importanza, l'ulti-
    ma regola che incontra e' quella che vince.
    """
    from Utility import tema

    colori = tema.colori(chiaro)
    testo = colori["testo"]
    grigio = colori["grigio"]
    sfondo = colori["sfondo"]
    # Il fondo chiaro delle caselle: quello del sito (#f1f1f1) sta bene
    # anche in scuro, perche' e' il colore di un foglio stampato.
    chiaro_casella = "#f1f1f1"
    scuro_casella = "#292929"
    return f"""
/* ---- i colori del tema dell'app ( Utility/Stuff.py ) ---- */
:root {{
  color-scheme: {tema.nome_css(chiaro)};
}}
body {{
  background: {sfondo};
  color: {testo};
}}
/* i grigi intermedi del sito non si leggono in scuro */
p.qu, figcaption, .contextTtl, .featureTtl,
.blockTxt, .bodyTxtAlt.rule, .stdCaption, .stdPullQuote, blockquote.rule {{
  color: {grigio};
}}
/* le caselle con fondo chiaro: testo scuro, perche' il fondo e' chiaro */
.blockTeach, .boxSupplement, .du-bgColor--warmGray-50, .du-bgColor--warmGray-100 {{
  background-color: {chiaro_casella};
  color: {scuro_casella};
}}
.blockTeach .contextTtl, .boxSupplement .contextTtl {{
  color: {scuro_casella};
}}
/* i bordi colorati del sito (le linee arancioni) */
.du-borderColor--orange-700 {{ border-color: #c25708; }}
.du-color--orange-700 {{ color: #c25708; }}
.du-color--coolGray-600 {{ color: {grigio}; }}
/* La barra di scorrimento: la disegna il programma, non il motore.
   Il capitolo ha la barra del programma accanto (6 pixel, viola, la
   maniglia sottile), come in tutte le altre sezioni, e il CSS della pagina
   tiene la sua a zero: cosi' le due non si vedono insieme. */
::-webkit-scrollbar {{ width: 0; height: 0; }}
"""


def carica_script() -> str:
    """Il JavaScript del capitolo.  Vedi ``carica_style`` per il perche'."""
    testo = leggi_utente(get_documents_directory() / "script.js")
    if not testo:
        try:
            testo = bundle_file("script.js").read_text(encoding="utf-8")
        except OSError:
            testo = ""
    return testo


def control_background_color(widget=None) -> QColor:
    """Il colore di fondo dei controlli.

    In Swift ``Color(NSColor.controlBackgroundColor)``, che segue il tema di
    sistema (chiaro o scuro).  In Qt e' il ruolo Base della palette, che
    cambia da solo con il tema della applicazione: quindi si prende dalla
    palette e non si scrive un colore fisso.
    """
    if widget is not None:
        return widget.palette().color(widget.palette().ColorRole.Base)
    return QApplication.palette().color(QApplication.palette().ColorRole.Base)


ICON_SIZE = QSize(22, 22)