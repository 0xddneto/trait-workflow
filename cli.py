"""CLI para testar o fluxo sem host MCP.

Exemplos:
  py -3.12 cli.py create hidden --base base.png
  py -3.12 cli.py place hidden --image trait_rgba.png
  py -3.12 cli.py qa hidden
  py -3.12 cli.py visibility hidden --hidden
  py -3.12 cli.py inspect hidden
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

    p = sub.add_parser("place")
    p.add_argument("name")
    p.add_argument("--image", required=True)

    v = sub.add_parser("visibility")
    v.add_argument("name")
    group = v.add_mutually_exclusive_group(required=True)
    group.add_argument("--visible", action="store_true")
    group.add_argument("--hidden", action="store_true")

    i = sub.add_parser("inspect")
    i.add_argument("name")

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
        out = document.create(a.name, a.base)
    elif a.cmd == "place":
        out = pipeline.op_place_trait(a.name, a.image)
    elif a.cmd == "visibility":
        out = pipeline.op_set_base_visibility(a.name, a.visible)
    elif a.cmd == "inspect":
        out = pipeline.op_inspect(a.name)
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
