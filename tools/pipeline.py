"""Fases 2–5 para qualquer tarefa: preparar -> baseline -> treinar -> testar.

uso: uv run python tools/pipeline.py <etapa> <tarefa> [--run v1]

- preparar: fontes em tasks/<t>/dados/{sintetico,ood-sintetico}.jsonl -> train/dev/test/ood,
            deduplicação exata e aproximada (5-gramas de caracteres), split por grupo, data-manifest.json.
- baseline: zero-shot de cada candidato da ficha + rede de palavras-chave, só no dev. Decide se treina.
- treinar : últimas 2 camadas + cabeça do candidato escolhido; checkpoint pelo dev; temperatura no dev.
- testar  : UMA execução. Base vs. treinado no teste e na raia OOD, com as mesmas entradas.

Recibos (versionados): tasks/<t>/recibos/<run>/. Pesos (NÃO versionados): workshops/<t>-<run>/.
Nenhuma etapa sobrescreve um recibo existente.
"""
import argparse, hashlib, json, random, re, sys, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.task import ROOT, load_ficha, load_records, exige_uso_em_dados
from core.metricas import resumo

SEED = 20260925
SPLITS = ('train', 'dev', 'test', 'ood')
JACCARD_NEAR_DUP = 0.6


def agora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def grava(path, valor):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:  # nunca sobrescreve
        json.dump(valor, f, indent=1, ensure_ascii=False)
    print('recibo:', path.relative_to(ROOT))


def norm(t):
    t = unicodedata.normalize('NFKD', t.lower())
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^\w ]', ' ', t)).strip()


def shingles(t, k=5):
    t = norm(t)
    return {t[i:i + k] for i in range(max(1, len(t) - k + 1))}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


# ---------------------------------------------------------------- preparar
def preparar(a, ficha, dados, recibos):
    if (recibos / 'data-manifest.json').exists():
        raise SystemExit('data-manifest.json já existe: dados congelados. Use outro --run para dados novos.')
    fontes = {'indist': dados / 'sintetico.jsonl', 'ood': dados / 'ood-sintetico.jsonl'}
    for f in fontes.values():
        exige_uso_em_dados(f, ficha)
    regs = {k: load_records(f, ficha) for k, f in fontes.items()}
    revisao = [shingles(r['texto']) for r in load_records(ROOT / 'tasks' / a.tarefa / 'exemplos-revisao.jsonl', ficha)]
    descartes = {'exato': [], 'perto_de_revisao': [], 'ood_perto_de_indist': []}

    def filtra(lista):
        vistos, out = set(), []
        for r in lista:
            n = norm(r['texto'])
            if n in vistos:
                descartes['exato'].append(r['id']); continue
            sh = shingles(r['texto'])
            if any(jaccard(sh, s) >= JACCARD_NEAR_DUP for s in revisao):
                descartes['perto_de_revisao'].append(r['id']); continue
            vistos.add(n); r['_sh'] = sh; out.append(r)
        return out

    indist, ood = filtra(regs['indist']), filtra(regs['ood'])
    # quase-duplicatas no in-dist viram o mesmo grupo (union-find), para nunca cruzarem splits
    pai = {r['id']: r['id'] for r in indist}

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]; x = pai[x]
        return x
    pares_perto = 0
    for i, r in enumerate(indist):
        for s in indist[i + 1:]:
            if jaccard(r['_sh'], s['_sh']) >= JACCARD_NEAR_DUP:
                pai[raiz(s['id'])] = raiz(r['id']); pares_perto += 1
    for r in indist:
        r['grupo'] = raiz(r['id'])
    todos_sh = [r['_sh'] for r in indist]
    ood_ok = []
    for r in ood:
        if any(jaccard(r['_sh'], s) >= JACCARD_NEAR_DUP for s in todos_sh):
            descartes['ood_perto_de_indist'].append(r['id'])
        else:
            ood_ok.append(r)
    grupos = sorted({r['grupo'] for r in indist})
    random.Random(SEED).shuffle(grupos)
    alvo = {'train': .625, 'dev': .1875}
    split_de, acc = {}, 0
    for g in grupos:
        n = sum(r['grupo'] == g for r in indist)
        frac = acc / len(indist)
        split_de[g] = 'train' if frac < alvo['train'] else 'dev' if frac < alvo['train'] + alvo['dev'] else 'test'
        acc += n
    saida = {s: [] for s in SPLITS}
    for r in indist:
        saida[split_de[r['grupo']]].append(r)
    saida['ood'] = ood_ok
    manifest = {'data': agora(), 'tarefa': a.tarefa, 'run': a.run, 'sintetico': True,
                'aviso': 'dados 100% sintéticos gerados e conferidos por LLMs locais; resultados são [simulação] do pipeline, não evidência do domínio',
                'fontes': {k: {'arquivo': str(f.relative_to(ROOT)), 'sha256': sha(f), 'registros': len(regs[k])} for k, f in fontes.items()},
                'dedup': {'jaccard_5gramas': JACCARD_NEAR_DUP, 'pares_perto_no_indist_agrupados': pares_perto,
                          'descartes': {k: len(v) for k, v in descartes.items()}, 'ids_descartados': descartes},
                'splits': {}}
    for s, lista in saida.items():
        path = dados / f'{s}.jsonl'
        with path.open('x') as f:
            for r in lista:
                f.write(json.dumps({k: v for k, v in r.items() if k != '_sh'}, ensure_ascii=False) + '\n')
        manifest['splits'][s] = {'arquivo': str(path.relative_to(ROOT)), 'sha256': sha(path), 'registros': len(lista),
                                 'grupos': len({r['grupo'] for r in lista}),
                                 'rotulos': {q['id']: {l: sum(r['respostas'][q['id']] == l for r in lista) for l in ficha['rotulos']}
                                             for q in ficha['perguntas']}}
    # checagem final: nenhum texto nem grupo cruza splits
    for i, s1 in enumerate(SPLITS):
        for s2 in SPLITS[i + 1:]:
            if {norm(r['texto']) for r in saida[s1]} & {norm(r['texto']) for r in saida[s2]}:
                raise SystemExit(f'sobreposição exata entre {s1} e {s2}')
            if s2 != 'ood' and {r['grupo'] for r in saida[s1]} & {r['grupo'] for r in saida[s2]}:
                raise SystemExit(f'grupo cruzando {s1} e {s2}')
    grava(recibos / 'data-manifest.json', manifest)
    print({s: v['registros'] for s, v in manifest['splits'].items()})


