"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { ModalConfirm } from "@/components/ui/ModalConfirm";
import { inativarAluno } from "@/lib/portal-client";
import { ApiError } from "@/types/api";
import type { AlunoTurma } from "@/types/portal";

interface Props {
  turmaId: string;
  aluno: AlunoTurma;
  onAlteracao?: () => void;
}

export function AlunoListItem({ turmaId, aluno, onAlteracao }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  async function confirmarRemover() {
    setLoading(true);
    try {
      await inativarAluno(turmaId, aluno.id, false);
      toast.success(`${aluno.nome} marcado como inativo.`);
      setOpen(false);
      onAlteracao?.();
    } catch (err) {
      const e = err as ApiError;
      toast.error(e.detail || "Erro ao remover aluno");
    } finally {
      setLoading(false);
    }
  }

  const dataEntrada = new Date(aluno.vinculado_em).toLocaleDateString("pt-BR");

  return (
    <li className="flex items-center justify-between gap-3 py-3 px-3 sm:px-4 hover:bg-muted rounded-lg">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium truncate">{aluno.nome}</p>
        <p className="text-xs text-ink-400 font-mono">
          {aluno.telefone_mascarado} · entrou em {dataEntrada}
        </p>
      </div>
      <div className="text-xs text-ink-400 hidden sm:block">
        {aluno.n_envios} envio{aluno.n_envios !== 1 ? "s" : ""}
      </div>
      <Button
        variant="ghost"
        size="md"
        onClick={() => setOpen(true)}
        className="text-danger hover:bg-danger/10 px-3"
        aria-label={`Remover ${aluno.nome} da turma`}
      >
        Remover
      </Button>
      <ModalConfirm
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={confirmarRemover}
        loading={loading}
        title={`Remover ${aluno.nome.split(" ")[0]} da turma?`}
        description="O aluno será marcado como inativo. Os envios e correções dele ficam preservados — só não aparece mais nas listagens. Você pode reativar depois."
        confirmLabel="Marcar inativo"
        confirmVariant="danger"
      />
    </li>
  );
}
