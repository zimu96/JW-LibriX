"""Quale schermo usare per mostrare video e immagini grandi.

PERCHE' UN MODULO PER UN COSI' PICCOLA COSA
-------------------------------------------
La scelta dello schermo serve a due finestre diverse — quella dei video
(`LettoreSchermo`, quando si preme il tasto di tutto schermo) e quella dello
schermo secondario (`SchermoEsterno`, che c'e' tutto il tempo) — e prima di
questo modulo la logica stava dentro `LettoreSchermo`, dove le immagini non
potevano arrivare senza copiarla.  Due copie di «scegli lo schermo» sono due
posti che un giorno dicono cose diverse, e il difetto che c'era prima
(scegliere sempre il primario) e' nato proprio da una logica che guardava la
cosa sbagliata in un posto solo.

Qui c'e' la logica, una volta sola.  Chi deve scegliere chiama
`per_il_video` e riceve lo schermo gia' giusto.

IL DIFETTO CHE C'ERA, E DA DOVE VIENE
------------------------------------
`LettoreSchermo` prometteva gia' nel suo docstring «sul monitor dove sta la
finestra», ma il codice faceva:

    finestra = QGuiApplication.primaryScreen()
    for schermo in QGuiApplication.screens():
        if finestra.geometry().contains(schermo.geometry().center()):
            finestra = schermo

Il centro dello schermo principale e' **sempre** dentro lo schermo
principale, quindi il ciclo sceglieva subito il primo e non cambiava mai
niente: il tutto schermo andava sempre sul primario, qualunque fosse la
posizione della finestra da cui l'utente era partito.

Misurato su una macchina con due schermi: l'applicazione a x=0 (monitor di
sinistra) e la finestra a tutto schermo a x=1920 (il primario, a destra).
Esattamente il difetto.

Adesso il punto da cui si parte e' il **rettangolo della finestra** da cui
l'utente ha aperto il video: e' l'unico rettangolo che dice dove si trova
l'utente.

PERCHE' SI SALVA IL NOME E NON UN NUMERO
---------------------------------------
Perche' il numero cambia.  Staccando il secondo schermo, quello che era «2»
diventa «1», e una finestra a tutto schermo andrebbe sullo schermo sbagliato
senza dire niente.  Il nome che dà il sistema o c'e' o non c'e', e si puo'
controllare.  Vedi `Utility/tema.video_schermo`.
"""

from PyQt6.QtGui import QGuiApplication


def elenco() -> list:
    """Gli schermi collegati adesso, nell'ordine in cui li dà il sistema.

    Ogni voce e' un dizionario con:

        `nome`   il nome che ha dato il sistema (`HDMI-A-1`, `DP-1`, …)
        `larghezza`, `altezza`   la misura in pixel
        `principale`  True se e' quello principale **per il sistema**
        `etichetta`  la riga da mostrare nelle impostazioni

    «PRINCIPALE» E «SECONDARIO» SONO PAROLE DEL SISTEMA
    ---------------------------------------------------
    Il sistema chiama «principale» lo schermo che ha deciso di usare per
    aprire le finestre, e gli altri «secondari».  Si usano queste parole e non
    altre: sono le parole che l'utente ha gia' letto nelle impostazioni del
    sistema, e rinominarle non aiuta nessuno.

    PERCHE' NON SI DICE DOVE STA LA FINESTRA
    --------------------------------------
    Si potrebbe aggiungere «qui c'e' la finestra del programma», e sarebbe
    un'informazione vera.  Ma non si mette, perche' cambierebbe l'ordine
    delle voci se si volesse metterlo per primo, e l'ordine delle voci non
    deve dipendere da dove si trova la finestra: uno schermo che cambia
    posizione nella tendina mentre l'utente la guarda fa scegliere la voce
    sbagliata.  Il nome del sistema e la sua posizione nella lista sono la
    stessa cosa dall'avvio alla fine.

    Non si restituiscono gli oggetti `QScreen`: sono vivi solo finche' c'e' la
    `QApplication`, e una lista che li tiene riscalda il programma per nessun
    motivo.  Qui si tiene solo il testo, e chi lo usa cerca lo schermo per
    nome quando serve.
    """
    schermi = QGuiApplication.screens()
    primario = QGuiApplication.primaryScreen()
    nome_primario = primario.name() if primario is not None else ""

    voci = []
    for schermo in schermi:
        geometria = schermo.geometry()
        principale = schermo.name() == nome_primario
        voci.append({
            "nome": schermo.name(),
            "larghezza": geometria.width(),
            "altezza": geometria.height(),
            "principale": principale,
            "etichetta": (
                f"{schermo.name()} — {geometria.width()}×{geometria.height()}"
                f" ({'principale' if principale else 'secondario'})"),
        })
    return voci


