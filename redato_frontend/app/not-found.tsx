import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Logo } from "@/components/ui/Logo";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-muted">
      <Card className="w-full max-w-md text-center">
        <Logo size="lg" />
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mt-6">
          404
        </p>
        <h1 className="font-display text-2xl mt-1 mb-2">Página não encontrada</h1>
        <p className="text-sm text-ink-400">
          O endereço acessado não existe ou foi movido.
        </p>
        <Link href="/" className="inline-block mt-6">
          <Button variant="primary">Voltar pro início</Button>
        </Link>
      </Card>
    </div>
  );
}
