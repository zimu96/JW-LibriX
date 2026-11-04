# JW LibriX

Porting a Linux del progetto `JW-Library-macOS` di Dario Ragusa (MIT).
Python + PyQt6 + QtWebEngine, niente altro da installare.

Questo file dice tre cose: **come si avvia**, **come è fatto il porting**, e
**come si costruisce un `.jwpub` da soli**.

Le lezioni sono scritte **dentro i file**, dove servono. Qui ci sono solo
quello che non sta in nessun altro posto.

---

## 1. Avviare

```bash
./jw.sh                     # avvia l'app dal terminale
./installa.sh               # facoltativo: icona, voce nel menu, comando jwlibrix
python3 JWLibraryApp.py     # come jw.sh, senza lo script
```

`jw.sh` apre l'app **subito**: i controlli veloci (ambiente, moduli, server,
~0,1 s) girano dentro la schermata di avvio, non prima. Variabili utili:

| | |
|---|---|
| `JWL_VERIFICA=1 ./jw.sh` | solo i controlli, poi esce (il codice di uscita dice se parte) |
| `JWL_CONTROLLO_COMPLETO=1 ./jw.sh` | all'avvio anche i controlli pesanti (~7 s) |
| `JWL_SENZA_CONTROLLO=1 ./jw.sh` | nessun controllo |
| `JW_MISURA=1 ./jw.sh` | stampa i tempi |

```bash
python3 JWLibraryApp.py --verifica   # controlla tutto, non apre nulla
python3 JWLibraryApp.py --dati       # dice dove stanno i dati
```

`installa.sh` serve **solo** per avere l'app nel menu delle applicazioni:
copia l'icona in 7 misure in `~/.local/share/icons/hicolor/`, mette
`JWLibriX.desktop` in `~/.local/share/applications/` e crea il comando
`jwlibrix` in `~/.local/bin/`. Senza, il programma parte lo stesso con `./jw.sh`.

Dipendenze: PyQt6 e QtWebEngine, il resto è libreria standard. Nessun `pip`.

**Opzionali, per «Aggiungi file» nei contenuti delle adunanze** (il programma parte e funziona senza):

- **PDF**: serve *uno* fra PyMuPDF (`pip install pymupdf`), QtPdf (pacchetto Qt del sistema) o poppler
  (`poppler-utils` su Debian/Ubuntu, `poppler` su Arch e con `brew` su macOS). Il primo trovato viene usato.
