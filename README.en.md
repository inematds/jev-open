# jev-open

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

![jev-open — local triage specialist](guia/assets/banner.jpg)

## 📖 User Guide

Complete guide (landing page + step-by-step instructions): **https://inematds.github.io/jev-open/guia/en/**

A **local, open-source** Jev-style classification specialist: the model reads a document and answers fixed questions with 3 responses (meets / contradicts / no evidence), and the code applies the business rules. Uncertainty is sent for review.

Status: **v0.6.4.** Complete v1 run in both example niches (`tasks/advocacia-atendimento/`, `tasks/clinica-triagem/`): data, baseline, training, final test, ONNX int8, CPU API, and Docker. The data is **100% synthetic**, so the numbers are [simulation] of the pipeline; see [v1 Results](docs/RESULTADOS-v1.md).

- [Reference material analysis](docs/ANALISE.md)
- [How it works (hotel)](docs/COMO-FUNCIONA.md)
- [Default model plan for any system](docs/PLANO.md)
- [Step-by-step by niche (and from scratch for others)](docs/PASSO-A-PASSO.md)
- [Results of the v1 run](docs/RESULTADOS-v1.md)
- [Suggestion: choose a model and tool in assistants (Jarvis, openpcbotv3)](docs/SUGESTAO-ROTEAMENTO.md) — not implemented
- [Task sheet (template)](templates/FICHA-TAREFA.md)

Public reference: <https://github.com/earlyaidopters/away-together-starter> (MIT). Independent project; not an official Jev implementation.
