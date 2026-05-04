"use client";

/**
 * Dashboard da turma — hierarquia visual reorganizada (refactor
 * 2026-05-04, proposta D consolidada).
 *
 * Layout em 5 áreas (top-down):
 *   1. Stats line + filtros: 1 linha enxuta "X envios · Y ativas
 *      · Z encerradas" + ToggleModo + botões Exportar PDF / Histórico
 *   2. Diagnóstico storytelling (DiagnosticoTurma) — bloco central,
 *      destaque visual (UI da Fase 4 + proposta D, intacta)
 *   3. Alunos em risco — visível, acionável
 *   4. ▼ Distribuição de notas — accordion fechado por default
 *   5. ▼ Evolução da turma — accordion fechado por default
 *
 * Removido (refactor 2026-05-04): bloco "Top detectores" — redundante
 * com o diagnóstico cognitivo de 40 descritores. Backend mantém o
 * campo `top_detectores` no payload pra compat (PDFs + escola
 * dashboard), só não é mais renderizado aqui.
 *
 * Decisões (Daniel):
 * - Diagnóstico cognitivo é o bloco mais valioso → posição central
 * - Alunos em risco é acionável → mantém visível
 * - Distribuição/Evolução são consultivos → accordion (acessíveis
 *   mas não competem por atenção com o storytelling)
 * - Stats topo são contexto rápido → 1 linha, sem card
 */
import { useEffect, useMemo, useState } from "react";

import { AlunosEmRiscoCard } from "@/components/portal/AlunosEmRiscoCard";
import { DiagnosticoTurma } from "@/components/portal/DiagnosticoTurma";
import { DistribuicaoNotasChart } from "@/components/portal/DistribuicaoNotasChart";
import { EmptyDashboardCard } from "@/components/portal/EmptyDashboardCard";
import { EvolucaoChart } from "@/components/portal/EvolucaoChart";
import { ExportarPdfModal } from "@/components/portal/ExportarPdfModal";
import { ToggleModo, type ModoFiltro } from "@/components/portal/ToggleModo";
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

// ──────────────────────────────────────────────────────────────────────
// Sub-componentes
// ──────────────────────────────────────────────────────────────────────

/** Stats topo: 1 linha enxuta + toggle de modo + botões à direita. */
function StatsTopo({
  data,
  modo,
  onModoChange,
  onExportar,
  turmaId,
}: {
  data: TurmaDashboard;
  modo: ModoFiltro;
  onModoChange: (m: ModoFiltro) => void;
  onExportar: () => void;
  turmaId: string;
}) {
  const envios = data.n_envios_total;
  const ativas = data.atividades_ativas;
  const encerradas = data.atividades_encerradas;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-[0.95rem] text-ink-700">
        <strong>{envios}</strong> envio{envios !== 1 ? "s" : ""} ·{" "}
        <strong>{ativas}</strong> atividade{ativas !== 1 ? "s" : ""} ativa
        {ativas !== 1 ? "s" : ""} ·{" "}
        <strong>{encerradas}</strong> encerrada
        {encerradas !== 1 ? "s" : ""}
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <ToggleModo value={modo} onChange={onModoChange} />
        <Button variant="ghost" onClick={onExportar}>
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
  );
}

/** Bloco "Alunos em risco" mantido visível (acionável). */
function BlocoAlunosEmRisco({
  data,
  turmaId,
}: {
  data: TurmaDashboard;
  turmaId: string;
}) {
  return (
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
  );
}

/** Accordion: Distribuição de notas. Conteúdo idêntico ao layout
 *  original, só envolvido em <details> fechado por default. */
function AccordionDistribuicao({
  data,
  modo,
}: {
  data: TurmaDashboard;
  modo: ModoFiltro;
}) {
  return (
    <details className="group border border-border rounded-lg overflow-hidden bg-white">
      <summary className="cursor-pointer flex items-center justify-between px-4 py-3 hover:bg-muted bg-muted/40">
        <span className="font-display text-sm">
          Distribuição de notas
        </span>
        <span className="flex items-center gap-3">
          <span className="font-mono text-xs text-ink-400">
            {modo === "todos" ? "completo + foco" : modo}
          </span>
          <span className="text-ink-400 transition-transform group-open:rotate-180">
            ▼
          </span>
        </span>
      </summary>
      <div className="p-4 border-t border-border">
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
      </div>
    </details>
  );
}

