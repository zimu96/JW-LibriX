#
#  JWLibraryApp.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 01/01/21.
#

"""L'avvio dell'applicazione.

In Swift ``JWLibraryApp`` era quattro righe: un ``@main``, una
``WindowGroup`` e dentro ``SidebarView``.  Tutto il resto stava sotto.

Qui le stesse quattro righe, con le tre cose che su Linux servono e che
su macOS facevano il sistema:

  1. il nome dell'applicazione, cosche' la finestra si chiama come si deve
     invece che ``python3``;
  2. il foglio di stile, cosche' i pulsanti abbiano un aspetto solo invece di
     di quello di Qt grezzo;
  3. il simbolo sulla barra dei programmi.

E POI: si puo' provare senza aprire niente::

    python3 JWLibraryApp.py --verifica        controlla che i moduli entrino
    python3 JWLibraryApp.py --dati            dice dove stanno i dati
    python3 JWLibraryApp.py --estradi w_I.db  prova la decodifica

Le tre opzioni esistono perche' la lezione di COME-FUNZIONA.txt e' che un
errore che si vede a schermo arriva tardi e da un altro posto.  Un modulo che
non entra lo si scopre subito, senza aprire una finestra.
"""

import os
import sys
from pathlib import Path

# La radice del progetto in sys.path, cosche' ``python3 JWLibraryApp.py`` da
# qualunque cartella funzioni e non solo dalla radice.
RADICE = Path(__file__).resolve().parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))


def _opzioni(argv: list[str]) -> bool:
    """Le opzioni da riga di comando.  Ritorna False se si e' aperta la finestra."""
    if "--dati" in argv:
        from Utility.Extensions.Ext_FileManager import get_documents_directory
        radice = get_documents_directory()
        from Utility.Structures import Paths as modulo_paths
        print(f"I dati stanno qui: {radice}")
        if modulo_paths.da_variabile():
            print("  (scelta con JWL_HOME)")
        elif modulo_paths.cartella_scelta():
            print(f"  (scelta nelle Impostazioni, salvata in {modulo_paths.FILE_PERCORSO})")
        else:
            print("  (cartella predefinita)")
        if radice.exists():
            for voce in sorted(radice.iterdir()):
                print(f"  {voce.name}")
        else:
            print("  (la cartella non c'e' ancora: si crea al primo avvio)")
        return True

    if "--estradi" in argv:
        indice = argv.index("--estradi")
        if indice + 1 >= len(argv):
            print("Uso: --estradi percorso/del/pacchetto.db")
            return True
        from Utility.JWPubExtractor import JWPubExtractor
        cartella = argv[indice + 2] if indice + 2 < len(argv) else None
        JWPubExtractor(argv[indice + 1]).test_extraction(Path(cartella) if cartella else None)
        return True

    if "--verifica" in argv:
        return _verifica()

    return False


#: I moduli che l'avvio controlla uno per uno.
#:
#: Sta qui e non dentro la funzione perche' adesso i moduli si controllano
#: da due posti: `--verifica` quando lo chiedi a mano, e `_controlli_avvio`
#: quando parte il programma.  Due elenchi uguali in due posti sono due
#: elenchi che il giorno dopo sono diversi, e il secondo non controlla
#: quello che crede di controllare.
MODULI_DA_CONTROLLARE: list[str] = [
        "Utility.Stuff",
        "Utility.Paths" if False else "Utility.Structures.Paths",
        "Utility.Structures.Generals",
        "Utility.Structures.ButtonStyle",
        "Utility.Extensions.Ext_Int",
        "Utility.Extensions.Ext_String",
        "Utility.Extensions.Ext_Color",
        "Utility.Extensions.Ext_FileManager",
        "Utility.Extensions.Ext_DispatchQueue",
        "Utility.Extensions.Ext_ScrollRuota",
        "Utility.DBManager",
        "Utility.Aggiornamenti",
        "Utility.CatalogoMedia",
        "Utility.Copertine",
        "Utility.CaricaCopertine",
        "Utility.JWPubManager",
        "Utility.JWPubExtractor",
        "Utility.FileDownloader",
        "Utility.Lettore",
        "Utility.MediaScaricati",
        "Utility.RiferimentiWol",
        "Utility.Rete",
        "Utility.RiferimentiLocali",
        "Utility.RicercaTesto",
        "Utility.CodaPlaylist",
        "Utility.UserData.PlaylistManager",
        "Utility.UserData.TagManager",
        "Utility.UserData.FormatoJWLibrary",
        "Utility.UserData.BackupManager",
        "SubViews.BackupIniziale",
        "SubViews.SceltaCartellaDati",
        "SubViews.BarraBackup",
        "Utility.UserData.BlockRangeManager",
        "Utility.UserData.BookmarkManager",
        "Utility.UserData.HighlightManager",
        "Utility.UserData.LocationManager",
        "Utility.UserData.NoteManager",
        "Utility.UserData.UserMarkManager",
        "WebBrowserView",
        "SubViews.WebBrowserArticleView",
        "SubViews.PannelloRiferimenti",
        "SubViews.ArticleView",
        "SubViews.BibleBooksView",
        "SubViews.BibleChaptersView",
        "SubViews.BibleView",
        "SubViews.PubListView",
        "SubViews.PubDocumentView",
        "SubViews.PubView",
        "SubViews.AdunanzeView",
        "SubViews.PlaylistView",
        "SubViews.RicercaLocale",
        "SubViews.RisultatiTesto",
        "SubViews.DialoghiNote",
        "SubViews.ContenutiView",
        "SubViews.PersonalStudyView",
        "ContentView",
        "SidebarView",
]


def _passo_ambiente() -> str | None:
    """Le versioni, e WebEngine.  Restituisce l'errore che ferma tutto, se c'e'.

    Dentro l'app questa funzione e' quasi sempre un no-op: WebEngine e' gia'
    importato da `main()` perche' senza non parte niente.  Resta perche' quando
    si lancia `--verifica` da solo e' la prima cosa che dice se l'ambiente e'
    quello che il programma si aspetta.
    """
    import sqlite3

    print(f"Python      {sys.version.split()[0]}")
    print(f"SQLite      {sqlite3.sqlite_version}")
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        print(f"Qt          {QT_VERSION_STR}")
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        print("WebEngine   ok")
    except ImportError as errore:
        print(f"WebEngine   MANCANTE ⚠️  {errore}")
        print("  Installa: sudo pacman -S python-pyqt6 python-pyqt6-webengine")
        print("           oppure: sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine")
        return f"WebEngine mancante: {errore}"
    return None


