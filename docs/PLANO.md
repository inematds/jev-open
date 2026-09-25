# Plano: jev-open como modelo padrão de "especialista local" para qualquer sistema

Data: 2026-09-24 · Status: **plano, nada executado ainda** · Base: `docs/ANALISE.md`

## 1. Objetivo

Transformar o método do kit "Your Own Jev" num **padrão reutilizável**, para que qualquer sistema (INEMA, bots, cursos, pipelines de documentos) plugue um classificador local, barato e auditável:

> **O modelo observa, o código decide, e a incerteza vira revisão.**

A entrega é um molde em que cada novo domínio entra preenchendo uma ficha e um dataset, sem reescrever código. Não é um modelo único.

## 2. Princípios (inegociáveis)

1. **Uma pergunta = uma decisão com 3 respostas**: atende / contraria / não dá pra saber. Ausência de evidência é "não dá pra saber", nunca "sim".
2. **Aritmética e regras de negócio ficam no código.** Orçamento, datas, somas e combinações não passam pelo modelo.
3. **Hipóteses autocontidas.** Cada candidato cita a condição ("Há reembolso integral em dinheiro"), ou a pergunta vai na premissa. A serialização é idêntica em treino, teste e predict. (Corrige o problema 6.1 da análise.)
4. **Medir antes de treinar**, com zero-shot e com um baseline de regras simples. Só treinar se o ganho justificar.
5. **Três splits + uma raia independente.** Treino / dev / teste final congelado, mais um **conjunto OOD** vindo de outra fonte, outro redator e outro template. O teste roda uma vez só.
6. **Recibos em tudo.** Revisão do modelo base, hashes de dados e checkpoint, seed, device, curvas de treino e predições individuais. Nada é sobrescrito.
7. **Procedência explícita.** Cada número recebe a marca [medido], [relato] ou [simulação]. Dado sintético é rotulado como sintético, e revisão feita por IA não conta como validação humana.
8. **Probabilidade não é garantia.** Calibrar no dev (temperatura) antes de usar limiar de revisão, e medir "aceitos errados".
9. **Sem truncar em silêncio.** Documento longo passa por chunking com agregação explícita (ex.: "atende" só com evidência em algum trecho e nenhuma contradição).
10. **Imagem é uma fonte separada.** Foto gera observações próprias e não prova cláusula contratual. As regras combinam as fontes preservando a incerteza.

## 3. Estrutura proposta do repositório

```
jev-open/
├── AGENTS.md  README.md  CHANGELOG.md  pyproject.toml  uv.lock
├── core/                      # motor genérico (independe de domínio)
│   ├── schema.py              # valida ficha + registros (N candidatos, não fixo em 3)
│   ├── serialize.py           # UMA função (documento, pergunta, candidato) -> par; usada em tudo
│   ├── model.py               # NLIModel com base configurável, device cuda|mps|cpu
│   ├── chunk.py               # janelas + agregação explícita
│   ├── calibrate.py           # temperatura no dev, limiar de revisão
│   ├── stages.py              # prepare/download/baseline/train/freeze/test/ood/predict
│   └── receipts.py            # hashes, manifestos, escrita "x" (sem sobrescrever)
├── export/                    # checkpoint -> ONNX int8 + pacote com manifesto
├── serve/api.py               # FastAPI + ONNX Runtime (CPU): POST /classify {tarefa, documento}
├── vision/                    # opcional: CLIP/SigLIP zero-shot (CPU) ou VLM pequeno
├── deploy/                    # Dockerfile (amd64+arm64), docker-compose.yml, Caddyfile
├── rules/                     # motor de regras: observações + perfil -> match/recusa/revisão
├── tasks/<dominio>/           # UM diretório por sistema que adota o padrão
│   ├── ficha.yaml             # perguntas, hipóteses, significados, ações
│   ├── rules.yaml             # como as observações viram decisão
│   ├── data/{train,dev,test,ood}.jsonl
│   └── adapter.py             # converte o formato bruto do sistema -> registros
├── workshops/                 # execuções (gitignored; só manifestos resumidos vão ao Git)
├── templates/FICHA-TAREFA.md  # ficha em branco + checklist
└── docs/ (ANALISE, PLANO, originais/ e ref/ locais)
```

