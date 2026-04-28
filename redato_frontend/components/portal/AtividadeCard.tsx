import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { formatModoCorrecao, formatPrazo } from "@/lib/format";
import type { AtividadeListItem } from "@/types/portal";

interface Props {
  atividade: AtividadeListItem;
}

export function AtividadeCard({ atividade }: Props) {
  const variant =
    atividade.status === "ativa"
      ? "ativa"
      : atividade.status === "agendada"
        ? "agendada"
        : "encerrada";
  return (
    <Link
      href={`/atividade/${atividade.id}`}
      className="group block bg-white border border-border rounded-xl p-4 hover:border-ink-400 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Badge variant={variant} className="mb-2">{atividade.status}</Badge>
          <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
            Oficina {atividade.oficina_numero}
          </p>
          <h4 className="font-display text-lg leading-tight group-hover:underline underline-offset-4">
            {atividade.missao_titulo}
          </h4>
          <p className="text-xs text-ink-400 mt-0.5">
            {formatModoCorrecao(atividade.modo_correcao)}
          </p>
        </div>
        <div className="text-right text-xs text-ink-400 shrink-0">
          <p>até</p>
          <p className="text-sm text-ink font-medium">
            {formatPrazo(atividade.data_fim)}
          </p>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-ink-400">
        <span>{atividade.n_envios} envio{atividade.n_envios !== 1 ? "s" : ""}</span>
        {atividade.notificacao_enviada_em && (
          <>
            <span aria-hidden="true">·</span>
            <span>notificada</span>
          </>
        )}
      </div>
    </Link>
  );
}
