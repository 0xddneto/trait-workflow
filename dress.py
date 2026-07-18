"""dress.py — do PROMPT a trait exportada, em um comando. Gratis.

  py -3.12 dress.py red-jacket --prompt "red leather biker jacket, dark jeans"

Como funciona (e por que nao tem erro estrutural):
  1. INPAINTING (Cloudflare Workers AI, gratis): a base e enviada com a
     mascara canonica — o motor SO PODE pintar dentro dela. A base e travada
     ANTES de a pintura existir, nao depois.
  2. RECOMPOSICAO BYTE A BYTE: fora da mascara, os pixels da base original
     sao restaurados exatamente. Qualquer deriva do decoder desaparece.
  3. REMOVER A CAMADA 1: subtracao contra a base conhecida — fora da mascara
     a diferenca e zero POR CONSTRUCAO; dentro, o que difere e a trait.
  4. O MCP (intocado) coloca, julga (qa) e exporta.

Ferramenta de CLI, separada do MCP — o MCP continua sem gerar imagem.
"""

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trait_workflow import document, pipeline
from forge import forge

CANON = Path(r"C:/Nova pasta/DN/DEV/projeto MOBs/assets/base/masks_canonical")
KEYS = Path.home() / ".trait-workflow" / "keys.json"
STYLE = ("chibi cartoon character, clean dark outlines, soft cel shading, "
         "flat colors")


def _png_ints(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return list(buf.getvalue())


def cf_inpaint(prompt, base_flat, paint, size, steps, guidance, seed=None):
    keys = json.loads(KEYS.read_text())
    acct, tok = keys["cloudflare_account"], keys["cloudflare_token"]
    body = {
        "prompt": f"{STYLE}, wearing {prompt}",
        "image": _png_ints(base_flat.resize((size, size), Image.LANCZOS)),
        "mask": _png_ints(paint.resize((size, size), Image.NEAREST)),
        "num_steps": steps,
        "strength": 1.0,
        "guidance": guidance,
    }
    if seed is not None:
        body["seed"] = seed
    r = requests.post(
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{acct}/ai/run/@cf/runwayml/stable-diffusion-v1-5-inpainting",
        headers={"Authorization": f"Bearer {tok}"}, json=body, timeout=180)
    ct = r.headers.get("content-type", "")
    if r.status_code != 200 or not ct.startswith("image"):
        raise RuntimeError(f"inpainting HTTP {r.status_code}: {r.text[:200]}")
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def main():
    ap = argparse.ArgumentParser(prog="dress")
    ap.add_argument("name", help="nome da trait (vira o documento)")
    ap.add_argument("--prompt", required=True,
                    help="a roupa/trait, ex. 'red leather jacket, dark jeans'")
    ap.add_argument("--base", default=str(CANON / "base_1024.png"))
    ap.add_argument("--paint", default=str(CANON / "paint.png"))
    ap.add_argument("--protected", default=str(CANON / "protected.png"))
    ap.add_argument("--size", type=int, default=512,
                    help="resolucao da geracao (512 = nativo do SD 1.5)")
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--guidance", type=float, default=7.5)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--t0", type=int, default=5)
    ap.add_argument("--t1", type=int, default=16)
    ap.add_argument("--dest")
    a = ap.parse_args()

    passos = {}

    try:
        meta = document.load(a.name)
        passos["documento"] = "ja existia"
    except FileNotFoundError:
        meta = document.create(a.name, a.base)
        passos["documento"] = "criado"
    pipeline.op_build_mask(a.name, "paint", from_file=a.paint)
    pipeline.op_build_mask(a.name, "protected", from_file=a.protected)
    meta = document.load(a.name)

    base = document.base_image(meta)
    base_flat = Image.new("RGB", base.size, (255, 255, 255))
    base_flat.paste(base, mask=base.getchannel("A"))
    paint = Image.open(a.paint).convert("L").resize(base.size, Image.NEAREST)

    # 1. inpainting: base travada ANTES de pintar
    gen = cf_inpaint(a.prompt, base_flat, paint, a.size, a.steps,
                     a.guidance, a.seed)
    passos["inpainting"] = f"{a.size}x{a.size} ok"

    # 2. recomposicao byte a byte: fora da mascara = base exata
    dressed = base_flat.copy()
    dressed.paste(gen.resize(base.size, Image.LANCZOS), mask=paint)
    render = meta["dir"] / "forge" / "dressed_render.png"
    render.parent.mkdir(parents=True, exist_ok=True)
    dressed.save(render)

    # 3. remover a camada 1 (subtracao) e colocar na camada 2
    info = forge(a.name, str(render), t0=a.t0, t1=a.t1)
    passos["remocao_camada_1"] = {"cobertura": info["coverage_pct"]}
    pipeline.op_place_trait(a.name, info["out"])

    # 4. o MCP julga e exporta
    qa = pipeline.op_qa(a.name)
    passos["qa"] = {k: qa[k] for k in ("pass", "problems", "violations_px",
                                       "preview", "trait_alone")}
    if qa["pass"]:
        passos["export"] = pipeline.op_export(a.name, dest=a.dest)
    else:
        passos["export"] = "BLOQUEADO pelo QA — rode de novo (outro seed)"

    print(json.dumps(passos, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
