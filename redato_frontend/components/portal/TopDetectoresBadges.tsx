import { Badge } from "@/components/ui/Badge";

interface Props {
  detectores: Array<{ detector: string; ocorrencias: number }>;
}

/** Limpa nomes técnicos (flag_repeticao_lexical → "repeticao lexical"). */
function humanize(detector: string): string {
  return detector
    .replace(/^(flag|detector|alerta|aviso)_/i, "")
    .replace(/_/g, " ");
}

export function TopDetectoresBadges({ detectores }: Props) {
  if (detectores.length === 0) {
    return (
      <p className="text-sm text-ink-400">
        Nenhum detector pedagógico acionado.
      </p>
    );
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {detectores.map((d) => (
        <li key={d.detector}>
          <Badge variant="warning" className="normal-case tracking-normal text-xs">
            <span>{humanize(d.detector)}</span>
            <span className="ml-1.5 opacity-70">×{d.ocorrencias}</span>
          </Badge>
        </li>
      ))}
    </ul>
  );
}
