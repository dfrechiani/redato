"use client";

/**
 * Perfil do aluno na turma (M9.7) — drill-down de
 * `/turma/{turma_id}/aluno/{aluno_id}`.
 *
 * Layout (top-down):
 *   1. Identificação (nome + ATIVO/DESVINCULADO + telefone + entrou_em)
 *   2. Stats em cards (Envios, Nota média + tendência, Ponto forte,
 *      Ponto fraco) + barrinhas C1-C5
 *   3. Gráfico de evolução (chart SVG simples, mesmo do EvolucaoChart)
 *   4. Tabela de envios — linha clicável (vai pro detalhe), botão
 *      Reprocessar inline quando tem_problema=true
 *
 * Estado vazio (total_envios === 0): substitui blocos 2-4 por uma única
 * mensagem "Nenhum envio ainda".
 *
 * Endpoint backend: GET /portal/turmas/{turma_id}/alunos/{aluno_id}/perfil.
 */
import Link from "next/link";

import { EvolucaoChart } from "@/components/portal/EvolucaoChart";
import { MapaCognitivo } from "@/components/portal/MapaCognitivo";
import { ReprocessarEnvioButton } from "@/components/portal/ReprocessarEnvioButton";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { formatModoCorrecao, formatPrazo } from "@/lib/format";
import type {
  AlunoPerfil,
  AlunoTendencia,
  CompetenciaKey,
} from "@/types/portal";

interface Props {
  turmaId: string;
  turmaCodigo: string;
  perfil: AlunoPerfil;
}

const COMPS: CompetenciaKey[] = ["c1", "c2", "c3", "c4", "c5"];

function tendenciaIcon(t: AlunoTendencia): string {
  if (t === "subindo") return "↑";
  if (t === "caindo") return "↓";
  if (t === "estavel") return "=";
  return "—";
}

function tendenciaColor(t: AlunoTendencia): string {
  if (t === "subindo") return "text-lime";
  if (t === "caindo") return "text-danger";
  return "text-ink-400";
}

function tendenciaLabel(t: AlunoTendencia): string {
  if (t === "subindo") return "subindo";
  if (t === "caindo") return "caindo";
  if (t === "estavel") return "estável";
  return "dados insuficientes";
}

