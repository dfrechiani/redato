import { redirect } from "next/navigation";

import { AuthHydrator } from "@/components/layout/AuthHydrator";
import { Header } from "@/components/layout/Header";
import { fetchBackend } from "@/lib/api";
import { clearSessionCookies, getSessionToken } from "@/lib/auth-server";
import { ApiError, type AuthenticatedUser } from "@/types/api";

/**
 * Layout do app autenticado. Faz a chamada server-side em /auth/me usando
 * o cookie httpOnly. Se falhar com 401, limpa cookies e manda pra /login.
 *
 * Middleware já bloqueia acesso sem cookie. Esse layout fecha o caso de
 * cookie presente mas inválido (token revogado/expirado).
 */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const token = getSessionToken();
  if (!token) {
    redirect("/login");
  }

  let user: AuthenticatedUser;
  try {
    user = await fetchBackend<AuthenticatedUser>("/auth/me", { bearer: token });
  } catch (err) {
    const e = err as ApiError;
    if (e.status === 401 || e.status === 403) {
      clearSessionCookies();
      redirect("/login");
    }
    throw err;
  }

  return (
    <>
      <AuthHydrator initialUser={user} />
      <Header />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {children}
      </main>
    </>
  );
}
