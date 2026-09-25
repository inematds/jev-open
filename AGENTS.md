# Regras do projeto jev-open

Ler, nesta ordem: este arquivo, `docs/ANALISE.md` e `docs/PLANO.md`.

- Conta de destino: **inematds**. Autor e committer: `inematds <inematds@gmail.com>`. Publicação via Git. Não consultar nem manipular o Vercel.
- Projeto de pesquisa/educação: especialista classificador local e open-source no estilo Jev. **Não** declarar paridade com o Jev, superioridade, prontidão para produção ou benchmark do Jev real sem evidência medida.
- Marcar todo número como **[medido]**, **[relato]** ou **[simulação]**. Dado sintético é rotulado como sintético, e revisão feita por IA não é validação humana.
- `docs/originais/` (materiais recebidos) e `docs/ref-away-together-starter/` (clone de referência) ficam **somente locais**, ignorados pelo Git. Não usar `git add -f` nesses caminhos. Não publicar os documentos recebidos.
- Código copiado do starter (MIT) leva junto o aviso de licença. Modelos e datasets mantêm os próprios termos.
- Não versionar segredos, pesos (`*.safetensors`), `workshops/` nem dados pessoais.
- Chamadas pagas (Jev, APIs hospedadas) só com autorização explícita. A comparação com o Jev passa pelo `jev-gw` do repo `jev`.
- Versionamento conforme as regras globais (`vX.XX.YY`, sem zerar os campos inferiores fora de major). Registrar no CHANGELOG.
