"use client";

/**
 * Mapa cognitivo — visualização do diagnóstico cognitivo do aluno
 * pra o professor.
 *
 * Histórico:
 * - Fase 3 (commit 75edfcc, 2026-05-03): primeiro draft com
 *   heatmap 5×8 (40 quadrados com IDs tipo "1.5"), cards de lacuna
 *   só com evidência.
 * - Fix Fase 3 (este arquivo, 2026-05-03): 3 problemas resolvidos:
 *   #1 Heatmap reformatado: 5 colunas com nome legível ao lado de
 *      cada descritor (não só ID — IDs sozinhos não comunicavam).
 *   #2 Diversidade nas lacunas prioritárias forçada no backend
 *      (max 2 por competência).
 *   #3 Cards de lacuna ganham 3 seções: 📌 O que é (definição) +
 *      🔍 Evidência + 🎯 Como trabalhar (sugestão pedagógica).
 *
 * Visibilidade: este componente SÓ aparece na tela do professor
 * (`/turma/[id]/aluno/[id]`). Aluno consome correção via WhatsApp.
 */
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { formatModoCorrecao, formatPrazo } from "@/lib/format";
import type {
  DiagnosticoConfianca,
  DiagnosticoDescritor,
  DiagnosticoLacunaEnriquecida,
  DiagnosticoOficinaLivroSugerida,
  DiagnosticoRecente,
  DiagnosticoStatus,
} from "@/types/portal";

interface Props {
  turmaId: string;
  diagnostico: DiagnosticoRecente | null;
}

const COMPETENCIAS = ["C1", "C2", "C3", "C4", "C5"] as const;
type Competencia = (typeof COMPETENCIAS)[number];

const COMPETENCIA_NOME: Record<Competencia, string> = {
  C1: "Norma culta",
  C2: "Tema",
  C3: "Argumentação",
  C4: "Coesão",
  C5: "Proposta",
};

const STATUS_COR: Record<DiagnosticoStatus, string> = {
  dominio: "bg-emerald-500",
  incerto: "bg-amber-500",
  lacuna: "bg-red-500",
};

const STATUS_LABEL: Record<DiagnosticoStatus, string> = {
  dominio: "Domínio",
  incerto: "Incerto",
  lacuna: "Lacuna",
};

const CONFIANCA_LABEL: Record<DiagnosticoConfianca, string> = {
  alta: "Alta",
  media: "Média",
  baixa: "Baixa",
};

/** Trunca string em max chars com reticências. */
function truncar(s: string, max = 100): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}

/** Slug pra anchor do scroll-into-view (lacuna prioritária). */
function lacunaAnchorId(descritorId: string): string {
  return `lacuna-${descritorId.replace(/\./g, "-")}`;
}

/** Item de uma coluna do heatmap (1 descritor). */
function HeatmapItem({
  desc,
  isLacunaPrioritaria,
  turmaId,
}: {
  desc: DiagnosticoDescritor;
  isLacunaPrioritaria: boolean;
  turmaId: string;
}) {
  const handleClick = () => {
    if (isLacunaPrioritaria) {
      // Scrolla até o card detalhado da lacuna prioritária
      const el = document.getElementById(lacunaAnchorId(desc.id));
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      // Highlight visual breve (CSS animation)
      el?.classList.add("ring-2", "ring-ink", "ring-offset-2");
      setTimeout(() => {
        el?.classList.remove("ring-2", "ring-ink", "ring-offset-2");
      }, 1500);
    }
  };

  const Tag = isLacunaPrioritaria ? "button" : "div";
  return (
    <Tag
      type={isLacunaPrioritaria ? "button" : undefined}
      onClick={isLacunaPrioritaria ? handleClick : undefined}
      className={cn(
        "flex items-center gap-2 py-1.5 text-left",
        isLacunaPrioritaria
          ? "cursor-pointer hover:bg-muted rounded px-1 -mx-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink"
          : "px-1 -mx-1",
      )}
      title={
        isLacunaPrioritaria
          ? `Lacuna prioritária — clique pra ver detalhes`
          : `${desc.nome} — ${STATUS_LABEL[desc.status]}`
      }
    >
      <span
        className={cn(
          "inline-block w-4 h-4 rounded shrink-0",
          STATUS_COR[desc.status],
        )}
        aria-hidden="true"
      />
      <span className="flex-1 min-w-0">
        <span className="block text-[13px] leading-tight truncate">
          {desc.nome}
          {isLacunaPrioritaria && (
            <span className="ml-1 text-amber-700" aria-label="Lacuna prioritária">
              ★
            </span>
          )}
        </span>
        <span className="block text-[11px] text-ink-400 font-mono">
          {desc.id}
        </span>
      </span>
    </Tag>
  );
}

