import Link from "next/link";
import { redirect } from "next/navigation";

import { HistoricoPdfsList } from "@/components/portal/HistoricoPdfsList";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AuthenticatedUser } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function HistoricoEscolaPage() {
  const token = getSessionToken();
  const user = await fetchBackend<AuthenticatedUser>("/auth/me", {
    bearer: token!,
  });
  if (user.papel !== "coordenador") {
    redirect("/");
  }
  return (
    <div className="space-y-6">
      <nav aria-label="breadcrumb" className="text-sm text-ink-400">
        <Link
          href="/escola/dashboard"
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pro dashboard da escola
        </Link>
      </nav>
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          {user.escola_nome}
        </p>
        <h1 className="font-display text-3xl mt-1">Histórico de PDFs</h1>
        <p className="mt-1 text-sm text-ink-400">
          Todos os PDFs gerados nessa escola (qualquer turma). Política
          de retenção: 365 dias.
        </p>
      </header>
      <HistoricoPdfsList />
    </div>
  );
}
