"""Servidor MCP (stdio): documento em camadas para traits de NFT.

Camada 1 = base oficial, travada (edit-locked no .ora). Camada 2 = trait
RGBA gerada pelo AGENTE que chama (com fundo transparente). O MCP nao gera
imagem nenhuma: coloca, julga e exporta. A camada 2 nunca e limpa, recortada
ou reconstruida."""

import json

from mcp.server.fastmcp import FastMCP

from . import document, pipeline

mcp = FastMCP("trait-workflow")


def _j(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


@mcp.tool()
def create_document(name: str, base_image: str) -> str:
    """Cria o documento em camadas: camada 1 = base oficial (PNG RGBA,
    travada), camada 2 = vazia. Gera document.ora (abre em Krita/GIMP)."""
    meta = document.create(name, base_image)
    return _j(meta)


@mcp.tool()
def place_trait(name: str, image_path: str) -> str:
    """Coloca na camada 2 uma imagem RGBA TRANSPARENTE gerada por voce —
    apenas a trait (roupa, item, aura...), sem a base, sem fundo. O PNG e
    copiado byte a byte, sem retoque. Depois rode qa."""
    out = pipeline.op_place_trait(name, image_path)
    return _j(out)


@mcp.tool()
def inspect_document(name: str) -> str:
    """Valida estrutura, tamanhos, modos, hashes, imutabilidade da base,
    visibilidade e bytes das duas camadas dentro do ORA. Nao altera pixels."""
    return _j(pipeline.op_inspect(name))


@mcp.tool()
def set_base_layer_visibility(name: str, visible: bool,
                              order: str = "over") -> str:
    """Mostra ou oculta somente a camada 1 no ORA. Confirma pelos hashes que
    nenhum byte da camada 2 mudou."""
    return _j(pipeline.op_set_base_visibility(name, visible, order=order))


@mcp.tool()
def qa(name: str, order: str = "over", min_coverage_pct: float = 1.0) -> str:
    """Julga a camada 2 atual SEM alterar nenhum pixel: pixels em zona
    protegida (reprova), cobertura, previews (composicao, trait sozinha no
    xadrez, overlay com violacoes em vermelho). order: 'over' (roupa/item)
    ou 'behind' (aura). Olhe as imagens antes de exportar."""
    out = pipeline.op_qa(name, order=order, min_coverage_pct=min_coverage_pct)
    return _j(out)


@mcp.tool()
def export_trait(name: str, dest: str = "", force: bool = False,
                 order: str = "over") -> str:
    """'Remove a base': exporta a camada 2 sozinha (copia byte a byte do que
    foi colocado) + o .ora final com as duas camadas. Bloqueado se o QA
    reprovou ou esta desatualizado (force=true ignora a reprovacao)."""
    out = pipeline.op_export(name, dest=dest or None, force=force, order=order)
    return _j(out)


@mcp.tool()
def list_documents() -> str:
    """Lista documentos existentes com o estado do ultimo QA."""
    return _j(document.list_documents())


def main():
    mcp.run()


if __name__ == "__main__":
    main()
