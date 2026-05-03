"use client";

import Link from "next/link";
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

/**
 * Item da lista "Alunos cadastrados" na página da turma.
 *
 * M9.7: nome+meta viraram link clicável pro perfil
 * (`/turma/{id}/aluno/{aluno_id}`). O botão "Remover" mantém-se à
 * direita FORA do link pra evitar clique acidental — clique no
 * botão abre modal de confirmação com `stopPropagation` no Link
 * (Next.js: <Link> wrapping não captura evento do <button> interno
 * porque o botão chama setOpen sem propagar pra navegação).
 */
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
    <li className="flex items-center gap-2 py-3 px-3 sm:px-4 hover:bg-muted rounded-lg">
      <Link
        href={`/turma/${turmaId}/aluno/${aluno.id}`}
        className="flex items-center gap-3 min-w-0 flex-1 group"
        aria-label={`Abrir perfil de ${aluno.nome}`}
      >
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate group-hover:text-ink">
            {aluno.nome}
          </p>
          <p className="text-xs text-ink-400 font-mono">
            {aluno.telefone_mascarado} · entrou em {dataEntrada}
          </p>
        </div>
        <div className="text-xs text-ink-400 hidden sm:block">
          {aluno.n_envios} envio{aluno.n_envios !== 1 ? "s" : ""}
        </div>
        <span
          className="text-ink-400 group-hover:text-ink shrink-0 ml-2"
          aria-hidden="true"
        >
          ›
        </span>
      </Link>
      <Button
        variant="ghost"
        size="md"
        onClick={(e) => {
          // Stop propagation pra garantir que o Link irmão não seja
          // ativado se layout vier a aninhá-los no futuro.
          e.stopPropagation();
          setOpen(true);
        }}
        className="text-danger hover:bg-danger/10 px-3 shrink-0"
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
