# Análise do material "Your Own Jev"

Data: 2026-09-24. Base: 4 materiais recebidos (PDF de 1 página, prompt `TRAIN-MY-SPECIALIST.txt`, zip do kit, transcrição do vídeo) + clone do repositório público `earlyaidopters/away-together-starter` (MIT), commit `5b89c40bc1ef077effe15023ecab83d37f4c8eab` (23/09/2026). Originais ficam em `docs/originais/` e o clone em `docs/ref-away-together-starter/`, ambos **somente locais** (fora do Git).

Legenda de procedência, usada em todo o projeto:

- **[medido]**: rodei ou li o código/arquivo e confirmei.
- **[relato]**: o material afirma, mas não reproduzi.
- **[simulação]**: dados sintéticos, ou saídas gravadas que não são inferência ao vivo.

---

## 1. O que é, em uma frase

Um **especialista pequeno e local**: um encoder open-source (ModernBERT treinado em NLI/zero-shot) que lê um documento e responde perguntas fixas com **3 respostas** (atende / contraria / não dá pra saber). A decisão final sobre cada usuário fica com **código determinístico** (orçamento, lista de desejos), não com o modelo.

## 2. Arquitetura (o padrão reutilizável)

```
Documento ──► [modelo: 1 pergunta = 1 escolha entre 3 hipóteses + probabilidades]
                      │  observações (por documento, independem do usuário)
                      ▼
Perfil do usuário ─► [regras em código: aritmética, requisitos, combinação]
                      │
                      ▼
            match / recusa / REVISÃO (evidência ausente ou incerta)
```

- **Tarefa do modelo**: NLI. Para cada pergunta existem 3 frases-hipótese; o modelo pontua `(documento, hipótese)` e a maior pontuação vence. [medido: `apps/agency/travel_lab/nli.py`]
- **Base**: `MoritzLaurer/ModernBERT-base-zeroshot-v2.0`, rev. `d421c45…`, Apache-2.0. [medido: API do HF]
- **Treino do tutorial**: congela tudo menos as 2 últimas camadas + cabeça; AdamW lr 5e-6, batch 8, 2 épocas, seed 20260921. [medido: `tools/tutorial.py`]
- **Disciplina de experimento** (o ponto mais valioso do kit): `prepare` valida o schema e bloqueia sobreposição exata entre splits. `baseline` mede antes. `train` escolhe o checkpoint pelo dev. `freeze.json` guarda os hashes. `test` roda **uma única vez** e depois se recusa a rodar de novo. Nada é sobrescrito (`open('x')`). [medido]
- **Imagem**: um serviço separado, "OpenJev" (visão pré-treinada, ~16 GB, Apple silicon, porta 8081). Ele gera observações próprias ("tem escada", "é lago e não piscina"), que as regras combinam com as do texto. **Não** é um modelo multimodal treinado. [relato: GUIDE.md] O serviço **não está** no repo público.

## 3. O que o repo público entrega e o que não entrega

| Entrega (público, MIT) | Não entrega (é da comunidade paga) |
|---|---|
| Demo web com **observações gravadas** de 40 ofertas e 9 fotos; as regras rodam no browser [simulação] | App local com inferência ao vivo |
| `tools/tutorial.py`: prepare/download/baseline/train/test/predict | Checkpoint V2 e pipeline completo |
| 24 train / 12 dev / 12 test cenários sintéticos (4 perguntas cada) [medido] | Serviço de imagem OpenJev |
| `prepare_task.py`: exemplo de adaptador (roteamento de suporte) | — |
| Prompt `TRAIN-MY-SPECIALIST` (idêntico ao `.txt` recebido) [medido: diff] | — |

Obs.: os diretórios `apps/agency` e `apps/public-demo` existem no clone. `public-demo` precisa de Node 22+.

## 4. Números: o que dizem e o que valem

Resultados do próprio autor em `site/assets/FROZEN-V2-RESULTS.md` [relato]:

| Conjunto | Local (V2) | Jev |
|---|---:|---:|
| Viagem sintético (360 cenários, 1.440 decisões) | **95,28%** | **98,61%** |
| typed-independent (2.000) | 34,05% | 73,65% |
| btzsc-independent (300) | 49,67% | 76,33% |
| Mediana de latência (viagem) | 98,6 ms | 165,6 ms |

Leitura:

