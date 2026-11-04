#
#  BackupManager.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 29/07/21.
#

"""Salvare e riaprire i dati dell'utente.

Il formato del file e la conversione stanno in ``FormatoJWLibrary``: qui ci
sono le finestre di scelta del file e il database che si scrive.  Il file
prodotto e' un ``.jwlibrary`` vero, apribile da JW Library su Android,
Windows, iOS e iPadOS, e quelli di quelle app si importano qui.

Il nome non si sceglie: ``UserdataBackup_<data>_<dispositivo>.jwlibrary``.
Si sceglie solo la cartella.

PERCHE' LA FUSIONE DEL WAL PRIMA DI SCRIVERE
---------------------------------------------
Il database sta in modalita' WAL: le scritture recenti possono essere nel
file ``-wal`` e non dentro il database.  Prima di leggerlo per il backup si fa
``wal_checkpoint(TRUNCATE)`` (``store_data_in_db``).
"""

import sqlite3
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog

from Utility.Structures.Paths import Paths
from Utility.UserData import FormatoJWLibrary as Formato
from Utility.UserData import StatoBackup


class BackupManager:

    @staticmethod
    def cartella_ultimo_backup() -> Path:
        return Path.home()

    @staticmethod
    def create_backup(parent=None, su_fine=None) -> None:
        """Chiede dove salvare e scrive il backup, con la barra di avanzamento.

        ``su_fine(percorso, errore)`` parte alla fine: se l'utente annulla non parte.
        """
        percorso = QFileDialog.getSaveFileName(
            parent,
            "Esporta backup",
            str(BackupManager.cartella_ultimo_backup() / Formato.nome_file()),
            "Backup JW Library (*.jwlibrary)",
        )[0]
        if not percorso:
            return
        if not percorso.endswith(".jwlibrary"):
            percorso += ".jwlibrary"

        def lavoro(progresso):
            BackupManager.store_data_in_db()
            Formato.crea_backup(Path(percorso), progresso=progresso)
            print(f"Backup creato [{percorso}] \u2705")
            # Il nuovo sostituisce il precedente: quello vecchio si elimina
            StatoBackup.registra_esportato(percorso)
            return percorso

        from SubViews.BarraBackup import BarraBackup
        BarraBackup.esegui(parent, "Esporto il backup", lavoro, su_fine)

    @staticmethod
    def crea_per_condividere(parent=None, su_fine=None) -> None:
        """Scrive il backup in ``userData/da-condividere``; ``su_fine(percorso, errore)``.

        Ne tiene uno solo: quello di prima si butta, cosi' la cartella non cresce.
        """
        def lavoro(progresso):
            cartella = Paths.user_data_path / "da-condividere"
            cartella.mkdir(parents=True, exist_ok=True)
            for vecchio in cartella.glob("*.jwlibrary*"):
                vecchio.unlink(missing_ok=True)
            BackupManager.store_data_in_db()
            destinazione = cartella / Formato.nome_file()
            Formato.crea_backup(destinazione, progresso=progresso)
            StatoBackup.registra_condiviso(destinazione)
            return destinazione

        from SubViews.BarraBackup import BarraBackup
        BarraBackup.esegui(parent, "Preparo il backup", lavoro, su_fine)

    @staticmethod
    def condividi(parent, titolo: str, invio, su_fine=None) -> None:
        """Crea il backup e lo manda, tutto nella stessa barra di avanzamento.

        ``invio(file, avanza)`` ritorna ``(riuscito, messaggio)`` e chiama
        ``avanza(testo, frazione)``; se non riesce la barra mostra l'errore.
        Dopo un invio riuscito la copia sul computer si elimina, se
        l'utente non ha tolto la spunta.  ``su_fine(messaggio, errore)``.
        """
        def lavoro(progresso):
            cartella = Paths.user_data_path / "da-condividere"
            cartella.mkdir(parents=True, exist_ok=True)
            for vecchio in cartella.glob("*.jwlibrary*"):
                vecchio.unlink(missing_ok=True)
            BackupManager.store_data_in_db()
            destinazione = cartella / Formato.nome_file()
            Formato.crea_backup(destinazione,
                                progresso=lambda f, t="": progresso(0.4 * f, t))
            StatoBackup.registra_condiviso(destinazione)
            riuscito, messaggio = invio(
                destinazione, lambda t, f=0.0: progresso(0.4 + 0.6 * f, t))
            if not riuscito:
                raise RuntimeError(messaggio)
            if StatoBackup.elimina_dopo_invio():
                StatoBackup.dimentica_condiviso_eliminando()
                messaggio += " (copia eliminata dal computer)"
            return messaggio

        from SubViews.BarraBackup import BarraBackup
        BarraBackup.esegui(parent, titolo, lavoro, su_fine)

    @staticmethod
    def restore_backup(parent=None, su_fine=None) -> None:
        """Chiede un file .jwlibrary e lo importa; ``su_fine(riepilogo, errore)``."""
        percorso = QFileDialog.getOpenFileName(
            parent,
            "Importa backup",
            str(Path.home()),
            "Backup JW Library (*.jwlibrary);;Tutti i file (*)",
        )[0]
        if percorso:
            BackupManager.importa_da(percorso, parent, su_fine)

    @staticmethod
    def importa_da(percorso: str, parent=None, su_fine=None) -> None:
        """Importa il file con la barra di avanzamento."""
        def lavoro(progresso):
            riepilogo = Formato.importa_backup(Path(percorso), progresso)
            print(f"Backup importato con successo \u2705 {riepilogo}")
            return riepilogo

        from SubViews.BarraBackup import BarraBackup
        BarraBackup.esegui(parent, "Importo il backup", lavoro, su_fine)

    @staticmethod
    def testo_riepilogo(r: dict) -> str:
        testo = (f"Backup importato: {r['preferiti']} preferiti, {r['segnalibri']} segnalibri, "
                 f"{r['sottolineature']} sottolineature, {r['appunti']} appunti.")
        if r.get("versione_nuova"):
            testo += " Il backup viene da una versione piu' recente: potrebbe mancare qualcosa."
        return testo

    @staticmethod
    def store_data_in_db() -> None:
        """ Riversa il WAL dentro il database e lo svuota.

        Va chiamata dopo ogni scrittura.  E' una operazione brevissima, ma e'
        quella che fa si che quello che hai scritto sia davvero nel file e non
        solo in memoria.
        """
        connessione = BackupManager._apri()
        if connessione is None:
            return
        try:
            connessione.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            connessione.commit()
            print("Dati salvati nel DB ✅")
        except sqlite3.Error as errore:
            print(f"Error: {errore} ⚠️")
        finally:
            connessione.close()

    @staticmethod
    def _apri() -> sqlite3.Connection | None:
        """Apre il database degli utenti in scrittura."""
        Paths.prepare()
        try:
            return sqlite3.connect(str(Paths.db_path))
        except sqlite3.Error as errore:
            print(f"Errore apertura database ⚠️  {errore}")
            return None