**Sobre reuso de código do starter (MIT):** a ideia é reescrever o `core/` inspirado no `tutorial.py`. Se algum trecho for copiado, o aviso MIT vai junto (THIRD-PARTY-NOTICES).

## 4. Contrato da tarefa (`tasks/<dominio>/ficha.yaml`)

```yaml
tarefa: reembolso-viagem
idioma: pt
entrada: "Termos completos de reserva de uma oferta"
modelo_base: {id: MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7, revisao: b5113eb…}
perguntas:
  - id: reembolso
    pergunta: "Há reembolso integral em dinheiro antes do prazo?"
    candidatos:            # autocontidos; ordem = rótulos
      - "O documento garante reembolso integral em dinheiro antes do prazo."
      - "O documento nega reembolso integral em dinheiro (ex.: só crédito)."
      - "O documento não informa se há reembolso integral em dinheiro."
    rotulos: [atende, contraria, sem_evidencia]
    significados:
      atende: "cláusula explícita de reembolso em dinheiro"
      contraria: "crédito, voucher, multa ou 'não reembolsável'"
      sem_evidencia: "ausente, ambíguo ou 'consulte a central'"
    acao: {atende: seguir, contraria: recusar, sem_evidencia: revisao_humana}
metas:                     # rubrica definida ANTES de treinar
  macro_f1_dev_min: 0.85
  aceitos_errados_max: 0.01   # atende previsto quando o gold é outro
  ood_macro_f1_min: 0.70
  queda_ood_max_pp: 15
```

Registro de dados (`*.jsonl`): `{id, grupo, fonte, sintetico: bool, documento, respostas: {reembolso: 2, ...}, evidencia: {reembolso: "C1"}}`. O campo `grupo` garante que templates e documentos parentes caiam todos no mesmo split.

## 5. Fases e portões

Cada fase só termina com **um recibo salvo** e o portão aprovado.

| # | Fase | Faz | Portão (critério de saída) |
|---|---|---|---|
| 0 | Ambiente | `uv sync`, checar `torch.cuda.is_available()`, `torch.version.cuda`, `get_device_capability()` na GB10; rodar o smoke test de 8 decisões do starter **como está** num workshop | torch com CUDA ativo na GB10 (ou fallback CPU documentado); `test.json` do smoke gerado |
| 1 | Ficha + 5 exemplos | Preencher `ficha.yaml` do 1º domínio; 5 exemplos anotados, incluindo 1 ambíguo; **o usuário revisa** | Usuário aprova os significados dos rótulos |
| 2 | Dados | Coletar exemplos reais (sintético só para prototipar, marcado); split por `grupo`; checagem de sobreposição exata + near-dup (MinHash/embeddings); montar a raia OOD de outra fonte | `data-manifest.json` com hashes; contagem por rótulo; OOD separado |
| 3 | Baselines | Zero-shot do modelo base (EN e multilíngue) + baseline de regras/regex no dev | `baseline.json`; **decisão explícita**: treinar ou não (se o zero-shot já bate a meta, parar aqui) |
| 4 | Treino | Smoke (8 decisões) → completo; 2 camadas + cabeça, seed fixa, escolha de checkpoint pelo dev; calibrar temperatura | `training.json` + `freeze.json`; loss finita; curva salva |
| 5 | Teste final + OOD | Uma execução: base vs. treinado no teste e na raia OOD, com as mesmas entradas | `test.json` com todas as predições; metas da ficha aprovadas **ou** relatório de falha preservado |
| 6 | Servir | Export ONNX int8 + pacote; `serve/api.py` em CPU; Docker amd64/arm64; motor de regras com ramo de revisão; testes com entrada ambígua, contraditória, ausente e longa | int8 empata com FP32 no teste congelado (±1 pp); **latência e RAM medidas numa VPS de 2 vCPU/4 GB**; resultado inspecionável |
| 7 | Imagem (opcional) | Só se o domínio pedir. VLM local separado (ex.: via Ollama/ComfyUI na GB10) gera observações visuais; regras combinam | Testes: foto enganosa, foto ausente; imagem nunca prova cláusula |
| 8 | Comparação com Jev (opcional) | Mesmo teste pelo `jev-gw` do repo `jev` | **Só com autorização explícita** para as chamadas pagas; resultado marcado [medido] com data |

