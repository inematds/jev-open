"""Camada de CÓDIGO: observações do modelo + rede de palavras-chave -> encaminhamento.

Nenhum modelo aqui. Toda mensagem vai para a secretária; isto só define fila e prioridade.
"""
from rede_alarme import dispara  # pasta com hífen não é pacote; importar com a pasta da tarefa no sys.path

PRIORIDADE = ['humano_imediato', 'fila_agenda', 'fila_documentos', 'fila_secretaria', 'fila_normal']


def decide(texto, observacoes, acoes, limiar=0.0):
    """observacoes: {pergunta: {'rotulo': str, 'confianca': float}}.

    Confiança abaixo do limiar vira 'incerto' (limiar calibrado na fase 6; 0 = desligado).
    """
    motivos, filas = [], set()
    for q, obs in observacoes.items():
        rotulo = obs['rotulo']
        if rotulo != 'incerto' and obs['confianca'] < limiar:
            rotulo = 'incerto'
            motivos.append(f'{q}: confiança {obs["confianca"]:.2f} < limiar -> incerto')
        fila = acoes[q].get(rotulo)
        if fila:
            filas.add(fila)
            motivos.append(f'{q}={rotulo} -> {fila}')
    termos = dispara(texto)
    if termos:
        filas.add('humano_imediato')
        motivos.append(f'rede de palavras-chave: {", ".join(termos)} -> humano_imediato')
    filas = sorted(filas or {'fila_normal'}, key=PRIORIDADE.index)
    return {'prioridade': filas[0], 'filas': filas, 'motivos': motivos}
