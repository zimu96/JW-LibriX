"""Le figure con più immagini si sfogliano, una per volta, come nell'app ufficiale.

Nei libri e nelle riviste una figura può avere più immagini (sul sito la classe
``gen-flipbook``): la prima di solito le mostra tutte insieme («Sequenza: …»),
le altre mostrano ogni scena da sola.  JW Library non le mette una accanto
all'altra: ne mostra una e ai lati ci sono due frecce semitrasparenti; la
freccia passa alla successiva (o alla precedente), e dopo l'ultima si torna
alla prima.  Sotto, dei puntini dicono a quale si è.

Serve uguale alla lettura offline (WebBrowserArticleView) e a quella online
(NotiziaView): entrambe eseguono ``JS_SFOGLIATORE`` quando la pagina è pronta,
e di nuovo dopo aver ridisegnato le sottolineature.

PERCHÉ COSÌ
-----------
* Le frecce e i puntini **non hanno testo** (il simbolo lo disegna il CSS):
  ``generateSelectable()`` trasforma in parole selezionabili ogni testo della
  pagina, e un «‹» diventerebbe una parola.
* Lo stato (quale immagine si vede) sta in attributi e stili della pagina, e
  i clic sono attributi ``onclick`` che chiamano una funzione di ``window``:
  le sottolineature ricostruiscono il corpo con ``innerHTML`` e così non si
  perde niente.
* Le ``<img>`` restano dov'erano e nello stesso ordine: l'indice che apre la
  figura a schermo intero (``showImg(i)``) non cambia.
"""
from __future__ import annotations

JS_SFOGLIATORE = r"""
(function () {
  if (!document.getElementById('jwl-sfoglia-stile')) {
    var stile = document.createElement('style');
    stile.id = 'jwl-sfoglia-stile';
    stile.textContent =
      '.jwl-sfoglia-quadro{position:relative;display:inline-block;max-width:100%;' +
      'vertical-align:top;line-height:0;margin:12px 0;}' +
      '.jwl-sfoglia-quadro>img{display:none !important;}' +
      '.jwl-sfoglia-quadro>img.jwl-sfoglia-attiva{display:block !important;' +
      'margin:0 auto !important;}' +
      '.jwl-freccia{position:absolute;top:50%;width:44px;height:44px;margin-top:-22px;' +
      'border-radius:50%;background:rgba(0,0,0,0.38);cursor:pointer;opacity:0.55;' +
      'transition:opacity .15s;-webkit-user-select:none;user-select:none;z-index:2;}' +
      '.jwl-freccia:hover{opacity:1;}' +
      '.jwl-freccia::before{content:"";position:absolute;top:50%;left:50%;width:12px;height:12px;' +
      'border-top:3px solid #fff;border-right:3px solid #fff;}' +
      '.jwl-freccia.jwl-sx{left:10px;}' +
      '.jwl-freccia.jwl-sx::before{margin:-7px 0 0 -4px;transform:rotate(-135deg);}' +
      '.jwl-freccia.jwl-dx{right:10px;}' +
      '.jwl-freccia.jwl-dx::before{margin:-7px 0 0 -9px;transform:rotate(45deg);}' +
      '.jwl-puntini{position:absolute;left:0;right:0;bottom:10px;text-align:center;z-index:2;' +
      '-webkit-user-select:none;user-select:none;pointer-events:none;}' +
      '.jwl-puntino{display:inline-block;width:8px;height:8px;margin:0 4px;border-radius:50%;' +
      'background:rgba(255,255,255,0.45);box-shadow:0 0 2px rgba(0,0,0,0.6);}' +
      '.jwl-puntino.jwl-qui{background:#fff;}';
    (document.head || document.documentElement).appendChild(stile);
  }

  window.__jwlSfoglia = function (freccia, passo, evento) {
    if (evento) { evento.stopPropagation(); evento.preventDefault(); }
    var quadro = freccia.parentNode;
    var immagini = quadro.querySelectorAll(':scope > img');
    if (!immagini.length) { return false; }
    var qui = (Number(quadro.getAttribute('data-jwl-qui')) || 0) + passo;
    qui = (qui % immagini.length + immagini.length) % immagini.length;
    quadro.setAttribute('data-jwl-qui', String(qui));
    for (var i = 0; i < immagini.length; i++) {
      immagini[i].classList.toggle('jwl-sfoglia-attiva', i === qui);
    }
    var puntini = quadro.querySelectorAll('.jwl-puntino');
    for (var k = 0; k < puntini.length; k++) {
      puntini[k].classList.toggle('jwl-qui', k === qui);
    }
    return false;
  };

  var fermo = 'event.stopPropagation();';
  var figure = document.querySelectorAll('figure.gen-flipbook, figure[data-jwl-sfoglia]');
  for (var f = 0; f < figure.length; f++) {
    var figura = figure[f];
    if (figura.querySelector('.jwl-sfoglia-quadro')) { continue; }
    var immagini = [];
    for (var c = 0; c < figura.children.length; c++) {
      if (figura.children[c].tagName === 'IMG') { immagini.push(figura.children[c]); }
    }
    if (immagini.length < 2) { continue; }
    var quadro = document.createElement('div');
    quadro.className = 'jwl-sfoglia-quadro';
    quadro.setAttribute('data-jwl-qui', '0');
    figura.insertBefore(quadro, immagini[0]);
    for (var m = 0; m < immagini.length; m++) {
      quadro.appendChild(immagini[m]);
      immagini[m].classList.toggle('jwl-sfoglia-attiva', m === 0);
    }
    var sx = document.createElement('span');
    sx.className = 'jwl-freccia jwl-sx';
    sx.title = 'Immagine precedente';
    sx.setAttribute('onclick', 'return __jwlSfoglia(this, -1, event);');
    sx.setAttribute('onmousedown', fermo);
    sx.setAttribute('onmouseup', fermo);
    var dx = document.createElement('span');
    dx.className = 'jwl-freccia jwl-dx';
    dx.title = 'Immagine successiva';
    dx.setAttribute('onclick', 'return __jwlSfoglia(this, 1, event);');
    dx.setAttribute('onmousedown', fermo);
    dx.setAttribute('onmouseup', fermo);
    var puntini = document.createElement('span');
    puntini.className = 'jwl-puntini';
    for (var p = 0; p < immagini.length; p++) {
      var punto = document.createElement('span');
      punto.className = 'jwl-puntino' + (p === 0 ? ' jwl-qui' : '');
      puntini.appendChild(punto);
    }
    quadro.appendChild(sx);
    quadro.appendChild(dx);
    quadro.appendChild(puntini);
  }
})();
"""
