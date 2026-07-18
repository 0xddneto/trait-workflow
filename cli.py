"""CLI para testar o pipeline sem host MCP.

Exemplos:
  py -3.12 cli.py create hidden --base base.png --paint paint.png --protected prot.png
  py -3.12 cli.py generate hidden --prompt "dark high-collar jacket..." --backend gemini
  py -3.12 cli.py extract hidden
  py -3.12 cli.py export hidden
  py -3.12 cli.py list
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trait_workflow import pipeline, projects


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

    ac = sub.add_parser("add-candidate")
    ac.add_argument("name")
    ac.add_argument("--image", required=True)

    g = sub.add_parser("generate")
    g.add_argument("name")
    g.add_argument("--prompt", required=True)
    g.add_argument("--backend", default="gemini")
    g.add_argument("--model")
    g.add_argument("-n", type=int, default=1)
    g.add_argument("--no-guard", action="store_true")

    e = sub.add_parser("extract")
    e.add_argument("name")
    e.add_argument("--candidate", default="latest")
    e.add_argument("--t0", type=int, default=12)
    e.add_argument("--t1", type=int, default=40)
    e.add_argument("--open-px", type=int, default=1)
    e.add_argument("--feather", type=float, default=1.0)
    e.add_argument("--order", default="over", choices=["over", "behind"])

    x = sub.add_parser("export")
    x.add_argument("name")
    x.add_argument("--candidate", default="latest")
    x.add_argument("--dest")
    x.add_argument("--no-ora", action="store_true")
    x.add_argument("--order", default="over", choices=["over", "behind"])

    sub.add_parser("list")

    a = ap.parse_args()
    if a.cmd == "create":
        out = projects.create(a.name, a.base, a.paint, a.protected)
    elif a.cmd == "mask":
        out = pipeline.op_build_mask(a.name, a.kind, regions=a.regions,
                                     from_file=a.from_file)
    elif a.cmd == "add-candidate":
        out = pipeline.op_add_candidate(a.name, a.image)
    elif a.cmd == "generate":
        out = pipeline.op_generate(a.name, a.prompt, backend=a.backend,
                                   model=a.model, n=a.n, guard=not a.no_guard)
    elif a.cmd == "extract":
        out = pipeline.op_extract(a.name, a.candidate, t0=a.t0, t1=a.t1,
                                  open_px=a.open_px, feather=a.feather,
                                  order=a.order)
    elif a.cmd == "export":
        out = pipeline.op_export(a.name, a.candidate, dest=a.dest,
                                 write_ora=not a.no_ora, order=a.order)
    elif a.cmd == "list":
        out = projects.list_projects()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
