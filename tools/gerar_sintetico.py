"""Fase 2 (protótipo): gera mensagens SINTÉTICAS com um LLM local (Ollama), a partir da ficha.

O rótulo de cada pergunta é o ALVO pedido ao gerador, não uma anotação humana.
Um segundo LLM local confere cada rótulo; só ficam os registros em que os dois concordam.
Isso é revisão por IA, não validação humana: tudo sai com sintetico=true e a fonte registrada.

uso: uv run python tools/gerar_sintetico.py <tarefa> <saida.jsonl> --n 300 --gerador qwen3.6:35b-a3b \
        --verificador qwen3:30b --estilo variado --seed 1
"""
import argparse, json, random, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.task import load_ficha

OLLAMA = 'http://127.0.0.1:11434/api/chat'
# Alvo: 0 a 3 perguntas ativas por mensagem (o resto é 'nao'); cada ativa é 'sim' (70%) ou 'incerto' (30%).
K_ATIVAS = {0: .1, 1: .5, 2: .3, 3: .1}
P_ATIVA = {'sim': .7, 'incerto': .3}
ESTILOS = {
    'variado': [
        'WhatsApp informal, frases curtas, pode ter abreviações (vc, pq, tb) e erros de digitação',
        'WhatsApp educado e direto, com saudação',
        'áudio transcrito automaticamente: sem pontuação, repetitivo, oral',
        'mensagem de uma pessoa idosa, formal e um pouco confusa',
        'familiar escrevendo em nome de outra pessoa',
    ],
    'email': [
        'e-mail formal e longo, com assunto na primeira linha, saudação e assinatura',
        'e-mail corporativo de uma empresa ou de um RH, impessoal',
    ],
}


def sorteia_alvo(ficha, rng):
    ids = [q['id'] for q in ficha['perguntas']]
    k = rng.choices(list(K_ATIVAS), weights=list(K_ATIVAS.values()))[0]
    ativas = set(rng.sample(ids, k))
    return {q: rng.choices(list(P_ATIVA), weights=list(P_ATIVA.values()))[0] if q in ativas else 'nao' for q in ids}


def esquema(ficha):
    props = {q['id']: {'type': 'string', 'enum': ficha['rotulos']} for q in ficha['perguntas']}
    return {'type': 'object', 'properties': props, 'required': list(props)}


def chat(modelo, prompt, temperatura, seed, formato='json'):
    body = json.dumps({'model': modelo, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False,
                       'think': False, 'format': formato,
                       'options': {'temperature': temperatura, 'seed': seed, 'num_predict': 600}}).encode()
    req = urllib.request.Request(OLLAMA, body, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(json.loads(r.read())['message']['content'])


def descreve(ficha, alvo):
    linhas = []
    for q in ficha['perguntas']:
        linhas.append(f"- {q['pergunta']} -> {alvo[q['id']].upper()}: {q['significados'][alvo[q['id']]]}")
    return '\n'.join(linhas)


def prompt_gerar(ficha, alvo, estilo):
    return f"""Você escreve dados de TESTE sintéticos, em português do Brasil, para um sistema de triagem.
Contexto: {ficha['entrada']}.
Escreva UMA mensagem realista no estilo: {estilo}.
Invente nomes, datas e detalhes plausíveis (nada de pessoas reais). Não cite estas instruções.
A mensagem precisa satisfazer EXATAMENTE todas as condições abaixo (SIM = a mensagem faz isso;
NAO = a mensagem não faz isso de jeito nenhum; INCERTO = há uma pista ambígua, dá para ler dos dois jeitos):
{descreve(ficha, alvo)}
Responda só com JSON: {{"texto": "<a mensagem>"}}"""


def prompt_verificar(ficha, texto):
    perguntas = '\n'.join(
        f"- {q['id']}: {q['pergunta']} (sim: {q['significados']['sim']}; nao: {q['significados']['nao']}; "
        f"incerto: {q['significados']['incerto']})" for q in ficha['perguntas'])
    return f"""Classifique a mensagem abaixo. Contexto: {ficha['entrada']}.
Para cada pergunta, responda sim, nao ou incerto, seguindo os significados.
{perguntas}

Mensagem:
\"\"\"{texto}\"\"\"

Responda só com o JSON pedido."""


def main():
    p = argparse.ArgumentParser()
    p.add_argument('tarefa'); p.add_argument('saida')
    p.add_argument('--n', type=int, required=True, help='registros aceitos desejados')
    p.add_argument('--gerador', required=True); p.add_argument('--verificador', required=True)
    p.add_argument('--estilo', choices=list(ESTILOS), default='variado')
    p.add_argument('--prefixo', required=True, help='prefixo dos ids, ex.: syn ou ood')
    p.add_argument('--seed', type=int, default=1)
    a = p.parse_args()
    ficha = load_ficha(a.tarefa)
    rng = random.Random(a.seed)
    saida = Path(a.saida)
    feitos = [json.loads(l) for l in saida.read_text().splitlines()] if saida.exists() else []  # retomável
    log = saida.with_suffix('.log.jsonl')
    tentativa = len(feitos) * 2 + int(log.exists() and sum(1 for _ in log.open()))
    rng.seed(a.seed * 100003 + tentativa)
    t0 = time.time()
    with saida.open('a') as out, log.open('a') as lg:
        while len(feitos) < a.n:
            tentativa += 1
            alvo = sorteia_alvo(ficha, rng)
            estilo = rng.choice(ESTILOS[a.estilo])
            try:
                texto = chat(a.gerador, prompt_gerar(ficha, alvo, estilo), .9, a.seed * 1000 + tentativa)['texto'].strip()
                conf = chat(a.verificador, prompt_verificar(ficha, texto), 0, 7, esquema(ficha))
            except Exception as e:  # JSON quebrado ou timeout: registra e segue
                lg.write(json.dumps({'tentativa': tentativa, 'erro': repr(e)[:200]}) + '\n'); lg.flush()
                continue
            divergencias = {q: (alvo[q], conf.get(q)) for q in alvo if conf.get(q) != alvo[q]}
            lg.write(json.dumps({'tentativa': tentativa, 'aceito': not divergencias, 'divergencias': divergencias},
                                ensure_ascii=False) + '\n'); lg.flush()
            if divergencias or not texto:
                continue
            rid = f'{a.prefixo}-{len(feitos) + 1:04d}'
            r = {'id': rid, 'grupo': rid, 'sintetico': True, 'texto': texto, 'respostas': alvo,
                 'fonte': f'sintético: gerado por {a.gerador} (Ollama local), estilo "{estilo}"; rótulo = alvo do gerador, '
                          f'confirmado por {a.verificador} (revisão por IA, não humana)'}
            out.write(json.dumps(r, ensure_ascii=False) + '\n'); out.flush()
            feitos.append(r)
            if len(feitos) % 10 == 0:
                print(f'{len(feitos)}/{a.n} aceitos, {tentativa} tentativas, {time.time() - t0:.0f}s', flush=True)
    print(f'fim: {len(feitos)} aceitos em {tentativa} tentativas')


if __name__ == '__main__':
    main()
