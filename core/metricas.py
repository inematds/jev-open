"""Métricas comuns: macro-F1 sobre os 3 rótulos, por pergunta e no total, e perdidos da pergunta crítica."""


def macro_f1(gold, pred, n=3):
    """Média do F1 dos rótulos presentes no gabarito ou na previsão (ausente dos dois não conta)."""
    f1s = []
    for c in range(n):
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        if tp + fp + fn:
            f1s.append(2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s) if f1s else 1.0


def resumo(decs, pred, ficha):
    """decs: decisões com 'pergunta' e 'gold' (índice); pred: índices previstos."""
    rot = ficha['rotulos']
    critica = ficha['rede']['pergunta']
    sim, nao = rot.index('sim'), rot.index('nao')
    gold = [d['gold'] for d in decs]
    out = {'decisoes': len(decs),
           'acuracia': round(sum(g == p for g, p in zip(gold, pred)) / len(decs), 4),
           'macro_f1': round(macro_f1(gold, pred), 4),
           f'{critica}_perdidos': sum(d['pergunta'] == critica and d['gold'] == sim and p == nao
                                      for d, p in zip(decs, pred)),
           f'{critica}_sim_total': sum(d['pergunta'] == critica and d['gold'] == sim for d in decs),
           'por_pergunta': {}}
    for q in ficha['perguntas']:
        idx = [i for i, d in enumerate(decs) if d['pergunta'] == q['id']]
        g, p = [gold[i] for i in idx], [pred[i] for i in idx]
        out['por_pergunta'][q['id']] = {'macro_f1': round(macro_f1(g, p), 4),
                                        'acuracia': round(sum(a == b for a, b in zip(g, p)) / len(idx), 4),
                                        'gold_por_rotulo': {r: g.count(i) for i, r in enumerate(rot)}}
    return out
