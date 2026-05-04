"use client";

/**
 * Diagnóstico cognitivo da turma — proposta D (storytelling acionável,
 * 2026-05-04 fix UX da Fase 4).
 *
 * Substitui o layout original (heatmap + 4 sub-blocos pesados) por
 * 3 áreas:
 *   1. Header compacto: título + cobertura
 *   2. Narrativa principal: 1 frase + 3 listas de cards (Trabalhar
 *      agora / Esta semana / Este mês)
 *   3. Accordion fechado por default: heatmap detalhado dos 40
 *      descritores + cards de sugestão pedagógica (UI antiga, agora
 *      escondida) — extraído pra `HeatmapDetalhado.tsx`
 *
 * Decisões de design (Daniel):
 * - Heatmap não some — fica disponível, mas não é o primeiro thing
 *   que o professor vê. Information overload original era 40 quadrados
 *   colorindo simultaneamente sem contexto.
 * - Cards de "agora" são os únicos com CTA forte (botão "Criar
 *   atividade"). "Semana" e "Mês" são consultivos.
 * - Cores das bordas dos cards seguem a urgência: vermelho/amarelo/
 *   verde — sinaliza temporalidade sem precisar reler.
 *
 * Estado vazio:
 * - 0 alunos diagnosticados → callout "Aguardando primeira redação"
 * - <30% cobertura → narrativa pede mais envios, sem cards
 *
 * Visibilidade: aba Dashboard da página da turma (mesmo lugar da
 * Fase 4). Aluno não tem rota.
 */
import Link from "next/link";
import { useEffect, useState } from "react";

import { HeatmapDetalhado } from "@/components/portal/HeatmapDetalhado";
import { Card } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { cn } from "@/lib/cn";
import { formatModoCorrecao, formatPrazo } from "@/lib/format";
import { diagnosticoAgregadoTurma } from "@/lib/portal-client";
import { ApiError } from "@/types/api";
import type {
  DiagnosticoAgregado,
  DiagnosticoCardAcao,
} from "@/types/portal";

interface Props {
  turmaId: string;
}

const COBERTURA_MIN_AVISO = 50;
const COBERTURA_MIN_PARCIAL = 3;

// ──────────────────────────────────────────────────────────────────────
// Estilo por urgência
// ──────────────────────────────────────────────────────────────────────

const URGENCIA_BORDER: Record<string, string> = {
  alta: "border-red-300",
  media: "border-amber-300",
  baixa: "border-emerald-300",
};

const URGENCIA_BG: Record<string, string> = {
  alta: "bg-red-50/40",
  media: "bg-amber-50/40",
  baixa: "bg-emerald-50/40",
};

const URGENCIA_LABEL_COR: Record<string, string> = {
  alta: "text-red-700",
  media: "text-amber-700",
  baixa: "text-emerald-700",
};

const URGENCIA_HEADER_BADGE: Record<string, { emoji: string; label: string }> = {
  alta: { emoji: "🔴", label: "TRABALHAR AGORA" },
  media: { emoji: "🟡", label: "ESTA SEMANA" },
  baixa: { emoji: "🟢", label: "ESTE MÊS" },
};

// ──────────────────────────────────────────────────────────────────────
// Sub-componentes
// ──────────────────────────────────────────────────────────────────────

/** Header compacto: título + cobertura + barrinha + aviso opcional. */
function Header({ data }: { data: DiagnosticoAgregado }) {
  const { turma, atualizado_em } = data;
  const cobertura =
    turma.total_alunos > 0
      ? Math.round((turma.alunos_com_diagnostico / turma.total_alunos) * 100)
      : 0;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-lg">
          📊 Diagnóstico da turma {turma.codigo}
        </h3>
        {atualizado_em && (
          <p className="text-xs text-ink-400 font-mono">
            Atualizado em {formatPrazo(atualizado_em)}
          </p>
        )}
      </div>
      <p className="text-sm text-ink-400 mt-1">
        <strong className="text-ink-700">
          {turma.alunos_com_diagnostico}
        </strong>{" "}
        de {turma.total_alunos} alunos diagnosticados ({cobertura}%)
      </p>

      {/* Barra compacta */}
      <div
        className="h-1.5 bg-muted rounded-full overflow-hidden mt-2"
        aria-label={`Cobertura ${cobertura}%`}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all",
            cobertura >= COBERTURA_MIN_AVISO
              ? "bg-emerald-500"
              : "bg-amber-500",
          )}
          style={{ width: `${cobertura}%` }}
        />
      </div>

      {/* Avisos só quando relevantes — não polui o header */}
      {turma.alunos_com_diagnostico > 0 &&
        turma.alunos_com_diagnostico < COBERTURA_MIN_PARCIAL && (
          <p className="text-xs text-amber-800 mt-2">
            ⚠️ Diagnóstico em formação — análise estatística fica
            confiável a partir de 3+ alunos.
          </p>
        )}
    </div>
  );
}

/** Card de ação. Renderização compacta com borda colorida pela urgência.
 *  Botão "Criar atividade" só aparece quando urgencia=alta + tem oficina. */
