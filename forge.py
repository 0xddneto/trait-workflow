"""A Forja: converte um render CHAPADO do personagem ja vestido (qualquer
tamanho, fundo solido) em PNG RGBA nativo no canvas do documento.

Matematica deterministica de ponta a ponta — sem IA, sem chroma-key, sem
adivinhacao. Ferramenta SEPARADA do MCP: ela so produz o arquivo; quem coloca,
julga e exporta e o proprio MCP (place_trait -> qa -> export_trait), intocado.

Passos:
  1. cor de fundo do render estimada pelos cantos (mediana);
  2. resize deterministico para o canvas (LANCZOS) — antes de a camada nascer;
  3. registro opcional: busca em grade de escala/deslocamento que minimiza a
     diferenca na regiao onde a base DEVE aparecer (fora da paint_mask);
  4. extracao por diferenca contra a base travada (camada2 = render - base);
  5. descontaminacao de borda: c_fg = (c_obs - (1-a)*c_base) / a  (algebra);
  6. PNG RGBA nativo no canvas -> pronto para place_trait.

Uso:
  py -3.12 forge.py <documento> --flat render.png [--out saida.png]
      [--no-register] [--no-decontaminate] [--t0 12 --t1 40]
      [--open-px 1 --feather 1.0] [--place]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trait_workflow import document, pipeline
from trait_workflow.extract import extract_layer, flatten


def estimate_bg(im_rgb, patch=16):
    """Mediana dos quatro cantos = cor de fundo do render."""
    a = np.asarray(im_rgb.convert("RGB"))
    corners = np.concatenate([
        a[:patch, :patch].reshape(-1, 3),
        a[:patch, -patch:].reshape(-1, 3),
        a[-patch:, :patch].reshape(-1, 3),
        a[-patch:, -patch:].reshape(-1, 3),
    ])
    return tuple(int(v) for v in np.median(corners, axis=0))


def fit_to_canvas(gen, canvas, bg, scale=1.0, dx=0, dy=0):
    """Render redimensionado para o canvas e colado com escala/offset dados."""
    W, H = canvas
    sw = max(1, round(W * scale))
    sh = max(1, round(H * scale))
    g = gen.convert("RGB").resize((sw, sh), Image.LANCZOS)
    out = Image.new("RGB", (W, H), bg)
    out.paste(g, ((W - sw) // 2 + dx, (H - sh) // 2 + dy))
    return out


def register(gen, base_flat, ref_mask, bg, scales=None, max_shift=24, down=4):
    """Busca em grade (deterministica) da escala/offset que melhor alinha o
    render com a base, medida so onde a base deve aparecer (ref_mask)."""
    if scales is None:
        scales = [0.96 + i * 0.01 for i in range(9)]      # 0.96..1.04
    W, H = base_flat.size
    bf = np.asarray(base_flat.convert("L"), np.float32)[::down, ::down]
    rm = ref_mask[::down, ::down]
    if not rm.any():
        return 1.0, 0, 0
    step = max_shift // down
    best = (float("inf"), 1.0, 0, 0)
    for s in scales:
        gl = np.asarray(fit_to_canvas(gen, (W, H), bg, s).convert("L"),
                        np.float32)[::down, ::down]
        for dy in range(-step, step + 1):
            for dx in range(-step, step + 1):
                shifted = np.roll(gl, (dy, dx), (0, 1))
                err = float(np.abs(shifted - bf)[rm].mean())
                if err < best[0]:
                    best = (err, s, dx * down, dy * down)
    return best[1], best[2], best[3]


def magnet_diff(gen_rgb, base_flat, radius=3, patch=5):
    """O ima da base: diferenca minima sobre deslocamentos locais (+-radius),
    comparando retalhos (patch x patch), nao pixels isolados. Pele redesenhada
    alguns pixels fora do lugar 'gruda' de volta na base (diff ~0); o que nao
    existe na base em lugar nenhum proximo — a trait — fica com diff alto.
    Deterministico; sem mascara."""
    from scipy.ndimage import uniform_filter
    g = np.asarray(gen_rgb, np.float32)
    b = np.asarray(base_flat, np.float32)
    best = None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = np.roll(b, (dy, dx), (0, 1))
            d = np.abs(g - shifted).max(axis=2)
            d = uniform_filter(d, size=patch)
            best = d if best is None else np.minimum(best, d)
    return best


def extract_pure(base, aligned, bg, t0=10, t1=32, radius=3, patch=5,
                 open_px=1, feather=1.0, protected=None):
    """Extracao SEM mascara: alpha vem do ima da base. Mascara protected,
    se existir, e so cinto de seguranca extra (nunca necessaria)."""
    from PIL import ImageFilter
    base_flat = flatten(base, bg)
    gen_rgb = aligned.convert("RGB")
    diff = magnet_diff(gen_rgb, base_flat)
    alpha = np.clip((diff - t0) / max(t1 - t0, 1) * 255, 0, 255).astype(np.uint8)

    prot_a = None
    if protected is not None:
        prot_a = np.asarray(protected.convert("L")) > 127
        alpha[prot_a] = 0

    a_im = Image.fromarray(alpha, "L")
    for _ in range(int(open_px)):
        a_im = a_im.filter(ImageFilter.MinFilter(3))
    for _ in range(int(open_px)):
        a_im = a_im.filter(ImageFilter.MaxFilter(3))
    if feather > 0:
        a_im = a_im.filter(ImageFilter.GaussianBlur(feather))
    a = np.asarray(a_im, np.uint8).copy()
    if prot_a is not None:
        a[prot_a] = 0

    trait = Image.fromarray(
        np.dstack([np.asarray(gen_rgb, np.uint8), a]), "RGBA")
    info = {"coverage_pct": round(float((a > 32).mean()) * 100, 2),
            "modo": "pure (ima da base, sem mascara)"}
    return trait, info


def decontaminate(trait, base_flat):
    """Remove o vazamento da cor da base nos pixels semi-transparentes:
    c_obs = a*c_fg + (1-a)*c_base  =>  c_fg = (c_obs - (1-a)*c_base) / a."""
    t = np.asarray(trait, np.float32)
    b = np.asarray(base_flat.convert("RGB"), np.float32)
    a = t[..., 3:4] / 255.0
    sem = (t[..., 3] > 8) & (t[..., 3] < 247)
    fg = (t[..., :3] - (1.0 - a) * b) / np.maximum(a, 1e-3)
    out = t.copy()
    out[sem, :3] = np.clip(fg[sem], 0, 255)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def forge(doc_name, flat_path, out=None, do_register=True,
          do_decontaminate=True, t0=12, t1=40, open_px=1, feather=1.0,
          pure=False):
    meta = document.load(doc_name)
    canvas = tuple(meta["canvas"])
    base = document.base_image(meta)
    paint = document.get_mask(meta, "paint")
    if paint is None and not pure:
        raise RuntimeError(
            "documento sem paint_mask — defina com pipeline.op_build_mask, "
            "ou use o modo pure (ima da base, sem mascara)")
    protected = document.get_mask(meta, "protected")

    gen = Image.open(flat_path)
    bg = estimate_bg(gen)
    base_flat = flatten(base, bg)

    info = {"flat": str(flat_path), "flat_size": list(gen.size),
            "bg_estimado": list(bg)}

    scale, dx, dy = 1.0, 0, 0
    if do_register:
        base_a = np.asarray(base.getchannel("A")) > 127
        if paint is not None:
            ref = base_a & ~(np.asarray(paint) > 127)  # onde a base DEVE aparecer
            if protected is not None:
                ref |= np.asarray(protected) > 127
        else:
            ref = base_a
        scale, dx, dy = register(gen, base_flat, ref, bg)
    info["registro"] = {"scale": scale, "dx": dx, "dy": dy}

    aligned = fit_to_canvas(gen, canvas, bg, scale, dx, dy)
    if pure:
        trait, ext_info = extract_pure(
            base, aligned, bg, t0=t0, t1=t1,
            open_px=open_px, feather=feather, protected=protected)
    else:
        trait, ext_info, _ = extract_layer(
            base, aligned, paint, protected,
            t0=t0, t1=t1, open_px=open_px, feather=feather, bg=bg)
    info.update(ext_info)

    if do_decontaminate:
        trait = decontaminate(trait, base_flat)

    out = Path(out) if out else meta["dir"] / "forge" / "trait_forged.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    trait.save(out)
    info["out"] = str(out)
    info["next"] = f"place_trait('{doc_name}', '{out}') -> qa -> export_trait"
    return info


def main():
    ap = argparse.ArgumentParser(prog="forge")
    ap.add_argument("name", help="nome do documento (create_document antes)")
    ap.add_argument("--flat", required=True,
                    help="render chapado do personagem ja vestido")
    ap.add_argument("--out")
    ap.add_argument("--no-register", action="store_true")
    ap.add_argument("--no-decontaminate", action="store_true")
    ap.add_argument("--t0", type=int, default=12)
    ap.add_argument("--t1", type=int, default=40)
    ap.add_argument("--open-px", type=int, default=1)
    ap.add_argument("--feather", type=float, default=1.0)
    ap.add_argument("--place", action="store_true",
                    help="ja coloca a saida na camada 2 via place_trait")
    ap.add_argument("--pure", action="store_true",
                    help="ima da base: sem mascara (recomendado t0=10 t1=32)")
    a = ap.parse_args()

    info = forge(a.name, a.flat, out=a.out, do_register=not a.no_register,
                 do_decontaminate=not a.no_decontaminate,
                 t0=a.t0, t1=a.t1, open_px=a.open_px, feather=a.feather,
                 pure=a.pure)
    if a.place:
        info["place"] = pipeline.op_place_trait(a.name, info["out"])
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
