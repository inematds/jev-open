"""Rede determinística de palavras-chave de urgência jurídica. Não é modelo.

Só ESCALONA: o resultado entra em OU com o modelo (sim/incerto do modelo OU disparo da rede).
Não trata negação de propósito: um falso alarme custa pouco; uma urgência perdida, muito.
LISTA A VALIDAR PELO ESCRITÓRIO antes de qualquer uso real.
"""
import re
import unicodedata

TERMOS = [
    r'\bpres[oa]\b', r'\bprisao', r'flagrante', r'delegacia', r'mandado', r'oficial de justica',
    r'audiencia (e |eh )?(hoje|amanha)', r'prazo (\w+ )?(vence|acaba|termina) (hoje|amanha)',
    r'\bintimad', r'\bcitad', r'penhora', r'bloque\w* (a |minha |da )?(conta|salario)',
    r'despejo', r'reintegracao de posse', r'medida protetiva', r'violencia', r'agredi', r'ameac',
    r'\bliminar',
]
_RX = re.compile('|'.join(TERMOS))


def normaliza(texto):
    t = unicodedata.normalize('NFKD', texto.lower())
    return ''.join(c for c in t if not unicodedata.combining(c))


def dispara(texto):
    """Retorna a lista de termos encontrados (vazia = não disparou)."""
    return sorted({m.group(0) for m in _RX.finditer(normaliza(texto))})
