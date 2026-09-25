# Como funciona o exemplo do hotel: onde entra o Jev, onde entra o LLM, onde não entra nenhum

Base: código do demo público (`apps/public-demo/src/sample-api.js`, as regras) e `FROZEN-V2-RESULTS.md` [medido: li o código; os números são relato do autor].

## As 3 camadas

```
 ┌──────────────── ANTES (construção, uma vez) ────────────────┐
 │  LLMs trabalham aqui:                                        │
 │   • Claude Opus (agente "Astra") → escreve o código          │
 │   • Qwen → gera 360 ofertas de hotel sintéticas e escreve    │
 │            o gabarito (resposta certa)                       │
 │   • Gemma → audita o gabarito                                │
 │   → treina o classificador local (ModernBERT)                │
 └──────────────────────────────────────────────────────────────┘
 ┌──────────────── DURANTE (uso, sem nenhum LLM) ──────────────┐
 │ 1. CLASSIFICADOR ← é aqui que o Jev entra                    │
 │    Lê o texto da oferta (uma vez, vale para todos)           │
 │    4 perguntas → atende / contraria / não dá pra saber + %   │
 │    Motor: Jev (API paga)  OU  clone local (ModernBERT)       │
 │                                                              │
 │ 2. VISÃO (opcional)                                          │
 │    Lê as fotos → "escada visível? piscina visível?" + %      │
 │    Modelo de visão pré-treinado de terceiros (OpenJev)       │
 │                                                              │
 │ 3. CÓDIGO PURO ← nenhum modelo                               │
 │    orçamento, lista de desejos, limiar, combinação           │
 │    → match / recusa / revisão para cada viajante             │
 └──────────────────────────────────────────────────────────────┘
```

- **Jev**: camada 1, leitor de documento que classifica. No projeto do autor ele foi a referência de comparação (98,61% contra 95,28% do clone [relato]). O Jev e o clone são **intercambiáveis**: mesma entrada (texto + pergunta + 3 opções), mesma saída (escolha + probabilidade).
- **LLM**: só na construção (código, dados sintéticos, auditoria). Em uso não há LLM, por isso é barato e rápido (~100 ms [relato]).
- **Nenhum dos dois**: regras, contas e a combinação final ficam em código comum.

## A Maya, passo a passo (regras reais do `sample-api.js`)

Perfil: orçamento de €1.600, exige reembolso e quer evitar escadas.

| Etapa | Quem faz | Regra |
|---|---|---|
| Preço | código | `preço > orçamento` → recusa; senão, ok |
| Reembolso | classificador | escolhe atende / contraria / não dá pra saber, com probabilidade |
| Limiar | código | contraria → recusa; "não dá pra saber" **ou** confiança < `accept_threshold` → revisão; senão, ok |
| Escada | visão | por foto: "escada visível?", com probabilidade |
| Regra da foto | código | alguma foto com escada visível ≥ 0,8 → **recusa**; nenhuma → **revisão** (foto não prova rota sem degraus) |
| Veredito | código | alguma recusa → recusa; senão, alguma revisão → revisão; senão → match |

É isso que o demo mostra: com a foto da escada, a Maya é recusada; sem ela, cai em revisão, nunca em match.

## Por que o desenho funciona

1. O modelo lê a oferta **uma vez**. Os 12 clientes são só regras sobre as mesmas observações.
2. O modelo **não faz conta**: preço contra orçamento é um `if`.
3. O modelo **não decide sozinho**: dá uma observação com confiança, e o código transforma dúvida em revisão.

## Regra geral para qualquer sistema

**LLM para construir · classificador (Jev ou clone) para ler texto · visão para ler foto · código para decidir.**

## Verificação local (2026-09-25) [medido]

O demo público rodou localmente (`apps/public-demo`, `npm ci && npm run dev`, Node 24; `npm test` 4/4). Oferta "The flexible escape · 2" (Madeira, €1.465):

- Com as 3 fotos: **Maya · decline** (`capturas/maya-com-escada.png`)
- Sem a foto "Approach": **Maya · review** (`capturas/maya-sem-escada.png`)

O demo usa **observações gravadas**: nenhum modelo roda no navegador, só as regras são recalculadas.
