/**
 * Diff por palavras entre dois textos pra UI do professor (Fase 2 passo 7a).
 *
 * Usa diff-match-patch (Google) com pré-tokenização: palavras viram
 * "characters" sintéticos, dmp roda diff em cima desse alfabeto, e o
 * resultado é re-mapeado pra palavras. Greater granularity que
 * diff-match-patch nativo (que opera em chars — bagunça visual em
 * texto corrente).
 *
 * Output: array de tuplas [op, text] com op ∈ {-1, 0, 1}:
 *   -1 = removido (existe só em textA)
 *    0 = igual (presente em ambos)
 *    1 = adicionado (existe só em textB)
 *
 * Caller renderiza:
 * - Coluna esquerda (textA, "texto montado"): trechos op=-1 em vermelho
 *   riscado; op=0 neutro
 * - Coluna direita (textB, "reescrita autoral"): trechos op=1 em verde
 *   destacado; op=0 neutro
 */

import DiffMatchPatch from "diff-match-patch";


/** Quebra texto em tokens — palavras, pontuação, whitespace mantidos
 *  como itens separados. `\S+` pega palavra+pontuação grudada
 *  ("não" / "saúde,"); `\s+` pega blocos de whitespace
 *  preservando quebras de linha. */
export function tokenize(text: string): string[] {
  const matches = text.match(/\S+|\s+/g);
  return matches ?? [];
}


/** Tupla [op, text] do diff-match-patch (op em -1, 0, 1). Re-exposta
 *  aqui pro caller não precisar importar diff-match-patch direto. */
export type DiffOp = -1 | 0 | 1;
export type DiffTuple = [DiffOp, string];


/** Limite de chars combinados acima do qual emitimos warning.
 *  diff-match-patch escala bem até alguns MB, mas pra UI de partida
 *  esperamos ~350-2000 chars por texto. Sinaliza se algo escapou. */
const _MAX_CHARS_WARN = 5000;


/** Diff por palavras entre `textA` e `textB`. Internamente:
 * 1. Tokeniza ambos os textos
 * 2. Mapeia cada token único pra um char sintético do BMP (Basic
 *    Multilingual Plane) — lib trabalha em chars, mas tratamos
 *    palavras como unidade
 * 3. Roda diff_main + diff_cleanupSemantic em cima dos charsA/B
 * 4. Re-mapeia chars de volta pra palavras
 *
 * Limite prático: pré-tokenização cabe ~50K palavras únicas no BMP
 * (16-bit). Pro caso de uso (textos de 200-2000 chars) sobra muito.
 */
export function diffByWords(
  textA: string, textB: string,
): DiffTuple[] {
  if (textA.length + textB.length > _MAX_CHARS_WARN) {
    // Não bloqueia — só sinaliza pra Daniel investigar caso veja em
    // prod. UI continua funcional.
    if (typeof console !== "undefined") {
      console.warn(
        `[diff-words] textos combinados de ${textA.length + textB.length} ` +
        `chars excedem ${_MAX_CHARS_WARN}. Diff funciona mas vale checar ` +
        `o caso de uso — esperávamos ~350-2000 chars por reescrita.`,
      );
    }
  }

  const tokensA = tokenize(textA);
  const tokensB = tokenize(textB);

  // Mapeia cada token único pra um char Unicode privado. Começamos
  // em 0xE000 (Private Use Area do BMP) pra evitar conflito com
  // chars normais que possam aparecer nos textos. PUA tem ~6400 slots
  // — sobra muito pra textos de partida.
  const tokenToChar: Map<string, string> = new Map();
  let nextCodePoint = 0xE000;

  function tokenChar(t: string): string {
    const existing = tokenToChar.get(t);
    if (existing !== undefined) return existing;
    const c = String.fromCharCode(nextCodePoint++);
    tokenToChar.set(t, c);
    return c;
  }

  const charsA = tokensA.map(tokenChar).join("");
  const charsB = tokensB.map(tokenChar).join("");

  const dmp = new DiffMatchPatch.diff_match_patch();
  // Timeout default é 1s; nosso caso de uso não chega perto. Mas
  // explícito = ler mais fácil.
  dmp.Diff_Timeout = 1.0;
  const diffs = dmp.diff_main(charsA, charsB);
  // cleanupSemantic agrupa edições adjacentes em chunks legíveis
  // (ex.: "abc" → "xyz" vira 1 remoção + 1 adição em vez de inter-
  // calado char por char). Crítico pra UX — sem isso o output fica
  // poluído.
  dmp.diff_cleanupSemantic(diffs);

  // Inverte o map char → token. PUA chars únicos no Map garantem
  // sem colisão.
  const charToToken: Map<string, string> = new Map();
  for (const [t, c] of tokenToChar.entries()) {
    charToToken.set(c, t);
  }

  // Reconstrói os trechos: pra cada [op, charsString], mapeia cada
  // char de volta pro token original e concatena.
  return diffs.map(([op, chars]: [number, string]): DiffTuple => {
    const text = chars
      .split("")
      .map((c) => charToToken.get(c) ?? c)
      .join("");
    return [op as DiffOp, text];
  });
}


/** Calcula percentual do textB que é AUTORAL — i.e., chars que
 *  existem só em textB (op=1) sobre o tamanho total de textB.
 *
 *  Usamos esse cálculo localmente em vez de só ler `transformacao_cartas`
 *  do redato_output porque:
 *  1. transformacao_cartas é qualitativo (Claude avalia bandas)
 *  2. % autoral é mecânico (dá pra mostrar consistência: se Claude
 *     diz transformacao=80 mas só 10% do texto difere, há divergência
 *     útil de surfacear)
 *
 *  Retorna 0 se textB vazio.
 */
export function pctAutoral(diffs: DiffTuple[]): number {
  let charsAdded = 0;
  let charsTotalB = 0;
  for (const [op, text] of diffs) {
    if (op !== -1) {
      charsTotalB += text.length;
    }
    if (op === 1) {
      charsAdded += text.length;
    }
  }
  if (charsTotalB === 0) return 0;
  return Math.round((charsAdded / charsTotalB) * 100);
}
