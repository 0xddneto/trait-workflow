"""CLI para testar o fluxo sem host MCP.

Exemplos:
  py -3.12 cli.py create hidden --base base.png --paint paint.png --protected prot.png
  py -3.12 cli.py place hidden --image trait_rgba.png
  py -3.12 cli.py from-flat hidden --image personagem_vestido.png
  py -3.12 cli.py qa hidden
  py -3.12 cli.py export hidden
  py -3.12 cli.py list
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trait_workflow import document, pipeline


def main():
    ap = argparse.ArgumentParser(prog="trait-workflow")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("name")
    c.add_argument("--base", required=True)
    c.add_argument("--paint")
    c.add_argument("--protected")

    m = sub.add_parser("mask")
    m.add_argument("name")
    m.add_argument("--kind", choices=["paint", "protected"], required=True)
    m.add_argument("--regions")
    m.add_argument("--from-file")

    p = sub.add_parser("place")
    p.add_argument("name")
    p.add_argument("--image", required=True)
    p.add_argument("-x", type=int, default=0)
    p.add_argument("-y", type=int, default=0)
    p.add_argument("--allow-resize", action="store_true")

    f = sub.add_parser("from-flat")
    f.add_argument("name")
    f.add_argument("--image", required=True)
    f.add_argument("--t0", type=int, default=12)
    f.add_argument("--t1", type=int, default=40)
    f.add_argument("--open-px", type=int, default=1)
    f.add_argument("--feather", type=float, default=1.0)

    q = sub.add_parser("qa")
    q.add_argument("name")
    q.add_argument("--order", default="over", choices=["over", "behind"])
    q.add_argument("--min-coverage", type=float, default=1.0)

    x = sub.add_parser("export")
    x.add_argument("name")
    x.add_argument("--dest")
    x.add_argument("--force", action="store_true")
    x.add_argument("--order", default="over", choices=["over", "behind"])

    sub.add_parser("list")

    a = ap.parse_args()
    if a.cmd == "create":
        out = document.create(a.name, a.base, a.paint, a.protected)
    elif a.cmd == "mask":
        out = pipeline.op_build_mask(a.name, a.kind, regions=a.regions,
                                     from_file=a.from_file)
    elif a.cmd == "place":
        out = pipeline.op_place_trait(a.name, a.image, x=a.x, y=a.y,
                                      allow_resize=a.allow_resize)
    elif a.cmd == "from-flat":
        out = pipeline.op_extract_from_flat(a.name, a.image, t0=a.t0, t1=a.t1,
                                            open_px=a.open_px,
                                            feather=a.feather)
    elif a.cmd == "qa":
        out = pipeline.op_qa(a.name, order=a.order,
                             min_coverage_pct=a.min_coverage)
    elif a.cmd == "export":
        out = pipeline.op_export(a.name, dest=a.dest, force=a.force,
                                 order=a.order)
    elif a.cmd == "list":
        out = document.list_documents()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
