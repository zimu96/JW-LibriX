#
#  tema.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""I due temi, con i colori presi dagli asset originali.

I COLORI DA DOVE VENGONO
------------------------
Sono i valori che la tua app precedente ha campionato dagli PNG dell'app
originale, e quella tabella e' giusta: i colori si contano sui pixel dei
file, non si indovinano.

    ruolo              chiaro     scuro
    sfondo             #ffffff    #1f1f1f
    pannello           #ffffff    #262626
    bordo              #e3e3e3    #3d3d3d
    testo              #333333    #f0f0f0
    grigio             #8e8e8e    #a7a7a7
    lavato             #efeaf5    #2e2838     il viola al 12% / 18%
    hover              #f0edf2    #333333

IL VIOLA E' UNO SOLO E NON E' UN COLORE DI TEMA
-----------------------------------------------
Prima il viola stava dentro i due temi e cambiava: #5b3c88 in chiaro,
#c1a7e2 in scuro.  In scuro la fascia diventava un lilla' slavato, e sopra
un lilla' le icone bianche spariscono.

Quindi il viola sta FUORI dai due temi.  Il tema cambia lo sfondo, il testo
e i bordi; la fascia e la rail sono un pezzo dell'app e restano come sono.
E' la stessa regola che vale in Qt: un tema si applica alla finestra, e i
pulsanti della fascia non cambiano colore con il tema.

IL VIOLETTO CHE ABBIAMO MISURATO
--------------------------------
Sul campionamento c'e' una differenza, e la dico perche' due progetti non
possono dare due numeri diversi per la stessa cosa:

    questo file       #5b3c88   (dalla app precedente, che dichiara
                                "campionato dagli asset originali")
    misurato sull'icona  #64398b

Campionando davvero i pixel di ``Icon-1024.png`` il viola e' #64398b: sono
548.655 pixel su 1.048.576, ed e' nettamente il primo colore.  Il valore
#5b3c88 e' molto vicino ma non e' quello che c'e' nel file.

Qui dentro metto il valore che ho misurato, e il precedente lo tengo
accanto con la sua provenienza: se un domani si torna sul campionamento
dell'app precedente, e' una riga.
"""

# ---------------------------------------------------------------------------
# IL VIOLA
# ---------------------------------------------------------------------------

ACCENTO = "#64398b"              # misurato sui pixel di Icon-1024.png
ACCENTO_ALTRO = "#5b3c88"        # il valore della app precedente

#: Il viola chiaro della barra di avanzamento.  Sta qui e non dentro i due
#: temi per lo stesso motivo di `ACCENTO`: la barra sta **sopra** la fascia, e
#: la fascia non cambia colore, quindi un colore "di tema" cambierebbe da solo
#: mentre il fondo non cambierebbe — e in scuro diventerebbe una riga scura
#: su una fascia scura, cioe' invisibile.
#:
#: Il bianco non va bene: su una riga di 3 pixel il contrasto con il viola
#: e' fortissimo e si legge come un difetto di disegno, non come una
#: percentuale.  Questo e' il viola schiarito abbastanza da vedersi e
#: abbastanza vicino da sembrare parte della fascia.
AVANZAMENTO = "#a77fd4"

# QUI C'ERANO DUE ALTRI COLORI, E NON SONO PIU'
# ----------------------------------------------
# `ACCENTO_BORDO` (#4a2c70) e `ACCENTO_ALTRO_BORDO` (#422c66) erano il viola
# scurito a mano, per i bordi sotto la fascia e a destra della rail.
#
# Sono tolti perche' non servivano piu': i due bordi che li usavano sono
# spariti, e il foglio di stile sotto spiega perche' sono spariti.  Restare
# dei colori senza un posto in cui sono usati e' il modo piu' economico di
# ricreare il difetto senza accorgersene: il giorno che qualcuno rimette un
# bordo, il colore c'e' gia' e sembra una scelta fatta apposta.
#
# Erano inventati: la tavolozza di `jwl/DESIGN-SYSTEM.txt` ha tre ruoli
# campionati dai pixel, e sono accento, testo secondario, testo forte.
# Nessuno e' un viola scurito.

# I sei colori per sottolineare, dall'app originale.  UserMarkColor della
# app originale: None=0, Yellow=1, Green=2, Blue=3, Pink=4, Orange=5, Purple=6.
MARCATURE = [0xFFEB3B, 0x9EF953, 0x29B6F6, 0xFFA1C8, 0xFFB976, 0xAF85FF]

# L'oro della stella dei Preferiti.  Stessa in chiaro e in scuro, come il
# viola: e' un segno, non una parte della pagina che si adatta al fondo.
#
# STA QUI E NON IN OGNI SCHERMATA
# ------------------------------
# La stella compare nelle liste delle pubblicazioni e nella sezione Scaricati.
# Definita in due posti, il giorno che la si corregge a mano perche' non si
# vede in chiaro, se ne corregge una e l'altra resta quella vecchia: e la
# differenza si vede solo in uno dei due temi, che e' il modo peggiore per
# trovare un difetto di colore.
#
# PERCHE' L'ORO E NON IL COLORE DEL TESTO
# --------------------------------------
# Una stella del colore del titolo sembra un pezzo di titolo.  E non e' il
# viola dell'accento perche' quello e' il colore dei due pulsanti della riga,
# e un terzo uso dello stesso colore nella stessa riga non aiuta a distinguere
# niente.
ORO_PREFERITO = "#e0b341"


# ---------------------------------------------------------------------------
# I DUE TEMI
# ---------------------------------------------------------------------------

CHIARO = {
    "sfondo": "#ffffff",
    "pannello": "#ffffff",
    "bordo": "#e3e3e3",
    "testo": "#333333",
    "grigio": "#8e8e8e",
    "lavato": "#efeaf5",
    "hover": "#f0edf2",
    "ombra": "0 1px 2px rgba(0,0,0,.10)",
    "img": "#e8e6e4",
    "vuoto": "#aaaaaa",
    "spento": "#c7c7c7",
    # IL FONDO DIETRO LA GRIGLIA DELLA SEZIONE BIBLIOTECA
    # ------------------------------------------------------
    # In chiaro non e' `sfondo`: `sfondo` e' bianco e serve alle pagine dove
    # non c'e' una griglia, ma qui il fondo dei tasselli e' grigio e sta un
    # gradino sotto le celle bianche.  Senza questa chiave la griglia
    # diventerebbe bianco su bianco e le celle non si vedrebbero: non e' un
    # colore a caso, e' il fondo fra due celle.
    #
    # In scuro la chiave vale come `sfondo`: la pagina e' gia' #1f1f1f e il
    # fondo fra le celle non ha motivo di essere un altro scuro.
    "griglia": "#f1f1f1",
    # IL COLORE DELLE ICONE DI CATEGORIA
    # ------------------------------------
    # Le icone delle pubblicazioni sono disegni a tratteggio dentro un quadrato
    # 100x100.  In chiaro il tratteggio e' grigio scuro (#4F4F4F) su fondo
    # bianco; in scuro **invertisce** e diventa grigio chiaro (#C0C0C0), perche'
    # la cella passa da bianca a #292929 e un tratteggio scuro sparirebbe
    # dentro il fondo.
    #
    # Non e' un colore di tema libero: e' l'inverso del fondo della cella, e se
    # i due non si muovono insieme la categoria sparisce.
    "icona": "#4f4f4f",
    # IL TESTO DELLA TAB ATTIVA
    # --------------------------
    # Il viola `ACCENTO` (#64398b) su fondo scuro (#1f1f1f) non si legge: il
    # contrasto e' troppo basso e la tab attiva sembra non attiva.  Quindi il
    # testo della tab attiva in scuro e' il viola chiaro (#C1A7E2), che e'
    # anche il colore dell'icona selezionata nella barra laterale.
    #
    # La **barra** sotto la tab attiva resta `ACCENTO` in entrambi i temi: e'
    # un segnale, come la fascia e la rail, e non segue il tema.
    "accentoTesto": "#64398b",
    # Il nero di una finestra che mostra solo un video o una figura.
    #
    # E' nero in **entrambi** i temi, e non e' una dimenticanza: una figura o
    # un video si guardano su fondo nero anche in tema chiaro, perche' il nero
    # e' la fine delle immagini e mettere li' del grigio fa vedere la
    # finestra invece della figura.  Come la fascia e la rail, che non si
    # adattano al tema: sono un pezzo dell'app, non una scelta.
    #
    # Messo qui perche' i colori si prendono dal tema e non si scrivono a mano
    # nelle regole: se il nero serve in tre posti, deve stare in un posto solo.
    "pieno": "#000000",
    # Il testo **su** quel nero.  Va detto a parte dal testo normale perche' il
    # testo normale in tema chiaro e' grigio scuro (`#333333`), e grigio
    # scuro su nero non si legge.  Una finestra che mostra solo una figura o
    # un video e' nera e chiara **anche quando il programma e' in tema
    # chiaro**, quindi anche il suo testo lo e': il tema non si stende a una
    # superficie che non e' del tema.
    "pienoTesto": "#f0f0f0",
}

SCURO = {
    "sfondo": "#1f1f1f",
    "pannello": "#262626",
    "bordo": "#3d3d3d",
    "testo": "#f0f0f0",
    "grigio": "#a7a7a7",
    "lavato": "#2e2838",
    "hover": "#333333",
    "ombra": "0 1px 2px rgba(0,0,0,.5)",
    "img": "#2b2b2b",
    "vuoto": "#767676",
    "spento": "#545454",
    # Vedi la nota di questa chiave in `CHIARO`: il fondo dietro la griglia e'
    # gia' il fondo della pagina, che in scuro e' #1f1f1f.  Resta la chiave
    # perche' le due cose si muovono insieme e una chiave che c'e' solo in un
    # tema e' una chiave che un giorno manca.
    "griglia": "#1f1f1f",
    # Vedi la nota in `CHIARO`: in scuro il tratteggio INVERTE perch' il fondo
    # della cella passa da bianco a #292929.
    "icona": "#c0c0c0",
    # Vedi la nota in `CHIARO`: il viola profondo non si legge su #1f1f1f.
    "accentoTesto": "#c1a7e2",
    # Vedi la nota di questa chiave in `CHIARO`: il nero di una finestra che
    # mostra solo un video o una figura e' nero anche in tema chiaro.
    "pieno": "#000000",
    # E il testo su quel nero anche: in tema scuro il testo normale e' gia'
    # chiaro, ma la chiave ci sta lo stesso perche' i due temi si leggono
    # insieme e una chiave che c'e' solo in uno e' un chiave che un giorno
    # manca.
    "pienoTesto": "#f0f0f0",
}

TEMI = {"chiaro": CHIARO, "scuro": SCURO}


# ---------------------------------------------------------------------------
# LE MISURE
# ---------------------------------------------------------------------------
#
# Non sono dedotte dagli screenshot: sono nella specifica.
#
RAIL = 48           # la colonna stretta delle icone, a sinistra
ALTO = 32           # la fascia in alto
RAGGIO = 8          # gli angoli arrotondati
ICONA_RAIL = 36     # la casella dell'icona nella rail
ALTEZZA_RAIL = 34
ICONA_ALTO = 32     # la casella di un pulsante nella fascia


def colori(chiaro: bool) -> dict:
    """Il dizionario del tema richiesto."""
    return CHIARO if chiaro else SCURO


def nome(chiaro: bool) -> str:
    return "chiaro" if chiaro else "scuro"


def nome_css(chiaro: bool) -> str:
    """Il nome del tema per il CSS: ``light`` o ``dark``.

    `nome()` dice «chiaro» o «scuro», che e' italiano e va bene per
    l'interfaccia.  Ma il CSS vuole ``light`` e ``dark``, e un valore
    sbagliato li' non fa niente: il browser ignora `color-scheme` e la
    pagina resta con i colori del **sistema**, che non e' quello
    dell'app.
    """
    return "light" if chiaro else "dark"


# ---------------------------------------------------------------------------
# I FONT
# ---------------------------------------------------------------------------
#
# PERCHE' SERVONO E PERCHE' NON BASTA QUELLO DEL SISTEMA
# -----------------------------------------------------
# La specifica dice ``font: 13px/1.45 'n400','Noto Sans'``.  Se si usa il
# font di sistema il testo ha un'altra aria e un'altra larghezza: la stessa
# frase occupa un numero di pixel diverso e le colonne non coincidono.  Non
# e' un dettaglio, e' la differenza fra "simile" e "uguale".
#
# Noto Sans e Noto Serif sono liberi (SIL OFL 1.1) e li porta gia' la app
# precedente, quindi non e' una scelta nuova: sono gli stessi file con lo
# stesso nome.  Roboto e' quello delle schermate UWP, DejaVu sta per i
# glifi che Noto non ha.
#
# WOFF
# ----
# I file sono .woff e non .ttf.  Qt li accetta: ``addApplicationFont``
# chiede a FreeType, e FreeType sa leggerli.  Verificato: i dodici file
# entrano e restituiscono le famiglie giuste.
#
# Roboto si carica DOPO Noto perche' a volte ha dentro un nome di famiglia
# coincidente e vince l'ultimo caricato.  L'ordine dei file non e' casuale.

FONT_DIR = "Files/font"
CORPO = 13            # il corpo del testo, come nella specifica
INTERLINEA = 1.45     # anche questo e' nella specifica
FAMIGLIA = "Noto Sans"
FAMIGLIA_SERIF = "Noto Serif"

_font_caricati = False


def cartella_font():
    """La cartella dei font dentro l'app."""
    from Utility.Extensions.Ext_FileManager import BUNDLE_DIR
    return BUNDLE_DIR / "Files" / "font"


