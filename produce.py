"""Producao em um comando: exatamente o modelo 'base na camada 1, trait na
camada 2, remove a camada 1'.

  py -3.12 produce.py <trait> --render render_do_personagem_vestido.png

O render e gerado pelo agente COM A BASE NO QUADRO (imagegen vestindo o
personagem exato -> encaixe por construcao). Este script entao:

  1. cria o documento (base oficial travada na camada 1), se nao existir;
  2. aplica as mascaras canonicas da colecao (feitas uma unica vez);
  3. 'remove a camada 1': Forja = subtracao deterministica render - base
     (registro automatico de escala/posicao, fundo estimado pelos cantos);
  4. roda o QA do MCP (unico juiz, intocado);
  5. se aprovado, exporta trait PNG byte a byte + .ora final.

Tudo depois do render e matematica; nenhum pixel e inventado."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trait_workflow import document, pipeline
from forge import forge

CANON = Path(r"C:/Nova pasta/DN/DEV/projeto MOBs/assets/base/masks_canonical")
DEFAULT_BASE = CANON / "base_1024.png"


def main():
    ap = argparse.ArgumentParser(prog="produce")
    ap.add_argument("name", help="nome da trait (vira o documento)")
    ap.add_argument("--render", required=True,
                    help="render do personagem JA VESTIDO (base no quadro)")
    ap.add_argument("--base", default=str(DEFAULT_BASE))
    ap.add_argument("--paint", default=str(CANON / "paint.png"))
    ap.add_argument("--protected", default=str(CANON / "protected.png"))
    ap.add_argument("--t0", type=int, default=5)
    ap.add_argument("--t1", type=int, default=16)
    ap.add_argument("--dest", help="pasta final (padrao: exports do documento)")
    ap.add_argument("--stencil", nargs="?", const="partial",
                    choices=["partial", "full"],
                    help="o render veio de um estencil: 'partial' (anatomia "
                         "magenta, stencil.png) ou 'full' (manequim todo "
                         "magenta, stencil_full.png); subtrai contra ele")
    a = ap.parse_args()

    passos = {}

    # 1. documento (base travada na camada 1)
    try:
        document.load(a.name)
        passos["documento"] = "ja existia"
    except FileNotFoundError:
        document.create(a.name, a.base)
        passos["documento"] = "criado"

    # 2. mascaras canonicas da colecao
    pipeline.op_build_mask(a.name, "paint", from_file=a.paint)
    pipeline.op_build_mask(a.name, "protected", from_file=a.protected)
    passos["mascaras"] = "canonicas aplicadas"

    # 3. remove a camada 1 (subtracao deterministica) e coloca na camada 2
    against = None
    if a.stencil == "partial":
        against = str(CANON / "stencil.png")
    elif a.stencil == "full":
        against = str(CANON / "stencil_full.png")
    info = forge(a.name, a.render, t0=a.t0, t1=a.t1, against=against)
    passos["forja"] = {k: info[k] for k in
                       ("bg_estimado", "registro", "coverage_pct")}
    passos["place"] = pipeline.op_place_trait(a.name, info["out"])

    # 4. QA (o MCP julga; nada e retocado)
    qa = pipeline.op_qa(a.name)
    passos["qa"] = {k: qa[k] for k in
                    ("pass", "problems", "violations_px", "preview",
                     "trait_alone")}

    # 5. export somente se aprovado
    if qa["pass"]:
        passos["export"] = pipeline.op_export(a.name, dest=a.dest)
    else:
        passos["export"] = "BLOQUEADO pelo QA — gere outro render e repita"

    print(json.dumps(passos, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
