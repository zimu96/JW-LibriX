#
#  InvioKde.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Mandare un file a un telefono con KDE Connect (se e' installato)."""

import subprocess


def invia(file, id_dispositivo: str, nome: str, avanza=None) -> tuple[bool, str]:
    """Ritorna (riuscito, messaggio).  Bloccante: fuori dal thread della finestra."""
    if avanza:
        avanza(f"Invio a {nome}\u2026", 0.2)
    try:
        esito = subprocess.run(["kdeconnect-cli", "-d", id_dispositivo, "--share", str(file)],
                               capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False, f"{nome}: il telefono non ha risposto in tempo"
    except (OSError, subprocess.SubprocessError) as errore:
        return False, f"Invio a {nome} non riuscito: {errore}"
    fuori, errori = (esito.stdout or "").strip(), (esito.stderr or "").strip()
    print(f"KDE Connect: codice {esito.returncode} {fuori} {errori}")
    if esito.returncode == 0 and not errori:
        return True, f"Backup inviato a {nome}"
    return False, f"Invio a {nome} non riuscito: {errori or fuori or 'errore sconosciuto'}"
