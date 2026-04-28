"use client";

import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { ApiError } from "@/types/api";
import type { GerarPdfResponse } from "@/types/portal";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Função que de fato dispara a geração no backend. */
  onGerar: (params: {
    periodo_inicio?: string;
    periodo_fim?: string;
  }) => Promise<GerarPdfResponse>;
  title?: string;
  description?: ReactNode;
}

/**
 * Modal compacto pra exportar PDF. Aceita período opcional.
 *
 * Sucesso: toast "PDF gerado" + abre tab pra download via proxy
 * `/api/portal/pdfs/{id}/download`. Browser respeita o
 * content-disposition: attachment do backend e baixa o arquivo
 * (em vez de exibir inline).
 */
export function ExportarPdfModal({
  open, onClose, onGerar,
  title = "Exportar como PDF",
  description,
}: Props) {
  const [periodoInicio, setPeriodoInicio] = useState("");
  const [periodoFim, setPeriodoFim] = useState("");
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  function fechar() {
    if (loading) return;
    setPeriodoInicio("");
    setPeriodoFim("");
    onClose();
  }

  async function gerar() {
    setLoading(true);
    try {
      const params: { periodo_inicio?: string; periodo_fim?: string } = {};
      if (periodoInicio) {
        params.periodo_inicio = new Date(periodoInicio).toISOString();
      }
      if (periodoFim) {
        params.periodo_fim = new Date(periodoFim).toISOString();
      }
      const resp = await onGerar(params);
      const kb = Math.round(resp.tamanho_bytes / 1024);
      toast.success(`PDF gerado (${kb} KB). Abrindo download…`);
      // Abre via proxy local (browser dispara download por causa do
      // content-disposition: attachment do backend).
      window.open(`/api/portal/pdfs/${resp.pdf_id}/download`, "_blank");
      fechar();
    } catch (err) {
      toast.error((err as ApiError).detail || "Erro ao gerar PDF.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="exportar-pdf-title"
    >
      <button
        type="button"
        aria-label="Fechar"
        onClick={fechar}
        className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
        tabIndex={-1}
      />
      <div className="relative w-full sm:max-w-md bg-white rounded-t-2xl sm:rounded-2xl border border-border shadow-card p-5 sm:p-6 mx-0 sm:mx-4">
        <h2 id="exportar-pdf-title" className="font-display text-xl">
          {title}
        </h2>
        {description && (
          <div className="mt-2 text-sm text-ink-400">{description}</div>
        )}
        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <FormField label="Período início" hint="opcional">
            <Input
              type="date"
              value={periodoInicio}
              onChange={(e) => setPeriodoInicio(e.target.value)}
              disabled={loading}
            />
          </FormField>
          <FormField label="Período fim" hint="opcional">
            <Input
              type="date"
              value={periodoFim}
              onChange={(e) => setPeriodoFim(e.target.value)}
              disabled={loading}
            />
          </FormField>
        </div>
        <p className="text-xs text-ink-400 mt-3">
          Sem período definido, o PDF cobre todos os dados disponíveis.
        </p>
        <div className="mt-6 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
          <Button variant="ghost" onClick={fechar} disabled={loading}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={gerar} loading={loading}>
            {loading ? "Gerando…" : "Gerar PDF"}
          </Button>
        </div>
      </div>
    </div>
  );
}
