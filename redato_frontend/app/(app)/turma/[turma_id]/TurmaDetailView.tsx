"use client";

import { useCallback, useState } from "react";

import { AlunoListItem } from "@/components/portal/AlunoListItem";
import { AtivarMissaoModal } from "@/components/portal/AtivarMissaoModal";
import { AtividadeCard } from "@/components/portal/AtividadeCard";
import { CodigoTurmaBox } from "@/components/portal/CodigoTurmaBox";
import { DashboardTurma } from "@/components/portal/DashboardTurma";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { formatSerie } from "@/lib/format";
import { detalheTurma } from "@/lib/portal-client";
import type { TurmaDetail } from "@/types/portal";

type Aba = "atividades" | "dashboard";

interface Props {
  initial: TurmaDetail;
}

export function TurmaDetailView({ initial }: Props) {
  const [data, setData] = useState<TurmaDetail>(initial);
  const [modalOpen, setModalOpen] = useState(false);
  const [showAlunos, setShowAlunos] = useState(false);
  const [aba, setAba] = useState<Aba>("atividades");

  const recarregar = useCallback(async () => {
    try {
      const novo = await detalheTurma(initial.id);
      setData(novo);
    } catch {
      /* já fez redirect em 401; outros erros silenciados — UI segue stale */
    }
  }, [initial.id]);

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            {data.escola_nome} · {formatSerie(data.serie)} · {data.ano_letivo}
          </p>
          <h1 className="font-display text-3xl mt-1">Turma {data.codigo}</h1>
          <p className="mt-1 text-sm text-ink-400">
            Professor(a): {data.professor_nome}
          </p>
        </div>
        {data.pode_criar_atividade && (
          <Button
            variant="secondary"
            size="lg"
            onClick={() => setModalOpen(true)}
          >
            + Ativar missão
          </Button>
        )}
      </header>

      <CodigoTurmaBox codigo={data.codigo_join} />

      {/* Tabs Atividades | Dashboard */}
      <nav role="tablist" className="border-b border-border flex gap-1">
        {([
          { id: "atividades" as Aba, label: "Atividades" },
          { id: "dashboard" as Aba, label: "Dashboard" },
        ]).map((t) => {
          const ativo = aba === t.id;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={ativo}
              onClick={() => setAba(t.id)}
              className={cn(
                "px-4 py-2 -mb-px text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime",
                ativo
                  ? "border-b-2 border-ink text-ink"
                  : "border-b-2 border-transparent text-ink-400 hover:text-ink",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </nav>

      {aba === "dashboard" && (
        <DashboardTurma turmaId={data.id} />
      )}

      {aba === "atividades" && (<>
      <section aria-labelledby="atividades-h">
        <div className="flex items-center justify-between mb-4">
          <h2 id="atividades-h" className="font-display text-xl">
            Atividades
          </h2>
          {data.atividades.length > 0 && (
            <span className="font-mono text-xs text-ink-400 uppercase tracking-wider">
              {data.atividades.length} ao todo
            </span>
          )}
        </div>
        {data.atividades.length === 0 ? (
          <EmptyState
            title="Nenhuma atividade ainda"
            description={
              data.pode_criar_atividade
                ? "Clique em '+ Ativar missão' pra criar a primeira atividade da turma."
                : "Aguarde o professor responsável criar uma atividade."
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {data.atividades.map((a) => (
              <AtividadeCard key={a.id} atividade={a} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="alunos-h" className="bg-muted rounded-xl p-1">
        <button
          type="button"
          onClick={() => setShowAlunos((s) => !s)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-white rounded-lg"
          aria-expanded={showAlunos}
          aria-controls="alunos-panel"
        >
          <span className="font-display text-lg" id="alunos-h">
            Alunos cadastrados ({data.alunos.length})
          </span>
          <span className="font-mono text-xs text-ink-400 uppercase tracking-wider">
            {showAlunos ? "ocultar" : "ver lista"}
          </span>
        </button>
        {showAlunos && (
          <div id="alunos-panel" className="bg-white rounded-lg mt-1 p-2">
            {data.alunos.length === 0 ? (
              <p className="px-4 py-6 text-sm text-ink-400 text-center">
                Nenhum aluno ativo nesta turma. Importe pela planilha
                via painel admin.
              </p>
            ) : (
              <ul role="list" className="divide-y divide-border">
                {data.alunos.map((a) => (
                  <AlunoListItem
                    key={a.id}
                    turmaId={data.id}
                    aluno={a}
                    onAlteracao={recarregar}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      </>)}

      <AtivarMissaoModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        turmaId={data.id}
        turmaCodigo={data.codigo}
        onCriada={recarregar}
      />
    </div>
  );
}