## 6. Adotar em um sistema novo (receita curta)

1. `cp -r tasks/_modelo tasks/<sistema>` e preencher `ficha.yaml` (perguntas, hipóteses autocontidas, ações).
2. Escrever `adapter.py`: formato bruto do sistema → registros (o `prepare_task.py` do starter é o exemplo).
3. Rodar as fases 2 → 5 num workshop novo (`workshops/<sistema>-v1`).
4. Escrever `rules.yaml`: como as observações + o perfil viram decisão.
5. Plugar via API (`/classify?tarefa=<sistema>`). O modelo carregado é o do `freeze.json` daquela tarefa, e o contrato (ordem de rótulos, temperatura) é validado na carga.

**Arquivos que mudam por domínio:** só `tasks/<sistema>/*`. **Nunca** o `core/`, exceto por bug.

## 7. Candidatos de primeiro uso (exemplos, a escolher)

| Sistema | Entrada | Pergunta-exemplo | 3 respostas |
|---|---|---|---|
| Viagem (réplica do kit, em PT) | termos de reserva | reembolso em dinheiro? | sim / não / não informa |
| Suporte / bots | mensagem do usuário | é cobrança? | cobrança / técnico / revisão |
| Cursos INEMA | texto de uma aula | cita fonte verificável? | cita / não cita / ambíguo |
| Políticas / contratos | cláusula | permite uso comercial? | permite / proíbe / não especifica |

Recomendação: **começar pela réplica de viagem em PT**. Ela tem dados e gabarito comparáveis ao original e isola a variável "idioma/modelo base" antes de mudar de domínio. Depois disso, a clínica médica (seção 7B) vira o primeiro caso "de verdade".

## 7A. Rodar em qualquer VPS (requisito)

A ideia é **treinar na GB10 e servir em qualquer lugar.** Treinar exige GPU e acontece raramente. Servir precisa só de CPU e roda o tempo todo.

```
GB10 (treino, GPU)                          VPS qualquer (serviço, só CPU)
  fases 2–5 → checkpoint congelado            docker compose up
  → export ONNX + quantização int8   ───►     jev-open-api  (texto, ONNX Runtime CPU)
  → pacote: modelo + ficha + rules            jev-open-vision (opcional, imagem)
    + manifesto (hashes, metas batidas)       sem GPU, sem internet obrigatória
```

- **Pacote de modelo** (`dist/<tarefa>-vX.tar`): `model.onnx` (int8) + tokenizer + `ficha.yaml` + `rules.yaml` + `manifest.json` (hashes, temperatura de calibração, métricas do teste). A API **se recusa a subir** se o hash ou o contrato não baterem.
- **Runtime**: ONNX Runtime em CPU, sem PyTorch e sem CUDA na VPS. Imagem Docker alvo < 1 GB e duas arquiteturas (amd64 e arm64), para servir em Hetzner, Contabo, Oracle ARM etc.
- **Porte mínimo alvo (a medir, não medido)**: 2 vCPU e 4 GB de RAM só para texto. Modelo base de ~150–280M parâmetros vira ~150–300 MB em int8. Estimativa de 0,3–2 s por documento com 4 perguntas em 2 vCPU; **a fase 6 mede isso de verdade**, numa VPS barata real.
- **Quantização é um experimento**: o int8 roda o mesmo teste congelado. Se cair mais que 1 pp, entrega FP32 e registra a diferença.
- **Imagem na VPS**: um VLM grande em CPU é lento demais, então há 3 níveis:
  1. **CLIP/SigLIP zero-shot** (~150–400M parâmetros, roda em CPU) para perguntas visuais simples ("há documento na foto?", "está legível?", "é piscina ou lago?").
  2. **VLM pequeno** (2–4B, int4) só se o nível 1 não bastar, com 8 GB+ de RAM e latência de segundos.
  3. **Imagem desligada**: a tarefa roda só com texto.
- **Operação**: `docker compose` com `/health`, `/classify` e `/version`, um token por cliente, log de auditoria sem conteúdo sensível, e HTTPS via Caddy.
- **Multi-tarefa**: a mesma API serve várias tarefas (`/classify?tarefa=clinica-triagem`), cada uma com o próprio pacote.

