"""Documento em camadas: camada 1 = base oficial (edit-locked), camada 2 =
trait RGBA. O arquivo `document.ora` (OpenRaster) e regravado a cada mudanca
e abre em Krita/GIMP/MyPaint."""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from . import ora
from .extract import compose

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("TRAIT_WORKFLOW_ROOT", str(REPO_ROOT / "documents")))

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def doc_dir(name):
    if not SAFE_NAME.match(name):
        raise ValueError(f"nome invalido: {name!r} (use letras, numeros, . _ -)")
    return ROOT / name


def create(name, base_image, paint_mask=None, protected_mask=None):
    p = doc_dir(name)
    for sub in ("qa", "exports"):
        (p / sub).mkdir(parents=True, exist_ok=True)

    base = Image.open(base_image).convert("RGBA")
    base.save(p / "base.png")

    from .masks import load_mask
    if paint_mask:
        load_mask(paint_mask, base.size).save(p / "paint_mask.png")
    if protected_mask:
        load_mask(protected_mask, base.size).save(p / "protected_mask.png")

    # camada 2 nasce vazia (100% transparente)
    Image.new("RGBA", base.size, (0, 0, 0, 0)).save(p / "trait.png")

    meta = {
        "name": name,
        "canvas": list(base.size),
        "created": datetime.now(timezone.utc).isoformat(),
        "source_base": str(base_image),
    }
    (p / "document.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_ora_file({"dir": p, **meta})
    return meta


def load(name):
    p = doc_dir(name)
    f = p / "document.json"
    if not f.exists():
        raise FileNotFoundError(
            f"documento '{name}' nao existe em {ROOT} (crie com create_document)")
    meta = json.loads(f.read_text(encoding="utf-8"))
    meta["dir"] = p
    return meta


def base_image(meta):
    return Image.open(meta["dir"] / "base.png").convert("RGBA")


def trait_image(meta):
    return Image.open(meta["dir"] / "trait.png").convert("RGBA")


def get_mask(meta, kind):
    f = meta["dir"] / f"{kind}_mask.png"
    return Image.open(f).convert("L") if f.exists() else None


def trait_sha1(meta):
    return hashlib.sha1((meta["dir"] / "trait.png").read_bytes()).hexdigest()


def write_ora_file(meta, order="over"):
    p = meta["dir"]
    base = Image.open(p / "base.png").convert("RGBA")
    trait = Image.open(p / "trait.png").convert("RGBA")
    merged = compose(base, trait, order=order)
    ora.write_ora(p / "document.ora", base, trait, merged)


def set_trait(meta, im, order="over"):
    """Grava a camada 2 (pixel a pixel, sem retoque) e invalida o QA."""
    im.save(meta["dir"] / "trait.png")
    qa_file = meta["dir"] / "qa" / "qa.json"
    if qa_file.exists():
        qa_file.unlink()
    write_ora_file(meta, order=order)


def list_documents():
    out = []
    if not ROOT.exists():
        return out
    for p in sorted(ROOT.iterdir()):
        if (p / "document.json").exists():
            meta = json.loads((p / "document.json").read_text(encoding="utf-8"))
            qa_file = p / "qa" / "qa.json"
            meta["qa"] = (json.loads(qa_file.read_text(encoding="utf-8"))
                          if qa_file.exists() else None)
            out.append(meta)
    return out
