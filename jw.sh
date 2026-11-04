#!/usr/bin/env bash
#
# jw.sh
# Avvia JW LibriX.
#
# Apre il programma. Subito.
#
# PERCHE' NON C'E' PIU' UN `--verifica` QUI DAVANTI
# -------------------------------------------------
# Qui prima c'era:
#
#     "$PY" JWLibraryApp.py --verifica || exit 1
#     "$PY" JWLibraryApp.py "$@"
#
# cioe' i controlli giravano in un processo **separato**, prima del programma.
# Misurati: 14 secondi.  E in quei 14 secondi non c'era nessuna finestra — la
# schermata di avvio non era ancora stata costruita, perche' l'app non era
# ancora partita.  Sul terminale comparivano righe e poi il terminale fermo, e
# un terminale fermo senza finestra e' indistinguibile da un programmo partito e
# bloccato.
#
# La riga e' sparita perche' i controlli ora girano **dentro** l'app
# (`_controlli_avvio` in `JWLibraryApp.py`): la schermata di avvio si mostra
# subito, e i controlli passano a un giro di eventi per volta, in mezzo al
# ridisegno.  Il log esce nei due posti come prima, perche' passa da
# `Messaggi`, che e' gia' deviato sulla schermata.
#
# Se una regola del player fallisce, la finestra principale non si apre e la
# schermata dice quale regola e' rotta: e' quello che faceva il `|| exit 1`, ma
# detto dove l'utente lo sta guardando invece che sparire nel terminale.
#
# All'avvio girano solo i controlli veloci (ambiente, moduli, server: ~0,1 s).
# Quelli pesanti — costruire le schermate e provare le regole del player, ~7 s —
# girano con JWL_CONTROLLO_COMPLETO=1 oppure con JWL_VERIFICA=1.
# I controlli si saltano del tutto con JWL_SENZA_CONTROLLO=1, come prima.
# Con JWL_VERIFICA=1 si lancia `--verifica` da sola e si esce: li' i controlli
# girano in fila e il codice di uscita dice se il programma puo' partire.
# Con JW_MISURA=1 si vedono i tempi.

set -e

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

# LA VERSIONE DI SVILUPPO TIENE I SUOI DATI
# ----------------------------------------
# Se accanto al programma c'e' una cartella `dati/` (la versione di prova,
# non quella pulita ne' l'AppImage), si usa quella: cosi' i dati di prova non
# si mescolano con quelli veri in ~/.local/share/JW-LibriX o nella cartella
# scelta nelle Impostazioni.  JWL_HOME scelta a mano vince sempre.
if [ -z "${JWL_HOME:-}" ] && [ -d dati ]; then
  export JWL_HOME="$(pwd)/dati"
fi

# SOLO CONTROLLI, E POI ESCE
# --------------------------
# Questa e' la strada che esisteva prima, e resta per quando si vuole la risposta
# senza aprire niente: «il programma partira'?».
if [ -n "${JWL_VERIFICA:-}" ]; then
  exec "$PY" JWLibraryApp.py --verifica
fi

if [ -n "$JW_MISURA" ]; then
  echo "avvio $(date +%s.%N)"
fi

exec "$PY" JWLibraryApp.py "$@"

# Nessun pacchetto da installare con pip: tutto quello che serve e' nella
# libreria standard piu' PyQt6.