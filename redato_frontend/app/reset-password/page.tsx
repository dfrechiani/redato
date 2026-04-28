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
import * as authClient from "@/lib/auth-client";
import { ApiError } from "@/types/api";

function SolicitarReset() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [enviado, setEnviado] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email) {
      setError("Informe seu email.");
      return;
    }
    setLoading(true);
    try {
      await authClient.resetSolicitar(email);
      setEnviado(true);
    } catch (err) {
      const e = err as ApiError;
      setError(e.detail || "Erro inesperado.");
    } finally {
      setLoading(false);
    }
  }

  if (enviado) {
    return (
      <Card className="w-full max-w-md text-center">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-4 mb-2">Verifique seu email</h1>
        <p className="text-sm text-ink-400">
          Se o email estiver cadastrado, mandamos instruções pra redefinir
          a senha. O link vale por 2 horas.
        </p>
        <Link
          href="/login"
          className="inline-block mt-5 text-sm text-ink underline-offset-4 hover:underline"
        >
          ← Voltar ao login
        </Link>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <div className="text-center mb-6">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-3">Esqueceu a senha?</h1>
        <p className="mt-1 text-sm text-ink-400">
          Informe seu email cadastrado. Vamos enviar um link pra redefinir.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormField label="Email" required>
          <Input
            type="email"
            autoFocus
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="seu@email.com"
            disabled={loading}
          />
        </FormField>

        {error && (
          <div
            role="alert"
            className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2"
          >
            {error}
          </div>
        )}

        <Button type="submit" loading={loading} fullWidth size="lg">
          {loading ? "Enviando…" : "Enviar link de reset"}
        </Button>

        <Link
          href="/login"
          className="text-center text-sm text-ink-400 hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar ao login
        </Link>
      </form>
    </Card>
  );
}

function ConfirmarReset({ token }: { token: string }) {
  const router = useRouter();
  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const err = authClient.validarSenhaLocal(senha);
    if (err) return setError(err);
    if (senha !== confirmar) return setError("As senhas não conferem.");

    setLoading(true);
    try {
      await authClient.resetConfirmar(token, senha);
      toast.success("Senha redefinida. Entre com a nova senha.");
      router.push("/login");
    } catch (err) {
      const e = err as ApiError;
      if (e.status === 410) {
        setError("Este link expirou. Solicite um novo reset.");
      } else if (e.status === 404) {
        setError("Link inválido. Solicite um novo reset.");
      } else {
        setError(e.detail || "Erro inesperado.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <div className="text-center mb-6">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-3">Nova senha</h1>
        <p className="mt-1 text-sm text-ink-400">
          Defina sua nova senha de acesso.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          label="Nova senha"
          required
          hint="Mínimo 8 caracteres, com pelo menos 1 letra e 1 número."
        >
          <PasswordInput
            autoComplete="new-password"
            autoFocus
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            disabled={loading}
          />
        </FormField>

        <FormField label="Confirmar senha" required>
          <PasswordInput
            autoComplete="new-password"
            value={confirmar}
            onChange={(e) => setConfirmar(e.target.value)}
            disabled={loading}
          />
        </FormField>

        {error && (
          <div
            role="alert"
            className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2"
          >
            {error}
          </div>
        )}

        <Button type="submit" loading={loading} fullWidth size="lg">
          {loading ? "Redefinindo…" : "Redefinir senha"}
        </Button>
      </form>
    </Card>
  );
}

function ResetPasswordContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  return token
    ? <ConfirmarReset token={token} />
    : <SolicitarReset />;
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-muted">
      <Suspense
        fallback={
          <Card className="w-full max-w-md text-center text-ink-400">
            Carregando…
          </Card>
        }
      >
        <ResetPasswordContent />
      </Suspense>
    </div>
  );
}