def carrega_split(a, ficha, recibos, split):
    manifest = json.loads((recibos / 'data-manifest.json').read_text())
    m = manifest['splits'][split]
    path = ROOT / m['arquivo']
    if sha(path) != m['sha256']:
        raise SystemExit(f'{split} mudou depois do manifest: crie outro --run')
    exige_uso_em_dados(path, ficha)
    return load_records(path, ficha), manifest


# ---------------------------------------------------------------- baseline
def baseline(a, ficha, recibos):
    from core.model import NLIReader
    from core.especialista import decisoes
    import importlib
    if (recibos / 'baseline.json').exists():
        raise SystemExit('baseline.json já existe; preserve-o')
    dev, manifest = carrega_split(a, ficha, recibos, 'dev')
    decs = decisoes(dev, ficha)
    rot = ficha['rotulos']
    rep = {'data': agora(), 'split': 'dev', 'escopo': '[simulação] dados sintéticos', 'dev_sha256': manifest['splits']['dev']['sha256'],
           'motores': {}}
    for cand in ficha['modelos_candidatos']:
        reader = NLIReader(cand['id'], cand['revisao'])
        for modo in ['hipoteses'] + (['unica'] if reader.three_way else []):
            t0 = time.time()
            pred = []
            for d in decs:
                q = next(x for x in ficha['perguntas'] if x['id'] == d['pergunta'])
                p = reader.hipoteses(d['texto'], q['hipoteses'], rot) if modo == 'hipoteses' else reader.unica(d['texto'], q['afirmacao'])
                pred.append(max(range(3), key=lambda i: p[i]))
            nome = f"{cand['id']}|{modo}"
            rep['motores'][nome] = {'modelo': cand['id'], 'revisao': cand['revisao'], 'modo': modo, 'device': reader.device,
                                    'segundos': round(time.time() - t0, 1), **resumo(decs, pred, ficha)}
            print(f"{nome:70s} macro_f1={rep['motores'][nome]['macro_f1']}")
        del reader
    sys.path.insert(0, str(ROOT / 'tasks' / a.tarefa))
    dispara = importlib.import_module(ficha['rede']['modulo']).dispara
    crit = [d for d in decs if d['pergunta'] == ficha['rede']['pergunta']]
    rp = [rot.index('sim') if dispara(d['texto']) else rot.index('nao') for d in crit]
    fcrit = {**ficha, 'perguntas': [q for q in ficha['perguntas'] if q['id'] == ficha['rede']['pergunta']]}
    rep['rede_palavras_chave'] = {'pergunta': ficha['rede']['pergunta'], **resumo(crit, rp, fcrit)}
    treinaveis = {k: v for k, v in rep['motores'].items() if v['modo'] == 'hipoteses'}
    melhor = max(treinaveis, key=lambda k: treinaveis[k]['macro_f1'])
    meta = ficha['metas']['macro_f1_dev_min']
    rep['decisao'] = {'meta_macro_f1_dev_min': meta, 'melhor_zero_shot': melhor,
                      'macro_f1': treinaveis[melhor]['macro_f1'],
                      'treinar': treinaveis[melhor]['macro_f1'] < meta,
                      'modelo_para_treino': {'id': treinaveis[melhor]['modelo'], 'revisao': treinaveis[melhor]['revisao']},
                      'regra': 'treina o melhor candidato do modo hipoteses se o zero-shot não bate a meta no dev'}
    grava(recibos / 'baseline.json', rep)
    print('decisão:', rep['decisao'])


