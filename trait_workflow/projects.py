"""Projetos: uma pasta por trait, com base, mascaras, candidatos e camadas."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("TRAIT_WORKFLOW_ROOT", str(REPO_ROOT / "projects")))

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def project_dir(name):
    if not SAFE_NAME.match(name):
        raise ValueError(f"nome de projeto invalido: {name!r} (use letras, numeros, . _ -)")
    return ROOT / name


def create(name, base_image, paint_mask=None, protected_mask=None):
    p = project_dir(name)
    for sub in ("candidates", "layers", "qa", "exports"):
        (p / sub).mkdir(parents=True, exist_ok=True)

    base = Image.open(base_image).convert("RGBA")
    base.save(p / "base.png")

    from .masks import load_mask
    if paint_mask:
        load_mask(paint_mask, base.size).save(p / "paint_mask.png")
    if protected_mask:
        load_mask(protected_mask, base.size).save(p / "protected_mask.png")

    meta = {
        "name": name,
        "canvas": list(base.size),
        "created": datetime.now(timezone.utc).isoformat(),
        "source_base": str(base_image),
    }
    (p / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load(name):
    p = project_dir(name)
    meta_file = p / "project.json"
    if not meta_file.exists():
        raise FileNotFoundError(
            f"projeto '{name}' nao existe em {ROOT} (crie com create_project)")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["dir"] = p
    return meta


def base_image(meta):
    return Image.open(meta["dir"] / "base.png").convert("RGBA")


def get_mask(meta, kind):
    f = meta["dir"] / f"{kind}_mask.png"
    return Image.open(f).convert("L") if f.exists() else None


def next_index(folder, prefix):
    best = 0
    for f in Path(folder).glob(f"{prefix}_*.png"):
        m = re.search(r"_(\d+)\.png$", f.name)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


def resolve_candidate(meta, candidate="latest"):
    folder = meta["dir"] / "candidates"
    if candidate in ("", "latest", None):
        cands = sorted(folder.glob("cand_*.png"))
        if not cands:
            raise FileNotFoundError("projeto sem candidatos: rode generate primeiro")
        return cands[-1]
    name = str(candidate)
    f = folder / (name if name.endswith(".png") else f"{name}.png")
    if not f.exists():
        raise FileNotFoundError(f"candidato nao encontrado: {f}")
    return f


def list_projects():
    out = []
    if not ROOT.exists():
        return out
    for p in sorted(ROOT.iterdir()):
        if (p / "project.json").exists():
            meta = json.loads((p / "project.json").read_text(encoding="utf-8"))
            meta["candidates"] = len(list((p / "candidates").glob("cand_*.png")))
            meta["layers"] = len(list((p / "layers").glob("trait_*.png")))
            out.append(meta)
    return out