def carica_font() -> str:
    """Carica i font dell'app e restituisce la famiglia da usare.

    Va chiamata una volta sola, DOPO che esiste la QApplication: senza un
    QApplication ``QFontDatabase`` non sa dove mettere i font e non carica
    niente, senza dire niente.

    Se la cartella non c'e' restituisce comunque il nome della famiglia: e'
    un ripiego, e un ripiego silenzioso e' meglio di un'eccezione che
    impedisce di aprire la finestra.
    """
    global _font_caricati
    from PyQt6.QtGui import QFontDatabase

    if _font_caricati:
        return FAMIGLIA

    cartella = cartella_font()
    trovato = False
    if cartella.is_dir():
        # Noto per primo, Roboto e DejaVu dopo: vince l'ultimo caricato fra
        # famiglie con lo stesso nome, e cosi' l'ordine e' quello giusto.
        for ordine in ("NotoSans", "NotoSerif", "Roboto", "DejaVu",
                       "Wt-ClearText"):
            for file in sorted(cartella.glob(f"{ordine}-*")):
                if file.suffix.lower() not in (".woff", ".ttf", ".otf"):
                    continue
                QFontDatabase.addApplicationFont(str(file))
                trovato = True

    _font_caricati = True
    if not trovato:
        print("Font dell'app non trovati: uso quello di sistema ⚠️")
    return FAMIGLIA


# ---------------------------------------------------------------------------
# IL TRABATTO DI Qt: IL FOGLIO DI STILE SU UN QWidget PURO
# ---------------------------------------------------------------------------
#
# In Qt il foglio di stile disegna fondo e bordo di un QWidget solo se il
# widget SA disegnarsi da solo.  Un QWidget puro non sa: il suo paintEvent
# di default non disegna niente, quindi una regola come
#
#     #scheda { background-color: ...; border: 1px solid ...; }
#
# viene IGNORATA senza dire niente.
#
# Non sembra un difetto del foglio di stile e non si vede con QLabel,
# QFrame o QPushButton: quelli lo sanno gia'.  Si vede solo con le classi
# che scriviamo noi, ed e' la parte che somiglia a Qt che non funziona.
#
# IL SINTOMO E' MENSO DI QUELLO CHE SEMBRA
# ---------------------------------------
# In chiaro il fondo della scheda e' bianco come la pagina e il bordo e'
# #e3e3e3: sembra che ci sia e sembra solo pallido.  Passando al tema
# scuro il fondo dovrebbe diventare #262626 sopra #1f1f1f, e non si vede
# NIENTE.  E' li' che si capisce che la regola non e' mai arrivata, e che
# il problema non e' il colore scelto.
#
# WA_StyledBackground e' l'attributo che dice a Qt "per me il foglio di
# stile vale".  Senza, le regole che nominano un QWidget puro non hanno
# effetto.


def sfondo(widget, nome: str = ""):
    """Il widget, con il foglio di stile che vale per lui.

    Va chiamata su ogni QWidget puro che ha una regola `#nome` con fondo o
    bordo.  Su QLabel, QFrame e pulsanti non serve: lo fanno gia' e la
    chiamata e' innocua.

    SE IL NOME CAMBIA, IL COLORE SI RICALCOLA
    -----------------------------------------
    Il nome dell'oggetto e' l'unica cosa che distingue due stati di uno
    stesso widget nel foglio di stile, e in Qt **cambiare il nome non basta**:
    il widget continua a mostrare il colore vecchio finche' non riceve un
    avviso di ricalcolo.  Il sintomo e' che la scheda premuta resta del
    colore di prima e la pagina resta del colore di prima: sembra che la
    regola non sia arrivata, mentre e' arrivata e non e' stata applicata.

    Quindi qui, se il nome e' davvero cambiato, si dice a Qt di rivedere il
    widget.  Il confronto con il nome di prima serve a non rifarlo a ogni
    chiamata: `sfondo` la chiamano decine di widget e il ricalcolo non e'
    gratis.
    """
    from PyQt6.QtCore import Qt

    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    if nome:
        if widget.objectName() != nome:
            widget.setObjectName(nome)
            stile = widget.style()
            if stile is not None:
                stile.unpolish(widget)
                stile.polish(widget)
        else:
            widget.setObjectName(nome)
    return widget


def applica_font(applicazione, chiaro: bool = True) -> None:
    """Mette il font del testo su tutta l'applicazione.

    Un foglio di stile che nomina un font lo mette SOLO dove lo nomina, e
    gli schermati che non hanno un foglio di stile restano con quello di
    sistema.  Impostando il font sull'applicazione tutti gli schermati,
    anche quelli creati dopo, partono con il font giusto.
    """
    from PyQt6.QtGui import QFont

    famiglia = carica_font()
    c = colori(chiaro)
    font = QFont(famiglia)
    font.setPointSize(CORPO)
    # L'interlinea e' un multiplo, e in Qt si mette come Frazione di altezza
    # di riga, non come "line-height".
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    applicazione.setFont(font)
    return c


# ---------------------------------------------------------------------------
# IL FOGLIO DI STILE
# ---------------------------------------------------------------------------
#
# Tutto quello che cambia con il tema sta in un foglio solo, e il tema si
# cambia riapplicandolo.  Non si tocca ogni widget uno per uno: e' la
# ragione per cui aggiungere una schermata non richiede di ricordarsi di
# colorarla.

