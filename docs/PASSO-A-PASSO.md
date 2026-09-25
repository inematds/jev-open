# Passo a passo: construir um especialista local num nicho

Este guia ensina a montar, do zero, um **especialista classificador local**: um modelo pequeno que lê uma mensagem ou um documento e responde a perguntas fixas com **sim / não / não dá pra saber**. Depois, código comum decide o que fazer, e toda dúvida vai para uma pessoa.

Os exemplos são os dois nichos deste repositório: **atendimento de escritório de advocacia** (`tasks/advocacia-atendimento/`) e **recepção de clínica** (`tasks/clinica-triagem/`). A parte 3 mostra como aplicar a mesma receita em qualquer outro nicho.

> **Estado honesto (2026-09-25).** O run v1 rodou de ponta a ponta nos dois nichos (fases 2–6), com **dados 100% sintéticos**: os números são **[simulação] do pipeline, não evidência do domínio**, e várias metas foram reprovadas (urgência perdida, OOD abaixo de 0,70, portão int8 da clínica) (ver [RESULTADOS-v1.md](RESULTADOS-v1.md)). Nada aqui foi medido numa VPS nem comparado com o Jev.

---

## Parte 0 — A ideia em uma figura

```
mensagem ──► MODELO observa ──► 7 respostas (sim/não/incerto + %) ──► CÓDIGO decide ──► fila + motivos
                                                               ▲
                     rede de palavras-chave (só escalona) ─────┘
qualquer dúvida (incerto, texto vazio, longo, erro) ──────────────► pessoa
```

Três regras que não mudam em nicho nenhum:

1. **O modelo observa, o código decide.** Datas, prazos, valores, agenda, cadastro e prioridade são código. O modelo nunca escolhe a ação.
2. **A incerteza vira revisão humana.** "Não dá pra saber" nunca é tratado como "não".
3. **Recibo em tudo.** Cada etapa grava um JSON com hashes e resultados, e nada é sobrescrito.

---

## Parte 1 — Passo a passo usado nos dois nichos

Todos os comandos rodam na raiz do repositório. A máquina de treino tem GPU (GB10); o serviço roda só em CPU.

### Passo 0 — Ambiente

```bash
uv sync                       # instala torch (CUDA), transformers, onnx...
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Portão: torch enxerga a GPU. Sem GPU também funciona, só que o treino fica lento.

### Passo 1 — A ficha (o contrato da tarefa)

Arquivo: `tasks/<nicho>/ficha.yaml`. É a parte mais importante e a que mais exige conhecimento do nicho.

| Campo | O que é | Exemplo (advocacia) |
|---|---|---|
| `rotulos` | sempre `[sim, nao, incerto]`; a ordem é contrato | — |
| `perguntas[].pergunta` | a pergunta para a pessoa | "O remetente quer saber como está um processo…?" |
| `perguntas[].hipoteses` | **uma frase autocontida por rótulo**: é o que o modelo lê | sim: "O remetente quer saber como está o andamento do seu processo ou caso." |
| `perguntas[].significados` | o critério de anotação de cada rótulo | nao: "não fala de processo em curso" |
| `rede` | módulo de palavras-chave + a pergunta crítica que ele protege | `{modulo: rede_urgencia, pergunta: urgencia}` |
| `acoes` | rótulo → fila (aplicado pelo **código**) | `urgencia: {sim: advogado_imediato, incerto: advogado_imediato}` |
| `fila_revisao` | para onde vai o que o modelo não consegue ler | `fila_atendimento` |
| `metas` | rubrica definida **antes** de treinar | `urgencia_perdidos_teste: 0` |
| `somente_teste` | arquivos que nunca viram dado de treino | `[exemplos-revisao.jsonl]` |
| `modelos_candidatos` | modelos base, com revisão fixada (hash do commit) | bge-m3-zeroshot, mDeBERTa, ModernBERT |

Como escrever boas perguntas:

- **Uma intenção por pergunta.** "Agendar ou remarcar" pode virar uma só, se a ação for a mesma. "Preço de serviço novo" (comercial) e "boleto de algo contratado" (financeiro) precisam ser perguntas separadas, porque vão para filas diferentes.
- **A pergunta crítica é assimétrica.** Errar para menos é inaceitável (alarme na clínica, urgência na advocacia). "Incerto" também escala, e a meta é **perdidos = 0**, não acurácia.
- **Escreva as fronteiras nos `significados`.** Exemplo: "negação explícita ('não tem prazo') conta como não". É o que resolve os casos difíceis na hora de anotar.

### Passo 2 — Código que não é modelo

- `tasks/<nicho>/rede_<algo>.py`: expressões regulares com `\b` (para não disparar dentro de outras palavras). Elas **só escalonam** e entram em OU com o modelo. Não trate negação: falso alarme custa pouco, alarme perdido custa muito.
- `tasks/<nicho>/regras.py`: `decide(texto, observacoes, acoes)` → `{prioridade, filas, motivos}`. A lista `PRIORIDADE` define a ordem das filas.

Exemplos reais: `tasks/advocacia-atendimento/regras.py` e `tasks/clinica-triagem/regras.py`.

### Passo 3 — 5 exemplos de revisão + teste de fumaça

`tasks/<nicho>/exemplos-revisao.jsonl`: 5 mensagens anotadas, com pelo menos 1 ambígua, 1 caso crítico e 1 negação que engana a rede. Cada registro:

```json
{"id": "adv-03", "grupo": "adv-03", "fonte": "...", "sintetico": true,
 "texto": "Bom dia. Não é nada urgente, não tem prazo nem audiência marcada...",
 "respostas": {"agendar": "sim", "servico": "incerto", "...": "...", "urgencia": "nao"}}
