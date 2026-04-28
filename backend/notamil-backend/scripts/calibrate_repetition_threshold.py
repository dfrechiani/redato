#!/usr/bin/env python3
"""
calibrate_repetition_threshold.py

Roda o detector de repetição lexical (lexical_repetition_detector.py) contra:
- Os 11 canários do calibration set v2 (docs/redato/v2/canarios.yaml)
- 5 textos sintéticos com ground truth conhecido

Faz grid search no espaço (min_occurrences × ttr_max_for_suppress) e
sugere a configuração ótima por F1.

USO:
    cd backend/notamil-backend
    python -m redato_backend.scripts.calibrate_repetition_threshold

Ou ajuste os paths via flags:
    python redato_backend/scripts/calibrate_repetition_threshold.py \\
        --canarios docs/redato/v2/canarios.yaml \\
        --output scripts/ab_tests/threshold_calibration.json

DEPENDÊNCIAS:
    pip install pyyaml
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Ajuste o import conforme a estrutura final no repo:
# Se o detector está em backend/notamil-backend/redato_backend/audits/, então:
#     from redato_backend.audits.lexical_repetition_detector import detect_lexical_repetition
# Caso fique em scripts/audits/:
#     from audits.lexical_repetition_detector import detect_lexical_repetition
# Para este script funcionar standalone, espera-se o arquivo em mesmo dir
# OU em PYTHONPATH.
try:
    from redato_backend.audits.lexical_repetition_detector import detect_lexical_repetition  # type: ignore
except ImportError:
    from lexical_repetition_detector import detect_lexical_repetition  # type: ignore


# ──────────────────────────────────────────────────────────────────────
# CONJUNTO SINTÉTICO COM GROUND TRUTH
# ──────────────────────────────────────────────────────────────────────

SYNTHETIC_TEXTS = [
    {
        'id': 'synth_low_rep',
        'expected_flag': False,
        'reason': 'Diversidade lexical alta, sem repetição estrutural',
        'text': """A exclusão digital no Brasil revela um problema multifacetado. Famílias
em regiões periféricas enfrentam barreiras econômicas concretas. Estudantes
sem acesso à rede ficam alijados de oportunidades educacionais que hoje
circulam primordialmente online. Trabalhadores informais perdem visibilidade
em mercados que migraram para plataformas digitais. Cabe ao Estado articular
políticas que combinem infraestrutura, capacitação e fomento — caminhos
distintos, mas convergentes na superação dessa fratura."""
    },
    {
        'id': 'synth_obvious_rep',
        'expected_flag': True,
        'reason': 'Repetição evidente do termo "exclusão" e "internet" em todas as frases',
        'text': """A exclusão digital é um problema. A exclusão atinge muitas pessoas. A
exclusão é causada por falta de internet. Sem internet, as pessoas ficam
excluídas. A internet é importante. A internet melhora a vida. Sem internet,
a exclusão aumenta. A exclusão precisa acabar. O governo deve combater a
exclusão. A internet deve chegar a todos."""
    },
    {
        'id': 'synth_borderline',
        'expected_flag': True,
        'reason': '"redes sociais" 3x espalhadas — borderline mas qualifica por spread',
        'text': """Os jovens brasileiros enfrentam uma crise de saúde mental. As redes sociais
contribuem para o problema através da comparação constante. Estudos mostram
que adolescentes passam horas conectados, o que afeta a qualidade do sono.
Já no plano educativo, escolas começam a discutir letramento midiático. A
pressão por desempenho acadêmico se soma à influência das redes sociais,
formando um cenário desafiador. Por fim, intervenções em rede social na
adolescência se mostram urgentes."""
    },
    {
        'id': 'synth_high_ttr_no_flag',
        'expected_flag': False,
        'reason': 'Texto longo com vocabulário diversificado, TTR alto',
        'text': """A precarização do trabalho contemporâneo manifesta-se em múltiplas dimensões.
Plataformas digitais reorganizaram a economia urbana, transformando entregadores
e motoristas em empreendedores compulsórios sem proteção previdenciária.
Sociólogos como Ricardo Antunes denominam esse fenômeno de uberização —
extensão da lógica algorítmica para vínculos antes formalizados. Concomitantemente,
profissionais de áreas tradicionais enfrentam reconfigurações: jornalistas
disputam espaço com criadores de conteúdo, professores convivem com tutores
automatizados, médicos atendem por telemedicina. Essa metamorfose laboral
exige resposta política: regulação específica, proteção mínima, fomento à
sindicalização nos novos arranjos."""
    },
    {
        'id': 'synth_short_rep',
        'expected_flag': True,
        'reason': 'Texto curto mas com repetição saturada de "violência"',
        'text': """A violência contra a mulher é um problema grave. Existem muitos tipos de
