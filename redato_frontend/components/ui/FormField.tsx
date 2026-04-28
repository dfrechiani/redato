"use client";

import { useId, type ReactElement, type ReactNode } from "react";

import { cn } from "@/lib/cn";

interface Props {
  label: string;
  error?: string | null;
  hint?: string;
  required?: boolean;
  className?: string;
  /** Recebe `id` e `aria-invalid` injetados via cloneElement. */
  children: ReactElement;
}

export function FormField({
  label,
  error,
  hint,
  required,
  className,
  children,
}: Props) {
  const reactId = useId();
  const id = `f-${reactId}`;
  const errId = error ? `${id}-err` : undefined;
  const hintId = hint && !error ? `${id}-hint` : undefined;

  // Inject id + a11y props into child
  const child = {
    ...children,
    props: {
      ...children.props,
      id,
      "aria-invalid": Boolean(error) || undefined,
      "aria-describedby": errId ?? hintId,
      invalid: Boolean(error),
    },
  };

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label
        htmlFor={id}
        className="text-sm font-medium text-ink-800"
      >
        {label}
        {required && (
          <span className="text-danger ml-0.5" aria-hidden="true">*</span>
        )}
      </label>
      {child as ReactNode}
      {error ? (
        <p id={errId} className="text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-ink-400">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
