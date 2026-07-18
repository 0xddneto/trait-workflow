# trait-workflow

MCP para gerar **traits de NFT em camadas** sobre uma base travada.

O problema que ele resolve: modelos de difusão não geram "camada 2" — geram a
imagem inteira. Pedir para a IA "remover a base depois" (segmentação) vaza pele
para a camada da roupa. Aqui a responsabilidade é invertida:

1. **IA** gera o personagem-base já vestido/decorado (Gemini ou FLUX Fill).
2. **Aritmética determinística** extrai a camada 2: `diff = |gerado − base|`.
   Como a base é conhecida pixel a pixel, o que não mudou é base por definição
   (alpha 0). Máscaras `paint` e `protected` limitam onde a trait pode existir.
   Pixels protegidos (cabeça, mãos...) **nunca** entram na camada — por
   construção, não por QA.
3. Export: PNG RGBA da trait + `.ora` (camada 1 = base travada, camada 2 = trait).

O MCP é **agnóstico de slot**: quem chama decide se é roupa, aura, item ou
marca — mudam apenas o prompt, as máscaras e a ordem de composição
(`over`/`behind`).

## Instalação

```bash
py -3.12 -m pip install -r requirements.txt
```

Chaves de API (nunca commitadas): copie `keys.example.json` para
`%USERPROFILE%/.trait-workflow/keys.json`, ou defina `GEMINI_API_KEY` /
`FAL_KEY` no ambiente.

### Claude Code

O `.mcp.json` do repo já registra o servidor — basta abrir o Claude Code na
pasta do repo. Ou global: `claude mcp add trait-workflow -- py -3.12 "C:/caminho/para/server.py"`.

### Codex

Em `~/.codex/config.toml`:

```toml
[mcp_servers.trait-workflow]
command = "py"
args = ["-3.12", "C:/caminho/para/trait-workflow/server.py"]
```

## Ferramentas MCP

| Ferramenta | O que faz |
|---|---|
| `create_project` | Cria projeto com base RGBA (+ máscaras opcionais) |
| `build_mask` | Monta máscara `paint`/`protected` por formas JSON ou arquivos |
| `add_candidate` | Registra imagem gerada pelo PRÓPRIO agente (ex.: imagegen do Codex) |
| `generate` | (Opcional) gera candidatos via API: `gemini`, `fal` ou `cloudflare` |
| `extract` | Extrai a camada 2 determinística + QA + preview |
| `export` | PNG final + `.ora` com as duas camadas |
| `list_projects` | Lista projetos |

## Fluxo principal (agente com gerador próprio, ex. Codex)

1. `create_project` com a base oficial + máscaras (`paint` = onde a trait pode
   existir; `protected` = cabeça, mãos... nunca).
2. O agente gera com o **imagegen dele** a imagem do personagem-base já
   vestido — mesma pose e enquadramento.
3. `add_candidate` com o arquivo gerado.
4. `extract` → devolve a trait RGBA + preview + overlay de QA (tentativas de
   invasão em vermelho) + métricas. Se o preview estiver ruim, o agente gera
   outro candidato e repete — a extração é determinística e a base é
   intocável, então iterar é seguro.
5. `export` → PNG final + `.ora`.

**Importante (lição do caso `hidden`):** a máscara é política de design. Se a
roupa aprovada tem gola que cobre o pescoço, o pescoço não pode estar na
`protected_mask` — senão todo candidato correto é reprovado para sempre.
Validação real: trait extraída vs. referência aprovada = IoU 0,95, diferença
de cor 0,2/255, zero pixels em zona protegida.

## Fluxo típico (CLI de teste)

```bash
py -3.12 cli.py create hidden --base base.png --paint paint.png --protected prot.png
py -3.12 cli.py generate hidden --prompt "dark navy high-collar jacket, black tactical pants, heavy boots"
py -3.12 cli.py extract hidden          # gera layers/trait_XXX.png + qa/
py -3.12 cli.py export hidden           # PNG final + .ora
```

Ajuste fino da extração: `--t0/--t1` (limiar de diferença — suba se vazar
pele, desça se sumir detalhe), `--open-px` (remove pontas soltas),
`--feather` (suaviza a borda).

## Estrutura de um projeto

```
projects/<nome>/
  base.png            # base travada (nunca alterada)
  paint_mask.png      # branco = onde a trait PODE existir
  protected_mask.png  # branco = onde NUNCA pode (cabeça, mãos...)
  candidates/         # saídas brutas da IA (base vestida)
  layers/             # traits RGBA extraídas
  qa/                 # previews, overlays (invasão em vermelho), métricas
  exports/            # PNG final + .ora
```
