"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { formatMissaoLabel } from "@/lib/format";
import { criarAtividade, listarMissoes } from "@/lib/portal-client";
import { ApiError } from "@/types/api";
import type { Missao } from "@/types/portal";

interface Props {
  open: boolean;
  onClose: () => void;
  turmaId: string;
  turmaCodigo: string;
  /** Disparado após criar (com sucesso). Use pra recarregar a turma. */
  onCriada?: (atividadeId: string) => void;
}

function defaultDates() {
  const hoje = new Date();
  hoje.setSeconds(0, 0);
  const fim = new Date(hoje);
  fim.setDate(fim.getDate() + 7);
  fim.setHours(23, 59, 0, 0);
  const fmt = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
      `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  return { inicio: fmt(hoje), fim: fmt(fim) };
}

export function AtivarMissaoModal({
  open,
  onClose,
  turmaId,
  turmaCodigo,
  onCriada,
}: Props) {
  const router = useRouter();
  const [missoes, setMissoes] = useState<Missao[]>([]);
  const [loadingMissoes, setLoadingMissoes] = useState(true);
  const [missaoId, setMissaoId] = useState("");
  const dates = useMemo(defaultDates, []);
  const [dataInicio, setDataInicio] = useState(dates.inicio);
  const [dataFim, setDataFim] = useState(dates.fim);
  const [notificar, setNotificar] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingMissoes(true);
    listarMissoes()
      .then((ms) => {
        if (cancelled) return;
        setMissoes(ms);
        if (ms.length > 0 && !missaoId) setMissaoId(ms[0].id);
      })
      .catch((err) => {
        if (cancelled) return;
        setError((err as ApiError).detail || "Erro ao carregar missões");
      })
      .finally(() => {
        if (!cancelled) setLoadingMissoes(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, missaoId]);

  // ESC fecha
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, loading, onClose]);

  function reset() {
    setError(null);
    setDuplicateWarning(false);
  }

  async function submeter(forcar: boolean) {
    setError(null);
    if (!missaoId) {
      setError("Selecione uma missão.");
      return;
    }
    if (!dataInicio || !dataFim) {
      setError("Preencha as datas.");
      return;
    }
    if (new Date(dataFim) <= new Date(dataInicio)) {
      setError("A data de fim deve ser depois da data de início.");
      return;
    }
    setLoading(true);
    try {
      const resp = await criarAtividade({
        turma_id: turmaId,
        missao_id: missaoId,
        data_inicio: new Date(dataInicio).toISOString(),
        data_fim: new Date(dataFim).toISOString(),
        notificar_alunos: notificar,
        confirmar_duplicata: forcar,
      });

      if (resp.duplicate_warning) {
        setDuplicateWarning(true);
        return;
      }

      if (!resp.id) {
        setError("Resposta inesperada do servidor.");
        return;
      }

      const msg = notificar && resp.notificacao_disparada
        ? `Missão ativada e ${resp.notificacao_enviadas} aluno(s) notificado(s).`
        : "Missão ativada.";
      toast.success(msg);
      onCriada?.(resp.id);
      reset();
      onClose();
      router.push(`/atividade/${resp.id}`);
    } catch (err) {
      const e = err as ApiError;
      setError(e.detail || "Erro ao criar atividade.");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submeter(false);
  }

  function fechar() {
    if (loading) return;
    reset();
    onClose();
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ativar-missao-title"
    >
      <button
        type="button"
        aria-label="Fechar"
        onClick={fechar}
        className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
        tabIndex={-1}
      />
      <div className="relative w-full sm:max-w-lg bg-white rounded-t-2xl sm:rounded-2xl border border-border shadow-card p-5 sm:p-6 mx-0 sm:mx-4">
        <div className="mb-5">
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            Turma {turmaCodigo}
          </p>
          <h2 id="ativar-missao-title" className="font-display text-2xl mt-0.5">
            Ativar missão
          </h2>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FormField label="Missão" required>
            <select
              value={missaoId}
              onChange={(e) => {
                setMissaoId(e.target.value);
                setDuplicateWarning(false);
              }}
              disabled={loadingMissoes || loading}
              className="block w-full rounded-lg border border-border bg-white px-3.5 py-2.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime"
            >
              {loadingMissoes && <option>Carregando…</option>}
              {missoes.map((m) => (
                <option key={m.id} value={m.id}>
                  {formatMissaoLabel({
                    oficina_numero: m.oficina_numero,
                    titulo: m.titulo,
                    modo_correcao: m.modo_correcao,
                  })}
                </option>
              ))}
            </select>
          </FormField>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FormField label="Início" required>
              <Input
                type="datetime-local"
                value={dataInicio}
                onChange={(e) => setDataInicio(e.target.value)}
                disabled={loading}
              />
            </FormField>
            <FormField label="Fim" required>
              <Input
                type="datetime-local"
                value={dataFim}
                onChange={(e) => setDataFim(e.target.value)}
                disabled={loading}
              />
            </FormField>
          </div>

          <label className="flex items-start gap-2.5 text-sm cursor-pointer select-none p-2 -mx-2 hover:bg-muted rounded">
            <input
              type="checkbox"
              checked={notificar}
              onChange={(e) => setNotificar(e.target.checked)}
              disabled={loading}
              className="mt-0.5 rounded border-border accent-ink"
            />
            <span>
              <span className="block">
                Notificar alunos por WhatsApp agora
              </span>
              <span className="block text-xs text-ink-400 mt-0.5">
                Dispara mensagem na hora pra todos os alunos ativos da turma.
              </span>
            </span>
          </label>

          {duplicateWarning && (
            <div
              role="alert"
              className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5"
            >
              <p className="font-medium">Já existe uma atividade aberta pra essa turma e missão.</p>
              <p className="mt-1 text-amber-800">
                Continuar mesmo assim cria uma atividade paralela. Em geral
                você quer editar o prazo da existente em vez disso.
              </p>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2"
            >
              {error}
            </div>
          )}

          <div className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-1">
            <Button variant="ghost" onClick={fechar} disabled={loading}>
              Cancelar
            </Button>
            {duplicateWarning ? (
              <Button
                variant="primary"
                onClick={() => submeter(true)}
                loading={loading}
              >
                Criar mesmo assim
              </Button>
            ) : (
              <Button type="submit" variant="primary" loading={loading}>
                Ativar
              </Button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
