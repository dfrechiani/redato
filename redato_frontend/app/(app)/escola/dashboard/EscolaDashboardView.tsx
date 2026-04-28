"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { AlunosEmRiscoCard } from "@/components/portal/AlunosEmRiscoCard";
import { ComparacaoTurmasChart } from "@/components/portal/ComparacaoTurmasChart";
import { DistribuicaoNotasChart } from "@/components/portal/DistribuicaoNotasChart";
import { EmptyDashboardCard } from "@/components/portal/EmptyDashboardCard";
import { EvolucaoChart } from "@/components/portal/EvolucaoChart";
import { ExportarPdfModal } from "@/components/portal/ExportarPdfModal";
import { ToggleModo, type ModoFiltro } from "@/components/portal/ToggleModo";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatSerie } from "@/lib/format";
import { gerarPdfDashboardEscola } from "@/lib/portal-client";
import type { EscolaDashboard } from "@/types/portal";

interface Props {
  initial: EscolaDashboard;
}

const MIN_EVOLUCAO = 3;

export function EscolaDashboardView({ initial }: Props) {
  const [data] = useState<EscolaDashboard>(initial);
  const [modo, setModo] = useState<ModoFiltro>("todos");
  const [pdfOpen, setPdfOpen] = useState(false);

  const evolucaoFiltrada = useMemo(() => {
    if (modo === "todos") return data.evolucao_escola;
    return data.evolucao_escola.filter((p) => {
      const isFoco = p.modo?.startsWith("foco_");
      return modo === "foco" ? isFoco : !isFoco;
    });
  }, [data, modo]);

  const yMaxEvolucao = modo === "foco" ? 200 : 1000;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            {data.escola.nome}
          </p>
          <h1 className="font-display text-3xl mt-1">Dashboard da escola</h1>
          <p className="mt-1 text-sm text-ink-400">
            <span className="text-ink font-semibold">{data.escola.n_turmas}</span> turma
            {data.escola.n_turmas !== 1 ? "s" : ""} ·{" "}
            <span className="text-ink font-semibold">
              {data.escola.n_alunos_ativos}
            </span>{" "}
            aluno{data.escola.n_alunos_ativos !== 1 ? "s" : ""} ativo
            {data.escola.n_alunos_ativos !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/escola/historico-pdfs"
            className="text-sm text-ink-400 hover:text-ink underline-offset-4 hover:underline"
          >
            Histórico de PDFs
          </Link>
          <Button variant="primary" onClick={() => setPdfOpen(true)}>
            Exportar PDF da escola
          </Button>
        </div>
      </header>
      <ExportarPdfModal
        open={pdfOpen}
        onClose={() => setPdfOpen(false)}
        title="Exportar dashboard da escola"
        description="O PDF inclui comparação entre turmas, distribuição agregada, detectores e alunos em risco."
        onGerar={(p) => gerarPdfDashboardEscola(data.escola.id, p)}
      />

      {/* Resumo + Comparação */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Comparação entre turmas
          </p>
          {data.comparacao_turmas.length < 2 ? (
            <EmptyDashboardCard
              title="Comparação aparece com ≥ 2 turmas com dados"
              description="Quando ao menos duas turmas tiverem envios processados, a comparação de médias aparece aqui."
              className="border-0 shadow-none p-0"
            />
          ) : (
            <ComparacaoTurmasChart turmas={data.comparacao_turmas} />
          )}
        </Card>

        <Card>
          <div className="flex items-baseline justify-between mb-3">
            <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
              Distribuição da escola
            </p>
            <ToggleModo
              value={modo}
              onChange={setModo}
              className="scale-90 origin-right"
            />
          </div>
          {modo === "foco" ? (
            <DistribuicaoNotasChart porModo={data.distribuicao_notas_escola} modo="foco" />
          ) : modo === "completo" ? (
            <DistribuicaoNotasChart porModo={data.distribuicao_notas_escola} modo="completo" />
          ) : (
            <div className="space-y-4">
              <div>
                <p className="font-mono text-[10px] text-ink-400 mb-1.5 uppercase tracking-wider">
                  Foco
                </p>
                <DistribuicaoNotasChart porModo={data.distribuicao_notas_escola} modo="foco" />
              </div>
              <div>
                <p className="font-mono text-[10px] text-ink-400 mb-1.5 uppercase tracking-wider">
                  Completo
                </p>
                <DistribuicaoNotasChart porModo={data.distribuicao_notas_escola} modo="completo" />
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Top detectores + Alunos em risco */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <div className="flex items-baseline justify-between mb-3">
            <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
              Top detectores da escola
            </p>
            {data.outros_detectores_escola > 0 && (
              <p className="font-mono text-[10px] text-ink-400">
                +{data.outros_detectores_escola} outros
              </p>
            )}
          </div>
          {data.top_detectores_escola.length === 0 ? (
            <p className="text-sm text-ink-400">
              Nenhum detector pedagógico acionado ainda.
            </p>
          ) : (
            <ul className="space-y-2">
              {data.top_detectores_escola.map((d) => (
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

        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Alunos em risco (escola)
          </p>
          {data.alunos_em_risco_escola.length === 0 ? (
            <EmptyDashboardCard
              positive
              title="Nenhum aluno em risco"
              description="Sem alunos com 2+ missões abaixo da faixa esperada na escola."
              className="border-0 shadow-none p-0"
            />
          ) : (
            <AlunosEmRiscoCard alunos={data.alunos_em_risco_escola} />
          )}
        </Card>
      </div>

      {/* Evolução geral */}
      <Card>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
          Evolução agregada da escola
        </p>
        {evolucaoFiltrada.length < MIN_EVOLUCAO ? (
          <EmptyDashboardCard
            title={
              evolucaoFiltrada.length === 0
                ? "Sem missões com nota ainda"
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
            }))}
            yMax={yMaxEvolucao}
            yLabel="Média"
          />
        )}
      </Card>

      {/* Resumo das turmas com link */}
      <section aria-labelledby="turmas-h">
        <h2 id="turmas-h" className="font-display text-xl mb-3">
          Turmas
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.turmas_resumo.map((t) => (
            <Link
              key={t.turma_id}
              href={`/turma/${t.turma_id}`}
              className="block bg-white border border-border rounded-xl p-4 hover:border-ink-400 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
                    {formatSerie(t.serie)} · {t.professor_nome}
                  </p>
                  <h3 className="font-display text-xl mt-0.5">{t.codigo}</h3>
                </div>
                {t.n_em_risco > 0 && (
                  <Badge variant="warning">{t.n_em_risco} risco</Badge>
                )}
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <dt className="text-ink-400">Média</dt>
                  <dd className="text-ink font-semibold text-base">
                    {t.media_geral ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-400">Atividades</dt>
                  <dd className="text-ink font-semibold text-base">
                    {t.n_atividades}
                  </dd>
                </div>
              </dl>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
