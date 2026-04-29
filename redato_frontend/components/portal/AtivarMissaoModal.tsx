"use client";

import { useEffect, useState, type FormEvent } from "react";
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
  /** Série da turma (1S/2S/3S). Filtra dropdown de missões: turma 1S
   *  só lista oficinas 1S etc. */
  turmaSerie: string;
  /** Disparado após criar (com sucesso). Use pra recarregar a turma. */
  onCriada?: (atividadeId: string) => void;
}

// Formata Date local pro formato `<input type="datetime-local">`
// (`YYYY-MM-DDTHH:MM`, zero-padded, hora local do navegador).
function fmtDatetimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function defaultDates() {
  const hoje = new Date();
  hoje.setSeconds(0, 0);
  const fim = new Date(hoje);
  fim.setDate(fim.getDate() + 7);
  fim.setHours(23, 59, 0, 0);
  return { inicio: fmtDatetimeLocal(hoje), fim: fmtDatetimeLocal(fim) };
}

export function AtivarMissaoModal({
  open,
  onClose,
  turmaId,
  turmaCodigo,
  turmaSerie,
  onCriada,
}: Props) {
  const router = useRouter();
  const [missoes, setMissoes] = useState<Missao[]>([]);
  const [loadingMissoes, setLoadingMissoes] = useState(true);
  const [missaoId, setMissaoId] = useState("");
  // Defaults inicializam com `defaultDates()` calculado UMA vez, mas
  // o `useEffect([open])` abaixo recalcula sempre que o modal abre —
  // antes esse cálculo ficava em `useMemo([])` e congelava na hora do
  // primeiro mount. Bug de produção: professor abria modal de manhã,
  // criava atividade à tarde, `data_inicio` ficava com hora da manhã.
  const initial = defaultDates();
  const [dataInicio, setDataInicio] = useState(initial.inicio);
  const [dataFim, setDataFim] = useState(initial.fim);
  // "Iniciar agora" é o caso padrão (~95% das atividades). Quando
  // marcado, ignoramos o input `dataInicio` e enviamos `new Date()`
  // ao backend no MOMENTO do clique em Ativar. Elimina toda
  // dependência de timezone do navegador, comportamento de picker no
  // iOS, e valor congelado no estado.
  const [iniciarAgora, setIniciarAgora] = useState(true);
  const [notificar, setNotificar] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState(false);
  const [loading, setLoading] = useState(false);

  // Recalcula defaults toda vez que o modal abre (evita hora congelada
  // se o componente fica vivo entre aberturas) e reseta a flag
  // "Iniciar agora" pro padrão.
  useEffect(() => {
    if (!open) return;
    const fresh = defaultDates();
    setDataInicio(fresh.inicio);
    setDataFim(fresh.fim);
    setIniciarAgora(true);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingMissoes(true);
    // Filtra catálogo pela série da turma — turma 1S não deve ver
    // oficinas 2S/3S no dropdown.
    listarMissoes(turmaSerie)
      .then((ms) => {
        if (cancelled) return;
        setMissoes(ms);
        // Auto-seleciona primeira missão DISPONÍVEL pra ativação
        // (modos sem schema aparecem na lista mas como `disabled`).
        if (!missaoId) {
          const primeiraDisponivel = ms.find((m) => m.disponivel_para_ativacao);
          if (primeiraDisponivel) setMissaoId(primeiraDisponivel.id);
        }
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
  }, [open, missaoId, turmaSerie]);

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
    if (!dataFim) {
      setError("Preencha a data de fim.");
      return;
    }
    // `data_inicio` final: se "Iniciar agora" está marcado, usa o
    // momento EXATO do clique (não o valor estado-do-input, que pode
    // estar desatualizado). Senão, parseia o input local pra ISO UTC.
    const dataInicioISO = iniciarAgora
      ? new Date().toISOString()
      : (dataInicio
          ? new Date(dataInicio).toISOString()
          : "");
    if (!dataInicioISO) {
      setError("Preencha a data de início (ou marque 'Iniciar agora').");
      return;
    }
    if (new Date(dataFim) <= new Date(dataInicioISO)) {
      setError("A data de fim deve ser depois da data de início.");
      return;
    }
    setLoading(true);
    try {
      const resp = await criarAtividade({
        turma_id: turmaId,
        missao_id: missaoId,
        data_inicio: dataInicioISO,
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
              {missoes.map((m) => {
                const baseLabel = formatMissaoLabel({
                  oficina_numero: m.oficina_numero,
                  titulo: m.titulo,
                  modo_correcao: m.modo_correcao,
                });
                // Modos sem schema (foco_c1/c2 hoje) aparecem na lista
                // pra dar visibilidade pedagógica, mas ficam bloqueados
                // até a rubrica ser implementada (Op. B do plano M9).
                const indisponivel = !m.disponivel_para_ativacao;
                const label = indisponivel
                  ? `${baseLabel} — em desenvolvimento`
                  : baseLabel;
                return (
                  <option
                    key={m.id}
                    value={m.id}
                    disabled={indisponivel}
                    title={
                      indisponivel
                        ? "Rubrica em desenvolvimento. Disponível em breve."
                        : undefined
                    }
                  >
                    {label}
                  </option>
                );
              })}
            </select>
          </FormField>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FormField label="Início" required>
              {iniciarAgora ? (
                <div
                  className="block w-full rounded-lg border border-border bg-muted px-3.5 py-2.5 text-sm text-ink-400 select-none"
                  aria-label="Início definido como agora"
                >
                  Agora (no momento de criar)
                </div>
              ) : (
                <Input
                  type="datetime-local"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                  disabled={loading}
                />
              )}
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

          {/* Default "Iniciar agora" cobre o caso comum (~95% das
              ativações) e elimina ambiguidade de timezone/picker. Se
              o professor quer agendar pro futuro, desmarca. */}
          <label className="flex items-start gap-2.5 text-sm cursor-pointer select-none p-2 -mx-2 hover:bg-muted rounded">
            <input
              type="checkbox"
              checked={iniciarAgora}
              onChange={(e) => setIniciarAgora(e.target.checked)}
              disabled={loading}
              className="mt-0.5 rounded border-border accent-ink"
            />
            <span>
              <span className="block">
                Iniciar agora
              </span>
              <span className="block text-xs text-ink-400 mt-0.5">
                Atividade fica ativa imediatamente após criar. Desmarque
                pra agendar pra depois.
              </span>
            </span>
          </label>

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