```

```bash
uv run python tools/zeroshot_smoke.py <nicho>     # recibo em tasks/<nicho>/recibos/
```

Portão 1: **uma pessoa do nicho** revisa os significados e os 5 exemplos. Esses 5 são **somente teste** (a guarda `exige_uso_em_dados()` impede usá-los como dado).

Resultado do smoke [medido, 5 exemplos sintéticos, não é benchmark]: bge-m3 acertou 15/20 na clínica e 22/35 na advocacia, sem perder nenhum caso crítico.

### Passo 4 — Dados (fase 2)

O formato é o mesmo dos exemplos. O pipeline lê duas fontes:

- `tasks/<nicho>/dados/sintetico.jsonl`: vira treino, dev e teste;
- `tasks/<nicho>/dados/ood-sintetico.jsonl`: vira a **raia OOD**, que precisa vir de outra fonte (outro redator, outro canal, outro escritório).

**Protótipo sintético** (o que fizemos aqui, sem custo, com LLM local via Ollama):

```bash
uv run python tools/gerar_sintetico.py <nicho> tasks/<nicho>/dados/sintetico.jsonl \
    --n 320 --gerador qwen3.6:35b-a3b --verificador qwen3:30b --estilo variado --prefixo syn --seed 11
uv run python tools/gerar_sintetico.py <nicho> tasks/<nicho>/dados/ood-sintetico.jsonl \
    --n 60 --gerador command-r:35b --verificador qwen3:30b --estilo email --prefixo ood --seed 23
