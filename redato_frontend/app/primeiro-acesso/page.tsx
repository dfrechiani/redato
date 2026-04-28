"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Logo } from "@/components/ui/Logo";
import { PasswordInput } from "@/components/ui/PasswordInput";
import * as authClient from "@/lib/auth-client";
import { ApiError } from "@/types/api";
import type { PrimeiroAcessoValidarResponse } from "@/types/api";

type Estado =
  | { kind: "loading" }
  | { kind: "sem-token" }
  | { kind: "expirado" }
  | { kind: "invalido"; detail?: string }
  | { kind: "ok"; info: PrimeiroAcessoValidarResponse };

function PrimeiroAcessoForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [estado, setEstado] = useState<Estado>({ kind: "loading" });

  const [senha, setSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [submitErr, setSubmitErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setEstado({ kind: "sem-token" });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const info = await authClient.primeiroAcessoValidar(token);
        if (cancelled) return;
        setEstado({ kind: "ok", info });
      } catch (err) {
        if (cancelled) return;
        const e = err as ApiError;
        if (e.status === 410) setEstado({ kind: "expirado" });
        else setEstado({ kind: "invalido", detail: e.detail });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitErr(null);

    const err = authClient.validarSenhaLocal(senha);
    if (err) return setSubmitErr(err);
    if (senha !== confirmar) return setSubmitErr("As senhas não conferem.");

    setLoading(true);
    try {
      await authClient.primeiroAcessoDefinir(token, senha);
      toast.success("Senha definida. Entre com seu email e a nova senha.");
      router.push("/login");
    } catch (err) {
      const e = err as ApiError;
      if (e.status === 410) setEstado({ kind: "expirado" });
      else setSubmitErr(e.detail || "Erro inesperado.");
    } finally {
      setLoading(false);
    }
  }

  // Render por estado
  if (estado.kind === "loading") {
    return (
      <Card className="w-full max-w-md flex items-center justify-center gap-3 py-12">
        <LoadingSpinner size={20} />
        <span className="text-sm text-ink-400">Validando link…</span>
      </Card>
    );
  }

  if (estado.kind === "sem-token") {
    return (
      <Card className="w-full max-w-md text-center">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-4 mb-2">Link incompleto</h1>
        <p className="text-sm text-ink-400">
          A URL não tem token de primeiro acesso. Confere o link que veio no
          email — deve terminar com <code className="font-mono">?token=…</code>.
        </p>
      </Card>
    );
  }

  if (estado.kind === "expirado") {
    return (
      <Card className="w-full max-w-md text-center">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-4 mb-2">Link expirado</h1>
        <p className="text-sm text-ink-400">
          Esse link de primeiro acesso já passou da validade. Pede um novo
          ao admin do portal ou à coordenação da sua escola.
        </p>
      </Card>
    );
  }

  if (estado.kind === "invalido") {
    return (
      <Card className="w-full max-w-md text-center">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-4 mb-2">Link inválido</h1>
        <p className="text-sm text-ink-400">
          {estado.detail || "Não consegui validar esse link. Confere o email."}
        </p>
      </Card>
    );
  }

  // estado.kind === "ok"
  const { info } = estado;
  return (
    <Card className="w-full max-w-md">
      <div className="text-center mb-6">
        <Logo size="lg" />
        <h1 className="font-display text-xl mt-3">Defina sua senha</h1>
        <div className="mt-3 text-sm text-ink-400 space-y-0.5">
          <p>
            <span className="text-ink">{info.nome}</span> · {info.email}
          </p>
          {info.escola_nome && (
            <p className="capitalize">
              {info.papel} · {info.escola_nome}
            </p>
          )}
        </div>
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

        {submitErr && (
          <div
            role="alert"
            className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2"
          >
            {submitErr}
          </div>
        )}

        <Button type="submit" loading={loading} fullWidth size="lg">
          {loading ? "Definindo…" : "Definir senha e entrar"}
        </Button>
      </form>
    </Card>
  );
}

export default function PrimeiroAcessoPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-muted">
      <Suspense
        fallback={
          <Card className="w-full max-w-md text-center text-ink-400">
            Carregando…
          </Card>
        }
      >
        <PrimeiroAcessoForm />
      </Suspense>
    </div>
  );
}
