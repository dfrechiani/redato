import Link from "next/link";

import { cn } from "@/lib/cn";
import type { ComparacaoTurma } from "@/types/portal";

interface Props {
  turmas: ComparacaoTurma[];
  yMax?: number; // default 1000
  className?: string;
}

/**
 * Bar chart horizontal: cada turma é uma barra com a média geral
 * sobreposta ao eixo. Sem dependência de Recharts.
 */
export function ComparacaoTurmasChart({
  turmas, yMax = 1000, className,
}: Props) {
  if (turmas.length === 0) {
    return (
      <p className="text-sm text-ink-400">
        Esta comparação aparece quando há ≥ 2 turmas com dados.
      </p>
    );
  }

  return (
    <ul className={cn("space-y-3", className)}>
      {turmas.map((t) => {
        const pct = Math.max(0, Math.min(100, (t.media / yMax) * 100));
        return (
          <li key={t.turma_id}>
            <Link
              href={`/turma/${t.turma_id}`}
              className="block group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-display text-sm group-hover:underline underline-offset-4">
                  {t.turma_codigo}
                </span>
                <span className="font-mono text-xs">
                  <span className="font-semibold">{t.media}</span>
                  <span className="text-ink-400">/{yMax}</span>
                  <span className="text-ink-400 ml-2">
                    ({t.n_envios} envio{t.n_envios !== 1 ? "s" : ""})
                  </span>
                </span>
              </div>
              <div className="h-3 bg-muted rounded overflow-hidden">
                <div
                  className="h-full bg-ink rounded group-hover:bg-lime group-hover:transition-colors"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
