# trait-workflow

MCP de **imagem em camadas** para produção de traits de NFT sobre uma base
oficial travada.

O modelo é o de um editor de camadas (Krita/Photoshop), não o de um gerador:

- **Camada 1** = base oficial, travada (`edit-locked` no `.ora`, conforme a
  [especificação OpenRaster](https://www.openraster.org/)). Nunca é alterada.
- **Camada 2** = trait RGBA transparente, gerada **pelo agente que chama**
  (Codex, Claude...) com o gerador de imagens dele próprio.
- **"Remover a base"** = exportar a camada 2 sozinha, byte a byte.

Este MCP **não gera imagem nenhuma**. Ele coloca, julga e exporta. A camada 2
nunca é limpa, recortada nem reconstruída depois de colocada.

## O fluxo

```
create_document ──► [agente gera a trait RGBA] ──► place_trait ──► qa ──► export_trait
                        (fundo transparente)                        │
                                                        reprovou? gere outra e
                                                        repita place_trait
```

1. `create_document` — base na camada 1 (travada), camada 2 vazia. Já grava
   `document.ora`, que abre em Krita/GIMP/MyPaint.
2. O agente gera **apenas a trait** com fundo transparente:
   - Codex / OpenAI imagegen: `gpt-image-1` com `background: "transparent"` e
     `output_format: "png"` (o `gpt-image-2` **não** suporta transparência).
   - Prompt tipo: *"apenas a jaqueta X, vestível, sem personagem, sem fundo,
     mesma pose/ângulo da referência, abertura de pescoço e punhos"*.
3. `place_trait` — pixels copiados como estão para a camada 2.
4. `qa` — julga sem tocar em nada: pixels em zona protegida (reprova),
   cobertura, previews (composição, trait sozinha em xadrez, overlay com
   violações em vermelho).
5. `export_trait` — só passa se o QA passou (ou `force=true`): PNG da trait
   (cópia byte a byte) + `.ora` final.

### Fallback: só existe a imagem chapada

Se o gerador só produz o personagem **já vestido** (imagem opaca), use
`extract_trait_from_flat`: separação determinística por diferença contra a
base travada — sem IA, pele protegida por construção. Requer `paint_mask`.
Validado no caso `hidden` do projeto MOBs: IoU 0,95 contra a referência
aprovada, diferença de cor 0,2/255, zero pixels em zona protegida.

## Ferramentas MCP

| Ferramenta | O que faz |
|---|---|
| `create_document` | Base travada na camada 1, camada 2 vazia, `.ora` criado |
| `build_mask` | Define política: `paint` (pode) / `protected` (nunca) |
| `place_trait` | Coloca trait RGBA transparente na camada 2, pixel a pixel |
| `extract_trait_from_flat` | Fallback p/ imagem chapada (diferença determinística) |
| `qa` | Julga a camada 2; previews; nunca altera pixels |
| `export_trait` | Camada 2 sozinha (byte a byte) + `.ora`; bloqueado sem QA |
| `list_documents` | Lista documentos e estado do QA |

## Máscaras são política de design

`protected` diz onde a trait **nunca** pode existir (cabeça, orelhas, mãos).
`paint` diz onde ela **pode**. Lição do caso `hidden`: a roupa aprovada tinha
gola cobrindo o pescoço, mas o pescoço estava marcado como protegido — todo
candidato correto era reprovado para sempre. Se a arte aprovada cobre uma
região, essa região não pode estar em `protected`.

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
py -3.12 cli.py create hidden --base base.png --paint paint.png --protected prot.png
py -3.12 cli.py place hidden --image trait_rgba.png
py -3.12 cli.py qa hidden
py -3.12 cli.py export hidden
```

## Estrutura de um documento

```
documents/<nome>/
  document.ora        # camada 1 = base (edit-locked), camada 2 = trait
  base.png            # fonte da camada 1 (nunca alterada)
  trait.png           # camada 2 atual (pixels do agente, sem retoque)
  paint_mask.png      # política: onde pode
  protected_mask.png  # política: onde nunca
  qa/                 # preview.png, trait_alone.png, overlay.png, qa.json
  exports/            # <nome>_trait.png + <nome>.ora finais
```

Referências: [OpenRaster spec](https://www.openraster.org/) ·
[edit-locking](https://www.openraster.org/extensions/layer-edit-locking-status.html) ·
[Krita e .ora](https://docs.krita.org/en/general_concepts/file_formats/file_ora.html) ·
[OpenAI image API (background transparent)](https://developers.openai.com/api/docs/guides/image-generation)
