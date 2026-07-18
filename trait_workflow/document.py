"""Documento em camadas: camada 1 = base oficial (edit-locked), camada 2 =
trait RGBA. O arquivo `document.ora` (OpenRaster) e regravado a cada mudanca
e abre em Krita/GIMP/MyPaint."""

import hashlib
import json
import os
import re
import shutil
import zipfile
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
    if (p / "document.json").exists():
        raise FileExistsError(f"documento '{name}' ja existe em {p}")
    for sub in ("qa", "exports"):
        (p / sub).mkdir(parents=True, exist_ok=True)

    source = Image.open(base_image)
    if source.format != "PNG" or source.mode != "RGBA":
        raise ValueError(
            f"base deve ser PNG RGBA nativo; recebido {source.format} {source.mode}"
        )
    source.load()
    base = source
    shutil.copyfile(base_image, p / "base.png")

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
        "base_sha256": file_sha256(p / "base.png"),
        "base_visible": True,
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


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_ora_file(meta, order="over"):
    p = meta["dir"]
    base = Image.open(p / "base.png").convert("RGBA")
    trait = Image.open(p / "trait.png").convert("RGBA")
    base_visible = bool(meta.get("base_visible", True))
    if base_visible:
        merged = compose(base, trait, order=order)
    else:
        merged = trait.copy()
    ora.write_ora(
        p / "document.ora", base, trait, merged,
        base_visible=base_visible,
        base_png_bytes=(p / "base.png").read_bytes(),
        trait_png_bytes=(p / "trait.png").read_bytes(),
    )


def set_trait(meta, im, order="over"):
    """Grava a camada 2 (pixel a pixel, sem retoque) e invalida o QA."""
    im.save(meta["dir"] / "trait.png")
    qa_file = meta["dir"] / "qa" / "qa.json"
    if qa_file.exists():
        qa_file.unlink()
    write_ora_file(meta, order=order)


def set_trait_file(meta, image_path, order="over"):
    """Copia o PNG da trait byte a byte para a camada 2."""
    source = Path(image_path)
    shutil.copyfile(source, meta["dir"] / "trait.png")
    qa_file = meta["dir"] / "qa" / "qa.json"
    if qa_file.exists():
        qa_file.unlink()
    write_ora_file(meta, order=order)


def set_base_visibility(meta, visible, order="over"):
    before = file_sha256(meta["dir"] / "trait.png")
    meta["base_visible"] = bool(visible)
    payload = {k: v for k, v in meta.items() if k != "dir"}
    (meta["dir"] / "document.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    write_ora_file(meta, order=order)
    after = file_sha256(meta["dir"] / "trait.png")
    return {
        "base_visible": bool(visible),
        "trait_sha256_before": before,
        "trait_sha256_after": after,
        "trait_unchanged": before == after,
        "ora": str(meta["dir"] / "document.ora"),
    }


def inspect(name):
    meta = load(name)
    p = meta["dir"]
    base = Image.open(p / "base.png")
    trait = Image.open(p / "trait.png")
    with zipfile.ZipFile(p / "document.ora") as zf:
        stack = zf.read("stack.xml").decode("utf-8")
        ora_base_sha = hashlib.sha256(zf.read("data/layer_base.png")).hexdigest()
        ora_trait_sha = hashlib.sha256(zf.read("data/layer_trait.png")).hexdigest()
    base_layer_xml = next(
        line for line in stack.splitlines() if 'layer 1 - base (locked)' in line
    )
    base_sha = file_sha256(p / "base.png")
    trait_sha = file_sha256(p / "trait.png")
    return {
        "name": name,
        "canvas": meta["canvas"],
        "base": {"mode": base.mode, "size": list(base.size), "sha256": base_sha},
        "trait": {
            "mode": trait.mode, "size": list(trait.size), "sha256": trait_sha,
            "empty": trait.getchannel("A").getbbox() is None,
        },
        "base_immutable": base_sha == meta.get("base_sha256"),
        "base_visible": bool(meta.get("base_visible", True)),
        "ora_base_locked": 'edit-locked="true"' in base_layer_xml,
        "ora_base_visibility_matches": (
            ('visibility="visible"' in base_layer_xml)
            == bool(meta.get("base_visible", True))
        ),
        "ora_base_bytes_match": ora_base_sha == base_sha,
        "ora_trait_bytes_match": ora_trait_sha == trait_sha,
        "ora": str(p / "document.ora"),
    }


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
