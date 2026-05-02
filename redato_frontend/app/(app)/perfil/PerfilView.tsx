"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { ModalConfirm } from "@/components/ui/ModalConfirm";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { useAuth } from "@/hooks/useAuth";
import { validarSenhaLocal } from "@/lib/auth-client";
import {
  desvincularTelefone,
  meDetalhe,
  mudarSenha,
  sairTodasSessoes,
  vincularTelefone,
} from "@/lib/portal-client";
import { ApiError, type AuthenticatedUser } from "@/types/api";

// Regex E.164 simples (mesma do backend): "+" + 10 a 15 dígitos.
const TELEFONE_E164_RE = /^\+\d{10,15}$/;

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

  // M10 — Telefone WhatsApp (só pra professor). Estado local — fetch
  // inicial via /auth/me detalhe pra pegar telefone + lgpd_aceito_em
  // (não cabem em useAuth zustand sem mexer no shape do AuthenticatedUser).
  const [telefoneAtual, setTelefoneAtual] = useState<string | null>(null);
  const [telefoneInput, setTelefoneInput] = useState("");
  const [telefoneErr, setTelefoneErr] = useState<string | null>(null);
  const [telefoneLoading, setTelefoneLoading] = useState(false);
  const [lgpdAceitoEm, setLgpdAceitoEm] = useState<string | null>(null);
  const [modalDesvincularOpen, setModalDesvincularOpen] = useState(false);

  useEffect(() => {
    if (user.papel !== "professor") return;
    let cancel = false;
    meDetalhe()
      .then((me) => {
        if (cancel) return;
        setTelefoneAtual(me.telefone ?? null);
        setLgpdAceitoEm(me.lgpd_aceito_em ?? null);
      })
      .catch(() => {
        // Silencioso — se /auth/me falhar, card simplesmente não aparece
        // ou aparece sem dados. Toast aqui seria ruído (não é erro do
        // usuário).
      });
    return () => { cancel = true; };
  }, [user.papel]);

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

  // M10 — vincular telefone WhatsApp
  async function onSubmitTelefone(e: FormEvent) {
    e.preventDefault();
    setTelefoneErr(null);
    const tel = telefoneInput.trim();
    if (!TELEFONE_E164_RE.test(tel)) {
      setTelefoneErr(
        "Use formato E.164: +55 + DDD + número, ex: +5561912345678",
      );
      return;
    }
    setTelefoneLoading(true);
    try {
      const res = await vincularTelefone(tel);
      setTelefoneAtual(res.telefone);
      setLgpdAceitoEm(null); // novo telefone exige novo aceite LGPD
      setTelefoneInput("");
      toast.success(
        "Telefone vinculado. No WhatsApp você receberá um aviso ao "
        + "usar pela primeira vez.",
        { duration: 7000 },
      );
    } catch (err) {
      const msg = (err as ApiError).detail || "Erro ao vincular.";
      setTelefoneErr(msg);
    } finally {
      setTelefoneLoading(false);
    }
  }

  async function onConfirmDesvincular() {
    setTelefoneLoading(true);
    try {
      await desvincularTelefone();
      setTelefoneAtual(null);
      setLgpdAceitoEm(null);
      toast.success("Telefone desvinculado.");
    } catch (err) {
      toast.error((err as ApiError).detail || "Erro ao desvincular.");
    } finally {
      setTelefoneLoading(false);
      setModalDesvincularOpen(false);
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

      {user.papel === "professor" && (
        <Card>
          <h2 className="font-display text-lg mb-1">
            Telefone WhatsApp
          </h2>
          <p className="text-sm text-ink-400 mb-4">
            Vincule um telefone pra acessar o dashboard via WhatsApp
            (consultar turmas, alunos e atividades por mensagem).
          </p>

          {telefoneAtual ? (
            <div className="space-y-3">
              <div className="flex items-baseline gap-3 flex-wrap">
                <span className="font-mono text-xs uppercase tracking-wider text-ink-400">
                  Vinculado:
                </span>
                <span className="text-base font-semibold">
                  {telefoneAtual}
                </span>
                {lgpdAceitoEm ? (
                  <span className="text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    LGPD aceito
                  </span>
                ) : (
                  <span className="text-xs text-amber-800 bg-amber-50 px-2 py-0.5 rounded">
                    Aguardando aceite LGPD
                  </span>
                )}
              </div>
              {!lgpdAceitoEm && (
                <p className="text-xs text-ink-400">
                  Mande qualquer mensagem pelo WhatsApp e responda &quot;sim&quot;
                  ao aviso pra ativar o dashboard.
                </p>
              )}
              <Button
                variant="ghost"
                onClick={() => setModalDesvincularOpen(true)}
                disabled={telefoneLoading}
              >
                Desvincular
              </Button>
            </div>
          ) : (
            <form
              onSubmit={onSubmitTelefone}
              className="flex flex-col gap-3"
              noValidate
            >
              <FormField
                label="Telefone"
                hint="Formato E.164: +55 + DDD + número (ex: +5561912345678)"
                error={telefoneErr ?? undefined}
              >
                <Input
                  type="tel"
                  value={telefoneInput}
                  onChange={(e) => setTelefoneInput(e.target.value)}
                  placeholder="+5561912345678"
                  disabled={telefoneLoading}
                />
              </FormField>
              <div>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={telefoneLoading}
                >
                  {telefoneLoading ? "Salvando…" : "Salvar"}
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}

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

      {/* M10 — Modal desvincular telefone WhatsApp */}
      <ModalConfirm
        open={modalDesvincularOpen}
        onClose={() => !telefoneLoading && setModalDesvincularOpen(false)}
        onConfirm={onConfirmDesvincular}
        loading={telefoneLoading}
        title="Desvincular telefone do WhatsApp?"
        description={
          <>
            Você não vai mais receber comandos do dashboard pelo WhatsApp.
            Pode vincular outro telefone depois.
          </>
        }
        confirmLabel="Desvincular"
        confirmVariant="danger"
      />
    </div>
  );
}