def _passo_moduli() -> int:
    """I moduli, uno per uno.  Restituisce quanti non entrano.

    Non entra e non esce dal ciclo di eventi: quando gira dentro l'app e' un
    passo come un altro, e i moduli sono gia' quasi tutti in memoria perche'
    l'app e' gia' partita — quindi qui costa poco e serve a dare il nome a
    quello che manca.
    """
    falliti = 0
    for nome in MODULI_DA_CONTROLLARE:
        try:
            __import__(nome)
            print(f"  ok    {nome}")
        except Exception as errore:  # noqa: BLE001 - qui si vuole vedere tutto
            falliti += 1
            print(f"  ROTTO {nome}: {type(errore).__name__}: {errore}")

    if falliti:
        print(f"\n{falliti} moduli non entrano su {len(MODULI_DA_CONTROLLARE)}")
        return falliti

    print(f"\nTutti i {len(MODULI_DA_CONTROLLARE)} moduli entrano.")
    righe = len((RADICE / "Files" / "script.js").read_text().splitlines())
    print(f"Il JavaScript ha {righe} righe e resta identico al progetto originale.")
    return 0


def _passo_server() -> None:
    """Una richiesta sola al server: e' l'unica cosa che cambia da un giorno all'altro.

    Nessun controllo fatto offline se ne accorge: i file sono sul disco, il
    codice e' lo stesso, e il server puo' aver cambiato indirizzo.

    Non ferma nessuno: quando non risponde si dice e si continua.  Fermare un
    programto perche' la rete non c'e' e' la cosa che fa un programma che sembra
    rotto invece che uno che aspetta.
    """
    try:
        from Utility import MepsAPI
        voci = MepsAPI.media("sjj", "I")
        pacchetto = MepsAPI.scegli(voci, "JWPUB")
        print(f"Il server risponde: {len(voci)} file per sjj_I, "
              f"{len(MepsAPI.per_traccia(voci))} tracce, "
              f"pacchetto {'presente' if pacchetto else 'NON TROVATO'}")
    except Exception as errore:  # noqa: BLE001 - qui si vuole vedere tutto
        print(f"Il server non risponde ⚠️  {type(errore).__name__}: {errore}")


def _verifica() -> bool:
    """Tutti i controlli, uno dopo l'altro, in un pezzo solo.

    E' la strada di `--verifica`: quando la chiedi a mano, la vuoi tutta e
    subito, e vuoi che il codice di uscita dica se il programma puo' partire.

    Il programma, quando parte da solo, non usa questa funzione: usa
    `_controlli_avvio`, che e' la stessa lista di passi ma a un giro di eventi
    per volta, cosi' la schermata di avvio si ridisegna mentre lavorano.
    """
    if _passo_ambiente() is not None:
        return True
    if _passo_moduli():
        return True
    _passo_server()
    schermate_a_posto = _verifica_schermate()
    # Il codice di errore e' quello che faceva fermare `jw.sh`, che scriveva
    # `JWLibraryApp.py --verifica || exit 1`.  Oggi i controlli girano dentro
    # l'app, e li' non si esce: si dice nella schermata e non si apre la
    # finestra.  Vedi `_controlli_avvio`.
    if not _verifica_prove():
        raise SystemExit(1)
    return schermate_a_posto


