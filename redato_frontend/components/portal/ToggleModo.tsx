"use client";

import { cn } from "@/lib/cn";

export type ModoFiltro = "foco" | "completo" | "todos";

interface Props {
  value: ModoFiltro;
  onChange: (m: ModoFiltro) => void;
  className?: string;
  /** Esconde uma das opções se não há dados (ex.: turma sem envios Foco). */
  disabledOptions?: ModoFiltro[];
}

const OPCOES: Array<{ value: ModoFiltro; label: string }> = [
  { value: "todos", label: "Todos" },
  { value: "foco", label: "Foco" },
  { value: "completo", label: "Completo" },
];

export function ToggleModo({
  value, onChange, className, disabledOptions = [],
}: Props) {
  return (
    <div
      role="tablist"
      aria-label="Filtrar por modo de correção"
      className={cn(
        "inline-flex bg-muted rounded-lg p-1 gap-0.5",
        className,
      )}
    >
      {OPCOES.map((o) => {
        const ativo = o.value === value;
        const desabilitado = disabledOptions.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={ativo}
            aria-disabled={desabilitado}
            disabled={desabilitado}
            onClick={() => !desabilitado && onChange(o.value)}
            className={cn(
              "px-3 h-8 text-xs font-medium rounded transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime",
              ativo
                ? "bg-white text-ink shadow-sm"
                : "text-ink-400 hover:text-ink",
              desabilitado && "opacity-40 cursor-not-allowed",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
