"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Logo } from "@/components/ui/Logo";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Hook pra Sentry/observabilidade futura
    console.error("[redato] runtime error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-muted">
      <Card className="w-full max-w-md text-center">
        <Logo size="lg" />
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mt-6">
          500
        </p>
        <h1 className="font-display text-2xl mt-1 mb-2">Algo deu errado</h1>
        <p className="text-sm text-ink-400">
          Tivemos um problema ao carregar essa página. Tente de novo em alguns
          segundos.
        </p>
        {error.digest && (
          <p className="text-xs font-mono text-ink-400 mt-3 break-all">
            id: {error.digest}
          </p>
        )}
        <div className="mt-6 flex gap-2 justify-center">
          <Button variant="primary" onClick={reset}>Tentar de novo</Button>
        </div>
      </Card>
    </div>
  );
}
