"""Testes de serviço contra a API rodando: entrada ambígua, contraditória, ausente, longa e malformada.

uso: uv run python tools/testar_servico.py http://127.0.0.1:8080 <tarefa> [--run v1] [--origem local|docker]

Os casos saem dos exemplos de revisão (somente teste) da própria tarefa, então a ferramenta
não depende de domínio. Grava tasks/<t>/recibos/<run>/servico-testes-<origem>.json.
"""
import argparse, json, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import pipeline as pl
from core.task import load_ficha, load_records


def post(url, corpo, cru=None):
    dados = cru if cru is not None else json.dumps(corpo).encode()
    req = urllib.request.Request(url, dados, {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('base'); p.add_argument('tarefa'); p.add_argument('--run', default='v1')
    p.add_argument('--origem', default='local')
    a = p.parse_args()
    ficha = load_ficha(a.tarefa)
    crit, rev = ficha['rede']['pergunta'], ficha['fila_revisao']
    imediato = ficha['acoes'][crit]['sim']
    exemplos = load_records(ROOT / 'tasks' / a.tarefa / 'exemplos-revisao.jsonl', ficha)
    urgente = next(r for r in exemplos if r['respostas'][crit] == 'sim')
    duvidoso = next((r for r in exemplos if r['respostas'][crit] == 'incerto'), exemplos[-1])
    url = f'{a.base}/classify?tarefa={a.tarefa}'
    casos = [
        ('urgente', {'texto': urgente['texto']}, 200, lambda r: r['decisao']['prioridade'] == imediato),
        ('ambigua', {'texto': duvidoso['texto']}, 200, lambda r: r['observacoes'] is not None and r['decisao']['prioridade']),
        ('contraditoria', {'texto': urgente['texto'] + ' Esquece, não é nada urgente, está tudo bem.'}, 200,
         lambda r: r['decisao']['prioridade'] == imediato),
        ('vazia', {'texto': '   '}, 200, lambda r: r['decisao']['prioridade'] == rev and r['observacoes'] is None),
        ('longa_sem_truncar', {'texto': ('Bom dia, segue um relato detalhado. ' * 400) + urgente['texto']}, 200,
         lambda r: r['observacoes'] is None and rev in r['decisao']['filas'] and r['decisao']['prioridade'] == imediato),
        ('sem_campo_texto', {'mensagem': 'oi'}, 400, lambda r: 'erro' in r),
        ('json_quebrado', None, 400, lambda r: 'erro' in r),
        ('texto_nao_string', {'texto': 123}, 400, lambda r: 'erro' in r),
    ]
    resultados, ok_total = [], True
    for nome, corpo, status_esperado, cond in casos:
        st, r = post(url, corpo, b'{quebrado' if corpo is None else None)
        ok = st == status_esperado and bool(cond(r))
        ok_total &= ok
        resultados.append({'caso': nome, 'status': st, 'ok': ok, 'prioridade': (r.get('decisao') or {}).get('prioridade'),
                           'motivos': (r.get('decisao') or {}).get('motivos'), 'ms': r.get('ms')})
        print(f"{'OK ' if ok else 'FALHOU'} {nome:20s} {st} {resultados[-1]['prioridade']} {r.get('ms')}ms")
    st, r = post(f'{a.base}/classify?tarefa=nao-existe', {'texto': 'oi'})
    resultados.append({'caso': 'tarefa_desconhecida', 'status': st, 'ok': st == 400}); ok_total &= st == 400
    recibos = ROOT / 'tasks' / a.tarefa / 'recibos' / a.run
    pl.grava(recibos / f'servico-testes-{a.origem}.json', {'data': pl.agora(), 'base': a.base, 'origem': a.origem,
                                                          'todos_ok': ok_total, 'casos': resultados})
    sys.exit(0 if ok_total else 1)


if __name__ == '__main__':
    main()
