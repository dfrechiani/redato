/**
 * Helpers de formatação puros (sem "use client") — funcionam em
 * Server Components e em Client Components.
 *
 * Espelha `redato_backend/portal/formatters.py` (PDF + email do backend
 * usam os mesmos rótulos). Quando atualizar aqui, atualizar lá também.
 */

const _SERIE_HUMANA: Record<string, string> = {
  "1S": "1ª série",
  "2S": "2ª série",
  "3S": "3ª série",
};

/** "1S" → "1ª série". Fallback: devolve o input se não conhecido. */
export function formatSerie(serie: string | null | undefined): string {
  if (!serie) return "";
  return _SERIE_HUMANA[serie] ?? serie;
}

const _MODO_HUMANO: Record<string, string> = {
  foco_c1: "Foco C1",
  foco_c2: "Foco C2",
  foco_c3: "Foco C3",
  foco_c4: "Foco C4",
  foco_c5: "Foco C5",
  completo_parcial: "Correção parcial",
  completo: "Correção 5 competências",
};

/** "foco_c3" → "Foco C3". Fallback humanizado pra modos novos. */
export function formatModoCorrecao(modo: string | null | undefined): string {
  if (!modo) return "";
  if (modo in _MODO_HUMANO) return _MODO_HUMANO[modo];
  return modo
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface MissaoLabelInput {
  oficina_numero?: number | null;
  titulo?: string | null;
  modo_correcao?: string | null;
}

/**
 * Constrói "Oficina 10 — Jogo Dissertativo (Foco C3)".
 * Sem `modo_correcao`: omite parênteses.
 * Sem `oficina_numero`: usa apenas título.
 * Sem `titulo`: fallback "Oficina N".
 */
export function formatMissaoLabel(input: MissaoLabelInput): string {
  const { oficina_numero, titulo, modo_correcao } = input;
  let base: string;
  if (oficina_numero && titulo) {
    base = `Oficina ${oficina_numero} — ${titulo}`;
  } else if (oficina_numero) {
    base = `Oficina ${oficina_numero}`;
  } else if (titulo) {
    base = titulo;
  } else {
    return "Missão";
  }
  if (modo_correcao) {
    return `${base} (${formatModoCorrecao(modo_correcao)})`;
  }
  return base;
}


export function formatPrazo(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function formatPrazoCurto(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export function formatDateInput(iso: string): string {
  // YYYY-MM-DDTHH:mm pra <input type="datetime-local">
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
