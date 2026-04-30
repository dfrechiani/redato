/**
 * Diff visual lado-a-lado entre texto montado e reescrita autoral
 * (Fase 2 passo 7a).
 *
 * Substitui o lado-a-lado simples do Passo 6 por rendering com:
 * - Coluna esquerda (texto montado): trechos REMOVIDOS na reescrita
 *   em vermelho riscado; trechos mantidos neutros
 * - Coluna direita (reescrita autoral): trechos NOVOS em verde
 *   destacado; trechos copiados do montado neutros
 * - Cabeçalho discreto: "Texto autoral: X% · Cópia das cartas: Y%"
 *
 * % autoral é calculado localmente via `pctAutoral(diffs)` —
 * complementar (não substituto) ao `transformacao_cartas` do
 * redato_output. transformacao_cartas é qualitativo (Claude avalia
 * bandas); % autoral é mecânico. Surfacear ambos ajuda professor a
 * detectar divergências (Claude pode achar autoral alto mas só 10%
 * do texto diferir → vale checar).
 *
 * Server Component (não usa state, hooks ou interatividade) — cabe
 * no fluxo do Passo 6 (server-side render).
 */

import { Card } from "@/components/ui/Card";
import { diffByWords, pctAutoral } from "@/lib/diff-words";


interface Props {
  textoMontado: string;
  reescritaTexto: string;
  /** Score 0-100 do redato_output. Se ausente (avaliação pendente),
   *  ainda mostra % autoral mecânico. */
  transformacaoCartas?: number | null;
}


export function ReescritaDiffView({
  textoMontado, reescritaTexto, transformacaoCartas,
}: Props) {
  const diffs = diffByWords(textoMontado, reescritaTexto);
  const pct = pctAutoral(diffs);

  return (
    <section className="space-y-3">
      {/* Cabeçalho — % autoral mecânico + comparação opcional com
          transformação qualitativa do Claude. */}
      <div className="flex items-center justify-between gap-3 px-1">
        <p className="text-sm text-ink-400">
          <span className="font-semibold text-ink">
            Texto autoral: {pct}%
          </span>
          {" · "}
          <span>Cópia das cartas: {100 - pct}%</span>
        </p>
        {pct === 0 && (
          <span
            className="text-xs font-mono uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded"
            title="Reescrita idêntica ao texto montado pelas cartas"
          >
            atenção
          </span>
        )}
        {/* Quando transformação Claude e % mecânico divergem
            substancialmente, mostra ambos discreto pro professor
            decidir. Threshold de 30 é arbitrário — pega divergências
            grosseiras sem ser ruidoso. */}
        {transformacaoCartas != null
          && Math.abs(pct - transformacaoCartas) >= 30 && (
          <span
            className="text-xs text-ink-400 italic"
            title="% mecânico difere da avaliação qualitativa do Claude — vale conferir"
          >
            (avaliação Claude: {transformacaoCartas}/100)
          </span>
        )}
      </div>

      {/* 2 colunas — mesmo grid do Passo 6 pra consistência visual */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Texto montado pelo grupo
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-line font-body">
            {textoMontado ? (
              <DiffSide diffs={diffs} side="left" />
            ) : (
              <span className="text-ink-400 italic">
                (texto montado ainda não disponível)
              </span>
            )}
          </p>
        </Card>
        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Reescrita autoral
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-line font-body">
            <DiffSide diffs={diffs} side="right" />
          </p>
        </Card>
      </div>
    </section>
  );
}


/**
 * Renderiza um lado do diff. Internamente itera os tuples [op, text]
 * e emite spans coloridas:
 *
 * Lado esquerdo (texto montado):
 *   op=-1 (removido na reescrita) → vermelho riscado
 *   op=0  (mantido)               → neutro
 *   op=+1 (novo na reescrita)     → omitido (não existe nesse lado)
 *
 * Lado direito (reescrita):
 *   op=-1 (removido)              → omitido (não existe nesse lado)
 *   op=0  (mantido)               → neutro
 *   op=+1 (autoral novo)          → verde destacado
 *
 * Spans usam React.Fragment com key estável pelo índice — diffs são
 * imutáveis na render (vêm de fetch); ordenação não muda.
 */
function DiffSide({
  diffs, side,
}: {
  diffs: ReturnType<typeof diffByWords>;
  side: "left" | "right";
}) {
  return (
    <>
      {diffs.map(([op, text], i) => {
        if (side === "left" && op === 1) {
          // Adicionado: não aparece na coluna esquerda
          return null;
        }
        if (side === "right" && op === -1) {
          // Removido: não aparece na coluna direita
          return null;
        }
        if (op === 0) {
          // Igual nos 2 lados
          return <span key={i}>{text}</span>;
        }
        if (op === -1) {
          // Removido — vermelho riscado (lado esquerdo)
          return (
            <span
              key={i}
              className="text-red-700 line-through bg-red-50 rounded px-0.5"
            >
              {text}
            </span>
          );
        }
        // op === 1 — adicionado (lado direito)
        return (
          <span
            key={i}
            className="text-green-900 bg-green-100 rounded px-0.5"
          >
            {text}
          </span>
        );
      })}
    </>
  );
}
