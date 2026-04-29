"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { DistribuicaoNotasChart } from "@/components/portal/DistribuicaoNotasChart";
import { TopDetectoresBadges } from "@/components/portal/TopDetectoresBadges";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { ModalConfirm } from "@/components/ui/ModalConfirm";
import {
  formatDateInput,
  formatModoCorrecao,
  formatPrazo,
  formatSerie,
} from "@/lib/format";
import {
  detalheAtividade,
  encerrarAtividade,
  patchAtividade,
} from "@/lib/portal-client";
import { ApiError } from "@/types/api";
import type { AtividadeDetail } from "@/types/portal";

interface Props {
  initial: AtividadeDetail;
}

export function AtividadeDetailView({ initial }: Props) {
  const router = useRouter();
  const [data, setData] = useState<AtividadeDetail>(initial);
  const [editOpen, setEditOpen] = useState(false);
  const [encerrarOpen, setEncerrarOpen] = useState(false);
  const [dataInicio, setDataInicio] = useState(formatDateInput(initial.data_inicio));
  const [dataFim, setDataFim] = useState(formatDateInput(initial.data_fim));
  const [editLoading, setEditLoading] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [encerrarLoading, setEncerrarLoading] = useState(false);

  async function recarregar() {
    try {
      const novo = await detalheAtividade(initial.id);
      setData(novo);
    } catch {
      /* silencioso */
    }
  }

  async function salvarEdicao() {
    setEditErr(null);
    if (!dataInicio || !dataFim) {
      setEditErr("Preencha as duas datas.");
      return;
    }
    if (new Date(dataFim) <= new Date(dataInicio)) {
      setEditErr("A data de fim deve ser depois da data de início.");
      return;
    }
    setEditLoading(true);
    try {
      await patchAtividade(initial.id, {
        data_inicio: new Date(dataInicio).toISOString(),
        data_fim: new Date(dataFim).toISOString(),
      });
      toast.success("Prazo atualizado.");
      setEditOpen(false);
      await recarregar();
    } catch (err) {
      setEditErr((err as ApiError).detail || "Erro ao salvar.");
    } finally {
      setEditLoading(false);
    }
  }

  async function confirmarEncerrar() {
    setEncerrarLoading(true);
    try {
      await encerrarAtividade(initial.id);
      toast.success("Atividade encerrada.");
      setEncerrarOpen(false);
      await recarregar();
    } catch (err) {
      toast.error((err as ApiError).detail || "Erro ao encerrar.");
    } finally {
      setEncerrarLoading(false);
    }
  }

  const variantBadge =
    data.status === "ativa" ? "ativa"
    : data.status === "agendada" ? "agendada"
    : "encerrada";

  const taxaEnvio = data.n_alunos_total > 0
    ? Math.round((data.n_enviados / data.n_alunos_total) * 100)
    : 0;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            Turma {data.turma_codigo} · {formatSerie(data.turma_serie)} ·{" "}
            {data.escola_nome}
          </p>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mt-1">
            Oficina {data.oficina_numero}
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <h1 className="font-display text-3xl">{data.missao_titulo}</h1>
            <Badge variant={variantBadge}>{data.status}</Badge>
          </div>
          <p className="mt-1 text-sm text-ink-400">
            {formatModoCorrecao(data.modo_correcao)}
          </p>
          <p className="mt-2 text-sm">
            <span className="text-ink-400">Janela:</span>{" "}
            {formatPrazo(data.data_inicio)} → {formatPrazo(data.data_fim)}
          </p>
        </div>
        {data.pode_editar && (
          <div className="flex flex-wrap gap-2">
            {/* Acesso à tela de partidas (Fase 2 do jogo). Visível
                pra qualquer atividade — atividades não-jogo terão
                lista vazia, sem custo. */}
            <Link
              href={`/atividade/${data.id}/partidas`}
              className="inline-flex items-center justify-center rounded-md text-sm font-medium px-4 py-2 transition-colors bg-transparent text-ink hover:bg-ink-100 active:bg-ink-200"
            >
              Partidas do jogo
            </Link>
            <Button variant="ghost" onClick={() => setEditOpen(true)}>
              Editar prazo
            </Button>
            {data.status !== "encerrada" && (
              <Button
                variant="primary"
                onClick={() => setEncerrarOpen(true)}
              >
                Encerrar
              </Button>
            )}
          </div>
        )}
      </header>

      {/* Resumo agregado */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
            Envios
          </p>
          <p className="font-display text-3xl mt-1">
            {data.n_enviados}
            <span className="text-ink-400">/{data.n_alunos_total}</span>
          </p>
          <p className="text-sm text-ink-400 mt-1">
            {taxaEnvio}% participaram · {data.n_pendentes} pendente
            {data.n_pendentes !== 1 ? "s" : ""}
          </p>
          <div className="mt-3 h-2 bg-muted rounded overflow-hidden">
            <div
              className="h-full bg-lime"
              style={{ width: `${taxaEnvio}%` }}
              aria-hidden="true"
            />
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Distribuição de notas
          </p>
          <DistribuicaoNotasChart distribuicao={data.distribuicao} />
        </Card>
      </section>

      <section>
        <h2 className="font-display text-base mb-3">
          Detectores acionados (top {data.top_detectores.length})
        </h2>
        <TopDetectoresBadges detectores={data.top_detectores} />
      </section>

      {/* Tabela de envios */}
      <section aria-labelledby="envios-h">
        <h2 id="envios-h" className="font-display text-xl mb-3">
          Envios da turma
        </h2>

        {/* Desktop: tabela */}
        <div className="hidden md:block bg-white border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr className="text-left text-xs uppercase tracking-wider text-ink-400">
                <th className="px-4 py-3 font-medium">Aluno</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Enviado em</th>
                <th className="px-4 py-3 font-medium">Nota</th>
                <th className="px-4 py-3 font-medium">Faixa</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.envios.map((e) => (
                <tr key={e.aluno_turma_id} className="hover:bg-muted">
                  <td className="px-4 py-3 font-medium">{e.aluno_nome}</td>
                  <td className="px-4 py-3">
                    {e.enviado_em ? (
                      <Badge variant="ativa">enviado</Badge>
                    ) : (
                      <Badge variant="encerrada">pendente</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-400 font-mono text-xs">
                    {e.enviado_em ? formatPrazo(e.enviado_em) : "—"}
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    {e.nota_total ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-400 font-mono">
                    {e.faixa === "sem_nota" ? "—" : e.faixa}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {e.tem_feedback && (
                      <Link
                        href={`/atividade/${data.id}/aluno/${e.aluno_turma_id}`}
                        className="text-sm font-medium hover:underline underline-offset-4"
                      >
                        Ver feedback →
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile: cards */}
        <ul className="md:hidden space-y-2">
          {data.envios.map((e) => {
            const conteudo = (
              <div className="block bg-white border border-border rounded-xl p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{e.aluno_nome}</span>
                  {e.enviado_em ? (
                    <Badge variant="ativa">enviado</Badge>
                  ) : (
                    <Badge variant="encerrada">pendente</Badge>
                  )}
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-ink-400">Nota:</span>{" "}
                    <span className="font-semibold text-base">
                      {e.nota_total ?? "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-400">Faixa:</span>{" "}
                    <span className="font-mono">
                      {e.faixa === "sem_nota" ? "—" : e.faixa}
                    </span>
                  </div>
                </div>
                {e.enviado_em && (
                  <p className="text-xs text-ink-400 font-mono mt-2">
                    {formatPrazo(e.enviado_em)}
                  </p>
                )}
              </div>
            );
            return (
              <li key={e.aluno_turma_id}>
                {e.tem_feedback ? (
                  <Link href={`/atividade/${data.id}/aluno/${e.aluno_turma_id}`}>
                    {conteudo}
                  </Link>
                ) : (
                  conteudo
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {/* Modais */}
      <ModalConfirm
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onConfirm={salvarEdicao}
        loading={editLoading}
        title="Editar prazo da atividade"
        description="Alterar as datas afeta o status (agendada/ativa/encerrada) e quando os alunos podem enviar."
        confirmLabel="Salvar"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <FormField label="Início">
            <Input
              type="datetime-local"
              value={dataInicio}
              onChange={(e) => setDataInicio(e.target.value)}
            />
          </FormField>
          <FormField label="Fim">
            <Input
              type="datetime-local"
              value={dataFim}
              onChange={(e) => setDataFim(e.target.value)}
            />
          </FormField>
        </div>
        {editErr && (
          <p role="alert" className="text-sm text-danger mt-2">
            {editErr}
          </p>
        )}
      </ModalConfirm>

      <ModalConfirm
        open={encerrarOpen}
        onClose={() => setEncerrarOpen(false)}
        onConfirm={confirmarEncerrar}
        loading={encerrarLoading}
        title="Encerrar atividade agora?"
        description="O bot vai recusar novos envios desta missão. Você pode reabrir editando o prazo depois."
        confirmLabel="Encerrar"
        confirmVariant="danger"
      />
    </div>
  );
}
