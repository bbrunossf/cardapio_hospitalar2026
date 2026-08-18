"""Log das execuções do motor de otimização (JSON Lines).

Cada execução do PuLP grava UMA linha JSON em
`logs/motor_otimizacao.log` (ou no caminho de MOTOR_LOG_PATH, se definido).
Estrutura pensada para análise: entradas (dieta, overrides, exclusões),
resultado (status, tempo, métricas) e o cardápio gerado (pratos por
refeição/dia).

Exemplo de leitura:
    jq -r 'select(.status == "Optimal") | .ts, .dieta, .tempo_s' logs/motor_otimizacao.log

O log nunca derruba a requisição: qualquer falha de escrita é engolida.
"""
import json
import os
from datetime import datetime

from flask_login import current_user

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "logs", "motor_otimizacao.log")


def _caminho():
    return os.environ.get("MOTOR_LOG_PATH") or DEFAULT_PATH


def registrar(dados: dict) -> None:
    """Grava uma linha JSONL com ts e usuário (nunca levanta exceção)."""
    try:
        linha = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "usuario": current_user.email if current_user.is_authenticated else None,
        }
        linha.update(dados)
        caminho = _caminho()
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def resumo_cardapio(cardapio: list) -> list:
    """Cardápio do solver → versão compacta p/ log (nomes, sem nutrientes)."""
    return [
        {
            "dia": dia["dia"],
            "refeicoes": [
                {
                    "refeicao": ref["refeicao_nome"],
                    "horario": ref.get("horario", ""),
                    "pratos": [p["nome"] for t in ref["tipos"] for p in t["pratos"]],
                }
                for ref in dia["refeicoes"]
            ],
        }
        for dia in cardapio
    ]


# ─── Debug (MOTOR_DEBUG=1) ──────────────────────────────────────────────
def debug_ativo() -> bool:
    """MOTOR_DEBUG=1 ativa artefatos de debug: dump .lp, log do solver CBC,
    nº variáveis/restrições e totais por dia."""
    return os.environ.get("MOTOR_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def caminho_debug(prefixo: str, extensao: str) -> str:
    """Caminho único para artefato de debug em logs/ (ex.: motor_lp_<ts>.lp)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return os.path.join(os.path.dirname(_caminho()), f"motor_{prefixo}_{ts}.{extensao}")


def totais_por_dia(cardapio: list) -> list:
    """Totais por dia com TODOS os nutrientes do motor (debug)."""
    nutrientes = ["energia_kcal", "proteina_g", "carboidrato_g", "lipidios_g",
                  "sodio_mg", "potassio_mg", "fosforo_mg", "calcio_mg", "ferro_mg",
                  "gordura_saturada_g"]
    dias = []
    for dia in cardapio:
        totais = {
            n: round(sum(float(p.get(n, 0) or 0)
                         for rf in dia["refeicoes"]
                         for t in rf["tipos"] for p in t["pratos"]), 1)
            for n in nutrientes
        }
        dias.append({"dia": dia["dia"], **totais})
    return dias