/** Coluna de uma competência no heatmap. */
function CompetenciaColuna({
  competencia,
  descritores,
  lacunasPrioritarias,
  turmaId,
}: {
  competencia: Competencia;
  descritores: DiagnosticoDescritor[];
  lacunasPrioritarias: Set<string>;
  turmaId: string;
}) {
  // Filtra descritores dessa competência e ordena por número (1-8)
  const ordenados = useMemo(() => {
    return descritores
      .filter((d) => d.competencia === competencia)
      .sort((a, b) => a.id.localeCompare(b.id));
  }, [descritores, competencia]);

  // Mini-resumo: X em domínio, Y em lacuna (de 8)
  const resumo = useMemo(() => {
    let dominio = 0;
    let lacuna = 0;
    for (const d of ordenados) {
      if (d.status === "dominio") dominio++;
      if (d.status === "lacuna") lacuna++;
    }
    return { dominio, lacuna, total: ordenados.length };
  }, [ordenados]);

  return (
    <div className="flex-1 min-w-0">
      <div className="mb-2 pb-2 border-b border-border">
        <p className="font-display text-sm">
          <span className="text-ink-400 font-mono text-xs mr-1">
            {competencia}
          </span>
          {COMPETENCIA_NOME[competencia]}
        </p>
        <p className="text-[11px] text-ink-400 mt-0.5">
          {resumo.dominio}/{resumo.total} em domínio
          {resumo.lacuna > 0 && (
            <>
              {" · "}
              <span className="text-red-700 font-medium">
                {resumo.lacuna} em lacuna
              </span>
            </>
          )}
        </p>
      </div>
      <ul role="list" className="space-y-0.5">
        {ordenados.map((d) => (
          <li key={d.id}>
            <HeatmapItem
              desc={d}
              isLacunaPrioritaria={lacunasPrioritarias.has(d.id)}
              turmaId={turmaId}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Heatmap principal: 5 colunas (desktop) ou acordeão (mobile). */
function Heatmap({
  descritores,
  lacunasPrioritarias,
  turmaId,
}: {
  descritores: DiagnosticoDescritor[];
  lacunasPrioritarias: Set<string>;
  turmaId: string;
}) {
  const [colunaExpanded, setColunaExpanded] = useState<Competencia | null>(null);

  return (
    <div>
      {/* Desktop: 5 colunas lado a lado */}
      <div className="hidden md:flex gap-4">
        {COMPETENCIAS.map((c) => (
          <CompetenciaColuna
            key={c}
            competencia={c}
            descritores={descritores}
            lacunasPrioritarias={lacunasPrioritarias}
            turmaId={turmaId}
          />
        ))}
      </div>

      {/* Mobile: acordeão (1 expandida por vez) */}
      <div className="md:hidden space-y-2">
        {COMPETENCIAS.map((c) => {
          const isOpen = colunaExpanded === c;
          const dominio = descritores.filter(
            (d) => d.competencia === c && d.status === "dominio",
          ).length;
          const lacuna = descritores.filter(
            (d) => d.competencia === c && d.status === "lacuna",
          ).length;
          return (
            <details
              key={c}
              open={isOpen}
              onToggle={(e) => {
                if ((e.target as HTMLDetailsElement).open) {
                  setColunaExpanded(c);
                } else if (colunaExpanded === c) {
                  setColunaExpanded(null);
                }
              }}
              className="border border-border rounded-lg overflow-hidden"
            >
              <summary className="cursor-pointer flex items-center justify-between px-3 py-2 bg-muted/50 hover:bg-muted">
                <span className="font-display text-sm">
                  <span className="text-ink-400 font-mono text-xs mr-1">{c}</span>
                  {COMPETENCIA_NOME[c]}
                </span>
                <span className="text-[11px] text-ink-400">
                  {dominio} dom · {lacuna > 0 ? (
                    <span className="text-red-700 font-medium">{lacuna} lac</span>
                  ) : (
                    <span>0 lac</span>
                  )}
                </span>
              </summary>
              <div className="px-3 py-2">
                <CompetenciaColuna
                  competencia={c}
                  descritores={descritores}
                  lacunasPrioritarias={lacunasPrioritarias}
                  turmaId={turmaId}
                />
              </div>
            </details>
          );
        })}
      </div>

      {/* Legenda */}
      <div className="flex flex-wrap gap-3 mt-4 text-xs text-ink-400">
        <LegendaSwatch cor="bg-emerald-500" label="Domínio" />
        <LegendaSwatch cor="bg-amber-500" label="Incerto" />
        <LegendaSwatch cor="bg-red-500" label="Lacuna" />
        <span className="inline-flex items-center gap-1.5">
          <span className="text-amber-700">★</span>
          Lacuna prioritária (clique pra detalhes)
        </span>
      </div>
    </div>
  );
}

function LegendaSwatch({ cor, label }: { cor: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("inline-block w-3 h-3 rounded", cor)} />
      {label}
    </span>
  );
}

/** Card detalhado de uma lacuna prioritária com 3 seções. */
function LacunaCardEnriquecido({
  lac,
}: {
  lac: DiagnosticoLacunaEnriquecida;
}) {
  return (
    <Card
      id={lacunaAnchorId(lac.id)}
      className="p-4 transition-all"
    >
      <header className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <Badge variant="warning">{lac.competencia}</Badge>
          <h4 className="font-display text-base mt-1.5 leading-snug">
            {lac.nome}
          </h4>
          <p className="font-mono text-[11px] text-ink-400 mt-0.5">
            {lac.id} · Confiança {CONFIANCA_LABEL[lac.confianca]}
          </p>
        </div>
      </header>

      {/* Seção 1: O que é */}
      <section className="mb-3">
        <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-1">
          📌 O que é
        </p>
        <p className="text-sm leading-relaxed">{lac.definicao_curta}</p>
      </section>

      {/* Seção 2: Evidência no texto */}
      <section className="mb-3">
        <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-1">
          🔍 Evidência no texto
        </p>
        {lac.evidencias.length > 0 ? (
          <p className="text-sm italic text-ink-700 leading-relaxed">
            &ldquo;{truncar(lac.evidencias[0], 200)}&rdquo;
          </p>
        ) : (
          <p className="text-sm italic text-ink-400">
            Sem evidência textual citada — diagnóstico inferiu a lacuna pelo
            que está AUSENTE no texto.
          </p>
        )}
      </section>

      {/* Seção 3: Como trabalhar */}
      <section className="bg-amber-50/40 border border-amber-200 rounded p-3 -mx-1">
        <p className="font-mono text-[11px] uppercase tracking-wider text-amber-700 mb-1">
          🎯 Como trabalhar
        </p>
        <p className="text-sm leading-relaxed">{lac.sugestao_pedagogica}</p>
      </section>
    </Card>
  );
}

export function MapaCognitivo({ turmaId, diagnostico }: Props) {
  if (diagnostico === null) {
    return (
      <section aria-labelledby="mapa-cog-h">
        <h2 id="mapa-cog-h" className="font-display text-xl mb-3">
          Mapa cognitivo
        </h2>
        <Card className="p-6 text-center text-sm text-ink-400">
          <p>
            <strong className="text-ink-700">
              Diagnóstico cognitivo aparece aqui
            </strong>{" "}
            após o aluno enviar uma redação. Última correção sem diagnóstico
            significa que não foi possível processar — clique em{" "}
            <em>Reprocessar avaliação</em> na tabela abaixo.
          </p>
        </Card>
      </section>
    );
  }

  const { professor } = diagnostico;
  const lacunasSet = new Set(professor.lacunas_prioritarias);

  return (
    <section aria-labelledby="mapa-cog-h" className="space-y-6">
      <div className="flex items-baseline justify-between flex-wrap gap-2">
        <h2 id="mapa-cog-h" className="font-display text-xl">
          Mapa cognitivo
        </h2>
        <p className="text-xs text-ink-400 font-mono">
          Diagnóstico de {formatPrazo(diagnostico.criado_em)}
          {diagnostico.modelo ? ` · ${diagnostico.modelo}` : ""}
        </p>
      </div>

      {/* Sub-bloco 1 — Heatmap (5 colunas com nome legível) */}
      <Card className="p-4">
        <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-3">
          Mapa dos 40 descritores observáveis
        </p>
        <Heatmap
          descritores={professor.descritores}
          lacunasPrioritarias={lacunasSet}
          turmaId={turmaId}
        />
      </Card>

      {/* Sub-bloco 2 — Lacunas prioritárias com 3 seções */}
      {professor.lacunas_enriquecidas.length > 0 && (
        <div>
          <h3 className="font-display text-base mb-2">
            Lacunas prioritárias
          </h3>
          <p className="text-xs text-ink-400 mb-3">
            Top {professor.lacunas_enriquecidas.length} lacunas com
            diversidade entre competências (max 2 por C). Cada card tem
            o que é, evidência e sugestão de como trabalhar.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {professor.lacunas_enriquecidas.map((lac) => (
              <LacunaCardEnriquecido key={lac.id} lac={lac} />
            ))}
          </div>
        </div>
      )}

      {/* Sub-bloco 3 — Resumo + Recomendação */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-2">
            📊 Análise
          </p>
          <p className="text-sm leading-relaxed">
            {professor.resumo_qualitativo}
          </p>
        </Card>
        <Card className="p-4 bg-amber-50/40 border-amber-200">
          <p className="font-mono text-[11px] uppercase tracking-wider text-amber-700 mb-2">
            🎯 Recomendação
          </p>
          <p className="text-sm leading-relaxed">
            {professor.recomendacao_breve}
          </p>
        </Card>
      </div>

      {/* Sub-bloco 4 — Atividades sugeridas (banco) */}
      {professor.oficinas_sugeridas.length > 0 && (
        <div>
          <h3 className="font-display text-base mb-2">
            <span aria-label="Avaliáveis pelo Redato" title="Avaliáveis pelo Redato">✅</span>{" "}
            Atividades no Redato
          </h3>
          <p className="text-xs text-ink-400 mb-3">
            Missões já cadastradas no Redato (aluno envia foto via WhatsApp,
            bot corrige). Clique em &ldquo;Criar atividade&rdquo; pra abrir o
            modal de ativação na turma com a missão pré-selecionada.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {professor.oficinas_sugeridas.map((s) => (
              <Card
                key={s.codigo}
                className="p-4 flex flex-col gap-2"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-[11px] text-ink-400">
                    {s.codigo}
                  </span>
                  <Badge variant="neutral">
                    {formatModoCorrecao(s.modo_correcao)}
                  </Badge>
                </div>
                <p className="font-medium text-sm">{s.titulo}</p>
                <p className="text-xs text-ink-400 italic">{s.razao}</p>
                <Link
                  href={`/turma/${turmaId}?aba=atividades&missao=${encodeURIComponent(s.codigo)}`}
                  className="text-xs text-ink underline-offset-4 hover:underline mt-auto"
                >
                  Criar atividade →
                </Link>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Sub-bloco 5 — Oficinas do livro (Fase 5A.1, em revisão) */}
      <OficinasLivroBlock
        oficinas={professor.oficinas_livro_sugeridas}
        statusRevisao={professor.mapeamento_livros_status}
      />
    </section>
  );
}

const TIPO_LABEL: Record<string, string> = {
  conceitual: "📚 Conceitual",
  pratica: "✏️ Prática",
  avaliativa: "🎯 Avaliativa",
  jogo: "🎲 Jogo",
  diagnostico: "🩺 Diagnóstico",
};

const INTENSIDADE_ESTRELAS: Record<string, string> = {
  alta: "★★★",
  media: "★★",
  baixa: "★",
};

function OficinasLivroBlock({
  oficinas,
  statusRevisao,
}: {
  oficinas: DiagnosticoOficinaLivroSugerida[];
  statusRevisao: string | null;
}) {
  if (!oficinas || oficinas.length === 0) {
    return null;
  }
  const showAviso = statusRevisao === "em_revisao";

  return (
    <div>
      <h3 className="font-display text-base mb-2">
        <span aria-label="Oficinas do livro" title="Oficinas do livro">📖</span>{" "}
        Oficinas no livro
      </h3>
      <p className="text-xs text-ink-400 mb-2">
        Oficinas do livro do professor que trabalham as competências em
        lacuna — incluindo atividades conceituais, jogos e exercícios
        não avaliados pelo Redato. Use no planejamento da próxima aula.
      </p>
      {showAviso && (
        <div className="mb-3 inline-flex items-center gap-2 text-[11px] bg-amber-50 border border-amber-200 rounded px-2 py-1 text-amber-900">
          <span aria-hidden="true">⚠️</span>
          <span>
            Sugestões automáticas em revisão pedagógica — confirme antes
            de aplicar
          </span>
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {oficinas.map((o) => {
          const tipoLabel = o.tipo_atividade
            ? TIPO_LABEL[o.tipo_atividade] ?? `📖 ${o.tipo_atividade}`
            : "📖 Oficina";
          const estrelas = INTENSIDADE_ESTRELAS[o.intensidade] ?? "★";
          return (
            <Card
              key={`${o.codigo}-${o.descritor_id}`}
              className="p-4 flex flex-col gap-2"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-[11px] text-ink-400">
                  {o.codigo}
                </span>
                <Badge variant="neutral">{tipoLabel}</Badge>
              </div>
              <p className="font-medium text-sm">{o.titulo}</p>
              <p className="text-xs text-ink-400">
                <span className="text-amber-600" title={`Intensidade: ${o.intensidade}`}>
                  {estrelas}
                </span>{" "}
                <span className="font-mono">{o.descritor_id}</span>
                {o.tem_redato_avaliavel && (
                  <span className="ml-2 text-emerald-700" title="Avaliável pelo Redato">
                    ✅ Redato
                  </span>
                )}
              </p>
              <p className="text-xs text-ink-400 italic line-clamp-3">
                {o.razao}
              </p>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
