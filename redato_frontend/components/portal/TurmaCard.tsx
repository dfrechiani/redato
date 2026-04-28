import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { formatSerie } from "@/lib/format";
import type { TurmaListItem } from "@/types/portal";

interface Props {
  turma: TurmaListItem;
  showProfessor?: boolean;
}

export function TurmaCard({ turma, showProfessor = false }: Props) {
  return (
    <Link
      href={`/turma/${turma.id}`}
      className="group block bg-white border border-border rounded-xl p-5 shadow-card hover:border-ink-400 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            {formatSerie(turma.serie)} · {turma.ano_letivo}
          </p>
          <h3 className="font-display text-2xl mt-0.5 group-hover:underline underline-offset-4">
            {turma.codigo}
          </h3>
          {showProfessor && (
            <p className="text-xs text-ink-400 mt-0.5 truncate">
              {turma.professor_nome}
            </p>
          )}
        </div>
        {turma.n_atividades_ativas > 0 && (
          <Badge variant="ativa">
            {turma.n_atividades_ativas} ativa{turma.n_atividades_ativas !== 1 ? "s" : ""}
          </Badge>
        )}
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-xs">
        <div>
          <dt className="text-ink-400">Alunos</dt>
          <dd className="text-ink font-semibold text-base">{turma.n_alunos}</dd>
        </div>
        <div>
          <dt className="text-ink-400">Em curso</dt>
          <dd className="text-ink font-semibold text-base">
            {turma.n_atividades_ativas}
          </dd>
        </div>
        <div>
          <dt className="text-ink-400">Encerradas</dt>
          <dd className="text-ink font-semibold text-base">
            {turma.n_atividades_encerradas}
          </dd>
        </div>
      </dl>
    </Link>
  );
}