violência, e a violência doméstica é o pior. A violência precisa ser combatida.
Mulheres sofrem violência todos os dias. A violência atinge mulheres pobres
e ricas. Toda forma de violência merece punição."""
    },
]


# ──────────────────────────────────────────────────────────────────────
# CARREGA CANÁRIOS DO REPO
# ──────────────────────────────────────────────────────────────────────

def load_canarios(path: Path) -> list[dict]:
    """
    Carrega canarios.yaml v2 e infere ground truth de repetição.
    
    Heurística: repetição esperada quando:
    - Canário tem `c4` ≤ 120 no gabarito (coesão baixa = candidato a repetição)
    - OU tem `structural_check` mencionando 'repetition' / 'mechanical' / 'most_used_connector'
    
    Retorna lista de dicts no formato comum com SYNTHETIC_TEXTS.
    """
    try:
        import yaml
    except ImportError:
        print("ERRO: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    if not path.exists():
        print(f"AVISO: {path} não encontrado — rodando só com synthetic set", file=sys.stderr)
        return []

    with open(path) as f:
        data = yaml.safe_load(f)

    canarios = []
    for c in data.get('canarios', []):
        gabarito = c.get('gabarito', {})
        c4 = gabarito.get('c4', 200)
        
        # Heurística automática para ground truth
        expected = False
        reason_bits = [f"gabarito C4={c4}"]
        
        if c4 <= 120:
            expected = True
            reason_bits.append("C4 baixo")
        
        # Verifica structural_checks
        for check in c.get('structural_checks', []):
            kind = check.get('kind', '')
            if 'mechanical_repetition' in kind or 'most_used_connector' in kind:
                expected = True
                reason_bits.append(f"check:{kind}")
        
        # Override manual via campo opcional
        if 'expected_repetition_flag' in c:
            expected = bool(c['expected_repetition_flag'])
            reason_bits.append("override manual")

        canarios.append({
            'id': c['id'],
            'text': c.get('essay', ''),
            'expected_flag': expected,
            'reason': ' · '.join(reason_bits),
            'source': 'canary',
        })

    return canarios


# ──────────────────────────────────────────────────────────────────────
# AVALIAÇÃO COM GRID SEARCH
# ──────────────────────────────────────────────────────────────────────

def run_detection(text: str, min_occurrences: int, ttr_max: Optional[float]) -> bool:
    """Roda detector com config específica e retorna o flag final."""
    report = detect_lexical_repetition(
        text,
        min_occurrences=min_occurrences,
        suppress_above_ttr=ttr_max,
    )
    return report.has_significant_repetition


def evaluate_config(items: list[dict], min_occ: int, ttr_max: Optional[float]) -> dict:
    """Avalia uma config e retorna métricas."""
    tp = fp = tn = fn = 0
    detail = []
    for item in items:
        flag = run_detection(item['text'], min_occ, ttr_max)
        expected = item['expected_flag']
        if flag and expected:
            tp += 1; outcome = 'TP'
        elif flag and not expected:
            fp += 1; outcome = 'FP'
        elif not flag and not expected:
            tn += 1; outcome = 'TN'
        else:
            fn += 1; outcome = 'FN'
        detail.append({'id': item['id'], 'expected': expected, 'flag': flag, 'outcome': outcome})

    n = max(tp + fp + tn + fn, 1)
    precision = tp / max(tp + fp, 1) if (tp + fp) > 0 else 0
    recall = tp / max(tp + fn, 1) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / max(precision + recall, 0.001)

    return {
        'min_occurrences': min_occ,
        'ttr_max_for_suppress': ttr_max,
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'precision': round(precision, 3),
        'recall': round(recall, 3),
        'f1': round(f1, 3),
        'flagged_rate': round((tp + fp) / n, 3),
        'detail': detail,
    }


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Calibra detector de repetição lexical')
    parser.add_argument(
        '--canarios', type=str,
        default='docs/redato/v2/canarios.yaml',
        help='Path para canarios.yaml v2'
    )
    parser.add_argument(
        '--output', type=str,
        default='scripts/ab_tests/threshold_calibration.json',
        help='Path de saída do JSON com resultados'
    )
    args = parser.parse_args()

    canary_set = load_canarios(Path(args.canarios))
    full_set = canary_set + [{**s, 'source': 'synthetic'} for s in SYNTHETIC_TEXTS]

    print(f"\n{'='*78}")
    print(f"  CALIBRAÇÃO DO LIMIAR DE REPETIÇÃO LEXICAL")
    print(f"{'='*78}")
    print(f"  Total: {len(full_set)} textos ({len(canary_set)} canários + {len(SYNTHETIC_TEXTS)} sintéticos)\n")

    # Detecções com config default — só pra mostrar
    print(f"{'─'*78}")
    print(f"  DETECÇÕES COM CONFIG DEFAULT (min_occ=4, ttr_max=None)")
    print(f"{'─'*78}")
    print(f"  {'ID':<32} {'src':<10} {'esperado':<10} {'flag':<6} {'top×':>6} {'TTR':>6}")
    print(f"  {'─'*76}")
    for item in full_set:
        report = detect_lexical_repetition(item['text'])
        exp = '🔴 sim' if item['expected_flag'] else '⚪ não'
        flag = '🔴 sim' if report.has_significant_repetition else '⚪ não'
        print(f"  {item['id']:<32} {item['source']:<10} {exp:<10} {flag:<6} "
              f"{report.most_repeated_count:>5}× {report.type_token_ratio:>6.3f}")

    # Grid search
    print(f"\n{'─'*78}")
    print(f"  GRID SEARCH")
    print(f"{'─'*78}")

    grid = []
    for min_occ in [3, 4, 5, 6]:
        for ttr in [None, 0.55, 0.50, 0.45, 0.40]:
            grid.append(evaluate_config(full_set, min_occ, ttr))

    grid.sort(key=lambda r: (-r['f1'], r['flagged_rate']))

    print(f"  {'min_occ':<8} {'ttr_max':<10} {'TP':<4} {'FP':<4} {'TN':<4} {'FN':<4} "
          f"{'P':>6} {'R':>6} {'F1':>6} {'flag%':>7}")
    print(f"  {'─'*72}")
    for r in grid[:15]:
        ttr = f"{r['ttr_max_for_suppress']}" if r['ttr_max_for_suppress'] else 'none'
        print(f"  {r['min_occurrences']:<8} {ttr:<10} {r['tp']:<4} {r['fp']:<4} "
              f"{r['tn']:<4} {r['fn']:<4} {r['precision']:>6.3f} {r['recall']:>6.3f} "
              f"{r['f1']:>6.3f} {r['flagged_rate']*100:>6.1f}%")

    # Recomendação
    best = grid[0]
    print(f"\n{'='*78}")
    print(f"  RECOMENDAÇÃO")
    print(f"{'='*78}")
    print(f"  Melhor config por F1: min_occurrences={best['min_occurrences']}, "
          f"ttr_max_for_suppress={best['ttr_max_for_suppress']}")
    print(f"    Precision: {best['precision']:.3f}")
    print(f"    Recall:    {best['recall']:.3f}")
    print(f"    F1:        {best['f1']:.3f}")
    print(f"    % flagados: {best['flagged_rate']*100:.1f}%\n")

    print(f"  Em lexical_repetition_detector.py, ajustar:")
    print(f"      DEFAULT_MIN_OCCURRENCES = {best['min_occurrences']}")
    if best['ttr_max_for_suppress'] is not None:
        print(f"      SUPPRESS_FLAG_IF_TTR_ABOVE = {best['ttr_max_for_suppress']}")
    else:
        print(f"      SUPPRESS_FLAG_IF_TTR_ABOVE = None")

    # Casos onde a recomendação errou (falsos positivos / negativos)
    errors = [d for d in best['detail'] if d['outcome'] in ('FP', 'FN')]
    if errors:
        print(f"\n  Erros remanescentes na config recomendada:")
        for err in errors:
            print(f"    [{err['outcome']}] {err['id']}: esperado={err['expected']}, flag={err['flag']}")
    else:
        print(f"\n  ✓ Sem erros na config recomendada — F1 perfeito no test set.")

    # Salva
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Limpa detail dos itens não-best pra reduzir tamanho
        for r in grid:
            if r is not best:
                r.pop('detail', None)
        with open(out_path, 'w') as f:
            json.dump({
                'best_config': best,
                'grid_search': grid,
                'test_set_size': len(full_set),
                'canary_count': len(canary_set),
                'synthetic_count': len(SYNTHETIC_TEXTS),
            }, f, indent=2, ensure_ascii=False)
        print(f"\n  Resultados salvos em {out_path}")
    print()


if __name__ == '__main__':
    main()