def foglio_stile(chiaro: bool) -> str:
    """Il foglio di stile del tema.

    LE REGOLE DELL'APP PRECEDENTE, TRADOTTE
    ---------------------------------------
    * la fascia e la rail sono viola e bianche in entrambi i temi
    * il testo del tema non tocca la fascia
    * gli angoli sono arrotondati di 8 px, anche nella rail
    * la rail e' 48 px e le icone 36x34
    """
    c = colori(chiaro)
    return f"""
/* ---------- LA REGOLA GENERICA DEVE ESSERE TRASPARENTE ----------
   Il primo tentativo metteva qui dentro ``background-color: sfondo`` e
   sembrava la cosa giusta.  Non lo e'.

   In Qt un selettore ``QWidget`` non indica "il widget che contiene tutto",
   indica TUTTI i QWidget: le caselle dei pulsanti, i contenitori dei
   layout, i riquadri dentro i pannelli.  Quindi ogni contenitore che
   doveva lasciar vedere il viola della fascia si metteva da solo il fondo
   del tema sopra il viola, e la fascia risultava tagliata: una striscia
   bianca a destra, nel mezzo delle icone.

   Il sintomo e' una fascia viola che finisce a meta' finestra e le icone
   che galleggiano sul bianco.  Non sembra un problema di colori: sembra
   che la fascia sia della lunghezza sbagliata.

   Quindi: la regola generica e' trasparente, e il fondo si mette sui
   contenitori che devono averlo, uno per uno. */
QWidget {{
    background-color: transparent;
    color: {c['testo']};
    font-size: 13px;
}}

/* I contenitori con il fondo del tema.  Sono tre e sono elencati, non
   e' un caso: la finestra, la riga che tiene rail e colonna, e la colonna
   stessa.  Ogni altro contenitore e' trasparente e lascia vedere il fondo
   del padre. */
QMainWindow, #riga, #colonna, #contenitore {{
    background-color: {c['sfondo']};
}}

/* ---------- la fascia e la rail: viola in entrambi i temi ---------- */
/* Il tema non le tocca.  Sono un pezzo dell'app, non qualcosa che si
   adatta al fondo: e' la regola che evita il lilla' slavato in scuro. */

/* QUI C'ERANO DUE BORDI, E ADESSO NON CE NE SONO
   ----------------------------------------------
   La fascia aveva `border-bottom` e la rail `border-right`, entrambi di un
   pixel in un viola piu' scuro (#4a2c70).

   LA GEOMETRIA, MISURATA
   ----------------------
   Non e' come sembra guardando la finestra.  Misurando le posizioni vere:

     fascia   x= 48  y=0   1870 x 32
     rail     x=  0  y=0     48 x 1017

   La rail e' alta TUTTA la finestra e parte da `y=0`; la fascia parte da
   `x=48`, cioe' sta a fianco della rail e non sopra.  Non si incrociano.

   E IL BORDO CHE FACEVA IL DANNO ERA UNO SOLO
   ------------------------------------------
   Il `border-right` della rail e' a `x=47` e gira per tutta l'altezza, quindi
   passa anche per i 32 pixel di fascia.  In quei 32 pixel mette una riga
   scura fra la rail e la fascia: due pezzi di viola dello stesso colore
   separati da una riga scura.  E' la "riga nera" segnalata.

   Il `border-bottom` della fascia e' a `y=31` e parte da `x=48`, quindi NON
   passa sopra la rail: quello e' al suo posto e segna il confine col
   contenuto.

   La prima versione di questo commento diceva che i due bordi si
   incrociassero nell'angolo, ed era sbagliata: era scritta prima di misurare
   e raccontava quello che sembrava.  La misura e' un'altra cosa, e va nella
   spiegazione.

   PERCHE' COMUNQUE LI TOGLIO ENTRAMBI
   -------------------------------------
   Il confine col contenuto si vede gia' senza nessun bordo: il viola e'
   scuro abbastanza da stare bene sia su bianco sia su #1f1f1f.  Il bordo non
   aggiungeva separazione, aggiungeva solo il difetto nell'angolo.

   E LA SPECIFICA L'AVEVA DETTO PRIMA
   ---------------------------------
   `jwl/DESIGN-SYSTEM.txt` sulle due barre scrive una cosa sola, che restano
   viola in chiaro e in scuro.  Dei bordi non parla.  E la sua tavolozza ha
   tre ruoli campionati (accento, testo secondario, testo forte): nessuno e'
   un viola scurito.  `ACCENTO_BORDO` era un colore inventato di proposito,
   per separare una cosa che si separava gia' da sola. */
#fascia, #rail {{
    background-color: {ACCENTO};
    border: none;
}}
QLabel {{ background: transparent; }}

/* ---------- pulsanti della fascia e della rail ---------- */
QToolButton, QPushButton {{
    background: transparent;
    border: none;
    border-radius: {RAGGIO}px;
    padding: 0px;
}}
QToolButton:hover, QPushButton:hover {{
    background-color: rgba(255, 255, 255, 32);
}}
QToolButton:pressed, QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 48);
}}
QToolButton:disabled {{
    background: transparent;
}}

/* ---------- la voce attiva nella rail ---------- */
/* Fondo bianco al 22%: si vede qual e' la sezione senza dover cambiare
   il colore dell'icona, che resta bianca. */
QToolButton.attiva {{
    background-color: rgba(255, 255, 255, 56);
}}

/* ---------- le finestre di avviso: testi del tema, tasti viola ---------- */
QMessageBox {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
}}
QMessageBox QLabel {{ color: {c['testo']}; font-size: 13px; }}
QMessageBox QPushButton {{
    background-color: #64398b;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 7px 16px;
    min-width: 70px;
}}
QMessageBox QPushButton:hover {{ background-color: #a77fd4; }}

/* ---------- il contenuto ---------- */
#titoloPagina {{
    font-size: 20px;
    font-weight: 600;
    padding: 8px 12px;
}}
QToolTip {{
    background-color: {c['pannello']};
    color: {c['testo']};
    border: 1px solid {c['bordo']};
    padding: 3px 6px;
}}
/* ---------- le barre di scorrimento: viola e sottili ----------
   La maniglia e' **il viola dell'app**, quello della fascia e della rail
   (`ACCENTO`), e non il viola chiaro della barra di avanzamento: la barra di
   scorrimento sta dentro la pagina, accanto alle card, e il viola profondo e'
   quello che si legge li' senza fare a impazzire la striscia.  E non e' un
   colore "di tema" perche' la barra e' un segno, come la fascia: se cambiasse
   col tema cambierebbe da sola mentre il fondo resterebbe com'e'.

   E sono **sottili**: 3 pixel.  Con 10 era una barra, con 6 era ancora una
   barra, con 4 era gia' una riga ma si vedeva; tre pixel e' una riga che si
   vede appena e si capisce lo stesso che si puo' afferrare.  Nella Home sotto
   Preferiti ci sono quattro strisce di fila e le barre non devono fare
   rumore piu' delle card.

   Le due regole `add-line` e `sub-line` a zero non sono cosmetica: senza
   quelle Qt disegna i due pulsanti della barra e la striscia resta alta 10
   pixel anche se la maniglia e' piccola. */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {ACCENTO};
    border-radius: 1px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    width: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 3px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {ACCENTO};
    border-radius: 1px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0px;
    width: 0px;
}}

/* ---------- il mini-player in fondo ---------- */
/* IL DIFETTO CHE NON SI COPIA.
   Nella schermata scura della app precedente il mini-player era BIANCO:
   aveva il suo colore fisso e non guardava il tema.  Il risultato e' una
   striscia chiara in fondo a una finestra scura, che si vede male e
   sembra un errore.

   Qui i colori vengono dal tema come quelli di tutto il resto: sfondo,
   bordo, testo e grigio.  Il mini-player non ha nessun colore proprio,
   e per questo non puo' sbagliare: se il tema cambia, cambia anche lui.

   Non e' viola perche' il viola e' della fascia e della rail: il
   mini-player sta sotto il contenuto, e sotto il contenuto il fondo e'
   quello del tema. */
#mini {{
    background-color: {c['pannello']};
    border-top: 1px solid {c['bordo']};
}}
#mini .titolo {{
    color: {c['testo']};
    font-size: 13px;
}}
#mini .stato {{
    color: {c['grigio']};
    font-size: 11px;
}}
#mini QToolButton {{
    background: transparent;
    border-radius: {RAGGIO}px;
}}
#mini QToolButton:hover {{
    background-color: {c['hover']};
}}
/* QUI C'ERANO TRE REGOLE `#mini QSlider`, E SONO STATE TOLTE
   -------------------------------------------------------
   La striscia in fondo aveva le sue tre regole per i cursori, con colori
   suoi: la corsia grigia, la parte piena viola, la maniglia viola.  Il
   lettore grande aveva le sue, con altri colori.  Due cursori nella stessa
   finestra, due colori diversi, e l'utente ne correggeva uno e non sapeva
   che ce n'era un altro.

   La correzione non e' stata copiare i colori giusti qui: e' stato dare ai
   due cursori **lo stesso nome di oggetto** — `barraLettore` e
   `volumeLettore`, come nel lettore grande — cosi' una sola regola vale per
   tutti e quattro.  Con quattro regole, il giorno che il viola cambia, ne
   cambia una e gli altri tre restano indietro.

   Se un domani la striscia in fondo avesse un cursore **diverso** — uno che
   non e' un cursore di tempo o di volume — allora avrebbe bisogno di un
   nome suo e di regole sue, e sarebbe giusto.  Finche' e' un cursore come
   gli altri, ha un nome come gli altri.

/* ---------- il lettore video ---------- */
/* Stessa regola: il video sta nel contenuto, quindi prende il fondo del
   tema.  Il nero lo si mette solo all'INTERNO del video, dove serve per
   non avere le lettere bianche su bianco.  Intorno al video resta il
   tema, e cosi' in scuro non c'e' una cornice bianca. */
#video {{
    background-color: {c['sfondo']};
}}
#video QWidget {{
    background-color: #000000;
}}

/* ---------- la Home ---------- */
/* Le misure vengono dalla specifica della app precedente, non dagli
   screenshot: il riquadro del giorno 14 sopra e sotto e 28 ai lati, la
   griglia a cinque colonne con 10 di vuoto, la card quadrata con il
   titolo 6 sotto. */
#testoGiorno {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: 4px;
}}
/* LA DATA E' VIOLA, COME LA FASCIA E COME LA RAIL

   Il viola e' uno solo in tutto il programma (`ACCENTO`), ed e' quello delle
   due barre laterali.  La data e' l'unica scritta della Home che non e' un
   titolo e non e' un testo da leggere: e' l'intestazione del riquadro, e senza
   un colore suo sparisce fra il titolo della sezione e il versetto, che sono
   entrambi neri.

   Il colore viene da `ACCENTO` e non e' scritto qui: due violeti diversi in
   due posti diversi sono l'errore che rende impossibile sapere quale dei due
   aggiustare quando uno dei due sembra stonato. */
#giorno {{
    font-size: 15px;
    font-weight: 600;
    color: {ACCENTO};
    background: transparent;
}}
/* Il versetto del giorno, sotto la data.

   Non e' un collegamento e non ha colore di collegamento: nella sezione
   Articolo il riferimento bibrico e' blu e si preme, e li' e' giusto perche'
   apre la Bibbia.  Qui non apre niente — e' una riga da leggere — quindi un
   colore che dicesse «cliccami» sarebbe una promessa falsa.  Il testo e'
   perche' quello intero, riferimento compreso, e il riferimento serve.

   Il corpo e' di 17 pixel, e non i 15 della data: e' la parte che si legge e
   la data e' solo l'intestazione.  Non e' molto piu' grande perche' questa
   riga si legge da vicino, sul monitor davanti, e non e' la «Scrittura
   dell'anno» del monitor secondario: li' il corpo e' di 70. */
#versettoGiorno {{
    font-size: 17px;
    /* Stessa ragione di `#scritturaAnnoLontano`: e' una citazione biblica, e
       il programma originale la scrive in `WTClearText`. */
    font-family: "ClearTextMedium";
    color: {c['testo']};
    background: transparent;
}}
/* Il tasto che scarica le Scritture del giorno.  Centrato nella riga, e non
   allineato a sinistra come gli altri pulsanti: qui non e' un'azione fra
   altre, e' l'unica cosa che il riquadro offre. */
#rigaTastoGiorno {{
    background: transparent;
}}
#tastoGiorno {{
    font-size: 13px;
    color: {c['testo']};
    background: transparent;
    border: 1px solid {c['bordo']};
    border-radius: 4px;
    padding: 5px 14px;
}}
#tastoGiorno:hover {{
    background-color: {c['hover']};
    border-color: {c['grigio']};
}}
#sottoGiorno {{
    font-size: 12px;
    color: {c['grigio']};
    background: transparent;
}}
/* L'ARGOMENTO PRINCIPALE DELLA HOME
   --------------------------------
   E' la stessa cosa di una card delle notizie — la foto, il titolo, la riga
   sotto — ma **larga**, perche' sta in cima alla Home e non in una striscia
   di card strette.  Per questo il titolo e' piu' grande di quello di una
   card: a dodici pixel, in un riquadro largo, il titolo sembra una riga di
   testo e non un titolo.

   I colori vengono dal tema come sempre: il titolo e' quello del testo, la
   riga sotto e' il grigio delle righe secondarie.  Il tasto e' quello dei
   tasti dell'app, e per questo la sua regola e' la stessa di quella del
   tasto del giorno: due nomi, una regola sola. */
#argomentoTitolo {{
    font-size: 16px;
    font-weight: 600;
    color: {c['testo']};
    background: transparent;
}}
#argomentoSotto {{
    font-size: 13px;
    color: {c['grigio']};
    background: transparent;
}}
/* Il verso del giorno sullo schermo secondario: piu' grande, ma non tanto da
   riempire lo schermo.  La ragione e' la distanza: quell Monitor e' a un
   braccio e mezzo, e 15 pixel a quella distanza non si leggono.

   Non e' "enorme": un riquadro grande mezzo schermo sembra un avviso, e il
   verso del giorno e' una cosa da leggere passeggiando, non un cartello.
   Quindi circa il doppio della Home, che a un metro e mezzo si legge bene. */
#testoGiornoLontano {{
    background-color: {c['pieno']};
    /* Il bordo non si vede: e' dello stesso nero del fondo, e metterlo uguale
       serve perche' `tema.sfondo()` mette un bordo a tutti i riquadri.  Un
       bordo grigio intorno al testo, su uno schermo nero, sembra una
       finestra dentro la finestra. */
    border: 1px solid {c['pieno']};
    border-radius: 6px;
}}
#giornoLontano {{
    font-size: 30px;
    font-weight: 600;
    color: {c['pienoTesto']};
    background: transparent;
}}
/* La «Scrittura dell'anno»: la riga che sta sulla pagina degli editori di
   «Esaminiamo le Scritture ogni giorno», letta dal pacchetto scaricato.

   IL CORPO DI 70 PIXEL E' MISURATO SU DUE NUMERI
   ---------------------------------------------
   Era 54, ed era «un po' piccolo, a distanza non si vede» — cioe' il corpo
   giusto non era.  Adesso e' 70, e la ragione per cui si puo' salire a 70
   senza che la frase vada su tre righe e' la larghezza del riquadro: a 1180
   pixel di riquadro il 70 occupa tre righe, a 1340 occupa due.

   Percio' il corpo grande e le due righe non sono in conflitto: e' la
   larghezza del riquadro che li rende compatibili, e il riquadro e' largo in
   percentuale dello schermo (`scrittura_dell_anno`), quindi su uno schermo
   stretto si stringe e la frase va a capo da sola invece di finire tagliata.

   Le due righe occupano il 21% dell'altezza di uno schermo 1080: il resto
   resta nero, che e' il modo in cui si legge una riga passeggiando.

   NELLA HOME NON E' LA META' E NON E' UN TERZO
   ------------------------------------------
   La coppia che c'era gia' nel foglio di stile, `#giorno` 15 e
   `#giornoLontano` 30, e' esattamente la meta'.  Qui non si puo' fare la
   meta' perche' la colonna della Home e' larga 448 pixel e a 35 la frase
   diventerebbe cinque righe: un muro di parole in una colonna stretta, che e'
   il contrario di quello che si vuole.  Quindi 24, che e' piu' del 21 di
   prima e resta una riga breve. */
#scritturaAnnoLontano {{
    background-color: {c['pieno']};
    /* Come `#testoGiornoLontano`: il bordo e' dello stesso nero del fondo, al
      trimenti si vede una cornice intorno al testo. */
    border: 1px solid {c['pieno']};
    border-radius: 6px;
}}
#scritturaAnnoLontano {{
    font-size: 70px;
    /* Il font delle Scritture del programma originale NON e' Georgia: e'
       `Wt-ClearText`, cioe' ClearText in grassetto.  Nel CSS di quell'app
       (`YearTextDisplay.bundle.js`) la famiglia si chiama `WTClearText` e i
       quattro file Wt-ClearText-*.woff sono i suoi.  Il nome interno che Qt
       registra per il solo grassetto e' pero' `ClearTextBold`, ed e' quello
       che va citato qui perche' `carica_font()` carica i .woff come famiglie
       separate. */
    font-family: "ClearTextBold";
    color: {c['pienoTesto']};
    background: transparent;
}}
/* Nella Home la stessa voce, ma alla taglia della Home: 21 pixel e' la scala
   di `#giorno` (30 sul monitor secondario, 15 nella Home) applicata alla
   frase, e non un corpo scelto per conto suo.  La frase e' la stessa, quindi
   anche qui le parole sono quelle e basta. */
#scritturaAnno {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: 6px;
}}
#scritturaAnno {{
    font-size: 24px;
    color: {c['testo']};
    background: transparent;
}}
#sottoGiornoLontano {{
    font-size: 22px;
    color: {c['pienoTesto']};
    background: transparent;
}}
/* ---------- i tasti che si illuminano col mouse ----------
   Sono i due tasti della finestra dello schermo secondario: compaiono quando il
   mouse passa sopra la finestra, e ciascuno si illumina quando il mouse passa
   sopra **lui**.

   Il colore e' quello del passaggio del mouse in questo tema, quindi non e' un
   colore inventato: se il tema cambia, l'illuminazione cambia con lui.

   Il bordo arrotondato serve perche' il fondo illuminato deve avere gli angoli
   tondi come il resto dei pulsanti del programma; senza, il rettangolo
   illuminato si vede come un timbro rettangolare su uno schermo nero. */
#bottoneLuce {{
    background-color: transparent;
    border-radius: 6px;
}}
#bottoneLuce:hover {{
    background-color: {c['hover']};
}}
#vuoto {{
    background-color: {c['img']};
    border-radius: 4px;
    padding: 14px;
    color: {c['grigio']};
    font-size: 13px;
}}
/* la miniatura della card: quadrata per costruzione, e il colore di
   quando l'immagine non c'e'.  Non e' un colore fisso: in scuro sarebbe
   un rettangolo bianco in mezzo alla pagina. */
#miniatura {{
    background-color: {c['img']};
    border: 1px solid {c['bordo']};
    border-radius: 4px;
}}
#targhetta {{
    font-size: 10px;
    color: {c['testo']};
    background-color: {c['pannello']};
    padding: 2px 5px;
    border-top-right-radius: 3px;
}}
#titoloCard {{
    font-size: 12px;
    font-weight: 600;
    margin-top: 6px;
    background: transparent;
}}
#sottoCard {{
    font-size: 12px;
    color: {c['grigio']};
    background: transparent;
}}

/* ---------- la sezione Novita' della Home ----------
   Nell'applicazione originale, sotto «What's New», le voci sono un elenco:
   miniatura a sinistra, titolo accanto, tre puntini in fondo a destra.
   Qui le regole sono tre, una per pezzo, e i colori vengono dal tema come
   sempre: il fondo del pannello, il bordo, il grigio del testo secondario. */
#rigaNovita {{
    background-color: {c['pannello']};
    border-bottom: 1px solid {c['bordo']};
}}
/* Le righe della sezione Adunanze, come nell'originale: piatte, senza riquadro
   ne' bordo, miniatura e testo direttamente sul fondo della pagina.  Solo al
   passaggio del puntatore si accende un velo leggero. */
#rigaPiatta {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
}}
#rigaPiatta:hover {{
    background-color: {c['pannello']};
}}
/* L'elenco a tendina dei passi di testo sotto la barra di ricerca. */
#popupRicerca {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: 8px;
}}
#popupRicerca #rigaPiatta:hover {{
    background-color: {c['sfondo']};
}}
/* La settimana in alto, in viola come nell'originale ("6-12 ottobre - Questa
   settimana"): l'accento del testo, che in scuro e' piu' chiaro per leggersi. */
#testoSettimana {{
    color: {c['accentoTesto']};
    font-size: 15px;
    font-weight: 700;
    background: transparent;
}}
#frecciaSettimana {{
    color: {c['accentoTesto']};
    font-size: 20px;
    font-weight: 700;
    background: transparent;
    border: none;
}}
#frecciaSettimana:disabled {{
    color: {c['grigio']};
}}
/* Il titolo della riga e' di 14 pixel e non 12 come quello delle card: qui
   il titolo e' la parte che si legge, e la miniatura sta accanto per
   aiutare a riconoscerlo, non al posto suo. */
#titoloNovita {{
    font-size: 14px;
    color: {c['testo']};
    background: transparent;
}}
/* La lingua a destra del titolo della sezione.  Grigio e non pieno perche'
   e' un'indicazione, non la parte che si va a leggere. */
#linguaSezione {{
    font-size: 13px;
    color: {c['grigio']};
    background: transparent;
    padding-bottom: 9px;
}}
/* L'area che scorre le righe.  Senza fondo proprio mostrerebbe il fondo
   della pagina fra una riga e l'altra, e le righe sembrerebbero separate a
   metà invece che da una linea sola. */
#scorriNovita {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: 4px;
}}

/* La durata sulla miniatura, nell'angolo in alto a sinistra.
   Sopra la miniatura e non dentro: dentro coprirebbe la figura, e la figura e'
   la cosa che fa riconoscere il video.  Il fondo e' nero con un quarto di
   opacita' perche' il video puo' essere chiaro o scuro e il testo deve
   leggersi su entrambi; il nero del tema (`pieno`) e' gia' nero in chiaro e
   in scuro, quindi non c'e' niente da scegliere. */
#durataMedia {{
    font-size: 10px;
    color: {c['pienoTesto']};
    background-color: rgba(0, 0, 0, 160);
    padding: 1px 4px;
    border-radius: 3px;
}}
/* I due bottoni dentro la miniatura della card: tre puntini e nuvoletta.
   Hanno uno sondo scuro come il badge della durata, perche' stanno **sopra
   un'immagine** che non si controlla: sopra una copertina chiara diventerebbero
   bianchi su bianco, e i tre puntini sparirebbero proprio quando la si guarda
   meglio.  Il bordo arrotondato li fa leggere come due bottoni e non come due
   macchie nere sulla copertina. */
#bottoneCard {{
    background-color: rgba(0, 0, 0, 110);
    border: none;
    border-radius: 10px;
}}
#bottoneCard:hover {{
    background-color: rgba(0, 0, 0, 170);
}}

/* ---------- la riga degli scaricamenti ----------
   Sta in fondo alla finestra, dentro il contenuto, e non sulla fascia viola:
   la fascia e' il bordo, e un bordo non e' il posto dove si guarda mentre si
   aspetta.  I tre colori vengono dal tema come sempre. */
#scaricamento {{
    background-color: {c['pannello']};
    border-top: 1px solid {c['bordo']};
}}
#scaricaNome {{
    font-size: 12px;
    font-weight: 600;
    color: {c['testo']};
    background: transparent;
}}
/* Il conto e il tempo che manca: grigio, perche' e' l'informazione che
   accompanya il nome e non la cosa che si cerca per prima. */
#scaricaConto {{
    font-size: 12px;
    color: {c['grigio']};
    background: transparent;
}}
/* La barra: alta sei pixel e senza bordo.  Alta twenty sembra un dialogo
   che si e' aperto, e sei pixel si leggono senza coprire niente.

   La parte piena e' **il viola della fascia e della rail** (`ACCENTO`), non il
   viola chiaro: e' la stessa barra che dice quanto manca, e due barre dello
   stesso colore si leggono come due cose diverse. */
#scaricaBarra {{
    background-color: {c['img']};
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
}}
#scaricaBarra::chunk {{
    background-color: #c084fc;
    border: none;
    border-radius: 3px;
}}

/* La barra di scaricamento **dentro una card larga**.
 *
 * È una regola a parte da quella sopra, e non una modifica di quella: la
 * card della Home è quasi quadrata e la sua barra sta dentro una
 * miniatura di 124 pixel, dove 6 pixel si vedono e non coprono niente.
 * La card della Biblioteca è larga 417 e alta 100 — dentro una cella
 * così bassa 6 pixel sono un sesto della copertina, e la barra si
 * legge come un bordo colorato invece che come un progresso.
 *
 * Qui sono 3: abbastanza per vederla avanzare, abbastanza sottile da
 * restare sul bordo. Le due regole hanno lo stesso colore e la stessa
 * aria tonda, perché la barra è la stessa cosa — cambia solo quanto è
 * alta rispetto alla scheda in cui sta. */
#scaricaBarraCard {{
    background-color: {c['img']};
    border: none;
    border-radius: 2px;
    max-height: 5px;
    min-height: 5px;
}}
#scaricaBarraCard::chunk {{
    background-color: #c084fc;
    border: none;
    border-radius: 2px;
}}

/* ---------- le impostazioni ---------- */
/* La colonna larga 620 e le schede con 14 di vuoto fra una e l'altra. */
#scheda {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: {RAGGIO}px;
}}
/* il titolo e' gia' maiuscolo nel testo, perche' in Qt il foglio di
   stile non ha text-transform e metterlo qui in maiuscolo renderebbe
   "ASCOLTO E VIDEO" invece di "Ascolto e video". */
#titoloScheda {{
    font-size: 12px;
    font-weight: 600;
    color: {c['grigio']};
    letter-spacing: 0.4px;
    background: transparent;
}}
#riga {{
    background: transparent;
}}
#etichetta {{
    font-size: 13px;
    background: transparent;
}}
/* il valore a destra: sono numeri e devono stare in colonna, quindi
   figurato. */
#valore {{
    font-family: monospace;
    font-size: 12px;
    color: {c['grigio']};
    background: transparent;
}}
#nota {{
    font-size: 12px;
    color: {c['grigio']};
    background: transparent;
    padding: 2px 0px;
}}
/* ---------- il campo di ricerca ---------- */
/* Sta sopra l'elenco, non dentro.  Si cerca in tutta la pubblicazione e
   dentro un capitolo non avrebbe senso. */
#campoCerca {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: {RAGGIO}px;
    padding: 6px 10px;
    font-size: 13px;
    color: {c['testo']};
    min-height: 18px;
}}
#campoCerca:focus {{
    border-color: {ACCENTO};
}}
#campoCerca::placeholder {{
    color: {c['grigio']};
}}

QComboBox {{
    background-color: {c['sfondo']};
    border: 1px solid {c['bordo']};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 13px;
    color: {c['testo']};
    min-width: 130px;
}}
QComboBox:hover {{
    border-color: {ACCENTO};
}}
QComboBox QAbstractItemView {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    selection-background-color: {c['lavato']};
    selection-color: {c['testo']};
    color: {c['testo']};
}}

/* ---------- i menu' a tendina, tutti ----------
   Un QMenu e' una **finestra a parte**, e una finestra a parte su Linux non
   segue il tema da sola: viene con i colori del tema del sistema.  Il
   risultato era un menu' trasparente o chiaro che si apriva sopra una pagina
   scura, con il testo illeggibile e la miniatura della card che si vedeva
   *attraverso* le voci.

   La regola e' per `QMenu` generico e non per un menu' solo, perche' i
   menu' dell'app sono quattro — quello delle risoluzioni, quello dei tre
   puntini delle card, quello delle righe degli scaricati e quello del
   lettore — e nessuno dei quattro poteva restare con i colori del sistema.
   `#menuLingua` qui sotto aggiunge i pezzi che sono solo suoi: il
   separatore e il campo di ricerca.

   Il padding a destra (22 pixel) e' il posto dove Qt mette il segno di
   spunta: senza quello, le voci con il segno hanno il testo sotto al segno e
   non si allineano con le altre. */
QMenu {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px 6px 12px;
    border-radius: 4px;
    color: {c['testo']};
}}
QMenu::item:selected {{
    background-color: {c['lavato']};
    color: {c['testo']};
}}
QMenu::item:disabled {{
    color: {c['grigio']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['bordo']};
    margin: 4px 6px;
}}

/* ---------- il menu della lingua ---------- */
/* Il menu e' una finestra a parte, e una finestra a parte segue il tema
   come tutto il resto.  Senza queste regole un QMenu su Linux viene con i
   colori del tema del sistema, che in scuro restano chiari: un menu chiaro
   che si apre da una fascia viola sopra una pagina scura.

   I colori vengono tutti da `tema`, come gli altri: se il viola dell'app
   cambia, la spunta della lingua scelta cambia con lui. */
#menuLingua {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    padding: 4px;
}}
#menuLingua::item {{
    padding: 5px 10px;
    border-radius: 4px;
    color: {c['testo']};
}}
#menuLingua::item:selected {{
    background-color: {c['lavato']};
    color: {c['testo']};
}}
#menuLingua::item:disabled {{
    color: {c['grigio']};
}}
#menuLingua::separator {{
    height: 1px;
    background: {c['bordo']};
    margin: 4px 6px;
}}
/* Il campo di ricerca dentro il menu.  Le sue regole sono le stesse di
   `#campoCerca`, che sta sopra gli elenchi delle pubblicazioni: due posti
   dove si scrive, quindi due gruppi di regole, ma gli stessi colori e le
   stesse misure. */
#campoLingua {{
    background-color: {c['sfondo']};
    border: 1px solid {c['bordo']};
    border-radius: {RAGGIO}px;
    padding: 5px 8px;
    font-size: 13px;
    color: {c['testo']};
    min-width: 220px;
}}
#campoLingua:focus {{
    border-color: {ACCENTO};
}}
#campoLingua::placeholder {{
    color: {c['grigio']};
}}

/* ---------- i media ---------- */
/* Le righe dei media e le schede Audio/Video.  La scheda scelta ha il
   fondo acceso: e' l'unico segnale che serve, e non serve un colore
   diverso perche' non si vede quale sia. */
#rigaMedia {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: {RAGGIO}px;
}}
/* ---------- i capitoli di una pubblicazione ----------
   Sono righe che si premono, e vengono disegnate come pulsanti piatti senza
   niente: testo del colore del fondo su fondo scuro, senza bordo ne' forma.
   Il risultato e' una schermata che sembrava scritta a mano — e che sembrava
   un campo nel quale si puo' scrivere, perche' un testo piatto su uno sfondo
   piatto si legge come un campo di modifica.

   Qui prendono l'aspetto delle altre righe dell'app: fondo del pannello,
   bordo arrotondato, e il passaggio del mouse che le accende.  Non un colore
   nuovo: le stesse tre chiavi di `#rigaMedia`, perche' una riga che si puo'
   premere e' la stessa cosa in tutta l'applicazione e non due. */
#capitoloPub {{
    background-color: {c['pannello']};
    border: 1px solid {c['bordo']};
    border-radius: {RAGGIO}px;
    color: {c['testo']};
    font-size: 14px;
    padding: 9px 12px;
    text-align: left;
}}
#capitoloPub:hover {{
    background-color: {c['hover']};
}}
/* ---------- il lettore ---------- */
/* Il video e' nero e il nero non e' un colore del tema: sotto il video ci
   deve essere qualcosa su cui i glifi bianchi si vedano, e i colori li prende
   dal tema come tutto il resto.  Il lettore non porta colori propri: un
   lettore con i propri colori e' un programma dentro un programma. */
#lettore {{
    background-color: {c['lavato']};
    border: 1px solid {c['bordo']};
    border-radius: {RAGGIO}px;
    /* Niente `overflow`.  Non e' una proprieta' che Qt conosca, quindi
       ogni volta che la finestra si costruisce esce:

           [Qt AVVISO] Unknown property overflow

       e non e' un avviso una volta sola: la finestra si ricostruisce a ogni
       avvio e a ogni "Aggiorna", quindi l'avviso riempie il terminale fino a
       coprire il messaggio che serve davvero.  Il bordo arrotondato si
       ottiene senza `overflow` perche' il video e' un figlio dentro il
       riquadro e non esce dai bordi. */
}}
#videoLettore {{
    background-color: #000000;
}}
/* LA COPERTINA, AL POSTO DEL VIDEO QUANDO C'E' UN AUDIO
   --------------------------------------------------------
   Stessa regola del video: fondo scuro, cosi' la copertina non ha un bordo
   che la divide dal resto, e il pezzo si legge come un'immagine e non come
   un riquadro con dentro un'altra cosa. */
#copertinaLettore {{
    background-color: #000000;
}}
#comandiLettore {{
    background-color: {c['lavato']};
    border-top: 1px solid {c['bordo']};
}}
/* I CURSORI, VIOLA COME LE LINGUETTE E COME LA FASCIA
   ----------------------------------------------------
   Il disegno di default di Qt e' azzurro, e in un programma che ha una sola
   famiglia di colori un cursore azzurro accanto a una fascia viola sembra
   un pulsante di un'altra applicazione.

   Il colore e' lo stesso viola dei pulsanti della fascia, e arriva da
   `tema`: il cursore non puo' avere un colore suo, perche' un giorno il tema
   cambia e il cursore resterebbe indietro.

   La parte colorata e' il `groove` e il `handle`: il groove e' la corsia su
   cui scorre il cursore, e deve sembrare parte della finestra. */
#barraLettore, #volumeLettore, #lettore, #barraTesto {{
    background: transparent;
}}
/* LA PARTE PIENA E' VIOLA, LA CORSA E' SCURA
   ------------------------------------------
   Era il contrario, e si vedeva: la parte **piena** era chiara e la corsia
   era viola, quindi la barra sembrava un tratto di cancellazione e non un
   cursore.  Ora e' come le linguette e come la fascia: quello che e' passato
   e' viola, quello che resta e' scuro e non si vede.

   `sub-page` e' la parte piena e `groove` e' la corsia: i due nomi di Qt
   sembrano il contrario di quello che dicono, ed e' per questo che il
   commento e' qui. */
#barraLettore::groove:horizontal, #volumeLettore::groove:horizontal,
#barraTesto::groove:horizontal {{
    background: #1c1725;
    height: 4px;
    border-radius: 2px;
}}
/* LA PARTE PIENA E' LO STESSO VIOLO DELLA FASCIA E DELLA RAIL
   ------------------------------------------------------------
   Era `#d2c6e0`, un viola chiaro che non e' il viola dell'app.  La fascia e
   la rail sono `ACCENTO`, e il cursore sta nella stessa finestra: due viola
   diversi nella stessa finestra si vedono, e sembra che il cursore sia di un
  'altra applicazione.

   Quindi la parte piena e' `ACCENTO`, come la fascia e la rail.  Il colore
   viene da li' e non e' scritto qui: se il viola dell'app cambiasse, il
   cursore deve cambiarne con lui senza che nessuno se ne ricordi. */
#barraLettore::sub-page:horizontal, #volumeLettore::sub-page:horizontal,
#barraTesto::sub-page:horizontal {{
    background: {ACCENTO};
    border-radius: 2px;
}}
#barraLettore::handle:horizontal, #volumeLettore::handle:horizontal,
#barraTesto::handle:horizontal {{
    background: #ffffff;
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}
#rigaMedia:hover {{
    background-color: {c['hover']};
}}
#titoloRiga {{
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}
/* La riga che spiega perche' una scheda di Novita' e' in elenco.  Piu'
   piccola del titolo e nel colore delle note: e' un'informazione, non un
   richiamo.  Il colore la fa leggere come nota e non come parte del nome
   della pubblicazione.

   Il colore e' `grigio`, quello di `#nota`, e non un colore nuovo: due
   grigi che si distinguono di poco servono solo a far sembrare la scheda
   disallineata. */
#spiegazione {{
    font-size: 11px;
    color: {c['grigio']};
    background: transparent;
}}
#scheda {{
    background-color: {c['lavato']};
    border: 1px solid {c['lavato']};
    border-radius: {RAGGIO}px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
}}

/* ---------- il pannello di lato ---------- */
/* Il pannello delle citazioni bibliche: si stacca dal contenuto con un
   bordo, non con un colore diverso. */
#laterale {{
    background-color: {c['pannello']};
    border-left: 1px solid {c['bordo']};
}}

/* ---------- la sezione Biblioteca: le quattro tab ----------
   PERCHE' UN NOME NUOVO E NON `#scheda`
   --------------------------------------
   `#scheda` esiste gia' e la usa la sezione Impostazioni, dove e' una
   **capsula** colorata (sfondo `lavato`, angoli tondi).  La tab della
   Biblioteca e' una cosa diversa: sfondo trasparente e una **barra** viola
   sotto, 3 pixel.

   Se avessimo cambiato `#scheda`, le Impostazioni avreb perso la capsula e
   la Biblioteca avrebbe preso il nome giusto per caso.  Percio' qui il nome
   e' `#tab` ed e' solo della Biblioteca: due pezzi che si somigliano hanno
   due nomi.

   La barra e' `ACCENTO` e non `accentoTesto`: la barra e' un segnale, come la
   fascia e la rail, e non segue il tema.  Il TESTO invece cambia, perche'
   serve che si legga: vedi la chiave `accentoTesto` nei due temi. */
#tab {{
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    color: {c['testo']};
    font-size: 15px;
    padding: 6px 10px 9px 10px;
    letter-spacing: 0.6px;
}}
#tab:hover {{
    color: {c['accentoTesto']};
}}
#tabAttiva {{
    background: transparent;
    border: none;
    border-bottom: 3px solid {ACCENTO};
    color: {c['accentoTesto']};
    font-size: 15px;
    font-weight: 600;
    padding: 6px 10px 9px 10px;
    letter-spacing: 0.6px;
}}
/* Il fondo sotto la striscia delle tab.  `griglia`, non `sfondo`: e' il fondo
   fra le celle, e in chiaro non e' bianco. */
#strisciaTab {{
    background-color: {c['griglia']};
    border-bottom: 1px solid {c['bordo']};
}}
/* ---------- la sezione Biblioteca: il fondo e le celle ---------- */
#paginaGriglia {{
    background-color: {c['griglia']};
    border: none;
}}
/* LA CELLA
   ---------
   417 per 100.  Il vuoto di 4 pixel fra una cella e l'altra non e' un
   `margin`: e' lo sfondo della pagina che si vede fra due celle, e con un
   margine il bordo della cella si sposterebbe di 4 pixel senza che nessuno
   l'abbia chiesto. */
#cella {{
    background-color: {c['pannello']};
    border: none;
    border-radius: 0px;
}}
#cella:hover {{
    background-color: {c['hover']};
}}
/* Il titolo dentro la cella: 20 pixel, come misurato, e non i 13 del corpo
   del testo.  Il titolo e' la cosa che si legge e l'icona sta accanto per
   aiutare a riconoscerlo. */
#titoloCella {{
    font-size: 15px;
    color: {c['testo']};
    background: transparent;
}}
#sottoCella {{
    font-size: 12px;
    color: {c['grigio']};
    background: transparent;
}}
/* LA Sfumata SOPRA LA FOTO DELLE TILE VIDEO
   ------------------------------------------
   Il gradiente nero da sinistra a meta' e' quello che rende leggibile il
   titolo bianco sopra una foto che puo' essere chiara o scura.

   E' `qlineargradient` e non un'immagine perche' in Qt il gradiente e' una
   riga di foglio di stile: metterlo in Python significerebbe un pixmap per
   ogni tema, e un pixmap che non cambia se cambia il tema e' un pixnap
   sbagliato.

   Il nero e' `pieno` anche in chiaro, perche' una foto si scurisce in tutti e
   due i temi: e' la foto che va scurita, non il tema. */
#sfumaturaVideo {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(0, 0, 0, 235),
        stop:0.35 rgba(0, 0, 0, 150),
        stop:0.55 rgba(0, 0, 0, 40),
        stop:1 rgba(0, 0, 0, 0));
    border: none;
}}
/* Il titolo bianco sopra la sfumatura.  Sempre bianco, anche in tema chiaro:
   sta sopra una foto, e il tema non arriva fin li'. */
#titoloVideo {{
    font-size: 15px;
    color: #ffffff;
    background: transparent;
}}
/* Lo stato vuoto della sezione. */
#vuotoGriglia {{
    background-color: {c['griglia']};
    border: none;
    color: {c['grigio']};
    font-size: 13px;
}}
"""


