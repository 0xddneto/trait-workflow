"""Operacoes de alto nivel usadas pelo servidor MCP e pela CLI.

Modelo: documento em camadas. A camada 2 e SEMPRE colocada pronta (pixel a
pixel) ou construida uma unica vez a partir de um flat; nunca e limpa,
recortada ou reconstruida depois. O QA apenas julga; o export apenas copia.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from . import document, extract
from .masks import mask_from_regions

ALPHA_ON = 16  # acima disso o pixel conta como parte da trait


def op_build_mask(name, kind, regions=None, from_file=None):
    if kind not in ("paint", "protected"):
        raise ValueError("kind deve ser 'paint' ou 'protected'")
    meta = document.load(name)
    base = document.base_image(meta)
    if from_file:
        from .masks import load_mask
        m = load_mask(from_file, base.size)
    elif regions:
        if isinstance(regions, str):
            regions = json.loads(regions)
        m = mask_from_regions(base.size, regions, base=base)
    else:
        raise ValueError("informe regions (JSON) ou from_file")
    out = meta["dir"] / f"{kind}_mask.png"
    m.save(out)
    qa_file = meta["dir"] / "qa" / "qa.json"
    if qa_file.exists():                     # politica mudou -> QA anterior invalido
        qa_file.unlink()
    cov = round(float((np.asarray(m) > 127).mean()) * 100, 2)
    return {"mask": str(out), "active_area_pct": cov}


def op_place_trait(name, image_path):
    """Coloca uma imagem RGBA transparente na camada 2, pixel a pixel."""
    meta = document.load(name)
    canvas = tuple(meta["canvas"])
    im = Image.open(image_path)
    if im.format != "PNG" or im.mode != "RGBA":
        raise ValueError(
            f"trait deve ser PNG RGBA nativo; recebido {im.format} {im.mode}"
        )
    im.load()
    a = np.asarray(im.getchannel("A"))
    opaque_pct = float((a > 250).mean()) * 100
    if opaque_pct > 97:
        raise ValueError(
            f"imagem {opaque_pct:.1f}% opaca — isso e uma imagem chapada, nao "
            "uma camada transparente. Gere com fundo transparente ou use "
            "extract_trait_from_flat.")

    if im.size != canvas:
        raise ValueError(
            f"trait {im.size} diferente do canvas travado {canvas}; "
            "resize, padding e translacao sao proibidos"
        )

    document.set_trait_file(meta, image_path)
    aa = np.asarray(im.getchannel("A"))
    return {
        "trait": str(meta["dir"] / "trait.png"),
        "ora": str(meta["dir"] / "document.ora"),
        "coverage_canvas_pct": round(float((aa > ALPHA_ON).mean()) * 100, 2),
        "next": "rode qa para validar e export_trait para finalizar",
    }


def op_set_base_visibility(name, visible, order="over"):
    return document.set_base_visibility(document.load(name), visible, order=order)


def op_inspect(name):
    return document.inspect(name)


def op_extract_from_flat(name, image_path, t0=12, t1=40, open_px=1,
                         feather=1.0):
    """Fallback: constroi a camada 2 a partir de uma imagem CHAPADA do
    personagem ja vestido, por diferenca deterministica contra a base."""
    meta = document.load(name)
    base = document.base_image(meta)
    paint = document.get_mask(meta, "paint")
    if paint is None:
        raise RuntimeError("defina a paint_mask antes (build_mask)")
    prot = document.get_mask(meta, "protected")

    gen = Image.open(image_path)
    trait, info, _ = extract.extract_layer(
        base, gen, paint, prot, t0=t0, t1=t1, open_px=open_px, feather=feather)
    document.set_trait(meta, trait)
    info.update({
        "trait": str(meta["dir"] / "trait.png"),
        "ora": str(meta["dir"] / "document.ora"),
        "next": "rode qa para validar e export_trait para finalizar",
    })
    return info


def op_qa(name, order="over", min_coverage_pct=1.0):
    """Julga a camada 2 atual. Nao modifica nenhum pixel, nunca."""
    meta = document.load(name)
    base = document.base_image(meta)
    trait = document.trait_image(meta)
    a = np.asarray(trait.getchannel("A"))
    on = a > ALPHA_ON

    paint = document.get_mask(meta, "paint")
    prot = document.get_mask(meta, "protected")
    paint_a = (np.asarray(paint) > 127) if paint is not None else np.ones_like(on)
    prot_a = (np.asarray(prot) > 127) if prot is not None else np.zeros_like(on)

    violations = int((on & prot_a).sum())
    outside = int((on & ~paint_a & ~prot_a).sum())
    coverage = round(float(on.mean()) * 100, 2)

    problems = []
    if violations:
        problems.append(f"{violations} px de trait em zona protegida")
    if coverage < min_coverage_pct:
        problems.append(f"camada 2 quase vazia (cobertura {coverage}%)")

    qa_dir = meta["dir"] / "qa"
    extract.compose(base, trait, order=order).save(qa_dir / "preview.png")
    extract.on_checkerboard(trait).save(qa_dir / "trait_alone.png")
    extract.qa_overlay(base, trait, {"invasion": on & prot_a}).save(
        qa_dir / "overlay.png")

    result = {
        "pass": not problems,
        "problems": problems,
        "violations_px": violations,
        "outside_paint_px": outside,
        "coverage_canvas_pct": coverage,
        "preview": str(qa_dir / "preview.png"),
        "trait_alone": str(qa_dir / "trait_alone.png"),
        "overlay": str(qa_dir / "overlay.png"),
        "trait_sha1": document.trait_sha1(meta),
        "checked": datetime.now(timezone.utc).isoformat(),
    }
    (qa_dir / "qa.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def op_export(name, dest=None, force=False, order="over"):
    """'Remove a base': entrega a camada 2 sozinha (copia byte a byte) + .ora."""
    meta = document.load(name)
    qa_file = meta["dir"] / "qa" / "qa.json"
    if not qa_file.exists():
        raise RuntimeError("rode qa antes de exportar")
    qa = json.loads(qa_file.read_text(encoding="utf-8"))
    if qa.get("trait_sha1") != document.trait_sha1(meta):
        raise RuntimeError("camada 2 mudou depois do ultimo qa — rode qa de novo")
    if not qa.get("pass") and not force:
        raise RuntimeError(
            f"QA reprovado ({'; '.join(qa.get('problems', []))}). "
            "Corrija a camada 2 ou exporte com force=true.")

    dest_dir = Path(dest) if dest else meta["dir"] / "exports"
    dest_dir.mkdir(parents=True, exist_ok=True)
    trait_png = dest_dir / f"{meta['name']}_trait.png"
    shutil.copyfile(meta["dir"] / "trait.png", trait_png)  # byte a byte
    ora_out = dest_dir / f"{meta['name']}.ora"
    document.write_ora_file(meta, order=order)
    shutil.copyfile(meta["dir"] / "document.ora", ora_out)
    return {"trait_png": str(trait_png), "ora": str(ora_out),
            "qa_pass": bool(qa.get("pass")),
            "trait_sha256": document.file_sha256(trait_png)}
