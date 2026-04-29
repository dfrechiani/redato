"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { ModalConfirm } from "@/components/ui/ModalConfirm";
import {
  criarPartida, deletarPartida, patchPartida,
} from "@/lib/portal-client";
import { formatPrazo } from "@/lib/format";
import type {
  MinideckResumo, PartidaResumo, StatusPartida,
} from "@/types/portal";

interface AlunoSimples {
  aluno_turma_id: string;
  nome: string;
}

interface Props {
  atividadeId: string;
  alunosDaTurma: AlunoSimples[];
  initialPartidas: PartidaResumo[];
  minidecks: MinideckResumo[];
}

/** Mapeia status_partida → variant do Badge + label legível. */
function statusBadge(s: StatusPartida): { variant: "neutral" | "warning" | "ativa"; label: string } {
  if (s === "aguardando_cartas") {
    return { variant: "warning", label: "Aguardando cartas" };
  }
  if (s === "aguardando_reescritas") {
    return { variant: "warning", label: "Aguardando reescritas" };
  }
  return { variant: "ativa", label: "Concluída" };
}


/** Calcula default ISO 8601 com offset BRT pra `prazo_reescrita`:
 *  7 dias a partir de agora, às 22:00 horário de Brasília. */
function defaultPrazoBrt(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  d.setHours(22, 0, 0, 0);
  // toLocaleString("sv-SE") gera YYYY-MM-DD HH:mm:ss; convertemos pro
  // formato ISO com offset -03:00 (BRT padrão; sem horário de verão
  // desde 2019). datetime-local <input> consome esse formato pré-offset.
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
}


/** Converte valor de <input type="datetime-local"> (sem tz) pra
 *  ISO 8601 BRT (-03:00) — backend exige aware datetime. */
function localToIsoBrt(localValue: string): string {
  // localValue: "2026-05-06T22:00"
  return `${localValue}:00-03:00`;
}


