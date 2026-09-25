"""Carrega a ficha de uma tarefa e valida registros. Independe de domínio."""
from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_ficha(tarefa):
    path = ROOT / 'tasks' / tarefa / 'ficha.yaml'
    ficha = yaml.safe_load(path.read_text())
    ids = [q['id'] for q in ficha['perguntas']]
    if len(ids) != len(set(ids)):
        raise ValueError('ids de pergunta repetidos na ficha')
    rotulos = ficha['rotulos']
    for q in ficha['perguntas']:
        h = q['hipoteses']
        if set(h) != set(rotulos):
            raise ValueError(f"{q['id']}: hipoteses precisam cobrir exatamente {rotulos}")
        if len(set(h.values())) != len(h):
            raise ValueError(f"{q['id']}: hipoteses repetidas")
        if not q.get('afirmacao'):
            raise ValueError(f"{q['id']}: falta 'afirmacao' (modo hipótese única)")
    return ficha


def load_records(path, ficha):
    """Registro: {id, grupo, fonte, sintetico, texto, respostas: {pergunta: rotulo}}."""
    ids, out = set(), []
    perguntas = [q['id'] for q in ficha['perguntas']]
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if not isinstance(r.get('id'), str) or r['id'] in ids:
            raise ValueError(f'linha {n}: id ausente ou repetido')
        ids.add(r['id'])
        for campo in ('grupo', 'fonte', 'texto'):
            if not isinstance(r.get(campo), str) or not r[campo].strip():
                raise ValueError(f"{r['id']}: falta '{campo}'")
        if not isinstance(r.get('sintetico'), bool):
            raise ValueError(f"{r['id']}: 'sintetico' precisa ser true/false")
        resp = r.get('respostas', {})
        if set(resp) != set(perguntas):
            raise ValueError(f"{r['id']}: respostas precisam cobrir {perguntas}")
        for q, v in resp.items():
            if v not in ficha['rotulos']:
                raise ValueError(f"{r['id']}.{q}: rótulo inválido {v!r}")
        out.append(r)
    if not out:
        raise ValueError('arquivo vazio')
    return out
