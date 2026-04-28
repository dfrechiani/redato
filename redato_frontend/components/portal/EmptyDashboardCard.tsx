import type { ReactNode } from "react";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

interface Props {
  title: string;
  description?: string;
  icon?: ReactNode;
  /** Variante "positivo" pra ausência boa (zero alunos em risco). */
  positive?: boolean;
  className?: string;
}

const DefaultIcon = () => (
  <svg
    width="40" height="40" viewBox="0 0 40 40" fill="none"
    xmlns="http://www.w3.org/2000/svg" aria-hidden="true"
  >
    <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="2" />
    <path d="M14 20h12M20 14v12" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" />
  </svg>
);

const PositiveIcon = () => (
  <svg
    width="40" height="40" viewBox="0 0 40 40" fill="none"
    xmlns="http://www.w3.org/2000/svg" aria-hidden="true"
  >
    <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="2" />
    <path d="M13 21l5 5 9-12" stroke="currentColor" strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/**
 * Estado vazio padronizado pros cards de dashboard. Mensagem curta,
 * ícone discreto. `positive=true` usa cor lime e ícone de check pra
 * "ausência boa" (ex.: nenhum aluno em risco).
 */
export function EmptyDashboardCard({
  title,
  description,
  icon,
  positive = false,
  className,
}: Props) {
  return (
    <Card
      className={cn(
        "flex flex-col items-center text-center py-8 px-5",
        className,
      )}
    >
      <div
        className={cn(
          "mb-3",
          positive ? "text-lime" : "text-ink-400",
        )}
      >
        {icon ?? (positive ? <PositiveIcon /> : <DefaultIcon />)}
      </div>
      <p className="font-display text-base">{title}</p>
      {description && (
        <p className="text-sm text-ink-400 mt-1 max-w-xs">{description}</p>
      )}
    </Card>
  );
}
