import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import type { AlunoEmRisco } from "@/types/portal";

interface Props {
  /** Necessário pra montar link da evolução. */
  turmaId?: string;
  alunos: AlunoEmRisco[];
  /** Limite visual; null = sem limite. */
  max?: number | null;
  className?: string;
}

function severidadeDe(n: number): "alta" | "media" | "baixa" {
  if (n >= 4) return "alta";
  if (n >= 3) return "media";
  return "baixa";
}

const sevVariant = {
  alta: "warning" as const,
  media: "warning" as const,
  baixa: "neutral" as const,
};

const sevLabel: Record<"alta" | "media" | "baixa", string> = {
  alta: "Alta",
  media: "Média",
  baixa: "Baixa",
};

/**
 * Lista de alunos com ≥ 2 missões abaixo da faixa esperada. Cada item
 * é clicável (vai pra evolução do aluno) se `turmaId` é dado.
 */
export function AlunosEmRiscoCard({
  turmaId, alunos, max = 5, className,
}: Props) {
  const lista = max ? alunos.slice(0, max) : alunos;

  return (
    <ul role="list" className={cn("divide-y divide-border", className)}>
      {lista.map((a) => {
        const sev = severidadeDe(a.n_missoes_baixa);
        const conteudo = (
          <div className="flex items-center justify-between gap-2 py-2.5 px-1">
            <div className="min-w-0">
              <p className="font-medium truncate">{a.nome}</p>
              <p className="text-xs text-ink-400 mt-0.5">
                {a.n_missoes_baixa} missões abaixo
                {a.ultima_nota !== null && (
                  <> · última: <span className="font-mono">{a.ultima_nota}</span></>
                )}
              </p>
            </div>
            <Badge variant={sevVariant[sev]}>{sevLabel[sev]}</Badge>
          </div>
        );
        return (
          <li key={a.aluno_id}>
            {turmaId ? (
              <Link
                href={`/turma/${turmaId}/aluno/${a.aluno_id}/evolucao`}
                className="block hover:bg-muted rounded-lg"
              >
                {conteudo}
              </Link>
            ) : (
              conteudo
            )}
          </li>
        );
      })}
    </ul>
  );
}