export function PerfilAlunoView({ turmaId, turmaCodigo, perfil }: Props) {
  const { aluno, stats, envios } = perfil;
  const dataEntrada = new Date(aluno.entrou_em).toLocaleDateString("pt-BR");
  const semEnvios = stats.total_envios === 0;

  // yMax adaptativo igual EvolucaoView: foco usa 200, completo 1000.
  // Mistura: se TODO envio com nota é foco_*, usa 200; senão 1000.
  const todosFoco =
    envios.length > 0 &&
    envios.every((e) => e.modo_correcao.startsWith("foco_"));
  const yMax = todosFoco ? 200 : 1000;

  // Pontos do chart: ordem cronológica ASC (mais antigo → mais novo).
  // Backend manda envios desc, invertemos pro chart.
  const chartPontos = [...envios]
    .filter((e) => e.nota_total !== null)
    .reverse()
    .map((e) => ({
      x: new Date(e.criado_em).toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
      }),
      y: e.nota_total as number,
      label: e.atividade_codigo,
    }));

  return (
    <div className="space-y-8">
      {/* ─── Bloco 1 — Identificação ─────────────────────── */}
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Turma {turmaCodigo}
        </p>
        <div className="flex flex-wrap items-baseline gap-3 mt-1">
          <h1 className="font-display text-3xl">{aluno.nome}</h1>
          <Badge variant={aluno.ativo ? "ativa" : "encerrada"}>
            {aluno.ativo ? "ATIVO" : "DESVINCULADO"}
          </Badge>
        </div>
        <p className="mt-2 text-sm text-ink-400 font-mono">
          Telefone: {aluno.telefone_mascarado} · Entrou em {dataEntrada}
        </p>
      </header>

      {semEnvios ? (
        <EmptyState
          title="Nenhum envio ainda"
          description="Quando o aluno mandar a primeira redação pelo WhatsApp, os dados aparecem aqui (nota média, evolução por competência, histórico)."
        />
      ) : (
        <>
          {/* ─── Bloco 2 — Stats em cards ──────────────────── */}
          <section
            aria-labelledby="stats-h"
            className="space-y-4"
          >
            <h2 id="stats-h" className="sr-only">
              Estatísticas
            </h2>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="p-5">
                <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                  Envios
                </p>
                <p className="font-display text-3xl mt-1">
                  {stats.total_envios}
                </p>
                <p className="text-xs text-ink-400 mt-1">
                  {stats.envios_com_nota} com nota
                  {stats.envios_com_problema > 0 && (
                    <>
                      {" · "}
                      <span className="text-amber-700 font-medium">
                        {stats.envios_com_problema} com problema
                      </span>
                    </>
                  )}
                </p>
              </Card>

              <Card className="p-5">
                <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                  Nota média
                </p>
                <p className="font-display text-3xl mt-1">
                  {stats.media_geral ?? "—"}
                </p>
                <p
                  className={cn(
                    "text-xs mt-1 font-medium",
                    tendenciaColor(stats.tendencia),
                  )}
                  title={
                    stats.tendencia === "dados_insuficientes"
                      ? "Tendência precisa de pelo menos 6 envios com nota."
                      : "Comparação das últimas 3 com as 3 anteriores."
                  }
                >
                  {tendenciaIcon(stats.tendencia)} {tendenciaLabel(stats.tendencia)}
                </p>
              </Card>

              <Card
                className={cn(
                  "p-5",
                  stats.ponto_forte && "border-lime/40 bg-lime/5",
                )}
              >
                <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                  Ponto forte
                </p>
                <p className="font-display text-3xl mt-1">
                  {stats.ponto_forte ?? "—"}
                </p>
                <p className="text-xs text-ink-400 mt-1">
                  {stats.ponto_forte && stats.medias_cN[
                    stats.ponto_forte.toLowerCase() as CompetenciaKey
                  ] !== null
                    ? `média ${stats.medias_cN[
                        stats.ponto_forte.toLowerCase() as CompetenciaKey
                      ]}`
                    : "sem dados"}
                </p>
              </Card>

              <Card
                className={cn(
                  "p-5",
                  stats.ponto_fraco && "border-amber-300 bg-amber-50/40",
                )}
              >
                <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                  Ponto fraco
                </p>
                <p className="font-display text-3xl mt-1">
                  {stats.ponto_fraco ?? "—"}
                </p>
                <p className="text-xs text-ink-400 mt-1">
                  {stats.ponto_fraco && stats.medias_cN[
                    stats.ponto_fraco.toLowerCase() as CompetenciaKey
                  ] !== null
                    ? `média ${stats.medias_cN[
                        stats.ponto_fraco.toLowerCase() as CompetenciaKey
                      ]}`
                    : "sem dados"}
                </p>
              </Card>
            </div>

            {/* Barras compactas C1-C5 */}
            <Card className="p-4">
              <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-3">
                Médias por competência
              </p>
              <ul className="space-y-2">
                {COMPS.map((ck) => {
                  const v = stats.medias_cN[ck];
                  // Escala da barra: o frontend não sabe qual é o yMax
                  // "real" da competência (foco vs completo retornam
                  // ambos em escala 0-200 ENEM por C). Padronizamos
                  // /200 — bate com a rubrica oficial.
                  const pct =
                    v !== null ? Math.min(100, (v / 200) * 100) : 0;
                  return (
                    <li
                      key={ck}
                      className="grid grid-cols-[3rem_1fr_3rem] items-center gap-3 text-sm"
                    >
                      <span className="font-mono text-xs uppercase text-ink-400">
                        {ck.toUpperCase()}
                      </span>
                      <div
                        className="h-2 bg-muted rounded-full overflow-hidden"
                        aria-label={
                          v !== null
                            ? `${ck.toUpperCase()} média ${v} de 200`
                            : `${ck.toUpperCase()} sem dados`
                        }
                      >
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            v === null
                              ? "bg-transparent"
                              : "bg-ink-700",
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-right font-mono text-xs">
                        {v ?? "—"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Card>
          </section>

          {/* ─── Bloco 3 — Mapa cognitivo (Fase 3) ─────────── */}
          {/* Heatmap dos 40 descritores + lacunas prioritárias +
              resumo + recomendação + oficinas sugeridas. Renderiza
              estado vazio quando aluno não tem envio diagnosticado. */}
          <MapaCognitivo
            turmaId={turmaId}
            diagnostico={perfil.diagnostico_recente}
          />

          {/* ─── Bloco 4 — Gráfico de evolução ─────────────── */}
          <section aria-labelledby="evolucao-h">
            <h2 id="evolucao-h" className="font-display text-xl mb-3">
              Evolução
            </h2>
            <Card>
              {chartPontos.length < 2 ? (
                <p className="text-sm text-ink-400 text-center py-6">
                  Precisa de pelo menos 2 envios com nota pra ver evolução.
                </p>
              ) : (
                <EvolucaoChart
                  pontos={chartPontos}
                  yMax={yMax}
                  yLabel="Nota"
                />
              )}
            </Card>
          </section>

          {/* ─── Bloco 4 — Tabela de envios ────────────────── */}
          <section aria-labelledby="envios-h">
            <h2 id="envios-h" className="font-display text-xl mb-3">
              Envios ({envios.length})
            </h2>
            <Card className="p-0 overflow-hidden">
              <ul role="list" className="divide-y divide-border">
                {envios.map((e) => (
                  <li
                    key={e.id || e.atividade_id}
                    className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-muted"
                  >
                    {/* Linha clicável: data + atividade — vai pro
                        detalhe individual (modal de feedback existe lá) */}
                    <Link
                      href={`/atividade/${e.atividade_id}/aluno/${aluno.id}`}
                      className="min-w-0 flex-1 hover:text-ink"
                      aria-label={`Ver feedback de ${e.atividade_titulo}`}
                    >
                      <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                        {e.atividade_codigo} · {formatModoCorrecao(e.modo_correcao)}
                      </p>
                      <p className="font-medium truncate">
                        {e.atividade_titulo}
                      </p>
                      <p className="text-xs text-ink-400 mt-0.5">
                        {formatPrazo(e.criado_em)}
                      </p>
                    </Link>

                    <div className="text-right shrink-0 min-w-[3.5rem]">
                      <p className="font-display text-xl">
                        {e.nota_total ?? "—"}
                      </p>
                      {e.tem_problema && (
                        <p className="text-[10px] uppercase tracking-wide text-amber-700">
                          problema
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {e.tem_feedback && (
                        <Link
                          href={`/atividade/${e.atividade_id}/aluno/${aluno.id}`}
                          className="text-xs text-ink underline-offset-4 hover:underline"
                        >
                          Ver feedback
                        </Link>
                      )}
                      {/* ReprocessarEnvioButton já trata shouldShow
                          internamente — mantém código consistente
                          com outras telas que usam o mesmo botão. */}
                      <ReprocessarEnvioButton
                        envioId={e.id}
                        shouldShow={e.tem_problema && !!e.id}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        </>
      )}

      {/* Link auxiliar pra evolução completa (PDF + missões pendentes
          ficam lá pra não duplicar conteúdo). */}
      {!semEnvios && (
        <p className="text-sm">
          <Link
            href={`/turma/${turmaId}/aluno/${aluno.id}/evolucao`}
            className="text-ink underline-offset-4 hover:underline"
          >
            Ver evolução completa + exportar PDF →
          </Link>
        </p>
      )}
    </div>
  );
}
