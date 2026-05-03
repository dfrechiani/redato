import Link from "next/link";

import { PerfilAlunoView } from "./PerfilAlunoView";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AlunoPerfil, TurmaDetail } from "@/types/portal";

export const dynamic = "force-dynamic";

interface Props {
  params: { turma_id: string; aluno_id: string };
}

/**
 * Perfil do aluno na turma (M9.7) — drill-down de
 * `/turma/{turma_id}/alunos cadastrados`. Server component faz fetch
 * paralelo de:
 *   - `/portal/turmas/{turma_id}` — pra mostrar "Voltar pra turma {codigo}"
 *   - `/portal/turmas/{turma_id}/alunos/{aluno_id}/perfil` — dados do drill
 *
 * O view component é client-side porque usa `ReprocessarEnvioButton`
 * (handler de POST) e `EvolucaoChart` (hover state).
 */
export default async function PerfilAlunoPage({ params }: Props) {
  const token = getSessionToken();
  const [turma, perfil] = await Promise.all([
    fetchBackend<TurmaDetail>(`/portal/turmas/${params.turma_id}`, {
      bearer: token!,
    }),
    fetchBackend<AlunoPerfil>(
      `/portal/turmas/${params.turma_id}/alunos/${params.aluno_id}/perfil`,
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
      <PerfilAlunoView
        turmaId={params.turma_id}
        turmaCodigo={turma.codigo}
        perfil={perfil}
      />
    </div>
  );
}
