"use client";

import { useEffect, useState } from "react";

import { EmptyDashboardCard } from "@/components/portal/EmptyDashboardCard";
import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { formatPrazo } from "@/lib/format";
import { listarPdfsHistorico, pdfDownloadUrl } from "@/lib/portal-client";
import type { PdfHistoricoItem, PdfTipo } from "@/types/portal";

interface Props {
  /** Filtra por escopo (turma_id ou escola_id). Undefined = todos. */
  escopoId?: string;
}

const TIPO_LABEL: Record<PdfTipo, string> = {
  dashboard_turma: "Dashboard da turma",
  dashboard_escola: "Dashboard da escola",
  evolucao_aluno: "Evolução do aluno",
  atividade_detalhe: "Detalhe da atividade",
};

export function HistoricoPdfsList({ escopoId }: Props) {
  const [items, setItems] = useState<PdfHistoricoItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filtroTipo, setFiltroTipo] = useState<PdfTipo | "todos">("todos");

  useEffect(() => {
    let cancelled = false;
    listarPdfsHistorico({
      escopo_id: escopoId,
      tipo: filtroTipo === "todos" ? undefined : filtroTipo,
      limit: 50,
    })
      .then((data) => { if (!cancelled) setItems(data); })
      .catch((err) => { if (!cancelled) setError(String(err)); });
    return () => { cancelled = true; };
  }, [escopoId, filtroTipo]);

  if (error) {
    return (
      <Card className="text-sm text-danger">
        Erro ao carregar histórico: {error}
      </Card>
    );
  }
  if (items === null) {
    return (
      <Card className="flex items-center justify-center gap-3 py-10">
        <LoadingSpinner size={20} />
        <span className="text-sm text-ink-400">Carregando…</span>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Filtrar:
        </span>
        <select
          value={filtroTipo}
          onChange={(e) => setFiltroTipo(e.target.value as PdfTipo | "todos")}
          className="rounded-lg border border-border bg-white px-2 h-8 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime"
        >
          <option value="todos">Todos os tipos</option>
          <option value="dashboard_turma">Dashboard turma</option>
          <option value="dashboard_escola">Dashboard escola</option>
          <option value="evolucao_aluno">Evolução aluno</option>
        </select>
      </div>

      {items.length === 0 ? (
        <EmptyDashboardCard
          title="Nenhum PDF gerado ainda"
          description="Use o botão 'Exportar PDF' nos dashboards. Os arquivos gerados ficam aqui pra consulta posterior."
        />
      ) : (
        <ul className="space-y-2">
          {items.map((p) => {
            const kb = Math.max(1, Math.round(p.tamanho_bytes / 1024));
            return (
              <li key={p.id}>
                <a
                  href={pdfDownloadUrl(p.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block bg-white border border-border rounded-xl p-4 hover:border-ink-400 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium">{TIPO_LABEL[p.tipo]}</p>
                      <p className="text-xs text-ink-400 mt-0.5">
                        Gerado em {formatPrazo(p.gerado_em)} ·{" "}
                        <span className="font-mono">{kb} KB</span>
                      </p>
                    </div>
                    <span className="font-mono text-xs uppercase tracking-wider text-ink-400 group-hover:text-ink">
                      baixar →
                    </span>
                  </div>
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
