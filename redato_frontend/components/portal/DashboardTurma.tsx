"use client";

import { useEffect, useMemo, useState } from "react";

import { AlunosEmRiscoCard } from "@/components/portal/AlunosEmRiscoCard";
import { DistribuicaoNotasChart } from "@/components/portal/DistribuicaoNotasChart";
import { EmptyDashboardCard } from "@/components/portal/EmptyDashboardCard";
import { EvolucaoChart } from "@/components/portal/EvolucaoChart";
import { ExportarPdfModal } from "@/components/portal/ExportarPdfModal";
import { ToggleModo, type ModoFiltro } from "@/components/portal/ToggleModo";
import { TopDetectoresBadges } from "@/components/portal/TopDetectoresBadges";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { dashboardTurma, gerarPdfDashboardTurma } from "@/lib/portal-client";
import { ApiError } from "@/types/api";
import type { TurmaDashboard } from "@/types/portal";

interface Props {
  turmaId: string;
}

const MIN_EVOLUCAO = 3;

export function DashboardTurma({ turmaId }: Props) {
  const [data, setData] = useState<TurmaDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modo, setModo] = useState<ModoFiltro>("todos");
  const [pdfOpen, setPdfOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    dashboardTurma(turmaId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((err) => { if (!cancelled) setError((err as ApiError).detail); });
    return () => { cancelled = true; };
  }, [turmaId]);

  const evolucaoFiltrada = useMemo(() => {
    if (!data) return [];
    if (modo === "todos") return data.evolucao_turma;
    return data.evolucao_turma.filter((p) => {
      const isFoco = p.modo?.startsWith("foco_");
      return modo === "foco" ? isFoco : !isFoco;
    });
  }, [data, modo]);

  const yMaxEvolucao = modo === "foco" ? 200
    : modo === "completo" ? 1000
    : 1000; // default 1000 pra "todos" (foco será visualmente baixo, ok)

  if (error) {
    return (
      <Card className="text-sm text-danger">
        Erro ao carregar dashboard: {error}
      </Card>
    );
  }
  if (!data) {
    return (
      <Card className="flex items-center justify-center gap-3 py-10">
        <LoadingSpinner size={20} />
        <span className="text-sm text-ink-400">Carregando dashboard…</span>
      </Card>
    );
  }

  const semEnvios = data.n_envios_total === 0;
  const naoQualificaEvolucao = evolucaoFiltrada.length < MIN_EVOLUCAO;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            Resumo
          </p>
          <p className="text-sm text-ink mt-1">
            <span className="font-semibold">{data.n_envios_total}</span>{" "}
            envio{data.n_envios_total !== 1 ? "s" : ""} ·{" "}
            <span className="font-semibold">{data.atividades_ativas}</span>{" "}
            atividade{data.atividades_ativas !== 1 ? "s" : ""} ativa
            {data.atividades_ativas !== 1 ? "s" : ""} ·{" "}
            <span className="font-semibold">{data.atividades_encerradas}</span>{" "}
            encerrada{data.atividades_encerradas !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <ToggleModo value={modo} onChange={setModo} />
          <Button variant="ghost" onClick={() => setPdfOpen(true)}>
            Exportar PDF
          </Button>
          <a
            href={`/turma/${turmaId}/historico-pdfs`}
            className="text-xs text-ink-400 hover:text-ink underline-offset-4 hover:underline px-2"
          >
            Histórico
          </a>
        </div>
      </div>
      <ExportarPdfModal
        open={pdfOpen}
        onClose={() => setPdfOpen(false)}
        title="Exportar dashboard da turma"
        description="O PDF inclui distribuição, top detectores, alunos em risco e evolução."
        onGerar={(p) => gerarPdfDashboardTurma(turmaId, p)}
      />

      {semEnvios ? (
        <EmptyDashboardCard
          title="Sem envios ainda"
          description="Quando os alunos começarem a mandar redações, o dashboard mostra distribuição, detectores e progresso aqui."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <div className="flex items-baseline justify-between mb-3">
                <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
                  Distribuição de notas
                </p>
                <p className="font-mono text-xs text-ink-400">
                  {modo === "todos" ? "completo + foco" : modo}
                </p>
              </div>
              {modo === "foco" ? (
                <DistribuicaoNotasChart porModo={data.distribuicao_notas} modo="foco" />
              ) : modo === "completo" ? (
                <DistribuicaoNotasChart porModo={data.distribuicao_notas} modo="completo" />
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="font-mono text-[10px] text-ink-400 mb-1.5 uppercase tracking-wider">
                      Foco (0-200)
                    </p>
                    <DistribuicaoNotasChart porModo={data.distribuicao_notas} modo="foco" />
                  </div>
                  <div>
                    <p className="font-mono text-[10px] text-ink-400 mb-1.5 uppercase tracking-wider">
                      Completo (0-1000)
                    </p>
                    <DistribuicaoNotasChart porModo={data.distribuicao_notas} modo="completo" />
                  </div>
                </div>
              )}
            </Card>

            <Card>
              <div className="flex items-baseline justify-between mb-3">
                <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
                  Top detectores
                </p>
                {data.outros_detectores > 0 && (
                  <p className="font-mono text-[10px] text-ink-400">
                    +{data.outros_detectores} outros
                  </p>
                )}
              </div>
              {data.top_detectores.length === 0 ? (
                <p className="text-sm text-ink-400">
                  Nenhum detector pedagógico acionado ainda.
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.top_detectores.map((d) => (
                    <li key={d.codigo}
                        className="flex items-center justify-between text-sm">
                      <span>{d.nome}</span>
                      <span className="font-mono text-xs text-ink-400">
                        ×{d.contagem}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
                Alunos em risco
              </p>
              {data.alunos_em_risco.length === 0 ? (
                <EmptyDashboardCard
                  positive
                  title="Nenhum aluno em risco"
                  description="Sem alunos com 2+ missões abaixo da faixa esperada."
                  className="border-0 shadow-none p-0"
                />
              ) : (
                <AlunosEmRiscoCard turmaId={turmaId} alunos={data.alunos_em_risco} />
              )}
            </Card>

            <Card>
              <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
                Evolução da turma
              </p>
              {naoQualificaEvolucao ? (
                <EmptyDashboardCard
                  title={
                    evolucaoFiltrada.length === 0
                      ? "Sem missões nesse modo"
                      : "Histórico aparece após 3 missões"
                  }
                  description={
                    evolucaoFiltrada.length === 0
                      ? undefined
                      : `Atualmente: ${evolucaoFiltrada.length}/3 missões com média.`
                  }
                  className="border-0 shadow-none p-0"
                />
              ) : (
                <EvolucaoChart
                  pontos={evolucaoFiltrada.map((p) => ({
                    x: new Date(p.data).toLocaleDateString("pt-BR", {
                      day: "2-digit", month: "2-digit",
                    }),
                    y: p.nota_media,
                    label: `${p.missao_codigo} · ${p.n_envios} envios`,
                    faixa: p.modo,
                  }))}
                  yMax={yMaxEvolucao}
                  yLabel="Média da turma"
                />
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
