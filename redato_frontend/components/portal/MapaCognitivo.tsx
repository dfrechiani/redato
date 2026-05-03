"use client";

/**
 * Mapa cognitivo — visualização do diagnóstico cognitivo do aluno
 * pra o professor (Fase 3, 2026-05-03).
 *
 * 4 sub-blocos:
 *   1. Heatmap dos 40 descritores (5 colunas × 8 linhas, hover/tap
 *      mostra tooltip)
 *   2. Lacunas prioritárias (top 5 cards horizontais com evidência)
 *   3. Resumo + Recomendação (texto da Fase 2)
 *   4. Oficinas sugeridas (cards com botão "Criar atividade" deeplink)
 *
 * Estado vazio: prop `diagnostico` null → mensagem "diagnóstico
 * aparece aqui após o aluno enviar redação".
 *
 * Visibilidade: este componente SÓ aparece na tela do professor
 * (`/turma/[id]/aluno/[id]`). Aluno não tem acesso — não há frontend
 * dedicado pro aluno (consome correção via WhatsApp).
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
  DiagnosticoRecente,
  DiagnosticoStatus,
} from "@/types/portal";

interface Props {
  turmaId: string;
  diagnostico: DiagnosticoRecente | null;
}

const COMPETENCIAS = ["C1", "C2", "C3", "C4", "C5"] as const;
type Competencia = (typeof COMPETENCIAS)[number];

const STATUS_COR: Record<DiagnosticoStatus, string> = {
  dominio: "bg-emerald-500 text-white",   // verde #10B981
  incerto: "bg-amber-500 text-white",     // amarelo #F59E0B
  lacuna: "bg-red-500 text-white",        // vermelho #EF4444
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

/** Extrai número do descritor (1..8) a partir de "C{n}.{nnn}". */
function indiceDescritor(id: string): number | null {
  const m = id.match(/^C[1-5]\.(\d{3})$/);
  if (!m) return null;
  return Number(m[1]);
}

/** Trunca evidência pra primeira linha do tooltip (100 chars). */
function truncar(s: string, max = 100): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}

/**
 * Heatmap 5×8 dos 40 descritores. Cada célula é um botão clicável
 * que abre tooltip embaixo (estado simples — 1 célula selecionada
 * por vez, second click fecha).
 */
