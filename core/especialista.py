"""Especialista treinável: leitor NLI no modo 'hipoteses' com pontuação diferenciável.

Cada decisão (texto, pergunta) vira 3 pares (texto, hipótese do rótulo); a pontuação de cada rótulo
é o log P(entailment) do par, e o softmax sobre os 3 dá a distribuição. O treino ajusta só as
últimas camadas do encoder e a cabeça. A temperatura é calibrada no dev depois do treino.
"""
import math
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from core.model import pick_device, premise


def decisoes(records, ficha):
    """Achata registros em decisões: uma por (registro, pergunta)."""
    out = []
    for r in records:
        for q in ficha['perguntas']:
            out.append({'id': r['id'], 'pergunta': q['id'], 'texto': r['texto'],
                        'hipoteses': [q['hipoteses'][l] for l in ficha['rotulos']],
                        'gold': ficha['rotulos'].index(r['respostas'][q['id']])})
    return out


def _camadas(model):
    base = model.base_model
    for caminho in ('encoder.layer', 'layers', 'encoder.layers'):
        m = base
        try:
            for parte in caminho.split('.'):
                m = getattr(m, parte)
            return m
        except AttributeError:
            continue
    raise ValueError(f'não achei as camadas do encoder em {type(base).__name__}')


class Especialista(torch.nn.Module):
    def __init__(self, model_id, revision, device=None, max_length=1024):
        super().__init__()
        self.model_id, self.revision = model_id, revision
        self.device = device or pick_device()
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_id, revision=revision, dtype=torch.float32)
        labels = {i: l.lower() for i, l in self.model.config.id2label.items()}
        self.entail = next(i for i, l in labels.items() if l.startswith('entail'))
        self.max_length = max_length
        self.temperatura = 1.0
        self.to(self.device)

    def congela(self, n_topo):
        """Treina só as últimas `n_topo` camadas do encoder e a cabeça de classificação."""
        for p in self.model.parameters():
            p.requires_grad = False
        for camada in list(_camadas(self.model))[-n_topo:]:
            for p in camada.parameters():
                p.requires_grad = True
        for nome, p in self.model.named_parameters():
            if nome.startswith(('classifier', 'head', 'pooler')):
                p.requires_grad = True
        return [p for p in self.model.parameters() if p.requires_grad]

    def pontua(self, lote):
        """lote: lista de decisões -> tensor [B, 3] de log P(entailment) por rótulo (sem temperatura)."""
        pares = [(premise(d['texto']), h) for d in lote for h in d['hipoteses']]
        enc = self.tokenizer([p for p, _ in pares], [h for _, h in pares],
                             padding=True, truncation=False, return_tensors='pt')
        if enc['input_ids'].shape[1] > self.max_length:
            raise ValueError(f"entrada com {enc['input_ids'].shape[1]} tokens > {self.max_length}; sem truncar em silêncio")
        z = self.model(**{k: v.to(self.device) for k, v in enc.items()}).logits.float()
        return z.log_softmax(-1)[:, self.entail].view(len(lote), -1)

    @torch.no_grad()
    def prediz(self, decs, lote=16):
        """Retorna logits de grupo [N, 3] (antes da temperatura)."""
        self.eval()
        return torch.cat([self.pontua(decs[i:i + lote]).cpu() for i in range(0, len(decs), lote)])

    def calibra(self, logits, gold):
        """Temperatura escalar que minimiza a NLL no dev (busca em grade, sem otimizador)."""
        y = torch.tensor(gold)
        melhor = min((torch.nn.functional.cross_entropy(logits / t, y).item(), t)
                     for t in [math.exp(x / 20) for x in range(-40, 61)])
        self.temperatura = melhor[1]
        return {'temperatura': round(melhor[1], 4), 'nll_dev': round(melhor[0], 4),
                'nll_dev_t1': round(torch.nn.functional.cross_entropy(logits, y).item(), 4)}