# ---------------------------------------------------------------- treinar
def treinar(a, ficha, recibos, oficina):
    import torch
    from safetensors.torch import save_file
    from core.especialista import Especialista, decisoes
    base = json.loads((recibos / 'baseline.json').read_text())
    if not base['decisao']['treinar']:
        raise SystemExit('baseline decidiu não treinar (zero-shot já bate a meta)')
    if (recibos / 'freeze.json').exists():
        raise SystemExit('freeze.json já existe; treino congelado')
    train, manifest = carrega_split(a, ficha, recibos, 'train')
    dev, _ = carrega_split(a, ficha, recibos, 'dev')
    torch.manual_seed(SEED); rng = random.Random(SEED)
    cand = base['decisao']['modelo_para_treino']
    m = Especialista(cand['id'], cand['revisao'])
    params = m.congela(a.camadas)
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=.01)
    dtr, ddev = decisoes(train, ficha), decisoes(dev, ficha)
    oficina.mkdir(parents=True, exist_ok=True)
    ck = oficina / 'checkpoint.safetensors'
    if ck.exists():
        raise SystemExit(f'{ck} já existe; use outro --run')
    hist, melhor, t0 = [], None, time.time()
    for ep in range(1, a.epocas + 1):
        m.train(); rng.shuffle(dtr); perdas = []
        for i in range(0, len(dtr), a.lote):
            lote = dtr[i:i + a.lote]
            y = torch.tensor([d['gold'] for d in lote], device=m.device)
            loss = torch.nn.functional.cross_entropy(m.pontua(lote), y)
            if not torch.isfinite(loss):
                raise SystemExit(f'loss não finita na época {ep}')
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step()
            perdas.append(loss.item())
        z = m.prediz(ddev)
        met = resumo(ddev, z.argmax(-1).tolist(), ficha)
        linha = {'epoca': ep, 'loss_treino': round(sum(perdas) / len(perdas), 4), 'dev': met, 'segundos': round(time.time() - t0, 1)}
        hist.append(linha)
        print(json.dumps({k: linha[k] for k in ('epoca', 'loss_treino', 'segundos')} | {'dev_macro_f1': met['macro_f1']}), flush=True)
        if melhor is None or met['macro_f1'] > melhor['macro_f1']:
            melhor = {'epoca': ep, 'macro_f1': met['macro_f1']}
            treinados = {n for n, p in m.model.named_parameters() if p.requires_grad}
            save_file({n: t.detach().cpu().contiguous() for n, t in m.model.state_dict().items() if n in treinados}, str(ck))
    # recarrega o melhor e calibra a temperatura no dev
    from safetensors.torch import load_file
    m.model.load_state_dict(load_file(str(ck)), strict=False)
    cal = m.calibra(m.prediz(ddev), [d['gold'] for d in ddev])
    receita = {'modelo': cand, 'camadas_treinadas': a.camadas, 'lr': a.lr, 'lote_decisoes': a.lote, 'epocas': a.epocas,
               'seed': SEED, 'otimizador': 'AdamW wd=0.01, clip 1.0', 'device': m.device}
    grava(recibos / 'training.json', {'data': agora(), 'escopo': '[simulação] dados sintéticos', 'receita': receita,
                                      'historia': hist, 'melhor': melhor, 'calibracao': cal})
    grava(recibos / 'freeze.json', {'data': agora(), 'checkpoint': str(ck.relative_to(ROOT)), 'checkpoint_sha256': sha(ck),
                                    'formato': 'só os parâmetros treinados; carregar sobre o modelo base na revisão fixa',
                                    'modelo': cand, 'temperatura': cal['temperatura'], 'rotulos': ficha['rotulos'],
                                    'dados': {s: v['sha256'] for s, v in manifest['splits'].items()}})


def carrega_congelado(a, ficha, recibos):
    from safetensors.torch import load_file
    from core.especialista import Especialista
    fz = json.loads((recibos / 'freeze.json').read_text())
    ck = ROOT / fz['checkpoint']
    if sha(ck) != fz['checkpoint_sha256']:
        raise SystemExit('checkpoint mudou depois do freeze')
    if fz['rotulos'] != ficha['rotulos']:
        raise SystemExit('ordem de rótulos da ficha mudou depois do freeze')
    m = Especialista(fz['modelo']['id'], fz['modelo']['revisao'])
    faltando, inesperado = m.model.load_state_dict(load_file(str(ck)), strict=False)
    if inesperado:
        raise SystemExit(f'checkpoint com chaves inesperadas: {inesperado[:3]}')
    m.temperatura = fz['temperatura']
    return m, fz


