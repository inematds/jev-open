"""Leitor NLI genérico. Serialização única, usada por todas as etapas.

Dois modos de pontuação:
- 'hipoteses': uma frase autocontida por rótulo; vence a de maior log P(entailment).
  Funciona com modelos NLI binários (entailment/not_entailment) e de 3 classes.
- 'unica': uma afirmação por pergunta; entailment=sim, contradiction=nao, neutral=incerto.
  Só existe para modelos NLI de 3 classes.
Os índices dos rótulos NLI vêm de config.id2label, nunca fixos no código.
"""
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def pick_device():
    if torch.cuda.is_available():
        return 'cuda'
    if torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'


def premise(texto):
    # As hipóteses carregam a pergunta; a premissa é só o documento.
    return texto


class NLIReader:
    def __init__(self, model_id, revision, device=None, max_length=1024):
        self.model_id, self.revision = model_id, revision
        self.device = device or pick_device()
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_id, revision=revision, dtype=torch.float32).to(self.device).eval()
        self.max_length = max_length
        labels = {i: l.lower() for i, l in self.model.config.id2label.items()}
        find = lambda key: next((i for i, l in labels.items() if l.startswith(key)), None)
        self.entail = find('entail')
        if self.entail is None:
            raise ValueError(f'{model_id}: sem rótulo entailment em {labels}')
        self.contra, self.neutral = find('contradiction'), find('neutral')
        self.three_way = self.contra is not None and self.neutral is not None
        self.nli_labels = labels

    def _logprobs(self, pairs):
        enc = self.tokenizer([p for p, _ in pairs], [h for _, h in pairs],
                             padding=True, truncation=False, return_tensors='pt')
        if enc['input_ids'].shape[1] > self.max_length:
            raise ValueError(f"entrada com {enc['input_ids'].shape[1]} tokens > {self.max_length}; sem truncar em silêncio")
        with torch.no_grad():
            z = self.model(**{k: v.to(self.device) for k, v in enc.items()}).logits.float()
        return z.log_softmax(-1).cpu()

    def hipoteses(self, texto, hipoteses_por_rotulo, rotulos):
        """Retorna probabilidades sobre `rotulos` (softmax dos log P(entailment))."""
        pairs = [(premise(texto), hipoteses_por_rotulo[r]) for r in rotulos]
        lp = self._logprobs(pairs)[:, self.entail]
        return lp.softmax(-1).tolist()

    def unica(self, texto, afirmacao):
        """Retorna probabilidades [sim, nao, incerto] a partir de uma afirmação."""
        if not self.three_way:
            raise ValueError(f'{self.model_id} não é NLI de 3 classes; use o modo hipoteses')
        p = self._logprobs([(premise(texto), afirmacao)])[0].exp()
        return [float(p[self.entail]), float(p[self.contra]), float(p[self.neutral])]
