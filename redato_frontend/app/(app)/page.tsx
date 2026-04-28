import { EmptyState } from "@/components/ui/EmptyState";
import { TurmaCard } from "@/components/portal/TurmaCard";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import type { AuthenticatedUser } from "@/types/api";
import type { TurmaListItem } from "@/types/portal";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const token = getSessionToken();
  const [user, turmas] = await Promise.all([
    fetchBackend<AuthenticatedUser>("/auth/me", { bearer: token! }),
    fetchBackend<TurmaListItem[]>("/portal/turmas", { bearer: token! }),
  ]);

  const primeiroNome = user.nome.split(" ")[0] || user.nome;
  const ehProf = user.papel === "professor";
  const titulo = ehProf ? "Suas turmas" : "Turmas da escola";

  // Coordenador: agrupa turmas por professor.
  const grupos = new Map<string, { nome: string; turmas: TurmaListItem[] }>();
  if (!ehProf) {
    for (const t of turmas) {
      const g = grupos.get(t.professor_id) ?? {
        nome: t.professor_nome, turmas: [],
      };
      g.turmas.push(t);
      grupos.set(t.professor_id, g);
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Início
        </p>
        <h1 className="font-display text-3xl sm:text-4xl mt-1">
          Olá, {primeiroNome}.
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          {ehProf ? "Professora(o)" : "Coordenadora(o)"} de{" "}
          <span className="text-ink">{user.escola_nome}</span>.
        </p>
      </header>

      <section aria-labelledby="suas-turmas">
        <h2 id="suas-turmas" className="font-display text-xl mb-4">
          {titulo}
        </h2>

        {turmas.length === 0 ? (
          <EmptyState
            title="Nenhuma turma cadastrada"
            description={
              ehProf
                ? "A coordenação ainda não vinculou turmas ao seu nome. Fale com a coordenação da escola."
                : "Importe a planilha de turmas pelo painel admin pra começar. As turmas aparecem aqui assim que forem cadastradas."
            }
            icon={
              <svg
                width="48" height="48" viewBox="0 0 48 48" fill="none"
                xmlns="http://www.w3.org/2000/svg" aria-hidden="true"
              >
                <rect x="6" y="10" width="36" height="28" rx="4"
                      stroke="currentColor" strokeWidth="2" />
                <path d="M14 20h20M14 28h12" stroke="currentColor"
                      strokeWidth="2" strokeLinecap="round" />
              </svg>
            }
          />
        ) : ehProf ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {turmas.map((t) => (
              <TurmaCard key={t.id} turma={t} />
            ))}
          </div>
        ) : (
          <div className="space-y-8">
            {Array.from(grupos.entries()).map(([profId, g]) => (
              <div key={profId}>
                <h3 className="font-display text-base mb-3 flex items-center gap-2">
                  {g.nome}
                  <span className="font-body font-normal text-xs text-ink-400">
                    · {g.turmas.length} turma{g.turmas.length !== 1 ? "s" : ""}
                  </span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {g.turmas.map((t) => (
                    <TurmaCard key={t.id} turma={t} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