def scelto_dalle_impostazioni():
    """Lo schermo scelto nelle impostazioni, o None se non ne e' stato scelto uno.

    None vuol dire «Segui la finestra».  Non un errore: l'opzione non e'
    obbligatoria, e il valore salvato che non trova uno schermo collegato non
    e' un errore neanche lui — uno schermo staccato e uno rinominato sono la
    stessa cosa dal punto di vista di chi sta usando il programma.

    Il valore salvato non si cancella: se lo schermo torna collegato,
    l'opzione torna a valere.  E il posto giusto per accorgersi che uno
    schermo e' sparito e' l'elenco delle impostazioni, che elenca solo quelli
    che ci sono.
    """
    from Utility import tema

    nome = tema.video_schermo()
    if nome == tema.SEGUI:
        return None
    for schermo in QGuiApplication.screens():
        if schermo.name() == nome:
            return schermo
    return None


def schermo_dove_sta(finestra):
    """Lo schermo su cui si trova la finestra, o None se non si trova.

    Il confronto e' fra il **centro** della finestra e il rettangolo dello
    schermo: e' il punto che decide, perche' una finestra straripa su due
    schermi non ha un solo schermo «su cui sta», e il centro e' la scelta che
    risponde alla domanda «dove sta guardando l'utente».
    """
    if finestra is None:
        return None
    try:
        centro = finestra.geometry().center()
    except (AttributeError, RuntimeError):
        # Un oggetto di cui e' stato distrutto il lato C++ solleva
        # RuntimeError su qualunque cosa: e' il caso normale qui, non un
        # errore, quindi si esce in silenzio e si lascia decidere il chiamante.
        return None
    for schermo in QGuiApplication.screens():
        if schermo.geometry().contains(centro):
            return schermo
    return None


def schermo_che_serve(finestra_app=None):
    """Lo schermo su cui il programma **accende** la finestra del secondo monitor.

    TRE SCELTE, IN QUEST'ORDINE
    --------------------------
    1.  quello scelto nelle impostazioni, se c'e' ed e' ancora collegato;
    2.  quello dove **non** sta la finestra del programma, se ci sono due
        schermi o piu';
    3.  `None`, se c'e' un solo schermo.

    PERCHE' IL PUNTO 2 E' IL PUNTO CHE MANCAVA
    ------------------------------------------
    Prima la finestra del secondo schermo esisteva **solo** se nelle
    impostazioni era stato scelto uno schermo con il suo nome.  Con l'opzione
    «Segui la finestra» — che e' quella di partenza — non esisteva, e quindi:

        _finestra_esterna() -> None

    e di conseguenza il video usciva solo dentro l'app, sul primo schermo.
    Non per un guasto: semplicemente la finestra non era mai stata creata,
    e tutto il resto del programma lavorava correttamente con quel `None`.

    Il punto 2 e' quello che rende il secondo schermo una cosa che c'e' quando
    c'e', senza dover prima andare a sceglierlo a mano.  E' la stessa domanda
    che gia' si faceva per il video a tutto schermo, risolta con la stessa
    regola — cosi' i due posti non possono divergere.
    """
    scelto = scelto_dalle_impostazioni()
    if scelto is not None:
        return scelto

    # DISATTIVATO
    # ------------
    # Qui prima c'era un pezzo che sceglieva **da solo** «il primo schermo che
    # non e' quello dove sta la finestra».  Con due monitor accadeva sempre, e
    # il risultato era che il video si apriva sul primo schermo — cioe' dove
    # sta la finestra, **dentro l'app** — che e' l'unica cosa che non deve
    # succedere.
    #
    # La scelta del monitor e' dell'utente, e vuota significa «nessuno».
    # Il programma non indovina: se l'utente ha due monitor e non ha scelto,
    # il video resta dentro l'app come quando ne aveva uno solo, e lo schermo
    # esterno si accende scegliendolo.
    return None


