"""I documenti scaricati dal sito che NON sono JWPUB (oggi: PDF).

Stanno in `<cartella dati>/PdfSito/` con un piccolo registro `indice.json`.
Compaiono in Biblioteca Digitale > Scaricati (dove si eliminano) e nella
categoria giusta delle Pubblicazioni; se nessuna categoria ci sta bene, in
«Altri formati».  Esistono come voci solo perche' il JWPUB non c'e': se c'e', si
usa quello (vedi `FormatiSito`).
"""
from __future__ import annotations

import json
from pathlib import Path

ALTRI = "altri_formati"
NOME_ALTRI = "Altri formati (PDF)"

#: contesto scritto dal sito -> categoria delle Pubblicazioni
_CATEGORIE = {"LIBRI": "libri", "OPUSCOLI": "brochure", "VOLANTINI E INVITI": "trattati",
              "BROCHURE": "brochure", "TRATTATI": "trattati"}


def cartella() -> Path:
    from Utility.Extensions.Ext_FileManager import get_documents_directory
    return get_documents_directory() / "PdfSito"


def _indice() -> Path:
    return cartella() / "indice.json"


def _leggi() -> list[dict]:
    try:
        dati = json.loads(_indice().read_text(encoding="utf8"))
        return [d for d in dati if (cartella() / d.get("file", "")).is_file()]
    except (OSError, ValueError):
        return []


def elenco() -> list[dict]:
    """Quelli scaricati e ancora sul disco."""
    return _leggi()


def trova(sigla: str, lingua: str) -> dict | None:
    return next((d for d in _leggi() if d["sigla"] == sigla and d["lingua"] == lingua), None)


def percorso(d: dict) -> str:
    return str(cartella() / d["file"])


def nome_file(sigla: str, lingua: str) -> str:
    return f"{sigla}_{lingua}.pdf".replace("/", "_")


def categoria_da_contesto(contesto: str) -> str:
    return _CATEGORIE.get((contesto or "").strip().upper(), ALTRI)


def aggiungi(sigla: str, lingua: str, titolo: str, contesto: str = "") -> dict:
    """Registra un PDF gia' scritto in `cartella()/nome_file(...)`."""
    file = nome_file(sigla, lingua)
    d = {"sigla": sigla, "lingua": lingua, "titolo": titolo, "file": file,
         "categoria": categoria_da_contesto(contesto),
         "byte": (cartella() / file).stat().st_size}
    resto = [x for x in _leggi() if not (x["sigla"] == sigla and x["lingua"] == lingua)]
    _indice().write_text(json.dumps(resto + [d], ensure_ascii=False, indent=1), encoding="utf8")
    return d


def elimina(d: dict) -> None:
    try:
        (cartella() / d["file"]).unlink(missing_ok=True)
        resto = [x for x in _leggi() if x["file"] != d["file"]]
        _indice().write_text(json.dumps(resto, ensure_ascii=False, indent=1), encoding="utf8")
    except OSError:
        pass


def di_categoria(chiave: str) -> list[dict]:
    return [d for d in _leggi() if d.get("categoria") == chiave]
