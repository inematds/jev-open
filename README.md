# jev-open

![jev-open — especialista local de triagem](guia/assets/banner.jpg)

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/jev-open/guia/**

Especialista classificador **local e open-source** no estilo Jev: o modelo lê um documento e responde perguntas fixas com 3 respostas (atende / contraria / sem evidência), e o código aplica as regras de negócio. A incerteza vai para revisão.

Status: **v0.6.4.** Run v1 completo nos dois nichos de exemplo (`tasks/advocacia-atendimento/`, `tasks/clinica-triagem/`): dados, baseline, treino, teste final, ONNX int8, API em CPU e Docker. Dados **100% sintéticos**, então os números são [simulação] do pipeline; ver [Resultados v1](docs/RESULTADOS-v1.md).

- [Análise do material de referência](docs/ANALISE.md)
- [Como funciona (hotel)](docs/COMO-FUNCIONA.md)
- [Plano do modelo padrão para qualquer sistema](docs/PLANO.md)
- [Passo a passo por nicho (e do zero em outros)](docs/PASSO-A-PASSO.md)
- [Resultados do run v1](docs/RESULTADOS-v1.md)
- [Ficha de tarefa (template)](templates/FICHA-TAREFA.md)

Referência pública: <https://github.com/earlyaidopters/away-together-starter> (MIT). Projeto independente; não é uma implementação oficial do Jev.
