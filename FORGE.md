# Produzir a camada 2 sem gerador com transparência nativa

Duas ferramentas **separadas do MCP** (não alteram nenhuma ferramenta dele)
resolvem o problema "o gerador integrado só produz imagem chapada". A saída
das duas é PNG RGBA nativo no canvas, aceito pelo `place_trait` estrito;
`qa` e `export_trait` continuam sendo os únicos juízes.

## Rota 1 — O Lift (`lift.py`) — principal, SEM máscara

A objeção correta contra extração mascarada é: se a base está no quadro, o
gerador redesenha anatomia e ela vira trait. O Lift elimina a causa: **a
base não entra no quadro**. O agente pede ao imagegen **apenas a trait**,
flutuando, sobre **fundo magenta sólido `#FF00FF`** — manequim invisível.
Tudo que existe no quadro JÁ É a camada 2; recuperar o alpha de um fundo
sólido conhecido é a álgebra invertível da composição
(`c_obs = α·c_fg + (1−α)·bg`), não segmentação:

1. cor de fundo pela mediana dos cantos;
2. **fundo = só o que está conectado à borda do quadro** (flood fill,
   `scipy.binary_propagation`) — detalhe magenta *dentro* da trait não vira
   buraco;
3. alpha suave na banda de transição (anti-aliasing preservado);
4. descontaminação: `c_fg = (c_obs − (1−α)·bg)/α`;
5. resize determinístico para o canvas (antes de a camada nascer).

```bash
py -3.12 lift.py <doc> --image render_trait_sozinha.png --place
py -3.12 cli.py qa <doc> && py -3.12 cli.py export <doc>
```

**Contrato de prompt para o imagegen** (o que importa de verdade):

> ONLY the garment/item, NO character in the image; invisible-mannequin
> shape fitted to this exact character's pose (attach the base image as
> reference); neck/sleeve openings; same art style; background solid flat
> pure magenta #FF00FF, uniform, no gradients, no shadows; same framing
> and scale as the character in the reference.

**Por que magenta é obrigatório:** a cor-chave precisa estar fora da paleta
da arte. Validação com a roupa aprovada `hidden` (escura): fundo magenta →
IoU **0,9964**; fundo branco → 0,9963; fundo **preto → 0,27** (o flood
fill come as partes pretas da roupa — física de chroma-key, não bug).

## Rota 2 — A Forja (`forge.py`) — fallback, com máscaras

Para quando só existe o render do personagem **já vestido** (chapado).
Extração por diferença contra a base travada: fundo estimado pelos cantos,
registro por busca em grade (±4 %, ±24 px), rampa `t0→t1`, descontaminação.
Requer `paint_mask`/`protected_mask` — e anatomia redesenhada *dentro* da
área de pintura pode virar trait (limite conhecido e documentado; o QA
existe para reprovar). Use a Rota 1 sempre que possível.

```bash
py -3.12 forge.py <doc> --flat render_vestido.png --place
```

## Resultados validados

| Cenário | Ferramenta | Resultado |
|---|---|---|
| Trait aprovada sobre magenta (ground truth) | Lift | IoU **0,9964**, cor 0,32/255, QA pass, export ok |
| Trait aprovada sobre branco | Lift | IoU 0,9963 |
| Trait aprovada sobre preto (roupa escura) | Lift | IoU 0,27 — cor-chave inválida, QA reprova por cobertura |
| Base + trait aprovada, achatado | Forja | IoU 0,9485, registro exato 1.0/0/0 |
| Render real Imagegen 1254 px fundo preto | Forja | QA pass; capuz recortado pela política de máscara |

## Papéis

- **Imagegen do agente**: cria a arte (é o único que pinta).
- **Lift/Forja**: matemática determinística que dá forma de camada à arte.
- **MCP**: documento `.ora`, colocação byte a byte, QA, visibilidade da
  base, export — intocado, único juiz.
