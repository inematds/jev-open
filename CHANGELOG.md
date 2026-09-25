# Changelog

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
