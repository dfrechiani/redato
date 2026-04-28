import Link from "next/link";

import { HistoricoPdfsList } from "@/components/portal/HistoricoPdfsList";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { TurmaDetail } from "@/types/portal";

export const dynamic = "force-dynamic";

interface Props {
  params: { turma_id: string };
}

export default async function HistoricoTurmaPage({ params }: Props) {
  const token = getSessionToken();
  const turma = await fetchBackend<TurmaDetail>(
    `/portal/turmas/${params.turma_id}`,
    { bearer: token! },
  );
  return (
    <div className="space-y-6">
      <nav aria-label="breadcrumb" className="text-sm text-ink-400">
        <Link
          href={`/turma/${params.turma_id}`}
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pra turma {turma.codigo}
        </Link>
      </nav>
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Turma {turma.codigo}
        </p>
        <h1 className="font-display text-3xl mt-1">Histórico de PDFs</h1>
        <p className="mt-1 text-sm text-ink-400">
          PDFs gerados pra essa turma. Política de retenção: 365 dias.
        </p>
      </header>
      <HistoricoPdfsList escopoId={params.turma_id} />
    </div>
  );
}
