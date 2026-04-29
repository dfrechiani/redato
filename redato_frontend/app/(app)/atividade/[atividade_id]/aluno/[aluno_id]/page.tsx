import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { fetchBackend } from "@/lib/api";
import { getSessionToken } from "@/lib/auth-server";
import { formatMissaoLabel, formatPrazo } from "@/lib/format";
import type { EnvioFeedback } from "@/types/portal";

export const dynamic = "force-dynamic";

interface Props {
  params: { atividade_id: string; aluno_id: string };
  // M9.6 (2026-04-29): `?envio_id=xxx` carrega tentativa específica.
  // Sem o param o backend devolve a mais recente — comportamento
  // padrão pra quem chega pela tela da turma sem clicar em tentativa
  // anterior.
  searchParams?: { envio_id?: string };
}

function faixaBadgeVariant(faixa: string) {
  if (faixa === "Excelente") return "ativa" as const;
  if (faixa === "Bom") return "lime" as const;
  if (faixa === "Regular") return "warning" as const;
  if (faixa === "Insuficiente") return "encerrada" as const;
  return "neutral" as const;
}

export default async function FeedbackAlunoPage({
  params, searchParams,
}: Props) {
  const token = getSessionToken();
  // Monta URL do backend com `?envio_id=xxx` quando presente. O backend
  // valida que o envio pertence a (atividade_id, aluno_id) — se não
  // pertencer, devolve 404. Encoded URI evita injection caso o param
  // venha mal-formado.
  const envioIdParam = searchParams?.envio_id;
  const url =
    `/portal/atividades/${params.atividade_id}/envios/${params.aluno_id}` +
    (envioIdParam ? `?envio_id=${encodeURIComponent(envioIdParam)}` : "");
  const data = await fetchBackend<EnvioFeedback>(url, { bearer: token! });

  const semEnvio = data.enviado_em === null;
  // É tentativa anterior se o envio_id renderizado não é o mais recente.
  // Backend ordena `tentativas_anteriores` desc por tentativa_n, e o
  // mais recente = o de maior tentativa_n. Se a atual não é a maior,
  // estamos vendo histórico.
  const maxTentativa = Math.max(
    data.tentativa_n,
    ...data.tentativas_anteriores.map((t) => t.tentativa_n),
    1,
  );
  const vendoTentativaAnterior = data.tentativa_n < maxTentativa;
  const temMultiplasTentativas = data.tentativa_total > 1;

  return (
    <div className="space-y-6">
      <nav aria-label="breadcrumb" className="text-sm text-ink-400">
        <Link
          href={`/atividade/${data.atividade_id}`}
          className="hover:text-ink underline-offset-4 hover:underline"
        >
          ← Voltar pra atividade
        </Link>
      </nav>

      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          {formatMissaoLabel({
            oficina_numero: data.oficina_numero,
            titulo: data.missao_titulo,
            modo_correcao: data.modo_correcao,
          })}
        </p>
        <h1 className="font-display text-3xl mt-1">
          {data.aluno_nome}
          {temMultiplasTentativas && (
            // Badge inline pro professor saber que essa tela tem
            // histórico antes mesmo de scrollar pra ver o expansor.
            <span className="ml-3 align-middle">
              <Badge variant="neutral">
                Tentativa {data.tentativa_n} de {data.tentativa_total}
              </Badge>
            </span>
          )}
        </h1>
        {!semEnvio && (
          <p className="mt-1 text-sm text-ink-400">
            Enviado em {formatPrazo(data.enviado_em!)}
          </p>
        )}
      </header>

      {/* Banner de "vendo tentativa anterior" — amarelo pra contrastar
          e botão pra voltar pro padrão (drop do `?envio_id` da URL). */}
      {vendoTentativaAnterior && (
        <div className="rounded border border-amber-300 bg-amber-50 px-4 py-3 flex items-center justify-between gap-3">
          <p className="text-sm text-amber-900">
            👁️ Você está vendo a <strong>tentativa {data.tentativa_n}</strong>
            {" "}— versão antiga. A tentativa mais recente é a {maxTentativa}.
          </p>
          <Link
            href={
              `/atividade/${params.atividade_id}/aluno/${params.aluno_id}`
            }
            className="shrink-0 text-sm font-medium text-amber-900 underline-offset-4 hover:underline"
          >
            Voltar pra mais recente
          </Link>
        </div>
      )}

      {semEnvio ? (
        <Card>
          <p className="text-ink-400">
            Este aluno ainda não enviou redação pra esta atividade.
          </p>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Foto + Transcrição (mesma coluna no desktop) */}
            <div className="lg:col-span-2 space-y-4">
              <Card>
                <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
                  Foto da redação
                </p>
                {data.foto_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={data.foto_url}
                    alt={`Redação de ${data.aluno_nome}`}
                    className="w-full rounded border border-border bg-muted object-contain max-h-[600px]"
                  />
                ) : (
                  // Mensagem diagnóstica baseada em foto_status — ajuda
                  // professor entender por que a foto sumiu sem precisar
                  // olhar logs do servidor.
                  <p className="text-sm text-ink-400">
                    {data.foto_status === "file_missing" ? (
                      <>
                        Arquivo da foto sumiu do servidor (provavelmente
                        perdido em deploy). Aluno precisa reenviar.
                      </>
                    ) : data.foto_status === "not_persisted" ? (
                      <>
                        Foto não foi salva pelo bot. O envio chegou ao
                        portal mas o download do WhatsApp pode ter
                        falhado. Aluno precisa reenviar.
                      </>
                    ) : (
                      <>Foto não disponível.</>
                    )}
                  </p>
                )}
                {data.ocr_quality_issues.length > 0 && (
                  <ul className="mt-3 text-xs text-amber-800 list-disc list-inside">
                    {data.ocr_quality_issues.map((iss, i) => (
                      <li key={i}>{iss}</li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card>
                <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
                  Transcrição
                </p>
                {data.texto_transcrito ? (
                  <p className="text-sm leading-relaxed whitespace-pre-line font-body">
                    {data.texto_transcrito}
                  </p>
                ) : (
                  <p className="text-sm text-ink-400">
                    Transcrição não disponível.
                  </p>
                )}
              </Card>
            </div>

            {/* Nota total + faixas */}
            <div className="space-y-4">
              <Card>
                <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
                  Nota total
                </p>
                <p className="font-display text-5xl mt-1">
                  {data.nota_total ?? "—"}
                  <span className="text-ink-400 text-2xl font-body">/1000</span>
                </p>
              </Card>

              <Card>
                <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
                  Competências
                </p>
                {data.faixas.length === 0 ? (
                  <p className="text-sm text-ink-400">Não disponíveis.</p>
                ) : (
                  <ul className="space-y-2">
                    {data.faixas.map((f) => (
                      <li
                        key={f.competencia}
                        className="flex items-center justify-between gap-2"
                      >
                        <span className="font-mono text-sm">{f.competencia}</span>
                        <span className="flex items-center gap-2">
                          <Badge variant={faixaBadgeVariant(f.faixa)}>
                            {f.faixa}
                          </Badge>
                          <span className="font-semibold tabular-nums w-10 text-right">
                            {f.nota ?? "—"}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </div>

          {/* Análise da redação (M9.4 — substitui "Audit pedagógico").
              Renderiza estrutura discreta quando o output moderno
              tem pontos_fortes/pontos_fracos. Senão, fallback pra
              prosa_completa de outputs legacy. */}
          {(data.analise_da_redacao.pontos_fortes.length > 0 ||
            data.analise_da_redacao.pontos_fracos.length > 0 ||
            data.analise_da_redacao.padrao_falha ||
            data.analise_da_redacao.transferencia ||
            data.analise_da_redacao.prosa_completa) && (
            <Card>
              <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
                Análise da redação
              </p>

              {data.analise_da_redacao.pontos_fortes.length > 0 && (
                <section className="mb-4">
                  <h3 className="font-semibold text-sm mb-2">
                    📌 Pontos fortes
                  </h3>
                  <ul className="space-y-1.5 list-disc list-inside text-sm leading-relaxed">
                    {data.analise_da_redacao.pontos_fortes.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </section>
              )}

              {data.analise_da_redacao.pontos_fracos.length > 0 && (
                <section className="mb-4">
                  <h3 className="font-semibold text-sm mb-2">
                    ⚠️ Pontos fracos
                  </h3>
                  <ul className="space-y-1.5 list-disc list-inside text-sm leading-relaxed">
                    {data.analise_da_redacao.pontos_fracos.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </section>
              )}

              {data.analise_da_redacao.padrao_falha && (
                <section className="mb-4">
                  <h3 className="font-semibold text-sm mb-2">
                    🎯 Padrão de falha
                  </h3>
                  <p className="text-sm leading-relaxed">
                    {data.analise_da_redacao.padrao_falha}
                  </p>
                </section>
              )}

              {data.analise_da_redacao.transferencia && (
                <section className="mb-4">
                  <h3 className="font-semibold text-sm mb-2">
                    🔁 Transferência para outras competências
                  </h3>
                  <p className="text-sm leading-relaxed">
                    {data.analise_da_redacao.transferencia}
                  </p>
                </section>
              )}

              {/* Fallback pra outputs legacy que ainda têm prosa
                  monolítica em audit_completo, ou seeds antigos com
                  top-level audit/feedback. Só mostra quando NÃO tem
                  estrutura nova (evita duplicar). */}
              {data.analise_da_redacao.prosa_completa &&
                data.analise_da_redacao.pontos_fortes.length === 0 &&
                data.analise_da_redacao.pontos_fracos.length === 0 && (
                <p className="text-sm leading-relaxed whitespace-pre-line">
                  {data.analise_da_redacao.prosa_completa}
                </p>
              )}
            </Card>
          )}

          {data.detectores.length > 0 && (
            <Card>
              <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-2">
                Detectores acionados
              </p>
              <ul className="space-y-1.5">
                {data.detectores.map((d) => (
                  <li key={d.detector} className="text-sm">
                    <span className="font-mono text-xs bg-amber-50 text-amber-900 px-2 py-0.5 rounded">
                      {d.detector
                        .replace(/^(flag|detector|alerta|aviso)_/i, "")
                        .replace(/_/g, " ")}
                    </span>
                    {d.detalhe && (
                      <span className="text-ink-400 ml-2">— {d.detalhe}</span>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Histórico de tentativas (M9.6). Native <details> evita
              precisar de Client Component só pra um expansor. Cada
              item é um Link — clica e o servidor recarrega com
              `?envio_id=xxx`. Ordem desc por tentativa_n vem do
              backend. */}
          {data.tentativas_anteriores.length > 0 && (
            <Card>
              <details className="group">
                <summary className="cursor-pointer list-none flex items-center justify-between">
                  <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
                    Tentativas anteriores ({data.tentativas_anteriores.length})
                  </p>
                  <span className="text-ink-400 text-sm transition-transform group-open:rotate-180">
                    ▾
                  </span>
                </summary>
                <ul className="mt-3 space-y-2 divide-y divide-border">
                  {data.tentativas_anteriores.map((t) => (
                    <li key={t.envio_id} className="pt-2 first:pt-0">
                      <Link
                        href={
                          `/atividade/${params.atividade_id}` +
                          `/aluno/${params.aluno_id}` +
                          `?envio_id=${encodeURIComponent(t.envio_id)}`
                        }
                        className="block hover:bg-muted/50 -mx-2 px-2 py-2 rounded transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-mono text-xs text-ink-400">
                            Tentativa {t.tentativa_n}
                          </span>
                          <span className="flex items-center gap-2">
                            {t.nota_total !== null && (
                              <span className="font-semibold tabular-nums text-sm">
                                {t.nota_total}/1000
                              </span>
                            )}
                            <span className="text-xs text-ink-400">
                              {formatPrazo(t.enviado_em)}
                            </span>
                          </span>
                        </div>
                        {t.texto_curto && (
                          <p className="text-xs text-ink-400 italic line-clamp-2">
                            “{t.texto_curto}”
                          </p>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </details>
            </Card>
          )}

        </>
      )}
    </div>
  );
}
