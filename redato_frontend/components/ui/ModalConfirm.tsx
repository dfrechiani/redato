"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "primary" | "danger" | "secondary";
  loading?: boolean;
  /** Conteúdo extra entre description e botões. */
  children?: ReactNode;
}

export function ModalConfirm({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  confirmVariant = "primary",
  loading = false,
  children,
}: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // ESC + click fora = close. Foco no diálogo quando abre.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) onClose();
    }
    document.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, loading, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-confirm-title"
    >
      <button
        type="button"
        aria-label="Fechar"
        onClick={() => !loading && onClose()}
        className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
        tabIndex={-1}
      />
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={cn(
          "relative w-full sm:max-w-md bg-white rounded-t-2xl sm:rounded-2xl",
          "border border-border shadow-card p-5 sm:p-6 mx-0 sm:mx-4",
          "animate-in fade-in slide-in-from-bottom-4 duration-150",
        )}
      >
        <h2
          id="modal-confirm-title"
          className="font-display text-xl"
        >
          {title}
        </h2>
        {description && (
          <div className="mt-2 text-sm text-ink-400">{description}</div>
        )}
        {children && <div className="mt-4">{children}</div>}
        <div className="mt-6 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={loading}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