```

O gerador recebe um alvo (0 a 3 intenções por mensagem) e um segundo LLM confere. Só fica o que os dois concordam [medido: ~53% de aceitação, ~6–7 s por registro aceito na GB10]. **Limite:** quem escreve os dados, os rótulos e a ficha é a mesma família de IA, o que é circular. Isso serve para testar o pipeline, não para provar o domínio.

Depois:

```bash
uv run python tools/pipeline.py preparar <nicho>
```

Esse comando remove duplicatas exatas e quase-duplicatas (5-gramas, Jaccard ≥ 0,6), agrupa as parecidas no mesmo `grupo` (que nunca cruza splits), afasta tudo que for parecido com os exemplos de revisão e grava `recibos/v1/data-manifest.json` com hashes e contagem por rótulo.

### Passo 5 — Baseline (fase 3)

```bash
uv run python tools/pipeline.py baseline <nicho>
```

Roda cada modelo candidato sem treino e a rede de palavras-chave, **só no dev**. O `baseline.json` traz a decisão explícita: se o zero-shot já bate `macro_f1_dev_min`, **não treina**.

### Passo 6 — Treino (fase 4)

```bash
uv run python tools/pipeline.py treinar <nicho>   # --camadas 2 --lr 1e-5 --epocas 4 --lote 8
```

Treina só as 2 últimas camadas e a cabeça (26M de 568M parâmetros no bge-m3), com seed fixa. Escolhe o checkpoint pelo dev e calibra a temperatura no dev. Grava `training.json` e `freeze.json`. Os pesos ficam em `workshops/` e não entram no Git.

### Passo 7 — Teste final + OOD (fase 5)

```bash
uv run python tools/pipeline.py testar <nicho>    # roda UMA vez; recusa se test.json existir
```

Compara base e treinado com as mesmas entradas, no teste e na OOD. Mede os perdidos da pergunta crítica **com e sem a rede** (o que o sistema faz de verdade). O `test.json` traz todas as predições.

### Passo 8 — Servir em CPU (fase 6)

```bash
uv run python tools/exportar_onnx.py <nicho>      # ONNX int8 (~570 MB) + paridade + latência
mkdir -p pacotes && cp -r workshops/<nicho>-v1/pacote pacotes/<nicho>
JEV_PACOTES=pacotes uv run python -m serve.api --tarefas <nicho>
uv run python tools/testar_servico.py http://127.0.0.1:8080 <nicho>
docker compose up --build                         # mesma API em container, 2 CPUs / 4 GB
```

- Portão: int8 empata com fp32 no teste congelado (±1 pp).
- O pacote carrega um hash da ficha. Se as hipóteses mudarem, o serviço **recusa** o pacote em vez de rodar um modelo que aprendeu outra coisa.
- Texto vazio, texto longo demais (nunca truncado) e erro interno vão para `fila_revisao`. No texto longo, a rede de palavras-chave ainda roda.
- Os logs guardam só rota e status, nunca o texto (LGPD e sigilo).
- Latência e RAM [medido na GB10, CPU, 2 threads, **não é VPS**]: p50 de 1,53 s (advocacia, 7 perguntas) e 0,73 s (clínica, 4 perguntas); pico de 1,2–1,3 GB por nicho. Meça com `uv run python tools/medir_pacote.py <nicho>` num processo limpo (sem torch).

---

## Parte 2 — Como ir além nestes dois nichos

### 2.1 O que troca o protótipo por algo que vale como evidência

| Hoje (protótipo) | Próximo nível |
|---|---|
| Mensagens sintéticas de LLM | **Mensagens reais anonimizadas** do escritório ou da clínica (WhatsApp/e-mail exportado), com autorização por escrito |
| Rótulo = alvo do gerador, conferido por IA | **Duas pessoas anotam** as mesmas 100 mensagens; medir concordância (kappa de Cohen); reescrever os `significados` onde discordarem |
| OOD = outro LLM, estilo e-mail | OOD = **outro escritório/clínica** ou **outro período** (ex.: treino com jan–jun, OOD com set) |
| Metas "não verificáveis" | Metas aprovadas no teste real: perdidos = 0, macro-F1 dev ≥ 0,85, OOD ≥ 0,70 |
| Latência na GB10 | Latência e RAM medidas **numa VPS real de 2 vCPU / 4 GB** |

Anonimização **antes** de qualquer coisa: trocar nome, CPF, telefone, número de processo, endereço e nome de médico/advogado por marcadores (`<NOME>`, `<PROCESSO>`). Dados reais **nunca** entram no Git: ficam fora do repositório ou em `workshops/`.

> Observação técnica: hoje `tools/pipeline.py preparar` lê arquivos com os nomes `sintetico.jsonl` e `ood-sintetico.jsonl` e grava `"sintetico": true` no manifest. Para dados reais, esse passo precisa ganhar um parâmetro de fonte, para não rotular dado real como sintético. É uma mudança pequena, ainda não feita.

### 2.2 Ciclo de melhoria contínua (a fila de revisão vira dado)

1. Toda mensagem que cai em `fila_revisao` ou recebe "incerto" é resolvida por uma pessoa.
2. A decisão da pessoa é gravada como anotação (texto anonimizado + respostas).
3. A cada N anotações novas, cria-se um **novo run** (`--run v2`) com dados novos. Os recibos do v1 continuam intactos.
4. O v2 só substitui o v1 se ganhar no **mesmo teste congelado** e não piorar os perdidos.

### 2.3 Ajustes finos que valem a pena

- **Limiar por pergunta.** `regras.decide(..., limiar=0.x)` transforma confiança baixa em "incerto". Calibre no dev: na pergunta crítica, prefira um limiar alto (mais revisão, zero perdidos).
- **Medir "aceitos errados".** Quantas mensagens foram para a fila errada com confiança alta? Isso importa mais que acurácia.
- **Modelo menor para VPS fraca.** Se ~1 s por mensagem pesar, teste um candidato menor (mDeBERTa, ~280M) treinado. Ele perdeu no zero-shot, mas pode empatar depois do treino. Decida com números, não com tamanho.
- **Documentos longos.** Para ler petições, contratos ou laudos (não só mensagens), implemente chunking com agregação explícita: "sim" só com evidência em algum trecho e nenhuma contradição.

### 2.4 Novas tarefas no mesmo nicho (cada uma com a própria ficha)

**Advocacia:**

| Tarefa | Entrada | Perguntas | Código decide |
|---|---|---|---|
| Triagem de intimações | texto da publicação/intimação | é intimação para manifestação? cita audiência? cita prazo? é sentença? | prazo calculado pelo **sistema** (dias úteis, feriados); o modelo nunca calcula |
| Conferência de procuração | texto (OCR) | tem outorgante? tem poderes especiais? tem assinatura? tem data? | completo → segue; faltando → devolve com motivo |
| Leitura de contrato | cláusula | tem multa? tem foro de eleição? tem renovação automática? | cruza com o checklist do cliente |
| Documentos por foto | foto de RG/comprovante | é o documento pedido? está legível? | foto ruim → pede outra |

**Clínica** (ver `docs/PLANO.md`, seção 7B): conferência de guia/pedido de exame, regras do convênio (coberto? exige autorização? carência?), documentos por foto.

### 2.5 Cuidados específicos de cada nicho

- **Advocacia:** sigilo profissional (andamento só depois de verificar identidade); **nenhuma resposta de mérito automática**; nada de captação ativa (Código de Ética da OAB); prazos sempre pelo sistema ou pelo advogado. A lista de palavras-chave de urgência e os textos fixos (plantão, Defensoria, 180/190) **precisam ser validados pelo escritório**.
- **Clínica:** escopo **administrativo**, sem diagnóstico (diagnóstico é software médico, regulado pela ANVISA); dado de saúde é sensível na LGPD; a lista de sintomas de alarme e os textos 192/188 **precisam ser validados por profissional de saúde**; o aviso "não substitui avaliação profissional" aparece sempre.

---

## Parte 3 — Do zero em outro nicho

### 3.1 O nicho serve?

Serve quando **todas** estas condições valem:

- Chegam muitas mensagens ou documentos de texto parecidos, e hoje uma pessoa lê e encaminha.
- A decisão pode ser quebrada em **perguntas de sim/não/incerto** sobre o texto.
- O que vem depois da resposta é **regra de negócio** (fila, checklist, cálculo) que dá para escrever em código.
- Existe um "caso que não pode passar" claro (a pergunta crítica), ou pelo menos um custo de erro conhecido.
- Dá para conseguir, com autorização, algumas centenas de exemplos reais (ou começar sintético para prototipar).

Não serve, ou precisa de muito cuidado, quando:

- A resposta exige raciocínio longo, cálculo ou consulta a dados externos. Isso é trabalho de código, busca ou LLM, não deste classificador.
- A decisão é **sobre pessoas** (aprovar crédito, selecionar currículo, negar benefício): há risco de viés e exigências legais. Se for fazer, o modelo só ordena a fila, uma pessoa decide sempre, e você mede o viés por grupo.
- O erro crítico é irreversível e não há pessoa na ponta.

Candidatos bons: SAC de e-commerce (troca? atraso? cobrança indevida? ameaça de Procon/processo?), imobiliária (visita? proposta? manutenção urgente como vazamento de gás?), contabilidade (pede guia? prazo de imposto? notificação da Receita?), escola (falta? documento? bullying/violência → crítica), ouvidoria de prefeitura (tema, urgência, órgão responsável).

### 3.2 Receita, em ordem

1. **Copie um nicho existente** como molde:
   ```bash
   mkdir tasks/<nicho>
   cp tasks/advocacia-atendimento/{ficha.yaml,regras.py,rede_urgencia.py,__init__.py} tasks/<nicho>/
   ```
   Use hífen no nome da pasta (ex.: `imobiliaria-atendimento`). Os módulos são importados pela pasta no `sys.path`, não como pacote.
2. **Entreviste alguém do nicho** (30 min) e escreva a ficha:
   - Quais são as 5–8 intenções mais comuns? Viram as perguntas.
   - Qual caso não pode passar? Vira a pergunta crítica, a rede de palavras-chave e a meta `<critica>_perdidos_teste: 0`.
   - Para onde vai cada intenção? Vira `acoes` e a `PRIORIDADE` em `regras.py`.
   - Quem cuida do que ninguém entendeu? Vira `fila_revisao`.
   - O que é **código** e nunca modelo? Vira a lista `codigo:` (agenda, cadastro, prazos, valores).
3. **Hipóteses:** para cada pergunta, 3 frases completas e autocontidas (sim / não / não dá para saber). Evite pronomes soltos; repita o assunto em cada frase.
4. **Rede de palavras-chave** da pergunta crítica, sem acento e com `\b`. Teste as palavras que contêm os termos ("solicitado" não pode disparar "citado").
5. **5 exemplos de revisão** (1 ambíguo, 1 crítico, 1 negação, 1 com duas intenções, 1 comum) → `zeroshot_smoke.py` → **portão 1 com uma pessoa do nicho**.
6. **Dados:** reais anonimizados sempre que possível; sintético só para prototipar, marcado. Raia OOD de outra fonte.
7. **Fases 3 → 6** com os mesmos comandos da Parte 1 (`pipeline.py baseline|treinar|testar`, `exportar_onnx.py`, `testar_servico.py`).
8. **Plugue no sistema:** o sistema do cliente faz `POST /classify?tarefa=<nicho>` com `{"texto": ...}` e usa `decisao.prioridade` para rotear. O `motivos` explica cada decisão.
9. **Rode o ciclo de melhoria** (seção 2.2) com o que cair na revisão humana.

### 3.3 O que muda e o que nunca muda

| Muda por nicho (só em `tasks/<nicho>/`) | Nunca muda (exceto por bug) |
|---|---|
| `ficha.yaml`, `regras.py`, `rede_*.py`, exemplos, dados, recibos | `core/`, `tools/`, `serve/`, `Dockerfile` |

Se você precisou mexer em `core/` ou `tools/` para um nicho novo, provavelmente falta um campo na ficha. Generalize a ferramenta em vez de fazer um caso especial.

### 3.4 Checklist de publicação

- [ ] Números marcados como [medido], [relato] ou [simulação]; sintético rotulado como sintético.
- [ ] Revisão por IA não foi apresentada como validação humana.
- [ ] Nenhum dado pessoal, peso (`*.safetensors`, `*.onnx`) ou segredo no Git.
- [ ] Listas de palavras-chave e textos fixos validados por profissional do nicho.
- [ ] Pergunta crítica: perdidos = 0 no teste **real**, com a rede ligada.
- [ ] Aviso no produto: triagem automatizada, não substitui o profissional.
- [ ] CHANGELOG atualizado e versão com a regra `vX.XX.YY`.

---

## Referência rápida de arquivos

| Arquivo | Papel |
|---|---|
| `core/task.py` | carrega e valida ficha e registros; guarda `exige_uso_em_dados()` |
| `core/model.py` | leitor NLI zero-shot (modos `hipoteses` e `unica`) |
| `core/especialista.py` | leitor treinável, congelamento de camadas, calibração de temperatura |
| `core/metricas.py` | macro-F1 por pergunta e total, perdidos da pergunta crítica |
| `tools/zeroshot_smoke.py` | teste de fumaça com os 5 exemplos |
| `tools/gerar_sintetico.py` | dados sintéticos com LLM local (gerador + verificador) |
| `tools/pipeline.py` | preparar / baseline / treinar / testar |
| `tools/exportar_onnx.py` | pacote ONNX int8 + paridade + latência |
| `serve/api.py`, `serve/especialista_onnx.py` | API em CPU, sem torch |
| `tools/testar_servico.py` | testes de entrada ambígua, contraditória, vazia, longa e malformada |
| `Dockerfile`, `docker-compose.yml` | serviço em container (pesos montados em `/pacotes`) |
