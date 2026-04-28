"use client";

import { useMemo, useState } from "react";

import { cn } from "@/lib/cn";

interface Point {
  x: string;        // ISO timestamp ou label
  y: number;        // valor numérico
  label?: string;   // tooltip/sub-label
  faixa?: string;
}

interface Props {
  pontos: Point[];
  /** Escala máxima do eixo Y (ex.: 200 pra Foco, 1000 pra Completo). */
  yMax: number;
  yLabel?: string;
  className?: string;
  /** Altura em pixels. */
  height?: number;
}

/**
 * Line chart simples em SVG (sem dependência externa). Eixo X é
 * cronológico (interpola posições igualmente espaçadas), Y é nota
 * normalizada por `yMax`.
 *
 * Hover destaca o ponto e mostra label + valor.
 */
export function EvolucaoChart({
  pontos,
  yMax,
  yLabel = "Nota",
  className,
  height = 220,
}: Props) {
  const [hovered, setHovered] = useState<number | null>(null);

  const layout = useMemo(() => {
    if (pontos.length === 0) {
      return { paths: "", points: [] as Array<{ x: number; y: number }> };
    }
    const padding = { top: 16, right: 16, bottom: 24, left: 36 };
    const width = 600;
    const innerW = width - padding.left - padding.right;
    const innerH = height - padding.top - padding.bottom;

    const xs = pontos.map((_, i) =>
      pontos.length === 1
        ? padding.left + innerW / 2
        : padding.left + (i / (pontos.length - 1)) * innerW
    );
    const ys = pontos.map(
      (p) => padding.top + (1 - Math.max(0, Math.min(1, p.y / yMax))) * innerH
    );

    const points = xs.map((x, i) => ({ x, y: ys[i] }));
    const paths = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
      .join(" ");

    return { paths, points, width, height, padding };
  }, [pontos, yMax, height]);

  if (pontos.length === 0) {
    return (
      <div
        role="img"
        aria-label="Sem dados de evolução"
        className={cn("text-sm text-ink-400 text-center py-6", className)}
      >
        Sem envios pra plotar.
      </div>
    );
  }

  const { paths, points, padding } = layout as ReturnType<typeof useMemo> & {
    paths: string;
    points: Array<{ x: number; y: number }>;
    width: number;
    height: number;
    padding: { top: number; right: number; bottom: number; left: number };
  };
  const lay = layout as Required<typeof layout> & {
    width: number;
    padding: { top: number; right: number; bottom: number; left: number };
  };

  return (
    <div className={cn("relative", className)} role="img"
         aria-label={`Evolução temporal — eixo Y de 0 a ${yMax}`}>
      <svg
        viewBox={`0 0 ${(lay.width)} ${height}`}
        className="w-full h-auto"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Eixo X */}
        <line
          x1={lay.padding.left} y1={height - lay.padding.bottom}
          x2={lay.width - lay.padding.right} y2={height - lay.padding.bottom}
          stroke="currentColor" strokeWidth="1" className="text-ink-200"
        />
        {/* Eixo Y */}
        <line
          x1={lay.padding.left} y1={lay.padding.top}
          x2={lay.padding.left} y2={height - lay.padding.bottom}
          stroke="currentColor" strokeWidth="1" className="text-ink-200"
        />
        {/* Ticks Y: 0, max/2, max */}
        {[0, yMax / 2, yMax].map((v) => {
          const yPx = lay.padding.top
            + (1 - v / yMax) * (height - lay.padding.top - lay.padding.bottom);
          return (
            <g key={v}>
              <line
                x1={lay.padding.left - 4} y1={yPx}
                x2={lay.padding.left} y2={yPx}
                stroke="currentColor" strokeWidth="1" className="text-ink-200"
              />
              <text
                x={lay.padding.left - 6} y={yPx + 3}
                textAnchor="end"
                className="fill-current text-ink-400"
                fontSize="10" fontFamily="var(--font-mono)"
              >
                {Math.round(v)}
              </text>
            </g>
          );
        })}
        {/* Linha conectando pontos */}
        <path
          d={paths}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-ink"
          strokeLinejoin="round" strokeLinecap="round"
        />
        {/* Pontos */}
        {points.map((p, i) => {
          const isHover = hovered === i;
          return (
            <g key={i}>
              <circle
                cx={p.x} cy={p.y}
                r={isHover ? 6 : 4}
                fill={isHover ? "var(--redato-lime)" : "var(--redato-ink)"}
                stroke="white" strokeWidth="2"
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(i)}
                onBlur={() => setHovered(null)}
                tabIndex={0}
                aria-label={`${pontos[i].label ?? pontos[i].x}: ${pontos[i].y}`}
              />
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hovered !== null && pontos[hovered] && (
        <div
          className={cn(
            "absolute pointer-events-none px-2.5 py-1.5 rounded-md",
            "bg-ink text-white text-xs shadow-card",
          )}
          style={{
            left: `${(points[hovered].x / lay.width) * 100}%`,
            top: `${(points[hovered].y / height) * 100}%`,
            transform: "translate(-50%, -130%)",
          }}
        >
          <div className="font-mono text-[10px] opacity-70">
            {pontos[hovered].label ?? pontos[hovered].x}
          </div>
          <div className="font-semibold">
            {yLabel}: {pontos[hovered].y}
          </div>
          {pontos[hovered].faixa && (
            <div className="text-[10px] opacity-70">{pontos[hovered].faixa}</div>
          )}
        </div>
      )}
    </div>
  );
}
