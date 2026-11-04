#
#  Ext_ScrollRuota.py
#  JWLibrary  (porting Swift -> Python/PyQt6 per Linux)
#
#  Creato da Dario Ragusa il 09/10/26.
#

"""Fa girare in orizzontale la striscia sotto il mouse.

IL DIFETTO
----------
Nella Home le sezioni lunghe sono strisce che scorrono **in orizzontale**: i
Preferiti, le Notizie, il «Kit dell'insegnante», «Le ultime novita'».  Ma la
rotella del mouse gira solo su e giu', e Qt passa alla striscia l'evento come
se fosse verticale.  Quindi passando il mouse sopra le card la rotella alzava
la pagina intera e la striscia non si moveva: per veder le voci dopo le prime
cinque bisognava afferrarla e trascinarla.

Con questo la rotella gira la striscia che e' sotto il mouse, e gira la
striscia **in orizzontale**, che e' quello che l'utente si aspetta da una
striscia.

PERCHE' UNA STRISCIA E NON UN PULSANTE O UN'AREA TRANSPARENTE
------------------------------------------------------------
L'evento di rotella lo prende il widget che e' sotto il mouse — la card — e
poi risale ai genitori finche' qualcuno lo prende.  Il filtro va sul
**viewport** della `QScrollArea`: e' il widget che copre tutta la striscia,
quindi il filtro lo vede sempre, sia sopra una card sia nel vuoto accanto, e
non serve metterlo su ogni card.

LA PAGINA CONTINUA A SCENDERE ALLA FINE
---------------------------------------
La rotella muove la striscia solo se la striscia puo' ancora muoversi in
quella direzione.  Quando e' arrivata in fondo, l'evento **non** viene
consumato e la pagina riprende a scorrere sotto il mouse.  Senza questo la
striscia diventerebbe un buco: arrivato in fondo non si potrebbe piu' alzare
la pagina finche' il mouse non esce da li'.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint


class _Ruota(QObject):
    """Il filtro: prende la rotella e la gira in orizzontale."""

    def __init__(self, area, padre=None) -> None:
        super().__init__(padre)
        self._area = area

    def eventFilter(self, oggetto, evento) -> bool:
        if evento.type() != QEvent.Type.Wheel:
            return False

        barra = self._area.horizontalScrollBar()
        # Niente da scorrere in orizzontale: e' una sezione corta, e la
        # rotella deve girare la pagina come prima.
        if barra.maximum() <= 0:
            return False

        angolo = evento.angleDelta()
        pixeli = evento.pixelDelta()

        if pixeli.x() or pixeli.y():
            passata = pixeli.x() or pixeli.y()
        else:
            # `angleDelta` conta gradi di rotella, 120 per un dentino, e la
            # rotella **verso il basso** li da' negativi.  Su una barra
            # orizzontale "andare in basso" vuol dire andare verso destra, cioe'
            # aumentare il valore: per questo il segno e' cambiato una volta
            # sola, qui.  Il gesto e' moltiplicato per `singleStep` cosi' una
            # striscia lunga non richiede quaranta giri per passare da una
            # card all'altra.
            denti = (angolo.x() or angolo.y()) / 120.0
            passata = -denti * barra.singleStep() * 2

        prima = barra.value()
        barra.setValue(prima + int(round(passata)))

        # La striscia si e' mossa: l'evento e' consumato e la pagina resta
        # ferma.  Se non si e' mossa era perche' la striscia e' gia' in fondo:
        # l'evento passa e la pagina scende sotto il mouse.
        return barra.value() != prima


def ruota_orizzontale(area):
    """Mette il filtro sulla ``QScrollArea`` e la restituisce.

    Si puo' scrivere senza assegnare il risultato::

        self.contenitore = ruota_orizzontale(QScrollArea(self))

    Il filtro viene tenuto attaccato alla ``QScrollArea`` con un attributo:
    un filtro installato e non più tenuto da nessuna parte viene distrutto
    insieme al ``QObject`` che lo contiene, e la rotella smetterebbe di
    funzionare senza nessun avviso.
    """
    filtro = _Ruota(area, area)
    area.viewport().installEventFilter(filtro)
    area._filtro_ruota = filtro
    return area