"""Extracao deterministica da camada de trait. Sem IA em nenhum passo.

A base e conhecida pixel a pixel. O candidato gerado e comparado com a base
achatada sobre o mesmo fundo; so vira trait o que (1) difere alem do limiar,
(2) esta dentro da mascara de pintura e (3) fora da mascara protegida.
"""

import numpy as np
from PIL import Image, ImageFilter

WHITE = (255, 255, 255)


def flatten(base_rgba, bg=WHITE):
    out = Image.new("RGB", base_rgba.size, bg)
    out.paste(base_rgba, mask=base_rgba.getchannel("A"))
    return out


def extract_layer(base, gen, paint, protected=None,
                  t0=12, t1=40, open_px=1, feather=1.0, bg=WHITE):
    """Retorna (trait RGBA, info dict, debug dict de arrays booleanos)."""
    size = base.size
    if gen.size != size:
        gen = gen.resize(size, Image.LANCZOS)
    gen_rgb = gen.convert("RGB")

    base_flat = np.asarray(flatten(base, bg), dtype=np.int16)
    g = np.asarray(gen_rgb, dtype=np.int16)
    diff = np.abs(g - base_flat).max(axis=2).astype(np.float32)

    # rampa suave: t0 = identico a base, t1 = certamente trait
    alpha = np.clip((diff - t0) / max(t1 - t0, 1) * 255.0, 0, 255).astype(np.uint8)
    changed = alpha > 32

    paint_a = np.asarray(paint.convert("L")) > 127
    prot_a = (np.asarray(protected.convert("L")) > 127) if protected is not None \
        else np.zeros_like(paint_a)
    allowed = paint_a & ~prot_a

    # quanto o gerador TENTOU invadir (informativo; sera zerado a seguir)
    invasion = changed & prot_a
    outside = changed & ~paint_a & ~prot_a
    alpha[~allowed] = 0

    a_im = Image.fromarray(alpha, "L")
    for _ in range(int(open_px)):          # abertura morfologica: mata pontas soltas
        a_im = a_im.filter(ImageFilter.MinFilter(3))
    for _ in range(int(open_px)):
        a_im = a_im.filter(ImageFilter.MaxFilter(3))
    if feather > 0:
        a_im = a_im.filter(ImageFilter.GaussianBlur(feather))

    a = np.asarray(a_im, dtype=np.uint8).copy()
    a[~allowed] = 0                        # o blur nunca pode vazar em zona proibida

    trait = Image.fromarray(
        np.dstack([np.asarray(gen_rgb, dtype=np.uint8), a]), "RGBA")

    allowed_n = max(int(allowed.sum()), 1)
    info = {
        "coverage_pct": round(float((a > 32).sum()) / allowed_n * 100, 2),
        "invasion_attempt_px": int(invasion.sum()),
        "outside_paint_px": int(outside.sum()),
        "protected_px_in_layer": 0,        # por construcao
        "thresholds": {"t0": t0, "t1": t1, "open_px": open_px, "feather": feather},
    }
    debug = {"invasion": invasion, "outside": outside}
    return trait, info, debug


def compose(base, trait, order="over"):
    """Preview final. order='over' (roupa, item) ou 'behind' (aura, fundo)."""
    canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
    if order == "behind":
        canvas.alpha_composite(trait)
        canvas.alpha_composite(base)
    else:
        canvas.alpha_composite(base)
        canvas.alpha_composite(trait)
    return canvas


def qa_overlay(base, trait, debug):
    """Composicao + tinta vermelha onde o gerador tentou invadir zona protegida."""
    over = compose(base, trait).convert("RGB")
    arr = np.asarray(over, dtype=np.uint8).copy()
    inv = debug["invasion"]
    arr[inv] = (arr[inv] * 0.4 + np.array([255, 0, 0]) * 0.6).astype(np.uint8)
    return Image.fromarray(arr, "RGB")
