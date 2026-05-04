"use client";

/**
 * Heatmap detalhado dos 40 descritores + top lacunas (extraído da
 * Fase 4 original em 2026-05-04, fix UX proposta D).
 *
 * Renderizado dentro de um accordion no DiagnosticoTurma novo —
 * fica escondido por default, professor expande quando quer ver
 * o mapa completo. UI principal (storytelling + cards de ação)
 * fica fora deste componente.
 *
 * Cores do heatmap (% alunos com lacuna):
 *   < 30% → verde (saúde coletiva)
 *   30-50% → amarelo (atenção)
 *   > 50% → vermelho (lacuna coletiva)
 *   0 alunos avaliados → cinza (sem dado)
 */
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatModoCorrecao } from "@/lib/format";
import type {
  DiagnosticoAgregado,
  DiagnosticoTurmaPorDescritor,
  DiagnosticoTurmaTopLacuna,
} from "@/types/portal";

interface Props {
  turmaId: string;
  agregado: DiagnosticoAgregado;
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

/** Cor do quadrado do heatmap pela % de alunos com lacuna. */
function corPorPercentLacuna(pct: number, totalAlunos: number): string {
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
                className={cn("inline-block w-4 h-4 rounded shrink-0", cor)}
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

/** Card de uma top lacuna coletiva (com sugestão pedagógica + oficinas). */
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
          variant={pctRender >= THRESHOLD_VERMELHO ? "encerrada" : "warning"}
        >
          {lac.competencia}
        </Badge>
        <h4 className="font-display text-base mt-1.5 leading-snug">
          {lac.nome}
        </h4>
        <p className="font-mono text-[11px] text-ink-400 mt-0.5">{lac.id}</p>
      </header>

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

      <div className="bg-amber-50/40 border border-amber-200 rounded p-2.5 -mx-1">
        <p className="font-mono text-[10px] uppercase tracking-wider text-amber-700 mb-1">
          🎯 Como trabalhar com a turma
        </p>
        <p className="text-xs leading-relaxed">{lac.sugestao_pedagogica}</p>
      </div>

      {lac.oficinas_sugeridas.length > 0 && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-400 mb-1.5">
            Oficinas pra mini-aula coletiva
          </p>
          <ul className="space-y-1.5">
            {lac.oficinas_sugeridas.map((o) => (
              <li
                key={o.codigo}
                className="flex items-baseline gap-2 text-xs"
              >
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

export function HeatmapDetalhado({ turmaId, agregado }: Props) {
  const { turma, agregado_por_descritor, top_lacunas } = agregado;

  return (
    <div className="space-y-5">
      {/* Mapa coletivo dos 40 descritores */}
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

      {/* Top lacunas coletivas (cards detalhados com sugestão pedagógica) */}
      {top_lacunas.length > 0 && (
        <div>
          <h4 className="font-display text-base mb-2">
            Lacunas coletivas mais frequentes
          </h4>
          <p className="text-xs text-ink-400 mb-3">
            Top {top_lacunas.length} descritores com ≥30% dos alunos em
            lacuna. Sugestão pedagógica detalhada por descritor.
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
      )}
    </div>
  );
}
