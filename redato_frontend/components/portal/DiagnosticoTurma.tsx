"use client";

/**
 * Diagnóstico cognitivo agregado da turma (Fase 4, 2026-05-03).
 *
 * Renderizado dentro do Dashboard da turma (aba "Dashboard" da
 * página `/turma/[id]`). Mostra visão coletiva: heatmap dos 40
 * descritores com cor por % lacuna, top lacunas, resumo executivo.
 *
 * Decisões de design (Daniel, Fase 4):
 * - Visível só pro professor (mesmo padrão Fase 3 — aluno não tem
 *   surface pra isso)
 * - Sem agregação cross-turma (uma turma por vez)
 * - Cores do heatmap diferentes da Fase 3:
 *     <30% lacuna → verde (saúde coletiva)
 *     30-50% → amarelo (atenção)
 *     >50% → vermelho (lacuna coletiva)
 *     0 alunos avaliados → cinza (sem dado)
 *
 * Estado vazio:
 * - 0 alunos diagnosticados → mensagem "Aguardando primeira redação"
 * - <3 alunos → mostra dados parciais com aviso
 */
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { cn } from "@/lib/cn";
import { formatModoCorrecao, formatPrazo } from "@/lib/format";
import { diagnosticoAgregadoTurma } from "@/lib/portal-client";
import { ApiError } from "@/types/api";
import type {
  DiagnosticoAgregado,
  DiagnosticoTurmaPorDescritor,
  DiagnosticoTurmaTopLacuna,
} from "@/types/portal";

interface Props {
  turmaId: string;
}

const COMPETENCIAS = ["C1", "C2", "C3", "C4", "C5"] as const;
type Competencia = (typeof COMPETENCIAS)[number];

const COMPETENCIA_NOME: Record<Competencia, string> = {
  C1: "Norma culta",
  C2: "Tema",
  C3: "Argumentação",
  C4: "Coesão",
  C5: "Proposta",
};

const THRESHOLD_AMARELO = 30;
const THRESHOLD_VERMELHO = 50;
const COBERTURA_MIN_AVISO = 50;
const COBERTURA_MIN_PARCIAL = 3;

/** Cor do quadrado do heatmap pela % de alunos com lacuna. */
function corPorPercentLacuna(
  pct: number,
  totalAlunos: number,
): string {
  if (totalAlunos === 0) return "bg-gray-300";
  if (pct >= THRESHOLD_VERMELHO) return "bg-red-500";
  if (pct >= THRESHOLD_AMARELO) return "bg-amber-500";
  return "bg-emerald-500";
}

