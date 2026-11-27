#!/usr/bin/env bash
# Costruisce JW-LibriX-<versione>-x86_64.AppImage (senza timer, senza dati),
# la stessa che si scarica dalle release.
#
# Uso:  ./crea-appimage.sh      -> il file esce in questa cartella
#       JWL_USCITA=/altra/cartella ./crea-appimage.sh
#
# Serve: Linux x86_64, bash, curl, internet (scarica il Python portatile di
# niess/python-appimage, appimagetool e PyQt6 da pip).  Qualche minuto.
# Dentro l'AppImage: il codice di questa cartella, Python 3.12, PyQt6 con
# WebEngine e le librerie che usa il plugin timer (che si scarica a parte).
set -euo pipefail
QUI="$(cd "$(dirname "$0")" && pwd)"
APP="$QUI"
USCITA="${JWL_USCITA:-$QUI}"
# Nome dal numero in Utility/Versione.py: 1.0.0 -> V1, 1.0.1 -> V1.0.1
VER="$(sed -n 's/^VERSIONE_APP = "\(.*\)"/\1/p' "$APP/Utility/Versione.py")"
[ "$VER" = "1.0.0" ] && ETI="V1" || ETI="V$VER"
FILE="$USCITA/JW-LibriX-$ETI-x86_64.AppImage"
LAV="$(mktemp -d)"; trap 'rm -rf "$LAV"' EXIT
cd "$LAV"

