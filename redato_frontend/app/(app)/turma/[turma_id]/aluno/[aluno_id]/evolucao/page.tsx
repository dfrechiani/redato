import Link from "next/link";

import { EvolucaoAlunoView } from "./EvolucaoAlunoView";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AlunoEvolucao, TurmaDetail } from "@/types/portal";

export const dynamic = "force-dynamic";

interface Props {
  params: { turma_id: string; aluno_id: string };
}

export default async function EvolucaoAlunoPage({ params }: Props) {
  const token = getSessionToken();
  const [turma, evolucao] = await Promise.all([
    fetchBackend<TurmaDetail>(`/portal/turmas/${params.turma_id}`, {
      bearer: token!,
    }),
    fetchBackend<AlunoEvolucao>(
      `/portal/turmas/${params.turma_id}/alunos/${params.aluno_id}/evolucao`,
      { bearer: token! },
    ),
  ]);
  return (
    <div>
      <nav aria-label="breadcrumb" className="mb-4 text-sm text-ink-400">
        <Link
          href={`/turma/${params.turma_id}`}
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pra turma {turma.codigo}
        </Link>
      </nav>
      <EvolucaoAlunoView
        turmaId={params.turma_id}
        turmaCodigo={turma.codigo}
        evolucao={evolucao}
      />
    </div>
  );
}
