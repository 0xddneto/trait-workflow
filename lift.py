"""O Lift: converte um render da TRAIT SOZINHA sobre fundo solido em PNG RGBA
nativo — sem base no quadro, sem mascara, sem adivinhacao.

E a rota "camada 2 direto do gerador": o agente pede ao imagegen APENAS a
trait (roupa, item, aura...) flutuando sobre uma cor solida (ideal: magenta
#FF00FF). Como nao ha personagem no quadro, nao existe anatomia redesenhada
para vazar. Recuperar o alpha de um fundo solido conhecido e algebra
invertivel da composicao (c_obs = a*c_fg + (1-a)*bg):

  1. cor de fundo estimada pela mediana dos cantos;
  2. fundo = somente o que esta CONECTADO A BORDA do quadro (flood fill) —
     uma jaqueta magenta sobre fundo magenta nao vira buraco;
  3. alpha suave na banda de transicao (anti-aliasing preservado);
  4. descontaminacao: c_fg = (c_obs - (1-a)*bg) / a;
  5. resize deterministico para o canvas (antes de a camada nascer);
  6. PNG RGBA nativo -> place_trait -> qa -> export_trait (MCP intocado).

Uso:
  py -3.12 lift.py <documento> --image render_trait_sozinha.png [--out x.png]
      [--t0 24 --t1 96] [--no-decontaminate] [--place]
  py -3.12 lift.py --canvas 1024x1024 --image render.png --out trait.png
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))


def estimate_bg(im_rgb, patch=16):
    a = np.asarray(im_rgb.convert("RGB"))
    corners = np.concatenate([
        a[:patch, :patch].reshape(-1, 3),
        a[:patch, -patch:].reshape(-1, 3),
        a[-patch:, :patch].reshape(-1, 3),
        a[-patch:, -patch:].reshape(-1, 3),
    ])
    return tuple(int(v) for v in np.median(corners, axis=0))


def border_connected(similar):
    """Componentes de `similar` que tocam a borda do quadro (flood fill)."""
    from scipy.ndimage import binary_propagation
    seed = np.zeros_like(similar)
    seed[0, :] = similar[0, :]
    seed[-1, :] = similar[-1, :]
    seed[:, 0] = similar[:, 0]
    seed[:, -1] = similar[:, -1]
    return binary_propagation(seed, mask=similar)


def lift(image_path, canvas, t0=24, t1=96, decontaminate=True):
    gen = Image.open(image_path).convert("RGB")
    bg = estimate_bg(gen)
    c = np.asarray(gen, np.int16)
    dist = np.abs(c - np.array(bg, np.int16)).max(axis=2).astype(np.float32)

    # fundo de verdade = parecido com o bg E conectado a borda do quadro
    bg_region = border_connected(dist < t1)

    alpha = np.full(dist.shape, 255, np.uint8)
    soft = np.clip((dist - t0) / max(t1 - t0, 1) * 255, 0, 255).astype(np.uint8)
    alpha[bg_region] = soft[bg_region]

    out = np.dstack([c.astype(np.uint8), alpha])
    if decontaminate:
        a = alpha.astype(np.float32)[..., None] / 255.0
        sem = (alpha > 8) & (alpha < 247)
        fg = (c.astype(np.float32) - (1.0 - a) * np.array(bg, np.float32)) \
            / np.maximum(a, 1e-3)
        out[sem, :3] = np.clip(fg[sem], 0, 255).astype(np.uint8)

    im = Image.fromarray(out, "RGBA")
    if canvas and im.size != tuple(canvas):
        im = im.resize(tuple(canvas), Image.LANCZOS)

    stats = {
        "bg_estimado": list(bg),
        "tamanho_render": list(gen.size),
        "opacidade_pct": round(float((np.asarray(im.getchannel('A')) > 16)
                                     .mean()) * 100, 2),
    }
    return im, stats


def main():
    ap = argparse.ArgumentParser(prog="lift")
    ap.add_argument("name", nargs="?",
                    help="documento (usa o canvas dele); ou use --canvas")
    ap.add_argument("--image", required=True,
                    help="render da trait SOZINHA sobre fundo solido")
    ap.add_argument("--canvas", help="ex. 1024x1024 (se nao houver documento)")
    ap.add_argument("--out")
    ap.add_argument("--t0", type=int, default=24)
    ap.add_argument("--t1", type=int, default=96)
    ap.add_argument("--no-decontaminate", action="store_true")
    ap.add_argument("--place", action="store_true",
                    help="ja coloca a saida na camada 2 via place_trait")
    a = ap.parse_args()

    meta = None
    if a.name:
        from trait_workflow import document
        meta = document.load(a.name)
        canvas = meta["canvas"]
    elif a.canvas:
        canvas = [int(v) for v in a.canvas.lower().split("x")]
    else:
        ap.error("informe um documento ou --canvas WxH")

    im, stats = lift(a.image, canvas, t0=a.t0, t1=a.t1,
                     decontaminate=not a.no_decontaminate)
    out = Path(a.out) if a.out else (
        meta["dir"] / "forge" / "trait_lifted.png" if meta
        else Path(a.image).with_name("trait_lifted.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    stats["out"] = str(out)

    if a.place and meta:
        from trait_workflow import pipeline
        stats["place"] = pipeline.op_place_trait(meta["name"], str(out))
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
