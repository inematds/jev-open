# Changelog

## v0.1.1 — 2026-09-24

- PLANO: requisito "roda em qualquer VPS" (treino na GB10, serviço em CPU via ONNX int8, Docker amd64/arm64, imagem em 3 níveis) e exemplo de clínica médica (escopo administrativo, sem diagnóstico, LGPD, meta de alarmes perdidos = 0).

## v0.1.0 — 2026-09-24

- Projeto criado. Materiais recebidos guardados em `docs/originais/`, e o starter público clonado em `docs/ref-away-together-starter/` (commit `5b89c40`); ambos somente locais.
- `docs/ANALISE.md`: arquitetura, números com procedência, contradições entre fontes e problemas do código (pergunta ausente da entrada no tutorial, 3 candidatos fixos, sem chunking, engine sem CUDA, base só em inglês).
- `docs/PLANO.md`: padrão "modelo observa, código decide, incerteza vira revisão", com fases 0–8, portões e contrato `ficha.yaml`.
- `templates/FICHA-TAREFA.md`.