# ---------------------------------------------------------------------------
# IL TEMA SCELTO
# ---------------------------------------------------------------------------
#
# Il tema sta in un file.  E' una cosa sola, e non si cancella a vicenda a
# nessun'altra impostazione: e' la regola che la tua documentazione chiama
# "un file solo, e che non si cancellano a vicenda".

# ---------------------------------------------------------------------------
# IL FILE DELLE IMPOSTAZIONI
# ---------------------------------------------------------------------------
#
# PERCHE' STA QUI E NON DUE VOLTE
# --------------------------------
# `impostazioni.json` contiene piu' cose, e ogni cosa deve poter cambiare
# senza toccare le altre.  Il tema e' la prima, e la lingua (che sta in
# `Utility/Lingua.py`) e' un'altra che verrà.
#
# Il modo per riuscirci e' uno solo: ogni scrittura LEGGE il file, cambia UN
# campo e lo riscrive.  Non un file per cosa, e non un `dati["chiaro"] = ...`
# scritto da due posti diversi: due scritture che si sovrascrivono a vicenda
# sono un difetto che si vede una volta su trecento, quando si cambia tema
# e la lingua sparisce.
#
# Quindi qui ci sono le due operazioni, e chi salva un'impostazione chiama
# `salva_impostazione`.  Il nome dice cosa fa: cambia un campo e lascia gli
# altri come sono.
#
# PERCHE' IL RITORNO E' UNDICITARIO E NON UN ERRORE
# ----------------------------------------------
# Un'impostazione illeggibile non e' un programma rotto: e' un tema di
# default.  Se il file non c'e', non e' JSON, o non si puo' scrivere, si
# dice con un valore di ripiego e si va avanti.  Un'eccezione qui
# impedirebbe di aprire la finestra per colpa di un file di testo.
FILE_IMPOSTAZIONI = "impostazioni.json"


