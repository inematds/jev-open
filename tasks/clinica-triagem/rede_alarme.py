"""Rede determinística de palavras-chave de alarme. Não é modelo.

Só ESCALONA: o resultado entra em OU com o modelo (sim/incerto do modelo OU disparo da rede).
Não trata negação de propósito: um falso alarme custa pouco; um alarme perdido, muito.
LISTA A VALIDAR POR PROFISSIONAL DE SAÚDE antes de qualquer uso real.
"""
import re
import unicodedata

TERMOS = [
    r'dor no peito', r'aperto no peito', r'falta de ar', r'sem ar\b', r'nao consigo respirar',
    r'desmai', r'convuls', r'sangra\w* (muito|forte|sem parar)', r'hemorragia',
    r'boca torta', r'fala enrolada', r'nao mexe (o|a) (braco|perna|lado)', r'formigamento de um lado',
    r'me matar', r'suicid', r'me machucar', r'tirar minha vida', r'nao quero mais viver',
    r'febre alta', r'bebe (roxo|mole)', r'\bengoliu', r'intoxica',
]
_RX = re.compile('|'.join(TERMOS))


def normaliza(texto):
    t = unicodedata.normalize('NFKD', texto.lower())
    return ''.join(c for c in t if not unicodedata.combining(c))


def dispara(texto):
    """Retorna a lista de termos encontrados (vazia = não disparou)."""
    return sorted({m.group(0) for m in _RX.finditer(normaliza(texto))})
