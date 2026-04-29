import Link from "next/link";

import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import { formatMissaoLabel } from "@/lib/format";
import type {
  AtividadeDetail, MinideckResumo, PartidaResumo,
} from "@/types/portal";

import { PartidasView } from "./PartidasView";

export const dynamic = "force-dynamic";

interface Props {
  params: { atividade_id: string };
}

/**
 * Tela do professor: lista de partidas do jogo "Redação em Jogo"
 * pra uma atividade. Suporta múltiplos grupos por atividade
 * (decisão G.1.2 do adendo G).
 *
 * Server-side: pré-carrega atividade + partidas + minidecks (3 fetches
 * paralelos), passa pro Client Component renderizar interatividade
 * (modal de cadastro, edição inline, delete).
 */
export default async function PartidasAtividadePage({ params }: Props) {
  const token = getSessionToken();

  // 3 fetches em paralelo: atividade (header context) + partidas
  // existentes + minidecks (pra dropdown do modal de cadastro).
  const [ativ, partidas, minidecks] = await Promise.all([
    fetchBackend<AtividadeDetail>(
      `/portal/atividades/${params.atividade_id}`,
      { bearer: token! },
    ),
    fetchBackend<PartidaResumo[]>(
      `/portal/atividades/${params.atividade_id}/partidas`,
      { bearer: token! },
    ),
    fetchBackend<MinideckResumo[]>(
      `/portal/jogos/minidecks`,
      { bearer: token! },
    ),
  ]);

  return (
    <div className="space-y-6">
      <nav aria-label="breadcrumb" className="text-sm text-ink-400">
        <Link
          href={`/atividade/${params.atividade_id}`}
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pra atividade
        </Link>
      </nav>

      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          {formatMissaoLabel({
            oficina_numero: ativ.oficina_numero,
            titulo: ativ.missao_titulo,
            modo_correcao: ativ.modo_correcao,
          })}
        </p>
        <h1 className="font-display text-3xl mt-1">
          Partidas do jogo
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          {ativ.turma_codigo} · {ativ.escola_nome}
        </p>
      </header>

      <PartidasView
        atividadeId={params.atividade_id}
        alunosDaTurma={ativ.envios.map((e) => ({
          aluno_turma_id: e.aluno_turma_id,
          nome: e.aluno_nome,
        }))}
        initialPartidas={partidas}
        minidecks={minidecks}
      />
    </div>
  );
}
