"""Fase 6: congelado -> pacote ONNX int8 para CPU + medição (paridade, latência, memória).

uso: uv run python tools/exportar_onnx.py <tarefa> [--run v1] [--threads 2]

Saída: workshops/<t>-<run>/pacote/ (NÃO versionado: pesos) e tasks/<t>/recibos/<run>/servir.json.
Latência e RAM são [medido] nesta máquina (GB10, CPU aarch64, N threads) — NÃO é uma VPS.
"""
import argparse, json, platform, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import pipeline as pl
from core.task import load_ficha
from core.metricas import resumo
from serve.especialista_onnx import contrato_ficha

MAX_TOKENS = 1024

MEDIR = r'''
import json, resource, sys, time
sys.path.insert(0, sys.argv[1])
import yaml
from serve.especialista_onnx import OnnxEspecialista
ficha = yaml.safe_load(open(sys.argv[2]))
t0 = time.perf_counter(); m = OnnxEspecialista(sys.argv[3], ficha, int(sys.argv[4]), sys.argv[5]); carga = time.perf_counter() - t0
textos = [json.loads(l)['texto'] for l in open(sys.argv[6])]
m.observa(textos[0])  # aquecimento
lat, obs = [], []
for t in textos:
    a = time.perf_counter(); obs.append(m.observa(t)); lat.append((time.perf_counter() - a) * 1000)
lat.sort()
print(json.dumps({'carga_s': round(carga, 2), 'n': len(lat), 'p50_ms': round(lat[len(lat) // 2], 1),
                  'p95_ms': round(lat[int(len(lat) * .95) - 1], 1), 'max_ms': round(lat[-1], 1),
                  'obs': obs}))
'''


