import { cn } from "@/lib/cn";
import type { DistribuicaoNotas, DistribuicaoPorModo } from "@/types/portal";

interface PropsLegacy {
  /** M6 (compat): distribuição flat (Completo). */
  distribuicao: DistribuicaoNotas;
  porModo?: never;
  modo?: never;
  className?: string;
}

interface PropsPorModo {
  porModo: DistribuicaoPorModo;
  /** "foco" usa 0-40..161-200, "completo" usa 0-200..801-1000. */
  modo: "foco" | "completo";
  distribuicao?: never;
  className?: string;
}

type Props = PropsLegacy | PropsPorModo;

const FAIXAS_FOCO: Array<{ key: string; label: string }> = [
  { key: "0-40", label: "0-40" },
  { key: "41-80", label: "41-80" },
  { key: "81-120", label: "81-120" },
  { key: "121-160", label: "121-160" },
  { key: "161-200", label: "161-200" },
];

const FAIXAS_COMPLETO: Array<{ key: string; label: string }> = [
  { key: "0-200", label: "0-200" },
  { key: "201-400", label: "201-400" },
  { key: "401-600", label: "401-600" },
  { key: "601-800", label: "601-800" },
  { key: "801-1000", label: "801-1000" },
];

/**
 * Gráfico de barras horizontal. Aceita dois shapes:
 * - `distribuicao` (legado): map plano (M6 default = completo).
 * - `porModo` + `modo`: M7 com buckets segregados por modo de correção.
 */
export function DistribuicaoNotasChart(props: Props) {
  const { className } = props;
  let dist: Record<string, number>;
  let faixas: typeof FAIXAS_COMPLETO;
  if ("porModo" in props && props.porModo) {
    dist = props.porModo[props.modo!];
    faixas = props.modo === "foco" ? FAIXAS_FOCO : FAIXAS_COMPLETO;
  } else {
    dist = (props as PropsLegacy).distribuicao;
    faixas = FAIXAS_COMPLETO;
  }

  const max = Math.max(1, ...faixas.map((f) => dist[f.key] ?? 0));
  const totalEnvios = faixas.reduce((s, f) => s + (dist[f.key] ?? 0), 0);

  return (
    <div
      className={cn("space-y-2", className)}
      role="img"
      aria-label="Distribuição de notas por faixa"
    >
      {faixas.map((f) => {
        const v = dist[f.key] ?? 0;
        const pct = (v / max) * 100;
        return (
          <div key={f.key} className="flex items-center gap-3">
            <span className="font-mono text-xs text-ink-400 w-20 shrink-0">
              {f.label}
            </span>
            <div className="flex-1 h-6 bg-muted rounded relative overflow-hidden">
              <div
                className={cn(
                  "absolute inset-y-0 left-0 bg-ink rounded",
                  v === 0 && "bg-transparent",
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="font-semibold text-sm w-8 text-right">{v}</span>
          </div>
        );
      })}
      {totalEnvios === 0 && (
        <p className="text-xs text-ink-400 mt-2 text-center">
          Sem envios nesse modo ainda.
        </p>
      )}
      {(dist.sem_nota ?? 0) > 0 && (
        <p className="text-xs text-ink-400 mt-2">
          {dist.sem_nota} envio{dist.sem_nota !== 1 ? "s" : ""} sem nota processada
        </p>
      )}
    </div>
  );
}
