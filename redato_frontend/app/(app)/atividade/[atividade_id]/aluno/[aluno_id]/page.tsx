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
}

function faixaBadgeVariant(faixa: string) {
  if (faixa === "Excelente") return "ativa" as const;
  if (faixa === "Bom") return "lime" as const;
  if (faixa === "Regular") return "warning" as const;
  if (faixa === "Insuficiente") return "encerrada" as const;
  return "neutral" as const;
}

export default async function FeedbackAlunoPage({ params }: Props) {
  const token = getSessionToken();
  const data = await fetchBackend<EnvioFeedback>(
    `/portal/atividades/${params.atividade_id}/envios/${params.aluno_id}`,
    { bearer: token! },
  );

  const semEnvio = data.enviado_em === null;

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
        <h1 className="font-display text-3xl mt-1">{data.aluno_nome}</h1>
        {!semEnvio && (
          <p className="mt-1 text-sm text-ink-400">
            Enviado em {formatPrazo(data.enviado_em!)}
          </p>
        )}
      </header>

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

        </>
      )}
    </div>
  );
}
