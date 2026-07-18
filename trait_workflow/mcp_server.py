"""Servidor MCP (stdio). Ferramentas genericas: o modelo que chama decide o
slot (roupa, aura, item...) via prompt + mascaras."""

import json

from mcp.server.fastmcp import FastMCP

from . import pipeline, projects

mcp = FastMCP("trait-workflow")


def _j(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


@mcp.tool()
def create_project(name: str, base_image: str,
                   paint_mask: str = "", protected_mask: str = "") -> str:
    """Cria um projeto de trait. base_image: PNG RGBA da base oficial (sera
    travada). paint_mask/protected_mask: PNGs L opcionais (branco = ativo);
    podem ser construidos depois com build_mask."""
    meta = projects.create(name, base_image,
                           paint_mask or None, protected_mask or None)
    return _j(meta)


@mcp.tool()
def build_mask(name: str, kind: str, regions_json: str = "",
               from_file: str = "") -> str:
    """Constroi a mascara 'paint' (onde a trait PODE existir) ou 'protected'
    (onde NUNCA pode: cabeca, maos...). regions_json: lista de formas, ex.
    [{"shape":"base_alpha","grow":-2},{"shape":"rect","mode":"subtract",
    "xy":[300,0,720,470]}]. Alternativa: from_file com um PNG pronto."""
    out = pipeline.op_build_mask(name, kind,
                                 regions=regions_json or None,
                                 from_file=from_file or None)
    return _j(out)


@mcp.tool()
def add_candidate(name: str, image_path: str) -> str:
    """Registra uma imagem gerada POR VOCE (seu proprio gerador de imagens)
    como candidato. A imagem deve mostrar o personagem-base ja vestido com a
    trait, mesma pose e enquadramento. Depois rode extract para separar a
    camada. Este e o fluxo principal quando o agente tem gerador integrado."""
    out = pipeline.op_add_candidate(name, image_path)
    return _j(out)


@mcp.tool()
def generate(name: str, prompt: str, backend: str = "gemini",
             model: str = "", n: int = 1, guard: bool = True) -> str:
    """Gera candidatos: o personagem-base JA VESTIDO com a trait descrita no
    prompt. backend 'gemini' (gratis) ou 'fal' (FLUX Fill, inpainting com
    mascara real). guard=True acrescenta instrucoes de pose/enquadramento
    travados. A base nunca e alterada: a protecao e imposta na extracao."""
    out = pipeline.op_generate(name, prompt, backend=backend,
                               model=model or None, n=n, guard=guard)
    return _j(out)


@mcp.tool()
def extract(name: str, candidate: str = "latest", t0: int = 12, t1: int = 40,
            open_px: int = 1, feather: float = 1.0, order: str = "over") -> str:
    """Extrai a camada 2 (trait RGBA) do candidato, por diferenca deterministica
    contra a base. Gera preview, overlay de QA e metricas. order: 'over'
    (roupa/item) ou 'behind' (aura). Ajuste t0/t1 se vazar pele (aumente) ou
    sumir detalhe da trait (diminua)."""
    out = pipeline.op_extract(name, candidate, t0=t0, t1=t1,
                              open_px=open_px, feather=feather, order=order)
    return _j(out)


@mcp.tool()
def export(name: str, candidate: str = "latest", dest: str = "",
           ora: bool = True, order: str = "over") -> str:
    """Exporta a trait aprovada: PNG RGBA final + .ora (base travada na camada
    1, trait na camada 2)."""
    out = pipeline.op_export(name, candidate, dest=dest or None,
                             write_ora=ora, order=order)
    return _j(out)


@mcp.tool()
def list_projects() -> str:
    """Lista projetos existentes com contagem de candidatos e camadas."""
    return _j(projects.list_projects())


def main():
    mcp.run()


if __name__ == "__main__":
    main()
