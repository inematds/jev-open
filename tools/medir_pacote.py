"""Mede o pacote ONNX como o serviço o usa: latência por mensagem e pico de RAM do processo.

Roda num processo limpo (sem torch importado) e lê o pico de RAM de /proc/self/status (VmHWM).
Não use `resource.ru_maxrss` num filho de um processo grande: no Linux ele sobrevive ao execve
e devolve o pico do pai (foi o que invalidou o `rss_max_mb` dos servir.json da v1).

uso: uv run python tools/medir_pacote.py <tarefa> [--run v1] [--threads 2] [--split test]
Grava tasks/<t>/recibos/<run>/medida-<split>-<threads>t.json. [medido] nesta máquina, não numa VPS.
"""
import argparse, json, platform, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml
from serve.especialista_onnx import OnnxEspecialista


def pico_mb():
    for linha in open('/proc/self/status'):
        if linha.startswith('VmHWM:'):
            return round(int(linha.split()[1]) / 1024, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('tarefa'); p.add_argument('--run', default='v1')
    p.add_argument('--threads', type=int, default=2); p.add_argument('--split', default='test')
    a = p.parse_args()
    if 'torch' in sys.modules:
        raise SystemExit('torch importado: a medida de RAM não seria do serviço')
    recibos = ROOT / 'tasks' / a.tarefa / 'recibos' / a.run
    destino = recibos / f'medida-{a.split}-{a.threads}t.json'
    if destino.exists():
        raise SystemExit(f'{destino.name} já existe')
    manifest = json.loads((recibos / 'data-manifest.json').read_text())
    ficha = yaml.safe_load((ROOT / 'tasks' / a.tarefa / 'ficha.yaml').read_text())
    pacote = ROOT / 'workshops' / f'{a.tarefa}-{a.run}' / 'pacote'
    antes = pico_mb()
    t0 = time.perf_counter(); m = OnnxEspecialista(pacote, ficha, a.threads); carga = time.perf_counter() - t0
    depois_carga = pico_mb()
    textos = [json.loads(l)['texto'] for l in (ROOT / manifest['splits'][a.split]['arquivo']).read_text().splitlines()]
    m.observa(textos[0])
    lat = []
    for t in textos:
        s = time.perf_counter(); m.observa(t); lat.append((time.perf_counter() - s) * 1000)
    lat.sort()
    rep = {'data': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'pacote': m.meta['versao'],
           'escopo': '[medido] nesta máquina, processo limpo sem torch; NÃO é uma VPS',
           'maquina': {'cpu': platform.machine(), 'threads_onnx': a.threads},
           'split': a.split, 'n': len(lat), 'perguntas_por_mensagem': len(ficha['perguntas']),
           'carga_s': round(carga, 2), 'p50_ms': round(lat[len(lat) // 2], 1), 'p95_ms': round(lat[int(len(lat) * .95) - 1], 1),
           'max_ms': round(lat[-1], 1), 'ram_pico_mb': pico_mb(), 'ram_pico_apos_carga_mb': depois_carga,
           'ram_python_antes_mb': antes,
           'corrige': 'rss_max_mb do servir.json (ru_maxrss herdado do processo pai com torch)'}
    with destino.open('x') as f:
        json.dump(rep, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: rep[k] for k in ('pacote', 'p50_ms', 'p95_ms', 'ram_pico_mb', 'carga_s')}))


if __name__ == '__main__':
    main()
