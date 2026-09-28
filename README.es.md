# jev-open

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

![jev-open — especialista local de triagem](guia/assets/banner.jpg)

## 📖 Guía de uso

Guía completa (landing + paso a paso): **https://inematds.github.io/jev-open/guia/es/**

Especialista clasificador **local y de código abierto** al estilo Jev: el modelo lee un documento y responde preguntas fijas con 3 respuestas (cumple / contradice / sin evidencia), y el código aplica las reglas de negocio. La incertidumbre pasa a revisión.

Estado: **v0.6.4.** Run v1 completo en los dos nichos de ejemplo (`tasks/advocacia-atendimento/`, `tasks/clinica-triagem/`): datos, baseline, entrenamiento, prueba final, ONNX int8, API en CPU y Docker. Datos **100% sintéticos**, así que las cifras son [simulación] del pipeline; ver [Resultados v1](docs/RESULTADOS-v1.md).

- [Análisis del material de referencia](docs/ANALISE.md)
- [Cómo funciona (hotel)](docs/COMO-FUNCIONA.md)
- [Plan del modelo estándar para cualquier sistema](docs/PLANO.md)
- [Paso a paso por nicho (y desde cero en otros)](docs/PASSO-A-PASSO.md)
- [Resultados del run v1](docs/RESULTADOS-v1.md)
- [Sugerencia: elegir modelo y herramienta en asistentes (Jarvis, openpcbotv3)](docs/SUGESTAO-ROTEAMENTO.md) — no implementado
- [Ficha de tarea (template)](templates/FICHA-TAREFA.md)

Referencia pública: <https://github.com/earlyaidopters/away-together-starter> (MIT). Proyecto independiente; no es una implementación oficial de Jev.