/** Accordion: Evolução da turma. */
function AccordionEvolucao({
  data,
  modo,
}: {
  data: TurmaDashboard;
  modo: ModoFiltro;
}) {
  const evolucaoFiltrada = useMemo(() => {
    if (modo === "todos") return data.evolucao_turma;
    return data.evolucao_turma.filter((p) => {
      const isFoco = p.modo?.startsWith("foco_");
      return modo === "foco" ? isFoco : !isFoco;
    });
  }, [data.evolucao_turma, modo]);

  const yMaxEvolucao =
    modo === "foco" ? 200 : modo === "completo" ? 1000 : 1000;
  const naoQualifica = evolucaoFiltrada.length < MIN_EVOLUCAO;

  return (
    <details className="group border border-border rounded-lg overflow-hidden bg-white">
      <summary className="cursor-pointer flex items-center justify-between px-4 py-3 hover:bg-muted bg-muted/40">
        <span className="font-display text-sm">Evolução da turma</span>
        <span className="text-ink-400 transition-transform group-open:rotate-180">
          ▼
        </span>
      </summary>
      <div className="p-4 border-t border-border">
        {naoQualifica ? (
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
                day: "2-digit",
                month: "2-digit",
              }),
              y: p.nota_media,
              label: `${p.missao_codigo} · ${p.n_envios} envios`,
              faixa: p.modo,
            }))}
            yMax={yMaxEvolucao}
            yLabel="Média da turma"
          />
        )}
      </div>
    </details>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Componente principal
// ──────────────────────────────────────────────────────────────────────

export function DashboardTurma({ turmaId }: Props) {
  const [data, setData] = useState<TurmaDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modo, setModo] = useState<ModoFiltro>("todos");
  const [pdfOpen, setPdfOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    dashboardTurma(turmaId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setError((err as ApiError).detail);
      });
    return () => {
      cancelled = true;
    };
  }, [turmaId]);

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

  return (
    <div className="space-y-6">
      {/* Área 1 — Stats topo + filtros (1 linha enxuta) */}
      <StatsTopo
        data={data}
        modo={modo}
        onModoChange={setModo}
        onExportar={() => setPdfOpen(true)}
        turmaId={turmaId}
      />

      <ExportarPdfModal
        open={pdfOpen}
        onClose={() => setPdfOpen(false)}
        title="Exportar dashboard da turma"
        description="O PDF inclui distribuição, top detectores, alunos em risco e evolução."
        onGerar={(p) => gerarPdfDashboardTurma(turmaId, p)}
      />

      {semEnvios ? (
        <>
          {/* Área 2 — Diagnóstico storytelling: trata estado vazio
              internamente, mostra callout encorajador quando não há
              alunos diagnosticados */}
          <DiagnosticoTurma turmaId={turmaId} />
          <EmptyDashboardCard
            title="Sem envios ainda"
            description="Quando os alunos começarem a mandar redações, distribuição, alunos em risco e evolução aparecem aqui."
          />
        </>
      ) : (
        <>
          {/* Área 2 — Diagnóstico storytelling (bloco central, destaque) */}
          <DiagnosticoTurma turmaId={turmaId} />

          {/* Área 3 — Alunos em risco (acionável, visível) */}
          <BlocoAlunosEmRisco data={data} turmaId={turmaId} />

          {/* Áreas 4-5 — Distribuição + Evolução em accordions
              fechados por default (consultivos, não competem com o
              diagnóstico storytelling pela atenção do professor) */}
          <div className="space-y-3">
            <AccordionDistribuicao data={data} modo={modo} />
            <AccordionEvolucao data={data} modo={modo} />
          </div>
        </>
      )}
    </div>
  );
}
