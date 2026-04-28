"use client";

import Link from "next/link";
import { useState } from "react";

import { EmptyDashboardCard } from "@/components/portal/EmptyDashboardCard";
import { EvolucaoChart } from "@/components/portal/EvolucaoChart";
import { ExportarPdfModal } from "@/components/portal/ExportarPdfModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { formatModoCorrecao, formatPrazo } from "@/lib/format";
import { gerarPdfEvolucaoAluno } from "@/lib/portal-client";
import type { AlunoEvolucao } from "@/types/portal";

interface Props {
  turmaId: string;
  turmaCodigo: string;
  evolucao: AlunoEvolucao;
}

function faixaVariant(faixa: string) {
  if (faixa === "Excelente") return "ativa" as const;
  if (faixa === "Bom") return "lime" as const;
  if (faixa === "Regular") return "warning" as const;
  if (faixa === "Insuficiente") return "encerrada" as const;
  return "neutral" as const;
}

// modoLabel removido — usa formatModoCorrecao de @/lib/format.

export function EvolucaoAlunoView({ turmaId, turmaCodigo, evolucao }: Props) {
  // yMax adaptativo: se há mistura de modos, usa 1000; se só foco, 200.
  const todosFoco = evolucao.envios.length > 0
    && evolucao.envios.every((e) => e.modo.startsWith("foco_"));
  const yMax = todosFoco ? 200 : 1000;
  const [pdfOpen, setPdfOpen] = useState(false);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            Turma {turmaCodigo}
          </p>
          <h1 className="font-display text-3xl mt-1">{evolucao.aluno.nome}</h1>
          <p className="mt-1 text-sm text-ink-400">
            <span className="text-ink font-semibold">
              {evolucao.n_missoes_realizadas}
            </span>{" "}
            missão{evolucao.n_missoes_realizadas !== 1 ? "ões" : ""} realizada
            {evolucao.n_missoes_realizadas !== 1 ? "s" : ""} ·{" "}
            <span className="text-ink font-semibold">
              {evolucao.missoes_pendentes.length}
            </span>{" "}
            pendente{evolucao.missoes_pendentes.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Button variant="ghost" onClick={() => setPdfOpen(true)}>
          Exportar evolução PDF
        </Button>
      </header>
      <ExportarPdfModal
        open={pdfOpen}
        onClose={() => setPdfOpen(false)}
        title="Exportar evolução do aluno"
        description="O PDF inclui chart de notas, missões realizadas e pendentes."
        onGerar={(p) =>
          gerarPdfEvolucaoAluno(turmaId, evolucao.aluno.id, p)
        }
      />

      <Card>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
          Evolução das notas
        </p>
        {evolucao.evolucao_chart.length === 0 ? (
          <EmptyDashboardCard
            title="Aluno ainda não realizou missões"
            description="Quando o aluno enviar a primeira redação, a evolução aparece aqui."
            className="border-0 shadow-none p-0"
          />
        ) : (
          <EvolucaoChart
            pontos={evolucao.evolucao_chart.map((p) => ({
              x: new Date(p.data).toLocaleDateString("pt-BR", {
                day: "2-digit", month: "2-digit",
              }),
              y: p.nota,
              label: p.missao_codigo,
            }))}
            yMax={yMax}
            yLabel="Nota"
          />
        )}
      </Card>

      <section aria-labelledby="missoes-realizadas">
        <h2 id="missoes-realizadas" className="font-display text-xl mb-3">
          Missões realizadas
        </h2>
        {evolucao.envios.length === 0 ? (
          <p className="text-sm text-ink-400">
            Sem envios ainda.
          </p>
        ) : (
          <ul className="space-y-2">
            {evolucao.envios.map((e) => (
              <li key={e.atividade_id}>
                <Link
                  href={`/atividade/${e.atividade_id}/aluno/${evolucao.aluno.id}`}
                  className="block bg-white border border-border rounded-xl p-4 hover:border-ink-400 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                        Oficina {e.oficina_numero}
                      </p>
                      <h3 className="font-display text-base">
                        {e.missao_titulo}
                      </h3>
                      <p className="text-xs text-ink-400 mt-0.5">
                        {formatModoCorrecao(e.modo)}
                      </p>
                      <p className="text-xs text-ink-400 mt-1">
                        Enviado em {formatPrazo(e.data)}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-display text-2xl">
                        {e.nota ?? "—"}
                      </p>
                      <Badge variant={faixaVariant(e.faixa)}>{e.faixa}</Badge>
                    </div>
                  </div>
                  {e.detectores.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {e.detectores.slice(0, 4).map((d) => (
                        <span
                          key={d}
                          className="font-mono text-[11px] bg-amber-50 text-amber-900 px-2 py-0.5 rounded"
                        >
                          {d}
                        </span>
                      ))}
                      {e.detectores.length > 4 && (
                        <span className="text-[11px] text-ink-400">
                          +{e.detectores.length - 4}
                        </span>
                      )}
                    </div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {evolucao.missoes_pendentes.length > 0 && (
        <section aria-labelledby="missoes-pendentes">
          <h2 id="missoes-pendentes" className="font-display text-xl mb-3">
            Missões pendentes
          </h2>
          <ul className="space-y-2">
            {evolucao.missoes_pendentes.map((m) => (
              <li key={m.atividade_id}>
                <Link
                  href={`/atividade/${m.atividade_id}`}
                  className="block bg-muted border border-border rounded-xl p-3 hover:bg-white transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                        Oficina {m.oficina_numero} · {formatModoCorrecao(m.modo_correcao)}
                      </p>
                      <p className="font-medium">{m.missao_titulo}</p>
                      <p className="text-xs text-ink-400">
                        até {formatPrazo(m.data_fim)}
                      </p>
                    </div>
                    <Badge variant={m.status === "ativa" ? "ativa" : "agendada"}>
                      {m.status}
                    </Badge>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