def percorso_impostazioni():
    """Il file delle impostazioni, o None se la cartella dati non c'e'."""
    try:
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        return get_documents_directory() / "userData" / FILE_IMPOSTAZIONI
    except Exception:  # noqa: BLE001 - i dati non ci sono: si resta senza salvataggio
        return None


#: Le impostazioni gia' lette, o ``None`` se non sono state lette ancora.
#:
#: Il file e' piccolo ma veniva aperto, letto e parsato **a ogni chiamata**, e la
#: chiamata piu' frequente non e' un impostatore: e' `Lingua.corrente_id()`, che
#: la chiama per sapere che lingua si sta usando.  Quella finiscono dentro la
#: costruzione di ogni card, quindi 300 volte per griglia: 1500 `stat` e 300
#: letture di un file JSON per rivedere la stessa schermata.
_cache_impostazioni: dict | None = None


def impostazioni() -> dict:
    """Tutte le impostazioni salvate.  {} se non ce ne sono.

    Non solleva niente: un file illeggibile vale come un file assente, e in
    entrambi i casi l'app parte con i valori di default.

    IL DIZIONARIO E' CONDIVISO, NON UNA COPIA
    -----------------------------------------
    Chi lo riceve non lo puo' modificare senza passare da
    `salva_impostazione`: oggi l'unico che lo legge e' `Lingua`, e lo legge con
    `.get()`, quindi non c'e' nessuno che lo cambi sotto.  Il vantaggio e' che
    `salva_impostazione` riceve lo stesso oggetto che ha letto, ci scrive dentro
    e lo riscrive su disco: la copia in memoria e il file restano d'accordo senza
    nessun codice che li metta in fila.

    Se un domani un altro pezzo lo modifica, la riga da cambiare e' una:
    `salva_impostazione` deve aggiornare la cache, e va detto in questa riga.
    """
    global _cache_impostazioni
    if _cache_impostazioni is not None:
        return _cache_impostazioni
    percorso = percorso_impostazioni()
    if percorso is None or not percorso.is_file():
        _cache_impostazioni = {}
        return _cache_impostazioni
    try:
        import json
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dati = {}
    _cache_impostazioni = dati if isinstance(dati, dict) else {}
    return _cache_impostazioni


