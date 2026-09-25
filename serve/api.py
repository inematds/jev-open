"""API mínima em CPU: POST /classify?tarefa=<t>  corpo {"texto": "..."}.

O modelo observa (rótulo por pergunta), o CÓDIGO da tarefa decide a fila (tasks/<t>/regras.py),
e toda dúvida vira revisão humana: texto vazio, longo demais ou erro interno nunca é descartado.
Resposta inspecionável: observações com probabilidades, fila, motivos e versão do pacote.

uso: JEV_PACOTES=/pacotes python -m serve.api --porta 8080 --tarefas advocacia-atendimento clinica-triagem
     (cada tarefa em $JEV_PACOTES/<tarefa>/)
"""
import argparse, importlib, json, os, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from serve.especialista_onnx import OnnxEspecialista, TextoLongo

MAX_BYTES = 64_000


def carrega_tarefa(tarefa, pacotes, threads):
    ficha = yaml.safe_load((ROOT / 'tasks' / tarefa / 'ficha.yaml').read_text())
    sys.path.insert(0, str(ROOT / 'tasks' / tarefa))
    regras = importlib.import_module('regras')
    sys.path.pop(0)
    sys.modules.pop('regras')  # cada tarefa tem o seu regras.py
    return {'ficha': ficha, 'regras': regras, 'modelo': OnnxEspecialista(Path(pacotes) / tarefa, ficha, threads)}


def revisao(ficha, motivo):
    """Sem observação confiável: vai para atendimento humano, com o motivo explícito."""
    fila = ficha['fila_revisao']
    return {'prioridade': fila, 'filas': [fila], 'motivos': [motivo]}


def classifica(t, texto):
    if not texto.strip():
        return {'observacoes': None, 'decisao': revisao(t['ficha'], 'texto vazio -> revisão humana')}
    try:
        obs = t['modelo'].observa(texto)
    except TextoLongo as e:
        dec = revisao(t['ficha'], f'texto longo demais ({e}) -> revisão humana, sem truncar')
        # a rede de palavras-chave ainda roda: urgência em texto longo não pode sumir
        extra = t['regras'].decide(texto, {}, t['ficha']['acoes'])
        if extra['motivos']:
            dec = {'prioridade': extra['prioridade'], 'filas': extra['filas'] + dec['filas'], 'motivos': extra['motivos'] + dec['motivos']}
        return {'observacoes': None, 'decisao': dec}
    return {'observacoes': obs, 'decisao': t['regras'].decide(texto, obs, t['ficha']['acoes'])}


def servidor(tarefas):
    class H(BaseHTTPRequestHandler):
        def _json(self, code, body):
            b = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if urlparse(self.path).path == '/health':
                return self._json(200, {'ok': True, 'tarefas': {k: v['modelo'].meta['versao'] for k, v in tarefas.items()}})
            self._json(404, {'erro': 'use POST /classify?tarefa=<t> ou GET /health'})

        def do_POST(self):
            u = urlparse(self.path)
            if u.path != '/classify':
                return self._json(404, {'erro': 'rota desconhecida'})
            tarefa = parse_qs(u.query).get('tarefa', [None])[0]
            if tarefa not in tarefas:
                return self._json(400, {'erro': f'tarefa desconhecida; disponíveis: {sorted(tarefas)}'})
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_BYTES:
                return self._json(413, {'erro': f'corpo > {MAX_BYTES} bytes'})
            try:
                corpo = json.loads(self.rfile.read(n) or b'{}')
                texto = corpo['texto']
                if not isinstance(texto, str):
                    raise TypeError
            except (ValueError, KeyError, TypeError):
                return self._json(400, {'erro': 'corpo precisa ser JSON {"texto": "<string>"}'})
            t0 = time.perf_counter()
            t = tarefas[tarefa]
            try:
                r = classifica(t, texto)
            except Exception as e:  # erro interno também vira revisão, nunca descarte
                r = {'observacoes': None, 'decisao': revisao(t['ficha'], f'erro interno ({type(e).__name__}) -> revisão humana')}
            r.update({'tarefa': tarefa, 'pacote': t['modelo'].meta['versao'],
                      'aviso': t['ficha'].get('aviso', 'triagem administrativa automatizada; não substitui avaliação profissional'),
                      'ms': round((time.perf_counter() - t0) * 1000, 1)})
            self._json(200, r)

        def log_message(self, *a):  # logs só com rota e status; nunca o texto (LGPD / sigilo)
            sys.stderr.write(f'{self.command} {urlparse(self.path).path} {a[1] if len(a) > 1 else ""}\n')
    return H


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--porta', type=int, default=8080)
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--tarefas', nargs='+', required=True)
    p.add_argument('--threads', type=int, default=int(os.environ.get('JEV_THREADS', 2)))
    a = p.parse_args()
    pacotes = os.environ.get('JEV_PACOTES', str(ROOT / 'pacotes'))
    tarefas = {t: carrega_tarefa(t, pacotes, a.threads) for t in a.tarefas}
    print(f'servindo {sorted(tarefas)} em {a.host}:{a.porta}', flush=True)
    ThreadingHTTPServer((a.host, a.porta), servidor(tarefas)).serve_forever()


if __name__ == '__main__':
    main()