def secondario_per_video(finestra_app=None):
    """Lo schermo «secondario multimediale»: quello dove va il video.

    E' il posto principale del video quando l'utente non ha scelto niente:
    il secondo schermo che c'e', quello dove non sta la finestra del programma.
    Vedi `schermo_che_serve`, che e' la regola completa.

    PERCHE' UNA FUNZIONE A PARTE E NON `schermo_che_serve`
    -----------------------------------------------------
    Perche' `schermo_che_serve` risponde anche «non c'e' niente» quando c'e'
    un solo schermo, e quella risposta va bene a chi decide se aprire una
    finestra.  Ma chi deve sapere **quale** schermo e' il secondario ha
    bisogno della risposta anche quando e' None, per poter dire «e allora
    non c'e' nessun secondo schermo, e nessuno da duplicare».

    Sono due domande diverse e hanno due risposte diverse, quindi due
    funzioni: quando un posto chiede una cosa e un altro posto un'altra,
    accorciarle in una sola con un parametro e un valore magico e' il modo
    di sbagliare una delle due.
    """
    scelto = scelto_dalle_impostazioni()
    if scelto is not None:
        return scelto
    # Nessuna scelta = disattivato.  Vedi la nota di `schermo_che_serve`: il
    # programma non sceglie il monitor da solo, perche' scegliendolo metteva
    # il video sul primo schermo, dentro l'app.
    return None


def duplicati(finestra_app=None):
    """Gli schermi **in piu'** su cui il video viene duplicato.

    Sono quelli che l'utente ha spuntato nelle impostazioni, nell'ordine in
    cui li ha spuntati — che e' l'ordine che vede lui, e quindi quello che
    vede anche il resto del programma.

    I TRE FILTRRI, E SONO TRE PER UN MOTIVO
    ---------------------------------------
    Un nome che compare nella lista non basta per aprire una finestra:

    1.  **Deve essere ancora collegato.**  Se l'utente aveva spuntato un
        terzo schermo e poi l'ha staccato, quel nome e' ancora nella lista ma
        non c'e' piu' nessuno schermo con quel nome.  Vedi
        `tema.video_schermi_duplica`.

    2.  **Non puo' essere il secondario gia' scelto.**  Se lo fosse, quella
        finestra ci sarebbe gia': aprirne una seconda sopra produrrebbe due
        finestre a tutto schermo una sopra l'altra, e l'utente ne vedrebbe
        una e si chiederebbe perche' l'altra esiste.

    3.  **Non puo' essere quello dove sta la finestra del programma.**  Il
        video si vede gia' li', nel player: metterci sopra una finestra a
        tutto schermo coprirebbe l'applicazione, e l'utente che sta
        leggendo una pubblicazione si ritrova a non poterla piu' toccare.

    Il risultato e' quello che l'utente si aspetta spuntando le caselle:
    il video su questo schermo, su quello, e su quello.
    """
    secondario = secondario_per_video(finestra_app)
    if secondario is None:
        # Nessuno schermo secondario: non ha senso duplicare niente, perche'
        # «dove sta il video» non e' definito.  Non succede quasi mai — senza
        # secondario siamo su un solo schermo, dove la finestra secondaria
        # non viene nemmeno aperta.
        return []
    dove_sta = schermo_dove_sta(finestra_app)
    scelti = tema_duplicati()
    fuori = []
    for schermo in QGuiApplication.screens():
        nome = schermo.name()
        if nome not in scelti:
            continue
        if secondario is not None and nome == secondario.name():
            continue                      # filtro 2
        if dove_sta is not None and nome == dove_sta.name():
            continue                      # filtro 3
        fuori.append(schermo)
    return fuori


def tema_duplicati():
    """I nomi spuntati dall'utente.  Una riga perche' il `tema` si importa qui."""
    from Utility import tema

    return tema.video_schermi_duplica()


def per_il_video(finestra_app=None):
    """Lo schermo su cui mettere il video a tutto schermo.

    Tre scelte, in quest'ordine:

    1.  quello scelto nelle impostazioni, se c'e' ed e' ancora collegato;
    2.  quello dove sta la finestra da cui l'utente e' partito;
    3.  quello principale, se non si trova niente.

    Il punto 3 e' un ripiego e non una scelta: si arriva a lui solo se non si
    sa niente della finestra, e va bene il primario perche' e' l'unico
    schermo di cui il sistema ha detto con certezza che e' quello su cui
    parte tutto.  Meglio il primario che niente.
    """
    scelto = scelto_dalle_impostazioni()
    if scelto is not None:
        return scelto
    quello_giusto = schermo_dove_sta(finestra_app)
    if quello_giusto is not None:
        return quello_giusto
    primario = QGuiApplication.primaryScreen()
    if primario is not None:
        return primario
    schermi = QGuiApplication.screens()
    return schermi[0] if schermi else None