- **Word, Excel, LibreOffice**: serve [LibreOffice](https://www.libreoffice.org), che li converte in PDF.
- Immagini, video e audio non richiedono niente in più: dipendono dai formati che Qt sa leggere sul tuo sistema.

Se manca qualcosa, il visore lo dice a schermo e indica cosa installare.

```bash
sudo pacman -S python python-pyqt6 python-pyqt6-webengine    # Arch
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine      # Debian/Ubuntu
sudo dnf install python3-pyqt6 python3-qt6webengine           # Fedora
```

**SPLASH SCREEN ALL'AVVIO — è un terminale con sopra il logo**

Quando l'app parte appare una schermata nera **senza il contorno della finestra
di sistema**, con il logo e una barra. Sotto il pannello del logo c'è il testo
del terminale: è lo stesso log che andrebbe a schermo, e non si vede perché il
logo ci passa sopra.

1. Si mostra e si disegna subito (un giro di eventi, non un'attesa)
2. Il terminale viene deviato dentro la schermata: ogni riga che il programma
   scrive va **al terminale vero e alla schermata** — non è una scelta fra le
   due cose
3. Se auto-update è attivo (Impostazioni > Aggiornamenti): controlla il server
   in un thread e scarica catalogo pubblicazioni + elenco media insieme,
   aspettando **tutti e due** prima di chiudersi
4. Se ci sono errori: finestra con i dettagli e «Salva log» in TXT o JSON
5. Chiude con fade-in 300ms verso Home (stessa finestra, non close/open nuova)

**Nessun tempo minimo**: la schermata non è una pausa con dentro un logo, è il
lavoro. Finisce quando ha finito.

**La X in alto a destra chiude il programma**, non la schermata. Sta dentro la
finestra perché il bordo di sistema non c'è. Serve a interrompere un
aggiornamento partito per caso.

### Se il programma è rotto, la schermata si ferma

Un errore vero durante l'avvio blocca tutto **immediatamente**. Non è una
finestra di dialogo sopra: è **la stessa schermata** che cambia faccia —
sparisce il logo, il log si vede per intero e si può selezionare e copiare, e
in fondo compaiono la frase e i bottoni:

```
C'è 1 errore che impedisce al programma di partire.
Sopra c'è tutto quello che è stato scritto. Salvalo e mandalo a chi sviluppa.

[ Salva con nome... ]  [ Esci ]
```

La finestra principale **non parte**: andare avanti a metà di un crash vuol
dire che il difetto si vede tre schermate dopo, quando non si sa più cosa
l'ha causato. Vale anche per un crash avvenuto *prima* della schermata, durante
gli import e la costruzione della finestra.

**Quali errori fermano, e quali no:**

| | |
|---|---|
| **fermano** | `CRITICO`, `FATALE`, eccezioni non gestite |
| **non fermano** | `AVVISO` — si vedono, ma il programma parte |

Un `AVVISO` non blocca perché su questa macchina Qt ne scrive uno a ogni avvio
che non ha niente a che fare col programma
(`This plugin does not support propagateSizeHints()`). Bloccare su un avviso
vuo dire che il programma non parte più su quelle macchine. Gli avvisi si
vedono lo stesso e c'è «Ignora e parti», che non esiste quando l'errore
blocca davvero.

**«Salva con nome...»** apre la finestra di salvataggio di sistema e salva
**tutto** il log, non solo gli errori: in un crash la causa non è quasi mai
l'ultima riga. In TXT il testo come lo leggi a schermo, in JSON i messaggi
**coi livelli** accanto. Dopo aver salvato la schermata resta lì.

L'icona usata è `Files/JWLibrary.png` (fallback `Files/icons/1024.png`).

---

## 1 bis. Le sezioni dell'app

La finestra ha tre parti: la **rail** (colonna viola di icone a sinistra), la
**fascia** (barra viola in alto) e il contenuto. In fondo, quando serve, la
riga degli scaricamenti e il mini player.

### La rail, dall'alto in basso

| Sezione | Cosa c'è dentro |
|---|---|
| **Home** | testo del giorno, Argomento principale, Preferiti, Notizie, Novità e aggiornamenti (con «Scarica»), Novità, Kit dell'insegnante, Le ultime novità |
| **Bibbia** | i 66 libri, i capitoli, il testo; scelta della lingua della Bibbia, pannello dei riferimenti |
| **Biblioteca Digitale** | quattro schede: **Pubblicazioni** (catalogo con ricerca e copertine), **Video**, **Audio**, **Scaricati** (cosa c'è sul disco e come toglierlo) |
| **Adunanze** | la settimana in corso: Vita cristiana e ministero (`mwb`) e Studio della Torre di Guardia (`w`), con i contenuti multimediali di ogni pagina in ordine e «Aggiungi file» (PDF, Word, immagini, video, audio) |
| **Ricerche** | Sottolineature, Segnalibri, Appunti (arrivano dal backup del telefono) e le **Playlist** |
| **Impostazioni** | otto schede, vedi sotto |
| **Timer** | compare solo se il plugin timer è installato **e** acceso |

### La fascia

`<` `>` indietro e avanti · **lingua** · **lente** (cerca nella pubblicazione
aperta o ovunque) · **cuffie** (menu adattivo: streaming, scarica, cambia
lingua) · **aggiorna** · **segnalibri** · **tre puntini** (dimensione del
testo). Nella Home c'è solo «aggiorna»; segnalibri e cuffie compaiono mentre
si legge un capitolo.

### Le Impostazioni

| Scheda | Cosa |
|---|---|
| Generale | lingua |
| Ascolto e video | qualità streaming, scarica in Wi-Fi, schermo per video e immagini, duplicazione monitor |
| Backup | importa un `.jwlibrary` (dal telefono), esporta in una cartella, condividi, elimina |
| Spazio | spazio usato, ultimo aggiornamento |
| Aggiornamenti | «Offline» (nessun accesso alla rete), «Aggiorna il catalogo adesso» |
| Log | vedi e salva il log dell'avvio |
| Aspetto | tema chiaro / scuro |
| Plugin | acceso / spento del Timer adunanze, con la versione installata |

### Il player e gli schermi esterni

Video e audio si aprono nel lettore grande dentro l'app; chiudendolo resta il
mini player in fondo. Con uno o più monitor esterni scelti nelle Impostazioni,
il video e le immagini escono anche lì (una sola decodifica, copie dello stesso
fotogramma); quando non c'è niente lo schermo esterno mostra la Scrittura
dell'anno. La X torna sempre alla sezione da cui il media era partito.

### Il plugin Timer

Un pezzo a parte, **facoltativo**: l'app funziona identica con o senza. Sta in
`plugin/timer/` (basato su OnTime Meeting Timer 1.0.9, MIT) e si riconosce da
`plugin/timer/plugin.json`. È un repository a parte (`jw-librix-timer`): per
usarlo si copia il suo contenuto in `plugin/timer/` (nome, titolo, versione, file di entrata). Se c'è
e nelle Impostazioni è acceso, nella rail compare il tasto con l'orologio. Il
codice che lo carica è `Utility/Plugin.py`.

---



## 2. Modificare e rivedere subito

Il ciclo è: modifica il file, riavvia, guarda.

- **Python**: riavvia e basta, non c'è compilazione.
- **`Files/style.css`** e **`Files/script.js`**: non devi copiarli da nessuna
  parte. `Stuff.add_base_files()` li rimette nella cartella dati **a ogni
  avvio**, quindi l'icona di reload del browser prende subito il file nuovo.
  Se non fosse così, ogni modifica al CSS richiederebbe una copia manuale e
  il risultato sarebbe controllare la versione vecchia e non capire perché.

### Se tocchi il player: `./prove/prove.sh` prima di tutto

> In questa build pulita `prove/` e `controllo.py` non ci sono: stanno nella
> cartella di sviluppo. Senza `prove/` i controlli completi le saltano e lo dicono.

Sei cose del player sono **bloccate da una prova**, perché sono già
tornate indietro più volte e nessuna delle cinque dà un errore se va storto:

1. **Mini player.** La striscia in fondo sparisce quando il lettore grande è
   aperto — due lettori per lo stesso video non vanno — e torna quando l'utente
   preme la freccia giù **o cambia sezione dal menu laterale**. Il cambio
   sezione fa esattamente il gesto della freccia giù, prima di andare nella
   sezione scelta.
2. **Monitor esterni.** Con un monitor esterno acceso il video si vede
   **anche dentro l'app**, sul primo schermo, oltre che sull'esterno: con uno,
   due o tre schermi esterni. E resta una sola decodifica: il video esce
   sull'esterno e gli altri posti, player interno compreso, sono copie dello
   stesso fotogramma.
3. **La X.** Chiudendo un media si torna **da dove quel media è partito**:
   dalla Home si torna alla Home, da Adunanze si torna ad Adunanze, dalla
   sezione Multimedia si resta nei Multimedia. Vale anche se nel frattempo
   sei passato da altre sezioni — è quello che serve durante un adunanze,
   dove si parte un video, si torna indietro e se ne parte un altro.
4. **Gli schermi esterni si accendono tutti, al primo colpo.** All'avvio
   partono tutte le finestre configurate — seconda, terza, quarta, compresi i
   duplicati — senza che l'utente debba andare nelle impostazioni a togliere e
   rimettere la spunta. Vale anche per uno schermo che compare dopo l'avvio,
   che è la strada che prende uno schermo virtuale.
5. **La riga sotto il video elenca tutti gli schermi che lo mostrano**, non
   solo il secondo: con tre monitor accesi deve scrivere «su DP-1, DP-2 e
   VGA-1», altrimenti sembra che gli altri non siano accesi.
6. **L'icona è su tutte le finestre, a tutte e sette le misure** — la finestra
   principale e tutte quelle dei monitor esterni — lanciando da `jw.sh` come
   da installato.

   Quello che **non** si può fare, e che è stato provato: dichiarare a Qt il
   percorso di una voce `.desktop` temporanea per avere l'icona senza
   installare niente. Il Qt accetta il percorso, ma il portale del desktop va
   a cercare quel file, non lo trova, e **l'avvio del programma resta fermo**:
   la finestra non compare. La nota lunga di `_voce_da_usare` in
   `JWLibraryApp.py` dice perché, e cosa non si deve rifare.

   Sulla barra delle applicazioni l'icona la vedi **solo dopo `./installa.sh`**,
   perché KDE Plasma la cerca dentro la voce di menu, non sulla finestra. Non
   è un difetto e non si aggira: è come funziona il desktop.

```
./prove/prove.sh
```

Le sei prove girano con la finestra costruita fuori schermo, senza rete e
senza toccare i tuoi dati: circa quattro secondi in tutto.

Le stesse sei girano anche dentro l'app con `JWL_CONTROLLO_COMPLETO=1` o
`JWL_VERIFICA=1` (`_verifica_prove` in `JWLibraryApp.py` lancia i file di
`prove/`). Se una è rotta **il programma non parte**: un player che si
comporta male senza dirlo è peggio di uno che non parte. All'avvio normale
girano solo i controlli veloci. Per saltarli tutti:

```
JWL_SENZA_CONTROLLO=1 ./jw.sh
```

I dati stanno in `jw-librix/dati/`. Con `JWL_HOME=/percorso` ne scegli un
altro, utile per tenere due profili separati.

---

## 3. Il porting, in breve

`WKWebView` è WebKit, che è di Apple: su Linux non c'è. Al suo posto c'è
Chromium, che Qt espone come `QWebEngineView`. Non è la stessa cosa, ma è la
stessa posizione.

| Swift | Python |
|---|---|
| `WKWebView` | `QWebEngineView` |
| `loadHTMLString(p, baseURL: nil)` | `setHtml(p)` |
| `evaluateJavaScript(c) { ... }` | `run(c, callback)` |
| `webView(_:didFinish:)` | `page.loadFinished` |
| `WKScriptMessageHandler` | `QWebChannel` |
| `NSSavePanel` / `NSOpenPanel` | `QFileDialog` |
| `NSImage` | `QPixmap` |
| `DispatchQueue.global { }` | `threading.Thread` + segnale |
| `Color(NSColor.controlBackgroundColor)` | palette, ruolo `Base` |
| `Archive(url:accessMode:)` | `zipfile` |
| `Data.gunzipped()` | `gzip` |
| `sqlite3_open` / `sqlite3_prepare_v2` | modulo `sqlite3` |
| `Image(systemName: "house.fill")` | glifo da `Stuff.SF_SYMBOLS` |
| `@State` | attributo + `Signal` |
| `NavigationLink` | `QStackedWidget` + pila di indici |

**36 file Swift → 36 file Python**, stesso nome, stessa cartella.
3.031 righe Swift → 6.600 righe Python. Quasi tutto il di più è commento:
l'originale non spiega le trappole, questo le registra sul posto.

### Le cartelle che non sono state portate, e perché

**`JWLibrary/Zip/`** — 11 file, 2.481 righe. Non è logica di JW Library, è una
libreria di terzi che l'autore aveva messo dentro perché Swift non aveva niente
per gli ZIP nella libreria standard.

| dentro `Zip/` | Python | usato da |
|---|---|---|
| `ZIPFoundation/` (9 file, MIT) | `zipfile` | `BackupManager` righe 28, 109 |
| `CZLib/` (shim C per zlib) | — | solo `Data+Gzip` |
| `Data+Gzip.swift` (`gunzipped()`) | `gzip` | `FileDownloader` riga 56 |

In tutto il progetto originale queste librerie erano chiamate da **tre** punti,
tutti e tre sostituiti. E un quarto pezzo: `import SQLite3` → modulo `sqlite3`.

**`JWLibrary/Assets.xcassets/`** — è un contenitore di Xcode, non ha significato
fuori da Xcode. Dentro c'era una sola cosa che conta: le PNG dell'icona, e
quelle sono state prese (7 misure, `Files/icons/`). Il resto del contenuto non
era niente da portare, e una cosa diceva anche il contrario:

- `AccentColor.colorset/Contents.json` è **vuoto**: dichiara un colore e non
  dice quale.
- i file `Icon-257.png` e `Icon-513.png` sono le versioni 2× di 256 e 512.

La conseguenza di `AccentColor` vuoto è che **il viola dell'app non è mai stato
preso da lì**, e chi lo cerca lì non trova niente. Campionando l'icona vera
(`Icon-1024.png`, 548.655 pixel su 1.048.576) esce **`#64398b`**, non
`#5b3c88`. La regola scritta nei documenti dell'originale è proprio «il viola si
campiona dagli asset originali, non si indovina»: dagli asset originali esce
`#64398b`. Il valore è in `Utility/Stuff.py`, costante `ACCENTO`.

**`Info.plist`** → non si porta: diventa la voce di menu (`JWLibriX.desktop`).

---

## 4. `Files/script.js` è byte-identico

È la cosa più importante del porting. Il JavaScript che fa la parte difficile —
sottolineature parola per parola, riconoscimento dei paragrafi, divisione del
testo in pezzi selezionabili — è già scritto, è provato, e funziona
sull'originale. Riscriverlo significa perdere tutte le prove che l'originale
funziona.

Quindi non è stato toccato:

```
$ diff Files/script.js .../JW-Library-macOS-main/JWLibrary/Files/script.js
script.js: IDENTICO all'originale
```

Il problema è che quel file chiama `window.webkit.messageHandlers`, e `webkit`
è di WebKit. Invece di toccare `script.js`, si inietta prima di tutto il resto
un oggetto con lo stesso nome che fa la stessa cosa:

```js
window.webkit.messageHandlers.toggleMessageHandler.postMessage = function (p) {
  window.jwlBridge.received(JSON.stringify(p));
};
```

**`Files/style.css`** è l'unico file di testo cambiato, in due righe:
`font-family: -apple-system` non esiste su Linux. `-apple-system` resta primo,
così il file va bene anche su macOS, e dopo ci sono i font di sistema Linux.

---

## 5. I difetti del progetto originale che sono stati corretti

Non sono riscritture: sono cose che nel codice Swift non potevano funzionare.

### `JWPubExtractor`: l'algoritmo era sbagliato

L'originale mescolava i BLOB in stringhe di numeri (`"128 130 255 ..."`) e li
confrontava con `starts(with: "128")`. Su una parola che comincia con `"120"`
il confronto è falso; su una che comincia con `"1280"` è vero per sbaglio. Poi
`Int(rem)!` forza lo sconfezionamento di un valore che potrebbe non essere un
numero, e l'indice veniva mutilato con `removeFirst` mentre il ciclo lo leggeva.

Qui i BLOB restano byte e vale la regola documentata nel progetto originale.
**Verificata** sul pacchetto vero più duro:

```
yb88_I.jwpub:  8712/8730 parole tornano = 99,79%, 60.600 occorrenze
```

I 18 che non tornano sono **esattamente** i 18 che quei documenti indicano. Non
è una coincidenza: è la prova che la formula è quella giusta.

Una cosa che quei documenti non dicevano, emersa misurando:
**`PositionalList` non è una posizione per occorrenza, sono due byte.** Su
`yb88_I.jwpub` la parola `costruita` ha 9 occorrenze e 20 byte. Leggendo un byte
per occorrenza le posizioni vengono disallineate di mezzo byte.

### `BibleView`: la scrittura fuori posto

L'originale scriveva dentro `@State downloadProgress` da dentro il ciclo che gira
in background: 1.189 righe scaricate, tutte scrivendo nella stessa variabile di
stato da un thread che non è quello della grafica.

Qui il lavoro gira in un thread e l'avanzamento torna con un segnale. Stesso
lavoro, stesso ordine, stessa quantità di richieste.

### Difetti nati nel porting, non nel progetto originale

Quelli qui sopra venivano dal codice Swift. Questi sono nati qui, e sono
un'altra cosa: non sono un algorithm sbagliato, sono un pulsante non
collegato, un ciclo di rete sul thread sbagliato e una lista scritta a mano
che non poteva crescere. Non li correggeva nessuna riga dell'originale,
perché l'originale non li aveva.

### Il pulsante «Scarica» della sezione Novità non faceva niente

La sezione Novità è dentro la Home e i suoi segnali venivano rilanciati con
un ciclo che chiedeva `hasattr(self, nome)` alla classe che contiene la
sezione. Quella classe non dichiarava nessuno dei tre segnali: la condizione
era sempre falsa, il collegamento non si faceva, e il pulsante «Scarica»
non era collegato a niente.

È il difetto peggiore che possa capitare a un pulsante: c'era, era giusto,
era premibile, e premendolo non succedeva niente. Un pulsante che non dà
segni sembra un pulsante che non ha ancora finito, quindi si prova una volta,
si aspetta, e si conclude che il programma sia lento.

### La finestra si impiantava scaricando una pubblicazione

`FileDownloader` consegna le sue callback sul main thread, e da lì partiva
il ciclo che scarica i capitoli: **145 richieste una dopo l'altra** per
«Altri argomenti», 1.189 per la Bibbia. Ogni richiesta aspetta la risposta, e
l'attesa è lavoro che blocca: la finestra non rispondeva e KDE offriva di
terminarla, poi si riprendeva da sola quando il lavoro era finito.

Tre difetti uno dentro l'altro, e ognuno nascondeva il successivo:

1. il ciclo dei capitoli era sul main thread;
2. `dopo_url` accendeva la riga di scaricamento da un thread secondario, e i
   segnali sono collegati in modo diretto, quindi il metodo collegato girava
   lì;
3. la riga usava `time` senza averlo importato, e un `NameError` dentro un
   segnale Qt fa `abort()` senza lasciare una riga di traceback.

Il primo si vede dalla finestra. Il secondo e il terzo si vedono solo facendo
girare il download vero: `--verifica` costruisce le schermate e non preme
nessun pulsante, quindi passava con dieci schermate verdi e il pulsante morto.

### La sezione Novità elencava quattro sigle scritte a mano

La sezione mostrava «cosa posso scaricare», e per farlo chiedeva al server il
checksum di quattro pubblicazioni con il nome scritto a mano più i periodici
letti dal catalogo. Quattro nomi non cambiano: quando esce una pubblicazione
nuova non ne compare una di quinta, e quindi non si vede. Non è un difetto di
qualcosa che si rompe, è una lista che non può crescere.

Ora la domanda «che cosa è nuovo?» ha una risposta: il catalogo ha
`PublicationAsset.CatalogedOn`, che è il giorno esatto in cui ogni
pubblicazione è entrata. E come per tutte le altre sezioni, anche questa non
usa una lista scritta a mano.

### Il catalogo non si aggiornava mai

Il nome del file che arriva dal server è sempre `catalog.db.gz`, e
`FileDownloader.load_file_async` ha questa riga:

```python
if destination.exists():
    print(f"Il file esista gia' [{destination}]")
    completion(str(destination), None)
    return
```

Con il catalogo già presente — e c'è quasi sempre — dice «sono già fatto» e
non scarica niente. Il programma non lo sapeva e scriveva «File salvato»:
sembrava un aggiornamento, era un no-op. Per questo la scritta «il catalogo
da aggiornare» non andava via mai: non era un promemoria, era la verità.

Ora il download va in un file con un altro nome, si controlla che il database
si apra, e solo allora il nuovo sostituisce il vecchio: se il download si
interrompe, il catalogo di prima resta intatto.

### Il SQL parametrizato

In Swift le query si costruivano con interpolazione di stringhe. Qui tutti i
valori viaggiano come parametri (`?`). Query identiche, risultati identici, e il
numero non viene mai interpretato come SQL.

### La riga degli scaricamenti è dentro la finestra, non sulla fascia

La fascia viola è il **bordo** della finestra, e un bordo non è il posto dove
si guarda mentre si aspetta. La riga sta in fondo, dentro, con il nome di che
cosa si sta prendendo, il conto e il tempo che manca.

Il tempo che manca è una stima e la parola è «circa», perché non può essere
diversamente: la rete cambia velocità e un file grosso è più lento di dieci
piccoli. Con zero file fatti non si scrive niente, perché il primo capitolo
può durare più di tutti gli altri e una stima fatta sul primo file sbaglia
di un ordine di grandezza.

---

## 6. Costruire un `.jwpub` da soli

File: `crea_jwpub.py`.

### Perché conviene

Un `.jwpub` scaricato da jw.org ha il corpo del testo cifrato
(`Document.Content`). L'app non lo decifra e non vuole farlo: la chiave è
dentro l'app originale e dentro i suoi dati, e non è cosa che si fa con un
materiale del quale non si è i diritti. Quello che si vuole è poter leggere.

E si può, senza la chiave: **se il pacchetto lo scrivi tu, il testo è in chiaro
perché lo scrivi tu.** Nessuna cifratura, nessuna chiave, nessun limite. Non è
un trucco: è il caso in cui non c'è niente da aggirare.

### L'uso

```bash
cat > c1.txt <<'EOF'
Il primo capitolo.

Il testo dice Geova e il Regno. Geova torna due volte.
EOF

python3 crea_jwpub.py mio.jwpub --titolo "Il mio libro" \
    --simbolo mio --anno 2026 --testo c1.txt
```

Poi il controllo, **prima** di metterlo nell'app:

```bash
python3 crea_jwpub.py --verifica mio.jwpub
```

```
simbolo     mio
titolo      Il mio libro
database    mio_I.db
copertine   0
tabelle     9 ✅
decodifica  25/25 parole tornano (100.00%), 32 occorrenze ✅

[✅] 0  c1  (copertura 1.16)
       Il primo capitolo Il testo dice Geova e il Regno Geova torna due volte
```

**Il testo torna fuori esatto.** Non "quasi": la stessa frase, parola per parola.

La prova non è un paragone con il testo originale, è una **conta**: la somma dei
conteggi per capitolo dentro `PositionalListIndex` deve tornare a
`WordOccurrenceCount`, che è scritto in chiaro nella stessa riga. Se la codifica
a 7 bit fosse sbagliata la somma non tornerebbe su nessuna riga, e non su
poche.

### Cosa scrive dentro

```
mio.jwpub                       <- ZIP
  manifest.json                 <- in chiaro, i metadati
  contents                      <- ZIP annidato
    mio_E.db                    <- SQLite, obbligatorio
```

`manifest.json` dice `publication.fileName`, e quel nome è il nome del `.db`. Se
non combacia, il pacchetto si apre e dentro non c'è niente.

Nove tabelle: `Document`, `DocumentParagraph`, `TextUnit`, `Word`,
`SearchIndexDocument`, `Multimedia`, `DocumentMultimedia`, `Publication`,
`SearchTextRangeDocument`.

`Document.Content` resta **NULL**, e non è una dimenticanza: in un pacchetto
vero quel campo è cifrato, e qui non si cifra niente perché il testo si
ricostruisce dall'indice. Lasciarlo vuoto non impedisce niente.

### Le tre regole che rompono tutto

1. `manifest.json` deve dire `fileName`, e quel nome è il nome del `.db`.
2. La tabella dell'indice è `SearchIndexDocument`, quella delle parole è `Word`.
   `SearchIndexDocument` **non** è un indice delle parole: è l'indice delle
   *occorrenze*, una riga per parola.
3. La codifica a 7 bit è `b - 128` quando `b >= 128`. **Un byte `0x80` vuol dire
   zero, non 128.**

### `PositionalList` va a coppie

Non è una posizione per occorrenza: sono **due byte**. Il primo elemento è il
numero dell'unità (del capitolo), il secondo è la posizione **dentro** quel
capitolo:

```
costruita, 20 byte:  55 163  77 165  53 166  75 233  14 234 ...
coppie:             (55,163)(77,165)(53,166)(75,233)(14,234)
posizioni:           35     37     38     105    106     <- crescono
```

Il secondo cresce dentro ogni capitolo, ed è da lì che si mettono in fila le
parole per rileggerle nell'ordine giusto.

In un pacchetto costruito qui il significato è **noto**, perché lo si scrive: è il
vantaggio di costruire il pacchetto invece di leggerlo.

### Dove metterlo

```bash
cp mio.jwpub jw-librix/dati/
```

`JWPubManager.extract_pub` fa il resto: fuori il primo ZIP, poi dentro il
secondo.

---

## 7. Il limite che resta, detto chiaro

Sui pacchetti **veri** l'ordine di lettura si recupera solo in parte.

I documenti dell'originale dicono: «nella maggior parte dei capitoli la sequenza
coincide con l'ordine di lettura e si legge come una frase». Misurando su
`yb88_I.jwpub` non è quello che si ottiene sempre:

```
unita' 6-11:  "la e' a nazione non o pagina proclamatori ..."   <- si legge
unita' 0-5:   "36 a annuario atti battente cambiate cattolici"  <- alfabetico
```

Il primo elemento della coppia in `PositionalList` è il pezzo che manca, e non
si sa cosa sia. Nessuna fonte documenta l'encoding, e `TextPositions` — che lo
avrebbe — non è mai stato decodificato.

Quindi, sui pacchetti veri:

- la **decodifica** è provata (99,79%, con la prova della somma);
- il **vocabolario** di ogni capitolo è giusto;
- l'**ordine di lettura** è indovinato, e a volte indovinato bene.

È per questo che `testo()` ritorna anche la copertura e `COPERTURA_MINIMA = 0,65`
esiste: sotto quella soglia non si mostra niente e resta il vocabolario. Meglio
il vocabolario che mezzo testo.

Sui pacchetti **costruiti con `crea_jwpub.py`** il limite non c'è, perché il
significato dei numeri l'abbiamo scritto noi. È il motivo per cui esiste.

---

## 8. I dati

| | |
|---|---|
| Cartella | `jw-librix/dati/` (accanto al programma) |
| Cambiarla | `JWL_HOME=/percorso ./jw.sh` |
| Guardarla | `python3 JWLibraryApp.py --dati` |

macOS usava `~/Documents/JWLibrary` (contenitore sandbox). Qui la radice è
calcolata da `Utility/Structures/Paths.py` (`RADICE_PROGRAMMA / "dati"`), che
è l'unico posto in cui è scritta: nell'originale il percorso compariva in 17
punti su 12 file, e il giorno che cambia restano indietro due punti — e una
sezione semplicemente sparisce.

**Da cambiare per l'AppImage:** dentro un'AppImage la cartella del programma è
in sola lettura, quindi i dati non potranno stare accanto al programma. Il
prossimo passo è scegliere i percorsi al primo avvio e ricordarli fuori
dall'app.

```
jw-librix/dati/
  <sigla>_<lingua>[_<numero>]/   ogni pubblicazione scompattata
                                 (es. sjj_I/, mwb_I_202609/, w_I_202608/)
  *.mp3  *.mp4    audio e video scaricati, sciolti nella radice
  copertine/      la cache delle copertine
  cache_documenti/  la cache dei documenti aperti
  timer/          i dati del plugin timer
  userData/       user_data.db, manifest.json, style.css, script.js
    aggiornamenti.json         l'ultimo controllo al server
    catalogo_versione.txt      quale versione di catalogo c'e' sul disco
    preferiti.json  scaricati.json  impostazioni.json
    mediaCatalog/  il catalogo dei media, per lingua
  nwt_I/          il pacchetto della Bibbia scompattato
  catalog.db      il catalogo delle pubblicazioni, 216 MB
  Documents_I/    il testo HTML dei capitoli, in comune
```

`Documents_I/` è **in comune** e non dentro ogni pacchetto: i capitoli di
`tutti` i pacchetti stanno lì, e dentro ciascun pacchetto c'è solo
`contents/` con il database e le copertine. Il nome del file è il
`MepsDocumentId`, che è in chiaro, quindi non si può sbagliare quale
pacchetto sia.

I due cataloghi sono due file, e non uno, perché rispondono a due domande
diverse: `catalog.db` elenca i **libri** (per l'italiano tutte e 3.741 le
voci hanno formato `application/x-jwpub`, e un video non c'è), e
`mediaCatalog/I.json.gz` elenca i **video e l'audio**. Il primo sta sul
server in `catalogs/publications/v4/` e ha un `manifest.json` che dice
qual è la versione corrente; il secondo sta in `catalogs/media/` e non ha
un nome di versione, quindi per capire se è da riprendere si guarda la data.
Sono descritti in `COME-FUNZIONA-ADESSO.txt`, sezione 10.

---

## 9. Crediti

`JW-Library-macOS` di Dario Ragusa —
<https://github.com/Miaosi001/JW-Library-macOS>, MIT.
Porting a Linux non ufficiale.

`Files/script.js`, `Files/style.css`, `Files/manifestDefault.json`,
`Files/user_data.db` e `Files/icons/` vengono dal progetto originale.
`script.js` è byte-identico. Il testo delle Scritture viene da wol.jw.org come
nell'originale; i diritti sono dei suoi titolari.