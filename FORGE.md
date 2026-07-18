# A Forja (`forge.py`)

Ferramenta **separada do MCP** que resolve o impasse: o gerador integrado do
agente (ex.: Imagegen do Codex) só produz imagem **chapada** (RGB, fundo
sólido, tamanho variável), mas o contrato do MCP só aceita **PNG RGBA nativo
no canvas**. A Forja converte um no outro por matemática determinística —
sem IA, sem chroma-key, sem retoque posterior da camada.

Não é "limpeza": é a equação do editor de camadas, `camada2 = render − camada1`.
A base é conhecida byte a byte, então todo pixel que coincide com ela é base
por definição (alpha 0) e todo pixel diferente dentro da área permitida é
trait. O MCP continua sendo a única autoridade: a Forja apenas produz o
arquivo; `place_trait` → `qa` → `export_trait` seguem intocados.

## Pipeline (tudo determinístico)

1. **Fundo do render** estimado pela mediana dos 4 cantos (preto, branco,
   qualquer cor sólida);
2. **Resize LANCZOS** para o canvas — acontece *antes* de a camada nascer
   (a camada 2 em si nunca é redimensionada);
3. **Registro** (`--no-register` desliga): busca em grade de escala (±4%) e
   deslocamento (±24 px) que minimiza a diferença contra a base na região
   onde ela *deve* aparecer (fora da `paint_mask`). No ground truth
   pixel-perfeito devolve exatamente `scale=1.0, dx=0, dy=0`;
4. **Extração por diferença** contra a base travada (rampa `t0→t1`,
   morfologia, feather; zonas protegidas zeradas por construção);
5. **Descontaminação de borda** (`--no-decontaminate` desliga): nos pixels
   semi-transparentes resolve `c_fg = (c_obs − (1−α)·c_base)/α` — álgebra da
   composição alpha, remove o halo da base;
6. Saída: **PNG RGBA nativo no canvas**, aceita pelo `place_trait` estrito.

## Uso

```bash
# requisito: documento criado e paint_mask definida
py -3.12 forge.py hidden --flat render_do_imagegen.png --place
py -3.12 cli.py qa hidden
py -3.12 cli.py export hidden
```

`--place` já coloca a saída na camada 2 via `place_trait` (o validador
estrito do MCP continua decidindo). Sem `--place`, a saída fica em
`documents/<nome>/forge/trait_forged.png`.

Ajustes: `--t0/--t1` (limiar de diferença), `--open-px`, `--feather`.

## Resultados validados

| Cenário | Resultado |
|---|---|
| Ground truth (base + roupa aprovada, achatado) | IoU **0,9485** vs referência; registro 1.0/0/0; QA pass |
| Render real do Imagegen (1254 px, fundo preto) | bg detectado `[0,0,0]`; registro 1.02/0/+24; QA pass; capuz sobre a cabeça recortado pela política, como especificado |

## Limites honestos

- A qualidade do encaixe depende do render: quanto mais o prompt fixar pose,
  enquadramento e fundo sólido, melhor. O QA e os previews existem para o
  agente iterar.
- Pele/anatomia do render que caia *dentro* da área de pintura vira trait
  (a Forja não adivinha o que é pele — quem decide é a máscara). Máscaras
  por slot são política de design do dono da coleção.