1. **Os 95% valem dentro da distribuição.** As referências foram escritas pelo Qwen, auditadas por Gemma e **sem validação humana**. Nos conjuntos independentes o modelo local cai para 34–50%, enquanto o Jev fica em 74–76%. É a sobreadaptação que o próprio vídeo alerta, aparecendo nos dados do autor. **Consequência para o nosso modelo padrão: uma raia de teste independente/fora de distribuição é obrigatória.**
2. O V2 **não bateu o Jev**. O autor registra que o "portão de superioridade" falhou.
3. A vantagem de latência é real no cenário dele [relato], mas compara inferência local aquecida com uma chamada HTTP remota.
4. O tutorial público (48 cenários) **não reproduz** esses números. Ele só testa o pipeline.

## 5. Contradições entre as fontes

| Tema | Fonte A | Fonte B |
|---|---|---|
| Modelo do V2 | Vídeo: "ModernBERT" | README: "video's **DeBERTa** V2 model" |
| Acurácia do V1 | Vídeo: "60%"; GUIDE: 60,28% | FROZEN-V2: "V1… earlier travel accuracy was 66,5%" |
| Multimodal | Vídeo: "Diffusion Gemma" | Docs: serviço OpenJev de visão |
| Hardware | Vídeo: "sem GPU, 3–6 h por treino" | Spec: M5 Max 128 GB, MPS |

## 6. Problemas técnicos encontrados no código (importam para generalizar)

1. **No `tutorial.py` a pergunta nunca chega ao modelo.** [medido] Os candidatos do dataset são genéricos e idênticos para as 4 perguntas ("The document explicitly satisfies the requirement."). O `minibatch` monta só o par `(state, candidato)`. Resultado: as 4 perguntas de um mesmo documento recebem **exatamente a mesma entrada** com golds diferentes (ex.: `train-00000` → golds 2,2,2,1), e o modelo não consegue separá-las. O app original evitava isso de dois jeitos: com hipóteses específicas por pergunta (`HYPOTHESES`) e com o `pairs_for`, que injeta `Decision question:` quando os candidatos não são os de viagem. **Regra no nosso padrão: toda hipótese precisa ser autocontida (citar a condição), ou a pergunta vai na premissa, com a mesma serialização no treino, no teste e no predict.**
2. **Número de respostas fixo em 3** em `records()` e `predict`. Mais rótulos exigem mudar o código.
3. **Limite de tokens sem chunking**: 1024 (tutorial) e 4096 (engine). O código recusa corretamente o truncamento silencioso, mas documento longo exige estratégia de chunking e agregação.
4. **`NLIEngine` só escolhe `mps` ou `cpu`**, sem CUDA. Na GB10 um servidor montado sobre ele rodaria em CPU. O `tutorial.py` escolhe CUDA.
5. **`predict` devolve `calibrated: False`**. Probabilidade não é confiabilidade, e é preciso calibrar (temperatura no dev) antes de usar limiar de revisão.
6. **Idioma**: `answerdotai/ModernBERT-base` é **somente inglês** [medido: card]. O zero-shot v2.0 herda isso. Para documentos em PT-BR, o candidato natural é um NLI multilíngue: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (MIT, inclui `pt`, rev `b5113eb…`) ou `MoritzLaurer/bge-m3-zeroshot-v2.0` (MIT, multilíngue, contexto longo, rev `9abf1c8…`). **Nada disso foi testado ainda.**

## 7. Ambiente local (esta máquina)

NVIDIA **GB10** (DGX Spark, aarch64, Blackwell), ~119 GB de memória unificada, Python 3.12.3, `uv` instalado [medido]. **Não testado**: se o `uv.lock` do starter resolve um torch com CUDA para aarch64/Blackwell. É o primeiro portão do plano.

## 8. Relação com o projeto `jev`

O repo `jev` (laboratório educacional v1.7.x, `jev-gw` como porta única para as consultas) é o lugar para a comparação com o Jev real. O `jev-open` é o lado **open-source local**: produz o especialista e seus recibos. Uma comparação contra o Jev passa pelo `jev-gw` e exige conta, permissão e autorização explícita para chamadas pagas.

## 9. Veredito

- **Vale como método**, não como modelo pronto. O valor está no padrão "modelo observa, código decide, incerteza vira revisão" e na higiene de experimento (hashes, freeze, teste único, sem sobrescrever).
- **Não vale** como prova de que um modelo local pequeno substitui o Jev. Os próprios dados do autor mostram queda forte fora da distribuição.
- Para usar como **modelo padrão em qualquer sistema**, é preciso corrigir: hipóteses autocontidas, base multilíngue, raia OOD obrigatória, calibração e chunking. Ver `PLANO.md`.