/** Coluna do heatmap pra 1 competência. */
function CompetenciaColuna({
  competencia,
  descritores,
  totalAlunosDiagnosticados,
}: {
  competencia: Competencia;
  descritores: DiagnosticoTurmaPorDescritor[];
  totalAlunosDiagnosticados: number;
}) {
  const ordenados = descritores
    .filter((d) => d.competencia === competencia)
    .sort((a, b) => a.id.localeCompare(b.id));

  // Mini-resumo pra header da coluna
  const emLacunaColetiva = ordenados.filter(
    (d) => d.percent_lacuna >= THRESHOLD_VERMELHO,
  ).length;

  return (
    <div className="flex-1 min-w-0">
      <div className="mb-2 pb-2 border-b border-border">
        <p className="font-display text-sm">
          <span className="text-ink-400 font-mono text-xs mr-1">
            {competencia}
          </span>
          {COMPETENCIA_NOME[competencia]}
        </p>
        <p className="text-[11px] text-ink-400 mt-0.5">
          {emLacunaColetiva > 0 ? (
            <span className="text-red-700 font-medium">
              {emLacunaColetiva} descritor{emLacunaColetiva > 1 ? "es" : ""} ≥50% lacuna
            </span>
          ) : (
            "Sem alerta crítico"
          )}
        </p>
      </div>
      <ul role="list" className="space-y-0.5">
        {ordenados.map((d) => {
          const cor = corPorPercentLacuna(
            d.percent_lacuna,
            totalAlunosDiagnosticados,
          );
          const semDado = totalAlunosDiagnosticados === 0;
          return (
            <li
              key={d.id}
              className="flex items-center gap-2 py-1.5 px-1 -mx-1"
              title={`${d.nome} — ${
                semDado
                  ? "sem dado"
                  : `${d.alunos_com_lacuna} de ${totalAlunosDiagnosticados} alunos com lacuna (${d.percent_lacuna}%)`
              }`}
            >
              <span
                className={cn(
                  "inline-block w-4 h-4 rounded shrink-0",
                  cor,
                )}
                aria-hidden="true"
              />
              <span className="flex-1 min-w-0">
                <span className="block text-[13px] leading-tight truncate">
                  {d.nome}
                </span>
                <span className="block text-[11px] text-ink-400 font-mono">
                  {d.id}
                  {!semDado && d.percent_lacuna > 0 && (
                    <span
                      className={cn(
                        "ml-1.5 font-semibold",
                        d.percent_lacuna >= THRESHOLD_VERMELHO
                          ? "text-red-700"
                          : d.percent_lacuna >= THRESHOLD_AMARELO
                          ? "text-amber-700"
                          : "text-emerald-700",
                      )}
                    >
                      {d.percent_lacuna}%
                    </span>
                  )}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Sub-bloco 1: card da visão geral com cobertura + aviso. */
function VisaoGeralCard({
  data,
}: {
  data: DiagnosticoAgregado;
}) {
  const { turma, atualizado_em } = data;
  const cobertura =
    turma.total_alunos > 0
      ? Math.round(
          (turma.alunos_com_diagnostico / turma.total_alunos) * 100,
        )
      : 0;

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3 mb-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            Visão geral
          </p>
          <p className="font-display text-2xl mt-1">
            {turma.alunos_com_diagnostico}{" "}
            <span className="text-ink-400 font-normal text-base">
              de {turma.total_alunos} alunos diagnosticados
            </span>
          </p>
        </div>
        {atualizado_em && (
          <p className="text-xs text-ink-400 font-mono">
            Última atualização: {formatPrazo(atualizado_em)}
          </p>
        )}
      </div>

      {/* Barra de progresso da cobertura */}
      <div
        className="h-2 bg-muted rounded-full overflow-hidden"
        aria-label={`Cobertura ${cobertura}%`}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all",
            cobertura >= COBERTURA_MIN_AVISO ? "bg-emerald-500" : "bg-amber-500",
          )}
          style={{ width: `${cobertura}%` }}
        />
      </div>
      <p className="text-xs text-ink-400 mt-1">
        {cobertura}% de cobertura
        {turma.alunos_sem_diagnostico > 0 && (
          <>
            {" · "}
            {turma.alunos_sem_diagnostico} aluno{turma.alunos_sem_diagnostico > 1 ? "s" : ""} sem
            diagnóstico
          </>
        )}
      </p>

      {/* Aviso de cobertura insuficiente */}
      {turma.alunos_com_diagnostico > 0 &&
        cobertura < COBERTURA_MIN_AVISO && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
            <strong>Atenção:</strong> diagnóstico pode não refletir a
            turma completa. Estimule mais alunos a enviar redações pra
            cobertura ≥ 50%.
          </div>
        )}
      {turma.alunos_com_diagnostico > 0 &&
        turma.alunos_com_diagnostico < COBERTURA_MIN_PARCIAL && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
            <strong>Diagnóstico em formação.</strong> Mostrando dados
            parciais com {turma.alunos_com_diagnostico} de{" "}
            {turma.total_alunos} alunos — análise estatística fica
            confiável a partir de 3+ diagnósticos.
          </div>
        )}
    </Card>
  );
}

/** Card horizontal de uma top lacuna coletiva. */
function TopLacunaCard({
  lac,
  turmaId,
  totalAlunos,
}: {
  lac: DiagnosticoTurmaTopLacuna;
  turmaId: string;
  totalAlunos: number;
}) {
  const pctRender = lac.percent_lacuna;
  return (
    <Card className="p-4 flex flex-col gap-3">
      <header>
        <Badge
          variant={
            pctRender >= THRESHOLD_VERMELHO ? "encerrada" : "warning"
          }
        >
          {lac.competencia}
        </Badge>
        <h4 className="font-display text-base mt-1.5 leading-snug">
          {lac.nome}
        </h4>
        <p className="font-mono text-[11px] text-ink-400 mt-0.5">
          {lac.id}
        </p>
      </header>

      {/* Barra de progresso "X de Y alunos com lacuna" */}
      <div>
        <p className="text-xs text-ink-400 mb-1">
          <strong className="text-ink-700">{lac.qtd_alunos}</strong> de{" "}
          {totalAlunos} alunos com lacuna
          <span
            className={cn(
              "ml-1.5 font-semibold",
              pctRender >= THRESHOLD_VERMELHO
                ? "text-red-700"
                : "text-amber-700",
            )}
          >
            ({pctRender}%)
          </span>
        </p>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full",
              pctRender >= THRESHOLD_VERMELHO
                ? "bg-red-500"
                : "bg-amber-500",
            )}
            style={{ width: `${pctRender}%` }}
          />
        </div>
      </div>

      {/* Sugestão pedagógica */}
      <div className="bg-amber-50/40 border border-amber-200 rounded p-2.5 -mx-1">
        <p className="font-mono text-[10px] uppercase tracking-wider text-amber-700 mb-1">
          🎯 Como trabalhar com a turma
        </p>
        <p className="text-xs leading-relaxed">{lac.sugestao_pedagogica}</p>
      </div>

      {/* Oficinas sugeridas */}
      {lac.oficinas_sugeridas.length > 0 && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-400 mb-1.5">
            Oficinas pra mini-aula coletiva
          </p>
          <ul className="space-y-1.5">
            {lac.oficinas_sugeridas.map((o) => (
              <li key={o.codigo} className="flex items-baseline gap-2 text-xs">
                <span className="font-mono text-ink-400">{o.codigo}</span>
                <Link
                  href={`/turma/${turmaId}?aba=atividades&missao=${encodeURIComponent(o.codigo)}`}
                  className="flex-1 truncate hover:text-ink underline-offset-4 hover:underline"
                >
                  {o.titulo}
                </Link>
                <Badge variant="neutral">
                  {formatModoCorrecao(o.modo_correcao)}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

/** Componente principal. */
export function DiagnosticoTurma({ turmaId }: Props) {
  const [data, setData] = useState<DiagnosticoAgregado | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    diagnosticoAgregadoTurma(turmaId)
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
      <Card className="text-sm text-danger p-4">
        Erro ao carregar diagnóstico agregado: {error}
      </Card>
    );
  }
  if (!data) {
    return (
      <Card className="flex items-center justify-center gap-3 py-10">
        <LoadingSpinner size={20} />
        <span className="text-sm text-ink-400">
          Carregando diagnóstico da turma…
        </span>
      </Card>
    );
  }

  const { turma, agregado_por_descritor, top_lacunas, resumo_executivo } = data;

  // Estado vazio: nenhum aluno diagnosticado
  if (turma.alunos_com_diagnostico === 0) {
    return (
      <section aria-labelledby="diag-turma-h" className="space-y-3">
        <h3 id="diag-turma-h" className="font-display text-lg">
          Diagnóstico cognitivo da turma
        </h3>
        <Card className="p-6 text-center text-sm text-ink-400">
          <p>
            <strong className="text-ink-700">
              Nenhum diagnóstico ainda.
            </strong>{" "}
            Quando alunos enviarem redações via WhatsApp, o
            diagnóstico coletivo aparece aqui — mostra quais
            competências a turma toda precisa reforçar.
          </p>
        </Card>
      </section>
    );
  }

  return (
    <section aria-labelledby="diag-turma-h" className="space-y-5">
      <div>
        <h3 id="diag-turma-h" className="font-display text-lg">
          Diagnóstico cognitivo da turma
        </h3>
        <p className="text-xs text-ink-400 mt-1">
          Visão coletiva baseada no diagnóstico mais recente de cada aluno
          ativo. Cada aluno conta no máx. 1 vez (último envio diagnosticado).
        </p>
      </div>

      {/* Sub-bloco 1 — Visão geral */}
      <VisaoGeralCard data={data} />

      {/* Sub-bloco 4 (vem antes do heatmap pra ser visível primeiro) — Resumo executivo */}
      <Card className="p-4 bg-amber-50/40 border-amber-200">
        <p className="font-mono text-[11px] uppercase tracking-wider text-amber-700 mb-2">
          🎯 Resumo executivo
        </p>
        <p className="text-sm leading-relaxed">{resumo_executivo}</p>
      </Card>

      {/* Sub-bloco 2 — Heatmap agregado da turma */}
      <Card className="p-4">
        <div className="flex items-baseline justify-between mb-3 flex-wrap gap-2">
          <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
            Mapa coletivo dos 40 descritores
          </p>
          <p className="text-[11px] text-ink-400">
            % alunos com lacuna em cada descritor
          </p>
        </div>

        {/* Desktop: 5 colunas */}
        <div className="hidden md:flex gap-4">
          {COMPETENCIAS.map((c) => (
            <CompetenciaColuna
              key={c}
              competencia={c}
              descritores={agregado_por_descritor}
              totalAlunosDiagnosticados={turma.alunos_com_diagnostico}
            />
          ))}
        </div>

        {/* Mobile: acordeão por competência */}
        <div className="md:hidden space-y-2">
          {COMPETENCIAS.map((c) => {
            const descritoresC = agregado_por_descritor.filter(
              (d) => d.competencia === c,
            );
            const emAlerta = descritoresC.filter(
              (d) => d.percent_lacuna >= THRESHOLD_VERMELHO,
            ).length;
            return (
              <details
                key={c}
                className="border border-border rounded-lg overflow-hidden"
              >
                <summary className="cursor-pointer flex items-center justify-between px-3 py-2 bg-muted/50 hover:bg-muted">
                  <span className="font-display text-sm">
                    <span className="text-ink-400 font-mono text-xs mr-1">
                      {c}
                    </span>
                    {COMPETENCIA_NOME[c]}
                  </span>
                  <span className="text-[11px]">
                    {emAlerta > 0 ? (
                      <span className="text-red-700 font-medium">
                        {emAlerta} crítico{emAlerta > 1 ? "s" : ""}
                      </span>
                    ) : (
                      <span className="text-ink-400">OK</span>
                    )}
                  </span>
                </summary>
                <div className="px-3 py-2">
                  <CompetenciaColuna
                    competencia={c}
                    descritores={agregado_por_descritor}
                    totalAlunosDiagnosticados={turma.alunos_com_diagnostico}
                  />
                </div>
              </details>
            );
          })}
        </div>

        {/* Legenda */}
        <div className="flex flex-wrap gap-3 mt-4 text-xs text-ink-400">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-emerald-500" />
            &lt;30% lacuna
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-amber-500" />
            30-50% lacuna
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-red-500" />
            &gt;50% lacuna
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded bg-gray-300" />
            sem dado
          </span>
        </div>
      </Card>

      {/* Sub-bloco 3 — Top lacunas coletivas */}
      {top_lacunas.length > 0 ? (
        <div>
          <h4 className="font-display text-base mb-2">
            Lacunas coletivas mais frequentes
          </h4>
          <p className="text-xs text-ink-400 mb-3">
            Top {top_lacunas.length} descritores com ≥30% dos alunos em
            lacuna. Use as oficinas sugeridas pra planejar mini-aula
            coletiva antes da próxima atividade.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {top_lacunas.slice(0, 5).map((lac) => (
              <TopLacunaCard
                key={lac.id}
                lac={lac}
                turmaId={turmaId}
                totalAlunos={turma.alunos_com_diagnostico}
              />
            ))}
          </div>
        </div>
      ) : (
        <Card className="p-4 text-center text-sm text-ink-400">
          Nenhum descritor crítico (≥30% alunos com lacuna) — turma
          está distribuída sem concentração específica. Continue
          acompanhando perfis individuais.
        </Card>
      )}
    </section>
  );
}