## 7B. Exemplo: consultório / clínica médica

**Escopo seguro: o modelo classifica texto administrativo e de atendimento. Ele NÃO diagnostica, não interpreta exame e não prioriza clinicamente.** Diagnóstico e análise de imagem médica são software como dispositivo médico, com regulação da ANVISA, e ficam fora do escopo.

| Tarefa | Entrada | Perguntas (3 respostas cada) | Ação do código |
|---|---|---|---|
| **Triagem de mensagens** (WhatsApp/e-mail) | mensagem do paciente | quer agendar? quer remarcar/cancelar? pede resultado/documento? **menciona sintoma de alarme?** | encaminha para a fila certa; **sintoma de alarme = "sim" OU "não dá pra saber" → humano na hora + orientação padrão de urgência (192/PS)**; nunca descarta |
| **Conferência de pedido de exame/guia** | texto do pedido ou da guia (OCR) | tem nome do paciente? tem CRM/assinatura? tem o procedimento? tem a data dentro da validade? | completo → segue; faltando → devolve com o motivo; incerto → secretária confere |
| **Regras do convênio** | termos do plano + procedimento | procedimento coberto? exige autorização prévia? tem carência? | cruza com o cadastro do paciente (código) → "autorizar", "pedir autorização", "revisar" |
| **Documentos por foto** (imagem, nível 1) | foto de carteirinha, pedido ou documento | é o documento esperado? está legível? está dentro da validade (o OCR lê, o código compara)? | foto ruim → pede outra; nunca aceita no lugar do texto |

É o mesmo padrão da agência de viagens: **o modelo observa, o código decide** (agenda, convênio, validade) **e a dúvida vai para a secretária.**

Regras específicas da saúde (entram na ficha):

- **Assimetria de erro**: na pergunta "sintoma de alarme", errar para menos é inaceitável. A meta é *recall ≈ 100% no teste* para "sim"; "não dá pra saber" também escala para um humano; e a métrica principal é **alarmes perdidos = 0**, não acurácia.
- **LGPD, dado sensível de saúde**: tudo roda na VPS da própria clínica (é mais um motivo para rodar local), sem enviar conteúdo a APIs externas. Logs guardam só IDs, rótulos e hashes. A anonimização dos exemplos acontece **antes** do treino. Dados reais de paciente nunca entram no Git.
- **Dados**: começar com mensagens sintéticas marcadas como sintéticas e, com autorização da clínica, usar amostras reais anonimizadas e anotadas pela equipe dela. O teste independente vem de outra clínica ou de outro período.
- **Aviso no produto**: "triagem administrativa automatizada; não substitui avaliação profissional".

## 8. Custos e tempo (estimativas, não medidas)

- Inferência local: sem custo de API. Latência e throughput na GB10 **a medir** na fase 6.
- Treino: o autor relata 3–6 h sem GPU. Na GB10 com CUDA deve ser bem menos [não medido].
- Download: ~0,6 GB (ModernBERT-base) a ~1,1 GB (mDeBERTa); bge-m3 ~2,3 GB [estimado].
- Pagos só na fase 8 (Jev), e só com OK explícito. O custo do agente de código é separado.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| torch/CUDA não resolve em aarch64 + Blackwell | Fase 0 primeiro; fallback: wheel NVIDIA para aarch64 ou container NGC PyTorch |
| Base inglesa com documentos PT | Comparar EN vs. multilíngue já na fase 3 |
| Números bons só dentro da distribuição (caso do autor) | Raia OOD obrigatória + meta de queda máxima |
| Dados sintéticos com gabarito escrito por LLM | Marcar `sintetico`; amostra revisada por humano antes do teste |
| Documento longo | Chunking + agregação; nunca truncar |
| Imagem "confirmando" o que não prova | Regras tratam a imagem como observação própria, com escopo limitado |

## 10. Próximos passos imediatos (aguardando OK)

1. **Fase 0**: rodar o smoke test do starter na GB10 num workshop dentro de `docs/ref-away-together-starter/` (local, sem custo) e registrar o resultado.
2. Decidir o 1º domínio (recomendado: viagem em PT).
3. Decidir sobre o remoto: criar `inematds/jev-open` e publicar (só os arquivos versionados; originais continuam locais)?