# ---------------------------------------------------------------- testar
def testar(a, ficha, recibos):
    import importlib
    from core.especialista import Especialista, decisoes
    if (recibos / 'test.json').exists():
        raise SystemExit('teste final já aberto; leia test.json em vez de rodar de novo')
    base = json.loads((recibos / 'baseline.json').read_text())
    treinou = base['decisao']['treinar']
    sys.path.insert(0, str(ROOT / 'tasks' / a.tarefa))
    dispara = importlib.import_module(ficha['rede']['modulo']).dispara
    crit, rot = ficha['rede']['pergunta'], ficha['rotulos']
    splits = {s: carrega_split(a, ficha, recibos, s)[0] for s in ('test', 'ood')}
    manifest = json.loads((recibos / 'data-manifest.json').read_text())
    cand = base['decisao']['modelo_para_treino']
    motores = {'base': lambda: Especialista(cand['id'], cand['revisao'])}
    if treinou:
        motores['treinado'] = lambda: carrega_congelado(a, ficha, recibos)[0]
    rep = {'data': agora(), 'escopo': '[simulação] teste final em dados sintéticos; UMA execução',
           'dados': {s: manifest['splits'][s]['sha256'] for s in splits}, 'motores': {}}
    if treinou:
        rep['freeze_sha256'] = sha(recibos / 'freeze.json')
    for nome, fabrica in motores.items():
        m = fabrica(); rep['motores'][nome] = {}
        for s, regs in splits.items():
            decs = decisoes(regs, ficha)
            probs = (m.prediz(decs) / m.temperatura).softmax(-1)
            pred = probs.argmax(-1).tolist()
            met = resumo(decs, pred, ficha)
            # perdidos depois do OU com a rede de palavras-chave (o que o código de fato faz)
            met[f'{crit}_perdidos_com_rede'] = sum(d['pergunta'] == crit and d['gold'] == rot.index('sim')
                                                   and p == rot.index('nao') and not dispara(d['texto'])
                                                   for d, p in zip(decs, pred))
            met['linhas'] = [{'id': d['id'], 'pergunta': d['pergunta'], 'gold': rot[d['gold']], 'pred': rot[p],
                              'probs': [round(x, 3) for x in pr]} for d, p, pr in zip(decs, pred, probs.tolist())]
            rep['motores'][nome][s] = met
            print(f"{nome:9s} {s:5s} macro_f1={met['macro_f1']} {crit}_perdidos={met[f'{crit}_perdidos']}"
                  f" com_rede={met[f'{crit}_perdidos_com_rede']}")
        del m
    final = rep['motores']['treinado' if treinou else 'base']
    metas = ficha['metas']
    queda = round((final['test']['macro_f1'] - final['ood']['macro_f1']) * 100, 1)
    rep['metas'] = {
        'aviso': 'com dados sintéticos isto verifica o pipeline, não o domínio; metas reais exigem dados reais',
        f'{crit}_perdidos_teste': {'meta': metas[f'{crit}_perdidos_teste'],
                                   'obtido_modelo': final['test'][f'{crit}_perdidos'],
                                   'obtido_com_rede': final['test'][f'{crit}_perdidos_com_rede']},
        'ood_macro_f1_min': {'meta': metas['ood_macro_f1_min'], 'obtido': final['ood']['macro_f1']},
        'queda_ood_max_pp': {'meta': metas['queda_ood_max_pp'], 'obtido': queda},
    }
    grava(recibos / 'test.json', rep)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('etapa', choices=['preparar', 'baseline', 'treinar', 'testar'])
    p.add_argument('tarefa')
    p.add_argument('--run', default='v1')
    p.add_argument('--camadas', type=int, default=2)
    p.add_argument('--lr', type=float, default=1e-5)
    p.add_argument('--lote', type=int, default=8)
    p.add_argument('--epocas', type=int, default=4)
    a = p.parse_args()
    ficha = load_ficha(a.tarefa)
    dados = ROOT / 'tasks' / a.tarefa / 'dados'
    recibos = ROOT / 'tasks' / a.tarefa / 'recibos' / a.run
    oficina = ROOT / 'workshops' / f'{a.tarefa}-{a.run}'
    {'preparar': lambda: preparar(a, ficha, dados, recibos), 'baseline': lambda: baseline(a, ficha, recibos),
     'treinar': lambda: treinar(a, ficha, recibos, oficina), 'testar': lambda: testar(a, ficha, recibos)}[a.etapa]()


if __name__ == '__main__':
    main()