function CardAcao({
  card,
  turmaId,
}: {
  card: DiagnosticoCardAcao;
  turmaId: string;
}) {
  const border = URGENCIA_BORDER[card.urgencia] ?? "border-border";
  const bg = URGENCIA_BG[card.urgencia] ?? "";
  const showCTA = card.urgencia === "alta" && card.oficina_sugerida;

  return (
    <Card
      className={cn(
        "p-4 flex flex-col gap-2 border-l-4",
        border,
        bg,
      )}
    >
      <h5 className="font-display text-sm leading-snug">{card.titulo}</h5>
      <p className="text-xs text-ink-700 leading-relaxed">{card.descricao}</p>
      {showCTA && card.oficina_sugerida && (
        <div className="flex items-center gap-3 mt-1 text-xs">
          <Link
            href={`/turma/${turmaId}?aba=atividades&missao=${encodeURIComponent(card.oficina_sugerida.codigo)}`}
            className="text-ink underline-offset-4 hover:underline font-medium"
          >
            📝 Criar atividade
          </Link>
          <span className="text-ink-400 font-mono">
            {card.oficina_sugerida.codigo}{" "}
            <span className="ml-1 text-[10px] uppercase">
              ({formatModoCorrecao(card.oficina_sugerida.modo_correcao)})
            </span>
          </span>
        </div>
      )}
    </Card>
  );
}

/** Bloco de uma das 3 categorias temporais (agora/semana/mês). */
function CategoriaAcoes({
  urgencia,
  cards,
  turmaId,
}: {
  urgencia: "alta" | "media" | "baixa";
  cards: DiagnosticoCardAcao[];
  turmaId: string;
}) {
  if (!cards || cards.length === 0) return null;
  const header = URGENCIA_HEADER_BADGE[urgencia];
  const corLabel = URGENCIA_LABEL_COR[urgencia];

  return (
    <div>
      <p
        className={cn(
          "font-mono text-[11px] uppercase tracking-wider font-semibold mb-2",
          corLabel,
        )}
      >
        {header.emoji} {header.label}
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {cards.map((c, i) => (
          <CardAcao
            key={`${urgencia}-${i}-${c.titulo}`}
            card={c}
            turmaId={turmaId}
          />
        ))}
      </div>
    </div>
  );
}

/** Accordion expansível com o heatmap detalhado dos 40 descritores. */
function AccordionHeatmap({
  turmaId,
  data,
}: {
  turmaId: string;
  data: DiagnosticoAgregado;
}) {
  return (
    <details className="group border border-border rounded-lg overflow-hidden">
      <summary className="cursor-pointer flex items-center justify-between px-4 py-3 hover:bg-muted bg-muted/50">
        <span className="font-display text-sm">
          Ver mapa completo dos 40 descritores
        </span>
        <span className="text-ink-400 transition-transform group-open:rotate-180">
          ▼
        </span>
      </summary>
      <div className="p-4 border-t border-border">
        <HeatmapDetalhado turmaId={turmaId} agregado={data} />
      </div>
    </details>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Componente principal
// ──────────────────────────────────────────────────────────────────────

export function DiagnosticoTurma({ turmaId }: Props) {
  const [data, setData] = useState<DiagnosticoAgregado | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    diagnosticoAgregadoTurma(turmaId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setError((err as ApiError).detail);
      });
    return () => {
      cancelled = true;
    };
  }, [turmaId]);

  if (error) {
    return (
      <Card className="text-sm text-danger p-4">
        Erro ao carregar diagnóstico agregado: {error}
      </Card>
    );
  }
  if (!data) {
    return (
      <Card className="flex items-center justify-center gap-3 py-10">
        <LoadingSpinner size={20} />
        <span className="text-sm text-ink-400">
          Carregando diagnóstico da turma…
        </span>
      </Card>
    );
  }

  const { turma, narrativa } = data;

  // Estado vazio: 0 alunos diagnosticados
  if (turma.alunos_com_diagnostico === 0) {
    return (
      <section aria-labelledby="diag-turma-h" className="space-y-3">
        <Header data={data} />
        <Card className="p-6 text-center text-sm text-ink-400">
          <p>
            <strong className="text-ink-700">
              Nenhum diagnóstico ainda.
            </strong>{" "}
            Quando alunos enviarem redações via WhatsApp, o
            diagnóstico coletivo aparece aqui — mostra quais
            competências a turma toda precisa reforçar.
          </p>
        </Card>
      </section>
    );
  }

  const temAcoes =
    narrativa.acoes_agora.length > 0 ||
    narrativa.acoes_semana.length > 0 ||
    narrativa.acoes_mes.length > 0;

  return (
    <section aria-labelledby="diag-turma-h" className="space-y-5">
      <Header data={data} />

      {/* Narrativa principal — frase storytelling em destaque */}
      <Card className="p-5">
        <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-2">
          🎯 O que sua turma precisa agora
        </p>
        <p className="text-base leading-relaxed text-ink-700">
          {narrativa.narrativa_principal}
        </p>
      </Card>

      {/* 3 categorias temporais de cards */}
      {temAcoes && (
        <div className="space-y-5">
          <CategoriaAcoes
            urgencia="alta"
            cards={narrativa.acoes_agora}
            turmaId={turmaId}
          />
          <CategoriaAcoes
            urgencia="media"
            cards={narrativa.acoes_semana}
            turmaId={turmaId}
          />
          <CategoriaAcoes
            urgencia="baixa"
            cards={narrativa.acoes_mes}
            turmaId={turmaId}
          />
        </div>
      )}

      {!temAcoes && turma.alunos_com_diagnostico >= COBERTURA_MIN_PARCIAL && (
        <Card className="p-4 text-center text-sm text-ink-400">
          Nenhum descritor crítico (≥30% alunos com lacuna) nos
          dados atuais. Continue acompanhando perfis individuais.
        </Card>
      )}

      {/* Accordion fechado por default — heatmap detalhado fica aqui */}
      <AccordionHeatmap turmaId={turmaId} data={data} />
    </section>
  );
}
