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
def create_document(name: str, base_image: str,
                    paint_mask: str = "", protected_mask: str = "") -> str:
    """Cria o documento em camadas: camada 1 = base oficial (PNG RGBA,
    travada), camada 2 = vazia. Gera document.ora (abre em Krita/GIMP).
    Mascaras opcionais: paint (onde a trait PODE existir) e protected (onde
    NUNCA pode: cabeca, maos...); podem ser criadas depois com build_mask."""
    meta = document.create(name, base_image,
                           paint_mask or None, protected_mask or None)
    return _j(meta)


@mcp.tool()
def build_mask(name: str, kind: str, regions_json: str = "",
               from_file: str = "") -> str:
    """Define a mascara 'paint' ou 'protected' do documento. regions_json:
    lista de formas, ex. [{"shape":"base_alpha","grow":-2},
    {"shape":"rect","mode":"subtract","xy":[300,0,720,470]},
    {"shape":"file","path":"ref.png"}]. Alternativa: from_file com PNG pronto
    (branco = ativo). Mascara e politica de design: onde a trait aprovada
    pode existir nao pode estar em protected."""
    out = pipeline.op_build_mask(name, kind,
                                 regions=regions_json or None,
                                 from_file=from_file or None)
    return _j(out)


@mcp.tool()
def place_trait(name: str, image_path: str, x: int = 0, y: int = 0,
                allow_resize: bool = False) -> str:
    """Coloca na camada 2 uma imagem RGBA TRANSPARENTE gerada por voce —
    apenas a trait (roupa, item, aura...), sem a base, sem fundo. Com
    gpt-image-1 use background='transparent' e output_format='png'. Os pixels
    sao copiados como estao, sem retoque. Depois rode qa."""
    out = pipeline.op_place_trait(name, image_path, x=x, y=y,
                                  allow_resize=allow_resize)
    return _j(out)


@mcp.tool()
def extract_trait_from_flat(name: str, image_path: str, t0: int = 12,
                            t1: int = 40, open_px: int = 1,
                            feather: float = 1.0) -> str:
    """FALLBACK quando so existe imagem CHAPADA do personagem ja vestido
    (sem transparencia): separa a camada 2 por diferenca deterministica
    contra a base travada (sem IA). Requer paint_mask. Ajuste t0/t1 se vazar
    pele (suba) ou sumir detalhe (desca). Depois rode qa."""
    out = pipeline.op_extract_from_flat(name, image_path, t0=t0, t1=t1,
                                        open_px=open_px, feather=feather)
    return _j(out)


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
