import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface Props {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: Props) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center py-12 px-6",
        "border-2 border-dashed border-border rounded-xl bg-muted",
        className,
      )}
    >
      {icon && (
        <div className="mb-4 text-ink-400" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="font-display text-lg text-ink mb-1.5">{title}</h3>
      {description && (
        <p className="text-sm text-ink-400 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
