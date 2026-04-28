import Link from "next/link";

import { AtividadeDetailView } from "./AtividadeDetailView";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AtividadeDetail } from "@/types/portal";

export const dynamic = "force-dynamic";

interface Props {
  params: { atividade_id: string };
}

export default async function AtividadePage({ params }: Props) {
  const token = getSessionToken();
  const data = await fetchBackend<AtividadeDetail>(
    `/portal/atividades/${params.atividade_id}`,
    { bearer: token! },
  );
  return (
    <div>
      <nav aria-label="breadcrumb" className="mb-4 text-sm text-ink-400">
        <Link
          href={`/turma/${data.turma_id}`}
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pra turma {data.turma_codigo}
        </Link>
      </nav>
      <AtividadeDetailView initial={data} />
    </div>
  );
}
