#!/usr/bin/env bash
#
# installa.sh
# Mette l'icona, la voce di menu e il comando nel posto dove Linux li cerca.
#
# Serve una volta sola, e non e' obbligatorio: senza questo il programma parte
# lo stesso e ./jw.sh funziona sempre.  Questo serve per averlo nel menu delle
# applicazioni, con l'icona giusta, e per poterlo lanciare con il solo nome.
#
# Le cartelle sono quelle di XDG, quindi funzionano su Arch, Fedora, Debian,
# Ubuntu e su qualunque altra distribuzione che segue lo stesso standard.

set -e
cd "$(dirname "$0")"
APP="$(pwd)"

# Dove stanno le icone e le voci: prima la scelta dell'utente, altrimenti
# quella di XDG.
if [ -n "$XDG_DATA_HOME" ]; then
  DEST="$XDG_DATA_HOME"
else
  DEST="$HOME/.local/share"
fi

echo "Installo in $DEST"

# Toglie le voci della versione con il nome vecchio, se ci sono: altrimenti
# nel menu resterebbero due programmi.
rm -f "$DEST/applications/JWLibrary.desktop" "$HOME/.local/bin/jwlibrary" \
      "$DEST"/icons/hicolor/*/apps/jwlibrary.png 2>/dev/null || true

# ---- il comando -------------------------------------------------------
#
# Si scrive un piccolo-wrapper con dentro il percorso vero del programma.
# Il percorso non puo' stare direttamente nell'Exec del file .desktop: con
# i caratteri di una shell dentro un Exec l'Entry diventa invalido, e
# desktop-file-validate lo segnala.  Il wrapper tiene la cosa semplice:
# l'Exec del file .desktop e' una parola sola, "jwlibrix".
if [ -n "$XDG_BIN_HOME" ]; then
  BIN="$XDG_BIN_HOME"
elif [ -d "$HOME/.local/bin" ] || [ ! -d "$HOME/bin" ]; then
  BIN="$HOME/.local/bin"
else
  BIN="$HOME/bin"
fi
mkdir -p "$BIN"

cat > "$BIN/jwlibrix" <<WRAPPER
#!/usr/bin/env bash
# Wrapper creato da installa.sh.
# Il percorso del programma e' qui dentro scritto, cosche' questo file possa
# stare dove Linux cerca i comandi senza dipendere da dove si e' lanciato.
exec "$APP/jw.sh" "\$@"
WRAPPER
chmod +x "$BIN/jwlibrix"
echo "  comando: $BIN/jwlibrix"

# ---- l'icona ----------------------------------------------------------
for s in 16 32 64 128 256 512 1024; do
  mkdir -p "$DEST/icons/hicolor/${s}x${s}/apps"
  cp "Files/icons/$s.png" "$DEST/icons/hicolor/${s}x${s}/apps/jwlibrix.png"
done
echo "  icona:   7 misure in icons/hicolor/"

# ---- la voce di menu --------------------------------------------------
mkdir -p "$DEST/applications"
cp JWLibriX.desktop "$DEST/applications/JWLibriX.desktop"
chmod +x "$DEST/applications/JWLibriX.desktop"
echo "  menu:    applications/JWLibriX.desktop"

# Il menu tiene in memoria l'elenco delle voci: senza questo la voce nuova
# non si vede fino al prossimo avvio della sessione.
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DEST/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$DEST/icons/hicolor" 2>/dev/null || true
fi
echo "  cache delle icone aggiornata"

echo
echo "Fatto. Adesso:"
echo "  jwlibrix        per partire, da qualunque cartella"
echo "  ./jw.sh         equivalente, da questa cartella"