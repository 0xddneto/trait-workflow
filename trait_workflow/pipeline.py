"""Operacoes de alto nivel usadas tanto pelo servidor MCP quanto pela CLI."""

import io
import json

import numpy as np
from PIL import Image, ImageChops

from . import backends, extract, ora, projects
from .masks import mask_from_regions


def _gen_inputs(meta):
    """Prepara (e cacheia) a base achatada e a mascara de inpainting."""
    p = meta["dir"]
    gen_input = p / "gen_input.png"
    if not gen_input.exists():
        extract.flatten(projects.base_image(meta)).save(gen_input)

    gen_mask = p / "gen_mask.png"
    paint = projects.get_mask(meta, "paint")
    if paint is not None and not gen_mask.exists():
        prot = projects.get_mask(meta, "protected")
        allowed = ImageChops.subtract(paint, prot) if prot else paint
        allowed.save(gen_mask)
    return gen_input, (gen_mask if gen_mask.exists() else None)


def op_build_mask(name, kind, regions=None, from_file=None):
    if kind not in ("paint", "protected"):
        raise ValueError("kind deve ser 'paint' ou 'protected'")
    meta = projects.load(name)
    base = projects.base_image(meta)
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
    # invalida cache de mascara de geracao
    gm = meta["dir"] / "gen_mask.png"
    if gm.exists():
        gm.unlink()
    cov = round(float((np.asarray(m) > 127).mean()) * 100, 2)
    return {"mask": str(out), "active_area_pct": cov}


def op_add_candidate(name, image_path):
    """Registra uma imagem gerada externamente (ex.: imagegen do Codex) como
    candidato. A imagem deve ser o personagem-base ja vestido/decorado."""
    meta = projects.load(name)
    folder = meta["dir"] / "candidates"
    im = Image.open(image_path).convert("RGB")
    if im.size != tuple(meta["canvas"]):
        im = im.resize(tuple(meta["canvas"]), Image.LANCZOS)
    idx = projects.next_index(folder, "cand")
    f = folder / f"cand_{idx:03d}.png"
    im.save(f)
    hist = meta["dir"] / "history.jsonl"
    with hist.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"external": str(image_path), "files": [str(f)]}) + "\n")
    return {"candidate": str(f), "source": str(image_path)}


def op_generate(name, prompt, backend="gemini", model=None, n=1, guard=True):
    meta = projects.load(name)
    gen_input, gen_mask = _gen_inputs(meta)
    folder = meta["dir"] / "candidates"
    out = []
    for _ in range(max(1, int(n))):
        png = backends.generate(backend, prompt, gen_input,
                                mask_path=gen_mask, model=model, guard=guard)
        idx = projects.next_index(folder, "cand")
        f = folder / f"cand_{idx:03d}.png"
        Image.open(io.BytesIO(png)).convert("RGB").save(f)
        out.append(str(f))
    hist = meta["dir"] / "history.jsonl"
    with hist.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"prompt": prompt, "backend": backend,
                             "model": model, "files": out}) + "\n")
    return {"candidates": out, "backend": backend}


def op_extract(name, candidate="latest", t0=12, t1=40, open_px=1,
               feather=1.0, order="over"):
    meta = projects.load(name)
    base = projects.base_image(meta)
    paint = projects.get_mask(meta, "paint")
    if paint is None:
        raise RuntimeError("projeto sem paint_mask: crie com build_mask")
    prot = projects.get_mask(meta, "protected")

    cand_file = projects.resolve_candidate(meta, candidate)
    gen = Image.open(cand_file)

    trait, info, debug = extract.extract_layer(
        base, gen, paint, prot, t0=t0, t1=t1, open_px=open_px, feather=feather)

    idx = cand_file.stem.split("_")[-1]
    p = meta["dir"]
    trait_file = p / "layers" / f"trait_{idx}.png"
    trait.save(trait_file)
    extract.compose(base, trait, order=order).save(p / "qa" / f"preview_{idx}.png")
    extract.qa_overlay(base, trait, debug).save(p / "qa" / f"overlay_{idx}.png")

    info.update({
        "candidate": str(cand_file),
        "trait": str(trait_file),
        "preview": str(p / "qa" / f"preview_{idx}.png"),
        "overlay": str(p / "qa" / f"overlay_{idx}.png"),
    })
    (p / "qa" / f"qa_{idx}.json").write_text(
        json.dumps(info, indent=2), encoding="utf-8")
    return info


def op_export(name, candidate="latest", dest=None, write_ora=True, order="over"):
    meta = projects.load(name)
    base = projects.base_image(meta)
    cand_file = projects.resolve_candidate(meta, candidate)
    idx = cand_file.stem.split("_")[-1]
    trait_file = meta["dir"] / "layers" / f"trait_{idx}.png"
    if not trait_file.exists():
        raise FileNotFoundError(f"camada nao extraida ainda: rode extract ({trait_file})")

    trait = Image.open(trait_file).convert("RGBA")
    from pathlib import Path
    dest_dir = Path(dest) if dest else meta["dir"] / "exports"
    dest_dir.mkdir(parents=True, exist_ok=True)

    final_png = dest_dir / f"{meta['name']}_{idx}.png"
    trait.save(final_png)
    out = {"trait_png": str(final_png)}
    if write_ora:
        merged = extract.compose(base, trait, order=order)
        ora_file = dest_dir / f"{meta['name']}_{idx}.ora"
        ora.write_ora(ora_file, base, trait, merged)
        out["ora"] = str(ora_file)
    return out
