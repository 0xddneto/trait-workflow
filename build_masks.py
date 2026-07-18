"""Reconstroi as mascaras canonicas da colecao a partir da arte da base.

Anatomia extraida dos CONTORNOS REAIS (flood fill entre linhas escuras),
nao desenhada a mao:

  - contorno = canal minimo < 110 (linhas pretas + terminadores de sombra);
  - cabeca   = uniao de TODAS as celulas na zona superior (bbox y<=490)
               + todo corpo acima de y=430 (la so existe cabeca) + fechamento;
  - orelhas  = celulas proprias (entram pela regra da zona superior);
  - maos     = flood a partir da palma, cortado na linha do pulso (y=673,
               herdada das mascaras aprovadas do workbench);
  - protected = (cabeca | maos) dilatado 3px, fechado, limitado ao corpo;
  - paint     = corpo dilatado 6px menos protected;
  - stencil   = base achatada em branco com protected em magenta #FF00FF.

Politica: o degrau no queixo e proposital — e onde golas pintam. Golas nao
sobem por cima da cabeca; visualmente passam por tras dela.

Uso: py -3.12 build_masks.py [--base caminho] [--out pasta]
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import (binary_closing, binary_dilation, binary_fill_holes,
                           binary_propagation, label)

CANON = Path(r"C:/Nova pasta/DN/DEV/projeto MOBs/assets/base/masks_canonical")

OUTLINE_THR = 110      # canal minimo abaixo disso = linha/sombra divisoria
HEAD_ZONE_Y = 490      # celulas inteiramente acima disso sao cabeca/orelha
HEAD_SOLID_Y = 430     # acima disso, TODO corpo e cabeca
WRIST_Y = 673          # linha do pulso (das mascaras aprovadas do workbench)
HAND_SEEDS = [(340, 735), (700, 735)]


def build(base_path, out_dir):
    base = Image.open(base_path).convert("RGBA")
    a = np.asarray(base)
    body = a[..., 3] > 127
    outline = binary_dilation(body & (a[..., :3].min(axis=2) < OUTLINE_THR),
                              iterations=1)
    cells = body & ~outline

    lab, n = label(cells)
    cabeca = np.zeros_like(cells)
    for i in range(1, n + 1):
        comp = lab == i
        if comp.sum() < 50:
            continue
        ys, _ = np.where(comp)
        if 50 <= ys.min() and ys.max() <= HEAD_ZONE_Y:
            cabeca |= comp
    yy = np.arange(body.shape[0])[:, None]
    cabeca |= body & (yy <= HEAD_SOLID_Y)
    cabeca = binary_fill_holes(binary_closing(cabeca, iterations=3))

    maos = np.zeros_like(cells)
    for x, y in HAND_SEEDS:
        if cells[y, x]:
            seed = np.zeros_like(cells)
            seed[y, x] = True
            maos |= binary_propagation(seed, mask=cells)
    maos &= yy >= WRIST_Y

    prot = binary_dilation(cabeca | maos, iterations=3) & body
    prot = binary_fill_holes(binary_closing(prot, iterations=2)) & body
    paint = binary_dilation(body, iterations=6) & ~prot

    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray((prot * 255).astype(np.uint8), "L").save(
        out_dir / "protected.png")
    Image.fromarray((paint * 255).astype(np.uint8), "L").save(
        out_dir / "paint.png")
    flat = Image.new("RGB", base.size, (255, 255, 255))
    flat.paste(base, mask=base.getchannel("A"))
    arr = np.asarray(flat).copy()
    arr[prot] = (255, 0, 255)
    Image.fromarray(arr).save(out_dir / "stencil.png")
    base.save(out_dir / "base_1024.png")
    return {"protected_pct": round(prot.mean() * 100, 1),
            "paint_pct": round(paint.mean() * 100, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(CANON / "base_1024.png"))
    ap.add_argument("--out", default=str(CANON))
    a = ap.parse_args()
    print(build(a.base, Path(a.out)))