export function PartidasView({
  atividadeId, alunosDaTurma, initialPartidas, minidecks,
}: Props) {
  const router = useRouter();
  const [partidas, setPartidas] = useState(initialPartidas);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<PartidaResumo | null>(null);
  const [deleting, setDeleting] = useState<PartidaResumo | null>(null);

  async function handleAfterMutation() {
    // Re-fetch via router.refresh() não é confiável aqui (RSC não
    // sabe que precisa rebuscar partidas). Forçamos via fetch direto.
    const r = await fetch(
      `/api/portal/atividades/${atividadeId}/partidas`,
      { credentials: "same-origin" },
    );
    if (r.ok) {
      setPartidas(await r.json());
    } else {
      // Fallback: server reload
      router.refresh();
    }
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-400">
          {partidas.length === 0
            ? "Nenhuma partida cadastrada nesta atividade."
            : `${partidas.length} partida${partidas.length > 1 ? "s" : ""} cadastrada${partidas.length > 1 ? "s" : ""}`}
        </p>
        <Button onClick={() => setCreating(true)}>
          + Cadastrar partida
        </Button>
      </div>

      {partidas.length === 0 ? (
        <Card>
          <p className="text-ink-400 text-sm">
            Cadastre uma partida pra cada grupo da turma. Cada grupo
            recebe um tema e tem prazo pra a reescrita individual via
            WhatsApp.
          </p>
        </Card>
      ) : (
        <ul className="space-y-3">
          {partidas.map((p) => {
            const sb = statusBadge(p.status_partida);
            return (
              <li key={p.id}>
                <Card>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-display text-xl">
                          {p.grupo_codigo}
                        </h3>
                        <Badge variant={sb.variant}>{sb.label}</Badge>
                      </div>
                      <dl className="text-sm space-y-1">
                        <div className="flex gap-2">
                          <dt className="text-ink-400 w-24">Tema:</dt>
                          <dd>{p.nome_humano_tema}</dd>
                        </div>
                        <div className="flex gap-2">
                          <dt className="text-ink-400 w-24">Alunos:</dt>
                          <dd>
                            {p.alunos.length === 0 ? (
                              <span className="text-ink-400 italic">
                                (nenhum aluno)
                              </span>
                            ) : (
                              p.alunos.map((a) => a.nome).join(", ")
                            )}
                          </dd>
                        </div>
                        <div className="flex gap-2">
                          <dt className="text-ink-400 w-24">Prazo:</dt>
                          <dd>{formatPrazo(p.prazo_reescrita)}</dd>
                        </div>
                        <div className="flex gap-2">
                          <dt className="text-ink-400 w-24">Reescritas:</dt>
                          <dd>
                            {p.n_reescritas}/{p.n_alunos}
                          </dd>
                        </div>
                      </dl>
                    </div>
                    <div className="flex flex-col gap-2 shrink-0">
                      <Button
                        variant="ghost" size="md"
                        onClick={() => setEditing(p)}
                      >
                        Editar
                      </Button>
                      <Button
                        variant="danger" size="md"
                        onClick={() => setDeleting(p)}
                      >
                        Apagar
                      </Button>
                    </div>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      {creating && (
        <PartidaFormModal
          atividadeId={atividadeId}
          alunosDaTurma={alunosDaTurma}
          minidecks={minidecks}
          onClose={() => setCreating(false)}
          onSaved={async () => {
            setCreating(false);
            await handleAfterMutation();
          }}
        />
      )}

      {editing && (
        <PartidaFormModal
          mode="edit"
          atividadeId={atividadeId}
          alunosDaTurma={alunosDaTurma}
          minidecks={minidecks}
          partida={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await handleAfterMutation();
          }}
        />
      )}

      {deleting && (
        <ModalConfirm
          open={true}
          onClose={() => setDeleting(null)}
          title={`Apagar "${deleting.grupo_codigo}"?`}
          description={
            deleting.n_reescritas > 0
              ? `Esta partida tem ${deleting.n_reescritas} reescrita(s) — não é possível apagar. Edite o prazo se quiser estender.`
              : "Tem certeza? Esta operação não pode ser desfeita."
          }
          confirmLabel="Apagar"
          cancelLabel="Cancelar"
          confirmVariant="danger"
          onConfirm={async () => {
            try {
              await deletarPartida(deleting.id);
              setDeleting(null);
              await handleAfterMutation();
            } catch (err) {
              alert(`Erro: ${(err as Error).message}`);
            }
          }}
        />
      )}
    </>
  );
}


// ──────────────────────────────────────────────────────────────────────
// Modal de cadastro/edição
// ──────────────────────────────────────────────────────────────────────

interface FormModalProps {
  mode?: "create" | "edit";
  atividadeId: string;
  alunosDaTurma: AlunoSimples[];
  minidecks: MinideckResumo[];
  partida?: PartidaResumo;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}

function PartidaFormModal({
  mode = "create",
  atividadeId, alunosDaTurma, minidecks, partida, onClose, onSaved,
}: FormModalProps) {
  const isEdit = mode === "edit" && partida !== undefined;

  const [grupoCodigo, setGrupoCodigo] = useState(
    partida?.grupo_codigo ?? "",
  );
  const [tema, setTema] = useState(
    partida?.tema ?? minidecks[0]?.tema ?? "",
  );
  const [selectedAlunos, setSelectedAlunos] = useState<Set<string>>(
    new Set(partida?.alunos.map((a) => a.aluno_turma_id) ?? []),
  );
  // Inicializa o input datetime-local com prazo existente OU default 7d
  const [prazoLocal, setPrazoLocal] = useState(() => {
    if (partida?.prazo_reescrita) {
      // ISO UTC → BRT local pro <input>
      const d = new Date(partida.prazo_reescrita);
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      const dd = String(d.getDate()).padStart(2, "0");
      const hh = String(d.getHours()).padStart(2, "0");
      const mi = String(d.getMinutes()).padStart(2, "0");
      return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
    }
    return defaultPrazoBrt();
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleAluno(id: string) {
    setSelectedAlunos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!grupoCodigo.trim()) {
      setError("Informe um código pro grupo");
      return;
    }
    if (selectedAlunos.size === 0) {
      setError("Selecione pelo menos 1 aluno");
      return;
    }
    setBusy(true);
    try {
      if (isEdit && partida) {
        await patchPartida(partida.id, {
          grupo_codigo: grupoCodigo,
          alunos_turma_ids: Array.from(selectedAlunos),
          prazo_reescrita: localToIsoBrt(prazoLocal),
        });
      } else {
        await criarPartida({
          atividade_id: atividadeId,
          tema,
          grupo_codigo: grupoCodigo,
          alunos_turma_ids: Array.from(selectedAlunos),
          prazo_reescrita: localToIsoBrt(prazoLocal),
        });
      }
      await onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="partida-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-card rounded-lg shadow-lg max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <h2 id="partida-modal-title" className="font-display text-2xl">
            {isEdit ? "Editar partida" : "Cadastrar nova partida"}
          </h2>

          <FormField label="Código do grupo" required>
            <Input
              type="text" value={grupoCodigo}
              onChange={(e) => setGrupoCodigo(e.target.value)}
              placeholder="Ex.: Grupo Azul"
              required maxLength={120}
            />
          </FormField>

          {/* Tema só edita na criação — backend bloqueia mudança de
              tema (criar partida nova se precisar trocar). FormField
              espera 1 elemento filho então usamos um wrapper. */}
          {!isEdit ? (
            <FormField label="Tema do minideck" required>
              <select
                className="w-full rounded border border-border bg-card px-3 py-2 text-sm"
                value={tema}
                onChange={(e) => setTema(e.target.value)}
                required
              >
                {minidecks.map((m) => (
                  <option key={m.tema} value={m.tema}>
                    {m.nome_humano} ({m.total_cartas} cartas)
                  </option>
                ))}
              </select>
            </FormField>
          ) : (
            <FormField
              label="Tema do minideck"
              hint="Imutável — crie partida nova pra trocar"
            >
              <div className="text-sm text-ink-400 px-3 py-2 bg-muted rounded">
                {partida?.nome_humano_tema}
              </div>
            </FormField>
          )}

          <FormField
            label="Alunos do grupo" required
            hint={`${selectedAlunos.size} aluno(s) selecionado(s)`}
          >
            <div
              className="space-y-1 max-h-48 overflow-y-auto border border-border rounded p-2"
            >
              {alunosDaTurma.length === 0 && (
                <p className="text-sm text-ink-400">
                  Turma sem alunos ativos.
                </p>
              )}
              {alunosDaTurma.map((a) => (
                <label
                  key={a.aluno_turma_id}
                  className="flex items-center gap-2 text-sm cursor-pointer hover:bg-muted px-2 py-1 rounded"
                >
                  <input
                    type="checkbox"
                    checked={selectedAlunos.has(a.aluno_turma_id)}
                    onChange={() => toggleAluno(a.aluno_turma_id)}
                  />
                  {a.nome}
                </label>
              ))}
            </div>
          </FormField>

          <FormField label="Prazo (horário de Brasília)" required>
            <Input
              type="datetime-local"
              value={prazoLocal}
              onChange={(e) => setPrazoLocal(e.target.value)}
              required
            />
          </FormField>

          {error && (
            <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button" variant="ghost"
              onClick={onClose} disabled={busy}
            >
              Cancelar
            </Button>
            <Button type="submit" loading={busy}>
              {isEdit ? "Salvar" : "Cadastrar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
