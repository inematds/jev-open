"""Inferência em CPU a partir do pacote congelado (ONNX int8 + tokenizer.json). Sem torch.

O contrato (ordem dos rótulos, hipóteses, temperatura, índice de entailment) vem do pacote e é
conferido contra a ficha na carga: se a ficha mudou, o pacote é recusado.
"""
import hashlib, json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


def contrato_ficha(ficha):
    """Hash do que o modelo aprendeu: rótulos + perguntas/hipóteses, nessa ordem."""
    base = {'rotulos': ficha['rotulos'],
            'perguntas': [[q['id'], [q['hipoteses'][r] for r in ficha['rotulos']]] for q in ficha['perguntas']]}
    return hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class TextoLongo(ValueError):
    pass


class OnnxEspecialista:
    def __init__(self, pacote_dir, ficha, threads=2, arquivo='model.int8.onnx'):
        pacote_dir = Path(pacote_dir)
        self.meta = json.loads((pacote_dir / 'pacote.json').read_text())
        if self.meta['contrato_ficha'] != contrato_ficha(ficha):
            raise ValueError('a ficha mudou depois do congelamento: pacote recusado (retreine ou use a ficha congelada)')
        self.ficha = ficha
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(pacote_dir / arquivo), so, providers=['CPUExecutionProvider'])
        self.entradas = {i.name for i in self.sess.get_inputs()}
        self.tok = Tokenizer.from_file(str(pacote_dir / 'tokenizer.json'))
        self.tok.no_truncation()
        self.tok.enable_padding(pad_id=self.meta['pad_id'], pad_token=self.meta['pad_token'])
        self.max_tokens = self.meta['max_tokens']

    def _logits_grupo(self, texto, hipoteses):
        enc = self.tok.encode_batch([(texto, h) for h in hipoteses])
        n = max(len(e.ids) for e in enc)
        if n > self.max_tokens:
            raise TextoLongo(f'{n} tokens > {self.max_tokens}')
        feed = {'input_ids': np.array([e.ids for e in enc], dtype=np.int64),
                'attention_mask': np.array([e.attention_mask for e in enc], dtype=np.int64)}
        feed = {k: v for k, v in feed.items() if k in self.entradas}
        z = self.sess.run(None, feed)[0].astype(np.float64)
        z = z - z.max(-1, keepdims=True)
        logp = z - np.log(np.exp(z).sum(-1, keepdims=True))
        return logp[:, self.meta['entail']]

    def observa(self, texto):
        """-> {pergunta: {'rotulo', 'confianca', 'probs'}} com a temperatura do dev aplicada."""
        rot, t = self.ficha['rotulos'], self.meta['temperatura']
        todas = [h for q in self.ficha['perguntas'] for h in (q['hipoteses'][r] for r in rot)]
        lg = self._logits_grupo(texto, todas).reshape(len(self.ficha['perguntas']), len(rot)) / t
        p = np.exp(lg - lg.max(-1, keepdims=True)); p /= p.sum(-1, keepdims=True)
        out = {}
        for q, pr in zip(self.ficha['perguntas'], p):
            i = int(pr.argmax())
            out[q['id']] = {'rotulo': rot[i], 'confianca': round(float(pr[i]), 4), 'probs': [round(float(x), 4) for x in pr]}
        return out
