# Falhas

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 2026-09-25 | `rss_max_mb` do exportar_onnx deu 12.458,8 MB iguais no fp32 e no int8: ru_maxrss sobrevive ao execve e mediu o processo pai com torch | medir RAM com VmHWM num processo limpo (`tools/medir_pacote.py`) e tirar o campo do exportar | prompt |
| 2026-09-25 | Geração OOD com `command-r:35b` a ~90 s por registro aceito (inviável) | trocar o gerador OOD por `llama3.1:8b`; registros parciais descartados | infra |
| 2026-09-25 | `pipeline.py testar` caiu com KeyError depois de imprimir os resultados: a ficha da advocacia dizia `urgencia_perdidas_teste`, o código esperava `urgencia_perdidos_teste` | `load_ficha` valida as chaves de `metas` na carga; chave uniformizada | prompt |
