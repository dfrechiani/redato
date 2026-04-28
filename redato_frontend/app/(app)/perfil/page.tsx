import Link from "next/link";

import { PerfilView } from "./PerfilView";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AuthenticatedUser } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function PerfilPage() {
  const token = getSessionToken();
  const user = await fetchBackend<AuthenticatedUser>("/auth/me", {
    bearer: token!,
  });
  return (
    <div>
      <nav aria-label="breadcrumb" className="mb-4 text-sm text-ink-400">
        <Link href="/" className="hover:text-ink underline-offset-4 hover:underline">
          ← Voltar pra início
        </Link>
      </nav>
      <PerfilView user={user} />
    </div>
  );
}