def _controlli_avvio(splash, quando_fatto) -> None:
    """I controlli dell'avvio, dentro l'app, a un giro di eventi per volta.

    IL PROBLEMA CHE RISOLVE
    -----------------------
    Fin qui i controlli giravano **prima** dell'app, in un processo separato:

        jw.sh ──► JWLibraryApp.py --verifica   (14 secondi, NESSUNA finestra)
                 └──► poi parte l'app e la schermata di avvio

    Quattordici secondi di terminale su cui non compare niente, e il peggio e'
    che non si capisce se il programma e' partito: la finestra non c'e', quindi
    l'unico indizio e' che il terminale e' fermo.  Il primo pezzo e' la splash
    stessa, quindi senza finestra non c'e' nemmeno il posto dove metterla.

    PERCHE' UN GIRO DI EVENTI PER PASSO, E NON UN THREAD
    ---------------------------------------------------
    `_verifica_schermate` costruisce dieci schermate vere, con Qt.  Un widget
    costruito fuori dal thread che possiede il ciclo di eventi non viene mai
    disegnato e, se viene toccato, Qt puo' arrestare il programma.  La strada
    sicura e' l'unica che c'e': restare sul thread principale e cedere il
    controllo fra un passo e l'altro, cosi' Qt ridisegna la schermata e il
    terminale scorre mentre i controlli lavorano.

    Non e' un trucco: `QTimer.singleShot(0, ...)` rimette la funzione in coda
    agli eventi, quindi il passo successivo parte **dopo** che Qt ha ridisegnato
    tutto quello che era in attesa.

    IL LOG
    ------
    Non c'e' niente da deviare qui: `Messaggi.devia` e' gia' stato chiamato da
    `_SplashScreen.start()` prima di questa funzione, quindi ogni `print` di
    sotto arriva al terminale vero **e** al riquadro della schermata, che e'
    esattamente quello che l'utente ha chiesto: lo stesso log nei due posti.

    SE UNA REGOLA DEL PLAYER FALLISCE
    --------------------------------
    Da terminale era `raise SystemExit(1)`, e `jw.sh` leggendo il codice di
    uscita non avviava niente.  Qui dentro non si puo' fare cosi': `SystemExit`
    dentro un callback Qt chiude il ciclo di eventi a meta' e lascia la
    schermata a meta'.  Quindi si dice nella schermata, si scrive la riga nel
    log, e la finestra principale **non** viene aperta: un programma che si
    apre e si comporta male e' peggio di uno che non parte.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    # I PASSI VELOCI GIRANO SEMPRE, QUELLI PESANTI SU RICHIESTA
    # ---------------------------------------------------------
    # Misurati: ambiente, moduli e server costano circa un decimo di secondo;
    # costruire dieci schermate vere ne costa 1,3 e le regole del player 5,5.  I
    # due pesanti sono autotest da sviluppo e a ogni avvio facevano aspettare
    # sette secondi.  Restano completi con `--verifica` e, dentro l'app, con
    # JWL_CONTROLLO_COMPLETO=1.
    completo = bool(os.environ.get("JWL_CONTROLLO_COMPLETO"))
    passi = [
        ("Controllo l'ambiente", "ambiente"),
        ("Controllo i moduli", "moduli"),
        ("Chiedo al server", "server"),
    ]
    if completo:
        passi += [("Costruisco le schermate", "schermate"),
                  ("Provo le regole del player", "player")]
    stato = {"i": 0}

    def prossimo() -> None:
        i = stato["i"]
        stato["i"] = i + 1
        testo, passo = passi[i]

        splash.imposta_stato(testo)
        splash._barra_inizia(len(passi))
        splash._barra_avanza(i + 1, len(passi))
        QApplication.processEvents()

        if passo == "ambiente":
            errore = _passo_ambiente()
            if errore is not None:
                print(errore)
                quando_fatto(False, "WebEngine mancante: il programma non puo' partire.")
                return
        elif passo == "moduli":
            if _passo_moduli():
                quando_fatto(True, "")
                return
        elif passo == "server":
            # Il primissimo avvio e' offline: niente rete finche' non si e'
            # scelta la cartella dati.
            from SubViews import SceltaCartellaDati
            if not SceltaCartellaDati.serve():
                _passo_server()
        elif passo == "schermate":
            if not _verifica_schermate():
                quando_fatto(True, "")
                return
        else:
            if not _verifica_prove():
                print("Una regola del player non e' a posto: la finestra non si apre.")
                quando_fatto(False, "Una regola del player non e' a posto.")
                return

        if stato["i"] < len(passi):
            QTimer.singleShot(0, prossimo)
        else:
            splash.imposta_stato("")
            quando_fatto(True, "")

    print("\n===== Controlli di avvio =====")
    QTimer.singleShot(0, prossimo)


def _verifica_prove() -> bool:
    """Le tre regole del player, provate a ogni avvio.

    LE PROVE NON SONO UN DIAGNOSTICO: SONO UN BLOCCO
    -----------------------------------------------
    Il mini player, il ritorno dopo la X e i monitor esterni sono tre cose
    gia' state sistemate piu' volte, e ognuna di loro si rompe senza dare un
    errore: il programma si apre e si comporta male.  Una prova che non gira
    serve a poco, perche' quando qualcuno tocca il player nessuno la guarda.

    Per questo girano a ogni avvio, e se una fallisce il programma non parte.
    Costano poco — un secondo l'una, con la finestra fuori schermo, senza rete
    e senza toccare i dati — e servono a una cosa sola: dire che il player e'
    quello che l'utente ha chiesto.

    LE STESSE CHE SI LANCIANO A MANO
    --------------------------------
    Sono gli stessi file di `./prove/prove.sh`, lanciati uno per uno.  Due
    copie delle prove sarebbero due cose da tenere dritte insieme, e la
    seconda e' sempre quella che non si aggiorna.

    LA FINESTRA FUORI SCHERMO
    -------------------------
    `QT_QPA_PLATFORM=offscreen`: una prova che aprisse una finestra a tutto
    schermo durante un avvio — e una di queste finestre copre un monitor
    intero — bloccherebbe l'avvio perche' l'utente non avrebbe piu' il desktop
    davanti.  Fuori schermo le finestre non escono dal processo.
    """
    import os
    import subprocess

    # LA BUILD PULITA NON HA LE PROVE
    # -------------------------------
    # La cartella che va su GitHub e nell'AppImage non porta `prove/`: le prove
    # servono a chi sviluppa, non a chi usa l'app.  Senza la cartella intera
    # non c'e' niente da provare, e si dice; un file mancante DENTRO `prove/`
    # resta invece un errore, perche' li' la cartella c'e' e la prova no.
    if not (RADICE / "prove").is_dir():
        print("  saltate le prove del player: questa build non ha la cartella prove/")
        return True

    prove = (
        ("mini player", "prove/prova_mini_player.py"),
        ("ritorno dopo la X", "prove/prova_ritorno.py"),
        ("monitor esterni", "prove/prova_schermi_esterni.py"),
        ("accensione schermi", "prove/prova_accensione_schermi.py"),
        ("riga degli schermi", "prove/prova_riga_schermi.py"),
        ("icona", "prove/prova_icona.py"),
    )
    ambiente = dict(os.environ)
    ambiente["QT_QPA_PLATFORM"] = "offscreen"

    rotte = []
    for nome, percorso in prove:
        percorso = RADICE / percorso
        if not percorso.is_file():
            # Una prova che non c'e' non puo' passare: dire «ok» per un file
            # assente e' la stessa bugia di un modulo che non entra.
            rotte.append((nome, percorso, "il file della prova non c'e'"))
            print(f"  ROTTA  {nome}: il file non c'e'")
            continue
        try:
            esito = subprocess.run([sys.executable, str(percorso)],
                                   capture_output=True, text=True,
                                   timeout=180, env=ambiente)
        except (subprocess.TimeoutExpired, OSError) as errore:
            rotte.append((nome, percorso, f"{type(errore).__name__}: {errore}"))
            print(f"  ROTTA  {nome}: non e' riuscita a girare ({type(errore).__name__})")
            continue
        if esito.returncode != 0:
            rotte.append((nome, percorso, esito.stdout or esito.stderr))
            print(f"  ROTTA  {nome}")
        else:
            print(f"  ok     {nome}")

    if not rotte:
        print(f"Le {len(prove)} regole del player sono tutte a posto.")
        return True

    print()
    for nome, percorso, uscita in rotte:
        print(f"=== {nome} ({percorso.name}) ===")
        for riga in str(uscita).strip().splitlines():
            print(f"  {riga}")
        print()
    print("Il programma non parte: il player non e' quello che deve essere.")
    print("Per vedere i dettagli:  ./prove/prove.sh")
    print("Per partire lo stesso:  JWL_SENZA_CONTROLLO=1 ./jw.sh")
    return False


def _pub_installata():
    """Una pubblicazione che c'e' davvero sul disco, o None.

    Il nome della cartella si indovina dal contenuto, non si scrive: si guarda
    quali cartelle hanno dentro `contents/*.db` e si legge da li' la sigla e la
    lingua.  Un nome scritto qui (`sjj`) va bene il giorno in cui quel
    pacchetto e' installato e il giorno dopo non piu', e il controllo comincia
    a dare errori che non hanno niente a che fare con il programma.

    L'ordine non e' importante: basta un pacchetto vero.  Si prende il primo
    che si trova, e il controllo dice quale: cosi' chi legge sa che cosa e'
    stato aperto e puo' ricontarlo.
    """
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    from Utility import Lingua
    from Utility.Structures.Generals import Publication

    radice = get_documents_directory()
    for cartella in sorted(radice.glob("*")):
        if not cartella.is_dir():
            continue
        database = sorted((cartella / "contents").glob("*.db"))
        if not database:
            continue
        # Il nome della cartella e' il nome del database, che e' il nome della
        # pubblicazione: `sn_I.db` dentro `sn_I/`.  Da li' si prendono sigla e
        # lingua, senza sapere niente in anticipo.
        pezzi = database[0].stem.split("_", 1)        # "sn_I" -> ["sn", "I"]
        if len(pezzi) != 2 or not pezzi[0] or not pezzi[1]:
            continue
        sigla, lingua = pezzi
        return Publication(ID=1, keySymbol=sigla, year=0,
                           mepsLanguageId=Lingua.da_simbolo(lingua),
                           publicationTypeId=1, issueTagNumber=0,
                           title=database[0].stem)
    return None


def _voce_di_menu() -> bool:
    """La voce di menu di questo programma e' installata?

    IL PERCHE' LA DOMANDA ESISTE
    -----------------------------
    `setDesktopFileName("JWLibriX")` dice a Qt: «questa applicazione e' la
    voce `JWLibriX.desktop`».  Con la voce installata fa quello che serve —
    la finestra viene accoppiata alla voce e prende l'icona giusta nella barra
    delle applicazioni, e il portale del desktop riesce a registrare il
    programma.

    Senza la voce installata promette un file che non c'e', e Qt lo dice a
    ogni avvio:

        [Qt AVVISO] Failed to register with host portal QDBusError(
            "org.freedesktop.portal.Error.Failed",
            "Could not register app ID: App info not found for 'JWLibriX'")

    Il messaggio e' esatto — non c'e' nessuna voce con quel nome — ma non
    aiuta nessuno: il programma parte benissimo lo stesso.  Peggio, fa
    credere che qualcosa sia rotto, e l'utente passa mezz'ora a cercare il
    difetto in un posto dove non c'e'.

    Quindi si guarda prima, e si dice la cosa vera: il programma funziona,
    ma non e' nel menu delle applicazioni.  La risposta e' `./installa.sh`.

    DOVE SI GUARDA
    --------------
    Nelle cartelle XDG, che sono le uniche dove il desktop cerca.  La prima
    che l'utente ha scelto vale piu' delle altre, quindi si guarda nell'ordine
    in cui XDG le ordina: prima `$XDG_DATA_HOME`, poi `/usr/local/share`, poi
    `/usr/share`.

    Non si controlla anche il contenuto del file: se il file c'e' ma dentro
    c'e' un'altra applicazione, il nome e' sbagliato per colpa di qualcun
    altro e non e' un problema di questo programma.
    """
    import os

    cartelle = []
    scelta = os.environ.get("XDG_DATA_HOME")
    if scelta:
        cartelle.append(Path(scelta))
    cartelle.append(Path("/usr/local/share"))
    cartelle.append(Path("/usr/share"))
    # La cartella di sempre quando XDG_DATA_HOME non e' impostata: e' il posto
    # dove `installa.sh` mette le cose, e senza questa riga il programma
    # direbbe che non e' installato anche quando lo e'.
    cartelle.append(Path.home() / ".local" / "share")

    for cartella in cartelle:
        if (cartella / "applications" / "JWLibriX.desktop").is_file():
            return True
    return False


def _icona_multipla() -> QIcon:
    """L'icona del programma, con tutte le misure che ci sono.

    PERCHE' TUTTE E NON UNA
    -----------------------
    Un `QIcon` puo' tenere piu' immagini, e ognuna e' una misura.  Il gestore
    delle finestre ne chiede una e prende la piu' vicina a quella che gli serve:
    chiedere 32 pixel e trovare un'immagine sola da 1024 significa ridimensionare
    sempre, che su un'icona con il testo dentro si vede — la «LIBRARY» sotto
    diventa una macchia.

    Per questo si aggiungono tutte le misure, dalla piu' piccola alla piu'
    grande: il risultato e' lo stesso PNG che si installerebbe, ma con dentro i
    numeri giusti per ogni schermo.

    LE MISURE SONO QUELLE DI `installa.sh`
    --------------------------------------
    16, 32, 64, 128, 256, 512, 1024: le stesse sette che vengono copiate in
    `icons/hicolor`.  Se un giorno ne arriva un'ottava, va aggiunta anche qui
    — altrimenti l'icona nella barra e' quella del tema, non questa.
    """
    # `QIcon` si importa qui e non in cima al file: il programma non deve
    # dipendere da PyQt6 per fare `--dati` o `--verifica`, e questa funzione
    # viene chiamata anche dalle prove, che costruiscono la finestra fuori
    # schermo.
    from PyQt6.QtGui import QIcon

    icona = QIcon()
    for misura in (16, 32, 64, 128, 256, 512, 1024):
        file = RADICE / "Files" / "icons" / f"{misura}.png"
        if file.is_file():
            icona.addFile(str(file))
    if icona.isNull():
        # Nessuna immagine: il programma parte lo stesso, con l'icona di
        # prima.  Meglio un'icona generica che nessuna finestra.
        grande = RADICE / "Files" / "JWLibrary.png"
        if grande.is_file():
            icona.addFile(str(grande))
    return icona


def _voce_da_usare() -> str:
    """La voce di menu da dichiarare a Qt: il nome, o "" se non e' installata.

    QUI C'E' STATO UN TENTATIVO CHE NON FUNZIONAVA
    ---------------------------------------------
    Il tentativo: scrivere una voce `.desktop` **temporanea**, in una cartella
    di `/tmp`, con dentro i percorsi veri di `jw.sh` e dell'icona, e passare a
    `setDesktopFileName` il **percorso** di quella voce invece del nome.  Il Qt
    accetta il percorso dal 6.3, quindi sembrava la strada giusta, e la
    finestra avrebbe avuto un'icona sua anche senza installare niente.

    Non funziona, e fa **pendere l'avvio del programma**: la finestra non
    compare piu'.  Il motivo e' che il percorso viene mandato al portale
    del desktop, e il portale risponde:

        [Qt AVVISO] Failed to register with host portal QDBusError(
            "org.freedesktop.portal.Error.Failed",
            "Could not register app ID: App info not found for
             '/tmp/jwl-xxxx/JWLibriX.desktop'")

    e la risposta non arriva subito: l'avvio resta fermo li'.  Il difetto e'
    che `/tmp` non e' una cartella che il desktop conosce — e' proprio il
    punto: una voce che il desktop **non** trova non e' una voce, e chiederla
    per farcela usare e' chiedere a qualcuno una cosa che non puo' dare.

    QUINDI, COME SI FA L'ICONA SENZA INSTALLARE
    ------------------------------------------
    Non serve la voce: basta l'icona **sulla finestra**, che e' quello che
    guarda davvero la barra delle applicazioni quando l'applicazione non ha
    una voce sua.  E la finestra ce l'ha, a tutte e sette le misure, grazie a
    `_icona_multipla` — che non ha niente a che fare con la voce di menu e
    funziona installato o no.

    Se un giorno l'icona nella barra non si vedesse ancora, la risposta non e'
    un altro trucco con `setDesktopFileName`: e' `./installa.sh`, che mette
    dove il desktop li cerca sia la voce sia le sette icone.  E' una scelta
    dell'utente, non una riga di programma.
    """
    return "JWLibriX" if _voce_di_menu() else ""


def _verifica_schermate() -> bool:
    """Prova a COSTRUIRE le schermate, non solo a importarle.

    PERCHE' ESISTE, DOPO CHE E' SUCCESSO
    -------------------------------------
    Controllare che un modulo entri dice che i nomi sono giusti.  Non dice
    che i pulsanti si possano creare.  E la differenza e' costata due volte
    di fila, e in due modi diversi:

      - ``QPushButton(icon("trash"), self)``: in PyQt6 non e' un overload
        che esiste, serve il testo in mezzo.  L'import era a posto, il modulo
        entrava, e il widget si costruiva solo quando arrivavano 3.741
        pubblicazioni dal catalogo.
      - ``self._costruisci_gruppo()`` chiamato su un metodo scritto
        ``_costruci_gruppo``: un refuso di una lettera.

    Entrambi sono invisibili a un controllo che guarda gli import, e visibili
    solo quando la finestra viene costruita.  Per questo qui le schermate si
    costruiscono davvero, con dati finti e senza rete.

    NON si costruiscono ``BibleView`` e ``PubView``: al costruttore partono
    i download, e un controllo che scarica 300 MB non e' un controllo.
    """
    print("\nCostruisco le schermate (senza rete):")

    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    from PyQt6.QtWidgets import QApplication

    from Utility.Structures.Generals import BibleBook

    app = QApplication.instance() or QApplication([])

    # UNA PUBBLICAZIONE DI PROVA CHE ESISTE SU DISCO
    # -----------------------------------------------
    # Prima qui c'era `sjj` scritto a mano, e il commento diceva «non si
    # tocca il disco».  Non era vero: `PubDocumentView` apre
    # il database **del pacchetto**, quindi ogni avvio di `jw.sh` stampava
    #
    #     Errore apertura database ⚠️  unable to open database file
    #     Errore apertura database ⚠️  sjj_I
    #
    # due volte, e non perche' il programma avesse un difetto: perche' il
    # pacchetto di prova non era installato.  Il peggio e' che un errore di
    # database in un messaggio di avvio e' la prima cosa che fa pensare che i
    # dati siano corrotti, mentre era il controllo a guardare nel posto
    # sbagliato.
    #
    # Quindi si cerca un pacchetto che ci sia davvero, e se non c'e' nessuno
    # si dice una volta sola, perche' quei due controlli allora non possono
    # verificare niente e fingere il contrario sarebbe falso.
    pub_prova = _pub_installata()
    if pub_prova is None:
        print("Nessun pacchetto installato: i controlli che aprono un "
              "pacchetto non possono verificare niente.")
    else:
        print(f"Pacchetto di prova: {pub_prova.title}")

    libro_prova = BibleBook(ID=1, shortName="Genesi", fullName="Genesi", chapters=50)

    controlli = [
        # LA FINESTRA, PER PRIMA
        # ----------------------
        # Prima non c'era, ed e' stato un buco per due motivi.
        #
        # Il motivo semplice: `SidebarView` non e' una schermata fra le altre,
        # e' quella che le tiene tutte, quindi non compariva nella lista e
        # nessuno pensava di costruirla.
        #
        # Il motivo vero e' peggiore: **la finestra costruisce cose che le
        # schermate non costruiscono**.  Costruisce la fascia, la rail, la
        # pila e la striscia del lettore in fondo, e ognuna di queste ha
        # collegamenti che esistono solo li'.  Un errore in uno di quelli non
        # lo vede nessuno dei nove controlli, e il programma parte e muore
        # subito:
        #
        #     AttributeError: type object 'Lettore' has no attribute 'motore'
        #
        # il `--verifica` diceva "Tutto bene: 9 schermate si costruiscono" e
        # il programma non partiva.  Un controllo che dice che tutto va bene
        # mentre il programma non parte e' peggio di nessun controllo, perche'
        # si smette di fidarsi.
        #
        # Quindi qui si costruisce anche la finestra, per prima, e si butta
        # via subito: non serve mostrarla, serve che i suoi costruttori
        # girino.
        ("SidebarView (finestra intera)",
         lambda: __import__("SidebarView", fromlist=["SidebarView"]
                            ).SidebarView()),
        ("ContentView", lambda: __import__("ContentView").ContentView()),
        ("HomeView", lambda: __import__("SubViews.HomeView",
                                        fromlist=["HomeView"]).HomeView()),
        ("SettingsView", lambda: __import__("SubViews.SettingsView",
                                            fromlist=["SettingsView"]).SettingsView()),
        ("BibleBooksView", lambda: __import__("SubViews.BibleBooksView",
                                              fromlist=["BibleBooksView"]
                                              ).BibleBooksView([libro_prova])),
        ("BibleChaptersView", lambda: __import__("SubViews.BibleChaptersView",
                                                 fromlist=["BibleChaptersView"]
                                                 ).BibleChaptersView(libro_prova)),
        ("PersonalStudyView", lambda: __import__("SubViews.PersonalStudyView",
                                                 fromlist=["PersonalStudyView"]
                                                 ).PersonalStudyView()),
        ("PlaylistView", lambda: __import__("SubViews.PlaylistView",
                                            fromlist=["PlaylistView"]).PlaylistView()),
        ("AdunanzeView", lambda: __import__("SubViews.AdunanzeView",
                                            fromlist=["AdunanzeView"]
                                            ).AdunanzeView()),
    ]

    # I due controlli che hanno bisogno di un pacchetto ci sono solo se il
    # pacchetto c'e'.  Senza, non si mettono: un controllo che non puo'
    # verificare niente, detto «ok», e' la stessa bugia del messaggio di
    # errore che c'era prima — solo piu' gentile.
    if pub_prova is not None:
        controlli += [
            ("PubListView", lambda: __import__("SubViews.PubListView",
                                               fromlist=["PubListView"]
                                               ).PubListView([pub_prova])),
            ("PubDocumentView", lambda: __import__("SubViews.PubDocumentView",
                                                   fromlist=["PubDocumentView"]
                                                   ).PubDocumentView(pub_prova)),
        ]

    rotti = 0
    for nome, costruisci in controlli:
        try:
            widget = costruisci()
            app.processEvents()
            widget.deleteLater()
            print(f"  ok    {nome}")
        except Exception as errore:  # noqa: BLE001 - qui si vuole vedere tutto
            rotti += 1
            print(f"  ROTTO {nome}: {type(errore).__name__}: {errore}")

    # Anche la barra di ogni schermata: i pulsanti della barra sono costruiti
    # dentro toolbar(), e quindi verrebbero fuori solo quando l'utente apre
    # un articolo.  E' il posto dove sta un quarto dei pezzi di interfaccia.
    #
    # LA BARRA SI CHIAMA, E NON SI COSTRUISCE E BASTA
    # -----------------------------------------------
    # Qui prima si costruiva la schermata, si faceva `deleteLater()` e si
    # scriveva «ok», senza chiamare `toolbar()`: il nome del controllo diceva
    # una cosa e il codice ne faceva un'altra.  Il controllo passava sempre,
    # anche con `toolbar()` rotta — cioe' non controllava niente, mentre il
    # commento sopra prometteva esattamente quello che non faceva.
    print("\nCostruisco le barre:")
    import SubViews.BibleChaptersView as bcv
    barre = [("BibleChaptersView.toolbar", bcv.BibleChaptersView(libro_prova))]
    if pub_prova is not None:
        import SubViews.PubDocumentView as pdv
        barre.append(("PubDocumentView.toolbar", pdv.PubDocumentView(pub_prova)))

    for nome, schermata in barre:
        try:
            pezzi = schermata.toolbar()
            if not pezzi:
                raise AssertionError("toolbar() ha restituito zero pezzi")
            app.processEvents()
            print(f"  ok    {nome} ({len(pezzi)} pezzi)")
        except Exception as errore:  # noqa: BLE001
            rotti += 1
            print(f"  ROTTO {nome}: {type(errore).__name__}: {errore}")
        finally:
            schermata.deleteLater()

    if rotti:
        print(f"\n{rotti} schermate non si costruiscono")
        return True

    print(f"\nTutto bene: {len(controlli)} schermate si costruiscono.")
    return True


def _copia_dati_in_sospeso() -> None:
    """Se le Impostazioni hanno chiesto di spostare o importare i dati, si fa ora."""
    from Utility.Structures import Paths as modulo_paths

    origine = modulo_paths.copia_in_sospeso()
    if origine is None:
        return
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

    verbo = "Sposto" if modulo_paths._leggi_config().get("sposta") else "Copio"
    attesa = QProgressDialog(f"{verbo} i dati da\n{origine}\nin\n{modulo_paths.Paths.root}",
                             None, 0, 100)
    attesa.setWindowTitle("JW LibriX")
    attesa.setWindowModality(Qt.WindowModality.ApplicationModal)
    attesa.setMinimumDuration(0)
    attesa.show()

    def avanza(fatti: int, totale: int) -> None:
        attesa.setMaximum(totale)
        attesa.setValue(fatti)
        QApplication.processEvents()

    errore = modulo_paths.esegui_copia_in_sospeso(avanza)
    attesa.close()
    if errore:
        QMessageBox.warning(None, "JW LibriX", errore)
    print(f"Dati copiati da {origine} ✅" if not errore else f"⚠️  {errore}")


def main() -> int:
    # LA DIAGNOSTICA DI QT, CHIUSA PRIMA DI TUTTO
    # -------------------------------------------
    # Il filtro qui sotto stava DOPO `_opzioni()`, quindi valeva solo per la
    # finestra.  Ma `--verifica` costruisce anch'esso le schermate, e li' la
    # riga di FFmpeg usciva:
    #
    #     qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version n9.0.2
    #
    # Una riga che arriva a ogni avvio, per un controllo che non sta
    # guardando nessun video.  La regola vale da quando Qt parte, quindi va
    # messa **prima** di qualunque cosa, e non nel ramo della finestra.
    from PyQt6.QtCore import QLoggingCategory

    for _categoria in ("qt.multimedia", "qt.multimedia.ffmpeg"):
        QLoggingCategory.setFilterRules(f"{_categoria}.debug=false\n"
                                         f"{_categoria}.info=false\n"
                                         f"{_categoria}.warning=false")

    if _opzioni(sys.argv[1:]):
        return 0

    # QtWebEngineWidgets va importato PRIMA di creare la QApplication.
    # Se arriva dopo, QtWebEngine non funziona e dice:
    #     "QtWebEngineWidgets must be imported or Qt.AA_ShareOpenGLContexts
    #      must be set before a QCoreApplication instance is created"
    # Il messaggio e' giusto ma lontano dalla causa: per questo l'import e'
    # qui, in cima, esplicito, e non lasciato al caso dell'ordine in cui
    # finiscono per essere importati i moduli.
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (deve stare qui)

    # La diagnostica di Qt era gia' chiusa sopra, prima di `_opzioni`: qui il
    # filtro esiste gia', e questo blocco ne spiega il perche'.  Sta commentato
    # perche' spostarlo piu' in alto e' stato un cambio, e il testo vale piu'
    # di una riga di spiegazione.
    #
    # Al primo video che parte Qt scriveva tutto quello che sapeva del file:
    #
    #     [mov,mp4,m4a,3gp,3g2,mj2 @ 0x...] stream 0, timescale not set
    #     Input #0, mov,mp4,m4a..., from 'https://cfp2.jw-cdn.org/...'
    #       Metadata:
    #         major_brand : isom
    #         title        : Ama il ministero | Amichevoli e pronti...
    #       Duration: 00:05:06.85
    #       Stream #0:0: Video: h264 ..., 1280x720
    #       Stream #0:1: Audio: aac ..., 48000 Hz, stereo
    #     qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version n9.0.2
    #
    # Sono dodici-quindici righe **per ogni video**, scritte sul terminale
    # mentre l'utente guarda il video che ha appena avviato.  E' la
    # diagnostica di FFmpeg, non un errore: ma sta dove si leggono gli
    # errori, quindi ogni messaggio vero del programma finisce sotto e non si
    # vede piu'.
    #
    # `qt.multimedia` e' la categoria che Qt usa per il lettore, e dentro c'e'
    # anche la sotto-categoria `ffmpeg` che e' la piu' rumorosa.  Si spengono
    # tutte e due **perche'**: quando qualcosa non va nel video, l'utente
    # vede che il video non parte e avvisa, e in quel momento il messaggio
    # c'e'.  Non serve tenere acceso un rumore che copre gli errori veri.
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from SidebarView import SidebarView

    applicazione = QApplication(sys.argv)

    # LA COPIA DEI DATI CHIESTA DALLE IMPOSTAZIONI
    # --------------------------------------------
    # Qui, prima di `Messaggi.installa()` (che apre il log) e prima di
    # qualunque database: copiare un database aperto lo puo' rovinare.
    _copia_dati_in_sospeso()

    # Si decide ADESSO se chiedere la cartella dati: dopo, il primo
    # scaricamento ha gia' creato quella predefinita (vedi `da_chiedere`).
    from SubViews import SceltaCartellaDati
    SceltaCartellaDati.serve()
    from Utility import Rete
    Rete.blocca(SceltaCartellaDati.serve())

    # Un gestore dei messaggi di Qt e delle eccezioni non gestite.
    #
    # Senza, un'eccezione dentro un callback Qt chiama qFatal e muore
    # l'applicazione SENZA dire il motivo: sul terminale resta
    # "Fatal Python error: Aborted" e un traceback del main thread che
    # punta a `exec()`.  Il motivo vero non compare da nessuna parte, e il
    # posto dove si e' rotto e' spesso lontano dal posto stampato.
    #
    # Va installato dopo `QApplication` e prima di `exec()`: dentro Qt il
    # primo arriva presto e l'ultimo tardi, e non tornano indietro.
    from Utility import Messaggi
    Messaggi.installa()

    applicazione.setApplicationName("JW LibriX")
    applicazione.setApplicationDisplayName("JW LibriX")
    applicazione.setOrganizationName("JWLibrary")

    # Il font e il foglio di stile vengono dal modulo del tema, non da qui.
    #
    # Qui prima c'era un foglio di stile scritto a mano, con dentro i
    # pulsanti e le liste.  Non funzionava piu': SidebarView._applica_tema()
    # chiama applicazione.setStyleSheet() e SOSTITUISCE quello che c'era,
    # quindi tutto quel testo veniva buttato via al primo cambio di tema.
    #
    # Due posti che scrivono lo stesso foglio di stile è la causa classica
    # di "cambio il colore e non cambia niente".
    from Utility import tema
    tema.applica_font(applicazione, tema.tema_salvato())
    applicazione.setStyleSheet(tema.foglio_stile(tema.tema_salvato()))

    # L'ICONA
    # --------
    # Gli stessi PNG che `installa.sh` mette in `icons/hicolor`, presi dal
    # progetto: cosi' l'icona e' la stessa installata o no, e non dipende da
    # quello che c'e' nella home dell'utente.
    #
    # Tutte e sette, non una sola: un `QIcon` puo' tenere piu' misure e il
    # gestore delle finestre prende la piu' adatta a quella che deve
    # disegnare.  Con una sola misura il 1024 finisce ridimensionato a 24
    # pixel e si vede che e' stato ridimensionato; con tutte e sette prende il
    # 32 o il 64 ed e' nitido.
    applicazione.setWindowIcon(_icona_multipla())
    # LA VOCE DI MENU
    # ----------------
    # Il **nome** della voce quando e' installata, e niente quando non lo e'.
    # Il percorso di una voce temporanea **non** si puo' usare: vedi la nota
    # lunga di `_voce_da_usare`, che spiega il tentativo e perche' e' tornato
    # indietro — faceva pendere l'avvio del programma.
    applicazione.setDesktopFileName(_voce_da_usare())

    # IL LOG DI AVVIO E' GIA' IN `Messaggi`
    # --------------------------------------
    # Qui prima c'era un `logging.Handler` montato a mano, che teneva i
    # WARNING e gli ERROR per mostrarli nella schermata.  Non serve piu': le
    # righe che servono sono gia' in `Messaggi.ULTIMI`, perche' `_stampa` ce le
    # mette e le mette **tutte** — anche quelle che passano dal ciclo di eventi,
    # che il logging di Python non vede.
    #
    # Due strade per lo stesso dato sono due posti in cui puo' finire la
    # copia sbagliata: una finestra che mostra gli errori presi dal logging e
    # non quelli presi dal ciclo di eventi mostra solo una parte di quello che
    # e' andato storto, e la parte che manca e' quasi sempre quella che
    # serve.

    # LA SCHERMATA DI AVVIO: IL TERMINALE NASCOSTO
    # -------------------------------------------
    # Si mostra **prima** della finestra principale e fa il lavoro dell'avvio:
    # prende i cataloghi se l'utente ha chiesto che siano presi da soli, e se
    # qualcosa e' andato storto mostra gli errori e permette di salvarli.
    #
    # Perche' qui e non dentro la finestra: la finestra principale si apre per
    # essere guardata, e metterci davanti 58 megabyte di catalogo significa
    # far aspettare l'utente su una schermata che non ha ancora scelto e non
    # contiene niente di suo.  Qui invece c'e' solo il logo, ed e' li' che si
    # mette un'attesa che non e' un'attesa ma e' lavoro.
    from SidebarView import SidebarView, _SplashScreen
    from Utility import Aggiornamenti, Messaggi

    splash = _SplashScreen()
    # Non `ULTIMI`: contiene anche `DEBUG` e `INFO`, che sono messaggi come
    # gli altri.  Con quelli dentro, la schermata degli errori si aprirebbe a
    # ogni avvio — e una schermata che si apre sempre non viene piu' letta.
    #
    # `problemi()` e non `problemi_bloccanti()`: qui si danno alla schermata
    # **tutti** i problemi perche' li mostri, e poi e' lei a decidere se fermare
    # il programma o no, guardando i livelli.  Passarle gia' filtrati sarebbe
    # decidere qui una cosa che dipende da come sono andate le cose: l'errore
    # che blocca potrebbe anche arrivare **dopo** questa riga, e li' non ci
    # sarebbe piu' nessuno a fermarlo.
    splash.imposta_errori_log(Messaggi.problemi())
    # Auto-update se l'impostazione e' accesa.  Spenta, la schermata fa
    # comunque un giro di eventi e chiude: il tempo che serve a disegnarla non
    # e' un tempo che si aspetta, e' il tempo di un'immagine.
    #
    # IL PRIMO AVVIO PRENDE IL CATALOGO ANCHE CON L'AUTOMATICO SPENTO
    # ---------------------------------------------------------------
    # Con la cartella dati vuota `catalog.db` non c'e', e senza catalogo la
    # Biblioteca e' vuota e la Home non sa nemmeno quale pacchetto contiene
    # le Scritture del giorno: diceva «sul server non c'e' l'edizione di
    # quest'anno», che era falso.  L'impostazione decide gli aggiornamenti,
    # non se l'app ha il minimo per funzionare.  Dal secondo avvio il catalogo
    # c'e' e torna a valere solo la casella.
    #
    # L'ORDINE DEL PRIMISSIMO AVVIO: CARTELLA, CATALOGO, BACKUP
    # ---------------------------------------------------------
    # Finche' l'utente non ha detto dove salvare i dati, non si scarica
    # niente: il catalogo finirebbe nel posto sbagliato.  La Home resta vuota
    # e chiede «Dove salvo i dati?»; dopo la risposta l'app si riavvia, e
    # solo allora la schermata scarica il catalogo.  Il backup si chiede
    # per ultimo, quando il catalogo c'e'.
    from SubViews import SceltaCartellaDati
    primo_avvio = (Aggiornamenti._file_catalogo() is None
                   and not SceltaCartellaDati.serve())
    splash.imposta_auto_update(Aggiornamenti.automatici() or primo_avvio)

    # LA CHIUSURA: LA FINESTRA PRENDE IL POSTO DELLA SCHERMATA
    # --------------------------------------------------------
    # Stessa finestra, non una nuova che si apre sopra: aprire una finestra e
    # chiuderne un'altra fa lampeggiare il gestore di finestre, e su alcuni
    # sistemi fa salire e scendere l'icona nella barra delle applicazioni.
    # DUE LAVORI, UNA SOLA USCITA
    # ---------------------------
    # La schermata fa due cose che non hanno la stessa durata: prende i
    # cataloghi se l'utente ha chiesto che siano presi da soli, e i controlli
    # dell'avvio.  Prima erano due tempi separati — i controlli giravano in un
    # processo **prima** dell'app, e finivano prima ancora che la schermata
    # esistesse — e adesso sono due lavori insieme dentro la stessa finestra.
    #
    # La finestra principale si apre quando sono finiti **entrambi**, e non
    # quando arriva il primo che capita: altrimenti si aprirebbe sopra una
    # schermata che sta ancora lavorando, o resterebbe chiusa perche' la
    # schermata aveva finito per prima e nessuno l'aveva notato.
    #
    # `_controlli` parte subito e il primo giro di eventi arriva prima che la
    # schermata abbia finito: e' il caso normale, e va bene.
    stato = {"controlli": None, "splash": None, "aperta": False}

    def _apri_ora() -> None:
        if stato["aperta"]:
            return
        if stato["controlli"] is None or stato["splash"] is None:
            return
        if not stato["controlli"] or not stato["splash"]:
            applicazione.quit()
            return
        stato["aperta"] = True
        splash.hide()
        splash.deleteLater()
        # Mostra finestra principale con fade-in
        finestra.show()
        # Fade-in semplice: da trasparente a opaco
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        effect = QGraphicsOpacityEffect(finestra)
        finestra.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        # Mantieni riferimento per non far garbage-collectare l'animazione
        finestra._fade_anim = anim
        QTimer.singleShot(900, finestra.prepara_in_anticipo)

    def _splash_finita(ok: bool, errori: list) -> None:
        stato["splash"] = (ok, errori)
        _apri_ora()

    splash.finito.connect(_splash_finita)

    # LA SCHERMATA PARTE PRIMA DI TUTTO
    # ----------------------------------
    # `start()` mostra la finestra, fa un giro di eventi per disegnarla e poi si
    # mette in ascolto del log.  Chiamato qui, e non dopo la costruzione della
    # finestra principale, l'utente vede il logo a un paio di decimi di secondo
    # invece che a tre secondi.
    #
    # `_apri_ora` aspetta i due lavori, quindi far partire la schermata per
    # prima non cambia l'ordine in cui si apre la finestra: cambia solo quando
    # l'utente comincia a vedere qualcosa.
    splash.start()

    # La finestra si costruisce qui, e i tre secondi che ci vogliono sono con la
    # schermata gia' a schermo.  Non si mostra: la mostra `_apri_ora`.
    # LA FINESTRA PRINCIPALE, NASCOSTA
    # --------------------------------
    # Si costruisce **dopo** che la schermata e' a schermo, e non si mostra.
    #
    # Prima era il contrario — la finestra prima della schermata — e sembrava la
    # cosa furba: il tempo in cui la schermata lavora e' anche il tempo in cui
    # la finestra si prepara, cosi' il tempo non si somma.  Il conto e' giusto e
    # la conclusione no: costruire la finestra **blocca**, quindi durante quei
    # tre secondi non si ridisegna niente, e la schermata che non e' ancora stata
    # mostrata non la vede nessuno.  Misurato: la schermata compariva a 3,19 s,
    # cioe' quando la finestra era gia' pronta — l'unica cosa che l'utente
    # vedeva in quei tre secondi era il vuoto.
    #
    # Adesso la schermata parte prima e la finestra si prepara **dietro**.  Il
    # tempo totale non cambia di un millisecondo, ma quei tre secondi sono con
    # qualcosa davanti invece che con niente.
    #
    # Pero' la schermata si disegna solo se la grafica ha un giro libero: senza
    # `processEvents` qui sotto la finestra veniva costruita (1,3 s) con la
    # schermata a meta', e sembrava inceppata.
    splash.imposta_stato("Costruisco la finestra")
    applicazione.processEvents()
    finestra = SidebarView()
    finestra.resize(1100, 750)
    # L'icona anche sulla finestra, non solo sull'applicazione.
    #
    # Sono due cose diverse: `applicazione.setWindowIcon` e' l'icona che
    # eredita ogni finestra che non ne ha una sua, e la finestra principale non
    # ne ha una sua — quindi senza questa riga prenderebbe quella di li' e
    # andrebbe bene.  Ma e' una riga sola e rende la cosa **detta**: se un
    # domani la finestra riceve un'icona diversa, il posto in cui succede si
    # vede, invece di doverlo andare a cercare.
    #
    # E' la stessa icona a piu' misure, non il 256 fisso di prima: la barra
    # delle applicazioni chiede 24 o 32 pixel e prende la piu' vicina.
    finestra.setWindowIcon(_icona_multipla())
    finestra.setVisible(False)  # nascosta finché splash non finisce



    # I CONTROLLI, DENTRO L'APP E DOPO LA SCHERMATA
    # ----------------------------------------------
    # `JWL_SENZA_CONTROLLO=1` li salta: e' la via d'uscita gia' dichiarata per
    # quando i controlli sono il problema e non il player.
    #
    # Prima giravano fuori dal programma, e questo e' l'unico posto dove si
    # decide che il terminale non deve piu' aspettare: senza finestra, un
    # quattordicesimo secondo di attesa non si distingue da un programmo che non
    # e' partito.
    if os.environ.get("JWL_SENZA_CONTROLLO"):
        stato["controlli"] = True
        _apri_ora()
    else:
        def _controlli_finiti(ok: bool, motivo: str) -> None:
            stato["controlli"] = ok
            if motivo:
                # Il motivo va in **due** posti: la schermata, perche' e' li'
                # che l'utente guarda, e il log, perche' `print` passa gia' da
                # `Messaggi` e finisce anche nel terminale.  Una riga sola nei
                # due posti significa che uno dei due mostra meta' della
                # spiegazione.
                print(motivo)
                splash.imposta_stato(motivo)
            _apri_ora()

        _controlli_avvio(splash, _controlli_finiti)

    return applicazione.exec()


if __name__ == "__main__":
    sys.exit(main())