function Heatmap({
  descritores,
}: {
  descritores: DiagnosticoDescritor[];
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Index por (competencia, idx) → descritor. Linhas faltantes ficam
  // como cinza (sem dado).
  const grid = useMemo(() => {
    const map: Record<string, DiagnosticoDescritor> = {};
    for (const d of descritores) {
      map[d.id] = d;
    }
    return map;
  }, [descritores]);

  const selected = selectedId ? grid[selectedId] : null;

  return (
    <div>
      {/* Header com nomes das competências */}
      <div className="grid grid-cols-5 gap-1 mb-1">
        {COMPETENCIAS.map((c) => (
          <div
            key={c}
            className="text-center font-mono text-[11px] uppercase tracking-wider text-ink-400"
          >
            {c}
          </div>
        ))}
      </div>

      {/* Grid 5×8 */}
      <div className="grid grid-cols-5 gap-1">
        {COMPETENCIAS.map((comp) =>
          Array.from({ length: 8 }, (_, i) => {
            const num = i + 1;
            const id = `${comp}.${String(num).padStart(3, "0")}`;
            const desc = grid[id];
            const status = desc?.status;
            const isSelected = selectedId === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() =>
                  setSelectedId(isSelected ? null : id)
                }
                title={desc ? `${id} — ${STATUS_LABEL[desc.status]}` : `${id} — sem dado`}
                aria-label={`Descritor ${id}${desc ? ", status " + STATUS_LABEL[desc.status] : ""}`}
                aria-pressed={isSelected}
                className={cn(
                  "aspect-square rounded font-mono text-[10px]",
                  "flex items-center justify-center transition-all",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink",
                  status
                    ? STATUS_COR[status]
                    : "bg-gray-300 text-gray-600",
                  isSelected
                    ? "ring-2 ring-offset-2 ring-ink scale-110"
                    : "hover:scale-105",
                )}
              >
                {comp.slice(1)}.{num}
              </button>
            );
          })
        )}
      </div>

      {/* Legenda */}
      <div className="flex flex-wrap gap-3 mt-3 text-xs text-ink-400">
        <LegendaSwatch cor="bg-emerald-500" label="Domínio" />
        <LegendaSwatch cor="bg-amber-500" label="Incerto" />
        <LegendaSwatch cor="bg-red-500" label="Lacuna" />
        <LegendaSwatch cor="bg-gray-300" label="Sem dado" />
      </div>

      {/* Tooltip do selecionado */}
      {selected && (
        <Card className="mt-3 p-3 border-ink-700">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="font-mono text-xs text-ink-400">{selected.id}</span>
            <span className={cn(
              "font-mono text-[11px] px-1.5 py-0.5 rounded",
              STATUS_COR[selected.status],
            )}>
              {STATUS_LABEL[selected.status]}
            </span>
            <span className="text-xs text-ink-400">
              · Confiança: {CONFIANCA_LABEL[selected.confianca]}
            </span>
          </div>
          {selected.evidencias.length > 0 ? (
            <ul className="text-sm space-y-1">
              {selected.evidencias.map((ev, i) => (
                <li key={i} className="italic text-ink-700">
                  &ldquo;{truncar(ev)}&rdquo;
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-400 italic">
              Sem evidência textual (status inferido sem citação direta).
            </p>
          )}
        </Card>
      )}
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

/** Card horizontal de uma lacuna prioritária (top 5). */
function LacunaCard({ desc }: { desc: DiagnosticoDescritor }) {
  const competencia = desc.id.slice(0, 2);
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <Badge variant="warning">{competencia}</Badge>
        <span className="font-mono text-[11px] text-ink-400 uppercase tracking-wider">
          {desc.id}
        </span>
      </div>
      {desc.evidencias.length > 0 ? (
        <p className="text-sm italic text-ink-700 mb-3 line-clamp-3">
          &ldquo;{truncar(desc.evidencias[0], 180)}&rdquo;
        </p>
      ) : (
        <p className="text-sm italic text-ink-400 mb-3">
          Sem evidência textual citada.
        </p>
      )}
      <p className="text-xs text-ink-400">
        Confiança: <strong>{CONFIANCA_LABEL[desc.confianca]}</strong>
      </p>
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
  const lacunasComoDescs = professor.descritores.filter((d) =>
    professor.lacunas_prioritarias.includes(d.id),
  );
  // Preserva ordem de lacunas_prioritarias (que vem do LLM)
  const lacunasOrdenadas = professor.lacunas_prioritarias
    .map((id) => lacunasComoDescs.find((d) => d.id === id))
    .filter((x): x is DiagnosticoDescritor => x !== undefined);

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

      {/* Sub-bloco 1 — Heatmap */}
      <Card className="p-4">
        <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-3">
          Heatmap dos 40 descritores
        </p>
        <Heatmap descritores={professor.descritores} />
      </Card>

      {/* Sub-bloco 2 — Lacunas prioritárias */}
      {lacunasOrdenadas.length > 0 && (
        <div>
          <h3 className="font-display text-base mb-2">
            Lacunas prioritárias
          </h3>
          <p className="text-xs text-ink-400 mb-3">
            Top {lacunasOrdenadas.length} dos pontos onde o aluno precisa de
            mais atenção, ordenadas por impacto pedagógico.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {lacunasOrdenadas.map((d) => (
              <LacunaCard key={d.id} desc={d} />
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

      {/* Sub-bloco 4 — Oficinas sugeridas */}
      {professor.oficinas_sugeridas.length > 0 && (
        <div>
          <h3 className="font-display text-base mb-2">
            Oficinas sugeridas
          </h3>
          <p className="text-xs text-ink-400 mb-3">
            Atividades da série do aluno que trabalham as competências em
            lacuna. Clique em &ldquo;Criar atividade&rdquo; pra abrir o
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
    </section>
  );
}
