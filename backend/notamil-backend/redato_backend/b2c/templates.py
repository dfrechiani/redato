"""Templates WhatsApp (Content API) do B2C — FONTE DE VERDADE.

Estes corpos são submetidos à Meta EXATAMENTE como estão aqui. As
mensagens iniciadas pelo negócio (M5/M8/M9) só entregam FORA da janela
de 24h como template pré-aprovado; dentro da janela vão freeform (as
copies de `messages.py`).

A ordem das variáveis `vars` é a fonte: `build_content_variables` monta
o mapa posicional `{"1": ..., "2": ...}` do Twilio A PARTIR dela, então
o código NUNCA monta posição na mão — mata a classe de bug "variável
trocada de posição" (ex.: "Seu acesso à  vence em 2 dias" com
nome_publico vazio).

⚠️ Ao editar um corpo: mantenha os `{{N}}` batendo com `vars` (há teste
que assere isso). Ao submeter na Meta, use `nome_meta` como nome do
template e cole o `body` literal.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


# key interno → (nome na Meta, env do Content SID, ordem das variáveis, corpo)
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "M5": {
        "nome_meta": "redato_m5_assinatura_ativa",
        "sid_env": "TWILIO_CONTENT_SID_M5",
        "vars": ["nome", "nome_publico"],
        "body": (
            "🎉 Sua assinatura {{2}} está ativa! Pode mandar redação sem "
            "limite, {{1}}. Dica: escreve → recebe o diagnóstico → reescreve "
            "em cima do erro → manda de novo. É assim que se chega no 900+."
        ),
    },
    "M8": {
        "nome_meta": "redato_m8_renovacao_falhou",
        "sid_env": "TWILIO_CONTENT_SID_M8",
        "vars": ["nome", "nome_publico", "link_fatura"],
        "body": (
            "Oi {{1}}! Não conseguimos renovar sua assinatura {{2}}. Pra "
            "não parar seu treino, regulariza aqui: {{3}}"
        ),
    },
    "M9": {
        "nome_meta": "redato_m9_acesso_vence",
        "sid_env": "TWILIO_CONTENT_SID_M9",
        "vars": ["nome", "nome_publico", "link_fatura"],
        "body": (
            "Seu acesso à {{2}} vence em 2 dias, {{1}}. Renova aqui pra não "
            "perder o ritmo (e o histórico da sua evolução): {{3}}"
        ),
    },
}


def indices_no_corpo(body: str) -> List[int]:
    """Índices `{{N}}` referenciados no corpo, ordenados e sem repetição."""
    return sorted({int(m) for m in re.findall(r"\{\{\s*(\d+)\s*\}\}", body)})


def build_content_variables(template_key: str,
                            valores: Dict[str, str]) -> Dict[str, str]:
    """Monta o ContentVariables do Twilio (`{"1": ..., "2": ...}`) a partir
    da ORDEM declarada em `vars` — não da ordem que o caller passou. Assim
    a posição é sempre correta.

    `valores` é um dict nome→valor (ex.: {"nome": "Maria",
    "nome_publico": "Correção Luma", "link_fatura": "https://..."}).
    Faltando uma var declarada → KeyError explícito (melhor que mandar
    variável vazia pro aluno)."""
    spec = TEMPLATES[template_key]
    return {
        str(i + 1): str(valores[nome])
        for i, nome in enumerate(spec["vars"])
    }
