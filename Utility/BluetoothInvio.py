#
#  BluetoothInvio.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#

"""Mandare un file a un telefono via Bluetooth, senza programmi in piu'.

Usa BlueZ e il suo servizio OBEX (pacchetto ``bluez-obex``, che quasi ogni
distribuzione con Bluetooth ha gia'), parlando con D-Bus tramite ``busctl``.
Funziona su qualunque ambiente grafico, KDE o GNOME o altro.

Il telefono deve essere **associato** (accoppiato) al computer, con il
Bluetooth acceso.  Sul telefono compare la richiesta di ricevere il file e
bisogna accettarla: finche' non si accetta, il file non parte.

Tutte le funzioni sono bloccanti: vanno chiamate fuori dal thread della finestra.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time

#: icone dei dispositivi a cui non ha senso mandare un file
_ESCLUSE = ("audio-", "input-", "printer")


def _busctl(*argomenti: str, utente: bool = False, timeout: int = 20) -> str:
    comando = ["busctl", "--user" if utente else "--system", "--json=short", *argomenti]
    esito = subprocess.run(comando, capture_output=True, text=True, timeout=timeout)
    if esito.returncode != 0:
        raise RuntimeError((esito.stderr or esito.stdout).strip() or "errore di D-Bus")
    return esito.stdout


def disponibile() -> bool:
    """Il Bluetooth e' usabile: BlueZ c'e', c'e' un adattatore e il servizio OBEX."""
    if not shutil.which("busctl"):
        return False
    try:
        fuori = _busctl("call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager",
                        "GetManagedObjects", timeout=5)
        oggetti = json.loads(fuori)["data"][0]
        if not any("org.bluez.Adapter1" in i for i in oggetti.values()):
            return False
        _busctl("introspect", "org.bluez.obex", "/org/bluez/obex", utente=True, timeout=5)
        return True
    except (OSError, RuntimeError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return False


def dispositivi() -> list[tuple[str, str]]:
    """I dispositivi associati a cui si puo' mandare un file: (indirizzo, nome)."""
    try:
        fuori = _busctl("call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager",
                        "GetManagedObjects", timeout=5)
        oggetti = json.loads(fuori)["data"][0]
    except (OSError, RuntimeError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return []
    trovati = []
    for interfacce in oggetti.values():
        d = interfacce.get("org.bluez.Device1")
        if not d or not d.get("Paired", {}).get("data"):
            continue
        icona = d.get("Icon", {}).get("data", "")
        if icona.startswith(_ESCLUSE):
            continue
        indirizzo = d.get("Address", {}).get("data", "")
        nome = d.get("Alias", {}).get("data") or d.get("Name", {}).get("data") or indirizzo
        if indirizzo:
            trovati.append((indirizzo, nome))
    return trovati


def _chiama(bus, destinazione: str, percorso: str, interfaccia: str, metodo: str,
            argomenti: list, timeout_ms: int = 20000):
    from PyQt6.QtDBus import QDBus, QDBusMessage
    messaggio = QDBusMessage.createMethodCall(destinazione, percorso, interfaccia, metodo)
    messaggio.setArguments(argomenti)
    risposta = bus.call(messaggio, QDBus.CallMode.Block, timeout_ms)
    if risposta.errorName():
        raise RuntimeError(risposta.errorMessage() or risposta.errorName())
    return risposta.arguments()


def _percorso(valore) -> str:
    return valore.path() if hasattr(valore, "path") else str(valore)


def invia(indirizzo: str, file, avanza=None, attesa: int = 180) -> tuple[bool, str]:
    """Manda ``file`` al dispositivo.  Ritorna (riuscito, messaggio).

    ``avanza(testo, frazione)`` e' chiamata quando cambia qualcosa (in attesa che il
    telefono accetti, in invio).

    La sessione OBEX vive finche' vive la connessione D-Bus che l'ha creata:
    per questo qui si usa QtDBus (una connessione sola per tutto l'invio) e non
    una chiamata ``busctl`` per volta, che la chiuderebbe subito.
    """
    import uuid
    from PyQt6.QtDBus import QDBusConnection

    nome = f"jwl-bt-{uuid.uuid4().hex}"
    bus = QDBusConnection.connectToBus(QDBusConnection.BusType.SessionBus, nome)
    sessione = None
    try:
        if not bus.isConnected():
            return False, "Il Bluetooth non e' raggiungibile (D-Bus)"
        risposta = _chiama(bus, "org.bluez.obex", "/org/bluez/obex", "org.bluez.obex.Client1",
                           "CreateSession", [indirizzo, {"Target": "opp"}], 40000)
        sessione = _percorso(risposta[0])
        risposta = _chiama(bus, "org.bluez.obex", sessione, "org.bluez.obex.ObjectPush1",
                           "SendFile", [str(file)])
        trasferimento = _percorso(risposta[0])
        if avanza:
            avanza("Accetta il file sul telefono", 0.0)
        fine = time.monotonic() + attesa
        ultimo = ""
        trasferito = dimensione = 0
        while time.monotonic() < fine:
            try:
                dati = _chiama(bus, "org.bluez.obex", trasferimento,
                               "org.freedesktop.DBus.Properties", "GetAll",
                               ["org.bluez.obex.Transfer1"], 5000)[0]
            except RuntimeError:
                # BlueZ toglie il trasferimento appena e' chiuso, e un file piccolo
                # puo' sparire fra due controlli.  Un errore si vedrebbe come
                # Status "error": non visto, e' finito.  Se non si e' fatto in
                # tempo a vedere i byte passare, lo si dice con cautela.
                if dimensione and trasferito >= dimensione:
                    return True, "File inviato"
                return True, "Invio terminato: controlla che il file sia arrivato sul telefono"
            stato = str(dati.get("Status", ""))
            trasferito = int(dati.get("Transferred", 0) or 0)
            dimensione = int(dati.get("Size", 0) or 0)
            if stato == "complete" or (dimensione and trasferito >= dimensione):
                return True, "File inviato"
            if stato == "error":
                return False, "Il telefono ha rifiutato o interrotto il file"
            if trasferito > 0:
                frazione = trasferito / max(1, dimensione)
                testo = "Invio in corso\u2026"
            else:
                frazione = 0.0
                testo = "Accetta il file sul telefono"
            if avanza and (testo != ultimo or trasferito > 0):
                avanza(testo, frazione)
            ultimo = testo
            time.sleep(0.1)
        return False, "Il telefono non ha accettato il file in tempo"
    except RuntimeError as errore:
        return False, f"Bluetooth non riuscito: {errore}"
    finally:
        if sessione:
            try:
                _chiama(bus, "org.bluez.obex", "/org/bluez/obex", "org.bluez.obex.Client1",
                        "RemoveSession", [sessione], 5000)
            except RuntimeError:
                pass
        QDBusConnection.disconnectFromBus(nome)