echo "1/5 scarico Python portatile e appimagetool"
curl -fsSLO https://github.com/niess/python-appimage/releases/download/python3.12/python3.12.15-cp312-cp312-manylinux_2_28_x86_64.AppImage
curl -fsSLO https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x ./*.AppImage

echo "2/5 apro Python"
./python3.12*.AppImage --appimage-extract >/dev/null
AD="$LAV/squashfs-root"

echo "3/5 installo PyQt6 con WebEngine (qualche minuto)"
"$AD/opt/python3.12/bin/python3.12" -m pip install --no-cache-dir PyQt6 PyQt6-WebEngine
# Librerie che usa il plugin timer (che si scarica a parte e sta nella cartella dati):
# devono stare nel Python dell'AppImage, perche' e' lui a eseguire il plugin.
"$AD/opt/python3.12/bin/python3.12" -m pip install --no-cache-dir \
    requests websockets "qrcode[pil]" dateparser beautifulsoup4 python-dateutil platformdirs jsonschema
"$AD/opt/python3.12/bin/python3.12" -c "import PyQt6.QtWebEngineWidgets, requests, websockets, qrcode, dateparser, bs4, dateutil, platformdirs, jsonschema; print('librerie ok')"

echo "4/5 copio l'app (senza dati, senza plugin)"
mkdir -p "$AD/opt/jw-librix"
tar -C "$APP" --exclude=__pycache__ --exclude=dati --exclude=plugin --exclude=.git \
    --exclude='*.AppImage' --exclude='*.part' --exclude=crea-appimage.sh -cf - . | tar -C "$AD/opt/jw-librix" -xf -
rm -f "$AD/AppRun"   # era un collegamento a usr/bin/python3.12: scriverci sopra lo rovinava
cat > "$AD/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONNOUSERSITE=1
PY="$HERE/opt/python3.12/bin/python3.12"
# Il Python portatile non conosce i certificati del sistema: senza questo ogni
# connessione HTTPS (jw.org, GitHub) fallisce con CERTIFICATE_VERIFY_FAILED.
# Si sostituisce SEMPRE quello che c'e' nell'ambiente: una variabile ereditata dal
# desktop (o da un altro programma) che punta a un file sbagliato o incompleto fa
# fallire lo stesso i certificati.
# DA UNA CARTELLA CHE C'E' e con -I: dopo un aggiornamento l'app vecchia
# rilancia questa da dentro la SUA AppImage, che intanto sparisce; Python
# cercava certifi anche nella cartella corrente (sparita), l'import falliva e
# restava il percorso dei certificati della vecchia: niente HTTPS fino al
# riavvio successivo.
cd "$HERE" 2>/dev/null || cd /
CERTIFICATI="$("$PY" -I -c 'import certifi; print(certifi.where())' 2>/dev/null)"
if [ -n "$CERTIFICATI" ] && [ -f "$CERTIFICATI" ]; then
  export SSL_CERT_FILE="$CERTIFICATI"
  unset SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE
elif [ -n "${SSL_CERT_FILE:-}" ] && [ ! -f "$SSL_CERT_FILE" ]; then
  unset SSL_CERT_FILE      # un file sparito e' peggio di nessun file
fi
# ---- voce di menu e icona, come fa installa.sh ---------------------------
# Senza una voce JWLibriX.desktop il desktop non sa abbinare la finestra a
# un'icona e ne mostra una generica.  La voce punta a questo stesso file
# AppImage ($APPIMAGE) e si riscrive solo se e' cambiata (ad es. se lo sposti).
# Per non farlo mai:  JWL_NO_INTEGRAZIONE=1
if [ -n "${APPIMAGE:-}" ] && [ -z "${JWL_NO_INTEGRAZIONE:-}" ]; then
  DATI="${XDG_DATA_HOME:-$HOME/.local/share}"
  VOCE="$DATI/applications/JWLibriX.desktop"
  NUOVA="$(mktemp)"
  cat > "$NUOVA" <<VOCE_FINE
[Desktop Entry]
Type=Application
Version=1.0
Name=JW LibriX
GenericName=Biblioteca delle Scritture
Comment=Leggere le Scritture e le pubblicazioni
Exec="$APPIMAGE"
Icon=jwlibrix
Terminal=false
Categories=Education;Literature;Viewer;
Keywords=bible;jw;library;librix;scripture;
StartupNotify=true
StartupWMClass=JWLibriX
VOCE_FINE
  CAMBIATO=0
  if ! cmp -s "$NUOVA" "$VOCE" 2>/dev/null; then
    mkdir -p "$DATI/applications"
    cp "$NUOVA" "$VOCE"
    chmod +x "$VOCE"
    CAMBIATO=1
  fi
  rm -f "$NUOVA"
  for MISURA in 16 32 64 128 256 512 1024; do
    SORGENTE="$HERE/opt/jw-librix/Files/icons/$MISURA.png"
    DEST="$DATI/icons/hicolor/${MISURA}x${MISURA}/apps/jwlibrix.png"
    if [ -f "$SORGENTE" ] && ! cmp -s "$SORGENTE" "$DEST" 2>/dev/null; then
      mkdir -p "$(dirname "$DEST")"
      cp "$SORGENTE" "$DEST"
      CAMBIATO=1
    fi
  done
  if [ "$CAMBIATO" = 1 ]; then
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATI/applications" 2>/dev/null
    command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$DATI/icons/hicolor" 2>/dev/null
  fi
fi
cd "$HERE/opt/jw-librix"
exec "$PY" JWLibraryApp.py "$@"
RUN
chmod +x "$AD/AppRun"
cp "$APP/Files/icons/256.png" "$AD/jw-librix.png"
rm -f "$AD"/*.desktop "$AD"/python*.png "$AD/.DirIcon"
cat > "$AD/jw-librix.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=JW LibriX
Exec=AppRun
Icon=jw-librix
Categories=Education;
DESK
ln -sf jw-librix.png "$AD/.DirIcon"

chmod -R a+rX "$AD"
echo "controllo HTTPS dal Python dell'AppImage"
SSL_CERT_FILE="$("$AD/opt/python3.12/bin/python3.12" -c 'import certifi; print(certifi.where())')" \
  "$AD/opt/python3.12/bin/python3.12" -c "import urllib.request; urllib.request.urlopen('https://github.com', timeout=20); print('HTTPS ok')"
echo "5/5 creo l'AppImage"
ARCH=x86_64 ./appimagetool-x86_64.AppImage --appimage-extract-and-run "$AD" "$FILE"
ls -lh "$FILE"