def main():
    import torch
    from onnxruntime.quantization import quantize_dynamic, QuantType
    from core.especialista import Especialista, decisoes
    p = argparse.ArgumentParser()
    p.add_argument('tarefa'); p.add_argument('--run', default='v1'); p.add_argument('--threads', type=int, default=2)
    a = p.parse_args()
    ficha = load_ficha(a.tarefa)
    recibos = ROOT / 'tasks' / a.tarefa / 'recibos' / a.run
    if (recibos / 'servir.json').exists():
        raise SystemExit('servir.json já existe; pacote congelado')
    pacote = ROOT / 'workshops' / f'{a.tarefa}-{a.run}' / 'pacote'
    if pacote.exists():
        raise SystemExit(f'{pacote} já existe')
    pacote.mkdir(parents=True)
    base = json.loads((recibos / 'baseline.json').read_text())
    if base['decisao']['treinar']:
        m, fz = pl.carrega_congelado(a, ficha, recibos)
        origem = {'tipo': 'treinado', 'freeze_sha256': pl.sha(recibos / 'freeze.json')}
    else:
        c = base['decisao']['modelo_para_treino']
        m, fz = Especialista(c['id'], c['revisao']), {'modelo': c, 'temperatura': 1.0}
        origem = {'tipo': 'zero-shot (baseline decidiu não treinar)'}
    m.model.to('cpu').eval(); m.device = 'cpu'

    # 1) export fp32
    enc = m.tokenizer([('texto de exemplo', 'hipótese de exemplo')] * 2, padding=True, return_tensors='pt')
    nomes = [k for k in ('input_ids', 'attention_mask') if k in enc]

    class Envolto(torch.nn.Module):
        def __init__(s, mod):
            super().__init__(); s.mod = mod

        def forward(s, input_ids, attention_mask):
            return s.mod(input_ids=input_ids, attention_mask=attention_mask).logits
    fp32 = pacote / 'model.fp32.onnx'
    torch.onnx.export(Envolto(m.model), tuple(enc[k] for k in nomes), str(fp32), input_names=nomes, output_names=['logits'],
                      dynamic_axes={k: {0: 'lote', 1: 'seq'} for k in nomes} | {'logits': {0: 'lote'}},
                      opset_version=17, dynamo=False, external_data=True)
    # 2) int8 dinâmico (pesos)
    int8 = pacote / 'model.int8.onnx'
    quantize_dynamic(str(fp32), str(int8), weight_type=QuantType.QInt8)
    # 3) tokenizer + contrato
    tj = next(Path.home().glob(f".cache/huggingface/hub/models--{fz['modelo']['id'].replace('/', '--')}/snapshots/{fz['modelo']['revisao']}/tokenizer.json"))
    shutil.copy(tj, pacote / 'tokenizer.json')
    meta = {'versao': f"{a.tarefa}-{a.run}-{pl.sha(int8)[:8]}", 'modelo': fz['modelo'], 'origem': origem,
            'entail': m.entail, 'temperatura': fz['temperatura'], 'rotulos': ficha['rotulos'],
            'contrato_ficha': contrato_ficha(ficha), 'pad_id': m.tokenizer.pad_token_id, 'pad_token': m.tokenizer.pad_token,
            'max_tokens': MAX_TOKENS, 'int8_sha256': pl.sha(int8)}
    (pacote / 'pacote.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    # 4) paridade no teste congelado: torch fp32 vs ONNX fp32 vs ONNX int8 (mesmas entradas)
    test_regs, manifest = pl.carrega_split(a, ficha, recibos, 'test')
    decs = decisoes(test_regs, ficha)
    ref = (m.prediz(decs) / m.temperatura).argmax(-1).tolist()
    # checagem do tokenizer: `tokenizers` (serviço) == transformers (treino)
    from tokenizers import Tokenizer
    tk = Tokenizer.from_file(str(pacote / 'tokenizer.json'))
    for d in decs[:30]:
        for h in d['hipoteses']:
            if tk.encode(d['texto'], h).ids != m.tokenizer(d['texto'], h)['input_ids']:
                raise SystemExit('tokenizer do serviço difere do treino')
    del m
    test_path = ROOT / manifest['splits']['test']['arquivo']
    medidas = {}
    for arq in ('model.fp32.onnx', 'model.int8.onnx'):
        out = subprocess.run([sys.executable, '-c', MEDIR, str(ROOT), str(ROOT / 'tasks' / a.tarefa / 'ficha.yaml'), str(pacote),
                              str(a.threads), arq, str(test_path)], capture_output=True, text=True, check=True)
        r = json.loads(out.stdout.strip().splitlines()[-1])
        obs = r.pop('obs')
        pred = [ficha['rotulos'].index(o[d['pergunta']]['rotulo']) for o, d in
                zip([o for o in obs for _ in ficha['perguntas']], decs)]
        r['metricas_teste'] = {k: v for k, v in resumo(decs, pred, ficha).items() if k != 'por_pergunta'}
        r['concordancia_com_torch'] = round(sum(x == y for x, y in zip(pred, ref)) / len(ref), 4)
        fixos = {'model.int8.onnx', 'tokenizer.json', 'pacote.json'}
        r['tamanho_mb'] = round(((pacote / arq).stat().st_size if arq in fixos else
                                 sum(f.stat().st_size for f in pacote.iterdir() if f.name not in fixos)) / 1e6, 1)
        medidas[arq] = r
        print(arq, {k: v for k, v in r.items() if k != 'metricas_teste'}, 'macro_f1', r['metricas_teste']['macro_f1'])
    torch_f1 = resumo(decs, ref, ficha)['macro_f1']
    delta = round((medidas['model.int8.onnx']['metricas_teste']['macro_f1'] - torch_f1) * 100, 2)
    pl.grava(recibos / 'servir.json', {
        'data': pl.agora(), 'pacote': meta['versao'], 'escopo': '[simulação] dados sintéticos; latência/RAM [medido] na GB10, NÃO numa VPS',
        'maquina': {'cpu': platform.machine(), 'threads_onnx': a.threads, 'nota': 'GB10 (aarch64); a VPS de 2 vCPU/4 GB continua [não medido]'},
        'teste_sha256': manifest['splits']['test']['sha256'], 'torch_fp32_macro_f1': torch_f1, 'medidas': medidas,
        'portao': {'int8_vs_fp32_pp': delta, 'meta_pp': 1.0, 'aprovado': abs(delta) <= 1.0}})
    for f in pacote.iterdir():  # o pacote leva só o int8, o tokenizer e o contrato
        if f.name not in ('model.int8.onnx', 'tokenizer.json', 'pacote.json'):
            f.unlink()


if __name__ == '__main__':
    main()
