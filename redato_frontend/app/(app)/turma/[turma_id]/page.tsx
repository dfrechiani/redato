import Link from "next/link";

import { TurmaDetailView } from "./TurmaDetailView";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { TurmaDetail } from "@/types/portal";

export const dynamic = "force-dynamic";

interface Props {
  params: { turma_id: string };
}

export default async function TurmaPage({ params }: Props) {
  const token = getSessionToken();
  const data = await fetchBackend<TurmaDetail>(
    `/portal/turmas/${params.turma_id}`,
    { bearer: token! },
  );
  return (
    <div>
      <nav aria-label="breadcrumb" className="mb-4 text-sm text-ink-400">
        <Link href="/" className="hover:text-ink underline-offset-4 hover:underline">
          ← Voltar pra início
        </Link>
      </nav>
      <TurmaDetailView initial={data} />
    </div>
  );
}
