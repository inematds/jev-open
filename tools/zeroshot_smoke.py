"""Teste de fumaça zero-shot: roda os modelos candidatos da ficha nos exemplos de revisão.

NÃO é benchmark: 5 mensagens, sem treino. Serve para ver se a pilha roda em PT
e se as saídas fazem sentido. A escolha do modelo base é feita depois, no dev.

uso: uv run python tools/zeroshot_smoke.py clinica-triagem
"""
import hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.task import ROOT, load_ficha, load_records
from core.model import NLIReader

tarefa = sys.argv[1]
ficha = load_ficha(tarefa)
arq = ROOT / 'tasks' / tarefa / 'exemplos-revisao.jsonl'
records = load_records(arq, ficha)
rotulos = ficha['rotulos']
assert rotulos == ['sim', 'nao', 'incerto'], 'modo unica assume a ordem sim/nao/incerto'

sys.path.insert(0, str(ROOT / 'tasks' / tarefa))
import importlib
rede = ficha['rede']  # {modulo, pergunta}: rede de palavras-chave e a pergunta crítica que ela protege
dispara = importlib.import_module(rede['modulo']).dispara
critica = rede['pergunta']

report = {'escopo': 'smoke zero-shot com exemplos somente_teste; NÃO é benchmark', 'tarefa': tarefa,
          'data': datetime.now(timezone.utc).isoformat(timespec='seconds'),
          'dados_sha256': hashlib.sha256(arq.read_bytes()).hexdigest(),
          'n_decisoes': len(records) * len(ficha['perguntas']), 'motores': {}}

for cand in ficha['modelos_candidatos']:
    t0 = time.time()
    reader = NLIReader(cand['id'], cand['revisao'])
    load_s = time.time() - t0
    modos = ['hipoteses'] + (['unica'] if reader.three_way else [])
    for modo in modos:
        nome = f"{cand['id'].split('/')[1]}|{modo}"
        linhas, acertos, t1 = [], 0, time.time()
        for r in records:
            for q in ficha['perguntas']:
                if modo == 'hipoteses':
                    p = reader.hipoteses(r['texto'], q['hipoteses'], rotulos)
                else:
                    p = reader.unica(r['texto'], q['afirmacao'])
                pred = rotulos[max(range(3), key=lambda i: p[i])]
                ok = pred == r['respostas'][q['id']]
                acertos += ok
                linhas.append({'id': r['id'], 'pergunta': q['id'], 'gold': r['respostas'][q['id']],
                               'pred': pred, 'probs': [round(x, 3) for x in p], 'ok': ok})
        report['motores'][nome] = {'modelo': cand['id'], 'revisao': cand['revisao'], 'device': reader.device,
                                   'nli_labels': reader.nli_labels, 'acertos': acertos,
                                   'carga_s': round(load_s, 1), 'inferencia_s': round(time.time() - t1, 2),
                                   'linhas': linhas,
                                   f'{critica}_perdidos': sum(l['pergunta'] == critica and l['gold'] == 'sim'
                                                              and l['pred'] == 'nao' for l in linhas)}
        print(f"{nome:55s} {acertos}/{len(linhas)}  {critica}_perdidos={report['motores'][nome][f'{critica}_perdidos']}")
    del reader

# baseline de regras só para a pergunta crítica: rede disparou -> sim, senão nao
linhas = [{'id': r['id'], 'gold': r['respostas'][critica], 'termos': dispara(r['texto']),
           'pred': 'sim' if dispara(r['texto']) else 'nao'} for r in records]
report[rede['modulo']] = {'pergunta': critica, 'linhas': linhas, 'acertos': sum(l['pred'] == l['gold'] for l in linhas)}
print(f"{rede['modulo'] + ' (só pergunta ' + critica + ')':55s} {report[rede['modulo']]['acertos']}/{len(linhas)}")

out = ROOT / 'tasks' / tarefa / 'recibos'
out.mkdir(exist_ok=True)
dest = out / f"zeroshot-smoke-{report['data'][:19].replace(':', '')}.json"
with dest.open('x') as f:
    json.dump(report, f, indent=1, ensure_ascii=False)
print('recibo:', dest.relative_to(ROOT))
