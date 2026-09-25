# Changelog

## v0.3.3 — 2026-09-25

- Novo domínio `tasks/advocacia-atendimento/`: 7 perguntas (agendar, serviço, andamento, pagamento, documento, dúvida jurídica, urgência), escopo administrativo (sem parecer, sem cálculo de prazo, andamento só após verificação de identidade), rede de palavras-chave de urgência (só escalona), `regras.py` e meta de urgências perdidas = 0.
- 5 exemplos **sintéticos escritos pelo Claude**, **não revisados pelo usuário** (revisão dispensada por ele; registrado em `portao_1`), somente teste.
- `tools/zeroshot_smoke.py` agora é genérico: a ficha declara `rede: {modulo, pergunta}` e o recibo conta `<pergunta>_perdidos`. `load_ficha` valida esse campo.
- Redes de palavras-chave com `\b` (evita falso disparo em "solicitado", "preliminarmente", "surpresa", "sem arrumar").
- Smoke zero-shot, **não é benchmark** (exemplos sintéticos, somente teste) [medido]: advocacia, 35 decisões: bge-m3 22/35, mDeBERTa 12/35 (`hipoteses`) e 8/35 (`unica`), ModernBERT 12/35, rede de urgência 4/5; urgências perdidas = 0 em todos. Clínica, re-rodada com a ferramenta genérica: mesmos números da v0.2.2, alarmes perdidos = 0.

## v0.2.3 — 2026-09-25

- Portão 1 aprovado pelo usuário: significados dos rótulos e os 5 exemplos da `clinica-triagem` (registrado em `portao_1` na ficha).
- Os 5 exemplos de revisão contam **somente como teste** (smoke/regressão da pilha): campo `somente_teste` na ficha e guarda `exige_uso_em_dados()` em `core/task.py`, que barra o arquivo como treino, dev, teste final ou OOD. O recibo do smoke da v0.2.2 não é benchmark.

## v0.2.2 — 2026-09-25

- Fase 0: ambiente com uv; `torch 2.14.0+cu130` com CUDA ativo na GB10 [medido].
- `core/task.py` (ficha + validação de registros) e `core/model.py` (leitor NLI genérico, modos `hipoteses` e `unica`, rótulos NLI lidos de `config.id2label`, sem truncar em silêncio).
- `tasks/clinica-triagem/`: ficha (4 perguntas, escopo administrativo), rede de palavras-chave de alarme (só escalona), `regras.py` (código decide a fila) e 5 exemplos **sintéticos** escritos pelo Claude para o portão 1 — **ainda não revisados pelo usuário**.
- `tools/zeroshot_smoke.py` + recibo `tasks/clinica-triagem/recibos/zeroshot-smoke-2026-09-25T033504.json`. Smoke zero-shot, **não é benchmark** (5 mensagens sintéticas, 20 decisões) [medido]: bge-m3-zeroshot 15/20; ModernBERT (só EN) 8/20; mDeBERTa-xnli 7/20 (`unica`) e 6/20 (`hipoteses`); rede de alarme 3/5 na pergunta alarme. Nenhum motor classificou como `nao` o único alarme real (`rev-02`), e a rede também o pega.

## v0.1.2 — 2026-09-25

- `docs/COMO-FUNCIONA.md`: onde entram o Jev, o LLM e o código puro no exemplo do hotel; demo reproduzido localmente (Maya: decline → review), com capturas.

## v0.1.1 — 2026-09-24

- PLANO: requisito "roda em qualquer VPS" (treino na GB10, serviço em CPU via ONNX int8, Docker amd64/arm64, imagem em 3 níveis) e exemplo de clínica médica (escopo administrativo, sem diagnóstico, LGPD, meta de alarmes perdidos = 0).

## v0.1.0 — 2026-09-24

- Projeto criado. Materiais recebidos guardados em `docs/originais/`, e o starter público clonado em `docs/ref-away-together-starter/` (commit `5b89c40`); ambos somente locais.
- `docs/ANALISE.md`: arquitetura, números com procedência, contradições entre fontes e problemas do código (pergunta ausente da entrada no tutorial, 3 candidatos fixos, sem chunking, engine sem CUDA, base só em inglês).
- `docs/PLANO.md`: padrão "modelo observa, código decide, incerteza vira revisão", com fases 0–8, portões e contrato `ficha.yaml`.
- `templates/FICHA-TAREFA.md`.
