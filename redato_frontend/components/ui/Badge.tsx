import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Variant = "neutral" | "ativa" | "agendada" | "encerrada" | "warning" | "lime";

interface Props {
  children: ReactNode;
  variant?: Variant;
  className?: string;
}

const styles: Record<Variant, string> = {
  neutral: "bg-ink-100 text-ink-800",
  ativa: "bg-emerald-100 text-emerald-800",
  agendada: "bg-blue-100 text-blue-800",
  encerrada: "bg-ink-100 text-ink-400",
  warning: "bg-amber-100 text-amber-800",
  lime: "bg-lime text-lime-ink",
};

export function Badge({ children, variant = "neutral", className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
        "uppercase tracking-wide font-mono",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
