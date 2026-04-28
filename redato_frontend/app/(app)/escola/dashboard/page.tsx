import Link from "next/link";
import { redirect } from "next/navigation";

import { EscolaDashboardView } from "./EscolaDashboardView";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AuthenticatedUser } from "@/types/api";
import type { EscolaDashboard } from "@/types/portal";

export const dynamic = "force-dynamic";

export default async function EscolaDashboardPage() {
  const token = getSessionToken();
  const user = await fetchBackend<AuthenticatedUser>("/auth/me", {
    bearer: token!,
  });
  if (user.papel !== "coordenador") {
    redirect("/");
  }
  const data = await fetchBackend<EscolaDashboard>(
    `/portal/escolas/${user.escola_id}/dashboard`,
    { bearer: token! },
  );
  return (
    <div>
      <nav aria-label="breadcrumb" className="mb-4 text-sm text-ink-400">
        <Link href="/" className="hover:text-ink underline-offset-4 hover:underline">
          ← Voltar pra início
        </Link>
      </nav>
      <EscolaDashboardView initial={data} />
    </div>
  );
}
