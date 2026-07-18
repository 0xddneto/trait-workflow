# trait-workflow

MCP de **imagem em camadas** para produção de traits de NFT sobre uma base
oficial travada.

O modelo é o de um editor de camadas (Krita/Photoshop), não o de um gerador:

- **Camada 1** = base oficial, travada (`edit-locked` no `.ora`, conforme a
  [especificação OpenRaster](https://www.openraster.org/)). Nunca é alterada.
- **Camada 2** = trait RGBA transparente, gerada **pelo agente que chama**
  (Codex, Claude...) com o gerador de imagens dele próprio.
- **"Remover a base"** = exportar a camada 2 sozinha, byte a byte.

Este MCP **não gera imagem nenhuma**. Ele cria e controla o documento, coloca,
inspeciona, julga e exporta. A camada 2 nunca é limpa, recortada,
redimensionada, transladada nem reconstruída depois de colocada.

## O fluxo

```
create_document ──► [agente gera a trait RGBA] ──► place_trait ──► qa
       │                                                        │
       └──── base visível e travada ───────────────► ocultar base ──► export_trait
                        (fundo transparente)                        │
                                                        reprovou? gere outra e
                                                        repita place_trait
```

1. `create_document` — base na camada 1 (travada), camada 2 vazia. Já grava
   `document.ora`, que abre em Krita/GIMP/MyPaint.
2. O agente gera **apenas a trait** como PNG RGBA transparente exatamente no
   tamanho do canvas. A origem/modelo não faz parte deste MCP.
   - Prompt tipo: *"apenas a jaqueta X, vestível, sem personagem, sem fundo,
     mesma pose/ângulo da referência, abertura de pescoço e punhos"*.
3. `place_trait` — arquivo copiado byte a byte para a camada 2. Tamanho,
   padding, deslocamento e modo incorretos são recusados.
4. `qa` — julga sem tocar em nada: pixels em zona protegida (reprova),
   cobertura, previews (composição, trait sozinha em xadrez, overlay com
   violações em vermelho).
5. `set_base_layer_visibility(false)` — oculta apenas a camada 1 e prova por
   hash que a camada 2 permaneceu idêntica.
6. `export_trait` — só passa se o QA passou (ou `force=true`): PNG da trait
   (cópia byte a byte) + `.ora` final.

## Ferramentas MCP

| Ferramenta | O que faz |
|---|---|
| `create_document` | Base travada na camada 1, camada 2 vazia, `.ora` criado |
| `place_trait` | Coloca o PNG RGBA na camada 2, byte a byte |
| `inspect_document` | Confere modos, tamanhos, hashes, lock e visibilidade |
| `set_base_layer_visibility` | Mostra/oculta só a base; trait não muda |
| `qa` | Julga a camada 2; previews; nunca altera pixels |
| `export_trait` | Camada 2 sozinha (byte a byte) + `.ora`; bloqueado sem QA |
| `list_documents` | Lista documentos e estado do QA |

## Instalação

```bash
py -3.12 -m pip install -r requirements.txt
```

### Claude Code
O `.mcp.json` do repo registra o servidor automaticamente ao abrir a pasta.

### Codex
Em `~/.codex/config.toml`:

```toml
[mcp_servers.trait-workflow]
command = "py"
args = ["-3.12", "C:/Nova pasta/DN/DEV/trait-workflow/server.py"]
```

## CLI de teste

```bash
py -3.12 cli.py create hidden --base base.png
py -3.12 cli.py place hidden --image trait_rgba.png
py -3.12 cli.py qa hidden
py -3.12 cli.py visibility hidden --hidden
py -3.12 cli.py inspect hidden
py -3.12 cli.py export hidden
```

## Estrutura de um documento

```
documents/<nome>/
  document.ora        # camada 1 = base (edit-locked), camada 2 = trait
  base.png            # fonte da camada 1 (nunca alterada)
  trait.png           # camada 2 atual (pixels do agente, sem retoque)
  qa/                 # preview.png, trait_alone.png, overlay.png, qa.json
  exports/            # <nome>_trait.png + <nome>.ora finais
```

Referências: [OpenRaster spec](https://www.openraster.org/) ·
[edit-locking](https://www.openraster.org/extensions/layer-edit-locking-status.html) ·
[Krita e .ora](https://docs.krita.org/en/general_concepts/file_formats/file_ora.html) ·
[OpenAI image API (background transparent)](https://developers.openai.com/api/docs/guides/image-generation)
