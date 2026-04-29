import Link from "next/link";

import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { ReescritaDetail } from "@/types/portal";

import { ReescritaDetailView } from "./ReescritaDetailView";

export const dynamic = "force-dynamic";

interface Props {
  params: {
    atividade_id: string;
    partida_id: string;
    aluno_id: string;
  };
}

/**
 * Tela do professor: detalhe da reescrita individual de um aluno
 * (Fase 2 passo 6). Renderiza:
 * - Cabeçalho com aluno + atividade + grupo + tema
 * - Banner DH se flag desrespeito_direitos_humanos=true
 * - Lado-a-lado texto montado vs reescrita autoral
 * - Notas ENEM por competência + total + badge transformação
 * - Lista de cartas escolhidas + sugestões pedagógicas (se houver)
 * - Análise da redação (feedback_professor: 4 blocos M9.4)
 *
 * Server-side fetch via portal-client (proxy /api/portal/...). Erros
 * 404 (aluno sem reescrita) ou 403 (sem permissão) bubblam pro
 * error.tsx do Next.js.
 */
export default async function ReescritaPage({ params }: Props) {
  const token = getSessionToken();
  const data = await fetchBackend<ReescritaDetail>(
    `/portal/partidas/${params.partida_id}` +
      `/reescritas/${params.aluno_id}`,
    { bearer: token! },
  );

  return (
    <div className="space-y-6">
      <nav aria-label="breadcrumb" className="text-sm text-ink-400">
        <Link
          href={`/atividade/${params.atividade_id}/partidas`}
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pra partidas
        </Link>
      </nav>
      <ReescritaDetailView data={data} />
    </div>
  );
}
