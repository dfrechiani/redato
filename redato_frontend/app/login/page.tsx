"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { Logo } from "@/components/ui/Logo";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { useAuth } from "@/hooks/useAuth";
import * as authClient from "@/lib/auth-client";
import { ApiError } from "@/types/api";

function isSafeFrom(from: string | null): from is string {
  return Boolean(from && from.startsWith("/") && !from.startsWith("//"));
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const from = params.get("from");
  const setUser = useAuth((s) => s.setUser);

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [lembrar, setLembrar] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!email || !senha) {
      setError("Preencha email e senha.");
      return;
    }

    setLoading(true);
    try {
      const user = await authClient.login(email, senha, lembrar);
      setUser(user);
      toast.success(`Bem-vindo, ${user.nome.split(" ")[0]}.`);
      const dest = isSafeFrom(from) ? from : "/";
      router.push(dest);
      router.refresh();
    } catch (err) {
      const e = err as ApiError;
      if (e.status === 401) {
        setError("Email ou senha incorretos.");
      } else if (e.status === 403) {
        setError("Sua conta está inativa. Fala com a coordenação da escola.");
      } else {
        setError(e.detail || "Erro inesperado. Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <div className="text-center mb-7">
        <Logo size="lg" />
        <p className="mt-2 text-sm text-ink-400">
          Portal do Professor — Projeto ATO
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormField label="Email" required>
          <Input
            type="email"
            inputMode="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="seu@email.com"
            disabled={loading}
          />
        </FormField>

        <FormField label="Senha" required>
          <PasswordInput
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            disabled={loading}
          />
        </FormField>

        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input
            type="checkbox"
            checked={lembrar}
            onChange={(e) => setLembrar(e.target.checked)}
            disabled={loading}
            className="rounded border-border accent-ink"
          />
          <span>Lembrar de mim por 30 dias</span>
        </label>

        {error && (
          <div
            role="alert"
            className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2"
          >
            {error}
          </div>
        )}

        <Button type="submit" loading={loading} fullWidth size="lg">
          {loading ? "Entrando…" : "Entrar"}
        </Button>

        <div className="text-center pt-1">
          <Link
            href="/reset-password"
            className="text-sm text-ink-400 hover:text-ink underline-offset-4 hover:underline"
          >
            Esqueci minha senha
          </Link>
        </div>
      </form>

      <p className="mt-6 pt-5 border-t border-border text-xs text-center text-ink-400">
        Acesso por convite. Sua escola recebe os dados de cadastro pela
        coordenação.
      </p>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-muted">
      <Suspense
        fallback={
          <Card className="w-full max-w-md text-center text-ink-400">
            Carregando…
          </Card>
        }
      >
        <LoginForm />
      </Suspense>
    </div>
  );
}
