# Sugestão: jev-open para escolher modelo e ferramenta em assistentes (Jarvis, openpcbotv3)

> **Status: sugestão, nada implementado.** Registrada em 2026-09-26. Nenhum número aqui mede roteamento: não existe ficha nem dado para esse uso ainda. Os números citados vêm do run v1 de outros nichos ([RESULTADOS-v1.md](RESULTADOS-v1.md)).

## 1. Onde encaixa

Os dois assistentes já têm um ponto de decisão **antes** da resposta:

| Sistema | O que decide hoje | Motor |
|---|---|---|
| **jarvisv7** | JEV Reflex: 5 decisões antes do cérebro principal (destino do pedido, completude, direcionamento ao assistente, necessidade de ação, cobertura das notas) | Jev pago via OpenRouter, com fallback local |
| **openpcbotv3** | `src/orquestrador/roteador.ts`: `{rota: direto\|agente, agente, tier: local\|barato\|premium}` | llama3.2 local (JSON); o Jev pago só **observa** (`/jev observar`, docs/JEV.md) |

É o mesmo lugar em que um classificador local pode ajudar: escolher **qual modelo** (tier) e **qual ferramenta** (agente/skill) usar.

## 2. O desenho: perguntar sobre o pedido, não "qual ferramenta"

Perguntar "qual das 30 skills?" não funciona bem aqui:

- toda skill nova muda as hipóteses, e o pacote treinado do jev-open **recusa rodar** se a ficha mudar (contrato na carga);
- custa caro: 30 skills × 3 hipóteses = 90 pares por mensagem, em CPU.

O jeito que segue o padrão do projeto (**o modelo observa, o código decide**) é o modelo responder a **propriedades estáveis do pedido**, e o **código** mapear isso para modelo e ferramenta:

| Pergunta (sim / não / incerto) | O código decide |
|---|---|
| Precisa agir fora do chat (arquivo, comando, repositório)? | rota `agente` |
| Precisa de informação atual da web? | ferramenta de busca |
| Exige raciocínio longo ou código? | tier `barato`; `premium` só por regra |
| Mexe em agenda, tarefa ou e-mail? | skill/conector de agenda |
| O pedido está completo, ou falta um dado para executar? | perguntar antes de gastar |
| Pede ação irreversível (enviar, apagar, pagar)? | pedir aprovação |

Trocar de modelo (qwen, Claude, Opus) ou adicionar uma skill vira **uma linha de regra no código**, sem retreinar. As 5 decisões do JEV Reflex do Jarvis já seguem essa ideia: são propriedades, não nomes de ferramenta.

## 3. Vantagens esperadas (a medir)

- **Contra o Jev pago:** sem custo por mensagem, a mensagem não sai da máquina, não depende de rede (o timeout de 3 s do openpcbotv3 deixa de ser gargalo).
- **Contra o llama3.2:** probabilidade calibrada por pergunta, então "incerto" tem um uso claro (cai para o roteador mais forte ou pergunta ao usuário), em vez de um JSON que às vezes vem quebrado. Determinístico, com recibo por decisão.
- **Auditável:** o campo `motivos` mostra qual pergunta levou a qual rota.

## 4. Limites conhecidos

- **Latência:** 0,7–1,5 s por mensagem com 4–7 perguntas, CPU com 2 threads [medido na GB10, outros nichos]. Na GPU deve cair muito, mas **não foi medido**. No caminho síncrono isso pesa; precisa ser comparado com o tempo do llama3.2 atual.
- **Memória:** ~1,2–1,3 GB por tarefa [medido]. O openpcbotv3 roda com `MemoryMax=2G`, então o jev-open fica **fora do processo**, no container (`POST /classify`).
- **Qualidade desconhecida para roteamento.** O zero-shot do bge-m3 ficou em 0,51–0,56 de macro-F1 [simulação] em outros nichos. Não dá para prever o desempenho aqui sem medir.
- **Dados:** o melhor rótulo vem do uso real (divergências entre llama3.2, Jev e o usuário). O `jev_comparacoes` do openpcbotv3 **não guarda o texto** das mensagens, de propósito. Gravar texto, nem que seja só das divergências, é uma decisão de privacidade do usuário.

## 5. Roteiro em degraus

Nunca pôr o classificador direto no caminho da decisão. Subir um degrau só quando os números do anterior mostrarem que vale, sempre com caminho de volta.

| Degrau | Onde o jev-open roda | Quem decide | Para subir |
|---|---|---|---|
| **1. Observa** | em paralelo, em segundo plano, com timeout | roteador atual; o jev-open só é registrado | concordância medida em 1–2 semanas de uso real, com as divergências revisadas pelo usuário |
| **2. Filtra** | **antes** do roteador, só quando confiante (limiar calibrado no dev) | jev-open acima do limiar; abaixo, o roteador atual | poucos "aceitos errados" acima do limiar, medidos em recibo |
| **3. Decide** | **antes**, sempre | jev-open; "incerto" cai no roteador mais forte ou pergunta ao usuário | — |

Caminho de volta em qualquer degrau: uma preferência (como o `/jev off` de hoje) devolve a decisão ao roteador atual, sem reiniciar.

## 6. Passos concretos sugeridos

1. **Ficha** `tasks/roteamento-assistente/` no jev-open com as ~6 perguntas da seção 2; pergunta crítica = "ação irreversível" (meta: perdidos = 0), rede de palavras-chave com verbos como enviar, apagar, pagar, publicar.
2. **Fumaça + dados sintéticos + baseline**, igual aos outros nichos (ver [PASSO-A-PASSO.md](PASSO-A-PASSO.md)). Serve para os dois assistentes.
3. **Degrau 1 no openpcbotv3:** um modo `/jev observar --local` que chama o container do jev-open em vez do OpenRouter e grava no mesmo `jev_comparacoes`, com o relatório diário comparando llama3.2, Jev pago e jev-open.
4. Se os números forem bons, **degrau 2** no `roteador.ts`, e o mesmo pacote como **fallback local do JEV Reflex** no Jarvis.

## Referências

- `jev/docs/03-plano-aplicacao.md`: roteiro em etapas para aplicar o Jev pago (inclui "observar tráfego" e "liberar rota limitada").
- `openpcbotv3/docs/JEV.md`: o degrau 1 já implementado com o Jev pago.
- `jarvisv7/docs/jev-reflex.md`: as 5 decisões do JEV Reflex.
