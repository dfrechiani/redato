"use client";

import { useState } from "react";
import { toast } from "sonner";

import { cn } from "@/lib/cn";

interface Props {
  codigo: string;
}

export function CodigoTurmaBox({ codigo }: Props) {
  const [copiado, setCopiado] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(codigo);
      setCopiado(true);
      toast.success("Copiado!");
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      toast.error("Não consegui copiar. Selecione e copie manualmente.");
    }
  }

  return (
    <div className="bg-ink text-white rounded-xl p-5 flex items-center justify-between gap-4">
      <div className="min-w-0">
        <p className="font-mono text-xs uppercase tracking-wider text-ink-200">
          Código de turma
        </p>
        <p className="font-mono text-lg sm:text-xl mt-1 break-all select-all">
          {codigo}
        </p>
        <p className="text-xs text-ink-200 mt-2">
          Compartilhe com a turma. Cada aluno manda esse código no
          WhatsApp pra se cadastrar.
        </p>
      </div>
      <button
        type="button"
        onClick={copiar}
        aria-label={copiado ? "Código copiado" : "Copiar código"}
        className={cn(
          "shrink-0 inline-flex items-center gap-2 px-4 h-10 rounded-lg font-medium text-sm",
          "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime",
          copiado
            ? "bg-lime text-lime-ink"
            : "bg-white text-ink hover:bg-ink-100",
        )}
      >
        {copiado ? "Copiado" : "Copiar"}
      </button>
    </div>
  );
}
