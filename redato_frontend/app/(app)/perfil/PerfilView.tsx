"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { ModalConfirm } from "@/components/ui/ModalConfirm";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { useAuth } from "@/hooks/useAuth";
import { validarSenhaLocal } from "@/lib/auth-client";
import { mudarSenha, sairTodasSessoes } from "@/lib/portal-client";
import { ApiError, type AuthenticatedUser } from "@/types/api";

interface Props {
  user: AuthenticatedUser;
}

export function PerfilView({ user }: Props) {
  const router = useRouter();
  const clearAuth = useAuth((s) => s.clear);

  const [modalSenhaOpen, setModalSenhaOpen] = useState(false);
  const [senhaAtual, setSenhaAtual] = useState("");
  const [senhaNova, setSenhaNova] = useState("");
  const [senhaConfirmar, setSenhaConfirmar] = useState("");
  const [senhaErr, setSenhaErr] = useState<string | null>(null);
  const [senhaLoading, setSenhaLoading] = useState(false);

  const [modalSairOpen, setModalSairOpen] = useState(false);
  const [sairLoading, setSairLoading] = useState(false);

  function resetForm() {
    setSenhaAtual("");
    setSenhaNova("");
    setSenhaConfirmar("");
    setSenhaErr(null);
  }

  async function onSubmitSenha(e: FormEvent) {
    e.preventDefault();
    setSenhaErr(null);
    if (!senhaAtual) return setSenhaErr("Informe sua senha atual.");
    const err = validarSenhaLocal(senhaNova);
    if (err) return setSenhaErr(err);
    if (senhaNova !== senhaConfirmar) {
      return setSenhaErr("A confirmação não bate com a nova senha.");
    }
    setSenhaLoading(true);
    try {
      await mudarSenha(senhaAtual, senhaNova);
      toast.success("Senha alterada.");
      setModalSenhaOpen(false);
      resetForm();
    } catch (err2) {
      setSenhaErr((err2 as ApiError).detail || "Erro ao alterar senha.");
    } finally {
      setSenhaLoading(false);
    }
  }

  async function onConfirmSair() {
    setSairLoading(true);
    try {
      await sairTodasSessoes();
      toast.success("Sessões encerradas. Faça login de novo.");
      clearAuth();
      router.push("/login");
    } catch (err) {
      toast.error((err as ApiError).detail || "Erro ao sair.");
    } finally {
      setSairLoading(false);
      setModalSairOpen(false);
    }
  }

  const papelLabel = user.papel === "coordenador" ? "Coordenador(a)" : "Professor(a)";

  return (
    <div className="space-y-6">
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Conta
        </p>
        <h1 className="font-display text-3xl mt-1">Perfil</h1>
      </header>

      <Card>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <dt className="font-mono text-xs uppercase tracking-wider text-ink-400">
              Nome
            </dt>
            <dd className="text-base mt-1">{user.nome}</dd>
          </div>
          <div>
            <dt className="font-mono text-xs uppercase tracking-wider text-ink-400">
              Email
            </dt>
            <dd className="text-base mt-1">{user.email}</dd>
          </div>
          <div>
            <dt className="font-mono text-xs uppercase tracking-wider text-ink-400">
              Papel
            </dt>
            <dd className="text-base mt-1">{papelLabel}</dd>
          </div>
          <div>
            <dt className="font-mono text-xs uppercase tracking-wider text-ink-400">
              Escola
            </dt>
            <dd className="text-base mt-1">{user.escola_nome}</dd>
          </div>
        </dl>
        <p className="text-xs text-ink-400 mt-5 pt-4 border-t border-border">
          Pra trocar nome, email ou escola, fale com a coordenação. Esses
          campos são gerenciados via importação de planilha.
        </p>
      </Card>

      <Card>
        <h2 className="font-display text-lg mb-1">Segurança</h2>
        <p className="text-sm text-ink-400 mb-4">
          Mude sua senha periodicamente. Se desconfia que alguém tem
          acesso, encerre todas as sessões.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button variant="primary" onClick={() => setModalSenhaOpen(true)}>
            Mudar senha
          </Button>
          <Button variant="ghost" onClick={() => setModalSairOpen(true)}>
            Sair de todas as sessões
          </Button>
        </div>
      </Card>

      {/* Modal mudar senha */}
      <ModalConfirm
        open={modalSenhaOpen}
        onClose={() => {
          if (!senhaLoading) {
            setModalSenhaOpen(false);
            resetForm();
          }
        }}
        onConfirm={() => {
          // O ModalConfirm onConfirm é chamado pelo botão Confirmar.
          // Submetemos via form pra capturar Enter.
          const form = document.getElementById("form-mudar-senha") as HTMLFormElement | null;
          form?.requestSubmit();
        }}
        loading={senhaLoading}
        title="Mudar senha"
        confirmLabel="Salvar nova senha"
      >
        <form
          id="form-mudar-senha"
          onSubmit={onSubmitSenha}
          className="flex flex-col gap-3"
          noValidate
        >
          <FormField label="Senha atual" required>
            <PasswordInput
              autoComplete="current-password"
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
              disabled={senhaLoading}
            />
          </FormField>
          <FormField
            label="Nova senha"
            hint="Mínimo 8 caracteres, com pelo menos 1 letra e 1 número."
            required
          >
            <PasswordInput
              autoComplete="new-password"
              value={senhaNova}
              onChange={(e) => setSenhaNova(e.target.value)}
              disabled={senhaLoading}
            />
          </FormField>
          <FormField label="Confirmar nova senha" required>
            <PasswordInput
              autoComplete="new-password"
              value={senhaConfirmar}
              onChange={(e) => setSenhaConfirmar(e.target.value)}
              disabled={senhaLoading}
            />
          </FormField>
          {senhaErr && (
            <p
              role="alert"
              className="text-sm text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2"
            >
              {senhaErr}
            </p>
          )}
          {/* botão hidden submit pra requestSubmit() vir aqui */}
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </ModalConfirm>

      {/* Modal sair de todas */}
      <ModalConfirm
        open={modalSairOpen}
        onClose={() => setModalSairOpen(false)}
        onConfirm={onConfirmSair}
        loading={sairLoading}
        title="Sair de todas as sessões?"
        description={
          <>
            Você será desconectado deste e de qualquer outro dispositivo
            onde tenha entrado. Vai precisar fazer login de novo.
          </>
        }
        confirmLabel="Encerrar todas"
        confirmVariant="danger"
      />
    </div>
  );
}