def salva_impostazione(chiave: str, valore) -> None:
    """Cambia UN campo del file delle impostazioni e lo riscrive.

    Gli altri campi restano come sono: e' il punto di questa funzione.
    """
    percorso = percorso_impostazioni()
    if percorso is None:
        return
    try:
        import json
        percorso.parent.mkdir(parents=True, exist_ok=True)
        # `impostazioni()` restituisce il dizionario in cache, quindi la scrittura
        # aggiorna anche la copia in memoria e i due non possono divergere.
        dati = impostazioni()
        dati[chiave] = valore
        percorso.write_text(json.dumps(dati, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError) as errore:
        print(f"Non riesco a salvare «{chiave}» ⚠️  {errore}")


# ---------------------------------------------------------------------------
# LA DIMENSIONE DEL TESTO
# ---------------------------------------------------------------------------
#
# PERCHE' STA QUI E NON SOLO NELLA FINESTRA
# -----------------------------------------
# La finestra conosce la misura scelta, ma non sono le sole a volerla: anche
# il capitolo della Bibbia, il pannello dei versetti e la notizia hanno un
# testo da ingrandire, e nascono lontani dalla finestra.  Se la misura
# vivesse solo in `SidebarView`, un capitolo aperto dopo il cambio partirebbe
# dalla misura di prima, e l'utente avrebbe l'impressione che il comando
# funzioni a meta'.
#
# Qui c'e' il valore **unico**: la finestra lo cambia, tutti lo leggono, e il
# file delle impostazioni lo conserva per la prossima apertura.
#
# LA PERCENTUALE, E PERCHE' NON I PIXEL
# -------------------------------------
# 100 e' la misura normale.  Il minimo non e' zero: a zero il testo sparisce
# e non c'e' piu' niente da leggere, quindi non sarebbe un comando ma un
# modo per perdere l'articolo.  Il massimo e' 200%, gia' un ingrandimento
# notevole senza righe troppo lunghe da leggere.
DIMENSIONE_TESTO_MIN = 50
DIMENSIONE_TESTO_MAX = 300
DIMENSIONE_TESTO_DEFAULT = 100
DIMENSIONE_TESTO_CHIAVE = "dimensione_testo"

#: La misura di adesso, in percentuale.  Cambia solo con
#: `imposta_dimensione_testo`.
_dimensione_testo: int = DIMENSIONE_TESTO_DEFAULT


def _limita_dimensione_testo(valore) -> int:
    """La percentuale dentro i limiti, qualunque cosa ci arrivi."""
    try:
        numero = int(valore)
    except (TypeError, ValueError):
        numero = DIMENSIONE_TESTO_DEFAULT
    return max(DIMENSIONE_TESTO_MIN, min(DIMENSIONE_TESTO_MAX, numero))


def dimensione_testo() -> int:
    """La percentuale del testo scelta dall'utente, in questa sessione."""
    return _dimensione_testo


def imposta_dimensione_testo(valore) -> int:
    """Cambia la misura del testo per tutta l'app, e restituisce il valore.

    Non scrive niente su disco: la scrittura e' un'altra cosa, e la fa
    `salva_impostazione`.  Qui si tiene solo il valore in memoria, cosi'
    chi lo cambia non deve per forza salvare.
    """
    global _dimensione_testo
    _dimensione_testo = _limita_dimensione_testo(valore)
    return _dimensione_testo


def carica_dimensione_testo() -> int:
    """La misura salvata nel file, e mette anche quella in memoria.

    Si chiama all'avvio dell'app: se il file c'e' e vale 150%, l'app parte
    con quella misura, e non con quella dell'ultima volta che si e' aperta
    una schermata.
    """
    global _dimensione_testo
    _dimensione_testo = _limita_dimensione_testo(
        impostazioni().get(DIMENSIONE_TESTO_CHIAVE, DIMENSIONE_TESTO_DEFAULT))
    return _dimensione_testo


#: L'impostazione «video a tutto schermo».
#:
#: Il valore e' il **nome** dello schermo, cosi' com'e' come il sistema lo
#: chiama — non un indice e non una posizione.  Un indice non significa niente
#: quando si stacca un monitor e la finestra andrebbe a schermo intero su
#: quello sbagliato; il nome invece o c'e' o non c'e', e si puo' controllare.
#:
#: Il valore speciale `NESSUNO` vuol dire **disattivato**: nessun monitor
#: esterno, il video resta dentro l'applicazione.
#:
#: PRIMA SI CHIAMAVA «SEGUI LA FINESTRA» E VUOL DIRE IL CONTRARIO
#: -------------------------------------------------------
#: Il nome vecchio diceva «dove sta la finestra», che si poteva leggere in due
#: modi: «il video va dove sta la finestra» — cioe' sul primo schermo, dentro
#: l'app — oppure «il video segue la finestra in giro».
#:
#: Il secondo significato e' quello che aveva il codice: se non si sceglieva
#: nessuno schermo, il programma sceglieva da solo «il primo che non e' quello
#: dove sta la finestra» e ci apriva la finestra del video.  Con due monitor
#: accadeva sempre: l'app si trovava il video davanti **sul primo schermo**,
#: che e' la cosa che non deve succedere.
#:
#: Adesso la parola e' una sola e non si puo' leggere in due modi:
#: **disattivato**.  Nessun monitor esterno, nessuna finestra secondaria, e il
#: video dentro l'app come prima di qualsiasi schermo esterno.
VIDEO_SCHERMO = "video_schermo"
NESSUNO = "nessuno"

#: Il nome che c'era prima.  Resta perche' nelle impostazioni di qualcuno puo'
#: essere gia' salvato quel valore, e senza questo verrebbe letto come il nome
#: di uno schermo — che non esiste — e la finestra del video non si aprirebbe
#: piu'.  Con questo la vecchia scelta vale come «disattivato», che e' quello
#: che voleva dire davvero.
SEGUI = NESSUNO


def video_schermo() -> str:
    """Il nome dello schermo scelto per il video, o `SEGUI`.

    Il default non e' una costante con dentro un nome di schermo: il nome
    degli schermi lo sa solo Qt, a runtime, e va letto lì.  Qui si puo' solo
    dire «non ho scelto niente», che e' un fatto e non un indovinare.
    """
    salvato = str(impostazioni().get(VIDEO_SCHERMO) or "")
    # Il valore di prima era `SEGUI = "seggi"` e voleva dire «disattivato».
    # Chi lo ha gia' salvato ce l'ha ancora nelle impostazioni, e senza questa
    # traduzione i confronti con `NESSUNO` non tornerebbero: il pulsante della
    # duplicazione si accenderebbe con lo schermo esterno spento, e la riga
    # direbbe che c'e' uno schermo scelto quando non ce n'e' nessuno.
    if not salvato or salvato == "seggi":
        return NESSUNO
    return salvato


def salva_video_schermo(nome: str) -> None:
    """Scrive lo schermo scelto per il video."""
    salva_impostazione(VIDEO_SCHERMO, nome or SEGUI)


#: Gli schermi **in piu'** su cui si duplica il video, oltre a quello scelto.
#:
#: E' una lista di nomi, non un solo nome come `VIDEO_SCHERMO`: la domanda e'
#: diversa.  `VIDEO_SCHERMO` e' «dove sta il video», che e' una cosa sola e
#: obbligatoria.  Questo e' «dove ne sta un'altra copia», che e' una cosa che
#: puo' essere zero, uno, tre o quindici.
#:
#: PERCHE' UNA LISTA E NON UNA MASCHERA DI TRUE E FALSE
#: ---------------------------------------------------
#: Sembra la stessa cosa, e non lo e'.  Una lista di nomi si legge da sola:
#: «HDMI-1, HDMI-2».  Una maschera si legge solo se sai la sua posizione,
#: e le posizioni cambiano: staccando il secondo monitor, «DP-1» smette di
#: essere il secondo e diventa il primo, e la maschera dice ancora «sì» per
#: un indice che ora significa un altro schermo.  Vedi `Schermi.elenco`, che
#: spiega perche' gia' il nome dello schermo si salva invece dell'indice.
VIDEO_SCHERMI_DUPLICA = "video_schermi_duplica"


def video_schermi_duplica() -> list[str]:
    """I nomi degli schermi in piu' su cui si duplica il video.

    Quelli che non sono piu' collegati **non vengono tolti**: sono ancora
    nella lista, semplicemente nessuno li cerca.  Il posto dove accorgersi
    che uno schermo e' sparito e' la tendina delle impostazioni, che elenca
    solo quelli che ci sono.  Come per `video_schermo`, e per lo stesso
    motivo: uno schermo staccato e uno rinominato sono la stessa cosa da
    chi sta usando il programma, e non vale la pena cancellare la scelta
    dell'utente perche' un cavo e' sceso.
    """
    grezzo = str(impostazioni().get(VIDEO_SCHERMI_DUPLICA) or "")
    return [n for n in (pezzo.strip() for pezzo in grezzo.split(",")) if n]


def salva_video_schermi_duplica(nomi) -> None:
    """Scrive gli schermi in piu' su cui si duplica il video."""
    puliti = [str(n).strip() for n in (nomi or []) if str(n).strip()]
    salva_impostazione(VIDEO_SCHERMI_DUPLICA, ",".join(puliti))


#: La risoluzione con cui si guarda il video.
#:
#: `AUTOMATICA` vuol dire «decidi tu»: la risoluzione si sceglie misurando la
#: casella che la mostra, ed e' il comportamento di sempre.
#:
#: Il resto e' l'etichetta che il server ha dato a un file di quel video —
#: "240p", "480p", "720p", e "1080p" solo per i video che ce l'hanno.  Non si
#: tiene qui un elenco: le risoluzioni cambiano da video a video, e una
#: risoluzione salvata che quel video non ha viene semplicemente ignorata.
RISOLUZIONE_VIDEO = "risoluzione_video"
AUTOMATICA = "auto"

#: Le quattro scelte delle impostazioni, che non sono risoluzioni ma **posizioni
#: nella lista** di quelle che quel video ha: la piu' piccola, una in mezzo, la
#: piu' grande.  Servono perche' "bassa" e "alta" hanno un senso anche quando il
#: video non ha il 720p, mentre "720p" non avrebbe.
PER_TAGLIO = ("bassa", "media", "alta")


def risoluzione_video() -> str:
    """La risoluzione scelta per il video, o `AUTOMATICA`.

    Il default e' `AUTOMATICA` e non una risoluzione: senza che l'utente scelga
    niente il video si sceglie da solo misurando la casella, e quella scelta
    cambia a seconda di dove lo si guarda.
    """
    return str(impostazioni().get(RISOLUZIONE_VIDEO) or AUTOMATICA)


def salva_risoluzione_video(scelta: str) -> None:
    """Scrive la risoluzione scelta per il video."""
    salva_impostazione(RISOLUZIONE_VIDEO, scelta or AUTOMATICA)


def tema_salvato() -> bool:
    """Il tema salvato.  Se non c'e' il file, chiaro."""
    return bool(impostazioni().get("chiaro", True))


def salva_tema(chiaro: bool) -> None:
    """Scrive il tema.  Non sovrascrive le altre impostazioni."""
    salva_impostazione("chiaro", chiaro)


# ---------------------------------------------------------------------------
# IL TEMA CHE STA A SCHERMO ADESSO
# ---------------------------------------------------------------------------
#
# PERCHE' SERVE E NON BASTA `tema_salvato`
# --------------------------------------
# `tema_salvato()` legge il **file**, e il file non cambia quando l'utente
# cambia tema: cambia quando l'app viene chiusa.  Quindi dentro la finestra,
# subito dopo aver premuto il tema scuro, il file dice ancora «chiaro».
#
# Serve per i pezzi che disegnano qualcosa **senza passare dal foglio di
# stile** — un pixmap, un pennello, il colore di un'icona.  Il foglio di
# stile risolve tutto il resto da solo, e non ha bisogno di sapere niente:
# chi lo interroga e' lui.
#
# Il valore sta qui e non in `SidebarView` perche' cosi' e' in un posto solo:
# se stesse nella finestra, ogni widget che lo vuole dovrebbe conoscere la
# finestra, e un widget che conosce la finestra non si puo' piu' usare da
# solo.

_attivo = {"chiaro": True}


def tema_attivo() -> bool:
    """Il tema che sta a schermo adesso, non quello salvato."""
    return _attivo["chiaro"]


def imposta_tema_attivo(chiaro: bool) -> None:
    """Dice quale dei due temi e' a schermo.

    Va chiamata **una** volta ogni volta che il tema cambia, dalla finestra
    che lo cambia.  Non la chiama nessun altro, e non prova a indovinare il
    tema da un colore: un tema indovinato e' un tema sbagliato una volta su
    due, e sbaglia solo in scuro, che e' dove si vede.
    """
    _attivo["chiaro"] = bool(chiaro)